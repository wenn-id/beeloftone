"""P03 (#52): tes job karyawan, realisasi, service charge, dan reversal.

Pola mengikuti tests/test_service_templates.py (P01 #48) dan
tests/test_production.py:
- subclass ProductionTest untuk setUp bersama (temp DB + TestClient);
- seeding master (service group, work type, tarif) via endpoint HTTP;
- pemanggilan store langsung untuk operasi P03 karena endpoint HTTP
  '/api/employee-jobs' belum di-wire di beeloft/api.py pada branch ini;
  status error diassert via DomainError.status (404/409/422/403);
- subTest untuk kasus validasi sejenis;
- ThreadPoolExecutor + Barrier untuk uji konkurensi;
- uji upgrade schema 60 -> 61 meniru pola test_upgrade_59_to_60.

Seluruh data sintetis. Setiap test independen (setUp bikin DB fresh).
"""

import json
import sqlite3
import unittest
from concurrent.futures import ThreadPoolExecutor, wait
from pathlib import Path
from threading import Barrier
from uuid import uuid4

from beeloft.contracts import DEMO_POLICY, wage_for_realization
from beeloft.store import DomainError, Store

import test_production

WORK_DATE = '2026-09-10'


class EmployeeJobTest(test_production.ProductionTest):

    def setUp(self):
        super().setUp()
        self.store = self.app.state.store
        # approver: admin kedua agar SoD (no self-approval) selalu terpenuhi;
        # pembuat/pengaju realisasi memakai self.operator.
        self.approver = self.store.provision_user('Penyetuju', 'admin')
        self.hr = self.store.provision_user('Staf HR', 'admin', preset='hr_payroll')
        self.finance = self.store.provision_user('Staf Keuangan', 'admin', preset='finance')
        self.prod_op = self.store.provision_user(
            'Operator Produksi', 'operator', preset='production_operator')
        self.group = self.post('/api/service-groups', {
            'code': 'P03-GRUP', 'name': 'Grup P03', 'reason': 'seed'})
        self.wt = self.work_type('P03-JAHIT', amount='120.00')
        self.emp = self.employee('P03-EMP-001', 'Sari')

    # -- helper seeding -------------------------------------------------

    def work_type(self, code, amount='120.00', expected_revision=0,
                  effective_from='2026-09-01', effective_to=None,
                  with_rate=True):
        wt = self.post('/api/work-types', {
            'code': code, 'name': 'Pekerjaan ' + code,
            'service_group_id': self.group['id'], 'reason': 'seed'})
        rate = None
        if with_rate:
            rate = self.post(f"/api/work-types/{wt['id']}/rates", {
                'expected_revision': expected_revision, 'rate_basis': 'lusin',
                'amount': amount, 'effective_from': effective_from,
                'effective_to': effective_to, 'active': True,
                'reason': 'seed ' + code})
        return dict(wt) | {'rate': rate}

    def employee(self, code='P03-EMP-001', name='Sari'):
        return self.post('/api/workforce/employees', {
            'code': code, 'name': name, 'department': 'Produksi',
            'reason': 'seed'})

    def job(self, employee=None, work_type=None, target=100,
            work_date=WORK_DATE, actor=None, **kw):
        body = {
            'employee_id': (employee or self.emp)['id'],
            'sku': 'SKU-DEMO-001',
            'work_type_id': (work_type or self.wt)['id'],
            'target_qty_pcs': target,
            'work_date': work_date,
        }
        body.update(kw)
        return self.store.create_employee_job(
            body, actor or self.operator, 'job-' + uuid4().hex)

    def realization(self, job_id, qty, work_date=WORK_DATE, actor=None):
        return self.store.create_job_realization(
            job_id, {'qty_pcs': qty, 'work_date': work_date},
            actor or self.operator, 'rlz-' + uuid4().hex)

    def submit(self, job_id, rid, actor=None, key=None):
        return self.store.submit_job_realization(
            job_id, rid, actor or self.operator,
            key or ('submit-' + uuid4().hex))

    def approve(self, job_id, rid, actor=None, key=None):
        return self.store.approve_job_realization(
            job_id, rid, actor or self.approver,
            key or ('approve-' + uuid4().hex))

    def err(self, fn, *args, **kwargs):
        with self.assertRaises(DomainError) as ctx:
            fn(*args, **kwargs)
        return ctx.exception

    def charge_count(self, job_id, rid):
        with self.store.transaction() as db:
            return db.execute(
                """SELECT COUNT(*) FROM p03_service_charges
                   WHERE source_namespace='p03.service_charge'
                   AND source_id=? AND source_line_id=?""",
                (job_id, rid)).fetchone()[0]

    def charge_row(self, charge_id):
        with self.store.transaction() as db:
            return dict(db.execute(
                'SELECT * FROM p03_service_charges WHERE id=?',
                (charge_id,)).fetchone())

    # -- 1. validasi pembuatan job --------------------------------------

    def test_create_job_validations(self):
        cases = [
            ('employee tidak ada', dict(employee={'id': 'EMP-TIDAK-ADA'}),
             404, 'Karyawan tidak ditemukan'),
            ('work_type tidak ada', dict(work_type={'id': 'WT-TIDAK-ADA'}),
             404, 'Jenis pekerjaan tidak ditemukan'),
            ('bundle tidak ada', dict(bundle_id='BND-TIDAK-ADA'),
             404, 'Bundle tidak ditemukan'),
            ('target_qty nol', dict(target=0), 422, 'integer positif'),
            ('target_qty negatif', dict(target=-5), 422, 'integer positif'),
        ]
        for label, kw, status, msg in cases:
            with self.subTest(label):
                e = self.err(self.job, **kw)
                self.assertEqual(e.status, status, e.message)
                self.assertIn(msg, e.message)

    def test_create_job_inactive_employee(self):
        emp = self.employee('P03-EMP-002', 'Budi')
        self.post(f"/api/workforce/employees/{emp['id']}/changes", {
            'expected_revision': 1, 'name': 'Budi', 'department': 'Produksi',
            'active': False, 'reason': 'nonaktif'}, status=201)
        e = self.err(self.job, employee=emp)
        self.assertEqual(e.status, 422, e.message)
        self.assertIn('nonaktif', e.message)

    # -- 2. remaining derived -------------------------------------------

    def test_remaining_derived(self):
        job = self.job(target=100)
        self.assertEqual(job['remaining_qty_pcs'], 100)
        r1 = self.realization(job['id'], 30)
        self.submit(job['id'], r1['id'])
        self.approve(job['id'], r1['id'])
        view = self.store.get_employee_job(job['id'], self.admin)
        self.assertEqual(view['approved_qty_pcs'], 30)
        self.assertEqual(view['remaining_qty_pcs'], 70)
        # melebihi sisa -> 422
        e = self.err(self.realization, job['id'], 80)
        self.assertEqual(e.status, 422, e.message)
        self.assertIn('70', e.message)
        # pas sisa -> ok, lalu remaining 0
        r2 = self.realization(job['id'], 70)
        self.submit(job['id'], r2['id'])
        self.approve(job['id'], r2['id'])
        view = self.store.get_employee_job(job['id'], self.admin)
        self.assertEqual(view['remaining_qty_pcs'], 0)
        e = self.err(self.realization, job['id'], 1)
        self.assertEqual(e.status, 422, e.message)

    # -- 3. snapshot tarif ----------------------------------------------

    def test_rate_change_snapshot(self):
        job = self.job(target=100)
        r1 = self.realization(job['id'], 30)
        self.submit(job['id'], r1['id'])
        charge1 = self.approve(job['id'], r1['id'])
        snap1 = json.loads(charge1['rate_snapshot'])
        self.assertEqual(snap1['rate_revision'], 'P03-JAHIT#1')
        self.assertEqual(snap1['rate_per_lusin_minor'], 12000)
        # revisi tarif: nonaktifkan rev 1, lalu simpan rev 3
        self.post(f"/api/work-types/{self.wt['id']}/rates/deactivate", {
            'expected_revision': 1, 'reason': 'ganti tarif'}, status=200)
        self.post(f"/api/work-types/{self.wt['id']}/rates", {
            'expected_revision': 2, 'rate_basis': 'lusin', 'amount': '180.00',
            'effective_from': '2026-09-01', 'effective_to': None,
            'active': True, 'reason': 'naik'})
        r2 = self.realization(job['id'], 40, work_date='2026-09-12')
        self.submit(job['id'], r2['id'])
        charge2 = self.approve(job['id'], r2['id'])
        snap2 = json.loads(charge2['rate_snapshot'])
        self.assertEqual(snap2['rate_revision'], 'P03-JAHIT#3')
        self.assertEqual(snap2['rate_per_lusin_minor'], 18000)
        # charge lama TIDAK berubah
        old = self.charge_row(charge1['id'])
        self.assertEqual(old['final_amount_minor'],
                         charge1['final_amount_minor'])
        self.assertEqual(json.loads(old['rate_snapshot'])['rate_revision'],
                         'P03-JAHIT#1')
        self.assertNotEqual(charge1['final_amount_minor'],
                            charge2['final_amount_minor'])

    # -- 4. tarif belum ada ----------------------------------------------

    def test_rate_missing(self):
        wt = self.work_type('P03-TANPA-TARIF', with_rate=False)
        job = self.job(work_type=wt)
        r = self.realization(job['id'], 10)
        self.submit(job['id'], r['id'])
        e = self.err(self.approve, job['id'], r['id'])
        self.assertEqual(e.status, 422, e.message)
        self.assertIn('belum pernah dibuat', e.message)

    # -- 5. reject tanpa charge ------------------------------------------

    def test_reject_no_charge(self):
        job = self.job()
        r = self.realization(job['id'], 25)
        self.submit(job['id'], r['id'])
        rejected = self.store.reject_job_realization(
            job['id'], r['id'], {'reason': 'kualitas kurang'},
            self.approver, 'reject-' + uuid4().hex)
        self.assertEqual(rejected['status'], 'rejected')
        self.assertEqual(rejected['reject_reason'], 'kualitas kurang')
        self.assertEqual(self.charge_count(job['id'], r['id']), 0)
        # reject tanpa reason -> 422
        r2 = self.realization(job['id'], 10)
        self.submit(job['id'], r2['id'])
        e = self.err(self.store.reject_job_realization, job['id'], r2['id'],
                     {'reason': ''}, self.approver, 'reject-' + uuid4().hex)
        self.assertEqual(e.status, 422, e.message)
        self.assertIn('Alasan penolakan wajib diisi', e.message)

    # -- 6. revision guard -----------------------------------------------

    def test_revision_guard(self):
        job = self.job()
        e = self.err(self.store.update_employee_job, job['id'],
                     {'expected_revision': 999, 'notes': 'ubah'},
                     self.admin, 'upd-' + uuid4().hex)
        self.assertEqual(e.status, 409, e.message)
        r = self.realization(job['id'], 10)
        e = self.err(self.store.update_job_realization, job['id'], r['id'],
                     {'expected_revision': 999, 'notes': 'ubah'},
                     self.admin, 'upd-' + uuid4().hex)
        self.assertEqual(e.status, 409, e.message)
        # revision benar tetap bisa
        ok = self.store.update_job_realization(
            job['id'], r['id'],
            {'expected_revision': 1, 'notes': 'catatan'},
            self.admin, 'upd-' + uuid4().hex)
        self.assertEqual(ok['revision'], 2)

    # -- 7. idempotent replay --------------------------------------------

    def test_approve_idempotent_replay(self):
        job = self.job()
        r = self.realization(job['id'], 20)
        self.submit(job['id'], r['id'])
        charge = self.approve(job['id'], r['id'])
        # approve ulang realisasi yang sudah approved -> 409
        e = self.err(self.approve, job['id'], r['id'])
        self.assertEqual(e.status, 409, e.message)
        self.assertEqual(self.charge_count(job['id'], r['id']), 1)
        # replay submit dengan Idempotency-Key SAMA -> respons identik
        r2 = self.realization(job['id'], 5)
        s1 = self.submit(job['id'], r2['id'], key='submit-sekali')
        s2 = self.submit(job['id'], r2['id'], key='submit-sekali')
        self.assertEqual(s1, s2)
        self.assertEqual(s1['status'], 'submitted')

    # -- 8. konkurensi approve -------------------------------------------

    def test_concurrent_approve_single_charge(self):
        job = self.job()
        r = self.realization(job['id'], 15)
        self.submit(job['id'], r['id'])
        barrier = Barrier(2, timeout=10)
        results = []

        def approve_once():
            barrier.wait()
            store = Store(self.path)
            try:
                results.append(store.approve_job_realization(
                    job['id'], r['id'], self.approver, 'approve-konkuren'))
            except Exception as exc:  # noqa: BLE001 - dikumpulkan utk assert
                results.append(exc)

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(approve_once) for _ in range(2)]
            wait(futures, timeout=15)
        errors = [x for x in results if isinstance(x, Exception)]
        self.assertEqual(errors, [])
        self.assertEqual(len(results), 2)
        # tepat 1 charge di DB; keduanya sukses dengan charge yang sama
        self.assertEqual(self.charge_count(job['id'], r['id']), 1)
        self.assertEqual(results[0]['id'], results[1]['id'])

    # -- 9. reversal charge ----------------------------------------------

    def test_reverse_charge(self):
        job = self.job()
        r = self.realization(job['id'], 30)
        self.submit(job['id'], r['id'])
        charge = self.approve(job['id'], r['id'])
        reversal = self.store.reverse_service_charge(
            charge['id'], {'reason': 'salah catat qty'},
            self.approver, 'reverse-' + uuid4().hex)
        self.assertEqual(reversal['reversal_of_charge_id'], charge['id'])
        self.assertEqual(reversal['final_amount_minor'],
                         -charge['final_amount_minor'])
        self.assertEqual(reversal['payable_qty_pcs'], -30)
        self.assertLess(reversal['final_amount_minor'], 0)
        # reverse lagi -> 409
        e = self.err(self.store.reverse_service_charge, charge['id'],
                     {'reason': 'lagi'}, self.approver,
                     'reverse-' + uuid4().hex)
        self.assertEqual(e.status, 409, e.message)
        # charge original immutable: tetap ada dan tidak berubah
        original = self.charge_row(charge['id'])
        self.assertEqual(original['final_amount_minor'],
                         charge['final_amount_minor'])
        self.assertIsNone(original['reversal_of_charge_id'])

    # -- 10. charge yang sudah dikonsumsi tidak bisa di-reverse -----------

    def test_consumed_charge_reject_reverse(self):
        job = self.job()
        r = self.realization(job['id'], 30)
        self.submit(job['id'], r['id'])
        charge = self.approve(job['id'], r['id'])
        # simulasi downstream (payroll #55) mengonsumsi charge: trigger
        # imutabilitas dilepas sementara untuk keperluan simulasi
        with self.store.transaction(write=True) as db:
            db.execute('DROP TRIGGER IF EXISTS p03_charge_no_update')
            db.execute("UPDATE p03_service_charges SET consumed_by='payroll#55' "
                       'WHERE id=?', (charge['id'],))
        e = self.err(self.store.reverse_service_charge, charge['id'],
                     {'reason': 'koreksi'}, self.approver,
                     'reverse-' + uuid4().hex)
        self.assertEqual(e.status, 409, e.message)
        self.assertIn('payroll#55', e.message)

    # -- 11. visibilitas gaji & izin approve ------------------------------

    def test_salary_visibility(self):
        job = self.job()
        r = self.realization(job['id'], 24)
        self.submit(job['id'], r['id'])
        charge = self.approve(job['id'], r['id'], actor=self.hr)
        # tanpa view_salary: nominal disembunyikan
        masked = self.store.get_service_charge(charge['id'], self.finance)
        self.assertIsNone(masked['final_amount_minor'])
        self.assertIsNone(masked['rate_snapshot'])
        listed = self.store.list_service_charges(
            {'job_id': job['id']}, self.finance)
        self.assertTrue(all(c['final_amount_minor'] is None
                            for c in listed['charges']))
        # dengan view_salary: nominal terlihat
        shown = self.store.get_service_charge(charge['id'], self.hr)
        self.assertEqual(shown['final_amount_minor'],
                         charge['final_amount_minor'])
        # tanpa approve_transaction (role operator): approve -> 403
        job2 = self.job()
        r2 = self.realization(job2['id'], 10)
        self.submit(job2['id'], r2['id'])
        e = self.err(self.store.approve_job_realization, job2['id'], r2['id'],
                     self.prod_op, 'approve-' + uuid4().hex)
        self.assertEqual(e.status, 403, e.message)

    # -- 12. upgrade schema 60 -> 62 --------------------------------------

    def test_upgrade_60_to_61(self):
        """Drop tabel p03_*, set version=60, reopen Store -> version 62.

        Sejak B01 (#50) mendarat di atas P03 (#52), migrasi berjalan
        60 -> 61 (P03) -> 62 (B01, supplier invoices). Nama test
        dipertahankan agar riwayat P03 tetap terbaca.
        """
        with self.store.transaction(write=True) as db:
            for table in ('p03_service_charges', 'p03_job_realizations',
                          'p03_jobs'):
                db.execute(f'DROP TABLE IF EXISTS {table}')
            for trigger in db.execute(
                    "SELECT name FROM sqlite_schema WHERE type='trigger' "
                    "AND name LIKE 'p03_%'"):
                db.execute(f"DROP TRIGGER IF EXISTS {trigger[0]}")
            db.execute('PRAGMA user_version=60')
        store2 = Store(self.path)
        with store2.transaction() as db:
            version = db.execute('PRAGMA user_version').fetchone()[0]
            tables = {row[0] for row in db.execute(
                "SELECT name FROM sqlite_schema WHERE type='table' "
                "AND name LIKE 'p03_%'")}
        self.assertEqual(version, 62)
        self.assertIn('p03_jobs', tables)
        self.assertIn('p03_job_realizations', tables)
        self.assertIn('p03_service_charges', tables)

        # Older migration tests rewind user_version while retaining P03 data.
        # Replaying migration 61 must preserve records and their SQL guards.
        job = self.job()
        realization = self.realization(job['id'], 12)
        self.submit(job['id'], realization['id'])
        charge = self.approve(job['id'], realization['id'])
        expected_job = store2.get_employee_job(job['id'], self.admin)
        expected_charge = self.charge_row(charge['id'])
        with store2.transaction() as db:
            expected_schema = [tuple(row) for row in db.execute(
                "SELECT type,name,sql FROM sqlite_schema "
                "WHERE tbl_name IN ('p03_jobs','p03_job_realizations',"
                "'p03_service_charges') ORDER BY type,name")]
        for _ in range(2):
            with store2.transaction(write=True) as db:
                db.execute('PRAGMA user_version=60')
            store2 = Store(self.path)
            Store(self.path)  # Opening the current version is also harmless.
            self.assertEqual(store2.get_employee_job(job['id'], self.admin), expected_job)
            self.assertEqual(self.charge_row(charge['id']), expected_charge)
            self.assertEqual(self.charge_count(job['id'], realization['id']), 1)
            with store2.transaction() as db:
                self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 62)
                self.assertEqual([tuple(row) for row in db.execute(
                    "SELECT type,name,sql FROM sqlite_schema "
                    "WHERE tbl_name IN ('p03_jobs','p03_job_realizations',"
                    "'p03_service_charges') ORDER BY type,name")], expected_schema)
                self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(), [])
            for sql, row_id, message in (
                ('UPDATE p03_service_charges SET final_amount_minor=0 WHERE id=?',
                 charge['id'], 'immutable'),
                ('DELETE FROM p03_service_charges WHERE id=?',
                 charge['id'], 'tidak boleh dihapus'),
                ("UPDATE p03_job_realizations SET status='draft' WHERE id=?",
                 realization['id'], 'sudah final'),
            ):
                with self.subTest(sql=sql):
                    with self.assertRaisesRegex(sqlite3.IntegrityError, message):
                        with store2.transaction(write=True) as db:
                            db.execute(sql, (row_id,))

    # -- 13. alur lengkap --------------------------------------------------

    def test_full_flow_demo(self):
        """planning tarif -> job -> realisasi -> submit -> approve -> charge."""
        job = self.job(target=120)
        r = self.realization(job['id'], 120)
        self.assertEqual(r['status'], 'draft')
        submitted = self.submit(job['id'], r['id'])
        self.assertEqual(submitted['status'], 'submitted')
        charge = self.approve(job['id'], r['id'])
        self.assertEqual(charge['calculation_policy_ref'],
                         'DEMO-P03-20260928-1')
        # hitung manual via kontrak publik
        expected = wage_for_realization(
            pcs=120, rate_per_lusin_minor=12000,
            rate_revision='P03-JAHIT#1', policy=DEMO_POLICY)
        self.assertEqual(charge['final_amount_minor'], expected['wage_minor'])
        self.assertEqual(charge['payable_qty_pcs'], 120)
        self.assertEqual(charge['employee_id'], self.emp['id'])
        snap = json.loads(charge['rate_snapshot'])
        self.assertEqual(snap['rate_revision'], expected['rate_revision'])
        # realisasi final, job habis
        view = self.store.get_employee_job(job['id'], self.admin)
        self.assertEqual(view['realizations'][0]['status'], 'approved')
        self.assertEqual(view['remaining_qty_pcs'], 0)


if __name__ == '__main__':
    unittest.main()
