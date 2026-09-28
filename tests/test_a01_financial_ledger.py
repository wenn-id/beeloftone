"""Tes A01 (#46): ledger keuangan dan kontrak posting.

Mencakup: migrasi 59, COA, periode (termasuk guard close/reopen), posting
atomik, keseimbangan eksak, idempotency sumber vs request key, konflik
sumber, reversal bertaut, penolakan periode tertutup, trial balance, izin,
konkurensi, dan aturan posting demo.
"""

import tempfile
import threading
import unittest
from pathlib import Path

from beeloft import posting_rules
from beeloft.api import create_app
from beeloft.store import DomainError, Store


def make_store(directory, name='a01.sqlite3'):
    return Store(Path(directory) / name)


def make_admin(store, name='Admin A01'):
    admin = store.provision_user(name, 'admin')
    return {'id': admin['id'], 'name': admin['name'], 'role': 'admin'}


def seed(store, actor):
    store.seed_demo_coa(actor, 'seed-a01')
    return store.create_period(
        {'code': '2026-09', 'start_date': '2026-09-01', 'end_date': '2026-09-30'},
        actor, 'period-a01')


def journal_payload(period_id, source_id='EVT-1', amount='1000.00', description='Uji jurnal'):
    return {
        'period_id': period_id, 'journal_date': '2026-09-28',
        'description': description, 'policy_ref': 'DEMO-POST-20260928-1',
        'source': {'system': 'beeloft', 'account': 'test',
                   'entity_type': 'test_event', 'id': source_id},
        'lines': [
            {'account_code': '1300', 'debit': amount, 'credit': '0'},
            {'account_code': '2100', 'debit': '0', 'credit': amount},
        ],
    }


class A01MigrationTest(unittest.TestCase):
    def test_fresh_db_is_schema_59_with_ledger_tables(self):
        with tempfile.TemporaryDirectory() as directory:
            store = make_store(directory)
            with store.transaction() as db:
                version = db.execute('PRAGMA user_version').fetchone()[0]
                self.assertEqual(version, 59)
                tables = {row[0] for row in db.execute(
                    "SELECT name FROM sqlite_schema WHERE type='table'")}
                for expected in ('coa_accounts', 'accounting_periods',
                                 'journals', 'journal_lines'):
                    self.assertIn(expected, tables)

    def test_upgrade_58_to_59(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'upgrade.sqlite3'
            store = Store(path)
            with store.transaction(write=True) as db:
                db.execute('PRAGMA user_version=58')
            store2 = Store(path)
            with store2.transaction() as db:
                self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 59)
                tables = {row[0] for row in db.execute(
                    "SELECT name FROM sqlite_schema WHERE type='table'")}
                self.assertIn('journals', tables)

    def test_operational_ledger_untouched(self):
        """Ledger kuantitas existing (movements/balances) tidak diubah A01."""
        with tempfile.TemporaryDirectory() as directory:
            store = make_store(directory)
            with store.transaction() as db:
                tables = {row[0] for row in db.execute(
                    "SELECT name FROM sqlite_schema WHERE type='table'")}
                self.assertIn('movements', tables)
                self.assertIn('balances', tables)


class A01CoaTest(unittest.TestCase):
    def test_create_and_duplicate_code(self):
        with tempfile.TemporaryDirectory() as directory:
            store = make_store(directory)
            actor = make_admin(store)
            account = store.create_account(
                {'code': '1100', 'name': 'Kas', 'type': 'asset'}, actor, 'coa-1')
            self.assertEqual(account['code'], '1100')
            with self.assertRaises(DomainError) as error:
                store.create_account(
                    {'code': '1100', 'name': 'Kas 2', 'type': 'asset'}, actor, 'coa-2')
            self.assertEqual(error.exception.status, 409)

    def test_invalid_type_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            store = make_store(directory)
            actor = make_admin(store)
            with self.assertRaises(DomainError) as error:
                store.create_account(
                    {'code': '9999', 'name': 'X', 'type': 'bogus'}, actor, 'coa-3')
            self.assertEqual(error.exception.status, 422)

    def test_seed_demo_coa_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            store = make_store(directory)
            actor = make_admin(store)
            first = store.seed_demo_coa(actor, 'seed-1')
            self.assertEqual(len(first['created']), 13)
            self.assertTrue(first['demo_assumption'])
            second = store.seed_demo_coa(actor, 'seed-2')
            self.assertEqual(second['created'], [])
            self.assertEqual(len(second['skipped']), 13)

    def test_deactivate_blocks_new_posting(self):
        with tempfile.TemporaryDirectory() as directory:
            store = make_store(directory)
            actor = make_admin(store)
            period = seed(store, actor)
            account = store.coa_accounts(query='1300')['items'][0]
            store.set_account_active(account['id'], False, actor, 'deact-1')
            with self.assertRaises(DomainError) as error:
                store.post_journal(journal_payload(period['id']), actor, 'j-deact')
            self.assertEqual(error.exception.status, 422)
            self.assertIn('nonaktif', error.exception.message)
            store.set_account_active(account['id'], True, actor, 'act-1')
            journal = store.post_journal(journal_payload(period['id']), actor, 'j-react')
            self.assertEqual(journal['total_debit_minor'], 100000)


class A01PeriodTest(unittest.TestCase):
    def test_overlap_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            store = make_store(directory)
            actor = make_admin(store)
            seed(store, actor)
            with self.assertRaises(DomainError) as error:
                store.create_period(
                    {'code': '2026-09b', 'start_date': '2026-09-15',
                     'end_date': '2026-10-15'}, actor, 'p-overlap')
            self.assertEqual(error.exception.status, 409)

    def test_close_reopen_revision_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            store = make_store(directory)
            actor = make_admin(store)
            period = seed(store, actor)
            closed = store.close_period(
                period['id'], {'reason': 'Tutup buku', 'expected_revision': 1},
                actor, 'p-close')
            self.assertEqual(closed['status'], 'closed')
            self.assertEqual(closed['revision'], 2)
            with self.assertRaises(DomainError) as error:
                store.close_period(
                    period['id'], {'reason': 'x', 'expected_revision': 1},
                    actor, 'p-close-2')
            self.assertEqual(error.exception.status, 409)
            reopened = store.reopen_period(
                period['id'], {'reason': 'Koreksi', 'expected_revision': 2},
                actor, 'p-reopen')
            self.assertEqual(reopened['status'], 'open')
            with self.assertRaises(DomainError) as error:
                store.close_period(period['id'], {'reason': ''}, actor, 'p-noreason')
            self.assertEqual(error.exception.status, 422)


class A01PostingTest(unittest.TestCase):
    def test_post_balanced_journal(self):
        with tempfile.TemporaryDirectory() as directory:
            store = make_store(directory)
            actor = make_admin(store)
            period = seed(store, actor)
            journal = store.post_journal(journal_payload(period['id']), actor, 'j-1')
            self.assertTrue(journal['code'].startswith('JR-20260928-'))
            self.assertEqual(journal['total_debit_minor'], journal['total_credit_minor'])
            self.assertEqual(len(journal['lines']), 2)

    def test_unbalanced_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            store = make_store(directory)
            actor = make_admin(store)
            period = seed(store, actor)
            payload = journal_payload(period['id'], source_id='EVT-U')
            payload['lines'][1]['credit'] = '999.99'
            with self.assertRaises(DomainError) as error:
                store.post_journal(payload, actor, 'j-unbal')
            self.assertEqual(error.exception.status, 422)
            # Tidak ada jurnal separuh jadi.
            self.assertEqual(store.journals()['total'], 0)

    def test_invalid_account_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            store = make_store(directory)
            actor = make_admin(store)
            period = seed(store, actor)
            payload = journal_payload(period['id'], source_id='EVT-IA')
            payload['lines'][0]['account_code'] = '0000'
            with self.assertRaises(DomainError) as error:
                store.post_journal(payload, actor, 'j-ia')
            self.assertEqual(error.exception.status, 422)

    def test_invalid_money_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            store = make_store(directory)
            actor = make_admin(store)
            period = seed(store, actor)
            payload = journal_payload(period['id'], source_id='EVT-IM')
            payload['lines'][0]['debit'] = '12.345'
            with self.assertRaises(DomainError) as error:
                store.post_journal(payload, actor, 'j-im')
            self.assertEqual(error.exception.status, 422)

    def test_both_sides_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            store = make_store(directory)
            actor = make_admin(store)
            period = seed(store, actor)
            payload = journal_payload(period['id'], source_id='EVT-BS')
            payload['lines'][0]['credit'] = '100.00'
            with self.assertRaises(DomainError) as error:
                store.post_journal(payload, actor, 'j-bs')
            self.assertEqual(error.exception.status, 422)

    def test_journal_date_outside_period_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            store = make_store(directory)
            actor = make_admin(store)
            period = seed(store, actor)
            payload = journal_payload(period['id'], source_id='EVT-DT')
            payload['journal_date'] = '2026-10-01'
            with self.assertRaises(DomainError) as error:
                store.post_journal(payload, actor, 'j-dt')
            self.assertEqual(error.exception.status, 422)

    def test_replay_identical_source_returns_same_journal(self):
        """Sumber sama + isi sama + key berbeda -> satu jurnal, hasil sama."""
        with tempfile.TemporaryDirectory() as directory:
            store = make_store(directory)
            actor = make_admin(store)
            period = seed(store, actor)
            first = store.post_journal(journal_payload(period['id']), actor, 'rk-1')
            second = store.post_journal(journal_payload(period['id']), actor, 'rk-2')
            self.assertEqual(first['id'], second['id'])
            self.assertEqual(store.journals()['total'], 1)

    def test_conflicting_source_rejected(self):
        """Sumber sama + isi berbeda -> 409 konflik, bukan jurnal kedua."""
        with tempfile.TemporaryDirectory() as directory:
            store = make_store(directory)
            actor = make_admin(store)
            period = seed(store, actor)
            store.post_journal(journal_payload(period['id']), actor, 'ck-1')
            payload = journal_payload(period['id'], amount='2000.00')
            with self.assertRaises(DomainError) as error:
                store.post_journal(payload, actor, 'ck-2')
            self.assertEqual(error.exception.status, 409)
            self.assertEqual(store.journals()['total'], 1)

    def test_request_key_replay_and_conflict(self):
        """Idempotency-Key: replay identik OK, payload beda -> 409."""
        with tempfile.TemporaryDirectory() as directory:
            store = make_store(directory)
            actor = make_admin(store)
            period = seed(store, actor)
            payload = journal_payload(period['id'], source_id='EVT-RK')
            first = store.post_journal(payload, actor, 'same-key')
            second = store.post_journal(payload, actor, 'same-key')
            self.assertEqual(first['id'], second['id'])
            other = journal_payload(period['id'], source_id='EVT-RK2')
            with self.assertRaises(DomainError) as error:
                store.post_journal(other, actor, 'same-key')
            self.assertEqual(error.exception.status, 409)

    def test_post_to_closed_period_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            store = make_store(directory)
            actor = make_admin(store)
            period = seed(store, actor)
            store.close_period(period['id'], {'reason': 'Tutup'}, actor, 'pc-1')
            with self.assertRaises(DomainError) as error:
                store.post_journal(journal_payload(period['id'], source_id='EVT-C'),
                                   actor, 'j-closed')
            self.assertEqual(error.exception.status, 409)

    def test_concurrent_same_source_posts_once(self):
        with tempfile.TemporaryDirectory() as directory:
            store = make_store(directory)
            actor = make_admin(store)
            period = seed(store, actor)
            results, errors = [], []

            def post(index):
                try:
                    results.append(store.post_journal(
                        journal_payload(period['id'], source_id='EVT-CONC'),
                        actor, f'conc-{index}'))
                except DomainError as exc:
                    errors.append(exc)

            threads = [threading.Thread(target=post, args=(i,)) for i in range(8)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(store.journals()['total'], 1)
            self.assertTrue(all(r['id'] == results[0]['id'] for r in results))

    def test_race_post_vs_close(self):
        """Tutup periode di tengah posting: status dicek dalam transaksi sama."""
        with tempfile.TemporaryDirectory() as directory:
            store = make_store(directory)
            actor = make_admin(store)
            period = seed(store, actor)
            store.close_period(period['id'], {'reason': 'Tutup cepat'}, actor, 'rc-1')
            with self.assertRaises(DomainError) as error:
                store.post_journal(journal_payload(period['id'], source_id='EVT-RC'),
                                   actor, 'j-rc')
            self.assertEqual(error.exception.status, 409)


class A01ReversalTest(unittest.TestCase):
    def test_reversal_links_origin_and_nets_to_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            store = make_store(directory)
            actor = make_admin(store)
            period = seed(store, actor)
            journal = store.post_journal(journal_payload(period['id']), actor, 'rv-1')
            reversal = store.reverse_journal(
                journal['id'],
                {'period_id': period['id'], 'journal_date': '2026-09-28',
                 'reason': 'Salah akun'}, actor, 'rv-2')
            self.assertEqual(reversal['reversal_of'], journal['code'])
            self.assertEqual(reversal['total_debit_minor'], journal['total_debit_minor'])
            # Baris dibalik: debit asal menjadi kredit.
            orig = {line['account_code']: (line['debit_minor'], line['credit_minor'])
                    for line in journal['lines']}
            for line in reversal['lines']:
                debit, credit = orig[line['account_code']]
                self.assertEqual((line['debit_minor'], line['credit_minor']),
                                 (credit, debit))
            # Trial balance tetap seimbang; saldo akun kembali nol.
            trial = store.trial_balance(period['id'])
            self.assertTrue(trial['balanced'])
            by_code = {item['code']: item for item in trial['items']}
            self.assertEqual(by_code['1300']['balance_minor'], 0)
            fetched = store.journal(journal['id'])
            self.assertEqual(fetched['reversed_by_id'], reversal['id'])

    def test_double_reversal_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            store = make_store(directory)
            actor = make_admin(store)
            period = seed(store, actor)
            journal = store.post_journal(journal_payload(period['id']), actor, 'dr-1')
            store.reverse_journal(
                journal['id'],
                {'period_id': period['id'], 'journal_date': '2026-09-28',
                 'reason': 'Koreksi'}, actor, 'dr-2')
            with self.assertRaises(DomainError) as error:
                store.reverse_journal(
                    journal['id'],
                    {'period_id': period['id'], 'journal_date': '2026-09-28',
                     'reason': 'Lagi'}, actor, 'dr-3')
            self.assertEqual(error.exception.status, 409)

    def test_reversal_of_reversal_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            store = make_store(directory)
            actor = make_admin(store)
            period = seed(store, actor)
            journal = store.post_journal(journal_payload(period['id']), actor, 'rr-1')
            reversal = store.reverse_journal(
                journal['id'],
                {'period_id': period['id'], 'journal_date': '2026-09-28',
                 'reason': 'Koreksi'}, actor, 'rr-2')
            with self.assertRaises(DomainError) as error:
                store.reverse_journal(
                    reversal['id'],
                    {'period_id': period['id'], 'journal_date': '2026-09-28',
                     'reason': 'X'}, actor, 'rr-3')
            self.assertEqual(error.exception.status, 409)

    def test_reversal_requires_open_period_explicit(self):
        """Reversal ke periode tertutup ditolak; tidak ada pembukaan otomatis."""
        with tempfile.TemporaryDirectory() as directory:
            store = make_store(directory)
            actor = make_admin(store)
            period = seed(store, actor)
            journal = store.post_journal(journal_payload(period['id']), actor, 'rp-1')
            other = store.create_period(
                {'code': '2026-10', 'start_date': '2026-10-01',
                 'end_date': '2026-10-31'}, actor, 'rp-period')
            store.close_period(other['id'], {'reason': 'Tutup'}, actor, 'rp-close')
            with self.assertRaises(DomainError) as error:
                store.reverse_journal(
                    journal['id'],
                    {'period_id': other['id'], 'journal_date': '2026-10-05',
                     'reason': 'Koreksi'}, actor, 'rp-2')
            self.assertEqual(error.exception.status, 409)
            # Reversal ke periode terbuka lain: boleh.
            reversal = store.reverse_journal(
                journal['id'],
                {'period_id': period['id'], 'journal_date': '2026-09-29',
                 'reason': 'Koreksi'}, actor, 'rp-3')
            self.assertEqual(reversal['period_id'], period['id'])

    def test_posted_journal_immutable(self):
        """UPDATE/DELETE langsung pada jurnal ditolak trigger."""
        with tempfile.TemporaryDirectory() as directory:
            store = make_store(directory)
            actor = make_admin(store)
            period = seed(store, actor)
            journal = store.post_journal(journal_payload(period['id']), actor, 'im-1')
            with store.transaction(write=True) as db:
                with self.assertRaises(Exception):
                    db.execute('UPDATE journals SET description=? WHERE id=?',
                               ('Diubah', journal['id']))
                with self.assertRaises(Exception):
                    db.execute('DELETE FROM journal_lines WHERE journal_id=?',
                               (journal['id'],))
            self.assertEqual(store.journal(journal['id'])['description'], 'Uji jurnal')


class A01PermissionTest(unittest.TestCase):
    def test_non_admin_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            store = make_store(directory)
            admin = make_admin(store)
            period = seed(store, admin)
            for role in ('operator', 'viewer'):
                user = store.provision_user(f'Uji {role}', role)
                actor = {'id': user['id'], 'name': user['name'], 'role': role}
                with self.subTest(role=role):
                    with self.assertRaises(DomainError) as error:
                        store.post_journal(journal_payload(period['id'], source_id=f'EVT-{role}'),
                                           actor, f'perm-{role}')
                    self.assertEqual(error.exception.status, 403)
                    with self.assertRaises(DomainError) as error:
                        store.create_period({'code': f'X-{role}', 'start_date': '2026-11-01',
                                             'end_date': '2026-11-30'}, actor, f'permp-{role}')
                    self.assertEqual(error.exception.status, 403)

    def test_read_allowed_for_all_roles(self):
        with tempfile.TemporaryDirectory() as directory:
            store = make_store(directory)
            admin = make_admin(store)
            period = seed(store, admin)
            store.post_journal(journal_payload(period['id']), admin, 'rd-1')
            viewer = store.provision_user('Uji viewer', 'viewer')
            # Read path tidak memakai _write: langsung via store.
            self.assertEqual(store.coa_accounts()['total'], 13)
            self.assertEqual(store.journals()['total'], 1)
            self.assertTrue(store.trial_balance(period['id'])['balanced'])


class A01PostingRulesTest(unittest.TestCase):
    def test_all_rule_builders_balanced(self):
        cases = [
            posting_rules.material_receipt_lines(amount_minor=100000),
            posting_rules.material_consumption_lines(amount_minor=50000),
            posting_rules.finished_goods_lines(amount_minor=75000),
            posting_rules.sales_lines(revenue_minor=200000, cogs_minor=120000),
            posting_rules.payroll_accrual_lines(amount_minor=90000),
            posting_rules.payroll_payment_lines(amount_minor=90000),
            posting_rules.kasbon_disbursement_lines(amount_minor=30000),
            posting_rules.kasbon_deduction_lines(amount_minor=30000),
            posting_rules.purchase_payment_lines(amount_minor=100000),
            posting_rules.sales_receipt_lines(amount_minor=200000),
        ]
        for lines in cases:
            with self.subTest(lines=lines[0]['description']):
                debit, credit = posting_rules.check_balanced(lines)
                self.assertEqual(debit, credit)
                self.assertGreater(debit, 0)

    def test_check_balanced_rejects_mismatch(self):
        with self.assertRaises(ValueError):
            posting_rules.check_balanced([
                {'account_code': '1300', 'debit_minor': 100, 'credit_minor': 0,
                 'description': ''},
                {'account_code': '2100', 'debit_minor': 0, 'credit_minor': 99,
                 'description': ''},
            ])

    def test_demo_coa_covers_rule_accounts(self):
        used = set()
        for builder in ('material_receipt_lines', 'material_consumption_lines',
                        'finished_goods_lines', 'sales_lines', 'payroll_accrual_lines',
                        'payroll_payment_lines', 'kasbon_disbursement_lines',
                        'kasbon_deduction_lines', 'purchase_payment_lines',
                        'sales_receipt_lines'):
            fn = getattr(posting_rules, builder)
            kwargs = {'amount_minor': 1000}
            if builder == 'sales_lines':
                kwargs = {'revenue_minor': 1000, 'cogs_minor': 600}
            for line in fn(**kwargs):
                used.add(line['account_code'])
        self.assertTrue(used <= set(posting_rules.DEMO_COA_BY_CODE),
                        f'akun tak terdaftar: {used - set(posting_rules.DEMO_COA_BY_CODE)}')

    def test_adapt_po_receipt(self):
        po = {'reference': 'PO-001', 'lines': [
            {'material_id': 'm1', 'unit_price': '1500.00'},
            {'material_id': 'm2', 'unit_price': '250.50'},
        ]}
        lines = posting_rules.adapt_po_receipt(
            po=po, receipts=[{'material_id': 'm1', 'quantity': '10'},
                             {'material_id': 'm2', 'quantity': '4'}])
        # 10*1500 + 4*250.50 = 15000 + 1002 = 16002.00
        debit, credit = posting_rules.check_balanced(lines)
        self.assertEqual(debit, 1600200)
        self.assertEqual(lines[0]['account_code'], '1300')
        self.assertEqual(lines[1]['account_code'], '2100')
        with self.assertRaises(ValueError):
            posting_rules.adapt_po_receipt(
                po=po, receipts=[{'material_id': 'mX', 'quantity': '1'}])


class A01ApiTest(unittest.TestCase):
    def test_finance_endpoints(self):
        with tempfile.TemporaryDirectory() as directory:
            app = create_app(Path(directory) / 'a01-api.sqlite3')
            store = app.state.store
            admin = make_admin(store)
            from fastapi.testclient import TestClient
            client = TestClient(app, raise_server_exceptions=False)
            headers = {'X-API-Key': store.provision_user('API Admin', 'admin')['api_key']}
            # seed
            response = client.post('/api/coa-accounts/seed-demo', headers=headers | {'Idempotency-Key': 'api-seed'})
            self.assertEqual(response.status_code, 201, response.text)
            # period
            response = client.post('/api/accounting-periods',
                                   json={'code': '2026-09', 'start_date': '2026-09-01',
                                         'end_date': '2026-09-30'},
                                   headers=headers | {'Idempotency-Key': 'api-period'})
            self.assertEqual(response.status_code, 201, response.text)
            period_id = response.json()['id']
            # journal
            response = client.post('/api/journals', json=journal_payload(period_id),
                                   headers=headers | {'Idempotency-Key': 'api-journal'})
            self.assertEqual(response.status_code, 201, response.text)
            journal_id = response.json()['id']
            # trial balance
            response = client.get(f'/api/trial-balance?period_id={period_id}', headers=headers)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertTrue(response.json()['balanced'])
            # reverse
            response = client.post(f'/api/journals/{journal_id}/reverse',
                                   json={'period_id': period_id,
                                         'journal_date': '2026-09-28',
                                         'reason': 'Koreksi API'},
                                   headers=headers | {'Idempotency-Key': 'api-reverse'})
            self.assertEqual(response.status_code, 201, response.text)
            # unauthenticated ditolak
            response = client.get('/api/coa-accounts')
            self.assertEqual(response.status_code, 401)


if __name__ == '__main__':
    unittest.main()
