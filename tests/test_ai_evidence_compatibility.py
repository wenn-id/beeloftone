"""Regresi kompatibilitas evidence investigasi AI setelah perbaikan P2-B.

Sebelum perbaikan, `evidence['approvals']` adalah list mentah berisi sampai 500 baris approval
yang dibaca dari satu halaman daftar. Sesudahnya, evidence memisahkan ringkasan seluruh populasi
dari contoh item yang ditampilkan:

    {'summary': {...}, 'sample': [...], 'sample_size': int, 'truncated': bool}

Snapshot investigasi bersifat abadi: `ai_investigations.result_snapshot` disimpan sekali dan dibaca
apa adanya, tidak pernah dihitung ulang. Modul ini menegakkan empat hal yang tidak dibuktikan oleh
cakupan yang sudah ada:

1. Investigasi historis tidak berubah sama sekali setelah perbaikan diterapkan.
2. Snapshot berformat evidence LAMA tetap dapat dibaca oleh seluruh jalur baca dan tulis turunannya.
3. Investigasi baru benar-benar mengabadikan agregat yang mendasari answer dan facts-nya.
4. Sampel yang terpotong dijelaskan apa adanya dan tidak pernah diperlakukan sebagai total penuh.
"""

import json
from decimal import Decimal
from unittest import TestCase

import test_approval_aggregates as aggregate_tests


HISTORICAL_ID = 'legacy-investigation-0001'
# Bentuk snapshot sebelum perbaikan: evidence['approvals'] berupa list mentah, tanpa summary,
# tanpa sample_size, dan tanpa penanda truncated. Angka pada answer dan facts memang berasal dari
# halaman terbatas itu, dan justru karena itu snapshot lama tidak boleh disentuh.
HISTORICAL_SNAPSHOT = {
    'question': 'Approval apa yang menunggu keputusan pada rilis lama?',
    'intent': 'approvals', 'interpretation': 'antrean approval', 'confidence': 'high',
    'matched_terms': ['approval', 'menunggu keputusan'],
    'focus': {'products': [], 'orders': []}, 'as_of': '2026-01-01',
    'engine': 'local_rules_v1', 'external_model_used': False, 'read_only': True,
    'answer': 'Ada 500 item menunggu keputusan dengan total nominal tercatat Rp500000.00.',
    'facts': [
        {'label': 'Approval tertunda', 'value': 500, 'unit': 'item',
         'source': '/api/approvals?status=pending'},
        {'label': 'Nominal tertunda', 'value': '500000.00', 'unit': 'IDR',
         'source': '/api/approvals?status=pending'},
    ],
    'findings': [{'severity': 'high', 'title': 'MKT-LEGACY · Marketing',
                  'detail': 'Kampanye lama', 'source': '/api/approvals?status=pending',
                  'entity': {'type': 'marketing_budget', 'id': 'MKT-LEGACY'}}],
    'recommendations': [{'kind': 'review_approval', 'title': 'Review MKT-LEGACY',
                         'detail': 'Kampanye lama', 'source': '/api/approvals?status=pending',
                         'approval_required': True, 'executable': False,
                         'preview': {'kind': 'marketing_budget', 'id': 'MKT-LEGACY'}}],
    # Inilah bentuk lama yang harus tetap terbaca: list, bukan dict.
    'evidence': {'approvals': [
        {'id': 'MKT-LEGACY', 'kind': 'marketing_budget', 'department': 'Marketing',
         'status': 'pending', 'reference': 'MKT-LEGACY', 'title': 'Kampanye lama',
         'amount': '1000.00', 'currency': 'IDR', 'reason': 'Rilis lama',
         'actor_id': 'legacy-actor', 'actor_name': 'Legacy', 'created_at': '2026-01-01T00:00:00+00:00',
         'context': {}},
    ]},
    'limitations': ['Bahasa dipetakan dengan aturan lokal.'],
}
HISTORICAL_SOURCE = {'question': HISTORICAL_SNAPSHOT['question'], 'as_of': '2026-01-01',
                     'window_days': 14, 'lead_time_days': 180, 'review_period_days': 180,
                     'safety_stock_days': 90, 'batch_multiple': 12}


class AiEvidenceCompatibilityTest(aggregate_tests.ApprovalFixture):
    """Memakai fixture approval P2-B supaya populasi pending dapat dikendalikan."""

    def question(self, text, **changes):
        return dict(question=text, as_of='2026-11-15', window_days=14, lead_time_days=180,
                    review_period_days=180, safety_stock_days=90, batch_multiple=12) | changes

    def ask(self, text, **changes):
        response = self.client.post('/api/ai/investigate', json=self.question(text, **changes))
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def fact(self, report, label):
        return next(row for row in report['facts'] if row['label'] == label)

    def insert_historical(self):
        """Tulis satu investigasi berformat lama langsung ke tabelnya.

        Ini satu-satunya cara jujur untuk menguji kompatibilitas: kode baru tidak lagi dapat
        menghasilkan bentuk evidence lama, sedangkan database pengguna sudah memuatnya.
        """
        with self.app.state.store.transaction(write=True) as db:
            db.execute('''INSERT INTO ai_investigations(id,question,intent,source_payload,
                result_snapshot,actor_id,created_at) VALUES(?,?,?,?,?,?,?)''',
                (HISTORICAL_ID, HISTORICAL_SNAPSHOT['question'], 'approvals',
                 json.dumps(HISTORICAL_SOURCE), json.dumps(HISTORICAL_SNAPSHOT),
                 self.operator['id'], '2026-01-01T00:00:00+00:00'))
        return HISTORICAL_ID

    # ------------------------------------------------------------------ 1 dan 2
    def test_historical_snapshot_is_returned_verbatim_and_never_recomputed(self):
        self.insert_historical()
        self.seed_marketing(520, amount_minor=1_000_00)  # populasi sekarang jauh berbeda
        detail = self.client.get('/api/ai/investigations/' + HISTORICAL_ID)
        self.assertEqual(detail.status_code, 200, detail.text)
        stored = detail.json()
        # Angka lama dipertahankan apa adanya, walaupun populasi nyata sekarang 520 item.
        self.assertEqual(stored['answer'], HISTORICAL_SNAPSHOT['answer'])
        self.assertEqual(stored['facts'], HISTORICAL_SNAPSHOT['facts'])
        self.assertEqual(stored['findings'], HISTORICAL_SNAPSHOT['findings'])
        self.assertEqual(stored['recommendations'], HISTORICAL_SNAPSHOT['recommendations'])
        # Bentuk evidence LAMA tetap list dan isinya identik.
        self.assertIsInstance(stored['evidence']['approvals'], list)
        self.assertEqual(stored['evidence'], HISTORICAL_SNAPSHOT['evidence'])
        self.assertEqual(stored['limitations'], HISTORICAL_SNAPSHOT['limitations'])
        # Baris database tidak tersentuh.
        with self.app.state.store.transaction() as db:
            raw = db.execute('SELECT result_snapshot FROM ai_investigations WHERE id=?',
                             (HISTORICAL_ID,)).fetchone()['result_snapshot']
        self.assertEqual(json.loads(raw), HISTORICAL_SNAPSHOT)

    def test_historical_snapshot_still_lists_and_accepts_feedback(self):
        """Jalur baca daftar dan tulis turunannya tidak boleh pecah karena bentuk evidence lama."""
        self.insert_historical()
        listed = self.client.get('/api/ai/investigations').json()
        entry = next(row for row in listed if row['id'] == HISTORICAL_ID)
        self.assertEqual((entry['answer'], entry['intent'], entry['interpretation']),
                         (HISTORICAL_SNAPSHOT['answer'], 'approvals', 'antrean approval'))
        self.assertEqual(entry['action_count'], 0)
        filtered = self.client.get('/api/ai/investigations?intent=approvals&q=rilis lama').json()
        self.assertEqual([row['id'] for row in filtered], [HISTORICAL_ID])
        saved = self.post('/api/ai/investigations/' + HISTORICAL_ID + '/feedback',
                          {'rating': 'not_helpful', 'reason': 'Angka lama sudah tidak relevan'},
                          key='legacy-feedback')
        self.assertEqual(saved['feedback_summary'],
                         {'helpful': 0, 'not_helpful': 1, 'respondents': 1})
        # Feedback tidak boleh menulis ulang snapshot.
        self.assertEqual(saved['evidence'], HISTORICAL_SNAPSHOT['evidence'])
        again = self.client.get('/api/ai/investigations/' + HISTORICAL_ID).json()
        self.assertEqual(again['evidence']['approvals'], HISTORICAL_SNAPSHOT['evidence']['approvals'])

    def test_new_investigation_does_not_disturb_the_historical_one(self):
        self.insert_historical()
        self.seed_marketing(505, amount_minor=1_000_00)
        fresh = self.post('/api/ai/investigations',
                          self.question('Antrean approval apa yang menunggu keputusan sekarang?'),
                          key='fresh-after-legacy')
        self.assertEqual(fresh['evidence']['approvals']['summary']['total'], 505)
        legacy = self.client.get('/api/ai/investigations/' + HISTORICAL_ID).json()
        self.assertEqual(legacy['answer'], HISTORICAL_SNAPSHOT['answer'])
        self.assertIsInstance(legacy['evidence']['approvals'], list)
        # Kedua bentuk hidup berdampingan pada satu database.
        both = self.client.get('/api/ai/investigations?intent=approvals').json()
        self.assertEqual({row['id'] for row in both}, {HISTORICAL_ID, fresh['id']})

    # ---------------------------------------------------------------------- 3
    def test_saved_snapshot_carries_the_aggregate_behind_answer_and_facts(self):
        """Agregat yang mendasari jawaban harus ikut tersimpan agar tetap dapat diaudit."""
        self.seed_marketing(512, amount_minor=1_250_50)
        self.seed_workforce(8, kind='overtime')
        expected = self.oracle()
        saved = self.post('/api/ai/investigations',
                          self.question('Antrean approval apa yang menunggu keputusan?'),
                          key='aggregate-audit')
        summary = saved['evidence']['approvals']['summary']
        # Ringkasan tersimpan sama dengan kebenaran fixture, bukan sekadar panjang halaman.
        self.assertEqual((summary['total'], summary['amount'], summary['without_amount']),
                         (expected['total'], expected['amount'], expected['without_amount']))
        # Answer dan facts benar-benar dibangun dari ringkasan yang tersimpan itu.
        self.assertIn('Ada %d item' % summary['total'], saved['answer'])
        self.assertIn('Rp' + summary['amount'], saved['answer'])
        self.assertEqual(self.fact(saved, 'Approval tertunda')['value'], summary['total'])
        self.assertEqual(self.fact(saved, 'Nominal tertunda')['value'], summary['amount'])
        # Facts merujuk sumber agregat, bukan halaman daftar.
        self.assertEqual(self.fact(saved, 'Approval tertunda')['source'],
                         '/api/approvals/summary?status=pending')
        # Nominal agregat konsisten dengan penjumlahan per kind pada snapshot yang sama.
        by_kind = sum((Decimal(row['amount']) for row in summary['by_kind'].values()), Decimal(0))
        self.assertEqual(format(by_kind, '.2f'), summary['amount'])
        self.assertEqual(sum(row['count'] for row in summary['by_kind'].values()), summary['total'])
        # Snapshot yang dibaca ulang identik dengan yang dijawab.
        replay = self.client.get('/api/ai/investigations/' + saved['id']).json()
        self.assertEqual(replay['evidence']['approvals']['summary'], summary)
        self.assertEqual(replay['answer'], saved['answer'])

    # ---------------------------------------------------------------------- 4
    def test_truncated_sample_is_explained_and_never_read_as_the_total(self):
        self.seed_marketing(530, amount_minor=1_000_00)
        report = self.ask('Antrean approval apa yang menunggu keputusan?')
        evidence = report['evidence']['approvals']
        self.assertTrue(evidence['truncated'])
        self.assertEqual(evidence['sample_size'], len(evidence['sample']))
        self.assertLess(evidence['sample_size'], evidence['summary']['total'])
        # Yang dilaporkan sebagai total adalah populasi, bukan panjang sampel.
        self.assertEqual(evidence['summary']['total'], 530)
        self.assertNotEqual(self.fact(report, 'Approval tertunda')['value'], evidence['sample_size'])
        self.assertEqual(self.fact(report, 'Approval tertunda')['value'], 530)
        # Sampel memang hanya potongan daftar, dan setiap barisnya item nyata.
        self.assertTrue(all(row['kind'] == 'marketing_budget' for row in evidence['sample']))
        self.assertEqual(len(report['findings']), evidence['sample_size'])
        self.assertEqual(len(report['recommendations']), evidence['sample_size'])
        # Sumber sampel jujur menyebut daftar, bukan agregat.
        self.assertTrue(all(row['source'] == '/api/approvals?status=pending'
                            for row in report['findings']))

    def test_untruncated_sample_reports_the_whole_population_as_the_sample(self):
        self.seed_marketing(3, amount_minor=1_000_00)
        evidence = self.ask('Antrean approval apa yang menunggu keputusan?')['evidence']['approvals']
        self.assertFalse(evidence['truncated'])
        self.assertEqual(evidence['sample_size'], evidence['summary']['total'])
        self.assertEqual(evidence['sample_size'], 3)

    def test_overview_evidence_keeps_its_existing_key_shape(self):
        """Kontrak kunci evidence tidak boleh berubah diam-diam."""
        self.seed_marketing(2, amount_minor=1_000_00)
        report = self.ask('Apa yang harus saya lihat sekarang?')
        self.assertEqual(report['intent'], 'overview')
        self.assertEqual(set(report['evidence']),
                         {'production_board', 'approvals', 'replenishment'})
        self.assertEqual(set(report['evidence']['approvals']),
                         {'summary', 'sample', 'sample_size', 'truncated'})
        self.assertEqual(set(report['evidence']['approvals']['summary']),
                         {'status', 'kind', 'currency', 'total', 'amount',
                          'with_amount', 'without_amount', 'by_kind'})
