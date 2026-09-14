import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from threading import Barrier
from unittest import TestCase
from fastapi.testclient import TestClient
from beeloft.api import create_app
from beeloft.store import Store
import test_purchase_requests


class PurchaseOrderTest(TestCase):
    setUp = test_purchase_requests.PurchaseRequestTest.setUp
    post = test_purchase_requests.PurchaseRequestTest.post
    material = test_purchase_requests.PurchaseRequestTest.material
    order = test_purchase_requests.PurchaseRequestTest.order
    payload = test_purchase_requests.PurchaseRequestTest.payload
    create = test_purchase_requests.PurchaseRequestTest.create
    decide = test_purchase_requests.PurchaseRequestTest.decide

    def supplier(self, **options):
        return self.post('/api/suppliers',dict(code='kain-a',name='Toko kain',
                         contact='PIC pembelian',address='Bandung',reason='Pemasok bahan'),**options)

    def setup_po(self):
        material = self.material()
        pr = self.decide(self.create(self.payload(material, order_id=self.order()['id'])), 'approved')
        supplier = self.supplier()
        return pr, dict(reference='PO-001',request_id=pr['id'],expected_revision=pr['revision'],
                        supplier_id=supplier['id'],expected_date='2026-10-15',terms='Bayar setelah diterima',
                        reason='Harga disepakati',prices=[dict(material_id=material['id'],unit_price='12.34')])

    def submit_po(self, payload, **options):
        return self.post('/api/purchase-orders',payload,**options)

    def approve_po(self, po, decision='approved', **options):
        return self.post('/api/purchase-orders/'+po['id']+'/decisions', dict(
            status=decision, expected_revision=po['revision'], reason='Keputusan PO'), **options)

    def issue(self, payload, **options):
        po = self.post('/api/purchase-orders', payload, **options)
        if options.get('status', 201) != 201:
            return po
        key = options.get('key')
        return self.post('/api/purchase-orders/'+po['id']+'/decisions', dict(
            status='approved', expected_revision=po['revision'], reason='Keputusan PO'),
            key=(key+'-approval') if key else None)

    def detail(self, po):
        response = self.client.get('/api/purchase-orders/'+po['id'])
        self.assertEqual(response.status_code,200,response.text)
        return response.json()

    def cancel(self, po, **options):
        return self.post('/api/purchase-orders/'+po['id']+'/cancel',dict(reason='Koreksi pembelian'),**options)

    def test_issue_locks_prices_supplier_and_pr_then_cancel_and_replace(self):
        pr,payload = self.setup_po()
        before = self.client.get('/api/orders/'+pr['order_id']).json()
        po = self.issue(payload,key='po-once')
        self.assertEqual(po,self.issue(payload,key='po-once'))
        self.assertEqual(po['total'],'26.22')
        self.assertEqual(po['lines'][0]['line_total'],'26.22')
        self.assertEqual(po['lines'][0]['quantity'],'2.125')
        self.assertEqual(po['supplier']['code'],'KAIN-A')
        self.assertEqual(po['request_revision'],pr['revision'])
        self.assertEqual(po['status'],'issued')
        self.decide(pr,'cancelled',status=409)
        self.issue(payload | {'reference':'PO-SECOND'},status=409)
        self.issue(payload | {'terms':'Berbeda'},key='po-once',status=409)
        cancelled = self.cancel(po,key='po-cancel')
        self.assertEqual(cancelled,self.cancel(po,key='po-cancel'))
        self.assertEqual(cancelled['status'],'cancelled')
        self.cancel(po,status=409)
        replacement = self.issue(payload | {'reference':'PO-REPLACED'})
        self.assertEqual(self.detail(po)['supplier'],po['supplier'])
        self.assertEqual(self.client.get('/api/material-batches').json(),[])
        self.assertEqual(self.client.get('/api/orders/'+pr['order_id']).json(),before)
        self.assertEqual(len(self.client.get('/api/purchase-requests/'+pr['id']).json()['purchase_orders']),2)
        self.cancel(replacement)
        self.decide(pr,'cancelled')
        self.issue(payload | {'reference':'PO-CLOSED-PR'},status=409)
        self.assertEqual(po,self.issue(payload,key='po-once'))

    def test_price_coverage_budget_validation_permissions_and_supplier_retry(self):
        pr,payload = self.setup_po()
        self.supplier(key='duplicate',status=409)
        pending = self.submit_po(payload | {'reference':'PO-OPERATOR'},api_key=self.operator['api_key'],key='operator-po')
        self.assertEqual(pending['status'],'pending')
        self.approve_po(pending,api_key=self.operator['api_key'],status=403)
        self.approve_po(pending,'cancelled',api_key=self.operator['api_key'])
        self.submit_po(payload | {'reference':'PO-VIEWER'},api_key=self.viewer['api_key'],status=403)
        for role in [self.operator,self.viewer]:
            self.supplier(api_key=role['api_key'],status=403)
        for change, code in [
            ({'prices':[]},422),({'prices':payload['prices']*2},422),
            ({'prices':[dict(material_id=payload['prices'][0]['material_id'],unit_price='0')]},422),
            ({'prices':[dict(material_id=payload['prices'][0]['material_id'],unit_price='1.001')]},422),
            ({'prices':[dict(material_id=payload['prices'][0]['material_id'],unit_price=1)]},422),
            ({'prices':[dict(material_id=payload['prices'][0]['material_id'],unit_price='1000000000.01')]},422),
            ({'prices':[dict(material_id='other',unit_price='1')]},422),
            ({'prices':[dict(material_id=payload['prices'][0]['material_id'],unit_price='999999')]},409),
            ({'supplier_id':'missing'},404),({'request_id':'missing'},404),
            ({'expected_revision':True},422),({'expected_revision':pr['revision']+1},409),
            ({'expected_date':'bad'},422),({'terms':' '},422),({'reason':' '},422),
        ]: self.issue(payload | change,status=code)
        po = self.issue(payload)
        self.cancel(po,api_key=self.operator['api_key'],status=403)
        for path in ['/api/suppliers','/api/purchase-orders','/api/purchase-orders/'+po['id']]:
            self.assertEqual(self.client.get(path,headers={'X-API-Key':self.viewer['api_key']}).status_code,200)
            self.assertEqual(self.client.get(path,headers={'X-API-Key':'bad'}).status_code,401)
        self.assertEqual(self.client.get('/api/purchase-orders?status=bad').status_code,422)
        self.assertEqual(self.client.get('/api/purchase-orders/missing').status_code,404)

    def test_approval_and_multiple_lines_round_half_up(self):
        material = self.material()
        pcs = self.material('BUTTON','pcs')
        pr = self.create(self.payload(material,estimated_value='5.00',lines=[
            dict(material_id=material['id'],quantity='0.5'),dict(material_id=pcs['id'],quantity='2')]))
        supplier = self.supplier(key='supplier-once')
        self.assertEqual(supplier,self.supplier(key='supplier-once'))
        body = dict(reference='PO-ROUND',request_id=pr['id'],expected_revision=pr['revision'],supplier_id=supplier['id'],
                    expected_date='2026-10-01',terms='Tunai',reason='Uji harga',prices=[
                        dict(material_id=material['id'],unit_price='0.01'),dict(material_id=pcs['id'],unit_price='1')])
        self.issue(body,status=409)
        pr = self.decide(pr,'approved')
        body['expected_revision']=pr['revision']
        self.issue(body | {'prices':body['prices'][:1]},status=422)
        po = self.issue(body,key='round')
        self.assertEqual(po['total'],'2.01')
        normalized=body | {'prices':[dict(material_id=pcs['id'],unit_price='1.00'),dict(material_id=material['id'],unit_price='0.01')]}
        self.assertEqual(po,self.issue(normalized,key='round'))

    def test_concurrent_issue_pr_cancel_and_rollback(self):
        pr,payload = self.setup_po()
        barrier = Barrier(2)
        def attempt(index):
            with TestClient(create_app(self.path)) as client:
                barrier.wait(timeout=10)
                return client.post('/api/purchase-orders',json=payload | {'reference':'PO-'+str(index)},
                    headers={'X-API-Key':self.admin['api_key'],'Idempotency-Key':'concurrent-'+str(index)}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(attempt,range(2))),[201,409])
        po = self.client.get('/api/purchase-orders').json()[0]
        po = self.approve_po(po)
        with self.app.state.store.transaction(write=True) as db:
            db.execute("CREATE TRIGGER fail_po BEFORE INSERT ON requests WHEN NEW.key='fail' BEGIN SELECT RAISE(ABORT,'test'); END")
        self.cancel(po,key='fail',status=409)
        self.assertEqual(self.detail(po)['status'],'issued')
        self.cancel(po)
        self.issue(payload,key='fail',status=409)
        self.assertEqual(len(self.client.get('/api/purchase-orders').json()),1)
        barrier=Barrier(2)
        def race(action):
            with TestClient(create_app(self.path)) as client:
                barrier.wait(timeout=10)
                path='/api/purchase-orders' if action=='issue' else '/api/purchase-requests/'+pr['id']+'/decisions'
                body=payload if action=='issue' else dict(status='cancelled',expected_revision=pr['revision'],reason='Batal PR')
                return client.post(path,json=body,headers={'X-API-Key':self.admin['api_key'],'Idempotency-Key':'race-'+action}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(race,['issue','cancel'])),[201,409])

    def test_migration_backup_immutability_and_pagination(self):
        material = self.material()
        pr = self.decide(self.create(self.payload(material)), 'approved')
        with closing(sqlite3.connect(self.path)) as db:
            for table in ['purchase_order_cancellations','purchase_orders','suppliers']:
                db.execute('DROP TABLE IF EXISTS '+table)
            db.execute('PRAGMA user_version=8');db.commit()
        Store(self.path);Store(self.path)
        supplier=self.supplier()
        body=dict(reference='PO-A',request_id=pr['id'],expected_revision=pr['revision'],supplier_id=supplier['id'],
                  expected_date='2026-10-01',terms='Tunai',reason='Belanja',
                  prices=[dict(material_id=material['id'],unit_price='2')])
        a=self.issue(body);self.cancel(a)
        b=self.issue(body | {'reference':'PO-B'})
        page=self.client.get('/api/purchase-orders?limit=1').json()
        self.assertEqual(page[0]['id'],b['id'])
        self.assertEqual(self.client.get('/api/purchase-orders?before='+str(page[0]['sequence'])).json()[0]['id'],a['id'])
        self.assertEqual(len(self.client.get('/api/purchase-orders?status=issued&request_id='+pr['id']).json()),1)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],47)
            for table in ['suppliers','purchase_orders','purchase_order_cancellations']:
                for sql in ['DELETE FROM '+table,'UPDATE '+table+' SET reason=reason']:
                    with self.assertRaises(sqlite3.IntegrityError):db.execute(sql)
        backup=self.path.parent/'po-backup.sqlite3'
        self.app.state.store.backup(backup)
        self.assertEqual(Store(backup).purchase_order(b['id']),self.detail(b))
