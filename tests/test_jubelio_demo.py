import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import tempfile
import sqlite3

from fastapi.testclient import TestClient
from beeloft.api import create_app
from beeloft.store import Store, DomainError
from beeloft.jubelio_demo import JubelioDemoDataset, JubelioDemoManager


class JubelioDemoDatasetTest(unittest.TestCase):
    def test_products_count_and_mappings(self):
        products = JubelioDemoDataset.products()
        self.assertEqual(len(products), 30)
        mapped = [p for p in products if p['is_mapped']]
        unmapped = [p for p in products if not p['is_mapped']]
        self.assertEqual(len(mapped), 28)
        self.assertEqual(len(unmapped), 2)
        unmapped_skus = {p['sku'] for p in unmapped}
        self.assertEqual(unmapped_skus, {'DEMO-BIMO-PANTS-L', 'DEMO-CACA-DRESS-S'})

    def test_baseline_dataset_structure_and_math(self):
        baseline = JubelioDemoDataset.generate_baseline()
        self.assertIn('orders', baseline)
        self.assertIn('items', baseline)
        self.assertIn('listings', baseline)
        self.assertIn('returns', baseline)

        self.assertEqual(len(baseline['orders']), 120)
        self.assertEqual(len(baseline['items']), 30)
        self.assertEqual(len(baseline['listings']), 30)
        self.assertEqual(len(baseline['returns']), 4)

        channels = set()
        for order in baseline['orders']:
            channels.add(order['marketplace'].casefold())
            lines_total = sum(Decimal(line['gross_revenue']) for line in order['lines'])
            self.assertGreater(lines_total, Decimal('0.00'))
            ordered_at = datetime.fromisoformat(order['ordered_at'].replace('Z', '+00:00'))
            self.assertIsNotNone(ordered_at.tzinfo)

        self.assertIn('shopee', channels)
        self.assertIn('tokopedia', channels)
        self.assertIn('tiktok shop', channels)

        for item in baseline['items']:
            self.assertGreaterEqual(item['sellable_quantity'], item['reserved_quantity'])

        order_refs = {order['external_order_reference'].casefold() for order in baseline['orders']}
        for ret in baseline['returns']:
            self.assertIn(ret['external_order_reference'].casefold(), order_refs)
            if ret['status'] == 'refunded':
                self.assertGreater(Decimal(ret['refund_amount']), Decimal('0.00'))

    def test_scenario_2_is_full_cumulative_snapshot(self):
        scen2 = JubelioDemoDataset.generate_scenario_2()
        self.assertEqual(len(scen2['orders']), 145)
        self.assertEqual(len(scen2['items']), 30)
        self.assertEqual(len(scen2['listings']), 30)
        self.assertEqual(len(scen2['returns']), 6)


class JubelioDemoManagerTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "demo.sqlite3"
        self.store = Store(self.db_path)
        self.admin = self.store.provision_user("Admin Demo", "admin")
        self.viewer = self.store.provision_user("Viewer Demo", "viewer")
        self.manager = JubelioDemoManager(self.store)

    def tearDown(self):
        del self.manager
        del self.store
        try:
            self.temp_dir.cleanup()
        except OSError:
            pass

    def test_demo_database_detection_and_activation(self):
        self.assertTrue(self.manager.is_demo_database())
        status = self.manager.get_status()
        self.assertFalse(status['is_active'])
        self.assertEqual(status['current_scenario'], 0)

        res = self.manager.activate(self.admin, "act-key-1")
        self.assertTrue(res['is_active'])
        self.assertEqual(res['current_scenario'], 1)

        products = self.store.products(limit=100)
        self.assertGreaterEqual(len(products), 30)

    def test_explicit_database_marker_and_non_demo_rejection(self):
        non_demo_path = Path(self.temp_dir.name) / "production_beeloft.sqlite3"
        non_demo_store = Store(non_demo_path)
        admin = non_demo_store.provision_user("Admin", "admin")
        manager = JubelioDemoManager(non_demo_store)
        self.assertFalse(manager.is_demo_database())
        with self.assertRaises(DomainError) as ctx:
            manager.activate(admin, "key-fail")
        self.assertEqual(ctx.exception.status, 400)
        manager.mark_as_demo_database(True)
        self.assertTrue(manager.is_demo_database())
        del manager
        del non_demo_store

    def test_sync_baseline_creates_quarantine_for_unmapped_skus(self):
        self.manager.activate(self.admin, "act-key-2")
        status = self.manager.sync(self.admin, "sync-key-1")
        self.assertEqual(status['last_status'], 'attention')
        self.assertGreater(status['last_summary']['total_quarantined'], 0)
        self.assertEqual(status['last_summary']['scopes']['listings']['status'], 'attention')
        self.assertEqual(status['last_summary']['scopes']['returns']['status'], 'succeeded')

        order_summary = self.store.jubelio_order_summary()
        self.assertGreater(order_summary['summary']['accepted_orders'], 100)
        self.assertGreater(order_summary['summary']['quarantined_orders'], 0)

        market_perf = self.store.jubelio_marketplace_performance()
        self.assertIn('marketplaces', market_perf)
        self.assertGreater(len(market_perf['marketplaces']), 0)

        reconcil = self.store.jubelio_stock_reconciliation()
        self.assertEqual(len(reconcil['items']), 28)
        self.assertEqual(len(reconcil['quarantine']), 2)

    def test_quarantine_remediation_via_mapping_and_resync(self):
        self.manager.activate(self.admin, "act-key-3")
        self.manager.sync(self.admin, "sync-key-3a")

        prods = JubelioDemoDataset.products()
        unmapped = [p for p in prods if not p['is_mapped']]
        for p in unmapped:
            prod_row = [row for row in self.store.products(limit=100) if row['sku'] == p['sku']][0]
            curr_map = self.store.product_external_mapping(prod_row['id'], 'jubelio')
            self.store.save_product_external_mapping(
                prod_row['id'],
                'jubelio',
                {
                    'expected_revision': curr_map['revision'],
                    'action': 'mapped',
                    'external_id': p['external_id'],
                    'external_sku': p['external_sku'],
                    'reason': 'Pemetaan perbaikan karantina',
                },
                self.admin,
                f"remedy-{prod_row['id']}"
            )

        status = self.manager.sync(self.admin, "sync-key-3b")
        self.assertEqual(status['last_status'], 'succeeded')
        self.assertEqual(status['last_summary']['total_quarantined'], 0)

        reconcil = self.store.jubelio_stock_reconciliation()
        self.assertEqual(len(reconcil['items']), 30)
        self.assertEqual(len(reconcil['quarantine']), 0)

    def test_database_concurrency_lock_prevents_simultaneous_sync(self):
        self.manager.activate(self.admin, "act-key-4")
        self.manager._acquire_lock()
        with self.assertRaises(DomainError) as ctx:
            self.manager.sync(self.admin, "sync-concurrent")
        self.assertEqual(ctx.exception.status, 409)
        self.assertIn("sedang berjalan", ctx.exception.message)
        self.manager._release_lock(status="idle")

    def test_retry_same_request_key_does_not_create_new_batches(self):
        self.manager.activate(self.admin, "act-key-6")
        self.manager.sync(self.admin, "sync-retry-key")
        with self.store.transaction() as db:
            before = {table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in (
                "jubelio_order_snapshot_batches", "jubelio_stock_snapshot_batches",
                "jubelio_return_snapshot_batches", "jubelio_listing_snapshot_batches")}
        result = self.manager.sync(self.admin, "sync-retry-key")
        with self.store.transaction() as db:
            after = {table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in before}
        self.assertEqual(before, after)
        self.assertEqual(result['current_scenario'], 1)

    def test_next_scenario_advances_cumulatively(self):
        self.manager.activate(self.admin, "act-key-5")
        self.manager.sync(self.admin, "sync-key-5a")
        order_summary_1 = self.store.jubelio_order_summary()
        baseline_orders_count = order_summary_1['summary']['accepted_orders'] + order_summary_1['summary']['quarantined_orders']
        self.assertEqual(baseline_orders_count, 120)

        status2 = self.manager.next_scenario(self.admin, "sync-key-5b")
        self.assertEqual(status2['current_scenario'], 2)

        order_summary_2 = self.store.jubelio_order_summary()
        total_orders_2 = order_summary_2['summary']['accepted_orders'] + order_summary_2['summary']['quarantined_orders']
        self.assertEqual(total_orders_2, 145)

    def test_concurrent_next_scenario_cannot_advance_twice(self):
        self.manager.activate(self.admin, "act-key-7")
        barrier = __import__('threading').Barrier(2)
        def advance(index):
            barrier.wait()
            try:
                return self.manager.next_scenario(self.admin, f"next-concurrent-{index}")
            except DomainError as error:
                return error.status
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(advance, range(2)))
        statuses = [item for item in outcomes if isinstance(item, int)]
        self.assertLessEqual(len(statuses), 1)
        self.assertLessEqual(self.manager.get_status()['current_scenario'], 2)

    def test_api_requires_admin_and_rejects_non_demo(self):
        non_demo_path = Path(self.temp_dir.name) / "regular.sqlite3"
        app = create_app(non_demo_path)
        client = TestClient(app)
        admin = app.state.store.provision_user("Admin", "admin")
        viewer = app.state.store.provision_user("Viewer", "viewer")

        viewer_resp = client.post('/api/integrations/jubelio/demo/activate', headers={
            'X-API-Key': viewer['api_key'], 'Idempotency-Key': 'viewer-activate'})
        self.assertEqual(viewer_resp.status_code, 403)

        regular_resp = client.post('/api/integrations/jubelio/demo/activate', headers={
            'X-API-Key': admin['api_key'], 'Idempotency-Key': 'regular-activate'})
        self.assertEqual(regular_resp.status_code, 400)
        client.close()

    def test_api_endpoints_full_lifecycle(self):
        demo_path = Path(self.temp_dir.name) / "demo_api.sqlite3"
        app = create_app(demo_path)
        client = TestClient(app)
        admin = app.state.store.provision_user("Admin", "admin")

        # 1. Get status
        status_resp = client.get('/api/integrations/jubelio/demo/status', headers={'X-API-Key': admin['api_key']})
        self.assertEqual(status_resp.status_code, 200)
        self.assertEqual(status_resp.json()['current_scenario'], 0)

        # 2. Activate
        act_resp = client.post('/api/integrations/jubelio/demo/activate', headers={
            'X-API-Key': admin['api_key'], 'Idempotency-Key': 'api-act-1'})
        self.assertEqual(act_resp.status_code, 200)
        self.assertEqual(act_resp.json()['current_scenario'], 1)

        # 3. Sync baseline
        sync_resp = client.post('/api/integrations/jubelio/demo/sync', headers={
            'X-API-Key': admin['api_key'], 'Idempotency-Key': 'api-sync-1'})
        self.assertEqual(sync_resp.status_code, 200)
        self.assertEqual(sync_resp.json()['last_status'], 'attention')

        # 4. Next scenario
        next_resp = client.post('/api/integrations/jubelio/demo/next-scenario', headers={
            'X-API-Key': admin['api_key'], 'Idempotency-Key': 'api-next-1'})
        self.assertEqual(next_resp.status_code, 200)
        self.assertEqual(next_resp.json()['current_scenario'], 2)

        # 5. Reset
        reset_resp = client.post('/api/integrations/jubelio/demo/reset', headers={
            'X-API-Key': admin['api_key'], 'Idempotency-Key': 'api-reset-1'})
        self.assertEqual(reset_resp.status_code, 200)
        self.assertEqual(reset_resp.json()['current_scenario'], 1)

        client.close()


if __name__ == '__main__':
    unittest.main()
