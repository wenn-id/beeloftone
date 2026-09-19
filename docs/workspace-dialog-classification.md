# Remaining dialog classification (Milestone G)

Baseline: `af27c4634e52a338fca31c0421d7937477fcd03a` (Milestone F, PR #16).

Every declared `*Dialog()` function in `beeloft/static/app.mjs` is listed below.
These are reachable secondary tasks or shared dialog infrastructure. None is a
primary sidebar destination. Lists retained here select a record, inspect a
specific order/history, or maintain a supporting master from an owning page;
they do not replace that page's primary roster, report, or queue.

## INTENTIONAL_DIALOG: focused secondary tasks

| Owning context / focused task | Functions retained |
|---|---|
| Audit: inspect one event | `auditEventDialog` |
| Master SKU: mapping and mapping history for one SKU | `productMappingDialog`, `productMappingHistoryDialog` |
| Master SKU / order: BOM and revision history for one SKU | `bomDialog`, `bomHistoryDialog` |
| Production order: changes and approval history | `orderChangesDialog`, `productionChangeRequestsDialog`, `productionChangeRequestDialog` |
| Production order: material requirements, reservations, usage and cost | `requirementsDialog`, `reservationsDialog`, `consumptionDialog`, `productionCostDialog`, `contributionMarginDialog` |
| Production order: cutting records and one run | `cuttingRunsDialog`, `cuttingRunDialog` |
| Production order / scanner: bundles, one bundle and its handoff history | `bundlesDialog`, `bundleDialog`, `bundleHandoffsDialog` |
| Production order: sewing jobs and one job | `sewingJobsDialog`, `sewingJobDialog` |
| Production order: finishing records and one record | `finishingRecordsDialog`, `finishingRecordDialog` |
| Production order: final QC records and one inspection | `finalQcRecordsDialog`, `finalQcRecordDialog` |
| Production order / QC: rework completion history and one completion | `reworkCompletionsDialog`, `finalQcReworkCompletionsDialog`, `reworkCompletionDialog` |
| Production order / scanner: finished goods receipts and receipt lineage | `finishedGoodsDialog`, `finishedGoodsReceiptDialog`, `finishedGoodsTraceabilityDialog` |
| Production order: warehouse stock and one movement | `warehouseDialog`, `warehouseMovementDialog` |
| Production order: marketplace reservations and one reservation | `marketplaceReservationsDialog`, `marketplaceReservationDialog` |
| Production order: picks and one pick | `marketplacePicksDialog`, `marketplacePickDialog` |
| Production order: packs and one pack | `marketplacePacksDialog`, `marketplacePackDialog` |
| Production order: shipments, one shipment and one settlement | `marketplaceShipmentsDialog`, `marketplaceShipmentDialog`, `marketplaceSaleSettlementDialog` |
| Production order: customer returns and one return | `marketplaceReturnsDialog`, `marketplaceReturnDialog` |
| Production order / analytics: stock adjustments and one adjustment | `finishedGoodsAdjustmentsDialog`, `finishedGoodsAdjustmentDialog` |
| Production order: stock counts and one count | `finishedGoodsStockCountsDialog`, `finishedGoodsStockCountDialog` |
| Integrations: select an immutable run and inspect its detail | `integrationRunsDialog`, `integrationRunDialog` |
| Integrations / command center: compare the latest Jubelio stock snapshot; inspect snapshot history or a batch | `jubelioStockReconciliationDialog`, `jubelioStockSnapshotsDialog`, `jubelioStockSnapshotDialog` |
| Integrations: inspect Jubelio order snapshots | `jubelioOrderSummaryDialog`, `jubelioOrderSnapshotsDialog`, `jubelioOrderSnapshotDialog` |
| Integrations: inspect Jubelio return snapshots | `jubelioReturnSummaryDialog`, `jubelioReturnSnapshotsDialog`, `jubelioReturnSnapshotDialog` |
| Integrations: inspect Jubelio listing snapshots | `jubelioListingSummaryDialog`, `jubelioListingSnapshotsDialog`, `jubelioListingSnapshotDialog` |
| Integrations: inspect Mekari finance snapshots | `mekariFinanceSummaryDialog`, `mekariFinanceSnapshotsDialog`, `mekariFinanceSnapshotDialog` |
| Integrations / command center: inspect Mekari payable snapshots | `mekariPayablesSummaryDialog`, `mekariPayableSnapshotsDialog`, `mekariPayableSnapshotDialog` |
| Integrations / command center: inspect Mekari receivable snapshots | `mekariReceivablesSummaryDialog`, `mekariReceivableSnapshotsDialog`, `mekariReceivableSnapshotDialog` |
| Integrations: inspect payroll snapshots and reconcile payment/accounting evidence | `mekariPayrollSummaryDialog`, `mekariPayrollSnapshotsDialog`, `mekariPayrollSnapshotDialog`, `payrollPaymentReconciliationDialog`, `payrollAccountingReconciliationDialog` |
| AI / approvals: inspect one saved investigation or action proposal | `aiInvestigationDetailDialog`, `aiActionProposalDialog` |
| Payroll / approvals: review one payroll approval request | `payrollApprovalRequestDialog` |
| People: select an employee for master maintenance; inspect employee or attendance revisions | `workforceEmployeeMasterDialog`, `workforceEmployeeHistoryDialog`, `workforceAttendanceHistoryDialog` |
| People / approvals: select and review leave/overtime requests | `workforceRequestsDialog`, `workforceRequestDialog` |
| Marketing / approvals: review one budget request | `marketingBudgetRequestDialog` |
| Production order / purchasing / approvals: PRs for one order and one PR | `orderPurchaseRequestsDialog`, `purchaseRequestDialog` |
| Purchasing: maintain supporting suppliers; select and review a PO | `suppliersDialog`, `purchaseOrdersDialog`, `purchaseOrderDialog` |
| Purchasing / approvals: inspect incoming QC or one supplier payment request | `qualityIntakeDialog`, `supplierPaymentRequestDialog` |
| Materials: scan one batch, maintain material master, inspect batch/order history and batch lineage | `materialBatchScanDialog`, `materialMasterDialog`, `materialHistoryDialog`, `materialBatchTraceabilityDialog` |

## Shared infrastructure (not destinations)

| Function | Purpose |
|---|---|
| `openDialog` | Opens the single focused-task shell; closes an open mobile drawer and remembers the menu toggle for pending recovery. |
| `closeDialog` | Closes only when no write is busy or unresolved. |
| `formDialog` | Shared create/edit/decision/recovery form with actor-bound idempotent writes. |
| `navigateFromDialog` | Closes a secondary dialog before activating its owning workspace page. |

Forms and label renderers without a `Dialog` suffix also use the same shell.
Their create/edit/decision/print flows, including capacity master forms, remain
unchanged. `guardPending()` may open recovery instead of honoring navigation;
that is an unresolved transaction task, not a legacy primary destination.

## Obsolete primary dialogs and markup

No obsolete primary `*Dialog()` implementation remains at this baseline.
Milestones B-F already removed/replaced the People, Master SKU, twelve analytics,
AI investigation/history, integrations, audit, approvals, purchasing, marketing,
bundle scanner, finished-goods scanner and backup primary modal paths. The
unscoped PR workspace is a page; the retained PR dialog has an order context.
`index.html` contains one empty shared dialog shell, not full-feature modal
templates. No live task or markup is deleted simply because its name is plural.

The obsolete sidebar click/microtask fallback for legacy modal destinations is
removed in G. Workspace activation alone handles normal drawer navigation;
`openDialog()` handles the recovery exception at its source. Section visibility
already has a single writer in `activateWorkspace()`; session login/logout
visibility and feature loading/empty states are separate concerns and retained.

## Width and scroll rules reviewed

| Rule | Decision and live consumer |
|---|---|
| Base `dialog` width, max-height, mobile padding and chrome | Retain for focused forms/details. |
| `dialog:has(.workforce-screen)` 960px width | Retain: employee master and leave/overtime request selection still emit `.workforce-screen`. This is not dead roster-only CSS. |
| `.product-list` scroll cap and `.workforce-master` cap | Retain for employee/material/supplier master lists in secondary dialogs. |
| `#products-view .product-list` uncapped page list | Retain: keeps the primary SKU page in the document scroll flow. |
| Print `#dialog[open]` width and `.bundle-label` 80mm output | Retain for existing focused labels; scanner migration did not remove printing. |

There are no unused primary-only dialog-width overrides to remove. No CSS or
HTML redesign is needed for this cleanup.

## Regression evidence

`tests/test_workspace_navigation.py` compares the actual sidebar with the
destination registry/section hosts and requires this classification to account
for every declared dialog function. `tests/browser_navigation_foundation.cjs`
compares its click sweep to the actual sidebar, checks workspace/ARIA/no-dialog
behavior across roles and mobile themes, and exercises pending recovery from
the drawer. Existing domain, transaction, session, print and responsive suites
remain the behavioral authority for each retained secondary task.
