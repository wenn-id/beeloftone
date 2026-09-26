"""A6.4 - Analitik modern workspace: the static half of the migration contract.

A6.0 built the shared inner-workspace language; A6.1 spent it on Produksi, A6.2 on the two
master-data workspaces, A6.3 on three workflow surfaces. A6.4 spends it on the one place in the
product where TWELVE destinations share a single host: `#analytics-view`.

That makes this a different kind of contract from every phase before it. The risk here is not that
one page was redesigned badly - it is that twelve distinct business questions were flattened into
one dashboard, or scattered into twelve unrelated visual systems, or quietly given conclusions the
API never returned. So what is asserted here is

  * the shared host is A6.0 `workspace-page` grammar and keeps every id the navigation contract
    addresses: `analytics-view`, `analytics-eyebrow`, `analytics-heading`, `analytics-body`,
    `analytics-back`;
  * there are exactly TWELVE reports - the twelve that already existed - registered in
    `analyticsReports`, reachable from twelve sidebar children, and there is no thirteenth;
  * the shared-host navigation is unchanged: one section, one `<h1>`, `activateAnalyticsReport()`
    still bumps `analyticsRequest`, still derives the eyebrow from the sidebar label, and switching
    reports still does not create a second workspace page;
  * every report still carries the four-part stale guard, and the paginated ones still carry their
    local `generation`/`offset` guards as well;
  * `saveAnalyticsFilters` / `restoreAnalyticsFilters` are still per-report and still called from
    every report, and `reloadAnalytics()` is still the one reload mechanism;
  * every endpoint, every filter name, every input attribute and every pagination limit is byte-for
    byte the one that shipped - 25 for the ten paginated reports, 100/offset=0 with no load-more for
    Forecast and Replenishment;
  * the reports that waited for Submit still wait: exactly two of the twelve auto-run, the same two
    that auto-ran before, and the ready state added for the other ten issues no request;
  * every load-bearing business truth is still printed - WIP's signal is not called a bottleneck,
    supplier quantities are not summed across units, material prices are still paired per supplier,
    "approved payment" is still not "paid", the forecast still disclaims stock and lead time,
    dead stock still has no rupiah valuation, and the adjustment audit still says it is not proof;
  * no score, grade, confidence, anomaly probability or AI insight was invented;
  * Capacity's master tooling is still admin-only and still carries `expected_revision`;
  * no chart library, no canvas, no new RAF, no new interval, no new polling;
  * the A5.2 shell, the A5.3 lens, the A3 spring and the frame/timer budget are untouched;
  * A6.1, A6.2 and A6.3 are not regressed;
  * no route, no schema, no migration.

The behavioural half lives in tests/browser_analytics_modern_workspace.cjs. The containment half -
that A6 primitives reached exactly this host, its twelve renderers, its shared markup helpers and
the three Capacity master forms and NOTHING else - stays in
tests/test_apple27_modern_workspace_foundation_contract.py, whose allow-list A6.4 widened on
purpose; what this file adds is the mirror image, that the A6.4 CSS block cannot reach a
thirteenth surface.
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

    Every "this must not appear" assertion runs against this rather than the raw text: the A6.4
    renderers are heavily commented and several of those comments necessarily NAME the thing being
    ruled out - "bukan funnel", "bukan bukti kehilangan stok", "tidak ada pustaka grafik". String
    literals are left intact, because the markup and the operator-facing sentences live inside
    template literals and those are the subject.
    """
    return re.sub(r'(?<!:)//[^\n]*', '', re.sub(r'/\*.*?\*/', '', source, flags=re.S))


def code_css(source):
    return re.sub(r'/\*.*?\*/', '', source, flags=re.S)


def renderer(name):
    """One top-level declaration's body from app.mjs, function or arrow const alike."""
    start = re.search(r'^(?:async )?(?:function|const) ' + re.escape(name) + r'\b', APP, re.M)
    assert start, f'{name} is missing from app.mjs'
    following = re.search(r'^(?:async )?function \w+\(|^const \w+ =|^let \w+ =',
                          APP[start.end():], re.M)
    return APP[start.start():start.end() + (following.start() if following else len(APP))]


def uses(text, primitive):
    """Whole-token search for a primitive inside a `class="..."` attribute."""
    return re.search(r'class="[^"]*(?<![\w-])' + re.escape(primitive) + r'(?![\w-])', text)


APP_CODE = code(APP)
ANALYTICS = section(HTML, 'analytics-view')
BOARD = section(HTML, 'board-view')
MATERIALS = section(HTML, 'materials-view')
PRODUCTS = section(HTML, 'products-view')
PEOPLE = section(HTML, 'people-view')

# The twelve reports, in sidebar order: nav id -> (sidebar label, <h1> title, endpoint).
# This table IS the contract. A thirteenth entry here would have to be a real destination, and a
# missing one would have to be a real removal; neither can happen by accident.
REPORTS = (
    ('wip-ageing-insights', 'WIP ageing', 'WIP ageing & sinyal hambatan',
     '/api/wip-ageing-insights'),
    ('capacity-plan', 'Kapasitas produksi', 'Kapasitas produksi', '/api/capacity-plan'),
    ('production-quality-insights', 'Kualitas produksi', 'Kualitas produksi',
     '/api/production-quality-insights'),
    ('supplier-performance-insights', 'Kinerja supplier', 'Kinerja supplier',
     '/api/supplier-performance-insights'),
    ('material-price-insights', 'Harga bahan', 'Pergerakan harga bahan',
     '/api/material-price-insights'),
    ('purchase-commitment-insights', 'Komitmen PO', 'Komitmen pembelian terbuka',
     '/api/purchase-commitment-insights'),
    ('demand-forecast', 'Forecast demand', 'Forecast demand per SKU', '/api/demand-forecast'),
    ('replenishment', 'Rekomendasi stok', 'Risiko stockout & rekomendasi',
     '/api/replenishment-recommendations'),
    ('size-demand-insights', 'Analisis ukuran', 'Analisis demand per ukuran',
     '/api/size-demand-insights'),
    ('return-insights', 'Analisis retur', 'Analisis retur per SKU', '/api/return-insights'),
    ('dead-stock-insights', 'Dead stock', 'Analisis dead stock', '/api/dead-stock-insights'),
    ('stock-adjustment-insights', 'Audit adjustment', 'Audit adjustment stok',
     '/api/stock-adjustment-insights'),
)
# nav id -> renderer name.
RENDERERS = {
    'wip-ageing-insights': 'showWipAgeingInsights',
    'capacity-plan': 'showCapacityPlan',
    'production-quality-insights': 'showProductionQualityInsights',
    'supplier-performance-insights': 'showSupplierPerformanceInsights',
    'material-price-insights': 'showMaterialPriceInsights',
    'purchase-commitment-insights': 'showPurchaseCommitmentInsights',
    'demand-forecast': 'showDemandForecast',
    'replenishment': 'showReplenishment',
    'size-demand-insights': 'showSizeDemandInsights',
    'return-insights': 'showReturnInsights',
    'dead-stock-insights': 'showDeadStockInsights',
    'stock-adjustment-insights': 'showStockAdjustmentInsights',
}
# The ten reports that page 25 rows at a time, and the id of their "load more" button.
PAGED = {
    'wip-ageing-insights': 'wip-ageing-more',
    'capacity-plan': 'capacity-plan-more',
    'production-quality-insights': 'production-quality-more',
    'supplier-performance-insights': 'supplier-performance-more',
    'material-price-insights': 'material-price-more',
    'purchase-commitment-insights': 'purchase-commitment-more',
    'size-demand-insights': 'size-demand-more',
    'return-insights': 'return-insights-more',
    'dead-stock-insights': 'dead-stock-more',
    'stock-adjustment-insights': 'stock-adjustment-insights-more',
}
# The two single-shot reports: 100 results, offset 0, and no load-more at all.
SINGLE_SHOT = ('demand-forecast', 'replenishment')
# Exactly the two reports that fetched on open before A6.4, and still do.
AUTO_RUN = ('capacity-plan', 'production-quality-insights')

BODIES = {nav: renderer(name) for nav, name in RENDERERS.items()}
CODE_BODIES = {nav: code(body) for nav, body in BODIES.items()}
ANALYTICS_RENDERERS = '\n'.join(BODIES.values())

# The A6.4 containment block: from its first selector to the end of the stylesheet.
A64_MARKER = '#analytics-view{max-width:1360px'
# A6.5 appended the Tanya Beeloft + Integrasi block after this one, so A6.4's slice is now bounded
# above by the A6.5 marker - the same deliberate act A6.3 and A6.4 performed for their
# predecessors. Without it every rule A6.5 writes would be read as an A6.4 rule.
A65_MARKER = '#ai-view,#integrations-view{max-width:1360px'
A64_BLOCK = code_css(CSS)[code_css(CSS).index(A64_MARKER):code_css(CSS).index(A65_MARKER)]


class SharedHostTest(unittest.TestCase):
    """One host, A6.0 grammar, and every id the navigation contract still addresses."""

    def test_the_host_is_a_workspace_page_built_from_a6_primitives(self):
        self.assertIn('<section id="analytics-view" class="workspace-page"', HTML)
        for primitive in ('workspace-page', 'workspace-heading', 'workspace-heading-copy',
                          'workspace-eyebrow', 'workspace-title', 'workspace-subtitle'):
            with self.subTest(primitive=primitive):
                self.assertTrue(uses(ANALYTICS, primitive),
                                f'#analytics-view does not consume .{primitive}')
        # The legacy heading grammar is gone from THIS host, and only from this host.
        for legacy in ('page-heading', 'eyebrow"'):
            with self.subTest(legacy=legacy):
                self.assertNotIn(f'class="{legacy}', ANALYTICS)

    def test_every_addressed_id_survived_the_migration(self):
        for element_id in ('analytics-view', 'analytics-eyebrow', 'analytics-heading',
                           'analytics-body', 'analytics-back'):
            with self.subTest(element_id=element_id):
                self.assertIn(f'id="{element_id}"', ANALYTICS)
        self.assertIn('id="analytics-body" class="analytics-body" aria-live="polite"', ANALYTICS)

    def test_the_host_keeps_exactly_one_h1_and_it_is_the_report_title(self):
        # activateWorkspace() focuses `querySelector('h1')` when the mobile drawer was open, so a
        # second or earlier h1 would steal the focus target from the report title.
        self.assertEqual(ANALYTICS.count('<h1'), 1)
        self.assertIn('<h1 class="workspace-title" id="analytics-heading">', ANALYTICS)

    def test_the_report_question_is_a_subtitle_not_a_second_title(self):
        # §112/§113: the eyebrow stays context, the title stays primary, and the question is a
        # subtitle - not a third equally loud line, and not scattered through twelve markup strings.
        self.assertIn('<p class="workspace-subtitle" id="analytics-subtitle">', ANALYTICS)
        questions = re.search(r'const analyticsReportQuestions=\{(.*?)\n\};', APP, re.S)
        self.assertIsNotNone(questions, 'the report questions live in one shared map')
        for nav, _label, title, _endpoint in REPORTS:
            with self.subTest(nav=nav):
                self.assertIn(f"'{nav}':", questions.group(1))
                # A question explains the business question; it does not restate the title.
                entry = re.search(r"'" + re.escape(nav) + r"':'([^']*)'", questions.group(1))
                self.assertIsNotNone(entry)
                self.assertNotEqual(entry.group(1).strip().rstrip('.'), title)
        self.assertEqual(len(re.findall(r"^\s*'[a-z-]+':'", questions.group(1), re.M)), 12)

    def test_the_session_reset_still_clears_the_whole_heading(self):
        reset = re.search(r"analyticsRequest\+\+; analyticsReport = null;.*?\n.*?\n", APP)
        self.assertIsNotNone(reset)
        for cleared in ("$('analytics-body').replaceChildren()",
                        "$('analytics-heading').textContent='Analitik'",
                        "$('analytics-eyebrow').textContent='Analitik'",
                        "$('analytics-subtitle').textContent=''"):
            with self.subTest(cleared=cleared):
                self.assertIn(cleared, reset.group(0))


class TwelveReportsTest(unittest.TestCase):
    """Exactly the twelve destinations that already existed. No thirteenth, none missing."""

    def test_there_are_exactly_twelve_sidebar_children(self):
        group = HTML[HTML.index('<summary'):]
        children = [nav for nav, *_ in REPORTS]
        for nav, label, _title, _endpoint in REPORTS:
            with self.subTest(nav=nav):
                self.assertIn(f'<button id="{nav}" class="nav-item" type="button">{label}</button>',
                              HTML)
        # The eyebrow is `'Analitik · ' + $(navId).textContent.trim()`, so the label must be the
        # button's ONLY text - an icon or a wrapping span would silently change the eyebrow.
        self.assertEqual(len(children), 12)

    def test_the_registry_is_complete_and_has_no_thirteenth_entry(self):
        registry = re.search(r'const analyticsReports=\{(.*?)\n\};', APP, re.S)
        self.assertIsNotNone(registry, 'analyticsReports is the one reload table')
        body = registry.group(1)
        for nav, name in RENDERERS.items():
            with self.subTest(nav=nav):
                self.assertIn(f"'{nav}':{name}", body)
        self.assertEqual(len(re.findall(r"^\s*'[a-z-]+':show", body, re.M)), 12)

    def test_every_destination_still_resolves_to_the_one_shared_host(self):
        destinations = re.search(r'const workspaceDestinations\s*=\s*\{(.*?)\n\}', APP, re.S)
        self.assertIsNotNone(destinations)
        for nav, *_ in REPORTS:
            with self.subTest(nav=nav):
                self.assertRegex(destinations.group(1),
                                 r"'" + re.escape(nav) + r"'\s*:\s*'analytics-view'")

    def test_every_report_is_bound_to_its_sidebar_button(self):
        for nav, name in RENDERERS.items():
            with self.subTest(nav=nav):
                self.assertIn(f"$('{nav}').onclick={name};", APP_CODE)

    def test_no_report_declares_a_second_workspace_page_or_a_second_host(self):
        # §9: switching between the twelve must not create a second workspace page or a second
        # page-level motion system, so no renderer may emit `workspace-page` or a new view id.
        for nav, body in CODE_BODIES.items():
            with self.subTest(nav=nav):
                self.assertFalse(uses(body, 'workspace-page'))
                self.assertNotIn('activateWorkspace(', body)
                self.assertNotIn('playEntryMotion', body)
        self.assertEqual(HTML.count('id="analytics-body"'), 1)
        self.assertEqual(len(re.findall(r'<section id="analytics', HTML)), 1)


class NavigationAndGuardTest(unittest.TestCase):
    """The stale-response fence, unchanged."""

    def test_activate_analytics_report_still_bumps_the_request_and_derives_the_eyebrow(self):
        activate = renderer('activateAnalyticsReport')
        for line in ('activateWorkspace(navId);', 'analyticsRequest++;', 'analyticsReport=navId;',
                     "$('analytics-eyebrow').textContent='Analitik · '+$(navId).textContent.trim();",
                     "$('analytics-heading').textContent=title;",
                     "$('analytics-body').innerHTML=content;", 'return analyticsRequest;'):
            with self.subTest(line=line):
                self.assertIn(line, activate)

    def test_the_host_still_invalidates_when_another_destination_is_activated(self):
        self.assertIn("{id:'analytics-view',view:'analytics',invalidate(){analyticsRequest++;}}",
                      APP_CODE)

    def test_every_report_keeps_the_four_part_stale_guard(self):
        for nav, body in CODE_BODIES.items():
            with self.subTest(nav=nav):
                guard = ("version===epoch&&view==='analytics'&&analyticsReport==='"
                         + nav + "'&&request===analyticsRequest")
                self.assertIn(guard, body)
                self.assertIn('const request=activateAnalyticsReport(', body)

    def test_every_paginated_report_keeps_its_local_generation_and_offset_guards(self):
        for nav in PAGED:
            body = CODE_BODIES[nav]
            with self.subTest(nav=nav):
                self.assertRegex(body, r'let offset=0,generation=0;')
                self.assertIn('const gen=generation', body)
                self.assertIn('gen!==generation', body)
                self.assertIn('gen===generation', body)

    def test_an_old_response_can_never_repaint_a_newer_run(self):
        # Both fences are checked before ANY paint, in one expression, in every paginated report.
        for nav in PAGED:
            with self.subTest(nav=nav):
                self.assertIn('if(!current()||gen!==generation)return;', CODE_BODIES[nav])
        for nav in SINGLE_SHOT:
            with self.subTest(nav=nav):
                self.assertIn('if(!current())return;', CODE_BODIES[nav])


class FilterMemoryTest(unittest.TestCase):
    """Per-report filter memory and the one reload mechanism."""

    def test_save_and_restore_are_still_per_report_and_still_form_data_based(self):
        save = renderer('saveAnalyticsFilters')
        self.assertIn('analyticsFilters[navId]=Object.fromEntries(new FormData(form));', save)
        restore = renderer('restoreAnalyticsFilters')
        self.assertIn('const saved=analyticsFilters[navId];', restore)
        self.assertIn('form.elements[name]', restore)

    def test_every_report_saves_on_submit_and_restores_on_render(self):
        for nav, body in CODE_BODIES.items():
            with self.subTest(nav=nav):
                self.assertIn(f"saveAnalyticsFilters('{nav}',form)", body)
                self.assertIn(f"restoreAnalyticsFilters('{nav}',form)", body)

    def test_no_report_shares_or_resets_another_reports_filters(self):
        for nav, body in CODE_BODIES.items():
            for other, *_ in REPORTS:
                if other == nav:
                    continue
                with self.subTest(nav=nav, other=other):
                    self.assertNotIn(f"saveAnalyticsFilters('{other}'", body)
                    self.assertNotIn(f"restoreAnalyticsFilters('{other}'", body)
        # The map is written in exactly two places: its declaration and the session reset. Nothing
        # else clears it - in particular, closing a child dialog does not.
        self.assertEqual(APP_CODE.count('analyticsFilters = {}'), 2)
        self.assertIn('let analyticsRequest = 0, analyticsReport = null, analyticsFilters = {};',
                      APP_CODE)
        self.assertIn('analyticsReport = null; analyticsFilters = {};', APP_CODE)

    def test_every_filter_control_is_a_named_control_inside_the_one_form(self):
        # FormData only collects named controls that are IN the form, so a control moved out of the
        # form or renamed would silently drop out of both the query and the saved filters.
        for nav, body in CODE_BODIES.items():
            with self.subTest(nav=nav):
                self.assertIn('new URLSearchParams(Object.fromEntries(new FormData(form)))', body)

    def test_reload_analytics_is_still_the_only_reload_mechanism(self):
        reload_fn = renderer('reloadAnalytics')
        self.assertIn('return analyticsReports[analyticsReport]?.();', reload_fn)
        self.assertEqual(APP_CODE.count('reloadAnalytics()'), 2, 'one definition, one call site')
        self.assertIn("if (view === 'analytics') reloadAnalytics();", APP_CODE)


class EndpointAndPaginationTest(unittest.TestCase):
    """No route changed, no limit changed, and no invented pagination."""

    def test_every_report_still_calls_exactly_its_own_endpoint(self):
        for nav, _label, _title, endpoint in REPORTS:
            with self.subTest(nav=nav):
                self.assertIn(f"api.get('{endpoint}?'+params)", CODE_BODIES[nav])

    def test_the_ten_paginated_reports_still_request_twenty_five_rows(self):
        for nav, more in PAGED.items():
            body = CODE_BODIES[nav]
            with self.subTest(nav=nav):
                self.assertIn("params.set('limit','25')", body)
                self.assertIn("params.set('offset',String(offset))", body)
                self.assertIn('offset+=report.items.length;', body)
                self.assertIn('more.hidden=offset>=report.total;', body)
                self.assertIn(f"$('{more}').onclick=()=>load();", body)
                # A button, not a scroll listener.
                self.assertNotRegex(body, r'IntersectionObserver|scrollend|addEventListener\(\s*[\'"]scroll')

    def test_forecast_and_replenishment_are_still_single_shot_with_no_load_more(self):
        for nav in SINGLE_SHOT:
            body = CODE_BODIES[nav]
            with self.subTest(nav=nav):
                self.assertIn("params.set('limit','100')", body)
                self.assertIn("params.set('offset','0')", body)
                self.assertNotIn("params.set('limit','25')", body)
                self.assertNotIn('offset+=', body)
                self.assertNotIn('analyticsPager(', body)
                self.assertNotIn('generation', body)
                # The honest alternative to a fake pager: narrow the search.
                self.assertIn('Persempit pencarian untuk melihat SKU lain.', body)

    def test_the_paginated_reports_share_one_pagination_presentation(self):
        pager = renderer('analyticsPager')
        self.assertIn('class="pagination"', pager)
        self.assertIn('class="workspace-meta"', pager)
        self.assertIn('class="action-secondary"', pager)
        for nav, more in PAGED.items():
            with self.subTest(nav=nav):
                self.assertIn(f"analyticsPager('{more}',", CODE_BODIES[nav])
                self.assertIn(f"analyticsPagerCount('{more}',offset,report.total,", CODE_BODIES[nav])


class InitialExecutionTest(unittest.TestCase):
    """§13: modernising the UI did not change when a report fetches."""

    def test_exactly_two_reports_auto_run_and_they_are_the_same_two(self):
        self.assertIn('await load(true);', CODE_BODIES['capacity-plan'])
        self.assertRegex(CODE_BODIES['production-quality-insights'],
                         r"\$\('production-quality-more'\)\.onclick=\(\)=>load\(\);load\(true\);")
        for nav, body in CODE_BODIES.items():
            if nav in AUTO_RUN:
                continue
            with self.subTest(nav=nav):
                # The last statement of a submit-gated renderer may bind handlers, never call load.
                tail = body[body.index('form.onsubmit='):]
                self.assertNotRegex(tail, r'(?<![>=])\bload\(true\);\s*$')
                self.assertNotRegex(tail.replace('()=>load()', ''), r'\bload\(\s*(true)?\s*\);\s*\}?\s*$')

    def test_the_ten_submit_gated_reports_got_a_ready_state_that_fetches_nothing(self):
        ready = renderer('analyticsReady')
        # It writes one A6 empty state and nothing else - no api call, no timer, no frame.
        self.assertIn("pageState(messageId,'empty','Laporan belum dijalankan',copy)", ready)
        self.assertNotIn('api.', ready)
        self.assertNotRegex(ready, r'setTimeout|setInterval|requestAnimationFrame|fetch\(')
        for nav, body in CODE_BODIES.items():
            with self.subTest(nav=nav):
                if nav in AUTO_RUN:
                    self.assertNotIn('analyticsReady(', body)
                else:
                    self.assertIn('analyticsReady(', body)

    def test_wip_ageing_still_reads_the_cached_owners_instead_of_fetching_them(self):
        self.assertIn('(boardData?.owners||[])', CODE_BODIES['wip-ageing-insights'])
        self.assertNotIn("api.get('/api/users", CODE_BODIES['wip-ageing-insights'])

    def test_no_report_added_an_api_call_to_decorate_itself(self):
        # §130: each report renders from the data its own endpoint already returned. Only Kapasitas
        # reads masters, and only the two it always read.
        for nav, body in CODE_BODIES.items():
            with self.subTest(nav=nav):
                calls = set(re.findall(r"a(?:pi\.get|llRows)\('([^'?]+)", body))
                expected = {dict((n, e) for n, _l, _t, e in REPORTS)[nav]}
                if nav == 'capacity-plan':
                    expected |= {'/api/work-centers', '/api/products'}
                self.assertEqual(calls, expected)


class FilterPresentationTest(unittest.TestCase):
    """§18-§19: an analytics command surface, with real labels and unchanged attributes."""

    def test_no_report_renders_the_legacy_filter_vocabulary_any_more(self):
        for nav, body in CODE_BODIES.items():
            for legacy in ('filter-form', 'form-grid', 'form-actions', 'form-info',
                           'material-event', 'requirement-values', 'issue-heading',
                           'status-label', 'history-item', 'product-list', 'product-item'):
                with self.subTest(nav=nav, legacy=legacy):
                    self.assertFalse(uses(body, legacy),
                                     f'{RENDERERS[nav]} still emits .{legacy}')

    def test_every_report_uses_one_form_with_a_command_bar(self):
        form = renderer('analyticsFilterForm')
        self.assertIn('class="analytics-filters"', form)
        self.assertIn('class="command-bar"', form)
        self.assertIn('class="command-filters"', form)
        for nav, body in CODE_BODIES.items():
            with self.subTest(nav=nav):
                self.assertIn('analyticsFilterForm(', body)

    def test_the_assumptions_area_is_in_the_same_form_and_is_never_hidden(self):
        # §106/§124: thresholds and lead times are part of what the numbers MEAN. They get a quieter
        # surface, not a disclosure that can hide them.
        assumptions = renderer('analyticsAssumptions')
        self.assertIn('class="utility-panel"', assumptions)
        self.assertIn('class="field-grid"', assumptions)
        self.assertNotIn('<details', assumptions)
        self.assertNotIn('hidden', assumptions)
        form = renderer('analyticsFilterForm')
        self.assertRegex(form, r'analyticsAssumptions\(assumptions\)[^;]*\+\'</form>\'')
        for nav in ('stock-adjustment-insights', 'replenishment', 'production-quality-insights',
                    'capacity-plan'):
            with self.subTest(nav=nav):
                self.assertIn('analyticsParam', CODE_BODIES[nav])

    def test_no_control_uses_a_placeholder_as_its_only_label(self):
        for helper in ('analyticsFilterControl', 'analyticsSearchFilter', 'analyticsParam',
                       'analyticsParamSelect'):
            with self.subTest(helper=helper):
                body = renderer(helper)
                self.assertRegex(body, r'aria-label=|class="field-label"|<span>\$\{e\(label\)\}')

    def test_every_filter_name_and_every_input_attribute_is_unchanged(self):
        expected = {
            'wip-ageing-insights': [('as_of', 'date'), ('idle_days', 'min="1" max="365"'),
                                    ('status', 'select'), ('stage', 'select'),
                                    ('owner_id', 'select'), ('query', 'maxlength="160"')],
            'capacity-plan': [('as_of', 'date'), ('horizon_days', 'min="1" max="90"'),
                              ('warning_percent', 'min="1" max="100"'), ('status', 'select'),
                              ('stage', 'select'), ('work_center_id', 'select')],
            'production-quality-insights': [('as_of', 'date'), ('window_days', 'min="7" max="365"'),
                                            ('warning_percent', 'min="1" max="100"'),
                                            ('change_threshold', 'min="1" max="100"'),
                                            ('query', 'maxlength="160"'),
                                            ('assignment_type', 'select'), ('status', 'select')],
            'supplier-performance-insights': [('as_of', 'date'),
                                              ('window_days', 'min="7" max="730"'),
                                              ('status', 'select'), ('query', 'maxlength="160"')],
            'material-price-insights': [('as_of', 'date'), ('window_days', 'min="7" max="730"'),
                                        ('status', 'select'), ('query', 'maxlength="160"')],
            'purchase-commitment-insights': [('as_of', 'date'),
                                             ('due_soon_days', 'min="1" max="90"'),
                                             ('status', 'select'), ('query', 'maxlength="160"')],
            'demand-forecast': [('as_of', 'date'), ('window_days', 'min="7" max="90"'),
                                ('horizon_days', 'min="1" max="180"'),
                                ('marketplace', 'maxlength="160"'), ('query', 'maxlength="160"')],
            'replenishment': [('as_of', 'date'), ('window_days', 'min="7" max="90"'),
                              ('lead_time_days', 'min="1" max="180"'),
                              ('review_period_days', 'min="1" max="180"'),
                              ('safety_stock_days', 'min="0" max="90"'),
                              ('batch_multiple', 'min="1" max="100000"'),
                              ('marketplace', 'maxlength="160"'), ('query', 'maxlength="160"')],
            'size-demand-insights': [('as_of', 'date'), ('window_days', 'min="7" max="90"'),
                                     ('lookahead_days', 'min="1" max="180"'),
                                     ('marketplace', 'maxlength="160"'),
                                     ('query', 'maxlength="160"')],
            'return-insights': [('as_of', 'date'), ('window_days', 'min="7" max="365"'),
                                ('marketplace', 'maxlength="160"'), ('query', 'maxlength="160"')],
            'dead-stock-insights': [('as_of', 'date'), ('inactivity_days', 'min="7" max="730"'),
                                    ('marketplace', 'maxlength="160"'), ('status', 'select'),
                                    ('query', 'maxlength="160"')],
            'stock-adjustment-insights': [('as_of', 'date'), ('window_days', 'min="7" max="365"'),
                                          ('quantity_threshold', 'min="1" max="1000000000"'),
                                          ('percentage_threshold', 'min="1" max="100"'),
                                          ('repeat_threshold', 'min="2" max="100"'),
                                          ('classification', 'select'), ('source', 'select'),
                                          ('record_status', 'select'), ('stock_status', 'select'),
                                          ('location', 'maxlength="160"'),
                                          ('query', 'maxlength="160"')],
        }
        self.assertEqual(set(expected), set(RENDERERS))
        # `query` is the one control every report spells the same way, so it is emitted by the one
        # shared search helper rather than restated twelve times. Its name and its maxlength are
        # asserted on the helper; the report only has to consume it.
        search = renderer('analyticsSearchFilter')
        self.assertIn('name="query" type="search" maxlength="160"', search)
        for nav, fields in expected.items():
            body = BODIES[nav]
            for name, marker in fields:
                with self.subTest(nav=nav, name=name):
                    if name == 'query':
                        self.assertIn('analyticsSearchFilter(', body,
                                      f'{nav} lost its search control')
                        continue
                    self.assertRegex(body, r"'" + re.escape(name) + r"'|name=\"" + re.escape(name) + '"',
                                     f'{nav} lost the {name} control')
                    if marker not in ('date', 'select'):
                        self.assertIn(marker, body, f'{nav}.{name} lost {marker}')

    def test_the_default_values_the_reports_shipped_with_are_unchanged(self):
        for nav, name, value in (
                ('wip-ageing-insights', 'idle_days', '7'),
                ('capacity-plan', 'horizon_days', '14'),
                ('capacity-plan', 'warning_percent', '80'),
                ('production-quality-insights', 'window_days', '30'),
                ('production-quality-insights', 'warning_percent', '5'),
                ('production-quality-insights', 'change_threshold', '1'),
                ('supplier-performance-insights', 'window_days', '90'),
                ('material-price-insights', 'window_days', '90'),
                ('purchase-commitment-insights', 'due_soon_days', '7'),
                ('demand-forecast', 'window_days', '28'),
                ('demand-forecast', 'horizon_days', '30'),
                ('replenishment', 'window_days', '28'),
                ('replenishment', 'lead_time_days', '14'),
                ('replenishment', 'review_period_days', '30'),
                ('replenishment', 'safety_stock_days', '7'),
                ('replenishment', 'batch_multiple', '1'),
                ('size-demand-insights', 'window_days', '28'),
                ('size-demand-insights', 'lookahead_days', '30'),
                ('return-insights', 'window_days', '90'),
                ('dead-stock-insights', 'inactivity_days', '90'),
                ('stock-adjustment-insights', 'window_days', '30'),
                ('stock-adjustment-insights', 'quantity_threshold', '5'),
                ('stock-adjustment-insights', 'percentage_threshold', '20'),
                ('stock-adjustment-insights', 'repeat_threshold', '3')):
            with self.subTest(nav=nav, name=name):
                line = re.search(r"'" + re.escape(name) + r"'.*", BODIES[nav])
                self.assertIsNotNone(line)
                self.assertIn(f'value="{value}"', line.group(0))


class VisualTruthTest(unittest.TestCase):
    """§15-§17: the visual family is generic, reused, honest, and not a chart library."""

    def test_the_quantity_bar_family_is_a_real_primitive_not_an_analytics_component(self):
        for selector in ('.analytics-bar-list', '.analytics-bar-row', '.analytics-bar-label',
                         '.analytics-bar-value', '.analytics-bar-track', '.analytics-bar-fill'):
            with self.subTest(selector=selector):
                self.assertIn(selector + '{', code_css(PRIMITIVES))
                self.assertNotIn(selector + '{', code_css(CSS))

    def test_the_bar_family_is_reused_by_at_least_three_reports(self):
        consumers = [nav for nav, body in CODE_BODIES.items() if 'analyticsBars(' in body]
        self.assertGreaterEqual(len(consumers), 3,
                                'a primitive reused twice is a report-specific component')
        for nav in ('wip-ageing-insights', 'return-insights', 'demand-forecast',
                    'production-quality-insights', 'material-price-insights'):
            with self.subTest(nav=nav):
                self.assertIn(nav, consumers)

    def test_the_exact_number_always_exists_as_text_outside_the_graphic(self):
        bars = renderer('analyticsBars')
        self.assertIn('class="analytics-bar-label">${e(row.label)}', bars)
        self.assertIn('class="analytics-bar-value">${row.value}', bars)
        # The bar itself is decoration and says so.
        self.assertIn('class="analytics-bar-track" aria-hidden="true"', bars)
        # Its width is geometry only: the computed share is never printed as a percentage.
        self.assertIn('style="--analytics-bar:${width.toFixed(1)}%"', bars)
        self.assertNotRegex(bars, r'analytics-bar-value">\$\{width')

    def test_the_bar_family_adds_no_motion_no_material_and_no_second_engine(self):
        block = code_css(PRIMITIVES)
        family = block[block.index('.analytics-bar-list{'):block.index('.scan-surface{')]
        self.assertNotRegex(family, r'@keyframes|animation\s*:|transition\s*:')
        self.assertNotRegex(family, r'backdrop-filter|filter\s*:\s*blur')
        bars = renderer('analyticsBars')
        self.assertNotRegex(bars, r'requestAnimationFrame|setTimeout|setInterval|\.animate\(')

    def test_capacity_uses_the_returned_utilisation_and_invents_no_replacement(self):
        body = CODE_BODIES['capacity-plan']
        self.assertIn('row.utilization_percent===null', body)
        self.assertIn('Utilisasi belum terukur', body)
        self.assertIn('role="progressbar"', body)
        # The printed value is the returned string; only the bar WIDTH is clamped.
        self.assertIn('class="progress-value">${e(row.utilization_percent)}%', body)
        self.assertIn('--progress-value:${Math.min(100,percent).toFixed(1)}%', body)

    def test_the_wip_stage_distribution_is_not_presented_as_a_funnel(self):
        body = BODIES['wip-ageing-insights']
        self.assertIn('Posisi per tahap', body)
        # The report says what the bars are, and says what they are NOT.
        self.assertIn('saldo ledger saat ini, bukan throughput kumulatif', body)
        self.assertIn('tidak menyatakan konversi dari satu tahap ke tahap berikutnya', body)
        self.assertNotRegex(code(body), r'(?i)funnel')

    def test_no_report_invents_a_score_grade_or_probability(self):
        for nav, body in CODE_BODIES.items():
            with self.subTest(nav=nav):
                self.assertNotRegex(body, r'(?i)\bskor\b|\bscore\b|health\s*grade|confidence'
                                          r'|anomal|probabilit|AI insight|prediksi|predict')


class ReportTruthTest(unittest.TestCase):
    """Every load-bearing business sentence is still printed, verbatim."""

    def test_wip_calls_its_signal_a_signal_and_not_a_bottleneck(self):
        body = BODIES['wip-ageing-insights']
        self.assertIn('Sinyal hambatan terbesar', body)
        self.assertNotRegex(CODE_BODIES['wip-ageing-insights'], r'(?i)bottleneck produksi')
        self.assertIn('Kapasitas target belum dihitung', body)
        self.assertIn('Umur dihitung sejak movement produksi terakhir per order', body)

    def test_capacity_still_says_it_is_an_estimate_and_keeps_its_coverage_gaps(self):
        body = BODIES['capacity-plan']
        self.assertIn('Hari kerja default Senin sampai Jumat', body)
        self.assertIn('estimasi standar, bukan janji jadwal produksi', body)
        self.assertIn('Data kapasitas belum lengkap', body)
        for field in ('coverage_gaps', 'missing_standard_quantity', 'order_reference', 'gap.sku',
                      'gap.stage', 'gap.quantity', 'gap.kind'):
            with self.subTest(field=field):
                self.assertIn(field, body)
        self.assertIn('inactive_work_center', body)

    def test_quality_keeps_its_first_pass_truth_and_its_four_trend_words(self):
        body = BODIES['production-quality-insights']
        self.assertIn('Yield first pass dihitung hanya dari inspeksi awal', body)
        self.assertIn('Koreksi final QC tidak ikut dihitung', body)
        self.assertIn("{worsening:'Memburuk',improving:'Membaik',stable:'Stabil',"
                      "new_baseline:'Baseline baru'}", body)
        for field in ('reinspected_quantity', 'reinspection_record_count',
                      'reinspection_accepted_quantity', 'reinspection_rework_quantity',
                      'reinspection_reject_quantity', 'nonconforming_rate_change_points'):
            with self.subTest(field=field):
                self.assertIn(field, body)

    def test_supplier_never_sums_quantities_across_material_units(self):
        body = BODIES['supplier-performance-insights']
        self.assertIn('Kuantitas bahan tidak dijumlahkan lintas satuan', body)
        for field in ('ordered_by_unit', 'received_by_unit', 'quality_by_unit'):
            with self.subTest(field=field):
                self.assertIn(field, body)
        # Each unit keeps its own row; nothing reduces the three lists to one number.
        self.assertNotRegex(code(body), r'\.reduce\(|Number\(unit\.quantity\)\s*\+')
        self.assertNotIn('supplier_score', body)

    def test_material_price_keeps_the_supplier_pairing_and_the_recorded_date_axis(self):
        body = BODIES['material-price-insights']
        self.assertIn('material dan supplier yang sama', body)
        self.assertIn('Tanggal pencatatan PO dipakai', body)
        self.assertIn('Harga supplier berbeda tidak dicampur menjadi satu tren', body)
        self.assertIn('Ringkasan mencakup hasil pencarian sebelum filter status', body)
        self.assertIn('row.earliest_recorded_date', body)
        self.assertIn('po.recorded_date', body)

    def test_purchase_commitment_never_claims_a_payment_was_made(self):
        body = BODIES['purchase-commitment-insights']
        self.assertIn('Payment approved berarti siap dibayar dan belum membuktikan transfer bank',
                      body)
        self.assertIn('PO pending, ditolak, dibatalkan, dan ditutup tidak masuk laporan', body)
        self.assertNotRegex(code(body), r'>Paid<|\'Paid\'|Sudah dibayar|Terbayar')
        for field in ('payment_pending', 'payment_approved', 'payment_unrequested'):
            with self.subTest(field=field):
                self.assertIn(field, body)

    def test_forecast_keeps_its_formula_and_its_limitations(self):
        body = BODIES['demand-forecast']
        self.assertIn('Demand terbaru berbobot 70% dan periode sebelumnya 30%', body)
        self.assertIn('Retur aktif mengurangi demand pada tanggal pengiriman asal', body)
        self.assertIn('belum memperhitungkan stok tersedia, stok dalam perjalanan, lead time, '
                      'MOQ, atau safety stock', body)

    def test_replenishment_keeps_its_six_risk_states_and_its_bom_gaps(self):
        body = BODIES['replenishment']
        for state in ('out_of_stock', 'stockout_before_replenishment', 'below_safety_stock',
                      'covered', 'insufficient_history', 'no_demand'):
            with self.subTest(state=state):
                self.assertIn(state + ':', body)
        self.assertIn('Harga, supplier, MOQ bahan, serta kapasitas produksi belum menentukan hasil',
                      body)
        self.assertIn('coverage_gaps', body)
        self.assertIn('mempunyai BOM', body)
        self.assertIn('BOM yang belum ada bukan berarti kebutuhan bahannya nol', body)

    def test_size_demand_keeps_the_marketplace_scope_and_the_leader_definition(self):
        body = BODIES['size-demand-insights']
        self.assertIn('Filter marketplace hanya membatasi demand', body)
        self.assertIn('Stok memakai seluruh inventori internal', body)
        self.assertIn('bukan bukti stockout historis', body)
        self.assertIn('consistent_demand_leader', body)

    def test_returns_keep_the_cohort_and_the_four_reason_groups(self):
        body = BODIES['return-insights']
        self.assertIn('Kohort memakai shipment dalam periode yang dipilih', body)
        self.assertIn('Sizing = terlalu kecil atau besar', body)
        self.assertIn('Halaman produk = barang atau warna tidak sesuai', body)
        for reason in ('too_small', 'too_big', 'wrong_item', 'color_mismatch', 'defect', 'other'):
            with self.subTest(reason=reason):
                self.assertIn(reason, body)

    def test_dead_stock_keeps_its_candidate_definition_and_refuses_to_value_stock(self):
        body = BODIES['dead-stock-insights']
        self.assertIn('stok sellable yang masih tersedia, umur lot tertuanya sudah melewati '
                      'ambang, dan tidak mempunyai demand neto', body)
        self.assertIn('Nilai rupiah belum dihitung karena valuasi stok per lot belum tersedia',
                      body)
        self.assertNotRegex(code(body), r'rupiah\(|potensi kerugian|cash trapped|nilai inventori')

    def test_the_adjustment_audit_still_says_it_is_not_proof(self):
        body = BODIES['stock-adjustment-insights']
        self.assertIn('Sinyal adalah alat audit, bukan bukti kehilangan stok', body)
        self.assertIn("{high:'Risiko tinggi',review:'Perlu tinjauan',normal:'Normal'}", body)
        for flag in ('large_quantity', 'large_receipt_share', 'repeated_bucket',
                     'corrected_record'):
            with self.subTest(flag=flag):
                self.assertIn(flag + ':', body)
        self.assertNotRegex(code(body), r'(?i)fraud|kecurangan|pencurian')


class StatusAndStateTest(unittest.TestCase):
    """§22 and §119: A6 chips and A6 states, with the original meanings intact."""

    def test_statuses_became_status_chips_with_a_non_colour_channel(self):
        chip = renderer('analyticsChip')
        self.assertIn('class="status-chip status-chip-${tone}"', chip)
        self.assertIn('class="status-dot" aria-hidden="true"', chip)
        for nav, body in CODE_BODIES.items():
            with self.subTest(nav=nav):
                self.assertIn('analyticsChip(', body)

    def test_not_every_negative_state_became_red(self):
        # A return is not a failure; an overdue PO is. The tones differentiate, and every report
        # that has a benign state still uses a non-danger tone for it.
        for nav in ('return-insights', 'size-demand-insights', 'dead-stock-insights',
                    'material-price-insights', 'wip-ageing-insights'):
            body = CODE_BODIES[nav]
            with self.subTest(nav=nav):
                tones = set(re.findall(r"analyticsChip\('(\w+)'", body)) | set(
                    re.findall(r"(\w+):'(?:danger|warning|success|info|neutral)'", body))
                self.assertTrue({'success', 'info', 'neutral'} & set(
                    re.findall(r"'(danger|warning|success|info|neutral)'", body)),
                    f'{nav} has no non-alarming tone at all')

    def test_every_state_host_keeps_its_id_role_and_state_class(self):
        for host in ('wip-ageing-message', 'capacity-plan-message', 'production-quality-message',
                     'supplier-performance-message', 'material-price-message',
                     'purchase-commitment-message', 'forecast-message', 'replenishment-message',
                     'size-demand-message', 'return-insights-message', 'dead-stock-message',
                     'stock-adjustment-insights-message'):
            with self.subTest(host=host):
                self.assertIn(f'id="{host}" class="state" role="status" hidden', APP)
                self.assertIn(host, A64_BLOCK, 'the legacy .state card must be withdrawn for it')

    def test_loading_empty_and_error_all_use_the_a6_state_grammar(self):
        for nav, body in CODE_BODIES.items():
            with self.subTest(nav=nav):
                self.assertRegex(body, r"pageState\('[\w-]+','loading'")
                self.assertIn('analyticsFail(', body)
                # Rekomendasi stok renders TWO lists in one result, so its empty states stand where
                # their list stands instead of on one shared status host that could not say which
                # list is empty. Either way the shape is the A6 empty state.
                self.assertTrue(re.search(r"pageState\('[\w-]+','empty'", body)
                                or uses(body, 'empty-state'),
                                f'{nav} has no A6 empty state')
        fail = renderer('analyticsFail')
        self.assertIn("pageState(messageId,'error',text,''", fail)
        self.assertIn('Coba lagi', fail)
        self.assertIn('$(retryId).onclick=handler;', fail)

    def test_a_pagination_error_does_not_erase_the_rows_already_loaded(self):
        for nav in PAGED:
            body = CODE_BODIES[nav]
            with self.subTest(nav=nav):
                # replaceChildren() only ever runs on reset, never in the catch block.
                catch = body[body.index('}catch(error){'):]
                self.assertNotIn('replaceChildren()', catch)


class DensityTest(unittest.TestCase):
    """§20, §21 and §117: fewer cards, no card-in-card-in-card."""

    def test_the_composite_record_is_one_list_item_not_a_nested_card(self):
        self.assertIn('.analytics-record{', A64_BLOCK)
        rule = A64_BLOCK[A64_BLOCK.index('.analytics-record{'):]
        rule = rule[:rule.index('}')]
        self.assertIn('border-bottom:1px solid var(--workspace-divider)', rule)
        for material in ('box-shadow', 'border-radius', 'background:'):
            with self.subTest(material=material):
                self.assertNotIn(material, rule)

    def test_nested_evidence_uses_divider_rows_rather_than_another_surface(self):
        subgroup = renderer('analyticsSubgroup')
        self.assertIn('class="analytics-subgroup"', subgroup)
        self.assertIn('class="analytics-sublist"', subgroup)
        self.assertFalse(uses(subgroup, 'data-surface'))
        self.assertFalse(uses(subgroup, 'record-list'))
        sub = A64_BLOCK[A64_BLOCK.index('.analytics-sublist>li{'):]
        sub = sub[:sub.index('}')]
        self.assertNotIn('box-shadow', sub)
        self.assertNotIn('border-radius', sub)

    def test_the_first_level_metric_strips_stay_between_three_and_five_cards(self):
        for nav, body in CODE_BODIES.items():
            for call in re.findall(r'analyticsMetrics\([^\[]*\[(.*?)\n\s*\]\)', body, re.S):
                with self.subTest(nav=nav):
                    cards = len(re.findall(r'^\s*\[', call, re.M))
                    self.assertGreaterEqual(cards, 3)
                    self.assertLessEqual(cards, 5, f'{nav} turned its summary into a dashboard')

    def test_every_report_renders_its_results_into_one_record_list(self):
        for nav in PAGED:
            with self.subTest(nav=nav):
                self.assertRegex(CODE_BODIES[nav], r'<ul id="[\w-]+-results" class="record-list">')


class ChildActionTest(unittest.TestCase):
    """§120: every drill-down still works, and no linked dialog was redesigned."""

    def test_every_child_action_survived_with_its_data_attributes(self):
        expected = {
            'wip-ageing-insights': [('detail', 'Buka order')],
            'capacity-plan': [('detail', 'Buka order')],
            'production-quality-insights': [('final-qc-record', 'Buka final QC ')],
            'supplier-performance-insights': [('purchase-order', 'Buka PO')],
            'material-price-insights': [('purchase-order', 'Buka PO')],
            'purchase-commitment-insights': [('purchase-order', 'Buka PO')],
            'stock-adjustment-insights': [('finished-goods-adjustment', 'Buka adjustment')],
        }
        for nav, actions in expected.items():
            for action, label in actions:
                with self.subTest(nav=nav, action=action):
                    self.assertRegex(CODE_BODIES[nav],
                                     r"analyticsOpen\('" + re.escape(action) + r"'")
                    self.assertIn(label, BODIES[nav])
        opener = renderer('analyticsOpen')
        self.assertIn('data-action="${action}"', opener)
        self.assertIn('data-id="${e(id)}"', opener)

    def test_the_linked_dialogs_were_not_dragged_into_this_migration(self):
        # A6.4 owns the analytics host and the Capacity master forms. The purchase order, final QC,
        # finished-goods adjustment and production order dialogs belong to other workflows.
        for name in ('purchaseOrderDialog', 'finalQcRecordDialog',
                     'finishedGoodsAdjustmentDialog'):
            match = re.search(r'^(?:async )?function ' + name + r'\b', APP, re.M)
            if not match:
                continue
            with self.subTest(name=name):
                for primitive in ('record-list', 'metric-strip', 'analytics-record'):
                    self.assertFalse(uses(renderer(name), primitive),
                                     f'{name} is not an A6.4 surface')


class CapacityMasterTest(unittest.TestCase):
    """§38-§41: admin-only, revision-safe, and unchanged in every rule."""

    def test_the_master_tooling_is_still_gated_on_the_admin_role_in_js(self):
        body = CODE_BODIES['capacity-plan']
        self.assertIn("user.role==='admin'?", body)
        self.assertIn("if(user.role==='admin'){", body)
        # The gate is a JS comparison, not a CSS rule: nothing is merely hidden.
        self.assertNotIn('capacity-center-master', A64_BLOCK.split('@media')[0].split(
            '#capacity-center-master{max-height')[0])
        for control in ('new-work-center', 'edit-work-center', 'capacity-standard-open',
                        'capacity-calendar-open'):
            with self.subTest(control=control):
                gated = body[body.index("user.role==='admin'?"):body.index("$('analytics-body').innerHTML=")]
                self.assertIn(control, gated + body[body.index("if(user.role==='admin'){"):])

    def test_the_three_master_forms_emit_a6_fields_through_the_shared_dialog(self):
        for name in ('capacityWorkCenterForm', 'capacityRoutingStandardForm',
                     'capacityCalendarForm'):
            body = code(renderer(name))
            with self.subTest(name=name):
                self.assertRegex(body, r'capacityField\(|capacitySelect\(|capacityFact\(')
                self.assertIn('reasonField(', body)
                self.assertIn('formDialog(', body)
                # The legacy bare-label helper is gone from these three, and formDialog itself is
                # untouched - A6.4 may not redesign the shared dialog for everyone else.
                self.assertNotRegex(body, r"[^y]field\('")
        self.assertIn('<fieldset id="form-fields"><div class="form-grid">',
                      renderer('formDialog'))

    def test_work_center_rules_are_unchanged(self):
        body = renderer('capacityWorkCenterForm')
        self.assertIn('maxlength="40"', body)
        self.assertIn('maxlength="160"', body)
        self.assertIn('min="1" max="100000" step="1" value="480"', body)
        self.assertIn('expected_revision:current.revision', body)
        # Stage and code stay immutable through the edit path: the edit branch never offers them.
        edit = body[body.index("formDialog('Ubah work center'"):body.index("formDialog('Tambah work center'")]
        self.assertNotIn("'stage'", edit)
        self.assertNotIn("'code'", edit)

    def test_routing_standard_rules_are_unchanged(self):
        body = renderer('capacityRoutingStandardForm')
        self.assertIn("allRows('/api/work-centers',{status:'active'})", body)
        self.assertIn('centers.filter(row=>row.stage===stage)', body)
        self.assertIn('min="0.001" max="100000" step="0.001"', body)
        self.assertIn('expected_revision:standard.revision', body)
        self.assertIn('Tambahkan work center ', body)

    def test_calendar_override_rules_and_meaning_are_unchanged(self):
        body = renderer('capacityCalendarForm')
        self.assertIn('required readonly value="${e(workDate)}"', body)
        self.assertIn('min="0" max="100000" step="1"', body)
        self.assertIn('expected_revision:current?.revision||0', body)
        self.assertIn('Isi 0 untuk libur atau isi menit tambahan untuk lembur.', body)


class ContainmentTest(unittest.TestCase):
    """The mirror image of the widened allow-list: the A6.4 CSS block cannot reach page thirteen."""

    def test_every_selector_in_the_block_belongs_to_analitik(self):
        allowed = ('#analytics-view', '#analytics-body', '#analytics-subtitle',
                   '.analytics-report', '.analytics-filters', '.analytics-record',
                   '.analytics-subgroup', '.analytics-sublist', '#capacity-center-master',
                   '-message', '#capacity-plan-boot')
        selectors = [part.strip() for match in re.finditer(r'([^{}]+)\{', A64_BLOCK)
                     for part in match.group(1).split(',')
                     if part.strip() and not part.strip().startswith('@')]
        self.assertTrue(selectors)
        for selector in selectors:
            with self.subTest(selector=selector[-70:]):
                self.assertTrue(any(name in selector for name in allowed),
                                f'{selector!r} is not an A6.4 surface')

    def test_no_a6_primitive_is_redefined_and_no_earlier_phase_is_touched(self):
        for primitive in ('.record-row', '.record-list', '.metric-card', '.metric-strip',
                          '.command-bar', '.data-surface', '.detail-grid', '.status-chip',
                          '.info-panel', '.utility-panel', '.field', '.progress-meter',
                          '.empty-state', '.analytics-bar-list'):
            with self.subTest(primitive=primitive):
                self.assertNotRegex(A64_BLOCK, r'(?m)^' + re.escape(primitive) + r'[^{,]*\{')
        for foreign in ('#board-view', '#detail-view', '#materials-view', '#products-view',
                        '#people-view', '#bundle-scan-view', '#finished-goods-scan-view',
                        '#command-center', '#order-list', '#batch-list', '#workforce-list'):
            with self.subTest(foreign=foreign):
                self.assertNotIn(foreign, A64_BLOCK)

    def test_the_block_adds_no_material_and_no_motion(self):
        self.assertNotRegex(A64_BLOCK, r'backdrop-filter|filter\s*:\s*blur')
        self.assertNotRegex(A64_BLOCK, r'@keyframes|animation\s*:|transition\s*:')

    def test_the_command_bar_is_still_the_only_blurred_surface(self):
        # Within the A6 content language. The shell's own chrome and the frozen Command Center keep
        # the material they were approved with; what A6.4 may not do is add a blurred surface to a
        # report - twelve of them repeating a blur per record is the cost this rule exists to stop.
        blurred = set()
        for selector, declarations in re.findall(r'([^{}@]+)\{([^}]*)\}', code_css(PRIMITIVES)):
            if re.search(r'backdrop-filter\s*:\s*(?!none)', declarations):
                blurred.update(part.strip() for part in selector.split(','))
        self.assertEqual({part for part in blurred if part.startswith('.')}, {'.command-bar'})
        self.assertNotRegex(A64_BLOCK, r'backdrop-filter')

    def test_the_retired_legacy_rules_stay_for_the_surfaces_that_still_render_them(self):
        for legacy in ('.filter-form', '.form-grid', '.form-actions', '.form-info',
                       '.material-event', '.requirement-values', '.status-label', '.hint',
                       '.page-heading', '.history-item', '.product-list', '.state{'):
            with self.subTest(legacy=legacy):
                self.assertIn(legacy, CSS,
                              f'{legacy} is still rendered by an unmigrated surface')

    def test_no_report_renderer_names_another_phases_host(self):
        for nav, body in CODE_BODIES.items():
            for foreign in ("$('order-list')", "$('batch-list')", "$('workforce-list')",
                            "$('product-list')", "$('summary')"):
                with self.subTest(nav=nav, foreign=foreign):
                    self.assertNotIn(foreign, body)


class DependencyAndBudgetTest(unittest.TestCase):
    """§17 and §130: still vanilla, still the same number of frames and timers."""

    def test_no_chart_library_or_any_other_dependency_was_added(self):
        source = '\n'.join(p.read_text(encoding='utf-8') for p in STATIC.iterdir()
                           if p.suffix in ('.css', '.mjs', '.html', '.js'))
        self.assertNotRegex(source, r'(?i)chart\.js|chartjs|\bd3\b|echarts|highcharts|plotly'
                                    r'|apexchart|recharts|nivo|vega')
        self.assertNotRegex(source, r'cdn\.|unpkg|jsdelivr|cdnjs')
        self.assertNotRegex(source, r"getContext\(['\"]2d|<canvas|new Chart\(")
        self.assertEqual(sorted(p.name for p in STATIC.iterdir()
                                if p.suffix in ('.mjs', '.js')),
                         ['app.mjs', 'appearance.js', 'client.mjs', 'workspace.mjs'])

    def test_the_frame_and_timer_budget_is_unchanged(self):
        self.assertEqual(len(re.findall(r'requestAnimationFrame\(', APP)), 6)
        self.assertEqual(len(re.findall(r'cancelAnimationFrame\(', APP)), 4)
        self.assertEqual(len(re.findall(r'setTimeout\(', APP)), 7)
        self.assertEqual(len(re.findall(r'setInterval\(', APP)), 0)

    def test_no_report_polls_animates_or_schedules_anything(self):
        for nav, body in CODE_BODIES.items():
            with self.subTest(nav=nav):
                self.assertNotRegex(body, r'setInterval|requestAnimationFrame|\.animate\('
                                          r'|setTimeout')

    def test_no_report_uses_svg_or_inline_style_for_anything_but_a_bar_width(self):
        for nav, body in CODE_BODIES.items():
            for style in re.findall(r'style="([^"]*)"', body):
                with self.subTest(nav=nav, style=style):
                    self.assertRegex(style, r'^--(analytics-bar|progress-value):')


class FrozenSurfacesTest(unittest.TestCase):
    """A5.2 shell, A5.3 lens, A3 spring, and the three earlier A6 workspaces."""

    def test_the_approved_shell_and_lens_markup_are_intact(self):
        for anchor in ('class="workspace-window"', 'class="app-shell"', 'id="app-sidebar"',
                       'class="masthead"', 'nav-selection-lens'):
            with self.subTest(anchor=anchor):
                self.assertIn(anchor, HTML)
        self.assertEqual(HTML.count('nav-selection-lens'), 2)
        for selector in ('.workspace-window', '.app-sidebar', '.nav-item', '.nav-selection-lens',
                         '.masthead'):
            with self.subTest(selector=selector):
                self.assertIn(selector, SHELL)
                self.assertNotIn(selector + '{', A64_BLOCK)

    def test_the_a3_spring_is_untouched(self):
        self.assertIn('const navigationLensSpring = {mass:1, stiffness:520, damping:40};', APP)
        self.assertEqual(len(re.findall(r'const navigationLensSpring = \{', APP)), 1)

    def test_the_earlier_a6_workspaces_are_not_regressed(self):
        self.assertIn('#board-view,#detail-view{max-width:1360px', code_css(CSS))
        self.assertIn('#materials-view,#products-view{max-width:1360px', code_css(CSS))
        self.assertIn('#people-view,#bundle-scan-view,#finished-goods-scan-view{max-width:1360px',
                      code_css(CSS))
        for markup, primitive in ((BOARD, 'metric-strip'), (BOARD, 'command-bar'),
                                  (MATERIALS, 'command-bar'), (PRODUCTS, 'workspace-title'),
                                  (PEOPLE, 'metric-strip')):
            with self.subTest(primitive=primitive):
                self.assertTrue(uses(markup, primitive))
        self.assertIn('.is-refreshing{opacity:.78}', code_css(CSS).replace(' ', ''))


class VersionAndSchemaTest(unittest.TestCase):
    """A visible workspace milestone, and nothing behind it."""

    def test_the_version_is_aligned_everywhere(self):
        version = re.search(r'^version = "([^"]+)"',
                            (ROOT / 'pyproject.toml').read_text(encoding='utf-8'),
                            re.M).group(1)
        self.assertEqual(version, '0.113.0', 'A6.4 is the visible workspace milestone')
        self.assertIn(f'version="{version}"',
                      (ROOT / 'beeloft' / 'api.py').read_text(encoding='utf-8'))
        contract = json.loads((ROOT / 'docs' / 'openapi.json').read_text(encoding='utf-8'))
        self.assertEqual(contract['info']['version'], version)
        self.assertEqual(len(contract['paths']), 221, 'A6.4 is presentation only')

    def test_the_schema_did_not_move_and_no_migration_was_added(self):
        versions = [int(value) for path in (ROOT / 'beeloft').glob('*.sql')
                    for value in re.findall(r'PRAGMA user_version\s*=\s*(\d+)',
                                            path.read_text(encoding='utf-8'))]
        self.assertEqual(max(versions), 55, 'A6.4 is presentation only')

    def test_no_backend_route_changed(self):
        from tempfile import TemporaryDirectory
        from beeloft.api import create_app
        contract = json.loads((ROOT / 'docs' / 'openapi.json').read_text(encoding='utf-8'))
        with TemporaryDirectory() as folder:
            live = create_app(Path(folder) / 'contract.sqlite3').openapi()
        self.assertEqual(contract['paths'], live['paths'])

    def test_the_documentation_exists(self):
        doc = ROOT / 'docs' / 'apple27-analytics-modern-workspace.md'
        self.assertTrue(doc.exists(), f'{doc} records the A6.4 decisions')
        text = doc.read_text(encoding='utf-8')
        for anchor in ('50474eb35705c638aacd5b0fa0542b1cce2cbfe1', '0.110.0', 'analytics-view'):
            with self.subTest(anchor=anchor):
                self.assertIn(anchor, text)
        for _nav, label, _title, _endpoint in REPORTS:
            with self.subTest(label=label):
                self.assertIn(label, text)


if __name__ == '__main__':
    unittest.main()
