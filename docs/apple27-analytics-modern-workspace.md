# Apple-27 · A6.4 — Analytics modern workspace

**Baseline** `50474eb35705c638aacd5b0fa0542b1cce2cbfe1` (A6.3 merged, exact-SHA CI #165 green)
**Branch** `ui/apple27-a6-4-analytics`
**Version** `0.109.0` → `0.110.0`
**Schema** `PRAGMA user_version = 55`, unchanged — no migration
**OpenAPI** structural diff is `info.version` only; 221 paths, 85 schemas, unchanged

A6.0 built the shared inner-workspace language. A6.1 spent it on Produksi, A6.2 on Bahan baku and
Master SKU, A6.3 on People and the two scanners. A6.4 spends it on the one place in the product
where **twelve** destinations share **one** host.

That is what makes this phase different. Every earlier phase migrated a page. This one migrated a
*grammar*: twelve reports that had to stop looking like twelve legacy forms without becoming twelve
unrelated visual systems, and without becoming one dashboard either.

---

## 1. The twelve reports

There are exactly twelve analytics destinations. There is no thirteenth, and none was removed. All
twelve share `#analytics-view` and remain distinct reports.

| # | Sidebar label | `<h1>` title | Endpoint | Page size | Runs on open |
|---|---|---|---|---|---|
| 1 | WIP ageing | WIP ageing & sinyal hambatan | `/api/wip-ageing-insights` | 25 | no |
| 2 | Kapasitas produksi | Kapasitas produksi | `/api/capacity-plan` | 25 | **yes** |
| 3 | Kualitas produksi | Kualitas produksi | `/api/production-quality-insights` | 25 | **yes** |
| 4 | Kinerja supplier | Kinerja supplier | `/api/supplier-performance-insights` | 25 | no |
| 5 | Harga bahan | Pergerakan harga bahan | `/api/material-price-insights` | 25 | no |
| 6 | Komitmen PO | Komitmen pembelian terbuka | `/api/purchase-commitment-insights` | 25 | no |
| 7 | Forecast demand | Forecast demand per SKU | `/api/demand-forecast` | 100, offset 0 | no |
| 8 | Rekomendasi stok | Risiko stockout & rekomendasi | `/api/replenishment-recommendations` | 100, offset 0 | no |
| 9 | Analisis ukuran | Analisis demand per ukuran | `/api/size-demand-insights` | 25 | no |
| 10 | Analisis retur | Analisis retur per SKU | `/api/return-insights` | 25 | no |
| 11 | Dead stock | Analisis dead stock | `/api/dead-stock-insights` | 25 | no |
| 12 | Audit adjustment | Audit adjustment stok | `/api/stock-adjustment-insights` | 25 | no |

No endpoint, query parameter, parameter name, input attribute, default value, response field or
page size changed. A6.4 is a presentation migration.

---

## 2. The shared host

`#analytics-view` (`index.html`) is now A6.0 `workspace-page` grammar:

```html
<section id="analytics-view" class="workspace-page" hidden>
  <button id="analytics-back" class="quiet back" type="button">… Papan produksi</button>
  <div class="workspace-heading"><div class="workspace-heading-copy">
    <p class="workspace-eyebrow" id="analytics-eyebrow">Analitik</p>
    <h1 class="workspace-title" id="analytics-heading">Analitik</h1>
    <p class="workspace-subtitle" id="analytics-subtitle"></p>
  </div></div>
  <div id="analytics-body" class="analytics-body" aria-live="polite"></div>
</section>
```

What was preserved deliberately, because other systems address it:

- **`analytics-view`** — `workspaceDestinations` maps all twelve nav ids to it.
- **`analytics-eyebrow`** — written by `activateAnalyticsReport()` as `'Analitik · ' + navLabel`.
- **`analytics-heading`** — the report title, and the **only** `<h1>` in the section, because
  `activateWorkspace()` focuses `querySelector('h1')` when the mobile drawer was open.
- **`analytics-body`** — kept its id, its `analytics-body` class and its `aria-live="polite"`, so
  every report swap is still announced.
- **`analytics-back`** — unchanged `quiet back` button, same as the other migrated views.

### Heading hierarchy

The brief's §112 problem was two equally loud titles. The fix is not to delete the eyebrow — it is
real context — but to let the A6.0 type scale do its job: `workspace-eyebrow` is metadata-sized,
`workspace-title` is page-title-sized. The reading order is therefore

```
Analitik · Harga bahan          ← eyebrow, context
Pergerakan harga bahan          ← title, primary
Bagaimana harga satuan bergerak antar PO approved untuk bahan dan supplier yang sama.
```

### Report metadata

The third line is new and comes from **one shared map**, `analyticsReportQuestions` in `app.mjs` —
not from twelve scattered markup strings. `activateAnalyticsReport()` reads the map by nav id, so a
report renderer cannot silently change the business question the page advertises. Each entry states
the *question*, never a paraphrase of the title.

---

## 3. Navigation, request safety and reload

All three contracts are byte-for-byte the behaviour that shipped. Only the subtitle assignment was
added to `activateAnalyticsReport()`.

```js
function activateAnalyticsReport(navId,title,content) {
  activateWorkspace(navId);
  analyticsRequest++;
  analyticsReport=navId;
  $('analytics-eyebrow').textContent='Analitik · '+$(navId).textContent.trim();
  $('analytics-heading').textContent=title;
  $('analytics-subtitle').textContent=analyticsReportQuestions[navId]||'';
  $('analytics-body').innerHTML=content;
  return analyticsRequest;
}
```

- **One host, no fake page transition.** Because all twelve nav ids resolve to the same
  `sectionId`, `activateWorkspace()`'s `enteredSection!==sectionId` test is false when moving
  report → report, so `playEntryMotion()` does not replay. No renderer emits `workspace-page`,
  calls `activateWorkspace()` or touches the motion system. There is still exactly one
  `<section id="analytics…">` and one `#analytics-body` in the document.
- **Stale guard.** Every report still closes over `const request=activateAnalyticsReport(…)` and
  checks all four parts:
  `version===epoch && view==='analytics' && analyticsReport==='<id>' && request===analyticsRequest`.
- **Local pagination guards.** The ten paginated reports still keep `let offset=0,generation=0`,
  capture `const gen=generation`, and check `if(!current()||gen!==generation)return;` *before any
  paint*. An old response cannot repaint a newer filter run, another report, or a later page.
- **Filter memory.** `saveAnalyticsFilters(navId,form)` / `restoreAnalyticsFilters(navId,form)`
  unchanged, still per-report, still `FormData`-based. Every control stayed a named
  `<input>`/`<select>` **inside the one `<form>`** — that is load-bearing, because a control moved
  out of the form would silently drop out of both the query string and the saved values. Closing a
  child dialog does not reset filters; the only two writes to `analyticsFilters` are its
  declaration and the session reset.
- **Reload.** `reloadAnalytics()` is still the one mechanism and still has exactly one call site,
  in `formDialog()`'s success path. Capacity master edits still re-render the active report.
- **Session reset** now also clears `#analytics-subtitle`, alongside the body, heading and eyebrow.

### Initial execution semantics

Unchanged, and asserted. **Exactly two** of the twelve fetch on open, the same two as before:

- **Kapasitas produksi** — awaits `/api/work-centers` and `/api/products`, then `await load(true)`.
- **Kualitas produksi** — trailing `load(true)`.

The other ten still wait for the operator. They now show a **ready state** instead of a blank area:

> **Laporan belum dijalankan** — Atur periode dan filter, lalu tekan *Tampilkan …* untuk
> menjalankan laporan.

`analyticsReady()` calls `pageState(id,'empty',…)` and nothing else. It contains no `api.` call, no
`fetch(`, no timer and no frame — the ready state issues **zero** requests.

---

## 4. Filter architecture

The legacy `.filter-form` / `.form-grid` / `.form-actions` appearance is retired inside the twelve
reports (the rules stay in `style.css` for the surfaces that still render them — see §11).

Each report is **one `<form class="analytics-filters">` in two tiers**:

```
<form class="analytics-filters">
  <div class="command-bar">            ← the daily question
    <div class="command-filters">…</div>
    <label class="command-search">…</label>
    <div class="command-actions"><button class="action-primary">Tampilkan …</button></div>
  </div>
  <div class="utility-panel">          ← the assumptions (only when the report has them)
    <p class="utility-panel-title">Parameter &amp; asumsi</p>
    <div class="field-grid">…</div>
  </div>
</form>
```

Tier 1 carries period, the report's main status/scope selects and the search. Tier 2 carries the
*assumptions*: thresholds, lead time, review period, safety stock, batch multiple, record/stock
state, location.

**The assumptions panel is not a disclosure.** It has no `<details>` and nothing `hidden`. A
threshold is part of what the printed numbers *mean*; hiding it would hide the scope of the result
(§124). It is given a quieter surface, not a closed one — and it stays in the same `<form>`, so
`FormData`, the saved filter values and every parameter name are untouched.

Per-report split:

| Report | Command bar | Parameter & asumsi |
|---|---|---|
| WIP ageing | as_of, idle_days, status, stage, owner_id, query | — |
| Kapasitas | as_of, status, stage, work_center_id | horizon_days, warning_percent |
| Kualitas | as_of, assignment_type, status, query | window_days, warning_percent, change_threshold |
| Kinerja supplier | as_of, window_days, status, query | — |
| Harga bahan | as_of, window_days, status, query | — |
| Komitmen PO | as_of, due_soon_days, status, query | — |
| Forecast | as_of, window_days, horizon_days, marketplace, query | — |
| Rekomendasi stok | as_of, marketplace, query | window_days, lead_time_days, review_period_days, safety_stock_days, batch_multiple |
| Analisis ukuran | as_of, window_days, lookahead_days, marketplace, query | — |
| Analisis retur | as_of, window_days, marketplace, query | — |
| Dead stock | as_of, inactivity_days, marketplace, status, query | — |
| Audit adjustment | as_of, window_days, classification, source, query | quantity_threshold, percentage_threshold, repeat_threshold, record_status, stock_status, location |

### Accessibility of the controls

Every control keeps `name`, `type`, `min`, `max`, `step`, `maxlength` and `required` exactly as
shipped. Every control has a real label:

- `.command-filter` is a `<label>` wrapping a visible `<span>` label **and** an explicit
  `aria-label` with the same words;
- `.command-search` uses a `visually-hidden` label plus `aria-label`;
- `.field` uses `<span class="field-label">` inside the `<label>`.

No placeholder is the only label anywhere. The `query` control is emitted by one shared helper
(`analyticsSearchFilter`), which is where `name="query" maxlength="160"` is asserted.

---

## 5. Report grammar

Every report reads in the same order, because the operator's job is the same in all twelve:

```
report identity (host heading + question)
→ filters / assumptions
→ scope & limitation notes
→ key metrics (3–5)
→ period / scope metadata
→ truthful visual comparison, where the data supports one
→ records
→ supporting evidence inside each record
→ pagination
```

Shared builders in `app.mjs` — each writes exactly one A6.0 shape, so twelve renderers do not
restate the same markup twelve times and cannot drift apart:

`analyticsFilterControl` · `analyticsDateFilter` · `analyticsNumberFilter` · `analyticsTextFilter` ·
`analyticsSelectFilter` · `analyticsSearchFilter` · `analyticsParam` · `analyticsParamSelect` ·
`analyticsAssumptions` · `analyticsSubmit` · `analyticsFilterForm` · `analyticsNote` ·
`analyticsChip` · `analyticsMetrics` · `analyticsFacts` · `analyticsBars` · `analyticsSubhead` ·
`analyticsSubgroup` · `analyticsOpen` · `analyticsPager` · `analyticsPagerCount` ·
`analyticsReady` · `analyticsFail`

These are builders, not a parallel component library: each one emits A6.0 primitives
(`metric-strip`, `command-bar`, `status-chip`, `detail-grid`, `record-list`, `info-panel`,
`utility-panel`, `field`, `empty-state`, `progress-meter`, `pagination`) and nothing of its own.

### Metric strips

First-level metrics are capped at **3–5 cards**, and only actual report outputs become metrics.
Secondary quantities stay in `detail-grid` or in the record body. No report turned its summary into
eight to twelve cards, and no sentence became a metric.

### Density

The legacy `.material-event` inside `.material-event` inside `.material-event` is gone. Records live
in **one** `.record-list`, and a record with nested evidence is **one `<li class="analytics-record">`**
carrying only the list's divider — no border of its own, no radius, no shadow, no second background.
Nested evidence becomes typographic, not material:

```
.analytics-record
  ├ head: h3 + status chips
  ├ secondary line
  ├ comparison bars (where truthful)
  ├ detail-grid of facts
  ├ .analytics-subgroup  → h4 + .analytics-sublist (divider rows)
  └ .analytics-record-actions
```

Ten reports render their rows into `<ul id="…-results" class="record-list">`, which lets the
existing `appendRows()` append pages into one continuous list instead of producing one card per
page.

### States

`pageState()` — the same A6 state surface Produksi introduced — provides loading, ready, empty and
error for all twelve. Every state host kept its id, its `role="status"` and its `.state` class,
because `message()`, `pageState()` and the request lifecycle all address them by exactly those; the
legacy `.state` card is withdrawn for those thirteen ids in the A6.4 CSS block so a state does not
draw a second panel inside the first.

`analyticsFail()` renders `error-state` with the backend's own message and rebinds the retry button,
preserving the existing retry semantics. A pagination error never clears already-loaded rows —
`replaceChildren()` appears only on reset, never in a `catch`.

### Pagination

One presentation for all ten paginated reports: a `.pagination` row with a `workspace-meta` count
(`"25 dari 63 order"`) and the original `action-secondary` button with its original label and id.
Limits are untouched (25, `offset` progression), there is no infinite scroll, and no
`IntersectionObserver` or scroll listener exists anywhere in the reports.

Forecast and Rekomendasi stok keep `limit=100&offset=0` with **no** load-more at all; when
`total > items.length` they keep the honest instruction to narrow the search.

---

## 6. Visualisation primitives

A6.0 predates the real analytics migration, so A6.4 adds **one** small generic family to
`workspace-primitives.css` — nothing else:

```
.analytics-bar-list
.analytics-bar-row
.analytics-bar-label
.analytics-bar-value
.analytics-bar-track     (aria-hidden decoration)
.analytics-bar-fill      (+ -success / -warning / -danger / -neutral)
.analytics-bar-note
```

It earns its place on the terms the brief set:

- **Generic, not report-specific** — it says "these labelled quantities belong to one distribution,
  and here is their relative size", which is the one shape the sheet could not already express.
- **Reused by five reports** — WIP stage balances, return reasons, forecast periods, quality
  current-vs-previous, and a material's first-versus-latest price.
- **Semantic HTML is the source of truth** — it is a real `<dl>`; the label and the exact figure are
  real text that exist whether or not the bar renders. The track carries `aria-hidden="true"`.
- **No derived percentage is ever printed.** The width comes from an inline `--analytics-bar` the
  caller computes purely as geometry; the figure in `.analytics-bar-value` is always the value the
  API returned.
- **No chart library, no canvas, no axis, no legend, no tooltip, no animation, no RAF, no timer, no
  per-chart `backdrop-filter`.**

Capacity needed no new primitive: A6.0's `.progress-meter` already expresses "this much of that
much", which is exactly what a returned `utilization_percent` is.

### Where a visual was added, and where it was refused

| Report | Visual | Why |
|---|---|---|
| WIP ageing | stage balance bars | returned per-stage `quantity`, `orders`, `stalled_quantity` |
| Kapasitas | `progress-meter` | returned `utilization_percent`; `null` prints "Utilisasi belum terukur" and no replacement is computed |
| Kualitas | 3-bar comparison | returned previous vs current nonconforming rate, plus current first-pass yield |
| Harga bahan | 2-bar comparison | returned earliest vs latest unit price, same material, same supplier, same unit |
| Analisis retur | reason distribution | returned reason quantities |
| Forecast | 3-bar comparison | returned previous / recent net demand and forecast quantity, each label naming its own period length |
| Kinerja supplier | **none** | quantities are per material unit and must never share an axis (§54) |
| Komitmen PO, Rekomendasi stok, Analisis ukuran, Dead stock, Audit adjustment | **none** | the numbers read better as facts; a chart would have been decoration |

The WIP stage bars carry an explicit note that they are **current ledger balances, not cumulative
throughput**, and that the bars do not state conversion between stages — they are not a funnel.

The forecast comparison prints the period length in every label, so a horizon total cannot be
mistaken for an equal-length historical window.

---

## 7. Business truth preserved per report

No calculation, conclusion, score, grade, confidence, anomaly probability, AI insight, inferred
cause or new risk classification was introduced. Every sentence below is still rendered.

**1 · WIP ageing** — Age runs from the latest production movement, or from order creation when there
is none; stage position uses the current ledger balance. The summary's signal is labelled
**"Sinyal hambatan terbesar"** and never "bottleneck", with the standing note that capacity targets
are not part of this report. All record fields kept: reference, title, owner, due date, flags, active
/ planned / in-process quantities, inactive days, open issue count, rework quantity, positions,
latest activity date, activity basis, activity-after-as_of, overdue days, products, open issues,
plus **Buka order**.

**2 · Kapasitas produksi** — Summary keeps `work_centers`, `attention_work_centers`,
`at_risk_orders`, `required_minutes`, `available_minutes`, `as_of`, `horizon_end`. The estimate
disclaimer is intact: default working days Monday–Friday, latest calendar override applies per date,
figures are standard estimates and **not a production schedule promise**. Coverage gaps stay
first-class in an `attention-note-critical` plus a divider list — `missing_standard_quantity`,
`order_reference`, `sku`, `stage`, `quantity`, `kind` (`inactive_work_center` / missing routing
standard) — and are not hidden to make the page look cleaner. Per work centre: code, name, stage,
status, utilisation, required / available / remaining / overload minutes, order count, at-risk count,
calendar days and orders, each embedded order keeping `required_minutes`,
`available_minutes_by_due`, `at_risk`, `capacity_shortfall_minutes`, products, `minutes_per_unit` and
**Buka order**.

**3 · Kualitas produksi** — Active final QC only; corrected records excluded; first-pass yield from
initial inspections only, so one unit re-inspected after rework is not counted twice. Reinspection
stays a separate block with all five returned figures. Trend words unchanged: Memburuk / Membaik /
Stabil / Baseline baru, with no predictive language and no claim of statistical significance. Defect
types, responsible sources, SKU breakdown and recent final-QC records all retained, with
**Buka final QC …**.

**4 · Kinerja supplier** — PO grouped by supplier and expected arrival; first *active* arrival
measures initial timeliness. **Material quantities are never totalled across units**:
`ordered_by_unit`, `received_by_unit` and `quality_by_unit` stay separate lists, one divider row per
unit, and no reduction over them exists in the code. No supplier score. PO links keep their existing
`data-action`, and Purchase Order internals were not touched.

**5 · Harga bahan** — Comparison is between approved POs for the *same material and the same
supplier*; suppliers are never merged into one trend. The axis is the PO **recorded** date, not the
expected arrival date. The summary's existing meaning — the matching search universe *before* status
filtering — is stated on the page and unchanged. History keeps reference, unit price, recorded date,
expected date and **Buka PO**.

**6 · Komitmen PO** — Open commitment is approved active PO value not yet represented by usable
receipt; pending, rejected, cancelled and closed remain excluded. Payment wording is unchanged:
approved means approved / ready in the workflow and **does not prove a bank transfer**. The word
"Paid" appears nowhere. `due_soon_end`, all three payment figures and the material lines are kept.

**7 · Forecast demand** — Formula and wording untouched: two equal historical windows, recent 70% /
previous 30%, active returns reducing demand on the original shipment date. The limitation note is
prominent, above the results: the forecast does **not** account for available stock, incoming stock,
lead time, MOQ or safety stock.

**8 · Rekomendasi stok** — All six stockout-risk states stay distinct (`out_of_stock`,
`stockout_before_replenishment`, `below_safety_stock`, `covered`, `insufficient_history`,
`no_demand`). Material recommendations keep every quantity in its own unit and never add
incompatible units. BOM coverage gaps are explicit — a missing BOM is not zero material demand. The
limitation is stated: the purchase recommendation subtracts material stock, open PR and open PO, but
price, supplier, material MOQ and production capacity do not determine the result.

**9 · Analisis ukuran** — Sizes are compared only within the same product and colour. The
marketplace filter constrains **demand only**; stock is total internal inventory, and the page says
so. "Pemimpin demand konsisten" keeps its definition — first by net demand in *both* periods — and
is explicitly not evidence of a historical stockout.

**10 · Analisis retur** — Cohort is shipments inside the period; returns are active returns through
the report date, grouped by SKU, size, marketplace and recorded reason. The four groups keep their
exact composition: Sizing = too small + too big, Product page = wrong item + colour mismatch, Defect,
Other. All six per-reason quantities are printed. The distribution bars take their geometry directly
from those quantities and imply no causal certainty.

**11 · Dead stock** — Candidate definition unchanged: sellable stock available **and** oldest lot age
at or beyond the threshold **and** no net demand in the period. The marketplace filter constrains
demand only; inventory and lot age are the internal total position. **No inventory valuation** —
there is no rupiah value, no potential loss and no cash-trapped figure anywhere in the report,
because per-lot valuation is unavailable.

**12 · Audit adjustment** — The page states prominently that this is an **audit signal, not proof of
stock loss, fraud or error**. Classifications stay Risiko tinggi / Perlu tinjauan / Normal, and all
four flags keep their wording without becoming accusations. Every record field is retained, with
**Buka adjustment**.

---

## 8. Capacity admin workflows

A6.4 also owns the three master forms embedded directly in the capacity report's workflow.

**Permissions.** The master block renders only when `user.role==='admin'`, and
`capacity-standard-open` / `capacity-calendar-open` are bound only in that branch. The gate is the
same JS comparison it always was — nothing is merely hidden with CSS, so a non-admin gains no
control. `Tambah work center`, `Ubah`, `Atur standar waktu` and `Atur kapasitas tanggal` are absent
for every other role.

**Presentation.** The master list became a `record-list` (`#capacity-center-master`, with its own
scroll so it cannot push the plan off the first viewport), the two tool groups became
`utility-panel` + `field-grid` + `field-actions`, and the three forms emit A6 `.field` markup through
three small builders — `capacityField`, `capacitySelect`, `capacityFact` — plus the shared
`reasonField`. The shared `formDialog()` infrastructure was **not** redesigned; the fields are handed
to it exactly as A6.2 and A6.3 do, so no unrelated form in the product is touched.

**Rules, unchanged.**

- *Work center create* — `code` max 40, `name` max 160, stage select, `daily_minutes` 1–100000
  default 480, `reason` max 1000.
- *Work center edit* — `name`, `daily_minutes`, `active`, `reason`, `expected_revision`. Stage and
  code remain immutable through this workflow; the edit branch never offers them.
- *Routing standard* — product, stage, only **active** work centres matching the stage,
  `minutes_per_unit` min 0.001 / max 100000 / step 0.001, `expected_revision`, `reason`; the existing
  "add an active work center first" notification is preserved.
- *Calendar override* — `work_date` readonly, `available_minutes` 0–100000, `expected_revision`,
  `reason`, and the preserved meaning that **0 = day off** and a higher value may represent overtime.

A successful child save still reloads the current report through `reloadAnalytics()`.

---

## 9. Responsive, accessibility, dark mode, performance

**1440** — Each report's first viewport reaches the actual analysis: heading and question, the
command bar, the assumptions panel, the notes, the metric strip and the beginning of the records. The
filter surface is one bar plus at most two rows of compact fields; no report's filters occupy the
viewport.

**1024 / 768** — Filters wrap deliberately (A6.0's `.command-bar` already wraps); metric strips
reflow on their own `auto-fit` track. Nothing creates document horizontal overflow. At 980px the
product's own 44px touch floor is restored for analytics buttons, command filters and assumption
fields, because A6's compact control height out-specifies the global rule.

**390 / 320** — Records read as columns: `.analytics-record-head` stops trying to put a reference and
its chip on one line, and the record's padding tightens. The quantity-bar row collapses to one column
(label, figure, bar) so a tabular figure is never pushed off the row. Title, critical filters, the run
button, the summary and the records stay in that priority order; the assumptions stack rather than
disappear.

**320 @ 200% text** — Exercised in the browser module as a document-level overflow assertion, on the
most parameter-heavy report. No single-letter SKU wrapping, no clipped currency, no overlapping
metrics, no unreachable filter, no truncated status word.

**Dark mode** — Full coverage for all twelve, entirely through the existing A6 material hierarchy:
the reports introduce no colour of their own, only `--workspace-surface`, `--workspace-secondary`,
`--workspace-divider`, `--ink`/`--ink-2`/`--muted` and the semantic tone tokens. There are no flat
black slabs because there is no new surface — a record is a list row, and a subsection is a rule.

**Reduced transparency** — Inherited from A6.0's single `@supports` gate. A6.4 adds no material.

**Forced colors** — Every analytical meaning survives without colour. Status is always a word inside
a `status-chip` with a `status-dot`; trend, risk and classification are words, never colour alone.
The quantity bar keeps an outline plus a `Highlight` fill and is never the only channel, because its
label and exact figure are real text.

**Reduced motion** — Nothing new moves. No chart animation, no bars growing from zero, no count-up
metrics, no stagger. Only the existing workspace entry motion, which report → report switching does
not replay.

**Performance** — No polling, no `setInterval`, no new `requestAnimationFrame`, no chart library, no
API fan-out to decorate a report. Frame and timer budget identical to the baseline:
`requestAnimationFrame` 6, `cancelAnimationFrame` 4, `setTimeout` 7, `setInterval` 0. The only inline
styles in the twelve renderers are `--analytics-bar` and `--progress-value`, both geometry.

---

## 10. Migration contract

`tests/test_apple27_modern_workspace_foundation_contract.py` is where A6.0's containment promise
lives, and A6.4 widened it **narrowly and by enumeration**:

- `MIGRATED_SECTIONS` gains `analytics-view`.
- `MIGRATED_RENDERERS` gains the twenty-two shared analytics builders, the twelve report renderers,
  and the three Capacity master forms plus their three field builders.

Everything Analitik merely *links to* — Purchase Order detail, Final QC detail, finished-goods
adjustment detail, production order detail — is deliberately **not** on the list and still fails the
contract if it starts emitting A6 markup. Those belong to other workflows and to A6.5–A6.7; their
entry points from analytics are preserved untouched.

The A6.3 CSS slice is now bounded above by the A6.4 marker
(`#analytics-view{max-width:1360px`), the same deliberate act A6.2 performed when A6.3 arrived.

---

## 11. Remaining legacy surfaces

Genuinely not modernised yet, and not in A6.4's scope:

- **Tanya Beeloft** (`#ai-view`) and **Integrasi** (`#integrations-view`) — A6.5
- **Aktivitas** (`#activity-view`), **Audit** (`#audit-view`), **Backup** (`#backup-view`) — A6.6
- **Purchase requests** (`#purchase-requests-view`), **Marketing budgets**
  (`#marketing-budgets-view`), **Approvals** (`#approvals-view`) — A6.7
- The production, warehouse, purchasing and marketplace child dialogs still rendering
  `.material-event`, `.requirement-values`, `.status-label`, `.form-info` and `.history-item`

**Command Center is modern and FROZEN.** It is not legacy.

Legacy CSS retained on purpose, because other surfaces still render it: `.filter-form` (Aktivitas'
audit filter), `.form-grid` / `.form-actions` / `.form-info` (every `formDialog()`),
`.material-event`, `.requirement-values`, `.status-label`, `.hint`, `.history-item`, `.page-heading`,
`.eyebrow`, `.state{`, `.product-list` (the Master SKU catalog host).

Two selectors became fully inert with this phase — `.issue-heading` and `.product-item` — and are
left in place rather than removed, following A6.1's documented rule that inert legacy CSS is deleted
by the phase that can prove the deletion safe on its own. Proving it needs the A6.5–A6.7 sweep this
phase is not allowed to start.

## 12. Deferred to A6.8

Known cross-product polish remains deferred and was not started here:

- cross-phase typographic and spacing reconciliation between A6.1–A6.4
- the shared `formDialog()` chrome itself (`.form-info`, the fieldset grid, the action row)
- removing the now-inert legacy selectors once every consumer is migrated
- a shared pagination component, if A6.5–A6.7 turn out to want the same row
- any further refinement of the five quantity-bar consumers once all twelve reports have been seen
  side by side by a human reviewer
