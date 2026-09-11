import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from threading import Barrier
from unittest import TestCase

from fastapi.testclient import TestClient
from beeloft.api import create_app
from beeloft.store import Store
import test_cutting as cutting_tests


class BundleTest(TestCase):
    setUp = cutting_tests.CuttingTest.setUp
    post = cutting_tests.CuttingTest.post
    order = cutting_tests.CuttingTest.order
    material = cutting_tests.CuttingTest.material
    receipt = cutting_tests.CuttingTest.receipt
    issue = cutting_tests.CuttingTest.issue
    setup_stock = cutting_tests.CuttingTest.setup_stock
    prepare = cutting_tests.CuttingTest.prepare
    cut = cutting_tests.CuttingTest.cut

    def setup_run(self):
        _, order, _, body = self.prepare()
        run = self.cut(order, body, key='cut-for-bundle')
        return order, run

    def create_bundle(self, run, reference='BDL-001', quantity=8, output_movement_id=None, **options):
        body = dict(reference=reference,
                    output_movement_id=output_movement_id or run['outputs'][0]['id'],
                    quantity=quantity,
                    reason='Pisahkan hasil cutting untuk sewing')
        return self.post('/api/cutting-runs/'+run['id']+'/bundles', body, **options)

    def test_create_partial_bundles_links_source_without_changing_wip(self):
        order, run = self.setup_run()
        before = self.client.get('/api/orders/'+order['id']).json()['totals']
        first = self.create_bundle(run, key='bundle-one')
        self.assertEqual(first, self.create_bundle(run, key='bundle-one'))
        second = self.create_bundle(run, reference='BDL-002', quantity=12, key='bundle-two')
        self.assertEqual((first['quantity'], second['quantity']), (8, 12))
        self.assertEqual(first['order_id'], order['id'])
        self.assertEqual(first['cutting_run_id'], run['id'])
        self.assertEqual(first['output_movement_id'], run['outputs'][0]['id'])
        self.assertEqual(first['status'], 'active')
        self.assertEqual(self.client.get('/api/orders/'+order['id']).json()['totals'], before)
        detail = self.client.get('/api/cutting-runs/'+run['id']).json()
        self.assertEqual(detail['outputs'][0]['bundled_quantity'], 20)
        self.assertEqual(detail['outputs'][0]['unbundled_quantity'], 0)
        self.assertEqual([row['reference'] for row in detail['bundles']], ['BDL-002', 'BDL-001'])
        listed = self.client.get('/api/orders/'+order['id']+'/bundles').json()
        self.assertEqual([row['id'] for row in listed], [second['id'], first['id']])
        self.assertEqual(self.client.get('/api/bundles/'+first['id']).json(), first)

    def test_correction_releases_allocation_without_moving_wip_and_unblocks_cutting(self):
        order, run = self.setup_run()
        bundle = self.create_bundle(run)
        before = self.client.get('/api/orders/'+order['id']).json()['totals']
        self.post('/api/cutting-runs/'+run['id']+'/reverse',
                  dict(reason='Cutting salah'), status=409)
        corrected = self.post('/api/bundles/'+bundle['id']+'/reverse',
                              dict(reason='Label bundle salah'), key='reverse-bundle')
        self.assertEqual(corrected, self.post('/api/bundles/'+bundle['id']+'/reverse',
                                             dict(reason='Label bundle salah'), key='reverse-bundle'))
        self.assertEqual(corrected['status'], 'corrected')
        self.assertEqual(self.client.get('/api/orders/'+order['id']).json()['totals'], before)
        output = self.client.get('/api/cutting-runs/'+run['id']).json()['outputs'][0]
        self.assertEqual((output['bundled_quantity'], output['unbundled_quantity']), (0, 20))
        self.post('/api/bundles/'+bundle['id']+'/reverse', dict(reason='Dua kali'), status=409)
        self.post('/api/cutting-runs/'+run['id']+'/reverse', dict(reason='Cutting salah'))

    def test_validation_permissions_and_source_guards(self):
        _, order, _, body = self.prepare()
        run = self.cut(order, body)
        other = self.cut(order, body | dict(reference='CUT-002', used='1', waste='0',
                                             outputs=[body['outputs'][0] | dict(quantity=5)]))
        self.create_bundle(run, api_key=self.viewer['api_key'], status=403)
        self.create_bundle(run, quantity=True, status=422)
        self.create_bundle(run, quantity=21, status=409)
        self.create_bundle(dict(id='missing', outputs=run['outputs']), status=404)
        self.create_bundle(run, output_movement_id=other['outputs'][0]['id'], status=422)
        bundle = self.create_bundle(run)
        self.create_bundle(run, reference='bdl-001', quantity=1, status=409)
        for role in (self.operator, self.viewer):
            self.post('/api/bundles/'+bundle['id']+'/reverse', dict(reason='Salah label'),
                      api_key=role['api_key'], status=403)
        self.assertEqual(self.client.get('/api/orders/'+order['id']+'/bundles',
                         headers={'X-API-Key': self.viewer['api_key']}).status_code, 200)
        self.assertEqual(self.client.get('/api/bundles/'+bundle['id'],
                         headers={'X-API-Key': 'bad'}).status_code, 401)

    def test_race_cannot_allocate_one_output_twice(self):
        order, run = self.setup_run()
        before = self.client.get('/api/orders/'+order['id']).json()['totals']
        barrier = Barrier(2)

        def save(index):
            with TestClient(create_app(self.path)) as client:
                barrier.wait(timeout=10)
                return client.post('/api/cutting-runs/'+run['id']+'/bundles',
                    json=dict(reference='BDL-RACE-'+str(index),
                              output_movement_id=run['outputs'][0]['id'], quantity=15,
                              reason='Uji alokasi bersamaan'),
                    headers={'X-API-Key': self.admin['api_key'],
                             'Idempotency-Key': 'bundle-race-'+str(index)}).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(save, range(2))), [201, 409])
        detail = self.client.get('/api/cutting-runs/'+run['id']).json()
        self.assertEqual(detail['outputs'][0]['bundled_quantity'], 15)
        self.assertEqual(self.client.get('/api/orders/'+order['id']).json()['totals'], before)

    def test_rollback_cursor_persistence_and_backup(self):
        order, run = self.setup_run()
        with self.app.state.store.transaction(write=True) as db:
            db.execute("CREATE TRIGGER fail_bundle BEFORE INSERT ON requests WHEN NEW.key='fail-bundle' "
                       "BEGIN SELECT RAISE(ABORT,'test'); END")
        self.create_bundle(run, key='fail-bundle', status=409)
        self.assertEqual(self.client.get('/api/orders/'+order['id']+'/bundles').json(), [])
        self.assertEqual(self.client.get('/api/cutting-runs/'+run['id']).json()
                         ['outputs'][0]['bundled_quantity'], 0)
        first = self.create_bundle(run, quantity=3, key='bundle-first')
        second = self.create_bundle(run, reference='BDL-002', quantity=4, key='bundle-second')
        route = '/api/orders/'+order['id']+'/bundles'
        page = self.client.get(route+'?limit=1').json()
        self.assertEqual(page[0]['id'], second['id'])
        older = self.client.get(route+'?before='+str(page[0]['sequence'])).json()
        self.assertEqual(older[0]['id'], first['id'])
        backup = self.path.with_name('bundle-backup.sqlite3')
        self.app.state.store.backup(backup)
        self.assertEqual(Store(backup).bundle(first['id']),
                         self.client.get('/api/bundles/'+first['id']).json())

    def test_upgrade_from_13_preserves_cutting_and_adds_empty_bundle_ledger(self):
        order, run = self.setup_run()
        before = self.client.get('/api/cutting-runs/'+run['id']).json()
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('DROP TRIGGER final_qc_blocks_finishing_reversal')
            db.execute('DROP TABLE final_qc_record_reversals')
            db.execute('DROP TABLE final_qc_records')
            db.execute('DROP TRIGGER finishing_blocks_sewing_reversal')
            db.execute('DROP TABLE finishing_record_reversals')
            db.execute('DROP TABLE finishing_records')
            db.execute('DROP TRIGGER sewing_job_blocks_bundle_reversal')
            db.execute('DROP TABLE sewing_job_reversals')
            db.execute('DROP TABLE sewing_job_results')
            db.execute('DROP TABLE sewing_jobs')
            db.execute('DROP TRIGGER bundle_blocks_cutting_output_reversal')
            db.execute('DROP TABLE bundle_reversals')
            db.execute('DROP TABLE bundles')
            db.execute('PRAGMA user_version=13')
            db.commit()
        Store(self.path)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 17)
        after = self.client.get('/api/cutting-runs/'+run['id']).json()
        self.assertEqual({k: after[k] for k in before if k != 'outputs'},
                         {k: before[k] for k in before if k != 'outputs'})
        self.assertEqual(after['bundles'], [])
        self.assertEqual(after['outputs'][0]['unbundled_quantity'], 20)

    def test_direct_sql_guards_and_immutable_history(self):
        _, run = self.setup_run()
        bundle = self.create_bundle(run)
        output = run['outputs'][0]
        with self.app.state.store.transaction(write=True) as db:
            for statement in ['UPDATE bundles SET reason=reason', 'DELETE FROM bundles']:
                with self.assertRaises(sqlite3.IntegrityError):
                    db.execute(statement)
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute('''INSERT INTO bundles(id,reference,cutting_run_id,output_movement_id,quantity,
                    reason,actor_id,created_at) VALUES(?,?,?,?,?,?,?,?)''',
                    ('direct-over', 'BDL-DIRECT', run['id'], output['id'], 99, 'Bypass API',
                     self.admin['id'], '2026-09-11T00:00:00+00:00'))
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute('''INSERT INTO bundles(id,reference,cutting_run_id,output_movement_id,quantity,
                    reason,actor_id,created_at) VALUES(?,?,?,?,?,?,?,?)''',
                    ('direct-space', ' BDL-SPACED ', run['id'], output['id'], 1, 'Bypass API',
                     self.admin['id'], '2026-09-11T00:00:00+00:00'))
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute('''INSERT INTO movements(id,line_id,from_stage,to_stage,quantity,reason,
                    actor_id,created_at,reversal_of) VALUES(?,?,?,?,?,?,?,?,?)''',
                    ('direct-reversal', output['line_id'], 'sewing', 'cutting', output['quantity'],
                     'Bypass API', self.admin['id'], '2026-09-11T00:00:00+00:00', output['id']))
        self.post('/api/bundles/'+bundle['id']+'/reverse', dict(reason='Salah label'))
        with self.app.state.store.transaction(write=True) as db:
            for statement in ['UPDATE bundle_reversals SET reason=reason',
                              'DELETE FROM bundle_reversals']:
                with self.assertRaises(sqlite3.IntegrityError):
                    db.execute(statement)

    def test_cutting_list_keeps_only_bounded_allocation_summary(self):
        order, run = self.setup_run()
        self.create_bundle(run, quantity=3)
        self.create_bundle(run, reference='BDL-002', quantity=4)
        listed = self.client.get('/api/orders/'+order['id']+'/cutting-runs').json()[0]
        self.assertNotIn('bundles', listed)
        self.assertEqual(listed['outputs'][0]['bundled_quantity'], 7)
        self.assertEqual(listed['outputs'][0]['unbundled_quantity'], 13)
