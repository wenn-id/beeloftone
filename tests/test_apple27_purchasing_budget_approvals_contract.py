"""A6.7 - Permintaan pembelian + Budget marketing + Inbox approval: the static half of the contract.

A6.7 is presentation-only. What can break here is not a layout; it is a quietly weakened invariant:
a queue's default filter, its 25-row page, its `before` or `offset` cursor, its retry, its stale
fence or its replacement-only fade; a request sheet's role gates, its `expected_revision`, its
decision wording or its history; a form's field names and limits, and therefore its payload; the
Inbox's nine kinds and the context each one prints. Each of those is pinned below against the
source text, together with the containment of the A6.7 CSS block, the legacy boundary A6.7 was not
allowed to cross, the unchanged frame / timer budget, the untouched shell and the aligned version.

The migration allowance itself lives in tests/test_apple27_modern_workspace_foundation_contract.py,
which A6.7 widened to exactly the three sections and the named renderers. The behavioural half is
tests/browser_purchasing_budget_approvals_modern_workspaces.cjs.
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
API = (ROOT / 'beeloft' / 'api.py').read_text(encoding='utf-8')


def section(html, element_id):
    start = html.index(f'<section id="{element_id}"')
    depth = 0
    for match in re.finditer(r'<section\b|</section>', html[start:]):
        depth += 1 if match.group().startswith('<section') else -1
        if depth == 0:
            return html[start:start + match.end()]
    raise AssertionError(f'#{element_id} is not a closed section')


def code_css(source):
    return re.sub(r'/\*.*?\*/', '', source, flags=re.S)


def body(name):
    """One top-level function, from its declaration to the `}` that closes it at column zero."""
    start = re.search(r'^(?:async )?function ' + re.escape(name) + r'\(', APP, re.M).start()
    return APP[start:APP.index('\n}\n', start) + 2]


def between(start, end):
    return APP[APP.index(start):APP.index(end, APP.index(start))]


def selectors(block):
    """Every selector of a stylesheet slice, split on the commas that are not inside `:is(...)`."""
    found = []
    for match in re.finditer(r'([^{}]+)\{', block):
        prelude = match.group(1).strip()
        if not prelude or prelude.startswith('@'):
            continue
        depth, current = 0, ''
        for char in prelude:
            depth += (char == '(') - (char == ')')
            if char == ',' and depth == 0:
                found.append(current.strip()); current = ''
            else:
                current += char
        found.append(current.strip())
    return [item for item in found if item]


PURCHASE = section(HTML, 'purchase-requests-view')
BUDGETS = section(HTML, 'marketing-budgets-view')
INBOX = section(HTML, 'approvals-view')
GRAMMAR = between('// ===================== A6.7 · antrean keputusan', "$('purchase-requests').onclick")
CONTEXT = body('approvalContextHTML')
LOAD_APPROVALS = body('loadApprovals')
LOAD_BUDGETS = body('loadMarketingBudgets')
BUDGET_FORM = body('marketingBudgetForm')
BUDGET_SHEET = body('marketingBudgetRequestDialog')
LOAD_PRS = body('loadPurchaseRequests')
PR_FORM = body('purchaseRequestForm')
PR_SHEET = body('purchaseRequestDialog')
SUPPLIERS = body('suppliersDialog')
SUPPLIER_FORM = body('supplierForm')
PO_LIST = body('purchaseOrdersDialog')
MIGRATED = (GRAMMAR, CONTEXT, LOAD_APPROVALS, LOAD_BUDGETS, BUDGET_FORM, BUDGET_SHEET, LOAD_PRS, PR_FORM,
            PR_SHEET, SUPPLIERS, SUPPLIER_FORM, PO_LIST)
A67_MARKER = '#purchase-requests-view,#marketing-budgets-view,#approvals-view{max-width:1360px'
A67_BLOCK = code_css(CSS)[code_css(CSS).index(A67_MARKER):]
LEGACY_CLASSES = r'class="(?:[^"]* )?(?:page-heading|eyebrow|hint|actions|primary|filter-form|form-grid|form-actions|form-info|material-event|status-label|requirement-values)(?: [^"]*)?"'


class QueueSectionTest(unittest.TestCase):
    def test_the_three_sections_consume_a6_with_their_approved_identity(self):
        for markup, element, eyebrow, title, subtitle in (
                (PURCHASE, 'purchase-requests-view', 'Purchasing · permintaan pembelian', 'Permintaan pembelian',
                 'Ajukan kebutuhan bahan dan tinjau keputusannya sebelum dipesan ke pemasok.'),
                (BUDGETS, 'marketing-budgets-view', 'Marketing · pengajuan budget', 'Budget marketing',
                 'Ajukan plafon kampanye ke manajemen dan pantau keputusannya.'),
                (INBOX, 'approvals-view', 'Antrean keputusan · lintas domain', 'Inbox approval',
                 'Satu antrean untuk keputusan purchasing, finance, marketing, produksi, People, dan tindakan hasil investigasi.')):
            with self.subTest(section=element):
                self.assertIn(f'<section id="{element}" class="workspace-page" hidden>', markup)
                self.assertIn(f'<p class="workspace-eyebrow">{eyebrow}</p>', markup)
                self.assertIn(f'<h1 class="workspace-title">{title}</h1>', markup)
                self.assertIn(f'<p class="workspace-subtitle">{subtitle}</p>', markup)
                self.assertNotRegex(markup, LEGACY_CLASSES, 'the two languages never coexist on one surface')
                self.assertEqual(markup.count('aria-live="polite"'), 1)

    def test_every_id_and_entry_point_is_preserved(self):
        for markup, ids in ((PURCHASE, ('purchase-requests-back', 'purchase-requests-refresh', 'new-purchase-request', 'purchase-requests-body')),
                            (BUDGETS, ('marketing-budgets-back', 'marketing-budgets-refresh', 'new-marketing-budget', 'marketing-budgets-body')),
                            (INBOX, ('approvals-back', 'approvals-refresh', 'approvals-body'))):
            for element in ids:
                with self.subTest(element=element):
                    self.assertIn(f'id="{element}"', markup)
        for wiring in ("$('purchase-requests').onclick = showPurchaseRequests;", "$('marketing-budgets').onclick = showMarketingBudgets;",
                       "$('approvals').onclick = showApprovals;", "$('approvals-refresh').onclick = () => loadApprovals();",
                       "$('purchase-requests-refresh').onclick = () => loadPurchaseRequests();",
                       "$('marketing-budgets-refresh').onclick = () => loadMarketingBudgets();",
                       "$('new-purchase-request').onclick = () => purchaseRequestForm(null);",
                       "$('new-marketing-budget').onclick = marketingBudgetForm;"):
            with self.subTest(wiring=wiring[:48]):
                self.assertIn(wiring, APP)

    def test_one_primary_action_per_page_and_quiet_utilities(self):
        self.assertIn('<button type="button" data-action="suppliers" class="action-quiet">Master pemasok</button>', PURCHASE)
        self.assertIn('<button type="button" data-action="purchase-orders" class="action-secondary">Daftar PO</button>', PURCHASE)
        self.assertIn('<button id="purchase-requests-refresh" type="button" class="action-quiet">Muat ulang PR</button>', PURCHASE)
        self.assertIn('<button id="new-purchase-request" class="action-primary" type="button" hidden>Buat PR</button>', PURCHASE)
        self.assertIn('<button type="button" data-action="approvals" class="action-quiet">Inbox approval</button>', BUDGETS)
        self.assertIn('<button id="marketing-budgets-refresh" type="button" class="action-quiet">Muat ulang</button>', BUDGETS)
        self.assertIn('<button id="new-marketing-budget" class="action-primary" type="button" hidden>Ajukan budget</button>', BUDGETS)
        self.assertIn('<button id="approvals-refresh" type="button" class="action-secondary">Muat ulang inbox</button>', INBOX)
        for markup in (PURCHASE, BUDGETS, INBOX):
            self.assertLessEqual(markup.count('action-primary'), 1)
        # Creating stays closed to viewers, exactly as before.
        self.assertIn("$('new-purchase-request').hidden = user.role === 'viewer';", body('showPurchaseRequests'))
        self.assertIn("$('new-marketing-budget').hidden = user.role === 'viewer';", body('showMarketingBudgets'))

    def test_every_word_of_page_context_is_kept(self):
        self.assertIn('Pengajuan bahan untuk ditinjau. PR yang disetujui belum menjadi pesanan ke pemasok;', PURCHASE)
        self.assertIn('Daftar plafon kampanye yang diajukan ke manajemen. Persetujuan belum mencatat realisasi belanja.', BUDGETS)
        self.assertIn('Nilai serta konteks asal tetap dibaca dari ledger domainnya.', INBOX)
        for text in (LOAD_APPROVALS, LOAD_BUDGETS, LOAD_PRS):
            self.assertNotIn('class="hint"', text, 'the scope notes moved to the static sections')

    def test_the_inbox_domain_lists_are_one_quiet_labelled_group(self):
        group = re.search(r'<div class="queue-sources" role="group" aria-labelledby="approvals-sources-label">(.*?)</div>', INBOX).group(1)
        self.assertIn('<span id="approvals-sources-label" class="workspace-meta">Daftar asal</span>', group)
        self.assertEqual(re.findall(r'<button type="button" data-action="([^"]+)" class="action-quiet">([^<]+)</button>', group),
                         [('purchase-requests', 'Semua PR'), ('marketing-budgets', 'Semua budget marketing'),
                          ('workforce-requests', 'Permintaan People'), ('mekari-payroll-summary', 'Payroll Mekari')])

    def test_the_list_hosts_keep_exactly_the_motion_contract_class(self):
        for text, host in ((LOAD_APPROVALS, 'approval-list'), (LOAD_BUDGETS, 'marketing-budget-list'), (LOAD_PRS, 'pr-page-list')):
            with self.subTest(host=host):
                self.assertIn(f'<div id="{host}" class="list-host">', text)
                self.assertIn(f"queueAppend('{host}',", text)
                self.assertNotIn('appendRows(', text, 'rows join one record list instead of the host')
                self.assertEqual(text.count('playEntryMotion('), 1)
                self.assertIn(f"if(replacing)playEntryMotion($('{host}'),'--motion-base');", text)


class InboxTest(unittest.TestCase):
    def test_the_request_contract_is_unchanged(self):
        self.assertIn("api.get('/api/approvals?'+new URLSearchParams({limit:25,offset,status:$('approval-status').value,kind:$('approval-kind').value}))", LOAD_APPROVALS)
        self.assertEqual(LOAD_APPROVALS.count('api.get('), 1, 'one request per load, no summary call was added')
        self.assertIn("$('approval-status').value='pending';", LOAD_APPROVALS)
        self.assertIn("$('approval-kind').value='all';", LOAD_APPROVALS)
        self.assertIn('offset+=rows.length;button.hidden=rows.length<25;button.textContent=\'Muat approval berikutnya\';', LOAD_APPROVALS)
        self.assertIn("button.hidden=false;button.textContent='Coba lagi';", LOAD_APPROVALS)
        self.assertIn("message('approval-error',error.message,true);clearPageLoading('approval-list');", LOAD_APPROVALS)
        self.assertIn("const current=()=>version===epoch&&request===approvalsRequest&&view==='approvals';", LOAD_APPROVALS)
        self.assertIn('if(!current()||gen!==generation)return;', LOAD_APPROVALS)
        self.assertIn("$('approval-status').onchange=$('approval-kind').onchange=()=>load(true);", LOAD_APPROVALS)
        self.assertIn("$('approval-filter').onsubmit=event=>{event.preventDefault();load(true);};", LOAD_APPROVALS)
        self.assertIn('approvalsRendered=null;', LOAD_APPROVALS)
        self.assertIn('const replacing=approvalsRendered!==null&&approvalsRendered!==rendered;', LOAD_APPROVALS)
        self.assertIn('@app.get("/api/approvals", tags=["Approvals"])', API)

    def test_status_and_kind_vocabulary(self):
        self.assertEqual(re.findall(r'<option value="([^"]+)">([^<]+)</option>', LOAD_APPROVALS.split('id="approval-status"')[1].split('</select>')[0]),
                         [('pending', 'Menunggu keputusan'), ('all', 'Semua status'), ('approved', 'Disetujui'),
                          ('rejected', 'Ditolak'), ('cancelled', 'Dibatalkan')])
        self.assertIn('<option value="all">Semua jenis</option>${Object.entries(approvalKind).map(([value,label])=>option(value,label)).join(\'\')}', LOAD_APPROVALS)
        kinds = dict(re.findall(r"(\w+):'([^']+)'", re.search(r'const approvalKind = \{(.*?)\};', APP).group(1)))
        self.assertEqual(list(kinds), ['purchase_request', 'purchase_order', 'supplier_payment', 'marketing_budget', 'production_change',
                                       'workforce_leave', 'workforce_overtime', 'payroll_batch', 'ai_action'])
        self.assertEqual(set(re.findall(r'(\w+):\'', re.search(r'const queueGlyph = \{(.*?)\};', GRAMMAR, re.S).group(1))), set(kinds),
                         'every kind has a glyph, and no glyph invents a kind')

    def test_records_are_escaped_and_open_the_domain_detail(self):
        for fragment in ('primary:e(row.reference),secondary:e(row.title)',
                         "queueChip('neutral',approvalKind[row.kind])+queueChip(approvalTone[row.status]||'neutral',approvalStatus[row.status])",
                         'stamp:`${e(row.actor_name)} · ${purchaseStamp(row.created_at)}`',
                         '`<p class="data-meta reason queue-reason">${e(row.reason)}</p>`',
                         '(row.amount?queueAmount(row.amount):\'\')',
                         'data-action="${approvalAction[row.kind]}" data-id="${e(row.id)}" aria-label="Rincian approval ${e(row.reference)}">Buka approval</button>',
                         'hook:` data-approval-kind="${e(row.kind)}"`'):
            with self.subTest(fragment=fragment[:50]):
                self.assertIn(fragment, LOAD_APPROVALS)
        self.assertIn("queueState('empty','Tidak ada approval yang sesuai filter.'", LOAD_APPROVALS)
        self.assertIn("queueState('loading','Memuat approval…')", LOAD_APPROVALS)

    def test_every_kind_keeps_its_context_sentence(self):
        for fragment in ('`Dibutuhkan ${date(row.context.required_date)} · ${n(row.context.line_count)} bahan`',
                         '`Perkiraan datang ${date(row.context.expected_date)} · ${n(row.context.line_count)} bahan`',
                         '`Invoice ${e(row.context.invoice_reference)} · jatuh tempo ${date(row.context.due_date)}`',
                         '`${e(row.context.channel)} · ${date(row.context.start_date)}–${date(row.context.end_date)}`',
                         "· ${n(row.context.days)} hari`", '· ${e(minuteQty(row.context.overtime_minutes))}`',
                         "karyawan${row.context.stale?' · sumber berubah':''}`", 'line(e(row.context.recommendation_title))',
                         '`Target ${date(row.context.old_due_date)} → ${date(row.context.new_due_date)}`',
                         '`PIC ${e(row.context.old_owner_name)} → ${e(row.context.new_owner_name)}`',
                         "${svgIcon('alert-triangle','icon-sm')}<span>Permintaan sudah stale.</span>"):
            with self.subTest(fragment=fragment[:50]):
                self.assertIn(fragment, CONTEXT)
        self.assertNotIn('status-label', CONTEXT)

    def test_decisions_still_refresh_the_queue_that_owns_them(self):
        success = body('formDialog')
        for line in ("if (view === 'approvals') reloadApprovals();", "if (view === 'purchase-requests') reloadPurchaseRequests();",
                     "if (view === 'marketing-budgets') reloadMarketingBudgets();"):
            self.assertIn(line, success)


class BudgetTest(unittest.TestCase):
    def test_the_request_contract_is_unchanged(self):
        self.assertIn("api.get('/api/marketing-budget-requests?'+new URLSearchParams({limit:25,status:$('marketing-budget-status').value,...(before?{before}:{})}))", LOAD_BUDGETS)
        self.assertEqual(LOAD_BUDGETS.count('api.get('), 1)
        self.assertIn("before=rows.at(-1)?.sequence;button.hidden=rows.length<25;button.textContent='Muat pengajuan berikutnya';", LOAD_BUDGETS)
        self.assertIn("button.hidden=false;button.textContent='Coba lagi';", LOAD_BUDGETS)
        self.assertIn("const current=()=>version===epoch&&request===marketingBudgetsRequest&&view==='marketing-budgets';", LOAD_BUDGETS)
        self.assertIn("$('marketing-budget-status').onchange=()=>load(true);", LOAD_BUDGETS)
        self.assertEqual(re.findall(r'<option value="([^"]+)">([^<]+)</option>', LOAD_BUDGETS),
                         [('all', 'Semua status'), ('submitted', 'Menunggu keputusan'), ('approved', 'Disetujui'),
                          ('rejected', 'Ditolak'), ('cancelled', 'Dibatalkan')])
        self.assertIn('aria-label="Rincian budget ${e(row.reference)}">Rincian budget</button>', LOAD_BUDGETS)
        self.assertIn("queueState('empty','Belum ada pengajuan budget yang sesuai filter.',", LOAD_BUDGETS)

    def test_the_sheet_keeps_every_gate_and_the_decision_body(self):
        self.assertIn("if(user.role==='admin'&&row.status==='submitted')buttons.push(['approved','Setujui budget'],['rejected','Tolak budget']);", BUDGET_SHEET)
        self.assertIn("if(row.status==='submitted'&&(user.role==='admin'||row.actor_id===user.id))buttons.push(['cancelled','Batalkan pengajuan']);", BUDGET_SHEET)
        self.assertIn('data-marketing-budget-decision="${status}"', BUDGET_SHEET)
        self.assertIn("formDialog(button.textContent,reasonField(),form=>({...Object.fromEntries(new FormData(form)),status:decision,expected_revision:row.revision}),", BUDGET_SHEET)
        self.assertIn("'/api/marketing-budget-requests/'+encodeURIComponent(row.id)+'/decisions',", BUDGET_SHEET)
        self.assertIn('`${row.reference} · ${rupiah(row.amount)}\\n${button.textContent}. Keputusan dan alasan tersimpan permanen.`', BUDGET_SHEET)
        self.assertIn("requestIdentity(`${e(row.reference)} · ${e(approvalStatus[row.status])}`,e(row.campaign_name),", BUDGET_SHEET)
        for fact in ("['Channel',e(row.channel)]", "['Periode kampanye',`${date(row.start_date)}–${date(row.end_date)}`]",
                     "['Nominal budget',e(rupiah(row.amount))]", "['Diajukan oleh',e(row.actor_name)]", "['Waktu pengajuan',purchaseStamp(row.created_at)]"):
            self.assertIn(fact, BUDGET_SHEET)
        self.assertIn("requestNote('Persetujuan hanya mengesahkan plafon dan belum mencatat belanja.','shield')", BUDGET_SHEET)
        self.assertIn("requestSection('Riwayat keputusan',requestHistory(row.history,approvalStatus))", BUDGET_SHEET)
        self.assertIn('data-action="marketing-budgets">Daftar budget</button>', BUDGET_SHEET)
        self.assertIn('data-action="approvals">Inbox approval</button>', BUDGET_SHEET)
        self.assertIn("if(version!==epoch||modal!==dialogVersion||!$('dialog').open)return;", BUDGET_SHEET)

    def test_the_form_keeps_every_name_limit_and_the_payload(self):
        for field in ("requestField('reference','Referensi pengajuan','text','required maxlength=\"160\"')",
                      "requestField('campaign_name','Nama kampanye','text','required maxlength=\"160\"')",
                      "requestField('channel','Channel marketing','text','required maxlength=\"160\"')",
                      "requestField('start_date','Tanggal mulai','date','required')",
                      "requestField('end_date','Tanggal selesai','date','required')",
                      "requestField('amount','Nominal budget (Rp)','number','required min=\"0.01\" max=\"1000000000000\" step=\"0.01\"')",
                      "requestTextarea('objective','Objective kampanye','required maxlength=\"1000\"')+reasonField()"):
            with self.subTest(field=field[:40]):
                self.assertIn(field, BUDGET_FORM)
        self.assertIn("form=>Object.fromEntries(new FormData(form)), '/api/marketing-budget-requests',", BUDGET_FORM)
        self.assertIn("'Approval mengesahkan plafon kampanye. Realisasi belanja, invoice platform, dan jurnal keuangan dicatat di sistem lain sampai integrasinya tersedia.'", BUDGET_FORM)


class PurchasingTest(unittest.TestCase):
    def test_the_request_contract_is_unchanged(self):
        self.assertIn("api.get('/api/purchase-requests?'+new URLSearchParams({limit:25,status:$('pr-page-status').value,...(before?{before}:{})}))", LOAD_PRS)
        self.assertEqual(LOAD_PRS.count('api.get('), 1)
        self.assertIn("before=rows.at(-1)?.sequence;button.hidden=rows.length<25;button.textContent='Muat PR berikutnya';", LOAD_PRS)
        self.assertIn("button.hidden=false;button.textContent='Coba muat PR lagi';", LOAD_PRS)
        self.assertIn("const current=()=>version===epoch&&request===purchaseRequestsRequest&&view==='purchase-requests';", LOAD_PRS)
        self.assertIn("$('pr-page-status').onchange=()=>load(true);", LOAD_PRS)
        self.assertIn("<option value=\"all\">Semua status</option>${Object.entries(purchaseStatus).map(([value,label])=>option(value,label)).join('')}", LOAD_PRS)
        self.assertIn('aria-label="Status PR"', LOAD_PRS)
        self.assertIn('aria-label="Rincian ${e(p.reference)}">Rincian PR</button>', LOAD_PRS)
        self.assertIn("secondary:`${e(p.order_reference || 'Permintaan umum')} · dibutuhkan ${date(p.required_date)}`", LOAD_PRS)
        self.assertIn("queueAmount(p.estimated_value,'estimasi total')", LOAD_PRS)
        self.assertIn("queueState('empty','Belum ada PR yang sesuai filter.',", LOAD_PRS)
        self.assertIn("const purchaseStatus = {submitted:'Menunggu keputusan',approved:'Disetujui',rejected:'Ditolak',cancelled:'Dibatalkan'};", APP)

    def test_the_sheet_keeps_every_gate_and_the_decision_body(self):
        self.assertIn("if(user.role==='admin' && p.status==='submitted')decisions.push(['approved','Setujui PR'],['rejected','Tolak PR']);", PR_SHEET)
        self.assertIn("if((user.role==='admin' && ['submitted','approved'].includes(p.status) && !p.purchase_orders.some(po=>!['cancelled','rejected'].includes(po.status))) ||\n"
                      "       (user.role==='operator' && p.actor_id===user.id && p.status==='submitted'))decisions.push(['cancelled','Batalkan PR']);", PR_SHEET)
        self.assertIn("const ordering=user.role!=='viewer' && p.status==='approved' && !p.purchase_orders.some(po=>!['cancelled','rejected'].includes(po.status));", PR_SHEET)
        self.assertIn('data-action="new-purchase-order" data-id="${e(id)}">Buat PO dari PR</button>', PR_SHEET)
        self.assertIn('data-pr-decision="${status}"', PR_SHEET)
        self.assertIn("formDialog(button.textContent,reasonField(),form=>({...Object.fromEntries(new FormData(form)),status:button.dataset.prDecision,expected_revision:p.revision}),", PR_SHEET)
        self.assertIn("'/api/purchase-requests/'+encodeURIComponent(id)+'/decisions',", PR_SHEET)
        self.assertIn('Keputusan beserta alasan akan tersimpan. Pengajuan yang ditolak atau dibatalkan tidak dapat dibuka kembali.', PR_SHEET)
        self.assertIn("requestIdentity(`${e(p.reference)} · ${e(purchaseStatus[p.status])}`,e(p.order_reference || 'Permintaan umum'),", PR_SHEET)
        for fact in ("['Dibutuhkan',date(p.required_date)]", "['Estimasi total',e(rupiah(p.estimated_value))]", "['Bahan diminta',`${n(p.lines.length)} bahan`]"):
            self.assertIn(fact, PR_SHEET)
        self.assertIn('${e(l.code)} · ${e(l.name)}', PR_SHEET)
        self.assertIn('${e(materialQty(l.quantity,l.unit))}', PR_SHEET)
        self.assertIn('Persetujuan dicatat oleh admin, termasuk pengajuan sendiri. Belum ada aturan batas nilai. Lihat PO terkait di bawah; '
                      'PR dengan PO ditutup sudah final; PO aktif harus dibatalkan sebelum PR.', PR_SHEET)
        self.assertIn('data-action="purchase-order" data-id="${e(po.id)}" aria-label="Buka PO ${e(po.reference)}">Buka PO</button>', PR_SHEET)
        for navigation in ('data-action="purchase-request" data-id="${e(id)}">Muat ulang rincian PR</button>',
                           'data-action="purchase-requests">Semua PR</button>', 'data-action="approvals">Inbox approval</button>'):
            self.assertIn(navigation, PR_SHEET)
        self.assertIn("requestSection('Riwayat keputusan',requestHistory(p.history,purchaseStatus))", PR_SHEET)
        self.assertIn("if(version!==epoch || modal!==dialogVersion || !$('dialog').open)return;", PR_SHEET)

    def test_the_form_keeps_every_name_limit_rule_and_the_payload(self):
        for field in ("requestField('reference','Referensi PR','text','required maxlength=\"160\"')",
                      "requestField('required_date','Tanggal dibutuhkan','date','required')",
                      '<select name="order_id" id="pr-order"><option value="">Permintaan umum</option>',
                      "requestField('estimated_value','Estimasi total (Rp)','number','required min=\"0.01\" max=\"1000000000000\" step=\"0.01\"')",
                      '<div id="pr-lines"></div>', 'id="pr-add" class="action-secondary">Tambah bahan PR</button>', '+reasonField(),'):
            with self.subTest(field=field[:40]):
                self.assertIn(field, PR_FORM)
        # The collector, the duplicate rule, the null order and the line limits are the legacy ones.
        self.assertIn("[...form.querySelectorAll('#pr-lines .bom-line')].map(row=>({material_id:row.querySelector('select').value,quantity:row.querySelector('input').value}))", PR_FORM)
        self.assertIn("throw new Error('Gabungkan bahan yang sama menjadi satu baris.');", PR_FORM)
        self.assertIn('return {...data,order_id:data.order_id || null,lines};', PR_FORM)
        self.assertIn("if($('pr-lines').children.length>=100)return;", PR_FORM)
        self.assertIn("notify('PR memerlukan minimal satu bahan.')", PR_FORM)
        self.assertIn("row.className='bom-line';", PR_FORM)
        self.assertIn('type="number" required max="1000000"', PR_FORM)
        self.assertIn("input.step=input.min=materials.find(m=>m.id===select.value).unit==='pcs'?'1':'0.001';", PR_FORM)
        self.assertIn('Tambahkan master bahan sebelum mengajukan pembelian.', PR_FORM)
        self.assertIn("'Isi jumlah yang diajukan dan estimasi total seluruh bahan dalam rupiah. Pengajuan langsung menunggu keputusan admin. "
                      "Periksa PR terbuka sebelum membuat permintaan tambahan; PR tidak mengurangi angka kekurangan bahan.'", PR_FORM)
        self.assertIn("if(orderId)$('pr-order').value=orderId;", PR_FORM)

    def test_the_supplier_master_and_form(self):
        self.assertIn("requestNote('Identitas pemasok yang dipakai saat membuat PO.')", SUPPLIERS)
        self.assertIn("secondary:e(s.contact || 'Kontak belum diisi')", SUPPLIERS)
        self.assertIn("${e(s.address || 'Alamat belum diisi')}", SUPPLIERS)
        self.assertIn('<p class="empty-state-title">Belum ada pemasok.</p>', SUPPLIERS)
        self.assertIn("user.role==='admin'?'<button type=\"button\" class=\"action-primary\" data-action=\"new-supplier\">Tambah pemasok</button>':''", SUPPLIERS)
        self.assertIn("primary:`${e(s.code)} · ${e(s.name)}`", SUPPLIERS)
        self.assertNotIn('status-chip', SUPPLIERS, 'master data has no status to invent')
        for field in ("requestField('code','Kode pemasok','text','required maxlength=\"160\"')",
                      "requestField('name','Nama pemasok','text','required maxlength=\"160\"')",
                      "requestField('contact','Kontak pemasok','text','maxlength=\"500\"')",
                      "requestTextarea('address','Alamat pemasok','maxlength=\"1000\"')+reasonField()"):
            self.assertIn(field, SUPPLIER_FORM)
        self.assertIn("form=>Object.fromEntries(new FormData(form)),'/api/suppliers',", SUPPLIER_FORM)
        self.assertIn("'Kode dan identitas pemasok disimpan permanen. Jika keliru, buat kode pemasok baru untuk PO berikutnya.'", SUPPLIER_FORM)

    def test_the_po_list(self):
        self.assertIn("api.get('/api/purchase-orders?'+new URLSearchParams({limit:25,status:$('po-status').value,...(before?{before}:{})}))", PO_LIST)
        self.assertEqual(re.findall(r'<option value="([^"]+)">([^<]+)</option>', PO_LIST),
                         [('all', 'Semua status'), ('pending', 'Menunggu keputusan'), ('issued', 'Aktif'), ('rejected', 'Ditolak'),
                          ('closed', 'Ditutup'), ('cancelled', 'Dibatalkan')])
        self.assertIn("$('po-status').onchange=$('po-refresh').onclick=()=>load(true);$('po-more').onclick=()=>load();await load();", PO_LIST)
        self.assertIn('aria-label="Rincian PO ${e(p.reference)}">Rincian PO</button>', PO_LIST)
        self.assertIn("(p.lines.some(l=>l.held!=='0.000')?queueChip('warning','Menunggu QC'):'')", PO_LIST)
        self.assertIn("queueChip(poTone[p.status]||'neutral',poStatus[p.status])+queueChip(fulfillmentTone[p.fulfillment]||'neutral',fulfillmentLabel[p.fulfillment])", PO_LIST)
        self.assertIn("queueState('empty','Belum ada PO yang sesuai filter.',", PO_LIST)
        self.assertIn('PO menunggu keputusan sebelum aktif. Buka rincian untuk melihat approval, penerimaan bahan, dan sisa pesanan.', PO_LIST)
        self.assertIn("const poStatus={pending:'Menunggu keputusan',issued:'Aktif',rejected:'Ditolak',cancelled:'Dibatalkan',closed:'Ditutup'};", APP)
        self.assertIn("const fulfillmentLabel={pending:'Belum diterima',partial:'Diterima sebagian',received:'Diterima lengkap'};", APP)


class GrammarTest(unittest.TestCase):
    def test_a_queue_state_lives_inside_its_host_behind_the_state_hook(self):
        self.assertIn('`<div class="state queue-state">${kind===\'loading\'', GRAMMAR)
        # appendRows() and clearPageLoading() recognise a placeholder by `.state` and "Memuat".
        self.assertIn("if(first&&first.classList.contains('state')&&/^(Memuat|Menghitung|Menggabungkan)/.test(first.textContent.trim()))first.remove();", body('clearPageLoading'))

    def test_every_page_joins_one_record_list(self):
        append = body('queueAppend')
        self.assertIn("let list = host.querySelector(':scope>.record-list');", append)
        self.assertIn('if (!list) { host.replaceChildren();', append)
        self.assertIn("list.insertAdjacentHTML('beforeend',rows);", append)

    def test_chips_always_carry_a_dot_and_text(self):
        self.assertIn('const queueChip = (tone,label) => `<span class="status-chip status-chip-${tone}"><span class="status-dot" aria-hidden="true"></span>${e(label)}</span>`;', GRAMMAR)
        self.assertIn("const approvalTone={submitted:'info',pending:'info',approved:'success',rejected:'danger',cancelled:'neutral'};", APP)
        self.assertIn("const requestDecisionWeight = {approved:'action-primary',rejected:'action-destructive',cancelled:'action-secondary'};", GRAMMAR)

    def test_history_is_the_domain_order_and_escaped(self):
        history = GRAMMAR[GRAMMAR.index('const requestHistory'):GRAMMAR.index('const requestDecisionWeight')]
        self.assertNotRegex(history, r'\.sort\(|\.reverse\(', 'history stays newest first, as the domain returns it')
        for fragment in ('${e(event.created_at)}', '${e(labels[event.status])}', '${e(event.actor_name)}', '${e(event.reason)}'):
            self.assertIn(fragment, history)
        self.assertIn('Belum ada keputusan.', history)

    def test_fields_keep_the_legacy_names(self):
        self.assertIn('<input id="request-${name}" name="${name}" type="${type}" ${attrs}>', GRAMMAR)
        self.assertIn('<textarea id="request-${name}" name="${name}" ${attrs}></textarea>', GRAMMAR)
        self.assertIn('const reasonField = (label = \'Alasan / catatan\') =>', APP)
        self.assertIn('name="reason" required maxlength="1000"', APP[APP.index('const reasonField'):])

    def test_no_legacy_vocabulary_in_the_migrated_renderers(self):
        for text in MIGRATED:
            with self.subTest(renderer=text[:40]):
                self.assertNotRegex(text, LEGACY_CLASSES)
                # The legacy builders are called as `field('...')` and `+materialReason`; a comment
                # that names them is not a call.
                self.assertNotRegex(text, r"(?<![\w$`])materialReason\b(?!`)|(?<![\w$])field\('")


class BoundaryTest(unittest.TestCase):
    def test_the_fulfilment_and_foreign_dialogs_stay_legacy(self):
        # The workflows A6.7 LINKS to are not redesigned here; they still render the legacy
        # vocabulary, and an A6 name appearing in any of them fails this and the foundation test.
        for name in ('orderPurchaseRequestsDialog', 'purchaseOrderForm', 'purchaseOrderDialog', 'qualityIntakeDialog',
                     'renderSupplierReturns', 'renderPOClosure', 'purchaseReceiptsHTML', 'supplierPaymentForm',
                     'supplierPaymentRequestDialog', 'productionChangeRequestDialog', 'payrollApprovalRequestDialog'):
            with self.subTest(renderer=name):
                text = body(name)
                self.assertNotRegex(text, r'class="[^"]*(?<![\w-])(?:record-row|record-list|status-chip|detail-grid|queue-[\w-]+|request-[\w-]+)(?![\w-])')
        self.assertIn('const materialReason = \'<label class="full">Alasan / catatan<textarea name="reason" required maxlength="1000"></textarea></label>\';', APP)
        self.assertIn('<p class="form-info">${e(p.reference)} · ${poStatus[p.status]}</p>', body('purchaseOrderDialog'))

    def test_form_dialog_chrome_is_untouched(self):
        dialog = body('formDialog')
        self.assertIn('<fieldset id="form-fields"><div class="form-grid">${fields}</div></fieldset>', dialog)
        self.assertIn('<button class="primary" id="save-form" type="submit">Simpan pencatatan</button>', dialog)


class CssContainmentTest(unittest.TestCase):
    def test_the_block_reaches_only_a67_surfaces(self):
        allowed = ('#purchase-requests-', '#marketing-budgets-', '#approvals-', '#approval-', '#pr-page-', '#marketing-budget-',
                   '#po-', '.queue-', '.request-')
        found = selectors(A67_BLOCK)
        self.assertTrue(found)
        for selector in found:
            with self.subTest(selector=selector[-70:]):
                self.assertTrue(any(name in selector for name in allowed), f'{selector!r} is not an A6.7 surface')

    def test_no_primitive_legacy_rule_or_earlier_phase_is_redefined(self):
        for primitive in ('.record-row', '.record-list', '.metric-card', '.metric-icon', '.command-bar', '.command-filter',
                          '.status-chip', '.info-panel', '.detail-grid', '.detail-field', '.timeline', '.timeline-item',
                          '.empty-state', '.error-state', '.loading-state', '.field', '.action-primary', '.data-meta'):
            with self.subTest(primitive=primitive):
                self.assertNotRegex(A67_BLOCK, r'(?m)^' + re.escape(primitive) + r'[^{,]*\{')
        self.assertNotRegex(A67_BLOCK, r'(?<![\w-])\.(?:state|error|material-event|bom-line|form-grid|form-info)\s*[{,]',
                            'legacy rules are withdrawn by A6.7 scope, never edited')
        for foreign in ('#board-view', '#detail-view', '#materials-view', '#products-view', '#people-view', '#analytics-view',
                        '#ai-view', '#integrations-view', '#activity-view', '#audit-view', '#backup-view', '#command-center',
                        '.approval-', '.decision-', '.workspace-window', '.app-sidebar', '.sidebar-cta', '.nav-selection-lens'):
            with self.subTest(foreign=foreign):
                self.assertNotIn(foreign, A67_BLOCK)

    def test_the_block_adds_no_material_and_no_motion(self):
        self.assertNotRegex(A67_BLOCK, r'backdrop-filter|filter\s*:\s*blur')
        self.assertNotRegex(A67_BLOCK, r'@keyframes|animation\s*:|transition\s*:')

    def test_it_is_the_last_block(self):
        # Later phases bound this slice exactly as A6.7 bounded A6.6's.
        self.assertEqual(code_css(CSS).count(A67_MARKER), 1)


class GlobalTest(unittest.TestCase):
    def test_frame_timer_budget_and_no_polling(self):
        self.assertEqual(len(re.findall(r'requestAnimationFrame\(', APP)), 6)
        self.assertEqual(len(re.findall(r'cancelAnimationFrame\(', APP)), 4)
        self.assertEqual(len(re.findall(r'setTimeout\(', APP)), 7)
        self.assertEqual(len(re.findall(r'setInterval\(', APP)), 0)
        for text in MIGRATED:
            self.assertNotRegex(text, r'setTimeout|setInterval|requestAnimationFrame|EventSource|WebSocket|IntersectionObserver')

    def test_shell_and_lens_are_untouched(self):
        lens = APP[APP.index('const navigationSurface ='):APP.index('// Drawer mobile.')]
        self.assertIn('const navigationLensSpring = {mass:1, stiffness:520, damping:40};', lens)
        self.assertIn('<button id="approvals" class="primary sidebar-cta-button" type="button">Inbox approval</button>', HTML)
        self.assertIn('<button id="purchase-requests" class="nav-item" type="button">', HTML)
        self.assertIn('<button id="marketing-budgets" class="nav-item" type="button">', HTML)
        self.assertEqual(HTML.count('/static/workspace-primitives.css'), 1)

    def test_version_schema_and_routes(self):
        version = re.search(r'^version = "([^"]+)"', (ROOT / 'pyproject.toml').read_text(encoding='utf-8'), re.M).group(1)
        self.assertEqual(version, '0.113.0', 'A6.7 is the visible workspace milestone')
        self.assertIn(f'version="{version}"', API)
        contract = json.loads((ROOT / 'docs' / 'openapi.json').read_text(encoding='utf-8'))
        self.assertEqual(contract['info']['version'], version)
        self.assertEqual(len(contract['paths']), 221, 'A6.7 is presentation only')
        versions = [int(value) for path in (ROOT / 'beeloft').glob('*.sql')
                    for value in re.findall(r'PRAGMA user_version\s*=\s*(\d+)', path.read_text(encoding='utf-8'))]
        self.assertEqual(max(versions), 55)

    def test_documentation_exists(self):
        text = (ROOT / 'docs' / 'apple27-purchasing-budget-approvals-modern-workspaces.md').read_text(encoding='utf-8')
        for anchor in ('2173ce9db466cd5037c1ea60c6e70f3aec049cb5', '0.113.0', 'purchase-requests-view', 'marketing-budgets-view',
                       'approvals-view', 'expected_revision', 'list-host', 'A6.8'):
            self.assertIn(anchor, text)


if __name__ == '__main__':
    unittest.main()
