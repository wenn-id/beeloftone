# Apple-27 A6.2 — Bahan baku + Master SKU modern workspaces

A6.0 built the shared inner-workspace language and deliberately kept it out of shipped markup.
A6.1 spent it on Produksi. A6.2 spends it on the two master-data workspaces — the material batch
inventory (`#materials-view`) and the SKU catalog (`#products-view`) — and, unlike A6.1, on the
dialogs those pages launch, because for a master-data workspace the dialogs *are* the workflow
rather than a side task.

This is a presentation migration. No route, no schema, no migration, no new API field, and no
business number that the existing endpoints do not already return.

---

## 1. Exact baseline

| | |
|---|---|
| Baseline `origin/main` | `87a70e827406f65db64a943ddf8252e4072492ab` |
| Post-merge CI on that exact SHA | run **#161**, `success` |
| Branch | `ui/apple27-a6-2-materials-master-sku` |
| Version | `0.107.0` → **`0.108.0`** |
| Schema | `PRAGMA user_version = 55` (unchanged, no migration) |
| A6.0 foundation | merged + human approved, consumed unchanged |
| A6.1 Produksi | merged through PR #100, frozen |
| A5.2 shell / A5.3 lens / A3 spring | frozen, untouched |

Files changed: `beeloft/static/index.html`, `beeloft/static/app.mjs`, `beeloft/static/style.css`,
`beeloft/api.py` (version string only), `pyproject.toml`, `docs/openapi.json` (`info.version` only),
`README.md` (the stated test count), three existing contract tests, this document, one new contract
test, one new browser module, and eight existing browser modules whose assertions named copy or
structure this phase intentionally changed (§20).

---

## 2. A6.0 primitives consumed

Nothing new was added to `workspace-primitives.css`. A6.2 introduced **no** new primitive and
**no** page-specific component clone. The vocabulary consumed:

**Page frame** — `workspace-page`, `workspace-heading`, `workspace-heading-copy`,
`workspace-eyebrow`, `workspace-title`, `workspace-subtitle`, `workspace-actions`,
`workspace-section-title`, `workspace-subhead`, `workspace-meta`.

**Controls** — `command-bar`, `command-filters`, `command-filter`, `command-search`,
`command-actions`, `action-primary`, `action-secondary`, `action-quiet`, `action-destructive`,
`action-row`, `field-actions`, `field-actions-end`.

**Data** — `data-surface`, `data-header`, `data-row`, `data-cell`, `data-cell-numeric`,
`data-cell-tight`, `data-primary`, `data-secondary`, `data-meta`, `record-list`, `record-row`,
`record-row-copy`, `record-row-aside`, `metric-icon`.

**State & meaning** — `status-chip` (+`-success`, `-neutral`, `-warning`), `status-dot`, `chip-row`,
`attention-note` (+`-info`), `attention-note-copy`, `attention-note-title`, `attention-note-reason`,
`empty-state`, `error-state`, `loading-state` (all three via the shared `pageState()` helper),
`info-panel`, `utility-panel`, `utility-panel-title`, `detail-grid`, `detail-grid-compact`,
`detail-field`, `timeline`, `timeline-item` (+`-success`, `-info`, `-warning`), `timeline-time`,
`timeline-event`, `timeline-actor`, `timeline-detail`.

**Forms** — `field`, `field-label`, `field-help`, `field-wide`, `scan-surface`, `scan-target`.

### The one shared helper A6.2 added

`reasonField(label)` in `app.mjs` — a top-level builder that emits the reason textarea as an A6
`.field` with the same `name="reason"`, the same `required` and the same `maxlength="1000"` as
before. The legacy `materialReason` constant is **left completely intact**, because Produksi's
`materialIssueForm` (reached from the order detail) still renders it and A6.1 is frozen. That is a
deliberate fork, not an oversight: A6.2 may not restyle a Produksi child dialog.

### Primitives deliberately *not* used

`metric-strip` / `metric-card` — see §5. `progress-*` — mixed units must never be drawn as one
cumulative bar (§7). `segmented-filter` / `filter-chip` — neither page has a filter whose values
live in the already-loaded data. `skeleton-line` — no skeleton delay was introduced.

---

## 3. Bahan baku hierarchy

```
Bahan baku                                  [Master bahan] [Scan batch bahan] [Terima batch bahan]
Pantau batch, saldo, reservasi, dan stok bebas untuk produksi.
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│ Bahan  [ Semua bahan ▾ ]                                            [ Muat ulang bahan ] │
└───────────────────────────────────────────────────────────────────────────────────────────┘
ⓘ Saldo adalah bahan layak pakai yang diterima, dikurangi pengeluaran ke order. Stok bebas = …
Batch bahan
┌──────────────────────┬──────────────────┬───────────┬────────┬─────────────┬────────────┬──┐
│ Batch / bahan        │ Supplier / lokasi│ Diterima  │ Saldo  │ Direservasi │ Stok bebas │  │
├──────────────────────┼──────────────────┼───────────┼────────┼─────────────┼────────────┼──┤
│ BTH-240901           │ Supplier A       │ 25 Sep    │ 120 m  │ 40 m        │ 80 m       │ →│
│ FAB-COT-01 · Cotton… │ Rak A-03         │ 2026      │        │             │            │  │
└──────────────────────┴──────────────────┴───────────┴────────┴─────────────┴────────────┴──┘
Batch 1–25                                      [ Batch sebelumnya ] [ Batch berikutnya ]
```

The legacy identity (`"Bahan baku · stok internal"` / `"Bahan masuk, pemakaian tercatat."`) is
replaced by the workspace's own name and its actual job. The page now leads with *what this
workspace is*, not with a slogan.

**Action hierarchy.** `Terima batch bahan` is the primary command, `Scan batch bahan` secondary,
`Master bahan` quiet. This is weight only — the permission rule is byte-identical (§11).

**Why a table.** The batch inventory is genuinely tabular: many rows, six aligned attributes, and
the core operator task is scanning a column downwards to compare quantities. So it is a real
`<table>` inside the A6 `data-surface`, with a real `<thead class="data-header">` and `scope="col"`
on every header. That keeps table semantics for assistive technology and gives the operator the
aligned numeric rhythm the job needs.

**Batch identity.** The batch reference is the row's primary text and a real `<button>` (so it is
focusable and its accessible name is exactly the reference — which is how the PO and incoming-QC
modules locate it). The material `code · name` is the secondary line. Supplier is the second
column's secondary line, location its metadata. A quiet row-end chevron marks "this opens" without
becoming the only way in; whole-row click was **not** introduced.

---

## 4. Batch quantity semantics

`balance`, `reserved` and `available` are rendered exactly as the API returns them, each through the
shared `formatMaterialQuantity()` formatter with the material's own unit. Nothing is summed,
derived, rounded or recombined; the browser module asserts each of the three against the value the
endpoint actually returned for that batch.

| Column | Field | Treatment |
|---|---|---|
| Saldo | `balance` | normal weight, `--ink` |
| Direservasi | `reserved` | quiet, `--muted` |
| Stok bebas | `available` | strongest, `--ink` at weight 650 |

The emphasis ordering follows the phase brief: free stock is what an operator can actually commit.
**This is emphasis, not authority.** Every figure is labelled by its own column header, so the
meaning never depends on weight — which is also what makes the treatment survive `forced-colors`,
where the weight difference collapses and the header is all that is left.

The business meaning communicated on the page is unchanged and preserved word for word:

> Saldo adalah bahan layak pakai yang diterima, dikurangi pengeluaran ke order. Stok bebas = saldo
> fisik dikurangi reservasi semua order. Untuk mengalokasikan atau mengeluarkan bahan, buka order
> produksi.

It moved from a bare `.hint` paragraph to an A6 `info-panel` whose filled surface is then withdrawn
(§12), keeping it a quiet utility note rather than a panel competing with the data.

---

## 5. No fabricated aggregate

Neither page grew a metric strip. `/api/material-batches` returns one page of 26 records and no
global aggregate, so there is no honest figure for *Total stok*, *Stok kritis*, *Pemakaian bulan
ini* or *Coverage* — and summing the 25 rendered batches would be a lie about global stock. The
contract test asserts `metric-strip`/`metric-card` appear in neither view nor either renderer, and
that `loadMaterials()` contains no `.reduce(`.

The batch inventory list is the page's primary surface, and it starts inside the first 1440×1000
viewport with nine rows visible.

**No invented batch status.** The list payload does carry a `status` field, but it is
receipt-correction bookkeeping and the list has never rendered it; it is used semantically only
inside the batch dialog (`penerimaan dikoreksi`, and the label print gate), where A6.2 preserves it
as a `status-chip-warning`. Deriving *Healthy* / *Low stock* / *Critical* from a quantity would be a
business claim this endpoint does not make, so no chip appears on a row at all.

Master SKU carries one restrained count in its section subhead —
`N SKU · N dipetakan · N belum dipetakan` — derived purely from the complete `productsCache` already
in the browser. When a search is active it becomes `N dari M SKU`. No request is made for it, and it
is `workspace-meta` on a heading row, not a dashboard.

---

## 6. Filter, pagination and request contract

Byte-identical to the baseline:

* `allRows('/api/materials')` fills the filter with every master row as `code · name (unit)`, plus
  the `Semua bahan` option.
* `GET /api/material-batches?limit=26&offset=<materialsOffset>&material_id=<id>`.
* **26 is the sentinel.** `batches.slice(0,25)` renders; `materials-next` is disabled when
  `batches.length <= 25`. Never infinite scroll — there is no `IntersectionObserver` in the file.
* `materials-previous` → `materialsOffset = Math.max(0, materialsOffset - 25)`;
  `materials-next` → `materialsOffset += 25`.
* Changing the filter → `materialsOffset = 0` then `loadMaterials()`.
* Label: `Batch X–Y`, or `0 batch di halaman ini`.

The browser module proves the offset reset by reading the **real query string** the page requested
after walking to page two, rather than trusting the control it clicked.

### Stale safety and refresh motion

All three guards survive: `epoch` (session generation), `materialsRequest` (bumped by a newer load
*and* by `activateWorkspace()` navigating away), and `view !== 'materials'`. The `catch` repeats the
same triple, so a late failure cannot paint an error onto another page.

`materialsQuery` keeps its original semantics — **the filter actually rendered, not the latest
request started.** That is what makes a retry after a failed load still count as a list replacement,
and removing it would break the replacement motion. `markRefreshing('batch-list')` /
`settleRefreshing` are unchanged: refreshing and paginating keep the visible rows dimmed and
`aria-busy`, only a real filter change plays `playEntryMotion($('batch-list'), '--motion-base')`.
M4's documented `.78` dim is restored by an id-scoped rule, because A6 would otherwise dim a busy
data surface to `.6`.

### States

| State | Presentation |
|---|---|
| First load | `pageState('materials-message','loading', 'Memuat stok bahan…')` |
| Populated | state host hidden |
| Empty page | `empty-state`: *Belum ada batch pada halaman ini.* + *Terima bahan untuk mulai mencatat stok, atau ubah filter bahan dan halaman.* |
| Empty page, write allowed | plus a real CTA named **Terima batch bahan pertama** |
| Empty page, viewer | no CTA |
| Load failure | `error-state` with the real message; `401` still routes through `fail()` so an expired session returns to login |

"No batches on this page" and "no material master exists" stay different statements: the empty state
names the *page* and points at both the filter and pagination. The CTA's name deliberately differs
from the header button so the two are never ambiguous to a keyboard or a screen reader — the same
idiom A6.1 used for *Buat order produksi pertama*. On an empty page the table is not rendered at
all, so no lone header row is left behind.

---

## 7. Batch detail, history and traceability

`materialHistoryDialog()` now reads in the order the operator asks:

1. **Identity** — `workspace-eyebrow` = `code · name`, section title = the reference, plus a
   `status-chip-warning` *Penerimaan dikoreksi* when `status === 'corrected'`.
2. **Current position** — a `utility-panel` titled *Posisi bahan sekarang* holding a
   `detail-grid detail-grid-compact` with Saldo / Direservasi / Stok bebas / Lokasi.
3. **Source** — a `detail-grid` with Pemasok / Diterima / Jumlah diterima.
4. **Related records** — an `action-row`: *QC asal batch*, *PO …*, *Jejak produksi lengkap*.
5. **Label** — the unchanged QR label, then *Cetak label batch*.
6. **Movement history** — the A6 `timeline`.

Physical quantities are no longer below the history; the contract test asserts the *Posisi bahan
sekarang* block precedes *Riwayat catatan bahan* in the source.

Supplier, received date, received quantity and `available` now appear in this dialog where they did
not before. **No new request was added** — every one of those fields was already on the
`GET /api/material-batches/{id}` response the dialog has always fetched.

**Order mode is intact.** Produksi's order detail calls the same renderer as
`materialHistoryDialog(null, selected)`. With no batch, every batch-only block collapses exactly as
it did before: no label, no QC/PO/traceability actions, no position panel, the header is the order
reference, and the path is `/api/orders/{id}/material-movements`. Both the contract test and the
browser module assert this explicitly, because it is the one place A6.2 could have broken A6.1
outright.

**Movement history.** `receipt` / `issue` / anything-else stay three distinct events with their own
labels (*Penerimaan* / *Pengeluaran* / *Pembalikan*) and their own timeline tone. Quantity and unit
remain a single string so a negative sign can never orphan from its number. Batch reference,
material code, optional order reference, reason, actor, timestamp and the *Sudah dibalik* reversal
state all survive. `limit=100` with the `sequence` cursor and *Muat catatan bahan sebelumnya*
unchanged; newest-first ordering is the server's and the renderer never re-sorts.

**Correction rules are untouched.** Still `user.role === 'admin' && !m.reversal_of && !m.reversed_by
&& !((batch?.qc_intake_id || batch?.po_closed) && m.kind === 'receipt')`, still posting to
`/api/material-movements/{id}/reverse`, still carrying the full reversal warning. Presentation only.

**The batch label is byte-identical.** `<section class="bundle-label material-batch-label">` with
the same `label.svg`, reference, material identity, received quantity, location and received date,
still gated on `status === 'active'`, and still a **direct child of `#dialog-content`** — which the
`@media print` rule depends on. Both tests assert the nesting.

**Traceability** (`materialBatchTraceabilityDialog()`) keeps `/api/material-batches/{id}/traceability`,
`limit=50` on the first page and every page, and the `next_before` object cursor spread straight
into `URLSearchParams`. All nineteen event labels and all ten status labels are preserved; the
`_correction` suffix still resolves to its base label with a `Koreksi · ` prefix and is the only
thing that tints a row. The browser module asserts the rendered `data-material-trace-event` sequence
equals the API's event sequence, so nothing was collapsed to simplify the visual.

The mixed-unit truth stays explicit — *Nilai bahan dan pcs memakai satuan berbeda dan tidak
dijumlahkan antarcatatan.* — and it is a timeline, never one cumulative progress graph. Both tests
assert no `progress` element exists in that dialog.

---

## 8. Master bahan, receiving, and the batch scanner

**Master bahan** is a compact `record-list` of identities: `code` as primary, `name · unit` as
secondary, with an `info-panel` stating where balances actually live (*Saldo dan stok bebas dicatat
per batch di halaman Bahan baku*). It carries **no quantity at all** — the contract test asserts
`materialQty` never appears in that renderer. `Tambah bahan` stays admin-only. The list keeps its
own scroll via an id-scoped rule so the primary action below it stays reachable.

**Tambah bahan** uses A6 `.field` markup with the accessible names `Kode bahan`, `Nama bahan` and
`Satuan dasar` unchanged, the three units `m` / `kg` / `pcs` unchanged, and the immutability rule
still stated: *Kode, nama, dan satuan tidak dapat diubah setelah disimpan.* No edit-material
behaviour was created.

**Terima batch bahan** keeps `material_id`, `reference`, `supplier`, `location`, `received_date`,
`quantity` and `reason`, the fixed `max="1000000"`, and the unit-dependent precision rewritten on
every material change — `pcs` → `step`/`min` = `1`, `m`/`kg` → `0.001`. Validation was not weakened
anywhere; the browser module drives both branches and then submits a real `3.25` receipt and asserts
the stored balance is exactly `3.250`.

**Scan batch bahan** stays a keyboard scanner: `autofocus` plus an explicit `input.focus()`, a real
`<form>` so Enter submits, `GET /api/material-batches/scan?code=`, success closes and opens the
batch, failure re-enables the button and **returns focus to the input**. No camera scanning was
added; the contract test asserts `getUserMedia` / `BarcodeDetector` / `video` appear nowhere in it.
The input sits in an A6 `scan-surface` / `scan-target`.

---

## 9. Master SKU hierarchy

```
Master SKU                                                     [ Muat ulang ] [ + Tambah SKU ]
Kelola identitas produk, mapping Jubelio, dan BOM.
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│ 🔍 Cari kode, nama, varian, atau SKU Jubelio                        [ Reset pencarian ]   │
└───────────────────────────────────────────────────────────────────────────────────────────┘
ⓘ Mapping Jubelio dipakai konektor untuk mencocokkan SKU tanpa menebak nama produk. …
Katalog SKU                                   3 SKU · 2 dipetakan · 1 belum dipetakan
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│ 🏷  SKU-LUNA-M-BLU                                              [ Jubelio ]  [ BOM ]      │
│     Luna Long Swimsuit                                                                    │
│     Blue / M                                                                              │
│     ● Terhubung   JUB-LUNA-M                                                              │
└───────────────────────────────────────────────────────────────────────────────────────────┘
```

**Why a record list, not a table.** This is the deliberate difference from Bahan baku. A SKU row is
identity plus a status plus two actions — there is no column of numbers to compare downwards. A
`record-list` gives the same A6 material and the same density, and it *reflows by itself* at narrow
widths through A6.0's own 650px rules (`.record-row{flex-wrap:wrap}`,
`.record-row-aside{width:100%}`). That means one renderer, no separate mobile path, and **no
horizontal scroll on a phone** — which a four-column table would have needed. The two pages belong
to one visual system without having the same composition.

Row hierarchy follows the brief: `data-primary` = SKU, `data-secondary` = product name,
`data-meta` = `color / size`, then a `chip-row` with the mapping state. No thumbnail was invented —
this workspace's API supplies no image. Both per-SKU actions keep their disambiguated accessible
names, `Jubelio {sku}` and `BOM {sku}`.

### Local search semantics

Unchanged and intentionally local: `$('products-search').oninput = paintProducts`, filtering the
complete `productsCache` on every keystroke with **no network request and no debounce**. All four
searchable values survive: `sku`, `name`, the composed `color / size` string, and the Jubelio
`external_sku`. `Reset pencarian` clears the input and repaints. The filtered-empty state offers the
same reset through a `reset-product-search` action that runs the identical local path.

The browser module attaches a request listener around each search case and asserts the collected
list of `/api/` requests is **empty**.

### Data contract

`loadProducts()` still issues exactly two paged reads — `allRows('/api/products')` and
`allRows('/api/product-external-mappings', {system:'jubelio'})` — joined client-side by
`product_id` into `productsCache`. No server-side search was introduced.

**No N+1.** Painting the catalog never requests a BOM. The list shows no BOM revision or completion
state, because showing one would require a request per SKU. The contract test asserts `/bom` appears
in neither `loadProducts` nor `paintProducts`; the browser module records every request made during
a real refresh and asserts none of them touched `/bom`.

### States

| State | Presentation |
|---|---|
| First load | `loading-state`: *Memuat daftar SKU…* |
| Refresh | rows kept, dimmed to `.78`, `aria-busy`; search and reset locked as before |
| No match | `empty-state`: *Tidak ada SKU yang cocok dengan pencarian ini.* + a reset action |
| Empty catalog | `empty-state`: *Belum ada SKU.* / *Tambahkan produk untuk membuat order pertama.* — with **Tambah SKU pertama** for admin only |
| Load failure | `error-state`: *Daftar SKU gagal dimuat.* + the real message + **Coba lagi** → `loadProducts` |

The two empty cases stay genuinely different states. The retry was not removed, and the existing
behaviour that search stays disabled until a load succeeds is preserved exactly.

---

## 10. Mapping truth

The distinction the brief insists on is preserved verbatim:

> Jubelio adalah sumber order marketplace dan stok jual. Mapping ini hanya mencocokkan identitas;
> belum menjalankan sinkronisasi.

Mapped state says exactly **Terhubung** and shows the `external_sku`. Unmapped says **Belum
dipetakan**. The words *Synced*, *Tersinkron*, *Sehat*, *Healthy* and *Connected live* appear
nowhere — asserted across the catalog renderer, the mapping dialog and the mapping history.

Visual treatment is restrained: mapped is `status-chip-success`, unmapped is `status-chip-neutral`.
**Never `status-chip-danger`** — an unmapped SKU is not broken. In the dialog the operational warning
(*Worker tidak boleh mengimpor data untuk SKU ini sebelum identitas Jubelio dipetakan.*) is an
`attention-note-info`, not `attention-note-critical`.

Mapped records keep `external_sku`, `external_id`, `reason`, `revision`, `actor_name` and
`created_at`. Admin gets `action-primary` *Ubah mapping* and `action-destructive` *Lepaskan mapping*;
every allowed role keeps quiet *Riwayat mapping* and *Kembali ke Master SKU* — and the contract test
asserts those two sit **outside** the admin branch.

The mapping form keeps `external_id`, `external_sku`, `reason` and `expected_revision` with
`action: 'mapped'`, identifiers stored exactly as given and no normalisation beyond the existing
implementation. The unmap form keeps `expected_revision`, `reason`, `action: 'unmapped'`, empty
`external_id`/`external_sku`, and the stop-matching warning. The browser module intercepts both
POSTs and asserts the payloads field by field, including the optimistic-concurrency token.

Mapping history keeps `limit=20`, the `sequence` cursor, and one entry per revision stating its own
revision number and its own mapped/unmapped state — never merged.

---

## 11. BOM truth

Unchanged: BOM is the material needed for **1 pcs** of the SKU, it follows material master units,
and it does **not** automatically include waste. That sentence is rendered word for word.

`bomDialog()` shows the revision, actor and date in a `workspace-subhead`, the components as a
`record-list` with each quantity stated as `… / pcs`, and the reason. The empty case is a proper A6
information state — *BOM belum diisi.* / *Kebutuhan bahan belum dapat dihitung untuk SKU ini.* —
with `Isi BOM` for admin only. `Riwayat BOM` stays revision-gated rather than role-gated, as before.

`bomForm()` keeps every rule: `.bom-line` rows (the class both the collector and the purchasing
editor address), `material_id` + quantity per pcs, `reason`, `expected_revision`, duplicate-material
rejection with the same message, the 100-line cap, the minimum of one line with the same `notify()`,
`max="1000000"`, and unit-dependent `step`/`min` (`pcs` → `1`, otherwise `0.001`) recomputed on every
material change. The save-semantics copy is intact:

> Menyimpan membuat versi baru dan memperbarui estimasi kebutuhan semua order SKU ini, termasuk
> order lama. Stok dan pengeluaran tidak berubah.

The browser module drives the duplicate rejection and asserts **nothing was persisted**, then fixes
the form and asserts exactly one revision was written.

`bomHistoryDialog()` keeps `limit=10`, the `revision` cursor and *Muat versi sebelumnya*, rendering
each revision as its own timeline entry with its own component list — revisions are never merged.
The browser module creates eleven revisions and asserts ten on the first page, eleven after paging,
and eleven separate component lists.

`productForm()` keeps `sku` / `name` / `color` / `size` with limits 160 / 160 / 80 / 40 and the same
one-code-per-combination copy. The optional marker (`field-label-optional`) is deliberately **not**
used: it would have renamed `Warna` and `Ukuran` in the accessibility tree.

---

## 12. CSS containment

One marked block appended to `style.css`, beginning at the selector
`#materials-view,#products-view{max-width:1360px`. It contains no component. Every rule is either
the bounded column, the grouping element's rhythm, or a narrow neutralisation of a legacy rule still
shipped for other pages:

| Rule | Why |
|---|---|
| `#materials-view,#products-view{max-width:1360px;margin-inline:auto}` | the approved reading column |
| `.materials-work,.products-work` | grouping flex column carrying **no** material — two nested surfaces would double the border and shadow |
| `#materials-message,#products-message{padding:0;border:0;…}` | withdraws the legacy `.state` card so `pageState()`'s primitive is not double-framed |
| `#materials-inventory-note,#products-mapping-note` | withdraws the `info-panel` surface and bounds the measure to 96ch |
| `#batch-list.is-refreshing,#product-list.is-refreshing{opacity:.78}` | keeps M4's documented dim over A6's `.6` |
| `#product-list{max-height:none;overflow:visible;margin:0;padding:0}` | the legacy `.product-list` scroll box belongs to the three dialogs that still render it |
| `#material-master-list{max-height:min(420px,52dvh);overflow:auto}` | re-opens the scroll `.record-list` closes, so the dialog's primary action stays reachable |
| `#batch-list [data-batch-*]` | the quantity emphasis of §4 |
| `@media(max-width:980px)` | `#batch-list>table{min-width:56rem}` and the touch-target floor |

**The A6.1 block was not widened.** Its slice in
`tests/test_apple27_production_workspace_contract.py` used to run to end-of-file; it is now bounded
by the A6.2 marker, so `test_the_migration_is_contained_to_produksi` keeps meaning exactly what it
meant when it was approved instead of having its allow-list stretched to cover a later phase. A6.2's
block is held to the same standard by its own containment test.

### Legacy vocabulary audit

Every legacy selector these pages used to render is **left in the stylesheet**, because deleting a
shared rule would break another workspace:

| Class | Still rendered by | A6.2 action |
|---|---|---|
| `.filters` | People, Aktivitas, purchase/marketing filters | stopped emitting on both pages; rule kept |
| `.search-field` | People search | stopped emitting; rule kept |
| `.page-heading`, `.eyebrow` | many workspaces | stopped emitting; rules kept |
| `.product-item` | material master, workforce master, work centres, BOM components (now via `record-list`) | stopped emitting on the catalog; rule kept |
| `.product-list` | three dialogs | kept on the page host as a legacy hook, neutralised by id |
| `.material-event` | ~124 sites across the app | stopped emitting in the five A6.2 dialogs; rule kept |
| `.reason` | ~113 sites | still emitted, now inside `timeline-detail` |
| `.form-info` | `formDialog` and ~85 sites | still emitted by `formDialog` itself |
| `.bom-line` | purchase-request line editor | still emitted, with A6 `.field` inside |
| `.bundle-label` | Bundle, Barang jadi, the print stylesheet | unchanged |
| `.list-host` | the motion contract's fade-host rule | kept on both hosts |
| `.order-title` | Aktivitas and Produksi | kept on the batch reference button |
| `.sku-block`, `.sku-heading`, `.material-balance` | **nothing, after A6.2** | stopped emitting; rules left in place |

The last row is deliberate. `.material-balance` and `#batch-list .sku-block` are now inert, but
A6.1's documented rule is that inert legacy CSS is removed by a phase that can prove the removal
safe on its own, not opportunistically by the next migration. They are recorded here as debt.

---

## 13. Permissions

Not one gate moved, and none is derived in CSS.

| Gate | Rule | Where |
|---|---|---|
| Receive material | `$('receive-material').hidden = user.role === 'viewer'` | `showMaterials()` |
| Empty-state receive CTA | omitted when `user.role === 'viewer'` | `loadMaterials()` |
| Create material | `user.role === 'admin'` | `materialMasterDialog()` |
| Correct a movement | `admin && !reversal_of && !reversed_by && !((qc_intake_id \|\| po_closed) && kind==='receipt')` | `materialHistoryDialog()` |
| Create SKU | `$('new-product').hidden = user.role !== 'admin'` | `showProducts()` |
| Empty-catalog SKU CTA | `user.role === 'admin'` | `paintProducts()` |
| BOM write | `user.role === 'admin'` | `bomDialog()` |
| Mapping write / unmap | `user.role === 'admin'` | `productMappingDialog()` |

Reading — master bahan, batch history, traceability, BOM, mapping and both histories — stays open to
every authenticated role. All three roles (admin, operator, viewer) are exercised in the browser
module against both workspaces.

---

## 14. Stale guards

| Guard | Preserved |
|---|---|
| `epoch` | both loaders, every dialog |
| `materialsRequest` / `productsRequest` | both loaders, bumped by `invalidate()` on navigation |
| `view !== 'materials'` / `'products'` | both loaders, success and failure paths |
| `materialsQuery` | the *rendered* filter, not the latest requested |
| `dialogVersion` | every migrated dialog |
| `$('dialog').open` | every migrated dialog |
| `guardPending()` | every migrated dialog entry point |

The shared dialog lifecycle is untouched: `openDialog()`, `formDialog()`, `modalBusy`, the animated
close guard, inert-on-close and focus return. No sheet system, no second modal element, no popover —
there is still exactly one `showModal()` call in the file.

The browser module proves the workspace guard behaviourally: it holds a `/api/material-batches`
response, navigates to Produksi while it is in flight, releases it, and asserts the materials
workspace does not resurrect.

---

## 15. Responsive strategy

| Width | Bahan baku | Master SKU |
|---|---|---|
| 1440 | heading, actions, filter bar, note, and nine batch rows in the first viewport | heading, search, count, and the catalog |
| 1024 | tighter A6 rhythm | unchanged composition |
| 980 | surface takes `overflow-x:auto`, table floored at `56rem`; touch targets restored to 44px | reflow begins |
| 768 | internal horizontal scroll, identifiers intact | rows still one line per fact |
| 390 | actions wrap, command bar stacks, surface scrolls internally | rows wrap, actions move to their own line |
| 320 | same, deliberately | same |
| 320 @ 200% | no document overflow, no one-character wrapping | mapping state still visible |

**The deliberate choice at phone width.** Bahan baku stays tabular and hands overflow to its own
surface; Master SKU reflows and never scrolls sideways. That difference is the point: the batch list
is a genuine table whose value is the aligned columns, and converting it to stacked cards in CSS
would have meant losing table semantics and maintaining a second layout. The SKU catalog is not a
table at all, so it simply wraps. Both use one renderer and one business path — there is no mobile
code path anywhere in this phase.

The table floor is in `rem`, not `px`, so at 200% text the columns grow with the text instead of
re-crushing at twice the size. The browser module measures the rendered width of the batch reference
and of the SKU at 320 @ 200% and asserts neither collapsed.

---

## 16. Accessibility

* Real heading structure: one `workspace-title` per page, `workspace-section-title` for sections,
  and `aria-labelledby` on both grouping sections.
* A real `<table>` with `<thead class="data-header">` and `scope="col"` on every batch column,
  including a `visually-hidden` header for the open-batch column.
* Every migrated form control is a labelled `.field` with explicit `for`/`id`. Every accessible name
  that an existing test or an operator relies on is unchanged.
* The search input keeps a `visually-hidden` label *and* an `aria-label`, and the material filter
  keeps an `aria-label` plus `aria-describedby` pointing at the inventory explanation.
* Opening a batch is a real `<button>` whose accessible name is the reference; the chevron is
  `aria-hidden`. No mouse-only rows.
* Per-SKU actions keep disambiguated names (`Jubelio {sku}`, `BOM {sku}`).
* Status is never colour alone: every `status-chip` carries a `status-dot` in `currentColor`, and
  every quantity is labelled by its column header.
* `role="status"` on both state hosts and `role="alert"` on every dialog error is unchanged.
* `focus-visible` comes from A6.0; the 980px touch floor is restored for both pages.

---

## 17. Light, dark, reduced transparency, forced colours, reduced motion

Both workspaces are theme-attribute driven only — A6.2 adds no `prefers-color-scheme` rule and no
colour of its own. Light keeps the scenic environment visible between near-opaque data surfaces,
with the command bar as the only restrained glass element (A6.0's single `backdrop-filter` site).
Dark is tuned rather than inverted, and quantities and chips stay legible; batch and SKU rows are
**not** glass panes, and no repeated row is a backdrop root.

`prefers-reduced-transparency` uses A6.0's fallback unchanged — it only ever withdraws the
enhancement, with no functional difference. `forced-colors` is exercised in the browser module at
1440 for both pages: no layout break, rows still visible, and the chip's `status-dot` survives as
the non-colour channel. `prefers-reduced-motion` is asserted to leave no replacement class behind.

No new motion system, no row stagger, no card cascade, no ambient animation. A6.2's CSS block
contains no `@keyframes`, no `animation:` and no `transition:` — asserted.

---

## 18. Performance

* No new API fan-out. Bahan baku is two requests per page load (materials + batches), Master SKU is
  two paged reads. **No BOM is ever fetched to render the catalog.**
* The batch detail shows more real fields than before using the response it already had.
* No new polling, no `requestAnimationFrame`, no `setInterval`, no `requestIdleCallback`, no
  `setTimeout` — the contract test asserts all five against every migrated renderer.
* Repeated surfaces stay cheap: no `backdrop-filter` on a row, cell, chip, timeline item or detail
  field, so there is no nested moving blur.

---

## 19. Screenshots

Deterministic local artefacts from `tests/browser_materials_master_sku_modern.cjs`. Following the
A6.1 convention they are written to `$BEELOFT_QA_SCREENSHOTS` (the runner's temporary directory by
default) and are **not committed**. Each is captured with the toast hidden, focus cleared, the
scroll region reset and — for dialogs — the M3 enter animation awaited to completion.

| File | Case |
|---|---|
| `a62-batch-list-1440-light-firstviewport.png` | Bahan baku, exactly what a 1440×1000 reviewer sees before scrolling |
| `a62-batch-list-1440-light.png` / `-dark.png` | Bahan baku, 1440, populated, both themes |
| `a62-batch-list-1024-light.png` / `-768-light.png` / `-390-light.png` | responsive |
| `a62-batch-list-320-light-200.png` / `-320-dark-200.png` | 320 at 200% text, both themes |
| `a62-batch-list-1440-light-filtered.png` | a material filter applied |
| `a62-batch-list-1440-light-empty.png` | empty page with the role-gated CTA |
| `a62-batch-list-1440-light-error.png` | load failure |
| `a62-batch-list-1440-forced-colors.png` | forced colours |
| `a62-batch-detail-1440-light.png` / `-dark.png` | batch detail, position, label and timeline |
| `a62-batch-detail-1440-light-viewer.png` | viewer: no correction action |
| `a62-traceability-1440-light.png` | full production lineage |
| `a62-master-bahan-1440-light.png` | material master list |
| `a62-master-bahan-form-1440-light.png` | Tambah bahan |
| `a62-receive-batch-form-1440-light.png` / `-dark.png` / `-390-light.png` | Terima batch bahan |
| `a62-scan-batch-1440-light.png` | batch scanner |
| `a62-catalog-1440-light-firstviewport.png` | Master SKU first viewport |
| `a62-catalog-1440-light.png` / `-dark.png` | Master SKU, 1440, both themes |
| `a62-catalog-1024-light.png` / `-768-light.png` / `-390-light.png` | responsive |
| `a62-catalog-320-light-200.png` / `-320-dark-200.png` | 320 at 200% text |
| `a62-catalog-1440-light-no-match.png` | search matched nothing |
| `a62-catalog-1440-light-empty.png` | catalog genuinely empty |
| `a62-catalog-1440-light-error.png` | load failure with retry |
| `a62-catalog-1440-forced-colors.png` | forced colours |
| `a62-add-sku-form-1440-light.png` | Tambah SKU |
| `a62-bom-empty-1440-light.png` | BOM belum diisi |
| `a62-bom-populated-1440-light.png` / `-dark.png` | BOM with a revision |
| `a62-bom-form-1440-light.png` | Susun BOM |
| `a62-bom-history-1440-light.png` | BOM revision history |
| `a62-mapping-unmapped-1440-light.png` / `-dark.png` | unmapped |
| `a62-mapping-mapped-1440-light.png` / `-dark.png` | mapped |
| `a62-mapping-history-1440-light.png` | mapping revision history |
| `a62-mapping-1440-light-viewer.png` | viewer: no mapping write actions |
| `a62-order-material-history-1440-light.png` | **A6.1 regression** — the order mode of the shared renderer |

---

## 20. Tests

**`tests/test_apple27_materials_master_sku_contract.py`** — 71 static assertions: the primitives are
consumed, the legacy page vocabulary is gone from these two pages but kept in the stylesheet, the two
grammars are genuinely different, no metric strip and no invented batch status, the three quantities
are unaltered, the filter/pagination/request contract is byte-identical, search is local with all
four values, the catalog costs two requests with no BOM fan-out, mapping never claims sync, BOM keeps
every rule, every permission gate and every stale guard survives, the CSS block is contained and
redefines no primitive, the table floor is rem-based, A6.1 and the A5 shell are untouched, no new
timer, and the version/schema/route contract holds.

**`tests/browser_materials_master_sku_modern.cjs`** — the behavioural half, registered in
`tests/browser_smoke.cjs` after the A6.1 module. Every visual case also asserts data or behaviour.

### Existing tests updated, and why

| File | Change | Reason |
|---|---|---|
| `test_apple27_modern_workspace_foundation_contract.py` | `MIGRATED_SECTIONS` += the two views; `MIGRATED_RENDERERS` += 19 named renderers | the deliberate, narrow widening each phase performs; still an enumeration, so an unrelated workspace or dialog that migrates by accident still fails |
| `test_apple27_production_workspace_contract.py` | `A61_BLOCK` slice bounded by the A6.2 marker; version pin | keeps "contained to Produksi" meaning what it meant, instead of widening its allow-list |
| `test_apple27_liquid_lens_contract.py` | version pin | `0.108.0` |
| `browser_navigation_foundation.cjs` | headings `Bahan baku` / `Master SKU`; content `#product-list .record-row` | the headings are the intended change; the catalog row is a record row now |
| `browser_smoke.cjs` | heading `Master SKU`; `#product-list .record-row`; new module registered | same |
| `browser_motion_dialogs.cjs` | heading `Master SKU` | same |
| `browser_materials.cjs` | `#batch-list [data-batch-balance]` | the balance is a labelled table cell, not a display-sized legacy figure |
| `browser_bom.cjs` | `/BOM belum diisi/` | the empty state is now a title + copy pair |
| `browser_product_external_mappings.cjs` | three assertions scoped to `#dialog` | the catalog row now states the mapping truth too, so those assertions have to say which surface they mean |
| `browser_reservations.cjs` | `Batch bahan` label lookup scoped to `#dialog`; the reservation figure read from `[data-batch-reserved]` | the page now has a `Batch bahan` **region** (from `aria-labelledby` on the grouping section) as well as the dialog's `Batch bahan` select, and the reservation is a labelled table cell rather than a `Direservasi 5 m` run of text inside a hint paragraph |
| `browser_functional_glass.cjs` | the filtered-surface count became "at least one, and every one is the bounded blur" | the assertion pinned `=== 1`, which was the *number of migrated pages* rather than a property of the glass contract. A6.1 made it 1 and A6.2 makes it 3; leaving the literal would have turned "no business surface is filtered" into "only one page may ever migrate". The real guarantee — `seen` is empty, and each command bar filters its backdrop and never its own content — is now what is asserted |

---

## 21. Remaining legacy surfaces

Not modernised in A6.2, by design:

* **People** (`#people-view`) and the two dedicated scan workspaces (`#bundle-scan-view`,
  `#finished-goods-scan-view`) — A6.3 owns these.
* **Command center**, **Analytics** (all thirteen destinations), **Tanya Beeloft**, **Integrasi**,
  **Aktivitas**, **Audit trail**, **Cadangan data**, **Inbox approval**, **Permintaan pembelian**,
  **Budget marketing**.
* **Produksi's child dialogs** — including `materialIssueForm` (*Keluarkan bahan ke order*),
  `requirementsDialog` (*Kebutuhan bahan*), cutting, bundles, handoffs, sewing, finishing, final QC,
  rework and finished-goods dialogs. A6.1 deliberately did not migrate them and A6.2 did not either.
* **Purchasing and supplier dialogs** — PO, receipts, incoming QC, supplier returns and payments —
  even where they open the batch dialog A6.2 modernised.
* **`formDialog()`'s own shell** — it still emits legacy `.form-info`, `.form-grid` and
  `.form-actions` around the A6 `.field` bodies A6.2 passes into it, exactly as A6.1 left it. The
  dialog shell is a shared surface and migrating it is its own phase.
* **Inert CSS debt** — `.material-balance` and `#batch-list .sku-block` now render nowhere but are
  intentionally left in `style.css` (§12).
