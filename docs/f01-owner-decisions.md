# Paket Keputusan F01 — untuk review pemilik

Issue [#40](https://github.com/wenn-id/beeloftone/issues/40) · Draft PR [#109](https://github.com/wenn-id/beeloftone/pull/109)
Baseline: `96bb48fa8889b3a483411768e2543838e69233b0` (v0.114.0/schema 55).
**Status:** IN_PROGRESS / bukti transaksi belum lengkap. Tidak ada persetujuan yang dicatat. Semua usulan tetap `PROPOSED`; #40 tetap OPEN.

## Cara membaca

- **Legacy terbukti** berarti hanya hal yang tertulis pada audit UI terdahulu di issue #40 atau issue #108; bukan pembuktian formula/backend atau pemakaian perusahaan secara menyeluruh.
- **Belum diketahui** menyebut bukti transaksi/role/dokumen yang belum tersedia.
- **Usulan One** adalah rekomendasi, bukan aturan berjalan dan bukan persetujuan.
- Contoh angka/alur bertanda **sintetis** tidak membuktikan legacy.
- `READY_TO_DECIDE` berarti arah kebijakan target dapat dipilih dengan catatan evidensial; bukan berarti legacy sudah dipahami atau keputusan diterima untuk freeze.

## Status akses dan kerja

- Issue #40 mencatat audit UI terdahulu pada 27 September 2026 (tanggal saja; jam observasi, filter, sampel, screenshot, dan nilai transaksi tidak tercatat di sumber yang tersedia). Issue #40 melaporkan dashboard + 30 menu, 8 form, dan satu detail payroll.
- Percobaan sesi sekarang gagal sebelum login: `browser-harness: daemon default didn't come up`; native desktop melaporkan `windows: []`. Tidak ada kredensial dimasukkan, tidak ada sampel transaksi baru dibuka.
- Belum ditelusuri: job → slip → pembayaran → kasbon; invoice/tender POS; AP → PO/receipt → pembayaran; rincian file download; role/permission.
- Sumber audit tidak mendukung klaim `/settings/periods` pernah diamati. Statusnya `UNVERIFIED`; bukan bukti route itu tidak ada.

## Daftar ringkas D01–D20

| ID | Status aturan legacy | Status target One | Bukti | Kesiapan pertanyaan owner |
|---|---|---|---|---|
| D01 | `PRIOR_AUDIT_REPORTED` / lihat rincian | `PROPOSED` | `EV-F01-0008`, `EV-F01-0009`, `EV-F01-0012` | `BLOCKED_BY_FIELD_AND_TRANSACTION_EVIDENCE` |
| D02 | `PRIOR_AUDIT_REPORTED` / lihat rincian | `PROPOSED` | `EV-F01-0011` | `NEEDS_LEGACY_TRACE` |
| D03 | `PRIOR_AUDIT_REPORTED` / lihat rincian | `PROPOSED` | `EV-F01-0011` | `NEEDS_TRANSACTION_TRACE` |
| D04 | `PRIOR_AUDIT_REPORTED` / lihat rincian | `PROPOSED` | `EV-F01-0003`, `EV-F01-0009`, `EV-F01-0010` | `NEEDS_SLIP_AND_HISTORY_TRACE` |
| D05 | `PRIOR_AUDIT_REPORTED` / lihat rincian | `PROPOSED` | `EV-F01-0003` | `NEEDS_OWNER_AND_LEGACY_CASES` |
| D06 | `PRIOR_AUDIT_REPORTED` / lihat rincian | `PROPOSED` | `EV-F01-0002` | `NEEDS_SLIP_TRACE` |
| D07 | `PRIOR_AUDIT_REPORTED` / lihat rincian | `PROPOSED` | `EV-F01-0002` | `NEEDS_LINKED_SLIP_AND_PAYMENT_TRACE` |
| D08 | `PRIOR_AUDIT_REPORTED` / lihat rincian | `PROPOSED` | `EV-F01-0004` | `NEEDS_LINKED_CASHBON_PAYROLL_TRACE` |
| D09 | `PRIOR_AUDIT_REPORTED` / lihat rincian | `PROPOSED` | `EV-F01-0005`, `EV-F01-0015` | `NEEDS_CHANNEL_TRACE` |
| D10 | `PRIOR_AUDIT_REPORTED` / lihat rincian | `PROPOSED` | `EV-F01-0005` | `NEEDS_POS_TRANSACTION_TRACE` |
| D11 | `PRIOR_AUDIT_REPORTED` / lihat rincian | `PROPOSED` | `EV-F01-0006` | `NEEDS_POS_PAYMENT_TRACE` |
| D12 | `PRIOR_AUDIT_REPORTED` / lihat rincian | `PROPOSED` | `EV-F01-0007` | `NEEDS_AP_TRANSACTION_TRACE` |
| D13 | `PRIOR_AUDIT_REPORTED` / lihat rincian | `PROPOSED` | `EV-F01-0013`, `EV-F01-0016` | `NEEDS_COST_AND_ANOMALY_TRACE` |
| D14 | `PRIOR_AUDIT_REPORTED` / lihat rincian | `PROPOSED` | `EV-F01-0001`, `EV-F01-0017` | `OWNER_SCOPE_DECISION_POSSIBLE_WITH_EVIDENCE_CAVEAT` |
| D15 | `PRIOR_AUDIT_REPORTED` / lihat rincian | `PROPOSED` | `EV-F01-0019`, `EV-F01-0002` | `NEEDS_ACCOUNTING_WORKFLOW_EVIDENCE` |
| D16 | `PRIOR_AUDIT_REPORTED` / lihat rincian | `PROPOSED` | `EV-F01-0014`, `EV-F01-0015` | `NEEDS_REPORT_AND_DOWNLOAD_TRACE` |
| D17 | `PRIOR_AUDIT_REPORTED` / lihat rincian | `PROPOSED` | `EV-F01-0012`, `EV-F01-0015` | `NEEDS_ROLE_OWNER_AND_ACCESS_EVIDENCE` |
| D18 | `PRIOR_AUDIT_REPORTED` / lihat rincian | `PROPOSED` | `EV-F01-0001`, `EV-F01-0015` | `NEEDS_CHANNEL_AND_VENDOR_TRACE` |
| D19 | `PRIOR_AUDIT_REPORTED` / lihat rincian | `PROPOSED` | `EV-F01-0016`, `EV-F01-0017` | `NEEDS_EXPORT_AND_PROFILE` |
| D20 | `PRIOR_AUDIT_REPORTED` / lihat rincian | `PROPOSED` | `EV-F01-0001`, `EV-F01-0018` | `NEEDS_OPERATIONS_AND_UAT_EVIDENCE` |

## D01 — Master data, UOM, product/material fields

**Aturan legacy yang terbukti (batas: laporan audit UI terdahulu):**

Prior audit reports product and material master areas, classifications, status, UOM, and product variants.

**Sumber dan keterbatasan:** `EV-F01-0008`, `EV-F01-0009`, `EV-F01-0012`. Bukti adalah ringkasan audit yang tersimpan di issue, tanpa record mentah/screenshot pada checkout ini. Tidak membuktikan rumus backend, seluruh alur, populasi transaksi, atau aturan perusahaan.

**Belum diketahui:**

Exact field list, required/optional rules, uniqueness, inactive-master behavior, UOM Range meaning, duplicate IDs, and live transactions against inactive masters.

**Usulan perubahan untuk One — belum berlaku:**

Map required relations explicitly in One; keep field retirements as proposals until owners confirm business use.

**Alternatif:**

A) Preserve all legacy fields/relations. B) Retire or merge only fields owners confirm unused.

**Contoh sintetis (bukan bukti legacy):**

Synthetic: SKU-A with size M/color Blue/UOM pcs; whether a missing Series field blocks save is unknown.

**Dampak jika dipilih:**

Master data usability, historical references, stock and migration reconciliation.

**Pertanyaan persetujuan spesifik:**

Which fields and master relationships must remain for operations? Are any identified fields approved for retirement?

**Kesiapan:** `BLOCKED_BY_FIELD_AND_TRANSACTION_EVIDENCE`. Pertanyaan target tidak menutup kekurangan bukti aturan legacy; keputusan tetap memerlukan revisi/approval manusia dan tidak mengubah status menjadi accepted.


## D02 — Planning changes and cutting linkage

**Aturan legacy yang terbukti (batas: laporan audit UI terdahulu):**

Prior audit reports planning code/date/target/status and cutting areas.

**Sumber dan keterbatasan:** `EV-F01-0011`. Bukti adalah ringkasan audit yang tersimpan di issue, tanpa record mentah/screenshot pada checkout ini. Tidak membuktikan rumus backend, seluruh alur, populasi transaksi, atau aturan perusahaan.

**Belum diketahui:**

Whether targets/PIC/dates can change after cutting, partial cancellation, approval gates, plan-to-cut lineage, and correction behavior.

**Usulan perubahan untuk One — belum berlaku:**

One could preserve revision history and require a reason/approval for post-start changes; proposal only.

**Alternatif:**

A) Allow edits under current legacy convention once verified. B) Require controlled revisions after work starts.

**Contoh sintetis (bukan bukti legacy):**

Synthetic: plan target 1,000 pcs, 600 cut, 400 remaining; disposition and approval are unknown.

**Dampak jika dipilih:**

WIP, capacity, material reservations, and downstream job quantities.

**Pertanyaan persetujuan spesifik:**

After cutting starts, what changes are allowed, who approves, and how is uncompleted quantity closed?

**Kesiapan:** `NEEDS_LEGACY_TRACE`. Pertanyaan target tidak menutup kekurangan bukti aturan legacy; keputusan tetap memerlukan revisi/approval manusia dan tidak mengubah status menjadi accepted.


## D03 — Cutting quantities and material usage

**Aturan legacy yang terbukti (batas: laporan audit UI terdahulu):**

Prior audit reports fields/areas for rolls, weight, sheets, setelan, grams, and realization.

**Sumber dan keterbatasan:** `EV-F01-0011`. Bukti adalah ringkasan audit yang tersimpan di issue, tanpa record mentah/screenshot pada checkout ini. Tidak membuktikan rumus backend, seluruh alur, populasi transaksi, atau aturan perusahaan.

**Belum diketahui:**

Actual consumption formula, unit conversion precision, waste vs reusable remainder, mixed-size behavior, corrections, and tie to inventory.

**Usulan perubahan untuk One — belum berlaku:**

One could store measured issued/returned quantities separately from planned output and calculated usage; method remains proposal.

**Alternatif:**

A) Keep legacy calculation after transaction proof. B) Adopt measured actual issue/return with separate estimated standard.

**Contoh sintetis (bukan bukti legacy):**

Synthetic: 1 roll 25 kg, 100 sheets, 2 setelan; arithmetic target is 200 pcs if those units mean what labels suggest; legacy effect not evidenced.

**Dampak jika dipilih:**

Material stock, production yield, and cost of finished goods.

**Pertanyaan persetujuan spesifik:**

Which quantities are actual measurements, what formula does legacy use, and how should reusable remainder/waste be recorded?

**Kesiapan:** `NEEDS_TRANSACTION_TRACE`. Pertanyaan target tidak menutup kekurangan bukti aturan legacy; keputusan tetap memerlukan revisi/approval manusia dan tidak mengubah status menjadi accepted.


## D04 — Piecework tariff, dozen conversion, rounding

**Aturan legacy yang terbukti (batas: laporan audit UI terdahulu):**

Prior audit reports tariff, realization in lusin, and amount fields across job/payroll surfaces; service settings/history also appear.

**Sumber dan keterbatasan:** `EV-F01-0003`, `EV-F01-0009`, `EV-F01-0010`. Bukti adalah ringkasan audit yang tersimpan di issue, tanpa record mentah/screenshot pada checkout ini. Tidak membuktikan rumus backend, seluruh alur, populasi transaksi, atau aturan perusahaan.

**Belum diketahui:**

Persisted conversion precision, amount formula, rounding point/mode, effective tariff date, tariff edits after job creation, missing/inactive tariff behavior.

**Usulan perubahan untuk One — belum berlaku:**

One should snapshot the applied tariff and expose exact quantity precision; rounding point/mode must follow verified legacy rule or explicit owner approval.

**Alternatif:**

A) Match verified legacy per-line rule. B) Aggregate exact fractions then round at payroll total. C) Owner-approved alternative.

**Contoh sintetis (bukan bukti legacy):**

Synthetic illustration only: 11 pcs / 12 × Rp25,000 = Rp22,916.666… before rounding. Display/paid amount unknown.

**Dampak jika dipilih:**

Employee pay, payroll totals, auditability, and historical tariff reproducibility.

**Pertanyaan persetujuan spesifik:**

What quantity precision, tariff effective-date rule, and rounding point/mode must One preserve?

**Kesiapan:** `NEEDS_SLIP_AND_HISTORY_TRACE`. Pertanyaan target tidak menutup kekurangan bukti aturan legacy; keputusan tetap memerlukan revisi/approval manusia dan tidak mengubah status menjadi accepted.


## D05 — Reject, rework, and payable quantity

**Aturan legacy yang terbukti (batas: laporan audit UI terdahulu):**

Prior audit reports target/realization and jobs; no reject/rework treatment is preserved in the issue audit.

**Sumber dan keterbatasan:** `EV-F01-0003`. Bukti adalah ringkasan audit yang tersimpan di issue, tanpa record mentah/screenshot pada checkout ini. Tidak membuktikan rumus backend, seluruh alur, populasi transaksi, atau aturan perusahaan.

**Belum diketahui:**

Whether reject/rework is recorded, paid, deducted, reworked by same/different employee, or netted by supervisor outside system.

**Usulan perubahan untuk One — belum berlaku:**

Record actual, accepted, reject, and rework separately only if owners confirm; do not set reject unpaid or rework unpaid by default.

**Alternatif:**

A) Preserve one net payable quantity if that is verified legacy practice. B) Track separate quality quantities and owner-approved payable rules.

**Contoh sintetis (bukan bukti legacy):**

Synthetic: 100 produced, 95 accepted, 3 rework, 2 reject; payable quantity is unknown.

**Dampak jika dipilih:**

Piecework pay, QC yield, cost, and employee disputes.

**Pertanyaan persetujuan spesifik:**

How does legacy pay for rejected and reworked pieces, who records them, and should One preserve or change that rule?

**Kesiapan:** `NEEDS_OWNER_AND_LEGACY_CASES`. Pertanyaan target tidak menutup kekurangan bukti aturan legacy; keputusan tetap memerlukan revisi/approval manusia dan tidak mengubah status menjadi accepted.


## D06 — Payroll components and deductions

**Aturan legacy yang terbukti (batas: laporan audit UI terdahulu):**

Prior audit reports gross/net and payroll component fields (including components summarized in the report).

**Sumber dan keterbatasan:** `EV-F01-0002`. Bukti adalah ringkasan audit yang tersimpan di issue, tanpa record mentah/screenshot pada checkout ini. Tidak membuktikan rumus backend, seluruh alur, populasi transaksi, atau aturan perusahaan.

**Belum diketahui:**

Exact definitions/formulas, whether gross already includes allowances, attendance/leave/overtime rules, manual vs derived values, tax/statutory deductions, negative-net handling.

**Usulan perubahan untuk One — belum berlaku:**

One should represent components transparently and avoid double-counting; do not invent a net-pay floor or formulas.

**Alternatif:**

A) Reproduce verified component-by-component legacy calculation. B) Change selected components with explicit approval and effective date.

**Contoh sintetis (bukan bukti legacy):**

Synthetic: gross Rp950,000, allowance Rp110,000, other deduction Rp10,000, cashbon Rp150,000; arithmetic result depends on what gross includes.

**Dampak jika dipilih:**

Pay correctness, compliance review, and reconciliation to payroll payment.

**Pertanyaan persetujuan spesifik:**

Please confirm the actual component definitions and calculation source after reviewing the linked slip(s); which parts may change in One?

**Kesiapan:** `NEEDS_SLIP_TRACE`. Pertanyaan target tidak menutup kekurangan bukti aturan legacy; keputusan tetap memerlukan revisi/approval manusia dan tidak mengubah status menjadi accepted.


## D07 — Payroll period, approval, payment, posting, correction

**Aturan legacy yang terbukti (batas: laporan audit UI terdahulu):**

Prior audit reports payroll period/batch and payroll payment status as visible areas.

**Sumber dan keterbatasan:** `EV-F01-0002`. Bukti adalah ringkasan audit yang tersimpan di issue, tanpa record mentah/screenshot pada checkout ini. Tidak membuktikan rumus backend, seluruh alur, populasi transaksi, atau aturan perusahaan.

**Belum diketahui:**

Cutoff, late jobs, overlapping periods, partial payment, what Paid means, posting/journal, reopen/correction after payment, and any relation to bank/cash proof.

**Usulan perubahan untuk One — belum berlaku:**

Keep approval, payment-recorded, and posted as distinct states; exact transitions must match verified legacy or be approved.

**Alternatif:**

A) Preserve verified legacy reopen/correction transitions. B) Lock paid periods and use a separately approved adjustment flow.

**Contoh sintetis (bukan bukti legacy):**

Synthetic: a job dated in a paid period is entered later; destination period and re-open policy unknown.

**Dampak jika dipilih:**

Payroll history, cash/bank reconciliation, and duplicate/delayed wages.

**Pertanyaan persetujuan spesifik:**

What is the cutoff rule for late jobs, and how are paid or posted slips corrected without rewriting payment history?

**Kesiapan:** `NEEDS_LINKED_SLIP_AND_PAYMENT_TRACE`. Pertanyaan target tidak menutup kekurangan bukti aturan legacy; keputusan tetap memerlukan revisi/approval manusia dan tidak mengubah status menjadi accepted.


## D08 — Cashbon lifecycle and payroll deductions

**Aturan legacy yang terbukti (batas: laporan audit UI terdahulu):**

Prior audit reports cashbon records and Cashbon Payment in payroll.

**Sumber dan keterbatasan:** `EV-F01-0004`. Bukti adalah ringkasan audit yang tersimpan di issue, tanpa record mentah/screenshot pada checkout ini. Tidak membuktikan rumus backend, seluruh alur, populasi transaksi, atau aturan perusahaan.

**Belum diketahui:**

Whether payroll deduction changes outstanding balance automatically, manual settlement steps, installment schedule, balance-forward, final installment, and reversals.

**Usulan perubahan untuk One — belum berlaku:**

One should preserve a linked audit trail between disbursement, payroll deduction, and repayment; do not introduce a non-negative net rule without authority.

**Alternatif:**

A) Match verified legacy deduction/balance behavior. B) Adopt an owner-approved cap/recovery rule with explicit carry-forward.

**Contoh sintetis (bukan bukti legacy):**

Synthetic: outstanding Rp300,000; scheduled deduction Rp200,000; payroll available Rp150,000. Actual legacy behavior unknown.

**Dampak jika dipilih:**

Employee liability, payroll net, cash, and duplicate repayment prevention.

**Pertanyaan persetujuan spesifik:**

Show/confirm the actual deduction-to-balance history; then decide what happens when available pay is less than scheduled installment.

**Kesiapan:** `NEEDS_LINKED_CASHBON_PAYROLL_TRACE`. Pertanyaan target tidak menutup kekurangan bukti aturan legacy; keputusan tetap memerlukan revisi/approval manusia dan tidak mengubah status menjadi accepted.


## D09 — Sales channels: POS and non-POS

**Aturan legacy yang terbukti (batas: laporan audit UI terdahulu):**

Prior audit reports POS/POS Template and dashboard sales/customer/product areas.

**Sumber dan keterbatasan:** `EV-F01-0005`, `EV-F01-0015`. Bukti adalah ringkasan audit yang tersimpan di issue, tanpa record mentah/screenshot pada checkout ini. Tidak membuktikan rumus backend, seluruh alur, populasi transaksi, atau aturan perusahaan.

**Belum diketahui:**

Whether wholesale, marketplace, online, or other sales are recorded in POS, another module, external platform, or manual records; order-to-fulfillment flow.

**Usulan perubahan untuk One — belum berlaku:**

One may need separate retail POS and non-POS sales paths if the business uses both; do not assume either is in scope.

**Alternatif:**

A) POS-only if confirmed. B) POS plus distinct order/invoice flow for confirmed channels.

**Contoh sintetis (bukan bukti legacy):**

Synthetic: retail one-item cash sale vs wholesale 50-dozen order with terms; current legacy workflow unknown.

**Dampak jika dipilih:**

Order lifecycle, stock reservation, receivables, fulfillment, and integration scope.

**Pertanyaan persetujuan spesifik:**

Which sales channels are in actual use, and where is each order/payment currently recorded?

**Kesiapan:** `NEEDS_CHANNEL_TRACE`. Pertanyaan target tidak menutup kekurangan bukti aturan legacy; keputusan tetap memerlukan revisi/approval manusia dan tidak mengubah status menjadi accepted.


## D10 — Price, discounts, tax, invoice calculation

**Aturan legacy yang terbukti (batas: laporan audit UI terdahulu):**

Prior audit reports POS invoice/customer/product/unit/storage/discount areas.

**Sumber dan keterbatasan:** `EV-F01-0005`. Bukti adalah ringkasan audit yang tersimpan di issue, tanpa record mentah/screenshot pada checkout ini. Tidak membuktikan rumus backend, seluruh alur, populasi transaksi, atau aturan perusahaan.

**Belum diketahui:**

Price source/lock, discount basis and authorization, percent vs fixed discounts, tax, rounding, invoice finalization, and historical price snapshots.

**Usulan perubahan untuk One — belum berlaku:**

One should preserve price/discount auditability and calculate from explicit line/order bases; rate and authorization limits remain open.

**Alternatif:**

A) Match verified current POS rules. B) Adopt controlled price/discount overrides with role-specific approval.

**Contoh sintetis (bukan bukti legacy):**

Synthetic: price Rp65,000 and fixed discount Rp15,000; whether allowed and where applied is unknown.

**Dampak jika dipilih:**

Sales totals, margins, receipts, discounts, and cashier reconciliation.

**Pertanyaan persetujuan spesifik:**

What price/discount rules actually run in legacy, and what permissions should One change, if any?

**Kesiapan:** `NEEDS_POS_TRANSACTION_TRACE`. Pertanyaan target tidak menutup kekurangan bukti aturan legacy; keputusan tetap memerlukan revisi/approval manusia dan tidak mengubah status menjadi accepted.


## D11 — Tender, change, partial payment, refund, void

**Aturan legacy yang terbukti (batas: laporan audit UI terdahulu):**

Prior audit reports payment method, paid amount, and change fields on POS.

**Sumber dan keterbatasan:** `EV-F01-0006`. Bukti adalah ringkasan audit yang tersimpan di issue, tanpa record mentah/screenshot pada checkout ini. Tidak membuktikan rumus backend, seluruh alur, populasi transaksi, atau aturan perusahaan.

**Belum diketahui:**

Split tenders, partial payment/AR, overpayment, refunds, exchange, void timing/roles, cash or bank settlement, and stock reversal.

**Usulan perubahan untuk One — belum berlaku:**

One should keep each tender/refund/void traceable and distinguish UI status from actual money movement; supported tender combinations need evidence.

**Alternatif:**

A) Match verified legacy tender/void behavior. B) Add split tenders/controlled reversals with owner-approved controls.

**Contoh sintetis (bukan bukti legacy):**

Synthetic: total Rp180,000 paid Rp100,000 cash + Rp80,000 QR; whether legacy allows this is unknown.

**Dampak jika dipilih:**

Cashier close, payment reconciliation, stock, revenue, and chargebacks/refunds.

**Pertanyaan persetujuan spesifik:**

Which tender combinations and refund/void flows are used today, and who can perform/approve each?

**Kesiapan:** `NEEDS_POS_PAYMENT_TRACE`. Pertanyaan target tidak menutup kekurangan bukti aturan legacy; keputusan tetap memerlukan revisi/approval manusia dan tidak mengubah status menjadi accepted.


## D12 — Purchasing, PO/receipt, AP settlement

**Aturan legacy yang terbukti (batas: laporan audit UI terdahulu):**

Prior audit reports AP Settlement, supplier document, and with/non-PO context.

**Sumber dan keterbatasan:** `EV-F01-0007`. Bukti adalah ringkasan audit yang tersimpan di issue, tanpa record mentah/screenshot pada checkout ini. Tidak membuktikan rumus backend, seluruh alur, populasi transaksi, atau aturan perusahaan.

**Belum diketahui:**

Purchase request/order/receipt chain, three-way match, partial settlement, allocation to invoices/POs, payment evidence, non-PO types, and reversal.

**Usulan perubahan untuk One — belum berlaku:**

One should link obligations to source documents and payment separately if legacy does so; do not assume strict matching without transaction proof or owner decision.

**Alternatif:**

A) Preserve verified legacy linking/non-PO behavior. B) Require PO/receipt match for selected purchase classes, with approved non-PO exceptions.

**Contoh sintetis (bukan bukti legacy):**

Synthetic: invoice for 500 kg vs receipt for 480 kg; variance handling and payable amount unknown.

**Dampak jika dipilih:**

Supplier balances, inventory receipt, duplicate payment risk, and cash/bank records.

**Pertanyaan persetujuan spesifik:**

Trace one with-PO and one non-PO settlement, including receipt and payment proof; what matching rules should One preserve/change?

**Kesiapan:** `NEEDS_AP_TRANSACTION_TRACE`. Pertanyaan target tidak menutup kekurangan bukti aturan legacy; keputusan tetap memerlukan revisi/approval manusia dan tidak mengubah status menjadi accepted.


## D13 — Inventory capital, costing, WIP and anomaly #108

**Aturan legacy yang terbukti (batas: laporan audit UI terdahulu):**

Prior audit reports quantity, Capital, and Total by unit/storage; #108 reports one negative quantity row with product identity placeholder.

**Sumber dan keterbatasan:** `EV-F01-0013`, `EV-F01-0016`. Bukti adalah ringkasan audit yang tersimpan di issue, tanpa record mentah/screenshot pada checkout ini. Tidak membuktikan rumus backend, seluruh alur, populasi transaksi, atau aturan perusahaan.

**Belum diketahui:**

Capital calculation method, valuation layers, receipt costs, WIP/COGS treatment, negative-stock policy, and root cause of #108.

**Usulan perubahan untuk One — belum berlaku:**

One should retain provenance and reject/quarantine only records proven invalid under owner-approved rules. Moving average is one possible proposal, not current policy.

**Alternatif:**

A) Match verified legacy valuation. B) Adopt moving average. C) Adopt FIFO/standard cost if accounting owners choose.

**Contoh sintetis (bukan bukti legacy):**

Synthetic: 100 units at Rp20,000 and 100 at Rp22,000; moving-average arithmetic would be Rp21,000, but legacy method is unknown.

**Dampak jika dipilih:**

Inventory valuation, margin, COGS, opening balances, and migration integrity.

**Pertanyaan persetujuan spesifik:**

What method does legacy currently use? After verifying that, which valuation method should One use and how should #108 be classified?

**Kesiapan:** `NEEDS_COST_AND_ANOMALY_TRACE`. Pertanyaan target tidak menutup kekurangan bukti aturan legacy; keputusan tetap memerlukan revisi/approval manusia dan tidak mengubah status menjadi accepted.


## D14 — Accounting scope, accounts, journal/ledger

**Aturan legacy yang terbukti (batas: laporan audit UI terdahulu):**

The recorded audit menu inventory does not list GL/COA/journal pages; this only describes the audited account/menu inventory, not the whole company accounting process.

**Sumber dan keterbatasan:** `EV-F01-0001`, `EV-F01-0017`. Bukti adalah ringkasan audit yang tersimpan di issue, tanpa record mentah/screenshot pada checkout ini. Tidak membuktikan rumus backend, seluruh alur, populasi transaksi, atau aturan perusahaan.

**Belum diketahui:**

External accounting tool/process, actual COA, source-of-truth per ledger, data exchange, posting timing, payroll/AP/POS journals.

**Usulan perubahan untuk One — belum berlaku:**

Decide One accounting scope only after mapping the actual company workflow; operational subledger/export vs native GL are alternatives, not settled.

**Alternatif:**

A) One operational subledgers with controlled export to existing accounting process. B) One includes native GL/COA/journals.

**Contoh sintetis (bukan bukti legacy):**

Synthetic: daily POS close produces one cash summary; account mapping and export destination unknown.

**Dampak jika dipilih:**

Replacement completeness, reconciliation, audit, and finance workload.

**Pertanyaan persetujuan spesifik:**

For the target replacement, should One include a native GL/COA, or should accounting remain in a separate system with controlled exports? This decides target scope only; current external workflow remains unverified.

**Kesiapan:** `OWNER_SCOPE_DECISION_POSSIBLE_WITH_EVIDENCE_CAVEAT`. Pertanyaan target tidak menutup kekurangan bukti aturan legacy; keputusan tetap memerlukan revisi/approval manusia dan tidak mengubah status menjadi accepted.


## D15 — Accounting period close/reopen

**Aturan legacy yang terbukti (batas: laporan audit UI terdahulu):**

The recorded audit sources do not support the prior claim that `/settings/periods` was observed. Correct status: unverified. Payroll period/batch area was reported, but that is not proof of accounting period control.

**Sumber dan keterbatasan:** `EV-F01-0019`, `EV-F01-0002`. Bukti adalah ringkasan audit yang tersimpan di issue, tanpa record mentah/screenshot pada checkout ini. Tidak membuktikan rumus backend, seluruh alur, populasi transaksi, atau aturan perusahaan.

**Belum diketahui:**

Whether a separate legacy route exists, how monthly books close, late adjustments, reopen permissions, payroll cutoff, and reports.

**Usulan perubahan untuk One — belum berlaku:**

One could provide controlled period close/reopen after current business rule and accounting workflow are verified.

**Alternatif:**

A) Reproduce actual close/reopen rule if found. B) Define a new close/reopen control with owner approval.

**Contoh sintetis (bukan bukti legacy):**

Synthetic: August close on 5 September then a late invoice; acceptance path unknown.

**Dampak jika dipilih:**

Period reporting, audit trails, late postings, and finance operations.

**Pertanyaan persetujuan spesifik:**

Does the company currently close periods outside the audited legacy menu? What close/reopen and late-posting policy should One implement?

**Kesiapan:** `NEEDS_ACCOUNTING_WORKFLOW_EVIDENCE`. Pertanyaan target tidak menutup kekurangan bukti aturan legacy; keputusan tetap memerlukan revisi/approval manusia dan tidak mengubah status menjadi accepted.


## D16 — Reports, exports, title report, dashboard metrics

**Aturan legacy yang terbukti (batas: laporan audit UI terdahulu):**

Prior audit reports Title Reports, a payroll download action, and dashboard metric areas.

**Sumber dan keterbatasan:** `EV-F01-0014`, `EV-F01-0015`. Bukti adalah ringkasan audit yang tersimpan di issue, tanpa record mentah/screenshot pada checkout ini. Tidak membuktikan rumus backend, seluruh alur, populasi transaksi, atau aturan perusahaan.

**Belum diketahui:**

Downloaded file content/layout, other report formats, filters/timezone, metric definitions, reconciliation and report readership.

**Usulan perubahan untuk One — belum berlaku:**

Inventory required reports and preserve verified filters/totals; any template consolidation/retirement is proposal only.

**Alternatif:**

A) Reproduce each verified report/layout. B) Consolidate after report owners confirm equivalence.

**Contoh sintetis (bukan bukti legacy):**

Synthetic: compare one dashboard period total with underlying POS invoices; no source values are preserved.

**Dampak jika dipilih:**

Daily operations, statutory/management reporting, archive, and trust in dashboard.

**Pertanyaan persetujuan spesifik:**

Which actual reports/files are required, who uses them, and what totals/filters must match?

**Kesiapan:** `NEEDS_REPORT_AND_DOWNLOAD_TRACE`. Pertanyaan target tidak menutup kekurangan bukti aturan legacy; keputusan tetap memerlukan revisi/approval manusia dan tidak mengubah status menjadi accepted.


## D17 — Roles, separation of duties, salary privacy

**Aturan legacy yang terbukti (batas: laporan audit UI terdahulu):**

Prior audit reports employee/position surfaces and dashboard user area.

**Sumber dan keterbatasan:** `EV-F01-0012`, `EV-F01-0015`. Bukti adalah ringkasan audit yang tersimpan di issue, tanpa record mentah/screenshot pada checkout ini. Tidak membuktikan rumus backend, seluruh alur, populasi transaksi, atau aturan perusahaan.

**Belum diketahui:**

Complete role/account inventory, per-action permission checks, business unit scoping, salary access, self-approval, delegation, audit log.

**Usulan perubahan untuk One — belum berlaku:**

One should enforce least privilege and maker-checker where owners require it; the suggested role matrix is not current legacy behavior.

**Alternatif:**

A) Mirror verified permissions then harden by explicit approval. B) Implement least-privilege roles with approved exceptions.

**Contoh sintetis (bukan bukti legacy):**

Synthetic: same user requests and approves a supplier payment; whether current legacy blocks it is unknown.

**Dampak jika dipilih:**

Salary privacy, fraud prevention, operational access, and approvals.

**Pertanyaan persetujuan spesifik:**

Which roles may view, create, approve, pay, export, or reverse each domain? Who may see payroll?

**Kesiapan:** `NEEDS_ROLE_OWNER_AND_ACCESS_EVIDENCE`. Pertanyaan target tidak menutup kekurangan bukti aturan legacy; keputusan tetap memerlukan revisi/approval manusia dan tidak mengubah status menjadi accepted.


## D18 — External channels/integrations/source of truth

**Aturan legacy yang terbukti (batas: laporan audit UI terdahulu):**

The recorded menu inventory names POS but does not itself establish integrations, vendors, or source-of-truth by object.

**Sumber dan keterbatasan:** `EV-F01-0001`, `EV-F01-0015`. Bukti adalah ringkasan audit yang tersimpan di issue, tanpa record mentah/screenshot pada checkout ini. Tidak membuktikan rumus backend, seluruh alur, populasi transaksi, atau aturan perusahaan.

**Belum diketahui:**

Platforms in use, connector/aggregator, sync direction/frequency, order/stock/refund/settlement ownership, retries and reconciliation.

**Usulan perubahan untuk One — belum berlaku:**

Keep or replace integrations only after inventory; no automatic CSV-only or API-first rule is proposed as current.

**Alternatif:**

A) Keep current validated channels/integrations with One connectors. B) Stage import/export transition then add connectors. C) Retire only with owner evidence.

**Contoh sintetis (bukan bukti legacy):**

Synthetic: duplicate marketplace order event; idempotency behavior unknown in legacy.

**Dampak jika dipilih:**

Stock accuracy, channel uptime, order capture, and cutover scope.

**Pertanyaan persetujuan spesifik:**

Which sales/inventory/finance systems and channels are actually used, and which objects should remain synchronized with One?

**Kesiapan:** `NEEDS_CHANNEL_AND_VENDOR_TRACE`. Pertanyaan target tidak menutup kekurangan bukti aturan legacy; keputusan tetap memerlukan revisi/approval manusia dan tidak mengubah status menjadi accepted.


## D19 — Migration, cutoff, opening balances, archive

**Aturan legacy yang terbukti (batas: laporan audit UI terdahulu):**

#108 reports one visible anomalous row; this does not characterize overall data quality or migration strategy.

**Sumber dan keterbatasan:** `EV-F01-0016`, `EV-F01-0017`. Bukti adalah ringkasan audit yang tersimpan di issue, tanpa record mentah/screenshot pada checkout ini. Tidak membuktikan rumus backend, seluruh alur, populasi transaksi, atau aturan perusahaan.

**Belum diketahui:**

Available exports, history depth, IDs/relations, balances/open items, paid/unpaid jobs, cashbon, AR/AP, WIP, deltas and record counts.

**Usulan perubahan untuk One — belum berlaku:**

Choose replay vs opening balances only after source profiling and dry-run controls. Opening-balance migration is not approved.

**Alternatif:**

A) Replay validated transaction history. B) Load approved opening balances plus immutable archive. C) Hybrid per domain.

**Contoh sintetis (bukan bukti legacy):**

Synthetic: cutover 30 Sep; stock/cashbon/AP balance values and archival reconciliation must be measured, not assumed.

**Dampak jika dipilih:**

Historical traceability, duplicate liabilities/payments, opening balances, and migration risk.

**Pertanyaan persetujuan spesifik:**

After evidence/profile, which domains require replay and which may use approved opening balances? What archive/retention is required?

**Kesiapan:** `NEEDS_EXPORT_AND_PROFILE`. Pertanyaan target tidak menutup kekurangan bukti aturan legacy; keputusan tetap memerlukan revisi/approval manusia dan tidak mengubah status menjadi accepted.


## D20 — Parallel run, cutover and operational readiness

**Aturan legacy yang terbukti (batas: laporan audit UI terdahulu):**

Prior audit inventory does not establish operational days, staffing/volume, parallel-run procedure, or rollback.

**Sumber dan keterbatasan:** `EV-F01-0001`, `EV-F01-0018`. Bukti adalah ringkasan audit yang tersimpan di issue, tanpa record mentah/screenshot pada checkout ini. Tidak membuktikan rumus backend, seluruh alur, populasi transaksi, atau aturan perusahaan.

**Belum diketahui:**

User readiness, peak volumes, RPO/RTO, backup/restore, reconciliation, freeze window, rollback controls and support coverage.

**Usulan perubahan untuk One — belum berlaku:**

Set measurable UAT/cutover/rollback gates with business/operations owners; a 1–2 week parallel run is only an option.

**Alternatif:**

A) Parallel run after rehearsed reconciliation. B) Direct cutover only after risk and recovery acceptance.

**Contoh sintetis (bukan bukti legacy):**

Synthetic: payroll and POS totals are compared in parallel; no target tolerances or source data are established.

**Dampak jika dipilih:**

Business continuity, double entry, data divergence, and recovery risk.

**Pertanyaan persetujuan spesifik:**

What readiness evidence and go/no-go authority are required before legacy shutdown? Is a parallel run mandatory?

**Kesiapan:** `NEEDS_OPERATIONS_AND_UAT_EVIDENCE`. Pertanyaan target tidak menutup kekurangan bukti aturan legacy; keputusan tetap memerlukan revisi/approval manusia dan tidak mengubah status menjadi accepted.

## Pertanyaan yang dapat diputuskan sekarang

1. **D14 — arah scope akuntansi target One saja:** apakah One harus menyediakan GL/COA native, atau boleh memakai sub-ledger dan ekspor ke proses akuntansi lain? Catatan: proses/sistem accounting yang sekarang belum terverifikasi; jawaban ini tidak boleh dipakai untuk menyatakan legacy tidak punya proses accounting.

Keputusan D01–D13 dan D15–D20 **belum siap diminta sebagai approval final** karena pertanyaan legacy masih dapat dijawab lewat bukti transaksi, laporan, role, atau data operasional yang belum berhasil diakses. Jangan menyetujui formula reject/rework, moving average, penghapusan field, atau saldo awal migrasi berdasarkan paket ini.

## Keputusan yang memerlukan pengambilan sampel legacy sebelum diajukan

- D02–D08: planning/cutting, tarif, job, slip payroll, payment, kasbon, koreksi.
- D09–D12: kanal sales, POS invoice/tender, refund/void, AP settlement, PO/receipt/payment.
- D01, D13, D15–D20: field master, stock/cost, accounting close, report, roles, integration, exports/migration, operations.

## Persetujuan

Belum ada tanda tangan, approver, tanggal efektif, atau expected business result yang dicatat. Jangan mengisi persetujuan sebelum jawaban owner yang eksplisit dan bukti pendukung dilampirkan.
