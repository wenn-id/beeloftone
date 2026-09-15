import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from threading import Barrier
from unittest import TestCase

from fastapi.testclient import TestClient

from beeloft.api import create_app
from beeloft.store import Store
import test_purchase_orders as po_tests


class PurchaseOrderApprovalTest(TestCase):
    setUp = po_tests.PurchaseOrderTest.setUp
    post = po_tests.PurchaseOrderTest.post
    material = po_tests.PurchaseOrderTest.material
    order = po_tests.PurchaseOrderTest.order
    payload = po_tests.PurchaseOrderTest.payload
    create = po_tests.PurchaseOrderTest.create
    decide = po_tests.PurchaseOrderTest.decide
    supplier = po_tests.PurchaseOrderTest.supplier
    setup_po = po_tests.PurchaseOrderTest.setup_po
    submit_po = po_tests.PurchaseOrderTest.submit_po
    approve_po = po_tests.PurchaseOrderTest.approve_po
    issue = po_tests.PurchaseOrderTest.issue
    detail = po_tests.PurchaseOrderTest.detail

    def receipt(self, po, suffix='PENDING'):
        return dict(material_id=po['lines'][0]['material_id'], reference='BATCH-'+suffix,
                    quantity='1', location='Rak A', received_date='2026-10-15', reason='Bahan datang')

    def test_pending_po_enters_inbox_and_blocks_receipt_qc_until_approved(self):
        _, payload = self.setup_po()
        po = self.submit_po(payload, api_key=self.operator['api_key'], key='submit-po')
        self.assertEqual((po['status'],po['approval_status']), ('pending','submitted'))
        self.assertEqual(po['lines'][0]['receivable'], '0.000')
        self.assertEqual([event['status'] for event in po['approval_history']], ['submitted'])
        queue = self.client.get('/api/approvals?kind=purchase_order').json()
        self.assertEqual(len(queue), 1)
        self.assertEqual((queue[0]['id'],queue[0]['amount']), (po['id'],'26.22'))
        self.assertEqual(queue[0]['context']['supplier_name'], 'Toko kain')
        self.assertEqual(self.client.get('/api/purchase-orders?status=pending').json()[0]['id'], po['id'])
        body = self.receipt(po)
        self.post('/api/purchase-orders/'+po['id']+'/receipts', body, status=409)
        self.post('/api/purchase-orders/'+po['id']+'/qc-intakes', body, status=409)
        self.post('/api/purchase-orders/'+po['id']+'/cancel', {'reason':'Belum boleh'}, status=409)
        self.post('/api/purchase-orders/'+po['id']+'/close', {'reason':'Belum boleh'}, status=409)
        approved = self.approve_po(po, key='approve-po')
        self.assertEqual(approved, self.approve_po(po, key='approve-po'))
        self.assertEqual((approved['status'],approved['approval_status']), ('issued','approved'))
        self.assertEqual([event['status'] for event in approved['approval_history']], ['approved','submitted'])
        self.assertEqual(self.client.get('/api/approvals?status=approved&kind=purchase_order').json()[0]['id'], po['id'])
        self.assertEqual(self.client.get('/api/purchase-orders?status=issued').json()[0]['id'], po['id'])
        self.assertEqual(self.post('/api/purchase-orders/'+po['id']+'/receipts', body)['purchase_order_id'], po['id'])

    def test_roles_rejection_cancellation_and_replacement(self):
        pr, payload = self.setup_po()
        self.submit_po(payload, api_key=self.viewer['api_key'], status=403)
        pending = self.submit_po(payload, api_key=self.operator['api_key'])
        other = self.app.state.store.provision_user('Operator lain', 'operator')
        self.approve_po(pending, api_key=self.operator['api_key'], status=403)
        self.approve_po(pending, 'cancelled', api_key=other['api_key'], status=403)
        cancelled = self.approve_po(pending, 'cancelled', api_key=self.operator['api_key'])
        self.assertEqual((cancelled['status'],cancelled['approval_status']), ('cancelled','cancelled'))
        replacement = self.submit_po(payload | {'reference':'PO-REJECTED'})
        rejected = self.approve_po(replacement, 'rejected')
        self.assertEqual((rejected['status'],rejected['approval_status']), ('rejected','rejected'))
        self.approve_po(rejected, status=409)
        final = self.submit_po(payload | {'reference':'PO-FINAL'})
        self.assertEqual(final['status'], 'pending')
        self.decide(pr, 'cancelled', status=409)
        self.assertEqual(self.client.get('/api/purchase-orders?status=rejected').json()[0]['id'], rejected['id'])
        self.assertEqual(self.client.get('/api/approvals?status=cancelled&kind=purchase_order').json()[0]['id'], cancelled['id'])
        for changes in ({'status':'submitted'},{'expected_revision':True},{'expected_revision':0},{'reason':' '}):
            body = dict(status='approved',expected_revision=final['revision'],reason='Keputusan') | changes
            self.post('/api/purchase-orders/'+final['id']+'/decisions', body, status=422)

    def test_concurrent_decision_rollback_and_database_guards(self):
        _, payload = self.setup_po()
        pending = self.submit_po(payload)
        barrier = Barrier(2)
        def decide(status):
            with TestClient(create_app(self.path)) as client:
                barrier.wait(timeout=10)
                return client.post('/api/purchase-orders/'+pending['id']+'/decisions', json={
                    'status':status,'expected_revision':pending['revision'],'reason':'Keputusan bersamaan'},
                    headers={'X-API-Key':self.admin['api_key'],'Idempotency-Key':status}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(decide,['approved','rejected'])), [201,409])

        material = self.material('ROLLBACK-CLOTH')
        pr = self.decide(self.create(self.payload(material, reference='PR-ROLLBACK')), 'approved')
        pending2 = self.submit_po(payload | {'reference':'PO-ROLLBACK','request_id':pr['id'],
            'expected_revision':pr['revision'],'prices':[{'material_id':material['id'],'unit_price':'12.34'}]})
        with self.app.state.store.transaction(write=True) as db:
            db.execute("CREATE TRIGGER fail_po_approval BEFORE INSERT ON requests WHEN NEW.key='approval-fail' BEGIN SELECT RAISE(ABORT,'fail'); END")
        self.approve_po(pending2, key='approval-fail', status=409)
        self.assertEqual(self.detail(pending2)['approval_status'], 'submitted')
        batch = self.post('/api/material-batches', dict(material_id=pending2['lines'][0]['material_id'],
            reference='BATCH-BYPASS', supplier='Pemasok', location='Rak', received_date='2026-10-15',
            quantity='1', reason='Fixture guard'))

        with closing(sqlite3.connect(self.path)) as db:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("INSERT INTO purchase_order_cancellations(id,order_id,reason,actor_id,created_at) VALUES('bad',?,'Bypass',?,'2026-09-12')",
                           (pending2['id'],self.admin['id']))
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute('INSERT INTO purchase_order_receipts(batch_id,purchase_order_id) VALUES(?,?)',
                           (batch['id'],pending2['id']))
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("""INSERT INTO qc_intakes(id,purchase_order_id,material_id,reference,location,received_date,
                    quantity_milli,reason,actor_id,created_at) VALUES('bad',?,?, 'QC-BYPASS','Hold','2026-10-15',1,'Bypass',?,'2026-09-12')""",
                    (pending2['id'],pending2['lines'][0]['material_id'],self.admin['id']))
            for sql in ('UPDATE purchase_order_approval_events SET reason=reason',
                        'DELETE FROM purchase_order_approval_events'):
                with self.assertRaises(sqlite3.IntegrityError):
                    db.execute(sql)

    def test_migration_from_26_backfills_existing_po_as_approved(self):
        _, payload = self.setup_po()
        issued = self.issue(payload)
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('DROP TABLE purchase_order_approval_events')
            db.execute('PRAGMA user_version=26')
            db.commit()
        Store(self.path); Store(self.path)
        migrated = self.detail(issued)
        self.assertEqual((migrated['status'],migrated['approval_status']), ('issued','approved'))
        self.assertEqual(migrated['approval_history'][0]['reason'],
                         'Migrasi: PO historis diperlakukan sudah disetujui.')
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],50)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM purchase_order_approval_events').fetchone()[0], 1)
