import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import tempfile
import sqlite3

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

        # Baseline count constraints
        self.assertEqual(len(baseline['orders']), 120)
        self.assertEqual(len(baseline['items']), 30)
        self.assertEqual(len(baseline['listings']), 30)
        self.assertEqual(len(baseline['returns']), 4)

        # Mathematical consistency on orders
        channels = set()
        for order in baseline['orders']:
            channels.add(order['marketplace'].casefold())
            lines_total = sum(Decimal(line['gross_revenue']) for line in order['lines'])
            self.assertGreater(lines_total, Decimal('0.00'))
            # UTC check
            ordered_at = datetime.fromisoformat(order['ordered_at'].replace('Z', '+00:00'))
            self.assertIsNotNone(ordered_at.tzinfo)

        self.assertIn('shopee', channels)
        self.assertIn('tokopedia', channels)
        self.assertIn('tiktok shop', channels)

        # Stock sellable >= reserved
        for item in baseline['items']:
            self.assertGreaterEqual(item['sellable_quantity'], item['reserved_quantity'])

        # Returns link to valid order references
        order_refs = {order['external_order_reference'].casefold() for order in baseline['orders']}
        for ret in baseline['returns']:
            self.assertIn(ret['external_order_reference'].casefold(), order_refs)
            if ret['status'] == 'refunded':
                self.assertGreater(Decimal(ret['refund_amount']), Decimal('0.00'))

    def test_scenario_2_is_full_cumulative_snapshot(self):
        scen2 = JubelioDemoDataset.generate_scenario_2()
        # Full cumulative dataset: all 120 previous orders + 25 new orders = 145 orders
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

        # Activate
        res = self.manager.activate(self.admin, "act-key-1")
        self.assertTrue(res['is_active'])
        self.assertEqual(res['current_scenario'], 1)

        # Verify products & mappings were seeded
        products = self.store.products(limit=100)
        self.assertGreaterEqual(len(products), 30)

    def test_non_demo_database_rejection(self):
        non_demo_path = Path(self.temp_dir.name) / "production_beeloft.sqlite3"
        non_demo_store = Store(non_demo_path)
        admin = non_demo_store.provision_user("Admin", "admin")
        manager = JubelioDemoManager(non_demo_store)
        manager.mark_as_demo_database(False)
        self.assertFalse(manager.is_demo_database())
        with self.assertRaises(DomainError) as ctx:
            manager.activate(admin, "key-fail")
        self.assertEqual(ctx.exception.status, 400)
        self.assertIn("bukan database demo", ctx.exception.message)
        del manager
        del non_demo_store

    def test_sync_baseline_creates_quarantine_for_unmapped_skus(self):
        self.manager.activate(self.admin, "act-key-2")
        status = self.manager.sync(self.admin, "sync-key-1")
        # Baseline has 2 unmapped SKUs, so status should be 'attention'
        self.assertEqual(status['last_status'], 'attention')
        self.assertGreater(status['last_summary']['total_quarantined'], 0)
        self.assertEqual(status['last_summary']['scopes']['listings']['status'], 'attention')
        self.assertEqual(status['last_summary']['scopes']['returns']['status'], 'succeeded')

        # Check Jubelio read models reflect data!
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

        # Now map the 2 unmapped products
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

        # Resync baseline with new batch
        status = self.manager.sync(self.admin, "sync-key-3b")
        # Now all 30 SKUs are mapped -> 0 quarantined -> 'succeeded'
        self.assertEqual(status['last_status'], 'succeeded')
        self.assertEqual(status['last_summary']['total_quarantined'], 0)

        # Reconciliation now shows all 30 items
        reconcil = self.store.jubelio_stock_reconciliation()
        self.assertEqual(len(reconcil['items']), 30)
        self.assertEqual(len(reconcil['quarantine']), 0)

    def test_database_concurrency_lock_prevents_simultaneous_sync(self):
        self.manager.activate(self.admin, "act-key-4")
        # Simulate lock held
        self.manager._acquire_lock()
        with self.assertRaises(DomainError) as ctx:
            self.manager.sync(self.admin, "sync-concurrent")
        self.assertEqual(ctx.exception.status, 409)
        self.assertIn("sedang berjalan", ctx.exception.message)
        # Release lock
        self.manager._release_lock(status="idle")

    def test_next_scenario_advances_cumulatively(self):
        self.manager.activate(self.admin, "act-key-5")
        self.manager.sync(self.admin, "sync-key-5a")
        order_summary_1 = self.store.jubelio_order_summary()
        baseline_orders_count = order_summary_1['summary']['accepted_orders'] + order_summary_1['summary']['quarantined_orders']
        self.assertEqual(baseline_orders_count, 120)

        # Advance to scenario 2
        status2 = self.manager.next_scenario(self.admin, "sync-key-5b")
        self.assertEqual(status2['current_scenario'], 2)

        order_summary_2 = self.store.jubelio_order_summary()
        total_orders_2 = order_summary_2['summary']['accepted_orders'] + order_summary_2['summary']['quarantined_orders']
        # Must be 145 orders! (All 120 baseline + 25 new orders)
        self.assertEqual(total_orders_2, 145)


if __name__ == '__main__':
    unittest.main()
