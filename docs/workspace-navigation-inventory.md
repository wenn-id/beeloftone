# Workspace Navigation Inventory

Program: Beeloft One — Workspace Navigation Architecture Roadmap, Version 1.0
Current milestone: G (Architecture cleanup and consistency verification)
Baseline: `main` @ `af27c4634e52a338fca31c0421d7937477fcd03a`
Branch: `refactor/workspace-navigation-cleanup`
Date: 19 September 2026

The original Milestone 0 inspection used `0748571ade0f8c8da5cdff9ed17dfb8acf746991`.
Historical renderer names, line references and milestone deltas below describe
that migration history. The summary counts and Milestone G current map are the
final-state inventory.

Core rule under inventory: primary navigation must establish context in the main
workspace. A modal is reserved for a focused secondary task (create, edit, review,
confirmation, or record detail). This document records the current state of every
persistent primary sidebar destination so later milestones migrate from evidence
rather than labels.

## 1. Summary counts

| Classification | Count | Destinations |
|---|---|---|
| EXISTING_PAGE | 4 | Command center, Produksi, Bahan baku, Laporan aktivitas |
| LEGACY_DIALOG | 0 | (none) |
| MIGRATED_PAGE | 23 | People, Master SKU, Tanya Beeloft, Integrasi, Audit trail, Inbox approval, Permintaan pembelian, Budget marketing, Scan bundle, Scan barang jadi, Cadangan data, 12 Analitik children (WIP ageing, Kapasitas produksi, Kualitas produksi, Kinerja supplier, Harga bahan, Komitmen PO, Forecast demand, Rekomendasi stok, Analisis ukuran, Analisis retur, Dead stock, Audit adjustment) |
| INTENTIONAL_DIALOG | 0 | (none among primary sidebar destinations) |
| NEEDS_VERIFICATION | 0 | (none) |
| OTHER | 0 | — |
| **Total primary destinations** | **27** | |

Non-destination workspace sections reached by navigation but not present in the
sidebar: `detail-view` (order detail, opened from the production board) and the
shared `analytics-view` host (reached by the twelve Analitik children). Both are
pages, not sidebar destinations, and are out of scope for the migration counts.

After Milestone F, every persistent primary sidebar destination activates a
workspace page. None calls `openDialog()` as its primary experience.

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
| View switching | `showBoard`, `showMaterials`, `showCommandCenter`, `activity` onclick | Each routes through `activateWorkspace()` (Milestone A), which hides every other `workspace-main` section while bumping its request counter, records the active `view`, and moves `aria-current` |

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
- Child dialogs: delegated destinations `replenishment`, `approvals`,
  `jubelio-stock-reconciliation`, `production-quality-insights`, `capacity-plan`,
  `command-workforce`, `mekari-payables-summary`, `mekari-receivables-summary`,
  and `integrations` open dialogs; only `production_overdue` and
  `production_issues` navigate to the board
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
- Renderer: `showPeople` (`app.mjs:3758`, wired `app.mjs:967`); loader
  `loadPeople` (`app.mjs:3769`)
- Interaction: **PAGE** → `people-view` (migrated in Milestone B)
- Data: `GET /api/workforce/employees` + `GET /api/workforce/attendance` (via
  `workforcePage` helper, `app.mjs:3746`); filters: `work_date`, `status`, `q`,
  held in `workforceFilters` and synced into the page filter form on entry
- Mutation: none from the roster surface itself; attendance corrections and
  request decisions are child dialogs with their own idempotency keys
- Access: all roles see roster; `new-employee` admin-only; viewer cannot mutate
- Async: `epoch` + `peopleRequest` + `view === 'people'`
- State: `workforce-message` status region, summary `dl`, empty roster and
  empty-filter states handled
- Child dialogs: `workforceEmployeeForm` (new/edit), `workforceEmployeeHistoryDialog`,
  `workforceAttendanceForm`, `workforceAttendanceHistoryDialog`,
  `workforceRequestsDialog`, `workforceEmployeeMasterDialog`
- Filter state: `workforceFilters` persists in module scope across page revisits;
  reset by `clearWorkspace()` on session switch and by the `command-workforce`
  shortcut
- Target: `people-view` — **MIGRATED_PAGE** (Milestone B)

#### `scan-bundle` — Scan bundle
- Renderer: `showScanner('bundle')`
- Interaction: **PAGE** → `bundle-scan-view`
- Data: `GET /api/bundles/scan?` only on submit; keyboard/QR input and latest
  successful record identity/quantity remain on the page
- Mutation: none on entry or scan; handoff writes remain focused child forms
- Access: all roles scan/read; viewer cannot mutate through child dialogs
- Async: `epoch` + shared `scanRequest` + `view === 'bundle-scan'`; navigation,
  re-entry, and a new submit invalidate older responses
- State: idle, loading, result, error/not-found; resubmit retries the same input;
  input/result survive navigation and child-dialog close until the next scan or logout
- Child dialogs: `bundleDialog`, `bundleHandoffsDialog`, handoff accept/cancel forms
- Target: `bundle-scan-view` (Milestone F) — **MIGRATED_PAGE**

#### `scan-finished-goods` — Scan barang jadi
- Renderer: `showScanner('finished-goods')`
- Interaction: **PAGE** → `finished-goods-scan-view`
- Data: `GET /api/finished-goods-receipts/scan?`
- Mutation: none on entry or scan; receipt operations remain focused child forms
- Access: all roles scan/read; viewer read-only
- Async: `epoch` + shared `scanRequest` + `view === 'finished-goods-scan'`
- State: same scanner contract as bundle; latest result is a scan snapshot,
  while the detail dialog fetches current inventory and record history
- Child dialogs: `finishedGoodsReceiptDialog`, stock traceability, label/print,
  warehouse and marketplace record actions
- Target: `finished-goods-scan-view` (Milestone F) — **MIGRATED_PAGE**

#### `products` — Master SKU
- Renderer: `showProducts` (`app.mjs:877`, wired `app.mjs:965`); loader
  `loadProducts` (`app.mjs:882`); client-side search painter
  `paintProducts` (`app.mjs:897`)
- Interaction: **PAGE** → `products-view` (migrated in Milestone B)
- Data: `GET /api/products` + `GET /api/product-external-mappings` (both via
  `allRows`, `app.mjs:870` — full list, no pagination); cached in `productsCache`
  and re-filtered by the page search field without a new request
- Mutation: none from the list surface; SKU/BOM/mapping writes are child forms
- Access: all roles browse; `new-product`, `edit-bom`, mapping forms admin-only
- Async: `epoch` + `productsRequest` + `view === 'products'`
- State: loading placeholder; empty state ("Belum ada SKU"); filter-empty state
  ("Tidak ada SKU yang cocok dengan pencarian ini."); error with retry
  (`#products-retry`)
- Child dialogs: `productForm` (Tambah SKU), `bomDialog`/`bomForm`/`bomHistoryDialog`,
  `productMappingDialog`/`productMappingForm`/`productMappingHistoryDialog`,
  `unmapProductForm`
- Target: `products-view` — **MIGRATED_PAGE** (Milestone B)

### 4.3 Analitik group — 12 insight children

All twelve previously shared one shape: `openDialog(<title>, <filter form + list
host>)`, a filter form, one `GET /api/<report>` call, and per-report local
`generation` counters layered on `epoch`. All are read-only (no `api.post` on the
primary surface). All were **LEGACY_DIALOG** and are now **MIGRATED_PAGE**
(Milestone C): each sidebar child activates the shared `analytics-view` host
through `activateAnalyticsReport()` and renders into `#analytics-body`.

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

Migration notes for the Milestone C host:
- One host, twelve renderers. `workspaceDestinations` maps all twelve nav ids to
  `analytics-view`; `analyticsReports` maps each nav id to its renderer so
  `reloadAnalytics()` can refresh the active report after a child dialog write.
- Stale-response guard is now `epoch` + `view === 'analytics'` +
  `analyticsReport === <nav id>` + `request === analyticsRequest`. Moving between
  two reports in the same host does not hide the section, so the host bumps
  `analyticsRequest` on every activation, not only on `invalidate()`.
- Filter state persists per report in `analyticsFilters` and is restored on
  re-render, so a child dialog write (e.g. work-center master) does not reset the
  filter the operator set.
- Drill-downs kept their existing behavior: focused record dialogs
  (`purchaseOrderDialog`, `finishedGoodsAdjustmentsDialog`, `finalQcRecordDialog`)
  or navigation to an existing page (`openDetail`).
- Empty state: each report distinguishes "no rows after filter" from loading.
- Error state: `message(..., true)` with a retry button that re-invokes the same
  loader.
- No report writes; viewer access is identical to admin on the read surface. The
  admin-only master kapasitas section is rendered for `role === 'admin'` only.

### 4.4 Group 3 — oversight

#### `ai-brain` — Tanya Beeloft
- Renderer: `showAi` (`app.mjs`, wired `$('ai-brain').onclick=showAi`); page
  renderer `submitAiInvestigation` for the write and `loadAiHistory` for the
  history section
- Interaction: **PAGE** → `ai-view` — prompt, assumptions, result, feedback, and
  investigation history all live on the page
- Data: `POST /api/ai/investigations` (transactional, `api.transaction()` +
  `api.save()`); history via `GET /api/ai/investigations` into `#ai-history-list`
- Mutation: the investigation write is exact-once with a pending draft persisted in
  `sessionStorage` under `pendingKey()`; `sameActorGuard(actorId)` binds the
  transaction to the originating account; re-auth path via `reauthenticate`
- Access: all roles may ask; proposals/execution gated separately
- Async: `epoch` + `aiRequest` (submit) and `aiHistoryRequest` (history), with
  `view==='ai'` in `current()`; lost-response retry reuses the same transaction and
  idempotency key
- State: `ai-message` status, locked form during analysis, re-auth button reveal,
  `ai-history-message` loading/empty/error
- Child dialogs: `aiInvestigationDetailDialog` (saved investigation detail),
  `aiActionProposalDialog`/`aiActionProposalForm` (proposals + execution
  confirmation), feedback via `formDialog`
- Target: `ai-view` (Milestone D) — **MIGRATED_PAGE**
- Protected (must not weaken): pending investigation recovery, snapshot/evidence
  compatibility, lost-response retry, cross-account session guard, exact-once replay

#### `integrations` — Integrasi
- Renderer: `showIntegrations` (`app.mjs`, wired `$('integrations').onclick=showIntegrations`);
  page renderer `loadIntegrations` into `#integrations-body`
- Interaction: **PAGE** → `integrations-view` — health, source-of-truth status,
  latest run, and per-scope state on the page
- Data: `GET /api/integrations`; per-system snapshot summary dialogs each issue
  their own `GET /api/<system>/...` calls
- Mutation: none from the primary surface; run detail and reconciliation are reads
- Access: all roles; admin-only actions where present live in child surfaces
- Async: `epoch` + `integrationsRequest` + `view==='integrations'`
- State: `integrations-message` loading/error with inline retry, health badges
- Child dialogs: `integrationRunsDialog`, `integrationRunDialog`,
  `jubelioStockSnapshotsDialog`/reconciliation, `jubelioOrder/Return/ListingSummary`
  + snapshot dialogs, `mekariFinance/Payables/Receivables/PayrollSummary` + snapshot
  dialogs, `payrollPaymentReconciliationDialog`,
  `payrollAccountingReconciliationDialog`
- Target: `integrations-view` (Milestone D) — **MIGRATED_PAGE**
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
- Nav item hidden unless admin (`app.mjs`)
- Renderer: `showAuditEvents` (`app.mjs`, wired `$('audit-trail').onclick=showAuditEvents`);
  page renderer `loadAuditEvents` into `#audit-body`
- Interaction: **PAGE** → `audit-view` — filters + cursor list on the page
- Data: `GET /api/audit-events?` (cursor `before` pagination, limit 25) +
  `GET /api/users` for actor filter; filters: `q`, `category`, `actor_id`,
  `start_date`, `end_date` (held in `auditFilters`, reset by `clearWorkspace`)
- Mutation: none (immutable audit log)
- Access: admin-only at the nav level; viewer/operator never see the item
- Async: `epoch` + `auditRequest` + `view==='audit'`
- State: loading placeholder, empty state, error with retry
- Child dialogs: `auditEventDialog` (raw event detail)
- Target: `audit-view` (Milestone D); admin-only restriction unchanged —
  **MIGRATED_PAGE**

#### `backup` — Cadangan data
- Renderer: inline onclick activates `backup-view`; purpose/status and
  `download-backup` are persistent page markup
- Interaction: **PAGE**; `GET /api/backup` (blob via `api.download`) only on
  explicit download, never on page entry; no filters or pagination
- Mutation: none (read-only download of the SQLite database)
- Access: admin-only sidebar, activation/download guards, unchanged backend role check
- Async: `epoch` + `backupRequest` + active view/role; navigation/re-entry/session
  switch invalidates late downloads; disabled button prevents duplicate requests
- State: purpose/safety copy retained; preparing, error/retry, download-started
  status; browser filename and backend path/overwrite protection unchanged
- Child dialogs: none
- Verdict: persistent primary sidebar entry for admins; Milestone F resolves
  NEEDS_VERIFICATION to **MIGRATED_PAGE**, following the inventory recommendation

### 4.5 Group 4 tail — business

#### `purchase-requests` — Permintaan pembelian
- Renderer: `showPurchaseRequests` → `loadPurchaseRequests` (page renderer,
  Milestone E); the order-scoped list remains the focused dialog
  `orderPurchaseRequestsDialog(orderId)` from order detail
  (`data-action="order-purchases"`)
- Interaction: **PAGE** — browse/filter/list inside `purchase-requests-view`
- Data: `GET /api/purchase-requests?` — cursor `before` pagination (25/page),
  status filter
- Mutation: none from list; create/decision are child forms
- Access: all roles browse; `new-purchase-request` hidden for viewer
- Async: `epoch` + `purchaseRequestsRequest` + local `generation`
- State: `pr-page-error` alert region, empty-filter state, retry button
- Child dialogs: `purchaseRequestForm` (create), `purchaseRequestDialog` (detail),
  `suppliersDialog`, `purchaseOrdersDialog`
- Target: `purchase-requests-view` — **MIGRATED_PAGE** (Milestone E)

#### `marketing-budgets` — Budget marketing
- Renderer: `showMarketingBudgets` → `loadMarketingBudgets` (page renderer,
  Milestone E)
- Interaction: **PAGE** — budget queue inside `marketing-budgets-view`
- Data: `GET /api/marketing-budget-requests?`
- Mutation: none from list; create/decision are child forms
- Access: all roles browse; `new-marketing-budget` hidden for viewer
- Async: `epoch` + `marketingBudgetsRequest` + local `generation`
- State: error region, empty state, retry
- Child dialogs: `marketingBudgetForm`, `marketingBudgetRequestDialog`,
  decision form via approvals
- Target: `marketing-budgets-view` — **MIGRATED_PAGE** (Milestone E)

### 4.6 CTA card — approval inbox

#### `approvals` — Inbox approval
- Renderer: `showApprovals` → `loadApprovals` (page renderer, Milestone E); also
  reachable as `data-action="approvals"` from many surfaces
- Interaction: **PAGE** — cross-domain decision queue inside `approvals-view`
- Data: `GET /api/approvals?` — **offset** pagination (25/page), filters: status
  (pending/all/approved/rejected/cancelled) and kind
- Mutation: none from the queue surface; approve/reject happen in per-kind
  decision dialogs (`approvalAction[row.kind]`), each with idempotency key +
  actor binding
- Access: all roles see queue; decision authority follows per-kind role rules
- Async: `epoch` + `approvalsRequest` + local `generation`
- State: `approval-error` alert region, empty-filter state, retry
- Cross-domain shortcuts: `purchase-requests`, `marketing-budgets`,
  `workforce-requests`, `mekari-payroll-summary`
- Nine approval kinds in the filter: `purchase_request`, `purchase_order`,
  `supplier_payment`, `marketing_budget`, `production_change`, `workforce_leave`,
  `workforce_overtime`, `payroll_batch`, `ai_action`
- Target: `approvals-view` — **MIGRATED_PAGE** (Milestone E)
- Protected (Milestone E must retain): pending totals above 500, exact money
  arithmetic, all nine kinds, SQLite aggregate-overflow regression, stale decision
  handling, cancellation, lost-response retry, audit event integrity, no duplicate
  mutation

## 5. Handlers that call `openDialog()` as primary experience

None after Milestone F. The scanner handlers use `showScanner()` and the inline
`backup` handler activates `backup-view`. Scanner `data-action` shortcuts also
close their originating dialog through `navigateFromDialog()` before activation.

The twelve Analitik children used to be in this list as
`*InsightsDialog`/`capacityPlanDialog`/`demandForecastDialog`/
`replenishmentDialog`; Milestone C renamed them to `show*` page renderers that
activate `analytics-view` instead. Milestone D removed `auditEventsDialog`,
`aiInvestigationDialog`, and `integrationsDialog` from this list for the same
reason: `showAuditEvents`, `showAi`, and `showIntegrations` activate
`audit-view`, `ai-view`, and `integrations-view`. Milestone E removed
`approvalsDialog`, `marketingBudgetsDialog`, and the primary
`purchaseRequestsDialog` for the same reason: `showApprovals`,
`showMarketingBudgets`, and `showPurchaseRequests` activate `approvals-view`,
`marketing-budgets-view`, and `purchase-requests-view`. The order-scoped
`orderPurchaseRequestsDialog` remains a focused
dialog reached from order detail, not a primary sidebar destination.

The global click-delegation map (`app.mjs:899`) also routes many `data-action`
values to these same dialog functions (e.g. `order-purchases:
() => orderPurchaseRequestsDialog(selected.id)`).
Milestone D repointed the migrated entries at the page renderers
(`ai-brain: () => navigateFromDialog(showAi)`,
`integrations: () => navigateFromDialog(showIntegrations)`,
`audit-events: () => navigateFromDialog(showAuditEvents)`), and the
`ai-investigations` entry was removed together with the history dialog because
the history list is now a section of `ai-view`. The migrated analytics retry
entries route to the page renderers (`demand-forecast: showDemandForecast`,
`replenishment: showReplenishment`, `capacity-plan: showCapacityPlan`,
`production-quality-insights:
showProductionQualityInsights`). Migrated destinations route their delegated
entry points through `navigateFromDialog(show…)` instead, so a "Kembali ke …"
button inside a focused dialog closes that dialog and activates the page rather
than reopening a modal (e.g. `products`, `workforce`, `command-workforce`).
Milestone E repointed the three business-queue entries the same way
(`approvals`, `purchase-requests`, `marketing-budgets`), so cross-navigation
among the approval inbox, PR, marketing, and People surfaces stays coherent.

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

## 8. Milestone A delta — navigation foundation implemented (pending merge)

Milestone A (`refactor/workspace-navigation-foundation`) introduces the single
activation path and did not migrate any feature. Migration counts are unchanged:
4 EXISTING_PAGE, 22 LEGACY_DIALOG, 1 NEEDS_VERIFICATION, 0 MIGRATED_PAGE.

What changed mechanically, without altering any business presentation:

- `activateWorkspace(navId, sectionId)` is the sole entry point for page
  activation. It hides every other `workspace-main` section while bumping that
  section's feature-local request counter, reveals the target, records the active
  `view`, moves `aria-current="page"`, closes the mobile drawer, and settles focus.
- `workspaceDestinations` (sidebar item → section) and `workspaceSections`
  (section → `view` name + `invalidate()` counter bump) are the coordination
  tables. They hold no business logic.
- `showBoard`, `showCommandCenter`, `showMaterials`, the `activity` onclick, and
  `openDetail` now delegate to the helper instead of manual `.hidden` toggles.
- The sidebar click delegation closes the drawer and records focus only for
  destinations that do not yet route through the helper (legacy dialogs).
- Contract and extension guide: `docs/workspace-navigation-architecture.md`.
- Regression: `tests/browser_navigation_foundation.cjs`.

Destinations integrated: `command-center`, `board-home`, `materials`,
`activity`, plus the internal `detail-view` section. Every legacy `*Dialog()`
handler is untouched and still opens the global modal as before.

Next: Milestone B — `refactor/workspace-pages-people-products`. Do not begin
without approval, per roadmap §4 hard-stop rule.

## 9. Milestone B delta — People and Master SKU migrated to pages

Milestone B (`refactor/workspace-pages-people-products`) migrates the first two
legacy dialogs into persistent workspace pages. Migration counts move to
4 EXISTING_PAGE, 20 LEGACY_DIALOG, 1 NEEDS_VERIFICATION, 2 MIGRATED_PAGE.

Destinations integrated: `workforce` → `people-view`, `products` →
`products-view`, both added to `workspaceDestinations` and `workspaceSections`
with feature-local request counters (`peopleRequest`, `productsRequest`).

What changed mechanically, without altering any business calculation or backend
contract:

- `workforceDialog` is replaced by `showPeople` / `loadPeople`. The roster, date
  / status / search filter form, summary, and list render inside `people-view`.
  `workforceFilters` remains the single filter state holder and is re-read on
  every load, so child dialogs cannot desync it.
- `productsDialog` is replaced by `showProducts` / `loadProducts` / 
  `paintProducts`. Browse, search, and Jubelio mapping status render inside
  `products-view`; `productsCache` holds the joined product + mapping rows and
  `paintProducts` re-filters it on keystroke without a network round trip.
- Both loaders mirror `loadMaterials`: per-feature request counter plus module
  `epoch` plus active `view` check, so a stale response arriving after the user
  navigated away is discarded rather than painted.
- Record-specific work stays in focused dialogs opened from the page: Tambah
  karyawan, Ubah karyawan, koreksi kehadiran, riwayat kehadiran, daftar
  karyawan, permintaan cuti / lembur, Tambah SKU, Ubah SKU, BOM, riwayat BOM,
  mapping Jubelio, riwayat mapping.
- In-dialog "Kembali ke roster" / "Kembali ke Master SKU" / "Buka Master SKU"
  routes now go through `navigateFromDialog(show…)`, which closes the focused
  dialog before activating the page. This preserves the old "replace dialog
  content" destination without leaving a modal stacked over a page.
- `formDialog`'s success chain refreshes the parent page instead of a modal when
  the write originated from one: employee writes and attendance corrections call
  `loadPeople()` when `view === 'people'`, mapping writes call `loadProducts()`
  when `view === 'products'` and reopen the mapping dialog, BOM writes reopen
  the BOM dialog, and the generic tail refreshes whichever page is active.
- `clearWorkspace()` bumps both new counters, resets `workforceFilters`, drops
  `productsCache`, and empties both list containers, so a session switch cannot
  paint a previous actor's roster or SKU list.
- Regression: `tests/browser_workforce.cjs` (rewritten for the page), plus
  `tests/browser_navigation_foundation.cjs`, `tests/browser_shared_ui.cjs`,
  `tests/browser_workforce_approvals.cjs`, and `tests/browser_smoke.cjs`
  updated for the page surface.

Next: Milestone C. Do not begin without approval, per roadmap §4 hard-stop rule.

## 10. Milestone C delta — Analytics children migrated to one page host

Milestone C (`refactor/workspace-pages-analytics`) migrates all twelve Analytics
sidebar children out of the global dialog into a single shared workspace page.
Migration counts move to 4 EXISTING_PAGE, 8 LEGACY_DIALOG, 1 NEEDS_VERIFICATION,
14 MIGRATED_PAGE.

Destinations integrated: `wip-ageing-insights`, `capacity-plan`,
`production-quality-insights`, `supplier-performance-insights`,
`material-price-insights`, `purchase-commitment-insights`, `demand-forecast`,
`replenishment`, `size-demand-insights`, `return-insights`,
`dead-stock-insights`, `stock-adjustment-insights` — all twelve map to
`analytics-view` in `workspaceDestinations`, and `workspaceSections` carries one
entry for the host (`view: 'analytics'`, `invalidate()` bumps
`analyticsRequest`).

What changed mechanically, without altering any report formula, endpoint, or
backend contract:

- The twelve `*Dialog()` handlers are renamed `show*()` and now call
  `activateAnalyticsReport(navId, title, content)` instead of `openDialog()`.
  The helper activates the shared host through `activateWorkspace()`, bumps the
  shared request counter, records which report is live, and sets the page
  eyebrow/heading/body in one place.
- One host, twelve reports — the roadmap explicitly forbids twelve static
  sections for symmetry. `analyticsReports` maps nav id → renderer and is used
  by `reloadAnalytics()` so a child dialog write (capacity master, work center,
  routing standard) re-fetches the visible report instead of reopening a modal.
- Stale-response protection extends to the shared host. Switching between two
  analytics children never hides the section, so `invalidate()` alone cannot
  guard the report being left; `activateAnalyticsReport()` bumps
  `analyticsRequest` on every activation and each loader also checks
  `analyticsReport === <navId>` alongside `epoch` and `view === 'analytics'`.
- Report filters survive a child dialog: `analyticsFilters` holds one saved form
  per report (saved on submit, restored after the host re-renders), mirroring
  `workforceFilters` from Milestone B.
- `formDialog`'s success chain gained `view === 'analytics' → reloadAnalytics()`
  between the products and detail branches, so a write performed from an
  analytics page refreshes that page rather than a modal.
- `clearWorkspace()` bumps `analyticsRequest`, clears `analyticsReport` and
  `analyticsFilters`, and empties the host, so a session switch cannot paint a
  previous actor's report.
- Record-specific work stays in focused dialogs opened from the page: PO and
  final-QC drill-downs, order detail, finished-goods adjustment, and the
  capacity master (work center, routing standard, calendar) all open over the
  page and refresh it on save.
- Regression: the eleven existing analytics browser modules were retargeted from
  `dialog` to `#analytics-view`; `tests/browser_return_insights.cjs` is new for
  the twelfth child; `tests/browser_navigation_foundation.cjs` gained a
  twelve-child host sweep and a cross-report stale-response race; and
  `tests/browser_management_command_center.cjs`, `tests/browser_date_boundaries.cjs`,
  `tests/browser_shared_ui.cjs`, and `tests/browser_returns_adjustments.cjs` were
  updated where they drilled into a report that is now a page.

Remaining LEGACY_DIALOG (8): Tanya Beeloft, Integrasi, Audit trail, Inbox
approval, Permintaan pembelian, Budget marketing, Scan bundle, Scan barang jadi.
These are Milestone D/E/F scope.

Next: Milestone D. Do not begin without approval, per roadmap §4 hard-stop rule.

## 11. Milestone D delta — AI, Integrations, and Audit migrated to pages

Milestone D (`refactor/workspace-pages-intelligence-integrations`) migrates the
three oversight destinations out of the global dialog into workspace pages.
Migration counts move to 4 EXISTING_PAGE, 5 LEGACY_DIALOG, 1 NEEDS_VERIFICATION,
17 MIGRATED_PAGE.

Destinations integrated: `ai-brain` → `ai-view`, `integrations` →
`integrations-view`, `audit-trail` → `audit-view`. `workspaceDestinations` maps
all three, and `workspaceSections` carries one entry each (`view: 'ai'`,
`view: 'integrations'`, `view: 'audit'`), each with an `invalidate()` that bumps
its feature-local counter.

What changed mechanically, without altering any endpoint, report logic, or
backend contract:

- `aiInvestigationDialog` → `showAi` + `submitAiInvestigation`; `integrationsDialog`
  → `showIntegrations` + `loadIntegrations`; `auditEventsDialog` →
  `showAuditEvents` + `loadAuditEvents`. All three call `activateWorkspace()` and
  load data into page containers (`#ai-results`/`#ai-history-list`,
  `#integrations-body`, `#audit-body`) instead of `openDialog()`.
- The three show functions keep the `guardPending()` interception the dialog
  openers had, so an unresolved pending write still forces recovery before the
  user can start a new task from that destination.
- Tanya Beeloft's history moved onto the page: `aiInvestigationsDialog` is
  removed and `loadAiHistory()` renders the filter form, cursor list, and
  load-more into `#ai-history` inside `ai-view`. Saved-investigation detail
  (`aiInvestigationDetailDialog`) and action proposals remain focused dialogs.
- The AI write keeps its exact-once contract: `aiTransaction` is module-level
  state (cleared on confirmed success, on non-uncertain failure, and by
  `clearWorkspace()`), the pending draft stays at `pendingKey()` with its
  idempotency key, and lost-response retry reuses both.
- `submitAiInvestigation` guards on `epoch` + `aiRequest` + `view === 'ai'`;
  `loadAiHistory` guards on a separate `aiHistoryRequest` so loading history
  cannot drop an in-flight investigation guard. `modalBusy` is released in the
  `finally` block without a page-active precondition, because a page can be left
  mid-analysis without a dialog close path to reset it.
- `formDialog`'s success chain refreshes `loadAiHistory()` when `view === 'ai'`
  before opening the saved-investigation detail dialog, so a recovery replay
  from the page still lands fresh history behind the dialog.
- Delegated entry points (`ai-brain`, `integrations`, `audit-events`) now route
  through `navigateFromDialog(show…)`, so "Kembali ke …" buttons inside focused
  dialogs close the dialog and activate the page. The `ai-investigations`
  delegation entry was removed with the history dialog; `renderAiInvestigation`'s
  "Riwayat investigasi" button became `data-ai-history`, which closes any open
  dialog, activates `ai-view` if needed, and scrolls to the history section.
- `clearWorkspace()` bumps the three new counters, clears `aiTransaction` and
  `aiHistoryBefore`, and empties the three page containers, so a session switch
  cannot paint a previous actor's AI result, integration status, or audit list.
- Record-specific work stays in focused dialogs opened from the pages: audit-event
  detail, integration run history/detail, per-system snapshot summaries and
  reconciliations, saved-investigation detail, feedback, and action proposals.
- Regression: `tests/browser_navigation_foundation.cjs` gained the three new
  destinations in its one-visible-page/aria-current/no-dialog sweep plus a
  delayed-response race for the audit page; `tests/browser_integrations.cjs` and
  `tests/browser_ai_investigation_logout.cjs` were retargeted from the modal to
  the page, with the logout module asserting the AI failure now surfaces on the
  page and the session banner is reachable rather than trapped behind a modal.

Remaining LEGACY_DIALOG (5): Inbox approval, Permintaan pembelian, Budget
marketing, Scan bundle, Scan barang jadi. These are Milestone E/F scope.

Next: Milestone E. Do not begin without approval, per roadmap §4 hard-stop rule.

## 13. Milestone E delta — approvals, purchasing, and marketing migrated to pages

Milestone E (`refactor/workspace-pages-approvals-business`) migrates the three
cross-domain business queues out of the global dialog into workspace pages.
Migration counts move to 4 EXISTING_PAGE, 2 LEGACY_DIALOG, 1 NEEDS_VERIFICATION,
20 MIGRATED_PAGE.

Destinations integrated: `approvals` → `approvals-view`, `purchase-requests` →
`purchase-requests-view`, `marketing-budgets` → `marketing-budgets-view`.
`workspaceDestinations` maps all three, and `workspaceSections` carries one entry
each (`view: 'approvals'`, `view: 'purchase-requests'`, `view:
'marketing-budgets'`), each with an `invalidate()` that bumps its feature-local
counter.

What changed mechanically, without altering any endpoint, approval semantics, or
backend contract:

- `approvalsDialog` → `showApprovals` + `loadApprovals`; `marketingBudgetsDialog`
  → `showMarketingBudgets` + `loadMarketingBudgets`; the primary
  `purchaseRequestsDialog()` → `showPurchaseRequests` + `loadPurchaseRequests`.
  All three call `activateWorkspace()` and render into page containers
  (`#approvals-body`, `#purchase-requests-body`, `#marketing-budgets-body`)
  instead of `openDialog()`.
- The order-scoped PR list stays a focused dialog, renamed
  `orderPurchaseRequestsDialog(orderId)`, because it is reached from order detail
  (`data-action="order-purchases"`) and scoped to one order rather than being a
  primary destination. Its `pr-status`/`pr-list`/`pr-error`/`pr-more` ids are
  unchanged; the page uses `pr-page-*` ids so the two can never collide in the
  DOM at once.
- The three show functions keep the `guardPending()` interception the dialog
  openers had, so an unresolved pending write still forces recovery before the
  user can start a new task from that destination.
- Filter controls have no module-state persistence. Each render resets them to
  hardcoded defaults: approvals uses `pending` (and kind `all`), while PR and
  marketing both use `all`.
- Pagination models are unchanged: approvals keeps **offset** pagination
  (25/page), PR and marketing keep cursor `before` pagination. Loading, empty,
  filter-empty, error, and retry states live on the page; the retry path keeps
  the existing behaviour of reusing the load-more button as "Coba lagi".
- `formDialog`'s success chain refreshes the owning page through
  `reloadApprovals()` / `reloadPurchaseRequests()` / `reloadMarketingBudgets()`
  when that page is active, before reopening the record detail dialog, so the
  queue behind the dialog reflects the new status without a reopen.
- Delegated entry points (`approvals`, `purchase-requests`, `marketing-budgets`)
  now route through `navigateFromDialog(show…)`, so "Inbox approval", "Semua
  PR", "Semua budget marketing", and "Daftar budget" buttons inside focused
  dialogs close the dialog and activate the page. The order-scoped
  `order-purchases` entry keeps opening its own dialog.
- `clearWorkspace()` bumps the three new counters and empties the three page
  containers; there are no per-page filter objects to reset. This prevents a
  session switch from painting a previous actor's approval queue, PR list, or
  budget list.
- Record-specific work stays in focused dialogs opened from the pages:
  per-kind approval detail and decision forms (`approvalAction[row.kind]`), PR
  create/detail/decision, marketing budget create/detail/decision, suppliers,
  and the PO list.
- The nine approval kinds, aggregate semantics, money arithmetic, idempotency
  keys, actor binding, stale-decision handling, cancellation, lost-response
  retry, and audit-event integrity are untouched. No backend route changed.
- Regression: `tests/browser_navigation_foundation.cjs` gains the three new
  destinations in its one-visible-page/aria-current/no-dialog sweep plus a
  delayed-response race for the approvals page; `browser_unified_approvals.cjs`,
  `browser_purchase_requests.cjs`, and `browser_marketing_budgets.cjs` were
  retargeted from the modal to the page.

Remaining LEGACY_DIALOG (2): Scan bundle, Scan barang jadi. These are Milestone
F scope, alongside the Cadangan data verification.

Next: Milestone F. Do not begin without approval, per roadmap §4 hard-stop rule.

## 13. Milestone F delta — Scanner and utility pages

Baseline: `164d9a54eb7314e2dd738873a1d4264193a19df6` (Milestone E, PR #15 merged).
Branch: `refactor/workspace-pages-utilities`.

- `scan-bundle` → `bundle-scan-view`, `scan-finished-goods` →
  `finished-goods-scan-view`, `backup` → `backup-view`.
- Scanner input and latest successful result live on the page. Opening the
  result's detail button fetches the current record in its existing focused
  dialog; record history, labels/print, and mutations keep their existing flows.
  No new scan-history persistence or endpoint is introduced.
- `showScanner(kind)` shares only the identical lookup lifecycle of the two
  scanners. A request counter plus epoch and active view rejects abandoned
  responses even after leaving and re-entering the same scanner. Desktop entry
  focuses the scan input; mobile drawer navigation keeps heading focus.
- Backup remains an explicit admin download, with the original purpose/safety
  copy, filename, and success/error status. Page entry never downloads. Late
  responses cannot download after navigation or session switch. Backend path
  safety and exclusive-create overwrite protection are unchanged.
- `clearWorkspace()` clears both inputs/results/messages and invalidates scan
  and backup requests. `guardPending()` and the child transaction machinery
  remain intact.
- Activity already routes through `activateWorkspace('activity')`; it was
  verified through the existing foundation regression and was not rewritten.
- Tests: extended real scanner/QR/print/handoff tests and backup download test;
  all three pages join the navigation matrix. `browser_workspace_utilities.cjs`
  checks not-found, retry, delayed re-entry responses, duplicate submit/download,
  escaping, role/session reset, mobile focus, and light/dark responsive layouts.

Inventory delta: 4 EXISTING_PAGE unchanged; LEGACY_DIALOG 2 → 0;
NEEDS_VERIFICATION 1 → 0; MIGRATED_PAGE 20 → 23. Total remains 27.

Next: Milestone G (cleanup and verification), only after F is reviewed and merged.

Local verification (19 September 2026, Windows, Python 3.12.14):

- `python -m unittest discover -s tests -v`: 507 tests, PASS.
- `python -m pip check`: PASS; no broken requirements.
- `python -m compileall -q beeloft`: PASS.
- `node --check beeloft/static/app.mjs` and `node --check beeloft/static/client.mjs`: PASS.
- `node tests/test_client.mjs`: PASS.
- `python tests/run_browser.py --channel chromium` (bundled Playwright module
  supplied through `--playwright-module`): full suite PASS, no JS errors.
  Local Playwright is 1.62.1; CI uses its existing 1.63.0 pin on Linux.
- `python -m build`: sdist and wheel PASS.
- Screenshots reviewed for all three pages at 1440 light/dark, 390 mobile,
  and 320/200% text. Disposable synthetic data only.
- Bundle handoff cancellation and lost-response replay also pass from the new
  scanner page: retry retains its idempotency key and creates one handoff.

The published PR records its actual HEAD and GitHub Core/Browser results;
local passes alone do not establish the roadmap's CI gate.

## 14. Milestone G delta: cleanup and consistency verification

Baseline: `af27c4634e52a338fca31c0421d7937477fcd03a` (F merged as PR #16).
Branch: `refactor/workspace-navigation-cleanup`.

No new destinations are migrated in G. Final inventory stays at 4 EXISTING_PAGE,
23 MIGRATED_PAGE, 0 LEGACY_DIALOG and 0 NEEDS_VERIFICATION, total 27.

| Current sidebar id(s) | Workspace host | Status |
|---|---|---|
| `command-center` | `command-center-view` | EXISTING_PAGE |
| `board-home` | `board-view` | EXISTING_PAGE |
| `materials` | `materials-view` | EXISTING_PAGE |
| `activity` | `activity-view` | EXISTING_PAGE |
| `workforce` | `people-view` | MIGRATED_PAGE |
| `products` | `products-view` | MIGRATED_PAGE |
| `wip-ageing-insights`, `capacity-plan`, `production-quality-insights`, `supplier-performance-insights`, `material-price-insights`, `purchase-commitment-insights`, `demand-forecast`, `replenishment`, `size-demand-insights`, `return-insights`, `dead-stock-insights`, `stock-adjustment-insights` | `analytics-view` | MIGRATED_PAGE (12) |
| `ai-brain` | `ai-view` | MIGRATED_PAGE |
| `integrations` | `integrations-view` | MIGRATED_PAGE |
| `audit-trail` | `audit-view` | MIGRATED_PAGE |
| `approvals` | `approvals-view` | MIGRATED_PAGE |
| `purchase-requests` | `purchase-requests-view` | MIGRATED_PAGE |
| `marketing-budgets` | `marketing-budgets-view` | MIGRATED_PAGE |
| `scan-bundle` | `bundle-scan-view` | MIGRATED_PAGE |
| `scan-finished-goods` | `finished-goods-scan-view` | MIGRATED_PAGE |
| `backup` | `backup-view` | MIGRATED_PAGE |

- All 99 remaining `*Dialog()` functions are accounted for in
  `docs/workspace-dialog-classification.md`: 95 focused secondary entry points
  and four shared lifecycle helpers. No obsolete primary implementation remains.
- Removed the legacy sidebar click/microtask fallback. Normal navigation already
  uses `activateWorkspace()`; pending recovery closes the drawer and saves return
  focus inside `openDialog()`. Recovery, busy/unresolved guards, actor binding,
  exact-once writes and per-feature request counters remain intact.
- Reviewed all dialog-width/scroll rules and markup. Each remaining override has
  live secondary consumers; the single HTML dialog shell is still required.
  Section show/hide logic is already centralized. No CSS, HTML, backend, schema,
  business calculation or endpoint change is needed.
- Static tests compare sidebar ids to registered page hosts and require every
  dialog function to have a classification. The browser sweep compares its
  expected destinations with the real sidebar, preventing new untested items.
- Browser coverage adds all-role keyboard navigation at 1440, 1024, 768, 390 and
  320px/200% in light/dark, one visible page, one `aria-current`, no primary modal
  opening (including transient opens), mobile heading focus and drawer close.
  A separate pending recovery check verifies the original transaction key/actor,
  Escape protection and menu focus after recovery.

G remains a review unit until its actual PR HEAD passes Core and Browser CI and
the PR is reviewed and merged. After that merge, stop the architecture program;
premium refinement starts only as a separately authorized series.

Local verification (19 September 2026, Windows, Python 3.12.14):

- `python -m unittest discover -s tests -v`: 509 tests, PASS.
- `python -m pip check` and `python -m compileall -q beeloft`: PASS.
- `node --check beeloft/static/app.mjs`, `node --check beeloft/static/client.mjs`
  and `node tests/test_client.mjs`: PASS.
- Focused navigation browser module: PASS, including all-role keyboard sweep
  and drawer-interrupted pending recovery.
- `python tests/run_browser.py --channel chromium` with the local bundled
  Playwright module supplied through `--playwright-module`: full suite PASS,
  no JavaScript errors. A previous run was interrupted by `route.fetch: socket
  hang up` in the unchanged settlement test; the complete rerun passed without
  changing that test or its assertions.
- `python -m build`: sdist and wheel PASS; `git diff --check`: PASS.
- Local Playwright is 1.62.1; CI keeps its existing Linux 1.63.0 pin. The PR body
  records actual published HEAD and Core/Browser CI results separately.
