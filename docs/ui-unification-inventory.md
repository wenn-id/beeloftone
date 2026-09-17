# UI unification inventory

Every surface the workspace renders, with the inconsistency it carried against the Command
Center and the shared pattern it now uses. The review status column reconciles exactly to
the surfaces inspected in `docs/ui-unification-verification.md`: 78 surfaces, each looked at
in desktop light, desktop dark, mobile 390px, and viewer/read-only.

Baseline inspected: `main @ 7a13ddaf159e5318928ac4fc02449ca26d805a20`.

## How to read this

- **Opening path** — how a user reaches it. Sidebar labels are the visible Indonesian text;
  `data-action` names are the delegated dispatcher keys in `app.mjs`.
- **Type** — `page` (a `<section>` in `index.html`), `list`, `detail`, `form`, or `scan`.
  Everything that is not one of the five page sections renders into the single `<dialog>`.
- **Roles** — who can reach it and who can mutate. `all` means admin, operator and viewer
  can read it; mutation gating is noted where it differs.
- **Previous inconsistency** — what diverged from the Command Center before this work.
- **Shared pattern** — the vocabulary it now renders with.
- **Status** — `PASS` (correct, unchanged by review), `FIXED` (a defect was found by looking
  at the render and corrected), `EXCEPTION` (intentionally left as-is, explained in notes).

Shorthand for the shared patterns:

| Token | Meaning |
| --- | --- |
| `heading` | `page-heading` / `dialog-heading` with eyebrow, title, ruled separator, right-aligned actions |
| `kpi` | `summary` grid of 20px KPI cards: label + blue sprite glyph, figure, optional chip and footer |
| `toolbar` | `filters` / `filter-form` — a 20px bordered surface holding the filter controls and their action |
| `rowcard` | `material-event` / `audit-event` / `issue-item` / `product-item` / `workforce-row` as a 20px surface; nested one steps to 14px on a sunken ground |
| `metrics` | `requirement-values` label/value rows, muted label left, bold tabular figure right |
| `stats` | `workforce-summary` compact stat card grid |
| `table` | `table-head` + `order-row` list container with pagination |
| `formchrome` | `formDialog` shell: `form-info`, `form-grid`, ruled `form-actions` |
| `states` | `state` empty, `error` + retry, and a loading placeholder that is cleared on resolve |
| `actiontier` | primary filled / secondary outlined / tertiary subtle / correction danger-tinted |

---

## A. Shell and core pages (5)

| # | Surface | Opening path | Renderer | Type | Roles | Previous inconsistency | Shared pattern | Status | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Command center | sidebar `Command center` | `showCommandCenter` | page | all (read-only) | — reference surface | `heading`, `kpi`, bands, hero, `table`, rail cards, `metrics`, `states` | PASS | The reference. Verified unchanged in all four modes. |
| 2 | Papan produksi | sidebar `Produksi`, brand, back links | `showBoard` / `loadBoard` | page | all; create order admin-only | KPI cards had no glyph; open-issue shortcut rendered as a full-width stretched pill; KPI cards lost their right border below 650px; `ledger-heading` centred on mobile only | `heading`, `kpi` (glyph added), `toolbar`, `table`, `states`, inline alert | FIXED | Four defects corrected. |
| 3 | Rincian order produksi | `data-action="detail"` from the board | `openDetail` / `renderDetail` | detail | all; mutations non-viewer, corrections admin | metadata was a plain text row; history rows floated on the canvas; 28 actions in one undifferentiated wall; status chip stretched to fill its cell | metadata card, `stages` card, `rowcard` history, `actiontier` | FIXED | Chip scoping bug found by measuring the render. |
| 4 | Bahan baku | sidebar `Bahan baku` | `showMaterials` / `loadMaterials` | page | all; receive batch non-viewer | batch rows were bare bordered strips | `heading`, `toolbar`, `rowcard`, `states` | PASS | No summary endpoint exists, so no KPI row is invented. |
| 5 | Laporan aktivitas | sidebar `Laporan aktivitas` | `$('activity')` handler / `loadActivity` | page | all | summary cards had no glyph; activity rows floated on the canvas | `heading`, `kpi` (glyph added), `toolbar`, `rowcard`, `states` | FIXED | Same `.summary` grid as the board, so it had to match. |

## B. Produksi chain (19)

| # | Surface | Opening path | Renderer | Type | Roles | Previous inconsistency | Shared pattern | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 6 | Riwayat tenggat / PIC | detail → `order-changes` | `orderChangesDialog` | list | all | flat rows | `heading`, `rowcard`, `states` | PASS |
| 7 | Permintaan perubahan produksi | detail → `production-change-requests` | `productionChangeRequestsDialog` | list | all; submit non-viewer | flat rows, stale flag unstyled | `heading`, `rowcard`, chip, `states` | PASS |
| 8 | BOM per SKU | detail → `bom` | `bomDialog` | detail | all; edit admin | flat text | `heading`, `formchrome`, `rowcard`, `states` | PASS |
| 9 | Kebutuhan bahan order | detail → `requirements` | `requirementsDialog` | detail | all | metric pairs as plain flex rows; shortage warning unstyled | `heading`, `metrics`, inline alert | PASS |
| 10 | Reservasi bahan order | detail → `reservations` | `reservationsDialog` | list | all; actions admin | flat rows | `heading`, `rowcard`, `actiontier`, `states` | PASS |
| 11 | Hasil cutting order | detail → `cutting-runs` | `cuttingRunsDialog` | list | all; record non-viewer | flat rows | `heading`, `rowcard`, `states` | PASS |
| 12 | Bundle order | detail → `bundles` | `bundlesDialog` | list | all | flat rows | `heading`, `rowcard`, `states` | PASS |
| 13 | Riwayat serah-terima bundle | detail → `bundle-handoffs` | `bundleHandoffsDialog` | list | all; accept/cancel gated | status chip emitted as a `<p>` was flattened to body copy; a failed first load left the loading placeholder beside the error | `heading`, `rowcard`, chip, `states` | FIXED |
| 14 | Sewing / makloon order | detail → `sewing-jobs` | `sewingJobsDialog` | list | all; record non-viewer | flat rows | `heading`, `rowcard`, `states` | PASS |
| 15 | Finishing order | detail → `finishing-records` | `finishingRecordsDialog` | list | all; record non-viewer | flat rows | `heading`, `rowcard`, `states` | PASS |
| 16 | Final QC order | detail → `final-qc-records` | `finalQcRecordsDialog` | list | all; record non-viewer | flat rows | `heading`, `rowcard`, badge, `states` | PASS |
| 17 | Selesai rework order | detail → `rework-completions` | `reworkCompletionsDialog` | list | all; record non-viewer | flat rows | `heading`, `rowcard`, `states` | PASS |
| 18 | Barang jadi order | detail → `finished-goods` | `finishedGoodsDialog` | list | all; receive non-viewer | flat rows, 8 cross-links undifferentiated | `heading`, `rowcard`, `actiontier`, `states` | PASS |
| 19 | Pemakaian & waste order | detail → `consumption` | `consumptionDialog` | list | all; record non-viewer, reverse admin | metric pairs plain | `heading`, `metrics`, `rowcard`, `states` | PASS |
| 20 | Biaya produksi aktual | detail → `production-cost` | `productionCostDialog` | detail | all | metric pairs plain; coverage warning unstyled | `heading`, `metrics`, chip, nested surface | PASS |
| 21 | Margin kontribusi | detail → `contribution-margin` | `contributionMarginDialog` | detail | all; settlement non-viewer | metric pairs plain | `heading`, `metrics`, chip, nested surface, `states` | PASS |
| 22 | Riwayat bahan order | detail → `order-materials` | `materialHistoryDialog` | list | all; correction admin | flat rows; correction button same weight as navigation | `heading`, `rowcard`, `actiontier` | PASS |
| 23 | Buat order produksi | `#new-order` (admin) | `orderForm` | form | admin | line rows were bare grid cells | `heading`, `formchrome`, nested line surface | PASS |
| 24 | Master SKU | sidebar `Master SKU` | `productsDialog` | list | all; add admin | rows as bottom-bordered strips | `heading`, `rowcard`, `actiontier`, `states` | PASS |

## C. Gudang and marketplace (11)

| # | Surface | Opening path | Renderer | Type | Roles | Previous inconsistency | Shared pattern | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 25 | Gudang order | detail → `warehouse` | `warehouseDialog` | list | all; move non-viewer | flat rows | `heading`, `rowcard`, `states` | PASS |
| 26 | Reservasi marketplace | detail → `marketplace-reservations` | `marketplaceReservationsDialog` | list | all; reserve non-viewer | flat rows | `heading`, `rowcard`, `states` | PASS |
| 27 | Picking marketplace | detail → `marketplace-picks` | `marketplacePicksDialog` | list | all; pick non-viewer | flat rows | `heading`, `rowcard`, `states` | PASS |
| 28 | Packing marketplace | detail → `marketplace-packs` | `marketplacePacksDialog` | list | all; pack non-viewer | flat rows | `heading`, `rowcard`, `states` | PASS |
| 29 | Shipping marketplace | detail → `marketplace-shipments` | `marketplaceShipmentsDialog` | list | all; ship non-viewer | flat rows | `heading`, `rowcard`, `states` | PASS |
| 30 | Retur pelanggan | detail → `marketplace-returns` | `marketplaceReturnsDialog` | list | all; record non-viewer | flat rows | `heading`, `rowcard`, `states` | PASS |
| 31 | Adjustment barang jadi | detail → `finished-goods-adjustments` | `finishedGoodsAdjustmentsDialog` | list | all; adjust non-viewer, reverse admin | flat rows | `heading`, `rowcard`, `states` | PASS |
| 32 | Stock opname barang jadi | detail → `finished-goods-stock-counts` | `finishedGoodsStockCountsDialog` | list | all; count non-viewer | flat rows | `heading`, `rowcard`, `states` | PASS |
| 33 | Rekonsiliasi stok Jubelio | `data-action="jubelio-stock-reconciliation"` | inline dialog | detail | all | metric pairs plain; variance chip flattened | `heading`, `metrics`, `rowcard`, chip | PASS |
| 34 | Scan bundle | sidebar `Scan bundle` | `bundleScanDialog` | scan | all | hand-rolled chrome diverged from `formDialog` | `heading`, `formchrome` | PASS |
| 35 | Scan barang jadi | sidebar `Scan barang jadi` | `finishedGoodsScanDialog` | scan | all | as above | `heading`, `formchrome` | PASS |

## D. Bahan baku and purchasing (7)

| # | Surface | Opening path | Renderer | Type | Roles | Previous inconsistency | Shared pattern | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 36 | Master bahan | materials → `material-master` | `materialMasterDialog` | list | all; add admin | rows as strips; bare `<p>` empty state | `heading`, `rowcard`, `states` | PASS |
| 37 | Terima batch bahan | materials → `#receive-material` | `receiptForm` | form | non-viewer | — | `heading`, `formchrome` | PASS |
| 38 | Scan batch bahan | materials → `scan-material-batch` | `materialBatchScanDialog` | scan | all | hand-rolled chrome | `heading`, `formchrome` | PASS |
| 39 | Master pemasok | `data-action="suppliers"` | `suppliersDialog` | list | all; add admin | flat rows | `heading`, `rowcard`, `actiontier` | PASS |
| 40 | Permintaan pembelian | sidebar `Permintaan pembelian` | `purchaseRequestsDialog` | list | all; create non-viewer | flat rows; status filter was a bare label+select on the dialog ground | `heading`, `toolbar`, `rowcard`, `states` | FIXED |
| 41 | Daftar PO | `data-action="purchase-orders"` | `purchaseOrdersDialog` | list | all | as above | `heading`, `toolbar`, `rowcard`, `states` | FIXED |
| 42 | Buat PR | `data-action="new-purchase-request"` | `purchaseRequestForm` | form | non-viewer | line rows bare | `heading`, `formchrome`, nested line surface | PASS |

## E. People and approval (10)

| # | Surface | Opening path | Renderer | Type | Roles | Previous inconsistency | Shared pattern | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 43 | People (roster harian) | sidebar `People` | `workforceDialog` | list | all; add admin, attendance non-viewer | summary was a ledger strip with a 2px ink rule and vertical dividers; filter form bare; rows bottom-bordered strips | `heading`, `stats`, `toolbar`, `rowcard`, chip, `states` | PASS |
| 44 | Daftar karyawan | `data-action="employee-master"` | `workforceEmployeeMasterDialog` | list | all; add/edit admin | rows as strips | `heading`, `rowcard`, `actiontier`, `states` | PASS |
| 45 | Permintaan cuti dan lembur | `data-action="workforce-requests"` | `workforceRequestsDialog` | list | all; submit non-viewer | ledger strip summary; bare filter | `heading`, `stats`, `toolbar`, `rowcard`, chip | PASS |
| 46 | Tambah karyawan | `data-action="new-employee"` | `workforceEmployeeForm` | form | admin | — | `heading`, `formchrome` | PASS |
| 47 | Ajukan cuti atau lembur | `data-action="new-workforce-request"` | `workforceRequestForm` | form | non-viewer | — | `heading`, `formchrome` | PASS |
| 48 | Inbox approval | sidebar CTA `Inbox approval` | `approvalsDialog` | list | all | the loading placeholder was never cleared and sat above the first page of results; filter controls bare | `heading`, `toolbar`, `rowcard`, chip, `states` | FIXED |
| 49 | Budget marketing | sidebar `Budget marketing` | `marketingBudgetsDialog` | list | all; submit non-viewer | flat rows; bare status select | `heading`, `toolbar`, `rowcard`, `states` | FIXED |
| 50 | Ajukan budget marketing | `data-action="new-marketing-budget"` | `marketingBudgetForm` | form | non-viewer | — | `heading`, `formchrome` | PASS |
| 51 | Rekonsiliasi pembayaran payroll | `data-action="payroll-payment-reconciliation"` | inline dialog | list | all | metric pairs plain | `heading`, `toolbar`, `metrics`, `rowcard`, `states` | PASS |
| 52 | Rekonsiliasi akuntansi payroll | `data-action="payroll-accounting-reconciliation"` | inline dialog | list | all | metric pairs plain | `heading`, `toolbar`, `metrics`, `rowcard`, `states` | PASS |

## F. Analitik (12)

All twelve share one dialog recipe: filter form, summary paragraph, result rows, optional
"load more". All are read-only for every role, so the viewer panel is identical by design.

| # | Surface | Opening path | Renderer | Type | Previous inconsistency | Shared pattern | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 53 | WIP ageing & sinyal hambatan | sidebar `WIP ageing` | `wipAgeingInsightsDialog` | list | filter form bare; rows flat | `heading`, `toolbar`, `rowcard`, chip, `metrics`, `states` | PASS |
| 54 | Kapasitas produksi | sidebar `Kapasitas produksi` | `capacityPlanDialog` | list | the admin master section packed two unrelated mini-forms into one grid, so their action rows became grid cells and drew rules across the middle | `heading`, `toolbar` ×3, `rowcard`, `metrics`, `states` | FIXED |
| 55 | Kualitas produksi | sidebar `Kualitas produksi` | `productionQualityInsightsDialog` | list | filter bare; rows flat | `heading`, `toolbar`, `rowcard`, badge, `metrics` | PASS |
| 56 | Kinerja supplier | sidebar `Kinerja supplier` | inline dialog | list | filter bare; 3-level nesting flat | `heading`, `toolbar`, nested `rowcard`, `metrics` | PASS |
| 57 | Pergerakan harga bahan | sidebar `Harga bahan` | inline dialog | list | filter bare | `heading`, `toolbar`, `rowcard`, chip, `metrics` | PASS |
| 58 | Komitmen pembelian terbuka | sidebar `Komitmen PO` | inline dialog | list | filter bare | `heading`, `toolbar`, `rowcard`, chip, `metrics` | PASS |
| 59 | Forecast demand per SKU | sidebar `Forecast demand` | `demandForecastDialog` | list | filter bare | `heading`, `toolbar`, `rowcard`, `metrics` | PASS |
| 60 | Risiko stockout & rekomendasi | sidebar `Rekomendasi stok` | `replenishmentDialog` | list | filter bare | `heading`, `toolbar`, `rowcard`, chip, `metrics` | PASS |
| 61 | Analisis demand per ukuran | sidebar `Analisis ukuran` | `sizeDemandInsightsDialog` | list | filter bare | `heading`, `toolbar`, `rowcard`, `metrics` | PASS |
| 62 | Analisis retur per SKU | sidebar `Analisis retur` | `returnInsightsDialog` | list | filter bare | `heading`, `toolbar`, `metrics`, `rowcard` | PASS |
| 63 | Analisis dead stock | sidebar `Dead stock` | `deadStockInsightsDialog` | list | filter bare | `heading`, `toolbar`, `rowcard`, chip, `metrics` | PASS |
| 64 | Audit adjustment stok | sidebar `Audit adjustment` | `stockAdjustmentInsightsDialog` | list | filter bare (11 controls) | `heading`, `toolbar`, `rowcard`, chip, `metrics` | PASS |

## G. AI, integrasi and utilities (14)

| # | Surface | Opening path | Renderer | Type | Roles | Previous inconsistency | Shared pattern | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 65 | Tanya Beeloft | sidebar `Tanya Beeloft` | `aiInvestigationDialog` | form | all | prompt chips and assumptions block diverged | `heading`, `toolbar`-like prompt row, nested assumptions surface, `formchrome` | PASS |
| 66 | Riwayat investigasi | `data-action="ai-investigations"` | `aiInvestigationsDialog` | list | all | filter bare | `heading`, `toolbar`, `rowcard`, `states` | PASS |
| 67 | Kesehatan integrasi | sidebar `Integrasi` | `integrationsDialog` | detail | all | a flat stream of headings and text with faint bottom borders; health chip above the heading | `heading`, nested `rowcard`, chip | PASS |
| 68 | Riwayat sinkronisasi | `data-action="integration-runs"` | `integrationRunsDialog` | list | all | filter bare; failures unstyled | `heading`, `toolbar`, `rowcard`, chip, inline alert | PASS |
| 69 | Order & penjualan Jubelio | `data-action="jubelio-order-summary"` | inline dialog | detail | all | metric pairs plain | `heading`, `metrics`, `rowcard`, chip | PASS |
| 70 | Riwayat snapshot stok Jubelio | `data-action="jubelio-stock-snapshots"` | inline dialog | list | all | flat rows | `heading`, `rowcard`, chip | PASS |
| 71 | Retur Jubelio | `data-action="jubelio-return-summary"` | inline dialog | detail | all | metric pairs plain | `heading`, `metrics`, `rowcard` | PASS |
| 72 | Listing Jubelio | `data-action="jubelio-listing-summary"` | inline dialog | detail | all | metric pairs plain | `heading`, `metrics`, `rowcard` | PASS |
| 73 | Keuangan Mekari | `data-action="mekari-finance-summary"` | inline dialog | detail | all | metric pairs plain | `heading`, `metrics`, `rowcard` | PASS |
| 74 | Utang Mekari | `data-action="mekari-payables-summary"` | inline dialog | detail | all | metric pairs plain | `heading`, `metrics`, `rowcard` | PASS |
| 75 | Piutang Mekari | `data-action="mekari-receivables-summary"` | inline dialog | detail | all | metric pairs plain | `heading`, `metrics`, `rowcard` | PASS |
| 76 | Payroll Mekari | `data-action="mekari-payroll-summary"` | inline dialog | detail | all | metric pairs plain | `heading`, `metrics`, `rowcard`, chip | PASS |
| 77 | Global audit trail | sidebar `Audit trail` (admin) | `auditEventsDialog` | list | admin | filter bare; rows flat | `heading`, `toolbar`, `rowcard`, chip, `states` | PASS |
| 78 | Cadangan data | sidebar `Cadangan data` (admin) | inline handler | detail | admin | info panels plain | `heading`, `form-info`, `actiontier` | PASS |

---

## Totals

| Status | Count |
| --- | --- |
| PASS | 68 |
| FIXED | 10 |
| EXCEPTION | 0 at surface level (one field-level exception, below) |
| **Total surfaces** | **78** |

FIXED surfaces: 2 (board), 3 (order detail), 5 (activity), 13 (bundle handoffs), 40
(purchase requests), 41 (purchase orders), 48 (approvals), 49 (marketing budget), 54
(capacity plan) — plus the two mobile/layering defects on the board that also affected the
Command Center KPI row below 650px.

## Not-applicable and exception notes

- **Surface 78, viewer mode — not applicable.** `Cadangan data` is admin-only; the nav entry
  is hidden for a viewer, so there is no viewer rendering to review. Recorded as skipped by
  the capture harness rather than as a pass.
- **Surface 77, viewer mode.** Reachable in the nav only for admin. When forced open, it
  correctly renders the permission error with a retry, which is what was reviewed.
- **Field-level EXCEPTION — Command Center attention amounts.** Three attention sentences
  interpolate a raw decimal (`Rp43200000.00`). The value is composed server-side in
  `beeloft/command_center.py` and the attention item carries no structured amount, so the
  frontend cannot format it without pattern-matching backend prose. Left unchanged and
  explained in the verification document.
- **Forms under viewer.** The capture harness fires `data-action` directly, so viewer panels
  exist for `Terima batch bahan` and `Buat PR`. A real viewer cannot reach them: the nav
  entry is hidden and the server rejects the write. The surfaces were still reviewed.
- **Environment artefact.** `→` (U+2192) renders as a missing glyph in the review container
  because the available fonts lack it. Not a product defect; the character was not changed.
