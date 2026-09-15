import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from threading import Barrier
from unittest import TestCase

from fastapi.testclient import TestClient

from beeloft.api import create_app
from beeloft.store import Store
import test_production as production_tests


class ProductExternalMappingTest(TestCase):
    setUp = production_tests.ProductionTest.setUp
    post = production_tests.ProductionTest.post

    def route(self, product=None, suffix=''):
        return f"/api/products/{(product or self.product)['id']}/external-mappings/jubelio{suffix}"

    def body(self, expected_revision=0, action='mapped', **changes):
        body={'expected_revision':expected_revision,'action':action,
              'external_id':'item-42' if action=='mapped' else '',
              'external_sku':'JUB-LUNA-M' if action=='mapped' else '',
              'reason':'Cocokkan master SKU sebelum read sync'}
        body.update(changes)
        return body

    def test_mapping_is_idempotent_visible_and_has_immutable_history(self):
        empty=self.client.get(self.route()).json()
        self.assertEqual((empty['system'],empty['status'],empty['revision'],empty['external_id']),
                         ('jubelio','unmapped',0,''))
        coverage=self.client.get('/api/integrations').json()['systems'][0]['product_mapping']
        self.assertEqual(coverage,{'total_products':1,'mapped_products':0,'unmapped_products':1})
        payload=self.body()
        saved=self.post(self.route(),payload,key='map-product-once')
        self.assertEqual(saved,self.post(self.route(),payload,key='map-product-once'))
        self.assertEqual((saved['status'],saved['revision'],saved['external_id'],saved['external_sku']),
                         ('mapped',1,'item-42','JUB-LUNA-M'))
        coverage=self.client.get('/api/integrations').json()['systems'][0]['product_mapping']
        self.assertEqual(coverage,{'total_products':1,'mapped_products':1,'unmapped_products':0})
        self.assertEqual(self.client.get(self.route()).json()['id'],saved['id'])
        history=self.client.get(self.route(suffix='/history')).json()
        self.assertEqual((len(history),history[0]['actor_name']),(1,self.admin['name']))
        mapped=self.client.get('/api/product-external-mappings?system=jubelio&status=mapped').json()
        self.assertEqual([(row['product_id'],row['external_sku']) for row in mapped],
                         [(self.product['id'],'JUB-LUNA-M')])
        self.assertEqual(self.client.get('/api/product-external-mappings?system=jubelio&status=unmapped').json(),[])

    def test_revision_uniqueness_correction_and_unmap(self):
        first=self.post(self.route(),self.body())
        second_product=self.post('/api/products',{'sku':'LUNA-BLUE-L','name':'Luna Blue','size':'L'})
        self.post(self.route(second_product),self.body(external_id='item-42',external_sku='OTHER'),status=409)
        self.post(self.route(second_product),self.body(external_id='other',external_sku='jub-luna-m'),status=409)
        changed=self.post(self.route(),self.body(1,external_id='item-43',external_sku='JUB-LUNA-M2'))
        self.assertEqual(changed['revision'],2)
        self.post(self.route(),self.body(1,external_id='stale',external_sku='STALE'),status=409)
        removed=self.post(self.route(),self.body(2,'unmapped'))
        self.assertEqual((removed['status'],removed['revision'],removed['external_id']),('unmapped',3,''))
        reused=self.post(self.route(second_product),self.body(external_id='item-43',external_sku='JUB-LUNA-M2'))
        self.assertEqual(reused['status'],'mapped')
        history=self.client.get(self.route(suffix='/history?limit=2')).json()
        self.assertEqual([row['revision'] for row in history],[3,2])
        older=self.client.get(self.route(suffix='/history?before='+str(history[-1]['sequence']))).json()
        self.assertEqual([row['revision'] for row in older],[1])
        self.assertEqual(first['product_id'],self.product['id'])

    def test_validation_roles_filters_and_missing_product(self):
        for body in (self.body(external_id=' '),self.body(external_sku=' '),
                     self.body(0,'unmapped',external_id='still-set'),
                     self.body(expected_revision=True),self.body(unexpected='field')):
            self.post(self.route(),body,status=422)
        self.post(self.route(),self.body(0,'unmapped'),status=409)
        self.post(self.route(),self.body(),api_key=self.operator['api_key'],status=403)
        self.post(self.route(),self.body(),api_key=self.viewer['api_key'],status=403)
        for key in (self.operator,self.viewer):
            self.assertEqual(self.client.get(self.route(),headers={'X-API-Key':key['api_key']}).status_code,200)
        self.assertEqual(self.client.get('/api/products/missing/external-mappings/jubelio').status_code,404)
        self.assertEqual(self.client.get('/api/products/'+self.product['id']+'/external-mappings/unknown').status_code,422)
        self.assertEqual(self.client.get('/api/product-external-mappings?status=bad').status_code,422)

    def test_concurrent_duplicate_mapping_has_one_owner(self):
        second=self.post('/api/products',{'sku':'LUNA-RED-M','name':'Luna Red','size':'M'})
        barrier=Barrier(2)
        def save(product,index):
            with TestClient(create_app(self.path)) as client:
                barrier.wait(timeout=10)
                response=client.post(self.route(product),json=self.body(),headers={
                    'X-API-Key':self.admin['api_key'],'Idempotency-Key':'map-race-'+str(index)})
                return response.status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses=sorted(pool.map(lambda pair:save(*pair),[(self.product,1),(second,2)]))
        self.assertEqual(statuses,[201,409])
        rows=self.client.get('/api/product-external-mappings?system=jubelio&status=mapped').json()
        self.assertEqual(len(rows),1)

    def test_rollback_immutability_backup_and_migration_from_33(self):
        with self.app.state.store.transaction(write=True) as db:
            db.execute("""CREATE TRIGGER fail_product_mapping BEFORE INSERT ON requests
                WHEN NEW.key='fail-product-mapping' BEGIN SELECT RAISE(ABORT,'fail'); END""")
        self.post(self.route(),self.body(),key='fail-product-mapping',status=409)
        self.assertEqual(self.client.get(self.route()).json()['revision'],0)
        with self.app.state.store.transaction(write=True) as db:
            db.execute('DROP TRIGGER fail_product_mapping')
        saved=self.post(self.route(),self.body(),key='saved-product-mapping')
        with closing(sqlite3.connect(self.path)) as db:
            for sql in ('UPDATE product_external_mapping_events SET reason=reason',
                        'DELETE FROM product_external_mapping_events'):
                with self.assertRaises(sqlite3.IntegrityError): db.execute(sql)
        backup=self.path.with_name('product-mapping-backup.sqlite3')
        self.app.state.store.backup(backup)
        self.assertEqual(Store(backup).product_external_mapping(self.product['id'],'jubelio')['id'],saved['id'])
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('DROP TABLE product_external_mapping_events')
            db.execute('PRAGMA user_version=33');db.commit()
        Store(self.path);Store(self.path)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],53)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM product_external_mapping_events').fetchone()[0],0)
