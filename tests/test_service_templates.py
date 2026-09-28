"""P01 (#48): tes template jasa, tarif berversi, resolver, snapshot, izin, migrasi.

Mengikuti pola tests/test_bom.py dan tests/test_m01_master_catalog.py:
- subclass ProductionTest untuk setUp bersama;
- helper post() untuk idempotency key dan assertion status;
- tes konversi pcs/lusin eksak via contracts.wage_for_realization;
- tes boundary tanggal efektif, missing, overlap, nonaktif;
- tes snapshot transaksi lama tetap setelah perubahan tarif;
- tes retry, revision guard, izin server, dan upgrade schema.
"""

import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import date
from pathlib import Path
from threading import Barrier

from starlette.testclient import TestClient

from beeloft.api import create_app
from beeloft.contracts import wage_for_realization, DEMO_POLICY
from beeloft.store import DomainError

import test_production


class ServiceTemplateTest(test_production.ProductionTest):

    def setUp(self):
        super().setUp()
        # kelompok jasa
        self.group = self.post('/api/service-groups', {
            'code': 'DEMO-GRUP', 'name': 'Kelompok Demo', 'reason': 'seed'})
        # dua jenis pekerjaan
        self.wt_jahit = self.post('/api/work-types', {
            'code': 'DEMO-JAHIT', 'name': 'Jahit',
            'service_group_id': self.group['id'], 'reason': 'seed'})
        self.wt_label = self.post('/api/work-types', {
            'code': 'DEMO-LABEL', 'name': 'Pasang Label', 'reason': 'seed'})
        # template jasa
        self.template = self.post('/api/service-templates', {
            'code': 'TPL-DEMO', 'name': 'Template Demo', 'note': 'catatan',
            'components': [
                {'work_type_id': self.wt_jahit['id']},
                {'work_type_id': self.wt_label['id']},
            ], 'reason': 'seed'})
        # tarif R1 dan R2 untuk DEMO-JAHIT
        self.rate_r1 = self.post(f'/api/work-types/{self.wt_jahit["id"]}/rates', {
            'expected_revision': 0, 'rate_basis': 'lusin', 'amount': '120.00',
            'effective_from': '2026-09-01', 'effective_to': '2026-09-16',
            'active': True, 'reason': 'R1'})
        self.rate_r2 = self.post(f'/api/work-types/{self.wt_jahit["id"]}/rates', {
            'expected_revision': 1, 'rate_basis': 'lusin', 'amount': '144.00',
            'effective_from': '2026-09-16', 'effective_to': None,
            'active': True, 'reason': 'R2'})
        # tarif untuk DEMO-LABEL (pcs basis)
        self.rate_label = self.post(f'/api/work-types/{self.wt_label["id"]}/rates', {
            'expected_revision': 0, 'rate_basis': 'pcs', 'amount': '10.00',
            'effective_from': '2026-09-01', 'effective_to': None,
            'active': True, 'reason': 'label rate'})

    # -- Master CRUD --

    def test_work_type_list_and_filter(self):
        all_wt = self.client.get('/api/work-types').json()
        self.assertEqual(len(all_wt), 2)
        active = self.client.get('/api/work-types?status=active').json()
        self.assertEqual(len(active), 2)
        inactive = self.client.get('/api/work-types?status=inactive').json()
        self.assertEqual(len(inactive), 0)

    def test_work_type_change(self):
        result = self.post(f'/api/work-types/{self.wt_jahit["id"]}/changes', {
            'expected_revision': 1, 'name': 'Jahit Utama',
            'service_group_id': self.group['id'], 'active': True, 'reason': 'rename'}, status=200)
        self.assertEqual(result['name'], 'Jahit Utama')
        self.assertEqual(result['revision'], 2)

    def test_work_type_duplicate_code(self):
        resp = self.post('/api/work-types', {
            'code': 'DEMO-JAHIT', 'name': 'Duplikat', 'reason': 'x'}, status=409)

    def test_service_group_list(self):
        groups = self.client.get('/api/service-groups').json()
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]['code'], 'DEMO-GRUP')

    def test_service_template_list(self):
        templates = self.client.get('/api/service-templates').json()
        self.assertEqual(len(templates), 1)
        self.assertEqual(len(templates[0]['components']), 2)

    def test_service_template_change(self):
        result = self.post(f'/api/service-templates/{self.template["id"]}/changes', {
            'expected_revision': 1, 'name': 'Template Ubah', 'note': '',
            'active': True,
            'components': [{'work_type_id': self.wt_jahit['id']}],
            'reason': 'reduce components'}, status=200)
        self.assertEqual(result['revision'], 2)
        self.assertEqual(len(result['components']), 1)

    def test_service_template_duplicate_component(self):
        resp = self.post('/api/service-templates', {
            'code': 'TPL-DUP', 'name': 'Dup', 'note': '',
            'components': [
                {'work_type_id': self.wt_jahit['id']},
                {'work_type_id': self.wt_jahit['id']},
            ], 'reason': 'x'}, status=422)

    def test_service_template_history(self):
        self.post(f'/api/service-templates/{self.template["id"]}/changes', {
            'expected_revision': 1, 'name': 'V2', 'note': 'updated', 'active': True,
            'components': [{'work_type_id': self.wt_jahit['id']}], 'reason': 'v2'}, status=200)
        history = self.client.get(
            f'/api/service-templates/{self.template["id"]}/history').json()
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]['revision'], 2)
        self.assertEqual(history[1]['revision'], 1)

    # -- Tarif dan konversi --

    def test_rate_pcs_lusin_conversion(self):
        """Basis lusin 120.00 -> per pcs = 1000 minor (exact Fraction)."""
        self.assertEqual(self.rate_r1['rate_basis'], 'lusin')
        self.assertEqual(self.rate_r1['amount_minor'], 12000)
        self.assertEqual(self.rate_r1['rate_per_lusin_minor'], 12000)
        self.assertEqual(self.rate_r1['rate_per_pcs_exact'], '1000')
        self.assertEqual(self.rate_r1['rate_per_pcs_money'], '10.00')

    def test_rate_pcs_basis_conversion(self):
        """Basis pcs 10.00 -> per lusin = 12000 minor."""
        self.assertEqual(self.rate_label['rate_basis'], 'pcs')
        self.assertEqual(self.rate_label['amount_minor'], 1000)
        self.assertEqual(self.rate_label['rate_per_lusin_minor'], 12000)
        self.assertEqual(self.rate_label['rate_per_lusin_money'], '120.00')
        self.assertEqual(self.rate_label['rate_per_pcs_exact'], '1000')

    def test_rate_revision_guard(self):
        """Stale expected_revision -> 409."""
        self.post(f'/api/work-types/{self.wt_jahit["id"]}/rates', {
            'expected_revision': 0, 'rate_basis': 'lusin', 'amount': '200.00',
            'effective_from': '2027-01-01', 'effective_to': None,
            'active': True, 'reason': 'stale'}, status=409)

    def test_rate_overlap_rejected(self):
        """New active interval overlapping existing active -> 409."""
        self.post(f'/api/work-types/{self.wt_jahit["id"]}/rates', {
            'expected_revision': 2, 'rate_basis': 'lusin', 'amount': '200.00',
            'effective_from': '2026-09-10', 'effective_to': '2026-09-20',
            'active': True, 'reason': 'overlap'}, status=409)

    def test_rate_boundary_date(self):
        """Sep 15 -> R1, Sep 16 -> R2 (half-open [from, to))."""
        snap15 = self.client.get(
            f'/api/work-types/{self.wt_jahit["id"]}/rate-preview?effective_date=2026-09-15').json()
        self.assertEqual(snap15['rate_revision'], 'DEMO-JAHIT#1')
        self.assertEqual(snap15['rate_per_lusin_minor'], 12000)
        snap16 = self.client.get(
            f'/api/work-types/{self.wt_jahit["id"]}/rate-preview?effective_date=2026-09-16').json()
        self.assertEqual(snap16['rate_revision'], 'DEMO-JAHIT#2')
        self.assertEqual(snap16['rate_per_lusin_minor'], 14400)

    def test_rate_missing_date(self):
        """No rate covering Aug 2026 -> 422."""
        resp = self.client.get(
            f'/api/work-types/{self.wt_jahit["id"]}/rate-preview?effective_date=2026-08-01')
        self.assertEqual(resp.status_code, 422)

    def test_rate_deactivation_and_replacement(self):
        """Deactivate R2, then replace with R4. Old R1 untouched."""
        self.post(f'/api/work-types/{self.wt_jahit["id"]}/rates/deactivate', {
            'expected_revision': 2, 'reason': 'stop'}, status=200)
        resp = self.client.get(
            f'/api/work-types/{self.wt_jahit["id"]}/rate-preview?effective_date=2026-09-20')
        self.assertEqual(resp.status_code, 422)
        self.assertIn('nonaktif', resp.json()['detail'])
        # new rate replaces deactivated interval
        r4 = self.post(f'/api/work-types/{self.wt_jahit["id"]}/rates', {
            'expected_revision': 3, 'rate_basis': 'lusin', 'amount': '180.00',
            'effective_from': '2026-09-16', 'effective_to': None,
            'active': True, 'reason': 'R4'})
        self.assertEqual(r4['revision'], 4)
        snap = self.client.get(
            f'/api/work-types/{self.wt_jahit["id"]}/rate-preview?effective_date=2026-09-20').json()
        self.assertEqual(snap['rate_revision'], 'DEMO-JAHIT#4')
        # R1 still valid
        snap15 = self.client.get(
            f'/api/work-types/{self.wt_jahit["id"]}/rate-preview?effective_date=2026-09-15').json()
        self.assertEqual(snap15['rate_revision'], 'DEMO-JAHIT#1')

    def test_rate_history_preserved(self):
        history = self.client.get(
            f'/api/work-types/{self.wt_jahit["id"]}/rate-history').json()
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]['revision'], 2)
        self.assertEqual(history[1]['revision'], 1)

    # -- Wage preview with exact arithmetic --

    def test_wage_preview_13pcs(self):
        """13 pcs @ 144.00/lusin: 13/12 * 14400 = 15600 minor = Rp156.00."""
        resp = self.client.get(
            f'/api/work-types/{self.wt_jahit["id"]}/rate-preview'
            f'?effective_date=2026-09-16&pcs=13').json()
        self.assertEqual(resp['pcs'], 13)
        self.assertEqual(resp['lusin_exact'], '13/12')
        self.assertEqual(resp['wage_minor'], 15600)
        self.assertEqual(resp['wage_money'], '156.00')
        self.assertEqual(resp['rate_revision'], 'DEMO-JAHIT#2')

    def test_wage_preview_1pcs(self):
        resp = self.client.get(
            f'/api/work-types/{self.wt_jahit["id"]}/rate-preview'
            f'?effective_date=2026-09-16&pcs=1').json()
        self.assertEqual(resp['wage_minor'], 1200)
        self.assertEqual(resp['wage_money'], '12.00')

    # -- Template application to SKU --

    def test_apply_template_to_sku(self):
        app = self.post(f'/api/service-templates/{self.template["id"]}/apply', {
            'product_id': self.product['id'], 'reason': 'apply test'})
        self.assertEqual(app['template_code'], 'TPL-DEMO')
        self.assertEqual(app['template_revision'], 1)
        self.assertEqual(len(app['components']), 2)
        self.assertIsNotNone(app['actor_name'])
        # current state
        current = self.client.get(
            f'/api/products/{self.product["id"]}/service-template').json()
        self.assertEqual(current['template_code'], 'TPL-DEMO')
        # product service rates
        resolved = self.client.get(
            f'/api/products/{self.product["id"]}/service-rates'
            f'?effective_date=2026-09-16').json()
        self.assertEqual(resolved['sku'], self.product['sku'])
        self.assertEqual(len(resolved['services']), 2)

    def test_apply_template_history(self):
        self.post(f'/api/service-templates/{self.template["id"]}/apply', {
            'product_id': self.product['id'], 'reason': 'first'})
        self.post(f'/api/service-templates/{self.template["id"]}/apply', {
            'product_id': self.product['id'], 'reason': 'second'})
        history = self.client.get(
            f'/api/products/{self.product["id"]}/service-template-history').json()
        self.assertEqual(len(history), 2)

    def test_snapshot_unchanged_after_rate_change(self):
        """Snapshot taken before rate change must remain identical."""
        self.post(f'/api/service-templates/{self.template["id"]}/apply', {
            'product_id': self.product['id'], 'reason': 'apply'})
        snapshot_before = self.client.get(
            f'/api/work-types/{self.wt_jahit["id"]}/rate-preview'
            f'?effective_date=2026-09-16').json()
        # change rate
        self.post(f'/api/work-types/{self.wt_jahit["id"]}/rates/deactivate', {
            'expected_revision': 2, 'reason': 'stop'}, status=200)
        self.post(f'/api/work-types/{self.wt_jahit["id"]}/rates', {
            'expected_revision': 3, 'rate_basis': 'lusin', 'amount': '999.00',
            'effective_from': '2026-09-16', 'effective_to': None,
            'active': True, 'reason': 'new price'})
        # old application still points to old template revision
        current = self.client.get(
            f'/api/products/{self.product["id"]}/service-template').json()
        self.assertEqual(current['template_revision'], 1)
        # saved snapshot values untouched
        self.assertEqual(snapshot_before['rate_revision'], 'DEMO-JAHIT#2')
        self.assertEqual(snapshot_before['rate_per_lusin_minor'], 14400)

    # -- Inactive template blocks new application --

    def test_deactivated_work_type_does_not_break_template_history(self):
        """Inactive work type can stay in old template revisions; no new apply."""
        self.post(f'/api/service-templates/{self.template["id"]}/apply', {
            'product_id': self.product['id'], 'reason': 'historical apply'})
        self.post(f'/api/work-types/{self.wt_jahit["id"]}/changes', {
            'expected_revision': 1, 'name': 'Jahit',
            'service_group_id': self.group['id'], 'active': False, 'reason': 'retire'}, status=200)
        changed = self.post(f'/api/service-templates/{self.template["id"]}/changes', {
            'expected_revision': 1, 'name': 'Template Demo', 'note': 'retired',
            'active': False,
            'components': [
                {'work_type_id': self.wt_jahit['id']},
                {'work_type_id': self.wt_label['id']},
            ], 'reason': 'retire template'}, status=200)
        self.assertEqual(changed['revision'], 2)
        applications = self.client.get(
            f'/api/products/{self.product["id"]}/service-template-history').json()
        self.assertEqual(applications[0]['template_revision'], 1)
        self.assertEqual(len(applications[0]['components']), 2)
        self.post(f'/api/service-templates/{self.template["id"]}/apply', {
            'product_id': self.product['id'], 'reason': 'try inactive'}, status=422)

    def test_inactive_template_blocked(self):
        self.post(f'/api/service-templates/{self.template["id"]}/changes', {
            'expected_revision': 1, 'name': 'Template Demo', 'note': 'catatan',
            'active': False,
            'components': [
                {'work_type_id': self.wt_jahit['id']},
                {'work_type_id': self.wt_label['id']},
            ], 'reason': 'deactivate'}, status=200)
        self.post(f'/api/service-templates/{self.template["id"]}/apply', {
            'product_id': self.product['id'], 'reason': 'try inactive'},
            status=422)

    # -- Permission boundaries --

    def test_operator_cannot_create_work_type(self):
        self.client.headers['X-API-Key'] = self.operator['api_key']
        self.post('/api/work-types', {
            'code': 'OP-TEST', 'name': 'Op', 'reason': 'x'}, status=403)

    def test_operator_cannot_save_rate(self):
        self.client.headers['X-API-Key'] = self.operator['api_key']
        self.post(f'/api/work-types/{self.wt_jahit["id"]}/rates', {
            'expected_revision': 2, 'rate_basis': 'lusin', 'amount': '200.00',
            'effective_from': '2027-01-01', 'effective_to': None,
            'active': True, 'reason': 'op'}, status=403)

    def test_viewer_can_read_work_types(self):
        self.client.headers['X-API-Key'] = self.viewer['api_key']
        resp = self.client.get('/api/work-types')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 2)

    def test_viewer_can_read_rate_preview(self):
        self.client.headers['X-API-Key'] = self.viewer['api_key']
        resp = self.client.get(
            f'/api/work-types/{self.wt_jahit["id"]}/rate-preview?effective_date=2026-09-16')
        self.assertEqual(resp.status_code, 200)

    # -- Replay / idempotency --

    def test_idempotency_replay(self):
        """Same key+payload returns same result."""
        result1 = self.post('/api/work-types', {
            'code': 'IDMP', 'name': 'Idem', 'reason': 'x'}, key='idem-1')
        result2 = self.post('/api/work-types', {
            'code': 'IDMP', 'name': 'Idem', 'reason': 'x'}, key='idem-1')
        self.assertEqual(result1['id'], result2['id'])

    # -- Concurrent saves --

    def test_concurrent_rate_save(self):
        """Two concurrent rate saves: one 201, one 409."""
        extra = self.post('/api/work-types', {
            'code': 'CONCURRENT', 'name': 'Concurrent', 'reason': 'race'})
        barrier = Barrier(2, timeout=5)
        results = []
        def save(key):
            barrier.wait()
            app = create_app(self.path)
            with TestClient(app) as c:
                c.headers['X-API-Key'] = self.admin['api_key']
                resp = c.post(f'/api/work-types/{extra["id"]}/rates', json={
                    'expected_revision': 0, 'rate_basis': 'pcs', 'amount': '20.00',
                    'effective_from': '2027-01-01', 'effective_to': None,
                    'active': True, 'reason': 'concurrent'},
                    headers={'Idempotency-Key': key})
                results.append(resp.status_code)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(save, f'conc-{i}') for i in range(2)]
            wait(futures, timeout=10)
        self.assertIn(201, results)
        self.assertIn(409, results)

    # -- Schema upgrade --

    def test_upgrade_59_to_60(self):
        """Drop service tables, set version=59, reopen Store -> version=60."""
        with self.app.state.store.transaction(write=True) as db:
            for table in ('service_template_applications', 'service_rate_events',
                          'service_rates', 'service_template_events',
                          'service_templates', 'service_work_type_events',
                          'service_work_types', 'service_group_events',
                          'service_groups'):
                db.execute(f'DROP TABLE IF EXISTS {table}')
            # drop triggers
            for trigger in db.execute(
                    "SELECT name FROM sqlite_schema WHERE type='trigger' AND name LIKE 'service_%'"):
                db.execute(f'DROP TRIGGER IF EXISTS {trigger[0]}')
            db.execute('PRAGMA user_version=59')
        from beeloft.store import Store
        store2 = Store(self.path)
        with store2.transaction() as db:
            version = db.execute('PRAGMA user_version').fetchone()[0]
            tables = {r[0] for r in db.execute(
                "SELECT name FROM sqlite_schema WHERE type='table' AND name LIKE 'service_%'")}
        self.assertEqual(version, 60)
        self.assertIn('service_work_types', tables)
        self.assertIn('service_rate_events', tables)
        self.assertIn('service_template_applications', tables)

    # -- Exact wage arithmetic cross-check with contracts.py --

    def test_wage_exact_arithmetic_contract(self):
        """Cross-check API preview with direct contracts.wage_for_realization."""
        for pcs in (1, 11, 12, 13):
            with self.subTest(pcs=pcs):
                api = self.client.get(
                    f'/api/work-types/{self.wt_jahit["id"]}/rate-preview'
                    f'?effective_date=2026-09-16&pcs={pcs}').json()
                direct = wage_for_realization(
                    pcs=pcs, rate_per_lusin_minor=14400,
                    rate_revision='DEMO-JAHIT#2')
                self.assertEqual(api['wage_minor'], direct['wage_minor'])
                self.assertEqual(api['lusin_exact'], direct['lusin_exact'])

    # -- Rate list and history --

    def test_service_rates_list(self):
        rates = self.client.get('/api/service-rates').json()
        self.assertEqual(len(rates), 2)  # jahit + label

    def test_effective_to_before_from_rejected(self):
        """effective_to < effective_from -> 422."""
        self.post(f'/api/work-types/{self.wt_label["id"]}/rates', {
            'expected_revision': 1, 'rate_basis': 'pcs', 'amount': '20.00',
            'effective_from': '2027-06-01', 'effective_to': '2027-01-01',
            'active': True, 'reason': 'bad'}, status=422)


if __name__ == '__main__':
    unittest.main()
