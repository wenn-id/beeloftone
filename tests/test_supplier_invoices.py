"""B01 (#50): tagihan supplier (supplier invoice) + identitas invoice payment request.

Fondasi minimal scope #50:
- Invoice = entitas terpisah: identitas global (supplier_id, reference) unik,
  snapshot pemasok, tanggal invoice/jatuh tempo, alokasi qty/nilai ke baris PO
  berdasar penerimaan fisik yang belum direversal.
- Harga alokasi WAJIB sama dengan harga aktual baris PO (terkunci saat PO
  diterbitkan); harga referensi master tidak dipakai untuk invoice.
- Payment request baru WAJIB menunjuk invoice terdaftar; approval tetap hanya
  izin (bukan settlement/pembayaran), sesuai pemisahan scope #50 vs #54.
- Baris payment request legacy (invoice_id NULL) dikecualikan dari validasi
  baru: histori tidak difabrikasi.

Di luar scope #50 (milik #54/#59): credit note/reversal invoice,
multi-mata uang, posting AP otomatis, settlement/kas/bank.

Konvensi fixture: rantai test_purchase_requests -> test_purchase_orders ->
test_po_receipts (PO diterbitkan, penerimaan 1.125 m @ Rp12,34 = Rp13,88).
"""
import re
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from threading import Barrier
from unittest import TestCase

from beeloft.store import Store
import test_po_receipts as receipt_tests


class SupplierInvoiceTest(TestCase):
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
    cancel = receipt_tests.PurchaseReceiptTest.cancel
    setup_receipt = receipt_tests.PurchaseReceiptTest.setup_receipt
    receive = receipt_tests.PurchaseReceiptTest.receive
    reverse = receipt_tests.PurchaseReceiptTest.reverse

    # -- Fixture ------------------------------------------------------------
    def invoice_body(self, po, reference='INV-001', quantity='1.125', **changes):
        line = po['lines'][0]
        return dict(reference=reference, supplier_id=po['supplier']['id'],
                    invoice_date='2026-10-15', due_date='2026-10-30',
                    lines=[dict(purchase_order_id=po['id'], material_id=line['material_id'],
                                quantity=quantity, unit_price=line['unit_price'])],
                    reason='Tagihan sesuai penerimaan fisik') | changes

    def register_invoice(self, po, **options):
        changes = options.pop('changes', {})
        return self.post('/api/supplier-invoices', self.invoice_body(po, **changes), **options)

    def received_po(self, quantity='1.125'):
        po, body = self.setup_receipt()
        self.receive(po, body | {'quantity': quantity})
        return po

    def payment_body(self, invoice, reference='PAY-001', **changes):
        return dict(reference=reference, invoice_id=invoice['id'],
                    invoice_reference=invoice['reference'],
                    invoice_date=invoice['invoice_date'], due_date=invoice['due_date'],
                    amount='10.00', reason='Bayar tagihan supplier') | changes

    def request_payment(self, po, invoice, **options):
        changes = options.pop('changes', {})
        return self.post('/api/purchase-orders/' + po['id'] + '/payment-requests',
                         self.payment_body(invoice, **changes), **options)

    # -- Alur utama ---------------------------------------------------------
    def test_register_allocates_received_value_and_links_payment_request(self):
        po = self.received_po()
        invoice = self.register_invoice(po, key='inv-once')
        self.assertEqual(invoice, self.register_invoice(po, key='inv-once'))
        self.assertEqual((invoice['reference'], invoice['total'], invoice['currency']),
                         ('INV-001', '13.88', 'IDR'))
        allocation = invoice['allocations'][0]
        self.assertEqual((allocation['purchase_order_reference'], allocation['quantity'],
                          allocation['unit_price'], allocation['line_total']),
                         (po['reference'], '1.125', '12.34', '13.88'))
        self.assertEqual((allocation['received'], allocation['invoiced'], allocation['uninvoiced']),
                         ('1.125', '1.125', '0.000'))
        self.assertEqual(invoice['supplier']['id'], po['supplier']['id'])

        payment = self.request_payment(po, invoice, key='pay-once')
        self.assertEqual(payment, self.request_payment(po, invoice, key='pay-once'))
        self.assertEqual(payment['invoice'], {'id': invoice['id'], 'reference': 'INV-001'})
        self.assertEqual(payment['status'], 'submitted')

        again = self.client.get('/api/supplier-invoices/' + invoice['id']).json()
        self.assertEqual(again['payment_requests'][0]['id'], payment['id'])
        listed = self.client.get('/api/supplier-invoices?purchase_order_id=' + po['id']).json()
        self.assertEqual([row['id'] for row in listed], [invoice['id']])

    def test_partial_invoice_and_second_receipt(self):
        po = self.received_po('1.000')
        first = self.register_invoice(po, key='inv-1', changes={'quantity': '1.000'})
        self.assertEqual(first['total'], '12.34')
        # Penerimaan berikutnya membuka sisa yang bisa ditagih.
        self.receive(po, dict(material_id=po['lines'][0]['material_id'],
                              reference='BATCH-PO-001-B', quantity='1.125',
                              location='Rak A', received_date='2026-10-16',
                              reason='Sisa kiriman'))
        second = self.register_invoice(po, changes={'reference': 'INV-002'}, key='inv-2')
        self.assertEqual(second['total'], '13.88')
        detail = self.client.get('/api/supplier-invoices/' + first['id']).json()
        self.assertEqual(detail['allocations'][0]['uninvoiced'], '0.000')
        detail2 = self.client.get('/api/supplier-invoices/' + second['id']).json()
        self.assertEqual(detail2['allocations'][0]['uninvoiced'], '0.000')

    # -- Validasi -----------------------------------------------------------
    def test_supplier_mismatch_rejected(self):
        po = self.received_po()
        other = self.post('/api/suppliers',
                            dict(code='kain-b', name='Toko lain', contact='PIC',
                                 address='Jakarta', reason='Pemasok lain'))
        self.register_invoice(po, changes={'supplier_id': other['id']}, status=422)
        # Invoice milik pemasok A tidak bisa dipakai untuk PO pemasok B.
        material_b = self.material(code='KAIN-C')
        pr = self.decide(self.create(self.payload(material_b, reference='PR-B')), 'approved')
        po_b = self.issue(dict(reference='PO-B', request_id=pr['id'],
                                expected_revision=pr['revision'], supplier_id=other['id'],
                                expected_date='2026-10-15', terms='Tunai', reason='Uji',
                                prices=[dict(material_id=material_b['id'], unit_price='5.00')]))
        self.receive(po_b, dict(material_id=material_b['id'], reference='BATCH-PO-B',
                                quantity='2', location='Rak A', received_date='2026-10-16',
                                reason='Diterima'))
        invoice_a = self.register_invoice(po, key='inv-a')
        self.request_payment(po_b, invoice_a,
                             changes={'invoice_reference': invoice_a['reference']}, status=422)

    def test_material_price_and_quantity_validation(self):
        po = self.received_po()
        line = po['lines'][0]
        base = dict(purchase_order_id=po['id'], material_id=line['material_id'],
                    quantity='1.125', unit_price=line['unit_price'])
        self.register_invoice(po, changes={'lines': [base | {'material_id': 'missing'}]},
                              status=422)
        self.register_invoice(po, changes={'lines': [base | {'material_id': line['material_id'],
                                                             'unit_price': '12.35'}]},
                              status=422)
        self.register_invoice(po, changes={'lines': [base | {'quantity': '1.126'}]},
                              status=409)
        self.register_invoice(po, changes={'lines': []}, status=422)
        self.register_invoice(po, changes={'lines': [base, base]}, status=422)
        self.register_invoice(po, changes={'invoice_date': '2026-10-31'}, status=422)

    def test_master_reference_price_change_does_not_move_invoice_price(self):
        # B01 (#50): harga referensi master (M01) bukan harga aktual. Diubah
        # setelah receipt, invoice tetap wajib memakai harga aktual baris PO
        # yang terkunci saat PO diterbitkan.
        po = self.received_po()
        line = po['lines'][0]
        self.post('/api/materials/' + line['material_id'] + '/changes',
                  {'reference_price': '99.99'}, status=200)
        invoice = self.register_invoice(po, key='inv-ref-price')
        self.assertEqual(invoice['allocations'][0]['unit_price'], line['unit_price'])
        self.register_invoice(po, changes={
            'reference': 'INV-REFPRICE',
            'lines': [dict(purchase_order_id=po['id'], material_id=line['material_id'],
                           quantity='0.100', unit_price='99.99')]}, status=422)

    def test_double_invoicing_rejected(self):
        po = self.received_po()
        self.register_invoice(po, key='inv-1')
        self.register_invoice(po, changes={'reference': 'INV-002'}, status=409)

    def test_reference_unique_per_supplier(self):
        po = self.received_po()
        self.register_invoice(po, key='inv-1')
        self.register_invoice(po, changes={'reference': 'INV-001'}, status=409)
        # Reference sama di pemasok lain: identitas = (supplier_id, reference).
        other = self.post('/api/suppliers',
                            dict(code='kain-b', name='Toko lain', contact='PIC',
                                 address='Jakarta', reason='Pemasok lain'))
        material_b = self.material(code='KAIN-C')
        pr = self.decide(self.create(self.payload(material_b, reference='PR-B')), 'approved')
        po_b = self.issue(dict(reference='PO-B', request_id=pr['id'],
                               expected_revision=pr['revision'], supplier_id=other['id'],
                               expected_date='2026-10-15', terms='Tunai', reason='Uji',
                               prices=[dict(material_id=material_b['id'], unit_price='5.00')]))
        self.receive(po_b, dict(material_id=material_b['id'], reference='BATCH-PO-B',
                                quantity='2', location='Rak A', received_date='2026-10-16',
                                reason='Diterima'))
        invoice_b = self.register_invoice(po_b, changes={'reference': 'INV-001'}, key='inv-b')
        self.assertEqual(invoice_b['reference'], 'INV-001')

    def test_invoice_requires_issued_po(self):
        _, payload = self.setup_po()
        pending = self.post('/api/purchase-orders', payload, api_key=self.operator['api_key'])
        self.register_invoice(pending, status=409)
        material = self.material(code='KAIN-E')
        pr = self.decide(self.create(self.payload(material, reference='PR-E')), 'approved')
        issued = self.issue(payload | {'reference': 'PO-002', 'request_id': pr['id'],
                                       'expected_revision': pr['revision'],
                                       'prices': [dict(material_id=material['id'],
                                                       unit_price='12.34')]})
        cancelled = self.cancel(issued, key='cancel-issued')
        self.assertEqual(cancelled['status'], 'cancelled')
        self.register_invoice(issued, status=409)

    def test_inactive_supplier_and_material_rejected(self):
        po = self.received_po()
        changed = self.post('/api/suppliers/' + po['supplier']['id'] + '/changes',
                            dict(active=False, reason='Nonaktif sementara'))
        self.assertFalse(changed['active'])
        self.register_invoice(po, status=422)
        # PO baru dari pemasok nonaktif tetap ditolak di sumbernya.
        material = self.material(code='KAIN-D')
        pr = self.decide(self.create(self.payload(material, reference='PR-D')), 'approved')
        self.post('/api/purchase-orders',
                  dict(reference='PO-D', request_id=pr['id'], expected_revision=pr['revision'],
                       supplier_id=po['supplier']['id'], expected_date='2026-10-15',
                       terms='Tunai', reason='Uji', prices=[dict(material_id=material['id'],
                                                                  unit_price='1.00')]),
                  api_key=self.operator['api_key'], status=422)

    def test_roles_and_retry(self):
        po = self.received_po()
        self.register_invoice(po, api_key=self.viewer['api_key'], status=403)
        invoice = self.register_invoice(po, key='inv-op', api_key=self.operator['api_key'])
        self.assertEqual(invoice['actor_name'], 'Tim produksi')
        self.assertEqual(self.client.get('/api/supplier-invoices',
                                         headers={'X-API-Key': self.viewer['api_key']}
                                         ).status_code, 200)

    # -- Payment request beridentitas invoice --------------------------------
    def test_payment_request_invoice_rules(self):
        po = self.received_po()
        invoice = self.register_invoice(po, key='inv-1')
        path = '/api/purchase-orders/' + po['id'] + '/payment-requests'
        base = self.payment_body(invoice)
        without = dict(base)
        del without['invoice_id']
        self.post(path, without, status=422)
        self.post(path, base | {'invoice_id': 'missing'}, status=404)
        self.post(path, base | {'invoice_reference': 'INV-X'}, status=422)
        self.post(path, base | {'invoice_date': '2026-10-16'}, status=422)
        self.post(path, base | {'due_date': '2026-10-31'}, status=422)
        self.post(path, base | {'amount': '13.89'}, status=409)
        payment = self.post(path, base, key='pay')
        self.assertEqual(payment['amount'], '10.00')
        self.post(path, base | {'reference': 'PAY-002'}, status=409)
        # Tolak lalu ajukan ulang invoice yang sama: boleh (UNIQUE komposit
        # dicabut di skema 62); duplikat AKTIF tetap ditolak.
        decision = self.post('/api/supplier-payment-requests/' + payment['id'] + '/decisions',
                             dict(status='rejected', expected_revision=payment['revision'],
                                  reason='Koreksi nominal'))
        self.assertEqual(decision['status'], 'rejected')
        again = self.post(path, base | {'reference': 'PAY-003'})
        self.assertEqual(again['status'], 'submitted')

    def test_approval_is_permission_not_settlement(self):
        with closing(sqlite3.connect(self.path)) as raw:
            tables_before = {row[0] for row in
                             raw.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        po = self.received_po()
        invoice = self.register_invoice(po, key='inv-1')
        payment = self.request_payment(po, invoice, key='pay')
        approved = self.post('/api/supplier-payment-requests/' + payment['id'] + '/decisions',
                             dict(status='approved', expected_revision=payment['revision'],
                                  reason='Setuju dibayar nanti'))
        self.assertEqual(approved['status'], 'approved')
        # Approval tidak membuat jurnal/settlement: tidak ada tabel pembayaran
        # aktual baru, dan tidak ada jurnal yang menunjuk payment request ini.
        with closing(sqlite3.connect(self.path)) as raw:
            tables_after = {row[0] for row in
                            raw.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            journals = raw.execute(
                "SELECT COUNT(*) FROM journals WHERE source_id LIKE ?", ('%'+payment['id']+'%',)
            ).fetchone()[0]
        self.assertEqual(tables_after, tables_before)
        self.assertEqual(journals, 0)

    # -- Unit scope ----------------------------------------------------------
    def test_unit_scope_restricts_invoice_and_payment(self):
        unit = self.post('/api/business-units',
                         dict(code='U-SATU', name='Unit Satu', reason='Uji scope'))
        limited = self.app.state.store.provision_user('Operator unit', 'operator')
        response = self.client.put('/api/users/' + limited['id'] + '/units',
                                   json=dict(business_unit_ids=[unit['id']],
                                             all_units=False, reason='Uji scope'))
        self.assertEqual(response.status_code, 200, response.text)
        stranger = self.app.state.store.provision_user('Operator lain', 'operator')
        response = self.client.put('/api/users/' + stranger['id'] + '/units',
                                   json=dict(business_unit_ids=[], all_units=False,
                                             reason='Uji scope'))
        self.assertEqual(response.status_code, 200, response.text)

        material = self.material(code='KAIN-U1')
        pr = self.decide(self.create(self.payload(material, reference='PR-U1')), 'approved')
        payload = dict(reference='PO-U1', request_id=pr['id'],
                       expected_revision=pr['revision'], supplier_id=self.supplier()['id'],
                       expected_date='2026-10-15', terms='Tunai', reason='Uji',
                       business_unit_id=unit['id'],
                       prices=[dict(material_id=material['id'], unit_price='7.00')])
        # Operator tanpa akses unit tidak bisa menerbitkan PO ber-unit.
        self.post('/api/purchase-orders', payload, api_key=stranger['api_key'], status=403)
        issued = self.issue(payload, api_key=limited['api_key'])
        self.assertEqual(issued['business_unit_id'], unit['id'])
        self.receive(issued, dict(material_id=material['id'], reference='BATCH-PO-U1',
                                  quantity='2', location='Rak A',
                                  received_date='2026-10-16', reason='Diterima'),
                     api_key=stranger['api_key'], status=403)
        self.receive(issued, dict(material_id=material['id'], reference='BATCH-PO-U1',
                                  quantity='2', location='Rak A',
                                  received_date='2026-10-16', reason='Diterima'),
                     api_key=limited['api_key'])
        self.register_invoice(issued, api_key=stranger['api_key'], status=403)
        invoice = self.register_invoice(issued, api_key=limited['api_key'], key='inv-u1',
                                        changes={'quantity': '2'})
        self.assertEqual(invoice['total'], '14.00')
        payment = self.request_payment(issued, invoice, api_key=stranger['api_key'],
                                       status=403)
        payment = self.request_payment(issued, invoice, api_key=limited['api_key'],
                                       key='pay-u1')
        self.assertEqual(payment['status'], 'submitted')

    # -- Konkurensi ----------------------------------------------------------
    def test_concurrent_invoice_registration_keeps_single_row(self):
        po = self.received_po()
        barrier = Barrier(2)

        def attempt(index):
            from fastapi.testclient import TestClient
            with TestClient(self.app) as client:
                client.headers['X-API-Key'] = self.admin['api_key']
                barrier.wait(timeout=10)
                return client.post('/api/supplier-invoices', json=self.invoice_body(po),
                                   headers={'Idempotency-Key': 'inv-race-' + str(index)}
                                   ).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(attempt, range(2))), [201, 409])
        self.assertEqual(len(self.client.get('/api/supplier-invoices').json()), 1)

    # -- Bukti adapter jurnal penerimaan (#46, tanpa engine kedua) --------------
    def test_receipt_journal_adapter_is_idempotent_and_explicit(self):
        # Adapter A01: posting penerimaan PO ke jurnal umum memakai source
        # identity ('beeloft','purchasing','po_receipt',po_id,'',1) sehingga
        # replay tidak double-count; tidak ada auto-posting dari receive.
        po = self.received_po()
        self.post('/api/coa-accounts/seed-demo', {}, key='seed-coa')
        period = self.post('/api/accounting-periods',
                           dict(code='2026-10', start_date='2026-10-01',
                                end_date='2026-10-31'), key='period-2026-10')
        body = dict(period_id=period['id'], journal_date='2026-10-15',
                    receipts=[dict(material_id=po['lines'][0]['material_id'],
                                   quantity='1.125')])
        journal = self.post('/api/purchase-orders/' + po['id'] + '/receipt-journal',
                            body, key='j-post')
        self.assertEqual((journal['total_debit_minor'], journal['total_credit_minor']),
                         (1388, 1388))
        self.assertEqual((journal['source_system'], journal['source_account'],
                          journal['source_entity_type'], journal['source_id'],
                          journal['source_line_id'], journal['source_revision']),
                         ('beeloft', 'purchasing', 'po_receipt', po['id'], '', 1))
        # Replay dengan idempotency key berbeda: jurnal yang sama, tanpa
        # double-count; tetap eksplisit (tidak terpicu otomatis oleh receive).
        replay = self.post('/api/purchase-orders/' + po['id'] + '/receipt-journal',
                           body, key='j-post-retry')
        self.assertEqual(replay['id'], journal['id'])
        journals = self.client.get('/api/journals', params={'period_id': period['id']}).json()
        self.assertEqual(journals['total'], 1)
        self.assertEqual(journals['items'][0]['id'], journal['id'])

    # -- Migrasi 61 -> 62 ----------------------------------------------------
    def test_upgrade_61_to_62_preserves_payment_history(self):
        po = self.received_po()
        admin = self.admin
        sql_file = Path('beeloft/supplier_payment_approvals.sql').read_text()
        create_table = re.search(r'CREATE TABLE IF NOT EXISTS supplier_payment_requests \(.*?\);',
                                 sql_file, re.S).group(0)
        triggers = re.findall(r'CREATE TRIGGER.*?END;', sql_file, re.S)
        legacy_id = 'spr-legacy-1'
        with closing(sqlite3.connect(self.path)) as raw:
            raw.execute('PRAGMA foreign_keys=OFF')
            raw.execute('DROP TRIGGER IF EXISTS supplier_payment_request_event_valid')
            raw.execute('DROP TRIGGER IF EXISTS supplier_payment_request_preserve_receipt')
            # Bangun bentuk lama di bawah nama temp, lalu tukar: FK
            # supplier_payment_request_events.request_id tetap menunjuk nama
            # 'supplier_payment_requests' seperti DB skema 61 asli.
            raw.executescript(create_table.replace(
                'CREATE TABLE IF NOT EXISTS supplier_payment_requests (',
                'CREATE TABLE spr_shape_60 ('))
            columns = ('sequence,id,reference,purchase_order_id,invoice_reference,'
                       'invoice_date,due_date,amount_minor,reason,actor_id,created_at')
            raw.execute('INSERT INTO spr_shape_60 (' + columns + ') '
                        'SELECT ' + columns + ' FROM supplier_payment_requests')
            raw.execute('DROP TABLE supplier_payment_requests')
            raw.execute('ALTER TABLE spr_shape_60 RENAME TO supplier_payment_requests')
            for trigger in triggers:
                raw.execute(trigger)
            # Payment request legacy (pra-#50): tanpa invoice_id.
            raw.execute(
                'INSERT INTO supplier_payment_requests (id,reference,purchase_order_id,'
                'invoice_reference,invoice_date,due_date,amount_minor,reason,actor_id,'
                'created_at) VALUES (?,?,?,?,?,?,?,?,?,?)',
                (legacy_id, 'PAY-LEGACY', po['id'], 'INV-LEGACY', '2026-10-14',
                 '2026-10-28', 1000, 'Tagihan lama', admin['id'], '2026-10-14T00:00:00'))
            raw.execute(
                'INSERT INTO supplier_payment_request_events (request_id,status,reason,'
                'actor_id,created_at) VALUES (?,?,?,?,?)',
                (legacy_id, 'submitted', 'Tagihan lama', admin['id'], '2026-10-14T00:00:00'))
            raw.execute('PRAGMA user_version=61')
            raw.commit()

        Store(self.path)
        with closing(sqlite3.connect(self.path)) as raw:
            self.assertEqual(raw.execute('PRAGMA user_version').fetchone()[0], 64)
            row = raw.execute('SELECT invoice_id,invoice_reference FROM '
                              'supplier_payment_requests WHERE id=?', (legacy_id,)).fetchone()
            self.assertEqual(row, (None, 'INV-LEGACY'))
            self.assertEqual(raw.execute('PRAGMA foreign_key_check').fetchall(), [])
            names = {name for (name,) in raw.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger'")}
        self.assertTrue({'supplier_payment_request_event_valid',
                         'supplier_payment_request_preserve_receipt',
                         'supplier_payment_request_invoice_valid'} <= names)

        # Histori legacy tetap bisa dibaca; invoice baru bisa didaftarkan untuk
        # PO yang sama, dan pengajuan ulang setelah reject tidak lagi diblokir
        # UNIQUE komposit lama.
        history = self.client.get('/api/purchase-orders/' + po['id'] + '/payment-requests').json()
        self.assertEqual(history[0]['invoice'], None)
        invoice = self.register_invoice(po, key='inv-migrated',
                                        changes={'reference': 'INV-LEGACY'})
        decided = self.post('/api/supplier-payment-requests/' + legacy_id + '/decisions',
                            dict(status='rejected', expected_revision=1,
                                 reason='Ganti invoice terdaftar'))
        self.assertEqual(decided['status'], 'rejected')
        resubmitted = self.request_payment(po, invoice,
                                           changes={'reference': 'PAY-LEGACY-2'})
        self.assertEqual(resubmitted['status'], 'submitted')
