# Apple-27 · A6.3 — People + Scan workflows modern workspaces

A6.0 built the shared inner-workspace language, A6.1 spent it on Produksi, A6.2 on the two
master-data workspaces. A6.3 spends it on three **workflow** surfaces, each with its own job:

- **People** — the daily roster. Who is active, who has no record yet, who is present, on leave or
  absent, and who worked overtime.
- **Scan bundle** — a high-focus utility that turns a bundle label into bundle identity.
- **Scan barang jadi** — the same utility for finished-goods receipts.

The three deliberately do **not** look alike, and none of them became a Command Center clone, a KPI
dashboard, a generic admin form, or a copy of Produksi or Bahan baku. This document records what
was decided, what was preserved, and what was left alone.

## 1. Exact baseline

| | |
|---|---|
| Baseline `main` | `c7f296a52fa7f97645a959726f339c941a7e97c4` |
| Post-merge CI for that exact SHA | run #163, `completed` / `success` |
| Branch | `ui/apple27-a6-3-people-scan-workflows` |
| Version | `0.108.0` → **`0.109.0`** |
| Schema | `PRAGMA user_version = 55`, unchanged — no migration |
| OpenAPI structural diff | `info.version` only |
| Predecessors | A6.0, A6.1, A6.2 merged and human-approved; A5.2 shell and A5.3 lens frozen |

No backend file changed. No route was added, no response field was invented, and nothing in
`beeloft/*.sql` was touched.

## 2. A6.0 primitives consumed

People uses `workspace-page`, `workspace-heading`/`-copy`, `workspace-title`, `workspace-subtitle`,
`workspace-actions`, `metric-strip`/`metric-card`/`metric-icon`/`metric-label`/`metric-value`/
`metric-unit`, `command-bar`/`command-filters`/`command-filter`/`command-search`/`command-actions`,
`info-panel`, `workspace-subhead`, `workspace-section-title`, `workspace-meta`, `record-list`/
`record-row`/`record-row-copy`/`record-row-aside`, `data-primary`/`data-secondary`/`data-meta`,
`chip-row`/`status-chip`/`status-dot`, `empty-state`, `error-state`, `loading-state`, `timeline`
and its parts, `detail-grid`/`detail-field`, `utility-panel`, `action-row`, and the field grammar
(`field`, `field-label`, `field-wide`, `field-help`, `field-actions`).

The two scanners are the phase that finally **spends the scan-surface family A6.0 reserved for
A6.3**: `scan-surface`, `scan-target`, `scan-state` and `scan-recent`. A6.0's banner said what was
settled there was "the shape: one large focused input region, the current state beside it, a recent
result area and a manual fallback"; that is exactly the shape shipped here. `.scan-fallback` is the
one member left unused — these two scanners have no separate manual-entry fallback, because the
single field *is* the manual entry.

### Primitives deliberately not used

- **No `metric-strip` on either scanner.** A scanner answers "what should I scan?" and "what did the
  scan return?". Neither endpoint returns an aggregate, and a scan count would have been invented.
- **No `data-surface` anywhere in A6.3.** None of these three surfaces is tabular. People is a list
  of people; a scan result is a single record; inventory is three-to-five rows.
- **No `progress-meter`.** Bundle allocation is two counts, not a percentage.
- **No `segmented-filter`/`filter-chip`.** The roster filter is a deliberate submitted query, and
  chips would have implied instant re-filtering.

### The one shared helper A6.3 added

`workforceField()`, `workforceSelect()` and `workforceFact()` in `app.mjs` compose the A6 field
grammar for the People forms. They exist because the legacy `field()` helper emits a *wrapping*
label, and A6's `.field` needs an explicit `<label for>` + control pair. Every accessible name is
byte-identical to the wrapping label it replaced — that is the whole point, and it is why the
existing browser contract still resolves every `getByLabel`. Ids are prefixed `wf-` so a dialog
control can never collide with a roster control on the page underneath. The reason textarea reuses
A6.2's existing `reasonField()` rather than adding a fourth helper.

## 3. People hierarchy

```
People                                    ← workspace identity
Pantau kehadiran, jam kerja, lembur, dan status tim.
                    [Daftar karyawan] [Permintaan cuti / lembur] [Tambah karyawan]

Karyawan aktif · Belum dicatat · Hadir · Cuti · Absen · Lembur     ← the daily state

[ Tanggal ][ Status ▾ ][ 🔍 kode / nama / departemen ][ Tampilkan roster ]

Karyawan aktif yang belum memiliki catatan tetap ditampilkan. …    ← the load-bearing note

Roster harian                                     6 dari 8 karyawan aktif

  Rina Wulandari
  EMP-021 · Produksi
  ● Hadir
  08:00–17:00 · kerja 8 j · lembur 1 j        [Koreksi kehadiran] [Riwayat]
```

The roster is the visual centre. The summary sits **above** the command bar and the roster below it,
so the first viewport at 1440 shows identity, the daily state, the controls and several real rows —
not half a screen of metrics.

### Action hierarchy

`Tambah karyawan` is the primary action and stays admin-only (`new-employee.hidden =
user.role !== 'admin'`, in JS, never in CSS). `Permintaan cuti / lembur` is secondary — it is a real
workflow, but not the page's purpose. `Daftar karyawan` is quiet: it opens master data.

## 4. Workforce data mapping

Both sources are preserved exactly, and `workforcePage()` still walks **every** page rather than
reading one:

```js
page = await api.get(path + '?' + new URLSearchParams({...params, limit: 500, offset: items.length}));
items.push(...page.items);
while (page.items.length && items.length < page.total);
```

| Source | Request |
|---|---|
| employees | `workforcePage('/api/workforce/employees', {status: 'active', q})` |
| attendance | `workforcePage('/api/workforce/attendance', {start_date: work_date, end_date: work_date, status: 'all', q})` |

The two are joined on `attendance.employee_id`, employees drive the row list, and a missing
attendance record is `null` rather than a skipped row — which is what keeps an unrecorded employee
visible.

## 5. Summary semantics

Six cells, because they describe **one** daily roster state rather than six KPIs:

| Cell | Value | Glyph | Tone |
|---|---|---|---|
| Karyawan aktif | `rows.length` | `users` | info |
| Belum dicatat | `rows.length - recorded.length` | `clipboard` | warning when > 0 |
| Hadir | `attendance.status === 'present'` | `check-circle` | success |
| Cuti | `attendance.status === 'leave'` | `external` | info |
| Absen | `attendance.status === 'absent'` | `alert-triangle` | warning when > 0 |
| Lembur | `SUM(overtime_minutes)` over recorded rows | `clock` | neutral |

All six are computed from **every matching active employee**, not from the rows that survive the
status filter. Narrowing the roster to "Absen" therefore does not change the daily truth above it.
Tone appears only when the number actually demands action today; the rest stay neutral.

Nothing else is derived. There is no productivity score, no attendance health, no average
performance, no shift-adherence percentage, no absence or overtime trend. `Roster harian` carries one
extra line — `6 dari 8 karyawan aktif` — and both numbers are counts that already existed.

## 6. Roster filtering

The filter is a **submitted** query, not a live one. `Tampilkan roster` is visible and is the only
thing that issues a request; there is no `oninput` handler and no debounce anywhere near the roster.

- `workforceFilters.work_date` defaults to `jakartaToday()`, and the date input's `max` is
  `jakartaToday()` — a future attendance date stays unreachable.
- Status values are exactly `all`, `unrecorded`, `present`, `leave`, `absent`, labelled
  `Semua status`, `Belum dicatat`, `Hadir`, `Cuti`, `Absen`.
- Filtering still happens **after** the join, and the attendance request still sends `status: 'all'`.
  Sending the roster status to the API instead would change what "Belum dicatat" means:

```js
const filtered = rows.filter(row => params.status === 'all' ? (true)
  : params.status === 'unrecorded' ? !row.attendance
  : row.attendance?.status === params.status);
```

`Reset filter` (offered from the filtered-empty state) resets **status and search only**. It
deliberately leaves `work_date` alone, because the request it answers is "show me the whole roster
for that day", not "take me back to today".

### States

| State | Treatment |
|---|---|
| Loading | `pageState('workforce-message', 'loading', 'Memuat roster karyawan…')` |
| Filtered miss (active employees exist) | `Tidak ada karyawan yang cocok dengan status dan pencarian ini.` + quiet `Reset filter` |
| Search miss (no active employee matches `q`) | `Tidak ada karyawan aktif yang cocok dengan pencarian ini.` + `Reset filter` |
| Genuinely empty | `Belum ada karyawan aktif.` + admin-only `Tambah karyawan pertama` |
| Error | `Roster karyawan gagal dimuat.` + the server message + `Coba lagi` → `loadPeople` |

Three different absences, and none of them claims to be another. The first two never say there are
no employees globally.

## 7. Attendance revision behaviour

One attendance record per employee per date. A correction stores a **new revision**; older revisions
stay intact and stay visible in the history. The form preserves every rule:

- `work_date` is `readonly`, preset from the row's `data-date`.
- `expected_revision: current?.revision || 0` — `0` for a brand-new record, so optimistic
  concurrency is never lost.
- `present` is the only status that enables the clock fields. Otherwise `clock_in`, `clock_out` and
  `overtime_minutes` are each `disabled`, not `required`, and cleared to `''`/`''`/`'0'`. The
  collector independently forces `null`/`null`/`0`, so a stale DOM value cannot leak into a payload.
- New records still default to `08:00` and `17:00`.
- `Catatan` keeps that exact label. An "optional" marker inside the label would have changed the
  accessible name, which is a contract; optionality is expressed by the absence of `required`.

Both histories are A6 timelines at `limit=100`, one item per revision, collapsing nothing, and both
still say `Menampilkan 100 revisi terbaru.` when the server reports more. No pagination was invented
that the shipped dialogs never had.

## 8. Employee master behaviour

`workforceEmployeeMasterDialog()` is a compact master-data record list — not a card grid — over
`/api/workforce/employees?status=all`. Each row keeps code, name, department, active state (as a
chip) and revision (as quiet context). `Ubah` stays admin-only, `Riwayat` stays available to every
allowed role, and `Kembali ke roster` is preserved.

The employee code rule is stated in both directions: creation says `Kode dinormalisasi menjadi huruf
besar dan tidak dapat dipakai ulang.`, and editing renders the code as an unfocusable **fact** with
`Kode karyawan tidak dapat diubah.` — there is no code-edit path to find. Edits carry
`expected_revision: employee.revision` plus name, department, active and reason. Limits are
unchanged: code 40, name 160, department 160, reason 1000.

## 9. Leave / overtime workflow and the approval distinction

`workforceRequestsDialog()` is a focused workflow workspace: an identity row, one A6 command bar
(status / kind / search with an explicit `Tampilkan permintaan`), the five real API summary figures
(`total`, `summary.submitted`, `summary.approved`, `summary.leave`, `summary.overtime`), and a record
list. Filters still go straight to the server, and the dialog keeps its own `generation` counter so a
slow response cannot repaint a newer one.

The load-bearing distinction is stated three times, because it is the thing that is easiest to
misread:

- the requests dialog: *Approval memberi izin; kehadiran aktual tetap dicatat terpisah di roster.*
- the request form: *Permintaan masuk ke inbox approval. Persetujuan tidak otomatis mencatat
  kehadiran aktual.*
- the request detail: *Approval memberi izin. Persetujuan tidak otomatis mencatat kehadiran aktual;
  kehadiran tetap dicatat di roster.*

The form still refuses to render without active employees (`Tambahkan karyawan aktif sebelum
membuat permintaan.`), and the overtime coupling is unchanged: `end_date` becomes `readOnly` and
mirrors `start_date`, and `overtime_minutes` becomes enabled and required. Leave keeps an editable
range.

The detail keeps `reference · status` as **one text node** — it is the sentence an operator comes
back for — alongside a status chip, the employee, the department, the active/inactive fact, kind,
dates, days, overtime, reason, actor, timestamp and the full decision timeline.

### Decision permissions

| Role | Condition | Actions |
|---|---|---|
| admin | `status === 'submitted'` | `Setujui`, `Tolak` |
| operator | `status === 'submitted' && user.id === item.actor_id` | `Batalkan` |
| viewer | — | none |

Unchanged, including the fact that an admin cannot cancel and an operator can only cancel their own.
Decisions still POST to `/api/workforce/requests/{id}/decisions` with
`expected_revision: item.revision` and a required reason, and still say *Keputusan tersimpan
permanen di riwayat approval.*

## 10. Scanner hierarchy and lifecycle

```
Scan bundle
Pindai label bundle untuk membuka identitas dan statusnya.

┌ scan-surface ───────────────────────────────────────────┐
│  Kode bundle                                            │
│  ┌ scan-target ─────────────────────────────────────┐   │
│  │ [ Bundle ID …………………………………………………… ]   │   │
│  └──────────────────────────────────────────────────┘   │
│  ⓘ Scanner USB/Bluetooth bekerja seperti keyboard, …    │
│                                        [ Buka bundle ]  │
└─────────────────────────────────────────────────────────┘

Hasil scan terakhir
  ● BDL-000123
    SKU-ABC · M
    Jumlah 5 pcs    Order ORD-77          [ Rincian bundle ]
```

The input is the page. The surface is bounded (`max-width: 44rem` on desktop, full width on a phone)
so the eye lands on the field rather than on a decorative illustration, and the instruction sits
directly beneath the input where it is read.

### Hardware semantics — unchanged

A USB/Bluetooth scanner types like a keyboard, the user may type manually, and Enter submits. Both
inputs keep every attribute: `name="code"`, `type="search"`, `required`, `maxlength="200"`,
`autocomplete="off"`, `autocapitalize="characters"`, `spellcheck="false"`. No camera scanning, no
barcode permission, no WebRTC, no new scanning library was introduced.

### Endpoints — unchanged

| Scanner | Request |
|---|---|
| bundle | `GET /api/bundles/scan?code=<trimmed>` |
| finished goods | `GET /api/finished-goods-receipts/scan?code=<trimmed>` |

Still GET, still one query parameter, no background prefetch.

### Autofocus

`showScanner(kind)` reads `document.body.classList.contains('nav-open')` **before** calling
`activateWorkspace`, because activation is what closes the drawer. The input is focused only when the
drawer was closed; on mobile the heading keeps focus so the drawer-close announcement is not stolen.

### Stale-scan protection

One shared `scanRequest` generation protects both scanners:

```js
let request = ++scanRequest;
const current = () => version === epoch && request === scanRequest && view === prefix;
```

`current()` is re-checked before painting, in the catch and in the finally, and `scanRequest` is
bumped again at submit time — so a slow first response can never repaint after a second scan.

### Submission lifecycle

`preventDefault` → reject if `!current()`, if the submit button is already disabled, or if
`guardPending()` → `++scanRequest` → disable submit → `clearScanFeedback(result)` →
`result.replaceChildren()` → clear the error → `Mencari hasil scan…` → request. Clearing the previous
result *before* the request is what stops a failed scan from leaving a stale result looking current.

### Scan feedback

`playScanFeedback(result)` and the one `SCAN_TINT_HOLD` (1200 ms) timer A6.0 shipped. Nothing was
duplicated, no new timer or animation frame was added, and the tint stays state rather than
decoration — it survives reduced motion and only its release is animated.

The tint lives on the `.scan-result` host, so **nothing rendered inside it carries an opaque
background**. The result row explicitly drops the record list's surface, divider and hover repaint;
otherwise the only feedback a scanner gives would be painted over.

### Success, failure, and the empty state

| Outcome | Behaviour |
|---|---|
| Success | tint, one result record, message cleared, `input.select()` so the next scan overwrites |
| Failure | message cleared, `fail(error, prefix + '-error')`, `input.select()`, submit re-enabled |
| Initial | `Belum ada hasil scan. Pindai label atau masukkan kode.` as a quiet `.scan-state` row |

Only the last result is shown. There is no fabricated recent-scan history and nothing is stored
client-side — no `localStorage`, no `sessionStorage`, no in-memory list.

The result states only what the scan endpoint returns: `reference`, `sku`, `size`,
`quantity`/`received_quantity`, `order_reference`, and the action that opens the detail. No status is
fabricated at scan-result level.

## 11. Bundle detail hierarchy

`bundleDialog()` is modernised because it is the direct destination of Scan bundle.

1. **Identity** — reference, `N pcs · SKU · size`, product · colour, and a status chip that is still
   binary: `active` → `Aktif`, anything else → `Sudah dikoreksi`.
2. **Posisi bundle sekarang** — `sewing_allocated_quantity` and `sewing_unassigned_quantity` as two
   plain numbers (no invented percentage), `custody_location`, and — only when `pending_handoff`
   exists — an info-toned attention note reading `Menuju <location>` /
   `Serah-terima belum selesai, menunggu penerima mengonfirmasi.` A pending handoff is never
   presented as a completed transfer.
3. **Asal bundle** — cutting reference, batch reference, material code.
4. **Reason, actor, timestamp.**
5. **Reversal**, when present — reason, actor, timestamp under a restrained `Sudah dikoreksi` heading.
6. **QR label** — unchanged markup, unchanged `/api/bundles/{id}/label.svg`, and still a direct child
   of `#dialog-content` so the print stylesheet still reaches it.
7. **Actions**, grouped last.

### Action grouping

Of twelve actions, seven only *open* something. Those became quiet utility rows with a chevron —
A6.1's own grammar, reused, not reinvented. Only genuine commands stay button-shaped, and correction
is the one destructive weight.

| Group | Rows (navigation) | Commands |
|---|---|---|
| Konteks & asal | Buka order produksi, Hasil cutting asal, Batch bahan asal, Semua bundle, Sewing / makloon order | — |
| Alur sewing | — | Kirim ke sewing |
| Custody & serah-terima | Riwayat serah-terima | Serahkan bundle, Konfirmasi terima, Batalkan handoff |
| Utilitas & koreksi | — | Cetak label, **Koreksi bundle** (destructive) |

No action was removed, no `data-action` value or id was renamed, and no menu or popover architecture
was introduced.

### Correction meaning

*Koreksi melepaskan alokasi identitas bundle. Posisi WIP tidak berubah dan riwayat asli tetap
tersimpan.* The correction form itself keeps the shared `formDialog` shell, deliberately, to avoid a
scope explosion.

## 12. Finished-goods detail hierarchy

`finishedGoodsReceiptDialog()` is modernised for the same reason.

1. **Identity** — reference, `N pcs · SKU · size`, status chip (`Aktif` / `Sudah dikoreksi`).
2. **Inventori sekarang** — placed **above** the action catalogue, because the first question in a
   warehouse is how much is there and whether it may be sold, not what is clickable.
3. **Sumber penerimaan** — initial location, received date, scanned SKU.
4. **Jejak produksi** — Final QC, Finishing, Sewing, Bundle.
5. **Reason, actor, timestamp.**
6. **Blocking conditions** — every count that is greater than zero, as a compact attention note.
7. **Reversal**, when present.
8. **QR label** — unchanged markup and endpoint.
9. **Actions**, grouped last.

### Inventory truth

`sellable`, `hold` and `damaged` keep their own words (rendered through the existing shared
`warehouseStatus` map, so they read identically to the traceability dialog) and are never renamed
into ambiguous marketing language. For a sellable row, `quantity`, `available_quantity` and
`reserved_quantity` stay **three separate, separately labelled figures** — merging them would erase
the difference between stock that exists and stock that can still be promised. Tones are
`sellable` → success, `hold` → warning, `damaged` → danger. When the receipt holds nothing, the
shipped sentence survives: `Stok penerimaan ini sudah dilepaskan.`

### Blocking conditions

`active_movement_count`, `active_reservation_count`, `active_adjustment_count` and
`active_stock_count_count` are all still shown with their real numbers and their real advice. They
are the explanation for why `Koreksi penerimaan` is unavailable, so hiding them would hide the cause.

### Action grouping

| Group | Rows (navigation) | Commands |
|---|---|---|
| Jejak & asal | Jejak stok lengkap, Buka order produksi, Final QC asal, Finishing asal, Job sewing asal, Bundle asal, Semua barang jadi | — |
| Gudang & stok | Gudang order, Riwayat adjustment, Riwayat stock opname | Catat stock opname, Catat adjustment, Transfer lokasi, Lepaskan hold, Tandai damaged |
| Marketplace | Reservasi order | Reservasi marketplace |
| Utilitas & koreksi | — | Cetak label barang jadi, **Koreksi penerimaan** (destructive) |

All nineteen actions survive with their `data-action`, their `data-kind`
(`transfer` / `hold_release` / `hold_damage`) and their ids.

### Correction meaning

*Koreksi melepaskan klasifikasi sellable/hold tanpa mengubah saldo WIP warehouse. Riwayat asli tetap
tersimpan.*

## 13. Permissions

Every gate is the same `user.role` comparison in JavaScript that shipped. None moved to CSS, and the
A6.3 CSS block contains no role name at all.

**People** — `Tambah karyawan`: admin. Attendance record/correct: non-viewer. `Riwayat`: every role.
Requests: `Ajukan permintaan` non-viewer; approve/reject admin + submitted; cancel operator +
submitted + own; viewer gains nothing.

**Bundle detail** — handoff creation: non-viewer + active + no pending handoff. Accept: non-viewer +
pending handoff + `sender_id !== user.id`. Cancel handoff: admin + pending handoff. New sewing job:
non-viewer + active + `sewing_unassigned_quantity > 0`. Reverse: admin + active.

**Finished-goods detail** — stock count and adjustment: non-viewer + active. Marketplace reservation:
non-viewer + active + reservable (some sellable row with `available_quantity > 0`). Transfer:
non-viewer + active + at least one sellable/hold/damaged row. Hold release and mark damaged:
non-viewer + active + hold exists. Receipt reversal: admin + active + **all four** blocking counts
zero.

## 14. Stale guards

| Surface | Guard |
|---|---|
| People | `version === epoch && request === peopleRequest && view === 'people'`, re-checked in the catch |
| People dialogs | `epoch` + `dialogVersion` + `$('dialog').open` |
| Requests dialog | the above plus its own `generation` counter |
| Both scanners | one shared `version === epoch && request === scanRequest && view === prefix` |

`workforceRendered` still holds the JSON of the last rendered filter set, and the replacement fade
plays only when a previous render existed **and** the filter changed — re-entering People with the
same filters is still a first render and still does not fade.

## 15. CSS containment

A third containment block was appended to `style.css`, scoped exactly like its two predecessors. Its
first selector is the marker the A6.2 contract now bounds itself against:

```css
#people-view,#bundle-scan-view,#finished-goods-scan-view{max-width:1360px;margin-inline:auto}
```

It contains only what a shared primitive must not own: the bounded column, `.people-work`'s stacking
rhythm, the withdrawal of the legacy `.state` card from the four message hosts, an A6 danger
treatment for the two scan error hosts (`fail()` writes `textContent`, so this has to live in CSS),
the info-panel withdrawal for the revision note, `h3` resets on the two record lists, the master
list's own scroll, the scanner's bounded measure, the result row's background/hover withdrawal that
protects the scan tint, the `#dialog-content .utility-rows` element resets, the narrow-width touch
floor, and two phone-width adjustments.

`#dialog-content .utility-rows` is the one selector not scoped to an id of A6.3's own. It is safe for
a structural reason rather than a stylistic one: an unmigrated dialog cannot be reached by it,
because emitting `.utility-rows` at all is precisely what the A6.0 containment test forbids outside
the migrated renderers.

### Legacy vocabulary audit

Audited and **left intact**, because other surfaces still render them: `.page-heading` (eleven other
pages), `.filters` (Aktivitas), `.filter-form`, `.form-info`, `.form-grid`, `.form-actions` (every
`formDialog`), `.search-field`, `.hint`, `.product-list`, `.product-item` (the capacity-plan dialog),
`.history-item` (Aktivitas and a purchasing detail), `.material-event` (production and warehouse
child dialogs), `.scan-result` (the tint host on these very pages), `.bundle-label` (both result
dialogs plus the print stylesheet), `.list-host`, `.state`.

Four selectors A6.3 stops emitting entirely — `.workforce-summary`, `.workforce-row`,
`.workforce-row-actions`, `.workforce-heading` — were **left in place** rather than deleted, per
A6.1's documented rule that inert legacy CSS is removed by the phase that can prove the removal safe
on its own, not opportunistically by the next migration.

`.workforce-screen` is **kept and still rendered five times**: it is the only thing making a People
dialog 960px wide, and the approvals overflow assertions depend on it.

## 16. A6.0 migration contract, narrowed

`MIGRATED_SECTIONS` gained `people-view`, `bundle-scan-view`, `finished-goods-scan-view`.
`MIGRATED_RENDERERS` gained exactly sixteen names: the three field helpers, `loadPeople`, the nine
People dialog renderers, `showScanner`, `bundleDialog`, `finishedGoodsReceiptDialog`.

The nested workflows those two result dialogs launch are deliberately **not** on the list — sewing
forms, bundle handoff internals, handoff history, stock adjustment, stock opname, marketplace
reservation, warehouse movement forms, cutting, QC and finishing dialogs all still fail the
containment contract if they start emitting A6 markup. Their entry points are preserved; their
interiors remain legacy.

## 17. Responsive strategy

**People** — at 1440 the first viewport shows the heading, the six-cell strip, the command bar and
several roster rows. At 1024/768 the strip wraps deliberately (A6.0's `auto-fit` steps down through
190px → 168px → 140px tracks). At 390 the rows become stacked records and the row aside takes its own
line. At 320 with 200% text the strip drops to two explicit columns, because six 140px tracks cannot
hold their labels at that size without breaking a word per line.

**Scanners** — the surface is bounded to 44rem on desktop and full width at ≤650px. The scan field
keeps its 44px minimum and its 1.05rem tabular face at every width, the primary button is never
clipped, there is no horizontal document scroll, and the result stacks naturally.

Every control on all three pages keeps the product's 44px touch floor at ≤980px, restored explicitly
because A6's compact control height out-specifies the global bare-element rule.

## 18. Accessibility

- One `<h1>` per section; the employee name and the request employee stay real headings, because a
  roster row is a record about a person.
- The roster search keeps a `visually-hidden` label plus `aria-label`, and both it and the status
  select point at the revision note through `aria-describedby`.
- Both scan inputs keep an explicit `<label for>`; the hint is wired with `aria-describedby`.
- The summary is a real `<dl>` with `aria-label`; histories are real lists; the label sections keep
  their `aria-label`.
- Status is never carried by colour alone: every chip pairs a `status-dot` with a word, and the
  roster row additionally carries a state-specific glyph. Under `forced-colors` chips, buttons,
  records, timelines and the scan state all keep border and text channels.
- `prefers-reduced-transparency` falls back to A6.0's solid material with no behaviour change.
- Focus rings are A6.0's, pulled inside clipping surfaces where needed.

## 19. Reduced motion, material, performance

No new motion system. No roster stagger, no scan-card entrance, no ambient pulse, no scanner
animation loop. The existing scan-success tint remains, and the roster replacement fade keeps its
existing single-unit semantics.

No new `requestAnimationFrame`, no new `setTimeout`, no `setInterval`, no polling — the shipped
budget (6 / 7 / 0) is unchanged and asserted. No repeated backdrop filters on roster rows, summary
cells, scan results or dialog action rows; `.command-bar` remains the only blurred surface. No
external UI framework.

## 20. Screenshots

Twenty-one deterministic QA captures are produced by
`tests/browser_people_scan_modern_workspaces.cjs`, prefixed `a63-`:

People — `a63-people-1440-light`, `a63-people-1440-dark`, `a63-people-390`,
`a63-people-320-200`, `a63-people-filtered`, `a63-people-attendance-form`,
`a63-people-attendance-history`, `a63-people-employee-master`, `a63-people-employee-form`,
`a63-people-requests`, `a63-people-request-detail`.

Scan bundle — `a63-bundle-scan-1440-empty`, `a63-bundle-scan-1440-success`,
`a63-bundle-scan-1440-dark`, `a63-bundle-scan-390`, `a63-bundle-detail`.

Scan barang jadi — `a63-goods-scan-1440-empty`, `a63-goods-scan-1440-success`,
`a63-goods-scan-1440-dark`, `a63-goods-scan-390`, `a63-goods-detail`.

## 21. Tests

| File | Role |
|---|---|
| `tests/test_apple27_people_scan_workspaces_contract.py` | the static half: identity, truth, endpoints, revisions, permissions, both action sets, containment, frozen surfaces, version |
| `tests/browser_people_scan_modern_workspaces.cjs` | the behavioural half, and the screenshot source |
| `tests/test_apple27_modern_workspace_foundation_contract.py` | allow-list widened to the three sections and the sixteen renderers |
| `tests/test_apple27_materials_master_sku_contract.py` | A6.2's CSS slice re-bounded at the A6.3 marker |

### Existing tests updated, and why

| File | Change |
|---|---|
| `browser_workforce.cjs`, `browser_workforce_approvals.cjs`, `browser_shared_ui.cjs`, `browser_motion_workspace.cjs`, `browser_management_command_center.cjs` | the People page-ready signal is the new workspace title `People` instead of the retired slogan heading |
| `browser_navigation_foundation.cjs` | People's heading and its content selector (`#workforce-list .record-row`) |
| `browser_motion_consistency.cjs` | roster rows are `.record-row`; the `#workforce-list` class assertion is unchanged |
| `browser_shared_ui.cjs` | the roster filter radius is the command bar's control radius (10px), not the legacy toolbar's 20px |
| `browser_bundle_scanning.cjs` | custody is a labelled fact, so the `<dt>` carries no sentence colon; the location still keeps its own exact text node |

## 22. Remaining legacy surfaces

A6.3 modernised its three workspaces and the two dialogs they open. The following are **still
legacy** and are explicitly out of scope until their own phase:

- every nested workflow launched from the two result dialogs — sewing / makloon forms, bundle handoff
  creation and history internals, stock adjustment forms, stock opname, marketplace reservation,
  warehouse movement forms, cutting dialogs, QC dialogs, finishing dialogs, and traceability beyond
  the presentation already shared elsewhere;
- Analitik (A6.4), Tanya Beeloft and Integrasi (A6.5), Aktivitas / Audit trail / Cadangan data
  (A6.6), Permintaan pembelian / Budget marketing / Inbox approval (A6.7);
- Command center, which is frozen by its own golden contract.

Their entry points are preserved and their behaviour is untouched.

## 23. Deferred to A6.8

Known visual polish debt stays deferred: the A6.2 dark-surface refinements, cross-workspace spacing
reconciliation, and the eventual removal of the four now-inert `.workforce-*` legacy selectors once a
phase can prove that removal safe on its own.
