"""Regresi P3-B: tanggal yang lolos validasi tidak boleh meledak saat dihitung.

Setiap laporan menurunkan batas periodenya dari tanggal acuan dengan aritmetika `timedelta`.
Kalender `datetime.date` berhenti di 0001-01-01 dan 9999-12-31, jadi kombinasi yang masing-masing
parameternya sah masih dapat menunjuk ke luar kalender. Sebelum perbaikan, `OverflowError` dari
operasi itu lolos tanpa handler dan sampai ke klien sebagai HTTP 500:

    GET /api/production-quality-insights?as_of=0001-01-01        -> 500
    GET /api/capacity-plan?as_of=9999-12-31                      -> 500
    POST /api/ai/investigate  {"as_of": "0001-01-01"}            -> 500

Yang ditegakkan modul ini:

* Tanggal yang seluruh periodenya dapat dihitung tetap diterima, termasuk 0001-01-01 dan
  9999-12-31 sendiri. Tidak ada batas tahun buatan seperti 1900-2100.
* Kombinasi yang menunjuk ke luar kalender ditolak 422 dengan pesan yang menyebut parameternya.
* Tanggal normal menghasilkan periode yang sama seperti sebelum perbaikan.
* Permintaan yang ditolak tidak meninggalkan investigasi, receipt idempotency, atau audit.

Batas aman di sini dihitung langsung dari `date.min`/`date.max` dengan `timedelta` biasa, bukan
dengan helper yang sedang diuji, dan beberapa kasus ditulis sebagai tanggal literal.
"""

import sqlite3
from contextlib import closing
from datetime import date, timedelta
from unittest import TestCase

import test_production


# Untuk setiap endpoint: parameter lebar periode, dan berapa hari dari `as_of` ke tepi periode
# terjauh yang dihitungnya. Nilai span diturunkan dari pembacaan kode dan dibuktikan oleh
# test_safe_boundary_is_accepted_and_one_day_further_is_refused: bila span-nya salah, tanggal
# "batas aman" akan ikut ditolak dan tesnya gagal.
BACKWARD = (
    # path,                                  extra params,                     span ke belakang
    ('/api/demand-forecast',                  {'window_days': 7},              2 * 7 - 1),
    ('/api/demand-forecast',                  {'window_days': 90},             2 * 90 - 1),
    ('/api/return-insights',                  {'window_days': 7},              7 - 1),
    ('/api/return-insights',                  {'window_days': 365},            365 - 1),
    ('/api/size-demand-insights',             {'window_days': 7},              2 * 7 - 1),
    ('/api/dead-stock-insights',              {'inactivity_days': 7},          7 - 1),
    ('/api/dead-stock-insights',              {'inactivity_days': 730},        730 - 1),
    ('/api/stock-adjustment-insights',        {'window_days': 7},              7 - 1),
    ('/api/supplier-performance-insights',    {'window_days': 730},            730 - 1),
    ('/api/material-price-insights',          {'window_days': 90},             90 - 1),
    ('/api/production-quality-insights',      {'window_days': 7},              2 * 7 - 1),
    ('/api/production-quality-insights',      {'window_days': 30},             2 * 30 - 1),
    ('/api/production-quality-insights',      {'window_days': 365},            2 * 365 - 1),
)

# Sama untuk arah maju. `low` adalah as_of dekat awal kalender yang dipakai untuk membuktikan
# ujung bawah tidak mengganggu: replenishment juga menghitung ke belakang lewat demand_forecast
# (window_days bawaan 28, jadi 55 hari), sehingga 0001-01-01 memang ditolak karena alasan itu.
FORWARD = (
    # path,                                 extra params,                  span maju,  low
    ('/api/purchase-commitment-insights',   {'due_soon_days': 1},          1,          '0001-01-01'),
    ('/api/purchase-commitment-insights',   {'due_soon_days': 90},         90,         '0001-01-01'),
    ('/api/capacity-plan',                  {'horizon_days': 1},           1 - 1,      '0001-01-01'),
    ('/api/capacity-plan',                  {'horizon_days': 90},          90 - 1,     '0001-01-01'),
    ('/api/replenishment-recommendations',  {'lead_time_days': 1, 'review_period_days': 1,
                                             'safety_stock_days': 0},      1 + 1 + 0,  '0001-03-01'),
    ('/api/replenishment-recommendations',  {'lead_time_days': 180, 'review_period_days': 180,
                                             'safety_stock_days': 90},     450,        '0001-03-01'),
)


class DateBoundaryTest(TestCase):
    """Semua kasus memakai database disposable dari ProductionTest.setUp."""

    setUp = test_production.ProductionTest.setUp
    post = test_production.ProductionTest.post
    order = test_production.ProductionTest.order

    def get(self, path, **params):
        return self.client.get(path, params=params)

    def assert_out_of_range(self, response, *parameters):
        """422 dengan pesan Bahasa Indonesia yang menyebut parameter yang bersangkutan."""
        self.assertEqual(response.status_code, 422, f'{response.request.url} -> {response.text}')
        detail = response.json()['detail']
        self.assertIsInstance(detail, str, detail)
        self.assertIn('di luar kalender', detail)
        self.assertIn('0001-01-01 sampai 9999-12-31', detail)
        for name in parameters:
            self.assertIn(name, detail, detail)
        return detail

    # ------------------------------------------------------- batas kalender itu sendiri
    def test_extreme_dates_are_refused_with_422_not_500(self):
        """0001-01-01 dan 9999-12-31 tidak boleh menjadi 500.

        Laporan yang periodenya nol hari di luar `as_of` -- misalnya horizon satu hari -- memang
        masih dapat dihitung tepat di tepi kalender, jadi jawaban benarnya 200.
        """
        for path, params, span in BACKWARD:
            with self.subTest(path=path, params=params, as_of='0001-01-01'):
                response = self.get(path, as_of='0001-01-01', **params)
                if span:
                    self.assert_out_of_range(response, 'as_of')
                else:
                    self.assertEqual(response.status_code, 200, response.text)
        for path, params, span, _ in FORWARD:
            with self.subTest(path=path, params=params, as_of='9999-12-31'):
                response = self.get(path, as_of='9999-12-31', **params)
                if span:
                    self.assert_out_of_range(response, 'as_of')
                else:
                    self.assertEqual(response.status_code, 200, response.text)

    def test_extreme_dates_are_accepted_when_the_period_still_fits(self):
        """Tanggal ekstremnya sendiri sah: yang menentukan hanya periode yang dibutuhkan."""
        # Laporan yang menghitung ke belakang tidak terganggu oleh ujung atas kalender.
        for path, params, _ in BACKWARD:
            with self.subTest(path=path, params=params, as_of='9999-12-31'):
                self.assertEqual(self.get(path, as_of='9999-12-31', **params).status_code, 200)
        # Laporan yang menghitung ke depan tidak terganggu oleh ujung bawah kalender.
        for path, params, _, low in FORWARD:
            with self.subTest(path=path, params=params, as_of=low):
                self.assertEqual(self.get(path, as_of=low, **params).status_code, 200)

    def test_safe_boundary_is_accepted_and_one_day_further_is_refused(self):
        """Tanggal tepat pada batas aman lolos; satu hari di luarnya ditolak 422."""
        for path, params, span in BACKWARD:
            safe = date.min + timedelta(days=span)
            with self.subTest(path=path, params=params, safe=safe.isoformat()):
                self.assertEqual(self.get(path, as_of=safe.isoformat(), **params).status_code,
                                 200, f'{path} {params} {safe}')
                if safe == date.min:
                    continue  # tidak ada hari sebelum awal kalender untuk diuji
                beyond = safe - timedelta(days=1)
                self.assert_out_of_range(self.get(path, as_of=beyond.isoformat(), **params),
                                         'as_of')
        for path, params, span, _ in FORWARD:
            safe = date.max - timedelta(days=span)
            with self.subTest(path=path, params=params, safe=safe.isoformat()):
                self.assertEqual(self.get(path, as_of=safe.isoformat(), **params).status_code,
                                 200, f'{path} {params} {safe}')
                if safe == date.max:
                    continue  # tidak ada hari setelah akhir kalender untuk diuji
                beyond = safe + timedelta(days=1)
                self.assert_out_of_range(self.get(path, as_of=beyond.isoformat(), **params),
                                         'as_of')

    def test_literal_boundaries_for_the_reported_endpoint(self):
        """Batas yang sama ditulis sebagai tanggal literal, tanpa aritmetika di dalam tes.

        `production_quality_insights` menghitung previous_start = as_of - (2*window_days - 1).
        Dengan window_days=7 itu 13 hari, jadi 0001-01-14 adalah hari pertama yang masih dapat
        dihitung dan 0001-01-13 sudah tidak.
        """
        safe = self.get('/api/production-quality-insights', as_of='0001-01-14',
                        window_days=7, status='all')
        self.assertEqual(safe.status_code, 200, safe.text)
        self.assertEqual(safe.json()['previous_period_start'], '0001-01-01')
        self.assertEqual(safe.json()['previous_period_end'], '0001-01-07')
        self.assertEqual(safe.json()['current_period_start'], '0001-01-08')
        self.assert_out_of_range(self.get('/api/production-quality-insights', as_of='0001-01-13',
                                          window_days=7, status='all'), 'as_of', 'window_days')
        # Ujung atas kalender untuk horizon ke depan: horizon_days=1 berakhir pada as_of sendiri.
        self.assertEqual(self.get('/api/capacity-plan', as_of='9999-12-31', horizon_days=1,
                                  status='all').status_code, 200)
        self.assert_out_of_range(self.get('/api/capacity-plan', as_of='9999-12-31',
                                          horizon_days=2, status='all'),
                                 'as_of', 'horizon_days')

    def test_capacity_plan_enumerates_the_last_representable_day(self):
        """Loop hari horizon dulu menambah satu hari melewati horizon untuk berhenti."""
        center = self.post('/api/work-centers', {'code': 'CUT-BOUND', 'name': 'Cutting batas',
            'stage': 'cutting', 'daily_minutes': 480, 'reason': 'Uji batas kalender'})
        self.assertTrue(center['id'])
        plan = self.get('/api/capacity-plan', as_of='9999-12-31', horizon_days=1, status='all')
        self.assertEqual(plan.status_code, 200, plan.text)
        days = plan.json()['items'][0]['days']
        self.assertEqual([row['date'] for row in days], ['9999-12-31'])
        # Horizon dua hari dari hari terakhir memang tidak terwakili kalender.
        self.assert_out_of_range(self.get('/api/capacity-plan', as_of='9999-12-31',
                                          horizon_days=2, status='all'),
                                 'as_of', 'horizon_days')
        # Horizon yang berakhir tepat di 9999-12-31 tetap menghasilkan seluruh harinya.
        three = self.get('/api/capacity-plan', as_of='9999-12-29', horizon_days=3, status='all')
        self.assertEqual(three.status_code, 200, three.text)
        self.assertEqual([row['date'] for row in three.json()['items'][0]['days']],
                         ['9999-12-29', '9999-12-30', '9999-12-31'])

    def test_error_message_names_the_parameters_involved(self):
        detail = self.assert_out_of_range(
            self.get('/api/dead-stock-insights', as_of='0001-01-01', inactivity_days=30),
            'as_of', 'inactivity_days')
        self.assertNotIn('window_days', detail)
        self.assert_out_of_range(
            self.get('/api/purchase-commitment-insights', as_of='9999-12-31', due_soon_days=30),
            'as_of', 'due_soon_days')
        self.assert_out_of_range(
            self.get('/api/replenishment-recommendations', as_of='9999-12-31'),
            'as_of', 'lead_time_days', 'review_period_days', 'safety_stock_days')

    # ------------------------------------------------------- batas parameter yang diizinkan
    def test_minimum_and_maximum_allowed_windows_work_on_a_normal_date(self):
        for path, params, _ in BACKWARD:
            with self.subTest(path=path, params=params):
                self.assertEqual(self.get(path, as_of='2026-09-23', **params).status_code, 200)
        for path, params, _, _low in FORWARD:
            with self.subTest(path=path, params=params):
                self.assertEqual(self.get(path, as_of='2026-09-23', **params).status_code, 200)

    def test_windows_outside_the_allowed_range_are_still_refused(self):
        """Batas ge/le existing tidak dilonggarkan oleh perbaikan ini."""
        for path, params in (('/api/production-quality-insights', {'window_days': 6}),
                             ('/api/production-quality-insights', {'window_days': 366}),
                             ('/api/return-insights', {'window_days': 366}),
                             ('/api/dead-stock-insights', {'inactivity_days': 731}),
                             ('/api/capacity-plan', {'horizon_days': 0}),
                             ('/api/capacity-plan', {'horizon_days': 91}),
                             ('/api/purchase-commitment-insights', {'due_soon_days': 0}),
                             ('/api/demand-forecast', {'window_days': 91})):
            with self.subTest(path=path, params=params):
                self.assertEqual(self.get(path, as_of='2026-09-23', **params).status_code, 422)

    # ------------------------------------------------------- kalender dan rentang
    def test_dates_that_do_not_exist_on_the_calendar_are_refused(self):
        for value in ('2026-02-30', '2025-02-29', '2026-13-01', '2026-00-10', '2026-09-31',
                      '10000-01-01', '0000-12-31', 'kemarin', '2026-9-23'):
            with self.subTest(as_of=value):
                self.assertEqual(self.get('/api/production-quality-insights',
                                          as_of=value).status_code, 422)

    def test_leap_day_and_month_and_year_rollovers_are_computed_correctly(self):
        """Periode melewati 29 Februari serta pergantian bulan dan tahun."""
        leap = self.get('/api/production-quality-insights', as_of='2024-03-01',
                        window_days=7, status='all')
        self.assertEqual(leap.status_code, 200, leap.text)
        # 2024 kabisat: 7 hari sampai 2024-03-01 mulai 2024-02-24, periode sebelumnya berakhir
        # 2024-02-23 dan mulai 2024-02-17.
        self.assertEqual(leap.json()['current_period_start'], '2024-02-24')
        self.assertEqual((leap.json()['previous_period_end'],
                          leap.json()['previous_period_start']), ('2024-02-23', '2024-02-17'))
        non_leap = self.get('/api/production-quality-insights', as_of='2025-03-01',
                            window_days=7, status='all')
        self.assertEqual(non_leap.json()['current_period_start'], '2025-02-23')
        year = self.get('/api/production-quality-insights', as_of='2026-01-01',
                        window_days=30, status='all')
        self.assertEqual(year.status_code, 200, year.text)
        self.assertEqual(year.json()['current_period_start'], '2025-12-03')
        self.assertEqual((year.json()['previous_period_end'],
                          year.json()['previous_period_start']), ('2025-12-02', '2025-11-03'))

    def test_single_day_ranges_are_accepted_across_the_date_range_endpoints(self):
        center = self.post('/api/work-centers', {'code': 'CUT-RANGE', 'name': 'Cutting rentang',
            'stage': 'cutting', 'daily_minutes': 480, 'reason': 'Uji rentang satu hari'})
        for path, params in (
                ('/api/audit-events', {'start_date': '2026-09-23', 'end_date': '2026-09-23'}),
                ('/api/activity', {'start_date': '2026-09-23', 'end_date': '2026-09-23'}),
                ('/api/activity', {'day': '2026-09-23'}),
                ('/api/workforce/attendance', {'start_date': '2026-09-23',
                                               'end_date': '2026-09-23'}),
                (f"/api/work-centers/{center['id']}/calendar",
                 {'start_date': '2026-09-23', 'end_date': '2026-09-23'})):
            with self.subTest(path=path, params=params):
                self.assertEqual(self.get(path, **params).status_code, 200)

    def test_start_date_after_end_date_is_refused_on_every_range_endpoint(self):
        center = self.post('/api/work-centers', {'code': 'CUT-ORDER', 'name': 'Cutting urutan',
            'stage': 'cutting', 'daily_minutes': 480, 'reason': 'Uji urutan rentang'})
        for path in ('/api/audit-events', '/api/activity', '/api/workforce/attendance',
                     f"/api/work-centers/{center['id']}/calendar", '/api/activity.csv'):
            with self.subTest(path=path):
                response = self.get(path, start_date='2026-09-24', end_date='2026-09-23')
                self.assertEqual(response.status_code, 422, f'{path} -> {response.text}')
                self.assertIsInstance(response.json()['detail'], str)

    def test_timezone_conversion_at_the_calendar_edge_answers_422_not_500(self):
        """Rentang audit dan aktivitas diubah ke UTC dari tengah malam Jakarta.

        Tengah malam 0001-01-01 di Jakarta jatuh sebelum awal kalender dalam UTC, jadi jalur ini
        memang terdampak konversi zona waktu dan harus menjawab 422.
        """
        for path in ('/api/audit-events', '/api/activity', '/api/activity.csv'):
            with self.subTest(path=path):
                edge = self.get(path, start_date='0001-01-01', end_date='0001-01-01')
                self.assertEqual(edge.status_code, 422, f'{path} -> {edge.text}')
                self.assertIsInstance(edge.json()['detail'], str)
        self.assertEqual(self.get('/api/activity', day='0001-01-01').status_code, 422)
        # Aktivitas mengubah rentangnya menjadi durasi setelah dikonversi, jadi ujung atas masih
        # terwakili. Audit menambahkan satu hari pada tengah malam Jakarta lebih dulu, sehingga
        # 9999-12-31 melewati kalender dan dijawab 422 -- bukan 500 -- oleh penjaga yang sudah ada.
        self.assertEqual(self.get('/api/activity', day='9999-12-31').status_code, 200)
        self.assertEqual(self.get('/api/audit-events', start_date='9999-12-29',
                                  end_date='9999-12-30').status_code, 200)
        upper = self.get('/api/audit-events', start_date='9999-12-31', end_date='9999-12-31')
        self.assertEqual(upper.status_code, 422)
        self.assertEqual(upper.json()['detail'], 'Tanggal audit di luar jangkauan.')
        # Kehadiran tidak melakukan konversi zona waktu, jadi kedua ujung kalender tetap dilayani.
        for value in ('0001-01-01', '9999-12-31'):
            self.assertEqual(self.get('/api/workforce/attendance', start_date=value,
                                      end_date=value).status_code, 200)

    def test_operational_jakarta_default_is_unchanged(self):
        """Tanpa as_of, laporan tetap memakai hari operasional Jakarta."""
        from beeloft.api import jakarta_today
        report = self.get('/api/demand-forecast')
        self.assertEqual(report.status_code, 200, report.text)
        self.assertEqual(report.json()['as_of'], jakarta_today().isoformat())

    # ------------------------------------------------------- tanggal normal tidak berubah
    def test_normal_dates_return_the_same_periods_as_before_the_fix(self):
        """Nilai yang di-pin di sini dihitung dengan tangan, bukan oleh kode yang diuji."""
        quality = self.get('/api/production-quality-insights', as_of='2026-09-23',
                           window_days=7, warning_percent=20, change_threshold=5, status='all')
        self.assertEqual(quality.status_code, 200, quality.text)
        body = quality.json()
        self.assertEqual((body['current_period_start'], body['previous_period_start'],
                          body['previous_period_end']),
                         ('2026-09-17', '2026-09-10', '2026-09-16'))
        forecast = self.get('/api/demand-forecast', as_of='2026-09-23', window_days=28,
                            horizon_days=30)
        self.assertEqual(forecast.status_code, 200, forecast.text)
        # 28 hari sampai 2026-09-23 mulai 2026-08-27; periode sebelumnya 2026-07-30..2026-08-26.
        self.assertEqual((forecast.json()['recent_period_start'],
                          forecast.json()['previous_period_end'],
                          forecast.json()['history_start']),
                         ('2026-08-27', '2026-08-26', '2026-07-30'))
        self.assertEqual((forecast.json()['window_days'], forecast.json()['horizon_days']),
                         (28, 30))
        commitments = self.get('/api/purchase-commitment-insights', as_of='2026-09-23',
                               due_soon_days=7)
        self.assertEqual(commitments.status_code, 200, commitments.text)
        plan = self.get('/api/capacity-plan', as_of='2026-09-23', horizon_days=14, status='all')
        self.assertEqual(plan.status_code, 200, plan.text)
        self.assertEqual(plan.json()['horizon_end'], '2026-10-06')

    def test_reports_are_read_only_even_when_the_date_is_refused(self):
        """Permintaan yang ditolak tidak boleh mengubah database sama sekali."""
        store = self.app.state.store
        with closing(sqlite3.connect(self.path)) as db:
            before = list(db.iterdump())
        for path, params in (('/api/production-quality-insights', {'as_of': '0001-01-01'}),
                             ('/api/capacity-plan', {'as_of': '9999-12-31'}),
                             ('/api/replenishment-recommendations', {'as_of': '0001-01-01'})):
            self.assertEqual(self.get(path, **params).status_code, 422)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(list(db.iterdump()), before)
        self.assertEqual(store.approvals_summary()['total'], 0)


class InvestigationDateBoundaryTest(TestCase):
    """Jalur internal: investigasi AI memakai fungsi laporan yang sama."""

    setUp = test_production.ProductionTest.setUp
    post = test_production.ProductionTest.post

    def question(self, **changes):
        return dict(question='Kenapa stok bisa kosong?', as_of='2026-11-15', window_days=14,
                    lead_time_days=180, review_period_days=180, safety_stock_days=90,
                    batch_multiple=12) | changes

    def counts(self):
        with closing(sqlite3.connect(self.path)) as db:
            return {name: db.execute('SELECT COUNT(*) FROM ' + name).fetchone()[0]
                    for name in ('ai_investigations', 'requests', 'audit_events')}

    def test_read_only_investigation_answers_422_instead_of_500(self):
        for as_of in ('0001-01-01', '9999-12-31'):
            with self.subTest(as_of=as_of):
                response = self.client.post('/api/ai/investigate',
                                            json=self.question(as_of=as_of))
                self.assertEqual(response.status_code, 422, response.text)
                self.assertIn('di luar kalender', response.json()['detail'])

    def test_every_intent_that_reaches_the_report_functions_is_covered(self):
        for question in ('Kenapa stok bisa kosong?', 'Apa yang harus saya lihat sekarang?',
                         'Bagaimana margin kontribusi kita?', 'Bagaimana produksi hari ini?'):
            with self.subTest(question=question):
                response = self.client.post('/api/ai/investigate',
                    json=self.question(question=question, as_of='0001-01-01'))
                self.assertIn(response.status_code, (200, 422), response.text)
                if response.status_code == 422:
                    self.assertIn('di luar kalender', response.json()['detail'])

    def test_a_refused_investigation_leaves_no_record_receipt_or_audit(self):
        before = self.counts()
        response = self.client.post('/api/ai/investigations',
                                    json=self.question(as_of='0001-01-01'),
                                    headers={'Idempotency-Key': 'p3b-refused'})
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.counts(), before)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM requests WHERE key='p3b-refused'")
                             .fetchone()[0], 0)
        self.assertEqual(self.client.get('/api/ai/investigations').json(), [])

    def test_the_same_idempotency_key_is_still_usable_after_a_refusal(self):
        """Penolakan tidak menghanguskan kunci: tidak ada receipt yang tertinggal."""
        refused = self.client.post('/api/ai/investigations',
                                   json=self.question(as_of='0001-01-01'),
                                   headers={'Idempotency-Key': 'p3b-reuse'})
        self.assertEqual(refused.status_code, 422, refused.text)
        saved = self.post('/api/ai/investigations', self.question(), key='p3b-reuse')
        self.assertTrue(saved['id'])
        replay = self.post('/api/ai/investigations', self.question(), key='p3b-reuse')
        self.assertEqual(replay, saved)
        self.assertEqual(len(self.client.get('/api/ai/investigations').json()), 1)

    def test_a_saved_investigation_on_a_normal_date_still_works(self):
        saved = self.post('/api/ai/investigations', self.question(), key='p3b-normal')
        self.assertEqual(saved['as_of'], '2026-11-15')
        stored = self.client.get('/api/ai/investigations/' + saved['id'])
        self.assertEqual(stored.status_code, 200, stored.text)
        self.assertEqual(stored.json()['answer'], saved['answer'])

    def test_action_proposals_refuse_the_same_combinations(self):
        """Proposal tindakan mewarisi as_of yang sama dan menjalankan ulang investigasinya."""
        before = self.counts()
        response = self.client.post('/api/ai/action-proposals',
            json=self.question(as_of='0001-01-01') | {'action_kind': 'create_production_order',
                'subject_id': self.product['id'], 'quantity': 12,
                'required_date': '2026-12-01', 'reason': 'Menambah stok'},
            headers={'Idempotency-Key': 'p3b-proposal'})
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.counts(), before)


class StockProjectionBoundaryTest(TestCase):
    """Proyeksi dari data, bukan dari parameter: jawabannya None, bukan 422.

    `projected_stockout_date` dihitung dari stok dibagi laju permintaan. Stok besar dengan laju
    sangat kecil memproyeksikan ribuan tahun ke depan dan dulu meledak dengan OverflowError.
    Permintaannya sah, jadi jawaban yang benar adalah "tidak ada tanggal habis stok yang
    terwakili" -- nilai None yang sama seperti produk tanpa laju permintaan.
    """

    setUp = test_production.ProductionTest.setUp
    post = test_production.ProductionTest.post
    order = test_production.ProductionTest.order

    def test_replenishment_answers_200_with_a_null_projection_at_the_calendar_edge(self):
        response = self.client.get('/api/replenishment-recommendations',
                                   params={'as_of': '9999-12-01', 'lead_time_days': 1,
                                           'review_period_days': 1, 'safety_stock_days': 0})
        self.assertEqual(response.status_code, 200, response.text)
        for row in response.json()['product_recommendations']:
            if row['projected_stockout_date'] is not None:
                self.assertLessEqual(row['projected_stockout_date'], '9999-12-31')

    def test_size_demand_answers_200_at_the_calendar_edge(self):
        response = self.client.get('/api/size-demand-insights',
                                   params={'as_of': '9999-12-01', 'window_days': 7,
                                           'lookahead_days': 1})
        self.assertEqual(response.status_code, 200, response.text)

    def test_the_projection_helper_reports_none_beyond_the_calendar(self):
        """Unit langsung atas helper, dengan nilai harapan yang ditulis tangan."""
        from beeloft.store import projected_date
        self.assertEqual(projected_date(date(2026, 1, 1), 5), '2026-01-06')
        self.assertEqual(projected_date(date(2026, 1, 1), 0), '2026-01-01')
        self.assertEqual(projected_date(date(9999, 12, 30), 1), '9999-12-31')
        self.assertIsNone(projected_date(date(9999, 12, 31), 1))
        self.assertIsNone(projected_date(date(2026, 1, 1), 10**9))
        self.assertIsNone(projected_date(date(2026, 1, 1), 10**30))


class ShiftDateHelperTest(TestCase):
    """Unit atas helper batas tanggal, dengan nilai harapan independen."""

    def test_normal_shifts_match_hand_written_dates(self):
        from beeloft.store import shift_date
        self.assertEqual(shift_date(date(2026, 9, 23), -6, 'as_of dan window_days'),
                         date(2026, 9, 17))
        self.assertEqual(shift_date(date(2026, 9, 23), 7, 'as_of dan due_soon_days'),
                         date(2026, 9, 30))
        self.assertEqual(shift_date(date(2024, 3, 1), -1, 'as_of'), date(2024, 2, 29))
        self.assertEqual(shift_date(date(2025, 3, 1), -1, 'as_of'), date(2025, 2, 28))
        self.assertEqual(shift_date(date(2026, 1, 1), -1, 'as_of'), date(2025, 12, 31))
        self.assertEqual(shift_date(date(1, 1, 1), 0, 'as_of'), date(1, 1, 1))
        self.assertEqual(shift_date(date(9999, 12, 31), 0, 'as_of'), date(9999, 12, 31))

    def test_shifts_outside_the_calendar_raise_a_422_domain_error(self):
        from beeloft.store import DomainError, shift_date
        for anchor, days in ((date(1, 1, 1), -1), (date(9999, 12, 31), 1),
                             (date(1, 1, 1), -10**9), (date(2026, 1, 1), 10**30)):
            with self.subTest(anchor=anchor.isoformat(), days=days):
                with self.assertRaises(DomainError) as caught:
                    shift_date(anchor, days, 'as_of dan window_days')
                self.assertEqual(caught.exception.status, 422)
                self.assertIn('as_of dan window_days', caught.exception.message)
                self.assertIn('0001-01-01 sampai 9999-12-31', caught.exception.message)

    def test_the_helper_does_not_swallow_unrelated_errors(self):
        """Hanya OverflowError yang ditangani; bug lain tetap muncul sebagai bug."""
        from beeloft.store import shift_date
        with self.assertRaises(TypeError):
            shift_date(date(2026, 1, 1), 'tujuh', 'as_of')
        with self.assertRaises(TypeError):
            shift_date('2026-01-01', 7, 'as_of')
        with self.assertRaises(ZeroDivisionError):
            shift_date(date(2026, 1, 1), 1 // 0, 'as_of')
