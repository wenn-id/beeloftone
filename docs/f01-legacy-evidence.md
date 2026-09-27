# Bukti legacy dan batas discovery F01

Issue [#40](https://github.com/wenn-id/beeloftone/issues/40) · terkait [#108](https://github.com/wenn-id/beeloftone/issues/108).
**Paket: IN_PROGRESS; belum REVIEW_READY dan belum BUSINESS_ACCEPTED.**
Baseline One: `96bb48fa8889b3a483411768e2543838e69233b0` (0.114.0/schema 55).

## Sumber, waktu, dan tingkat bukti

Waktu pada audit terdahulu yang tersedia hanya **tanggal 27 September 2026**; jam observasi/filter/sampel tidak ditulis. Waktu komentar issue adalah waktu komentar, bukan waktu pengambilan sampel.

- `PRIOR_AUDIT_REPORTED`: ringkasan audit UI di issue #40. Tidak tersedia tangkapan layar, record, filter, sample IDs, download, atau log transaksi pada checkout ini. Gunakan hanya untuk keberadaan surface/label yang disebut, bukan untuk menetapkan formula/aturan.
- `VERIFIED_CODE`: inspeksi statis Beeloft One di baseline. Ini bukan bukti perilaku legacy atau data produksi.
- `ACCESS_BLOCKED`: percobaan sesi terbaru tidak membuka halaman autentikasi/record karena daemon headless tidak berjalan dan desktop tidak punya window; tidak ada login atau kredensial yang diketik.

### Koreksi klaim `/settings/periods`

Pencarian pada body Issue #40, catatan navigasi rencana, dan sumber audit yang tersedia tidak menemukan bukti bahwa `/settings/periods` pernah diamati. Klaim di draf awal yang menyebut halaman itu teramati dihapus. Status yang benar: **UNVERIFIED**. Ini tidak membuktikan route tidak ada. Periode payroll (`/payroll/master-payroll`) bukan bukti periode akuntansi.

### Inventaris audit terdahulu

Issue #40 menyatakan dashboard + 30 menu, 8 form, dan satu detail payroll pernah dilihat read-only. Daftar nama/path di bawah menggabungkan nama pada audit issue dengan rute di execution plan; path belum dibuka ulang dalam sesi ini. Dashboard dicatat terpisah dari 30 menu; daftar berisi tepat 30 menu:

| # | Path dari execution plan | Nama permukaan menurut catatan audit | Status sesi ini |
|---:|---|---|---|
| 1 | `/support/title-report` | Title Reports | prior audit reported; not replayed |
| 2 | `/materials/category` | Material category | prior audit reported; not replayed |
| 3 | `/materials/sub-category` | Material subcategory | prior audit reported; not replayed |
| 4 | `/materials/type` | Material type | prior audit reported; not replayed |
| 5 | `/materials/list` | Materials | prior audit reported; not replayed |
| 6 | `/production/planning` | Planning | prior audit reported; not replayed |
| 7 | `/production/cutting` | Cutting | prior audit reported; not replayed |
| 8 | `/products/master-material-setting` | Master material setting | prior audit reported; not replayed |
| 9 | `/products/master-service-setting` | Master service setting | prior audit reported; not replayed |
| 10 | `/products/material-service-setting-history` | Material/service history | prior audit reported; not replayed |
| 11 | `/products/category` | Product category | prior audit reported; not replayed |
| 12 | `/products/sub-category` | Product subcategory | prior audit reported; not replayed |
| 13 | `/products/uoms` | UOM | prior audit reported; not replayed |
| 14 | `/products/sizes` | Sizes | prior audit reported; not replayed |
| 15 | `/products/colors` | Colors | prior audit reported; not replayed |
| 16 | `/products/item-series` | Item series | prior audit reported; not replayed |
| 17 | `/products/type` | Product type | prior audit reported; not replayed |
| 18 | `/products/list` | Product list | prior audit reported; not replayed |
| 19 | `/sales/pos-template` | POS template | prior audit reported; not replayed |
| 20 | `/sales/pos` | POS | prior audit reported; not replayed |
| 21 | `/stocks/stck-prdct` | Stock products | prior audit reported; not replayed |
| 22 | `/orders/ap-settlement` | AP settlement | prior audit reported; not replayed |
| 23 | `/payroll/position` | Position | prior audit reported; not replayed |
| 24 | `/payroll/employee` | Employee | prior audit reported; not replayed |
| 25 | `/payroll/job-type` | Job type | prior audit reported; not replayed |
| 26 | `/payroll/group-job` | Group job | prior audit reported; not replayed |
| 27 | `/payroll/job` | Job | prior audit reported; not replayed |
| 28 | `/payroll/master-payroll` | Master payroll | prior audit reported; not replayed |
| 29 | `/payroll/payrolls` | Payrolls | prior audit reported; not replayed |
| 30 | `/payroll/cash-receipt` | Cash receipt | prior audit reported; not replayed |

Form yang dilaporkan: Create Job, AP Settlement, Cutting, Plan, POS, Cash Receipt, Master Service, Master Material. Catatan sumber tidak menyimpan snapshot field/validasi tiap form. Detail yang dilaporkan: payroll dengan komponen, pekerjaan, kasbon, status bayar, dan tombol Download; isi file tidak tersedia.

### Sampel transaksi wajib yang belum dibuka

| Area | Sampel/alur belum diperiksa | Klaim yang karenanya belum boleh dibuat |
|---|---|---|
| Pekerjaan → payroll | Slip paid/unpaid; job sumber; tarif/history; target vs actual; jumlah/payable; tanggal/periode; perubahan; total slip | Formula upah, pembulatan, tarif efektif, status paid/posted dan koreksi belum terbukti. |
| Payroll payment → kasbon | Cashbon opening/disbursement/installment; deduction pada slip; pembayaran slip; saldo sebelum/sesudah; reversal | Link atomik, saldo kasbon, installment terakhir, batas potongan, paid proof belum terbukti. |
| POS | Invoice normal, discount percent/fixed, one/multiple tenders, cash/change, partial, refund/void, stock effect, shift reconciliation | Basis diskon, split payment, refund/void, cash/stock transition belum terbukti. |
| AP | With-PO dan non-PO; PO/receipt/invoice/supplier document; partial/mismatch; settlement/payment proof; outstanding/reversal | Three-way match, non-PO rules, allocation, actual payment, outstanding/reversal belum terbukti. |
| Accounting/period | Issue #40 prior audit reports that GL/COA/closing were not observed on audited account/menu; `/settings/periods` is unverified | Say ‘tidak terlihat pada akun/menu yang diaudit’; external books/source of truth, period workflow and transaction behavior unknown. No current-session transaction trace. |
| Master/roles/reports | Required fields, inactive masters, account roles, report file contents | Required flags, permission matrix, download schema, and retirement mapping not established. |

### Sampling methodology and coverage

Rencana #40 prescribes a 90-day window, 100 candidates per module, and one 12-month extension when needed. **No sampling run is recorded in current evidence**: no filter dates, row counts, status filters, sort order, or selected transaction IDs. Therefore this document does not claim that methodology was completed. Raw production data is absent from GitHub; no private locator was recorded.

## Evidence catalogue

`observed_at_wib` below preserves source date only; exact time was not recorded. `sample_alias` is intentionally empty because no real transaction sample was captured in this checkout.

| ID | observed_at_wib | source_kind | safe_path/source | filters | sample_alias | process_ids | decision_ids | ex_ids | finding | evidence_level | limitations | private_locator_id |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| EV-F01-0001 | 2026-09-27 (time not recorded) | PRIOR_AUDIT_REPORTED | Issue #40, audit section | not recorded | — | — | — | — | Issue #40 reports a read-only legacy UI audit: dashboard plus 30 menu pages, 8 forms, and one payroll detail view. It lists screen names and broad areas. | PRIOR_AUDIT_REPORTED | This is a written prior-audit report, not raw screenshots/export and not independently replayed in this session. Exact observation times, filters, selected records, and sample counts were not recorded. | — |
| EV-F01-0002 | 2026-09-27 (time not recorded) | PRIOR_AUDIT_REPORTED | Payroll detail surface (route listed in execution plan) | not recorded | — | P20-P23 | D06-D07 | EX04 | Prior audit report says payroll detail exposed employee-level gross/net, components, jobs, cashbon, payment status, and a download action. | PRIOR_AUDIT_REPORTED | No specific slip, values, file contents, formula, payment event, or posting effect is preserved in the issue. | — |
| EV-F01-0003 | 2026-09-27 (time not recorded) | PRIOR_AUDIT_REPORTED | Job/payroll surface (route listed in execution plan) | not recorded | — | P03,P07,P11 | D04-D05 | EX03 | Prior audit report says employee/job/planning/product, realization in lusin, tariff, and amount were visible across the audit surfaces. | PRIOR_AUDIT_REPORTED | No joined transaction IDs, values, formula replay, tariff version, or payroll link evidence is preserved. | — |
| EV-F01-0004 | 2026-09-27 (time not recorded) | PRIOR_AUDIT_REPORTED | Cashbon and payroll detail surfaces | not recorded | — | P24 | D08 | EX05 | Prior audit report says cashbon paid/due-date information and Cashbon Payment field were visible. | PRIOR_AUDIT_REPORTED | No linked cashbon-to-slip transaction history or before/after balance is preserved. | — |
| EV-F01-0005 | 2026-09-27 (time not recorded) | PRIOR_AUDIT_REPORTED | /sales/pos and /sales/pos-template (paths from execution plan) | not recorded | — | P17-P18 | D09-D11 | EX06-EX07 | Prior audit report says POS/customer/invoice/unit/storage/discount surfaces were seen. | PRIOR_AUDIT_REPORTED | No invoice, line values, discount calculation, stock movement, or customer record is preserved. | — |
| EV-F01-0006 | 2026-09-27 (time not recorded) | PRIOR_AUDIT_REPORTED | POS payment surface | not recorded | — | P17-P18 | D09-D11 | EX06-EX07 | Prior audit report says payment method, amount paid, and change were visible. | PRIOR_AUDIT_REPORTED | No payment transaction or proof of cash/bank settlement, split payment, refund, or void is preserved. | — |
| EV-F01-0007 | 2026-09-27 (time not recorded) | PRIOR_AUDIT_REPORTED | /orders/ap-settlement (path from execution plan) | not recorded | — | P06-P07,P25 | D12 | EX08 | Prior audit report says AP Settlement with/non-PO context and supplier document were visible. | PRIOR_AUDIT_REPORTED | No settlement record, PO/receipt/invoice chain, payment proof, or status transition is preserved. | — |
| EV-F01-0008 | 2026-09-27 (time not recorded) | PRIOR_AUDIT_REPORTED | Product and material master surfaces | not recorded | — | P01-P03 | D01,D04 | EX01-EX03 | Prior audit report says product classification/series/color/size/status and material classification/price/UOM/description areas were visible. | PRIOR_AUDIT_REPORTED | No full field dictionary, required flags, database constraints, or active/inactive transaction examples are preserved. | — |
| EV-F01-0009 | 2026-09-27 (time not recorded) | PRIOR_AUDIT_REPORTED | UOM and stock/payroll surfaces | not recorded | — | P01-P03 | D01,D04 | EX01-EX03 | Prior audit report says UOM and lusin concepts appeared in stock/payroll contexts. | PRIOR_AUDIT_REPORTED | No conversion precision, formula, or rounded legacy outputs are preserved. | — |
| EV-F01-0010 | 2026-09-27 (time not recorded) | PRIOR_AUDIT_REPORTED | /products/master-material-setting, /products/master-service-setting, /products/material-service-setting-history (paths from execution plan) | not recorded | — | P01-P03 | D01,D04 | EX01-EX03 | Prior audit report lists material/service settings and their history as observed areas. | PRIOR_AUDIT_REPORTED | No saved setting, change history values, effective date semantics, or product application evidence is preserved. | — |
| EV-F01-0011 | 2026-09-27 (time not recorded) | PRIOR_AUDIT_REPORTED | /production/planning and /production/cutting (paths from execution plan) | not recorded | — | P03-P10 | D02-D03 | EX02 | Prior audit report says planning code/date/target/status and cutting roll/weight/sheet/setelan/gram/realization areas were visible. | PRIOR_AUDIT_REPORTED | No linked plan/cut transaction, conversion, consumption, waste, or persisted result is preserved. | — |
| EV-F01-0012 | 2026-09-27 (time not recorded) | PRIOR_AUDIT_REPORTED | POS Template, employee, and position surfaces | not recorded | — | P02,P20,P29 | D01,D17 | EX01,EX12 | Prior audit report says Business Unit/Storage, POS Template, Employee, Position, and active status areas were visible. | PRIOR_AUDIT_REPORTED | No complete role matrix, account permissions, unit ownership, or access-control tests are preserved. | — |
| EV-F01-0013 | 2026-09-27 (time not recorded) | PRIOR_AUDIT_REPORTED | /stocks/stck-prdct (path from execution plan) | not recorded | — | P14,P26 | D13 | EX09 | Prior audit report says quantity, Capital, and Total by unit/storage were visible. | PRIOR_AUDIT_REPORTED | No transaction history or evidence defining Capital calculation/valuation method is preserved. | — |
| EV-F01-0014 | 2026-09-27 (time not recorded) | PRIOR_AUDIT_REPORTED | Title Reports and payroll download surface | not recorded | — | P30 | D16 | EX11 | Prior audit report says Title Reports and a payroll download action were visible. | PRIOR_AUDIT_REPORTED | Downloaded file content and other document layouts were not preserved or independently inspected. | — |
| EV-F01-0015 | 2026-09-27 (time not recorded) | PRIOR_AUDIT_REPORTED | /dashboard (path from execution plan) | not recorded | — | P30,P34 | D16 | EX11 | Prior audit report says dashboard sales/POS/product/user and sales/customer/product-by-period areas were seen. | PRIOR_AUDIT_REPORTED | No metric definitions, filters, period/timezone, query lineage, or reconciliation to transactions are preserved. | — |
| EV-F01-0016 | 2026-09-27 (date reported; time not recorded) | PRIOR_AUDIT_REPORTED | /stocks/stck-prdct | not recorded | — | P14,P26 | D13,D19 | EX09,EX14 | Issue #108 reports one UI row with negative quantity and product identity not displayed / SKU placeholder. | PRIOR_AUDIT_REPORTED | UI observation only. Root cause is explicitly unresolved; candidate explanations include invalid source relation, inactive/missing master, join/render issue, or legitimate negative stock. | — |
| EV-F01-0017 | 2026-09-27 (execution date; time not recorded) | VERIFIED_CODE | commit 96bb48fa8889b3a483411768e2543838e69233b0 | not recorded | — | P01-P34 | D01-D20 | — | Baseline is v0.114.0/schema 55. Static model/API inspection confirms some adjacent One capabilities and that payroll and supplier payments are represented by approval/snapshot/reconciliation flows, not proof of legacy parity. | VERIFIED_CODE | Static source inspection does not establish production use, business acceptance, or legacy behavior. Refer to process register for exact symbols and tests. | — |
| EV-F01-0018 | 2026-09-27 (execution date; time not recorded) | ACCESS_BLOCKED | https://backoffice.beeloftbaby.com/ | not recorded | — | P01-P34 | D01-D20 | — | Headless browser call returned `browser-harness: daemon default didn't come up`; native computer-use returned zero windows. No authenticated session was read and no credentials were entered. | ACCESS_BLOCKED | Therefore no new read-only transaction samples could be inspected. Do not treat this as evidence of system behavior. | — |
| EV-F01-0019 | 2026-09-27 (source review date; time not recorded) | SOURCE_CHECK | /settings/periods | not recorded | — | P27 | D14-D15 | EX10 | The available audit section and execution-plan navigation list do not mention `/settings/periods`. The earlier PR draft claim that this page was observed has no supporting source in the recorded audit. | UNKNOWN | Absence from these written lists does not prove the legacy route/page does not exist. Correct status: UNVERIFIED; no claim that accounting periods were observed. | — |
| EV-F01-0020 | 2026-09-27 (session launched; samples pending) | ACCESS_PENDING | https://backoffice.beeloftbaby.com/ | not recorded | — | P01-P34 | D01-D20 | — | Managed live-browser session launched read-only for transaction chains T03–T05 (payroll→kasbon, POS→stock, AP→payment, inventory capital). No login saved in vault for this site; session awaits user credential via secure login card. No transaction samples inspected yet and no forms submitted. | ACCESS_PENDING | Not evidence of system behavior. No credentials entered by the agent; no passwords, cookies, or session tokens are recorded in the repo. | — |

## AUD-01–AUD-17: status jujur

Ke-17 ID berikut memang tercantum di issue #40, tetapi subtask issue masih belum dicentang. Status di bawah berarti **tercatat sebagai permukaan yang dilaporkan**, bukan discovery transaksi selesai.

| Audit ID | Fokus dari issue #40 | Status bukti | Yang masih harus diperiksa |
|---|---|---|---|
| AUD-01 | Payroll per employee; gross/net/payment | Prior audit report; not independently replayed | Slip nilai, formula, paid/posted proof (`EV-F01-0002`) |
| AUD-02 | Employee/job/planning/product/lusin/tariff/amount | Prior audit report; not independently replayed | Join satu job ke slip dan tarif/history (`EV-F01-0003`) |
| AUD-03 | Cashbon/due date/Cashbon Payment | Prior audit report; not independently replayed | Saldo dan deduction terhubung (`EV-F01-0004`) |
| AUD-04 | POS/customer/invoice/unit/storage/discount | Prior audit report; not independently replayed | Invoice detail & calculation (`EV-F01-0005`) |
| AUD-05 | Payment method/amount/change | Prior audit report; not independently replayed | Tender dan payment settlement (`EV-F01-0006`) |
| AUD-06 | AP with/non-PO/supplier document | Prior audit report; not independently replayed | PO/receipt/invoice/payment chain (`EV-F01-0007`) |
| AUD-07 | Product category/series/color/size/status | Prior audit report; not independently replayed | Field rules/inactive sample (`EV-F01-0008`) |
| AUD-08 | Material classification/price/UOM/description | Prior audit report; not independently replayed | Master-to-receipt price behavior (`EV-F01-0008`) |
| AUD-09 | UOM and dozen in stock/payroll | Prior audit report; not independently replayed | Conversion and rounding results (`EV-F01-0009`) |
| AUD-10 | Material/service setting and history | Prior audit report; not independently replayed | Historical values/effective date (`EV-F01-0010`) |
| AUD-11 | Planning code/date/target/status | Prior audit report; not independently replayed | Change/partial/cancel transitions (`EV-F01-0011`) |
| AUD-12 | Cutting rolls/weight/sheet/setelan/gram/realization | Prior audit report; not independently replayed | Consumption/waste and persisted linkage (`EV-F01-0011`) |
| AUD-13 | Business Unit/Storage/POS template | Prior audit report; not independently replayed | Operational mapping and permissions (`EV-F01-0012`) |
| AUD-14 | Employee/Position/status | Prior audit report; not independently replayed | Role mapping and inactive behavior (`EV-F01-0012`) |
| AUD-15 | Stock quantity/Capital/Total | Prior audit report; not independently replayed | Cost method and stock movements (`EV-F01-0013`) |
| AUD-16 | Title Reports/payroll download | Prior audit report; not independently replayed | Downloaded file contents and other outputs (`EV-F01-0014`) |
| AUD-17 | Dashboard sales/POS/product/user by period | Prior audit report; not independently replayed | Definitions and transaction reconciliation (`EV-F01-0015`) |

## Status dan blocker

- Tidak ada penelusuran live transaksi pada sesi ini. Blocker spesifik tool: `browser-harness: daemon default didn't come up`; native computer-use melaporkan nol jendela. Kredensial tidak dimasukkan. Sampel belum diperiksa tercantum per domain di tabel di atas.
- Prior audit memberi peta permukaan, bukan approval untuk perilaku: tidak ada rumus backend, full transaction trace, full role matrix, sampling counts, atau file download.
- `/settings/periods` berstatus **UNVERIFIED**. Issue #40 menyebut bahwa menu akuntansi GL/COA/closing tidak teramati pada akun audit, bukan bahwa perusahaan tidak punya proses accounting.
- Status T01–T08 tidak boleh dinaikkan ke SELESAI berdasarkan sintetik atau hitungan aritmetika saja. Overall tetap `IN_PROGRESS`; #40 terbuka.

## Hitung sintetis yang boleh dipakai sebagai ilustrasi

Perhitungan berikut adalah matematika pada input buatan, bukan hasil observasi legacy dan bukan policy: 11/12 = 0.916666…; dengan tarif sintetis Rp25.000/lusin hasil perkalian eksak Rp22.916,666…; display/rounding legacy tidak diketahui. Moving-average example, reject treatment, dan opening-balance migration bukan aturan berlaku.


## Status D14: direction selected, evidence and detail still open

The user selected target-scope Option B by direct instruction: native COA, journals, GL, trial balance, balance sheet, P&L, reconciliation, and close, delivered by roadmap dependencies; operational events must be traceable, with exports retained for review/transition. This is **direction scope only**, not an approver identity/title/signature, not detailed posting/COA/period approval, and not F01 acceptance.

The legacy audit source only says GL/COA/closing were not observed on the audited account/menu. No current accounting application, legacy transaction, payment, journal, or period close was sampled. Do not phrase this as proof that the business has no accounting system.

One capability evidence is source-code inventory at baseline `96bb48fa8889b3a483411768e2543838e69233b0`, schema 55, documented in the “Akuntansi One” table in `f01-decisions-evidence.md` and `docs/a01-ledger-readiness.md`. It establishes existing operational ledgers/reversals, read-only external snapshots and external payroll journal reconciliation metadata; it does not establish a native GL. Detailed policy, source workflow, and D01–D20 acceptance remain open.
