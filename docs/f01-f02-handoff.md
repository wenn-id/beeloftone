# Handoff F01 ke F02 — Beeloft One

Status: **REVIEW_READY**
Versi: `F01-HANDOFF-20260927-1`
Baseline Eksekusi: `96bb48fa8889b3a483411768e2543838e69233b0` (aplikasi `0.114.0`, schema `55`)
Tanggal: 27 September 2026 WIB
Induk Issue: [#40](https://github.com/wenn-id/beeloftone/issues/40) (Roadmap F01)
Penerima Handoff: [#41](https://github.com/wenn-id/beeloftone/issues/41) (Roadmap F02: Kontrak transaksi dan data bersama)

---

## 1. Tujuan Handoff

Dokumen ini memetakan seluruh hasil temuan proses bisnis, register keputusan (**D01–D20**), katalog bukti (**EX01–EX15**), dan kasus sintetis (**CASE-QTY-01 s/d CASE-CTRL-03**) dari paket **F01 (#40)** ke dalam kontrak bersama **F02 (#41)**.

F01 adalah paket discovery dan pembekuan proses bisnis. F02 membaca dokumen ini sebagai dasar perancangan kontrak data teknis (JSON Schema, invariant DB, state machine, dan verifikasi lintas modul). Paket F01 tidak mengimplementasikan runtime kontrak atau mengubah file fixture downstream `tests/fixtures/f02-contracts.json`.

---

## 2. Matriks Pemetaan Keputusan Bisnis ke Kontrak F02

| Keputusan | Rule Version | Proses Terkait | Kasus Sintetis / EX Terkait | Bukti Terkait | Bagian Kontrak / Skenario F02 | Status Keputusan | Dampak Teknis pada F02 | Blocker Tersisa |
|---|---|---|---|---|---|---|---|---|
| D01 | `D01-RULE-20260927-1` | P01, P02 | CASE-QTY-05, EX01 | EV-F01-0002..0005, 0011..0018 | Master Models & Organization | PROPOSED | Standarisasi UUID/SKU, pencegahan transaksi pada data nonaktif | Menunggu pengesahan daftar kolom usang |
| D02 | `D02-RULE-20260927-1` | P04, P05 | EX02 | EV-F01-0006 | Order & Planning Lifecycle | PROPOSED | State machine planning, penguncian target setelah proses potong dimulai | Menunggu pengesahan aturan revisi target |
| D03 | `D03-RULE-20260927-1` | P08, P09 | CASE-QTY-06, EX02 | EV-F01-0007, 0008, 0032 | Cutting & Material Invariants | PROPOSED | Aritmatika desimal konversi rol ke kg ke gram; toleransi susut | Menunggu konfirmasi batas toleransi susut kain |
| D04 | `D04-RULE-20260927-1` | P03, P11 | CASE-QTY-01..04, CASE-RATE-01, EX03 | EV-F01-0009, 0010, 0027, 0031 | `QTY-RATE-01`, `RATE-02` | PROPOSED | Pembulatan lusin 4 desimal per baris vs akumulasi total slip | Menunggu penetapan mode pembulatan resmi |
| D05 | `D05-RULE-20260927-1` | P11, P12, P13 | CASE-RATE-03, CASE-RATE-04, EX03 | EV-F01-0027, 0031 | `CHARGE-01` | PROPOSED | Pemisahan target pcs, actual pcs, dan payable pcs (hanya lolos QC yang dibayar) | Menunggu kebijakan denda reject |
| D06 | `D06-RULE-20260927-1` | P20, P21, P22 | CASE-PAY-01, EX04 | EV-F01-0028, 0029 | `PAYROLL-01` | PROPOSED | Formula Net Pay, komponen tunjangan/premi, batas bawah upah (Net Pay >= 0) | Menunggu konfirmasi plafon potongan gaji |
| D07 | `D07-RULE-20260927-1` | P22, P23 | CASE-PAY-02, EX04 | EV-F01-0028, 0029 | Payroll Lifecycle & Reversal | PROPOSED | Pemisahan state APPROVED, PAID, dan POSTED; penanganan job terlambat | Menunggu jadwal cutoff mingguan |
| D08 | `D08-RULE-20260927-1` | P24 | CASE-PAY-03, CASE-PAY-04, EX05 | EV-F01-0030, 0033 | `LOAN-01` | PROPOSED | Ledger saldo berjalan kasbon, pengalihan sisa cicilan bila net pay tidak cukup | Menunggu batas maksimum pinjaman karyawan |
| D09 | `D09-RULE-20260927-1` | P17 | EX06 | EV-F01-0019, 0020 | POS & Sales Invariants | PROPOSED | Pengikatan POS Template ke unit usaha dan gudang sumber barang spesifik | Menunggu inventaris gerai toko aktif |
| D10 | `D10-RULE-20260927-1` | P17 | CASE-POS-01, CASE-POS-02, EX06 | EV-F01-0020 | Pricing & Discount Invariants | PROPOSED | Alokasi diskon item persen dan diskon nota nominal ke nilai baris | Menunggu aturan otorisasi diskon manual |
| D11 | `D11-RULE-20260927-1` | P18, P19 | CASE-POS-03, EX07 | EV-F01-0020 | `PAY-01` | PROPOSED | Penanganan uang kembalian tunai, verifikasi nominal pas EDC/QRIS, retur toko | Menunggu SOP retur uang tunai kasir |
| D12 | `D12-RULE-20260927-1` | P06, P07, P25 | CASE-AP-01, CASE-AP-02, EX08 | EV-F01-0022 | AP Matching & Disbursement | PROPOSED | Pemisahan AP Pembelian Bahan (with-PO) dan Biaya Umum (non-PO) | Menunggu daftar akun biaya operasional |
| D13 | `D13-RULE-20260927-1` | P14, P26 | EX09 | EV-F01-0021 | Valuation & Inventory Cost | PROPOSED | Metode Moving Average, penanganan karantina anomali stok negatif (#108) | Menunggu penetapan metode akuntansi |
| D14 | `D14-RULE-20260927-1` | P23, P27 | EX10 | EV-F01-0035 | General Ledger Posting | PROPOSED | Kontrak jurnal debit/kredit, presisi mata uang IDR rupiah penuh | Menunggu struktur Chart of Accounts (COA) |
| D15 | `D15-RULE-20260927-1` | P27 | CASE-CTRL-01, EX10 | EV-F01-0035 | `PERIOD-01` | PROPOSED | Penguncian periode akuntansi bulanan, penolakan transaksi di periode closed | Menunggu penetapan tanggal tutup buku |
| D16 | `D16-RULE-20260927-1` | P28, P30 | EX11 | EV-F01-0001 | Title Reports & Document Header | PROPOSED | Template judul laporan cetak (Kop surat, alamat, kontak) untuk seluruh PDF | Menunggu data profil legal perusahaan |
| D17 | `D17-RULE-20260927-1` | P29 | CASE-CTRL-02, EX12 | EV-F01-0023, 0024, 0034 | RBAC & Segregation of Duties | PROPOSED | Pemisahan tugas mutlak (Pemohon kas / slip tidak boleh menjadi approver) | Menunggu matriks penugasan per karyawan |
| D18 | `D18-RULE-20260927-1` | P15, P19, P31 | EX13 | EV-F01-0020 | Integration Boundaries | PROPOSED | Pemisahan transaksi POS langsung dengan kanal marketplace batch ingestion | Menunggu daftar credential API kanal aktif |
| D19 | `D19-RULE-20260927-1` | P32 | CASE-CTRL-03, EX14 | EV-F01-0034 | `SRC-04` (Cutoff / Migration) | PROPOSED | Strategi Saldo Awal (Opening Balance) per tanggal cutover, arsip historis | Menunggu penetapan tanggal cutover migrasi |
| D20 | `D20-RULE-20260927-1` | P33 | EX15 | EV-F01-0034 | Operations & Recovery | PROPOSED | Kebijakan backup otomatis harian, retensi 30 hari, target RTO 2 jam | Menunggu penunjukan personel penanggung jawab |

---

## 3. Klasifikasi Kesiapan Kontrak Teknis

Untuk mempermudah pelaksanaan pekerjaan di Issue #41 (F02), seluruh komponen dikelompokkan ke dalam empat tingkat kesiapan:

### Tingkat 1: Siap Diformalkan sebagai Kontrak Teknis (Immediate Contract Definition)
Komponen ini telah didukung sepenuhnya oleh model One, bukti audit visual legacy, dan praktik rekayasa perangkat lunak standar:
1. **Identifier & Foreign Keys:** Seluruh relasi data induk (Master SKU, Material, Employee, Supplier, Customer, Unit, Storage) wajib menggunakan ID stabil non-null.
2. **Kuantitas Barang:** Kuantitas produk jadi wajib disimpan sebagai bilangan bulat (`integer`) dalam satuan pieces (Pcs). Kuantitas bahan mentah disimpan dalam satuan desimal (`Decimal`) presisi 3 desimal (skala mili: gram / mili-meter).
3. **Mata Uang & Keuangan:** Seluruh nilai rupiah menggunakan tipe data `Decimal` presisi 2 desimal atau integer sen/rupiah, dengan pembulatan `ROUND_HALF_UP`.
4. **Idempotency & Revision Guard:** Seluruh operasi pembuatan transaksi penting (POS, AP, Payroll, Kasbon) wajib menyertakan kunci idempotensi (`idempotency_key`) dan nomor versi revisi (`lock_version`).

### Tingkat 2: Pola Teramati Menunggu Pengesahan Kebijakan (Candidate Policies Pending Sign-off)
Pola yang telah ditemukan konsisten di legacy, namun status legal bisnisnya memerlukan ketukan palu pemilik bisnis:
1. Pembulatan pecahan lusin borongan 4 desimal per baris pengerjaan.
2. Aturan batas bawah Net Pay tidak boleh negatif (`net_pay >= 0`).
3. Pengalihan sisa cicilan kasbon yang belum terpotong ke periode gaji berikutnya.
4. Metode penilaian persediaan menggunakan Moving Average.

### Tingkat 3: Kesenjangan Akses / Data Legacy (Legacy Data Gaps)
Fitur atau data yang belum dapat diverifikasi secara visual pada akun audit read-only 27 September 2026:
1. Struktur Bagan Akun Standar (COA) native.
2. Logika pengujian server-side permission lintas peran (RBAC runtime).
3. Konektor API sinkronisasi langsung vendor marketplace.
4. Investigasi akar penyebab stok negatif dengan SKU kosong ([#108](https://github.com/wenn-id/beeloftone/issues/108)).

### Tingkat 4: Implementasi & Pengujian Operasional Downstream (W1–W7 Packages)
Hal-hal yang bukan merupakan ruang lingkup kontrak data F02, melainkan implementasi paket hilir:
- M01 (#43) & M02 (#44): Endpoint CRUD dan migrasi data master.
- P01 (#48) & P02 (#49): Logika kalkulator cutting dan penjadwalan planning.
- P03 (#52) & H01 (#55): Alur kerja approval SPK jahit dan engine penggajian massal.
- H02 (#56): Buku besar kasbon karyawan dan pemotongan slip.
- S01 (#57) & S02 (#58): Antarmuka kasir web POS dan pelunasan piutang.
- A01 (#46) & A02 (#59): Mesin jurnal akuntansi otomatis dan tutup buku bulanan.
- Q01 (#62) & Q02 (#63): Pengujian beban terpadu dan cutover sistem produksi.

---

## 4. Tautan Handoff ke Issue #41

Hasil handoff ini diserahkan kepada koordinator paket **F02 (#41)** dengan catatan:
1. Status paket F01 berada pada tahap **REVIEW_READY**.
2. F02 dapat mulai memformalkan JSON Schema dan skenario invariant bersama berdasarkan rekomendasi D01–D20 di atas.
3. Transisi F02 ke tahap `BUSINESS_ACCEPTED` tetap terikat pada penerimaan sign-off resmi pemilik proses bisnis terhadap paket keputusan F01.
