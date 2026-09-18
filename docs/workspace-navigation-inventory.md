# Workspace Navigation Inventory

Program: Beeloft One — Workspace Navigation Architecture Roadmap, Version 1.0
Milestone: 0 (Inventory and migration map)
Baseline: `main` @ `0748571ade0f8c8da5cdff9ed17dfb8acf746991`
Branch: `docs-only`
Date: 18 September 2026

Core rule under inventory: primary navigation must establish context in the main
workspace. A modal is reserved for a focused secondary task (create, edit, review,
confirmation, or record detail). This document records the current state of every
persistent primary sidebar destination so later milestones migrate from evidence
rather than labels.

## 1. Summary counts

| Classification | Count | Destinations |
|---|---|---|
| EXISTING_PAGE | 4 | Command center, Produksi, Bahan baku, Laporan aktivitas |
| LEGACY_DIALOG | 22 | People, Master SKU, 12 Analitik children, Tanya Beeloft, Integrasi, Audit trail, Inbox approval, Permintaan pembelian, Budget marketing, Scan bundle, Scan barang jadi |
| INTENTIONAL_DIALOG | 0 | (none among primary sidebar destinations) |
| NEEDS_VERIFICATION | 1 | Cadangan data |
| OTHER | 0 | — |
| **Total primary destinations** | **27** | |

Non-destination workspace sections reached by navigation but not present in the
sidebar: `detail-view` (order detail, opened from the production board). It is a
page, not a sidebar destination, and is out of scope for the migration counts.

All 22 LEGACY_DIALOG handlers call `openDialog()` directly as the primary
experience. No primary sidebar click reaches `openDialog()` only through an
indirect chain — every legacy handler is a direct `*Dialog()` call.

## 2. Sidebar structure (source: `beeloft/static/index.html`)

The sidebar `aside#app-sidebar > nav.sidebar-nav` contains five groups plus one
call-to-action card. Two items are hidden until an admin session is established
(`index.html:108-109`, revealed at `app.mjs:198`).

| Sidebar group | Items |
|---|---|
| Group 1 (context) | `command-center`, `board-home` |
| Group 2 (operational) | `materials`, `workforce`, `scan-bundle`, `scan-finished-goods`, `products` |
| Analitik (collapsible `<details>`) | 12 insight children |
| Group 3 (oversight) | `ai-brain`, `integrations`, `activity`, `audit-trail` (admin-only), `backup` (admin-only) |
| Group 4 tail (business) | `purchase-requests`, `marketing-budgets` |
| CTA card (not a nav group) | `approvals` ("Inbox approval", blue CTA button) |

## 3. Current navigation foundation (baseline for Milestone A)

The application already has partial navigation primitives. Milestone A centralizes
these; they must be preserved, not rewritten.

| Primitive | Location | Role |
|---|---|---|
| `activeNavigation(id)` | `app.mjs:49` | Clears all `aria-current` in sidebar, sets `aria-current="page"` on the active item |
| `sidebar(open, restoreFocus)` | `app.mjs:39` | Toggles `nav-open` body class (mobile drawer); restores focus to menu toggle |
| Sidebar click delegation | `app.mjs:44-52` | Closes drawer after selection, moves focus to the visible section's `h1` (or defers to `dialogReturnFocus` when a dialog is open) |
| Escape-to-close drawer | `app.mjs:53` | Closes drawer on Escape |
| `epoch` (module global) | `app.mjs:19` | Navigation generation counter; bumped by `clearWorkspace()`; used by every async renderer as a stale-response guard |
| Per-view request counters | `app.mjs:19-27` | `boardRequest`, `detailRequest`, `activityRequest`, `commandCenterRequest`, `materialsRequest` — feature-local stale-response protection |
| `dialogVersion` | `app.mjs:20` | Modal generation counter; bumped by `openDialog()` and `clearWorkspace()` |
| `openDialog(title, content)` | `app.mjs:596` | Increments `dialogVersion`, resets `modalBusy`/`unresolved`, calls `dialog.showModal()` on the single global `<dialog id="dialog">` (`index.html:197`) |
| `guardPending()` | `app.mjs:784` | Reads pending draft from `sessionStorage` (`pendingKey()` = `beeloft.pending.<user_id>`); calls `recover()` and blocks navigation when a write is unresolved |
| `modalBusy`, `unresolved` | `app.mjs:19` | In-flight mutation and unconfirmed-write flags |
| View switching | `showBoard`, `showMaterials`, `showCommandCenter`, `activity` onclick | Manual `.hidden` toggles across `workspace-main` sections, each bumping the counters of the views it hides |

Views currently present in `workspace-main` (`index.html:125-193`):
`command-center-view`, `materials-view`, `board-view` (default visible),
`activity-view`, `detail-view`.

Target additions per roadmap §3: `people-view`, `products-view`, `analytics-view`,
`ai-view`, `integrations-view`, `audit-view`, `backup-view` (conditional),
`purchase-requests-view`, `marketing-budgets-view`, `approvals-view`,
`bundle-scan-view`, `finished-goods-scan-view`.

## 4. Primary destination map

Interaction: PAGE = renders a `workspace-main` section; DIALOG = primary handler
calls `openDialog()`; ACTION = entry performs one operation with no browse state.

### 4.1 Group 1 — context

#### `command-center` — Command center
- Renderer: `showCommandCenter` (`app.mjs:375`, wired `app.mjs:500`)
- Interaction: **PAGE** → `command-center-view`
- Data: `GET /api/command-center` (single payload: marketplace performance,
  operational attention list, snapshots); guarded by `commandCenterRequest` + `epoch`
- Mutation: none on the page; decision shortcuts call `showCommandOrders(status)`
  which resets board filters and shows the board
- Access: all roles; `new-order` hidden unless admin
- Async: `commandCenterRequest` counter; `view !== 'command-center'` early return
- State: explicit loading message, `aria-busy` on summary, `command-center-message`
  status region, refresh button
- Child dialogs: none primary; attention items navigate to the board
- Target: keep as page — **EXISTING_PAGE**

#### `board-home` — Produksi
- Renderer: `showBoard` (`app.mjs:242`, wired `app.mjs:250`); also reached via
  `brand` link and `back`/`activity-back`/`materials-back` buttons
- Interaction: **PAGE** → `board-view` (default destination after login, `aria-current="page"` in markup)
- Data: `GET /api/production-board?` — offset pagination (25/page), filters:
  search text, status, PIC, stage; summary aggregates across all production
- Mutation: none on page load; mutations live in order detail (`detail-view`):
  movement, reversal, issue, order change, consumption, reservation
- Access: all roles; `new-order` admin-only
- Async: `boardRequest`, `detailRequest`, `epoch`
- State: `board-message` status region, empty/error handled by `loadBoard`
- Child dialogs: `orderForm` (new order), `editOrderForm`, `issueForm`,
  `productionChangeRequestForm`, `moveForm`, `reverseForm`, and order-detail
  drill-downs (all reached from `detail-view`, not the board surface directly)
- Target: keep as page — **EXISTING_PAGE**

### 4.2 Group 2 — operational

#### `materials` — Bahan baku
- Renderer: `showMaterials` (`app.mjs:1225`, wired `app.mjs:4023`)
- Interaction: **PAGE** → `materials-view`
- Data: `GET /api/material-batches?` — offset pagination (25/page), material filter
  select; summary balances
- Mutation: none on page; receive/scan/master are child dialogs
- Access: all roles view; `receive-material` hidden for viewer
- Async: `materialsRequest`, `materialsOffset`, `epoch`
- State: `materials-message` status region, refresh + pagination buttons
- Child dialogs: `materialBatchScanDialog`, `materialMasterDialog`, `receiptForm`
- Target: keep as page — **EXISTING_PAGE**

#### `workforce` — People
- Renderer: `workforceDialog` (`app.mjs:3689`, wired `app.mjs:896`)
- Interaction: **DIALOG** (global modal "People") — full roster inside the modal
- Data: `GET /api/workforce/employees` + `GET /api/workforce/attendance` (via
  `workforcePage` helper, `app.mjs:3680`); filters: `work_date`, `status`, `q`;
  local `generation` counter inside the dialog
- Mutation: none from the roster surface itself; attendance corrections and
  request decisions are child dialogs with their own idempotency keys
- Access: all roles see roster; `new-employee` admin-only; viewer cannot mutate
- Async: `epoch` + `dialogVersion` + local `generation` (three-layer guard)
- State: `workforce-message` status region, summary `dl`, empty roster handled
- Child dialogs: `workforceEmployeeForm` (new/edit), `workforceEmployeeHistoryDialog`,
  `workforceAttendanceForm`, `workforceAttendanceHistoryDialog`,
  `workforceRequestsDialog`, `workforceEmployeeMasterDialog`
- Filter state: `workforceFilters` persists in module scope across dialog reopen
- Target: `people-view` (Milestone B) — **LEGACY_DIALOG**

#### `scan-bundle` — Scan bundle
- Renderer: `bundleScanDialog` (`app.mjs:1448`, wired `app.mjs:897`)
- Interaction: **DIALOG** — scanner surface inside modal
- Data: `GET /api/bundles/scan?` — live scan input, result/history on the same surface
- Mutation: scan accept/handoff writes happen in child forms (`bundleHandoffForm`,
  `acceptBundleHandoffForm`), each exact-once
- Access: operator/admin; viewer blocked from mutating scans
- Async: `epoch` + `dialogVersion`; `bundle-error` region with retry
- State: `bundle-error` status, loading placeholder, retry buttons
- Child dialogs: `bundleDialog`, `bundleHandoffsDialog`, handoff accept/cancel forms
- Target: `bundle-scan-view` (Milestone F) — **LEGACY_DIALOG**

#### `scan-finished-goods` — Scan barang jadi
- Renderer: `finishedGoodsScanDialog` (`app.mjs:4483`, wired `app.mjs:898`)
- Interaction: **DIALOG** — scanner surface inside modal
- Data: `GET /api/finished-goods-receipts/scan?`
- Mutation: receipt writes via child forms, exact-once
- Access: operator/admin; viewer read-only
- Async: `epoch` + `dialogVersion`
- State: error region with retry, loading placeholder
- Child dialogs: `finishedGoodsReceiptDialog`, label/print confirmation
- Target: `finished-goods-scan-view` (Milestone F) — **LEGACY_DIALOG**

#### `products` — Master SKU
- Renderer: `productsDialog` (`app.mjs:820`, wired `app.mjs:894`)
- Interaction: **DIALOG** — full master-data workspace inside modal
- Data: `GET /api/products` + `GET /api/product-external-mappings` (both via
  `allRows`, `app.mjs:815` — full list, no pagination)
- Mutation: none from the list surface; SKU/BOM/mapping writes are child forms
- Access: all roles browse; `new-product`, `edit-bom`, mapping forms admin-only
- Async: `epoch` + `dialogVersion`
- State: loading placeholder; empty state ("Belum ada SKU"); error with retry
  (`data-action="products"`)
- Child dialogs: `productForm` (Tambah SKU), `bomDialog`/`bomForm`/`bomHistoryDialog`,
  `productMappingDialog`/`productMappingForm`/`productMappingHistoryDialog`,
  `unmapProductForm`
- Target: `products-view` (Milestone B) — **LEGACY_DIALOG**

### 4.3 Analitik group — 12 insight children

All twelve share one shape: `openDialog(<title>, <filter form + list host>)`, a
filter form, one `GET /api/<report>` call, and per-dialog local `generation`
counters layered on `epoch`/`dialogVersion`. All are read-only (no `api.post` on
the primary surface). All are **LEGACY_DIALOG** → `analytics-view` host
(Milestone C).

| Nav id | Label | Endpoint | Drill-down (`data-action`) |
|---|---|---|---|
| `wip-ageing-insights` | WIP ageing | `GET /api/wip-ageing-insights?` | `detail` (open production order) |
| `capacity-plan` | Kapasitas produksi | `GET /api/capacity-plan?` | `detail`, `new-work-center`/`edit-work-center` (admin) |
| `production-quality-insights` | Kualitas produksi | `GET /api/production-quality-insights?` | `final-qc-record` |
| `supplier-performance-insights` | Kinerja supplier | `GET /api/supplier-performance-insights?` | `purchase-order` |
| `material-price-insights` | Harga bahan | `GET /api/material-price-insights?` | `purchase-order` |
| `purchase-commitment-insights` | Komitmen PO | `GET /api/purchase-commitment-insights?` | `purchase-order` |
| `demand-forecast` | Forecast demand | `GET /api/demand-forecast?` | none (inline result) |
| `replenishment` | Rekomendasi stok | `GET /api/replenishment-recommendations?` | none (inline result) |
| `size-demand-insights` | Analisis ukuran | `GET /api/size-demand-insights?` | none (inline result) |
| `return-insights` | Analisis retur | `GET /api/return-insights?` | none (inline result) |
| `dead-stock-insights` | Dead stock | `GET /api/dead-stock-insights?` | none (inline result) |
| `stock-adjustment-insights` | Audit adjustment | `GET /api/stock-adjustment-insights?` | `finished-goods-adjustment` |

Shared characteristics recorded for the Milestone C host design:
- Each dialog owns its own filter form and its own `generation` counter — the
  stale-response guard pattern to preserve.
- Drill-downs either open a focused record dialog (e.g. `purchaseOrderDialog`,
  `finishedGoodsAdjustmentsDialog`) or navigate to an existing page (`openDetail`).
  Roadmap §Milestone C allows either behavior to survive.
- Empty state: each report distinguishes "no rows after filter" from loading.
- Error state: `message(..., true)` with a retry button that re-invokes the same
  loader.
- No report writes; viewer access is identical to admin on the read surface.

### 4.4 Group 3 — oversight

#### `ai-brain` — Tanya Beeloft
- Renderer: `aiInvestigationDialog` (`app.mjs:2990`, wired `app.mjs:3056`)
- Interaction: **DIALOG** — prompt, assumptions, results, and history all in modal
- Data: `POST /api/ai/investigations` (transactional, `api.transaction()` +
  `api.save()`); history via `aiInvestigationsDialog` (`GET /api/ai/investigations`)
- Mutation: the investigation write is exact-once with a pending draft persisted in
  `sessionStorage` under `pendingKey()`; `sameActorGuard(actorId)` binds the
  transaction to the originating account; re-auth path via `reauthenticate`
- Access: all roles may ask; proposals/execution gated separately
- Async: `epoch` + `dialogVersion` + modal-local `current()`; lost-response retry
  reuses the same transaction and idempotency key
- State: `ai-message` status, locked form during analysis, re-auth button reveal
- Child dialogs: `aiInvestigationsDialog` (history), `aiInvestigationDetailDialog`,
  `aiActionProposalDialog` (action proposals + execution confirmation)
- Target: `ai-view` (Milestone D) — **LEGACY_DIALOG**
- Protected (must not weaken): pending investigation recovery, snapshot/evidence
  compatibility, lost-response retry, cross-account session guard, exact-once replay

#### `integrations` — Integrasi
- Renderer: `integrationsDialog` (`app.mjs:2599`, wired `app.mjs:2609`)
- Interaction: **DIALOG** — health, source-of-truth status, history in modal
- Data: `GET /api/integrations`; per-system snapshot summary dialogs each issue
  their own `GET /api/<system>/...` calls
- Mutation: none from the primary surface; run detail and reconciliation are reads
- Access: all roles; admin-only actions where present live in child surfaces
- Async: `epoch` + `dialogVersion`
- State: loading placeholder, health badges, error with retry
- Child dialogs: `integrationRunsDialog`, `integrationRunDialog`,
  `jubelioStockSnapshotsDialog`/reconciliation, `jubelioOrder/Return/ListingSummary`
  + snapshot dialogs, `mekariFinance/Payables/Receivables/PayrollSummary` + snapshot
  dialogs, `payrollPaymentReconciliationDialog`,
  `payrollAccountingReconciliationDialog`
- Target: `integrations-view` (Milestone D) — **LEGACY_DIALOG**
- Protected: immutable run history integrity; escaping of external payloads

#### `activity` — Laporan aktivitas
- Renderer: inline onclick (`app.mjs:1150`) calling `loadActivity`
- Interaction: **PAGE** → `activity-view`
- Data: `GET /api/activity?` — date range + kind filters, cursor pagination
  ("Muat aktivitas sebelumnya"), CSV export of the full filtered result
- Mutation: none (read-only report); export is a download
- Access: all roles
- Async: `activityRequest`, `activityCursor`, `epoch`
- State: `activity-message`, summary `dl`, empty/error, export disabled until a
  result exists
- Child dialogs: none (drill-downs go to order detail page)
- Target: keep as page; integrate into navigation foundation only (Milestone A/F)
  — **EXISTING_PAGE**

#### `audit-trail` — Audit trail
- Nav item hidden unless admin (`app.mjs:198`)
- Renderer: `auditEventsDialog` (`app.mjs:608`, wired `app.mjs:895`)
- Interaction: **DIALOG** — filters + cursor list inside modal
- Data: `GET /api/audit-events?` (cursor `before` pagination, limit 20) +
  `GET /api/users` for actor filter; filters: `q`, `category`, `actor_id`,
  `start_date`, `end_date` (held in `auditFilters`, reset by `clearWorkspace`)
- Mutation: none (immutable audit log)
- Access: admin-only at the nav level; viewer/operator never see the item
- Async: `epoch` + `dialogVersion` + local loader generation
- State: loading placeholder, empty state, error with retry
- Child dialogs: `auditEventDialog` (raw event detail)
- Target: `audit-view` (Milestone D); admin-only restriction unchanged —
  **LEGACY_DIALOG**

#### `backup` — Cadangan data
- Nav item hidden unless admin (`app.mjs:198`)
- Renderer: inline onclick (`app.mjs:4647`) — opens "Cadangan data" dialog whose
  only control is `download-backup`
- Interaction: **ACTION** — `GET /api/backup` (blob download via `api.download`),
  no browse/list state, no filters, no pagination
- Mutation: none (read-only download of the SQLite database)
- Access: admin-only at the nav level
- Async: `epoch` + `dialogVersion`; `current()` guards the download result
- State: `backup-message` status region; purpose/safety copy is static
- Child dialogs: none
- Verdict: this entry is action-only, not a persistent browse destination. It does
  not establish context and has no page-worthy state. It fits the roadmap's
  focused-secondary-task definition, so keeping it as a dialog is defensible;
  however roadmap Appendix A targets `backup-view` **if** it is a persistent
  destination. Recorded as **NEEDS_VERIFICATION** — Milestone F decides: expose a
  minimal `backup-view` (purpose/status + existing download action) for
  architectural consistency, or reclassify as INTENTIONAL_DIALOG. Recommendation
  recorded here: expose `backup-view` in Milestone F so zero primary entries
  remain on the dialog path, keeping the download confirmation inline.

### 4.5 Group 4 tail — business

#### `purchase-requests` — Permintaan pembelian
- Renderer: `purchaseRequestsDialog` (`app.mjs:4131`, wired `app.mjs:4049`); the
  same dialog is reused order-scoped via `purchaseRequestsDialog(orderId)` from
  order detail (`data-action="order-purchases"`)
- Interaction: **DIALOG** — browse/filter/list inside modal
- Data: `GET /api/purchase-requests?` — cursor `before` pagination (25/page),
  status filter, optional `order_id` scope
- Mutation: none from list; create/decision are child forms
- Access: all roles browse; `new-purchase-request` hidden for viewer
- Async: `epoch` + `dialogVersion` + local `generation`
- State: `pr-error` alert region, empty-filter state, retry button
- Child dialogs: `purchaseRequestForm` (create), `purchaseRequestDialog` (detail),
  `suppliersDialog`, `purchaseOrdersDialog`
- Target: `purchase-requests-view` (Milestone E) — **LEGACY_DIALOG**

#### `marketing-budgets` — Budget marketing
- Renderer: `marketingBudgetsDialog` (`app.mjs:4075`, wired `app.mjs:4050`)
- Interaction: **DIALOG** — budget queue inside modal
- Data: `GET /api/marketing-budget-requests?`
- Mutation: none from list; create/decision are child forms
- Access: all roles browse; `new-marketing-budget` hidden for viewer
- Async: `epoch` + `dialogVersion`
- State: error region, empty state, retry
- Child dialogs: `marketingBudgetForm`, `marketingBudgetRequestDialog`,
  decision form via approvals
- Target: `marketing-budgets-view` (Milestone E) — **LEGACY_DIALOG**

### 4.6 CTA card — approval inbox

#### `approvals` — Inbox approval
- Renderer: `approvalsDialog` (`app.mjs:4053`, wired `app.mjs:4051`); also reachable
  as `data-action="approvals"` from many surfaces
- Interaction: **DIALOG** — cross-domain decision queue inside modal
- Data: `GET /api/approvals?` — **offset** pagination (25/page), filters: status
  (pending/all/approved/rejected/cancelled) and kind
- Mutation: none from the queue surface; approve/reject happen in per-kind
  decision dialogs (`approvalAction[row.kind]`), each with idempotency key +
  actor binding
- Access: all roles see queue; decision authority follows per-kind role rules
- Async: `epoch` + `dialogVersion` + local `generation`
- State: `approval-error` alert region, empty-filter state, retry
- Cross-domain shortcuts: `purchase-requests`, `marketing-budgets`,
  `workforce-requests`, `mekari-payroll-summary`
- Nine approval kinds in the filter: `purchase_request`, `purchase_order`,
  `supplier_payment`, `marketing_budget`, `production_change`, `workforce_leave`,
  `workforce_overtime`, `payroll_batch`, `ai_action`
- Target: `approvals-view` (Milestone E) — **LEGACY_DIALOG**
- Protected (Milestone E must retain): pending totals above 500, exact money
  arithmetic, all nine kinds, SQLite aggregate-overflow regression, stale decision
  handling, cancellation, lost-response retry, audit event integrity, no duplicate
  mutation

## 5. Handlers that call `openDialog()` as primary experience

Complete list of primary sidebar handlers whose main effect is `openDialog()`:

`workforceDialog`, `productsDialog`, `auditEventsDialog`, `bundleScanDialog`,
`finishedGoodsScanDialog`, the twelve `*InsightsDialog`/`capacityPlanDialog`/
`demandForecastDialog`/`replenishmentDialog` functions, `aiInvestigationDialog`,
`integrationsDialog`, `purchaseRequestsDialog`, `marketingBudgetsDialog`,
`approvalsDialog`, and the inline `backup` handler.

The global click-delegation map (`app.mjs:899`) also routes many `data-action`
values to these same dialog functions (e.g. `products: productsDialog`,
`approvals: approvalsDialog`, `ai-brain: aiInvestigationDialog`,
`integrations: integrationsDialog`, `demand-forecast: demandForecastDialog`,
`replenishment: replenishmentDialog`). These delegated routes must be updated in
the same milestones as their sidebar counterparts, or the delegated entry points
will keep opening the modal after the sidebar is migrated.

## 6. Cross-cutting safety surface to preserve

| Concern | Mechanism | Location |
|---|---|---|
| Stale response (pages) | `epoch` + per-view request counters | `app.mjs:19-27` |
| Stale response (dialogs) | `dialogVersion` + per-loader `generation` | `app.mjs:20`, per dialog |
| Pending write recovery | `guardPending()` → `readPending()`/`recover()` + `sessionStorage` draft at `pendingKey()` | `app.mjs:682-784` |
| Modal in-flight guard | `modalBusy`, `unresolved` | `app.mjs:19` |
| Idempotency + actor binding | `api.transaction()` / `api.save()`, `sameActorGuard(actorId)` | `client.mjs`, `app.mjs` |
| Session safety | `sessionWarning`, `LOGOUT_FAILED`/`LOGOUT_UNCERTAIN` flows, `clearWorkspace()` | `app.mjs:61-110` |
| Escaping | `escapeHTML as e` on every interpolated external value | `client.mjs`, throughout |

## 7. Milestone 0 gate

This inventory accounts for every persistent primary sidebar destination: 27
entries, 4 existing pages, 22 legacy dialogs, 1 action-only entry pending a
Milestone F decision, 0 intentional dialogs among primary destinations. No
feature has been migrated. No code outside this document has been changed.

Next: Milestone A — `refactor/workspace-navigation-foundation`. Do not begin
without approval, per roadmap §4 hard-stop rule.
