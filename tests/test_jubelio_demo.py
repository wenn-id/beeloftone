import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from decimal import Decimal
from pathlib import Path
import tempfile
from threading import Barrier

from fastapi.testclient import TestClient
from beeloft.api import create_app
from beeloft.store import Store, DomainError
from beeloft.jubelio_demo import JubelioDemoDataset
from beeloft.jubelio_demo_manager import JubelioDemoManager


class JubelioDemoDatasetTest(unittest.TestCase):
    def test_products_count_and_mappings(self):
        products = JubelioDemoDataset.products()
        self.assertEqual(len(products), 30)
        self.assertEqual(sum(p['is_mapped'] for p in products), 28)
        self.assertEqual({p['sku'] for p in products if not p['is_mapped']},
                         {'DEMO-BIMO-PANTS-L', 'DEMO-CACA-DRESS-S'})

    def test_baseline_dataset_is_deterministic_and_consistent(self):
        baseline = JubelioDemoDataset.generate_baseline()
        self.assertEqual(baseline, JubelioDemoDataset.generate_baseline())
        self.assertEqual((len(baseline['orders']), len(baseline['items']),
                          len(baseline['listings']), len(baseline['returns'])), (120, 30, 30, 4))
        channels = {order['marketplace'].casefold() for order in baseline['orders']}
        self.assertEqual(channels, {'shopee', 'tokopedia', 'tiktok shop'})
        timestamps = [datetime.fromisoformat(order['ordered_at']) for order in baseline['orders']]
        self.assertTrue(all(stamp.utcoffset().total_seconds() == 0 for stamp in timestamps))
        self.assertEqual((min(stamp.date() for stamp in timestamps), max(stamp.date() for stamp in timestamps)),
                         (datetime(2026, 8, 30).date(), datetime(2026, 9, 28).date()))
        shifted_anchor = '2027-01-15T00:00:00+00:00'
        shifted = JubelioDemoDataset.generate_baseline(shifted_anchor)
        self.assertEqual(max(datetime.fromisoformat(order['ordered_at']) for order in shifted['orders']).date(),
                         datetime(2027, 1, 15).date())
        self.assertEqual(JubelioDemoDataset.generate_baseline(shifted_anchor), shifted)
        for item in baseline['items']:
            self.assertGreaterEqual(item['sellable_quantity'], item['reserved_quantity'])
        order_refs = {order['external_order_reference'] for order in baseline['orders']}
        for record in baseline['returns']:
            self.assertIn(record['external_order_reference'], order_refs)
            self.assertTrue(record['updated_at'].endswith('+00:00'))
            self.assertGreaterEqual(Decimal(record['refund_amount']), Decimal('0'))

    def test_scenario_2_contains_full_updated_snapshots(self):
        baseline = JubelioDemoDataset.generate_baseline()
        scenario = JubelioDemoDataset.generate_scenario_2()
        self.assertEqual((len(scenario['orders']), len(scenario['items']),
                          len(scenario['listings']), len(scenario['returns'])), (145, 30, 30, 6))
        before = {o['external_order_id']: o for o in baseline['orders']}
        after = {o['external_order_id']: o for o in scenario['orders']}
        self.assertTrue(set(before) < set(after))
        self.assertTrue(any(before[key]['status'] != after[key]['status'] for key in before))
        self.assertTrue(any(item['sellable_quantity'] < old['sellable_quantity']
                            for item, old in zip(scenario['items'], baseline['items'])))

    def test_external_ids_are_unique_and_stable_for_all_products(self):
        products = JubelioDemoDataset.products()
        self.assertEqual(len({p['external_id'] for p in products}), 30)
        self.assertEqual(len({p['external_sku'].casefold() for p in products}), 30)
        self.assertEqual({p['sku']:p['external_id'] for p in products},
                         {p['sku']:p['external_id'] for p in JubelioDemoDataset.products()})


class JubelioDemoManagerTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / 'demo.sqlite3'
        self.store = Store(self.db_path)
        self.admin = self.store.provision_user('Admin Demo', 'admin')
        self.viewer = self.store.provision_user('Viewer Demo', 'viewer')
        self.manager = JubelioDemoManager(self.store)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_demo_database_requires_explicit_database_marker(self):
        self.assertFalse(self.manager.is_demo_database())
        with self.assertRaises(DomainError) as ctx:
            self.manager.activate(self.admin, 'act-key-1')
        self.assertEqual(ctx.exception.status, 400)
        self.manager.mark_as_demo_database(True)
        self.assertTrue(self.manager.is_demo_database())

    def test_marker_and_activation_are_separate_and_anchor_persists(self):
        self.manager.mark_as_demo_database(True)
        before = self.manager.get_status()
        self.assertTrue(before['is_demo_database'])
        self.assertFalse(before['is_active'])
        self.assertEqual(before['anchor_at'], '')
        status = self.manager.activate(self.admin, 'activate-one')
        self.assertTrue(status['is_active'])
        self.assertEqual(status['anchor_at'], '2026-09-28T00:00:00+00:00')
        self.assertEqual(len(self.store.products(limit=100)), 30)
        self.assertIsNone(self.store.jubelio_order_summary()['snapshot'])

    def test_activation_replay_does_not_reset_progress(self):
        self.manager.mark_as_demo_database(True)
        self.manager.activate(self.admin, 'activate-first')
        self.manager.sync(self.admin, 'baseline-first')
        before = self.manager.get_status()
        self.manager.activate(self.admin, 'activate-again')
        after = self.manager.get_status()
        self.assertEqual(after['current_scenario'], before['current_scenario'])
        self.assertEqual(after['last_synced_at'], before['last_synced_at'])
        self.assertEqual(after['last_status'], before['last_status'])

    def test_sync_rejected_before_explicit_activation(self):
        self.manager.mark_as_demo_database(True)
        with self.assertRaises(DomainError) as ctx:
            self.manager.sync(self.admin, 'sync-not-active')
        self.assertEqual(ctx.exception.status, 409)

    def test_non_demo_database_rejected_even_if_filename_contains_demo(self):
        regular = Store(Path(self.temp_dir.name) / 'demo-looking.sqlite3')
        manager = JubelioDemoManager(regular)
        admin = regular.provision_user('Admin', 'admin')
        self.assertFalse(manager.is_demo_database())
        with self.assertRaises(DomainError) as ctx:
            manager.activate(admin, 'not-demo')
        self.assertEqual(ctx.exception.status, 400)

    def test_baseline_uses_all_existing_read_models_and_quarantines_unmapped_skus(self):
        self.manager.mark_as_demo_database(True)
        self.manager.activate(self.admin, 'activate-baseline')
        status = self.manager.sync(self.admin, 'sync-baseline')
        self.assertEqual(status['last_status'], 'failed')
        self.assertEqual(status['last_summary']['total_quarantined'], 12)
        self.assertEqual(set(status['last_summary']['scopes']),
                         {'orders', 'finished_goods', 'returns', 'listings'})
        self.assertEqual(self.store.jubelio_order_summary()['summary']['accepted_orders'], 112)
        self.assertEqual(self.store.jubelio_order_summary()['summary']['quarantined_orders'], 8)
        self.assertEqual(len(self.store.jubelio_marketplace_performance()['marketplaces']), 3)
        self.assertEqual(len(self.store.jubelio_stock_reconciliation()['items']), 28)
        self.assertEqual(len(self.store.jubelio_stock_reconciliation()['quarantine']), 2)
        self.assertEqual(self.store.jubelio_listing_summary()['summary']['accepted_listings'], 28)
        self.assertEqual(self.store.jubelio_return_summary()['summary']['accepted_returns'], 4)
        self.assertEqual(status['last_summary']['scopes']['orders']['status'], 'attention')
        self.assertEqual(status['last_summary']['scopes']['returns']['status'], 'succeeded')

    def test_same_request_retry_returns_same_operation_and_batches(self):
        self.manager.mark_as_demo_database(True)
        self.manager.activate(self.admin, 'activate-retry')
        first = self.manager.sync(self.admin, 'sync-stable')
        tables = ('jubelio_order_snapshot_batches', 'jubelio_stock_snapshot_batches',
                  'jubelio_return_snapshot_batches', 'jubelio_listing_snapshot_batches')
        with self.store.transaction() as db:
            before = [db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] for table in tables]
        second = self.manager.sync(self.admin, 'sync-stable')
        with self.store.transaction() as db:
            after = [db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] for table in tables]
        self.assertEqual(before, after)
        self.assertEqual(first['last_summary'], second['last_summary'])
        self.assertFalse(second['is_locked'])

    def test_next_scenario_serializes_and_same_key_is_idempotent(self):
        self.manager.mark_as_demo_database(True)
        self.manager.activate(self.admin, 'activate-concurrency')
        self.manager.sync(self.admin, 'baseline-concurrency')
        barrier = Barrier(2)
        def advance():
            barrier.wait()
            try:
                return self.manager.next_scenario(self.admin, 'next-shared-key')
            except DomainError as error:
                return error.status
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: advance(), range(2)))
        self.assertEqual(sum(isinstance(x, dict) for x in results), 1)
        self.assertEqual(sum(x == 409 for x in results), 1)
        self.assertEqual(self.manager.get_status()['current_scenario'], 2)
        self.assertEqual(len(self.store.jubelio_order_snapshots(limit=10)), 2)
        first = next(x for x in results if isinstance(x, dict))
        self.assertFalse(first['is_locked'])
        replay = self.manager.next_scenario(self.admin, 'next-shared-key')
        self.assertEqual(replay, first)
        self.assertEqual(len(self.store.jubelio_order_snapshots(limit=10)), 2)
        self.assertEqual(self.store.jubelio_order_summary()['summary']['accepted_orders'], 136)
        with self.assertRaises(DomainError) as error:
            self.manager.next_scenario(self.admin, 'next-too-far')
        self.assertEqual(error.exception.status, 409)

    def test_next_key_conflicts_with_sync_key_instead_of_claiming_false_advance(self):
        self.manager.mark_as_demo_database(True)
        self.manager.activate(self.admin, 'activate-cross-key')
        self.manager.sync(self.admin, 'shared-request-key')
        before = self.store.jubelio_order_summary()['summary']['accepted_orders']
        with self.assertRaises(DomainError) as error:
            self.manager.next_scenario(self.admin, 'shared-request-key')
        self.assertEqual(error.exception.status, 409)
        self.assertEqual(self.manager.get_status()['current_scenario'], 1)
        self.assertEqual(self.store.jubelio_order_summary()['summary']['accepted_orders'], before)

    def test_partial_retry_uses_operation_scope_receipts_not_global_latest_batch(self):
        self.manager.mark_as_demo_database(True)
        self.manager.activate(self.admin, 'activate-partial')
        original_return = self.store.import_jubelio_return_snapshot
        fail = [True]
        def failing_return(payload, actor, key):
            if fail[0]:
                fail[0] = False
                raise DomainError(503, 'Injected return failure')
            return original_return(payload, actor, key)
        self.store.import_jubelio_return_snapshot = failing_return
        first = self.manager.sync(self.admin, 'partial-operation')
        self.assertEqual(first['last_summary']['scopes']['returns']['status'], 'failed')
        before = {scope: len(self.store.integration_sync_runs(limit=100, system='jubelio', scope=scope))
                  for scope in ('orders','finished_goods','returns','listings')}
        self.store.import_jubelio_return_snapshot = original_return
        retried = self.manager.sync(self.admin, 'partial-operation')
        after = {scope: len(self.store.integration_sync_runs(limit=100, system='jubelio', scope=scope))
                 for scope in before}
        self.assertEqual(after['orders'], before['orders'])
        self.assertEqual(after['finished_goods'], before['finished_goods'])
        self.assertEqual(after['listings'], before['listings'])
        self.assertEqual(after['returns'], before['returns'] + 1)
        self.assertEqual(retried['last_summary']['scopes']['returns']['status'], 'succeeded')
        self.assertEqual(retried['last_summary']['scopes']['orders']['accepted'], 112)

    def test_mapping_repair_keeps_historical_quarantine_and_builds_full_new_batch(self):
        self.manager.mark_as_demo_database(True)
        self.manager.activate(self.admin, 'activate-mapping')
        self.manager.sync(self.admin, 'baseline-mapping')
        self.manager.next_scenario(self.admin, 'next-mapping')
        old_batch_id = self.store.jubelio_order_snapshots(limit=1)[0]['id']
        old_batch = self.store.jubelio_order_snapshot(old_batch_id)
        old_ids = {item['id'] for item in old_batch['quarantine']}
        for product in (p for p in JubelioDemoDataset.products() if not p['is_mapped']):
            stored = next(p for p in self.store.products(limit=100) if p['sku'] == product['sku'])
            mapping = self.store.product_external_mapping(stored['id'], 'jubelio')
            self.store.save_product_external_mapping(stored['id'], 'jubelio', {
                'expected_revision': mapping['revision'], 'action': 'mapped',
                'external_id': product['external_id'], 'external_sku': product['external_sku'],
                'reason': 'Perbaikan mapping demo'}, self.admin, f"fix-{stored['id']}")
        result = self.manager.sync(self.admin, 'resync-mapping')
        self.assertEqual(result['last_status'], 'succeeded')
        order_summary = self.store.jubelio_order_summary()
        self.assertEqual(order_summary['summary']['accepted_orders'], 145)
        self.assertEqual(order_summary['summary']['quarantined_orders'], 0)
        latest = self.store.jubelio_order_snapshot(order_summary['snapshot']['id'])
        self.assertEqual(len(latest['orders']), 145)
        self.assertEqual(len(latest['quarantine']), 0)
        self.assertEqual({item['id'] for item in self.store.jubelio_order_snapshot(old_batch_id)['quarantine']}, old_ids)

    def test_database_marker_and_anchor_survive_restart(self):
        self.manager.mark_as_demo_database(True)
        self.manager.activate(self.admin, 'activate-restart')
        anchor = self.manager.get_status()['anchor_at']
        restarted = Store(self.db_path)
        manager = JubelioDemoManager(restarted)
        self.assertTrue(manager.is_demo_database())
        self.assertTrue(manager.get_status()['is_active'])
        self.assertEqual(manager.get_status()['anchor_at'], anchor)

    def test_api_roles_marker_and_lifecycle(self):
        regular = Path(self.temp_dir.name) / 'regular.db'
        app = create_app(regular)
        client = TestClient(app)
        admin = app.state.store.provision_user('API Admin', 'admin')
        viewer = app.state.store.provision_user('API Viewer', 'viewer')
        read = client.get('/api/integrations/jubelio/demo/status', headers={'X-API-Key': viewer['api_key']})
        self.assertEqual(read.status_code, 200)
        self.assertFalse(read.json()['is_demo_database'])
        denied = client.post('/api/integrations/jubelio/demo/activate', headers={
            'X-API-Key': viewer['api_key'], 'Idempotency-Key': 'viewer-act'})
        self.assertEqual(denied.status_code, 403)
        regular_activation = client.post('/api/integrations/jubelio/demo/activate', headers={
            'X-API-Key': admin['api_key'], 'Idempotency-Key': 'regular-act'})
        self.assertEqual(regular_activation.status_code, 400)
        client.close()

        self.manager.mark_as_demo_database(True)
        app = create_app(self.db_path)
        client = TestClient(app)
        activation = client.post('/api/integrations/jubelio/demo/activate', headers={
            'X-API-Key': self.admin['api_key'], 'Idempotency-Key': 'activate-test'})
        self.assertEqual(activation.status_code, 200)
        self.assertTrue(activation.json()['is_active'])
        baseline = client.post('/api/integrations/jubelio/demo/sync', headers={
            'X-API-Key': self.admin['api_key'], 'Idempotency-Key': 'sync-test'})
        self.assertEqual(baseline.status_code, 200)
        self.assertEqual(baseline.json()['last_status'], 'failed')
        failed_run_count = len(self.store.integration_sync_runs(limit=100, system='jubelio'))
        retry = client.post('/api/integrations/jubelio/demo/sync', headers={
            'X-API-Key': self.admin['api_key'], 'Idempotency-Key': 'sync-test'})
        self.assertEqual(retry.json(), baseline.json())
        self.assertEqual(len(self.store.integration_sync_runs(limit=100, system='jubelio')), failed_run_count)
        client.close()


if __name__ == '__main__':
    unittest.main()
