"""Issue #49 — P02 parity planning dan cutting.

Rencana cutting (kode = referensi order), gate approval, parameter operasional
cutting (tanggal, PO, berat, rol, komposisi output), estimasi berlabel, dan
ekspor CSV. Aktual tetap lewat ledger existing tepat sekali; P02 tidak
menghitung kuantitas layak bayar.
"""
import sqlite3
from contextlib import closing
from unittest import TestCase
from unittest.mock import patch
from urllib.parse import unquote

import test_cutting as cutting_tests


class PlanningCuttingTest(TestCase):
    setUp = cutting_tests.CuttingTest.setUp
    post = cutting_tests.CuttingTest.post
    order = cutting_tests.CuttingTest.order
    material = cutting_tests.CuttingTest.material
    receipt = cutting_tests.CuttingTest.receipt
    issue = cutting_tests.CuttingTest.issue
    setup_stock = cutting_tests.CuttingTest.setup_stock
    prepare = cutting_tests.CuttingTest.prepare
    approve_cutting_plan = cutting_tests.CuttingTest.approve_cutting_plan

    def plan(self, order, **options):
        response = self.client.get('/api/orders/'+order['id']+'/plan',
                                   headers={'X-API-Key': options.get('api_key', self.admin['api_key'])})
        self.assertEqual(response.status_code, options.get('status', 200), response.text)
        return response.json()

    def decide_plan(self, order, mode, revision, **options):
        return self.post('/api/orders/'+order['id']+'/plan/'+mode,
                         dict(revision=revision, reason='Keputusan tes'), **options)

    def approved_order_with_cutting_setup(self, ref='PLAN-P02-001'):
        batch, order, _ = self.setup_stock()
        issue = self.issue(batch, order, '6')
        line = order['lines'][0]['id']
        self.post('/api/movements', dict(line_id=line, from_stage='planned', to_stage='cutting', quantity=30))
        self.approve_cutting_plan(order)
        return batch, order, issue, line

    def cut_body(self, issue, line, **changes):
        body = dict(reference='CUT-P02-001', issue_id=issue['id'], used='2.125', waste='0.375',
                    reason='Potongan selesai', cut_date='2026-09-28',
                    outputs=[dict(line_id=line, quantity=20)])
        body.update(changes)
        return body

    def cut(self, order, body, **options):
        return self.post('/api/orders/'+order['id']+'/cutting-runs', body, **options)

    # -- rencana: identitas, status, otorisasi ---------------------------------

    def test_order_creates_draft_plan_with_reference_as_code(self):
        order = self.order()
        plan = self.plan(order)
        self.assertEqual(plan['plan_code'], order['reference'])
        self.assertEqual(plan['status'], 'draft')
        self.assertEqual(plan['revision'], 0)
        self.assertEqual(plan['target_quantity'], order['target_quantity'])
        self.assertEqual(plan['realized_quantity'], 0)
        self.assertEqual(plan['remaining_target'], order['target_quantity'])
        self.assertEqual(len(plan['lines']), len(order['lines']))

    def test_plan_note_and_start_date_stored(self):
        order = self.order(plan_note='Prioritas kirim Senin', plan_start_date='2026-09-28')
        plan = self.plan(order)
        self.assertEqual(plan['note'], 'Prioritas kirim Senin')
        self.assertEqual(plan['start_date'], '2026-09-28')

    def test_approve_requires_admin_and_revision_guard(self):
        order = self.order()
        plan = self.plan(order)
        self.decide_plan(order, 'approve', plan['revision'], status=403, api_key=self.operator['api_key'])
        self.decide_plan(order, 'approve', plan['revision'], status=403, api_key=self.viewer['api_key'])
        approved = self.decide_plan(order, 'approve', plan['revision'])
        self.assertEqual(approved['status'], 'approved')
        self.assertEqual(approved['revision'], plan['revision']+1)
        self.assertEqual(approved['approver_name'], self.admin['name'])
        # revisi basi ditolak; approve kedua ditolak
        self.decide_plan(order, 'approve', plan['revision'], status=409)
        self.decide_plan(order, 'approve', approved['revision'], status=409)

    def test_close_plan_blocks_further_cutting(self):
        batch, order, issue, line = self.approved_order_with_cutting_setup()
        plan = self.plan(order)
        closed = self.decide_plan(order, 'close', plan['revision'])
        self.assertEqual(closed['status'], 'closed')
        self.cut(order, self.cut_body(issue, line), status=422)
        # rencana tertutup tidak bisa disetujui/disentuh lagi
        self.decide_plan(order, 'approve', closed['revision'], status=409)
        self.decide_plan(order, 'close', closed['revision'], status=409)

    def test_plan_history_records_decisions(self):
        order = self.order()
        plan = self.plan(order)
        self.decide_plan(order, 'approve', plan['revision'])
        history = self.plan(order)['history']
        self.assertTrue(any(e['operation'].startswith('plan-approve') for e in history))

    # -- gate: cutting hanya untuk rencana approved ------------------------------

    def test_cutting_rejected_until_plan_approved(self):
        batch, order, _ = self.setup_stock()
        issue = self.issue(batch, order, '6')
        line = order['lines'][0]['id']
        self.post('/api/movements', dict(line_id=line, from_stage='planned', to_stage='cutting', quantity=30))
        body = self.cut_body(issue, line)
        self.cut(order, body, status=422, api_key=self.operator['api_key'])
        self.approve_cutting_plan(order)
        run = self.cut(order, body, key='gate-once', api_key=self.operator['api_key'])
        self.assertEqual(run['total_output'], 20)

    # -- parameter operasional ----------------------------------------------------

    def test_cut_date_required_and_validated(self):
        batch, order, issue, line = self.approved_order_with_cutting_setup()
        body = self.cut_body(issue, line)
        del body['cut_date']
        self.cut(order, body, status=422)
        self.cut(order, self.cut_body(issue, line, cut_date='28-09-2026'), status=422)

    def test_rolls_and_output_params_recorded_atomically(self):
        batch, order, issue, line = self.approved_order_with_cutting_setup()
        run = self.cut(order, self.cut_body(issue, line,
            weight_kg='24.500',
            rolls=[dict(roll_no=1, weight_kg='12.250', sheets=100, note='Rol A'),
                   dict(roll_no=2, weight_kg='12.250', sheets=100)],
            output_params=[dict(line_id=line, setelan_per_lembar=3,
                                product_weight_gram='180.500', material_used_gram='19500')]),
            key='detail-once')
        detail = run['detail']
        self.assertEqual(detail['cut_date'], '2026-09-28')
        self.assertEqual(detail['weight_kg'], '24.500')
        self.assertEqual(detail['roll_count'], 2)
        self.assertEqual(detail['total_sheets'], 200)
        self.assertEqual(detail['total_roll_weight_kg'], '24.500')
        self.assertTrue(detail['sheets_complete'])
        output = run['outputs'][0]
        self.assertEqual(output['setelan_per_lembar'], 3)
        self.assertEqual(output['product_weight_gram'], '180.500')
        self.assertEqual(output['material_used_gram'], '19500.000')

    def test_roll_number_unique_and_row_needs_weight_or_sheets(self):
        batch, order, issue, line = self.approved_order_with_cutting_setup()
        dup = [dict(roll_no=1, sheets=10), dict(roll_no=1, sheets=5)]
        self.cut(order, self.cut_body(issue, line, rolls=dup), status=422)
        empty = [dict(roll_no=1)]
        self.cut(order, self.cut_body(issue, line, rolls=empty), status=422)
        sheets_only = [dict(roll_no=1, sheets=50)]
        run = self.cut(order, self.cut_body(issue, line, rolls=sheets_only), key='sheets-only')
        self.assertEqual(run['detail']['total_sheets'], 50)
        self.assertIsNone(run['detail']['total_roll_weight_kg'])

    def test_decimal_places_limited_to_three(self):
        batch, order, issue, line = self.approved_order_with_cutting_setup()
        from beeloft.models import CuttingRunCreate

        def weights(value):
            return dict(weight_kg=value, rolls=[dict(roll_no=1, weight_kg=value, sheets=1)],
                        output_params=[dict(line_id=line, product_weight_gram=value,
                                            material_used_gram=value)])

        for value in ('garbage', '', '1.2.3', 'NaN', 'sNaN', 'Infinity', '-Infinity',
                      '0', '-1', '1000000.001', '1.2345'):
            with self.subTest(value=value):
                result = self.cut(order, self.cut_body(issue, line, **weights(value)), status=422)
                locations = {tuple(error['loc']) for error in result['detail']}
                self.assertEqual(locations, {
                    ('body', 'weight_kg'), ('body', 'rolls', 0, 'weight_kg'),
                    ('body', 'output_params', 0, 'product_weight_gram'),
                    ('body', 'output_params', 0, 'material_used_gram'),
                })
        for value, expected in ((None, None), ('0.001', '0.001'), ('1.2300', '1.230'),
                                ('1000000', '1000000.000')):
            with self.subTest(value=value):
                parsed = CuttingRunCreate(**self.cut_body(issue, line, **weights(value)))
                self.assertEqual(parsed.weight_kg, expected)
                self.assertEqual(parsed.rolls[0].weight_kg, expected)
                self.assertEqual(parsed.output_params[0].product_weight_gram, expected)
                self.assertEqual(parsed.output_params[0].material_used_gram, expected)

    def test_output_param_line_must_match_run_output(self):
        batch, order, issue, line = self.approved_order_with_cutting_setup()
        other = self.order()
        self.cut(order, self.cut_body(issue, line,
            output_params=[dict(line_id=other['lines'][0]['id'], setelan_per_lembar=2)]), status=422)

    # -- estimasi berlabel, bukan aktual ------------------------------------------

    def test_estimate_is_labeled_and_separate_from_actual(self):
        batch, order, issue, line = self.approved_order_with_cutting_setup()
        run = self.cut(order, self.cut_body(issue, line,
            rolls=[dict(roll_no=1, sheets=100)],
            output_params=[dict(line_id=line, setelan_per_lembar=3)]), key='est-once')
        output = run['outputs'][0]
        self.assertEqual(output['quantity'], 20)  # aktual dari ledger
        self.assertEqual(output['estimated_output_pcs'], 300)  # 100 lembar x 3
        self.assertIn('DEMO-20260928-1', output['estimate_basis'])
        self.assertIn('estimasi', output['estimate_basis'])
        # estimasi tidak mengubah angka aktual maupun saldo
        totals = self.client.get('/api/orders/'+order['id']).json()['totals']
        self.assertEqual(totals['sewing'], 20)

    def test_estimate_absent_without_complete_inputs(self):
        batch, order, issue, line = self.approved_order_with_cutting_setup()
        run = self.cut(order, self.cut_body(issue, line,
            rolls=[dict(roll_no=1, weight_kg='5')],
            output_params=[dict(line_id=line, setelan_per_lembar=3)]), key='est-partial')
        output = run['outputs'][0]
        self.assertIsNone(output['estimated_output_pcs'])
        self.assertIsNone(output['estimate_basis'])

    # -- target / realisasi / sisa --------------------------------------------------

    def test_plan_tracks_target_realized_remaining(self):
        batch, order, issue, line = self.approved_order_with_cutting_setup()
        target = next(l['quantity'] for l in order['lines'] if l['id'] == line)
        self.cut(order, self.cut_body(issue, line), key='track-once')
        plan = self.plan(order)
        row = next(l for l in plan['lines'] if l['line_id'] == line)
        self.assertEqual((row['target_quantity'], row['realized_quantity'], row['remaining_target']),
                         (target, 20, target-20))
        self.assertEqual(plan['realized_quantity'], 20)

    # -- integritas: idempotency, over-output, reversal ------------------------------

    def test_cutting_idempotent_and_conflicting_retry_rejected(self):
        batch, order, issue, line = self.approved_order_with_cutting_setup()
        body = self.cut_body(issue, line)
        first = self.cut(order, body, key='idem-once')
        self.assertEqual(self.cut(order, body, key='idem-once'), first)
        self.cut(order, dict(body, used='3'), key='idem-once', status=409)

    def test_over_output_rejected(self):
        batch, order, issue, line = self.approved_order_with_cutting_setup()
        self.cut(order, self.cut_body(issue, line,
            outputs=[dict(line_id=line, quantity=31)]), status=409)

    def test_reversal_restores_plan_realized_and_links_history(self):
        batch, order, issue, line = self.approved_order_with_cutting_setup()
        run = self.cut(order, self.cut_body(issue, line), key='rev-once')
        reversed_run = self.post('/api/cutting-runs/'+run['id']+'/reverse',
                                 dict(reason='Salah catat hasil'), key='rev-run')
        self.assertEqual(reversed_run['reversal']['reason'], 'Salah catat hasil')
        detail = self.client.get('/api/cutting-runs/'+run['id']).json()
        self.assertIsNotNone(detail['reversal'])
        plan = self.plan(order)
        self.assertEqual(plan['realized_quantity'], 0)
        self.assertEqual(plan['remaining_target'], plan['target_quantity'])

    # -- PO opsional ------------------------------------------------------------------

    def test_po_reference_optional_but_validated(self):
        batch, order, issue, line = self.approved_order_with_cutting_setup()
        self.cut(order, self.cut_body(issue, line, po_reference='PO-TIDAK-ADA'), status=404)
        # tanpa PO tetap bisa dicatat
        run = self.cut(order, self.cut_body(issue, line), key='no-po')
        self.assertIsNone(run['detail']['po_reference'])

    # -- ekspor CSV --------------------------------------------------------------------

    def test_export_csv_lists_params_units_references_and_correction(self):
        batch, order, issue, line = self.approved_order_with_cutting_setup()
        run = self.cut(order, self.cut_body(issue, line,
            rolls=[dict(roll_no=1, weight_kg='12.250', sheets=100)],
            output_params=[dict(line_id=line, setelan_per_lembar=3)]), key='csv-once')
        response = self.client.get('/api/orders/'+order['id']+'/cutting-runs/export.csv')
        self.assertEqual(response.status_code, 200, response.text)
        text = response.text
        self.assertTrue(text.startswith('﻿'))
        for header in ['Kode rencana', 'Tanggal cutting', 'Status koreksi', 'Setelan per lembar',
                       'Estimasi pcs', 'Dasar estimasi', 'Sisa target pcs', 'Referensi kebijakan']:
            self.assertIn(header, text)
        self.assertIn(order['reference'], text)
        self.assertIn('DEMO-20260928-1', text)
        self.post('/api/cutting-runs/'+run['id']+'/reverse', dict(reason='Koreksi demo'), key='csv-rev')
        corrected = self.client.get('/api/orders/'+order['id']+'/cutting-runs/export.csv').text
        self.assertIn('Dikoreksi', corrected)

        for reference in ('PLAN-ASCII', 'Rencana-布-é', 'plan";filename="bad', 'plan\r\nX-Injected: yes',
                          'plan/with\\slashes'):
            with self.subTest(reference=reference):
                special_order = self.order(reference=reference)
                exported = self.client.get('/api/orders/'+special_order['id']+'/cutting-runs/export.csv')
                self.assertEqual(exported.status_code, 200, exported.text)
                disposition = exported.headers['Content-Disposition']
                prefix = 'attachment; filename="beeloft-cutting.csv"; filename*=UTF-8\'\''
                self.assertTrue(disposition.startswith(prefix), disposition)
                self.assertTrue(disposition.isascii())
                encoded = disposition[len(prefix):]
                self.assertFalse(any(char in encoded for char in '\r\n";/\\'))
                self.assertEqual(unquote(encoded), f'beeloft-cutting-{reference}.csv')

    # -- migrasi -------------------------------------------------------------------------

    def test_upgrade_from_56_backfills_approved_plans(self):
        from beeloft.store import Store
        order = self.order()
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('DROP TABLE cutting_run_output_params')
            db.execute('DROP TABLE cutting_run_rolls')
            db.execute('DROP TABLE cutting_run_details')
            db.execute('DROP TABLE production_plans')
            db.execute('PRAGMA user_version=56')
            db.commit()
        connect = Store.connect

        def fail_backfill(store):
            db = connect(store)
            db.set_authorizer(lambda action, table, *_:
                              sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_INSERT
                              and table == 'production_plans' else sqlite3.SQLITE_OK)
            return db

        with patch.object(Store, 'connect', fail_backfill):
            with self.assertRaises(sqlite3.DatabaseError):
                Store(self.path)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 57)
            self.assertIsNone(db.execute(
                "SELECT 1 FROM sqlite_master WHERE name='production_plans'").fetchone())
        Store(self.path)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],58)
        plan = self.plan(order)
        self.assertEqual(plan['status'], 'approved')  # grandfathered: histori lama tidak rusak
        self.assertEqual(plan['revision'], 0)
