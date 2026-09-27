# Paket Keputusan F01 — untuk review pemilik

Issue [#40](https://github.com/wenn-id/beeloftone/issues/40) · Draft PR [#109](https://github.com/wenn-id/beeloftone/pull/109)
Baseline: `96bb48fa8889b3a483411768e2543838e69233b0` (v0.114.0/schema 55).
**Status:** IN_PROGRESS / bukti transaksi belum lengkap. Satu-satunya arah yang dipilih adalah cakupan target D14 Opsi B berdasarkan instruksi langsung pengguna; detail D14 tetap OPEN, tidak ada approver identity/title yang dicatat. D01–D13 dan D15–D20 tetap usulan/terbuka; #40 tetap OPEN.

## Cara membaca

- **Legacy terbukti** berarti hanya hal yang tertulis pada audit UI terdahulu di issue #40 atau issue #108; bukan pembuktian formula/backend atau pemakaian perusahaan secara menyeluruh.
- **Belum diketahui** menyebut bukti transaksi/role/dokumen yang belum tersedia.
- **Usulan One** adalah rekomendasi, bukan aturan berjalan dan bukan persetujuan.
- Contoh angka/alur bertanda **sintetis** tidak membuktikan legacy.
- `READY_TO_DECIDE` berarti arah kebijakan target dapat dipilih dengan catatan evidensial; bukan berarti legacy sudah dipahami atau keputusan diterima untuk freeze.

## Status akses dan kerja

- Issue #40 mencatat audit UI terdahulu pada 27 September 2026 (tanggal saja; jam observasi, filter, sampel, screenshot, dan nilai transaksi tidak tercatat di sumber yang tersedia). Issue #40 melaporkan dashboard + 30 menu, 8 form, dan satu detail payroll.
- Percobaan sesi sebelumnya gagal sebelum login: `browser-harness: daemon default didn't come up`; native desktop melaporkan `windows: []`. Tidak ada kredensial dimasukkan, tidak ada sampel transaksi baru dibuka. Percobaan itu memakai harness lokal yang berbeda, bukan fasilitas browser sesi ini.
- Sesi ini (2026-09-27): managed live-browser tersedia dan satu sesi read-only diluncurkan ke `https://backoffice.beeloftbaby.com/` untuk rantai bukti T03–T05 (pekerjaan → slip → pembayaran → kasbon; POS → pembayaran → stok; AP → settlement → pembayaran; modal persediaan). Tidak ada login tersimpan di vault untuk situs tersebut, sehingga sesi menunggu kredensial aman dari pengguna; belum ada sampel transaksi baru yang diperiksa. Lihat `EV-F01-0020` di `f01-legacy-evidence.md`.
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


## D14 — Accounting scope and complete native General Ledger

**Status:** `DIRECTION_SELECTED_BY_USER` for target scope only; `DETAIL_POLICY_OPEN`; not `BUSINESS_ACCEPTED`.

**Aturan legacy yang terbukti (batas sumber):** Issue #40's prior audit report says accounting GL/COA/closing was not observed on the audited account/menu. This means **tidak terlihat pada akun/menu yang diaudit**; it does not establish that accounting does not exist elsewhere or that no external accounting software is used. No legacy transaction or accounting report was sampled in this session.

**Perilaku legacy terverifikasi lewat transaksi:** None. No production accounting transaction, payment, journal, or period-close chain was inspected.

**Kemampuan Beeloft One yang terbukti dari kode (baseline `96bb48fa8889b3a483411768e2543838e69233b0`, schema 55):** See the capability table “Akuntansi One” in `f01-decisions-evidence.md` and `docs/a01-ledger-readiness.md`. Existing operational ledgers/reversals, production-cost calculations, read-only Mekari finance snapshots, and external payroll journal metadata/reconciliation exist. These are **not** native GL/journal lines or a complete accounting system. No native COA, journal header/lines, accounting period lock, trial balance, balance sheet/P&L, cash/bank ledger, or period close/reopen was found in the schema-55 inventory. References include `beeloft/payroll_accounting.sql`, `beeloft/mekari_finance_snapshots.sql`, `docs/f02-ownership.csv`, and `docs/f02-shared-contracts.md`.

**Arah One dipilih pengguna:** Opsi B — native complete accounting in One: COA, journals, GL, trial balance, balance sheet, profit-and-loss, reconciliation, and period close. Build in roadmap stages: prepare transaction/accounting foundations early; have operational modules emit traceable events; complete accounting and reports in dependency order; retain exports to other accounting software for review/transition. This records only the user-selected direction, not a named approver, authority title, detailed accounting policy, acceptance of D14 details, other D01–D20 decisions, audit results, or final F01 acceptance.

**Kekurangan bukti / detail belum diputuskan:** External current accounting system/source of truth; approved COA and control accounts; journal mapping and recognition timing for inventory/COGS, sales/AR, AP, payroll/cashbon and cash/bank; tax; currency/precision/rounding; period calendar/lock/late adjustments/reopen; authorized roles; required/statutory reports; opening balances vs replay; and source-event ownership. #46 and #59 dependencies remain open.

**Rekomendasi implementasi (proposal teknis, not current policy):** Do not create a second operational ledger. Preserve existing immutable operational event ledgers as source state. Add a native financial projection/journal subsystem with unique source event + revision identity, one journal effect per eligible event, explicit reversal linkage, and reports derived from posted journal lines. Export reports/journals for transition and review. Do not post external snapshots as new economic events. Do not add future charge costs atop existing sewing cost for the same work.

**Roadmap / owner:** #41 F02 defines shared event/posting/idempotency/reversal contracts; #46 A01 builds COA, accounting periods, journal header/lines/source registry and atomic posting after #41/#44; domain issues #53–#58 build producers/subledgers; #59 A02 builds reconciliation, close/reopen and financial statements after upstream dependencies. Roadmap roles A2/A3 are proposed responsibility allocations, not evidence of a named person's approval. No implementation/schema change in this F01 revision.

**Contoh alur (sintetis, proposal only):** Suppose One records an accepted inventory receipt of 10 units at a documented unit cost of Rp 25,000. Operational receipt ledger remains source of quantity and receipt lineage. Once D13/D14-approved posting mapping exists, a future A01 journal might debit Inventory Rp 250,000 and credit a payable/clearing account Rp 250,000. The receipt itself must not also be counted as an independent second stock ledger. Posting mapping/account/timing are not yet approved; this example does not describe current legacy behavior.

**Dampak:** Full accounting enables a trace from operational events to approved journal lines/statements, but adds controls and migration risk. Incorrect mapping or duplicate posting can overstate inventory, expenses, payables, or sales. Staff workflows need COA ownership, review/close controls, reconciliation, and transition exports. Operational balances and financial balances must remain separately traceable.

**Pertanyaan yang masih perlu persetujuan manusia (not re-asking direction):**
1. Which current system/process owns accounting today, and which historical period/data must remain queryable?
2. Who is the authorized accounting policy owner, if formally designated? No individual/title is recorded here.
3. What COA/control-account structure, currency and rounding rules, tax treatment, recognition events, and posting examples should A01 implement?
4. What fiscal calendar, close/reopen roles, late-adjustment and cross-period reversal policy should #59 enforce?
5. Which financial statements/reconciliation exports are required, and what existing system must One export to during transition?
6. For each domain, is history replay required, or may approved opening balances plus immutable archive be used after profiling and reconciliation?

**Approval request:** D14 target direction already selected by the direct user instruction quoted in this issue context; do not request A/B again. Detailed policy questions above remain open for the authorized accounting owner. No approver identity, role/title, signature or `BUSINESS_ACCEPTED` claim has been invented.

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

Downloaded file content/layout, other report formats, filters/timezone, metric definitions, reconciliation and report readership. Actual legacy paper sizes and print practice are also unknown.

**Usulan perubahan untuk One — belum berlaku:**

Proposed report/export strategy (not legacy behavior, not approved):

1. **Output kind by purpose.** PDF print-ready for official/external documents; CSV for analysis, reconciliation, and migration extracts; in-app views for operational monitoring. Not every report needs all three formats.
2. **Proposed mandatory document catalog at launch.** Each entry still needs owner verification that the legacy process actually requires it (see questions below); nothing is launched by default:

| Document | User | Minimum content | Filters | Format |
|---|---|---|---|---|
| Payroll slip | employee (own slip only), HR/payroll | employee ref, period, gross components, deductions (incl. kasbon), net, payment status | period, employee | PDF print-ready |
| SPK / job card | production | job code, article, target/actual qty, tariff reference, status | period, status | PDF / in-app |
| POS receipt | cashier, customer | invoice no, lines, discount, tender/change, storage | date/shift | PDF print-ready |
| Delivery note (surat jalan) | warehouse, customer | shipment lines, qty, document references | date | PDF print-ready |
| Purchase order | purchasing, supplier | PO no, lines, prices, status | status/date | PDF print-ready |
| Payment proof | finance | payment ref, amount, method, allocation | date/method | PDF print-ready |
| Title reports | management | aggregates with preserved verified filters/totals | as verified | PDF + CSV |
| Dashboard metric extracts | management | metric values per period | period | CSV |

3. **Document lifecycle (proposal).** Draft → issued → corrected only by reversal or a new revision; issued documents are never silently edited. Document numbers are unique; the no-gap policy is decided with finance.
4. **No locked paper size and no full set at launch without verified need.** Choose sizes only after confirming actual legacy print practice. PDFs must render legibly on common office paper; exact sizes are decided per document with its owner.
5. **CSV schemas (proposal).** Column list, date basis, and totals defined per report; every CSV row carries its source document reference and revision for reconciliation.

**Alternatif:**

A) Reproduce each verified report/layout. B) Consolidate after report owners confirm equivalence.

**Contoh sintetis (bukan bukti legacy):**

Synthetic: compare one dashboard period total with underlying POS invoices; no source values are preserved.

**Dampak jika dipilih:**

Daily operations, statutory/management reporting, archive, and trust in dashboard.

**Pertanyaan persetujuan spesifik:**

For each document in the catalog: is it actually used (verify the legacy need)? Who reads it? What columns, totals, and filters must match, and in which output format? What paper size is actually printed today?

**Kesiapan:** `NEEDS_REPORT_AND_DOWNLOAD_TRACE`. Pertanyaan target tidak menutup kekurangan bukti aturan legacy; keputusan tetap memerlukan revisi/approval manusia dan tidak mengubah status menjadi accepted.


## D17 — Roles, separation of duties, salary privacy

**Aturan legacy yang terbukti (batas: laporan audit UI terdahulu):**

Prior audit reports employee/position surfaces and dashboard user area.

**Sumber dan keterbatasan:** `EV-F01-0012`, `EV-F01-0015`. Bukti adalah ringkasan audit yang tersimpan di issue, tanpa record mentah/screenshot pada checkout ini. Tidak membuktikan rumus backend, seluruh alur, populasi transaksi, atau aturan perusahaan.

**Belum diketahui:**

Complete role/account inventory, per-action permission checks, business unit scoping, salary access, self-approval, delegation, audit log.

**Usulan perubahan untuk One — belum berlaku:**

Proposed access model (not legacy behavior, not approved). Rights are separable and must NOT be bundled:

- `view_salary` — payroll detail per employee (gross/net/components).
- `view_margin_profit` — margin, P&L, and financial statements.
- `create_transaction`, `edit_draft_transaction` — operational data entry.
- `approve` — approve requests per domain (thresholds set by owner).
- `pay_execute` — execute actual payments.
- `export_data` — export/download reports and data.

Proposed function matrix (function labels, not job titles; the owner maps real roles onto these):

| Function | Create/edit | Approve | Pay | View salary | View margin/P&L | Export |
|---|---|---|---|---|---|---|
| Produksi | production tx | own domain* | no | no | no | operational only |
| HR/payroll | payroll tx | payroll | no | yes | no | payroll only |
| Finance/accounting | accounting tx | finance | yes | separate grant, default no | yes | yes |
| Kasir | POS tx | no | tender only | no | no | own shift only |
| Manajemen | no | yes (threshold) | no | separate grant only | yes | reports |

\*No self-approval: the requester may not approve their own transaction. Proposed backup/delegation: each approval queue names a substitute approver. Exceptions that require a human decision (e.g., approving one's own claim, overriding a blocked validation) must be listed explicitly by the owner and are never automatic.

`view_salary` and `view_margin_profit` are independent grants — salary view is never implied by a finance or management role, and they are not merged into a single Owner/Finance option. This proposal does not assume any company job structure or any specific person's authority.

Technical: RBAC must be enforced per endpoint (known gap #45 O01); every permission grant and change is audit-logged.

**Alternatif:**

A) Mirror verified permissions then harden by explicit approval. B) Implement least-privilege roles with approved exceptions.

**Contoh sintetis (bukan bukti legacy):**

Synthetic: same user requests and approves a supplier payment; whether current legacy blocks it is unknown.

**Dampak jika dipilih:**

Salary privacy, fraud prevention, operational access, and approvals.

**Pertanyaan persetujuan spesifik:**

Which functions may view salary versus margin/P&L — granted separately? Who approves each domain and at what threshold? Who are the named backup approvers per queue? Which exceptions require an explicit human decision?

**Kesiapan:** `NEEDS_ROLE_OWNER_AND_ACCESS_EVIDENCE`. Pertanyaan target tidak menutup kekurangan bukti aturan legacy; keputusan tetap memerlukan revisi/approval manusia dan tidak mengubah status menjadi accepted.


## D18 — External channels/integrations/source of truth

**Aturan legacy yang terbukti (batas: laporan audit UI terdahulu):**

The recorded menu inventory names POS but does not itself establish integrations, vendors, or source-of-truth by object.

**Sumber dan keterbatasan:** `EV-F01-0001`, `EV-F01-0015`. Bukti adalah ringkasan audit yang tersimpan di issue, tanpa record mentah/screenshot pada checkout ini. Tidak membuktikan rumus backend, seluruh alur, populasi transaksi, atau aturan perusahaan.

**Belum diketahui:**

Platforms in use, connector/aggregator, sync direction/frequency, order/stock/refund/settlement ownership, retries and reconciliation.

**Usulan perubahan untuk One — belum berlaku:**

Proposed integration model (not current behavior, not approved). Split needs by flow — order, stock/reservation, shipping, cancellation/return, settlement — each with its own source of truth:

- **Inventory of what One already has (baseline, read-only):** marketplace order/shipment/return/settlement snapshots, Jubelio order snapshots, Mekari finance snapshots — all read-only imports with no write-back. Sources: `EV-F01-0017`, `tests/test_integration_sync.py`, `tests/test_jubelio_order_snapshots.py`.
- **External services actually used by Beeloft:** UNKNOWN. The owner must confirm which marketplaces, sales channels, Jubelio/Mekari usage, and logistics partners are really in use. Neither keeping nor retiring any of them is decided here.
- **Per data-flow contract (proposal template):** source of truth (One vs external), sync direction (in / out / both), acceptable lag (e.g., minutes for stock, end-of-day for settlement — accepted by owner per flow), deduplication key (external event id + idempotency), failure handling (retry queue, quarantine with alert, reconciliation report).
- **Transition option:** periodic scheduled import may be proposed as an interim step ONLY if operational needs (order-capture latency, stock accuracy) are still met at the owner-accepted lag.
- **Explicitly not claimed:** a weekly CSV settlement does NOT substitute for full sales integration — it covers settlement only, not order, stock, or return timeliness.

**Alternatif:**

A) Keep current validated channels/integrations with One connectors. B) Stage import/export transition then add connectors. C) Retire only with owner evidence.

**Contoh sintetis (bukan bukti legacy):**

Synthetic: duplicate marketplace order event; idempotency behavior unknown in legacy.

**Dampak jika dipilih:**

Stock accuracy, channel uptime, order capture, and cutover scope.

**Pertanyaan persetujuan spesifik:**

Which vendors/channels are actually used? For each flow (order, stock, ship, cancel/return, settle): source of truth, direction, acceptable lag, dedup key, and failure owner? Is scheduled import acceptable as an interim step, and at what lag?

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

Proposed recovery and cutover model (not current behavior, not approved):

- **Separate RPO from RTO.** RPO = tolerable data-loss window (how much transaction history may be lost). RTO = target time to restore service. A daily backup is NOT an accepted 24h transaction loss unless the owner explicitly accepts RPO ≤ 24h.
- **Target options (proposal; the owner picks with technical cost and impact understood):**

| RPO option | Technical requirement | Impact |
|---|---|---|
| ~0 (near-zero) | continuous replication / WAL shipping + tested standby failover | highest infra cost and drill burden |
| ≤ 1 hour | hourly snapshots + WAL archiving, tested restore | moderate cost; small loss window |
| ≤ 24 hours | daily backup only | cheapest; up to a full day of transactions can be lost |

RTO options (e.g., ≤ 1h / ≤ 4h / ≤ 24h) each require a documented restore drill on a separate environment with a measured restore time — no target is claimed met without a successful drill.
- **Side-by-side (parallel) test design (proposal).** Exactly ONE system is the system of record for real transactions: all real payments, shipments, and customer-facing effects flow through it only. The comparison system runs shadow/read-only (mirrored or replayed data, no duplicate external effects).
- **Pass criteria (proposal).** (a) Transaction counts/totals and balances reconcile within owner-agreed tolerance. (b) Critical scenarios pass: a full payroll cycle, one POS day, one AP payment run. (c) The recovery drill meets the chosen RTO/RPO. (d) The rollback procedure is tested, including how transactions created during the rollback window are handled. A 1–2 week duration is a time window, not a pass criterion.

**Alternatif:**

A) Parallel run after rehearsed reconciliation. B) Direct cutover only after risk and recovery acceptance.

**Contoh sintetis (bukan bukti legacy):**

Synthetic: payroll and POS totals are compared in parallel; no target tolerances or source data are established.

**Dampak jika dipilih:**

Business continuity, double entry, data divergence, and recovery risk.

**Pertanyaan persetujuan spesifik:**

What RPO/RTO does the business accept, with cost and impact understood? Who owns go/no-go and incident response? What reconciliation tolerances define pass/fail? Is a parallel run mandatory before legacy shutdown?

**Kesiapan:** `NEEDS_OPERATIONS_AND_UAT_EVIDENCE`. Pertanyaan target tidak menutup kekurangan bukti aturan legacy; keputusan tetap memerlukan revisi/approval manusia dan tidak mengubah status menjadi accepted.

## Status Keputusan Arah D14

Arah cakupan D14 telah ditetapkan oleh pengguna melalui instruksi langsung. **Opsi A/B tidak ditanyakan lagi.**
- **Pilihan:** **Opsi B — Beeloft One memiliki modul akuntansi lengkap sendiri** (COA, jurnal, buku besar, neraca saldo, neraca, laba rugi, rekonsiliasi, dan tutup buku).
- **Status terstruktur:** `DIRECTION_SELECTED_BY_USER`; target direction only, bukan persetujuan detail D14 atau persetujuan bisnis atas keputusan D01–D20 lainnya.
- **Ruang lingkup terpilih:** fondasi transaksi dan akuntansi disiapkan sejak awal; modul operasional menghasilkan transaksi bertaut yang dapat ditelusuri ke posting akuntansi; kelengkapan GL/laporan dibangun bertahap sesuai dependensi; ekspor ke software akuntansi lain boleh disediakan untuk review dan transisi.
- **Detail tetap OPEN:** COA/akun kontrol, event dan waktu pengakuan, pajak, currency/presisi/pembulatan, kalender/lock/reopen, otorisasi, laporan wajib, sumber akuntansi saat ini, migrasi/replay/saldo awal dan penerimaan accounting owner.
- **Alternatif arsitektur yang dipertimbangkan:** Opsi A bergantung pada software accounting eksternal tanpa GL native lengkap—ditolak untuk arah target ini; ekspor tetap tersedia sebagai alat transisi/review, bukan pengganti arah native.
- **Dampak:** staf One perlu alur akun, posting, rekonsiliasi, laporan dan close bertahap; migrasi/pemetaan yang keliru atau posting ganda mengubah saldo/laporan. Tidak ada implementasi atau perubahan DB dalam revisi ini.
- **Pihak berwenang:** belum diketahui; jangan mengarang nama/jabatan. Pemilihan arah oleh pengguna tidak membuktikan ia bertindak sebagai accounting-policy approver.
- **Pertanyaan tersisa:** D14 arah tidak lagi perlu dijawab. Detail kebijakan hanya diminta dari accounting owner yang berwenang setelah legacy sample dan kebutuhan laporan/integrasi dihimpun.
- **Contoh sintetis (bukan bukti legacy):** receipt 10 × Rp25.000 = Rp250.000 dapat menjadi satu sumber operasional dan kelak satu efek jurnal sesuai mapping yang disahkan; contoh ilustratif, bukan jurnal/policy expected result.
- **Bukti legacy:** belum ada rantai transaksi GL yang diperiksa. Catatan lama hanya menyatakan fitur akuntansi “tidak terlihat pada akun/menu yang diaudit”; bukan bukti sistem tidak memilikinya.
- **Paket implementasi:** #41 F02 untuk identity/idempotency/posting/reversal contracts; #46 A01 untuk COA/period/journal/source registry/atomic posting setelah #41 dan #44; #53–#58 untuk operational producers/subledgers; #59 A02 untuk reconciliation, statements dan close setelah dependensi. Handoff di `f01-f02-handoff.md`.

Arah ini bukan persetujuan seluruh detail D14, keputusan D01–D20 lain, hasil audit, atau penerimaan akhir #40. Tidak ada approver identity, role/title, signature atau `BUSINESS_ACCEPTED` yang dicatat.

## Keputusan Arah Sistem yang Siap Direview Sekarang (Tidak Bergantung pada Sampling Legacy)

Berikut adalah keputusan arah arsitektur dan tata kelola yang tidak bergantung pada pembuktian transaksi backoffice legacy, siap dijawab manusia lengkap dengan contoh dan dampaknya:

1. **D16 — Katalog Laporan Wajib, Format, dan Hak Ekspor:**
   - *Aturan sekarang & bukti:* Laporan audit terdahulu mencatat Title Reports, tombol download payroll, dan area metrik dashboard (`EV-F01-0014`, `EV-F01-0015`). Isi file unduhan tidak tersimpan di repo.
   - *Kekurangan bukti:* Format layout persis, kolom, filter timezone, dan pengguna laporan belum terdokumentasi.
   - *Rekomendasi One:* Standardisasi dokumen operasional PDF (Slip Gaji per karyawan, SPK Cutting/Jahit, Surat Jalan Pengiriman, Struk POS, Bukti Kas Keluar AP) dan ekspor tabular CSV untuk analisis internal.
   - *Alternatif:* A) Duplikasi persis seluruh file/tampilan lama. B) Konsolidasi template standar industri setelah dikonfirmasi pengguna.
   - *Contoh alur:* Slip gaji dicetak PDF 1 halaman per karyawan dengan rincian pekerjaan lusin, potongan kasbon, dan take-home pay; ekspor rekap penggajian bulanan berbentuk CSV untuk arsip keuangan.
   - *Dampak:* Kelancaran administrasi pabrik, kepatuhan audit internal, dan kejelasan bagi pekerja borongan.
   - *Pertanyaan persetujuan spesifik:* Dokumen cetak apa saja selain Slip Gaji, SPK, dan Bukti Kas yang wajib berformat PDF siap cetak di One fase 1?

2. **D17 — Matriks Hak Akses, Pemisahan Tugas (SoD), dan Privasi Gaji:**
   - *Aturan sekarang & bukti:* Legacy menampilkan menu Employee dan Position (`EV-F01-0012`). Tidak ada bukti granular per-action permissions dari server.
   - *Kekurangan bukti:* Matriks izin per role, pemisahan tugas persetujuan (maker-checker), dan pembatasan data upah.
   - *Rekomendasi One:* Terapkan prinsip hak akses minimal (*least privilege*): data gaji/slip upah hanya dapat dilihat oleh HR/Payroll dan Owner (tertutup dari staf gudang/operator); persetujuan pembayaran supplier tidak boleh disetujui oleh staf pembuat PO (*no self-approval*).
   - *Alternatif:* A) Samakan hak akses seperti akun admin legacy yang serba bisa. B) Terapkan pemisahan tugas ketat (Owner, Finance, HR, Gudang, Operator Produksi) sejak hari pertama.
   - *Contoh kasus:* Staf purchasing mengajukan pembayaran AP Rp 5.000.000; sistem mengunci tombol approval agar hanya bisa disahkan oleh Finance Manager atau Owner, bukan staf purchasing itu sendiri.
   - *Dampak:* Mencegah kecurangan (*fraud*), melindungi kerahasiaan nominal upah borongan, dan memenuhi standar audit.
   - *Pertanyaan persetujuan spesifik:* Apakah pembuat dokumen (PO/AP/payroll) dilarang menyetujui dokumennya sendiri (wajib maker-checker), dan apakah data gaji wajib diisolasi hanya untuk HR/Owner?

3. **D18 — Strategi Integrasi Kanal Penjualan dan Vendor Fase 1:**
   - *Aturan sekarang & bukti:* Menu POS tercatat di legacy (`EV-F01-0005`), sedangkan marketplace/Mekari di One saat ini berstatus snapshot read-only (`docs/f02-shared-contracts.md`).
   - *Kekurangan bukti:* Ketersediaan API vendor live, kestabilan konektor, dan volume transaksi harian per kanal.
   - *Rekomendasi One:* Pada masa transisi fase 1 cutover, sediakan ekspor-impor data terstruktur (CSV/Excel) untuk software akuntansi dan kanal penjualan; sinkronisasi API live dua arah diaktifkan bertahap setelah stabilitas subledger One terbukti.
   - *Alternatif:* A) Wajibkan API live terintegrasi sebelum backoffice lama dimatikan. B) Gunakan ekspor/impor berkala untuk masa transisi 1–3 bulan pertama, lalu sambungkan API.
   - *Contoh alur:* Setiap sore jam 18:00, One mengekspor ringkasan penjualan POS dan ringkasan kas masuk ke format Excel/CSV yang siap diimpor ke software pembukuan masa transisi.
   - *Dampak:* Mengurangi risiko ketergantungan API eksternal saat peluncuran, menjamin operasional toko/gudang tetap jalan tanpa jeda teknis.
   - *Pertanyaan persetujuan spesifik:* Apakah integrasi fase 1 cukup menyediakan ekspor data berkala (Opsi B) untuk transisi, atau integrasi API langsung wajib aktif sebelum sistem lama dimatikan?

4. **D20 — Target Pemulihan Operasional (RPO/RTO) dan Kriteria Go/No-Go:**
   - *Aturan sekarang & bukti:* Baseline One memiliki script backup snapshot lokal (`operations.md`, `tests/test_backup_download.py`). Tidak ada data runbook pemulihan dari backoffice lama (`EV-F01-0018`).
   - *Kekurangan bukti:* RPO/RTO operasional garmen, jadwal maintenance window, dan toleransi downtime kasir toko.
   - *Rekomendasi One:* Target RPO <= 1 jam (kehilangan data maksimal 1 jam bila server rusak), RTO <= 4 jam (sistem kembali online dalam 4 jam); jalankan *parallel run* selama 1–2 minggu sebelum sistem legacy resmi dimatikan total.
   - *Alternatif:* A) *Cutover langsung (big bang)* di awal bulan tanpa parallel run. B) *Parallel run* 1–2 minggu di mana staf menginput data ke kedua sistem sampai saldo akhir terbukti selaras.
   - *Contoh skenario:* Pada minggu ke-1 bulan cutover, transaksi POS diinput di kedua sistem; setiap malam total omzet dan saldo kas dicocokkan. Bila selisih Rp 0 selama 7 hari berturut-turut, sistem lama dinonaktifkan.
   - *Dampak:* Mencegah kegagalan fatal pada hari peluncuran, memberikan rasa aman bagi staf operasional garmen dan kasir.
   - *Pertanyaan persetujuan spesifik:* Apakah manajemen mewajibkan masa uji coba paralel (parallel run) selama 1–2 minggu sebelum penghentian total backoffice lama?

## Keputusan yang Menunggu Penelusuran Transaksi Legacy (Jangan Diputuskan Sebelum Bukti Ada)

Keputusan berikut **tidak diajukan sebagai pertanyaan kebijakan saat ini**, karena jawaban dasarnya harus digali dari transaksi nyata backoffice untuk menjaga kesetaraan fungsi:
- **D02–D08 (Produksi, Upah, Payroll, Kasbon):**
  - Keterkaitan pengerjaan job → tarif → slip gaji → status bayar → potongan saldo kasbon.
  - Perlakuan reject/rework di slip fisik (apakah dipotong dari payable pcs atau ada insentif perbaikan).
  - Pembulatan pecahan lusin pada rupiah cetak (per baris vs total slip).
  - *Status:* Menunggu akses sesi baca transaksi nyata backoffice.
- **D09–D12 (Sales POS & Pembelian AP):**
  - Transaksi kasir POS: deduksi stok real-time, void/retur barang, dan diskon item vs diskon struk.
  - Transaksi AP Settlement: kelayakan bayar with-PO vs non-PO, serta pencocokan bukti penerimaan barang gudang (*three-way matching*).
  - *Status:* Menunggu akses sesi baca transaksi nyata backoffice.
- **D01, D13, D15, D19 (Master Data, Valuasi Stok, Tutup Buku, Migrasi Saldo):**
  - Pembentukan harga modal (*Capital*) produk dan investigasi akar penyebab anomali kuantitas negatif dengan SKU kosong (#108).
  - Profiling data riil (apakah histori transaksi lama bersih untuk di-replay, atau migrasi wajib menggunakan saldo awal cutover).
  - *Status:* Menunggu sampling dan audit data fisik/database.

## Persetujuan

Belum ada tanda tangan, approver, tanggal efektif, atau expected business result yang dicatat. Jangan mengisi persetujuan sebelum jawaban owner yang eksplisit dan bukti pendukung dilampirkan.
