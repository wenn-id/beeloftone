# Apple-27 A6.5 — Tanya Beeloft + Integrasi modern workspaces

Baseline: `main` at `94e83d83235cb536e98dc3c4227eaabb7b340412` (PR #103 merged, CI #167 success), version
0.110.0 → **0.111.0**, schema `PRAGMA user_version = 55` (unchanged, no migration). OpenAPI diff:
`info.version` only.

A6.5 migrates `#ai-view`, `#integrations-view` and the renderers they own onto the A6.0 workspace
grammar. It is presentation only. No route, schema, AI calculation, health calculation, snapshot
ingestion, reconciliation, approval, idempotency, ownership, session or stale-guard logic changed.

## Shared evidence grammar

Both workspaces read evidence, so they share one small set of helpers in `app.mjs`
(`evidenceChip`, `evidenceFacts`, `evidenceMetrics`, `evidenceNote`, `evidenceRecord`, `evidenceList`,
`evidenceSection`, `evidenceAttention`, `evidenceEmpty`, `evidenceFail`, `evidenceLoading`,
`evidenceNav`, `snapshotIdentity`, `snapshotHistory`). Each one writes exactly one A6.0 shape:
status chip, detail grid, metric strip, info panel, record list, attention note, or an
empty/error/loading state. They are not a second component system, and nothing outside A6.5 calls
them. The page compositions are still different on purpose: Tanya Beeloft is a composer above an
answer, and Integrasi is a set of system surfaces with scope rows.

CSS lives in one contained block at the end of `style.css`, starting at
`#ai-view,#integrations-view{max-width:1360px…}`. It only reaches A6.5 ids and the
`.investigation*` / `.integration-*` / `.evidence-*` / `.ai-*` names that only A6.5 renderers emit.
It redefines no primitive and adds no material, blur, transition or keyframe.

## Tanya Beeloft

**Hierarchy:** identity → composer (starters, question, assumptions, action) → request status →
result → history. The title is "Tanya Beeloft", with the subtitle *Tanyakan kondisi bisnis dari
ledger Beeloft dan simpan hasilnya sebagai investigasi.* The local-analysis note sits in the
composer header: analysis runs locally, only reads the Beeloft ledger, and sends nothing outside.
The answer still prints "Analisis lokal · tidak mengirim data keluar · hanya baca".

This is not a chat interface. There are no bubbles, avatars, streaming, typing dots, animated
reveal, timers or model picker. The result appears when the request completes.

- **Composer.** `#ai-form` / `#ai-question` (textarea, `required`, `minlength=2`, `maxlength=1000`,
  real label *Pertanyaan bisnis*). `#ai-submit` keeps "Analisis dan simpan" / "Menganalisis…" /
  "Coba ulang penyimpanan". `#ai-reauth` keeps "Masuk ulang".
- **Starters.** All five `data-ai-question` values are unchanged. They render as quiet
  `.filter-chip` buttons. A click fills `#ai-question` and focuses it. It does not submit.
- **Assumptions.** These stay in `details.ai-assumptions`, closed on every `showAi()`, as A6
  `.field` rows with unchanged names, defaults and min/max. `as_of` still has no `max`, so future
  dates are still allowed.
- **Activation reset.** `showAi()` is byte-identical in behaviour: it calls `guardPending`, then
  `activateWorkspace('ai-brain')`, resets the transaction/unresolved/modalBusy state, clears the
  result and message, closes the assumptions, sets `as_of` only when it is empty, enables the
  controls, restores the labels, hides re-auth, and reloads history.
- **Idempotency / unresolved save.** `submitAiInvestigation()` is unchanged apart from the
  class on its retry button. It still uses `aiTransaction` → `api.transaction()` → the
  `sessionStorage` draft under `pendingKey()` with `actor_id` → `sameActorGuard(actorId)` on retry
  → `api.save()` → `clearPending()`. An uncertain write keeps the form locked and reuses the same
  key. `#ai-message` keeps its id, `role=status` and `.state` class. When `message()` sets
  `.error`, it now renders as a danger-tinted panel rather than a quiet card.
- **Same-actor / logout safety.** This is untouched. `browser_ai_investigation_logout.cjs` and
  `browser_cross_account_retry.cjs` stay green.
- **Result.** `renderAiInvestigation(report, target, source = report.source_payload)` renders in
  this order: context (saved by/at, history link) → **one answer surface** (intent chip, confidence
  chip "Keyakinan tinggi/sedang/rendah", question, answer, local/read-only line with focus SKU/order
  refs) → *Fakta pendukung* (detail grid; units IDR/sku/order/issue/item/material/pcs/passthrough
  unchanged) → *Temuan* (record list; severity chips Kritis=danger, Tinggi=warning,
  Sedang=neutral, Informasi=info, with a text label always shown) → *Rekomendasi* (each one shows
  "Perlu approval" and "Belum dijalankan · sumber …", under a note that proposing does not
  execute) → linked actions → feedback → *Batas analisis* disclosure.
- **Evidence compatibility.** Every optional field is read defensively (`report.focus?.…||[]`,
  `facts`, `findings`, `recommendations`, `linked_actions`, `limitations`, `feedback_summary`). The
  renderer makes no API call, so an old investigation is never rebuilt from today's ledger.
  `test_ai_evidence_compatibility.py` stays green.
- **Proposals.** Only `create_production_order` and `create_purchase_request` get "Ajukan untuk
  approval", and only when `user.role !== 'viewer'`. The forms use A6 fields inside the unchanged
  `formDialog()`. The production PIC list is `/api/users` filtered to active non-viewers. The PR
  estimate keeps min 0.01 / max 1,000,000,000,000 / step 0.01. Both creation truths are printed.
  The payload is `{...source, investigation_id, action_kind, subject_id, …}`, taken from the stored
  snapshot.
- **Proposal detail.** `aiActionProposalDialog()` shows identity chips, the recommendation title,
  a payload detail grid, actor/time, reason, and the re-validation note (with the PR's Purchasing
  approval truth). "Tindakan selesai" appears only when `executed_entity_id` exists, and it
  navigates to the order or PR. Decision rules are unchanged (admin + submitted → approve/reject;
  submitted and admin-or-actor → cancel). The payload carries `expected_revision: row.revision`.
  History is an A6 timeline.
- **Feedback.** Choices are "Jawaban membantu" / "Perlu diperbaiki". The summary shows
  helpful · not_helpful · respondents, with no stars or averages. A note says feedback is
  append-only and that the latest response per person is counted.
- **History.** `#ai-history` stays inside `#ai-view`. The filter is a command bar (`q`
  maxlength 160, intent all/overview/production/stockout/approvals/margin) with an explicit
  submit. Requests use `limit=50`, `intent`, `q` and optional `before=` the last `sequence`, with
  "Muat investigasi sebelumnya" and no infinite scroll. The `aiHistoryRequest`/epoch/view fence is
  unchanged. Empty states are distinct: never saved, no filter match, or no older rows. Errors
  offer a retry. `#ai-history-jump` and `[data-ai-history]` keep their behaviour.

## Integrasi

**Hierarchy:** identity → ledger-truth context + freshness → two system surfaces → scope rows →
grouped utilities. The title is "Integrasi", with the subtitle *Pantau kesehatan sinkronisasi,
source of truth, dan snapshot vendor.*

- **Health truth.** One call to `GET /api/integrations`. The fence
  (`integrationsRequest`/epoch/view) is unchanged, and so is `loadIntegrations(refresh=false)`: a
  manual refresh calls `markRefreshing('integrations-body')` and keeps content dimmed, while
  first open shows a loading state. A failure sets `integrationsReport=false` and replaces the body
  with an A6 error that has `#integrations-retry` "Coba lagi". The ledger-truth sentence and
  "Batas stale N jam · diperiksa …" stay visible.
- **Health values.** The five values are kept exactly: Sehat=success, Gagal=danger, Stale=warning,
  Belum pernah sync=neutral, Belum lengkap=warning. They appear as chips only; system surfaces are
  never tinted.
- **Systems.** Each system (`data-integration-system`) is one surface showing label, health chip,
  and "N dari M scope perlu perhatian". The Jubelio SKU identity mapping row reads "Mapping SKU: x
  dari y terhubung · z belum dipetakan" and links to Master SKU. Utilities are grouped: *Snapshot
  vendor* / *Rekonsiliasi* for Jubelio, and *Snapshot akuntansi* / *Rekonsiliasi payroll* for
  Mekari. All 11 entry points remain.
- **Scopes.** Each scope (`data-integration-scope`) shows domain, *Source of truth: … · inbound
  read-only*, and age ("N menit lalu" / "floor(N/60) jam lalu" / "Belum ada run"), plus read/write
  counts, the latest error, and "Rincian run terbaru".
- **Run ledger.** `integrationRunsDialog()` uses a command-bar filter (system, status) with an
  explicit submit. It keeps `limit=50`, `before=sequence`, "Muat run sebelumnya", and the local
  `generation` + epoch + dialogVersion + open guards. Rows are records. `integrationRunDialog()`
  keeps every field and the same duration calculation. There is no rerun, edit or delete control.
- **Jubelio.** The stock reconciliation, order, return and listing summaries share one grammar:
  snapshot identity chip, metric strip, status detail grid, read-only truth note, navigation, then
  record-list sections. Quarantine is a first-class section with warning chips and escaped
  details; it is attention, not a system failure. "No snapshot" is an empty state with no zeros.
  All eight snapshot histories use `snapshotHistory()` at `limit=100` with no pagination. Details
  share `snapshotContext()`: counts, connector error, cursor/reason/actor.
- **Mekari.** Finance keeps three distinct states: no snapshot, snapshot without periods (an
  attention note), and a normal current report. Payables and receivables show overdue relative to
  the snapshot `as_of` date. None of these screens pays, collects, journals or changes vendor
  status.
- **Payroll.** Snapshots are aggregate only, with no employee identity. The Mekari status chip and
  the Beeloft approval chip are separate; "sumber berubah" appears when the approval is stale. The
  `payrollPeriodCard` submission gate is unchanged. Approval only authorises; it does not change
  Mekari, pay or journal.
- **Payroll reconciliations.** Both filter bars (status, `q` maxlength 160) submit explicitly.
  Both keep `limit=25` / `offset` with "Muat batch berikutnya". Exception mapping is unchanged
  (source missing / financial mismatch / cancelled / draft / reversed / unbalanced / amount
  mismatch) and shown in attention notes with the changed fields. There is no journal action.

## Global

- **Responsive.** At 1440 the Tanya Beeloft first view shows the heading, starters, composer,
  action and closed assumptions. Integrasi shows the context plus the beginning of both systems,
  side by side. At 390/320 everything stacks. At 320 @ 200% no document or dialog overflow was
  measured, so the evidence buttons, filters and chips are allowed to wrap. The ≤980px touch
  floor is restored for migrated controls.
- **Dark mode.** Near-opaque A6 surfaces are used throughout. The facts grid has its own surface,
  so evidence never floats on the wallpaper.
- **Accessibility.** One `h1` per page. Real labels. Native `details`/`summary`. Every state host
  keeps `role=status`. Status is always carried by text. No card is clickable without a control.
- **Forced colors / reduced transparency.** A6.5 adds no fourth forced-colors or
  reduced-transparency block. Every A6.5 surface has a real border, which the mode repaints, and
  the chip dots are mapped by `workspace-primitives.css`.
- **Performance.** No polling, interval, RAF, timer or decorative request. The budget is
  unchanged: RAF 6, cancelAnimationFrame 4, setTimeout 7, setInterval 0.
- **Escaping.** All vendor, AI and user text passes through `e()`. The suites keep `<timeout>`,
  `<SKU>` and `<script>` fixtures.
- **Migration contract.** `MIGRATED_SECTIONS` gains `ai-view` and `integrations-view`.
  `MIGRATED_RENDERERS` gains only the named A6.5 renderers and helpers. The Approval Inbox, Master
  SKU, the production order and PR details, and payroll approval-request internals stay blocked.
- **Tests.** Static: `tests/test_apple27_ai_integrations_workspace_contract.py`. Behavioural:
  `tests/browser_ai_integrations_modern_workspaces.cjs`, which also writes the 28-shot review set.
- **Legacy CSS.** `.ai-answer` and `.ai-prompts` are now inert, and `.ai-assumptions` keeps only
  the class hook. These are left for A6.8's proven sweep. Shared vocabulary (`.material-event`,
  `.status-label`, `.form-*`, `.filter-form`, `.history-*`) is still used by A6.6/A6.7 surfaces and
  `formDialog()`.

## Deferred

- A6.6: Activity, Audit and Backup.
- A6.7: Purchasing, Budget marketing and Approval Inbox.
- A6.8: cross-product consistency and the inert-selector sweep.
