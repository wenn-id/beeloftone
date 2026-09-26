"""A6.2 - Bahan baku + Master SKU modern workspaces: the static half of the migration contract.

A6.0 built the shared inner-workspace language, A6.1 spent it on Produksi, and A6.2 spends it on
the two master-data workspaces: the material batch inventory (`#materials-view`), the SKU catalog
(`#products-view`), and the dialogs those two pages launch - which, unlike Produksi's child
dialogs, ARE the workflow rather than a side task.

Two workspaces in one phase makes this mostly a *truth* contract, and a second thing besides: a
contract that the two pages did not collapse into one another. So what is asserted here is

  * the two pages have DIFFERENT compositions - Bahan baku is a table because its rows really are
    tabular, Master SKU is a record list because a SKU is identity plus status plus two actions -
    and neither page grew a metric strip, because neither endpoint returns a global aggregate;
  * balance / reserved / available stay three separate, separately labelled, unaltered figures,
    and no fourth number is derived from them;
  * no batch status chip is manufactured out of a quantity;
  * the material filter still resets the offset, the page is still 25 records with a 26th sentinel,
    and the request still carries the same three parameters;
  * Master SKU search is still local and instant against the complete `productsCache`, with all
    four searchable values intact, and the catalog still costs exactly two requests - no per-SKU
    BOM fan-out exists at any width;
  * mapping says "Terhubung", never "tersinkron"/"sehat", because mapping matches identity and does
    not itself synchronise;
  * BOM is still per 1 pcs, still master units, still no automatic waste, and still rejects
    duplicate materials / caps at 100 lines / requires one;
  * every permission gate is still the same `user.role` comparison in JS, and none moved to CSS;
  * every stale guard (`epoch`, the per-view request counter, `view`, `dialogVersion`) survives;
  * the A5.2 shell, the A5.3 lens, the A3 spring and the frame/timer budget are untouched;
  * A6.1 Produksi is not visually regressed;
  * no route, no schema, no migration.

The behavioural half lives in tests/browser_materials_master_sku_modern.cjs. The containment half -
that A6 primitives reached exactly these two workspaces and their named dialogs and nothing else -
stays in tests/test_apple27_modern_workspace_foundation_contract.py, whose allow-list A6.2 widened
on purpose; what this file adds is the mirror image, that the A6.2 CSS block cannot reach a third
page.
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
PRIMITIVES = (STATIC / 'workspace-primitives.css').read_text(encoding='utf-8')
SHELL = (STATIC / 'workspace.css').read_text(encoding='utf-8')


def section(html, element_id):
    """The complete markup of one `<section id=...>`, nested sections included."""
    start = html.index(f'<section id="{element_id}"')
    depth = 0
    for match in re.finditer(r'<section\b|</section>', html[start:]):
        depth += 1 if match.group().startswith('<section') else -1
        if depth == 0:
            return html[start:start + match.end()]
    raise AssertionError(f'#{element_id} is not a closed section')


def code(source):
    """`source` with its comments removed.

    Every "this must not appear" assertion runs against this rather than the raw text: the A6.2
    renderers are heavily commented and several of those comments necessarily NAME the thing being
    ruled out - "bukan 'tersinkron'", "tidak ada status batch yang dikarang". String literals are
    left intact, because the markup lives inside template literals and that markup is the subject.
    """
    return re.sub(r'(?<!:)//[^\n]*', '', re.sub(r'/\*.*?\*/', '', source, flags=re.S))


def code_css(source):
    return re.sub(r'/\*.*?\*/', '', source, flags=re.S)


def renderer(name):
    """One top-level declaration's body from app.mjs, function or arrow const alike.

    Declarations in this file all start at column zero, so the next one ends this one. That is
    enough to scope an assertion to a single renderer without brace matching, which template
    literals full of `${...}` would defeat.
    """
    start = re.search(r'^(?:async )?(?:function|const) ' + re.escape(name) + r'\b', APP, re.M)
    assert start, f'{name} is missing from app.mjs'
    following = re.search(r'^(?:async )?function \w+\(|^const \w+ =|^let \w+ =',
                          APP[start.end():], re.M)
    return APP[start.start():start.end() + (following.start() if following else len(APP))]


APP_CODE = code(APP)
MATERIALS = section(HTML, 'materials-view')
PRODUCTS = section(HTML, 'products-view')
BOARD = section(HTML, 'board-view')

# The A6.2 containment block: from its first selector to the first selector of the next phase's
# block. Its A6.1 counterpart is bounded by this same marker, so the blocks are checked separately
# and no test can silently start covering another's rules. A6.3 appended its own block after this
# one, which is why the upper bound is now its marker rather than the end of the stylesheet.
A62_MARKER = '#materials-view,#products-view{max-width:1360px'
A63_MARKER = '#people-view,#bundle-scan-view,#finished-goods-scan-view{max-width:1360px'
A62_BLOCK = code_css(CSS)[code_css(CSS).index(A62_MARKER):code_css(CSS).index(A63_MARKER)]

# Every renderer A6.2 migrated, by the name the A6.0 containment test attributes markup to.
BAHAN_BAKU_RENDERERS = ('loadMaterials', 'materialBatchScanDialog', 'materialMasterDialog',
                        'materialForm', 'receiptForm', 'materialHistoryDialog',
                        'materialBatchTraceabilityDialog')
MASTER_SKU_RENDERERS = ('loadProducts', 'paintProducts', 'productForm', 'bomComponentsHTML',
                        'bomDialog', 'bomForm', 'bomHistoryDialog', 'productMappingDialog',
                        'productMappingForm', 'unmapProductForm', 'productMappingHistoryDialog')


class MigrationHappenedTest(unittest.TestCase):
    """The widened allowance is spent, not merely granted."""

    def test_bahan_baku_consumes_the_a60_primitives(self):
        for primitive in ('workspace-page', 'workspace-heading', 'workspace-heading-copy',
                          'workspace-title', 'workspace-subtitle', 'workspace-actions',
                          'workspace-section-title', 'workspace-subhead', 'workspace-meta',
                          'command-bar', 'command-filters', 'command-filter', 'command-actions',
                          'info-panel', 'data-surface', 'action-primary', 'action-secondary',
                          'action-quiet'):
            with self.subTest(primitive=primitive):
                self.assertIn(f'class="{primitive}"', MATERIALS + ' ' + MATERIALS.replace(
                    'list-host data-surface', 'data-surface'),
                    f'#materials-view does not consume .{primitive}')

    def test_master_sku_consumes_the_a60_primitives(self):
        for primitive in ('workspace-page', 'workspace-heading', 'workspace-heading-copy',
                          'workspace-title', 'workspace-subtitle', 'workspace-actions',
                          'workspace-section-title', 'workspace-subhead', 'workspace-meta',
                          'command-bar', 'command-search', 'command-actions', 'info-panel',
                          'action-primary', 'action-secondary', 'action-quiet'):
            with self.subTest(primitive=primitive):
                self.assertIn(f'class="{primitive}"', PRODUCTS,
                              f'#products-view does not consume .{primitive}')

    def test_the_renderers_consume_the_a60_primitives(self):
        # The row/state/detail vocabulary is written by script, not by markup, so it is asserted
        # against the renderers that own it rather than against index.html.
        for primitive, owner in (('data-header', 'loadMaterials'), ('data-row', 'loadMaterials'),
                                 ('data-cell', 'loadMaterials'), ('data-primary', 'loadMaterials'),
                                 ('data-secondary', 'loadMaterials'),
                                 ('record-list', 'paintProducts'), ('record-row', 'paintProducts'),
                                 ('record-row-copy', 'paintProducts'),
                                 ('record-row-aside', 'paintProducts'),
                                 ('status-chip', 'paintProducts'), ('chip-row', 'paintProducts'),
                                 ('detail-grid', 'materialHistoryDialog'),
                                 ('utility-panel', 'materialHistoryDialog'),
                                 ('timeline-item', 'materialHistoryDialog'),
                                 ('timeline-item', 'materialBatchTraceabilityDialog'),
                                 ('record-list', 'materialMasterDialog'),
                                 ('field', 'materialForm'), ('field', 'receiptForm'),
                                 ('field', 'productForm'), ('record-list', 'bomComponentsHTML'),
                                 ('empty-state', 'bomDialog'), ('timeline-item', 'bomHistoryDialog'),
                                 ('status-chip', 'productMappingDialog'),
                                 ('timeline-item', 'productMappingHistoryDialog')):
            with self.subTest(primitive=primitive, owner=owner):
                self.assertRegex(renderer(owner),
                                 r'class="[^"]*(?<![\w-])' + re.escape(primitive) + r'(?![\w-])',
                                 f'{owner} does not consume .{primitive}')

    def test_every_state_goes_through_the_shared_state_primitive(self):
        # Both pages used the plain `message()` paragraph before A6.2. Loading, empty and error are
        # now the one shared surface, so a later phase cannot reintroduce a bespoke one.
        for owner, host in (('loadMaterials', 'materials-message'), ('loadProducts', 'products-message'),
                            ('paintProducts', 'products-message')):
            with self.subTest(owner=owner):
                self.assertIn(f"pageState('{host}'", renderer(owner))

    def test_the_legacy_page_vocabulary_is_gone_from_both_pages(self):
        # The stacked filter form, the page-heading block and the batch card are retired HERE, and
        # only here - each is still rendered by another workspace, so the rules stay in style.css.
        for legacy in ('class="filters"', 'class="page-heading"', 'class="search-field"',
                       'class="eyebrow"'):
            for name, markup in (('materials-view', MATERIALS), ('products-view', PRODUCTS)):
                with self.subTest(legacy=legacy, page=name):
                    self.assertNotIn(legacy, markup)
        for legacy in ('sku-block', 'sku-heading', 'material-balance'):
            with self.subTest(legacy=legacy):
                self.assertNotRegex(renderer('loadMaterials'),
                                    r'class="[^"]*(?<![\w-])' + legacy + r'(?![\w-])')
        self.assertNotRegex(renderer('paintProducts'), r'class="[^"]*(?<![\w-])product-item(?![\w-])')
        # ...and the rules themselves stay, because other pages and dialogs still render them.
        for kept in ('.filters,', '.page-heading', '.search-field{', '.sku-block{', '.sku-heading ',
                     '.material-balance{', '.product-item{', '.bom-line{', '.bundle-label',
                     '.product-list{', '.form-info{', '.list-host', '.state{'):
            with self.subTest(kept=kept):
                self.assertIn(kept, CSS, f'{kept} is still used by an unmigrated surface')

    def test_a_dialog_outside_the_named_set_did_not_migrate(self):
        # The point of naming the dialogs rather than allowing "any dialog": Produksi's own child
        # dialogs, reachable from the order detail, are NOT part of A6.2 and must still be legacy.
        self.assertNotRegex(renderer('materialIssueForm'), r'class="[^"]*(?<![\w-])field(?![\w-])',
                            'materialIssueForm is a Produksi child dialog; A6.1 is frozen')
        self.assertIn('materialReason', renderer('materialIssueForm'),
                      'the legacy reason field must stay for the dialogs A6.2 did not migrate')


class DifferentGrammarsTest(unittest.TestCase):
    """Same visual system, deliberately different compositions."""

    def test_bahan_baku_is_a_table_and_master_sku_is_a_record_list(self):
        batches = renderer('loadMaterials')
        self.assertIn('<table>', batches, 'the batch inventory is a real table')
        self.assertIn('<thead class="data-header">', batches)
        self.assertRegex(batches, r'<th scope="col">')
        catalog = renderer('paintProducts')
        self.assertNotIn('<table>', catalog, 'the SKU catalog is a record list, not a table')
        self.assertIn('<ul class="record-list">', catalog)
        # And the inverse, so a later edit cannot quietly converge them.
        self.assertNotRegex(batches, r'<ul class="record-list">')

    def test_neither_page_invents_a_metric_strip(self):
        # Neither endpoint returns a global aggregate for these pages, so there is no honest KPI row
        # to render, and summing the 25 paginated batches would be a lie about global stock.
        for name, markup in (('materials-view', MATERIALS), ('products-view', PRODUCTS)):
            with self.subTest(page=name):
                self.assertNotIn('metric-strip', markup)
                self.assertNotIn('metric-card', markup)
        for owner in ('loadMaterials', 'paintProducts', 'loadProducts'):
            with self.subTest(owner=owner):
                self.assertNotIn('metric-strip', code(renderer(owner)))
                self.assertNotIn('metric-card', code(renderer(owner)))
        # No page-level reduce/sum over the rendered page either.
        self.assertNotRegex(code(renderer('loadMaterials')), r'\.reduce\(')

    def test_bahan_baku_has_no_text_search_and_master_sku_has_no_extra_filter(self):
        # `/api/material-batches` has no search parameter, so the command bar must not grow a box
        # that looks like one; and Master SKU's one control is the local search.
        self.assertNotIn('command-search', MATERIALS)
        self.assertNotIn('type="search"', MATERIALS)
        self.assertNotIn('command-filter', PRODUCTS)
        self.assertEqual(len(re.findall(r'<select', PRODUCTS)), 0)
        for markup in (MATERIALS, PRODUCTS):
            self.assertNotIn('segmented-filter', markup)
            self.assertNotIn('filter-chip', markup)


class BatchInventoryTruthTest(unittest.TestCase):
    def test_the_three_quantities_stay_three_labelled_unaltered_figures(self):
        batches = renderer('loadMaterials')
        for header in ('Saldo', 'Direservasi', 'Stok bebas'):
            with self.subTest(header=header):
                self.assertIn(f'<th scope="col">{header}</th>', batches,
                              f'{header} must be labelled by its own column header')
        for field, hook in (('balance', 'data-batch-balance'), ('reserved', 'data-batch-reserved'),
                            ('available', 'data-batch-available')):
            with self.subTest(field=field):
                self.assertIn(f'{hook}>${{e(materialQty(b.{field},b.unit))}}', batches,
                              f'b.{field} must be rendered as-is, through the shared formatter')
        # No fourth figure is derived from the three real ones.
        self.assertNotRegex(code(batches), r'b\.(balance|reserved|available)\s*[-+*/]')
        self.assertNotRegex(code(batches), r'Number\(b\.|parseFloat\(b\.')

    def test_no_batch_status_is_manufactured_from_a_quantity(self):
        # `status` on the list payload is receipt-correction bookkeeping, not a stock health signal,
        # and the list never rendered it. Inventing Healthy/Low/Critical from a number would be a
        # business claim this endpoint does not make.
        batches = code(renderer('loadMaterials'))
        self.assertNotIn('status-chip', batches)
        for invented in ('Healthy', 'Low stock', 'Stok kritis', 'Critical', 'Aman', 'Menipis',
                         'Sehat', 'coverage', 'Coverage'):
            with self.subTest(invented=invented):
                self.assertNotIn(invented, batches)

    def test_the_batch_row_carries_only_fields_the_endpoint_returns(self):
        batches = renderer('loadMaterials')
        for field in ('id', 'reference', 'code', 'name', 'supplier', 'location', 'received_date',
                      'balance', 'reserved', 'available', 'unit'):
            with self.subTest(field=field):
                self.assertIn(f'b.{field}', batches)
        self.assertNotIn('b.trend', batches)
        self.assertNotIn('b.forecast', batches)

    def test_opening_a_batch_stays_a_real_focusable_button(self):
        batches = renderer('loadMaterials')
        self.assertRegex(batches, r'<button[^>]*data-action="material-batch" data-id="\$\{e\(b\.id\)\}"')
        # The accessible name is the reference and nothing else, which is what the PO and incoming-QC
        # modules locate the row by.
        self.assertIn('data-id="${e(b.id)}">${e(b.reference)}</button>', batches)
        # The chevron is decoration on top of that button, never the only way in.
        self.assertIn("svgIcon('arrow-right','icon-sm')", batches)
        self.assertNotIn('onclick', batches)

    def test_the_filter_pagination_and_request_contract_is_byte_identical(self):
        wiring = APP_CODE
        self.assertIn("$('material-filter').onchange = () => { materialsOffset = 0; loadMaterials(); }",
                      wiring, 'changing the material filter still resets the offset')
        self.assertIn('materialsOffset = Math.max(0,materialsOffset-25)', wiring)
        self.assertIn('materialsOffset += 25', wiring)
        batches = renderer('loadMaterials')
        self.assertIn('new URLSearchParams({limit:26,offset:materialsOffset,material_id:materialId})',
                      batches, 'the 26th record is the pagination sentinel')
        self.assertIn('batches.slice(0,25)', batches)
        self.assertIn("allRows('/api/materials')", batches)
        self.assertIn("api.get('/api/material-batches?'", batches)
        self.assertIn('`Batch ${materialsOffset+1}–${materialsOffset+Math.min(25,batches.length)}`',
                      batches)
        self.assertIn("'0 batch di halaman ini'", batches)
        self.assertIn('$(\'materials-next\').disabled = batches.length <= 25', batches)
        # Not infinite scroll.
        self.assertNotIn('IntersectionObserver', APP_CODE)
        for control in ('material-filter', 'materials-refresh', 'materials-previous',
                        'materials-next', 'receive-material', 'material-master',
                        'scan-material-batch', 'materials-page', 'materials-message', 'batch-list'):
            with self.subTest(control=control):
                self.assertIn(f'id="{control}"', MATERIALS)

    def test_the_inventory_explanation_survives_word_for_word(self):
        for sentence in ('Saldo adalah bahan layak pakai yang diterima, dikurangi pengeluaran ke order.',
                         'Stok bebas = saldo fisik dikurangi reservasi semua order.',
                         'Untuk mengalokasikan atau mengeluarkan bahan, buka order produksi.'):
            with self.subTest(sentence=sentence):
                self.assertIn(sentence, MATERIALS)

    def test_the_heading_states_the_workspace_and_its_job(self):
        self.assertIn('<h1 class="workspace-title">Bahan baku</h1>', MATERIALS)
        self.assertIn('Pantau batch, saldo, reservasi, dan stok bebas untuk produksi.', MATERIALS)

    def test_the_action_hierarchy_is_three_weights_not_three_capsules(self):
        self.assertRegex(MATERIALS, r'id="receive-material" class="action-primary"')
        self.assertRegex(MATERIALS, r'id="scan-material-batch" type="button" class="action-secondary"')
        self.assertRegex(MATERIALS, r'id="material-master" type="button" class="action-quiet"')

    def test_the_empty_state_distinguishes_an_empty_page_from_an_empty_master(self):
        batches = renderer('loadMaterials')
        self.assertIn('Belum ada batch pada halaman ini.', batches)
        self.assertIn('ubah filter bahan dan halaman', batches)
        # The write CTA is role-gated in JS, and its name differs from the header button so the two
        # are never ambiguous to a keyboard or a screen reader.
        self.assertIn("user.role === 'viewer' ? ''", batches)
        self.assertIn('Terima batch bahan pertama', batches)


class BatchDetailAndTraceabilityTest(unittest.TestCase):
    def test_current_physical_quantities_sit_above_the_history(self):
        detail = renderer('materialHistoryDialog')
        position = detail.index('Posisi bahan sekarang')
        self.assertLess(position, detail.index('Riwayat catatan bahan'),
                        'the quantities an operator came for must not be buried below history')
        for label in ('Saldo', 'Direservasi', 'Stok bebas'):
            with self.subTest(label=label):
                # Emitted through the local `quantity()` builder, which is what keeps every figure
                # on the same formatter and the same unit.
                self.assertIn(f"quantity('{label}',batch.", detail)
        self.assertIn('<dt>${label}</dt>', detail)
        for label in ('Lokasi', 'Pemasok', 'Diterima', 'Jumlah diterima'):
            with self.subTest(label=label):
                self.assertIn(f'<dt>{label}</dt>', detail)

    def test_the_order_mode_renderer_still_works_for_produksi(self):
        # Produksi's order detail calls this same renderer with (null, order). Every batch-only block
        # must stay behind an optional chain or the order branch, or A6.1 breaks.
        detail = renderer('materialHistoryDialog')
        self.assertIn('materialHistoryDialog(batchId, order=null)', detail)
        self.assertIn('const batch = order ? null :', detail)
        self.assertIn('`/api/orders/${encodeURIComponent(order.id)}/material-movements`', detail)
        self.assertIn('e(order.reference)', detail)
        self.assertIn("batch?.status === 'active'", detail)
        self.assertIn('Belum ada pengeluaran bahan untuk order ini.', detail)
        self.assertIn('order ? \'Riwayat bahan order\' : \'Riwayat batch bahan\'', detail)

    def test_movement_history_keeps_its_three_meanings_and_its_paging(self):
        detail = renderer('materialHistoryDialog')
        self.assertIn("m.kind === 'receipt' ? 'Penerimaan' : m.kind === 'issue' ? 'Pengeluaran' : 'Pembalikan'",
                      detail)
        # Quantity and unit stay one string, so a negative sign can never orphan from its number.
        self.assertIn('${kind} · ${e(materialQty(m.quantity,m.unit))}', detail)
        for field in ('m.batch_reference', 'm.code', 'm.order_reference', 'm.reason', 'm.actor_name',
                      'm.created_at', 'm.reversed_by'):
            with self.subTest(field=field):
                self.assertIn(field, detail)
        self.assertIn('Sudah dibalik', detail)
        self.assertIn('new URLSearchParams({limit:100,...(before ? {before} : {})})', detail)
        self.assertIn('before = rows.at(-1)?.sequence', detail)
        self.assertIn('Muat catatan bahan sebelumnya', detail)
        self.assertIn('button.hidden = page.length < 100', detail)
        # Newest-first ordering is the server's; the renderer must not re-sort.
        self.assertNotRegex(code(detail), r'rows\.(sort|reverse)\(')

    def test_correction_eligibility_is_unchanged_and_still_admin_only(self):
        detail = renderer('materialHistoryDialog')
        self.assertIn("user.role === 'admin' && !m.reversal_of && !m.reversed_by", detail)
        self.assertIn("!((batch?.qc_intake_id || batch?.po_closed) && m.kind==='receipt')", detail)
        self.assertIn('Koreksi catatan bahan', detail)
        self.assertIn('/reverse`', detail)
        self.assertIn('Pembalikan mengembalikan seluruh jumlah catatan.', detail)

    def test_the_batch_label_is_untouched_and_still_printable(self):
        detail = renderer('materialHistoryDialog')
        # The print stylesheet targets `#dialog-content .bundle-label` as a DIRECT child, so the
        # class and the nesting are both load-bearing.
        self.assertIn('<section class="bundle-label material-batch-label"', detail)
        self.assertIn('/label.svg', detail)
        self.assertIn('bundle-label-qty', detail)
        self.assertIn('batch.received_quantity', detail)
        self.assertIn('Cetak label batch', detail)
        self.assertIn('window.print()', detail)
        self.assertIn('#dialog-content .bundle-label', CSS)

    def test_traceability_keeps_every_event_label_and_its_cursor(self):
        trace = renderer('materialBatchTraceabilityDialog')
        self.assertIn("endpoint+'?limit=50'", trace)
        self.assertIn('new URLSearchParams({limit:50,...cursor})', trace)
        self.assertIn('cursor=page.next_before', trace)
        self.assertIn('data-material-trace-event="${e(row.event_type)}"', trace)
        self.assertIn("materialTraceLabels[base]||materialTraceLabels[row.event_type]", trace)
        self.assertIn("(corrected?'Koreksi · ':'')", trace)
        self.assertIn('materialTraceStatuses[row.status]||row.status', trace)
        # The full label vocabulary is still declared, so no event collapsed into another.
        for event in ('material_receipt', 'material_issue', 'material_movement',
                      'material_reservation', 'material_reservation_release',
                      'material_reservation_consumption', 'material_consumption', 'cutting_run',
                      'bundle', 'bundle_handoff', 'bundle_handoff_acceptance',
                      'bundle_handoff_cancellation', 'sewing_job', 'sewing_result', 'finishing',
                      'final_qc', 'final_qc_reinspection', 'rework_completion',
                      'finished_goods_receipt'):
            with self.subTest(event=event):
                self.assertRegex(APP, r'(?<![\w-])' + event + r":\s*'", 
                                 f'{event} lost its own label')

    def test_traceability_states_the_mixed_unit_truth_and_draws_no_cumulative_graph(self):
        trace = renderer('materialBatchTraceabilityDialog')
        self.assertIn('Nilai bahan dan pcs memakai satuan berbeda dan tidak dijumlahkan antarcatatan.',
                      trace)
        self.assertIn('class="timeline"', trace)
        for forbidden in ('progress-meter', 'progress-track', 'progress-native', '<progress'):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, code(trace))


class MaterialMasterAndReceiptTest(unittest.TestCase):
    def test_master_bahan_is_identity_and_carries_no_balance(self):
        master = renderer('materialMasterDialog')
        self.assertIn('m.code', master)
        self.assertIn('${e(m.name)} · ${e(m.unit)}', master)
        for quantity in ('balance', 'reserved', 'available', 'materialQty'):
            with self.subTest(quantity=quantity):
                self.assertNotIn(quantity, code(master))
        self.assertIn("user.role === 'admin'", master)
        self.assertIn('Tambah bahan', master)
        self.assertIn('empty-state', master)

    def test_the_add_material_form_keeps_its_fields_units_and_immutability_rule(self):
        form = renderer('materialForm')
        for name, label in (('code', 'Kode bahan'), ('name', 'Nama bahan')):
            with self.subTest(field=name):
                self.assertIn(f'>{label}</label>', form)
                self.assertIn(f'name="{name}"', form)
                self.assertIn('required maxlength="160"', form)
        self.assertIn('>Satuan dasar</label>', form)
        for unit in ('value="m"', 'value="kg"', 'value="pcs"'):
            with self.subTest(unit=unit):
                self.assertIn(unit, form)
        self.assertIn('Kode, nama, dan satuan tidak dapat diubah setelah disimpan.', form)
        self.assertIn("'/api/materials'", form)
        # No edit-material behaviour was invented.
        self.assertNotIn('editMaterial', APP_CODE)

    def test_the_receipt_form_keeps_every_field_and_its_unit_rules(self):
        form = renderer('receiptForm')
        for name, label in (('material_id', 'Bahan diterima'), ('reference', 'Referensi batch'),
                            ('supplier', 'Pemasok'), ('location', 'Lokasi / rak'),
                            ('received_date', 'Tanggal diterima'), ('quantity', 'Jumlah layak pakai')):
            with self.subTest(field=name):
                self.assertIn(f'>{label}</label>', form)
                self.assertIn(f'name="{name}"', form)
        self.assertIn('Alasan / catatan', renderer('reasonField'))
        self.assertIn('reasonField()', form)
        self.assertIn('max="1000000"', form)
        self.assertIn("m.unit === 'pcs' ? '1' : '0.001'", form)
        self.assertIn("$('receipt-material').onchange = updateUnit; updateUnit();", form)
        self.assertIn("'/api/material-batches'", form)
        self.assertIn('maksimal tiga desimal, pcs harus bulat', form)

    def test_the_shared_reason_field_is_still_required_and_still_capped(self):
        field = renderer('reasonField')
        self.assertIn('name="reason"', field)
        self.assertIn('required maxlength="1000"', field)

    def test_the_batch_scanner_is_still_a_keyboard_scanner(self):
        scan = renderer('materialBatchScanDialog')
        self.assertIn('autofocus', scan)
        self.assertIn("input.focus()", scan)
        self.assertIn('onsubmit', scan)
        self.assertIn("api.get('/api/material-batches/scan?'", scan)
        self.assertIn('materialHistoryDialog(batch.id)', scan)
        # Failure re-enables the control and hands focus back so the next scan lands.
        self.assertIn('button.disabled=false;message(\'material-batch-scan-error\',error.message,true);input.focus();',
                      scan)
        self.assertIn('Scanner USB/Bluetooth dapat digunakan seperti keyboard lalu tekan Enter.', scan)
        for camera in ('getUserMedia', 'BarcodeDetector', 'video'):
            with self.subTest(camera=camera):
                self.assertNotIn(camera, code(scan))


class MasterSkuCatalogTest(unittest.TestCase):
    def test_the_heading_states_the_workspace_and_its_job(self):
        self.assertIn('<h1 class="workspace-title">Master SKU</h1>', PRODUCTS)
        self.assertIn('Kelola identitas produk, mapping Jubelio, dan BOM.', PRODUCTS)

    def test_the_action_hierarchy_is_preserved_and_still_admin_gated(self):
        self.assertRegex(PRODUCTS, r'id="new-product" class="action-primary" type="button" hidden')
        self.assertRegex(PRODUCTS, r'id="products-refresh" type="button" class="action-secondary"')
        self.assertIn("$('new-product').hidden = user.role !== 'admin';", APP_CODE)

    def test_search_is_still_local_instant_and_four_valued(self):
        self.assertIn("$('products-search').oninput = paintProducts;", APP_CODE)
        paint = renderer('paintProducts')
        self.assertIn("[p.sku,p.name,[p.color,p.size].filter(Boolean).join(' / '),p.mapping?.external_sku||'']",
                      paint, 'all four searchable values must survive')
        self.assertIn('.some(value=>value.toLowerCase().includes(q))', paint)
        # No network per keystroke, and no server-side search parameter.
        self.assertNotIn('api.get', code(paint))
        self.assertNotIn('allRows', code(paint))
        self.assertNotIn('setTimeout', code(paint))
        self.assertNotRegex(code(paint), r'\bq(uery)?:\s*q\b')
        self.assertIn("$('products-clear').onclick", APP_CODE)

    def test_the_catalog_costs_exactly_two_requests_and_never_fans_out_per_sku(self):
        load = renderer('loadProducts')
        self.assertIn("Promise.all([allRows('/api/products'),allRows('/api/product-external-mappings',{system:'jubelio'})])",
                      load)
        self.assertEqual(len(re.findall(r'allRows\(', load)), 2,
                         'the catalog is two paged reads, nothing more')
        self.assertIn('new Map(mappings.map(row=>[row.product_id,row]))', load)
        self.assertIn('productsCache=products.map', load)
        # The decisive one: no renderer in the whole file asks for a BOM inside a loop or a map.
        for owner in ('loadProducts', 'paintProducts'):
            with self.subTest(owner=owner):
                self.assertNotIn('/bom', code(renderer(owner)),
                                 f'{owner} must not request a BOM to paint the list')
        self.assertNotRegex(code(APP), r'(map|forEach|for)\s*\([^)]*\)\s*(=>)?\s*\{?[^}]{0,200}?/bom`')

    def test_the_sku_row_hierarchy_is_identity_then_product_then_variant(self):
        paint = renderer('paintProducts')
        self.assertIn('<span class="data-primary">${e(p.sku)}</span>', paint)
        self.assertIn('<span class="data-secondary">${e(p.name)}</span>', paint)
        self.assertIn("variant=[p.color,p.size].filter(Boolean).join(' / ')", paint)
        self.assertIn('<span class="data-meta">${e(variant)}</span>', paint)
        # No thumbnail was invented: this workspace's API supplies no image.
        for invented in ('<img', 'thumbnail', 'image_url', 'photo'):
            with self.subTest(invented=invented):
                self.assertNotIn(invented, code(paint))

    def test_both_per_sku_actions_survive_with_their_accessible_names(self):
        paint = renderer('paintProducts')
        self.assertIn('data-action="product-mapping" data-id="${e(p.id)}" aria-label="Jubelio ${e(p.sku)}"',
                      paint)
        self.assertIn('data-action="bom" data-id="${e(p.id)}" aria-label="BOM ${e(p.sku)}"', paint)

    def test_the_two_empty_states_stay_two_different_states(self):
        paint = renderer('paintProducts')
        self.assertIn('Tidak ada SKU yang cocok dengan pencarian ini.', paint)
        self.assertIn('Belum ada SKU.', paint)
        self.assertIn('Tambahkan produk untuk membuat order pertama.', paint)
        # The filtered-empty state keeps a reset; the truly-empty state offers a write action only
        # to the role that has it.
        self.assertIn('data-action="reset-product-search"', paint)
        self.assertIn("user.role === 'admin' ?", paint)
        self.assertIn('data-action="new-product"', paint)
        self.assertIn("'reset-product-search':", APP_CODE)

    def test_the_error_state_keeps_its_retry(self):
        load = renderer('loadProducts')
        self.assertIn('Coba lagi', load)
        self.assertIn("$('products-retry').onclick=loadProducts", load)
        self.assertIn("pageState('products-message','error'", load)

    def test_the_inline_count_is_derived_only_from_the_complete_local_cache(self):
        paint = renderer('paintProducts')
        self.assertIn("mapped=productsCache.filter(p=>p.mapping?.status==='mapped').length", paint)
        self.assertIn('${n(productsCache.length)} SKU', paint)
        self.assertIn('${n(rows.length)} dari ${n(productsCache.length)} SKU', paint)
        # It is metadata on the section heading, not a dashboard.
        self.assertIn('id="products-count" class="workspace-meta"', PRODUCTS)
        self.assertNotIn('metric-card', paint)

    def test_the_refresh_lifecycle_is_unchanged(self):
        load = renderer('loadProducts')
        self.assertIn("markRefreshing('product-list')", load)
        self.assertIn("settleRefreshing('product-list')", load)
        self.assertIn('search.disabled = true; clear.disabled = true;', load)
        self.assertIn('search.disabled = false; clear.disabled = false;', load)


class MappingTruthTest(unittest.TestCase):
    def test_mapping_is_identity_matching_and_says_so(self):
        dialog = renderer('productMappingDialog')
        self.assertIn('Jubelio adalah sumber order marketplace dan stok jual. Mapping ini hanya '
                      'mencocokkan identitas; belum menjalankan sinkronisasi.', dialog)

    def test_mapped_state_is_terhubung_and_never_a_sync_claim(self):
        for owner in ('paintProducts', 'productMappingDialog', 'productMappingHistoryDialog'):
            body = code(renderer(owner))
            with self.subTest(owner=owner):
                self.assertIn('Terhubung', body)
                for lie in ('Synced', 'Tersinkron', 'tersinkron', 'Sinkron aktif', 'Healthy',
                            'Sehat', 'Connected live', 'Terhubung live'):
                    self.assertNotIn(lie, body, f'{owner} must not claim synchronisation')
        self.assertIn("mapping?.status==='mapped'", renderer('paintProducts'))
        self.assertIn("mapped=row.status==='mapped'", renderer('productMappingDialog'))

    def test_unmapped_is_attention_not_alarm(self):
        paint = renderer('paintProducts')
        self.assertIn('Belum dipetakan', paint)
        # Neutral, never danger: an unmapped SKU is not broken.
        self.assertIn('status-chip-neutral', paint)
        self.assertNotIn('status-chip-danger', paint)
        dialog = renderer('productMappingDialog')
        self.assertIn('attention-note-info', dialog)
        self.assertNotIn('attention-note-critical', dialog)
        self.assertNotIn('status-chip-danger', dialog)
        self.assertIn('Worker tidak boleh mengimpor data untuk SKU ini sebelum identitas Jubelio '
                      'dipetakan.', dialog)

    def test_the_mapped_record_keeps_every_field_and_every_permission(self):
        dialog = renderer('productMappingDialog')
        for field in ('row.external_sku', 'row.external_id', 'row.reason', 'row.revision',
                      'row.actor_name', 'row.created_at'):
            with self.subTest(field=field):
                self.assertIn(field, dialog)
        self.assertIn("user.role==='admin'", dialog)
        self.assertIn('data-action="edit-product-mapping"', dialog)
        self.assertIn('data-action="unmap-product"', dialog)
        self.assertIn('Riwayat mapping', dialog)
        self.assertIn('Kembali ke Master SKU', dialog)
        # The two navigation actions are outside the admin branch, as they were.
        start = dialog.index("user.role==='admin'")
        admin_branch = dialog[start:dialog.index("+ '</div>' : '')", start)]
        self.assertNotIn('product-mapping-history', admin_branch)
        self.assertNotIn('data-action="products"', admin_branch)

    def test_the_mapping_and_unmap_payloads_are_byte_identical(self):
        form = renderer('productMappingForm')
        self.assertIn("{expected_revision:row.revision,action:'mapped',external_id:data.get('external_id').trim(),"
                      "external_sku:data.get('external_sku').trim(),reason:data.get('reason').trim()}", form)
        self.assertIn('simpan identifier persis seperti yang diberikan Jubelio.', form)
        unmap = renderer('unmapProductForm')
        self.assertIn("{expected_revision:row.revision,action:'unmapped',external_id:'',external_sku:'',", unmap)
        self.assertIn('Worker tidak boleh mencocokkan SKU ini setelah mapping dilepas.', unmap)
        self.assertIn("if(row.status!=='mapped')return productMappingDialog(productId);", unmap)

    def test_mapping_history_keeps_its_limit_cursor_and_per_revision_fields(self):
        history = renderer('productMappingHistoryDialog')
        self.assertIn('limit:20', history)
        self.assertIn('before=rows.at(-1)?.sequence||before', history)
        self.assertIn('Muat riwayat sebelumnya', history)
        self.assertIn("mapped?'Terhubung':'Dilepas'", history)
        for field in ('row.revision', 'row.external_sku', 'row.external_id', 'row.reason',
                      'row.actor_name', 'row.created_at'):
            with self.subTest(field=field):
                self.assertIn(field, history)
        self.assertIn('button.hidden=rows.length<20', history)


class BomTruthTest(unittest.TestCase):
    def test_bom_is_per_one_pcs_in_master_units_with_no_automatic_waste(self):
        dialog = renderer('bomDialog')
        self.assertIn('Kebutuhan bahan untuk membuat 1 pcs SKU ini. Angka mengikuti satuan master, '
                      'belum termasuk tambahan waste otomatis.', dialog)
        self.assertIn('${e(materialQty(c.quantity,c.unit))} / pcs', renderer('bomComponentsHTML'))

    def test_the_bom_dialog_keeps_revision_metadata_and_role_gating(self):
        dialog = renderer('bomDialog')
        for field in ('bom.revision', 'bom.actor_name', 'bom.created_at', 'bom.components',
                      'bom.reason', 'bom.sku', 'bom.name'):
            with self.subTest(field=field):
                self.assertIn(field, dialog)
        self.assertIn('BOM belum diisi.', dialog)
        self.assertIn('Kebutuhan bahan belum dapat dihitung untuk SKU ini.', dialog)
        self.assertIn("user.role === 'admin'", dialog)
        self.assertIn("bom.revision ? 'Ubah BOM' : 'Isi BOM'", dialog)
        # Riwayat BOM is revision-gated, not role-gated, exactly as before.
        self.assertIn("bom.revision ? `<button class=\"action-quiet\" data-action=\"bom-history\"", dialog)

    def test_the_bom_form_keeps_every_validation_rule(self):
        form = renderer('bomForm')
        self.assertIn("[...form.querySelectorAll('.bom-line')]", form)
        self.assertIn("if (new Set(components.map(c => c.material_id)).size !== components.length) "
                      "throw new Error('Gabungkan bahan yang sama menjadi satu baris BOM.');", form)
        self.assertIn('expected_revision:bom.revision', form)
        self.assertIn("if ($('bom-lines').children.length >= 100) return;", form)
        self.assertIn("notify('BOM memerlukan minimal satu bahan.')", form)
        self.assertIn("input.step=input.min=materials.find(m=>m.id===select.value).unit==='pcs' ? '1':'0.001'",
                      form)
        self.assertIn('max="1000000"', form)
        self.assertIn('>Bahan BOM</label>', form)
        self.assertIn('>Jumlah per pcs</label>', form)
        self.assertIn('Menyimpan membuat versi baru dan memperbarui estimasi kebutuhan semua order '
                      'SKU ini, termasuk order lama. Stok dan pengeluaran tidak berubah.', form)
        # The row keeps the class both the collector and the purchasing editor address it by.
        self.assertIn("row.className='bom-line'", form)

    def test_bom_history_keeps_its_limit_cursor_and_does_not_merge_revisions(self):
        history = renderer('bomHistoryDialog')
        self.assertIn('limit:10', history)
        self.assertIn('before=rows.at(-1)?.revision', history)
        self.assertIn('Muat versi sebelumnya', history)
        self.assertIn('${e(b.sku)} · versi ${b.revision}', history)
        self.assertIn('b.actor_name', history)
        self.assertIn('b.created_at', history)
        self.assertIn('bomComponentsHTML(b.components)', history)
        self.assertIn('b.reason', history)
        self.assertIn('button.hidden=rows.length<10', history)
        # One timeline entry per revision, each with its own component list.
        self.assertEqual(len(re.findall(r'<li class="timeline-item"', history)), 1)

    def test_the_add_sku_form_keeps_its_four_fields_and_their_limits(self):
        form = renderer('productForm')
        for name, label, limit in (('sku', 'Kode SKU', 'required maxlength="160"'),
                                   ('name', 'Nama produk', 'required maxlength="160"'),
                                   ('color', 'Warna', 'maxlength="80"'),
                                   ('size', 'Ukuran', 'maxlength="40"')):
            with self.subTest(field=name):
                self.assertIn(f'>{label}</label>', form)
                self.assertIn(f'name="{name}"', form)
                self.assertIn(limit, form)
        self.assertIn('Gunakan satu kode SKU untuk setiap kombinasi produk, warna, dan ukuran.', form)
        # The accessible names are bare labels: the optional marker would rename two of them.
        self.assertNotIn('field-label-optional', form)


class PermissionsAndStaleGuardsTest(unittest.TestCase):
    def test_every_permission_gate_is_still_the_same_js_comparison(self):
        for gate in ("$('receive-material').hidden = user.role === 'viewer';",
                     "$('new-product').hidden = user.role !== 'admin';"):
            with self.subTest(gate=gate):
                self.assertIn(gate, APP_CODE)
        for owner, gate in (('materialMasterDialog', "user.role === 'admin'"),
                            ('materialHistoryDialog', "user.role === 'admin'"),
                            ('bomDialog', "user.role === 'admin'"),
                            ('productMappingDialog', "user.role==='admin'"),
                            ('loadMaterials', "user.role === 'viewer'"),
                            ('paintProducts', "user.role === 'admin'")):
            with self.subTest(owner=owner):
                self.assertIn(gate, renderer(owner))

    def test_no_permission_is_derived_in_css(self):
        for selector in ('role', 'admin', 'operator', 'viewer', 'permission'):
            with self.subTest(selector=selector):
                self.assertNotRegex(A62_BLOCK, r'\[data-' + selector + r'[\]=]')
                self.assertNotIn(f'.{selector}-only', A62_BLOCK)

    def test_every_workspace_stale_guard_survives(self):
        batches = renderer('loadMaterials')
        self.assertIn('const version = epoch, request = ++materialsRequest', batches)
        self.assertIn("if (version !== epoch || request !== materialsRequest || view !== 'materials') return;",
                      batches)
        self.assertIn("if (version === epoch && request === materialsRequest && view === 'materials')",
                      batches)
        # materialsQuery is the filter actually RENDERED, which is what makes a retry after a failed
        # load still count as a replacement. Removing it would break the replacement motion.
        self.assertIn('const replacing = refreshing && materialsQuery !== materialId;', batches)
        self.assertIn('materialsQuery = materialId;', batches)
        self.assertIn("playEntryMotion($('batch-list'), '--motion-base')", batches)
        load = renderer('loadProducts')
        self.assertIn('const version = epoch, request = ++productsRequest;', load)
        self.assertIn("if (version !== epoch || request !== productsRequest || view !== 'products') return;",
                      load)
        self.assertIn("{id:'materials-view',view:'materials',invalidate(){materialsRequest++;}}", APP_CODE)
        self.assertIn("{id:'products-view',view:'products',invalidate(){productsRequest++;}}", APP_CODE)

    def test_every_dialog_stale_guard_survives(self):
        for name in ('materialMasterDialog', 'receiptForm', 'materialHistoryDialog',
                     'materialBatchTraceabilityDialog', 'bomDialog', 'bomForm', 'bomHistoryDialog',
                     'productMappingDialog', 'productMappingForm', 'unmapProductForm',
                     'productMappingHistoryDialog'):
            body = renderer(name)
            with self.subTest(dialog=name):
                self.assertIn('epoch', body, f'{name} must still capture the session generation')
                self.assertIn('dialogVersion', body, f'{name} must still capture the modal generation')
                self.assertIn("$('dialog').open", body, f'{name} must still check the dialog is open')

    def test_the_shared_dialog_lifecycle_is_untouched(self):
        for name in BAHAN_BAKU_RENDERERS + MASTER_SKU_RENDERERS:
            if name in ('loadMaterials', 'loadProducts', 'paintProducts', 'bomComponentsHTML'):
                continue
            with self.subTest(dialog=name):
                self.assertIn('guardPending()', renderer(name),
                              f'{name} must still refuse to open over a pending transaction')
        # No new sheet system, no second modal element, no bespoke close path.
        self.assertEqual(len(re.findall(r'\.showModal\(\)', APP_CODE)), 1)
        for forbidden in ('new Dialog(', 'popover', 'showPopover', '<dialog'):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, code(renderer('materialHistoryDialog')))


class ContainmentTest(unittest.TestCase):
    def test_the_a62_css_block_only_addresses_these_two_workspaces(self):
        selectors = [part.strip() for match in re.finditer(r'([^{}]+)\{', A62_BLOCK)
                     for part in match.group(1).split(',') if part.strip()
                     and not part.strip().startswith('@')]
        self.assertTrue(selectors)
        allowed = ('#materials-view', '#products-view', '#materials-message', '#products-message',
                   '#materials-inventory-note', '#products-mapping-note', '#batch-list',
                   '#product-list', '#material-master-list', '.materials-work', '.products-work')
        for selector in selectors:
            with self.subTest(selector=selector):
                self.assertTrue(any(name in selector for name in allowed),
                                f'{selector} is not scoped to a A6.2 workspace')

    def test_the_a62_block_redefines_no_a60_primitive(self):
        for protected in (r'\.workspace-title', r'\.workspace-heading', r'\.data-row', r'\.data-cell',
                          r'\.data-surface', r'\.record-row', r'\.record-list', r'\.command-bar',
                          r'\.status-chip', r'\.timeline', r'\.detail-grid', r'\.field',
                          r'\.action-primary', r'\.empty-state', r'\.metric-card'):
            with self.subTest(protected=protected):
                self.assertNotRegex(A62_BLOCK, protected + r'[^{]*\{')

    def test_the_a62_block_adds_no_material_and_no_per_row_blur(self):
        self.assertNotRegex(A62_BLOCK, r'backdrop-filter|filter\s*:\s*blur')
        # Repeated rows stay cheap: no row, cell or chip gets its own surface here.
        for row in (r'\.data-row\s*\{', r'\.record-row\s*\{', r'\.data-cell\s*\{',
                    r'\.status-chip\s*\{', r'\.timeline-item\s*\{'):
            with self.subTest(row=row):
                self.assertNotRegex(A62_BLOCK, row)

    def test_the_narrow_width_table_floor_is_rem_based(self):
        narrow = A62_BLOCK[A62_BLOCK.index('@media(max-width:980px)'):]
        self.assertRegex(narrow, r'#batch-list>table\{min-width:\d+(\.\d+)?rem\}',
                         'the floor must be rem so 200% text grows the columns instead of '
                         're-crushing them')
        self.assertIn('min-height:var(--touch-target-min)', narrow)

    def test_no_a6_primitive_name_leaks_into_a_stylesheet_or_the_shell_modules(self):
        # The A6.0 containment test owns this rule globally; it is repeated here for the two names
        # A6.2 introduced, because a class attribute in a stylesheet has no allow-list at all.
        for text, label in ((CSS, 'style.css'), (SHELL, 'workspace.css')):
            for name in ('data-surface', 'record-list', 'workspace-heading', 'command-bar'):
                with self.subTest(sheet=label, name=name):
                    self.assertNotRegex(text, r'class="[^"]*(?<![\w-])' + name + r'(?![\w-])')


class FrozenSurfacesTest(unittest.TestCase):
    def test_a61_produksi_markup_is_untouched(self):
        self.assertIn('<h1 class="workspace-title">Produksi</h1>', BOARD)
        self.assertIn('Pantau order, progres, kendala, dan output produksi.', BOARD)
        for primitive in ('metric-strip', 'command-bar', 'command-search', 'attention-note',
                          'data-surface', 'info-panel'):
            with self.subTest(primitive=primitive):
                self.assertIn(primitive, BOARD)
        for owner in ('loadBoard', 'renderDetail', 'renderHistory', 'renderIssues', 'orderForm'):
            with self.subTest(owner=owner):
                self.assertIn('class="', renderer(owner))
        # The board's own data hierarchy is still warehouse-over-target, not a completion figure.
        self.assertIn('order.totals.warehouse / order.target_quantity', renderer('loadBoard'))

    def test_the_a61_css_block_is_still_present_and_still_scoped(self):
        self.assertIn('#board-view,#detail-view{max-width:1360px', CSS)
        self.assertIn('#order-list.is-refreshing{opacity:.78}', CSS)
        self.assertIn('#detail-content .utility-rows', CSS)

    def test_the_a52_shell_and_a53_lens_are_untouched(self):
        for selector in ('.app-shell', '.app-sidebar', '.masthead', '.workspace-main',
                         '.nav-item', '.window-controls'):
            with self.subTest(selector=selector):
                self.assertIn(selector, SHELL, f'{selector} must still be owned by the shell')
        # A6.2 declares nothing about the shell, the lens or the traffic lights.
        for selector in ('.app-shell', '.app-sidebar', '.masthead', '.workspace-main',
                         '.nav-item', '.window-controls', 'traffic', 'lens', 'wallpaper'):
            with self.subTest(selector=selector):
                self.assertNotIn(selector, A62_BLOCK)

    def test_the_a3_spring_constants_are_unchanged(self):
        spring = ROOT / 'tests' / 'browser_navigation_spring.cjs'
        self.assertTrue(spring.exists())
        for token in ('--motion-fast', '--motion-base', '--motion-enter'):
            with self.subTest(token=token):
                self.assertIn(token, CSS)
        # A6.2 introduces no duration, no easing and no keyframe of its own.
        self.assertNotRegex(A62_BLOCK, r'@keyframes|animation\s*:|transition\s*:')

    def test_no_new_frame_clock_or_timer(self):
        for owner in BAHAN_BAKU_RENDERERS + MASTER_SKU_RENDERERS + ('reasonField',):
            body = code(renderer(owner))
            with self.subTest(owner=owner):
                for clock in ('requestAnimationFrame', 'setInterval', 'requestIdleCallback',
                              'setTimeout'):
                    self.assertNotIn(clock, body, f'{owner} must not start a {clock}')

    def test_the_primitive_stylesheet_itself_was_not_edited_for_these_pages(self):
        for page_specific in ('materials-view', 'products-view', 'batch-list', 'product-list',
                              'material-master-list', 'materials-work', 'products-work'):
            with self.subTest(name=page_specific):
                self.assertNotIn(page_specific, PRIMITIVES,
                                 'A6.0 stays generic; A6.2 must not name a page inside it')


class VersionAndBackendTest(unittest.TestCase):
    def test_version_is_aligned_across_every_source(self):
        version = re.search(r'^version = "([^"]+)"',
                            (ROOT / 'pyproject.toml').read_text(encoding='utf-8'), re.M).group(1)
        self.assertEqual(version, '0.113.0',
                         'A6.2 is a visible master-data workspace migration milestone')
        self.assertIn(f'version="{version}"', (ROOT / 'beeloft' / 'api.py').read_text(encoding='utf-8'))
        contract = json.loads((ROOT / 'docs' / 'openapi.json').read_text(encoding='utf-8'))
        self.assertEqual(contract['info']['version'], version)

    def test_no_schema_change_and_no_migration(self):
        versions = [int(value) for path in (ROOT / 'beeloft').glob('*.sql')
                    for value in re.findall(r'PRAGMA user_version\s*=\s*(\d+)',
                                            path.read_text(encoding='utf-8'))]
        self.assertEqual(max(versions), 55, 'A6.2 is presentation only')

    def test_no_backend_route_was_added_or_changed(self):
        from tempfile import TemporaryDirectory

        from beeloft.api import create_app
        contract = json.loads((ROOT / 'docs' / 'openapi.json').read_text(encoding='utf-8'))
        with TemporaryDirectory() as folder:
            live = create_app(Path(folder) / 'contract.sqlite3').openapi()
        self.assertEqual(contract['paths'], live['paths'])
        self.assertEqual(contract.get('components'), live.get('components'))

    def test_the_endpoints_these_pages_use_are_exactly_the_existing_ones(self):
        contract = json.loads((ROOT / 'docs' / 'openapi.json').read_text(encoding='utf-8'))
        for path in ('/api/materials', '/api/material-batches', '/api/material-batches/{batch_id}',
                     '/api/material-batches/{batch_id}/movements',
                     '/api/material-batches/{batch_id}/traceability',
                     '/api/material-batches/scan', '/api/products',
                     '/api/product-external-mappings', '/api/products/{product_id}/bom',
                     '/api/products/{product_id}/bom-history'):
            with self.subTest(path=path):
                self.assertIn(path, contract['paths'], f'{path} must already exist')
        # And no field was invented client-side to decorate the design.
        for invented in ('stock_health', 'replenishment_risk', 'shortage', 'sales', 'sync_status',
                         'bom_completeness', 'forecast'):
            with self.subTest(invented=invented):
                self.assertNotIn(invented, code(renderer('loadMaterials')))
                self.assertNotIn(invented, code(renderer('paintProducts')))


if __name__ == '__main__':
    unittest.main()
