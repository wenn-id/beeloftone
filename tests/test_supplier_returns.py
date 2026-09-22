import sqlite3
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import TestCase

import test_incoming_qc as qc_tests
from beeloft.store import Store


class SupplierReturnTest(TestCase):
    setUp = qc_tests.IncomingQCTest.setUp
    post = qc_tests.IncomingQCTest.post
    material = qc_tests.IncomingQCTest.material
    order = qc_tests.IncomingQCTest.order
    payload = qc_tests.IncomingQCTest.payload
    create = qc_tests.IncomingQCTest.create
    decide = qc_tests.IncomingQCTest.decide
    supplier = qc_tests.IncomingQCTest.supplier
    setup_po = qc_tests.IncomingQCTest.setup_po
    issue = qc_tests.IncomingQCTest.issue
    detail = qc_tests.IncomingQCTest.detail
    cancel = qc_tests.IncomingQCTest.cancel
    setup_receipt = qc_tests.IncomingQCTest.setup_receipt
    receive = qc_tests.IncomingQCTest.receive
    reverse = qc_tests.IncomingQCTest.reverse
    intake = qc_tests.IncomingQCTest.intake
    inspect = qc_tests.IncomingQCTest.inspect
    qc = qc_tests.IncomingQCTest.qc
    reverse_decision = qc_tests.IncomingQCTest.reverse_decision

    def returned(self, intake, quantity='0.500', reference='RET-001', **options):
        return self.post('/api/qc-intakes/'+intake['id']+'/returns',
                         dict(quantity=quantity, reference=reference, returned_date='2026-10-16',
                              reason='Dikirim kembali karena cacat'), **options)

    def undo_return(self, event, **options):
        return self.post('/api/supplier-returns/'+event['id']+'/reverse',
                         dict(reason='Salah catat pengiriman'), **options)

    def close(self, po, **options):
        return self.post('/api/purchase-orders/'+po['id']+'/close',
                         dict(reason='Pemasok tidak mengirim sisa pesanan'), **options)

    def test_partial_return_retry_reversal_and_unchanged_stock_quota(self):
        po, body = self.setup_receipt()
        intake = self.intake(po, body)
        self.inspect(intake, 'reject', '1.125')
        before = self.detail(po)['lines'][0]['receivable']
        result = self.returned(intake, key='return')
        self.assertEqual(result, self.returned(intake, key='return'))
        self.assertEqual((result['returned'], result['return_pending']), ('0.500', '0.625'))
        self.assertEqual(self.detail(po)['lines'][0]['receivable'], before)
        self.assertEqual(self.client.get('/api/material-batches').json(), [])
        self.returned(intake, quantity='0.626', reference='OVER', status=409)
        self.returned(intake, quantity='0.625', reference='RET-002')
        first = result['returns'][0]
        undone = self.undo_return(first, key='undo-return')
        self.assertEqual(undone, self.undo_return(first, key='undo-return'))
        self.assertEqual((undone['returned'], undone['return_pending']), ('0.625', '0.500'))
        self.assertEqual(undone['returns'][0]['reversal_of'], first['id'])
        self.undo_return(first, status=409)
        self.undo_return(undone['returns'][0], status=409)
        self.assertEqual(result, self.returned(intake, key='return'))

    def test_reject_correction_and_cancellation_require_return_resolution(self):
        po, body = self.setup_receipt()
        intake = self.intake(po, body)
        rejected = self.inspect(intake, 'reject', '1.125')['history'][0]
        self.cancel(po, status=409)
        result = self.returned(intake)
        self.reverse_decision(rejected, status=409)
        self.undo_return(result['returns'][0])
        self.reverse_decision(rejected)
        self.assertEqual(self.qc(intake)['held'], '1.125')
        self.returned(intake, reference='NOT-REJECTED', status=409)
        self.inspect(intake, 'reject', '1.125')
        result = self.returned(intake, quantity='1.125', reference='ALL')
        self.cancel(po)
        self.undo_return(result['returns'][0], status=409)

    def test_close_partial_order_preserves_shortfall_and_locks_receipts(self):
        po, body = self.setup_receipt()
        self.close(po, status=409)
        batch = self.receive(po, body)
        closed = self.close(po, key='close')
        self.assertEqual(closed, self.close(po, key='close'))
        self.assertEqual((closed['status'], closed['fulfillment']), ('closed', 'partial'))
        line = closed['lines'][0]
        self.assertEqual((line['received'], line['remaining'], line['receivable']),
                         ('1.125', '1.000', '0.000'))
        self.assertEqual(closed['closure']['reason'], 'Pemasok tidak mengirim sisa pesanan')
        self.assertEqual(self.detail(po)['total'], po['total'])
        self.receive(po, body | {'reference':'LATE', 'quantity':'1'}, status=409)
        self.intake(po, body | {'reference':'LATE', 'quantity':'1'}, status=409)
        self.reverse(batch, status=409)
        self.cancel(po, status=409)
        self.close(po, status=409)
        self.assertEqual(self.client.get('/api/purchase-orders?status=issued').json(), [])
        self.assertEqual(self.client.get('/api/purchase-orders?status=closed').json()[0]['id'], po['id'])
        pr = self.client.get('/api/purchase-requests/'+po['request_id']).json()
        self.assertEqual(pr['purchase_orders'][0]['status'], 'closed')
        self.decide(pr, 'cancelled', status=409)
        replacement = dict(reference='DUP', request_id=pr['id'], expected_revision=pr['revision'],
                           supplier_id=po['supplier_id'], expected_date='2026-10-18', terms='Tunai',
                           reason='Duplikasi', prices=[dict(material_id=line['material_id'], unit_price='1')])
        self.issue(replacement, status=409)

    def test_close_requires_hold_and_rejected_material_resolved(self):
        po, body = self.setup_receipt()
        intake = self.intake(po, body | {'quantity':'2.125'})
        self.assertEqual(self.detail(po)['payment_received_value'], '0.00')
        accepted = self.inspect(intake, quantity='1.125')['history'][0]
        self.close(po, status=409)
        self.inspect(intake, 'reject', '1')
        self.close(po, status=409)
        returned = self.returned(intake, quantity='1')
        before = self.detail(po)
        self.assertEqual((before['payment_received_value'], before['payment_remaining']), ('13.88', '13.88'))
        closed = self.close(po, key='close-qc-partial')
        self.assertEqual(closed, self.close(po, key='close-qc-partial'))
        self.assertEqual((closed['status'], closed['fulfillment'], closed['total']), ('closed', 'partial', '26.22'))
        line = closed['lines'][0]
        self.assertEqual([line[k] for k in ('received','remaining','held','rejected','returned','return_pending','receivable')],
                         ['1.125','1.000','0.000','1.000','1.000','0.000','0.000'])
        self.assertEqual((closed['payment_received_value'], closed['payment_remaining']), ('13.88', '13.88'))
        payment_path = '/api/purchase-orders/'+po['id']+'/payment-requests'
        payment = dict(reference='DEMO-PAY-QC', invoice_reference='DEMO-INV-QC',
                       invoice_date='2026-10-16', due_date='2026-10-30', amount='13.88', reason='Penerimaan lolos QC')
        self.post(payment_path, payment | {'amount':'13.89'}, status=409)
        self.assertEqual(self.client.get(payment_path).json(), [])
        request = self.post(payment_path, payment, key='pay-qc-partial')
        self.assertEqual(request, self.post(payment_path, payment, key='pay-qc-partial'))
        self.assertEqual(request['supplier'], po['supplier'])
        self.assertEqual(len(self.client.get(payment_path).json()), 1)
        detail = self.detail(po)
        self.assertEqual([detail[k] for k in ('payment_received_value','payment_pending','payment_approved','payment_remaining')],
                         ['13.88','13.88','0.00','0.00'])
        self.undo_return(returned['returns'][0], status=409)
        self.reverse_decision(accepted, status=409)
        self.assertEqual(self.qc(intake)['po_closed'], 1)
        self.assertEqual(self.client.get('/api/material-batches/'+accepted['batch_id']).json()['balance'], '1.125')

    def test_return_validation_roles_and_atomic_rollback(self):
        po, body = self.setup_receipt()
        intake = self.intake(po, body)
        self.inspect(intake, 'reject', '1.125')
        for user in (self.operator, self.viewer):
            self.returned(intake, api_key=user['api_key'], status=403)
            self.close(po, api_key=user['api_key'], status=403)
        for quantity in ('0', '-1', '0.0001', 'NaN'):
            self.returned(intake, quantity=quantity, status=422)
        self.returned(intake, reference=' ', status=422)
        for returned_date in ('2026-10-14', 'not-a-date'):
            self.post('/api/qc-intakes/'+intake['id']+'/returns',
                      dict(reference='BAD-DATE', quantity='1', returned_date=returned_date, reason='Retur'), status=422)
        self.returned({'id':'missing'}, status=404)
        self.close({'id':'missing'}, status=404)
        with self.app.state.store.transaction(write=True) as db:
            db.execute("CREATE TRIGGER fail_return BEFORE INSERT ON requests WHEN NEW.key='fail' BEGIN SELECT RAISE(ABORT,'test'); END")
        self.returned(intake, key='fail', status=409)
        self.assertEqual(self.qc(intake)['returns'], [])
        self.assertEqual(self.qc(intake)['returned'], '0.000')
        result = self.returned(intake)
        self.assertEqual(result['returns'][0]['actor_id'], self.admin['id'])
        for user in (self.operator,self.viewer):
            self.undo_return(result['returns'][0], api_key=user['api_key'], status=403)
        self.returned(intake, status=409)

    def test_concurrent_returns_cannot_exceed_rejected_quantity(self):
        po, body = self.setup_receipt()
        intake = self.intake(po, body)
        self.inspect(intake, 'reject', '1.125')
        barrier = Barrier(2)
        def run(index):
            barrier.wait()
            return self.client.post('/api/qc-intakes/'+intake['id']+'/returns',
                json=dict(quantity='1', reference=f'RACE-{index}', returned_date='2026-10-16', reason='Retur'),
                headers={'Idempotency-Key':f'race-{index}'}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(run, range(2))), [201, 409])
        self.assertEqual(self.qc(intake)['returned'], '1.000')

    def test_sql_guards_and_persistence(self):
        po, body = self.setup_receipt()
        intake = self.intake(po, body)
        self.inspect(intake, 'reject', '1.125')
        result = self.returned(intake)
        with self.app.state.store.transaction(write=True) as db:
            for statement in (
                'UPDATE supplier_returns SET quantity_milli=1',
                'DELETE FROM supplier_returns',
                "INSERT INTO supplier_returns(id,intake_id,reference,returned_date,quantity_milli,reason,actor_id,created_at) SELECT 'over',intake_id,'OVER',returned_date,1000,reason,actor_id,created_at FROM supplier_returns",
                "INSERT INTO purchase_order_closures(order_id,reason,actor_id,created_at) SELECT purchase_order_id,'Invalid',actor_id,created_at FROM qc_intakes",
            ):
                with self.assertRaises(sqlite3.IntegrityError):
                    db.execute(statement)
        store = Store(self.app.state.store.path)
        self.assertEqual(store.quality_intake(intake['id']), result)
        backup = self.app.state.store.path.with_name('returns-backup.sqlite3')
        store.backup(backup)
        self.assertEqual(Store(backup).quality_intake(intake['id']), result)

    def test_upgrade_schema_11_preserves_cancelled_po_and_allows_legacy_return(self):
        po, body = self.setup_receipt()
        intake = self.intake(po, body)
        self.inspect(intake, 'reject', '1.125')
        migration = Path('beeloft/supplier_returns.sql').read_text(encoding='utf-8')
        with self.app.state.store.transaction(write=True) as db:
            names = db.execute("SELECT name FROM sqlite_master WHERE type='trigger'").fetchall()
            for row in names:
                if 'CREATE TRIGGER IF NOT EXISTS '+row[0]+' ' in migration:
                    db.execute('DROP TRIGGER '+row[0])
            db.execute('DROP VIEW qc_return_totals')
            db.execute('DROP TABLE supplier_returns')
            db.execute('DROP TABLE purchase_order_closures')
            db.execute('PRAGMA user_version=11')
            db.execute('INSERT INTO purchase_order_cancellations(id,order_id,reason,actor_id,created_at) VALUES(?,?,?,?,?)',
                       ('legacy-cancel',po['id'],'Pembatalan versi lama',self.admin['id'],'2026-10-16T00:00:00+00:00'))
        Store(self.path)
        self.assertEqual(self.detail(po)['status'], 'cancelled')
        self.assertEqual(self.qc(intake)['return_pending'], '1.125')
        self.returned(intake, quantity='1.125')
        self.assertEqual(Store(self.path).quality_intake(intake['id'])['return_pending'], '0.000')

    def test_closed_order_sql_guards_and_stock_remains_usable(self):
        po, body = self.setup_receipt()
        batch = self.receive(po, body | {'quantity':'2.125'})
        with self.app.state.store.transaction(write=True) as db:
            db.execute("CREATE TRIGGER fail_close BEFORE INSERT ON requests WHEN NEW.key='fail-close' BEGIN SELECT RAISE(ABORT,'test'); END")
        self.close(po, key='fail-close', status=409)
        self.assertEqual(self.detail(po)['status'], 'issued')
        closed = self.close(po)
        self.assertEqual(closed['fulfillment'], 'received')
        with self.app.state.store.transaction(write=True) as db:
            for statement in (
                'DELETE FROM purchase_order_closures',
                'UPDATE purchase_order_closures SET reason=reason',
                "INSERT INTO material_movements(id,batch_id,kind,quantity_milli,reversal_of,reason,actor_id,created_at) SELECT 'bad-reverse',batch_id,'reversal',-quantity_milli,id,reason,actor_id,created_at FROM material_movements WHERE kind='receipt'",
                "INSERT INTO qc_intakes(id,purchase_order_id,material_id,reference,location,received_date,quantity_milli,reason,actor_id,created_at) SELECT 'late',id,json_extract(lines,'$[0].material_id'),'LATE','Rak','2026-10-16',1,reason,actor_id,created_at FROM purchase_orders",
            ):
                with self.assertRaises(sqlite3.IntegrityError):
                    db.execute(statement)
        issued = self.post('/api/material-issues',dict(batch_id=batch['id'],order_id=po['production_order_id'],
                                                     quantity='1',reason='Mulai cutting'))
        self.post('/api/material-movements/'+issued['id']+'/reverse',dict(reason='Kembali dari cutting'))
        self.assertEqual(self.client.get('/api/material-batches/'+batch['id']).json()['balance'], '2.125')
        self.assertTrue(self.client.get('/api/material-batches/'+batch['id']).json()['po_closed'])

    def test_close_competes_with_return_reversal(self):
        po, body = self.setup_receipt()
        intake = self.intake(po, body | {'quantity':'2.125'})
        self.inspect(intake, quantity='1.125')
        self.inspect(intake, 'reject', '1')
        event = self.returned(intake, quantity='1')['returns'][0]
        barrier = Barrier(2)
        def run(action):
            barrier.wait(timeout=10)
            path = ('/api/purchase-orders/'+po['id']+'/close' if action=='close'
                    else '/api/supplier-returns/'+event['id']+'/reverse')
            return self.client.post(path,json=dict(reason='Uji bersamaan'),
                                    headers={'Idempotency-Key':'race-'+action}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(run, ['close','reverse'])), [201,409])
        detail = self.detail(po)
        expected = '0.000' if detail['status']=='closed' else '1.000'
        self.assertEqual(detail['lines'][0]['return_pending'], expected)
