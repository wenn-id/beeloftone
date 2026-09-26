"""A6.0's shared inner-workspace primitive system, and the boundary it promised not to cross.

A6.0 is foundation-only. It introduces one stylesheet of content primitives for the operational
workspaces and a non-production fixture to review them in, and it is explicitly NOT allowed to
redesign a production workflow, touch the approved A5.2/A5.3 shell, or change any backend or
business semantics. That makes this file mostly a *containment* contract rather than a feature
contract: the strongest thing it can assert is that the new system exists, is complete, is
accessible in both themes, and is simultaneously inert with respect to everything already shipped.

The zero-impact guarantee is the load-bearing one. Because every A6 selector is a name no shipped
page uses, adding the stylesheet cannot change a single rendered pixel today; `test_primitives_are
_inert_against_every_shipped_surface` is what keeps that true as A6.1-A6.8 land, and it is what
lets the phase claim "no production workspace has been redesigned yet" without hand-waving.
"""
import json
import re
import unittest
from pathlib import Path

from test_apple27_functional_glass_contract import parse, walk

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / 'beeloft' / 'static'
RAW = (STATIC / 'workspace-primitives.css').read_text(encoding='utf-8')
CSS = re.sub(r'/\*.*?\*/', '', RAW, flags=re.S)
HTML = (STATIC / 'index.html').read_text(encoding='utf-8')
SHELL = (STATIC / 'workspace.css').read_text(encoding='utf-8')
FOUNDATION = (STATIC / 'style.css').read_text(encoding='utf-8')
APP = (STATIC / 'app.mjs').read_text(encoding='utf-8')
FIXTURE = ROOT / 'tests' / 'fixtures' / 'a60-workspace-primitives.html'

# §5's inventory. Three requested names were already owned by shipped surfaces and would have
# silently redesigned them, so they use the cohesive alternatives recorded in the stylesheet
# banner and in docs/apple27-modern-workspace-foundation.md:
#   .attention-panel -> .attention-note   (Command Center owns .attention-panel)
#   .form-grid       -> .field-grid       (legacy dialog forms own .form-grid)
#   .form-actions    -> .field-actions    (legacy dialog forms own .form-actions)
PRIMITIVES = (
    'workspace-page', 'workspace-heading', 'workspace-heading-copy', 'workspace-eyebrow',
    'workspace-title', 'workspace-subtitle', 'workspace-actions',
    'metric-strip', 'metric-card', 'metric-icon', 'metric-value', 'metric-detail',
    'command-bar', 'command-search', 'command-filters', 'command-filter', 'command-actions',
    'segmented-filter', 'filter-chip',
    'data-surface', 'data-toolbar', 'data-header', 'data-row', 'data-cell',
    'data-primary', 'data-secondary', 'data-meta', 'data-actions',
    'status-chip', 'status-dot',
    'progress-meter', 'progress-track', 'progress-fill',
    'info-panel', 'utility-panel', 'attention-note',
    'empty-state', 'error-state', 'loading-state',
    'timeline', 'timeline-item',
    'record-list', 'record-row',
    'detail-grid', 'detail-field',
    'action-primary', 'action-secondary', 'action-quiet', 'action-destructive', 'icon-action',
    'field-grid', 'field', 'field-label', 'field-help', 'field-error', 'field-actions',
)
# §39's semantic workspace tokens.
TOKENS = (
    '--workspace-control-height', '--workspace-control-radius', '--workspace-surface-radius',
    '--workspace-panel-gap', '--workspace-row-height', '--workspace-divider',
    '--workspace-surface', '--workspace-surface-secondary', '--workspace-hover',
    '--workspace-selected',
)
# The A5.2/A5.3 shell. A6.0 owns the workspace CONTENT language and nothing on this list.
SHELL_SELECTORS = (
    '.workspace-window', '.traffic-light', '.window-controls', '.masthead', '.masthead-brand',
    '.masthead-tools', '.app-shell', '.app-sidebar', '.sidebar-nav', '.sidebar-brand',
    '.nav-group', '.nav-item', '.nav-summary', '.nav-children', '.nav-selection-lens',
    '.sidebar-actions', '.sidebar-cta', '.sidebar-cta-title', '.sidebar-cta-button',
    '.workspace-launcher', '.toolbar-menu', '.toolbar-popover', '.navigation-search',
    '.workspace-main', 'body::before',
)
# Names owned by already-shipped surfaces. A6 may not restyle any of them, because doing so
# would redesign a production page (or the frozen Command Center) as a side effect.
LEGACY_VOCABULARY = (
    '.state', '.card', '.sku-block', '.status-label', '.badge', '.chip', '.filters',
    '.filter-bar', '.filter-form', '.table-shell', '.data-table', '.table-head', '.order-row',
    '.order-grid', '.form-grid', '.form-actions', '.check-field', '.page-heading', '.eyebrow',
    '.hint', '.primary', '.quiet', '.icon-button', '.attention-panel', '.hero-panel',
    '.snapshot-card', '.summary', '.stages', '.stage', '.notice', '.workforce-summary',
    '.activity-item', '.history-item', '.decision-row', '.kpi-wallet', '.search-field',
)


# The migration boundary. These are the ONLY places in the shipped product allowed to name an A6
# primitive, and widening this list is the deliberate act each later phase has to perform. A6.1
# added Produksi; A6.2 adds the two master-data workspaces and, unlike A6.1, the specifically named
# dialog renderers those two workspaces launch - their dialogs ARE the workflow, not a side task.
# A6.3 adds People and the two scanners on the same terms: People's workflow lives almost entirely
# in dialogs, and a scanner's whole purpose is the result dialog it opens, so those named renderers
# come with it - and nothing else. The nested workflows those two result dialogs launch (sewing,
# handoff forms, stock adjustment, opname, marketplace reservation, warehouse movement, cutting, QC,
# finishing) are deliberately NOT on this list and still fail if they start emitting A6 markup.
# The list stays an enumeration rather than a pattern on purpose: an unrelated workspace or an
# unrelated dialog that starts emitting A6 markup still fails this contract.
# A6.4 adds the ONE host twelve analytics reports share, plus the twelve report renderers by
# name and the three Capacity master forms that are embedded directly in the capacity report's
# own workflow. The reports' own shared markup helpers come with them, because they exist only to
# stop twelve renderers from restating the same A6 markup twelve times. Everything else Analitik
# merely LINKS to - the purchase order, final QC, finished-goods adjustment and production order
# dialogs - is deliberately NOT on this list and still fails if it starts emitting A6 markup:
# those belong to other workflows and to A6.5-A6.7.
MIGRATED_SECTIONS = ('board-view', 'detail-view', 'materials-view', 'products-view',
                     'people-view', 'bundle-scan-view', 'finished-goods-scan-view',
                     'analytics-view')
MIGRATED_RENDERERS = frozenset({
    'pageState',      # the shared loading / empty / error surface, first consumed by Produksi
    'statusHTML', 'issueBadge',
    'loadBoard',      # the board: heading, metric strip, command bar, data surface
    'renderDetail', 'renderHistory', 'renderIssues',
    'orderForm',      # the create-order form's own fields
    # ---- A6.2: Bahan baku ----
    'reasonField',    # the shared A6 reason textarea the migrated forms consume
    'loadMaterials',  # the batch inventory surface, its states and its pagination label
    'materialBatchScanDialog', 'materialMasterDialog', 'materialForm', 'receiptForm',
    'materialHistoryDialog',          # batch identity, current position, movement timeline
    'materialBatchTraceabilityDialog',
    # ---- A6.2: Master SKU ----
    'paintProducts',  # the catalog record list and its two distinct empty states
    'loadProducts',   # the catalog's loading and error states
    'productForm', 'bomComponentsHTML', 'bomDialog', 'bomForm', 'bomHistoryDialog',
    'productMappingDialog', 'productMappingForm', 'unmapProductForm',
    'productMappingHistoryDialog',
    # ---- A6.3: People ----
    'workforceField', 'workforceSelect', 'workforceFact',   # the A6 field grammar People's forms use
    'loadPeople',     # the daily summary, the roster record list and its three distinct empty states
    'workforceEmployeeMasterDialog', 'workforceEmployeeForm', 'workforceEmployeeHistoryDialog',
    'workforceAttendanceForm', 'workforceAttendanceHistoryDialog',
    'workforceRequestsDialog', 'workforceRequestForm', 'workforceRequestDialog',
    'workforceRequestDecisionForm',
    # ---- A6.3: Scan bundle + Scan barang jadi ----
    'showScanner',    # the shared scanner lifecycle and its one result record
    'bundleDialog',             # the direct destination of Scan bundle
    'finishedGoodsReceiptDialog',   # the direct destination of Scan barang jadi
    # ---- A6.4: Analitik ----
    # The shared grammar the twelve reports are composed from. Each one writes exactly one A6.0
    # shape; none of them is a component, and none of them is reachable from a non-analytics
    # renderer because nothing else calls them.
    'analyticsFilterControl', 'analyticsDateFilter', 'analyticsNumberFilter',
    'analyticsTextFilter', 'analyticsSelectFilter', 'analyticsSearchFilter',
    'analyticsParam', 'analyticsParamSelect', 'analyticsAssumptions', 'analyticsSubmit',
    'analyticsFilterForm', 'analyticsNote', 'analyticsChip', 'analyticsMetrics',
    'analyticsFacts', 'analyticsBars', 'analyticsSubhead', 'analyticsSubgroup',
    'analyticsOpen', 'analyticsPager', 'analyticsReady', 'analyticsFail',
    # The twelve report renderers. This is the whole of Analitik; there is no thirteenth.
    'showWipAgeingInsights', 'showCapacityPlan', 'showProductionQualityInsights',
    'showSupplierPerformanceInsights', 'showMaterialPriceInsights',
    'showPurchaseCommitmentInsights', 'showDemandForecast', 'showReplenishment',
    'showSizeDemandInsights', 'showReturnInsights', 'showDeadStockInsights',
    'showStockAdjustmentInsights',
    # ---- A6.4: Kapasitas master, embedded in the capacity report's own workflow ----
    'capacityField', 'capacitySelect', 'capacityFact',
    'capacityWorkCenterForm', 'capacityRoutingStandardForm', 'capacityCalendarForm',
})


def section(html, element_id):
    """The complete markup of one `<section id=...>`, nested sections included.

    Tag counting rather than a lazy regex, because `#board-view` really does contain another
    `<section>` (the working surface) and `#activity-view` really does sit between the two
    migrated sections, so neither "up to the first `</section>`" nor "between board and
    detail" would describe the right text.
    """
    start = html.index(f'<section id="{element_id}"')
    depth = 0
    for match in re.finditer(r'<section\b|</section>', html[start:]):
        depth += 1 if match.group().startswith('<section') else -1
        if depth == 0:
            return html[start:start + match.end()]
    raise AssertionError(f'#{element_id} is not a closed section')


def rules(css=CSS):
    """(at-rule context, selector, declaration) for every declaration in the A6 stylesheet."""
    return list(walk(parse(css)[0]))


def declared(selector, css=CSS):
    """Every declaration block written for an exact selector, at any nesting depth."""
    return [declaration for _, found, declaration in rules(css)
            if found and any(part.strip() == selector for part in found.split(','))]


def tokens_in(selector):
    """The token block a selector declares unconditionally.

    Only the first match is read on purpose. The responsive and pointer blocks re-declare a
    handful of `:root` tokens inside media queries, and merging those over the baseline would
    report the narrow-viewport or coarse-pointer value as if it were the default - which is
    exactly the confusion the compact desktop step and the 44px touch step must not have.
    """
    block = re.search(re.escape(selector) + r'\s*\{([^}]+)\}', CSS)
    return dict(re.findall(r'(--[\w-]+)\s*:\s*([^;{}]+)', block.group(1))) if block else {}


def channel(value):
    value = value / 255
    return value / 12.92 if value <= .04045 else ((value + .055) / 1.055) ** 2.4


def contrast(foreground, background):
    """WCAG relative-luminance ratio for two opaque hex colours."""
    def luminance(colour):
        colour = colour.strip().lstrip('#')
        if len(colour) == 3:
            colour = ''.join(c * 2 for c in colour)
        r, g, b = (channel(int(colour[i:i + 2], 16)) for i in (0, 2, 4))
        return .2126 * r + .7152 * g + .0722 * b
    first, second = luminance(foreground), luminance(background)
    high, low = max(first, second), min(first, second)
    return (high + .05) / (low + .05)


# The role aliases A6 text actually consumes, resolved per theme from the shell that re-tunes
# them, and the opaque materials A6 surfaces resolve to outside the optical gate. Keeping this
# table explicit is what lets the contrast test be arithmetic rather than aspiration.
def alias(name, theme):
    source = SHELL if theme == 'light' else SHELL
    block = re.search(r':root\{([^}]*)\}', source) if theme == 'light' else \
        re.search(r':root\[data-theme=dark\]\{([^}]*)\}', source)
    found = dict(re.findall(r'(--[\w-]+)\s*:\s*([^;{}]+)', block.group(1)))
    if name in found:
        return found[name].strip()
    foundation = re.search(r':root\{(.*?)\n\}' if theme == 'light'
                           else r':root\[data-theme=dark\]\{(.*?)\n\}', FOUNDATION, re.S)
    table = dict(re.findall(r'(--[\w-]+)\s*:\s*([^;{}]+)', foundation.group(1)))
    value = table[name].strip()
    reference = re.fullmatch(r'var\((--[\w-]+)\)', value)
    return alias(reference.group(1), theme) if reference else value


class PrimitiveInventoryTest(unittest.TestCase):
    def test_the_stylesheet_is_loaded_after_the_approved_shell(self):
        # Load order is the guarantee that A6 can never outrank A5.2/A5.3 by cascade accident.
        self.assertLess(HTML.index('/static/style.css'), HTML.index('/static/workspace.css'))
        self.assertLess(HTML.index('/static/workspace.css'), HTML.index('/static/workspace-primitives.css'))
        self.assertEqual(HTML.count('/static/workspace-primitives.css'), 1)
        # Same-origin, no CDN, no import chain.
        self.assertRegex(HTML, r'<link rel="stylesheet" href="/static/workspace-primitives\.css">')

    def test_every_required_primitive_exists_as_a_real_rule(self):
        written = {part.strip().lstrip('.').split(':')[0].split('>')[0].split(' ')[0]
                   for _, selector, _ in rules() if selector
                   for part in selector.split(',')}
        for name in PRIMITIVES:
            with self.subTest(primitive=name):
                self.assertRegex(CSS, r'\.' + re.escape(name) + r'(?![\w-])',
                                 f'.{name} is required by the A6.0 primitive inventory')
        # And each one is a styled rule, not only a mention inside a compound selector.
        for name in ('workspace-page', 'metric-card', 'command-bar', 'data-surface', 'data-row',
                     'status-chip', 'progress-track', 'empty-state', 'error-state', 'loading-state',
                     'timeline-item', 'record-row', 'detail-field', 'field', 'field-grid',
                     'action-primary', 'action-destructive', 'icon-action', 'attention-note'):
            with self.subTest(styled=name):
                self.assertIn(name, written)

    def test_semantic_tokens_exist_and_never_duplicate_a_raw_colour(self):
        light = tokens_in(':root')
        for token in TOKENS:
            with self.subTest(token=token):
                self.assertIn(token, light)
        # §39: no raw colour literal may be repeated across many selectors. Every hex in the
        # sheet has to live in a token block, not in a component rule.
        for context, selector, declaration in rules():
            if selector and re.search(r'#[0-9a-fA-F]{3,8}\b', declaration):
                self.assertTrue(declaration.startswith('--'),
                                f'raw colour outside a token: {selector} {{{declaration}}}')

    def test_tokens_do_not_collide_with_the_shell_or_the_foundation(self):
        mine = set(re.findall(r'(--[\w-]+)\s*:', CSS))
        theirs = set(re.findall(r'(--[\w-]+)\s*:', re.sub(r'/\*.*?\*/', '', SHELL, flags=re.S)))
        theirs |= set(re.findall(r'(--[\w-]+)\s*:', re.sub(r'/\*.*?\*/', '', FOUNDATION, flags=re.S)))
        self.assertEqual(mine & theirs, set(),
                         'A6 must not redeclare a shell or foundation token')


class ZeroProductionImpactTest(unittest.TestCase):
    def test_primitives_are_inert_outside_the_migrated_workspace(self):
        """A6.0's containment promise, narrowed by exactly one deliberate migration.

        A6.0 could state this absolutely: no shipped surface used an A6 name, so loading the
        sheet changed nothing. A6.1 is the first phase allowed to spend that - it migrates the
        Produksi board, the Produksi order detail and the create-order form onto the
        primitives - so the promise becomes conditional rather than absent. It is deliberately
        NOT relaxed to "anything may use these names":

          * the stylesheets and the other three scripts still may not use one at all;
          * `index.html` may use them only inside `#board-view` and `#detail-view`;
          * `app.mjs` may use them only inside the Produksi renderers listed below.

        That is what keeps the original job of this test alive. A6.2-A6.8 each migrate another
        workspace, and each one has to come here and say so; a stray `.data-surface` added to
        Bahan baku, People, Analitik or a child dialog still fails, which is the whole point.
        """
        names = {part.strip().lstrip('.').split(':')[0].split('>')[0].split(' ')[0]
                 for _, selector, _ in rules() if selector for part in selector.split(',')}
        names -= {'', 'icon', 'icon-sm', 'icon-lg', 'visually-hidden'}
        names = sorted(name for name in names if re.match(r'^[a-z][\w-]*$', name))
        self.assertTrue(names)

        def used(text, name):
            # A CSS class matches whole tokens, so `search-field` can never be hit by
            # `.field`; the boundary here models that exactly.
            return re.search(r'class="[^"]*(?<![\w-])' + re.escape(name) + r'(?![\w-])', text)

        # 1. Nothing outside the migrated markup and the migrated renderers may name a primitive.
        for source in ('style.css', 'workspace.css', 'workspace.mjs', 'client.mjs'):
            text = (STATIC / source).read_text(encoding='utf-8')
            for name in names:
                with self.subTest(source=source, primitive=name):
                    self.assertIsNone(used(text, name),
                                      f'.{name} leaked into {source} - only #board-view, '
                                      '#detail-view and the Produksi renderers are migrated')

        # 2. index.html, with the two migrated sections removed.
        rest = HTML
        for element in MIGRATED_SECTIONS:
            markup = section(HTML, element)
            self.assertIn('class=', markup)
            rest = rest.replace(markup, '')
        for name in names:
            with self.subTest(source='index.html', primitive=name):
                self.assertIsNone(used(rest, name),
                                  f'.{name} is used by markup outside #board-view / #detail-view')

        # 3. app.mjs, attributed line by line to the top-level symbol that owns the line. The
        #    ownership walk needs no brace matching - every declaration in this file starts at
        #    column zero - so it cannot be confused by the `${...}` of a template literal.
        owners = []
        for line in APP.split('\n'):
            found = re.match(r'(?:async\s+)?function\s+([A-Za-z_$][\w$]*)'
                             r'|(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=', line)
            owners.append(found.group(1) or found.group(2) if found else
                          (owners[-1] if owners else None))
        for number, (line, owner) in enumerate(zip(APP.split('\n'), owners), start=1):
            for name in names:
                if used(line, name):
                    with self.subTest(line=number, primitive=name):
                        self.assertIn(owner, MIGRATED_RENDERERS,
                                      f'app.mjs:{number} uses .{name} inside {owner!r}, which is '
                                      'not one of the migrated Produksi renderers')

    def test_the_migration_actually_happened(self):
        """The other half of a narrowed promise: the exception has to be earning its keep.

        Without this, deleting the Produksi migration and leaving the allowance behind would
        still pass every assertion above. The detailed board/detail contract lives in
        tests/test_apple27_production_workspace_contract.py; this is only the A6.0-side proof
        that the door it opened is actually being used.
        """
        board, detail = section(HTML, 'board-view'), section(HTML, 'detail-view')
        for name in ('workspace-page', 'workspace-heading', 'workspace-title', 'metric-strip',
                     'command-bar', 'command-search', 'command-filter', 'attention-note',
                     'data-surface', 'info-panel'):
            with self.subTest(board=name):
                self.assertRegex(board, r'class="[^"]*(?<![\w-])' + name + r'(?![\w-])')
        self.assertRegex(detail, r'class="[^"]*(?<![\w-])workspace-page(?![\w-])')
        for name in ('data-row', 'data-cell', 'status-chip', 'progress-meter', 'detail-grid',
                     'timeline-item', 'record-row', 'utility-panel', 'field', 'empty-state'):
            with self.subTest(renderer=name):
                self.assertRegex(APP, r'class="[^"]*(?<![\w-])' + name + r'(?![\w-])')

    def test_no_legacy_vocabulary_is_restyled(self):
        for legacy in LEGACY_VOCABULARY:
            with self.subTest(legacy=legacy):
                self.assertEqual(declared(legacy), [],
                                 f'{legacy} belongs to a shipped surface')
                self.assertNotRegex(CSS, re.escape(legacy) + r'\s*[,{]')

    def test_the_approved_shell_is_untouched(self):
        for selector in SHELL_SELECTORS:
            with self.subTest(shell=selector):
                self.assertNotIn(selector, CSS, f'A6.0 does not own {selector}')
        # The shell stylesheet gained no A6 primitive either: the two files stay disjoint.
        for name in PRIMITIVES:
            with self.subTest(shell_leak=name):
                self.assertNotRegex(SHELL, r'\.' + re.escape(name) + r'(?![\w-])')

    def test_the_frozen_shell_markup_is_still_intact(self):
        # A6.0 could say "index.html changed only by adding the stylesheet". A6.1 edits the two
        # migrated sections, so what this can still promise - and the part that actually matters -
        # is that every shell node A5.2/A5.3 froze is present and unmodified.
        for anchor in ('<div id="workspace-window" class="workspace-window">',
                       'id="window-close"', 'id="window-minimize"', 'id="window-fullscreen"',
                       '<span id="nav-selection-lens" class="nav-selection-lens" aria-hidden="true" hidden></span>',
                       'class="sidebar-cta"', 'id="approvals"', 'class="masthead"',
                       'class="app-sidebar"', 'class="workspace-main"'):
            with self.subTest(anchor=anchor[:48]):
                self.assertIn(anchor, HTML)
        # Exactly one selection lens, as A2/A3/A5.3 require.
        self.assertEqual(HTML.count('nav-selection-lens'), 2)  # class + id on the single node
        self.assertEqual(len(re.findall(r'id="nav-selection-lens"', HTML)), 1)


class MotionAndPerformanceTest(unittest.TestCase):
    def test_a3_spring_constants_are_unchanged(self):
        lens = APP[APP.index('const navigationSurface ='):APP.index('// Drawer mobile.')]
        self.assertIn('const navigationLensSpring = {mass:1, stiffness:520, damping:40};', lens)
        self.assertIn('LENS_SETTLE_DISTANCE = .25', lens)
        self.assertIn('LENS_SETTLE_SPEED = 2', lens)
        self.assertIn('LENS_MAX_SUBSTEP = 1/120', lens)
        self.assertIn('LENS_MAX_FRAME = .032', lens)
        self.assertIn('LENS_STALL = .2', lens)
        self.assertIn('LENS_MORPH_MAX = .07', lens)
        self.assertIn('LENS_MORPH_SPEED = 3000', lens)
        self.assertEqual(len(re.findall(r'const navigationLensSpring = \{', APP)), 1,
                         'one spring configuration exists in the whole application')

    def test_a6_adds_no_script_no_frame_and_no_timer(self):
        # A6.0 is a CSS/markup contract. The application's JavaScript is not part of it, so the
        # lens budget the earlier phases pinned must still hold exactly.
        lens = APP[APP.index('const navigationSurface ='):APP.index('// Drawer mobile.')]
        self.assertEqual(lens.count('requestAnimationFrame('), 3)
        self.assertEqual(lens.count('cancelAnimationFrame('), 3)
        self.assertNotRegex(lens, r'setTimeout|setInterval|\.animate\(')
        self.assertEqual(len(re.findall(r'requestAnimationFrame\(', APP)), 6)
        self.assertEqual(len(re.findall(r'setTimeout\(', APP)), 7)
        self.assertEqual(len(re.findall(r'setInterval\(', APP)), 0)
        # No new static asset carries script, and the stylesheet carries no animation at all.
        self.assertEqual(sorted(p.name for p in STATIC.iterdir() if p.suffix in ('.mjs', '.js')),
                         ['app.mjs', 'appearance.js', 'client.mjs', 'workspace.mjs'])
        self.assertNotIn('@keyframes', CSS)
        self.assertNotRegex(CSS, r'(?<![-\w])animation\s*:')

    def test_motion_is_only_the_existing_hover_and_focus_grammar(self):
        for context, selector, declaration in rules():
            if not re.match(r'transition\s*:', declaration):
                continue
            with self.subTest(selector=selector):
                self.assertTrue(any('prefers-reduced-motion:no-preference' in at for at in context),
                                'every transition is gated on the motion preference')
                # Only the product's own motion tokens, never a raw duration.
                self.assertNotRegex(declaration, r'\d+ms|\d*\.?\d+s(?![\w-])')
                self.assertRegex(declaration, r'var\(--motion-(instant|fast|base)\)')
                self.assertRegex(declaration, r'var\(--ease-standard\)')

    def test_repeated_surfaces_are_never_backdrop_roots(self):
        """§46: material at container level, never once per row, chip or cell."""
        filtered = set()
        for context, selector, declaration in rules():
            if not re.match(r'(?:-webkit-)?backdrop-filter\s*:', declaration):
                continue
            if declaration.split(':', 1)[1].strip() == 'none':
                continue
            for part in selector.split(','):
                filtered.add(part.strip())
        self.assertEqual(filtered, {'.command-bar'},
                         'the command bar is the only blurred workspace surface')
        for repeated in ('.data-row', '.record-row', '.status-chip', '.filter-chip', '.data-cell',
                         '.metric-card', '.timeline-item', '.progress-track', '.data-header',
                         '.info-panel', '.utility-panel', '.detail-field', '.field'):
            for _, selector, declaration in rules():
                if selector and repeated in selector and 'backdrop-filter' in declaration:
                    self.assertEqual(declaration.split(':', 1)[1].strip(), 'none',
                                     f'{repeated} must never carry a live backdrop filter')

    def test_the_optical_layer_is_gated_and_contained(self):
        gate = '@supports ((backdrop-filter:blur(1px)) or (-webkit-backdrop-filter:blur(1px)))'
        self.assertEqual(CSS.count('@supports'), 1, 'one feature gate holds the A6 optical layer')
        self.assertIn(gate, CSS)
        start, depth = CSS.index(gate), 0
        for index in range(start, len(CSS)):
            if CSS[index] == '{':
                depth += 1
            elif CSS[index] == '}':
                depth -= 1
                if depth == 0:
                    break
        outside = CSS[:start] + CSS[index + 1:]
        self.assertNotRegex(outside, r'backdrop-filter\s*:\s*(?!none)',
                            'no A6 surface is translucent outside the feature gate')
        # The unconditional baseline resolves to the A1 opaque materials, so an engine without
        # backdrop filtering renders a finished solid workspace rather than a fallback.
        base = tokens_in(':root')
        self.assertEqual(base['--workspace-surface'].strip(), 'var(--material-content)')
        self.assertEqual(base['--workspace-surface-secondary'].strip(),
                         'var(--material-content-subtle)')
        self.assertEqual(base['--workspace-toolbar'].strip(), 'var(--material-content)')

    def test_the_ordinary_lens_still_has_no_nested_filter(self):
        for name in ('style.css', 'workspace.css', 'workspace-primitives.css'):
            css = re.sub(r'/\*.*?\*/', '', (STATIC / name).read_text(encoding='utf-8'), flags=re.S)
            for _, selector, declaration in walk(parse(css)[0]):
                if not selector or not re.match(r'(?:-webkit-)?backdrop-filter\s*:', declaration):
                    continue
                if declaration.split(':', 1)[1].strip() == 'none':
                    continue
                for target in selector.split(','):
                    if 'nav-selection-lens' in target:
                        self.assertEqual(target.strip(), '.sidebar-cta>.nav-selection-lens')


class AppearanceAndAccessibilityTest(unittest.TestCase):
    def test_light_and_dark_are_both_first_class(self):
        self.assertIn(':root[data-theme=dark]', CSS)
        self.assertEqual(len(re.findall(r':root\[data-theme=dark\]\s*\{', CSS)), 1)
        # The product themes by attribute, never by media query, so a stray
        # prefers-color-scheme rule would silently disagree with the toggle.
        self.assertNotIn('prefers-color-scheme', CSS)
        light, dark = tokens_in(':root'), tokens_in(':root[data-theme=dark]')
        # Every theme-dependent token is tuned for dark; the geometry tokens deliberately are not.
        for token in ('--workspace-divider', '--workspace-edge', '--workspace-hover',
                      '--workspace-selected', '--workspace-shadow', '--workspace-surface-tint',
                      '--workspace-surface-secondary-tint', '--workspace-toolbar-tint',
                      '--workspace-toolbar-highlight'):
            with self.subTest(token=token):
                self.assertIn(token, light)
                self.assertIn(token, dark)
                self.assertNotEqual(light[token].strip(), dark[token].strip(),
                                    'dark is tuned, not inherited')
        for geometry in ('--workspace-control-height', '--workspace-surface-radius',
                         '--workspace-row-height'):
            with self.subTest(geometry=geometry):
                self.assertNotIn(geometry, dark)

    def test_text_meets_wcag_on_workspace_surfaces_in_both_themes(self):
        # A6 text consumes the shell's re-tuned role aliases; the surfaces resolve to the A1
        # opaque materials outside the optical gate. Both are checked as actual arithmetic.
        for theme in ('light', 'dark'):
            surfaces = {'--workspace-surface': alias('--color-content', theme),
                        '--workspace-surface-secondary': alias('--color-content-subtle', theme)}
            for role, minimum in (('--ink', 4.5), ('--ink-2', 4.5), ('--muted', 4.5)):
                for name, background in surfaces.items():
                    with self.subTest(theme=theme, role=role, surface=name):
                        self.assertGreaterEqual(
                            contrast(alias(role, theme), background), minimum)
            # Status chip foregrounds over their own soft tints.
            for tone in ('accent', 'success', 'warning', 'danger'):
                with self.subTest(theme=theme, chip=tone):
                    self.assertGreaterEqual(
                        contrast(alias(f'--color-{tone}', theme),
                                 alias(f'--color-{tone}-soft', theme)), 4.5)

    def test_reduced_transparency_only_ever_withdraws_the_enhancement(self):
        self.assertEqual(CSS.count('prefers-reduced-transparency'), 1)
        self.assertIn('@media(prefers-reduced-transparency:reduce)', CSS)
        withdraw = CSS[CSS.index('@media(prefers-reduced-transparency:reduce)'):]
        withdraw = withdraw[:withdraw.index('@media(forced-colors:active)')]
        self.assertNotRegex(withdraw, r'backdrop-filter\s*:\s*(?!none)')
        # Dense data surfaces come back fully opaque: table readability is not negotiable.
        self.assertRegex(withdraw, r'\.data-surface[^{]*\{[^}]*background:var\(--material-content\)')
        self.assertIn('backdrop-filter:none', withdraw)
        # And the preference is honoured inside the gate, so it can actually switch it off.
        self.assertLess(CSS.index('@supports'), CSS.index('@media(prefers-reduced-transparency'))

    def test_forced_colors_never_relies_on_a_background_alone(self):
        self.assertIn('@media(forced-colors:active)', CSS)
        forced = CSS[CSS.index('@media(forced-colors:active)'):]
        for required in ('.status-chip', '.status-dot', '.progress-track', '.progress-fill',
                         '.filter-chip', '.data-row', '.record-row', '.data-header th',
                         '.action-primary', '.icon-action', '.attention-note', '.timeline-item'):
            with self.subTest(required=required):
                self.assertIn(required, forced)
        # System colours, real borders, and a non-colour channel for state.
        self.assertRegex(forced, r'\.status-chip\s*\{[^}]*border:1px solid CanvasText')
        self.assertRegex(forced, r'\.status-dot\s*\{[^}]*background:CanvasText')
        self.assertRegex(forced, r'\.progress-track\s*\{[^}]*border:1px solid CanvasText')
        self.assertRegex(forced, r'\.progress-fill\s*\{[^}]*background:Highlight')
        self.assertIn('-webkit-backdrop-filter:none', forced)
        self.assertNotRegex(forced, r'#[0-9a-fA-F]{3,8}\b',
                            'forced colours use system keywords, never product hexes')

    def test_focus_is_visible_on_everything_interactive(self):
        focus = [(selector, declaration) for _, selector, declaration in rules()
                 if selector and 'focus-visible' in selector]
        self.assertTrue(focus)
        covered = ' '.join(selector for selector, _ in focus)
        for target in ('.data-row', '.record-row', '.filter-chip', '.icon-action',
                       '.command-filter>select', '.data-toolbar'):
            with self.subTest(target=target):
                self.assertIn(target, covered)
        # Every focus-visible rule supplies a real ring in the product's own focus colour.
        for selector, declaration in focus:
            if declaration.startswith('outline') and ':' not in declaration.split(':', 1)[0]:
                with self.subTest(selector=selector):
                    self.assertNotRegex(declaration, r'outline\s*:\s*(none|0)\b')
        self.assertRegex(CSS, r'outline:2px solid var\(--focus\)')

    def test_focus_is_never_suppressed_without_a_replacement(self):
        """`outline:none` is allowed only to move a ring, never to remove one."""
        visible = {part.strip() for _, selector, _ in rules() if selector
                   and 'focus-visible' in selector for part in selector.split(',')}
        suppressed = [(selector, declaration) for _, selector, declaration in rules()
                      if selector and re.match(r'outline\s*:\s*(none|0)(?![\w-])', declaration)]
        for selector, _ in suppressed:
            for part in (p.strip() for p in selector.split(',')):
                with self.subTest(suppressed=part):
                    # It may only ever be scoped to a focus state, not to the resting control.
                    self.assertIn(':focus', part)
                    base = part.replace(':focus-visible', '').replace(':focus', '')
                    self.assertTrue(
                        any(base in candidate for candidate in visible),
                        f'{part} hides the default ring but declares no focus-visible ring')
        # The one place this happens is the compact filter control, whose ring is drawn on the
        # shared wrapper so the label and the select read as a single focused object.
        self.assertRegex(CSS, r'\.command-filter:focus-within\s*\{[^}]*border-color:var\(--focus\)')

    def test_touch_targets_are_restored_for_coarse_pointers_only(self):
        self.assertIn('@media(pointer:coarse)', CSS)
        coarse = CSS[CSS.index('@media(pointer:coarse)'):]
        coarse = coarse[:coarse.index('@media', 1)] if '@media' in coarse[1:] else coarse
        self.assertRegex(coarse, r'--workspace-control-height:var\(--touch-target-min\)')
        for target in ('.filter-chip', '.icon-action'):
            self.assertIn(target, coarse)
        self.assertRegex(coarse, r'min-height:var\(--touch-target-min\)')
        # Desktop density from the approved shell is preserved: the compact step is not 44px.
        self.assertEqual(tokens_in(':root')['--workspace-control-height'].strip(), '34px')

    def test_responsive_rules_reuse_the_shells_own_breakpoints(self):
        widths = sorted({int(w) for w in re.findall(r'@media\(max-width:(\d+)px\)', CSS)})
        shell = {int(w) for w in re.findall(r'@media\(max-width:(\d+)px\)', SHELL)}
        shell |= {int(w) for w in re.findall(r'@media\(max-width:(\d+)px\)', FOUNDATION)}
        self.assertTrue(widths, 'A6 declares responsive behaviour')
        for width in widths:
            with self.subTest(width=width):
                self.assertIn(width, shell, 'A6.0 introduces no new breakpoint')

    def test_tables_scroll_instead_of_crushing_identifiers(self):
        """The §34 responsive-table strategy, as a measurable rule rather than a promise."""
        narrow = CSS[CSS.index('@media(max-width:980px)'):]
        narrow = narrow[:narrow.index('@media(max-width:650px)')]
        self.assertRegex(narrow, r'\.data-surface\s*\{[^}]*overflow-x:auto')
        # A rem floor, so 200% text grows the columns instead of re-crushing them.
        table = re.search(r'\.data-surface>table\s*\{([^}]*)\}', narrow).group(1)
        self.assertRegex(table, r'min-width:\d+(\.\d+)?rem')
        # Cards are not forced on anyone: the stacked alternative is opt-in per page.
        self.assertNotRegex(CSS, r'\.data-surface[^{]*\{[^}]*display:(block|grid|flex)')
        self.assertIn('.data-column-secondary', CSS)


class QaFixtureTest(unittest.TestCase):
    def test_the_fixture_exists_and_demonstrates_the_whole_system(self):
        self.assertTrue(FIXTURE.is_file())
        markup = FIXTURE.read_text(encoding='utf-8')
        for name in ('workspace-heading', 'metric-card', 'command-bar', 'segmented-filter',
                     'data-surface', 'data-header', 'data-row', 'status-chip', 'progress-track',
                     'empty-state', 'error-state', 'loading-state', 'attention-note',
                     'timeline-item', 'record-row', 'detail-field', 'field-grid', 'field-error',
                     'action-primary', 'action-secondary', 'action-quiet', 'action-destructive',
                     'icon-action', 'scan-surface'):
            with self.subTest(demonstrated=name):
                self.assertIn(name, markup)

    def test_the_fixture_is_not_production(self):
        markup = FIXTURE.read_text(encoding='utf-8')
        # Not a static asset: never mounted by StaticFiles, never packaged by `static/*`.
        self.assertFalse((STATIC / FIXTURE.name).exists())
        self.assertEqual(FIXTURE.parent, ROOT / 'tests' / 'fixtures')
        # Not reachable: nothing in the application references it, and it is not navigation.
        for source in (HTML, APP, (ROOT / 'beeloft' / 'api.py').read_text(encoding='utf-8')):
            self.assertNotIn(FIXTURE.name, source)
            self.assertNotIn('a60-workspace-primitives', source)
        self.assertNotIn('nav-item', markup)
        self.assertNotIn('sidebar', markup)
        self.assertIn('NON-PRODUCTION', markup)
        self.assertIn('<meta name="robots" content="noindex">', markup)
        # It reviews the real cascade, by relative path, with no remote anything.
        for sheet in ('style.css', 'workspace.css', 'workspace-primitives.css'):
            self.assertIn(f'../../beeloft/static/{sheet}', markup)
        self.assertNotRegex(markup, r'https?://')

    def test_the_fixture_uses_native_semantics(self):
        markup = FIXTURE.read_text(encoding='utf-8')
        # §44: native elements, not div-role recreation.
        for element in ('<table', '<thead', '<tbody', '<th scope="col"', '<td', '<button',
                        '<select', '<input', '<label', '<form', '<dl', '<dt', '<dd', '<ul', '<li'):
            with self.subTest(element=element):
                self.assertIn(element, markup)
        for forged in ('role="table"', 'role="row"', 'role="cell"', 'role="columnheader"',
                       'role="button"', 'role="checkbox"', 'role="textbox"'):
            with self.subTest(forged=forged):
                self.assertNotIn(forged, markup)
        # The one ARIA role used is the one with no styleable native equivalent, and it carries
        # real values rather than being decorative.
        self.assertIn('role="progressbar"', markup)
        for attribute in ('aria-valuenow=', 'aria-valuemin="0"', 'aria-valuemax="100"'):
            self.assertIn(attribute, markup)
        self.assertEqual(markup.count('role="progressbar"'), markup.count('aria-valuenow='))
        # Icon-only controls and hidden labels stay named.
        self.assertIn('aria-label=', markup)
        self.assertIn('visually-hidden', markup)


class ContainmentTest(unittest.TestCase):
    def test_no_external_framework_font_or_asset_was_introduced(self):
        source = '\n'.join(p.read_text(encoding='utf-8') for p in STATIC.iterdir()
                           if p.suffix in ('.css', '.mjs', '.html', '.js'))
        source += FIXTURE.read_text(encoding='utf-8')
        self.assertNotRegex(source, r'fonts\.googleapis|fonts\.gstatic|use\.typekit')
        self.assertNotRegex(source, r'cdn\.|unpkg|jsdelivr|cdnjs|bootstrap|tailwind|ant-design'
                                    r'|material-ui|@mui|react|vue|svelte|angular')
        self.assertNotRegex(CSS, r'@import|@font-face|url\(|image-set\(')
        self.assertNotRegex(source, r'navigator\.gpu|getContext\([\'"]webg|WebGPU|createShader')
        # No Apple font or any new binary asset was copied into the product.
        self.assertEqual(sorted(p.name for p in STATIC.rglob('*') if p.suffix.lower() in
                                ('.woff', '.woff2', '.otf', '.ttf', '.png', '.jpg', '.jpeg',
                                 '.webp', '.svg', '.gif')),
                         ['wallpaper-landscape.webp', 'wallpaper-mist.webp'])
        # The system font stack is still the foundation's, unchanged and not redeclared.
        self.assertNotIn('font-family', CSS)
        self.assertIn('-apple-system,BlinkMacSystemFont', FOUNDATION)

    def test_static_assets_are_exactly_the_expected_set(self):
        self.assertEqual(sorted(p.name for p in STATIC.iterdir()),
                         ['app.mjs', 'appearance.js', 'client.mjs', 'index.html', 'style.css',
                          'wallpaper-landscape.webp', 'wallpaper-mist.webp',
                          'workspace-primitives.css', 'workspace.css', 'workspace.mjs'])


class VersionAndSchemaTest(unittest.TestCase):
    def test_version_is_aligned_across_every_source(self):
        version = re.search(r'^version = "([^"]+)"',
                            (ROOT / 'pyproject.toml').read_text(encoding='utf-8'), re.M).group(1)
        self.assertEqual(version, '0.110.0')
        self.assertIn(f'version="{version}"',
                      (ROOT / 'beeloft' / 'api.py').read_text(encoding='utf-8'))
        contract = json.loads((ROOT / 'docs' / 'openapi.json').read_text(encoding='utf-8'))
        self.assertEqual(contract['info']['version'], version)

    def test_no_schema_change_and_no_migration(self):
        versions = [int(value) for path in (ROOT / 'beeloft').glob('*.sql')
                    for value in re.findall(r'PRAGMA user_version\s*=\s*(\d+)',
                                            path.read_text(encoding='utf-8'))]
        self.assertEqual(max(versions), 55, 'A6.0 is presentation only')

    def test_no_backend_route_changed(self):
        """The committed contract still describes exactly the routes the application declares."""
        from tempfile import TemporaryDirectory

        from beeloft.api import create_app
        contract = json.loads((ROOT / 'docs' / 'openapi.json').read_text(encoding='utf-8'))
        with TemporaryDirectory() as folder:
            live = create_app(Path(folder) / 'contract.sqlite3').openapi()
        self.assertEqual(set(contract['paths']), set(live['paths']))
        self.assertEqual(contract['paths'], live['paths'])
        self.assertEqual(contract.get('components'), live.get('components'))
        # The A6.0 surface area is CSS and one markup line; it adds no endpoint.
        self.assertEqual(len(contract['paths']), 221)


if __name__ == '__main__':
    unittest.main()
