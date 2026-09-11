from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import TestCase
from fastapi.testclient import TestClient
from beeloft.api import create_app
from beeloft.store import Store
import test_purchase_orders as po_tests


class PurchaseReceiptTest(TestCase):
    setUp = po_tests.PurchaseOrderTest.setUp
    post = po_tests.PurchaseOrderTest.post
    material = po_tests.PurchaseOrderTest.material
    order = po_tests.PurchaseOrderTest.order
    payload = po_tests.PurchaseOrderTest.payload
    create = po_tests.PurchaseOrderTest.create
    decide = po_tests.PurchaseOrderTest.decide
    supplier = po_tests.PurchaseOrderTest.supplier
    setup_po = po_tests.PurchaseOrderTest.setup_po
    issue = po_tests.PurchaseOrderTest.issue
    detail = po_tests.PurchaseOrderTest.detail
    cancel = po_tests.PurchaseOrderTest.cancel

    def setup_receipt(self):
        _, payload = self.setup_po()
        po = self.issue(payload)
        body = dict(material_id=po['lines'][0]['material_id'], reference='BATCH-PO',
                    quantity='1.125', location='Rak A', received_date='2026-10-15', reason='Lolos pemeriksaan')
        return po, body

    def receive(self, po, body, **options):
        return self.post('/api/purchase-orders/'+po['id']+'/receipts', body, **options)

    def reverse(self, batch, **options):
        return self.post('/api/material-movements/'+batch['receipt_id']+'/reverse', {'reason':'Salah catat'}, **options)

    def test_partial_complete_retry_and_reversal(self):
        po, body = self.setup_receipt()
        batch = self.receive(po, body, key='receipt', api_key=self.operator['api_key'])
        self.assertEqual(batch, self.receive(po, body, key='receipt', api_key=self.operator['api_key']))
        self.assertEqual(batch['purchase_order_id'], po['id'])
        self.assertEqual(batch['supplier'], po['supplier']['name'])
        self.assertEqual(batch['balance'], '1.125')
        detail = self.detail(po)
        self.assertEqual(detail['fulfillment'], 'partial')
        self.assertEqual(detail['lines'][0]['received'], '1.125')
        self.assertEqual(detail['lines'][0]['remaining'], '1.000')
        self.cancel(po, status=409)
        self.receive(po, body | {'reference':'OVER'}, status=409)
        second = self.receive(po, body | {'reference':'SECOND','quantity':'1'})
        self.assertEqual(self.detail(po)['fulfillment'], 'received')
        self.reverse(batch)
        self.assertEqual(self.detail(po)['lines'][0]['remaining'], '1.125')
        self.assertTrue(self.detail(po)['receipts'][1]['reversed_by'])
        self.reverse(second)
        self.assertEqual(self.detail(po)['fulfillment'], 'pending')
        self.cancel(po)
        self.receive(po, body | {'reference':'CANCELLED'}, status=409)
        self.assertEqual(batch, self.receive(po, body, key='receipt', api_key=self.operator['api_key']))

    def test_validation_roles_stock_and_rollback(self):
        po, body = self.setup_receipt()
        self.receive(po, body, api_key=self.viewer['api_key'], status=403)
        for change, status in [({'quantity':'0'},422),({'quantity':'1.0001'},422),
                               ({'material_id':'missing'},422),({'supplier':'forged'},422),({'reason':' '},422)]:
            self.receive(po, body | change, status=status)
        with self.app.state.store.transaction(write=True) as db:
            db.execute("CREATE TRIGGER fail_receipt BEFORE INSERT ON requests WHEN NEW.key='fail' BEGIN SELECT RAISE(ABORT,'test'); END")
        self.receive(po, body, key='fail', status=409)
        self.assertEqual(self.client.get('/api/material-batches').json(), [])
        self.assertEqual(self.detail(po)['receipts'], [])
        batch = self.receive(po, body)
        self.receive(po, body, status=409)
        order = self.order()
        self.post('/api/material-reservations',dict(batch_id=batch['id'],order_id=order['id'],action='reserve',quantity='1',reason='Jatah'))
        self.reverse(batch, status=409)
        issue = self.post('/api/material-issues',dict(batch_id=batch['id'],order_id=order['id'],quantity='1',reason='Cutting'))
        self.reverse(batch, status=409)
        self.assertEqual(self.detail(po)['lines'][0]['received'], '1.125')
        self.post('/api/material-movements/'+issue['id']+'/reverse',dict(reason='Dikembalikan'))
        self.reverse(batch)

    def test_concurrent_receipts_and_cancel(self):
        po, body = self.setup_receipt()
        barrier = Barrier(2)
        def receive(index):
            with TestClient(create_app(self.path)) as client:
                barrier.wait(timeout=10)
                return client.post('/api/purchase-orders/'+po['id']+'/receipts',json=body | {'reference':str(index),'quantity':'2'},
                    headers={'X-API-Key':self.admin['api_key'],'Idempotency-Key':str(index)}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(receive,range(2))),[201,409])
        self.assertEqual(self.detail(po)['lines'][0]['remaining'],'0.125')
        receipt = self.detail(po)['receipts'][0]
        self.reverse(receipt)
        barrier = Barrier(2)
        def race(action):
            with TestClient(create_app(self.path)) as client:
                barrier.wait(timeout=10)
                return client.post('/api/purchase-orders/'+po['id']+('/receipts' if action=='receive' else '/cancel'),
                    json=body if action=='receive' else {'reason':'Batal'},
                    headers={'X-API-Key':self.admin['api_key'],'Idempotency-Key':action}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(race,['receive','cancel'])),[201,409])

    def test_migration_backup_and_pcs(self):
        po, body = self.setup_receipt()
        with self.app.state.store.transaction(write=True) as db:
            db.execute('DROP TABLE purchase_order_receipts')
            db.execute('PRAGMA user_version=9')
        Store(self.path)
        batch = self.receive(po, body)
        backup = self.path.parent/'receipt-backup.sqlite3'
        self.app.state.store.backup(backup)
        self.assertEqual(Store(backup).purchase_order(po['id']),self.detail(po))
        self.assertEqual(Store(backup).material_batch(batch['id']),batch)
        pcs = self.material('BUTTON','pcs')
        pr = self.decide(self.create(self.payload(pcs,reference='PR-PCS',lines=[dict(material_id=pcs['id'],quantity='2')])), 'approved')
        po2 = self.issue(dict(reference='PO-PCS',request_id=pr['id'],expected_revision=pr['revision'],supplier_id=po['supplier_id'],
                             expected_date='2026-10-15',terms='Tunai',reason='Beli',prices=[dict(material_id=pcs['id'],unit_price='1')]))
        self.receive(po2, body | {'reference':'PCS','material_id':pcs['id'],'quantity':'0.5'},status=422)
