import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from unittest import TestCase

from beeloft.store import Store
import test_production as production_tests


class JubelioReturnSnapshotTest(TestCase):
    setUp=production_tests.ProductionTest.setUp
    post=production_tests.ProductionTest.post

    def map_product(self, product=None, external_id='item-42', external_sku='JUB-LUNA-M'):
        product=product or self.product
        return self.post(f"/api/products/{product['id']}/external-mappings/jubelio",{
            'expected_revision':0,'action':'mapped','external_id':external_id,
            'external_sku':external_sku,'reason':'Mapping untuk snapshot retur'})

    def record(self, **changes):
        record={'external_return_id':'return-42','external_return_reference':'JUB-RETURN-0042',
                'external_order_id':'order-42','external_order_reference':'JUB-ORDER-0042',
                'marketplace':'Shopee','status':'received','updated_at':'2026-09-13T11:00:00+07:00',
                'refund_amount':'0','lines':[{'external_id':'item-42','external_sku':'JUB-LUNA-M','quantity':2}]}
        record.update(changes);return record

    def body(self, returns=None, **changes):
        finished=datetime.now(timezone.utc).replace(microsecond=0)
        body={'started_at':(finished-timedelta(minutes=2)).isoformat(),'finished_at':finished.isoformat(),
              'snapshot_at':finished.isoformat(),'external_cursor':'returns-page-6',
              'reason':'Snapshot retur penuh dari connector Jubelio',
              'returns':returns if returns is not None else [self.record()]}
        body.update(changes);return body

    def test_import_creates_truthful_run_and_return_summary(self):
        self.map_product()
        refunded=self.record(external_return_id='refund-43',external_return_reference='JUB-RETURN-0043',
            status='refunded',refund_amount='120000',
            lines=[{'external_id':'item-42','external_sku':'JUB-LUNA-M','quantity':1}])
        payload=self.body([self.record(),refunded])
        batch=self.post('/api/integrations/jubelio/return-snapshots',payload,key='returns-once')
        self.assertEqual(batch,self.post('/api/integrations/jubelio/return-snapshots',payload,key='returns-once'))
        self.assertEqual((batch['sync_status'],batch['records_read'],batch['records_written'],
                          batch['accepted_count'],batch['rejected_count']),('succeeded',2,2,2,0))
        run=self.client.get('/api/integration-sync-runs/'+batch['sync_run_id']).json()
        self.assertEqual((run['scope'],run['status'],run['records_written']),('returns','succeeded',2))
        report=self.client.get('/api/integrations/jubelio/return-summary').json()
        self.assertEqual(report['summary'],{'accepted_returns':2,'quarantined_returns':0,'received_units':3,
            'refunded_amount':'120000.00','requested':0,'in_transit':0,'received':1,'refunded':1,
            'rejected':0,'cancelled':0})
        self.assertEqual(report['marketplaces'],[{'marketplace':'Shopee','returns':2,'received_units':3,
                                                 'refunded_amount':'120000.00'}])
        self.assertEqual(report['products'][0]['received_units'],3)

    def test_unsafe_identifier_quarantines_whole_returns(self):
        self.map_product()
        returns=[self.record(external_return_id='bad-pair',external_return_reference='BAD-PAIR',
                    lines=[{'external_id':'item-42','external_sku':'WRONG','quantity':1}]),
                 self.record(external_return_id='unknown',external_return_reference='UNKNOWN',marketplace='<Tokopedia>',
                    lines=[{'external_id':'missing','external_sku':'<UNKNOWN>','quantity':3}])]
        batch=self.post('/api/integrations/jubelio/return-snapshots',self.body(returns))
        self.assertEqual((batch['sync_status'],batch['records_read'],batch['records_written'],
                          batch['accepted_count'],batch['rejected_count']),('failed',2,0,0,2))
        self.assertEqual({row['issue'] for row in batch['quarantine']},{'unmapped','mapping_mismatch'})
        self.assertEqual({row['total_quantity'] for row in batch['quarantine']},{1,3})
        health=self.client.get('/api/integrations').json()['systems'][0]
        scope=next(row for row in health['scopes'] if row['scope']=='returns')
        self.assertEqual((scope['health'],scope['latest_run']['records_written']),('failed',0))

    def test_validation_roles_listing_and_missing_records(self):
        self.map_product();duplicate=self.record()
        for returns in ([duplicate,dict(duplicate)],
                        [self.record(lines=[])],
                        [self.record(lines=[{'external_id':'item-42','external_sku':'JUB-LUNA-M','quantity':True}])],
                        [self.record(lines=[{'external_id':'a','external_sku':'SAME','quantity':1},
                                            {'external_id':'b','external_sku':'same','quantity':1}])],
                        [self.record(updated_at='2026-09-13T11:00:00')],
                        [self.record(status='closed')],
                        [self.record(status='refunded',refund_amount='0')],
                        [self.record(status='received',refund_amount='1')],
                        [self.record(status='refunded',refund_amount='1000000000000.01')]):
            self.post('/api/integrations/jubelio/return-snapshots',self.body(returns),status=422)
        for changes in ({'started_at':'2026-09-13T10:00:00'},
                        {'started_at':'2026-09-13T11:00:00+00:00','finished_at':'2026-09-13T10:00:00+00:00'},
                        {'unexpected':'field'}):
            self.post('/api/integrations/jubelio/return-snapshots',self.body(**changes),status=422)
        for account in (self.operator,self.viewer):
            self.post('/api/integrations/jubelio/return-snapshots',self.body(),
                      api_key=account['api_key'],status=403)
        batch=self.post('/api/integrations/jubelio/return-snapshots',self.body(returns=[]))
        listed=self.client.get('/api/integrations/jubelio/return-snapshots').json()[0]
        self.assertEqual(listed['id'],batch['id']);self.assertNotIn('returns',listed)
        self.assertEqual(self.client.get('/api/integrations/jubelio/return-snapshots/'+batch['id']).status_code,200)
        self.assertEqual(self.client.get('/api/integrations/jubelio/return-snapshots/missing').status_code,404)
        for account in (self.operator,self.viewer):
            self.assertEqual(self.client.get('/api/integrations/jubelio/return-summary',
                headers={'X-API-Key':account['api_key']}).status_code,200)

    def test_rollback_immutability_backup_and_migration_from_36(self):
        self.map_product()
        with self.app.state.store.transaction(write=True) as db:
            db.execute("""CREATE TRIGGER fail_return_snapshot BEFORE INSERT ON requests
                WHEN NEW.key='fail-return-snapshot' BEGIN SELECT RAISE(ABORT,'fail'); END""")
        self.post('/api/integrations/jubelio/return-snapshots',self.body(),key='fail-return-snapshot',status=409)
        self.assertEqual(self.client.get('/api/integrations/jubelio/return-snapshots').json(),[])
        self.assertEqual(self.client.get('/api/integration-sync-runs').json(),[])
        with self.app.state.store.transaction(write=True) as db: db.execute('DROP TRIGGER fail_return_snapshot')
        returns=[self.record(),self.record(external_return_id='bad',external_return_reference='BAD',
            lines=[{'external_id':'bad','external_sku':'BAD','quantity':1}])]
        batch=self.post('/api/integrations/jubelio/return-snapshots',self.body(returns))
        with closing(sqlite3.connect(self.path)) as db:
            for table in ('jubelio_return_snapshot_batches','jubelio_return_snapshot_records',
                          'jubelio_return_snapshot_lines','jubelio_return_quarantine_records'):
                for action in (f'UPDATE {table} SET id=id',f'DELETE FROM {table}'):
                    with self.assertRaises(sqlite3.IntegrityError): db.execute(action)
        backup=self.path.with_name('jubelio-return-backup.sqlite3');self.app.state.store.backup(backup)
        self.assertEqual(Store(backup).jubelio_return_snapshot(batch['id'])['returns'][0]['external_return_id'],'return-42')
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('DROP TABLE jubelio_return_quarantine_records');db.execute('DROP TABLE jubelio_return_snapshot_lines')
            db.execute('DROP TABLE jubelio_return_snapshot_records');db.execute('DROP TABLE jubelio_return_snapshot_batches')
            db.execute('PRAGMA user_version=36');db.commit()
        Store(self.path);Store(self.path)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],47)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM jubelio_return_snapshot_batches').fetchone()[0],0)
