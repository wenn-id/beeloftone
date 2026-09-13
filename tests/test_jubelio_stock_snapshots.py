import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from unittest import TestCase

from beeloft.store import Store
import test_production as production_tests


class JubelioStockSnapshotTest(TestCase):
    setUp=production_tests.ProductionTest.setUp
    post=production_tests.ProductionTest.post

    def map_product(self, product=None, external_id='item-42', external_sku='JUB-LUNA-M'):
        product=product or self.product
        return self.post(f"/api/products/{product['id']}/external-mappings/jubelio",{
            'expected_revision':0,'action':'mapped','external_id':external_id,
            'external_sku':external_sku,'reason':'Mapping untuk snapshot stok'})

    def body(self, items=None, **changes):
        finished=datetime.now(timezone.utc).replace(microsecond=0)
        body={'started_at':(finished-timedelta(minutes=2)).isoformat(),'finished_at':finished.isoformat(),
              'snapshot_at':finished.isoformat(),'external_cursor':'stock-page-12',
              'reason':'Snapshot stok penuh dari connector Jubelio','items':items if items is not None else [{
                  'external_id':'item-42','external_sku':'JUB-LUNA-M','sellable_quantity':10,
                  'reserved_quantity':2}]}
        body.update(changes);return body

    def test_import_creates_truthful_run_and_reconciliation(self):
        self.map_product()
        payload=self.body()
        batch=self.post('/api/integrations/jubelio/finished-goods-snapshots',payload,key='stock-once')
        self.assertEqual(batch,self.post('/api/integrations/jubelio/finished-goods-snapshots',payload,key='stock-once'))
        self.assertEqual((batch['sync_status'],batch['records_read'],batch['records_written'],
                          batch['accepted_count'],batch['rejected_count']),('succeeded',1,1,1,0))
        run=self.client.get('/api/integration-sync-runs/'+batch['sync_run_id']).json()
        self.assertEqual((run['scope'],run['status'],run['records_written']),('finished_goods','succeeded',1))
        report=self.client.get('/api/integrations/jubelio/finished-goods-reconciliation').json()
        self.assertEqual(report['summary'],{'mapped_products':1,'matched':0,'mismatched':1,
                         'missing_from_snapshot':0,'quarantined':0})
        row=report['items'][0]
        self.assertEqual((row['beeloft_available_quantity'],row['jubelio_available_quantity'],
                          row['variance_quantity'],row['status']),(0,8,8,'mismatched'))

    def test_unknown_and_inconsistent_identifiers_are_quarantined(self):
        self.map_product()
        items=[{'external_id':'item-42','external_sku':'WRONG-SKU','sellable_quantity':5,'reserved_quantity':0},
               {'external_id':'unknown','external_sku':'UNKNOWN','sellable_quantity':3,'reserved_quantity':1}]
        batch=self.post('/api/integrations/jubelio/finished-goods-snapshots',self.body(items))
        self.assertEqual((batch['sync_status'],batch['records_read'],batch['records_written'],
                          batch['accepted_count'],batch['rejected_count']),('failed',2,0,0,2))
        self.assertEqual({row['issue'] for row in batch['quarantine']},{'unmapped','mapping_mismatch'})
        health=self.client.get('/api/integrations').json()['systems'][0]
        self.assertEqual(health['health'],'failed')
        report=self.client.get('/api/integrations/jubelio/finished-goods-reconciliation').json()
        self.assertEqual((report['summary']['missing_from_snapshot'],report['summary']['quarantined']),(1,2))

    def test_validation_roles_listing_and_missing_records(self):
        self.map_product()
        for items in ([{'external_id':'a','external_sku':'A','sellable_quantity':1,'reserved_quantity':2}],
                      [{'external_id':'a','external_sku':'A','sellable_quantity':1,'reserved_quantity':0},
                       {'external_id':'a','external_sku':'B','sellable_quantity':1,'reserved_quantity':0}],
                      [{'external_id':'a','external_sku':'same','sellable_quantity':1,'reserved_quantity':0},
                       {'external_id':'b','external_sku':'SAME','sellable_quantity':1,'reserved_quantity':0}]):
            self.post('/api/integrations/jubelio/finished-goods-snapshots',self.body(items),status=422)
        for changes in ({'started_at':'2026-09-13T10:00:00'},
                        {'started_at':'2026-09-13T11:00:00+00:00','finished_at':'2026-09-13T10:00:00+00:00'},
                        {'items':[{'external_id':'a','external_sku':'A','sellable_quantity':True,'reserved_quantity':0}]},
                        {'unexpected':'field'}):
            self.post('/api/integrations/jubelio/finished-goods-snapshots',self.body(**changes),status=422)
        for account in (self.operator,self.viewer):
            self.post('/api/integrations/jubelio/finished-goods-snapshots',self.body(),
                      api_key=account['api_key'],status=403)
        batch=self.post('/api/integrations/jubelio/finished-goods-snapshots',self.body(items=[]))
        self.assertEqual(self.client.get('/api/integrations/jubelio/finished-goods-snapshots').json()[0]['id'],batch['id'])
        self.assertEqual(self.client.get('/api/integrations/jubelio/finished-goods-snapshots/'+batch['id']).status_code,200)
        self.assertEqual(self.client.get('/api/integrations/jubelio/finished-goods-snapshots/missing').status_code,404)
        for account in (self.operator,self.viewer):
            self.assertEqual(self.client.get('/api/integrations/jubelio/finished-goods-reconciliation',
                headers={'X-API-Key':account['api_key']}).status_code,200)

    def test_rollback_immutability_backup_and_migration_from_34(self):
        self.map_product()
        with self.app.state.store.transaction(write=True) as db:
            db.execute("""CREATE TRIGGER fail_stock_snapshot BEFORE INSERT ON requests
                WHEN NEW.key='fail-stock-snapshot' BEGIN SELECT RAISE(ABORT,'fail'); END""")
        self.post('/api/integrations/jubelio/finished-goods-snapshots',self.body(),key='fail-stock-snapshot',status=409)
        self.assertEqual(self.client.get('/api/integrations/jubelio/finished-goods-snapshots').json(),[])
        self.assertEqual(self.client.get('/api/integration-sync-runs').json(),[])
        with self.app.state.store.transaction(write=True) as db: db.execute('DROP TRIGGER fail_stock_snapshot')
        batch=self.post('/api/integrations/jubelio/finished-goods-snapshots',self.body())
        with closing(sqlite3.connect(self.path)) as db:
            for table in ('jubelio_stock_snapshot_batches','jubelio_stock_snapshot_items'):
                for action in (f'UPDATE {table} SET id=id',f'DELETE FROM {table}'):
                    with self.assertRaises(sqlite3.IntegrityError): db.execute(action)
        backup=self.path.with_name('jubelio-stock-backup.sqlite3');self.app.state.store.backup(backup)
        self.assertEqual(Store(backup).jubelio_stock_snapshot(batch['id'])['items'][0]['external_sku'],'JUB-LUNA-M')
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('DROP TABLE jubelio_stock_quarantine_items');db.execute('DROP TABLE jubelio_stock_snapshot_items')
            db.execute('DROP TABLE jubelio_stock_snapshot_batches');db.execute('PRAGMA user_version=34');db.commit()
        Store(self.path);Store(self.path)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],37)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM jubelio_stock_snapshot_batches').fetchone()[0],0)
