# Shopeers visual reconstruction verification

Branch: `ui/shopeers-redesign`

## Golden reference

The Shopeers AI-powered B2B eCommerce analytics dashboard by Dipa Inhouse:
<https://dribbble.com/shots/26628350-Shopeers-AI-Powered-B2B-eCommerce-Analytics-Dashboard>

That shot is the visual specification for this change. It was absent from the branch, so it was retrieved from the
original source and measured before any implementation work.

**The artwork is deliberately not redistributed in this repository.** To reproduce the comparisons below, save the
shot from the link above to `docs/reference/shopeers-dashboard-reference.png`; that path is git-ignored.

The artboard measures 1441 x 1033 inside a 1600 x 1200 presentation matte, so the reference describes a
1440px-wide full-bleed application; the grey surround is Dribbble matting and is not reproduced.

## Measured reference versus delivered implementation

Values were sampled from the reference with Pillow and read back from the running app with
`getBoundingClientRect` / `getComputedStyle` at a 1440 x 1024 viewport.

| Property | Reference | Delivered |
| --- | --- | --- |
| Header height | 72px | 72px |
| Sidebar width | 256px | 256px |
| Content padding | 32px | 32px |
| Working column | 1120px | 1120px |
| KPI card | 263 x 131, 22px gap | 264 x 130, 22px gap |
| Decision column | 687px | 687px |
| Operational rail | 411px | 411px |
| Grid gap | 22px | 22px |
| Card radius | 16px | 16px |
| Navigation row | 40px, 10px radius | 40px, 10px radius |
| Button shape | 40px pill | 40px pill |
| Canvas | `#f4f5f8` | `#f4f5f8` |
| Card border | `#ebecef` | `#ebecef` |
| Primary | `#2d5efb` | `#2d5efb` |
| Active navigation surface | `#eef3fd` | `#eef3fd` |
| Navigation edge marker | `#3c5dff`, 3px | `#3c5dff`, 3px |
| Page title | ~26px / 700 | 26px / 700 |
| KPI figure | ~32px / 800 | 32px / 800 |

## Visual comparison passes

1. **Macro layout.** Rendered a desktop screenshot and compared it with the reference. Corrected the shell
   framing, the sidebar/brand column and its shared vertical rule, the KPI proportions, and the main grid ratio.
2. **Visual system.** Retuned tokens, typography, radii, border and shadow intensity, the primary blue, neutral
   surfaces, and icon sizing. Fixed a horizontal overflow at 200% text zoom (an inline account element that could
   not shrink, and status labels that could not wrap).
3. **Pixel-level polish.** Aligned both grid columns to the same top edge by visually hiding the rail's section
   heading, compacted the decision rows from 103px to 81px, tightened card padding and metric rhythm, corrected
   the mobile header (legacy `≤650px` rules were stacking the wordmark and stretching the avatar), and replaced
   the text arrows in back controls with sprite icons.
4. **Further passes.** Reworked the hero card so it is always populated from real data, widened its chart slot,
   pinned the approval CTA to the bottom of the sidebar as in the reference, coloured the breakdown glyphs, and
   stopped bar-chart labels truncating.
5. **Marketplace rebalance passes.** Rendered the new business band against the reference with a populated
   snapshot. Fixed rupiah headline figures overflowing the KPI value row (compact `Rp39,9 jt` display with the
   exact amount kept in the footer and `title`), and stopped the per-channel status flow wrapping by dropping
   zero-count statuses. Confirmed the hero now mirrors the reference's headline-plus-trend composition and that
   the comparison table, contribution bars, and ranked products occupy the reference's table, bar-chart, and
   product-row slots.

## Command Center hierarchy

The page leads with marketplace business performance and demotes operations to a second, visually quieter band.

### Band 01 — marketplace business performance (Jubelio)

| Reference surface | Beeloft data |
| --- | --- |
| Four KPI cards | `net_revenue`, `orders`, `units`, `average_order_value` from `sales.marketplace.summary`, with chips and footers from `refund_amount`, `completed`, `pending`, `processing`, `cancelled`, `completed_orders`, `marketplaces` |
| Hero metric + trend chart | `gross_revenue` as the headline with an SVG line/area chart over `sales.marketplace.daily[]` — one real point per order date, no gap filling |
| Nested breakdown card | Order funnel: `pending / processing / completed / cancelled` with bars proportional to real counts |
| Table slot | Marketplace performance comparison: per channel `orders`, `units`, `average_order_value`, `contribution_percent`, `gross_revenue`, `net_revenue`, and the non-zero status flow |
| Bar-chart slot | Marketplace contribution — proportional bars over `contribution_percent`, ordered by completed gross sales |
| Ranked product rows | Top selling products from `sales.marketplace.products[]`, ordered by units sold, showing SKU, name, colour/size, order count, units, and revenue |

### Band 02 — operational decisions

| Reference surface | Beeloft data |
| --- | --- |
| Inline stat strip | `production.active_orders`, `approvals.pending_count`, `status.attention_count`, `finance.current.net_profit` |
| List / table surface | `Perlu perhatian` — the `attention[]` queue, critical first, with a column header, dashed row rules, a severity tile, and the existing action button |
| Gauge | `quality.first_pass_yield_percent` (integer display; the exact value stays in the metric list) |
| Progress / meter treatments | `rework_quantity / in_progress_quantity` and `capacity.required_minutes / available_minutes` |
| Three-up breakdown | `workforce.present / leave / absent` |
| Bar chart | Exception counts per `attention[].kind` |
| Status area | `integrations.systems[].health` badges |
| AI panel | Tanya Beeloft, opened through the existing `ai-brain` action |

## Marketplace data rules honoured

- **No schema migration.** Only the existing `jubelio_order_snapshot_*` and `jubelio_return_snapshot_*` tables and
  the existing `idx_jubelio_order_snapshot_product` index are used.
- **One endpoint, additive keys.** `/api/command-center` remains the only source. `sales` keeps all nine original
  keys and gains a single `sales.marketplace` object. Nothing was removed or renamed.
- **Dynamic channels.** No marketplace name is hardcoded anywhere in the backend or the interface; the UI renders
  whatever channels the snapshot contains.
- **Case-insensitive grouping.** Channels group on a whitespace-collapsed, case-folded key, so `Shopee`,
  `shopee`, and `  SHOPEE  ` are one channel. The displayed label is the most frequent real spelling, preferring
  mixed case on ties, so `Shopee` wins over `SHOPEE`.
- **One shared definition.** Sales, units, and AOV all derive from completed orders. AOV is completed gross
  revenue divided by completed order count, labelled `AOV order selesai`, and returns `0.00` rather than dividing
  by zero when nothing completed.
- **Latest batch only.** The trend groups the latest batch by `ordered_at` in Asia/Jakarta, so an order that
  recurs across snapshot batches is never counted twice. A test asserts that re-sending the same order in a later
  batch does not accumulate, and that dropping it shrinks the figures.
- **Honest window metadata.** `period_start` / `period_end` cover every accepted order in the batch;
  `trend_start` / `trend_end` cover only the completed-sales series the chart actually plots. The UI labels the
  chart from the latter and the band from the former.
- **Aligned net sales.** Only refunds whose `external_order_id` matches a completed order in the current order
  batch are subtracted. Everything else is surfaced separately as `unmatched_refunds` /
  `unmatched_refund_amount` instead of being netted off unrelated revenue.
- **Snapshot-scoped wording.** No figure is labelled "today" or "this month". Surfaces read
  `Jubelio snapshot <time>` plus the real derived order date range.
- **Not fabricated.** Marketplace fees, commissions, voucher/discount allocation, shipping subsidy, conversion,
  traffic, true channel margin, and per-shop breakdowns do not exist in the source data and are absent from the
  interface. Per-SKU refund value is likewise not derivable, so it is not shown.

## Backend additions

Additive only; no schema change, no new endpoint, no permission change.

- `store.jubelio_marketplace_performance()` — reads the latest order batch (and latest return batch when present)
  and returns `summary`, `marketplaces[]`, `products[]`, `daily[]`, plus snapshot and window metadata.
- `command_center.py` — calls it once and attaches the result as `sales.marketplace`.

### New Python coverage — `tests/test_jubelio_marketplace_performance.py` (11 tests)

Marketplace case-insensitive normalisation and canonical labelling; latest-batch-only aggregation; no
double-counting when an order recurs across batches; Jakarta-day sales grouping and window metadata; top-product
aggregation and unit ordering; aligned refund/net-sales calculation including unmatched and non-refunded returns;
refunds against uncompleted orders; zero/empty-data behaviour; AOV excluding uncompleted orders; AOV
zero-division; and preservation of every pre-existing `sales` field.

## Scope safeguards

- **The visual reconstruction commit modifies no test file and no backend file.** It touches only
  `beeloft/static/index.html`, `beeloft/static/style.css`, `beeloft/static/app.mjs`, `.gitignore`, `DESIGN.md`,
  and `docs/`.
- **The marketplace dashboard commit does change the backend, additively and by explicit request.** It adds
  `store.jubelio_marketplace_performance()`, attaches `sales.marketplace` in `command_center.py`, and adds
  `tests/test_jubelio_marketplace_performance.py`. No database schema, migration, endpoint, permission,
  accounting rule, inventory rule, or production rule was changed, and no existing API field was removed or
  renamed.
- **The pull request as a whole does contain test updates**, inherited from the earlier redesign commit
  (`169d937`) on this branch. Those updates adapted the acceptance suite to that commit's responsive
  sidebar/navigation changes and cover `tests/test_web.py` plus eleven `tests/browser_*.cjs` modules:
  `browser_smoke`, `browser_management_command_center`, `browser_ai_investigation`, `browser_bom`,
  `browser_bundle_scanning`, `browser_payroll_approvals`, `browser_product_external_mappings`,
  `browser_production_quality_insights`, `browser_reservations`, `browser_returns_adjustments`, and
  `browser_workforce_approvals`. That commit changes no backend or business-rule file either, so the PR as a
  whole still leaves the backend, schema, and business rules untouched.
- `showCommandCenter()` still requests `/api/command-center` once, keeps its request/epoch/view race guards, uses
  only existing response fields, and keeps every `data-action` value, drill-down, and ordering.
- `app.mjs` changes are limited to markup produced for presentation plus new pure render helpers
  (`svgIcon`, `commandGauge`, `commandMeter`, `commandSplit3`, `commandBars`, `commandHeroBars`,
  `attentionDomainRows`) and the matching reset of the new hero container.
- All element IDs, accessible names, `data-command-snapshot` / `data-command-attention` attributes, heading
  semantics, `hidden`-based visibility, and the `.attention-panel` wider than `.snapshot-panel` relationship are
  preserved.
- Navigation destinations are unchanged: the same 24 buttons with the same IDs, labels, and handlers. The twelve
  analytics destinations moved into an expanded disclosure group and remain visible and clickable.

## Verification results

- Python: `python -m unittest discover -s tests` — **351 tests passed** on the final code (340 pre-existing plus
  11 new marketplace-performance tests).
- Browser: the **complete Playwright acceptance suite passed end to end** on the final code, all 58 modules,
  with `assert.deepEqual(errors, [])` confirming no JavaScript errors.
- JavaScript: `node --check` on `app.mjs` and `client.mjs`; `node tests/test_client.mjs` passed (escaping, dates,
  exact-write retry, read-only requests, auth header, structured errors, CSV access).
- Responsive: no horizontal overflow at 320, 390, 768, 1024, and 1440 CSS pixels.
- 200% text zoom: no horizontal overflow at 390px. The base font size is now expressed in `rem`, so text zoom
  scales the interface instead of being pinned by an absolute `px` body size.
- Keyboard: focus rings on all controls, drawer Escape dismissal with focus return to `Menu`, focus return after
  dialog close, and the first sidebar `.nav-item` focusable.
- Dark theme: full token set re-declared for `[data-theme='dark']` and captured during QA.
- `pip check` reported no broken requirements; `compileall` and `git diff --check` are clean.
- Contrast: primary `#2d5efb` measures 5.11:1 on white in both directions; muted text `#6b7385` measures 4.75:1,
  so secondary copy meets WCAG AA even though the reference's lighter grey would not.

### Defect found and fixed outside the redesign surface

`tests/browser_workforce_approvals.cjs` asserts that the People approvals dialog does not overflow at 200% text
zoom. That assertion **failed identically on the unmodified branch code** in this environment, because the CSS
targets Segoe UI and the fallback font here is wider, so single-word labels in the dense metric strip forced
layout overflow. It is fixed by letting those labels break and by reducing the strip's padding on narrow
viewports. Verified by running the module against unmodified and modified code in isolation.

## Screenshots

- [Command Center desktop](screenshots/command-center-desktop.png)
- [Command Center mobile](screenshots/command-center-mobile.png)
- [Command Center at 200% text zoom](screenshots/command-center-200-text.png)

All three are regenerated by the acceptance suite itself, so they always reflect the tested build. The acceptance
fixture contains a single Jubelio order in one marketplace, so in those three images the marketplace band renders
its minimal honest state: a one-point trend, one channel at 100%, and one ranked product. That is real fixture
data, and it doubles as proof that the sparse-data states render correctly.

- [Marketplace band with a populated snapshot](screenshots/command-center-marketplace-seeded-preview.png)

**That last image is a local design-review preview rendered against a seeded snapshot. The numbers in it are
synthetic fixture data, not Beeloft's trading figures.** It exists only because the acceptance fixture is too
small to show the layout at scale; the seed script is not part of the repository.

## Regression report

No functional, API, permission, accessibility, JavaScript, or overflow regressions were detected. The one
initially observed browser failure — focus return after closing the People dialog from the mobile drawer — did not
reproduce on re-runs or in faithful isolation; it stems from a pre-existing microtask race between the sidebar
handler and the dialog opening, which this change does not touch.
