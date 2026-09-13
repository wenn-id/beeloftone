import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from threading import Barrier
from unittest import TestCase

from fastapi.testclient import TestClient
from beeloft.api import create_app
from beeloft.store import Store
import test_bundles as bundle_tests


class SewingJobTest(TestCase):
    setUp = bundle_tests.BundleTest.setUp
    post = bundle_tests.BundleTest.post
    order = bundle_tests.BundleTest.order
    material = bundle_tests.BundleTest.material
    receipt = bundle_tests.BundleTest.receipt
    issue = bundle_tests.BundleTest.issue
    setup_stock = bundle_tests.BundleTest.setup_stock
    prepare = bundle_tests.BundleTest.prepare
    cut = bundle_tests.BundleTest.cut
    create_bundle = bundle_tests.BundleTest.create_bundle

    def setup_bundle(self):
        _, order, _, body = self.prepare()
        run = self.cut(order, body)
        bundle = self.create_bundle(run, quantity=20)
        return order, run, bundle

    def create_job(self, bundle, reference='SEW-001', quantity=8, cost='160000.00', **options):
        body = dict(reference=reference, assignment_type='makloon', assignee='Atelier Satu',
                    quantity_out=quantity, cost=cost, sent_date='2026-09-11',
                    reason='Kirim bundle ke penjahit')
        return self.post('/api/bundles/'+bundle['id']+'/sewing-jobs', body, **options)

    def complete(self, job, completed=6, defects=1, missing=1,
                 returned_date='2026-09-15', **options):
        body = dict(completed_quantity=completed, defect_quantity=defects,
                    missing_quantity=missing, returned_date=returned_date,
                    reason='Hasil jahit diterima dan dihitung')
        return self.post('/api/sewing-jobs/'+job['id']+'/complete', body, **options)

    def test_partial_jobs_capture_cost_outcome_turnaround_and_wip(self):
        order, _, bundle = self.setup_bundle()
        first = self.create_job(bundle, key='sewing-one')
        self.assertEqual(first, self.create_job(bundle, key='sewing-one'))
        second = self.create_job(bundle, reference='SEW-002', quantity=12, key='sewing-two')
        self.assertEqual((first['quantity_out'], second['quantity_out']), (8, 12))
        self.assertEqual(first['cost'], '160000.00')
        self.assertEqual(first['sku'], self.product['sku'])
        self.assertEqual(first['bundle_reference'], bundle['reference'])
        self.assertEqual(first['order_id'], order['id'])
        before = self.client.get('/api/orders/'+order['id']).json()['totals']
        result = self.complete(first, key='sewing-complete')
        self.assertEqual(result, self.complete(first, key='sewing-complete'))
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['result']['turnaround_days'], 4)
        self.assertEqual(result['result']['completed_quantity'], 6)
        self.assertEqual(result['result']['defect_quantity'], 1)
        self.assertEqual(result['result']['missing_quantity'], 1)
        totals = self.client.get('/api/orders/'+order['id']).json()['totals']
        self.assertEqual((totals['sewing'], totals['finishing'], totals['reject']), (12, 6, 2))
        self.assertEqual(sum(totals.values()), sum(before.values()))
        listed = self.client.get('/api/orders/'+order['id']+'/sewing-jobs').json()
        self.assertEqual([row['id'] for row in listed], [second['id'], first['id']])
        self.assertEqual(self.client.get('/api/sewing-jobs/'+first['id']).json(), result)

    def test_job_correction_restores_wip_and_releases_bundle(self):
        order, _, bundle = self.setup_bundle()
        job = self.create_job(bundle, quantity=20)
        self.post('/api/bundles/'+bundle['id']+'/reverse',
                  dict(reason='Bundle salah'), status=409)
        self.complete(job, completed=17, defects=2, missing=1)
        corrected = self.post('/api/sewing-jobs/'+job['id']+'/reverse',
                              dict(reason='Hasil jahit salah hitung'), key='reverse-sewing')
        self.assertEqual(corrected, self.post('/api/sewing-jobs/'+job['id']+'/reverse',
                                             dict(reason='Hasil jahit salah hitung'), key='reverse-sewing'))
        self.assertEqual(corrected['status'], 'corrected')
        totals = self.client.get('/api/orders/'+order['id']).json()['totals']
        self.assertEqual((totals['sewing'], totals['finishing'], totals['reject']), (20, 0, 0))
        replacement = self.create_job(bundle, reference='SEW-REPLACEMENT', quantity=20)
        self.assertEqual(replacement['status'], 'open')

    def test_validation_roles_dates_totals_and_linked_movement_guard(self):
        _, _, bundle = self.setup_bundle()
        self.create_job(bundle, api_key=self.viewer['api_key'], status=403)
        self.create_job(bundle, quantity=True, status=422)
        self.create_job(bundle, quantity=21, status=409)
        self.create_job(bundle, cost=-1, status=422)
        self.create_job(bundle, cost=10, status=422)
        self.create_job(dict(id='missing'), status=404)
        job = self.create_job(bundle)
        self.create_job(bundle, reference='sew-001', quantity=1, status=409)
        self.complete(job, api_key=self.viewer['api_key'], status=403)
        self.complete(job, completed=7, defects=0, missing=0, status=409)
        self.complete(job, returned_date='2026-09-10', status=422)
        result = self.complete(job, api_key=self.operator['api_key'])
        self.complete(job, status=409)
        for role in (self.operator, self.viewer):
            self.post('/api/sewing-jobs/'+job['id']+'/reverse', dict(reason='Salah'),
                      api_key=role['api_key'], status=403)
        self.post('/api/movements/'+result['result']['completion_movement_id']+'/reverse',
                  dict(reason='Terpisah'), status=409)
        self.assertEqual(self.client.get('/api/sewing-jobs/'+job['id'],
                         headers={'X-API-Key':self.viewer['api_key']}).status_code, 200)
        self.assertEqual(self.client.get('/api/orders/missing/sewing-jobs').status_code, 404)

    def test_race_cannot_overallocate_or_complete_twice(self):
        _, _, bundle = self.setup_bundle()
        barrier = Barrier(2)

        def dispatch(index):
            with TestClient(create_app(self.path)) as client:
                barrier.wait(timeout=10)
                return client.post('/api/bundles/'+bundle['id']+'/sewing-jobs', json=dict(
                    reference='SEW-RACE-'+str(index), assignment_type='internal', assignee='Line A',
                    quantity_out=15, cost='0.00', sent_date='2026-09-11', reason='Uji bersamaan'),
                    headers={'X-API-Key':self.operator['api_key'],
                             'Idempotency-Key':'sewing-race-'+str(index)}).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(dispatch, range(2))), [201, 409])
        jobs = self.client.get('/api/orders/'+bundle['order_id']+'/sewing-jobs').json()
        self.assertEqual(sum(row['quantity_out'] for row in jobs), 15)
        job = jobs[0]
        complete_barrier = Barrier(2)

        def finish(index):
            with TestClient(create_app(self.path)) as client:
                complete_barrier.wait(timeout=10)
                return client.post('/api/sewing-jobs/'+job['id']+'/complete', json=dict(
                    completed_quantity=15, defect_quantity=0, missing_quantity=0,
                    returned_date='2026-09-12', reason='Selesai bersamaan'), headers={
                    'X-API-Key':self.operator['api_key'],
                    'Idempotency-Key':'finish-race-'+str(index)}).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(finish, range(2))), [201, 409])

    def test_create_and_completion_rollback(self):
        order, _, bundle = self.setup_bundle()
        with self.app.state.store.transaction(write=True) as db:
            db.execute("CREATE TRIGGER fail_sewing_create BEFORE INSERT ON requests WHEN NEW.key='fail-sewing' "
                       "BEGIN SELECT RAISE(ABORT,'test'); END")
        self.create_job(bundle, key='fail-sewing', status=409)
        self.assertEqual(self.client.get('/api/orders/'+order['id']+'/sewing-jobs').json(), [])
        self.assertEqual(self.client.get('/api/bundles/'+bundle['id']).json()['sewing_allocated_quantity'], 0)
        job = self.create_job(bundle)
        before = self.client.get('/api/orders/'+order['id']).json()['totals']
        with self.app.state.store.transaction(write=True) as db:
            db.execute("CREATE TRIGGER fail_sewing_complete BEFORE INSERT ON requests WHEN NEW.key='fail-finish' "
                       "BEGIN SELECT RAISE(ABORT,'test'); END")
        self.complete(job, key='fail-finish', status=409)
        self.assertEqual(self.client.get('/api/orders/'+order['id']).json()['totals'], before)
        self.assertIsNone(self.client.get('/api/sewing-jobs/'+job['id']).json()['result'])

    def test_downstream_wip_blocks_job_correction_atomically(self):
        order, _, bundle = self.setup_bundle()
        job = self.create_job(bundle)
        self.complete(job, completed=8, defects=0, missing=0)
        line = order['lines'][0]['id']
        self.post('/api/movements', dict(line_id=line, from_stage='finishing', to_stage='qc',
                                         quantity=8, reason='Lanjut QC'))
        self.post('/api/sewing-jobs/'+job['id']+'/reverse',
                  dict(reason='Salah hasil'), status=409)
        current = self.client.get('/api/sewing-jobs/'+job['id']).json()
        self.assertEqual(current['status'], 'completed')
        totals = self.client.get('/api/orders/'+order['id']).json()['totals']
        self.assertEqual((totals['sewing'], totals['qc']), (12, 8))

    def test_cursor_backup_migration_and_direct_sql_guards(self):
        order, _, bundle = self.setup_bundle()
        first = self.create_job(bundle, quantity=3)
        second = self.create_job(bundle, reference='SEW-002', quantity=4)
        route = '/api/orders/'+order['id']+'/sewing-jobs'
        page = self.client.get(route+'?limit=1').json()
        self.assertEqual(page[0]['id'], second['id'])
        self.assertEqual(self.client.get(route+'?before='+str(page[0]['sequence'])).json()[0]['id'], first['id'])
        backup = self.path.with_name('sewing-backup.sqlite3')
        self.app.state.store.backup(backup)
        self.assertEqual(Store(backup).sewing_job(first['id']),
                         self.client.get('/api/sewing-jobs/'+first['id']).json())
        with self.app.state.store.transaction(write=True) as db:
            for statement in ['UPDATE sewing_jobs SET reason=reason', 'DELETE FROM sewing_jobs']:
                with self.assertRaises(sqlite3.IntegrityError):
                    db.execute(statement)
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute('''INSERT INTO sewing_jobs(id,reference,bundle_id,assignment_type,assignee,
                    quantity_out,cost_minor,sent_date,reason,actor_id,created_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?)''',('direct','DIRECT-SEW',bundle['id'],'internal','Line A',
                    99,0,'2026-09-11','Bypass API',self.admin['id'],'2026-09-11T00:00:00+00:00'))
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute('INSERT INTO bundle_reversals(bundle_id,reason,actor_id,created_at) VALUES(?,?,?,?)',
                           (bundle['id'],'Bypass API',self.admin['id'],'2026-09-11T00:00:00+00:00'))

    def test_upgrade_from_14_preserves_bundle_and_starts_empty(self):
        order, _, bundle = self.setup_bundle()
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('DROP TRIGGER finished_goods_reversal_valid')
            db.execute('DROP TRIGGER marketplace_reservation_release_valid')
            db.execute('DROP TRIGGER marketplace_pick_reversal_valid')
            db.execute('DROP TRIGGER marketplace_pack_reversal_valid')
            db.execute('DROP VIEW finished_goods_reserved_stock')
            db.execute('DROP VIEW finished_goods_stock_ledger')
            db.execute('DROP TABLE finished_goods_adjustment_reversals')
            db.execute('DROP TABLE finished_goods_adjustments')
            db.execute('DROP TABLE finished_goods_stock_count_reversals')
            db.execute('DROP TABLE finished_goods_stock_counts')
            db.execute('DROP TABLE marketplace_return_reversals')
            db.execute('DROP TABLE marketplace_returns')
            db.execute('DROP TABLE marketplace_shipment_reversals')
            db.execute('DROP TABLE marketplace_shipments')
            db.execute('DROP TABLE marketplace_pack_reversals')
            db.execute('DROP TABLE marketplace_packs')
            db.execute('DROP TABLE marketplace_pick_reversals')
            db.execute('DROP TABLE marketplace_picks')
            db.execute('DROP TABLE marketplace_reservation_releases')
            db.execute('DROP TABLE marketplace_reservations')
            db.execute('DROP TABLE warehouse_movement_reversals')
            db.execute('DROP TABLE warehouse_movements')
            db.execute('DROP TRIGGER finished_goods_blocks_final_qc_reversal')
            db.execute('DROP TABLE finished_goods_receipt_reversals')
            db.execute('DROP TABLE finished_goods_receipts')
            db.execute('DROP TRIGGER final_qc_blocks_finishing_reversal')
            db.execute('DROP TABLE final_qc_record_reversals')
            db.execute('DROP TABLE final_qc_records')
            db.execute('DROP TRIGGER finishing_blocks_sewing_reversal')
            db.execute('DROP TABLE finishing_record_reversals')
            db.execute('DROP TABLE finishing_records')
            for table in ['sewing_job_reversals','sewing_job_results','sewing_jobs']:
                db.execute('DROP TABLE '+table)
            db.execute('PRAGMA user_version=14')
            db.commit()
        Store(self.path)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],40)
        self.assertEqual(self.client.get('/api/orders/'+order['id']+'/sewing-jobs').json(), [])
        current = self.client.get('/api/bundles/'+bundle['id']).json()
        self.assertEqual((current['sewing_allocated_quantity'], current['sewing_unassigned_quantity']), (0, 20))
