"""A6.5 - Tanya Beeloft + Integrasi modern workspaces: the static half of the migration contract.

A6.5 spends the A6.0 language on two workspaces that read EVIDENCE: Tanya Beeloft investigates the
Beeloft ledger and stores the result as an investigation; Integrasi reports connector health from
the actual run ledger and opens read-only vendor snapshots and payroll reconciliations. The risk
here is not a bad layout. It is that a presentation pass quietly weakens something load-bearing -
the idempotent investigation write, the same-actor retry, historical evidence compatibility, the
viewer proposal gate, the five health values, or the read-only boundary - or invents a control the
product does not have (sync now, import, post journal). So what is asserted here is

  * both sections are A6 `workspace-page` grammar, with the approved titles and subtitles, and the
    local-analysis truth still printed verbatim;
  * every composer constraint, all five starters, every assumption default/min/max, and NO max on
    as_of;
  * the investigation write still goes through api.transaction()/api.save() with the per-user
    pending draft, sameActorGuard() and clearPending(), and the uncertain-save wording is intact;
  * renderAiInvestigation still takes `source = report.source_payload`, tolerates missing fields,
    still gates proposals on `user.role !== 'viewer'` and exactly two supported kinds, and the
    decision payload still carries `expected_revision: row.revision`;
  * history is still 50/before with its request fence;
  * `/api/integrations`, its request fence and its refresh-hold are unchanged; all five health
    labels and the source-of-truth / inbound read-only wording remain; every Jubelio and Mekari
    entry point remains; runs are 50/before with a generation guard; snapshot histories are
    limit=100; payroll reconciliations are 25/offset;
  * no write, sync, import or journal control was invented, and payroll stays aggregate;
  * the A6.5 CSS block reaches only A6.5 surfaces, redefines no primitive, and adds no material or
    motion; no RAF, interval or polling was added; the shell and lens are untouched;
  * no route, schema or migration changed, and the version is aligned.

The containment half - that A6 primitives reached exactly these two sections and the named A6.5
renderers - lives in tests/test_apple27_modern_workspace_foundation_contract.py, whose allow-list
A6.5 widened on purpose. The behavioural half is tests/browser_ai_integrations_modern_workspaces.cjs.
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / 'beeloft' / 'static'
HTML = (STATIC / 'index.html').read_text(encoding='utf-8')
APP = (STATIC / 'app.mjs').read_text(encoding='utf-8')
CSS = (STATIC / 'style.css').read_text(encoding='utf-8')
SHELL = (STATIC / 'workspace.css').read_text(encoding='utf-8')


def section(html, element_id):
    start = html.index(f'<section id="{element_id}"')
    depth = 0
    for match in re.finditer(r'<section\b|</section>', html[start:]):
        depth += 1 if match.group().startswith('<section') else -1
        if depth == 0:
            return html[start:start + match.end()]
    raise AssertionError(f'#{element_id} is not a closed section')


def code(source):
    return re.sub(r'(?<!:)//[^\n]*', '', re.sub(r'/\*.*?\*/', '', source, flags=re.S))


def code_css(source):
    return re.sub(r'/\*.*?\*/', '', source, flags=re.S)


def renderer(name):
    start = re.search(r'^(?:async )?(?:function|const) ' + re.escape(name) + r'\b', APP, re.M)
    assert start, f'{name} is missing from app.mjs'
    following = re.search(r'^(?:async )?function \w+\(|^const \w+ ?=|^let \w+ =|^\$\(|^document\.',
                          APP[start.end():], re.M)
    return APP[start.start():start.end() + (following.start() if following else len(APP))]


def uses(text, primitive):
    return re.search(r'class="[^"]*(?<![\w-])' + re.escape(primitive) + r'(?![\w-])', text)


AI = section(HTML, 'ai-view')
INTEGRATIONS = section(HTML, 'integrations-view')
A65_MARKER = '#ai-view,#integrations-view{max-width:1360px'
# A6.6 appended the Aktivitas + Audit trail + Cadangan data block after this one, so A6.5's slice is
# now bounded above by the A6.6 marker - the same deliberate act A6.3-A6.5 performed for their
# predecessors. Without it every rule A6.6 writes would be read as an A6.5 rule.
A66_MARKER = '#activity-view,#audit-view,#backup-view{max-width:1360px'
A65_BLOCK = code_css(CSS)[code_css(CSS).index(A65_MARKER):code_css(CSS).index(A66_MARKER)]
A65_APP = APP[APP.index("const integrationHealth="):APP.index('// ===================== A6.4 ·')]

SUBMIT = renderer('submitAiInvestigation')
SHOW_AI = renderer('showAi')
HISTORY = renderer('loadAiHistory')
RESULT = renderer('renderAiInvestigation')
PROPOSAL_FORM = renderer('aiActionProposalForm')
PROPOSAL = renderer('aiActionProposalDialog')
LOAD_INTEGRATIONS = renderer('loadIntegrations')
SYSTEM = renderer('integrationSystem')
RUNS = renderer('integrationRunsDialog')
RUN = renderer('integrationRunDialog')
PAYROLL_CARD = renderer('payrollPeriodCard')

SNAPSHOT_HISTORIES = {
    'jubelioStockSnapshotsDialog': '/api/integrations/jubelio/finished-goods-snapshots?limit=100',
    'jubelioOrderSnapshotsDialog': '/api/integrations/jubelio/order-snapshots?limit=100',
    'jubelioReturnSnapshotsDialog': '/api/integrations/jubelio/return-snapshots?limit=100',
    'jubelioListingSnapshotsDialog': '/api/integrations/jubelio/listing-snapshots?limit=100',
    'mekariFinanceSnapshotsDialog': '/api/integrations/mekari/finance-snapshots?limit=100',
    'mekariPayableSnapshotsDialog': '/api/integrations/mekari/payable-snapshots?limit=100',
    'mekariReceivableSnapshotsDialog': '/api/integrations/mekari/receivable-snapshots?limit=100',
    'mekariPayrollSnapshotsDialog': '/api/integrations/mekari/payroll-snapshots?limit=100',
}
SUMMARIES = {
    'jubelioStockReconciliationDialog': '/api/integrations/jubelio/finished-goods-reconciliation',
    'jubelioOrderSummaryDialog': '/api/integrations/jubelio/order-summary',
    'jubelioReturnSummaryDialog': '/api/integrations/jubelio/return-summary',
    'jubelioListingSummaryDialog': '/api/integrations/jubelio/listing-summary',
    'mekariFinanceSummaryDialog': '/api/integrations/mekari/finance-summary',
    'mekariPayablesSummaryDialog': '/api/integrations/mekari/payables-summary',
    'mekariReceivablesSummaryDialog': '/api/integrations/mekari/receivables-summary',
    'mekariPayrollSummaryDialog': '/api/integrations/mekari/payroll-summary',
}
DETAILS = {
    'jubelioStockSnapshotDialog': '/api/integrations/jubelio/finished-goods-snapshots/',
    'jubelioOrderSnapshotDialog': '/api/integrations/jubelio/order-snapshots/',
    'jubelioReturnSnapshotDialog': '/api/integrations/jubelio/return-snapshots/',
    'jubelioListingSnapshotDialog': '/api/integrations/jubelio/listing-snapshots/',
    'mekariFinanceSnapshotDialog': '/api/integrations/mekari/finance-snapshots/',
    'mekariPayableSnapshotDialog': '/api/integrations/mekari/payable-snapshots/',
    'mekariReceivableSnapshotDialog': '/api/integrations/mekari/receivable-snapshots/',
    'mekariPayrollSnapshotDialog': '/api/integrations/mekari/payroll-snapshots/',
}


class TanyaBeeloftPageTest(unittest.TestCase):
    def test_the_section_is_a6_workspace_grammar(self):
        self.assertIn('<section id="ai-view" class="workspace-page" hidden>', AI)
        for primitive in ('workspace-heading', 'workspace-title', 'workspace-subtitle', 'workspace-subhead',
                          'workspace-section-title', 'field', 'field-label', 'field-grid', 'field-actions',
                          'filter-chip', 'command-bar', 'command-search', 'command-filter', 'record-list',
                          'action-primary', 'action-secondary'):
            with self.subTest(primitive=primitive):
                self.assertTrue(uses(AI, primitive))
        self.assertIn('<h1 class="workspace-title">Tanya Beeloft</h1>', AI)
        self.assertIn('Tanyakan kondisi bisnis dari ledger Beeloft dan simpan hasilnya sebagai investigasi.', AI)
        self.assertNotIn('Analisis operasional dari ledger sendiri.', AI)
        self.assertNotIn('page-heading', AI)
        # The local / read-only truth, both near the composer and on every rendered answer.
        self.assertIn('Analisis berjalan lokal dan hanya membaca ledger Beeloft. Tidak ada data yang dikirim keluar.', AI)
        self.assertIn('Analisis lokal · tidak mengirim data keluar · hanya baca', RESULT)

    def test_it_is_not_a_chat_clone(self):
        text = code(AI + RESULT + SUBMIT).lower()
        for forbidden in ('avatar', 'bubble', 'typing', 'stream', 'model-picker', 'chat-', '>kirim<'):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, text)
        self.assertNotRegex(code(A65_APP), r'requestAnimationFrame|setInterval|setTimeout')

    def test_the_composer_is_unchanged(self):
        self.assertRegex(AI, r'<textarea id="ai-question" name="question" rows="3" required minlength="2" maxlength="1000"')
        self.assertIn('<label class="field-label" for="ai-question">Pertanyaan bisnis</label>', AI)
        self.assertIn('<form id="ai-form"', AI)
        self.assertIn('<button class="action-primary" id="ai-submit" type="submit">Analisis dan simpan</button>', AI)
        self.assertIn('<button type="button" id="ai-reauth" class="action-secondary" hidden>Masuk ulang</button>', AI)
        self.assertLess(AI.index('data-ai-question'), AI.index('id="ai-question"'), 'starters precede the question')
        self.assertLess(AI.index('id="ai-question"'), AI.index('details class="ai-assumptions"'))
        self.assertLess(AI.index('id="ai-results"'), AI.index('id="ai-history"'), 'the result precedes the history')

    def test_all_five_starters_are_preserved_and_only_fill(self):
        starters = re.findall(r'data-ai-question="([^"]+)">([^<]+)</button>', AI)
        self.assertEqual(starters, [
            ('SKU apa yang berisiko stockout?', 'Risiko stockout'),
            ('Apa yang menunggu approval?', 'Approval tertunda'),
            ('Order produksi mana yang terlambat?', 'Produksi terlambat'),
            ('Bagaimana kondisi margin?', 'Kondisi margin'),
            ('Apa prioritas hari ini?', 'Prioritas hari ini')])
        self.assertIn("document.querySelectorAll('[data-ai-question]').forEach(example=>example.onclick=()=>{\n"
                      "  $('ai-question').value=example.dataset.aiQuestion;$('ai-question').focus();\n});", APP)
        self.assertEqual(len(re.findall(r'type="button" class="filter-chip" data-ai-question', AI)), 5,
                         'a starter is a button, never a submit')

    def test_the_assumptions_are_a_closed_disclosure_with_unchanged_constraints(self):
        self.assertIn('<details class="ai-assumptions"><summary>Asumsi analisis</summary>', AI)
        self.assertIn("form.querySelector('details.ai-assumptions').open=false;", SHOW_AI)
        expected = {
            'as_of': 'type="date" required>',
            'window_days': 'type="number" required min="7" max="90" step="1" value="28">',
            'lead_time_days': 'type="number" required min="1" max="180" step="1" value="14">',
            'review_period_days': 'type="number" required min="1" max="180" step="1" value="30">',
            'safety_stock_days': 'type="number" required min="0" max="90" step="1" value="7">',
            'batch_multiple': 'type="number" required min="1" max="100000" step="1" value="1">',
        }
        for name, attrs in expected.items():
            with self.subTest(field=name):
                self.assertRegex(AI, r'name="' + name + r'" ' + re.escape(attrs))
        as_of = re.search(r'<input id="ai-as-of"[^>]*>', AI).group()
        self.assertNotIn('max=', as_of, 'as_of intentionally allows future dates')

    def test_activation_resets_exactly_as_before(self):
        for statement in ("if(guardPending())return;", "activateWorkspace('ai-brain');",
                          "aiTransaction=null;unresolved=false;modalBusy=false;",
                          "$('ai-results').replaceChildren();", "message('ai-message','');",
                          "if(!form.elements.as_of.value)form.elements.as_of.value=jakartaToday();",
                          "[...form.elements].forEach(control=>control.disabled=false);",
                          "$('ai-submit').textContent='Analisis dan simpan';$('ai-reauth').hidden=true;",
                          "loadAiHistory(true);"):
            with self.subTest(statement=statement):
                self.assertIn(statement, SHOW_AI)


class InvestigationSafetyTest(unittest.TestCase):
    def test_the_write_is_idempotent_and_actor_bound(self):
        for statement in ("storageKey=pendingKey(),actorId=user.id",
                          "aiTransaction=api.transaction('/api/ai/investigations',raw);",
                          "sessionStorage.setItem(storageKey,JSON.stringify({transaction:aiTransaction,",
                          "actor_id:actorId}));", "}else await sameActorGuard(actorId);",
                          "const report=await api.save(aiTransaction);", "clearPending(storageKey,aiTransaction);",
                          "unresolved=Boolean(error.uncertain||(unresolved&&denied));",
                          "if(!unresolved){clearPending(storageKey,aiTransaction);aiTransaction=null;}",
                          "lock(unresolved);reauth.hidden=!denied;",
                          "' Masuk ulang dengan akun yang sama untuk memastikan snapshot tidak digandakan.'",
                          "button.textContent=unresolved?'Coba ulang penyimpanan':'Analisis dan simpan';",
                          "button.disabled=true;button.textContent='Menganalisis…';modalBusy=true;"):
            with self.subTest(statement=statement[:60]):
                self.assertIn(statement, SUBMIT)
        self.assertNotIn('fetch(', SUBMIT, 'no direct fetch replaces the transaction path')
        self.assertIn("function pendingKey() { return 'beeloft.pending.' + user.id; }", APP)
        self.assertIn("if (identity && identity.id !== actorId) {", APP)

    def test_historical_evidence_stays_compatible(self):
        self.assertIn('function renderAiInvestigation(report,target,source=report.source_payload) {', RESULT)
        self.assertIn('{...source,investigation_id:report.id}', RESULT)
        for tolerant in ('(report.focus?.products||[])', '(report.focus?.orders||[])', '(report.facts||[])',
                         '(report.findings||[])', '(report.recommendations||[])', '(report.linked_actions||[])',
                         '(report.limitations||[])', 'report.feedback_summary||{helpful:0,not_helpful:0,respondents:0}'):
            with self.subTest(field=tolerant):
                self.assertIn(tolerant, RESULT)
        self.assertNotRegex(code(RESULT), r'api\.get\(', 'a stored investigation is never rebuilt from today')

    def test_labels_and_evidence_metadata_are_preserved(self):
        self.assertIn("{overview:'Ringkasan bisnis',production:'Kondisi produksi',stockout:'Risiko stockout',"
                      "approvals:'Antrean approval',margin:'Margin kontribusi'}", RESULT)
        self.assertIn("{high:'tinggi',medium:'sedang',low:'rendah'}", RESULT)
        self.assertIn("{critical:'Kritis',high:'Tinggi',medium:'Sedang',info:'Informasi'}", RESULT)
        self.assertIn("{sku:'SKU',order:'order',issue:'kendala',item:'item',material:'bahan',pcs:'pcs'}", RESULT)
        self.assertIn("row.unit==='IDR'?rupiah(String(row.value)):`${n(Number(row.value))} ${unit[row.unit]||row.unit}`", RESULT)
        self.assertNotRegex(code(RESULT), r'%|score|skor', 'confidence is never a percentage or a score')

    def test_recommendations_stay_unexecuted_and_gated(self):
        self.assertIn("const supported=new Set(['create_production_order','create_purchase_request']);", RESULT)
        self.assertIn("user.role!=='viewer'&&supported.has(row.kind)?", RESULT)
        self.assertIn("evidenceChip('warning','Perlu approval')", RESULT)
        self.assertIn('`Belum dijalankan · sumber ${e(row.source)}`', RESULT)
        self.assertIn("recommendation.kind==='create_production_order'", PROPOSAL_FORM)
        self.assertEqual(len(re.findall(r'create_(?:production_order|purchase_request)', code(PROPOSAL_FORM))), 1,
                         'the form has exactly the two branches it had')

    def test_feedback_is_append_only(self):
        self.assertIn("data-ai-feedback=\"helpful\">Jawaban membantu", RESULT)
        self.assertIn("data-ai-feedback=\"not_helpful\">Perlu diperbaiki", RESULT)
        self.assertIn("${n(feedback.helpful)} membantu · ${n(feedback.not_helpful)} perlu diperbaiki · ${n(feedback.respondents)} responden", RESULT)
        self.assertIn("'/api/ai/investigations/'+encodeURIComponent(report.id)+'/feedback'", RESULT)
        self.assertIn('Feedback tersimpan sebagai event append-only.', RESULT)

    def test_proposal_forms_keep_their_fields_and_truths(self):
        for field in ("aiProposalField('reference','Referensi order','text','required maxlength=\"160\"')",
                      "aiProposalField('title','Nama order','text','required maxlength=\"160\"')",
                      'name="owner_id" required', "aiProposalField('due_date','Target selesai','date','required')",
                      "aiProposalField('reference','Referensi PR','text','required maxlength=\"160\"')",
                      "aiProposalField('required_date','Tanggal kebutuhan','date','required')",
                      "aiProposalField('estimated_value','Estimasi total (Rp)','number','required min=\"0.01\" max=\"1000000000000\" step=\"0.01\"')"):
            with self.subTest(field=field[:50]):
                self.assertIn(field, PROPOSAL_FORM)
        self.assertIn("(await api.get('/api/users')).filter(row=>row.active&&row.role!=='viewer')", PROPOSAL_FORM)
        self.assertIn('Order baru dibuat hanya setelah admin menyetujui proposal dan rekomendasi masih sama.', PROPOSAL_FORM)
        self.assertIn('PR dibuat setelah admin menyetujui proposal; PR tersebut tetap masuk workflow approval purchasing.', PROPOSAL_FORM)
        self.assertIn("const common=form=>({...source,action_kind:recommendation.kind,", PROPOSAL_FORM)
        self.assertEqual(PROPOSAL_FORM.count("'/api/ai/action-proposals'"), 2)

    def test_proposal_decisions_keep_their_permissions_and_revision(self):
        self.assertIn("if(user.role==='admin'&&row.status==='submitted')decisions.push(['approved','Setujui dan jalankan'],['rejected','Tolak proposal']);", PROPOSAL)
        self.assertIn("if(row.status==='submitted'&&(user.role==='admin'||row.actor_id===user.id))decisions.push(['cancelled','Batalkan proposal']);", PROPOSAL)
        self.assertIn('status:decision,expected_revision:row.revision', PROPOSAL)
        self.assertIn('const executed=row.executed_entity_id?', PROPOSAL)
        self.assertIn("Tindakan selesai. ${production?'Order produksi':'Purchase request'} sudah dibuat.", PROPOSAL)
        self.assertIn("data-action=\"${production?'detail':'purchase-request'}\"", PROPOSAL)
        self.assertIn('Saat approval, sistem menghitung ulang rekomendasi dan membatalkan eksekusi bila sumber berubah', PROPOSAL)
        self.assertIn('Rekomendasi diperiksa ulang lalu tindakan dijalankan dalam satu transaksi.', PROPOSAL)

    def test_history_keeps_its_cursor_and_fence(self):
        self.assertIn("new URLSearchParams({limit:50,intent:values.intent,q:values.q.trim()})", HISTORY)
        self.assertIn("if(aiHistoryBefore)query.set('before',aiHistoryBefore);", HISTORY)
        self.assertIn("const current=()=>version===epoch&&request===aiHistoryRequest&&view==='ai';", HISTORY)
        self.assertIn('aiHistoryBefore=rows.at(-1)?.sequence||aiHistoryBefore;more.hidden=rows.length<50;', HISTORY)
        self.assertIn('>Muat investigasi sebelumnya</button>', AI)
        self.assertIn("Buka investigasi", HISTORY)
        self.assertRegex(AI, r'<input name="q" type="search" maxlength="160"')
        self.assertEqual(re.findall(r'<option value="(\w+)"', AI[AI.index('name="intent"'):AI.index('</select>', AI.index('name="intent"'))]),
                         ['all', 'overview', 'production', 'stockout', 'approvals', 'margin'])
        self.assertNotRegex(code(HISTORY), r'IntersectionObserver|oninput|addEventListener\(.input')
        # Three distinct empty conditions, three sentences.
        for sentence in ('Belum ada investigasi tersimpan.', 'Tidak ada investigasi yang cocok.', 'Tidak ada riwayat yang lebih lama.'):
            self.assertIn(sentence, HISTORY)


class IntegrasiPageTest(unittest.TestCase):
    def test_the_section_is_a6_workspace_grammar(self):
        self.assertIn('<section id="integrations-view" class="workspace-page" hidden>', INTEGRATIONS)
        self.assertIn('<h1 class="workspace-title">Integrasi</h1>', INTEGRATIONS)
        self.assertIn('Pantau kesehatan sinkronisasi, source of truth, dan snapshot vendor.', INTEGRATIONS)
        self.assertIn('id="integrations-refresh" type="button" class="action-quiet">Muat ulang status', INTEGRATIONS)
        self.assertIn('data-action="integration-runs" class="action-secondary">Riwayat sinkronisasi', INTEGRATIONS)
        for primitive in ('status-chip', 'record-row', 'info-panel', 'workspace-meta', 'utility-panel-title',
                          'field-error', 'error-state'):
            with self.subTest(primitive=primitive):
                self.assertTrue(uses(SYSTEM + LOAD_INTEGRATIONS + renderer('evidenceChip') + renderer('evidenceNote'), primitive))

    def test_the_endpoint_fence_and_refresh_are_unchanged(self):
        self.assertIn("const report=await api.get('/api/integrations');", LOAD_INTEGRATIONS)
        self.assertEqual(LOAD_INTEGRATIONS.count('api.get('), 1, 'no decorative fan-out')
        self.assertIn("const version=epoch,request=++integrationsRequest;", LOAD_INTEGRATIONS)
        self.assertIn("const current=()=>version===epoch&&request===integrationsRequest&&view==='integrations';", LOAD_INTEGRATIONS)
        self.assertIn("const holding=refresh&&integrationsReport&&markRefreshing('integrations-body');", LOAD_INTEGRATIONS)
        self.assertIn('integrationsReport=true;', LOAD_INTEGRATIONS)
        self.assertIn("settleRefreshing('integrations-body');integrationsReport=false;", LOAD_INTEGRATIONS)
        self.assertIn('id="integrations-retry" type="button"', LOAD_INTEGRATIONS)
        self.assertIn("$('integrations-retry').onclick=()=>loadIntegrations();", LOAD_INTEGRATIONS)
        self.assertIn('async function loadIntegrations(refresh = false) {', LOAD_INTEGRATIONS)

    def test_health_is_ledger_truth_in_five_states(self):
        self.assertIn("const integrationHealth={healthy:'Sehat',failed:'Gagal',stale:'Stale',never_synced:'Belum pernah sync',incomplete:'Belum lengkap'};", APP)
        self.assertIn('Status berasal dari ledger run aktual. Scope tanpa catatan tetap ditandai belum pernah sync; '
                      'sistem tidak menganggap koneksi vendor aktif hanya karena kontraknya tersedia.', LOAD_INTEGRATIONS)
        self.assertIn('Batas stale ${n(report.stale_after_minutes/60)} jam · diperiksa ${purchaseStamp(report.generated_at)}', LOAD_INTEGRATIONS)
        self.assertIn("const age=value=>value===null?'Belum ada run':value<60?`${n(value)} menit lalu`:`${n(Math.floor(value/60))} jam lalu`;", LOAD_INTEGRATIONS)
        self.assertNotRegex(code(A65_APP), r"'Connected'|'Disconnected'|Terhubung'|Terputus'")

    def test_systems_keep_source_of_truth_scopes_and_mapping(self):
        for fragment in ('Source of truth: ${e(scope.source_of_truth)} · inbound read-only',
                         'data-integration-system="${e(system.system)}"', 'data-integration-scope="${e(scope.scope)}"',
                         '${n(system.attention_count)} dari ${n(system.scopes.length)} scope perlu perhatian.',
                         ' · dibaca ${n(scope.latest_run.records_read)} · ditulis ${n(scope.latest_run.records_written)}',
                         'scope.latest_run?.error?', "'Rincian run terbaru'",
                         'Mapping SKU: ${n(system.product_mapping.mapped_products)} dari ${n(system.product_mapping.total_products)} terhubung · ${n(system.product_mapping.unmapped_products)} belum dipetakan.'):
            with self.subTest(fragment=fragment[:50]):
                self.assertIn(fragment, SYSTEM)
        self.assertNotRegex(code(SYSTEM).lower(), r'kelengkapan sinkronisasi|sync completeness|coverage stok')

    def test_every_direct_action_remains(self):
        for action, label in (('products', 'Buka Master SKU'), ('jubelio-order-summary', 'Order & penjualan Jubelio'),
                              ('jubelio-return-summary', 'Retur Jubelio'), ('jubelio-listing-summary', 'Listing Jubelio'),
                              ('jubelio-stock-reconciliation', 'Rekonsiliasi stok Jubelio'),
                              ('mekari-finance-summary', 'Keuangan Mekari'), ('mekari-payables-summary', 'Utang Mekari'),
                              ('mekari-receivables-summary', 'Piutang Mekari'), ('mekari-payroll-summary', 'Payroll Mekari'),
                              ('payroll-payment-reconciliation', 'Pembayaran payroll'),
                              ('payroll-accounting-reconciliation', 'Akuntansi payroll')):
            with self.subTest(label=label):
                self.assertIn(f"'{action}','{label}'", SYSTEM)
        self.assertIn('const utilities=system.product_mapping', SYSTEM)
        self.assertIn(":system.system==='mekari'", SYSTEM)


class LedgerAndSnapshotTest(unittest.TestCase):
    def test_the_run_ledger_keeps_50_before_and_its_guards(self):
        self.assertIn("new URLSearchParams({limit:50,system:values.system,status:values.status})", RUNS)
        self.assertIn("if(before)query.set('before',before);", RUNS)
        self.assertIn("let before=null,generation=0;", RUNS)
        self.assertIn("if(version!==epoch||modal!==dialogVersion||!$('dialog').open||request!==generation)return;", RUNS)
        self.assertIn('before=rows.at(-1)?.sequence||before;more.hidden=rows.length<50;', RUNS)
        self.assertIn('>Muat run sebelumnya</button>', RUNS)
        self.assertIn('<option value="jubelio">Jubelio</option><option value="mekari">Mekari</option>', RUNS)
        self.assertIn('<option value="succeeded">Berhasil</option><option value="failed">Gagal</option>', RUNS)
        self.assertIn('Ledger run dari connector atau worker integrasi. Catatan terbaru ditampilkan lebih dahulu dan tidak dapat diubah.', RUNS)

    def test_the_run_detail_keeps_every_field_and_its_duration(self):
        self.assertIn("const duration=Math.max(0,Math.round((new Date(row.finished_at)-new Date(row.started_at))/1000));", RUN)
        for label in ('Mulai', 'Selesai', 'Durasi', 'Record dibaca', 'Record ditulis', 'Cursor eksternal', 'Dicatat oleh',
                      'Dicatat pada', 'Alasan / konteks', 'Error connector'):
            with self.subTest(label=label):
                self.assertIn(f"'{label}'", RUN)

    def test_snapshot_endpoints_and_limits_are_unchanged(self):
        for name, endpoint in {**SNAPSHOT_HISTORIES, **SUMMARIES}.items():
            with self.subTest(renderer=name):
                self.assertIn(f"api.get('{endpoint}')", renderer(name))
        for name, endpoint in DETAILS.items():
            with self.subTest(renderer=name):
                self.assertIn(f"api.get('{endpoint}'+encodeURIComponent(batchId))", renderer(name))
        self.assertNotRegex(code(A65_APP), r"snapshots\?limit=(?!100')")

    def test_payroll_reconciliations_stay_25_offset(self):
        for name, endpoint in (('payrollPaymentReconciliationDialog', '/api/payroll-payment-reconciliation?'),
                               ('payrollAccountingReconciliationDialog', '/api/payroll-accounting-reconciliation?')):
            body = renderer(name)
            with self.subTest(renderer=name):
                self.assertIn(f"api.get('{endpoint}'+new URLSearchParams({{...values,limit:25,offset}}))", body)
                self.assertIn('offset+=report.items.length;more.hidden=offset>=report.total;', body)
                self.assertIn('>Muat batch berikutnya</button>', body)
                self.assertIn('if(request!==generation||version!==epoch||modal!==dialogVersion||!$(\'dialog\').open)return;', body)
        filter_ = renderer('payrollReconciliationFilter')
        self.assertIn('name="q" type="search" maxlength="160"', filter_)

    def test_business_truths_are_still_printed(self):
        for sentence in (
                'Perbandingan memakai available Jubelio (sellable dikurangi reserved) dan available ledger Beeloft. Snapshot tidak menulis atau menyesuaikan stok Beeloft.',
                'Unit dan penjualan kotor hanya menghitung order berstatus selesai. Snapshot ini read-only dan tidak membuat order produksi, reservasi, shipment, atau settlement Beeloft.',
                'Unit diterima hanya menghitung status diterima dan refund selesai. Nilai refund hanya menghitung status refund selesai. Snapshot ini tidak mengubah stok atau retur internal Beeloft.',
                'Snapshot ini hanya membaca listing vendor. Data ini tidak mengubah master produk, harga internal, atau stok Beeloft.',
                'Pendapatan bersih, laba kotor, laba bersih, dan posisi likuiditas dihitung dari angka snapshot. Mekari tetap menjadi sumber pencatatan akuntansi; layar ini tidak membuat jurnal atau pembayaran.',
                'Overdue dihitung terhadap tanggal posisi snapshot. Layar ini tidak membayar invoice, mengubah status vendor, atau membuat jurnal Mekari.',
                'Overdue dihitung terhadap tanggal posisi snapshot. Layar ini tidak menagih pelanggan, mengubah status invoice, atau membuat jurnal Mekari.',
                'Angka merupakan ringkasan agregat dari Mekari tanpa identitas karyawan.',
                'Approval Beeloft menyimpan otorisasi manajemen tanpa mengubah status Mekari, menjalankan pembayaran, atau membuat jurnal.',
                'Menghubungkan approval Beeloft terbaru dengan status pembayaran pada snapshot Mekari terbaru. Laporan ini tidak mengirim uang atau membuat jurnal.',
                'Mencocokkan payroll approved dan dibayar dengan metadata jurnal pada snapshot Mekari terbaru. Laporan ini hanya baca dan tidak membuat atau mem-posting jurnal.',
                'Connector worker harus mengirim snapshot sebelum ringkasan tersedia.'):
            with self.subTest(sentence=sentence[:50]):
                self.assertIn(sentence, A65_APP)
        for reason in ('posting_reversed', 'posting_unbalanced', 'posting_amount_mismatch', 'payment_source_missing',
                       'payment_financial_mismatch', 'payment_source_cancelled', 'payment_source_draft',
                       'source_missing', 'financial_mismatch', 'source_cancelled', 'source_draft'):
            self.assertIn(reason + ':', A65_APP)

    def test_payroll_gate_and_privacy_are_unchanged(self):
        self.assertIn("const canSubmit=user.role!=='viewer'&&row.status==='reviewing'&&(!approval||['rejected','cancelled'].includes(approval.status)||(approval.status==='approved'&&financialChange));", PAYROLL_CARD)
        self.assertIn("['period_start','period_end','currency','employee_count','gross_pay','employee_deductions','employer_contributions'].some(key=>row[key]!==approval.source[key])", PAYROLL_CARD)
        self.assertIn("approval.stale?' · sumber berubah':''", PAYROLL_CARD)
        self.assertNotRegex(code(A65_APP), r'employee_name|employee_id|nama karyawan')

    def test_no_write_or_sync_control_was_invented(self):
        text = code(A65_APP)
        for forbidden in ('Sync now', 'Sinkronkan', 'Impor', 'Kirim snapshot', 'Buat jurnal', 'Post jurnal', 'Perbaiki jurnal',
                          'Bayar invoice', 'Tagih', 'Jalankan payroll', 'Sesuaikan stok', 'Jalankan ulang'):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, text)
        # The only writes A6.5 renderers can reach are the ones that existed: the investigation
        # transaction, feedback, AI proposals and their decisions. Payroll approvals stay owned by
        # their own dialog and are only LINKED from the payroll card.
        self.assertEqual(len(re.findall(r'api\.(?:save|transaction)\(', text)), 2)
        targets = re.findall(r"'(/api/ai/[a-z\-]+)'", text)
        self.assertEqual(sorted(set(targets)), ['/api/ai/action-proposals', '/api/ai/investigations'])
        self.assertEqual(text.count('formDialog('), 4, 'feedback, two proposal forms, one decision form')
        self.assertNotRegex(text, r"api\.post\(")

    def test_quarantine_and_no_snapshot_are_first_class(self):
        self.assertIn("const quarantineLabel=(issue,unmapped='SKU belum dipetakan')=>issue==='unmapped'?unmapped:'Mapping tidak konsisten';", APP)
        self.assertIn("evidenceSection('Karantina identifier'", A65_APP)
        self.assertNotIn('<details', code(renderer('jubelioStockReconciliationDialog')), 'quarantine is never hidden in a disclosure')
        for name in SUMMARIES:
            with self.subTest(renderer=name):
                body = renderer(name)
                if name != 'jubelioStockReconciliationDialog':
                    self.assertRegex(body, r"if\(!report\.snapshot\)\{\$\('dialog-content'\)\.innerHTML=evidenceEmpty\(")
        self.assertIn('evidenceChip(succeeded?\'success\':\'warning\'', APP, 'quarantine is attention, not failure')

    def test_untrusted_text_stays_escaped(self):
        for fragment in ('${e(row.external_sku)} · ${e(row.external_id)}', 'e(row.detail)', "e(row.external_cursor||'tidak dicatat')",
                         '${e(row.reason)}', '${e(report.question)}', '${e(report.answer)}', '${e(row.question)}',
                         '${e(scope.latest_run.error)}', '${e(row.error)}', '${e(item.listing_title)}'):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, A65_APP)
        self.assertNotRegex(A65_APP, r'\$\{(?:row|item|order|report|scope|period)\.(?:reason|detail|error|question|answer|external_sku|external_cursor|listing_title|marketplace|supplier_name|customer_name)\}')


class ContainmentAndBudgetTest(unittest.TestCase):
    def test_every_selector_in_the_block_belongs_to_a65(self):
        allowed = ('#ai-', '#integrations-', '#integration-run-', '#payroll-payment-', '#payroll-accounting-',
                   '.ai-', '.investigation', '.integration-', '.evidence-', '#dialog-content>.evidence-block',
                   '#dialog-content .evidence-block', '#dialog-content>h3.investigation', '#ai-view', '#integrations-view')
        selectors = [part.strip() for match in re.finditer(r'([^{}]+)\{', A65_BLOCK)
                     for part in match.group(1).split(',') if part.strip() and not part.strip().startswith('@')]
        self.assertTrue(selectors)
        for selector in selectors:
            with self.subTest(selector=selector[-70:]):
                self.assertTrue(any(name in selector for name in allowed), f'{selector!r} is not an A6.5 surface')

    def test_no_primitive_is_redefined_and_no_earlier_phase_is_touched(self):
        for primitive in ('.record-row', '.record-list', '.metric-card', '.metric-strip', '.command-bar', '.data-surface',
                          '.detail-grid', '.status-chip', '.info-panel', '.utility-panel', '.field', '.attention-note',
                          '.empty-state', '.error-state', '.filter-chip', '.timeline'):
            with self.subTest(primitive=primitive):
                self.assertNotRegex(A65_BLOCK, r'(?m)^' + re.escape(primitive) + r'[^{,]*\{')
        for foreign in ('#board-view', '#detail-view', '#materials-view', '#products-view', '#people-view',
                        '#bundle-scan-view', '#finished-goods-scan-view', '#analytics-view', '#command-center',
                        '#approvals-view', '#audit-view', '#activity-view', '.workforce-screen', '.analytics-'):
            with self.subTest(foreign=foreign):
                self.assertNotIn(foreign, A65_BLOCK)

    def test_the_block_adds_no_material_and_no_motion(self):
        self.assertNotRegex(A65_BLOCK, r'backdrop-filter|filter\s*:\s*blur')
        self.assertNotRegex(A65_BLOCK, r'@keyframes|animation\s*:|transition\s*:')

    def test_the_frame_and_timer_budget_is_unchanged(self):
        self.assertEqual(len(re.findall(r'requestAnimationFrame\(', APP)), 6)
        self.assertEqual(len(re.findall(r'cancelAnimationFrame\(', APP)), 4)
        self.assertEqual(len(re.findall(r'setTimeout\(', APP)), 7)
        self.assertEqual(len(re.findall(r'setInterval\(', APP)), 0)
        self.assertNotRegex(code(A65_APP), r'EventSource|WebSocket|IntersectionObserver|setTimeout|setInterval|requestAnimationFrame')

    def test_the_shell_and_lens_are_untouched(self):
        for selector in ('.workspace-window', '.traffic-light', '.masthead', '.app-sidebar', '.nav-selection-lens',
                         '.sidebar-cta', 'body::before'):
            with self.subTest(selector=selector):
                self.assertNotIn(selector, A65_BLOCK)
        lens = APP[APP.index('const navigationSurface ='):APP.index('// Drawer mobile.')]
        self.assertIn('const navigationLensSpring = {mass:1, stiffness:520, damping:40};', lens)
        self.assertEqual(HTML.count('/static/workspace-primitives.css'), 1)

    def test_unrelated_sections_are_not_migrated_by_a65(self):
        # A6.6 migrated Aktivitas and Audit trail and A6.7 the three business queues. What A6.5
        # still owes is that none of those migrations lives in, or leaks through, its own block.
        for element in ('approvals-view', 'purchase-requests-view', 'marketing-budgets-view'):
            with self.subTest(section=element):
                self.assertIn('workspace-page', section(HTML, element))
                self.assertNotIn('#' + element, A65_BLOCK)
        for name in ('#approval-', '#pr-page-', '#marketing-budget-', '.queue-', '.request-'):
            with self.subTest(a67=name):
                self.assertNotIn(name, A65_BLOCK)


class VersionAndSchemaTest(unittest.TestCase):
    def test_the_version_is_aligned_everywhere(self):
        version = re.search(r'^version = "([^"]+)"', (ROOT / 'pyproject.toml').read_text(encoding='utf-8'), re.M).group(1)
        self.assertEqual(version, '0.113.0', 'A6.7 is the visible workspace milestone')
        self.assertIn(f'version="{version}"', (ROOT / 'beeloft' / 'api.py').read_text(encoding='utf-8'))
        contract = json.loads((ROOT / 'docs' / 'openapi.json').read_text(encoding='utf-8'))
        self.assertEqual(contract['info']['version'], version)
        self.assertEqual(len(contract['paths']), 221, 'A6.5 is presentation only')

    def test_the_schema_did_not_move(self):
        versions = [int(value) for path in (ROOT / 'beeloft').glob('*.sql')
                    for value in re.findall(r'PRAGMA user_version\s*=\s*(\d+)', path.read_text(encoding='utf-8'))]
        self.assertEqual(max(versions), 55)

    def test_no_backend_route_changed(self):
        from tempfile import TemporaryDirectory
        from beeloft.api import create_app
        contract = json.loads((ROOT / 'docs' / 'openapi.json').read_text(encoding='utf-8'))
        with TemporaryDirectory() as folder:
            live = create_app(Path(folder) / 'contract.sqlite3').openapi()
        self.assertEqual(contract['paths'], live['paths'])

    def test_the_documentation_exists(self):
        doc = ROOT / 'docs' / 'apple27-ai-integrations-modern-workspaces.md'
        self.assertTrue(doc.exists())
        text = doc.read_text(encoding='utf-8')
        for anchor in ('94e83d83235cb536e98dc3c4227eaabb7b340412', '0.111.0', 'ai-view', 'integrations-view',
                       'sameActorGuard', 'source_payload', 'A6.8'):
            with self.subTest(anchor=anchor):
                self.assertIn(anchor, text)


if __name__ == '__main__':
    unittest.main()
