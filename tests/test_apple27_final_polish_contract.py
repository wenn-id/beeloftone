"""A6.8 - final consistency, polish and cleanup: the static half of the contract.

A6.8 is not a workspace migration. It owns four things the earlier phases explicitly deferred to
it, and this file pins each of them so A6.1-A6.7 cannot drift apart again:

  * the shared dialog chrome - `#dialog` with three semantic widths and a sticky heading, and
    `formDialog()`'s form chrome - modernised in CSS WITHOUT touching the dialog lifecycle, the
    write-safety path or a single compatibility hook;
  * the remaining high-visibility sheets A6.7 left legacy (PO fulfilment, incoming QC and supplier
    returns, supplier payment approval, production change approval, payroll approval, the
    order-scoped "PR untuk order ini"), migrated by NAME onto A6.7's request grammar;
  * ONE approval-status tone map, replacing the two conventions A6.3 and A6.5 left;
  * the legacy selectors earlier phases made inert, removed only after proving no shipped surface
    emits them.

The behavioural half is tests/browser_final_polish.cjs.
"""
import json
import re
import unittest
from pathlib import Path

from test_apple27_modern_workspace_foundation_contract import MIGRATED_RENDERERS, MIGRATED_SECTIONS, section

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / 'beeloft' / 'static'
APP = (STATIC / 'app.mjs').read_text(encoding='utf-8')
HTML = (STATIC / 'index.html').read_text(encoding='utf-8')
CSS = (STATIC / 'style.css').read_text(encoding='utf-8')
SHELL = (STATIC / 'workspace.css').read_text(encoding='utf-8')
PRIMITIVES = (STATIC / 'workspace-primitives.css').read_text(encoding='utf-8')
RUNTIME = {path.name: path.read_text(encoding='utf-8') for path in STATIC.iterdir()
           if path.suffix in ('.html', '.mjs', '.js')}


def code_css(source):
    return re.sub(r'/\*.*?\*/', '', source, flags=re.S)


def body(name):
    """One top-level function, from its declaration to the `}` that closes it at column zero."""
    start = re.search(r'^(?:async )?function ' + re.escape(name) + r'\(', APP, re.M).start()
    return APP[start:APP.index('\n}\n', start) + 2]


def const(name):
    """One top-level `const` declaration, up to the next top-level declaration."""
    start = re.search(r'^const ' + re.escape(name) + r'\b', APP, re.M).start()
    end = re.search(r'^(?:const|let|function|async function|\$\(|//|document)', APP[start + 1:], re.M)
    return APP[start:start + 1 + end.start()] if end else APP[start:]


A67_MARKER = '#purchase-requests-view,#marketing-budgets-view,#approvals-view{max-width:1360px'
A68_MARKER = '#dialog{--dialog-inset:12px;--dialog-pad:24px;'
A68_BLOCK = code_css(CSS)[code_css(CSS).index(A68_MARKER):]

# The renderers A6.8 migrated, by name. Nothing else joined the allow-list in this phase.
A68_RENDERERS = frozenset({
    'requestAttention', 'requestRecord', 'requestRecords', 'requestQuantities',
    'purchaseOrderDialog', 'purchaseReceiptsHTML', 'qualityIntakesHTML', 'renderPOClosure',
    'qualityIntakeDialog', 'renderSupplierReturns', 'supplierPaymentRequestDialog',
    'productionChangeRequestDialog', 'payrollApprovalRequestDialog', 'orderPurchaseRequestsDialog',
})
# The fulfilment FORMS, and representative Produksi child dialogs, that A6.8 deliberately left on
# legacy markup: formDialog()'s chrome is CSS, so they gained the modern shell unchanged.
STILL_LEGACY = ('purchaseOrderForm', 'purchaseReceiptForm', 'qualityDecisionForm', 'supplierPaymentForm',
                'payrollApprovalForm', 'moveForm', 'materialIssueForm', 'cuttingForm', 'finalQcForm')

# §100: every selector A6.8 removed, and why it was dead. Each is proven below against every shipped
# runtime source; the list is deliberately small and explicit, not an "unused CSS" parser.
REMOVED_SELECTORS = {
    # The pre-A6.1 Produksi board table (A6.1 moved the board onto `.data-surface`).
    'order-grid': 'pre-A6.1 board grid', 'table-head': 'pre-A6.1 board header row',
    'cell': 'pre-A6.1 board cell', 'cell-label': 'pre-A6.1 board cell label',
    'progress-cell': 'pre-A6.1 board progress cell', 'status-cell': 'pre-A6.1 board status cell',
    'progress-note': 'pre-A6.1 board progress note',
    # The pre-A6.1 order detail (A6.1 moved it onto `.detail-grid`, `.utility-panel`, `.timeline`).
    'detail-top': 'pre-A6.1 detail heading row', 'detail-meta': 'pre-A6.1 detail facts strip',
    'stages': 'pre-A6.1 stage strip', 'stage': 'pre-A6.1 stage tile', 'stage-number': 'pre-A6.1 stage index',
    'exceptions': 'pre-A6.1 rework/reject line', 'sku-balances': 'pre-A6.1 per-SKU balances',
    'order-settings': 'pre-A6.1 order action row', 'ledger-heading': 'pre-A6.1 board heading row',
    'issues-summary': 'pre-A6.1 issue button CLASS (the #issues-summary id and its A6.1 rules stay)',
    'issue-resolution': 'pre-A6.1 resolved-issue panel',
    # The pre-A6.2 batch inventory cards (A6.2 moved Bahan baku onto a data surface).
    'material-balance': 'pre-A6.2 batch balance figure', 'sku-block': 'pre-A6.1/A6.2 SKU and batch card',
    'sku-heading': 'pre-A6.1/A6.2 SKU card heading',
}
# Legacy class names that LOOK retired but are still load-bearing hooks, and so stay (§52).
RETAINED_HOOKS = {
    'state': 'appendRows() / clearPageLoading() / the shared-UI suite recognise a state by it',
    'list-host': 'the M6 motion contract reads it back after every replacement fade',
    'reason': 'pre-wrap for business text in legacy child dialogs and history rows',
    'line-input': 'the create-order line collector',
    'bom-line': 'the BOM and PR line collectors',
    'bundle-label': 'the printable bundle label and its print stylesheet',
    'material-event': 'Produksi / warehouse child dialogs and the PO price rows in purchaseOrderForm',
    'form-grid': "formDialog()'s field grid, read by every legacy form",
    'form-actions': "formDialog()'s footer",
    'form-info': "formDialog()'s context note",
}


class ShellTest(unittest.TestCase):
    def test_the_frozen_shell_markup_is_intact(self):
        for anchor in ('<div id="workspace-window" class="workspace-window">', 'id="window-close"',
                       'id="window-minimize"', 'id="window-fullscreen"',
                       '<span id="nav-selection-lens" class="nav-selection-lens" aria-hidden="true" hidden></span>',
                       'class="sidebar-cta"', 'class="masthead"', 'class="app-sidebar"', 'class="workspace-main"',
                       '<button id="approvals" class="primary sidebar-cta-button" type="button">Inbox approval</button>'):
            with self.subTest(anchor=anchor[:48]):
                self.assertIn(anchor, HTML)

    def test_the_lens_physics_are_unchanged(self):
        lens = APP[APP.index('const navigationSurface ='):APP.index('// Drawer mobile.')]
        self.assertIn('const navigationLensSpring = {mass:1, stiffness:520, damping:40};', lens)
        for constant in ('LENS_SETTLE_DISTANCE = .25', 'LENS_SETTLE_SPEED = 2', 'LENS_MAX_SUBSTEP = 1/120',
                         'LENS_MAX_FRAME = .032', 'LENS_STALL = .2', 'LENS_MORPH_MAX = .07', 'LENS_MORPH_SPEED = 3000'):
            with self.subTest(constant=constant):
                self.assertIn(constant, lens)

    def test_no_a6_or_a68_name_leaks_into_the_shell(self):
        for name in ('workspace-page', 'record-row', 'status-chip', 'request-', 'data-size', '#action-form', '#dialog{'):
            with self.subTest(name=name):
                self.assertNotIn(name, SHELL)
        for shell in ('.workspace-window', '.masthead', '.app-sidebar', '.sidebar-cta', '.nav-selection-lens',
                      '.nav-item', '.toolbar', '.workspace-main', 'body::before'):
            with self.subTest(shell=shell):
                self.assertNotIn(shell, A68_BLOCK)


class WorkspaceCoverageTest(unittest.TestCase):
    def test_every_primary_destination_is_a_modern_workspace(self):
        # Fifteen primary destinations (plus the order detail) are A6 workspace pages. The sixteenth,
        # Command Center, is the frozen A5 golden composition (tests/test_apple27_command_center_
        # golden_contract.py) and deliberately keeps its own hero grammar.
        primary = ('board-view', 'materials-view', 'products-view', 'people-view', 'bundle-scan-view',
                   'finished-goods-scan-view', 'analytics-view', 'ai-view', 'integrations-view', 'activity-view',
                   'audit-view', 'backup-view', 'purchase-requests-view', 'marketing-budgets-view', 'approvals-view')
        for element in primary + ('detail-view',):
            with self.subTest(section=element):
                self.assertIn(element, MIGRATED_SECTIONS)
                markup = section(HTML, element)
                self.assertRegex(markup, rf'<section id="{element}" class="workspace-page"')
                self.assertNotRegex(markup, r'class="[^"]*(?<![\w-])page-heading(?![\w-])')
        self.assertIn('<section id="command-center-view" class="command-center-view" hidden>', HTML)


class SharedDialogTest(unittest.TestCase):
    def test_one_dialog_element_with_its_hooks(self):
        self.assertEqual(HTML.count('<dialog id="dialog"'), 1)
        self.assertIn('<dialog id="dialog" aria-labelledby="dialog-title"><div class="dialog-heading"><h2 id="dialog-title"></h2>'
                      '<button id="close-dialog" class="quiet" type="button" aria-label="Tutup dialog">Tutup</button></div>'
                      '<div id="dialog-content"></div></dialog>', HTML)
        # No second dialog system: no sheet, drawer, popover framework or modal library.
        self.assertEqual(len(re.findall(r'<dialog\b', HTML)), 1, 'the one shared #dialog')
        self.assertNotRegex(APP, r'\bpopover=|showPopover\(|new\s+\w*Modal\(')

    def test_three_semantic_widths_assigned_deterministically(self):
        self.assertIn("const DIALOG_SIZES = ['compact','standard','wide'];", APP)
        opener = body('openDialog')
        self.assertIn("function openDialog(title, content, size = 'standard')", opener)
        self.assertIn("$('dialog').dataset.size = DIALOG_SIZES.includes(size) ? size : 'standard';", opener)
        form = body('formDialog')
        self.assertIn("const size = !fields || fields === materialReason || fields === reasonField() ? 'compact' : 'standard';", form)
        # `wide` belongs to the one fulfilment ledger, and nothing else asks for a width.
        self.assertEqual(re.findall(r"openDialog\([^;]*?,'(compact|wide)'\)", APP), ['wide'])
        self.assertIn("openDialog('Rincian PO',requestLoading('Memuat PO…'),'wide')", body('purchaseOrderDialog'))
        for rule in ('#dialog[data-size=compact]{width:min(520px,', '#dialog[data-size=wide]{width:min(880px,',
                     '#dialog:has(.workforce-screen){width:min(960px,'):
            with self.subTest(rule=rule):
                self.assertIn(rule, A68_BLOCK)
        self.assertIn('width:min(650px,calc(100vw - var(--dialog-inset)*2))', A68_BLOCK, 'standard stays 650px')

    def test_viewport_safe_px_insets_and_internal_scroll(self):
        self.assertIn('max-width:calc(100vw - var(--dialog-inset)*2)', A68_BLOCK)
        self.assertIn('max-height:min(90dvh,calc(100dvh - var(--dialog-inset)*2))', A68_BLOCK)
        self.assertIn('overflow-y:auto', A68_BLOCK)
        self.assertRegex(A68_BLOCK, r'@media\(max-width:650px\)\{[^@]*#dialog\{--dialog-inset:8px;--dialog-pad:16px\}')
        self.assertNotRegex(A68_BLOCK, r'--dialog-(?:inset|pad):[\d.]+rem', 'rem insets cost 320px/200% a third of the sheet')

    def test_the_heading_is_sticky_and_opaque_and_keeps_its_rule(self):
        heading = re.search(r'#dialog>\.dialog-heading\{([^}]*)\}', A68_BLOCK).group(1)
        for declaration in ('position:sticky', 'top:0', 'align-items:center', 'border-bottom:1px solid',
                            'background:var(--material-floating-solid)'):
            with self.subTest(declaration=declaration):
                self.assertIn(declaration, heading)

    def test_the_lifecycle_is_untouched(self):
        for fragment in ("$('close-dialog').onclick = closeDialog;",
                         "if (dialogCloseBlocked('Konfirmasi penyimpanan lewat tombol coba ulang sebelum menutup.')) return;",
                         "if (dialogCloseBlocked('Penyimpanan belum terkonfirmasi. Gunakan coba ulang.')) return;",
                         'dialogVersion++; closeDialogAnimated();',
                         "const target=dialogReturnFocus;dialogReturnFocus=null;if(target&&!target.hidden)target.focus();",
                         "if (!$('dialog').open) { resetDialogMotionState(); $('dialog').showModal(); }",
                         'modalBusy = false; unresolved = false;'):
            with self.subTest(fragment=fragment[:50]):
                self.assertIn(fragment, APP)

    def test_the_a68_block_adds_no_material_and_no_motion(self):
        self.assertNotRegex(A68_BLOCK, r'backdrop-filter|filter\s*:\s*blur')
        self.assertNotRegex(A68_BLOCK, r'@keyframes|animation\s*:|transition\s*:')

    def test_the_a68_block_reaches_only_its_own_surfaces(self):
        # ...plus the one Command Center regression the product sweep found (see RegressionTest).
        allowed = ('#dialog', '#action-form', '#form-fields', '#form-error', '#pr-error', '#pr-status', '.request-',
                   '#command-center-hero .hero-ring')
        for match in re.finditer(r'([^{}]+)\{', A68_BLOCK):
            prelude = match.group(1).strip()
            if not prelude or prelude.startswith('@'):
                continue
            for part in re.split(r',(?![^(]*\))', prelude):
                with self.subTest(selector=part.strip()[:70]):
                    self.assertTrue(any(name in part for name in allowed), f'{part!r} is not an A6.8 surface')
        # It never redefines an A6.0 primitive, and the primitives sheet did not change for A6.8.
        for primitive in ('.record-row{', '.record-list{', '.status-chip{', '.info-panel{', '.detail-grid{',
                          '.timeline-item{', '.field{', '.action-primary{', '.attention-note{'):
            with self.subTest(primitive=primitive):
                self.assertNotRegex(A68_BLOCK, r'(?m)^' + re.escape(primitive))
        for owned in ('data-size', '#action-form', '.request-', '#dialog'):
            self.assertNotIn(owned, code_css(PRIMITIVES))


class FormDialogTest(unittest.TestCase):
    FORM = body('formDialog')

    def test_every_compatibility_hook_keeps_its_name(self):
        for hook in ('<form id="action-form">', '<fieldset id="form-fields"><div class="form-grid">${fields}</div></fieldset>',
                     '<p class="error" id="form-error" role="alert" hidden></p>', '<div class="form-actions">',
                     '<button type="button" data-action="cancel-form">Batal</button>',
                     '<button type="button" id="reauth" hidden>Masuk ulang</button>',
                     '<button class="primary" id="save-form" type="submit">Simpan pencatatan</button>',
                     '<p class="form-info">${e(info)}</p>'):
            with self.subTest(hook=hook[:40]):
                self.assertIn(hook, self.FORM)
        # Action order: cancel, re-authenticate, the one primary.
        self.assertLess(self.FORM.index('cancel-form'), self.FORM.index('id="reauth"'))
        self.assertLess(self.FORM.index('id="reauth"'), self.FORM.index('id="save-form"'))

    def test_write_safety_is_unchanged(self):
        for fragment in ('if (!transaction) transaction = api.transaction(path, collect(event.currentTarget));',
                         'sessionStorage.setItem(storageKey, JSON.stringify({transaction, title, info, actor_id: actorId}));',
                         'if (initial || unresolved) await sameActorGuard(actorId);',
                         'const result = await api.save(transaction);',
                         'clearPending(storageKey, transaction);',
                         "unresolved = Boolean(error.uncertain || (unresolved && denied));",
                         "$('form-fields').disabled = unresolved;",
                         "button.textContent = unresolved ? 'Coba ulang penyimpanan' : 'Simpan pencatatan';",
                         "$('reauth').hidden = !denied;",
                         "$('reauth').onclick = () => reauthenticate('form-error');",
                         "if (initial) { unresolved = true; $('form-fields').disabled = true; $('save-form').textContent = 'Coba ulang penyimpanan'; }"):
            with self.subTest(fragment=fragment[:60]):
                self.assertIn(fragment, self.FORM)
        self.assertIn("function guardPending() { const pending = readPending(); if (pending) { recover(pending); return true; } return false; }", APP)

    def test_the_chrome_is_css_scoped_to_the_one_form(self):
        for selector in ('#action-form>.form-info{', '#action-form .form-grid{', '#action-form>.form-actions{', '#form-error{'):
            with self.subTest(selector=selector):
                self.assertIn(selector, A68_BLOCK)
        # Labels stay visible: the legacy `<label>Text<control></label>` is restyled, never hidden.
        self.assertNotRegex(A68_BLOCK, r'label[^{]*\{[^}]*(?:display:none|visually-hidden|font-size:0)')
        # A6 fields inside the same grid are left to A6.0.
        self.assertIn(':not(.field>*)', A68_BLOCK)


class RemainingSheetsTest(unittest.TestCase):
    def test_exactly_the_a68_renderers_joined_the_allow_list(self):
        self.assertLessEqual(A68_RENDERERS, MIGRATED_RENDERERS)
        for name in STILL_LEGACY:
            with self.subTest(still_legacy=name):
                self.assertNotIn(name, MIGRATED_RENDERERS)
                self.assertNotRegex(body(name), r'class="[^"]*(?<![\w-])(?:record-row|record-list|status-chip|detail-grid|request-[\w-]+)(?![\w-])')

    def test_the_sheets_use_the_shared_request_grammar(self):
        for name in ('purchaseOrderDialog', 'qualityIntakeDialog', 'supplierPaymentRequestDialog',
                     'productionChangeRequestDialog', 'payrollApprovalRequestDialog'):
            text = body(name)
            with self.subTest(sheet=name):
                self.assertIn("'<div class=\"request-sheet\">'", text)
                self.assertIn('requestIdentity(', text)
                for legacy in ('class="form-info"', 'class="material-event"', 'class="actions"', 'class="history-item"',
                               'class="requirement-values"', '<p class="error">'):
                    self.assertNotIn(legacy, text)

    def test_identity_lines_and_one_primary(self):
        self.assertIn('requestIdentity(`${e(row.reference)} · ${e(approvalStatus[row.status])}`', body('productionChangeRequestDialog'))
        self.assertIn('requestIdentity(`${e(row.reference)} · ${e(approvalStatus[row.status])}`', body('payrollApprovalRequestDialog'))
        self.assertIn('requestIdentity(`${e(row.reference)} · ${e(approvalStatus[row.status])}`', body('supplierPaymentRequestDialog'))
        self.assertIn('requestIdentity(`${e(q.reference)} · ${e(q.code)} · ${e(q.name)}`', body('qualityIntakeDialog'))
        self.assertIn("const requestDecisionWeight = {approved:'action-primary',rejected:'action-destructive',cancelled:'action-secondary'};", APP)
        for name in ('productionChangeRequestDialog', 'payrollApprovalRequestDialog', 'supplierPaymentRequestDialog', 'purchaseOrderDialog'):
            with self.subTest(sheet=name):
                self.assertIn('requestDecisionWeight[status]', body(name))

    def test_gates_are_the_legacy_ones(self):
        change = body('productionChangeRequestDialog')
        self.assertIn("if(user.role==='admin'&&row.status==='submitted'&&!row.stale)decisions.push(['approved','Setujui perubahan']);", change)
        self.assertIn("if(user.role==='admin'&&row.status==='submitted')decisions.push(['rejected','Tolak perubahan']);", change)
        self.assertIn("const canCancel=row.status==='submitted'&&(user.role==='admin'||row.actor_id===user.id);", change)
        self.assertIn('expected_revision:row.revision', change)
        payroll = body('payrollApprovalRequestDialog')
        self.assertIn("if(pending&&user.role==='admin'&&!row.stale)buttons.push(['approved','Setujui payroll']);", payroll)
        self.assertIn("if(pending&&user.role==='operator'&&row.actor_id===user.id)buttons.push(['cancelled','Batalkan pengajuan']);", payroll)
        payment = body('supplierPaymentRequestDialog')
        self.assertIn("if(user.role==='admin'&&row.status==='submitted')buttons.push(['approved','Setujui pembayaran'],['rejected','Tolak pembayaran']);", payment)
        po = body('purchaseOrderDialog')
        self.assertIn("if(user.role==='admin'&&p.approval_status==='submitted')approvalButtons.push(['approved','Setujui penerbitan PO'],['rejected','Tolak PO']);", po)
        self.assertIn("user.role==='admin' && p.status==='issued' && p.fulfillment==='pending' && p.lines.every(l=>l.held==='0.000' && l.return_pending==='0.000')", po)
        qc = body('qualityIntakeDialog')
        self.assertIn("const active=!q.cancellation && !q.po_cancelled && !q.po_closed, admin=user.role==='admin';", qc)
        self.assertIn("(d.kind==='accept' || Number(d.quantity)<=Number(q.return_pending))", qc)
        self.assertIn("const writable=user.role==='admin' && !q.cancellation && !q.po_closed;", body('renderSupplierReturns'))
        self.assertIn("const ready=p.lines.every(l=>l.held==='0.000' && l.return_pending==='0.000');", body('renderPOClosure'))

    def test_po_quantity_and_payment_semantics_stay_separate(self):
        po = body('purchaseOrderDialog')
        for label, key in (('Diterima', 'received'), ('Sisa layak pakai', 'remaining'), ('Hold', 'held'), ('Reject', 'rejected'),
                           ('Bisa datang', 'receivable'), ('Diretur', 'returned'), ('Belum diretur', 'return_pending')):
            with self.subTest(quantity=key):
                self.assertIn(f"['{label}',qty(l.{key},l)]", po)
        self.assertNotRegex(po, r'progress-(?:meter|track|fill)', 'no merged progress figure')
        self.assertIn('Menunggu approval ${e(rupiah(p.payment_pending))} · disetujui ${e(rupiah(p.payment_approved))} · sisa ${e(rupiah(p.payment_remaining))}', po)
        self.assertIn('Approved berarti siap dibayar. Transfer bank dan jurnal akuntansi belum dijalankan aplikasi.', po)
        self.assertNotRegex(po, r"'Dibayar'|>Dibayar<|Lunas")

    def test_payroll_stays_aggregate_and_honest(self):
        payroll = body('payrollApprovalRequestDialog')
        self.assertNotRegex(payroll, r'employee_name|employee_id|employees\.|\.employees\b')
        self.assertIn('Keputusan tidak mengubah Mekari atau menjalankan pembayaran.', payroll)
        self.assertIn('Snapshot payroll sumber sudah berubah atau tidak lagi tersedia. Permintaan ini tidak dapat disetujui.', payroll)
        self.assertIn("queueChip('warning','Sumber berubah')", payroll)

    def test_the_order_scoped_pr_list_keeps_its_scope_and_cursor(self):
        text = body('orderPurchaseRequestsDialog')
        self.assertIn("new URLSearchParams({limit:25,status:$('pr-status').value,...(orderId?{order_id:orderId}:{}),...(before?{before}:{})})", text)
        self.assertIn("user.role!=='viewer' ? `<button type=\"button\" class=\"action-primary\" data-action=\"new-purchase-request\" data-id=\"${e(orderId || '')}\">Buat PR</button>` : ''", text)
        self.assertIn("before=rows.at(-1)?.sequence;button.hidden=rows.length<25;", text)
        for hook in ('id="pr-status"', 'id="pr-refresh"', 'id="pr-list"', 'id="pr-more"', 'id="pr-error"'):
            with self.subTest(hook=hook):
                self.assertIn(hook, text)

    def test_the_pr_sheet_names_every_po_status(self):
        # A6.7 regression: the PR detail's PO chip rendered as a bare dot for an issued PO, because the
        # PR payload reports an issued PO as `approved`. The chip now always carries its word.
        self.assertIn("const linkedPoStatus = status => status === 'approved' ? 'issued' : status;", APP)
        self.assertIn("queueChip(poTone[linkedPoStatus(po.status)]||'neutral',poStatus[linkedPoStatus(po.status)])", body('purchaseRequestDialog'))


class ToneMapTest(unittest.TestCase):
    def test_one_approval_tone_map(self):
        self.assertIn("const approvalTone={submitted:'info',pending:'info',approved:'success',rejected:'danger',cancelled:'neutral'};", APP)
        self.assertEqual(len(re.findall(r'^const approvalTone\s*=', APP, re.M)), 1)
        # A6.3 (leave / overtime) and A6.5 (AI actions) are the same five approval states.
        self.assertIn('const workforceRequestTone=approvalTone;', APP)
        self.assertIn('const aiActionTone=approvalTone;', APP)
        # The A6.7 timeline derives its markers from the same map (neutral draws the plain marker).
        self.assertIn("const requestTone = Object.fromEntries(Object.entries(approvalTone).map(([status,tone]) => [status,tone==='neutral'?'':tone]));", APP)
        # No approval surface restates "waiting" as a warning any more.
        self.assertNotRegex(APP, r"(?:submitted|pending):'warning'")

    def test_domain_health_keeps_its_own_maps(self):
        for pinned in ("const healthTone={healthy:'success',failed:'danger',stale:'warning',never_synced:'neutral',incomplete:'warning'};",
                       "const aiSeverityTone={critical:'danger',high:'warning',medium:'neutral',info:'info'};",
                       "const payrollTone={draft:'neutral',reviewing:'info',approved:'info',paid:'success',cancelled:'neutral'};",
                       "const poTone={pending:'info',issued:'success',rejected:'danger',cancelled:'neutral',closed:'neutral'};"):
            with self.subTest(pinned=pinned[:30]):
                self.assertIn(pinned, APP)

    def test_stale_is_a_sentence_and_a_warning_never_a_status(self):
        self.assertIn('Permintaan sudah stale.', APP)
        self.assertIn("queueChip('warning','Permintaan sudah stale')", body('productionChangeRequestDialog'))
        self.assertIn("· sumber berubah", APP)
        self.assertNotIn('stale:', const('approvalTone'))


class DeadCssTest(unittest.TestCase):
    def test_removed_selectors_are_gone_and_had_no_emitter(self):
        rules = code_css(CSS) + code_css(SHELL) + code_css(PRIMITIVES)
        for name, why in REMOVED_SELECTORS.items():
            token = r'(?<![\w-])' + re.escape(name) + r'(?![\w-])'
            with self.subTest(selector='.' + name, why=why):
                self.assertNotRegex(rules, r'\.' + re.escape(name) + r'(?![\w-])', f'.{name} was removed by A6.8')
                for source, text in RUNTIME.items():
                    for pattern in (r'class="[^"]*' + token, r"classList\.\w+\('" + re.escape(name) + r"'",
                                    r"className\s*=\s*'[^']*" + token, r"querySelector(?:All)?\('[^']*\." + re.escape(name) + r'(?![\w-])'):
                        self.assertNotRegex(text, pattern, f'{source} still emits .{name}')

    def test_retained_hooks_are_still_emitted_and_still_styled(self):
        for name, why in RETAINED_HOOKS.items():
            with self.subTest(hook=name, why=why):
                self.assertRegex(APP + HTML, r'class(?:Name\s*=\s*|=)["\'][^"\']*(?<![\w-])' + re.escape(name) + r'(?![\w-])')
                self.assertRegex(code_css(CSS), r'\.' + re.escape(name) + r'(?![\w-])')

    def test_the_issue_summary_id_keeps_its_a61_rules(self):
        self.assertIn('id="issues-summary"', HTML)
        self.assertIn('#issues-summary.attention-note-success', CSS)


class RegressionTest(unittest.TestCase):
    def test_the_command_center_marketplace_table_stays_inside_its_card(self):
        # A6.8 QA found the Command Center's "Rincian order, unit & refund" table bleeding 20px past
        # both sides of its card: the legacy `margin:0 -20px` assumed a 20px card inset that the
        # A5 card (16px) no longer has, so the solid table surface overhung the card edge. The table
        # keeps its own padding and its internal scroll; only the negative bleed is gone.
        self.assertIn('.table-scroll{margin:0;padding:0 20px;overflow-x:auto}', CSS)
        self.assertNotIn('.table-scroll{margin:0 -20px', CSS)

    def test_the_first_pass_yield_ring_grows_with_the_text_on_a_phone(self):
        # At 320px with 200% text the ring's figure (~160px) was wider than its fixed 120px circle and
        # collided with the stroke. On a phone the ring now scales with the root text size and never
        # leaves its card; 7.5rem is exactly 120px at the default size, so nothing moves until text grows.
        ring = re.search(r'@media\(max-width:650px\)\{\s*#command-center-hero \.hero-ring\{([^}]*)\}', A68_BLOCK)
        self.assertIsNotNone(ring)
        for declaration in ('width:clamp(120px,7.5rem,100%)', 'height:auto', 'aspect-ratio:1'):
            self.assertIn(declaration, ring.group(1))


class BudgetTest(unittest.TestCase):
    def test_frame_and_timer_budget(self):
        self.assertEqual(len(re.findall(r'requestAnimationFrame\(', APP)), 6)
        self.assertEqual(len(re.findall(r'cancelAnimationFrame\(', APP)), 4)
        self.assertEqual(len(re.findall(r'setTimeout\(', APP)), 7)
        self.assertEqual(len(re.findall(r'setInterval\(', APP)), 0)
        for name in A68_RENDERERS:
            source = body(name) if re.search(r'^(?:async )?function ' + name + r'\(', APP, re.M) else const(name)
            with self.subTest(renderer=name):
                self.assertNotRegex(source, r'setTimeout|setInterval|requestAnimationFrame|EventSource|WebSocket|IntersectionObserver')

    def test_no_new_request_for_decoration(self):
        # The Inbox still makes one list request per load and never asks for the aggregate summary.
        self.assertNotIn('/api/approvals/summary', body('loadApprovals'))
        # Each migrated sheet loads exactly what it loaded before.
        self.assertEqual(body('purchaseOrderDialog').count('api.get('), 2)
        for name in ('qualityIntakeDialog', 'supplierPaymentRequestDialog', 'productionChangeRequestDialog',
                     'payrollApprovalRequestDialog', 'orderPurchaseRequestsDialog'):
            with self.subTest(sheet=name):
                self.assertEqual(body(name).count('api.get('), 1)


class VersionTest(unittest.TestCase):
    def test_version_schema_and_contract(self):
        version = re.search(r'^version = "([^"]+)"', (ROOT / 'pyproject.toml').read_text(encoding='utf-8'), re.M).group(1)
        self.assertEqual(version, '0.114.0', 'A6.8 is the final Apple-27 milestone')
        self.assertIn(f'version="{version}"', (ROOT / 'beeloft' / 'api.py').read_text(encoding='utf-8'))
        contract = json.loads((ROOT / 'docs' / 'openapi.json').read_text(encoding='utf-8'))
        self.assertEqual(contract['info']['version'], version)
        self.assertEqual(len(contract['paths']), 221, 'A6.8 is presentation only')
        versions = [int(value) for path in (ROOT / 'beeloft').glob('*.sql')
                    for value in re.findall(r'PRAGMA user_version\s*=\s*(\d+)', path.read_text(encoding='utf-8'))]
        self.assertEqual(max(versions), 55)

    def test_documentation(self):
        text = (ROOT / 'docs' / 'apple27-final-consistency-polish.md').read_text(encoding='utf-8')
        for anchor in ('65e5635a548e4a18bf462b2be0c5b063e88e849e', '0.114.0', 'PRAGMA user_version = 55', 'data-size',
                       'formDialog', 'approvalTone', 'RUNTIME LEGACY HOOKS STILL REQUIRED', 'DEAD CSS REMOVED',
                       'INTENTIONALLY DEFERRED NON-VISUAL TECH DEBT'):
            with self.subTest(anchor=anchor):
                self.assertIn(anchor, text)
        for name in REMOVED_SELECTORS:
            with self.subTest(documented=name):
                self.assertIn('.' + name, text)
        foundation = (ROOT / 'docs' / 'apple27-modern-workspace-foundation.md').read_text(encoding='utf-8')
        self.assertIn('A6.8', foundation)


if __name__ == '__main__':
    unittest.main()
