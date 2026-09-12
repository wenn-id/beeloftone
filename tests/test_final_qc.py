import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from threading import Barrier
from unittest import TestCase

from fastapi.testclient import TestClient
from beeloft.api import create_app
from beeloft.store import Store
import test_finishing as finishing_tests


class FinalQcTest(TestCase):
    setUp = finishing_tests.FinishingTest.setUp
    post = finishing_tests.FinishingTest.post
    order = finishing_tests.FinishingTest.order
    material = finishing_tests.FinishingTest.material
    receipt = finishing_tests.FinishingTest.receipt
    issue = finishing_tests.FinishingTest.issue
    setup_stock = finishing_tests.FinishingTest.setup_stock
    prepare = finishing_tests.FinishingTest.prepare
    cut = finishing_tests.FinishingTest.cut
    create_bundle = finishing_tests.FinishingTest.create_bundle
    setup_bundle = finishing_tests.FinishingTest.setup_bundle
    create_job = finishing_tests.FinishingTest.create_job
    complete = finishing_tests.FinishingTest.complete
    setup_job = finishing_tests.FinishingTest.setup_job
    finish = finishing_tests.FinishingTest.finish

    def setup_finishing(self, quantity=20):
        order, _, job = self.setup_job(quantity)
        finishing = self.finish(job, quantity=quantity)
        return order, job, finishing

    def inspect(self, finishing, reference='QC-001', accepted=6, rework=1, reject=1,
                inspection_date='2026-09-17', **options):
        body=dict(reference=reference,measurement_notes='Ukuran sesuai toleransi',
                  visual_notes='Jahitan dan warna diperiksa',defect_type='Noda ringan',
                  responsible_source='Finishing internal',disposition='Pisahkan rework dan reject',accepted_quantity=accepted,
                  rework_quantity=rework,reject_quantity=reject,inspection_date=inspection_date,
                  reason='Final QC selesai dihitung')
        return self.post('/api/finishing-records/'+finishing['id']+'/qc-records',body,**options)

    def test_partial_qc_captures_findings_lineage_and_all_outcomes(self):
        order, _, finishing=self.setup_finishing()
        first=self.inspect(finishing,key='qc-one')
        self.assertEqual(first,self.inspect(finishing,key='qc-one'))
        second=self.inspect(finishing,reference='QC-002',accepted=10,rework=1,reject=1,key='qc-two')
        self.assertEqual((first['inspected_quantity'],second['inspected_quantity']),(8,12))
        self.assertEqual(first['finishing_reference'],finishing['reference'])
        self.assertEqual(first['sewing_reference'],finishing['sewing_reference'])
        self.assertEqual(first['bundle_reference'],finishing['bundle_reference'])
        self.assertEqual(first['batch_id'],finishing['batch_id'])
        totals=self.client.get('/api/orders/'+order['id']).json()['totals']
        self.assertEqual((totals['qc'],totals['warehouse'],totals['rework'],totals['reject']),(0,16,2,2))
        source=self.client.get('/api/finishing-records/'+finishing['id']).json()
        self.assertEqual((source['qc_inspected_quantity'],source['qc_remaining_quantity']),(20,0))
        listed=self.client.get('/api/orders/'+order['id']+'/final-qc-records').json()
        self.assertEqual([row['id'] for row in listed],[second['id'],first['id']])
        self.assertEqual(self.client.get('/api/final-qc-records/'+first['id']).json(),first)

    def test_correction_restores_qc_and_releases_finishing(self):
        order, _, finishing=self.setup_finishing()
        record=self.inspect(finishing)
        self.post('/api/finishing-records/'+finishing['id']+'/reverse',dict(reason='Finishing salah'),status=409)
        self.post('/api/movements/'+record['accepted_movement_id']+'/reverse',dict(reason='Terpisah'),status=409)
        corrected=self.post('/api/final-qc-records/'+record['id']+'/reverse',dict(reason='Hasil QC salah'),key='reverse-qc')
        self.assertEqual(corrected,self.post('/api/final-qc-records/'+record['id']+'/reverse',
                                             dict(reason='Hasil QC salah'),key='reverse-qc'))
        self.assertEqual(corrected['status'],'corrected')
        totals=self.client.get('/api/orders/'+order['id']).json()['totals']
        self.assertEqual((totals['qc'],totals['warehouse'],totals['rework'],totals['reject']),(20,0,0,0))
        source=self.client.get('/api/finishing-records/'+finishing['id']).json()
        self.assertEqual((source['qc_inspected_quantity'],source['qc_remaining_quantity']),(0,20))
        self.inspect(finishing,reference='QC-REPLACEMENT',accepted=20,rework=0,reject=0)

    def test_validation_roles_dates_totals_and_allocation(self):
        _, _, finishing=self.setup_finishing()
        self.inspect(finishing,api_key=self.viewer['api_key'],status=403)
        self.inspect(finishing,accepted=True,status=422)
        self.inspect(finishing,accepted=0,rework=0,reject=0,status=422)
        self.inspect(finishing,inspection_date='2026-09-15',status=422)
        self.inspect(dict(id='missing'),status=404)
        record=self.inspect(finishing,accepted=20,rework=0,reject=0)
        self.inspect(finishing,reference='QC-OVER',accepted=1,rework=0,reject=0,status=409)
        self.inspect(finishing,reference='qc-001',accepted=1,rework=0,reject=0,status=409)
        for role in (self.operator,self.viewer):
            self.post('/api/final-qc-records/'+record['id']+'/reverse',dict(reason='Salah'),
                      api_key=role['api_key'],status=403)
        self.assertEqual(self.client.get('/api/orders/missing/final-qc-records').status_code,404)
        self.assertEqual(self.client.get('/api/final-qc-records/missing').status_code,404)

    def test_race_cannot_overinspect_one_finishing_record(self):
        order, _, finishing=self.setup_finishing()
        barrier=Barrier(2)
        def save(index):
            with TestClient(create_app(self.path)) as client:
                barrier.wait(timeout=10)
                return client.post('/api/finishing-records/'+finishing['id']+'/qc-records',json=dict(
                    reference='QC-RACE-'+str(index),measurement_notes='Ukuran diperiksa',visual_notes='Visual diperiksa',
                    defect_type='Tidak ada',responsible_source='QC internal',disposition='Diterima gudang',
                    accepted_quantity=15,rework_quantity=0,reject_quantity=0,inspection_date='2026-09-17',
                    reason='Uji bersamaan'),headers={'X-API-Key':self.operator['api_key'],
                    'Idempotency-Key':'qc-race-'+str(index)}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(save,range(2))),[201,409])
        totals=self.client.get('/api/orders/'+order['id']).json()['totals']
        self.assertEqual((totals['qc'],totals['warehouse']),(5,15))

    def test_rework_moved_back_to_qc_blocks_correction_atomically(self):
        order, _, finishing=self.setup_finishing()
        record=self.inspect(finishing,accepted=0,rework=8,reject=0)
        self.post('/api/movements',dict(line_id=record['line_id'],from_stage='rework',to_stage='qc',
                                        quantity=8,reason='Rework selesai'))
        self.post('/api/final-qc-records/'+record['id']+'/reverse',dict(reason='Salah'),status=409)
        self.assertEqual(self.client.get('/api/final-qc-records/'+record['id']).json()['status'],'completed')
        totals=self.client.get('/api/orders/'+order['id']).json()['totals']
        self.assertEqual((totals['qc'],totals['rework']),(20,0))

    def test_rollback_backup_guards_and_migration_from_16(self):
        order, _, finishing=self.setup_finishing()
        with self.app.state.store.transaction(write=True) as db:
            db.execute("CREATE TRIGGER fail_final_qc BEFORE INSERT ON requests WHEN NEW.key='fail-final-qc' "
                       "BEGIN SELECT RAISE(ABORT,'test'); END")
        self.inspect(finishing,key='fail-final-qc',status=409)
        self.assertEqual(self.client.get('/api/orders/'+order['id']).json()['totals']['qc'],20)
        record=self.inspect(finishing,accepted=3,rework=0,reject=0)
        backup=self.path.with_name('final-qc-backup.sqlite3')
        self.app.state.store.backup(backup)
        self.assertEqual(Store(backup).final_qc_record(record['id']),record)
        with self.app.state.store.transaction(write=True) as db:
            for sql in ('UPDATE final_qc_records SET reason=reason','DELETE FROM final_qc_records'):
                with self.assertRaises(sqlite3.IntegrityError): db.execute(sql)
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute('''INSERT INTO final_qc_records(id,reference,finishing_record_id,measurement_notes,
                    visual_notes,accepted_quantity,rework_quantity,reject_quantity,inspection_date,
                    accepted_movement_id,rework_movement_id,reject_movement_id,reason,actor_id,created_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',('bad','QC-DIRECT',finishing['id'],'Ukuran','Visual',
                    99,0,0,'2026-09-17',record['accepted_movement_id'],None,None,'Bypass',self.admin['id'],
                    '2026-09-17T00:00:00+00:00'))

        fresh_path=self.path.with_name('schema16.sqlite3')
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
            db.execute('PRAGMA user_version=16');db.commit()
        Store(fresh_path)
        with closing(sqlite3.connect(fresh_path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],27)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM final_qc_records').fetchone()[0],0)
