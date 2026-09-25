# Apple-27 · A6.1 — Produksi modern workspace

A6.1 migrates the real Produksi workspace — the production board, the production order detail and
the create-order form — onto the shared A6.0 inner-workspace primitives. It is the first
production migration onto `beeloft/static/workspace-primitives.css`, and it is deliberately the
phase that proves A6.0 is reusable rather than decorative.

Version 0.107.0. Schema stays at `PRAGMA user_version = 55`; no migration, no new endpoint, no
new API field. The OpenAPI contract diff is `info.version` only.

## Baseline

| | |
|---|---|
| Baseline commit | `50a9b8bfcc0c376bc8f3f4a74b59818c6a72c3a2` (`origin/main`) |
| Baseline CI | run `36089390659` (CI #159), exact-SHA push build, conclusion `success` |
| Branch | `ui/apple27-a6-1-production-workspace` |
| Predecessor | A6.0 merged through PR #99, human visual approved |
| Frozen | A5.2 shell, A5.3 navigation lens, A3 spring constants |
| Version | 0.106.0 → 0.107.0 |
| Schema | 55 (unchanged) |

A6.1 started only after the exact-SHA CI build for the baseline commit had completed green. The
phase touches no backend code.

## What Produksi is, and is not

Produksi is workflow-centric, not a second Command Center. Its information hierarchy is

    production context → operational status → find/filter orders → work the order → inspect → act

so the order list is the visual centre of the page and the metric strip is deliberately the
shortest band on it. There are no executive hero charts, no marketplace dashboard composition, no
operational-health grammar, no decorative analytics and no overview modules. Every number on the
page comes from a field `GET /api/production-board` or `GET /api/orders/{id}` already returned.

## A6.0 primitives consumed

Layout and identity: `workspace-page`, `workspace-heading`, `workspace-heading-copy`,
`workspace-eyebrow`, `workspace-title`, `workspace-subtitle`, `workspace-actions`,
`workspace-section-title`, `workspace-meta`.

Data and status: `metric-strip`, `metric-card` (+ `-info` / `-warning` / `-danger`), `metric-icon`,
`metric-label`, `metric-value`, `data-surface`, `data-header`, `data-row`, `data-cell`,
`data-cell-tight`, `data-primary`, `data-secondary`, `data-meta`, `status-chip`
(+ `-info` / `-success` / `-warning`), `status-dot`, `progress-meter`.

Controls: `command-bar`, `command-search`, `command-filters`, `command-filter`, `command-actions`,
`action-primary`, `action-secondary`, `action-quiet`, `field-grid`-family (`field`, `field-label`,
`field-help`, `field-actions`, `field-wide`).

Panels, states and records: `info-panel`, `utility-panel`, `attention-note` (+ `-copy`, `-title`,
`-reason`, `-critical`), `empty-state`, `error-state`, `loading-state`, `record-list`,
`record-row` (+ `-copy`, `-aside`), `timeline`, `timeline-item` (+ `-warning`), `timeline-time`,
`timeline-event`, `timeline-actor`, `timeline-detail`, `detail-grid`, `detail-field`.

### Generic extensions added to A6.0

A6.1 extended the shared stylesheet rather than starting a parallel component library. Every
addition is generic and unprefixed — none is named after production — and each exists because a
real gap appeared while composing a real page:

| Primitive | Why |
|---|---|
| `workspace-subhead` | A section title with a quiet piece of metadata opposite it (here: "Order produksi" + the freshness stamp). |
| `progress-native` | The A6 track drawn on a native `<progress>`. The div-based `progress-track`/`progress-fill` pair reads its width from a custom property and cannot be driven by a script setting `.value`, which is exactly what the existing settle animation does. |
| `progress-meter-stack`, `progress-legend` | The stacked meter — legend above, track below — preferred where the numbers are the point and the bar is the confirmation. Three items on one line is what makes a measured table cell truncate first. |
| `utility-panel-title` | The caption of an existing `utility-panel`, at metadata weight so a control cluster never outranks the data. |
| `action-row` | A left-aligned wrapping row of actions. `workspace-actions` pushes right; `field-actions` belongs to a form. |
| `panel-grid` | Several panels side by side, `align-items:start` so a four-item group does not inherit a ten-item group's height. |
| `detail-grid-compact` | The same grid for many short numeric facts. At 180px a set of eight two-word labels wraps and reads as a table that lost its header. |
| `metric-unit` | The unit inside `metric-value`, so the figure and its scale are one string for a screen reader. |
| `attention-note-success` | The cleared state, so the absence of a warning is not the absence of a component. |
| `chip-row` | A cell carrying a status plus a qualifier. Two `inline-flex`, `nowrap` chips separated by whitespace wrap with no vertical rhythm at all. |

Two corrections were also made to existing A6.0 rules:

- `metric-value` gained `margin:0`, which is what allows the metric strip to be marked up as a
  real `<dl>` (a `<dd>` arrives with a 40px indent).
- `command-search input` and `command-filter > select|input` gained `margin:0`. This is a latent
  A6.0 bug that A6.1 surfaced: both shells are real `<label>` elements, and the foundation spaces
  a control that is a label's direct child (`label>input{margin-top:.4rem}`) for stacked forms.
  Inside a single-line control shell that margin pushed the control off the shared baseline and
  made the command bar wrap a row early.
- `attention-note` gained `justify-content:flex-start` and `text-align:left`, because the
  open-issue summary is an attention note that happens to be a `<button>`.

## Board hierarchy

    Produksi
    Pantau order, progres, kendala, dan output produksi.
                                          Muat ulang   + Buat order produksi

    [ Order aktif ] [ Lewat target ] [ Dalam proses ] [ Perlu rework ]

    [ open-issue attention surface — raised or cleared ]

    [ 🔍 Referensi, produk, atau SKU ][ Cari order ][ Status ▾ ][ PIC ▾ ][ Posisi ▾ ][ Reset filter ]
    ⓘ Posisi barang menampilkan order yang masih memiliki saldo di tahap tersebut. …

    Order produksi                                             Diperbarui 14.32
    ┌───────────────────────────────────────────────────────────────────────────┐
    │ Order / produk │ PIC │ Target selesai │ Progress │ Status │              │
    ├───────────────────────────────────────────────────────────────────────────┤
    │ …                                                                         │
    └───────────────────────────────────────────────────────────────────────────┘
    1–25 dari 41 order                          Sebelumnya   Berikutnya

The heading is `Produksi` / `Pantau order, progres, kendala, dan output produksi.`, replacing
`Papan produksi` / `Yang sedang dikerjakan.`. `Buat order produksi` is still hidden in markup and
revealed by the same single line of JavaScript (`$('new-order').hidden = me.role!=='admin'`); no
permission is derived in CSS.

## Metric mapping

| Card | Source | Unit | Tone |
|---|---|---|---|
| Order aktif | `summary.active` | order | accent (always) |
| Lewat target | `summary.overdue` | order | danger **only when > 0**, otherwise neutral |
| Dalam proses | `summary.in_progress` | pcs | accent (always) |
| Perlu rework | `summary.rework` | pcs | warning **only when > 0**, otherwise neutral |

The tint is on the icon tile only; every card body stays neutral. That is deliberate: the old
`.production-wip` card had a filled background and a blue border, which read as a selected tab.
These are metrics, not tabs, and `production-wip` is gone from the product.

The strip is global, not page-scoped — filtering the board leaves all four numbers unchanged,
which the browser module asserts directly. There is no chart and no comparison copy in the strip,
and `metric-card` is capped at 104px so the band stays shorter than the data.

## Filter mapping

| Control | id | Accessible name | Query parameter | Values |
|---|---|---|---|---|
| Search | `#search` | `Cari order atau SKU` | `q` | free text, `maxlength=160` |
| Submit | `.production-search` | `Cari order` | — | `offset = 0`, then `loadBoard()` |
| Status | `#status` | `Status` | `status` | `all` `active` `overdue` `blocked` `closed` |
| PIC | `#board-owner` | `PIC order` | `owner_id` | `''` + owner ids |
| Posisi | `#board-stage` | `Posisi barang` | `stage` | `all` `planned` `cutting` `sewing` `finishing` `qc` `rework` `reject` `warehouse` |
| Reset | `#reset-board` | `Reset filter` | — | clears all four, `offset = 0` |

Nothing about the query moved: `q`, `status`, `owner_id`, `stage`, `limit=25`, `offset`, in that
order, from the same expression as before. Search still submits on the button and on Enter and
**never** queries per keystroke — there is no debounce and no `input` handler. Changing any select
is still immediate and still returns to the first page.

The `#board-owner` fallback is intact: an owner selected in the rendered query that is no longer
in the latest owners list is re-appended with its previous label, or `PIC tidak lagi memiliki
order`, and the selection is never cleared during the rebuild.

`#production-filter-hint` keeps both sentences verbatim and is still `aria-describedby` for
`#board-stage`. After the visual review its `info-panel` surface is withdrawn and it reads as a
caption at metadata size — **18px** against the panel's ~44px. Size and position already say "read
me after the command bar"; a filled panel saying it as well was costing the order list its place
in the first viewport. No word and no relationship was removed.

There is exactly one status control. No segmented filter or chip row was added: A6.0 ships one,
but a second control driving the same state would be duplication, not modernisation.

## Order table semantics

`#order-list` **is** the `data-surface` — the page's one near-opaque primary surface — and it
contains a real `<table>`:

| Column | Content |
|---|---|
| Order / produk | `reference` (eyebrow) + `title` inside the detail button, then `N SKU · target N pcs` |
| PIC | `owner_name`, plain text, no fabricated avatar |
| Target selesai | `due_date` |
| Progress | legend + native meter + percentage |
| Status | status chip + optional issue chip |
| *(unlabelled)* | a decorative trailing chevron |

Native semantics only: `<thead class="data-header">`, `<th scope="col">` ×6, `<tr>`, `<td>`. No
`role="table"`, `role="row"`, `role="cell"` or `role="columnheader"` anywhere.

**Each row exposes exactly one button** — the title/reference button carrying
`data-action="detail"`. That is load-bearing rather than aesthetic: around twenty acceptance
modules open an order with `getByRole('button', {name: /REFERENCE/})`, so a second control whose
accessible name contained the reference would make every one of them ambiguous. The sixth column's
chevron is therefore an affordance, not a control; the title button remains the keyboard-reachable
detail trigger, so row navigation is never mouse-only.

`.order-row`, `.order-title` and `.reference` are kept as compatibility classes because
`playProgressSettle()`, the M4 motion module and those acceptance modules all address them.

## Progress meaning

Unchanged and explicit: **warehouse quantity ÷ production target**.

    80 / 500 pcs                                    16%
    [████                                              ]

- value `order.totals.warehouse`, maximum `order.target_quantity`;
- accessible label still `Jumlah diterima gudang <reference>`;
- never relabelled as production completion.

The element is a native `<progress class="progress-native" data-order="…">` because
`playProgressSettle()` interpolates `.value`. That animation is unchanged: it still only animates
values that actually changed, still compares against what is on screen (so a first load does not
count up from zero), still applies the target immediately under reduced motion, and is still the
only progress animation in the application. No new timer or animation frame was added anywhere —
the pinned budget (`requestAnimationFrame` ×6, `cancelAnimationFrame` ×4, `setTimeout` ×7,
`setInterval` ×0) is byte-identical.

## Status mapping

| Condition | Label | Chip |
|---|---|---|
| `overdue` (wins over any status) | Lewat target | `status-chip-danger` |
| `status === 'completed'` | Selesai | `status-chip-success` |
| `status === 'closed_with_reject'` | Ditutup · ada reject | `status-chip-warning` |
| otherwise | Dalam produksi | `status-chip-info` |
| `open_issues > 0` | `N kendala` visible, `N kendala terbuka` announced | `status-chip-warning` |

Order of evaluation, wording and meaning are unchanged. The one presentation-level refinement:
`closed_with_reject` moved from the same green as a clean completion to a warning tone. The label
already said `ada reject`; the tone now agrees with it. Every chip carries a `status-dot`, so
status never depends on colour alone — including under forced colours.

The issue indicator is a compact companion rather than a second full-size badge. Its visible text
is shortened to `N kendala` so the status column does not widen on every row, with ` terbuka` in a
visually hidden span so nothing is lost to a screen reader.

## Issues attention surface

`#issues-summary` keeps its id, its `has-issues` class and its exact behaviour in both states: one
click resets the board filters, selects `status = blocked`, and reloads. It is an `attention-note`:

- `open_issues > 0` → `attention-note-critical`, `#i-alert-triangle`, reason `Lihat order terkait`,
  trailing arrow, full width. **Prominent, and deliberately unchanged.**
- `open_issues === 0` → `attention-note-success`, `#i-check-circle`, reason
  `Semua order berjalan tanpa kendala terbuka`. **Compact.**

The two states carry different weights of message, so the visual review asked for different
weights of treatment. An all-clear should be confirmable at a glance and then ignored, and a
full-width two-line green-edged panel announcing that nothing is wrong was taking vertical space
from the data. The cleared state is therefore a single shrink-wrapped row — icon, count, reason,
separated by a drawn `·` — at **30px** against the raised state's ~62px:

    ✓ 0 kendala terbuka · Semua order berjalan tanpa kendala terbuka

The green stays in the tint and the check rather than in a callout edge (`border-color` falls back
to `--workspace-edge`). Only layout changes: the same element, the same DOM, the same click
semantics and the same state classes the lifecycle already toggles — which is why the browser
module asserts the cleared note is still clickable and still produces `status=blocked`.

The separator is a `::before`, so it never enters the text content or the accessible name. On a
phone the two runs stack and the separator is withdrawn rather than left to orphan at the start of
a wrapped line.

Following A6.0's grammar, the copy stays at the readable ink in both states and the semantic lives
in the tint, the border and the leading icon — which is the channel the acceptance module compares.

## Empty, error and refresh states

`#board-message` keeps its id, its `role="status"` and its `.state` class, because the request
lifecycle, `fail()` and the M4 motion contract all address it by exactly those (M4 asserts its
`className` returns to exactly `state` after the empty-state fade). What changed is what renders
*inside* it: a new `pageState()` helper composes the A6 `loading-state` / `empty-state` /
`error-state` shells, and the legacy `.state` card is withdrawn for this host so no state draws a
second bordered panel around the first.

| State | Rendering |
|---|---|
| Load from scratch | `loading-state`, `Memuat posisi produksi…`, list hidden |
| Refresh with rows on screen | rows kept, `aria-busy`, dimmed to the documented M4 value (0.78) |
| Filtered miss | `empty-state`, `Tidak ada order yang cocok.`, copy points at Reset filter, **no action button** |
| Genuinely empty, admin | `empty-state`, `Belum ada order.`, real action `Buat order produksi pertama` |
| Genuinely empty, non-admin | `empty-state`, `Belum ada order produksi.`, no action |
| Failure | `error-state` carrying the real message, `.error` class, existing rows kept, issue count and freshness stamp withdrawn |

The two empty states stay semantically distinct, and the filtered one deliberately carries no
button: nothing is missing, and a second control named `Reset filter` would be ambiguous beside
the one already in the command bar a row above.

A `401` still routes through the existing authentication failure path (`fail()` → logout → login
message); only other failures are drawn as an A6 error surface. A refresh failure never presents
stale rows as current — the rows stay readable, but the error appears immediately, undimmed, and
the stale issue count and timestamp are cleared.

`markRefreshing('order-list')` / `settleRefreshing()` are untouched, so existing rows remain
visible while a valid refresh is in flight, the table is never blanked, and no skeleton delay was
introduced.

## Stale-response behaviour

Every guard is preserved verbatim:

- board — `epoch`, `++boardRequest`, `view === 'board'`;
- detail — `epoch`, `++detailRequest`, `view === 'detail'`;
- history and issues pagination — `epoch`, `detailRequest`.

`boardQuery` still records the query that was actually *rendered* rather than the one requested.
That distinction is intentional and is what lets a retry of a previously failed query still read
as a replacement and keep its motion. The browser module holds one board request open, lets a
later one land first, then releases the first and asserts that neither the table nor the metric
strip was repainted by it.

## Pagination

`limit = 25`. Previous is `max(0, offset - 25)`, next is `offset + 25`, and the count is still
`X–Y dari N order`. Only the controls were restyled. No infinite scrolling.

## Detail hierarchy

Revised after human visual review. The order of the page is the order of the questions an operator
actually asks — *what is this order, where is the stock right now, what are the exceptions, which
SKU, and only then what can I do about it*:

    ← Semua order
    DEMO-PROD-001
    CONTOH - Produksi internal 500 pcs                    Muat ulang order

    Penanggung jawab   Target selesai   Target produksi   Status
    ───────────────────────────────────────────────────────────────
    Posisi barang sekarang                 Jumlah seluruh posisi: 500 pcs
      [ Belum cutting  Cutting  Sewing  Finishing  QC  Gudang ]
      [ Saldo pengecualian — Rework, Reject ]
      ⓘ balances, not cumulative progress
    Rincian per SKU
    Tindakan order
      [ Order & perencanaan ] [ Alur produksi ] [ Fulfilment & marketplace ]
    Kendala produksi · N terbuka
    Riwayat perpindahan

The first review found the action catalogue sitting directly under the summary, which pushed
`Posisi barang sekarang` to roughly y≈680 and left SKU information off the first viewport
entirely. Current position and SKU detail now both precede it; at 1440×1000 the first viewport
reaches real SKU balances. Both the DOM order and the measured first viewport are asserted.

Reference is the eyebrow, title is the `<h1>`. `← Semua order` is shrink-wrapped and
left-aligned with the order identity directly above it — it previously stretched to full width, and
the foundation's `button{justify-content:center}` parked its label near the horizontal centre of
the page, where it read as a control belonging to nothing. Behaviour is untouched: back still calls
`showBoard()` and returns focus to `#search`.

The four metadata facts — `Penanggung jawab`, `Target selesai`, `Target produksi`, `Status` — are a
`detail-grid` of four `detail-field`s, with nothing added.

`Tindakan order` is the one piece of new copy in the phase. It exists because the action groups
moved below the operational data and a section that low needs a label to be navigable rather than
appearing to float; it is also the `aria-labelledby` target for the section.

## Action grouping and weight

The old detail exposed a flat list of 27 buttons. A6.1 recomposes the **same** actions into three
`utility-panel` groups inside one `panel-grid`. Not one action was removed and not one
`data-action` changed.

The first review then found that three groups of equally loud white capsules was still a button
wall. So the actions now carry **weight**, and the discriminator is what an action *means*, not
taste:

| Weight | Meaning | Rendering | Count |
|---|---|---|---|
| `command` | Immediately changes something | Compact `action-secondary` button | 3 |
| `row` | Opens a record, a history or a list | `record-row` on a real `<button>`: label, then a trailing chevron | 24 |

The three commands are `edit-order`, `new-production-change-request` and `issue-material` — the only
actions on the page that act rather than navigate. Everything else is a row, including every action
the review named. Rows use A6.0's own `record-row` grammar; only the `<button>` element resets live
in the contained A6.1 block, which is the same containment already used for `#issues-summary`. The
rows are deliberately denser than a data row (36px, lifted to 44px under the narrow-width touch
floor) because a utility list is navigation, not content.

No popover or menu architecture was introduced — every action remains directly visible and
directly reachable, and each row's accessible name is still exactly its label, which is what the
fourteen child-dialog modules address it by.

| Group | Actions |
|---|---|
| Order & perencanaan | `edit-order`, `new-production-change-request`, `production-change-requests`, `order-changes`, `requirements`, `reservations`, `consumption`, `production-cost`, `contribution-margin`, `order-purchases` |
| Alur produksi | `cutting-runs`, `bundles`, `sewing-jobs`, `finishing-records`, `final-qc-records`, `rework-completions`, `finished-goods`, `warehouse`, `issue-material`, `order-materials` |
| Fulfilment & marketplace | `marketplace-reservations`, `marketplace-picks`, `marketplace-packs`, `marketplace-shipments`, `marketplace-returns`, `finished-goods-adjustments`, `finished-goods-stock-counts` |

Within a group, actions that do work are `action-secondary` and actions that only open a history
or a read-only view are `action-quiet`, so the page finally has a hierarchy it did not have
before. All actions stay visible; no popover or menu architecture was introduced, and nothing is
hidden behind a control that is not fully accessible.

Visibility is unchanged and still lives in JavaScript: `admin` gates `edit-order`, and
`writer` (`role !== 'viewer'`) gates `new-production-change-request` and `issue-material` — the
same two checks as before, evaluated in the same place.

## Stage-balance semantics

The stage read-out is a set of **current balances**, and the page now says so explicitly.

- Six flow positions (`planned`, `cutting`, `sewing`, `finishing`, `qc`, `warehouse`) in a
  `detail-grid-compact`, each with its label and its exact quantity in pcs.
- `rework` and `reject` in a separate panel titled `Saldo pengecualian`, so exception balances stay
  visually distinct.
- `Jumlah seluruh posisi: N pcs` retained for reconciliation.
- An `info-panel` states: *"Angka di atas adalah saldo yang sedang berada di tiap posisi saat ini,
  bukan jumlah yang sudah selesai melewatinya. Deretan ini karena itu tidak berjumlah maju dari
  kiri ke kanan."*

There are no connectors, no `01/02/03` numbering, no animated flow and nothing that implies the
values accumulate left to right. The old `.stage-number` is gone.

Following the visual review, a position holding **zero** is dimmed to the muted ink so the
positions actually holding stock read first. This is emphasis only: every label and every exact
quantity is still rendered, nothing is hidden, filtered or rounded away, and the contract test
asserts the rule is a colour change and nothing more.

## SKU treatment

Each SKU line is a `utility-panel`: `SKU` as `data-primary`, then
`name · colour / size · target N pcs` as `data-secondary`, then all eight balances in a
`detail-grid-compact` with explicit labels and exact quantities. Balances are data, not a chart.
For a non-viewer, `Catat perpindahan` and `Catat kendala` remain on the record. At narrow widths
the compact grid keeps wrapping in columns rather than collapsing to one balance per row — eight
stacked rows would be eight screens of scrolling for data whose value is being comparable at a
glance.

## Issues and history treatment

`Kendala produksi · N terbuka` is a `record-list` of `record-row`s, newest first as the subtitle
states. Every field is still rendered: SKU, stage, open/resolved chip, description, PIC with its
inactive-account marker, creator, created timestamp, and — when resolved — the resolution, the
resolver and the resolution timestamp. `Selesaikan kendala` remains for the roles that had it.
`Muat kendala sebelumnya` and its 100-row cursor behaviour are unchanged.

`Riwayat perpindahan` is an `<ol class="timeline">`, oldest recording order as the subtitle
states. Timestamp, quantity, from-stage → to-stage, SKU, actor, reason, reversal state, every
linked cutting/sewing/finishing/QC/rework record and the `Koreksi` eligibility rule are all
preserved. Reversing and reversed records additionally get a `timeline-item-warning` marker so
exceptions are visible without reading every line. `Muat riwayat berikutnya` and its 100-row
offset behaviour are unchanged.

`.reason` is deliberately retained on both, because its `white-space:pre-wrap` is what keeps a
multi-line operator note readable.

## Create-order presentation

Presentation only, inside the existing modal architecture — A6.1 introduces no sheets and does not
touch the shared `formDialog()` shell used by every other dialog.

- `Referensi order`, `Nama order`, `Penanggung jawab`, `Target selesai` are `field` /
  `field-label` pairs with their `name` attributes, `required` and `maxlength="160"` unchanged.
- `Produk yang dikerjakan` gains a `field-help` line stating the one-row-per-SKU and 100-row rules.
- A line stays `SKU select | quantity | quiet remove` on desktop and wraps deliberately on mobile.
  Removal is `action-quiet`, not red: removing an unsaved line is not destructive enough for the
  shared destructive treatment.
- With no products, the dialog renders an `empty-state` with the real `Tambah SKU` action instead
  of an unusable form.

Every business rule is untouched: at least one product must exist; only active non-viewer users
appear as owners; at least one SKU line; maximum 100 lines; quantity 1…1,000,000,000; duplicate
SKU rows rejected with the same message; the last remaining line cannot be removed;
`POST /api/orders` through the same `formDialog()`; the same idempotency and pending-write
behaviour; `guardPending()`; `modalVersion` / `dialogVersion` stale protection. `.line-input` is
retained because the collector finds the rows by it.

## Permissions

No permission behaviour changed, and none is expressed in CSS.

| Role | Board | Detail |
|---|---|---|
| admin | `Buat order produksi` visible | all actions, including `edit-order` and `Koreksi` |
| operator | create hidden | operational actions kept (`move`, `new-issue`, `issue-material`, `resolve-issue`); no `edit-order` |
| viewer | create hidden | three groups still render, but zero write actions; read-only views kept |

The browser module asserts all three explicitly, including that a viewer gains no write action
from the redesign.

## Light and dark

Produksi belongs to the approved A5.2 shell. The canvas stays environment-aware over the
wallpaper; the command bar is the single bounded optical surface (one blurred surface on the
page); `#order-list` is near-opaque because table readability is not negotiable; metric cards and
utility panels use the secondary translucent grade; controls follow the A6 light treatment.
`.production-work` carries no material of its own — a second card wrapped around the data surface
would put two borders and two shadows between the wallpaper and the table.

Dark mode is tuned rather than inverted, and is asserted as such: row separation, header
distinguishability, chip readability, progress-track body and focus visibility are each measured
in dark mode, not screenshotted.

## Accessibility

- Semantic headings: `h1` page identity, `h2` for the four detail sections and the order list.
- A real `<table>` with `<th scope="col">`; no forged ARIA table roles.
- Every filter keeps its accessible name (`Cari order atau SKU`, `Status`, `PIC order`,
  `Posisi barang`); visible labels are shortened but remain contained in the accessible name.
- `#production-filter-hint` remains `aria-describedby` for the stage select.
- Progress keeps `Jumlah diterima gudang <reference>` on the element that carries the value.
- Status never depends on colour alone (`status-dot` plus text, both preserved under forced
  colours) and the shortened issue chip keeps its full wording for assistive technology.
- `#board-message` / `#detail-message` remain `role="status"` live regions.
- Search submits from the keyboard; row navigation reaches the detail trigger by Tab.
- Focus is restored to `#search` when returning from an order.
- Forced colours: chips and the progress meter keep real borders, the fill keeps a Highlight
  paint, rows keep separation, controls keep visible edges.

## Performance

`backdrop-filter` remains on the command bar and nowhere else — no metric card, row, status chip,
SKU panel, timeline item or cell is a backdrop root, so a long board costs the compositor nothing
more than it did before. No new polling, no new idle animation frame and no new timer: the
acceptance module patches `requestAnimationFrame` and asserts a settled board schedules none.

## Responsive strategy

| Width | Behaviour |
|---|---|
| 1440 | One row of four metrics, one-row command bar, full table. At 1440×1000 the measured first viewport is heading 103 → metrics 182 → cleared note 318 (30px) → command bar 368 → hint 434 (18px) → `Order produksi` 477 → table header 519, with five real rows below it. The run between the metric strip and the order list is pinned at ≤200px so neither informational strip can re-inflate. |
| 1024 | Metric track narrows; table keeps its semantic width and its surface becomes a horizontal scroller. |
| 768 | Command bar wraps; table still scrolls inside its surface. |
| 390 | Metrics fall to 2×2; command bar takes full-width rows; the table keeps a `44rem` rem-based floor and scrolls. |
| 320 | Same strategy; identifiers never crush to one character per line. |
| 320 @ 200% text | Mandatory pass: no document overflow, nothing clips inside itself, every chrome control stays within the viewport, and the table's controls stay reachable through the scroller. |

Option A from the phase brief was taken: one horizontally scrollable semantic table at every
width, rather than a second stacked renderer. There is therefore exactly one business renderer,
one set of actions, one filter semantics and one pagination — no divergence to keep in sync. The
rem-based `min-width` is what makes 200% text grow the columns instead of re-crushing them.

The post-PR #98 scroll architecture is preserved and asserted: the document does not scroll,
`.workspace-main` is the scrolling region, the sidebar nav scrolls internally, the approval
utility stays pinned, and no second app-level scrollbar appears.

## Reduced motion / transparency / forced colours

Reduced motion keeps every state signal and drops every movement: the refresh dim still appears
(without a transition), the replacement fade does not run, progress applies its target
immediately. No new motion system, no row stagger, no card cascade, no animated command bar and no
ambient animation were introduced.

Reduced transparency falls back to A6.0's authoritative behaviour — dense surfaces return to the
fully opaque A1 materials and the blur is withdrawn. The withdrawal is pinned statically in
`tests/test_apple27_modern_workspace_foundation_contract.py`; the browser module asserts it live
only when the engine actually evaluates the preference, and otherwise asserts that the default
rendering is translucent so there is something to withdraw.

## Legacy CSS containment

The `#board-view`-scoped premium-UI block at the tail of `style.css` (≈95 lines redesigning
`.summary`, `#search-form`, `.order-grid`, `.table-head`, `.progress-note` plus three container
queries) was **deleted**, not overridden, and so was a stale standalone `#search-form` grid rule.
Both were id-scoped: an id out-specifies a class, so leaving them would have kept the old stacked
filter grid and the old KPI card alive underneath the command bar and the metric strip. Every
selector in both was scoped to Produksi, so removing them changes no other page.

What remains is a small documented A6.1 containment block:

- `#board-view, #detail-view` — the bounded 1360px column the workspace was approved with;
- `.production-work` — the grouping element's stacking rhythm, and no material;
- `#board-message, #detail-message` — the legacy `.state` card withdrawn, because the A6 state
  primitive now renders inside them;
- `#issues-summary` — the element resets an `attention-note` on a `<button>` needs, and a hover
  that keeps its semantic tint;
- `#order-list.is-refreshing` — M4's documented 0.78 refresh dim, which A6's generic
  `data-surface[aria-busy]` 0.6 would otherwise win on specificity and load order;
- a `max-width:980px` block restoring the product's own 44px touch floor for the migrated
  controls, because A6's compact control height and `.order-title`'s shared `min-height:auto`
  reset out-specify the global `button,input,select,textarea{min-height:44px}` rule. A6.0's
  `pointer:coarse` step is additive to that policy, not a replacement for it.

The legacy vocabulary itself is deliberately left intact, because Command Center, Bahan baku,
People, Aktivitas, Audit, the approval queues and every production child dialog still render with
it. Two groups came out of the audit:

**Still in active use elsewhere — must not be removed.** `.summary` (Command Center, Aktivitas,
People), `.filters` / `.filter-form` (Aktivitas and most pages), `.status-label` / `.badge`
(Command Center decision rows, Integrasi, Kapasitas produksi, Audit, People), `.sku-block` /
`.sku-heading` (Bahan baku batch list), `.issue-item` (the deadline/PIC change-history dialog),
`.issue-heading` (three analytics surfaces), `.history-item` (Aktivitas), `.order-title` (Aktivitas
and the board), `.reference` (People rows, Bahan baku batches and the board), `.list-host` (Audit,
approvals, purchase requests, marketing budgets), `.state` (every page and dialog),
`.history-section` / `.history-heading`, `.line-input` (the create-order collector).

**Now unreferenced by any shipped markup — inert, and a named follow-up rather than a silent
leftover.** `.order-grid`, `.table-head`, `.cell`, `.cell-label`, `.progress-cell`, `.status-cell`,
`.progress-note`, `.detail-top`, `.detail-meta`, `.stages`, `.stage`, `.stage-number`,
`.exceptions`, `.sku-balances`, `.order-settings`, `.ledger-heading`, `.issues-summary` (the class;
the `#issues-summary` id is still used), `.issue-resolution`, and `.production-wip` (whose rules
were inside the deleted block and are already gone).

These were all Produksi-exclusive, so they now match nothing and cannot fight the new board — the
containment requirement is satisfied. They are left in `style.css` rather than deleted in this
phase for one deliberate reason: removing ~70 lines of currently-inert CSS immediately before a
human visual gate adds regression surface without changing a single rendered pixel. They should be
deleted in a follow-up sweep, ideally alongside A6.2, once more of the legacy vocabulary retires
together and one browser run can cover the whole removal.

A6.1 contains its migration instead of widening it.

## A6.0 migration contract, narrowed

A6.0 promised that no shipped surface used an A6 primitive name, which made loading the stylesheet
a guaranteed no-op. A6.1 is the first phase allowed to spend that promise, so
`test_primitives_are_inert_against_every_shipped_surface` became
`test_primitives_are_inert_outside_the_migrated_workspace`. The allowance is narrow by
construction:

- `style.css`, `workspace.css`, `workspace.mjs` and `client.mjs` still may not use one at all;
- `index.html` may use them only inside `#board-view` and `#detail-view` (found by tag counting,
  because `#board-view` contains a nested `<section>` and `#activity-view` sits between the two);
- `app.mjs` may use them only inside the migrated renderers — `pageState`, `statusHTML`,
  `issueBadge`, `loadBoard`, `renderDetail`, `renderHistory`, `renderIssues`, `orderForm` —
  attributed line by line to the top-level symbol that owns each line.

A stray `data-surface` added to Bahan baku, People, Analitik or a child dialog therefore still
fails, which was the whole point of the original test. A companion
`test_the_migration_actually_happened` prevents the reverse failure: deleting the migration and
leaving the allowance behind.

## Tests

| File | Role |
|---|---|
| `tests/test_apple27_production_workspace_contract.py` | **new** — 41 static assertions: metric/field mapping, progress meaning, query identity, status mapping, action-group completeness, stage-balance semantics, create-order rules, frozen shell/lens/spring, frame-and-timer budget, containment, version/schema/route. |
| `tests/browser_production_modern_workspace.cjs` | **new** — behavioural: real-payload parity for every metric and every row, filter queries, both empty states, load failure, overtaken-response guard, pagination, refresh-in-place, detail structure and data parity, the reviewed section order and the measured first viewport, action weights (3 commands vs 24 chevron rows, each still addressable by its own accessible name), back-control alignment, three roles, create-order rules, five widths plus 320 @ 200%, dark mode, forced colours, reduced transparency, reduced motion, zero idle frames, shell/scroll regression. |
| `tests/test_apple27_modern_workspace_foundation_contract.py` | migration boundary narrowed as above; version pin 0.107.0. |
| `tests/browser_production_premium_ui.cjs` | rewritten for the migrated markup. Its overflow helper now exempts descendants of a scroll container (A6's documented table strategy) while still checking self-clipping and document overflow, and its contrast sweep now composites alpha over the canvas instead of reading the first non-transparent background as opaque — A6 hover is a 4% overlay and A6 surfaces are 92% alpha, so the old parser measured colours that are never on screen. |
| `tests/browser_shared_ui.cjs` | radius ladder read against A6's approved workspace scale (surface 16, panel 12, control 10, chips pill) with the shell still at 20; board and detail composition updated. |
| `tests/browser_kpi_glyphs.cjs` | glyph searched from the card rather than from inside `<dt>`; the board's tone policy asserted against resolved role colours in both themes; Aktivitas keeps the legacy end-of-row glyph assertion. |
| 14 child-dialog modules | `.order-settings` rescoped to `#detail-content .panel-grid` (50 call sites). Pure scoping change; no child dialog was redesigned. |
| 12 modules | board heading assertion `Yang sedang dikerjakan.` → `Produksi`, with `exact: true` (needed, because `Order produksi` and `Kendala produksi` would otherwise substring-match). |

## Screenshots

Deterministic, from the demo fixture plus synthetic board payloads for the states real data cannot
reach. Written to `$BEELOFT_QA_SCREENSHOTS` (the runner's temporary directory by default) and
**not committed**, per repository convention.

| File | Case |
|---|---|
| `a61-board-1440-light.png` | board, 1440, light, populated |
| `a61-board-1440-firstviewport.png` | board, exactly what a 1440×1000 reviewer sees before scrolling |
| `a61-board-1440-dark.png` | board, 1440, dark, populated |
| `a61-board-1024-light.png` | board, 1024 |
| `a61-board-768-light.png` | board, 768 |
| `a61-board-390-light.png` | board, 390 |
| `a61-board-320-light-200.png` | board, 320 at 200% text |
| `a61-board-1440-light-no-match.png` | filters return nothing |
| `a61-board-1440-light-empty.png` | production genuinely empty |
| `a61-board-1440-light-issues.png` | open issues present |
| `a61-detail-1440-light.png` | order detail, 1440, light |
| `a61-detail-1440-dark.png` | order detail, 1440, dark |
| `a61-detail-390-light.png` | order detail, 390 |
| `a61-detail-1440-firstviewport.png` | order detail, exactly what a 1440×1000 reviewer sees before scrolling — the unit the information-hierarchy review is judged on |
| `a61-create-order-desktop.png` | create-order dialog, populated |
| `a61-create-order-mobile.png` | create-order dialog, 390 |

## Remaining legacy — production child dialogs are NOT redesigned

A6.1 modernises the Produksi board, the Produksi order detail and the create-order form. **The
internals of the production child dialogs are explicitly out of scope and still render the legacy
dialog vocabulary** (`.form-grid`, `.form-actions`, `.status-label`, `.issue-item`,
`.material-event`, `.sku-block`, `.product-item`, `.list-host`). Their entry points were
reorganised into the three workflow groups on the order-detail page; their contents were not
touched.

Not modernised by this phase:

- cutting dialogs (`Hasil cutting`, `cutting-run`);
- bundle dialogs (`Bundle`, bundle scanning);
- sewing / makloon dialogs;
- finishing dialogs;
- final QC and rework-completion dialogs;
- material dialogs (`Kebutuhan bahan`, `Reservasi bahan`, `Pemakaian & waste`,
  `Keluarkan bahan ke order`, `Riwayat bahan order`);
- cost and margin dialogs (`Biaya aktual`, `Margin kontribusi`);
- deadline/PIC dialogs (`Ubah tenggat / PIC`, change-request and history dialogs);
- marketplace dialogs (`Reservasi jual`, `Picking`, `Packing`, `Shipping`, `Retur`, `Adjustment`);
- stock opname dialogs;
- purchasing dialogs (`PR untuk order ini`);
- the movement (`Catat perpindahan`) and issue (`Catat kendala`, `Selesaikan kendala`) dialogs.

Also still on the legacy language, and untouched here: Command Center, Bahan baku, People, Master
SKU, Aktivitas, Analitik, Tanya Beeloft, Integrasi, Audit trail, Inbox approval, Permintaan
pembelian, Budget marketing and both scan pages. Those belong to A6.2–A6.8.

Within the migrated pages, two legacy classes remain **by design** rather than by omission:
`.order-title` / `.reference` on a board row (addressed by `playProgressSettle()`, the M4 motion
module and ~20 acceptance modules) and `.line-input` in the create-order form (the row collector
finds lines by it). `.state` remains on the two message hosts for the same kind of reason.
