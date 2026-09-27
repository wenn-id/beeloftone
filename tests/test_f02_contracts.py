import csv
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from pydantic import ValidationError

from beeloft import contracts, models
from beeloft.api import create_app
from beeloft.store import DomainError, Store


REPO = Path(__file__).resolve().parent.parent


class F02ContractTest(unittest.TestCase):
    def test_baseline_fixture_matches_models_and_material_storage(self):
        fixture = json.loads((REPO / 'tests/fixtures/f02-contracts.json').read_text(encoding='utf-8'))
        case_ids = []
        for group in fixture['baseline_models']:
            model = getattr(models, group['model'])
            for case in group['cases']:
                case_ids.append(case['id'])
                with self.subTest(case=case['id']):
                    payload = group['base'] | case['input']
                    if 'error' in case:
                        self.assertEqual(case['error'], 422)
                        with self.assertRaises(ValidationError):
                            model.model_validate(payload)
                    else:
                        result = model.model_validate(payload).model_dump(mode='json')
                        for field, expected in case['expected'].items():
                            self.assertEqual(result[field], expected)
        for case in fixture['baseline_material_storage']:
            case_ids.append(case['id'])
            with self.subTest(case=case['id']):
                if 'error' in case:
                    with self.assertRaises(DomainError) as error:
                        Store._material_amount(case['quantity'], case['unit'])
                    self.assertEqual(error.exception.status, case['error'])
                else:
                    self.assertEqual(Store._material_amount(case['quantity'], case['unit']), case['expected'])
        # Target scenarios are review inputs, not an implementation or business oracle.
        for case in fixture['review_scenarios']:
            case_ids.append(case['id'])
            self.assertIn(case['status'], ('PROPOSED', 'BLOCKED_F01'))
            self.assertTrue(case['input'])
            self.assertTrue(case['decisions'])
            self.assertTrue(case['expected_invariant'])
            if case['status'] == 'BLOCKED_F01':
                self.assertIsNone(case['expected_business_result'])
        self.assertEqual(len(case_ids), len(set(case_ids)))

    def test_ownership_covers_persistent_tables_and_explicit_endpoints(self):
        with (REPO / 'docs/f02-ownership.csv').open(encoding='utf-8', newline='') as source:
            rows = list(csv.DictReader(source))
        identities = [(row['kind'], row['object']) for row in rows]
        self.assertEqual(len(identities), len(set(identities)))
        for row in rows:
            self.assertIn(row['kind'], ('table', 'endpoint'))
            self.assertIn(row['owner_proposed'], ('A0', 'A1', 'A2', 'A3'))
            self.assertTrue(row['packages'])
            self.assertTrue(set(row['reviewer_proposed'].split('/')) <= {'A0', 'A1', 'A2', 'A3'})
            self.assertTrue((REPO / row['source'].split('#')[0]).is_file(), row['source'])
        with tempfile.TemporaryDirectory() as directory:
            app = create_app(Path(directory) / 'f02.sqlite3')
            with app.state.store.transaction() as db:
                tables = {row[0] for row in db.execute(
                    "SELECT name FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
            endpoints = {f'{method} {route.path}' for route in app.routes
                         if getattr(getattr(route, 'endpoint', None), '__module__', None) == 'beeloft.api'
                         for method in route.methods}
        self.assertEqual({row['object'] for row in rows if row['kind'] == 'table'}, tables)
        self.assertEqual({row['object'] for row in rows if row['kind'] == 'endpoint'}, endpoints)


if __name__ == '__main__':
    unittest.main()


def _hydrate(value):
    """Ubah marker {"__decimal__": s} pada fixture menjadi Decimal."""
    if isinstance(value, dict) and set(value) == {'__decimal__'}:
        return Decimal(value['__decimal__'])
    if isinstance(value, list):
        return [_hydrate(item) for item in value]
    if isinstance(value, dict):
        return {key: _hydrate(item) for key, item in value.items()}
    return value


def _normalize(result):
    """Samakan tuple->list agar sebanding dengan JSON fixture."""
    if isinstance(result, (tuple, list)):
        return [_normalize(item) for item in result]
    if isinstance(result, dict):
        return {key: _normalize(item) for key, item in result.items()}
    return result


class F02Issue41ContractTest(unittest.TestCase):
    """Invariant teknis #41 — dieksekusi terhadap beeloft/contracts.py dan Store.

    Bukan business acceptance: vektor memakai data sintetis dan policy
    DEMO-20260928-1 yang dilabeli DEMO_ASSUMPTION.
    """

    def test_contract_vectors(self):
        fixture = json.loads((REPO / 'tests/fixtures/f02-contracts.json').read_text(encoding='utf-8'))
        self.assertEqual(fixture['contract_revision'], 'F02-draft-2')
        for vector in fixture['contract_vectors']:
            with self.subTest(vector=vector['id']):
                func = getattr(contracts, vector['function'])
                args = _hydrate(vector.get('args', []))
                kwargs = _hydrate(vector.get('kwargs', {}))
                if 'raises' in vector:
                    with self.assertRaises(getattr(__import__('builtins'), vector['raises'])):
                        func(*args, **kwargs)
                    continue
                result = _normalize(func(*args, **kwargs))
                if 'expected' in vector:
                    self.assertEqual(result, _normalize(_hydrate(vector['expected'])))
                if 'expected_wage_minor' in vector:
                    self.assertEqual(result['wage_minor'], vector['expected_wage_minor'])
                    self.assertEqual(result['calculation_policy_ref'], 'DEMO-20260928-1')
                if 'expected_total' in vector:
                    self.assertEqual(result['total'], vector['expected_total'])
                    self.assertEqual(len(result['excluded']), vector['expected_excluded'])

    def test_demo_assumptions_are_versioned_and_replaceable(self):
        fixture = json.loads((REPO / 'tests/fixtures/f02-contracts.json').read_text(encoding='utf-8'))
        assumptions = fixture['demo_assumptions']
        self.assertEqual(assumptions['policy_ref'], contracts.DEMO_POLICY.policy_ref)
        self.assertTrue(assumptions['scope'])
        for item in assumptions['assumptions']:
            self.assertTrue(item['id'].startswith('DA-'))
            self.assertTrue(item['statement'])
        # Policy bisa diganti tanpa mengubah kontrak: hasil membawa policy_ref.
        custom = contracts.ContractPolicy(policy_ref='CUSTOM-1', wage_money_rounding='DOWN')
        result = contracts.wage_for_realization(
            pcs=13, rate_per_lusin_minor=180000, rate_revision='R1', policy=custom)
        self.assertEqual(result['calculation_policy_ref'], 'CUSTOM-1')
        self.assertNotEqual(
            result['wage_minor'],
            contracts.wage_for_realization(
                pcs=13, rate_per_lusin_minor=180000, rate_revision='R1')['wage_minor'])

    def test_replay_same_idempotency_key_produces_no_second_effect(self):
        """Replay key+payload sama: hasil tersimpan, efek bisnis tepat satu."""
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / 'f02-replay.sqlite3')
            admin = store.provision_user('Admin F02', 'admin')
            actor = {'id': admin['id']}
            calls = []

            def perform(db):
                calls.append(1)
                return {'ok': True}

            key = 'f02-41-replay-001'
            first = store._write(actor, ('admin',), key, 'f02:contract-test', {'n': 1}, perform)
            second = store._write(actor, ('admin',), key, 'f02:contract-test', {'n': 1}, perform)
            self.assertEqual(first, second)
            self.assertEqual(len(calls), 1, 'efek bisnis harus tepat satu kali')
            with self.assertRaises(DomainError) as error:
                store._write(actor, ('admin',), key, 'f02:contract-test', {'n': 2}, perform)
            self.assertEqual(error.exception.status, 409)
            self.assertEqual(len(calls), 1)

    def test_reversal_tables_reference_origin(self):
        """Kontrak reversal: tiap tabel *_reversals wajib menautkan tepat satu
        transaksi asal (kolom <entity>_id) plus reason/actor/created_at.
        Record asli dipertahankan; reversal menautkan, bukan menimpa."""
        with tempfile.TemporaryDirectory() as directory:
            app = create_app(Path(directory) / 'f02-rev.sqlite3')
            with app.state.store.transaction() as db:
                tables = [row[0] for row in db.execute(
                    "SELECT name FROM sqlite_schema WHERE type='table' AND name LIKE '%_reversals'")]
                self.assertTrue(tables, 'tidak ada tabel reversal ditemukan')
                for table in tables:
                    with self.subTest(table=table):
                        columns = {row[1] for row in db.execute(f'PRAGMA table_info({table})')}
                        self.assertTrue({'reason', 'actor_id', 'created_at'} <= columns)
                        links = columns - {'reason', 'actor_id', 'created_at'}
                        self.assertEqual(len(links), 1,
                                         f'{table} wajib menautkan tepat satu transaksi asal')
                        link = next(iter(links))
                        self.assertTrue(link.endswith('_id'),
                                        f'{table}.{link} harus FK ke transaksi asal')

    def test_approved_paid_posted_are_independent_dimensions(self):
        """Approved tidak otomatis berarti paid atau posted: tiga ref bukti
        independen, dan memakai ulang ref yang sama ditolak."""
        record = contracts.validate_state_record({
            'approval_ref': 'APR-20260928-001',
            'payment_ref': 'PAY-20260928-001',
            'posting_ref': None,
        })
        self.assertIsNone(record['posting_ref'])
        # Hanya approval: sah, tetapi bukan bukti payment/posting.
        only_approved = contracts.validate_state_record({'approval_ref': 'APR-2'})
        self.assertNotIn('payment_ref', {k for k, v in only_approved.items() if v})
        with self.assertRaises(ValueError):
            contracts.validate_state_record({'approval_ref': 'SAMA', 'payment_ref': 'SAMA'})

    def test_native_and_snapshot_are_never_double_counted(self):
        """Skenario ala payroll: snapshot Mekari + record native untuk transaksi
        ekonomi yang sama dihitung tepat sekali; snapshot hanya rekonsiliasi."""
        records = [
            {'canonical_transaction_id': 'PAYROLL-2026-09-BUDI', 'measure': 'net_minor',
             'amount': 5500000, 'source_kind': 'external_snapshot'},
            {'canonical_transaction_id': 'PAYROLL-2026-09-BUDI', 'measure': 'net_minor',
             'amount': 5500000, 'source_kind': 'native'},
            {'canonical_transaction_id': 'PAYROLL-2026-09-SARI', 'measure': 'net_minor',
             'amount': 7200000, 'source_kind': 'native'},
        ]
        result = contracts.dedupe_contributions(records)
        self.assertEqual(result['total'], {'net_minor': 12700000})
        self.assertEqual(len(result['excluded']), 1)
        self.assertEqual(result['excluded'][0]['source_kind'], 'external_snapshot')
