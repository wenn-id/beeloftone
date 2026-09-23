# Apple-27 A5 — Command Center golden conversion

Status: implemented and locally verified on 23 September 2026.

## Scope and baseline

Work started from fetched `origin/main` at
`077a2090289f920232b4a40367e229d7baad14ca` (A4 scoped lens filter and test fixes),
including the merged dialog regression stabilization at `4720697`.
Branch: `ui/apple27-a5-command-center-golden`. Application version is 0.103.0;
database schema remains 55.

This phase changes Command Center presentation, its acceptance tests, and release
documentation. The only backend edit is the FastAPI version string. No business
endpoint, response schema, database, migration, permission, money calculation,
session, pending-recovery, dialog lifecycle, or action dispatcher changes.

## Composition

Before A5, the page used two numbered bands: marketplace performance, then an
attention list beside a long stack of equally weighted snapshots. Much of the left
column became empty while the snapshot rail continued down the page.

The new order is:

1. Quiet page heading and four marketplace KPIs.
2. Wide gross-sales hero with the real daily trend; beside it, an exception count
   and the first actionable attention item.
3. Compact operational totals, then the full decision queue beside approval
   aggregates and connector health.
4. Marketplace comparison with contribution and ranked products.
5. A full-width context grid. Production and capacity occupy wider cells; quality,
   People, inventory, sales, finance, and the existing AI entry point follow.

The first attention item is intentionally visible in the pulse before the full
queue. This gives the initial viewport an action without compressing the report
into tiny type. The actual queue keeps the backend's order.

All twelve existing runtime hosts remain: `command-center-summary`, `-content`,
`-period`, `-operations`, `-hero`, `-channels`, `-contribution`, `-products`,
`-attention`, `-snapshots`, `-message`, and `-updated`. The hero host now contains
both hero and pulse. The new `command-center-context` host holds approvals and
integrations and is included in error clearing and session teardown.

## Data and truthful deviations from the concept

The page still makes one atomic `GET /api/command-center` request. No secondary
fetch or client-side business calculation was added.

| Presentation | Existing response truth |
| --- | --- |
| Net revenue, orders, units, completed-order AOV | `sales.marketplace.summary` |
| Gross-sales hero and order-status breakdown | The same summary; completed orders only for sales |
| Sales trend | `sales.marketplace.daily`, with `trend_start` / `trend_end` |
| Marketplace comparison and contribution | `sales.marketplace.marketplaces`, including supplied contribution percent |
| Products ranked by units | Existing `sales.marketplace.products` order |
| Exception pulse | `status.attention_count`, `status.critical_count`, first `attention` item |
| Attention domain counts | Counts of existing attention rows using the existing domain map |
| Approval count, recorded amount, absent amounts, kind totals | `approvals.pending_count`, `pending_amount`, `pending_without_amount`, `by_kind` |
| Connector health | `integrations.systems[].health` |
| Context cards and profit strip | Existing production, quality, capacity, workforce, inventory, sales, finance fields |

The hero says **Total penjualan — Kotor · order selesai**, not profit or cashflow.
Net sales remains a separate KPI with its exact amount and refund definition.
Source timestamp and order dates remain explicit. Mekari profit uses its own
financial period; it is not described as today's profit. Exact amounts still use
the existing decimal-safe display helpers.

No growth percentage, generic recent activity feed, budget progress, customer
count, or synthetic health score was added. The conceptual activity area becomes
existing integration/source context. The pulse is a count, with critical versus
other exceptions written as text; no invented denominator or decorative score
ring. The decorative AI orb and the redundant domain bar-chart renderer were
removed; domain counts remain in the pulse.

Approvals are aggregates for all pending requests, not the first inbox page. Native
`details` exposes all nine kinds, including zero counts, using the existing human
labels for purchase request/order, supplier payment, marketing budget, production
change, leave, overtime, payroll batch, and AI action. Missing amounts are reported
separately. The panel opens the existing inbox without making decisions inline.

Integration labels distinguish **Sehat**, **Gagal**, **Stale**, **Belum lengkap**,
and **Belum sync**. Missing Jubelio orders show unavailable copy and dashes, not
revenue zero or a reassuring no-refund badge. Missing finance shows unavailable
copy. A real snapshot with a zero-value daily point still draws that point and
labels its peak Rp0: the chart's safe scale denominator no longer changes the
displayed peak to Rp1. Empty daily data draws no trend. Order-status bar widths use
actual proportions without a fabricated minimum share.

## Materials, motion and lifecycle

A single static `::before` on `.workspace-main`, conditional on the visible
Command Center, paints two restrained radial gradients using existing semantic
tokens. It has `pointer-events:none`, no DOM content, no image, blur, animation,
parallax, canvas, timer, or event handler. It disappears when another workspace is
active. Content stays on opaque `--material-content` surfaces; the operational
strip uses opaque `--material-content-subtle`.

A4's filter set is unchanged: masthead, sidebar, and the shared lens only in the
separate approval context. The travelling lens inside the filtered sidebar remains
unfiltered. Content, tables, charts, error text and dialogs never receive glass.
The A4 unsupported-filter, reduced-transparency and forced-colors paths are unchanged.

A3 remains frozen: mass 1, stiffness 520, damping 40; settle distance .25 and speed
2; substep 1/120, max frame .032, stall .2; morph cap .07 and speed 3000. Velocity
continuity, rebasing and reduced-motion cancellation are unchanged. Production
code retains six RAF call sites, three cancellation sites, seven timeout sites,
and zero intervals. A5 adds none.

The existing sequence remains `guardPending` → activate workspace → increment
request → API → epoch/request/view guard → render → report available. Refresh
retains the previous content while busy. Failed refresh clears the complete report,
including the new context panel. Navigation away prevents a delayed response from
painting. Auth teardown clears the new host alongside the old ones.

## Responsive layout and accessibility

At 1440 and 1280, four KPI columns lead a wide hero and smaller pulse. At 1200 and
below, including 1024 and 981, the KPI and context grids reduce to two columns.
At 980, the hero and main sections become one column, with a two-column pulse and
utility rail where space permits. At 768 these remain readable; below 760 the
utility/context panels become single-column. At 390, the pulse is compact, action
buttons span their row, products wrap with their amounts below the title, and the
order-status strip uses two columns. The marketplace table retains its labelled
columns inside its own horizontal scroller. The existing mobile drawer is unchanged.

KPI semantics remain `dl`; charts retain `role="img"` and meaningful source/date
labels. Status always has text. Details and all actions remain native keyboard
controls with visible focus and mobile targets of at least 44px. Labels and
product names wrap. The new background has no accessibility-tree presence.
Dark mode uses the existing distinct dark tokens, with opaque cards and quiet
gridlines rather than a second palette or brighter effects.

## Verification evidence

Local evidence lives in `C:\Users\acer\AppData\Local\Temp\beeloft-a5-qa`;
screenshots are not committed. Saved baseline HTML/CSS/JS were verified against
`077a209`, allowing only Windows newline normalization. The same populated fixture
is served to both versions. Fixtures are confined to the browser test.

### A4 optical remeasurement

The browser decodes screenshots to sample the final composited pixels. For each
label it reads the real foreground, temporarily hides glyph color with transitions
disabled, and takes the lowest contrast of nine background samples. It restores
the label immediately. No opacity or material is overridden. Masthead positions
are checked at scroll offsets 0, 600 and 1200. The values below are minima.

| Label | Light before → after | Dark before → after |
| --- | --- | --- |
| Masthead brand | 16.56 → 16.56 | 15.27 → 15.27 |
| Masthead primary context | 14.80 → 14.80 | 13.31 → 13.31 |
| Masthead metadata in context pill | 5.23 → 5.23 | 6.00 → 6.00 |
| Masthead account directly on glass | 5.75 → 5.70 | 6.09 → 6.33 |
| Sidebar primary | 8.94 → 8.94 | 9.80 → 9.80 |
| Sidebar secondary | 5.86 → 5.86 | 6.89 → 6.89 |
| Command Center selected lens | 4.98 → 4.98 | 5.51 → 5.51 |
| Approval selected lens | 4.69 → 4.69 | 5.74 → 5.74 |

New content also passes: pulse body 16.83 / 14.92, secondary text 9.09 / 9.57,
warning chip 6.28 / 7.92, critical status 5.91 / 7.84 (light / dark).
Every sampled label exceeds 4.5:1. `--chrome-tint` remains `#ffffffd1` / `#202023d1`
(the existing approximately .82 alpha), with 20px blur and saturation 1.3.
The selected lens's own tint and filter containment also remain unchanged.
There is no measured reason to increase opacity or blur. These are current
before/after measurements, not substituted historical A4 figures.

### Local performance

Headless Chromium on Windows, populated synthetic report, final paired local
sample at the same 1440×1000 viewport in both versions.
Timings include click, request, render and settling; they are not CPU-only render
times or a production latency benchmark. Frame observations include the existing
A3 spring and finite theme transition. Sampling uses the original browser RAF so
its own callbacks are excluded from the application's idle accounting.

| Operation | Before / after duration ms | Before / after p95 frame gap ms | Before / after max gap ms | Before / after long tasks |
| --- | --- | --- | --- | --- |
| First populated Command Center | 349.0 / 360.2 | 7.1 / 13.8 | 13.8 / 20.9 | 0 / 0 |
| Six scroll positions | 654.6 / 662.6 | 7.1 / 7.1 | 7.2 / 7.2 | 0 / 0 |
| Rapid navigation and spring | 417.9 / 428.9 | 7.1 / 7.1 | 13.8 / 14.0 | 0 / 0 |
| Light-to-dark transition | 581.5 / 589.7 | 14.0 / 27.7 | 21.0 / 28.0 | 0 / 0 |

Idle observation over 350ms in both versions: **zero executed callbacks and zero
pending RAFs**. No layout-shift entries occurred during render, scroll or rapid
navigation. Theme switching recorded the same small recent-input shift (.0000799)
in both versions. The final pair had no gap above 32ms. An earlier exploratory
A5 theme sample did record 61/55/58ms long tasks and a 76.1ms maximum gap; it is
retained in `a5-performance-initial.json`. Local results vary, so this is not a
claim of universally smooth rendering or 60fps. Real-device Safari/mobile GPU
and battery behavior are not measured here. Final raw data is in
`a5-performance.json` and `a5-optics.json`.

### Tests, build and visual review

The six new Python contract checks cover stable hosts, request/error/teardown
ordering, static page-scoped depth, material containment, existing data fields,
and frozen motion. All 61 Apple-27 static contract tests pass. The new browser
module checks first load, exact KPIs, marketplace rows and products, approvals
including all nine zero kinds, every action destination, all connector states,
held refresh, replacement, stale-response rejection, complete error clearing,
missing sources, zero-value trend, native keyboard focus, opaque cards, contrast,
zero idle RAF, eight widths, and 320px at 200% text.

The older shared-UI assertion for exactly two numbered bands was replaced with
assertions for the new overview, decisions, marketplace and business-context
sections. Its functional, KPI, radius, width, theme and overflow checks remain.
No A3/A4 or dialog lifecycle test was weakened.

The clean isolated Python environment is
`C:\Users\acer\AppData\Local\Temp\beeloft-a0-audit\venv\Scripts\python.exe`.
It satisfies pinned requirements; the repository's older `.venv` does not.

| Release check | Result |
| --- | --- |
| `python -m unittest discover -s tests -v` | Pass: 637 tests in 925.720s |
| `python -m pip check` | Pass; no broken requirements |
| `python -m compileall -q beeloft` | Pass |
| `node --check beeloft/static/app.mjs` and `client.mjs` | Pass |
| `node tests/test_client.mjs` | Pass, including exact retry, auth binding, CSV and date boundaries |
| `python tests/run_browser.py --channel chromium` | Pass: all 84 modules plus the smoke runner; no JS errors |
| `python -m build` | Pass: wheel and sdist |
| Version / OpenAPI / schema / packaged bytes | Pass |
| `git diff --check` | Pass |

The browser command uses the already bundled Playwright package through
`--playwright-module C:\Users\acer\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules\playwright`.
The full run includes `browser_motion_dialogs.cjs`, `browser_dialog_closing.cjs`,
all 27-destination consistency checks, A2 lens, A3 spring, and A4 glass. The paired
A5 run additionally sets `BEELOFT_A5_BASELINE_DIR` to the saved `before` directory.
Logs: `python-full.log`, `browser-full.log`, `paired-final.log`, `build.log`, and
`release-verification.log` in the local evidence directory.

Build output: `dist/beeloft_one-0.103.0-py3-none-any.whl` and
`dist/beeloft_one-0.103.0.tar.gz`. All four packaged static files match tested
source bytes in both archives. Runtime OpenAPI equals the regenerated stored
contract (221 paths, 85 component schemas); the baseline structural difference is
only `info.version`. A fresh database reports `PRAGMA user_version = 55`.

Screenshot paths relative to the local evidence directory:

- `before/a5-1440-light.png`, `before/a5-1440-dark.png`
- `a5-1440-light.png`, `a5-1440-dark.png` and their `-viewport` variants
- `a5-1024-light.png`, `a5-768-light.png`
- `a5-390-light.png`, `a5-390-dark.png`
- `a5-320-200-text.png`, `a5-320-200-decisions-viewport.png`,
  `a5-320-200-bottom-viewport.png` (actual viewport captures; the 18,000px full-page
  capture exceeded reliable compositor capture height on this engine)
- `a5-empty-missing.png`

Full-page images and readable crops were reviewed for hierarchy, spacing, card
separation, chart clarity, priority visibility, mobile reflow, and dark contrast.
At 390, labels and actions are readable and the secondary context has no empty
desktop-height placeholders. At 320 / 200% text, actions and labels wrap without
clipping or document overflow; the comparison table scrolls inside its card.
Automated screenshots are evidence, not pixel-equality assertions. This local
review is not a claim of user design approval.

### Changed files and local state

Presentation: `beeloft/static/index.html`, `style.css`, `app.mjs`.
Release metadata: `pyproject.toml`, `beeloft/api.py`, `docs/openapi.json`.
Tests: `tests/test_apple27_command_center_golden_contract.py`,
`tests/browser_command_center_golden.cjs`, `tests/browser_smoke.cjs`,
`tests/browser_shared_ui.cjs`.
Documentation: this report, `README.md`, `docs/version-history.md`, and only the
A5 roadmap row of `docs/apple27-native-parity-audit.md`.

The A5 change set has eleven modified files and three new files. Historical A0–A4
evidence is unchanged. The branch is prepared for draft review.

## A5 / A6 boundary

A5 stops at Command Center. No global control redesign, native form replacement,
sheet/popover/alert system, Production conversion, Materials/People/Approval/
Analytics redesign, bottom navigation, or new motion architecture is included.
Merge and deployment remain outside this phase.
