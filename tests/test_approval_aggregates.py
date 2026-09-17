"""Regresi P2-B: total approval tidak boleh bergantung pada halaman daftar.

Command Center dan AI Brain sebelumnya membaca `store.approvals(limit=500, ...)` lalu
menghitung `len()` dan `sum()` dari hasil terbatas itu. Begitu populasi pending melewati
500 item, jumlah dan nominalnya berhenti bertambah tanpa peringatan apa pun.

Fixture di sini menulis langsung ke tabel approval yang sebenarnya. Semua CHECK dan
trigger lifecycle tetap berjalan; hanya lapisan HTTP dan idempotency yang dilewati supaya
populasi di atas 1.000 baris tetap murah untuk dibangun. Nilai yang diharapkan selalu
berasal dari catatan fixture (oracle independen), bukan dari fungsi agregat yang diuji.
"""

from datetime import date, timedelta
from decimal import Decimal
from unittest import TestCase

from beeloft.store import APPROVAL_AGGREGATES, APPROVAL_KINDS
import test_materials
import test_po_receipts
import test_production
import test_purchase_orders
import test_purchase_requests


REASON = 'Kebutuhan anggaran kuartal empat'
PENDING = 'submitted'


def stamp(index):
    """Timestamp unik dan berurutan agar pengurutan daftar deterministik."""
    return '2026-01-01T%02d:%02d:%02d+00:00' % (index // 3600, index // 60 % 60, index % 60)


class ApprovalFixture(TestCase):
    setUp = test_production.ProductionTest.setUp
    post = test_production.ProductionTest.post
    order = test_production.ProductionTest.order

    def setUp(self):  # noqa: F811 - dibungkus supaya oracle ikut disiapkan
        test_production.ProductionTest.setUp(self)
        self.expected = []
        self.counter = 0

    # ------------------------------------------------------------------ oracle
    def record(self, kind, amount_minor, status=PENDING, amount=None):
        """Catat satu pengajuan pada oracle fixture.

        `amount` dipakai bila nominalnya bukan berasal dari kolom *_minor.
        """
        if amount is None and amount_minor is not None:
            amount = Decimal(amount_minor) / 100
        self.expected.append({'kind': kind, 'status': status,
                              'amount': None if amount is None else Decimal(amount)})

    def oracle(self, status='pending', kind='all'):
        """Oracle fixture. `status` memakai kosakata inbox, jadi 'pending' == event 'submitted'."""
        wanted = PENDING if status == 'pending' else status
        rows = [row for row in self.expected
                if (status == 'all' or row['status'] == wanted)
                and (kind == 'all' or row['kind'] == kind)]
        amount = sum((row['amount'] for row in rows if row['amount'] is not None), Decimal(0))
        return {'total': len(rows), 'amount': format(amount, '.2f'),
                'without_amount': sum(row['amount'] is None for row in rows)}

    def next_index(self):
        self.counter += 1
        return self.counter

    # ----------------------------------------------------------------- seeding
    def close_event(self, db, table, column, identifier, status, index):
        db.execute(f'''INSERT INTO {table}({column},status,reason,actor_id,created_at)
            VALUES(?,?,?,?,?)''', (identifier, status, 'Keputusan manajemen',
                                   self.admin['id'], stamp(index)))

    def seed_marketing(self, count, amount_minor=250_000_00, status=PENDING, prefix='MKT'):
        """Marketing budget: satu-satunya kind yang paling murah untuk dibuat massal."""
        with self.app.state.store.transaction(write=True) as db:
            for offset in range(count):
                index = self.next_index()
                identifier = f'{prefix}-{index:06d}'
                value = amount_minor(offset) if callable(amount_minor) else amount_minor
                db.execute('''INSERT INTO marketing_budget_requests(id,reference,campaign_name,
                    channel,start_date,end_date,amount_minor,objective,reason,actor_id,created_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
                    (identifier, identifier, 'Kampanye ' + identifier, 'Meta Ads',
                     '2026-10-01', '2026-10-31', value, 'Menambah pesanan koleksi baru',
                     REASON, self.operator['id'], stamp(index)))
                db.execute('''INSERT INTO marketing_budget_request_events(request_id,status,reason,
                    actor_id,created_at) VALUES(?,?,?,?,?)''',
                    (identifier, PENDING, REASON, self.operator['id'], stamp(index)))
                if status != PENDING:
                    self.close_event(db, 'marketing_budget_request_events', 'request_id',
                                     identifier, status, index)
                self.record('marketing_budget', value, status)

    def material_id(self):
        with self.app.state.store.transaction(write=True) as db:
            row = db.execute('SELECT id FROM materials LIMIT 1').fetchone()
            if row:
                return row['id']
            db.execute('''INSERT INTO materials(id,code,name,unit,created_by,created_at)
                VALUES('MAT-AGG','AGG-CLOTH','Kain agregat','m',?,?)''',
                (self.admin['id'], stamp(0)))
        return 'MAT-AGG'

    def seed_purchase_requests(self, count, amount_minor=100_000_00, status=PENDING):
        material = {'id': self.material_id()}
        with self.app.state.store.transaction(write=True) as db:
            for _ in range(count):
                index = self.next_index()
                identifier = f'PR-BULK-{index:06d}'
                value = amount_minor(index) if callable(amount_minor) else amount_minor
                lines = '[{"material_id": "%s", "quantity": "1.000"}]' % material['id']
                db.execute('''INSERT INTO purchase_requests(id,reference,order_id,required_date,
                    estimated_value_minor,lines,reason,actor_id,created_at)
                    VALUES(?,?,NULL,?,?,?,?,?,?)''',
                    (identifier, identifier, '2026-12-01', value, lines, REASON,
                     self.operator['id'], stamp(index)))
                db.execute('''INSERT INTO purchase_request_events(request_id,status,reason,
                    actor_id,created_at) VALUES(?,?,?,?,?)''',
                    (identifier, PENDING, REASON, self.operator['id'], stamp(index)))
                if status != PENDING:
                    self.close_event(db, 'purchase_request_events', 'request_id',
                                     identifier, status, index)
                self.record('purchase_request', value, status)

    def seed_workforce(self, count, kind='leave', status=PENDING):
        """Cuti dan lembur masuk inbox tanpa nominal: dihitung, tetapi tidak menambah amount."""
        prefix = 'CUTI' if kind == 'leave' else 'LBR'
        with self.app.state.store.transaction(write=True) as db:
            for _ in range(count):
                index = self.next_index()
                employee = f'EMP-{index:06d}'
                db.execute('''INSERT INTO workforce_employees(id,code,created_by,created_at)
                    VALUES(?,?,?,?)''', (employee, employee.upper(), self.admin['id'], stamp(index)))
                db.execute('''INSERT INTO workforce_employee_events(id,employee_id,revision,name,
                    department,active,reason,actor_id,created_at) VALUES(?,?,1,?,?,1,?,?,?)''',
                    (employee + '-EV', employee, 'Karyawan ' + employee, 'Produksi',
                     'Data awal approval People', self.admin['id'], stamp(index)))
                identifier = f'{prefix}-{index:06d}'
                day = '2026-11-%02d' % (index % 28 + 1)
                db.execute('''INSERT INTO workforce_requests(id,reference,employee_id,kind,
                    start_date,end_date,overtime_minutes,reason,actor_id,created_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?)''',
                    (identifier, identifier, employee, kind, day, day,
                     0 if kind == 'leave' else 90, REASON, self.operator['id'], stamp(index)))
                db.execute('''INSERT INTO workforce_request_events(request_id,status,reason,
                    actor_id,created_at) VALUES(?,?,?,?,?)''',
                    (identifier, PENDING, REASON, self.operator['id'], stamp(index)))
                if status != PENDING:
                    self.close_event(db, 'workforce_request_events', 'request_id',
                                     identifier, status, index)
                self.record('workforce_' + kind, None, status)

    def seed_ai_action(self, count, estimated_value='500000.00', status=PENDING):
        """Proposal AI menyimpan nominal di dalam JSON action_payload, bukan kolom *_minor."""
        action = 'create_purchase_request' if estimated_value else 'create_production_order'
        with self.app.state.store.transaction(write=True) as db:
            for _ in range(count):
                index = self.next_index()
                identifier = f'AI-{index:06d}'
                payload = ('{"estimated_value": "%s"}' % estimated_value
                           if estimated_value else '{"quantity": 12}')
                db.execute('''INSERT INTO ai_action_proposals(id,action_kind,subject_id,reference,
                    source_payload,recommendation,recommendation_fingerprint,action_payload,reason,
                    actor_id,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
                    (identifier, action, self.product['id'], identifier, '{"question": "cek"}',
                     '{"title": "Rekomendasi ' + identifier + '"}', 'fingerprint-' + identifier,
                     payload, REASON, self.operator['id'], stamp(index)))
                db.execute('''INSERT INTO ai_action_proposal_events(proposal_id,status,reason,
                    actor_id,created_at) VALUES(?,?,?,?,?)''',
                    (identifier, PENDING, REASON, self.operator['id'], stamp(index)))
                if status != PENDING:
                    db.execute('''INSERT INTO ai_action_proposal_events(proposal_id,status,reason,
                        actor_id,executed_entity_type,executed_entity_id,created_at)
                        VALUES(?,?,?,?,NULL,NULL,?)''',
                        (identifier, status, 'Keputusan manajemen', self.admin['id'], stamp(index)))
                self.record('ai_action', None,
                            status, Decimal(estimated_value) if estimated_value else None)

    def seed_payroll(self, count, gross_minor=0, employer_minor=0, status=PENDING):
        """Payroll batch: nominalnya turunan gross + kontribusi pemberi kerja, boleh nol."""
        with self.app.state.store.transaction(write=True) as db:
            batch = 'PAYBATCH-' + str(self.next_index())
            db.execute('''INSERT INTO integration_sync_runs(id,system,scope,status,started_at,
                finished_at,records_read,records_written,external_cursor,error,reason,actor_id,
                created_at) VALUES(?,'mekari','payroll','succeeded',?,?,?,?,?,'',?,?,?)''',
                (batch + '-RUN', stamp(1), stamp(2), count, count, 'cursor-' + batch,
                 'Snapshot payroll untuk approval', self.admin['id'], stamp(2)))
            db.execute('''INSERT INTO mekari_payroll_snapshot_batches(id,sync_run_id,snapshot_at,
                actor_id,created_at) VALUES(?,?,?,?,?)''',
                (batch, batch + '-RUN', stamp(2), self.admin['id'], stamp(2)))
            for _ in range(count):
                index = self.next_index()
                period = f'PAYPER-{index:06d}'
                # UNIQUE(batch_id,period_start,period_end): setiap periode perlu rentang sendiri.
                day = (date(2020, 1, 1) + timedelta(days=index)).isoformat()
                db.execute('''INSERT INTO mekari_payroll_snapshot_periods(id,batch_id,
                    external_payroll_id,period_start,period_end,status,currency,employee_count,
                    gross_pay_minor,employee_deductions_minor,employer_contributions_minor,
                    payment_date,updated_at) VALUES(?,?,?,?,?,'reviewing','IDR',?,?,0,?,NULL,?)''',
                    (period, batch, 'ext-' + period, day, day, 10,
                     gross_minor, employer_minor, stamp(index)))
                identifier = f'PAY-{index:06d}'
                db.execute('''INSERT INTO payroll_approval_requests(id,reference,source_period_id,
                    reason,actor_id,created_at) VALUES(?,?,?,?,?,?)''',
                    (identifier, identifier, period, REASON, self.operator['id'], stamp(index)))
                db.execute('''INSERT INTO payroll_approval_request_events(request_id,status,reason,
                    actor_id,created_at) VALUES(?,?,?,?,?)''',
                    (identifier, PENDING, REASON, self.operator['id'], stamp(index)))
                if status != PENDING:
                    self.close_event(db, 'payroll_approval_request_events', 'request_id',
                                     identifier, status, index)
                self.record('payroll_batch', gross_minor + employer_minor, status)

    # -------------------------------------------------------------- assertions
    def assert_summary_matches_oracle(self, status='pending', kind='all'):
        summary = self.app.state.store.approvals_summary(status=status, kind=kind)
        expected = self.oracle(status, kind)
        self.assertEqual((summary['total'], summary['amount'], summary['without_amount']),
                         (expected['total'], expected['amount'], expected['without_amount']))
        return summary

    def assert_list_agrees_with_summary(self, status='pending', kind='all'):
        """Silang-uji terhadap jalur hidrasi lama dengan limit yang cukup besar.

        Ini oracle kedua yang independen: implementasinya Python murni per baris,
        bukan agregasi SQL yang sedang diuji.
        """
        rows = self.app.state.store.approvals(1_000_000, 0, status, kind)
        amount = sum((Decimal(row['amount']) for row in rows
                      if row['amount'] is not None), Decimal(0))
        summary = self.app.state.store.approvals_summary(status=status, kind=kind)
        self.assertEqual((len(rows), format(amount, '.2f')),
                         (summary['total'], summary['amount']))


class ApprovalSummaryPopulationTest(ApprovalFixture):
    def test_boundaries_around_the_old_five_hundred_row_page(self):
        """0, 1, 499, 500, 501, dan >1.000 pending harus dilaporkan apa adanya."""
        store = self.app.state.store
        self.assertEqual(store.approvals_summary()['total'], 0)
        self.assertEqual(store.approvals_summary()['amount'], '0.00')
        for target in (1, 499, 500, 501, 1_050):
            self.seed_marketing(target - len(self.expected))
            self.assertEqual(len(self.expected), target)
            summary = self.assert_summary_matches_oracle()
            self.assertEqual(summary['total'], target)
        self.assertEqual(self.app.state.store.approvals_summary()['total'], 1_050)

    def test_single_kind_beyond_the_page_limit(self):
        self.seed_marketing(640, amount_minor=lambda offset: 1_00 + offset)
        summary = self.assert_summary_matches_oracle()
        self.assertEqual(summary['total'], 640)
        self.assertEqual(summary['by_kind']['marketing_budget']['count'], 640)
        self.assert_list_agrees_with_summary()

    def test_mixed_kinds_beyond_the_page_limit(self):
        self.seed_marketing(300, amount_minor=1_500_00)
        self.seed_purchase_requests(260, amount_minor=2_000_00)
        self.seed_workforce(120, kind='leave')
        self.seed_workforce(90, kind='overtime')
        self.seed_ai_action(40, estimated_value='1000.25')
        summary = self.assert_summary_matches_oracle()
        self.assertEqual(summary['total'], 810)
        self.assertEqual({kind: row['count'] for kind, row in summary['by_kind'].items()
                          if row['count']},
                         {'marketing_budget': 300, 'purchase_request': 260,
                          'workforce_leave': 120, 'workforce_overtime': 90, 'ai_action': 40})
        self.assertEqual(summary['without_amount'], 210)
        self.assert_list_agrees_with_summary()

    def test_amounts_that_are_null_zero_or_decimal(self):
        self.seed_workforce(3, kind='leave')                      # tanpa nominal
        self.seed_ai_action(2, estimated_value=None)              # tanpa nominal
        self.seed_payroll(2, gross_minor=0, employer_minor=0)     # nominal nol
        self.seed_marketing(2, amount_minor=1_00)                 # 1.00
        self.seed_marketing(1, amount_minor=1)                    # 0.01
        self.seed_ai_action(1, estimated_value='0.33')
        summary = self.assert_summary_matches_oracle()
        self.assertEqual(summary['total'], 11)
        self.assertEqual(summary['without_amount'], 5)
        self.assertEqual(summary['amount'], '2.34')
        self.assert_list_agrees_with_summary()

    def test_decided_requests_leave_the_pending_population(self):
        self.seed_marketing(520, amount_minor=1_000_00)
        self.seed_marketing(30, amount_minor=1_000_00, status='approved', prefix='MKT-APR')
        self.seed_marketing(20, amount_minor=1_000_00, status='rejected', prefix='MKT-REJ')
        self.seed_marketing(10, amount_minor=1_000_00, status='cancelled', prefix='MKT-CAN')
        summary = self.assert_summary_matches_oracle()
        self.assertEqual((summary['total'], summary['amount']), (520, '520000.00'))
        for status in ('approved', 'rejected', 'cancelled', 'all'):
            self.assert_summary_matches_oracle(status=status)
        self.assertEqual(self.app.state.store.approvals_summary(status='all')['total'], 580)

    def test_multiple_lifecycle_events_never_double_count_one_request(self):
        """Status bersumber dari event; agregat harus memakai event terakhir saja."""
        self.seed_marketing(3, amount_minor=1_000_00)
        pending = self.app.state.store.approvals_summary()
        self.assertEqual(pending['total'], 3)
        with self.app.state.store.transaction(write=True) as db:
            identifier = db.execute('''SELECT request_id FROM marketing_budget_request_events
                ORDER BY sequence LIMIT 1''').fetchone()['request_id']
            self.close_event(db, 'marketing_budget_request_events', 'request_id',
                             identifier, 'approved', 9_000)
            self.assertEqual(db.execute('''SELECT COUNT(*) FROM marketing_budget_request_events
                WHERE request_id=?''', (identifier,)).fetchone()[0], 2)
        after = self.app.state.store.approvals_summary()
        self.assertEqual((after['total'], after['amount']), (2, '2000.00'))
        self.assertEqual(self.app.state.store.approvals_summary(status='approved')['total'], 1)
        self.assertEqual(self.app.state.store.approvals_summary(status='all')['total'], 3)

    def test_list_pagination_never_changes_the_global_totals(self):
        self.seed_marketing(610, amount_minor=1_000_00)
        baseline = self.app.state.store.approvals_summary()
        for limit, offset in ((1, 0), (25, 100), (100, 500), (500, 0), (500, 500)):
            page = self.client.get(f'/api/approvals?limit={limit}&offset={offset}').json()
            self.assertLessEqual(len(page), limit)
            self.assertEqual(self.app.state.store.approvals_summary(), baseline)
        self.assertEqual((baseline['total'], baseline['amount']), (610, '610000.00'))

    def test_kind_filter_on_the_summary_matches_the_same_filter_on_the_list(self):
        self.seed_marketing(510, amount_minor=1_000_00)
        self.seed_purchase_requests(15, amount_minor=3_000_00)
        self.seed_workforce(5, kind='leave')
        for kind in ('all', 'marketing_budget', 'purchase_request', 'workforce_leave',
                     'purchase_order', 'supplier_payment', 'production_change',
                     'workforce_overtime', 'payroll_batch', 'ai_action'):
            self.assert_summary_matches_oracle(kind=kind)
            self.assert_list_agrees_with_summary(kind=kind)

    def test_summary_reports_every_kind_the_inbox_supports(self):
        summary = self.app.state.store.approvals_summary()
        self.assertEqual(set(summary['by_kind']),
                         {'purchase_request', 'purchase_order', 'supplier_payment',
                          'marketing_budget', 'production_change', 'workforce_leave',
                          'workforce_overtime', 'payroll_batch', 'ai_action'})



class ApprovalSummaryConsumerTest(ApprovalFixture):
    """Konsumen P2: Command Center, kartu perhatian, jawaban AI, dan overview."""

    def question(self, text, **changes):
        return dict(question=text, as_of='2026-11-15', window_days=14, lead_time_days=180,
                    review_period_days=180, safety_stock_days=90, batch_multiple=12) | changes

    def ask(self, text, **changes):
        response = self.client.post('/api/ai/investigate', json=self.question(text, **changes))
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def fact(self, report, label):
        return next(row for row in report['facts'] if row['label'] == label)

    def big_population(self):
        """610 pending: 500 bernominal Rp1.000,00 plus 110 tanpa nominal."""
        self.seed_marketing(500, amount_minor=1_000_00)
        self.seed_workforce(110, kind='leave')
        return self.oracle()

    def test_command_center_counts_and_amount_cover_the_whole_population(self):
        truth = self.big_population()
        self.assertEqual((truth['total'], truth['amount']), (610, '500000.00'))
        report = self.client.get('/api/command-center').json()
        approvals = report['approvals']
        self.assertEqual(approvals['pending_count'], 610)
        self.assertEqual(approvals['pending_amount'], '500000.00')
        self.assertEqual(approvals['by_kind']['marketing_budget'], 500)
        # Additive: menjelaskan mengapa count lebih besar daripada jumlah item bernominal.
        self.assertEqual(approvals['pending_without_amount'], 110)

    def test_attention_card_text_reports_the_whole_population(self):
        self.big_population()
        report = self.client.get('/api/command-center').json()
        card = next(row for row in report['attention'] if row['id'] == 'approvals-pending')
        self.assertEqual(card['detail'], '610 pengajuan senilai Rp500000.00 ada di inbox.')
        self.assertEqual((card['priority'], card['action']), ('warning', 'approvals'))

    def test_ai_approvals_answer_and_facts_report_the_whole_population(self):
        self.big_population()
        report = self.ask('Apa saja yang menunggu persetujuan approval?')
        self.assertEqual(report['intent'], 'approvals')
        self.assertEqual(report['answer'],
                         'Ada 610 item menunggu keputusan dengan total nominal '
                         'tercatat Rp500000.00.')
        self.assertEqual(self.fact(report, 'Approval tertunda')['value'], 610)
        self.assertEqual(self.fact(report, 'Nominal tertunda')['value'], '500000.00')
        self.assertEqual(self.fact(report, 'Approval marketing budget')['value'], 500)
        self.assertEqual(self.fact(report, 'Approval workforce leave')['value'], 110)

    def test_ai_facts_cite_the_aggregate_source_not_a_limited_page(self):
        self.big_population()
        report = self.ask('Apa saja yang menunggu persetujuan approval?')
        for label in ('Approval tertunda', 'Nominal tertunda', 'Approval marketing budget'):
            self.assertEqual(self.fact(report, label)['source'],
                             '/api/approvals/summary?status=pending')
        # Findings tetap merujuk daftar, karena isinya memang item daftar.
        self.assertEqual(report['findings'][0]['source'], '/api/approvals?status=pending')

    def test_overview_answer_uses_the_full_totals(self):
        self.big_population()
        report = self.ask('Apa yang harus saya lihat sekarang?')
        self.assertEqual(report['intent'], 'overview')
        self.assertIn('Ada 610 item menunggu keputusan dengan total nominal '
                      'tercatat Rp500000.00.', report['answer'])
        self.assertEqual(set(report['evidence']),
                         {'production_board', 'approvals', 'replenishment'})

    def test_evidence_separates_the_population_summary_from_the_sample(self):
        self.big_population()
        report = self.ask('Apa saja yang menunggu persetujuan approval?')
        evidence = report['evidence']['approvals']
        self.assertEqual(evidence['summary']['total'], 610)
        self.assertEqual(evidence['summary']['amount'], '500000.00')
        self.assertEqual(evidence['sample_size'], len(evidence['sample']))
        self.assertLessEqual(evidence['sample_size'], 10)
        self.assertTrue(evidence['truncated'])
        # Detail boleh terpotong, tetapi jumlah yang dijawab tetap jumlah penuh.
        self.assertEqual(len(report['findings']), evidence['sample_size'])
        self.assertEqual(len(report['recommendations']), evidence['sample_size'])

    def test_small_population_is_not_marked_as_truncated(self):
        self.seed_marketing(4, amount_minor=1_000_00)
        evidence = self.ask('Apa saja yang menunggu persetujuan approval?')['evidence']['approvals']
        self.assertEqual((evidence['summary']['total'], evidence['sample_size']), (4, 4))
        self.assertFalse(evidence['truncated'])

    def test_saved_investigation_keeps_the_snapshot_it_was_answered_with(self):
        self.seed_marketing(501, amount_minor=1_000_00)
        saved = self.post('/api/ai/investigations',
                          self.question('Antrian approval apa yang menunggu keputusan?'),
                          key='approval-investigation')
        self.assertEqual(saved['answer'],
                         'Ada 501 item menunggu keputusan dengan total nominal '
                         'tercatat Rp501000.00.')
        self.seed_marketing(9, amount_minor=1_000_00, prefix='MKT-LATER')
        replay = self.client.get('/api/ai/investigations/' + saved['id']).json()
        self.assertEqual(replay['answer'], saved['answer'])
        self.assertEqual(replay['evidence']['approvals']['summary']['total'], 501)
        # Investigasi baru memakai populasi terkini tanpa menyentuh snapshot lama.
        fresh = self.ask('Antrian approval apa yang menunggu keputusan?')
        self.assertEqual(self.fact(fresh, 'Approval tertunda')['value'], 510)

    def test_recommendations_stay_advisory_only(self):
        self.seed_marketing(520, amount_minor=1_000_00)
        report = self.ask('Apa saja yang menunggu persetujuan approval?')
        self.assertTrue(report['read_only'])
        for proposal in report['recommendations']:
            self.assertTrue(proposal['approval_required'])
            self.assertFalse(proposal['executable'])


class ApprovalSummaryApiTest(ApprovalFixture):
    def test_summary_endpoint_reports_totals_with_filters(self):
        self.seed_marketing(505, amount_minor=1_000_00)
        self.seed_workforce(7, kind='overtime')
        summary = self.client.get('/api/approvals/summary').json()
        self.assertEqual((summary['status'], summary['kind'], summary['currency']),
                         ('pending', 'all', 'IDR'))
        self.assertEqual((summary['total'], summary['amount']), (512, '505000.00'))
        self.assertEqual((summary['with_amount'], summary['without_amount']), (505, 7))
        filtered = self.client.get('/api/approvals/summary?kind=workforce_overtime').json()
        self.assertEqual((filtered['total'], filtered['amount'], filtered['kind']),
                         (7, '0.00', 'workforce_overtime'))
        self.assertEqual(set(summary['by_kind']),
                         {'purchase_request', 'purchase_order', 'supplier_payment',
                          'marketing_budget', 'production_change', 'workforce_leave',
                          'workforce_overtime', 'payroll_batch', 'ai_action'})

    def test_summary_status_filter_matches_the_list_population(self):
        self.seed_marketing(30, amount_minor=1_000_00)
        self.seed_marketing(12, amount_minor=1_000_00, status='approved', prefix='MKT-APR')
        for status in ('pending', 'approved', 'rejected', 'cancelled', 'all'):
            summary = self.client.get('/api/approvals/summary?status=' + status).json()
            listed = self.client.get('/api/approvals?status=' + status + '&limit=500').json()
            self.assertEqual(summary['total'], len(listed), status)

    def test_summary_rejects_unknown_filters_and_needs_authentication(self):
        self.assertEqual(self.client.get('/api/approvals/summary?kind=bad').status_code, 422)
        self.assertEqual(self.client.get('/api/approvals/summary?status=bad').status_code, 422)
        self.assertEqual(self.client.get('/api/approvals/summary',
                                         headers={'X-API-Key': 'invalid'}).status_code, 401)
        for account in (self.admin, self.operator, self.viewer):
            self.assertEqual(self.client.get('/api/approvals/summary',
                             headers={'X-API-Key': account['api_key']}).status_code, 200)

    def test_existing_list_contract_is_unchanged(self):
        self.seed_marketing(3, amount_minor=1_000_00)
        listed = self.client.get('/api/approvals').json()
        self.assertIsInstance(listed, list)
        self.assertEqual(len(listed), 3)
        self.assertEqual(set(listed[0]) >= {'id', 'kind', 'status', 'reference', 'amount',
                                            'currency', 'created_at', 'context'}, True)
        self.assertEqual(len(self.client.get('/api/approvals?limit=1&offset=1').json()), 1)
        self.assertEqual(self.client.get('/api/approvals?limit=501').status_code, 422)
        self.assertEqual(self.client.get('/api/approvals',
                         headers={'X-API-Key': self.viewer['api_key']}).status_code, 200)



class ApprovalSummaryOverflowTest(ApprovalFixture):
    """Regresi review Codex: SUM() SQLite dapat overflow sebelum dikonversi ke Decimal.

    Schema mengizinkan `gross_pay_minor` dan `employer_contributions_minor` masing-masing sampai
    100000000000000000 satuan minor, jadi satu periode payroll boleh bernilai 2e17. Akumulator SUM
    SQLite adalah integer 64-bit dengan batas 2^63-1 = 9223372036854775807, sehingga 47 pengajuan
    pending sudah melewatinya dan seluruh ringkasan gagal dengan "integer overflow".

    Nilai di sini ekstrem tetapi sah menurut schema. Ini pengujian batas aritmetika, bukan klaim
    bahwa ada database produksi yang pernah memuat angka sebesar itu.
    """

    EXTREME = 10**17  # batas atas yang diizinkan schema untuk kedua kolom payroll

    def payroll_oracle(self, count):
        """Oracle integer murni, tidak memakai fungsi agregat maupun Decimal yang diuji."""
        whole, cents = divmod(count * 2 * self.EXTREME, 100)
        return f'{whole}.{cents:02d}'

    def test_forty_six_payroll_approvals_stay_below_the_sqlite_limit(self):
        self.seed_payroll(46, gross_minor=self.EXTREME, employer_minor=self.EXTREME)
        summary = self.assert_summary_matches_oracle()
        self.assertEqual((summary['total'], summary['amount']), (46, '92000000000000000.00'))
        self.assertEqual(summary['amount'], self.payroll_oracle(46))
        self.assertLess(46 * 2 * self.EXTREME, 2**63 - 1)

    def test_forty_seven_payroll_approvals_cross_the_limit_and_stay_exact(self):
        """Populasi tepat di ambang overflow; sebelum perbaikan seluruh ringkasan gagal."""
        self.assertGreater(47 * 2 * self.EXTREME, 2**63 - 1)
        self.seed_payroll(47, gross_minor=self.EXTREME, employer_minor=self.EXTREME)
        summary = self.assert_summary_matches_oracle()
        self.assertEqual((summary['total'], summary['amount']), (47, '94000000000000000.00'))
        self.assertEqual(summary['amount'], self.payroll_oracle(47))
        self.assertEqual(summary['by_kind']['payroll_batch'],
                         {'count': 47, 'amount': '94000000000000000.00'})
        self.assertEqual((summary['with_amount'], summary['without_amount']), (47, 0))
        # Silang-uji terhadap jalur hidrasi lama yang memang selalu menjumlahkan di Python.
        self.assert_list_agrees_with_summary()

    def test_amount_stays_exact_far_beyond_the_sqlite_limit(self):
        """Kelipatan jauh di atas ambang tidak boleh dibulatkan oleh presisi Decimal default."""
        self.seed_payroll(150, gross_minor=self.EXTREME, employer_minor=self.EXTREME)
        summary = self.assert_summary_matches_oracle()
        self.assertEqual((summary['total'], summary['amount']),
                         (150, '300000000000000000.00'))
        self.assertEqual(summary['amount'], self.payroll_oracle(150))
        self.assertGreater(150 * 2 * self.EXTREME, 3 * (2**63 - 1))

    def test_extreme_amounts_mix_with_cents_zero_and_missing_amounts(self):
        """Nominal ekstrem, sen kecil, nol, dan tanpa nominal harus berjumlah eksak bersama."""
        self.seed_payroll(47, gross_minor=self.EXTREME, employer_minor=self.EXTREME)
        self.seed_payroll(2, gross_minor=0, employer_minor=0)          # nominal nol
        self.seed_marketing(1, amount_minor=1)                         # 0.01
        self.seed_marketing(1, amount_minor=99)                        # 0.99
        self.seed_workforce(3, kind='leave')                           # tanpa nominal
        self.seed_ai_action(1, estimated_value='0.33')                 # nominal desimal JSON
        summary = self.assert_summary_matches_oracle()
        self.assertEqual(summary['total'], 55)
        self.assertEqual(summary['without_amount'], 3)
        # 94000000000000000.00 + 0.00 + 0.01 + 0.99 + 0.33
        self.assertEqual(summary['amount'], '94000000000000001.33')
        self.assert_list_agrees_with_summary()

    def test_status_and_kind_filters_stay_exact_at_extreme_amounts(self):
        self.seed_payroll(47, gross_minor=self.EXTREME, employer_minor=self.EXTREME)
        self.seed_payroll(5, gross_minor=self.EXTREME, employer_minor=self.EXTREME,
                          status='approved')
        self.seed_marketing(3, amount_minor=2_500_00)
        for status in ('pending', 'approved', 'rejected', 'cancelled', 'all'):
            self.assert_summary_matches_oracle(status=status)
        for kind in ('all', 'payroll_batch', 'marketing_budget', 'purchase_request'):
            self.assert_summary_matches_oracle(kind=kind)
            self.assert_list_agrees_with_summary(kind=kind)
        pending = self.app.state.store.approvals_summary(kind='payroll_batch')
        self.assertEqual(pending['amount'], '94000000000000000.00')
        every = self.app.state.store.approvals_summary(status='all', kind='payroll_batch')
        self.assertEqual((every['total'], every['amount']), (52, self.payroll_oracle(52)))

    def executed_sql(self, run):
        """Rekam setiap statement yang benar-benar dieksekusi SQLite selama `run()`."""
        store = self.app.state.store
        statements, original = [], store.connect

        def connect():
            db = original()
            db.set_trace_callback(statements.append)
            return db

        store.connect = connect
        try:
            run()
        finally:
            store.connect = original
        return statements

    def test_no_amount_branch_delegates_summation_to_sqlite(self):
        """Perbaikan berlaku untuk seluruh cabang nominal, bukan pengecualian khusus payroll.

        Diperiksa dari statement yang benar-benar dieksekusi, bukan dari teks sumbernya.
        """
        self.seed_payroll(2, gross_minor=self.EXTREME, employer_minor=self.EXTREME)
        self.seed_marketing(2, amount_minor=1_000_00)
        self.seed_purchase_requests(2, amount_minor=1_000_00)
        self.seed_ai_action(1, estimated_value='10.00')
        store = self.app.state.store
        statements = self.executed_sql(lambda: [store.approvals_summary(status=status, kind=kind)
                                                for status in ('pending', 'all')
                                                for kind in ('all',) + APPROVAL_KINDS])
        self.assertTrue(statements)
        aggregates = [sql for sql in statements if 'FROM' in sql.upper()]
        self.assertTrue(aggregates)
        for sql in aggregates:
            upper = sql.upper()
            for forbidden in ('SUM(', 'TOTAL(', 'AVG(', 'CAST(', 'REAL'):
                self.assertNotIn(forbidden, upper, sql)
        # Setiap kind bernominal memakai satuan yang dideklarasikan, bukan cabang khusus per nama.
        self.assertEqual({row[0]: row[5] for row in APPROVAL_AGGREGATES}, {
            'purchase_request': 'minor', 'purchase_order': 'minor', 'supplier_payment': 'minor',
            'marketing_budget': 'minor', 'production_change': None, 'workforce_leave': None,
            'workforce_overtime': None, 'payroll_batch': 'minor', 'ai_action': 'rupiah'})

    def test_consumers_report_extreme_totals_without_failing(self):
        """Command Center, AI approvals, dan overview harus eksak dan tidak 500."""
        self.seed_payroll(47, gross_minor=self.EXTREME, employer_minor=self.EXTREME)
        expected = self.payroll_oracle(47)

        endpoint = self.client.get('/api/approvals/summary')
        self.assertEqual(endpoint.status_code, 200, endpoint.text)
        self.assertEqual((endpoint.json()['total'], endpoint.json()['amount']), (47, expected))

        report = self.client.get('/api/command-center')
        self.assertEqual(report.status_code, 200, report.text)
        approvals = report.json()['approvals']
        self.assertEqual((approvals['pending_count'], approvals['pending_amount']), (47, expected))
        card = next(row for row in report.json()['attention'] if row['id'] == 'approvals-pending')
        self.assertEqual(card['detail'], f'47 pengajuan senilai Rp{expected} ada di inbox.')

        question = dict(question='Antrean approval apa yang menunggu keputusan?', as_of='2026-11-15',
                        window_days=14, lead_time_days=180, review_period_days=180,
                        safety_stock_days=90, batch_multiple=12)
        answer = self.client.post('/api/ai/investigate', json=question)
        self.assertEqual(answer.status_code, 200, answer.text)
        self.assertEqual(answer.json()['answer'],
                         f'Ada 47 item menunggu keputusan dengan total nominal tercatat Rp{expected}.')
        self.assertEqual(answer.json()['evidence']['approvals']['summary']['amount'], expected)

        overview = self.client.post('/api/ai/investigate',
                                    json=question | {'question': 'Apa yang harus saya lihat sekarang?'})
        self.assertEqual(overview.status_code, 200, overview.text)
        self.assertIn(f'Rp{expected}', overview.json()['answer'])



class NineKindFixture(ApprovalFixture):
    """Fixture P3-A: pengajuan pending yang sah untuk kesembilan kind sekaligus.

    Tiga kind tidak punya seed SQL langsung karena rantai FK dan trigger-nya panjang: PO wajib
    menunjuk PR yang sudah disetujui, pembayaran supplier wajib menunjuk PO yang sudah disetujui
    *dan* sudah menerima bahan, dan perubahan produksi wajib cocok dengan due date serta pemilik
    order yang berlaku. Ketiganya karena itu dibuat lewat endpoint aslinya, sehingga yang terhitung
    memang pengajuan yang sah menurut aturan aplikasi, bukan baris yang ditanam paksa.
    """

    material = test_materials.MaterialsTest.material
    pr_payload = test_purchase_requests.PurchaseRequestTest.payload
    pr_create = test_purchase_requests.PurchaseRequestTest.create
    pr_decide = test_purchase_requests.PurchaseRequestTest.decide
    new_supplier = test_purchase_orders.PurchaseOrderTest.supplier
    submit_po = test_purchase_orders.PurchaseOrderTest.submit_po
    approve_po = test_purchase_orders.PurchaseOrderTest.approve_po
    receive = test_po_receipts.PurchaseReceiptTest.receive

    def supplier_id(self):
        """Satu pemasok dipakai bersama: kode pemasok unik, jadi tidak boleh dibuat dua kali."""
        if getattr(self, 'shared_supplier', None) is None:
            self.shared_supplier = self.new_supplier()
        return self.shared_supplier['id']

    def approved_purchase_request(self, code, reference, quantity='2'):
        material = self.material(code=code)
        approved = self.pr_decide(self.pr_create(self.pr_payload(material, reference=reference,
            lines=[dict(material_id=material['id'], quantity=quantity)])), 'approved')
        self.record('purchase_request', None, 'approved',
                    amount=Decimal(approved['estimated_value']))
        return material, approved

    def seed_purchase_order(self, code, pr_reference, po_reference, approve=False,
                            unit_price='10.00', quantity='2'):
        material, approved = self.approved_purchase_request(code, pr_reference, quantity)
        po = self.submit_po(dict(reference=po_reference, request_id=approved['id'],
            expected_revision=approved['revision'], supplier_id=self.supplier_id(),
            expected_date='2026-10-15', terms='Bayar setelah diterima',
            reason='Harga disepakati',
            prices=[dict(material_id=material['id'], unit_price=unit_price)]))
        if approve:
            self.approve_po(po)
        self.record('purchase_order', None, 'approved' if approve else PENDING,
                    amount=Decimal(po['total']))
        return material, po

    def seed_supplier_payment(self, code, pr_reference, po_reference, amount='10.00'):
        material, po = self.seed_purchase_order(code, pr_reference, po_reference, approve=True)
        self.receive(po, dict(material_id=material['id'], reference='BATCH-' + po_reference,
            quantity='2', location='Rak A', received_date='2026-10-15',
            reason='Lolos pemeriksaan'))
        payment = self.post('/api/purchase-orders/' + po['id'] + '/payment-requests',
            dict(reference='PAY-' + po_reference, invoice_reference='INV-' + po_reference,
                 invoice_date='2026-10-15', due_date='2026-10-30', amount=amount,
                 reason='Invoice sesuai penerimaan bahan'))
        self.record('supplier_payment', None, PENDING, amount=Decimal(payment['amount']))
        return payment

    def seed_production_change(self, reference='PCR-AGG'):
        target = self.order()
        request = self.post('/api/orders/' + target['id'] + '/change-requests',
            dict(reference=reference, owner_id=self.admin['id'], due_date='2099-01-01',
                 expected_revision=target['revision'],
                 reason='Jadwal produksi perlu disesuaikan'))
        self.record('production_change', None, PENDING)
        return request

    def seed_every_kind(self):
        """Tepat satu pengajuan pending untuk masing-masing dari kesembilan kind."""
        self.seed_purchase_requests(1, amount_minor=100_000_00)
        self.seed_purchase_order('AGG-PO-CLOTH', 'PR-AGG-PO', 'PO-AGG-PENDING')
        self.seed_supplier_payment('AGG-PAY-CLOTH', 'PR-AGG-PAY', 'PO-AGG-PAID')
        self.seed_marketing(1, amount_minor=250_000_00)
        self.seed_production_change()
        self.seed_workforce(1, kind='leave')
        self.seed_workforce(1, kind='overtime')
        self.seed_payroll(1, gross_minor=5_000_000_00, employer_minor=500_000_00)
        self.seed_ai_action(1, estimated_value='500000.00')

    def breakdown(self):
        report = self.client.get('/api/command-center')
        self.assertEqual(report.status_code, 200, report.text)
        return report.json()['approvals']


class CommandCenterApprovalBreakdownTest(NineKindFixture):
    """Regresi P3-A: rincian kategori approval harus memuat seluruh kategori agregat.

    Command Center sudah membaca `approvals_summary()` untuk total dan nominalnya, tetapi
    `approvals.by_kind` masih dipangkas ke enam kategori pilihan tangan. Cuti, lembur, dan batch
    payroll ikut dihitung pada `pending_count` namun tidak pernah muncul di rincian, sehingga
    jumlah rincian lebih kecil daripada totalnya dan tiga departemen kehilangan visibilitas.
    """

    # Enam kategori yang sudah dilaporkan sebelum perbaikan; nilainya tidak boleh bergeser.
    ORIGINAL = ('purchase_request', 'purchase_order', 'supplier_payment', 'marketing_budget',
                'production_change', 'ai_action')
    ADDED = ('workforce_leave', 'workforce_overtime', 'payroll_batch')

    def test_breakdown_reports_every_kind_the_aggregate_knows(self):
        """Kesembilan kind punya pengajuan pending yang sah, dan semuanya terlihat."""
        self.seed_every_kind()
        approvals = self.breakdown()
        self.assertEqual(set(approvals['by_kind']), set(APPROVAL_KINDS))
        self.assertEqual(approvals['by_kind'], {kind: 1 for kind in APPROVAL_KINDS})
        self.assertEqual(approvals['pending_count'], 9)
        # Oracle fixture, bukan agregat yang diuji.
        truth = self.oracle()
        self.assertEqual((approvals['pending_count'], approvals['pending_amount']),
                         (truth['total'], truth['amount']))
        self.assertEqual(approvals['pending_without_amount'], truth['without_amount'])

    def test_breakdown_sums_to_the_pending_count_for_the_same_scope(self):
        self.seed_every_kind()
        self.seed_marketing(4, amount_minor=1_000_00, prefix='MKT-EXTRA')
        self.seed_workforce(3, kind='overtime')
        approvals = self.breakdown()
        self.assertEqual(sum(approvals['by_kind'].values()), approvals['pending_count'])
        self.assertEqual(approvals['pending_count'], 16)

    def test_categories_without_pending_requests_stay_present_as_zero(self):
        """Kategori kosong tetap ada supaya rincian tidak berubah bentuk antar-permintaan."""
        self.seed_workforce(2, kind='leave')
        approvals = self.breakdown()
        self.assertEqual(set(approvals['by_kind']), set(APPROVAL_KINDS))
        self.assertEqual(approvals['by_kind']['workforce_leave'], 2)
        for kind in set(APPROVAL_KINDS) - {'workforce_leave'}:
            self.assertEqual(approvals['by_kind'][kind], 0, kind)
        self.assertEqual(sum(approvals['by_kind'].values()), approvals['pending_count'])

    def test_empty_dataset_reports_every_category_as_zero(self):
        approvals = self.breakdown()
        self.assertEqual(approvals['by_kind'], {kind: 0 for kind in APPROVAL_KINDS})
        self.assertEqual((approvals['pending_count'], approvals['pending_amount']), (0, '0.00'))
        self.assertEqual(sum(approvals['by_kind'].values()), 0)

    def test_leave_only_overtime_only_and_payroll_only_datasets_are_visible(self):
        """Sebelum perbaikan ketiga populasi ini seluruhnya tidak terlihat pada rincian."""
        for kind, seed in (('workforce_leave', lambda: self.seed_workforce(6, kind='leave')),
                           ('workforce_overtime', lambda: self.seed_workforce(4, kind='overtime')),
                           ('payroll_batch', lambda: self.seed_payroll(3, gross_minor=1_000_00))):
            with self.subTest(kind=kind):
                self.setUp()
                seed()
                approvals = self.breakdown()
                counts = {name: value for name, value in approvals['by_kind'].items() if value}
                self.assertEqual(list(counts), [kind])
                self.assertEqual(counts[kind], approvals['pending_count'])
                self.assertEqual(sum(approvals['by_kind'].values()),
                                 approvals['pending_count'])

    def test_leave_and_overtime_without_amounts_are_counted_but_add_no_nominal(self):
        self.seed_workforce(5, kind='leave')
        self.seed_workforce(2, kind='overtime')
        self.seed_marketing(1, amount_minor=750_00)
        approvals = self.breakdown()
        self.assertEqual((approvals['by_kind']['workforce_leave'],
                          approvals['by_kind']['workforce_overtime']), (5, 2))
        self.assertEqual(approvals['pending_count'], 8)
        self.assertEqual(approvals['pending_amount'], '750.00')
        self.assertEqual(approvals['pending_without_amount'], 7)

    def test_terminal_decisions_leave_the_breakdown_with_the_pending_scope(self):
        self.seed_workforce(5, kind='leave')
        self.seed_workforce(3, kind='overtime')
        self.seed_payroll(2, gross_minor=1_000_00)
        self.seed_marketing(4, amount_minor=1_000_00)
        # Setiap tabel approval punya transisi terminal yang diizinkannya sendiri; yang diuji di
        # sini adalah bahwa keputusan terminal apa pun mengeluarkan baris dari scope pending.
        self.seed_workforce(6, kind='leave', status='approved')
        self.seed_workforce(2, kind='overtime', status='rejected')
        self.seed_payroll(3, gross_minor=1_000_00, status='approved')
        self.seed_marketing(7, amount_minor=1_000_00, status='cancelled', prefix='MKT-CAN')
        approvals = self.breakdown()
        self.assertEqual({name: value for name, value in approvals['by_kind'].items() if value},
                         {'workforce_leave': 5, 'workforce_overtime': 3, 'payroll_batch': 2,
                          'marketing_budget': 4})
        self.assertEqual(approvals['pending_count'], 14)
        self.assertEqual(sum(approvals['by_kind'].values()), 14)
        self.assertEqual(self.app.state.store.approvals_summary(status='all')['total'], 32)

    def test_breakdown_stays_exact_beyond_the_old_five_hundred_row_page(self):
        """Populasi di atas 500 tetap dilaporkan apa adanya, termasuk kategori baru."""
        self.seed_marketing(400, amount_minor=1_000_00)
        self.seed_workforce(150, kind='leave')
        self.seed_workforce(60, kind='overtime')
        self.seed_payroll(30, gross_minor=1_000_00)
        approvals = self.breakdown()
        self.assertEqual(approvals['pending_count'], 640)
        self.assertGreater(approvals['pending_count'], 500)
        self.assertEqual(approvals['by_kind'], {'marketing_budget': 400, 'workforce_leave': 150,
            'workforce_overtime': 60, 'payroll_batch': 30, 'purchase_request': 0,
            'purchase_order': 0, 'supplier_payment': 0, 'production_change': 0, 'ai_action': 0})
        self.assertEqual(sum(approvals['by_kind'].values()), 640)
        truth = self.oracle()
        self.assertEqual((approvals['pending_count'], approvals['pending_amount']),
                         (truth['total'], truth['amount']))

    def test_the_six_original_categories_keep_their_values_and_types(self):
        """Kontrak lama tidak boleh bergeser: kunci, nilai, dan tipenya tetap sama."""
        self.seed_every_kind()
        self.seed_marketing(9, amount_minor=1_000_00, prefix='MKT-KEEP')
        self.seed_ai_action(4, estimated_value='250.00')
        approvals = self.breakdown()
        by_kind = approvals['by_kind']
        self.assertEqual({kind: by_kind[kind] for kind in self.ORIGINAL},
                         {'purchase_request': 1, 'purchase_order': 1, 'supplier_payment': 1,
                          'marketing_budget': 10, 'production_change': 1, 'ai_action': 5})
        for kind in APPROVAL_KINDS:
            self.assertIsInstance(by_kind[kind], int, kind)
            self.assertNotIsInstance(by_kind[kind], bool, kind)
        self.assertIsInstance(approvals['pending_count'], int)
        self.assertIsInstance(approvals['pending_amount'], str)
        self.assertIsInstance(approvals['pending_without_amount'], int)

    def test_breakdown_counts_match_the_aggregate_and_the_list_per_category(self):
        """Rincian bersumber dari agregat yang sama, bukan definisi pending kedua."""
        self.seed_every_kind()
        self.seed_workforce(3, kind='leave')
        store = self.app.state.store
        approvals = self.breakdown()
        summary = store.approvals_summary(status='pending')
        for kind in APPROVAL_KINDS:
            self.assertEqual(approvals['by_kind'][kind], summary['by_kind'][kind]['count'], kind)
            listed = store.approvals(1_000_000, 0, 'pending', kind)
            self.assertEqual(approvals['by_kind'][kind], len(listed), kind)

    def test_amount_semantics_per_kind_are_untouched_by_the_breakdown(self):
        """Rincian hanya melaporkan jumlah; nominal per kind tetap milik agregat."""
        self.seed_every_kind()
        summary = self.app.state.store.approvals_summary(status='pending')
        self.assertEqual({kind: summary['by_kind'][kind]['amount'] for kind in APPROVAL_KINDS},
                         {'purchase_request': '100000.00', 'purchase_order': '20.00',
                          'supplier_payment': '10.00', 'marketing_budget': '250000.00',
                          'production_change': '0.00', 'workforce_leave': '0.00',
                          'workforce_overtime': '0.00', 'payroll_batch': '5500000.00',
                          'ai_action': '500000.00'})
        approvals = self.breakdown()
        self.assertEqual(approvals['pending_amount'], summary['amount'])
        self.assertEqual(approvals['pending_amount'], self.oracle()['amount'])

    def test_extreme_amounts_do_not_disturb_the_added_categories(self):
        """Nominal melewati batas integer SQLite tetap eksak dan jumlahnya tetap benar."""
        extreme = 10**17
        self.seed_payroll(47, gross_minor=extreme, employer_minor=extreme)
        self.seed_workforce(4, kind='leave')
        self.seed_workforce(2, kind='overtime')
        approvals = self.breakdown()
        self.assertGreater(47 * 2 * extreme, 2**63 - 1)
        self.assertEqual(approvals['by_kind']['payroll_batch'], 47)
        self.assertEqual((approvals['by_kind']['workforce_leave'],
                          approvals['by_kind']['workforce_overtime']), (4, 2))
        self.assertEqual(approvals['pending_count'], 53)
        self.assertEqual(sum(approvals['by_kind'].values()), 53)
        # Oracle integer murni: 47 * 2 * 10^17 satuan minor dibagi 100.
        whole, cents = divmod(47 * 2 * extreme, 100)
        self.assertEqual(approvals['pending_amount'], f'{whole}.{cents:02d}')
        self.assertEqual(approvals['pending_amount'], '94000000000000000.00')

    def test_approvals_list_endpoint_is_still_a_list(self):
        """Kontrak GET /api/approvals tidak berubah menjadi object oleh perbaikan ini."""
        self.seed_every_kind()
        listed = self.client.get('/api/approvals?limit=500').json()
        self.assertIsInstance(listed, list)
        self.assertEqual(len(listed), 9)
        self.assertEqual({row['kind'] for row in listed}, set(APPROVAL_KINDS))

    def test_ai_facts_report_the_added_categories_too(self):
        """Facts AI memetakan kategori secara mekanis; kategori baru harus ikut muncul."""
        self.seed_workforce(4, kind='leave')
        self.seed_workforce(2, kind='overtime')
        self.seed_payroll(3, gross_minor=1_000_00)
        answer = self.client.post('/api/ai/investigate', json=dict(
            question='Apa saja yang menunggu persetujuan approval?', as_of='2026-11-15',
            window_days=14, lead_time_days=180, review_period_days=180, safety_stock_days=90,
            batch_multiple=12))
        self.assertEqual(answer.status_code, 200, answer.text)
        facts = {row['label']: row['value'] for row in answer.json()['facts']}
        self.assertEqual(facts['Approval workforce leave'], 4)
        self.assertEqual(facts['Approval workforce overtime'], 2)
        self.assertEqual(facts['Approval payroll batch'], 3)
        self.assertEqual(facts['Approval tertunda'], 9)
