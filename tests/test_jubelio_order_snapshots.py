import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from unittest import TestCase

from beeloft.store import Store
import test_production as production_tests


class JubelioOrderSnapshotTest(TestCase):
    setUp=production_tests.ProductionTest.setUp
    post=production_tests.ProductionTest.post

    def map_product(self, product=None, external_id='item-42', external_sku='JUB-LUNA-M'):
        product=product or self.product
        return self.post(f"/api/products/{product['id']}/external-mappings/jubelio",{
            'expected_revision':0,'action':'mapped','external_id':external_id,
            'external_sku':external_sku,'reason':'Mapping untuk snapshot order'})

    def order(self, **changes):
        record={'external_order_id':'order-42','external_order_reference':'JUB-ORDER-0042',
                'marketplace':'Shopee','status':'completed','ordered_at':'2026-09-13T09:00:00+07:00',
                'lines':[{'external_id':'item-42','external_sku':'JUB-LUNA-M','quantity':2,
                          'gross_revenue':'240000'}]}
        record.update(changes);return record

    def body(self, orders=None, **changes):
        finished=datetime.now(timezone.utc).replace(microsecond=0)
        body={'started_at':(finished-timedelta(minutes=2)).isoformat(),'finished_at':finished.isoformat(),
              'snapshot_at':finished.isoformat(),'external_cursor':'orders-page-8',
              'reason':'Snapshot order penuh dari connector Jubelio',
              'orders':orders if orders is not None else [self.order()]}
        body.update(changes);return body

    def test_import_creates_truthful_run_and_sales_summary(self):
        self.map_product();payload=self.body([self.order(),self.order(external_order_id='cancelled-1',
            external_order_reference='CANCELLED-1',status='cancelled',
            lines=[{'external_id':'item-42','external_sku':'JUB-LUNA-M','quantity':4,
                    'gross_revenue':'500000'}])])
        batch=self.post('/api/integrations/jubelio/order-snapshots',payload,key='orders-once')
        self.assertEqual(batch,self.post('/api/integrations/jubelio/order-snapshots',payload,key='orders-once'))
        self.assertEqual((batch['sync_status'],batch['records_read'],batch['records_written'],
                          batch['accepted_count'],batch['rejected_count']),('succeeded',2,2,2,0))
        order=next(row for row in batch['orders'] if row['external_order_id']=='order-42')
        self.assertEqual((order['gross_revenue'],order['total_quantity'],order['lines'][0]['gross_revenue']),
                         ('240000.00',2,'240000.00'))
        run=self.client.get('/api/integration-sync-runs/'+batch['sync_run_id']).json()
        self.assertEqual((run['scope'],run['status'],run['records_written']),('orders','succeeded',2))
        report=self.client.get('/api/integrations/jubelio/order-summary').json()
        self.assertEqual(report['summary'],{'accepted_orders':2,'quarantined_orders':0,'units':2,
            'gross_revenue':'240000.00','pending':0,'processing':0,'completed':1,'cancelled':1})
        self.assertEqual(report['marketplaces'],[{'marketplace':'Shopee','orders':2,'units':2,
                                                 'gross_revenue':'240000.00'}])

    def test_unsafe_identifier_quarantines_whole_orders(self):
        self.map_product()
        orders=[self.order(external_order_id='bad-pair',external_order_reference='BAD-PAIR',
                    lines=[{'external_id':'item-42','external_sku':'WRONG','quantity':1,'gross_revenue':'10'}]),
                self.order(external_order_id='unknown',external_order_reference='UNKNOWN',marketplace='<Tokopedia>',
                    lines=[{'external_id':'missing','external_sku':'<UNKNOWN>','quantity':3,'gross_revenue':'30'}])]
        batch=self.post('/api/integrations/jubelio/order-snapshots',self.body(orders))
        self.assertEqual((batch['sync_status'],batch['records_read'],batch['records_written'],
                          batch['accepted_count'],batch['rejected_count']),('failed',2,0,0,2))
        self.assertEqual({row['issue'] for row in batch['quarantine']},{'unmapped','mapping_mismatch'})
        self.assertEqual(batch['quarantine'][0]['gross_revenue'] in ('10.00','30.00'),True)
        health=self.client.get('/api/integrations').json()['systems'][0]
        order_scope=next(row for row in health['scopes'] if row['scope']=='orders')
        self.assertEqual((order_scope['health'],order_scope['latest_run']['records_written']),('failed',0))

    def test_validation_roles_listing_and_missing_records(self):
        self.map_product()
        duplicate=self.order()
        for orders in ([duplicate,dict(duplicate)],
                       [self.order(lines=[])],
                       [self.order(lines=[{'external_id':'item-42','external_sku':'JUB-LUNA-M',
                                           'quantity':True,'gross_revenue':'1'}])],
                       [self.order(lines=[{'external_id':'a','external_sku':'SAME','quantity':1,'gross_revenue':'1'},
                                          {'external_id':'b','external_sku':'same','quantity':1,'gross_revenue':'1'}])],
                       [self.order(ordered_at='2026-09-13T09:00:00')],
                       [self.order(status='refunded')],
                       [self.order(lines=[{'external_id':'a','external_sku':'A','quantity':1,
                                           'gross_revenue':'1000000000000.01'}])]):
            self.post('/api/integrations/jubelio/order-snapshots',self.body(orders),status=422)
        for changes in ({'started_at':'2026-09-13T10:00:00'},
                        {'started_at':'2026-09-13T11:00:00+00:00','finished_at':'2026-09-13T10:00:00+00:00'},
                        {'unexpected':'field'}):
            self.post('/api/integrations/jubelio/order-snapshots',self.body(**changes),status=422)
        for account in (self.operator,self.viewer):
            self.post('/api/integrations/jubelio/order-snapshots',self.body(),
                      api_key=account['api_key'],status=403)
        batch=self.post('/api/integrations/jubelio/order-snapshots',self.body(orders=[]))
        listed=self.client.get('/api/integrations/jubelio/order-snapshots').json()[0]
        self.assertEqual(listed['id'],batch['id']);self.assertNotIn('orders',listed)
        self.assertEqual(self.client.get('/api/integrations/jubelio/order-snapshots/'+batch['id']).status_code,200)
        self.assertEqual(self.client.get('/api/integrations/jubelio/order-snapshots/missing').status_code,404)
        for account in (self.operator,self.viewer):
            self.assertEqual(self.client.get('/api/integrations/jubelio/order-summary',
                headers={'X-API-Key':account['api_key']}).status_code,200)

    def test_rollback_immutability_backup_and_migration_from_35(self):
        self.map_product()
        with self.app.state.store.transaction(write=True) as db:
            db.execute("""CREATE TRIGGER fail_order_snapshot BEFORE INSERT ON requests
                WHEN NEW.key='fail-order-snapshot' BEGIN SELECT RAISE(ABORT,'fail'); END""")
        self.post('/api/integrations/jubelio/order-snapshots',self.body(),key='fail-order-snapshot',status=409)
        self.assertEqual(self.client.get('/api/integrations/jubelio/order-snapshots').json(),[])
        self.assertEqual(self.client.get('/api/integration-sync-runs').json(),[])
        with self.app.state.store.transaction(write=True) as db: db.execute('DROP TRIGGER fail_order_snapshot')
        orders=[self.order(),self.order(external_order_id='bad',external_order_reference='BAD',
            lines=[{'external_id':'bad','external_sku':'BAD','quantity':1,'gross_revenue':'1'}])]
        batch=self.post('/api/integrations/jubelio/order-snapshots',self.body(orders))
        with closing(sqlite3.connect(self.path)) as db:
            for table in ('jubelio_order_snapshot_batches','jubelio_order_snapshot_orders',
                          'jubelio_order_snapshot_lines','jubelio_order_quarantine_records'):
                for action in (f'UPDATE {table} SET id=id',f'DELETE FROM {table}'):
                    with self.assertRaises(sqlite3.IntegrityError): db.execute(action)
        backup=self.path.with_name('jubelio-order-backup.sqlite3');self.app.state.store.backup(backup)
        self.assertEqual(Store(backup).jubelio_order_snapshot(batch['id'])['orders'][0]['external_order_id'],'order-42')
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('DROP TABLE jubelio_order_quarantine_records');db.execute('DROP TABLE jubelio_order_snapshot_lines')
            db.execute('DROP TABLE jubelio_order_snapshot_orders');db.execute('DROP TABLE jubelio_order_snapshot_batches')
            db.execute('PRAGMA user_version=35');db.commit()
        Store(self.path);Store(self.path)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],41)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM jubelio_order_snapshot_batches').fetchone()[0],0)
