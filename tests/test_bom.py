import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from threading import Barrier
from unittest import TestCase
from fastapi.testclient import TestClient
from beeloft.api import create_app
from beeloft.store import Store
import test_materials


class BomTest(TestCase):
    setUp = test_materials.MaterialsTest.setUp
    post = test_materials.MaterialsTest.post
    order = test_materials.MaterialsTest.order
    material = test_materials.MaterialsTest.material
    receipt = test_materials.MaterialsTest.receipt

    def bom(self, material, quantity='1.250', revision=0, product=None, **options):
        return self.post('/api/products/'+(product or self.product)['id']+'/bom', {
            'expected_revision':revision, 'reason':'Kebutuhan standar cutting',
            'components':[{'material_id':material['id'],'quantity':quantity}]}, **options)

    def requirements(self, order):
        response = self.client.get('/api/orders/'+order['id']+'/material-requirements')
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_aggregate_shared_material_issue_reversal_and_missing_bom(self):
        fabric = self.material()
        product2 = self.post('/api/products',dict(sku='LUNA-L',name='Luna L'))
        self.bom(fabric, '1.250')
        order = self.order(lines=[dict(product_id=self.product['id'],quantity=10),dict(product_id=product2['id'],quantity=5)])
        partial = self.requirements(order)
        self.assertFalse(partial['complete'])
        self.assertEqual(partial['missing_bom'][0]['sku'], 'LUNA-L')
        self.assertEqual(partial['materials'][0]['required'], '12.500')
        self.bom(fabric,'1.500',product=product2)
        batch = self.post('/api/material-batches',self.receipt(fabric,quantity='15'))
        issued = self.post('/api/material-issues',dict(batch_id=batch['id'],order_id=order['id'],quantity='4.125',reason='Cutting'))
        report = self.requirements(order)
        self.assertTrue(report['complete'])
        row = report['materials'][0]
        self.assertEqual([row[k] for k in ['required','issued','remaining','stock','shortage']], ['20.000','4.125','15.875','10.875','5.000'])
        self.post('/api/material-movements/'+issued['id']+'/reverse',{'reason':'Bahan kembali'})
        row = self.requirements(order)['materials'][0]
        self.assertEqual([row[k] for k in ['issued','remaining','stock','shortage']], ['0.000','20.000','15.000','5.000'])
        extra = self.material('LABEL','pcs')
        extra_batch = self.post('/api/material-batches',self.receipt(extra,quantity='3',reference='LABEL-BATCH'))
        self.post('/api/material-issues',dict(batch_id=extra_batch['id'],order_id=order['id'],quantity='2',reason='Label tambahan'))
        extra_row = next(r for r in self.requirements(order)['materials'] if r['material_id']==extra['id'])
        self.assertTrue(extra_row['outside_bom'])
        self.assertEqual(extra_row['required'],'0.000')
        self.assertEqual(extra_row['issued'],'2.000')

    def test_revision_retry_conflict_history_and_latest_estimate(self):
        material = self.material()
        first = self.bom(material,key='bom-once')
        order = self.order(2)
        second = self.bom(material,'2',first['revision'])
        self.assertEqual(self.bom(material,key='bom-once'),first)
        self.bom(material,'3',0,status=409)
        self.bom(material,'3',0,key='bom-once',status=409)
        self.bom(material,'2',second['revision'],status=409)
        report = self.requirements(order)
        self.assertEqual(report['materials'][0]['required'],'4.000')
        self.assertEqual(report['sources'][0]['revision'],second['revision'])
        path='/api/products/'+self.product['id']+'/bom-history'
        rows=self.client.get(path+'?limit=1').json()
        self.assertEqual(rows[0]['revision'],second['revision'])
        older=self.client.get(path+'?before='+str(rows[0]['revision'])).json()
        self.assertEqual(older[0]['revision'],first['revision'])
        self.assertEqual(older[0]['actor_name'],self.admin['name'])

    def test_validation_roles_and_exact_large_arithmetic(self):
        material = self.material('ZIP','pcs')
        self.bom(material,'0.125',status=422)
        self.bom(material,'1',api_key=self.operator['api_key'],status=403)
        self.bom(material,'1',api_key=self.viewer['api_key'],status=403)
        path='/api/products/'+self.product['id']+'/bom'
        body=dict(expected_revision=0,reason='BOM',components=[dict(material_id=material['id'],quantity='1')])
        for changes in [dict(components=[]),dict(components=body['components']*2),dict(reason=' '),dict(expected_revision=True),dict(components=[dict(material_id='missing',quantity='1')])]:
            self.post(path,body|changes,status=422 if changes.get('components') != [dict(material_id='missing',quantity='1')] else 404)
        self.bom(material,'1000000')
        order=self.order(1_000_000_000)
        self.assertEqual(self.requirements(order)['materials'][0]['required'],'1000000000000000.000')
        for route in [path,path+'-history','/api/orders/'+order['id']+'/material-requirements']:
            self.assertEqual(self.client.get(route,headers={'X-API-Key':self.viewer['api_key']}).status_code,200)
            self.assertEqual(self.client.get(route,headers={'X-API-Key':'bad'}).status_code,401)
        self.assertEqual(self.client.get('/api/products/missing/bom').status_code,404)
        self.assertEqual(self.client.get('/api/orders/missing/material-requirements').status_code,404)

    def test_upgrade_rollback_and_immutable_history(self):
        material=self.material()
        order=self.order()
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('DROP TABLE IF EXISTS bom_revisions')
            db.execute('PRAGMA user_version=4')
            db.commit()
        Store(self.path)
        Store(self.path)
        self.assertEqual(self.client.get('/api/products/'+self.product['id']+'/bom').json()['revision'],0)
        with self.app.state.store.transaction(write=True) as db:
            db.execute("CREATE TRIGGER fail_bom BEFORE INSERT ON requests WHEN NEW.key='fail-bom' BEGIN SELECT RAISE(ABORT,'test'); END")
        self.bom(material,key='fail-bom',status=409)
        self.assertEqual(self.client.get('/api/products/'+self.product['id']+'/bom').json()['revision'],0)
        saved=self.bom(material)
        self.assertEqual(self.requirements(order)['materials'][0]['required'],'125.000')
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],17)
            for query in ['DELETE FROM bom_revisions','UPDATE bom_revisions SET reason=reason']:
                with self.assertRaises(sqlite3.IntegrityError): db.execute(query)
        self.assertEqual(Store(self.path).bom(self.product['id'])['revision'],saved['revision'])

    def test_concurrent_bom_saves_keep_one_revision(self):
        material=self.material()
        barrier=Barrier(2)
        def save(index):
            with TestClient(create_app(self.path)) as client:
                barrier.wait(timeout=10)
                return client.post('/api/products/'+self.product['id']+'/bom',json={
                    'expected_revision':0,'reason':'Tab '+str(index),
                    'components':[dict(material_id=material['id'],quantity=str(index+1))]},
                    headers={'X-API-Key':self.admin['api_key'],'Idempotency-Key':'bom-tab-'+str(index)}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(save,range(2))),[201,409])
        self.assertEqual(len(self.client.get('/api/products/'+self.product['id']+'/bom-history').json()),1)

    def test_aggregate_above_sqlite_integer_range_is_exact(self):
        material=self.material()
        lines=[]
        for index in range(10):
            product=self.post('/api/products',dict(sku='LARGE-'+str(index),name='Large aggregate'))
            self.bom(material,'1000000',product=product)
            lines.append(dict(product_id=product['id'],quantity=1_000_000_000))
        order=self.order(lines=lines)
        report=self.requirements(order)
        self.assertEqual(report['materials'][0]['required'],'10000000000000000.000')
        self.assertEqual(report['materials'][0]['shortage'],'10000000000000000.000')
