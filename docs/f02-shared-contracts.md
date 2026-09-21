# F02: kontrak transaksi dan data bersama

Persiapan [#41](https://github.com/wenn-id/beeloftone/issues/41), induk
[#39](https://github.com/wenn-id/beeloftone/issues/39). **DRAFT; belum business
accepted dan belum mengizinkan implementasi yang bergantung pada F01.**
Diperiksa 21 September 2026 pada `efe1156c4557e0f4b69f0000d674ce74fdc4ae0c`
(v0.97.0/schema 55). Baseline issue `f8921e7` sudah digantikan HEAD ini.

F01 sudah merged melalui PR #76, tetapi [D01–D20](f01-decisions-evidence.md#register-keputusan)
masih OPEN, EX01–EX15 belum disetujui, dan sign-off belum tersedia. Dokumen ini
menyediakan inventaris teruji serta kontrak usulan untuk dibahas; tidak menetapkan
rumus upah, metode valuasi, COA, atau keputusan bisnis yang belum diketahui.

## Status dan artefak

- **BASELINE**: perilaku kode saat commit di atas; bukan pengesahan aturan bisnis.
- **PROPOSED**: kontrak target yang belum menjadi API/DDL. Nama field di bawah
  adalah kosakata lintas domain, bukan janji bahwa payload tersebut diterima HEAD.
- **BLOCKED_F01**: expected result bisnis sengaja `null`; pemilik harus mengisinya
  bersama referensi Dxx/EXxx sebelum implementasi dan acceptance paket penerima.
- [Fixture sintetis](../tests/fixtures/f02-contracts.json): vektor BASELINE yang
  dijalankan tes dan skenario PROPOSED/BLOCKED_F01 yang harus direview A1/A2/A3.
- [Inventaris pemilik](f02-ownership.csv): tiap tabel persisten dan tiap endpoint
  eksplisit HEAD, satu owner teknis usulan dan reviewer. Bukan matriks izin user.
- [Tes kontrak](../tests/test_f02_contracts.py) memeriksa vektor terhadap model,
  konversi qty, serta kelengkapan inventaris terhadap database/API sungguhan.
  Tes ini **tidak** membuktikan implementasi kontrak native yang belum ada.

## Identitas, unit, dan Decimal

| Pokok | BASELINE | Kontrak target / keputusan terbuka |
|---|---|---|
| ID | ID domain umumnya UUID4 server yang disimpan sebagai TEXT; sequence adalah urutan event, bukan ID bisnis. `Text` input menerima teks terpangkas 1–160 karakter, bukan validator UUID | Pertahankan ID internal stabil dan FK; kode/nama/reference bukan kunci join lintas sistem. Bedakan `production_order_id`, `sales_order_id`, `employee_id`, `user_id`, dan `party_id`; pemetaan employee/user tidak otomatis sama (D01/D09/D17) |
| Qty produk | `Quantity`: integer JSON strict, positif, maksimum 1.000.000.000 pcs; boolean/string/pecahan ditolak. Field outcome boleh nol sesuai model | `target_qty`, `actual_qty`, `payable_qty` terpisah. Jangan ubah target menjadi actual atau menyimpulkan payable dari completed (D02/D05) |
| Qty bahan | Master `m`, `kg`, `pcs`; API string Decimal maksimal 3 desimal, positif sampai 1.000.000 unit. Store memakai integer `*_milli`; `pcs` harus bulat di Store | Simpan nilai dalam unit dasar master, konversi tercatat bersama versinya. Unit dasar/konversi tambahan dan presisi rol/lembar/setelan menunggu D01/D03 |
| Lusin | Tidak ada rumus upah lusin native | Konversi fisik 12 pcs = 1 lusin tidak menetapkan apakah 13 pcs dibayar 13/12, 1, atau 2 lusin. Simpan pcs asal; pembulatan kuantitas upah dan tahapnya menunggu D04 |
| Uang | Input string desimal biasa, tanpa pemisah ribuan/eksponen/tanda; output uang 2 desimal. `Decimal` untuk hitung, `*_minor` integer untuk penyimpanan utama (100 minor = 1 IDR). Beberapa payload/riwayat tetap JSON | Jangan lewatkan uang melalui float atau JavaScript `Number` untuk kalkulasi authoritative. Currency eksplisit; HEAD laporan/snapshot memakai IDR. Currency/scale lain harus diputuskan D14 |
| Batas uang | `PurchasePrice` >0 sampai 1.000.000.000; `SewingJobCreate.cost` 0 sampai 1.000.000.000.000; supplier payment >0 sampai 1.000.000.000.000; `FinanceAmount` memakai maksimal 15 digit sebelum titik dan 2 sesudahnya, lalu validasi per field | Jangan menyamakan batas semua field. Validasi string, finite, skala, tanda dan overflow total sebelum tulis. Nilai negatif untuk komponen potongan/adjustment memerlukan tipe/arah eksplisit, bukan mengirim negatif ke model positif existing |
| Nilai hilang | Costing memberi `total_cost=null` dan coverage gap bila data tidak lengkap | Unknown bukan nol. Simpan alasan/bukti yang kurang; blokir finalisasi yang memerlukan angka tersebut |

Sumber: [models.py](../beeloft/models.py) (`Quantity`, `MaterialAmount`,
`MaterialQuantity`, `PurchasePrice`, `SewingJobCreate`, `FinanceAmount`) dan
[store.py](../beeloft/store.py) (`_material_amount`, `_material_decimal`).
Input dengan desimal berlebih ditolak; normalisasi `"12.3" -> "12.30"` bukan
izin membulatkan `"12.345"` diam-diam.

### Skala dan titik pembulatan

BASELINE sudah mempunyai beberapa titik pembulatan yang berbeda:

| Perhitungan | Titik pembulatan existing | Bukti |
|---|---|---|
| PO | Qty × harga, `ROUND_HALF_UP` ke 0,01 **per baris**, lalu jumlah baris; baris hasil <0,01 ditolak | `Store.create_purchase_order`; [test_purchase_orders.py](../tests/test_purchase_orders.py), `test_approval_and_multiple_lines_round_half_up` |
| Nilai penerimaan untuk approval supplier | Received × unit price, half-up per baris PO, lalu jumlah | `Store._purchase_order`; [test_supplier_payment_approvals.py](../tests/test_supplier_payment_approvals.py) |
| Costing produksi | Used + waste digabung per batch bahan, kali harga PO, half-up ke minor per batch; tambah biaya total job sewing aktif | `Store.production_cost`; [test_production_cost.py](../tests/test_production_cost.py) |
| Margin | Alokasi total biaya × qty terjual / finished qty, half-up ke minor; persentase margin ke 0,01, `null` jika denominator nol | `Store.contribution_margin`; [test_contribution_margin.py](../tests/test_contribution_margin.py) |

Ini bukan keputusan memakai half-up di seluruh payroll. Kontrak PROPOSED untuk
hasil kalkulasi menyertakan `calculation_policy_ref`, `quantity_scale`,
`money_scale`, `rounding_mode`, `rounding_stage`, dan input/rate revision yang
dipakai. Nilainya untuk charge/payroll/sales/valuasi menunggu D04/D10/D13/D14.
Jangan menghitung ulang histori menggunakan konfigurasi terbaru.

## Sumber transaksi dan pencegahan hitung ganda

BASELINE: snapshot berada di tabel `jubelio_*`/`mekari_*`, terpisah dari ledger
internal. Mapping produk hanya mendukung sistem `jubelio`, dengan event revision
dan pemeriksaan benturan external ID/SKU. Batch snapshot punya ID internal sendiri;
ID record eksternal dapat berulang antar-batch. Ringkasan umumnya memakai batch
terbaru menurut sequence, bukan menjumlah semua batch. Tidak ada registry asal
lintas domain/account, sales native, payroll native, atau deduplikasi cutover umum.

PROPOSED untuk paket X01/X02 dan domain penerima:

| Field | Makna / invariant |
|---|---|
| `source_kind` | `native`, `external_snapshot`, `imported_transaction`, atau `opening_balance`; arti kontribusi berbeda |
| `source_namespace` | Tuple terstruktur `(system, account_or_company, entity_type)`; semua elemen wajib untuk sumber eksternal. Contoh sintetis `("mekari", "DEMO-A", "payroll")`; bukan satu ID tanpa namespace |
| `source_id`, `source_line_id` | Identifier opaque dari sumber, termasuk huruf besar/kecil; normalisasi hanya menurut kontrak connector. Scope line berada di dalam source ID |
| `source_revision` | Versi/hash konten asal untuk mendeteksi event sama dengan payload berubah; bukan Idempotency-Key |
| `observed_at`, `snapshot_batch_id` | Waktu pengamatan/batch; tidak mengubah identitas transaksi ekonomi dan bukan otomatis tanggal transaksi |
| `canonical_transaction_id` | Identitas transaksi ekonomi yang menghubungkan record native/imported dan observasi snapshot; mapping harus eksplisit dan diaudit |
| `authority_ref` | Keputusan sumber berwenang untuk domain, unit, scope waktu/cutoff dan basis tanggal, disahkan D18/D19 |

Aturan review kontrak:

1. Record `42` di dua account atau dua entity type berbeda tidak boleh bertabrakan.
   Gunakan kolom tuple/constraint terstruktur, jangan concatenation ambigu.
2. Ingest `(namespace, source_id, source_line_id, source_revision)` yang sama
   tidak membuat efek ekonomi kedua, meskipun HTTP key/batch berbeda. Revision
   berubah masuk rekonsiliasi/koreksi; bukan otomatis transaksi baru.
3. Snapshot adalah observasi. Setelah native/imported menjadi authoritative untuk
   transaksi yang dipetakan, snapshot pasangannya hanya untuk rekonsiliasi. Jumlah
   contribution untuk satu canonical transaction pada satu ukuran laporan adalah
   paling banyak satu. Jangan `SUM(native) + SUM(snapshot)` untuk scope sama.
4. Mapping/authority/cutoff belum disahkan atau ambigu: tandai unresolved dan
   jangan terbitkan total gabungan seolah lengkap. Jangan menebak kesamaan dari
   reference, nominal, employee name atau tanggal saja. Agregat snapshot payroll
   tidak dapat dideduplikasi per employee tanpa detail sumber yang memadai.
5. Opening balance dan replay histori untuk saldo/cutoff yang sama saling
   eksklusif. Histori payroll yang sudah dibayar tidak boleh menjadi payable baru.
6. Laporan menyertakan basis tanggal, coverage, source authority dan snapshot time;
   perubahan mapping tidak boleh diam-diam menulis ulang jurnal atau histori biaya.

Fixture `SRC-*` menggambarkan hasil seleksi **usulan**, bukan menjalankan engine
deduplikasi baru. Policy authority pada fixture diasumsikan diberikan oleh pemilik
untuk contoh sintetis itu saja; pilihan sumber produksi tetap BLOCKED_F01.

## Kontrak lintas domain

Setiap record target membawa `id`, source identity di atas, `revision` bila
mutable, `actor_id`, `created_at` UTC, tanggal bisnis, `reason`, serta referensi
audit/koreksi. Timestamp harus berzona; tanggal bisnis ISO `YYYY-MM-DD` tidak
dikonversi menjadi instant. HEAD memakai tanggal operasional Jakarta. Kalender,
cutoff payroll dan tanggal posting tetap keputusan D07/D15, bukan jam server.

| Kontrak PROPOSED | Input / referensi wajib | Hasil dan invariant | Pemilik / gerbang |
|---|---|---|---|
| Qty / realization | Production order/line, product, unit dasar, job/employee, target dan event actual, QC/rework lineage | Actual hanya dari event aktif; reject/rework/missing eksplisit. `payable_qty` memerlukan keputusan eligibility terpisah; conservation qty dan larangan overdraw tetap berlaku | A1 P03; A2 I01 reviewer; D01–D05 |
| Tarif efektif | Work type/product/employee scope, currency, unit basis, `effective_from`, `effective_to`, rate revision, policy ref | Usulan interval `[from,to)` dan tepat satu rate untuk scope+tanggal basis. Tanggal basis (sent/completed/approved/dll.) harus dipilih D04; missing/overlap tidak memakai fallback diam-diam. Simpan rate revision dan nominal saat charge difinalisasi | A1 P01; A2 reviewer; D04 |
| Charge jasa | Realization ID/revision, employee, work type, payable qty, rate revision, input & rounding policy, currency | Amount Decimal final menjadi satu sumber biaya jasa dan upah. Satu realization/work component tidak ditagih dua kali; reversal menautkan charge asal. Costing dan payroll membaca charge yang sama, tidak menghitung rumus kedua | A1 P03/H01; A2 I01; D04/D05/D13 |
| Payroll | Employee, periode/cutoff, charge IDs/revisions, komponen bertipe premi/transport/bonus/potongan, installment IDs, policy refs | Baris dan total dapat ditelusuri; satu charge aktif tidak masuk dua payroll payable. Pisahkan gross, employee deductions, net pay dan employer cost; eligible components/formula/negatif/overlap menunggu D06–D08 | A1 H01/H02; A2 finance; D04–D08 |
| Kasbon | Employee, disbursement/opening balance, installment schedule/revision, payroll allocation atau pembayaran langsung | Saldo = sumber sah dikurangi pelunasan aktif ditambah pembalikannya; potongan payroll dan saldo kasbon berubah atomik. Batas potongan, net tidak cukup, resign, urutan cicilan menunggu D08 | A1 H02; A2 A01; D08/D19 |
| Pembayaran | Payable/receivable/payroll obligation, party, currency, amount, business date, method/account, allocation lines, source/payment reference | Approval tidak membuat kas bergerak. Bukti payment dan alokasi tercatat atomik; amount allocated tidak melampaui kapasitas yang disahkan; retry tidak menggandakan pembayaran. Partial/overpay/change/void/refund perlu D07/D11/D12 | A2 B02/S02, A1 payroll consumer; D07/D11/D12 |
| Posting jurnal | Sumber domain ID/revision/event, posting date, period, currency, account mapping revision, debit/credit lines | Debit = kredit per jurnal/currency; akun valid, periode terbuka, source event diposting paling banyak sekali. Persetujuan sumber, payment, posting adalah dimensi terpisah. COA/timing/pajak belum ditetapkan | A2 A01/A02; A1/A3 reviewer; D14/D15 |

Biaya `sewing_jobs.cost_minor` BASELINE adalah total yang diinput, termasuk job
aktif yang belum selesai; bukan rate per lusin atau approval upah employee.
Transisi ke charge harus punya mapping job lama → charge dan pilihan sumber biaya
yang saling eksklusif. Jangan menambah charge di atas sewing cost untuk pekerjaan
yang sama. Compatibility data lama harus dibuktikan oleh P03/I01/H01.

### Approved, paid, posted

| Dimensi | Bukti yang diperlukan | Tidak membuktikan |
|---|---|---|
| Approval | Decision event, actor/role, source revision dan alasan | Uang sudah berpindah atau jurnal sudah posted |
| Payment | Payment/allocation aktif dan bukti metode/tanggal/nominal | Jurnal sudah posted atau seluruh obligation lunas bila baru parsial |
| Posting | Jurnal seimbang yang committed untuk source event tertentu | Payment sudah terjadi; timing accrual vs cash ditentukan D14 |

BASELINE payroll menyimpan approval internal terpisah dari status payroll Mekari
dan metadata accounting snapshot. Snapshot posting yang tidak seimbang tetap
diterima agar rekonsiliasi dapat menandainya sebagai exception. **Jangan mengubah
reader snapshot menjadi validator jurnal native**: native posting target harus
menolak unbalanced journal, reader harus mempertahankan bukti selisih eksternal.
Lihat [test_payroll_accounting_reconciliation.py](../tests/test_payroll_accounting_reconciliation.py).
Approval supplier `payment_approved` juga bukan kas keluar. Tidak ada tabel
payment/COA/journal/closed period native pada schema 55.

## Idempotency, revision, atomisitas dan reversal

BASELINE mutasi domain melewati `Store._write`:

- `Idempotency-Key`: 1–128 karakter `[A-Za-z0-9._:-]`, unik **seluruh database**
  setelah migrasi 54; fingerprint SHA256 dari operation + payload yang telah
  divalidasi. Key bukan nomor dokumen dan bukan pengganti source identity.
- Actor aktif dan role diverifikasi ulang di transaksi. Actor sama + key dan
  fingerprint sama mendapat hasil tersimpan; perubahan payload/operation memberi
  409; actor berbeda memakai key lama memberi 403; akun nonaktif memberi 401.
- `expected_revision` dibandingkan dengan revision terkini di write transaction
  pada operasi yang memilikinya. Revision adalah token opaque dari respons:
  sebagian event memakai sequence global; klien tidak boleh mengasumsikan `+1`.
  Konflik 409 memerlukan reload/review, bukan retry dengan revision ditebak.
- SQLite WAL, `BEGIN IMMEDIATE`, FK dan trigger menjaga saldo/state. Efek domain,
  receipt idempotency, audit dan event terkait commit bersama; error rollback
  semuanya. 503 busy membawa `Retry-After: 1`; retry memakai key yang sama.
- Data input tidak sah 422, objek tidak ditemukan 404, role terlarang 403,
  constraint/state/revision conflict 409. Pesan error tidak berarti sebagian
  transaksi boleh diteruskan.
- Reversal mempertahankan record asli: event `reversal_of` atau tabel reversal
  unik per sumber, alasan dan actor. Reverse berulang/ketika hasil sudah dipakai
  downstream ditolak; unwind dependensi dalam urutan terbalik. Retur/refund/void
  bukan sinonim reversal; domain harus menentukan efek fisik dan finansialnya.

Bukti: [test_idempotency_actor.py](../tests/test_idempotency_actor.py),
[test_production.py](../tests/test_production.py),
[test_cutting.py](../tests/test_cutting.py),
[test_payroll_approvals.py](../tests/test_payroll_approvals.py).
Session/SSO/read/backup bukan mutasi domain `_write`; jangan menjanjikan receipt
idempotency untuk semua endpoint di inventaris.

PROPOSED: payment allocation, charge/payroll consumption, kasbon deduction dan
posting menyertakan constraint uniqueness bisnis selain HTTP key. Perubahan
lintas domain dalam DB yang sama memakai satu transaksi, audit, revision guard
dan rollback menyeluruh. Efek sistem eksternal memerlukan kontrak retry serta
rekonsiliasi tersendiri (X01); tidak dijamin atomik oleh SQLite lokal.

### Locking periode (belum diimplementasikan)

A02 harus mengecek state/revision periode **di dalam transaksi yang sama** dengan
posting/reversal/correction. Close bersaing dengan post harus menghasilkan satu
urutan yang sah: post selesai sebelum close, atau post ditolak setelah close;
tidak ada write yang lolos karena mengecek periode sebelum mengambil lock.
Record posted immutable. Koreksi memakai jurnal pembalik bertaut sumber, dengan
nilai berlawanan dan referensi asli; bukan delete/update jurnal asal.

Tanggal reversal lintas periode, hak close/reopen, penanganan late adjustment,
cutoff, dan apakah wajib memakai periode terbuka berikutnya menunggu D15/D17.
Tidak otomatis membuka periode atau menggeser tanggal. Approval keputusan bisnis
tidak boleh meniadakan jejak koreksi. Fixture `PERIOD-01` belum bisa diberi expected
tanggal/jurnal final sebelum kebijakan ini disahkan.

## Pemilik dan urutan migrasi

[Inventaris CSV](f02-ownership.csv) mencatat objek **existing**, termasuk route
non-OpenAPI yang didefinisikan aplikasi. Static mount dan route dokumentasi
otomatis FastAPI di luar kontrak domain dan dimiliki A3. `sqlite_sequence` adalah
internal SQLite; `requests_v54` hanya tabel sementara migrasi yang sudah berganti
nama menjadi `requests`, sehingga tidak dicatat sebagai tabel persisten baru.

Owner di CSV adalah pembagian kerja **usulan** berdasarkan #39: A1 produksi/people,
A2 commerce/finance dan master employee M02, A3 integrasi/operasi/laporan, A0
kontrak bersama. Endpoint gabungan tetap satu owner; reviewer domain wajib ikut.
Tidak memberi izin runtime atau mengklaim orang/agent tersebut telah menyetujui.
Untuk M02 → P03/H01, A2 menjaga identitas employee dan A1 mengonsumsi ID yang sama.
A3 menjaga snapshot ingestion; A1/A2 mereview semantik data, A0 koordinasi konflik.

`store.py`, `models.py`, `api.py`, `static/app.mjs` serta migrasi adalah file
bersama: reservasi **fungsi/objek dan paket**, bukan kepemilikan eksklusif seluruh
file. Perubahan kontrak lintas domain direview kedua pemilik; A0 menyelesaikan
konflik dan memeriksa baseline lagi sebelum integrasi.

| Urutan dependensi | Objek target (nama logis, belum DDL/route) | Owner / reviewer | Gerbang sebelum implementasi/migrasi |
|---|---|---|---|
| W0 | F01 keputusan, F02 kontrak, F03 audit | A0; A1/A2/A3 | Freeze dan sign-off; merge dokumen saja tidak cukup |
| W1 M01/M02/O01 | Produk/unit/konversi; unit usaha/storage/party/employee; izin per fungsi | A1 / A2 / A3; A0 koordinasi FK | D01/D17, kontrak ID dan kompatibilitas data lama |
| W1 A01/O02 | COA, periode, journal header/lines/source; recovery/audit/idempotency bersama | A2/A3; A1 reviewer posting | D14/D15; kontrak posting disepakati sebelum produsen jurnal |
| W2 P01/P02/B01/X01 | Rate revision/template jasa, planning/cutting, parity PO, namespace/mapping/import manifest | A1/A2/A3 sesuai paket | Master/izin diterima; D02–D04/D12/D18/D19; dry-run mapping sebelum import |
| W3 P03/I01/B02 | Realization/charge, inventory cost/transfer, AP settlement/payment allocation | A1/A2; reviewer silang biaya | Tarif + accounting; D05/D12/D13; sewing cost lama tidak dihitung dua kali |
| W4 H01/H02/S01/S02 | Payroll/component/charge consumption, kasbon/installment, sales/price/payment/return | A1/A2; A3 reviewer invariant | D04–D12 dan kontrak payment/journal; stok/charge/ledger siap |
| W5 A02/R01 | Rekonsiliasi, close/reopen, laporan/export | A2/A3; A1 reviewer payroll | Subledger diterima, D15/D16; control totals lintas laporan |
| W6 X02/Q01 | Mapping final, saldo awal/delta, UAT | A3; A0 dan pemilik domain | D19/D20; rehearsal upgrade, restore dan deduplikasi |
| W7 Q02 | Cutover dan hypercare | A0/A3 + pemilik proses | Sign-off bisnis dan rollback yang melindungi transaksi baru |

Tabel ini urutan parsial dependensi, bukan izin menjalankan seluruh migrasi
gelombang serentak; ikuti juga dependensi tiap issue paket. **Tidak ada nomor
migrasi yang dipesan F02.** Schema tetap 55. A0 mengalokasikan nomor berikutnya
dari HEAD saat paket siap (bukan menganggap 56 masih kosong). Upgrade wajib
mempertahankan ID/source, jumlah dan nilai, status serta audit/reversal; backfill
tak pasti dikarantina, bukan default paid/posted. Bukti paket schema meliputi DB
baru, upgrade schema lama yang didukung, rerun aman, `integrity_check`,
`foreign_key_check`, control totals dan backup/restore terpisah. Data produksi
tidak digunakan dalam PR/CI atau validasi lokal.

## Fixture, penerimaan dan handoff

`BASELINE` memuat input valid/invalid quantity, money, timestamp, revision dan
metadata posting eksternal. `PROPOSED` memuat contoh namespace/deduplikasi serta
pemisahan state. `BLOCKED_F01` memuat 1/11/12/13 pcs, pergantian tarif, reject/rework,
komponen payroll, cicilan kasbon, pembayaran/retur dan koreksi periode tutup.
Semua identitas/angka sintetis; belum ada contoh bisnis EXxx berstatus approved.
Skenario target menyebut expected invariant dan Dxx yang harus diisi; nilainya
tidak boleh dijadikan fallback runtime.

| Penerimaan #41 | Status / bukti yang masih diperlukan |
|---|---|
| Fixture disepakati A1/A2/A3 | PENDING; masing-masing mereview input, expected result dan batas baseline/target pada revisi file yang sama |
| Namespace eksternal dan tanpa double count | Kontrak PROPOSED + fixture SRC; implementasi dan bukti cutover belum ada, menunggu D18/D19 |
| Pemilik tiap tabel/endpoint dan urutan migrasi tercatat | Inventaris HEAD dan urutan di atas tersedia; penugasan/reviewer masih usulan |
| F01 diterima dan aturan bisnis tersedia | BLOCKED_F01; D01–D20 OPEN, EX01–EX15 belum approved |
| Koordinator dan bisnis menerima F02 | PENDING; #41 tetap terbuka dan W0 belum lolos |

| Sign-off | Lingkup | Status / waktu / bukti |
|---|---|---|
| A1 | Qty, tarif, charge, payroll, kasbon; fixture QTY/RATE/CHARGE/PAYROLL/LOAN | PENDING / belum ada / belum ada |
| A2 | Money, payment, stok/valuasi, journal/period; fixture PAY/POST/PERIOD/SRC | PENDING / belum ada / belum ada |
| A3 | Namespace, retry/revision, audit, migrasi dan semua negative cases | PENDING / belum ada / belum ada |
| A0 + pemilik bisnis F01 | Dxx/EXxx, konflik ownership, batas penerimaan dan freeze | PENDING / belum ada / belum ada |

Approval harus mencantumkan commit/hash fixture, revisi keputusan, peran approver,
waktu dan referensi bukti yang aman dipublikasikan. Perubahan policy membuka ulang
review fixture/paket yang terdampak. Jangan mengubah status menjadi agreed dari
hasil tes atau merge saja.

Handoff teknis: branch `docs/f02-shared-transaction-contracts`; commit dasar
`efe1156c4557e0f4b69f0000d674ce74fdc4ae0c`. Commit akhir dan hasil perintah uji
dicatat pada body PR setelah commit. File berubah: README, dokumen ini, CSV
ownership, fixture JSON dan tes kontrak. Tidak ada perubahan runtime/API/schema,
nomor migrasi, dependency atau versi aplikasi. Jalankan:

```sh
python -m unittest discover -s tests -p test_f02_contracts.py -v
```

Tes integrasi existing yang dirujuk di atas tetap bukti perilaku baseline, bukan
sign-off rumus payroll/accounting baru. Risiko utama: F01 belum frozen, tidak ada
source-authority/cutoff produksi yang disahkan, dan belum ada pemisahan akses gaji
per fungsi. Langkah berikut: A0 meminta keputusan/bukti F01, reviewer melengkapi
expected result dan sign-off, baru membuka implementasi domain yang bergantung.
