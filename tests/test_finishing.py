import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from threading import Barrier
from unittest import TestCase

from fastapi.testclient import TestClient
from beeloft.api import create_app
from beeloft.store import Store
import test_sewing_jobs as sewing_tests


class FinishingTest(TestCase):
    setUp = sewing_tests.SewingJobTest.setUp
    post = sewing_tests.SewingJobTest.post
    order = sewing_tests.SewingJobTest.order
    material = sewing_tests.SewingJobTest.material
    receipt = sewing_tests.SewingJobTest.receipt
    issue = sewing_tests.SewingJobTest.issue
    setup_stock = sewing_tests.SewingJobTest.setup_stock
    prepare = sewing_tests.SewingJobTest.prepare
    cut = sewing_tests.SewingJobTest.cut
    create_bundle = sewing_tests.SewingJobTest.create_bundle
    setup_bundle = sewing_tests.SewingJobTest.setup_bundle
    create_job = sewing_tests.SewingJobTest.create_job
    complete = sewing_tests.SewingJobTest.complete

    def setup_job(self, quantity=20):
        order, _, bundle = self.setup_bundle()
        job = self.create_job(bundle, quantity=quantity)
        job = self.complete(job, completed=quantity, defects=0, missing=0)
        return order, bundle, job

    def finish(self, job, reference='FIN-001', quantity=8, completed_date='2026-09-16', **options):
        body = dict(reference=reference, quantity=quantity, thread_trimmed=True, ironed=True,
                    labels_attached=True, hangtags_attached=True, packaged=True,
                    completed_date=completed_date, reason='Semua langkah finishing diperiksa')
        return self.post('/api/sewing-jobs/'+job['id']+'/finishing-records', body, **options)

    def test_partial_completion_preserves_lineage_and_moves_wip_to_qc(self):
        order, _, job = self.setup_job()
        first = self.finish(job, key='finishing-one')
        self.assertEqual(first, self.finish(job, key='finishing-one'))
        second = self.finish(job, reference='FIN-002', quantity=12, key='finishing-two')
        self.assertEqual((first['quantity'], second['quantity']), (8, 12))
        self.assertTrue(all(first[field] for field in ('thread_trimmed','ironed','labels_attached',
                                                       'hangtags_attached','packaged')))
        self.assertEqual(first['sewing_reference'], job['reference'])
        self.assertEqual(first['bundle_reference'], job['bundle_reference'])
        self.assertEqual(first['order_id'], order['id'])
        self.assertEqual(first['batch_id'], job['batch_id'])
        totals = self.client.get('/api/orders/'+order['id']).json()['totals']
        self.assertEqual((totals['finishing'], totals['qc']), (0, 20))
        current = self.client.get('/api/sewing-jobs/'+job['id']).json()
        self.assertEqual((current['finishing_completed_quantity'],current['finishing_remaining_quantity']),(20,0))
        listed = self.client.get('/api/orders/'+order['id']+'/finishing-records').json()
        self.assertEqual([row['id'] for row in listed], [second['id'], first['id']])
        self.assertEqual(self.client.get('/api/finishing-records/'+first['id']).json(), first)

    def test_correction_restores_wip_and_releases_source(self):
        order, _, job = self.setup_job()
        record = self.finish(job, quantity=8)
        self.post('/api/sewing-jobs/'+job['id']+'/reverse',dict(reason='Sewing salah'),status=409)
        self.post('/api/movements/'+record['movement_id']+'/reverse',dict(reason='Terpisah'),status=409)
        corrected=self.post('/api/finishing-records/'+record['id']+'/reverse',
                            dict(reason='Checklist salah'),key='reverse-finishing')
        self.assertEqual(corrected,self.post('/api/finishing-records/'+record['id']+'/reverse',
                                             dict(reason='Checklist salah'),key='reverse-finishing'))
        self.assertEqual(corrected['status'],'corrected')
        totals=self.client.get('/api/orders/'+order['id']).json()['totals']
        self.assertEqual((totals['finishing'],totals['qc']),(20,0))
        current=self.client.get('/api/sewing-jobs/'+job['id']).json()
        self.assertEqual((current['finishing_completed_quantity'],current['finishing_remaining_quantity']),(0,20))
        self.finish(job,reference='FIN-REPLACEMENT',quantity=20)

    def test_validation_permissions_date_checklist_and_allocation(self):
        _, bundle, job = self.setup_job()
        self.finish(job,api_key=self.viewer['api_key'],status=403)
        self.finish(job,quantity=True,status=422)
        self.finish(job,completed_date='2026-09-14',status=422)
        body=dict(reference='FIN-BAD',quantity=1,thread_trimmed=False,ironed=True,
                  labels_attached=True,hangtags_attached=True,packaged=True,
                  completed_date='2026-09-16',reason='Belum lengkap')
        self.post('/api/sewing-jobs/'+job['id']+'/finishing-records',body,status=422)
        record=self.finish(job,quantity=20)
        self.finish(job,reference='FIN-OVER',quantity=1,status=409)
        self.finish(job,reference='fin-001',quantity=1,status=409)
        for role in (self.operator,self.viewer):
            self.post('/api/finishing-records/'+record['id']+'/reverse',dict(reason='Salah'),
                      api_key=role['api_key'],status=403)
        self.finish(dict(id='missing'),status=404)
        self.assertEqual(self.client.get('/api/orders/missing/finishing-records').status_code,404)
        self.assertEqual(self.client.get('/api/finishing-records/missing').status_code,404)

    def test_race_cannot_overallocate_one_sewing_result(self):
        order, _, job = self.setup_job()
        barrier=Barrier(2)
        def save(index):
            with TestClient(create_app(self.path)) as client:
                barrier.wait(timeout=10)
                return client.post('/api/sewing-jobs/'+job['id']+'/finishing-records',json=dict(
                    reference='FIN-RACE-'+str(index),quantity=15,thread_trimmed=True,ironed=True,
                    labels_attached=True,hangtags_attached=True,packaged=True,
                    completed_date='2026-09-16',reason='Uji bersamaan'),headers={
                    'X-API-Key':self.operator['api_key'],
                    'Idempotency-Key':'finishing-race-'+str(index)}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(save,range(2))),[201,409])
        totals=self.client.get('/api/orders/'+order['id']).json()['totals']
        self.assertEqual((totals['finishing'],totals['qc']),(5,15))

    def test_downstream_wip_blocks_correction_atomically(self):
        order, _, job = self.setup_job()
        record=self.finish(job,quantity=8)
        self.post('/api/movements',dict(line_id=record['line_id'],from_stage='qc',to_stage='warehouse',
                                        quantity=8,reason='Diterima gudang'))
        self.post('/api/finishing-records/'+record['id']+'/reverse',dict(reason='Salah'),status=409)
        self.assertEqual(self.client.get('/api/finishing-records/'+record['id']).json()['status'],'completed')
        totals=self.client.get('/api/orders/'+order['id']).json()['totals']
        self.assertEqual((totals['finishing'],totals['warehouse']),(12,8))

    def test_rollback_backup_guards_and_migration_from_15(self):
        order, _, job = self.setup_job()
        with self.app.state.store.transaction(write=True) as db:
            db.execute("CREATE TRIGGER fail_finishing BEFORE INSERT ON requests WHEN NEW.key='fail-finishing' "
                       "BEGIN SELECT RAISE(ABORT,'test'); END")
        self.finish(job,key='fail-finishing',status=409)
        self.assertEqual(self.client.get('/api/orders/'+order['id']).json()['totals']['qc'],0)
        record=self.finish(job,quantity=3)
        backup=self.path.with_name('finishing-backup.sqlite3')
        self.app.state.store.backup(backup)
        self.assertEqual(Store(backup).finishing_record(record['id']),record)
        with self.app.state.store.transaction(write=True) as db:
            for sql in ('UPDATE finishing_records SET reason=reason','DELETE FROM finishing_records'):
                with self.assertRaises(sqlite3.IntegrityError): db.execute(sql)
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute('''INSERT INTO finishing_records(id,reference,job_id,quantity,thread_trimmed,ironed,
                    labels_attached,hangtags_attached,packaged,completed_date,movement_id,reason,actor_id,created_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',('bad','FIN-DIRECT',job['id'],99,1,1,1,1,1,
                    '2026-09-16',record['movement_id'],'Bypass',self.admin['id'],'2026-09-16T00:00:00+00:00'))

        fresh_path=self.path.with_name('schema15.sqlite3')
        Store(fresh_path)
        with closing(sqlite3.connect(fresh_path)) as db:
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
            db.execute('PRAGMA user_version=15');db.commit()
        Store(fresh_path)
        with closing(sqlite3.connect(fresh_path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],42)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM finishing_records').fetchone()[0],0)
