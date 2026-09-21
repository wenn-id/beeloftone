import csv
import json
import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from beeloft import models
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
