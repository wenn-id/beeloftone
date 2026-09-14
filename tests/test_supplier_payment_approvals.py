import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from threading import Barrier
from unittest import TestCase

from fastapi.testclient import TestClient

from beeloft.api import create_app
from beeloft.store import Store
import test_po_receipts as receipt_tests


class SupplierPaymentApprovalTest(TestCase):
    setUp = receipt_tests.PurchaseReceiptTest.setUp
    post = receipt_tests.PurchaseReceiptTest.post
    material = receipt_tests.PurchaseReceiptTest.material
    order = receipt_tests.PurchaseReceiptTest.order
    payload = receipt_tests.PurchaseReceiptTest.payload
    create = receipt_tests.PurchaseReceiptTest.create
    decide = receipt_tests.PurchaseReceiptTest.decide
    supplier = receipt_tests.PurchaseReceiptTest.supplier
    setup_po = receipt_tests.PurchaseReceiptTest.setup_po
    issue = receipt_tests.PurchaseReceiptTest.issue
    detail = receipt_tests.PurchaseReceiptTest.detail
    setup_receipt = receipt_tests.PurchaseReceiptTest.setup_receipt
    receive = receipt_tests.PurchaseReceiptTest.receive
    reverse = receipt_tests.PurchaseReceiptTest.reverse

    def payment_body(self, reference='PAY-001', amount='10.00', **changes):
        return dict(reference=reference, invoice_reference='INV-001', invoice_date='2026-10-15',
                    due_date='2026-10-30', amount=amount,
                    reason='Invoice sesuai penerimaan bahan') | changes

    def request_payment(self, po, **options):
        body = self.payment_body(**options.pop('changes', {}))
        return self.post('/api/purchase-orders/'+po['id']+'/payment-requests', body, **options)

    def decide_payment(self, request, decision='approved', **options):
        body = dict(status=decision, expected_revision=request['revision'], reason='Keputusan pembayaran')
        body.update(options.pop('changes', {}))
        return self.post('/api/supplier-payment-requests/'+request['id']+'/decisions', body, **options)

    def received_po(self):
        po, receipt = self.setup_receipt()
        batch = self.receive(po, receipt | {'quantity':'2.125'})
        return po, batch

    def test_request_requires_received_po_and_enters_unified_inbox(self):
        _, payload = self.setup_po()
        po = self.issue(payload)
        self.request_payment(po, status=409)
        receipt = dict(material_id=po['lines'][0]['material_id'],reference='PAYMENT-RECEIPT',
            quantity='1',location='Rak',received_date='2026-10-15',reason='Bahan diterima')
        batch = self.receive(po, receipt)
        request = self.request_payment(po, api_key=self.operator['api_key'], key='payment-request')
        self.assertEqual(request, self.request_payment(po, api_key=self.operator['api_key'], key='payment-request'))
        self.assertEqual((request['status'],request['amount']), ('submitted','10.00'))
        self.assertEqual(request['supplier']['name'], 'Toko kain')
        payment_summary = self.client.get('/api/purchase-orders/'+po['id']).json()
        self.assertEqual((payment_summary['payment_received_value'],payment_summary['payment_remaining']),
                         ('12.34','2.34'))
        queue = self.client.get('/api/approvals?kind=supplier_payment').json()
        self.assertEqual((queue[0]['id'],queue[0]['amount']), (request['id'],'10.00'))
        self.assertEqual(queue[0]['context']['invoice_reference'], 'INV-001')
        self.assertEqual(self.client.get('/api/supplier-payment-requests/'+request['id']).json(), request)
        self.assertEqual(self.client.get('/api/purchase-orders/'+po['id']+'/payment-requests').json()[0], request)
        self.reverse(batch, status=409)
        approved = self.decide_payment(request, key='payment-approved')
        self.assertEqual(approved, self.decide_payment(request, key='payment-approved'))
        self.assertEqual(approved['status'], 'approved')
        detail = self.client.get('/api/purchase-orders/'+po['id']).json()
        self.assertEqual((detail['payment_pending'],detail['payment_approved'],detail['payment_remaining']),
                         ('0.00','10.00','2.34'))
        self.assertEqual(self.client.get('/api/approvals?status=approved&kind=supplier_payment').json()[0]['id'], request['id'])

    def test_amount_capacity_roles_cancellation_rejection_and_validation(self):
        po, _ = self.received_po()
        self.request_payment(po, api_key=self.viewer['api_key'], status=403)
        pending = self.request_payment(po, api_key=self.operator['api_key'])
        other = self.app.state.store.provision_user('Operator pembayaran lain', 'operator')
        self.decide_payment(pending, api_key=self.operator['api_key'], status=403)
        self.decide_payment(pending, 'cancelled', api_key=other['api_key'], status=403)
        cancelled = self.decide_payment(pending, 'cancelled', api_key=self.operator['api_key'])
        self.assertEqual(cancelled['status'], 'cancelled')
        rejected = self.request_payment(po, changes={'reference':'PAY-REJECT','invoice_reference':'INV-REJECT','amount':'20'})
        rejected = self.decide_payment(rejected, 'rejected')
        self.assertEqual(rejected['status'], 'rejected')
        active = self.request_payment(po, changes={'reference':'PAY-ACTIVE','invoice_reference':'INV-ACTIVE','amount':'20'})
        self.request_payment(po, changes={'reference':'PAY-OVER','invoice_reference':'INV-OVER','amount':'6.23'}, status=409)
        second = self.request_payment(po, changes={'reference':'PAY-BALANCE','invoice_reference':'INV-BALANCE','amount':'6.22'})
        self.assertEqual(self.client.get('/api/purchase-orders/'+po['id']).json()['payment_remaining'], '0.00')
        self.decide_payment(active)
        self.decide_payment(second)
        for changes, status in [
            ({'amount':'0'},422),({'amount':'1.001'},422),({'amount':1},422),
            ({'amount':'1000000000000.01'},422),({'invoice_date':'2026-11-01'},422),
            ({'reference':' '},422),({'invoice_reference':' '},422),({'reason':' '},422),
            ({'extra':'bad'},422)
        ]:
            self.request_payment(po, changes={'reference':'PAY-BAD-'+str(len(str(changes))),
                'invoice_reference':'INV-BAD-'+str(len(str(changes)))} | changes, status=status)
        for changes in ({'status':'submitted'},{'expected_revision':True},{'expected_revision':0},{'reason':' '}):
            self.decide_payment(active, changes=changes, status=422)
        self.assertEqual(self.client.get('/api/supplier-payment-requests/missing').status_code,404)
        self.assertEqual(self.client.get('/api/purchase-orders/missing/payment-requests').status_code,404)
        self.assertEqual(self.client.get('/api/approvals?kind=bad').status_code,422)

    def test_closed_po_allows_payment(self):
        po, _ = self.received_po()
        self.post('/api/purchase-orders/'+po['id']+'/close', {'reason':'Sisa tidak dikirim'})
        request = self.request_payment(po)
        self.assertEqual(request['status'],'submitted')
        self.assertEqual(self.client.get('/api/purchase-orders/'+po['id']).json()['status'], 'closed')

    def test_receipt_reversal_cannot_reduce_payment_coverage(self):
        po, body = self.setup_receipt()
        first = self.receive(po, body | {'quantity':'1'})
        self.receive(po, body | {'reference':'BATCH-SECOND','quantity':'1.125'})
        request = self.request_payment(po, changes={'amount':'20'})
        self.reverse(first, status=409)
        self.decide_payment(request, 'rejected')
        self.reverse(first)
        detail = self.client.get('/api/purchase-orders/'+po['id']).json()
        self.assertEqual((detail['payment_received_value'],detail['payment_remaining']), ('13.88','13.88'))

    def test_concurrent_amount_and_decisions_are_serialized(self):
        po, _ = self.received_po()
        barrier = Barrier(2)
        def create(index):
            with TestClient(create_app(self.path)) as client:
                barrier.wait(timeout=10)
                return client.post('/api/purchase-orders/'+po['id']+'/payment-requests', json=self.payment_body(
                    reference='PAY-RACE-'+str(index),amount='20',invoice_reference='INV-RACE-'+str(index)),
                    headers={'X-API-Key':self.admin['api_key'],'Idempotency-Key':'create-'+str(index)}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(create,range(2))), [201,409])
        request = self.client.get('/api/purchase-orders/'+po['id']+'/payment-requests').json()[0]
        barrier = Barrier(2)
        def decide(status):
            with TestClient(create_app(self.path)) as client:
                barrier.wait(timeout=10)
                return client.post('/api/supplier-payment-requests/'+request['id']+'/decisions', json={
                    'status':status,'expected_revision':request['revision'],'reason':'Keputusan bersamaan'},
                    headers={'X-API-Key':self.admin['api_key'],'Idempotency-Key':'decide-'+status}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(decide,['approved','rejected'])), [201,409])

    def test_atomic_rollback_immutable_backup_and_migration_from_27(self):
        po, _ = self.received_po()
        request = self.request_payment(po)
        with self.app.state.store.transaction(write=True) as db:
            db.execute("CREATE TRIGGER fail_payment BEFORE INSERT ON requests WHEN NEW.key='payment-fail' BEGIN SELECT RAISE(ABORT,'fail'); END")
        self.decide_payment(request, key='payment-fail', status=409)
        self.assertEqual(self.client.get('/api/supplier-payment-requests/'+request['id']).json()['status'], 'submitted')
        with closing(sqlite3.connect(self.path)) as db:
            for table in ('supplier_payment_requests','supplier_payment_request_events'):
                for sql in ('UPDATE '+table+' SET reason=reason','DELETE FROM '+table):
                    with self.assertRaises(sqlite3.IntegrityError):
                        db.execute(sql)
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("""INSERT INTO supplier_payment_request_events(request_id,status,reason,actor_id,created_at)
                    VALUES(?,'submitted','Repeat',?,'2026-09-12')""", (request['id'],self.admin['id']))
        backup = self.path.parent/'supplier-payment-backup.sqlite3'
        self.app.state.store.backup(backup)
        self.assertEqual(Store(backup).supplier_payment_request(request['id']),
                         self.client.get('/api/supplier-payment-requests/'+request['id']).json())

        with closing(sqlite3.connect(self.path)) as db:
            db.execute('DROP TABLE supplier_payment_request_events')
            db.execute('DROP TABLE supplier_payment_requests')
            db.execute('PRAGMA user_version=27')
            db.commit()
        Store(self.path); Store(self.path)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],46)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM supplier_payment_requests').fetchone()[0],0)
