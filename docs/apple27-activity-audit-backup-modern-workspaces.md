# A6.6 — Aktivitas + Audit trail + Cadangan data modern workspaces

Baseline: `main` @ `6014cefaa57647a5bf927f1987b38fe9ab90bb94` (exact-main CI #169 green).
Version `0.112.0`. Schema `PRAGMA user_version = 55`, no migration. OpenAPI diff: `info.version` only.

A6.6 migrates `#activity-view`, `#audit-view` and `#backup-view` onto the A6.0 workspace primitives.
It is presentation-only: no route, schema, event generation, audit storage, redaction, backup
creation, CSV generation, pagination, permission or request-guard change. The three pages share
one visual language and deliberately keep three different compositions.

## Aktivitas — chronological report

- **Identity.** Title `Aktivitas`, subtitle “Telusuri catatan produksi dalam waktu Jakarta dan ekspor
  hasilnya.”, eyebrow `Laporan aktivitas · waktu Jakarta (WIB)`. The sidebar label is unchanged.
- **Hierarchy.** Command bar → “Ringkasan rentang” (compact 4-figure strip + range meta) → scope note →
  “Linimasa aktivitas” (the page's centre, on one surface) → load more.
- **Access.** Admin, operator and viewer (unchanged; no role check was added).
- **Timezone.** Business-day boundaries and every timestamp are `Asia/Jakarta`; the browser timezone
  never decides the day.
- **Initial load.** `loadActivity()` with empty inputs sends only `kind` + `limit=50`; the backend
  defaults to today in Jakarta and the returned `start_date`/`end_date` are written back.
- **Filters.** `#activity-day`, `#activity-end` (required, no `max`), `#activity-kind`
  (`all, movement, reversal, issue_opened, issue_resolved, order_created, order_changed`). Submit
  loads; `change` loads when `reportValidity()` passes; `input` immediately invalidates the visible
  report (request counter, query, cursor, rows, list, summary, count, range meta, load-more, export).
  The range must be ordered and < 366 days; the backend validates it.
- **Summary semantics.** The four returned values — events, warehouse net, issues opened, issues
  resolved — cover the whole range across **all** kinds; the backend computes them before the kind
  filter, and the timeline alone is kind-filtered. Warehouse net can be negative, is not current
  stock and is never tinted as an error.
- **Events.** One `timeline-item` per event, newest first, never regrouped: movement/reversal
  (`N pcs · From → To`), issue opened (`stage · PIC`), issue resolved (`stage · description`),
  order changed (both due-date and PIC changes), order created (no invented detail). Reference/title
  keep `data-action="detail"`. All business text is escaped.
- **Cursor.** 50 rows, `before_time` + `before_id` from `next_before`, appended to `activityQuery`
  (so a later event cannot disturb the walk). “Muat aktivitas sebelumnya” only while `next_before`
  exists. Count: `<N> catatan ditampilkan · <M> cocok saat dimuat`.
- **CSV.** `GET /api/activity.csv` with the loaded `start_date`, `end_date`, `kind` — `limit` removed,
  no cursor. Disabled until a report succeeds, disabled again by any edit, `exportBusy` single-flight
  with `Menyiapkan CSV…`, filename `beeloft-aktivitas-<start>-<end>-<kind>.csv`. The 10.000-row and
  366-day limits stay backend-enforced (422, no partial file); errors render inline.

## Audit trail — immutable ledger

- **Access.** Admin only: `#audit-trail.hidden = role !== 'admin'` and 403 on both endpoints.
- **Truth.** Read-only note kept verbatim, plus “Catatan tidak dapat diubah atau dihapus.” (the
  database rejects UPDATE/DELETE). No edit/delete/restore/replay/undo control exists.
- **Lifecycle.** `showAuditEvents()` → `guardPending()` → `activateWorkspace` → `loadAuditEvents()`;
  `/api/users` is read first (unfiltered, as returned), guarded by `epoch/auditRequest/view`. A failed
  setup shows an error state with “Coba lagi” (`data-action="audit-events"`) and no command bar.
- **Filters.** `auditFilters {q, category, actor_id, start_date, end_date}`; search (maxlength 160)
  takes its own row; categories `all, master_data, production, materials, purchasing, warehouse,
  marketplace, approval, ai, integration`; actors `<name> · <role>`; explicit “Terapkan filter”,
  Reset rebuilds the page.
- **Pagination.** `limit=25`, `before` = sequence cursor (`ORDER BY sequence DESC`), empty params
  dropped, `page.total` is the filter total. Only a filter replacement plays the existing
  `playEntryMotion`; appending never does.
- **Records.** Record-list rows: reference-or-operation, neutral category chip, operation · subject
  type, actor · role · Jakarta time (`auditStamp`), “Lihat rincian”.
- **Evidence dialog.** Title `Audit · <reference or operation>`; Kategori, Operasi, Pelaku, Waktu
  Jakarta, Objek, Referensi, Request key; then “Input perubahan” (`changes`) and “Hasil tersimpan”
  (`outcome`) as two separate escaped `JSON.stringify(…, null, 2)` blocks that wrap and scroll.
  Redaction (`[REDACTED]`) and bulk-payload summarisation stay backend invariants; the UI never
  reconstructs values.

## Cadangan data — focused utility

- **Access.** Admin only at three layers: nav hidden, activation checks `user?.role === 'admin'`,
  backend 403.
- **Composition.** One surface: file identity (SQLite `.sqlite3`) and contents → sensitivity
  attention note → key/snapshot/after-download notes → one primary action → status. No invented
  history, schedule, size or health; no restore/upload UI (recovery stays in the README).
- **Wording.** The file contains access-key **hashes**; original keys are not included and must be
  kept to log in after restore. The snapshot is taken when the download is requested.
- **Lifecycle (unchanged).** `guardPending()` before opening and before downloading;
  `version = epoch`, `request = ++backupRequest`, `current()` also requires `view === 'backup'` and
  admin. One `GET /api/backup`, button disabled with `Menyiapkan cadangan…`, filename
  `beeloft-backup-<ISO with : and . → ->.sqlite3`, success text about the browser download list.
  A 503 renders inline, downloads nothing and restores the button for a manual retry.

## Global

- **CSS.** One block at the end of `style.css`, marker `#activity-view,#audit-view,#backup-view{max-width:1360px`,
  reaching only A6.6 ids/classes; no primitive redefined, no blur, no motion. Legacy hooks still
  emitted for existing suites (`.activity-item`, `.audit-event`, `.audit-json`) have their legacy
  boxes withdrawn by scope. Legacy selectors (`.page-heading`, `.filters`, `.summary`, `.history-item`,
  `.filter-form`, `.form-grid`, `.requirement-values`, …) remain for A6.7 surfaces; removal is A6.8.
- **Responsive.** 1440 shows heading, controls, summary and the start of the timeline/ledger; ≤650px
  filters become labelled full-width fields, the timeline goes single-column, audit rows stack, the
  backup action goes full-width. At 1440, 390 and 320px / 200% text the browser module asserts both
  that the document does not overflow and that nothing crosses its own section's edge — the floating
  window clips overflow, so a document check alone cannot see a clipped control. (The Activity date
  floor, `8.75rem`, is therefore desktop-only: at 320px / 200% it would be 280px, wider than the bar.)
- **Themes & accessibility.** Dark mode through A6 tokens; reduced transparency via A6.0 fallbacks; no
  new forced-colors block — meaning is carried by text (event label, chip text + dot, error copy).
- **Performance.** RAF 6 / cancelAnimationFrame 4 / setTimeout 7 / setInterval 0 unchanged; no
  polling, no extra requests.
- **Tests.** `tests/test_apple27_activity_audit_backup_contract.py` (static) and
  `tests/browser_activity_audit_backup_modern_workspaces.cjs` (behaviour + 21 review shots, written to
  `$BEELOFT_A66_REVIEW` or `<qa-shots>/a66-visual-gate`).
- **Deferred to A6.8.** Cross-product visual consistency and the legacy CSS sweep.
