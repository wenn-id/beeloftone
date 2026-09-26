"""A6.1's migration of the Produksi workspace onto the A6.0 primitives, as a static contract.

A6.0 built the shared inner-workspace language and deliberately kept it out of shipped markup.
A6.1 is the first phase that spends it: the production board (`#board-view`), the production
order detail (`#detail-view`) and the create-order form are rebuilt out of those primitives.

That makes this file a *truth* contract far more than a styling one. A visual migration of an
operational workspace is exactly the change where meaning is easiest to lose by accident, so what
is asserted here is mostly that nothing moved except presentation:

  * the four board metrics are still the four real `summary.*` fields with their real units;
  * progress is still `totals.warehouse / target_quantity` and is never relabelled as completion;
  * every filter id, every query parameter and every status value is byte-identical;
  * the stage read-out is still a set of CURRENT balances, never a cumulative funnel;
  * not one `data-action` was dropped when 25 flat buttons became three workflow groups;
  * no permission check moved out of JS, and none moved into CSS;
  * the A5.2 shell, the A5.3 lens, the A3 spring and the frame/timer budget are untouched;
  * no route, no schema, no migration.

The behavioural half lives in tests/browser_production_modern_workspace.cjs. The containment half
- that A6 primitives reached Produksi and nothing else - stays in
tests/test_apple27_modern_workspace_foundation_contract.py, which A6.1 narrowed on purpose.
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


def renderer(name):
    """One top-level function body from app.mjs.

    Declarations in this file all start at column zero, so the next one is the end of this one.
    That is enough to scope an assertion to a single renderer without brace matching, which
    template literals full of `${...}` would defeat.
    """
    start = re.search(r'^(?:async )?function ' + re.escape(name) + r'\(', APP, re.M)
    assert start, f'{name}() is missing from app.mjs'
    following = re.search(r'^(?:async )?function \w+\(|^const \w+ =', APP[start.end():], re.M)
    return APP[start.start():start.end() + (following.start() if following else len(APP))]


def code_css(source):
    """CSS with comments removed, for the same reason `code()` exists for JavaScript: the A6.1
    containment banner names every legacy class and every other workspace it is NOT touching."""
    return re.sub(r'/\*.*?\*/', '', source, flags=re.S)


def code(source):
    """`source` with its comments removed.

    Every "this must not appear" assertion below runs against this rather than the raw text. The
    renderers are heavily commented, and several of those comments necessarily NAME the thing
    being ruled out - "bukan 'produksi selesai'", "bukan grafik" - so matching raw source would
    fail on the prose that documents the rule. String literals are deliberately left intact:
    the markup lives inside template literals, and that markup is the subject.
    """
    return re.sub(r'(?<!:)//[^\n]*', '', re.sub(r'/\*.*?\*/', '', source, flags=re.S))


A61_BLOCK = code_css(CSS)
# The A6.1 block used to run to the end of the file, because it WAS the end of the file. A6.2
# appends its own containment block after it, so the slice is now bounded by that block's first
# selector instead. This keeps the assertions below meaning exactly what they meant when they were
# approved - "the A6.1 block is contained to Produksi" - rather than widening their allow-list to
# cover a later phase's rules, which would have quietly retired the guarantee. A6.2's own block is
# held to the same standard by tests/test_apple27_materials_master_sku_contract.py.
A61_BLOCK = A61_BLOCK[A61_BLOCK.index('#board-view,#detail-view{max-width:1360px'):
                      A61_BLOCK.index('#materials-view,#products-view{max-width:1360px')]

BOARD = section(HTML, 'board-view')
DETAIL = section(HTML, 'detail-view')
LOAD_BOARD = renderer('loadBoard')
RENDER_DETAIL = renderer('renderDetail')

# Every `data-action` the pre-A6.1 order detail exposed, in the three workflow groups A6.1
# recomposed them into. Reordering and regrouping is the whole point of the change; LOSING one
# would silently remove a production capability, which is what this list exists to prevent.
ORDER_ACTIONS = {
    'edit-order', 'new-production-change-request', 'production-change-requests', 'order-changes',
    'requirements', 'reservations', 'consumption', 'production-cost', 'contribution-margin',
    'order-purchases',
    'cutting-runs', 'bundles', 'sewing-jobs', 'finishing-records', 'final-qc-records',
    'rework-completions', 'finished-goods', 'warehouse', 'issue-material', 'order-materials',
    'marketplace-reservations', 'marketplace-picks', 'marketplace-packs',
    'marketplace-shipments', 'marketplace-returns', 'finished-goods-adjustments',
    'finished-goods-stock-counts',
}


class BoardIdentityTest(unittest.TestCase):
    def test_the_page_identity_is_modern_and_concise(self):
        self.assertIn('<h1 class="workspace-title">Produksi</h1>', BOARD)
        self.assertIn('<p class="workspace-subtitle">Pantau order, progres, kendala, dan output '
                      'produksi.</p>', BOARD)
        # The old identity is gone from the whole product, not just moved down the page.
        self.assertNotIn('Yang sedang dikerjakan.', HTML)
        self.assertNotIn('Papan produksi</p>', HTML)
        # It consumes the shared A6.0 heading grammar rather than a Produksi-only one: A6.1 is
        # the proof that A6.0 is reusable, so inventing a second heading system here would
        # defeat the phase.
        for primitive in ('workspace-page', 'workspace-heading', 'workspace-heading-copy',
                          'workspace-title', 'workspace-subtitle', 'workspace-actions'):
            with self.subTest(primitive=primitive):
                self.assertIn(f'class="{primitive}"', BOARD)

    def test_the_create_order_action_keeps_its_role_gate_in_javascript(self):
        # Hidden in markup, revealed by the same single line of JS as before. A CSS-derived
        # permission would be a security regression, not a styling choice.
        self.assertRegex(BOARD, r'<button id="new-order"[^>]*\bhidden\b')
        self.assertIn("$('new-order').hidden=me.role!=='admin';", APP)
        for pattern in (r'#new-order[^{]*\{[^}]*display', r'\[data-action=new-order\]',
                        r'role\s*==?=?\s*[\'"]admin[\'"]'):
            with self.subTest(pattern=pattern):
                self.assertNotRegex(CSS, pattern, 'permissions are never derived in CSS')
        self.assertNotRegex(PRIMITIVES, r'role\s*==?=?\s*[\'"]admin[\'"]')


class MetricTruthTest(unittest.TestCase):
    def test_the_four_metrics_are_the_four_real_summary_fields(self):
        strip = re.search(r"\$\('summary'\)\.innerHTML = \[(.*?)\]\.map", LOAD_BOARD, re.S)
        self.assertIsNotNone(strip, 'the metric strip is built from one declared table')
        rows = re.findall(r"\['([^']+)', s\.(\w+), '(\w+)', '([\w-]+)', ([^\]]+)\]", strip.group(1))
        self.assertEqual([(label, field, unit) for label, field, unit, _, _ in rows], [
            ('Order aktif', 'active', 'order'),
            ('Lewat target', 'overdue', 'order'),
            ('Dalam proses', 'in_progress', 'pcs'),
            ('Perlu rework', 'rework', 'pcs'),
        ], 'the metric strip is the existing board summary, with its existing units')
        # Nothing invented: no trend, estimate, efficiency, health score or growth anywhere in
        # the two migrated renderers.
        for forbidden in ('trend', 'efficiency', 'health', 'growth', 'forecast', 'estimasi',
                          'throughput', 'velocity'):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, code(LOAD_BOARD).lower())

    def test_the_metric_strip_is_a6_and_is_never_a_selected_tab(self):
        self.assertIn('class="metric-strip"', BOARD)
        for primitive in ('metric-card', 'metric-icon', 'metric-label', 'metric-value'):
            with self.subTest(primitive=primitive):
                self.assertIn(primitive, LOAD_BOARD)
        # A6 tints the icon tile only, so a metric can never read as a selection. The old
        # `.production-wip` emphasis - a filled card with a blue border - is gone entirely.
        self.assertNotIn('production-wip', code(APP))
        self.assertNotIn('production-wip', CSS)
        # Tone follows the data, and only for the two exception metrics.
        self.assertIn("s.overdue > 0 ? 'metric-card-danger' : ''", LOAD_BOARD)
        self.assertIn("s.rework > 0 ? 'metric-card-warning' : ''", LOAD_BOARD)
        # No chart, and no comparison copy, belongs in the strip.
        for forbidden in ('<svg viewBox', 'barchart', 'sparkline', 'dibanding', 'vs '):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, code(LOAD_BOARD))

    def test_the_strip_stays_denser_than_the_data(self):
        # A metric card is capped well below the data surface it introduces; the workspace is a
        # productivity page, so the KPI band may not own the first viewport.
        card = re.search(r'\.metric-card\{([^}]*)\}', PRIMITIVES).group(1)
        height = re.search(r'min-height:(\d+)px', card)
        self.assertIsNotNone(height)
        self.assertLessEqual(int(height.group(1)), 110)


class IssueSummaryTest(unittest.TestCase):
    def test_the_open_issue_action_is_preserved_exactly(self):
        self.assertIn("$('issues-summary').onclick = () => { resetBoardFilters(); "
                      "$('status').value = 'blocked'; loadBoard(); };", APP)
        self.assertIn('id="issues-summary"', BOARD)

    def test_it_is_a_compact_attention_surface_with_a_quiet_cleared_state(self):
        self.assertIn('class="attention-note"', BOARD)
        for primitive in ('attention-note-copy', 'attention-note-title', 'attention-note-reason'):
            with self.subTest(primitive=primitive):
                self.assertIn(primitive, LOAD_BOARD)
        # Raised vs cleared, and the legacy hook the state is still read through.
        self.assertIn("classList.toggle('has-issues', openIssues > 0)", LOAD_BOARD)
        self.assertIn("classList.toggle('attention-note-critical', openIssues > 0)", LOAD_BOARD)
        self.assertIn("classList.toggle('attention-note-success', openIssues === 0)", LOAD_BOARD)
        self.assertIn('kendala terbuka', LOAD_BOARD)
        # An attention note, not a banner: the primitive is a bordered inline panel, and the
        # count never becomes a page-level heading.
        self.assertNotRegex(LOAD_BOARD, r"issues-summary'\)\.innerHTML = `<h[12]")

    def test_the_cleared_state_is_quieter_than_the_raised_one(self):
        """The two states carry different weights of message, so they get different weights.

        An all-clear should be confirmable at a glance and then ignored; a full-width, two-line,
        green-edged panel announcing that nothing is wrong was taking space from the data. Only
        layout changes - same element, same DOM, same click behaviour, same state classes.
        """
        cleared = re.search(r'#issues-summary\.attention-note-success\{([^}]*)\}', CSS)
        self.assertIsNotNone(cleared, 'the cleared state has its own compact treatment')
        block = cleared.group(1)
        self.assertIn('width:auto', block, 'it shrink-wraps instead of spanning the workspace')
        self.assertIn('align-self:flex-start', block)
        self.assertRegex(block, r'padding:\d+px', 'and takes a compact padding step')
        # One row: the count and the reason share a line rather than stacking.
        self.assertRegex(CSS, r'#issues-summary\.attention-note-success>\.attention-note-copy'
                              r'\{[^}]*flex-direction:row')
        # The green stays in the tint and the check, not in a callout edge.
        self.assertIn('border-color:var(--workspace-edge)', block)
        # The separator is drawn, so it never enters the accessible name or the text content.
        self.assertRegex(CSS, r'\.attention-note-reason::before\{content:"·"')
        self.assertNotIn('·', re.search(r"attention-note-reason\">\$\{openIssues > 0 \? "
                                        r"'[^']*' : '([^']*)'\}", LOAD_BOARD).group(1))
        # A phone stacks the two runs and withdraws the separator rather than orphaning it.
        phone = CSS[CSS.index('@media(max-width:650px){', CSS.index('A6.1 · Produksi containment')):]
        phone = phone[:phone.index('\n}')]
        self.assertIn('flex-direction:column', phone)
        self.assertIn('content:none', phone)
        # The RAISED state is untouched and keeps the prominent treatment.
        self.assertNotRegex(CSS, r'#issues-summary\.attention-note-critical\{')

    def test_the_stage_filter_hint_is_secondary_without_losing_a_word(self):
        hint = re.search(r'#production-filter-hint\{([^}]*)\}', CSS)
        self.assertIsNotNone(hint)
        self.assertIn('background:none', hint.group(1), 'a caption, not a filled panel')
        self.assertIn('font-size:var(--type-metadata)', hint.group(1))
        # Every word, and the programmatic relationship, survive the visual reduction.
        markup = re.search(r'<p id="production-filter-hint"[^>]*>(.*?)</p>', BOARD, re.S).group(1)
        self.assertIn('Posisi barang menampilkan order yang masih memiliki saldo di tahap '
                      'tersebut.', markup)
        self.assertIn('Ringkasan di atas mencakup seluruh produksi.', markup)
        self.assertRegex(BOARD, r'id="board-stage"[^>]*aria-describedby="production-filter-hint"')

    def test_the_polish_did_not_shrink_the_things_it_was_told_not_to(self):
        """The review allowed weight to come off the two informational strips and nothing else."""
        # The page title, the metric figure and the data row keep their A6.0 scale.
        self.assertRegex(PRIMITIVES, r'\.workspace-title\{[^}]*font-size:var\(--type-page-title\)')
        self.assertRegex(PRIMITIVES, r'\.metric-value\{[^}]*font-size:1\.5rem')
        self.assertRegex(PRIMITIVES, r'\.data-row\{height:var\(--workspace-row-height\)')
        # And no A6.1 rule reaches into any of them, or into the command bar or the table.
        for protected in (r'\.workspace-title', r'\.metric-value', r'\.metric-card\{',
                          r'\.data-row', r'\.data-cell', r'\.command-bar', r'\.status-chip',
                          r'\.progress-native'):
            with self.subTest(protected=protected):
                self.assertNotRegex(A61_BLOCK, protected + r'[^{]*\{')


class CommandBarTest(unittest.TestCase):
    def test_the_stacked_filter_form_became_the_a6_command_bar(self):
        self.assertIn('<form id="search-form" class="command-bar">', BOARD)
        for primitive in ('command-search', 'command-filters', 'command-filter', 'command-actions'):
            with self.subTest(primitive=primitive):
                self.assertIn(f'class="{primitive}"', BOARD)
        # The legacy toolbar vocabulary is gone from this page...
        for legacy in ('class="filters"', 'class="search-field"'):
            with self.subTest(legacy=legacy):
                self.assertNotIn(legacy, BOARD)
        # ...and its id-scoped grid is gone from the stylesheet, rather than being overridden by
        # something even more specific. An id beats a class, so leaving it would have kept the
        # old stacked layout alive underneath the command bar.
        self.assertNotRegex(CSS, r'#search-form\s*[,{]')
        # Exactly one status control. A duplicate segmented filter driving the same state is
        # explicitly not wanted just because A6.0 ships one.
        self.assertNotIn('segmented-filter', BOARD)
        self.assertNotIn('filter-chip', BOARD)

    def test_every_filter_id_and_accessible_name_survives(self):
        for element_id, label in (('search', 'Cari order atau SKU'), ('status', 'Status'),
                                  ('board-owner', 'PIC order'), ('board-stage', 'Posisi barang')):
            with self.subTest(control=element_id):
                self.assertRegex(BOARD, r'id="' + element_id + r'"[^>]*aria-label="' + label + '"')
        for element_id in ('reset-board', 'refresh', 'new-order', 'previous', 'next',
                           'page-count', 'updated', 'board-message', 'order-list',
                           'production-filter-hint', 'issues-summary', 'summary'):
            with self.subTest(control=element_id):
                self.assertIn(f'id="{element_id}"', BOARD)
        self.assertIn('class="production-search', BOARD)
        # The submit affordance and Enter both still work: a real submit button in a real form.
        self.assertRegex(BOARD, r'<button type="submit" class="production-search')
        self.assertIn("$('search-form').onsubmit = event => { event.preventDefault(); "
                      "offset = 0; loadBoard(); };", APP)

    def test_the_query_contract_is_byte_identical(self):
        self.assertIn("const query = new URLSearchParams({q:$('search').value.trim(), "
                      "status:$('status').value, owner_id:$('board-owner').value, "
                      "stage:$('board-stage').value, limit:25, offset});", APP)
        # No debounced or per-keystroke search was introduced.
        self.assertNotRegex(APP, r"\$\('search'\)\.on(input|keyup|keydown)")
        self.assertNotIn('debounce', APP)

    def test_status_and_stage_values_are_unchanged(self):
        status = re.search(r'<select id="status"[^>]*>(.*?)</select>', BOARD, re.S).group(1)
        self.assertEqual(re.findall(r'value="([^"]*)"', status),
                         ['all', 'active', 'overdue', 'blocked', 'closed'])
        self.assertEqual(re.findall(r'>([^<]+)</option>', status),
                         ['Semua order', 'Aktif', 'Lewat target', 'Ada kendala terbuka',
                          'Selesai / ditutup'])
        stage = re.search(r'<select id="board-stage"[^>]*>(.*?)</select>', BOARD, re.S).group(1)
        self.assertEqual(re.findall(r'value="([^"]*)"', stage),
                         ['all', 'planned', 'cutting', 'sewing', 'finishing', 'qc', 'rework',
                          'reject', 'warehouse'])
        self.assertEqual(re.findall(r'>([^<]+)</option>', stage),
                         ['Semua posisi', 'Belum cutting', 'Cutting', 'Sewing', 'Finishing',
                          'QC', 'Rework', 'Reject', 'Gudang'])
        # Changing any of the three is still immediate and still resets the page.
        self.assertIn("$('status').onchange = $('board-owner').onchange = "
                      "$('board-stage').onchange = () => { offset = 0; loadBoard(); };", APP)

    def test_the_stage_filter_explanation_survives_as_a_utility_note(self):
        hint = re.search(r'<p id="production-filter-hint"[^>]*>(.*?)</p>', BOARD, re.S).group(1)
        self.assertIn('class="info-panel"', BOARD)
        self.assertIn('Posisi barang menampilkan order yang masih memiliki saldo di tahap '
                      'tersebut.', hint)
        self.assertIn('Ringkasan di atas mencakup seluruh produksi.', hint)
        # Still programmatically attached to the control it explains.
        self.assertRegex(BOARD, r'id="board-stage"[^>]*aria-describedby="production-filter-hint"')

    def test_the_owner_fallback_and_the_quiet_reset_are_untouched(self):
        self.assertIn("if (ownerId && !result.owners.some(owner => owner.id === ownerId)) "
                      "$('board-owner').insertAdjacentHTML('beforeend',option(ownerId,"
                      "previousOwnerLabel || 'PIC tidak lagi memiliki order'));", APP)
        self.assertIn("$('board-owner').value = ownerId;", APP)
        self.assertIn("function resetBoardFilters() { $('search').value = ''; "
                      "$('status').value = 'all'; $('board-owner').value = ''; "
                      "$('board-stage').value = 'all'; offset = 0; }", APP)
        # Reset is visually quiet and does not compete with the primary action.
        self.assertRegex(BOARD, r'id="reset-board"[^>]*class="action-quiet"')
        self.assertRegex(BOARD, r'id="new-order"[^>]*class="action-primary"')


class OrderSurfaceTest(unittest.TestCase):
    def test_the_order_list_is_the_primary_a6_data_surface(self):
        self.assertRegex(BOARD, r'id="order-list" class="list-host data-surface"')
        # A real table with real header cells, and no hand-rolled ARIA table roles.
        self.assertIn('<table><thead class="data-header"><tr>', LOAD_BOARD)
        self.assertEqual(LOAD_BOARD.count('<th scope="col">'), 6)
        for forged in ('role="table"', 'role="row"', 'role="cell"', 'role="columnheader"'):
            with self.subTest(forged=forged):
                self.assertNotIn(forged, code(LOAD_BOARD))
        # The legacy grid vocabulary is gone from the rendered row.
        for legacy in ('order-grid', 'table-head', 'cell-label', 'progress-cell', 'status-cell',
                       'progress-note'):
            with self.subTest(legacy=legacy):
                self.assertNotIn(legacy, code(LOAD_BOARD))
        # The compatibility classes the rest of the product still addresses are kept.
        self.assertIn('<tr class="order-row data-row">', LOAD_BOARD)
        self.assertIn('class="order-title data-primary"', LOAD_BOARD)
        self.assertIn('class="reference"', LOAD_BOARD)

    def test_each_row_exposes_exactly_one_detail_trigger(self):
        row = LOAD_BOARD[LOAD_BOARD.index('<tr class="order-row data-row">'):]
        row = row[:row.index('</tr>')]
        self.assertEqual(row.count('<button'), 1,
                         'a row has one control, so its accessible name is unambiguous')
        self.assertIn('data-action="detail"', row)
        self.assertIn('data-id="${e(order.id)}"', row)
        # The trailing chevron is an affordance, not a second control.
        self.assertIn("svgIcon('arrow-right','icon-sm')", row)

    def test_the_order_cell_hierarchy_is_reference_then_title_then_scale(self):
        self.assertRegex(LOAD_BOARD, r'<span class="reference">\$\{e\(order\.reference\)\}</span>'
                                     r'\$\{e\(order\.title\)\}')
        self.assertIn('<span class="data-secondary">${order.lines.length} SKU · target '
                      '${n(order.target_quantity)} pcs</span>', LOAD_BOARD)
        # No invented imagery: the board API returns no product image, so none is faked.
        for forged in ('<img', 'thumbnail', 'avatar', 'placeholder.', 'picsum', 'gravatar'):
            with self.subTest(forged=forged):
                self.assertNotIn(forged, code(LOAD_BOARD))

    def test_progress_still_means_warehouse_over_target(self):
        self.assertIn('const progress = Math.round(order.totals.warehouse / '
                      'order.target_quantity * 100);', LOAD_BOARD)
        self.assertIn('${n(order.totals.warehouse)} / ${n(order.target_quantity)} pcs',
                      LOAD_BOARD)
        self.assertIn('aria-label="Jumlah diterima gudang ${e(order.reference)}"', LOAD_BOARD)
        # A6 progress grammar on a native element, because the settle animation drives `.value`.
        self.assertIn('class="progress-meter progress-meter-stack"', LOAD_BOARD)
        self.assertIn('class="progress-native"', LOAD_BOARD)
        self.assertRegex(LOAD_BOARD, r'<progress class="progress-native" '
                                     r'data-order="\$\{e\(order\.id\)\}" '
                                     r'value="\$\{order\.totals\.warehouse\}" '
                                     r'max="\$\{order\.target_quantity\}"')
        # It is never relabelled as production completion.
        for wrong in ('selesai produksi', 'produksi selesai', 'completion', 'penyelesaian produksi'):
            with self.subTest(wrong=wrong):
                self.assertNotIn(wrong, code(LOAD_BOARD).lower())

    def test_the_progress_settle_animation_is_the_existing_one(self):
        # One animation system, still keyed on the rendered rows, still comparing against what
        # is on screen, still inert on first load and under reduced motion.
        self.assertIn("for (const node of document.querySelectorAll("
                      "'.order-row progress[data-order]'))", APP)
        self.assertIn('if (!before.size || reducedMotion()) return;', APP)
        self.assertIn('playProgressSettle(progressBefore);', LOAD_BOARD)
        self.assertEqual(len(re.findall(r'function playProgressSettle\(', APP)), 1)

    def test_status_mapping_is_truthful_and_not_colour_only(self):
        status = renderer('statusHTML')
        self.assertIn("order.overdue ? ['danger', 'Lewat target']", status)
        self.assertIn("order.status === 'completed' ? ['success', 'Selesai']", status)
        self.assertIn("order.status === 'closed_with_reject' ? ['warning', "
                      "'Ditutup · ada reject']", status)
        self.assertIn("['info', 'Dalam produksi']", status)
        self.assertIn('class="status-chip status-chip-${tone}"', status)
        self.assertIn('class="status-dot" aria-hidden="true"', status)
        self.assertNotIn('status-label', code(status))
        # The issue indicator stays secondary, and stays complete for a screen reader.
        issue = renderer('issueBadge')
        self.assertIn('status-chip status-chip-warning', issue)
        self.assertIn('${n(order.open_issues)} kendala', issue)
        self.assertIn('<span class="visually-hidden"> terbuka</span>', issue)

    def test_pagination_is_unchanged(self):
        self.assertIn("$('previous').onclick = () => { offset = Math.max(0, offset - 25); "
                      "loadBoard(); };", APP)
        self.assertIn("$('next').onclick = () => { offset += 25; loadBoard(); };", APP)
        self.assertIn("$('page-count').textContent = result.total ? `${offset + 1}–"
                      "${Math.min(offset + 25,result.total)} dari ${n(result.total)} order` "
                      ": '0 order';", APP)
        self.assertIn("$('previous').disabled = offset === 0; "
                      "$('next').disabled = offset + 25 >= result.total;", APP)
        # No infinite scrolling was introduced.
        self.assertNotIn('IntersectionObserver', APP)

    def test_the_two_empty_states_stay_distinct_and_honest(self):
        self.assertIn("if (result.summary.orders) pageState('board-message', 'empty', "
                      "'Tidak ada order yang cocok.'", LOAD_BOARD)
        self.assertIn("else if (user.role === 'admin') pageState('board-message', 'empty', "
                      "'Belum ada order.'", LOAD_BOARD)
        self.assertIn("else pageState('board-message', 'empty', 'Belum ada order produksi.', "
                      "'Minta admin membuat order untuk tim.');", LOAD_BOARD)
        # The genuine-empty action is offered to admin only, and it is the real action.
        admin_branch = LOAD_BOARD[LOAD_BOARD.index("user.role === 'admin'"):
                                  LOAD_BOARD.index("else pageState")]
        self.assertIn('data-action="new-order"', admin_branch)
        self.assertIn('class="action-primary"', admin_branch)

    def test_the_request_lifecycle_and_stale_guards_are_intact(self):
        self.assertIn('const version = epoch, request = ++boardRequest;', LOAD_BOARD)
        self.assertIn("if (version !== epoch || request !== boardRequest || view !== 'board') "
                      'return;', LOAD_BOARD)
        # The rendered-query identity, which the replacement motion depends on.
        self.assertIn('const rendered = query.toString();', LOAD_BOARD)
        self.assertIn('const replacing = refreshing && boardQuery !== rendered;', LOAD_BOARD)
        self.assertIn('boardQuery = rendered;', LOAD_BOARD)
        # Refresh keeps the rows; only a load from scratch shows the placeholder.
        self.assertIn("const refreshing = markRefreshing('order-list');", LOAD_BOARD)
        self.assertIn("if (!refreshing) { pageState('board-message', 'loading', "
                      "'Memuat posisi produksi…'); $('order-list').hidden = true; }", LOAD_BOARD)
        # A failure still routes 401 through the authentication path and never presents stale
        # data as current without saying so.
        self.assertIn("if (error.status === 401) fail(error, 'board-message');", LOAD_BOARD)
        self.assertIn("else pageState('board-message', 'error', error.message);", LOAD_BOARD)
        self.assertIn('const version = epoch, request = ++detailRequest;', APP)
        self.assertIn("if (version !== epoch || request !== detailRequest || view !== 'detail') "
                      'return;', APP)
        # No skeleton delay and no new polling were added.
        self.assertNotIn('skeleton', code(LOAD_BOARD))


class DetailTest(unittest.TestCase):
    def test_the_detail_page_is_the_same_modern_language(self):
        self.assertIn('class="workspace-page"', DETAIL)
        self.assertIn('<div id="detail-content" class="workspace-page">', DETAIL)
        # Reference as context, title as the page's own heading.
        self.assertIn('<p class="workspace-eyebrow">${e(o.reference)}</p>', RENDER_DETAIL)
        self.assertIn('<h1 class="workspace-title">${e(o.title)}</h1>', RENDER_DETAIL)
        self.assertIn('data-action="refresh-detail"', RENDER_DETAIL)
        # Back behaviour and focus restoration are untouched.
        self.assertIn("$('back').onclick = () => { showBoard(); $('search').focus(); };", APP)
        self.assertIn('Semua order</button>', DETAIL)

    def test_the_four_order_facts_use_the_shared_detail_grid(self):
        grid = re.search(r'<dl class="detail-grid">(.*?)</dl>', RENDER_DETAIL, re.S).group(1)
        self.assertEqual(re.findall(r'<dt>([^<]+)</dt>', grid),
                         ['Penanggung jawab', 'Target selesai', 'Target produksi', 'Status'])
        self.assertEqual(grid.count('class="detail-field"'), 4)
        self.assertIn('${statusHTML(o)}', grid)
        self.assertNotIn('detail-meta', code(RENDER_DETAIL))

    def test_the_flat_action_list_became_three_groups_without_losing_an_action(self):
        declared = re.findall(r"\['([a-z0-9-]+)', '[^']*', '(command|row)'\]", RENDER_DETAIL)
        self.assertEqual({action for action, _ in declared}, ORDER_ACTIONS,
                         'every pre-A6.1 order action is still rendered, and no new one appeared')
        self.assertEqual(len(declared), len(ORDER_ACTIONS), 'and none is declared twice')
        self.assertEqual(len(re.findall(r"\['(?:Order &amp; perencanaan|Alur produksi|"
                                        r"Fulfilment &amp; marketplace)'", RENDER_DETAIL)), 3)
        self.assertIn('class="utility-panel"', RENDER_DETAIL)
        self.assertIn('class="utility-panel-title"', RENDER_DETAIL)
        self.assertIn('class="panel-grid"', RENDER_DETAIL)
        self.assertNotIn('order-settings', code(RENDER_DETAIL))
        # The weight is decided by what an action MEANS, and the split is the load-bearing part:
        # an action that opens a record is a navigational row, and only a real command stays
        # button-shaped. Three commands, everything else a row.
        weights = {action: weight for action, weight in declared}
        self.assertEqual({action for action, weight in declared if weight == 'command'},
                         {'edit-order', 'new-production-change-request', 'issue-material'},
                         'only immediate commands stay button-shaped')
        self.assertEqual(sum(1 for weight in weights.values() if weight == 'row'), 24)
        # Every one of the actions the review named as suitable for a compact row really is one.
        for action in ('production-change-requests', 'order-changes', 'requirements',
                       'reservations', 'consumption', 'production-cost', 'contribution-margin',
                       'cutting-runs', 'bundles', 'sewing-jobs', 'finishing-records',
                       'final-qc-records', 'rework-completions', 'finished-goods', 'warehouse',
                       'order-materials', 'marketplace-reservations', 'marketplace-picks',
                       'marketplace-packs', 'marketplace-shipments', 'marketplace-returns',
                       'finished-goods-adjustments', 'finished-goods-stock-counts'):
            with self.subTest(row=action):
                self.assertEqual(weights[action], 'row')
        # A row is the A6 record-row grammar with a trailing chevron, on a real button, and its
        # accessible name is still exactly the action label.
        self.assertIn('<button class="record-row" data-action="${action}">', RENDER_DETAIL)
        self.assertIn('<span class="record-row-copy"><span class="data-primary">${label}</span>'
                      '</span>', RENDER_DETAIL)
        self.assertIn("svgIcon('arrow-right', 'icon-sm')", RENDER_DETAIL)
        self.assertIn('class="utility-rows"', RENDER_DETAIL)
        # No popover or menu architecture was introduced to hide any of them.
        for forged in ('<details', 'popover', 'aria-haspopup', 'aria-expanded'):
            with self.subTest(forged=forged):
                self.assertNotIn(forged, code(RENDER_DETAIL))
        # The permission gates are the same two role checks, still in JS.
        self.assertIn("const admin = user.role === 'admin', writer = user.role !== 'viewer';",
                      RENDER_DETAIL)
        self.assertIn("admin && ['edit-order'", RENDER_DETAIL)
        self.assertIn("writer && ['issue-material'", RENDER_DETAIL)
        self.assertIn("writer && ['new-production-change-request'", RENDER_DETAIL)

    def test_the_information_hierarchy_puts_operational_data_before_the_action_catalogue(self):
        """The reviewed order: what is this, where is the stock, then what can I do about it."""
        order = ['class="workspace-heading"', '<dl class="detail-grid">',
                 'id="stage-balance-heading"', 'Saldo pengecualian', 'id="sku-detail-heading"',
                 'id="order-actions-heading"', 'id="issues-heading"', 'id="history-heading"']
        positions = [RENDER_DETAIL.index(anchor) for anchor in order]
        self.assertEqual(positions, sorted(positions),
                         'current position and SKU detail both precede the action groups')
        # And the back control belongs to the order identity rather than floating mid-page.
        self.assertRegex(CSS, r'#detail-view>#back\{[^}]*align-self:flex-start')
        self.assertRegex(CSS, r'#detail-view>#back\{[^}]*justify-content:flex-start')
        self.assertIn("$('back').onclick = () => { showBoard(); $('search').focus(); };", APP)

    def test_stage_values_are_current_balances_and_never_a_funnel(self):
        self.assertIn('Posisi barang sekarang', RENDER_DETAIL)
        self.assertIn("${stages.map(stage => balance(labels[stage], o.totals[stage])).join('')}",
                      RENDER_DETAIL)
        self.assertIn("Jumlah seluruh posisi: ${n(Object.values(o.totals).reduce((a,b) => a+b,0))}"
                      ' pcs', RENDER_DETAIL)
        # Rework and reject stay a distinct exception read-out.
        self.assertIn("<p class=\"utility-panel-title\">Saldo pengecualian</p>", RENDER_DETAIL)
        self.assertIn("${balance('Rework', o.totals.rework)}${balance('Reject', o.totals.reject)}",
                      RENDER_DETAIL)
        # The anti-funnel statement is on the page, not only in the docs.
        self.assertIn('saldo yang sedang berada di tiap posisi saat ini, bukan jumlah yang sudah '
                      'selesai melewatinya', RENDER_DETAIL)
        # No connector, no numbered march, no animated flow.
        for forged in ('stage-number', 'funnel', '→</span>', 'connector'):
            with self.subTest(forged=forged):
                self.assertNotIn(forged, code(RENDER_DETAIL))
        # Every quantity keeps an explicit label.
        self.assertIn("const balance = (label, value) => `<div class=\"detail-field${value ? '' "
                      ": ' balance-idle'}\">`", RENDER_DETAIL)
        self.assertIn('<dt>${label}</dt><dd>${n(value)} <small class="metric-unit">pcs</small>'
                      '</dd></div>', RENDER_DETAIL)
        # Emphasis only: an empty position is dimmed, never hidden and never rounded away.
        self.assertRegex(CSS, r'#detail-content \.balance-idle>dd\{[^}]*color:var\(--muted\)')

    def test_sku_records_keep_their_data_and_their_actions(self):
        self.assertIn('Rincian per SKU', RENDER_DETAIL)
        self.assertIn('class="utility-panel sku-record"', RENDER_DETAIL)
        self.assertIn('<span class="data-primary">${e(line.sku)}</span>', RENDER_DETAIL)
        self.assertIn('${e(line.name)} · ${e([line.color,line.size].filter(Boolean)'
                      ".join(' / '))} · target ${n(line.quantity)} pcs", RENDER_DETAIL)
        self.assertIn("${[...stages,'rework','reject'].map(stage => balance(labels[stage], "
                      "line.balances[stage])).join('')}", RENDER_DETAIL)
        self.assertIn('data-action="move" data-id="${e(line.id)}"', RENDER_DETAIL)
        self.assertIn('data-action="new-issue" data-id="${e(line.id)}"', RENDER_DETAIL)
        self.assertIn('class="detail-grid detail-grid-compact"', RENDER_DETAIL)
        # Balances are data, not decoration.
        self.assertNotIn('chart', code(RENDER_DETAIL).lower())

    def test_issues_and_history_use_the_record_and_timeline_primitives(self):
        issues, history = renderer('renderIssues'), renderer('renderHistory')
        self.assertIn('class="record-list"', RENDER_DETAIL)
        self.assertIn('class="record-row"', issues)
        self.assertIn('class="record-row-copy"', issues)
        self.assertIn('class="timeline"', RENDER_DETAIL)
        self.assertIn('class="timeline-item', history)
        for part in ('timeline-time', 'timeline-event', 'timeline-actor', 'timeline-detail'):
            with self.subTest(part=part):
                self.assertIn(part, history)
        # Every issue field is still rendered, and resolution is still gated for a viewer.
        for field in ('item.sku', 'labels[item.stage]', 'item.description', 'item.owner_name',
                      'item.owner_active', 'item.creator_name', 'item.created_at',
                      'item.resolution', 'item.resolver_name', 'item.resolved_at'):
            with self.subTest(field=field):
                self.assertIn(field, issues)
        self.assertIn("user.role !== 'viewer' ? `<span class=\"record-row-aside\">"
                      '<button class="action-secondary" data-action="resolve-issue"', issues)
        self.assertIn('Kendala produksi · ${n(o.open_issues)} terbuka', RENDER_DETAIL)
        self.assertIn('Catatan terbaru dahulu · waktu Jakarta', RENDER_DETAIL)
        # Every movement field, every linked record, and the Koreksi eligibility rule.
        for field in ('item.created_at', 'item.quantity', 'labels[item.from_stage]',
                      'labels[item.to_stage]', 'item.sku', 'item.actor_name', 'item.reason',
                      'item.reversal_of', 'item.cutting_run_id', 'item.sewing_job_id',
                      'item.finishing_record_id', 'item.final_qc_record_id',
                      'item.rework_completion_id'):
            with self.subTest(field=field):
                self.assertIn(field, history)
        self.assertIn("const canReverse = user.role === 'admin' && !item.reversal_of && "
                      '!reversed.has(item.id)', history)
        self.assertIn('Urutan pencatatan terlama · waktu Jakarta', RENDER_DETAIL)
        # The `.reason` marker is deliberately kept: its `white-space:pre-wrap` is what keeps a
        # multi-line operator note readable.
        self.assertIn('class="data-secondary reason"', issues)
        self.assertIn('class="timeline-detail reason"', history)

    def test_both_history_paginations_are_unchanged(self):
        self.assertIn('/movements?limit=100&offset=${historyOffset}', APP)
        self.assertIn('historyOffset += rows.length; renderHistory(); '
                      'button.hidden = rows.length < 100;', APP)
        self.assertIn('/issues?limit=100&before=${issues.at(-1).sequence}', APP)
        self.assertIn('issuesMore = rows.length === 100;', APP)
        self.assertIn('Muat riwayat berikutnya', RENDER_DETAIL)
        self.assertIn('Muat kendala sebelumnya', RENDER_DETAIL)
        more = renderer('moreHistory')
        self.assertIn('const id = selected.id, version = epoch, request = detailRequest;', more)
        self.assertIn('if (version !== epoch || request !== detailRequest) return;', more)


class CreateOrderTest(unittest.TestCase):
    def test_the_form_is_presented_with_a6_field_primitives(self):
        form = renderer('orderForm')
        for primitive in ('class="field"', 'class="field-label"', 'class="field-help"',
                          'class="field-actions"', 'field-wide'):
            with self.subTest(primitive=primitive):
                self.assertIn(primitive, form)
        # The dialog architecture itself is untouched: no sheet, same shared formDialog().
        self.assertIn("}, '/api/orders');", form)
        self.assertIn('formDialog(', form)
        self.assertNotIn('sheet', code(form).lower())

    def test_every_business_rule_is_preserved(self):
        form = renderer('orderForm')
        self.assertIn('if (guardPending()) return;', form)
        self.assertIn('if (version !== epoch || modalVersion !== dialogVersion || '
                      "!$('dialog').open) return;", form)
        # Fields, with their names and their limits.
        for attribute in ('name="reference" type="text" required maxlength="160"',
                          'name="title" type="text" required maxlength="160"',
                          'name="owner_id" required',
                          'name="due_date" type="date" required'):
            with self.subTest(attribute=attribute):
                self.assertIn(attribute, form)
        # Only active non-viewer users can own an order.
        self.assertIn("users.filter(u => u.active && u.role !== 'viewer')", form)
        # Line rules: the collector, the duplicate rejection, the bounds, the 100-row cap and the
        # last-row floor.
        self.assertIn("[...form.querySelectorAll('.line-input')].map(row => "
                      "({product_id:row.querySelector('select').value, "
                      "quantity:Number(row.querySelector('input').value)}))", form)
        self.assertIn("if (new Set(lines.map(line => line.product_id)).size !== lines.length) "
                      "throw new Error('SKU yang sama cukup satu baris. Gabungkan jumlahnya.');",
                      form)
        self.assertIn('type="number" required min="1" max="1000000000" step="1"', form)
        self.assertIn('if (count >= 100) return;', form)
        self.assertIn("if ($('order-lines').children.length > 1) row.remove(); "
                      "else notify('Order memerlukan minimal satu SKU.');", form)
        # The row keeps the class the collector finds it by, and its labels stay reachable.
        self.assertIn("row.className = 'line-input';", form)
        self.assertIn('>SKU</label>', form)
        self.assertIn('>Jumlah</label>', form)
        self.assertIn('aria-label="Hapus baris SKU"', form)
        # Removing a line is quiet, not destructive-red.
        self.assertIn('class="action-quiet" aria-label="Hapus baris SKU"', form)

    def test_the_no_product_state_stays_a_real_route_forward(self):
        form = renderer('orderForm')
        self.assertIn('if (!products.length)', form)
        self.assertIn('Tambahkan minimal satu SKU sebelum membuat order.', form)
        self.assertIn('data-action="new-product"', form)
        self.assertIn('class="empty-state"', form)


class FrozenSurfaceTest(unittest.TestCase):
    def test_the_a3_spring_and_the_a5_3_lens_contract_are_unchanged(self):
        lens = APP[APP.index('const navigationSurface ='):APP.index('// Drawer mobile.')]
        self.assertIn('const navigationLensSpring = {mass:1, stiffness:520, damping:40};', lens)
        for constant in ('LENS_SETTLE_DISTANCE = .25', 'LENS_SETTLE_SPEED = 2',
                         'LENS_MAX_SUBSTEP = 1/120', 'LENS_MAX_FRAME = .032', 'LENS_STALL = .2',
                         'LENS_MORPH_MAX = .07', 'LENS_MORPH_SPEED = 3000'):
            with self.subTest(constant=constant):
                self.assertIn(constant, lens)
        self.assertEqual(len(re.findall(r'const navigationLensSpring = \{', APP)), 1)
        self.assertEqual(HTML.count('nav-selection-lens'), 2)
        self.assertEqual(len(re.findall(r'id="nav-selection-lens"', HTML)), 1)
        self.assertIn('<span id="nav-selection-lens" class="nav-selection-lens" '
                      'aria-hidden="true" hidden></span>', HTML)

    def test_the_approved_shell_markup_and_scroll_architecture_are_untouched(self):
        for anchor in ('<div id="workspace-window" class="workspace-window">', 'id="window-close"',
                       'id="window-minimize"', 'id="window-fullscreen"', 'class="masthead"',
                       'class="app-sidebar"', 'class="workspace-main"', 'class="sidebar-cta"',
                       'id="approvals"'):
            with self.subTest(anchor=anchor[:40]):
                self.assertIn(anchor, HTML)
        # A6.1 owns no shell selector.
        for selector in ('.workspace-window', '.traffic-light', '.masthead', '.app-sidebar',
                         '.sidebar-nav', '.nav-selection-lens', '.workspace-main'):
            with self.subTest(selector=selector):
                self.assertNotIn(selector, PRIMITIVES)
        # The post-PR #98 scroll architecture: the main region scrolls, the document does not.
        self.assertRegex(SHELL, r'\.workspace-main\{[^}]*overflow:auto')
        self.assertRegex(SHELL, r'body\{[^}]*height:100dvh[^}]*overflow:hidden')

    def test_no_new_animation_loop_timer_or_motion_system(self):
        # The exact budget the earlier phases pinned. A6.1 is presentation, so it may not spend
        # a single new frame or timer.
        self.assertEqual(len(re.findall(r'requestAnimationFrame\(', APP)), 6)
        self.assertEqual(len(re.findall(r'cancelAnimationFrame\(', APP)), 4)
        self.assertEqual(len(re.findall(r'setTimeout\(', APP)), 7)
        self.assertEqual(len(re.findall(r'setInterval\(', APP)), 0)
        self.assertNotIn('requestIdleCallback', APP)
        for renderer_name in ('loadBoard', 'renderDetail', 'renderHistory', 'renderIssues',
                              'orderForm', 'pageState'):
            body = renderer(renderer_name)
            with self.subTest(renderer=renderer_name):
                self.assertNotRegex(code(body), r'requestAnimationFrame\(|setTimeout\(|setInterval\('
                                          r'|\.animate\(')
        # No keyframes were added anywhere, and the primitives still declare no animation.
        self.assertNotIn('@keyframes', PRIMITIVES)
        self.assertNotRegex(PRIMITIVES, r'(?<![-\w])animation\s*:')
        # And no row stagger or card cascade crept into the containment block.
        a61 = A61_BLOCK
        self.assertNotRegex(a61, r'@keyframes|animation\s*:|nth-child\([^)]*\)[^{]*\{[^}]*delay')

    def test_repeated_rows_stay_cheap(self):
        # A6.0's material containment is the performance contract: the command bar is the only
        # blurred surface, and a 400-row table costs the compositor nothing extra.
        filtered = set()
        for match in re.finditer(r'([^{}]+)\{([^}]*)\}', re.sub(r'/\*.*?\*/', '', PRIMITIVES,
                                                                flags=re.S)):
            selector, block = match.group(1), match.group(2)
            for declaration in block.split(';'):
                if re.match(r'\s*(?:-webkit-)?backdrop-filter\s*:', declaration) \
                        and declaration.split(':', 1)[1].strip() != 'none':
                    filtered.update(part.strip() for part in selector.split(','))
        self.assertEqual(filtered, {'.command-bar'})
        # The A6.1 containment block introduces no filter and no per-row material either.
        a61 = A61_BLOCK
        self.assertNotRegex(a61, r'backdrop-filter|filter\s*:\s*blur')
        self.assertNotRegex(a61, r'\.order-row\s*\{|\.data-row\s*\{')

    def test_the_migration_is_contained_to_produksi(self):
        # The A6.1 block in style.css only ever addresses Produksi's own ids and its one grouping
        # class, so it cannot reach another workspace by accident.
        a61 = A61_BLOCK
        selectors = [part.strip() for match in re.finditer(r'([^{}]+)\{', a61)
                     for part in match.group(1).split(',') if part.strip()
                     and not part.strip().startswith('@')]
        self.assertTrue(selectors)
        allowed = ('#board-view', '#detail-view', '#board-message', '#detail-message',
                   '#issues-summary', '#order-list', '.production-work', '#detail-content',
                   '#production-filter-hint')
        for selector in selectors:
            with self.subTest(selector=selector):
                self.assertTrue(any(name in selector for name in allowed),
                                f'{selector} is not scoped to the Produksi workspace')
        # The legacy vocabulary other pages still render is deliberately left in place.
        for legacy in ('.summary{', '.status-label,', '.sku-block{', '.issue-item{',
                       '.history-item{', '.list-host', '.state{', '.filters,'):
            with self.subTest(legacy=legacy):
                self.assertIn(legacy, CSS, f'{legacy} is still used by an unmigrated surface')


class VersionAndBackendTest(unittest.TestCase):
    def test_version_is_aligned_across_every_source(self):
        version = re.search(r'^version = "([^"]+)"',
                            (ROOT / 'pyproject.toml').read_text(encoding='utf-8'), re.M).group(1)
        self.assertEqual(version, '0.112.0', 'A6.1 stays aligned with the shipped version')
        self.assertIn(f'version="{version}"', (ROOT / 'beeloft' / 'api.py').read_text(encoding='utf-8'))
        contract = json.loads((ROOT / 'docs' / 'openapi.json').read_text(encoding='utf-8'))
        self.assertEqual(contract['info']['version'], version)

    def test_no_schema_change_and_no_migration(self):
        versions = [int(value) for path in (ROOT / 'beeloft').glob('*.sql')
                    for value in re.findall(r'PRAGMA user_version\s*=\s*(\d+)',
                                            path.read_text(encoding='utf-8'))]
        self.assertEqual(max(versions), 55, 'A6.1 is presentation only')

    def test_no_backend_route_was_added_or_changed(self):
        from tempfile import TemporaryDirectory

        from beeloft.api import create_app
        contract = json.loads((ROOT / 'docs' / 'openapi.json').read_text(encoding='utf-8'))
        with TemporaryDirectory() as folder:
            live = create_app(Path(folder) / 'contract.sqlite3').openapi()
        self.assertEqual(contract['paths'], live['paths'])
        self.assertEqual(contract.get('components'), live.get('components'))
        self.assertEqual(len(contract['paths']), 221, 'A6.1 adds no endpoint')
        # The board still reads the same endpoint, and the renderers invented no field.
        self.assertIn("api.get('/api/production-board?' + query)", APP)

    def test_the_board_payload_is_consumed_and_never_extended(self):
        # Every property the migrated board reads off an order, so a future "just add a field for
        # the design" is visible in a diff rather than buried in a template.
        board = code(LOAD_BOARD) + code(renderer('statusHTML')) + code(renderer('issueBadge'))
        used = set(re.findall(r'order\.(\w+)', board)) | set(re.findall(r'result\.(\w+)', board))
        self.assertEqual(used, {
            'id', 'reference', 'title', 'owner_name', 'due_date', 'lines', 'target_quantity',
            'totals', 'status', 'overdue', 'open_issues', 'orders', 'owners', 'summary', 'total',
        }, 'the board renders exactly the fields the existing payload already carries')


if __name__ == '__main__':
    unittest.main()
