"""Regresi P1: pcs yang dikirim dari final QC ke rework harus dapat diinspeksi ulang secara sah.

Sebelum perbaikan ini pengembalian rework ke QC hanya berupa perpindahan generik `rework -> qc`
tanpa lineage. Inspeksi kedua atas pcs tersebut selalu ditolak 409 karena alokasi final QC dihitung
terhadap `finishing_records.quantity` yang sudah habis dipakai inspeksi awal.

Invarian yang diuji di sini:
  I1 tidak ada pcs yang tercipta atau hilang pada seluruh siklus rework/inspeksi ulang
  I2 inspeksi awal hanya boleh memakai jumlah finishing yang belum diperiksa; inspeksi ulang tidak
  I3 selesai rework tidak boleh melebihi rework aktif dari catatan final QC sumbernya
  I4 inspeksi ulang tidak boleh melebihi jumlah yang dikembalikan catatan selesai rework-nya
  I5 siklus rework berulang legal tanpa batas satu siklus
  I6 accepted dari inspeksi ulang dapat diterima menjadi barang jadi seperti inspeksi awal
  I7 koreksi harus dibongkar dari hilir ke hulu, tanpa mengubah baris ledger historis
  I8 tanggal selesai rework dan inspeksi ulang tidak boleh mendahului sumbernya
  I9 lineage inspeksi ulang dapat dilacak sampai batch bahan
"""
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from threading import Barrier
from unittest import TestCase

from fastapi.testclient import TestClient
from beeloft.api import create_app
from beeloft.store import Store
import test_final_qc as final_qc_tests


class ReworkReinspectionTest(TestCase):
    setUp = final_qc_tests.FinalQcTest.setUp
    post = final_qc_tests.FinalQcTest.post
    order = final_qc_tests.FinalQcTest.order
    material = final_qc_tests.FinalQcTest.material
    receipt = final_qc_tests.FinalQcTest.receipt
    issue = final_qc_tests.FinalQcTest.issue
    setup_stock = final_qc_tests.FinalQcTest.setup_stock
    prepare = final_qc_tests.FinalQcTest.prepare
    cut = final_qc_tests.FinalQcTest.cut
    create_bundle = final_qc_tests.FinalQcTest.create_bundle
    setup_bundle = final_qc_tests.FinalQcTest.setup_bundle
    create_job = final_qc_tests.FinalQcTest.create_job
    complete = final_qc_tests.FinalQcTest.complete
    setup_job = final_qc_tests.FinalQcTest.setup_job
    finish = final_qc_tests.FinalQcTest.finish
    setup_finishing = final_qc_tests.FinalQcTest.setup_finishing
    inspect = final_qc_tests.FinalQcTest.inspect

    # helpers -----------------------------------------------------------------

    def totals(self, order):
        response = self.client.get('/api/orders/' + order['id'])
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()['totals']

    def complete_rework(self, record, reference='RWK-001', quantity=8,
                        completed_date='2026-09-18', **options):
        body = dict(reference=reference, quantity=quantity, completed_date=completed_date,
                    reason='Rework selesai dikerjakan ulang')
        return self.post('/api/final-qc-records/' + record['id'] + '/rework-completions', body, **options)

    def reinspect(self, completion, reference='QC-RE-001', accepted=8, rework=0, reject=0,
                  inspection_date='2026-09-19', **options):
        body = dict(reference=reference, measurement_notes='Ukuran diperiksa ulang',
                    visual_notes='Visual diperiksa ulang', defect_type='Tidak ada',
                    responsible_source='Tim rework', disposition='Lolos setelah rework',
                    accepted_quantity=accepted, rework_quantity=rework, reject_quantity=reject,
                    inspection_date=inspection_date, reason='Inspeksi ulang setelah rework selesai')
        return self.post('/api/rework-completions/' + completion['id'] + '/qc-records', body, **options)

    def receive(self, record, reference='FG-RE-001', sellable=8, **options):
        body = dict(reference=reference, scanned_sku=record['sku'], location='Rak A',
                    sellable_quantity=sellable, hold_quantity=0, received_date='2026-09-23',
                    reason='Terima hasil inspeksi ulang')
        return self.post('/api/final-qc-records/' + record['id'] + '/finished-goods-receipts',
                         body, **options)

    def setup_rework(self, accepted=12, rework=8):
        order, _, finishing = self.setup_finishing(20)
        record = self.inspect(finishing, reference='QC-001', accepted=accepted, rework=rework,
                             reject=0, inspection_date='2026-09-17')
        return order, finishing, record

    # I1, I2, I6, I9 ----------------------------------------------------------

    def test_rework_completion_enables_reinspection_and_warehouse_receipt(self):
        order, finishing, record = self.setup_rework()
        self.assertEqual((record['inspection_kind'], record['inspection_round']), ('initial', 1))
        self.assertEqual((record['rework_completed_quantity'], record['rework_remaining_quantity']), (0, 8))
        completion = self.complete_rework(record, key='rework-one')
        # I7 retry idempoten byte-identical.
        self.assertEqual(completion, self.complete_rework(record, key='rework-one'))
        self.assertEqual((completion['quantity'], completion['reinspected_quantity'],
                          completion['reinspection_remaining_quantity'], completion['next_inspection_round']),
                         (8, 0, 8, 2))
        self.assertEqual((completion['final_qc_reference'], completion['finishing_reference'],
                          completion['sewing_reference'], completion['bundle_reference'],
                          completion['batch_id']),
                         (record['reference'], finishing['reference'], finishing['sewing_reference'],
                          finishing['bundle_reference'], finishing['batch_id']))
        self.assertEqual(self.totals(order), {'planned': 70, 'cutting': 10, 'sewing': 0,
                                              'finishing': 0, 'qc': 8, 'rework': 0, 'reject': 0,
                                              'warehouse': 12})
        source = self.client.get('/api/final-qc-records/' + record['id']).json()
        self.assertEqual((source['rework_completed_quantity'], source['rework_remaining_quantity'],
                          source['active_rework_completion_count']), (8, 0, 1))
        again = self.reinspect(completion, key='reinspect-one')
        self.assertEqual(again, self.reinspect(completion, key='reinspect-one'))
        self.assertEqual((again['inspection_kind'], again['inspection_round'],
                          again['rework_completion_id'], again['rework_completion_reference'],
                          again['source_final_qc_record_id'], again['source_final_qc_reference'],
                          again['source_inspection_round']),
                         ('reinspection', 2, completion['id'], completion['reference'],
                          record['id'], record['reference'], 1))
        self.assertEqual(again['finishing_record_id'], finishing['id'])
        # I2 inspeksi ulang tidak memakai alokasi finishing lagi.
        current = self.client.get('/api/finishing-records/' + finishing['id']).json()
        self.assertEqual((current['qc_inspected_quantity'], current['qc_remaining_quantity']), (20, 0))
        self.assertEqual(self.totals(order), {'planned': 70, 'cutting': 10, 'sewing': 0,
                                              'finishing': 0, 'qc': 0, 'rework': 0, 'reject': 0,
                                              'warehouse': 20})
        # I6 accepted dari inspeksi ulang masuk barang jadi lewat jalur yang sama.
        receipt = self.receive(again)
        self.assertEqual((receipt['received_quantity'], receipt['final_qc_record_id']), (8, again['id']))
        # I1 seluruh 100 pcs order tetap utuh sepanjang siklus.
        self.assertEqual(sum(self.totals(order).values()), 100)
        # I9 lineage inspeksi ulang terlacak sampai batch bahan.
        trace = self.client.get('/api/material-batches/' + again['batch_id'] + '/traceability').json()
        kinds = {row['event_type'] for row in trace['events']}
        self.assertLessEqual({'final_qc', 'final_qc_reinspection', 'rework_completion',
                              'finished_goods_receipt', 'finishing', 'sewing_job', 'bundle',
                              'cutting_run', 'material_issue'}, kinds)
        reinspection_event = next(row for row in trace['events']
                                  if row['event_type'] == 'final_qc_reinspection')
        self.assertEqual(reinspection_event['detail_action'], 'final-qc-record')
        self.assertIn('Inspeksi ulang #1', reinspection_event['description'])
        self.assertIn(completion['reference'], reinspection_event['description'])
        listed = self.client.get('/api/orders/' + order['id'] + '/rework-completions').json()
        self.assertEqual([row['id'] for row in listed], [completion['id']])
        self.assertEqual(self.client.get('/api/rework-completions/' + completion['id']).json(),
                         self.client.get('/api/final-qc-records/' + record['id']
                                         + '/rework-completions').json()[0])

    # I5 ----------------------------------------------------------------------

    def test_repeated_rework_cycles_have_no_one_cycle_limit(self):
        order, finishing, record = self.setup_rework()
        first = self.complete_rework(record, reference='RWK-C1', quantity=8)
        second = self.reinspect(first, reference='QC-C2', accepted=3, rework=5, reject=0)
        self.assertEqual(self.totals(order)['rework'], 5)
        third = self.complete_rework(second, reference='RWK-C2', quantity=5,
                                     completed_date='2026-09-20')
        self.assertEqual(third['next_inspection_round'], 3)
        final = self.reinspect(third, reference='QC-C3', accepted=5, rework=0, reject=0,
                               inspection_date='2026-09-21')
        self.assertEqual(final['inspection_round'], 3)
        self.assertEqual(self.totals(order), {'planned': 70, 'cutting': 10, 'sewing': 0,
                                              'finishing': 0, 'qc': 0, 'rework': 0, 'reject': 0,
                                              'warehouse': 20})
        self.assertEqual(sum(self.totals(order).values()), 100)
        rounds = [(row['reference'], row['inspection_kind'], row['inspection_round'])
                  for row in self.client.get('/api/orders/' + order['id'] + '/final-qc-records').json()]
        self.assertEqual(rounds, [('QC-C3', 'reinspection', 3), ('QC-C2', 'reinspection', 2),
                                  ('QC-001', 'initial', 1)])
        # Rantai lineage lengkap dari inspeksi terakhir sampai finishing.
        self.assertEqual(final['source_final_qc_record_id'], second['id'])
        self.assertEqual(second['source_final_qc_record_id'], record['id'])
        self.assertEqual(final['finishing_record_id'], finishing['id'])

    # I3, I4 ------------------------------------------------------------------

    def test_partial_and_over_allocation_of_completions_and_reinspections(self):
        _, _, record = self.setup_rework()
        first = self.complete_rework(record, reference='RWK-P1', quantity=3)
        self.assertEqual(self.client.get('/api/final-qc-records/' + record['id']
                                         ).json()['rework_remaining_quantity'], 5)
        second = self.complete_rework(record, reference='RWK-P2', quantity=5)
        # I3 selesai rework tidak boleh melebihi rework aktif sumbernya.
        self.complete_rework(record, reference='RWK-OVER', quantity=1, status=409)
        self.complete_rework(record, reference='rwk-p1', quantity=1, status=409)
        partial = self.reinspect(first, reference='QC-P1', accepted=1, rework=0, reject=0)
        self.assertEqual(partial['inspected_quantity'], 1)
        self.assertEqual(self.client.get('/api/rework-completions/' + first['id']
                                         ).json()['reinspection_remaining_quantity'], 2)
        self.reinspect(first, reference='QC-P2', accepted=2, rework=0, reject=0)
        # I4 inspeksi ulang tidak boleh melebihi jumlah yang dikembalikan catatan sumbernya.
        self.reinspect(first, reference='QC-P-OVER', accepted=1, rework=0, reject=0, status=409)
        self.reinspect(second, reference='QC-P3', accepted=5, rework=0, reject=0)
        self.reinspect(second, reference='QC-P4', accepted=1, rework=0, reject=0, status=409)
        self.assertEqual(self.client.get('/api/rework-completions/missing').status_code, 404)
        self.complete_rework(dict(id='missing'), status=404)
        self.reinspect(dict(id='missing'), status=404)
        self.assertEqual(self.client.get('/api/orders/missing/rework-completions').status_code, 404)
        self.assertEqual(self.client.get('/api/final-qc-records/missing/rework-completions').status_code, 404)

    def test_completion_requires_rework_on_the_source_record(self):
        _, _, record = self.setup_rework(accepted=20, rework=0)
        self.complete_rework(record, quantity=1, status=409)

    # legacy data migrated from schema 54 ---------------------------------------

    def test_legacy_untraced_rework_return_is_reported_and_remediable(self):
        """Database schema 54 dapat memuat perpindahan rework -> qc tanpa lineage.

        Jumlah rework catatan QC-nya sudah tidak berada di tahap rework, jadi selesai rework tidak
        dapat dicatat sampai perpindahan lama itu dikoreksi. Keadaan ini harus dilaporkan apa adanya,
        bukan disembunyikan di balik tombol yang selalu gagal.
        """
        order, finishing, record = self.setup_rework()
        with self.app.state.store.transaction(write=True) as db:
            legacy = self.app.state.store._transfer(db, dict(line_id=record['line_id'],
                from_stage='rework', to_stage='qc', quantity=8,
                reason='Pengembalian rework lama tanpa lineage'), self.admin)
        self.assertEqual(self.totals(order)['rework'], 0)
        stuck = self.client.get('/api/final-qc-records/' + record['id']).json()
        self.assertEqual((stuck['rework_quantity'], stuck['rework_completed_quantity'],
                          stuck['rework_remaining_quantity'],
                          stuck['untraced_rework_return_quantity'],
                          stuck['rework_completable_quantity']),
                         (8, 0, 8, 8, 0))

        # Kedua jalur inspeksi tertutup, dan pesan selesai rework menjelaskan penyebab sebenarnya.
        self.inspect(finishing, reference='QC-STUCK', accepted=8, rework=0, reject=0,
                     inspection_date='2026-09-18', status=409)
        response = self.client.post(
            '/api/final-qc-records/' + record['id'] + '/rework-completions',
            json=dict(reference='RWK-STUCK', quantity=8, completed_date='2026-09-18',
                      reason='Rework selesai'),
            headers={'X-API-Key': self.admin['api_key'], 'Idempotency-Key': 'stuck'})
        self.assertEqual(response.status_code, 409, response.text)
        self.assertIn('tanpa catatan selesai rework', response.json()['detail'])
        self.assertIn('riwayat perpindahan order', response.json()['detail'])
        # Remediasi: admin mengoreksi perpindahan lama, lalu jalur resmi terbuka kembali.
        self.post('/api/movements/' + legacy['id'] + '/reverse',
                  dict(reason='Pengembalian rework lama tanpa lineage dikoreksi'))
        self.assertEqual(self.totals(order)['rework'], 8)
        released = self.client.get('/api/final-qc-records/' + record['id']).json()
        self.assertEqual((released['untraced_rework_return_quantity'],
                          released['rework_completable_quantity']), (0, 8))
        completion = self.complete_rework(record, quantity=8)
        again = self.reinspect(completion, accepted=8, rework=0, reject=0)
        self.assertEqual((again['inspection_kind'], again['inspection_round']), ('reinspection', 2))
        self.assertEqual(self.totals(order), {'planned': 70, 'cutting': 10, 'sewing': 0,
                                              'finishing': 0, 'qc': 0, 'rework': 0, 'reject': 0,
                                              'warehouse': 20})
        self.assertEqual(sum(self.totals(order).values()), 100)
        # Baris perpindahan lama tetap terbaca beserta pembaliknya.
        history = self.client.get('/api/orders/' + order['id'] + '/movements?limit=500').json()
        legacy_rows = [row for row in history
                       if row['from_stage'] == 'rework' and row['to_stage'] == 'qc']
        self.assertEqual([(row['quantity'], row['rework_completion_id'] is not None)
                          for row in legacy_rows], [(8, False), (8, True)])
        self.assertTrue(any(row['reversal_of'] == legacy['id'] for row in history))

    # I3, I4 races ------------------------------------------------------------

    def test_race_cannot_overallocate_one_rework_source(self):
        order, _, record = self.setup_rework()
        barrier = Barrier(2)

        def save(index):
            with TestClient(create_app(self.path)) as client:
                barrier.wait(timeout=10)
                return client.post('/api/final-qc-records/' + record['id'] + '/rework-completions',
                    json=dict(reference='RWK-RACE-' + str(index), quantity=6,
                              completed_date='2026-09-18', reason='Uji bersamaan'),
                    headers={'X-API-Key': self.operator['api_key'],
                             'Idempotency-Key': 'rework-race-' + str(index)}).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(save, range(2))), [201, 409])
        totals = self.totals(order)
        self.assertEqual((totals['qc'], totals['rework']), (6, 2))
        self.assertEqual(sum(totals.values()), 100)

    def test_race_cannot_overallocate_one_rework_completion(self):
        order, _, record = self.setup_rework()
        completion = self.complete_rework(record, quantity=8)
        barrier = Barrier(2)

        def save(index):
            with TestClient(create_app(self.path)) as client:
                barrier.wait(timeout=10)
                return client.post('/api/rework-completions/' + completion['id'] + '/qc-records',
                    json=dict(reference='QC-RACE-' + str(index), measurement_notes='Ukuran diperiksa',
                              visual_notes='Visual diperiksa', defect_type='Tidak ada',
                              responsible_source='Tim rework', disposition='Diterima gudang',
                              accepted_quantity=6, rework_quantity=0, reject_quantity=0,
                              inspection_date='2026-09-19', reason='Uji bersamaan'),
                    headers={'X-API-Key': self.operator['api_key'],
                             'Idempotency-Key': 'reinspect-race-' + str(index)}).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(save, range(2))), [201, 409])
        totals = self.totals(order)
        self.assertEqual((totals['qc'], totals['warehouse']), (2, 18))
        self.assertEqual(sum(totals.values()), 100)

    def test_untraced_return_does_not_block_other_records_on_the_same_line(self):
        """Kapasitas dibatasi saldo tahap rework yang nyata, bukan riwayat sepanjang baris order.

        Saldo tahap dikumpulkan per baris, jadi mengurangi total pengembalian tanpa lineage dari
        setiap catatan QC pada baris itu akan memblokir inspeksi lain yang pcs-nya justru masih
        benar-benar berada di rework.
        """
        order, finishing, first = self.setup_rework(accepted=0, rework=6)
        with self.app.state.store.transaction(write=True) as db:
            self.app.state.store._transfer(db, dict(line_id=first['line_id'], from_stage='rework',
                to_stage='qc', quantity=6, reason='Pengembalian rework lama tanpa lineage'),
                self.admin)
        second = self.inspect(finishing, reference='QC-LATER', accepted=0, rework=14, reject=0,
                              inspection_date='2026-09-18')
        self.assertEqual(self.totals(order)['rework'], 14)
        later = self.client.get('/api/final-qc-records/' + second['id']).json()
        # Enam pcs tanpa lineage milik inspeksi lain tidak boleh memotong kapasitas inspeksi ini.
        self.assertEqual((later['rework_remaining_quantity'],
                          later['untraced_rework_return_quantity'],
                          later['rework_completable_quantity']), (14, 6, 14))
        # Predikat blokir dan peringatan UI adalah per catatan (`rework_remaining_quantity` >
        # `rework_completable_quantity`), bukan keberadaan pengembalian tanpa lineage pada baris
        # order. Karena itu inspeksi ini tidak diberi peringatan walau melaporkan
        # untraced_rework_return_quantity yang sama dengan inspeksi sumbernya.
        self.assertEqual(later['rework_remaining_quantity'], later['rework_completable_quantity'])
        # Saldo tahap rework dikumpulkan per baris order. Setelah inspeksi kedua mengisi ulang tahap
        # rework, catatan pertama pun tidak lagi terblokir: penyelesaiannya memang dapat dijalankan
        # terhadap pcs yang ada. Atribusi pcs pengembalian tanpa lineage tidak dapat dipastikan, dan
        # jumlah tetap kekal karena total seluruh penyelesaian tidak pernah melampaui saldo tahap.
        source = self.client.get('/api/final-qc-records/' + first['id']).json()
        self.assertEqual(source['untraced_rework_return_quantity'],
                         later['untraced_rework_return_quantity'])
        self.assertEqual((source['rework_remaining_quantity'],
                          source['rework_completable_quantity']), (6, 6))
        completion = self.complete_rework(second, reference='RWK-LATER', quantity=14,
                                         completed_date='2026-09-19')
        self.reinspect(completion, reference='QC-LATER-RE', accepted=14, rework=0, reject=0,
                       inspection_date='2026-09-20')
        self.assertEqual(self.totals(order), {'planned': 70, 'cutting': 10, 'sewing': 0,
                                              'finishing': 0, 'qc': 6, 'rework': 0, 'reject': 0,
                                              'warehouse': 14})
        self.assertEqual(sum(self.totals(order).values()), 100)

    # I7 ----------------------------------------------------------------------

    def test_corrections_unwind_in_reverse_dependency_order(self):
        order, finishing, record = self.setup_rework()
        completion = self.complete_rework(record, quantity=8)
        again = self.reinspect(completion, accepted=8, rework=0, reject=0)
        receipt = self.receive(again)
        # Hulu terkunci selama hilir masih aktif.
        self.post('/api/final-qc-records/' + record['id'] + '/reverse',
                  dict(reason='Inspeksi awal salah'), status=409)
        self.post('/api/rework-completions/' + completion['id'] + '/reverse',
                  dict(reason='Selesai rework salah'), status=409)
        self.post('/api/final-qc-records/' + again['id'] + '/reverse',
                  dict(reason='Inspeksi ulang salah'), status=409)
        self.post('/api/finishing-records/' + finishing['id'] + '/reverse',
                  dict(reason='Finishing salah'), status=409)
        # Perpindahan milik catatan selesai rework tidak dapat dikoreksi terpisah.
        self.post('/api/movements/' + completion['movement_id'] + '/reverse',
                  dict(reason='Terpisah'), status=409)
        # Bongkar dari hilir ke hulu.
        self.post('/api/finished-goods-receipts/' + receipt['id'] + '/reverse',
                  dict(reason='Penerimaan salah'))
        self.post('/api/final-qc-records/' + again['id'] + '/reverse',
                  dict(reason='Inspeksi ulang salah'), key='reverse-reinspection')
        self.assertEqual(self.totals(order)['qc'], 8)
        self.post('/api/rework-completions/' + completion['id'] + '/reverse',
                  dict(reason='Selesai rework salah'), status=403, api_key=self.operator['api_key'])
        corrected = self.post('/api/rework-completions/' + completion['id'] + '/reverse',
                              dict(reason='Selesai rework salah'), key='reverse-completion')
        self.assertEqual(corrected, self.post('/api/rework-completions/' + completion['id'] + '/reverse',
                                              dict(reason='Selesai rework salah'), key='reverse-completion'))
        self.assertEqual((corrected['status'], corrected['reinspection_remaining_quantity']),
                         ('corrected', 0))
        self.post('/api/rework-completions/' + completion['id'] + '/reverse',
                  dict(reason='Sudah dikoreksi'), status=409)
        self.assertEqual(self.totals(order), {'planned': 70, 'cutting': 10, 'sewing': 0,
                                              'finishing': 0, 'qc': 0, 'rework': 8, 'reject': 0,
                                              'warehouse': 12})
        self.post('/api/final-qc-records/' + record['id'] + '/reverse', dict(reason='Inspeksi awal salah'))
        self.assertEqual(self.totals(order), {'planned': 70, 'cutting': 10, 'sewing': 0,
                                              'finishing': 0, 'qc': 20, 'rework': 0, 'reject': 0,
                                              'warehouse': 0})
        source = self.client.get('/api/finishing-records/' + finishing['id']).json()
        self.assertEqual((source['qc_inspected_quantity'], source['qc_remaining_quantity']), (0, 20))
        # Baris ledger historis tetap ada; koreksi hanya menambah baris pembalik.
        self.post('/api/finishing-records/' + finishing['id'] + '/reverse', dict(reason='Finishing salah'))
        self.assertEqual(sum(self.totals(order).values()), 100)
        with self.app.state.store.transaction(write=True) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM rework_completions').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM rework_completion_reversals'
                                        ).fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM final_qc_records').fetchone()[0], 2)
            for sql in ('UPDATE rework_completion_reversals SET reason=reason',
                        'DELETE FROM rework_completion_reversals'):
                with self.assertRaises(sqlite3.IntegrityError):
                    db.execute(sql)
        # Setelah semuanya dikoreksi, inspeksi awal dapat dicatat ulang dari nol.
        replacement = self.finish(dict(id=finishing['job_id']), reference='FIN-REPLACEMENT',
                                  quantity=20, completed_date='2026-09-16')
        self.inspect(replacement, reference='QC-REPLACEMENT', accepted=20, rework=0, reject=0)

    # I8 ----------------------------------------------------------------------

    def test_dates_cannot_precede_their_source(self):
        _, _, record = self.setup_rework()
        self.complete_rework(record, completed_date='2026-09-16', status=422)
        completion = self.complete_rework(record, completed_date='2026-09-18')
        self.reinspect(completion, inspection_date='2026-09-17', status=422)
        first = self.reinspect(completion, reference='QC-D1', accepted=4, rework=4, reject=0,
                               inspection_date='2026-09-18')
        # Siklus berulang mempertahankan urutan kronologis.
        self.complete_rework(first, reference='RWK-D2', quantity=4, completed_date='2026-09-17',
                            status=422)
        second = self.complete_rework(first, reference='RWK-D2', quantity=4,
                                      completed_date='2026-09-18')
        self.reinspect(second, reference='QC-D2', accepted=4, rework=0, reject=0,
                       inspection_date='2026-09-17', status=422)
        self.reinspect(second, reference='QC-D2', accepted=4, rework=0, reject=0,
                       inspection_date='2026-09-19')

    # roles, validation, generic movement --------------------------------------

    def test_roles_validation_and_generic_rework_return_is_refused(self):
        order, _, record = self.setup_rework()
        self.complete_rework(record, api_key=self.viewer['api_key'], status=403)
        self.complete_rework(record, quantity=0, status=422)
        self.complete_rework(record, quantity=True, status=422)
        # Perpindahan rework -> qc tanpa lineage tidak lagi diizinkan lewat endpoint generik.
        self.post('/api/movements', dict(line_id=record['line_id'], from_stage='rework',
                                        to_stage='qc', quantity=8, reason='Rework selesai'),
                  status=422)
        self.assertNotIn(['rework', 'qc'], self.client.get('/api/stages').json()['transitions'])
        self.assertEqual(self.totals(order)['rework'], 8)
        completion = self.complete_rework(record, api_key=self.operator['api_key'])
        self.reinspect(completion, api_key=self.viewer['api_key'], status=403)
        self.reinspect(completion, accepted=0, rework=0, reject=0, status=422)
        self.reinspect(completion, accepted=True, status=422)
        for role in (self.operator, self.viewer):
            self.post('/api/rework-completions/' + completion['id'] + '/reverse',
                      dict(reason='Salah'), api_key=role['api_key'], status=403)
        # Viewer tetap dapat membaca seluruh daftar dan rincian.
        for route in ('/api/rework-completions/' + completion['id'],
                      '/api/orders/' + order['id'] + '/rework-completions',
                      '/api/final-qc-records/' + record['id'] + '/rework-completions'):
            response = self.client.get(route, headers={'X-API-Key': self.viewer['api_key']})
            self.assertEqual(response.status_code, 200, response.text)

    def test_browser_session_retry_keeps_actor_binding_and_writes_once(self):
        order, _, record = self.setup_rework()
        self.client.headers.pop('X-API-Key', None)
        session = self.client.post('/api/session', json={'api_key': self.operator['api_key']})
        self.assertEqual(session.status_code, 200, session.text)
        actor = session.json()['id']
        body = dict(reference='RWK-BROWSER', quantity=8, completed_date='2026-09-18',
                    reason='Rework selesai dari browser')
        route = '/api/final-qc-records/' + record['id'] + '/rework-completions'
        headers = {'Idempotency-Key': 'rework-browser',
                   'X-CSRF-Token': self.client.cookies.get('beeloft_csrf'),
                   'X-Beeloft-Actor': actor}
        first = self.client.post(route, json=body, headers=headers)
        self.assertEqual(first.status_code, 201, first.text)
        # Retry setelah respons hilang mengembalikan hasil yang sama tanpa efek samping kedua.
        retry = self.client.post(route, json=body, headers=headers)
        self.assertEqual(retry.status_code, 201, retry.text)
        self.assertEqual(retry.json(), first.json())
        # Binding aktor menolak retry dari akun lain pada session browser yang sama.
        stale = self.client.post(route, json=body, headers=headers | {'X-Beeloft-Actor': self.admin['id']})
        self.assertEqual(stale.status_code, 403, stale.text)
        conflict = self.client.post(route, json=body | {'quantity': 7}, headers=headers)
        self.assertEqual(conflict.status_code, 409, conflict.text)
        with self.app.state.store.transaction() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM rework_completions').fetchone()[0], 1)
            self.assertEqual(db.execute(
                'SELECT COUNT(*) FROM audit_events WHERE request_key=?', ('rework-browser',)
            ).fetchone()[0], 1)
            self.assertEqual(db.execute(
                'SELECT actor_id FROM requests WHERE key=?', ('rework-browser',)).fetchone()[0], actor)
        self.client.headers['X-API-Key'] = self.admin['api_key']
        self.assertEqual(self.totals(order)['qc'], 8)

    # analytics ---------------------------------------------------------------

    def test_quality_insights_keep_first_pass_yield_on_initial_inspections_only(self):
        _, _, record = self.setup_rework(accepted=12, rework=8)
        route = ('/api/production-quality-insights?as_of=2026-09-23&window_days=14&status=all')
        before = self.client.get(route).json()['summary']
        self.assertEqual((before['record_count'], before['inspected_quantity'],
                          before['accepted_quantity'], before['first_pass_yield_percent'],
                          before['rework_rate_percent'], before['reinspection_record_count'],
                          before['reinspected_quantity']),
                         (1, 20, 12, '60.00', '40.00', 0, 0))
        completion = self.complete_rework(record, quantity=8)
        self.reinspect(completion, accepted=6, rework=0, reject=2, inspection_date='2026-09-19')
        after = self.client.get(route).json()
        summary = after['summary']
        # Populasi first pass yield tidak berubah walau ada inspeksi ulang.
        self.assertEqual((summary['record_count'], summary['inspected_quantity'],
                          summary['accepted_quantity'], summary['rework_quantity'],
                          summary['reject_quantity'], summary['nonconforming_quantity'],
                          summary['first_pass_yield_percent'], summary['nonconforming_rate_percent'],
                          summary['rework_rate_percent'], summary['reject_rate_percent']),
                         (1, 20, 12, 8, 0, 8, '60.00', '40.00', '40.00', '0.00'))
        # Metrik inspeksi ulang bersifat tambahan.
        self.assertEqual((summary['reinspection_record_count'], summary['reinspected_quantity'],
                          summary['reinspection_accepted_quantity'],
                          summary['reinspection_rework_quantity'],
                          summary['reinspection_reject_quantity']),
                         (1, 8, 6, 0, 2))
        self.assertEqual((after['first_pass_yield_basis'], after['reinspections']),
                         ('initial_inspections_only', 'reported_separately'))
        group = after['items'][0]
        self.assertEqual((group['current']['inspected_quantity'],
                          group['current']['first_pass_yield_percent'],
                          group['current']['reinspected_quantity'],
                          group['current']['reinspection_reject_quantity']),
                         (20, '60.00', 8, 2))
        # Breakdown defect dan sumber tetap berbasis inspeksi awal.
        self.assertEqual([item['nonconforming_quantity'] for item in group['defect_types']], [8])
        self.assertEqual([item['nonconforming_quantity'] for item in group['responsible_sources']], [8])
        self.assertEqual(sum(item['inspected_quantity'] for item in group['skus']), 20)
        kinds = sorted(item['inspection_kind'] for item in group['recent_records'])
        self.assertEqual(kinds, ['initial', 'reinspection'])

    def test_reinspection_failures_still_raise_a_quality_flag(self):
        """Barang yang gagal lagi setelah rework tidak boleh terlihat sehat.

        First pass yield tetap berbasis inspeksi awal, jadi kegagalan inspeksi ulang memakai alasan
        perhatian tambahan dengan denominator inspeksi ulang sendiri.
        """
        _, _, record = self.setup_rework(accepted=12, rework=8)
        completion = self.complete_rework(record, quantity=8)
        self.reinspect(completion, accepted=0, rework=0, reject=8, inspection_date='2026-09-19')
        # Jendela yang hanya memuat inspeksi ulang: tidak ada inspeksi awal di dalamnya.
        route = ('/api/production-quality-insights?as_of=2026-09-25&window_days=7&'
                 'warning_percent=20&status=all')
        response = self.client.get(route)
        self.assertEqual(response.status_code, 200, response.text)
        report = response.json()
        summary = report['summary']
        self.assertEqual((summary['record_count'], summary['inspected_quantity'],
                          summary['nonconforming_quantity']), (0, 0, 0))
        self.assertEqual((summary['reinspection_record_count'], summary['reinspected_quantity'],
                          summary['reinspection_reject_quantity'],
                          summary['reinspection_nonconforming_quantity'],
                          summary['reinspection_nonconforming_rate_percent']),
                         (1, 8, 8, 8, '100.00'))
        group = report['items'][0]
        self.assertEqual(group['status'], 'attention')
        # Hanya alasan inspeksi ulang yang menyala; angka inspeksi awal tidak boleh diklaim.
        self.assertEqual(group['attention_reasons'], ['reinspection_above_warning'])
        self.assertEqual(summary['attention_groups'], 1)
        # Breakdown SKU harus membawa angka inspeksi ulangnya, bukan hanya nol inspeksi awal.
        sku = group['skus'][0]
        self.assertEqual((sku['inspected_quantity'], sku['reinspected_quantity'],
                          sku['reinspection_nonconforming_quantity'],
                          sku['reinspection_nonconforming_rate_percent']), (0, 8, 8, '100.00'))
        # Command center mengekspor angka inspeksi ulang. Isi kartu perhatiannya bergantung pada jam
        # server, jadi diuji dengan clock yang dikunci di tests/test_management_command_center.py.
        quality_block = self.client.get('/api/command-center').json()['quality']
        self.assertLessEqual({'reinspected_quantity', 'reinspection_nonconforming_quantity',
                              'reinspection_nonconforming_rate_percent'}, set(quality_block))

    # storage guards ----------------------------------------------------------

    def test_rollback_backup_guards_and_migration_from_54(self):
        order, _, record = self.setup_rework()
        with self.app.state.store.transaction(write=True) as db:
            db.execute("CREATE TRIGGER fail_rework BEFORE INSERT ON requests WHEN NEW.key='fail-rework' "
                       "BEGIN SELECT RAISE(ABORT,'test'); END")
        self.complete_rework(record, key='fail-rework', status=409)
        self.assertEqual(self.totals(order)['rework'], 8)
        completion = self.complete_rework(record, quantity=3)
        again = self.reinspect(completion, reference='QC-BK', accepted=3, rework=0, reject=0)
        backup = self.path.with_name('rework-backup.sqlite3')
        self.app.state.store.backup(backup)
        restored = Store(backup)
        self.assertEqual(restored.rework_completion(completion['id']),
                         self.client.get('/api/rework-completions/' + completion['id']).json())
        self.assertEqual(restored.final_qc_record(again['id']), again)
        with self.app.state.store.transaction(write=True) as db:
            for sql in ('UPDATE rework_completions SET reason=reason',
                        'DELETE FROM rework_completions'):
                with self.assertRaises(sqlite3.IntegrityError):
                    db.execute(sql)
            # Trigger menolak selesai rework yang melebihi rework sumbernya.
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute('''INSERT INTO rework_completions(id,reference,final_qc_record_id,quantity,
                    completed_date,movement_id,reason,actor_id,created_at)
                    VALUES(?,?,?,?,?,?,?,?,?)''', ('bad', 'RWK-DIRECT', record['id'], 99,
                    '2026-09-18', completion['movement_id'], 'Bypass', self.admin['id'],
                    '2026-09-18T00:00:00+00:00'))
            # Trigger menolak inspeksi ulang tanpa nomor putaran yang benar.
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute('''INSERT INTO final_qc_records(id,reference,finishing_record_id,
                    measurement_notes,visual_notes,accepted_quantity,rework_quantity,reject_quantity,
                    inspection_date,accepted_movement_id,rework_movement_id,reject_movement_id,
                    reason,actor_id,created_at,rework_completion_id,inspection_round)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', ('bad-qc', 'QC-DIRECT',
                    record['finishing_record_id'], 'Ukuran', 'Visual', 0, 0, 0, '2026-09-19',
                    None, None, None, 'Bypass', self.admin['id'], '2026-09-19T00:00:00+00:00',
                    completion['id'], 5))
            # Trigger menolak inspeksi ulang yang melebihi jumlah catatan selesai rework-nya.
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute('''INSERT INTO final_qc_records(id,reference,finishing_record_id,
                    measurement_notes,visual_notes,accepted_quantity,rework_quantity,reject_quantity,
                    inspection_date,accepted_movement_id,rework_movement_id,reject_movement_id,
                    reason,actor_id,created_at,rework_completion_id,inspection_round)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', ('bad-qc2', 'QC-DIRECT-2',
                    record['finishing_record_id'], 'Ukuran', 'Visual', 99, 0, 0, '2026-09-19',
                    again['accepted_movement_id'], None, None, 'Bypass', self.admin['id'],
                    '2026-09-19T00:00:00+00:00', completion['id'], 2))
            # Trigger menolak inspeksi awal yang mengaku sebagai inspeksi ulang.
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute('''INSERT INTO final_qc_records(id,reference,finishing_record_id,
                    measurement_notes,visual_notes,accepted_quantity,rework_quantity,reject_quantity,
                    inspection_date,accepted_movement_id,rework_movement_id,reject_movement_id,
                    reason,actor_id,created_at,rework_completion_id,inspection_round)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', ('bad-qc3', 'QC-DIRECT-3',
                    record['finishing_record_id'], 'Ukuran', 'Visual', 1, 0, 0, '2026-09-19',
                    None, None, None, 'Bypass', self.admin['id'], '2026-09-19T00:00:00+00:00',
                    None, 2))
            # Trigger menegakkan integritas referensial rework_completion_id tanpa klausa FK,
            # sehingga id yang tidak menunjuk catatan selesai rework mana pun tetap ditolak.
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute('''INSERT INTO final_qc_records(id,reference,finishing_record_id,
                    measurement_notes,visual_notes,accepted_quantity,rework_quantity,reject_quantity,
                    inspection_date,accepted_movement_id,rework_movement_id,reject_movement_id,
                    reason,actor_id,created_at,rework_completion_id,inspection_round)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', ('bad-qc4', 'QC-DIRECT-4',
                    record['finishing_record_id'], 'Ukuran', 'Visual', 1, 0, 0, '2026-09-19',
                    None, None, None, 'Bypass', self.admin['id'], '2026-09-19T00:00:00+00:00',
                    'tidak-ada-catatan-selesai-rework', 2))
            # Trigger menolak koreksi selesai rework selama inspeksi ulang masih aktif.
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute('''INSERT INTO rework_completion_reversals(record_id,reason,actor_id,created_at)
                    VALUES(?,?,?,?)''', (completion['id'], 'Bypass', self.admin['id'],
                    '2026-09-20T00:00:00+00:00'))

        # Fixture schema 54 yang setia: tabel, trigger, dan kedua kolom lineage dihapus, sehingga
        # migrasi benar-benar menjalankan cabang ALTER TABLE seperti pada database produksi.
        fresh_path = self.path.with_name('schema54.sqlite3')
        Store(fresh_path)
        with closing(sqlite3.connect(fresh_path)) as db:
            db.execute('DROP TRIGGER rework_completion_blocks_final_qc_reversal')
            db.execute('DROP TRIGGER final_qc_blocks_rework_completion_reversal')
            db.execute('DROP TABLE rework_completion_reversals')
            db.execute('DROP TABLE rework_completions')
            db.execute('DROP TRIGGER final_qc_source_valid')
            db.execute('DROP INDEX final_qc_records_rework_completion')
            db.execute('ALTER TABLE final_qc_records DROP COLUMN rework_completion_id')
            db.execute('ALTER TABLE final_qc_records DROP COLUMN inspection_round')
            db.execute('PRAGMA user_version=54')
            db.commit()
            self.assertEqual({row[1] for row in db.execute('PRAGMA table_info(final_qc_records)')}
                             & {'rework_completion_id', 'inspection_round'}, set())
        Store(fresh_path)
        with closing(sqlite3.connect(fresh_path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 55)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM rework_completions').fetchone()[0], 0)
            self.assertEqual({row[1] for row in db.execute('PRAGMA table_info(final_qc_records)')}
                             & {'rework_completion_id', 'inspection_round'},
                             {'rework_completion_id', 'inspection_round'})
            self.assertEqual(list(db.execute('PRAGMA foreign_key_check')), [])
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
