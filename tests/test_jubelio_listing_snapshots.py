import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from unittest import TestCase

from beeloft.store import Store
import test_production as production_tests


class JubelioListingSnapshotTest(TestCase):
    setUp=production_tests.ProductionTest.setUp
    post=production_tests.ProductionTest.post

    def map_product(self, external_id='item-42', external_sku='JUB-LUNA-M'):
        return self.post(f"/api/products/{self.product['id']}/external-mappings/jubelio",{
            'expected_revision':0,'action':'mapped','external_id':external_id,
            'external_sku':external_sku,'reason':'Mapping untuk snapshot listing'})

    def record(self, **changes):
        record={'external_listing_id':'listing-42','listing_reference':'SHP-LUNA-M',
                'external_id':'item-42','external_sku':'JUB-LUNA-M','marketplace':'Shopee',
                'listing_title':'Luna Dress Navy M','status':'active','listed_price':'120000',
                'updated_at':'2026-09-13T11:00:00+07:00'}
        record.update(changes);return record

    def body(self, listings=None, **changes):
        finished=datetime.now(timezone.utc).replace(microsecond=0)
        body={'started_at':(finished-timedelta(minutes=2)).isoformat(),'finished_at':finished.isoformat(),
              'snapshot_at':finished.isoformat(),'external_cursor':'listings-page-8',
              'reason':'Snapshot listing penuh dari connector Jubelio',
              'listings':listings if listings is not None else [self.record()]}
        body.update(changes);return body

    def test_import_creates_truthful_run_and_listing_summary(self):
        self.map_product()
        inactive=self.record(external_listing_id='listing-43',listing_reference='TOKO-LUNA-M',
                             marketplace='Tokopedia',status='inactive',listed_price='130000')
        payload=self.body([self.record(),inactive])
        batch=self.post('/api/integrations/jubelio/listing-snapshots',payload,key='listings-once')
        self.assertEqual(batch,self.post('/api/integrations/jubelio/listing-snapshots',payload,key='listings-once'))
        self.assertEqual((batch['sync_status'],batch['records_read'],batch['records_written'],
                          batch['accepted_count'],batch['rejected_count']),('succeeded',2,2,2,0))
        run=self.client.get('/api/integration-sync-runs/'+batch['sync_run_id']).json()
        self.assertEqual((run['scope'],run['status'],run['records_written']),('listings','succeeded',2))
        report=self.client.get('/api/integrations/jubelio/listing-summary').json()
        self.assertEqual(report['summary'],{'accepted_listings':2,'quarantined_listings':0,
            'active_products':1,'active':1,'inactive':1,'draft':0,'blocked':0,
            'min_active_price':'120000.00','max_active_price':'120000.00'})
        self.assertEqual(report['marketplaces'],[
            {'marketplace':'Shopee','listings':1,'active':1,'inactive':0,'draft':0,'blocked':0,'active_products':1},
            {'marketplace':'Tokopedia','listings':1,'active':0,'inactive':1,'draft':0,'blocked':0,'active_products':0}])

    def test_unsafe_identifier_quarantines_each_listing(self):
        self.map_product()
        listings=[self.record(external_listing_id='bad-pair',listing_reference='BAD-PAIR',external_sku='WRONG'),
                  self.record(external_listing_id='unknown',listing_reference='UNKNOWN',marketplace='<Tokopedia>',
                              external_id='missing',external_sku='<UNKNOWN>',status='blocked')]
        batch=self.post('/api/integrations/jubelio/listing-snapshots',self.body(listings))
        self.assertEqual((batch['sync_status'],batch['records_read'],batch['records_written'],
                          batch['accepted_count'],batch['rejected_count']),('failed',2,0,0,2))
        self.assertEqual({row['issue'] for row in batch['quarantine']},{'unmapped','mapping_mismatch'})
        health=self.client.get('/api/integrations').json()['systems'][0]
        scope=next(row for row in health['scopes'] if row['scope']=='listings')
        self.assertEqual((scope['health'],scope['latest_run']['records_written']),('failed',0))

    def test_validation_roles_listing_and_missing_records(self):
        self.map_product();duplicate=self.record()
        cases=([duplicate,dict(duplicate)],
               [duplicate,self.record(external_listing_id='second',marketplace='shopee',listing_reference='shp-luna-m')],
               [self.record(listed_price='0')],[self.record(listed_price='1000000000000.01')],
               [self.record(updated_at='2026-09-13T11:00:00')],[self.record(status='published')],
               [self.record(unexpected='field')])
        for listings in cases:
            self.post('/api/integrations/jubelio/listing-snapshots',self.body(listings),status=422)
        for changes in ({'started_at':'2026-09-13T10:00:00'},
                        {'started_at':'2026-09-13T11:00:00+00:00','finished_at':'2026-09-13T10:00:00+00:00'},
                        {'unexpected':'field'}):
            self.post('/api/integrations/jubelio/listing-snapshots',self.body(**changes),status=422)
        for account in (self.operator,self.viewer):
            self.post('/api/integrations/jubelio/listing-snapshots',self.body(),
                      api_key=account['api_key'],status=403)
        batch=self.post('/api/integrations/jubelio/listing-snapshots',self.body(listings=[]))
        listed=self.client.get('/api/integrations/jubelio/listing-snapshots').json()[0]
        self.assertEqual(listed['id'],batch['id']);self.assertNotIn('listings',listed)
        self.assertEqual(self.client.get('/api/integrations/jubelio/listing-snapshots/'+batch['id']).status_code,200)
        self.assertEqual(self.client.get('/api/integrations/jubelio/listing-snapshots/missing').status_code,404)
        for account in (self.operator,self.viewer):
            response=self.client.get('/api/integrations/jubelio/listing-summary',
                headers={'X-API-Key':account['api_key']})
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json()['summary']['accepted_listings'],0)

    def test_rollback_immutability_backup_and_migration_from_37(self):
        self.map_product()
        with self.app.state.store.transaction(write=True) as db:
            db.execute("""CREATE TRIGGER fail_listing_snapshot BEFORE INSERT ON requests
                WHEN NEW.key='fail-listing-snapshot' BEGIN SELECT RAISE(ABORT,'fail'); END""")
        self.post('/api/integrations/jubelio/listing-snapshots',self.body(),key='fail-listing-snapshot',status=409)
        self.assertEqual(self.client.get('/api/integrations/jubelio/listing-snapshots').json(),[])
        self.assertEqual(self.client.get('/api/integration-sync-runs').json(),[])
        with self.app.state.store.transaction(write=True) as db: db.execute('DROP TRIGGER fail_listing_snapshot')
        listings=[self.record(),self.record(external_listing_id='bad',listing_reference='BAD',
            external_id='bad',external_sku='BAD')]
        batch=self.post('/api/integrations/jubelio/listing-snapshots',self.body(listings))
        with closing(sqlite3.connect(self.path)) as db:
            for table in ('jubelio_listing_snapshot_batches','jubelio_listing_snapshot_records',
                          'jubelio_listing_quarantine_records'):
                for action in (f'UPDATE {table} SET id=id',f'DELETE FROM {table}'):
                    with self.assertRaises(sqlite3.IntegrityError): db.execute(action)
        backup=self.path.with_name('jubelio-listing-backup.sqlite3');self.app.state.store.backup(backup)
        self.assertEqual(Store(backup).jubelio_listing_snapshot(batch['id'])['listings'][0]['external_listing_id'],
                         'listing-42')
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('DROP TABLE jubelio_listing_quarantine_records')
            db.execute('DROP TABLE jubelio_listing_snapshot_records')
            db.execute('DROP TABLE jubelio_listing_snapshot_batches')
            db.execute('PRAGMA user_version=37');db.commit()
        Store(self.path);Store(self.path)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],52)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM jubelio_listing_snapshot_batches').fetchone()[0],0)
