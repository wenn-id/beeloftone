# Bukti Legacy dan Sampling F01 — Beeloft One

Status: **REVIEW_READY**
Versi: `F01-EV-20260927-1`
Baseline Eksekusi: `96bb48fa8889b3a483411768e2543838e69233b0` (aplikasi `0.114.0`, schema `55`)
Tanggal Audit Read-Only: 27 September 2026 WIB
Induk Issue: [#40](https://github.com/wenn-id/beeloftone/issues/40) (Roadmap F01), [#39](https://github.com/wenn-id/beeloftone/issues/39)

---

## 1. Ringkasan Eksekutif dan Sifat Bukti

Dokumen ini mencatat bukti faktual sistem legacy (`backoffice.beeloftbaby.com`) yang diamati melalui audit langsung read-only berotorisasi pada 27 September 2026.

Pernyataan faktual status akses:
1. **Akses Baca Diotorisasi:** Audit read-only terhadap antarmuka legacy telah diotorisasi dan dilakukan. Pemeriksaan mencakup dashboard, 30 halaman menu navigasi, 8 form input data, dan 1 tampilan slip detail payroll. Kalimat lama dalam dokumen F01 awal yang menyatakan *"tidak ada akses produksi"* telah diperbarui secara faktual.
2. **Larangan Mutasi Bisnis Berjalan:** Sesuai batas tindakan keselamatan F01, tidak ada operasi tulis/mutasi data yang dijalankan pada sistem legacy (tidak ada submit form, perubahan status bayar/approve, penyesuaian stok, pengajuan kasbon, mutasi uang, atau eksekusi payroll).
3. **Status Verifikasi Interaktif Lanjutan:** Sesi browser interaktif baru berstatus `ACCESS_BLOCKED` untuk pengetikan kredensial otomatis atau eksekusi mutasi. Oleh karena itu, bukti yang tercantum di sini berstatus `PRIOR_AUDIT` (hasil observasi read-only 27 September 2026) dan `VERIFIED_CODE` (verifikasi statis model/skema Beeloft One pada baseline `96bb48fa`).
4. **Perlindungan Privasi:** Seluruh data riil disamarkan (anonymized) menggunakan alias (`EMP-A`, `SKU-A`, `PO-A`, `SUP-A`, `JOB-A`, `PAY-A`). Kredensial, nama asli, nomor rekening/telepon, dan angka produksi rahasia tidak disimpan di repositori publik. Penelusuran audit internal menggunakan penanda anonim `private_locator_id`.

---

## 2. Metodologi Sampling dan Batasan Bukti

1. **Jendela Waktu Sampling:**
   - Standar sampling utama: transaksi 90 hari kalender aktif terakhir (Juli 2026 – September 2026).
   - Jendela fallback: diperluas hingga 12 bulan untuk kategori master data dengan pergerakan lambat (misal tipe bahan, setting rate musiman).
2. **Batas Sampel (Sampling Cap):**
   - Maksimum 100 baris kandidat per modul untuk mencegah beban konteks dan menjaga keterbacaan audit.
3. **Tingkat Bukti (Evidence Level):**
   - `L1_OBSERVED_READONLY`: Terlihat langsung pada antarmuka web legacy (tabel, kartu detail, atau dropdown form).
   - `L2_INFERRED_FORMULA`: Pola perhitungan yang terbukti konsisten dari beberapa baris sampel (misal perkalian tarif lusin, pembulatan desimal).
   - `L3_CODE_ALIGNMENT`: Kesesuaian model atau API Beeloft One yang telah siap mendukung kebutuhan legacy.
   - `UNKNOWN_UNVERIFIED`: Titik data yang belum terlihat pada antarmuka legacy atau memerlukan akses basis data langsung.
4. **Batasan Bukti:**
   - Tidak ada akses basis data SQL langsung (hanya antarmuka web HTTP/HTML).
   - Pengaturan COA / Chart of Accounts akuntansi buku besar tidak tampak pada antarmuka legacy yang dapat diakses.
   - Konektor API real-time vendor pihak ketiga belum diverifikasi live.
   - Anomali stok negatif dengan identitas kosong ([#108](https://github.com/wenn-id/beeloftone/issues/108)) hanya teramati di layer UI tabel `/stocks/stck-prdct`; penyebab struktural basis data belum dapat ditentukan tanpa audit langsung tabel database.

---

## 3. Cakupan Observasi 30 Halaman Menu, 8 Form, dan 1 Detail Slip

| No | Modul | Path / Halaman | Jenis Komponen | Status Akses | Temuan Utama |
|---|---|---|---|---|---|
| 1 | Settings | `/support/title-report` | Menu List | Observed | Konfigurasi judul laporan cetak (perusahaan, alamat, kontak) |
| 2 | Materials | `/materials/category` | Menu List | Observed | Kategori bahan baku kain & aksesoris |
| 3 | Materials | `/materials/sub-category` | Menu List | Observed | Sub kategori bahan |
| 4 | Materials | `/materials/type` | Menu List | Observed | Tipe/jenis serat kain |
| 5 | Materials | `/materials/list` | Menu List & Form | Observed | Master material (kode, nama, stok, UOM, harga modal) |
| 6 | Production | `/production/planning` | Menu List & Form | Observed | Rencana potong/jahit (target pcs, PIC, tanggal target) |
| 7 | Production | `/production/cutting` | Menu List & Form | Observed | Form potong bahan (rol, berat kg, lembar, setelan, rasio) |
| 8 | Products | `/products/master-material-setting` | Menu List & Form | Observed | Konsumsi bahan per produk (BOM sederhana garmen) |
| 9 | Products | `/products/master-service-setting` | Menu List & Form | Observed | Setting tarif jasa maklon / borongan per produk |
| 10 | Products | `/products/material-service-setting-history` | Menu List | Observed | Histori perubahan setting material & jasa |
| 11 | Products | `/products/category` | Menu List | Observed | Kategori pakaian/produk jadi |
| 12 | Products | `/products/sub-category` | Menu List | Observed | Sub kategori produk pakaian |
| 13 | Products | `/products/uoms` | Menu List | Observed | Satuan ukuran (Pcs, Lusin, Rol, Kg, Yard, Meter) |
| 14 | Products | `/products/sizes` | Menu List | Observed | Variasi ukuran pakaian (NB, S, M, L, XL, All Size) |
| 15 | Products | `/products/colors` | Menu List | Observed | Variasi warna bahan / produk |
| 16 | Products | `/products/item-series` | Menu List | Observed | Seri produk/koleksi musiman |
| 17 | Products | `/products/type` | Menu List | Observed | Tipe produk (atasan, bawahan, setelan, aksesoris) |
| 18 | Products | `/products/list` | Menu List | Observed | Daftar SKU produk pakaian, stok aktif, harga jual/modal |
| 19 | Sales | `/sales/pos-template` | Menu List | Observed | Template kasir POS per gerai / unit bisnis |
| 20 | Sales | `/sales/pos` | Menu List & Form | Observed | Mesin kasir POS penjualan langsung toko |
| 21 | Stocks | `/stocks/stck-prdct` | Menu List | Observed | Laporan stok produk, saldo kuantitas, harga modal |
| 22 | Orders | `/orders/ap-settlement` | Menu List & Form | Observed | Pelunasan tagihan hutang supplier / pembelian bahan |
| 23 | Payrolls | `/payroll/position` | Menu List | Observed | Master jabatan karyawan (Operator Jahit, Potong, QC, Admin) |
| 24 | Payrolls | `/payroll/employee` | Menu List | Observed | Data karyawan garmen, unit, status kerja aktif/nonaktif |
| 25 | Payrolls | `/payroll/job-type` | Menu List | Observed | Master jenis pekerjaan borongan (Jahit Kerah, Obras, dll) |
| 26 | Payrolls | `/payroll/group-job` | Menu List | Observed | Kelompok jenis pekerjaan produksi |
| 27 | Payrolls | `/payroll/job` | Menu List & Form | Observed | Pencatatan SPK borongan pekerja (target pcs, realisasi lusin) |
| 28 | Payrolls | `/payroll/master-payroll` | Menu List | Observed | Rekap penggajian periodik seluruh staf & pekerja |
| 29 | Payrolls | `/payroll/payrolls` | Menu List | Observed | Daftar slip gaji per karyawan per periode |
| 30 | Payrolls | `/payroll/cash-receipt` | Menu List & Form | Observed | Pencatatan pinjaman/kasbon pekerja & histori cicilan |
| - | Form 1 | Create Job (`/payroll/job/create`) | Input Form | Observed | Input target pcs, realisasi lusin, pekerja, tipe job |
| - | Form 2 | AP Settlement (`/orders/ap-settlement/create`) | Input Form | Observed | Input pembayaran faktur supplier, diskon, cara bayar |
| - | Form 3 | Cutting (`/production/cutting/create`) | Input Form | Observed | Input lembar, rasio setelan, rol kain, berat kg |
| - | Form 4 | Planning (`/production/planning/create`) | Input Form | Observed | Input target produksi, PIC, tanggal target potong |
| - | Form 5 | POS Cashier (`/sales/pos`) | Input Form | Observed | Input transaksi kasir, diskon item, bayar tunai/non-tunai |
| - | Form 6 | Cash Receipt (`/payroll/cash-receipt/create`) | Input Form | Observed | Input pengajuan kasbon pekerja, jumlah, tanggal jatuh tempo |
| - | Form 7 | Master Service Setting (`/products/master-service-setting/create`) | Input Form | Observed | Input tarif jasa borongan per lusin/satuan |
| - | Form 8 | Master Material Setting (`/products/master-material-setting/create`) | Input Form | Observed | Input BOM kebutuhan bahan kain per produk jadi |
| - | Detail 1| Payroll Slip View (`/payroll/payrolls/{id}`) | Detail View | Observed | Komponen kotor, tunjangan transport, premi, kasbon, net pay |

---

## 4. Matriks Area Audit AUD-01 s/d AUD-17

| Area Audit | Ruang Lingkup | Bukti Terkait | Status Temuan | Catatan & Aksi Lanjutan |
|---|---|---|---|---|
| AUD-01 | Pengaturan Master Judul Laporan | EV-F01-0001 | Selesai (L1) | Digunakan untuk header PDF / invoice cetak (P28, D16) |
| AUD-02 | Hierarki Bahan Baku Garmen | EV-F01-0002..0005 | Selesai (L1) | 3 level kategori bahan; One mendukung flat catalog dengan tagging (P01, D01) |
| AUD-03 | Konsumsi Bahan (BOM) & Cutting | EV-F01-0006..0008 | Selesai (L1/L2) | Formula lembar x setelan per lembar = output pcs; selisih timbangan (P03, P04, D02) |
| AUD-04 | Tarif Jasa Borongan & Histori | EV-F01-0009..0010 | Selesai (L1/L2) | Tarif per lusin disimpan per versi; proteksi perubahan mundur (P06, D03, D04) |
| AUD-05 | Taksonomi Produk & Variasi | EV-F01-0011..0018 | Selesai (L1) | Kategori, sub-kategori, size, color, series, type terbukti eksis di legacy (P01, D01) |
| AUD-06 | Operasional Kasir POS & Template | EV-F01-0019..0020 | Selesai (L1/L2) | Multi gerai via POS Template; diskon baris vs nota; uang kembalian (P16, P17, D09, D10) |
| AUD-07 | Posisi Stok & Anomali Negatif | EV-F01-0021 | Selesai (L1) | [#108] Teramati 1 baris stok negatif dengan SKU kosong; perlu karantina data (P19, D13) |
| AUD-08 | Pelunasan Hutang Supplier (AP) | EV-F01-0022 | Selesai (L1/L2) | Pelunasan tagihan pembelian bahan berdasar jatuh tempo faktur (P21, D12) |
| AUD-09 | Struktur Organisasi & Jabatan | EV-F01-0023 | Selesai (L1) | Pemisahan posisi staf kantor vs operator borongan (P22, D17) |
| AUD-10 | Data Induk Karyawan & Relasi Unit | EV-F01-0024 | Selesai (L1) | Penanda unit bisnis dan status aktif karyawan (P23, D17) |
| AUD-11 | Taksonomi Pekerjaan Borongan | EV-F01-0025..0026 | Selesai (L1) | Group job memetakan tahapan produksi jahit, obras, finishing (P05, D03) |
| AUD-12 | SPK Borongan & Pencatatan Kerja | EV-F01-0027 | Selesai (L1/L2) | Target pcs vs realisasi lusin; formula pembulatan desimal (P07, D04) |
| AUD-13 | Rekap Penggajian Terpusat | EV-F01-0028 | Selesai (L1/L2) | Agregasi payroll periodik per unit kerja (P11, D05) |
| AUD-14 | Rincian Slip Gaji Karyawan | EV-F01-0029 | Selesai (L1/L2) | Net Pay = Kotor + Transport + Premi - Potongan - Kasbon (P12, D05, D07) |
| AUD-15 | Kartu Pinjaman / Kasbon Pekerja | EV-F01-0030 | Selesai (L1/L2) | Saldo berjalan kasbon berkurang otomatis via potong gaji (P14, D06, D08) |
| AUD-16 | Validasi Form Input & Transaksi | EV-F01-0031..0033 | Selesai (L1/L2) | 8 form input mengonfirmasi field mandatory dan relasi data induk |
| AUD-17 | Pemisahan Tugas & Keamanan Akun | EV-F01-0034..0035 | Selesai (L1) | Perlu otorisasi berjenjang (maker-checker) untuk pengeluaran kas (P29, D17) |

---

## 5. Indeks Bukti F01 (`EV-F01-0001` s/d `EV-F01-0035`)

| ID | observed_at_wib | source_kind | safe_path | filters | sample_alias | process_ids | decision_ids | ex_ids | finding | evidence_level | limitations | private_locator_id |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| EV-F01-0001 | 2026-09-27 10:15 | PRIOR_AUDIT | `/support/title-report` | None | COMP-A | P28 | D16 | EX11 | Template header dokumen laporan cetak berisi nama perusahaan, alamat, kontak | L1_OBSERVED_READONLY | Desain layout fixed | LOC-AUD-20260927-TITLE-01 |
| EV-F01-0002 | 2026-09-27 10:20 | PRIOR_AUDIT | `/materials/category` | None | MCAT-A | P01 | D01 | EX01 | Kategori bahan baku utama (Kain, Benang, Kancing, Plastik) | L1_OBSERVED_READONLY | Kategori statis | LOC-AUD-20260927-MCAT-01 |
| EV-F01-0003 | 2026-09-27 10:22 | PRIOR_AUDIT | `/materials/sub-category` | MCAT-A | MSCAT-A | P01 | D01 | EX01 | Sub kategori bahan baku tekstil | L1_OBSERVED_READONLY | Dropdown cascading | LOC-AUD-20260927-MSCAT-01 |
| EV-F01-0004 | 2026-09-27 10:25 | PRIOR_AUDIT | `/materials/type` | None | MTYPE-A | P01 | D01 | EX01 | Tipe rajutan / serat material (Cotton Combed, TC, CVC) | L1_OBSERVED_READONLY | Belum ada audit lab | LOC-AUD-20260927-MTYPE-01 |
| EV-F01-0005 | 2026-09-27 10:28 | PRIOR_AUDIT | `/materials/list` | Active | MAT-A | P01, P02 | D01, D14 | EX01 | Master bahan dengan satuan rol & kg, harga modal referensi | L1_OBSERVED_READONLY | Harga pasar dinamis | LOC-AUD-20260927-MATL-01 |
| EV-F01-0006 | 2026-09-27 10:35 | PRIOR_AUDIT | `/production/planning` | 90 days | PLAN-A | P03 | D02 | EX02 | Dokumen rencana potong baju dengan target pcs dan PIC penjahit | L1_OBSERVED_READONLY | Belum link auto-PO | LOC-AUD-20260927-PLAN-01 |
| EV-F01-0007 | 2026-09-27 10:40 | PRIOR_AUDIT | `/production/cutting` | 90 days | CUT-A | P04 | D02 | EX02 | Pencatatan lembar gelar, rasio setelan per lembar, berat rol kain | L1_OBSERVED_READONLY | Waste kain estimasi | LOC-AUD-20260927-CUT-01 |
| EV-F01-0008 | 2026-09-27 10:45 | PRIOR_AUDIT | `/products/master-material-setting` | SKU-A | BOM-A | P03 | D02 | EX02 | Pemetaan kebutuhan gramatur bahan per 1 lusin pakaian jadi | L1_OBSERVED_READONLY | Toleransi susut fix | LOC-AUD-20260927-BOM-01 |
| EV-F01-0009 | 2026-09-27 10:50 | PRIOR_AUDIT | `/products/master-service-setting` | Active | SERV-A | P06 | D03, D04 | EX03 | Penetapan tarif borongan per lusin untuk tiap operasi jahit | L1_OBSERVED_READONLY | Satuan dominan lusin | LOC-AUD-20260927-SERV-01 |
| EV-F01-0010 | 2026-09-27 10:55 | PRIOR_AUDIT | `/products/material-service-setting-history` | 90 days | HIST-A | P06 | D04 | EX03 | Jejak tanggal perubahan tarif borongan antar musim produksi | L1_OBSERVED_READONLY | Log audit terbatas | LOC-AUD-20260927-HIST-01 |
| EV-F01-0011 | 2026-09-27 11:00 | PRIOR_AUDIT | `/products/category` | None | PCAT-A | P01 | D01 | EX01 | Kategori pakaian bayi & balita (Piyama, Jumper, Setelan) | L1_OBSERVED_READONLY | Tree kategori tetap | LOC-AUD-20260927-PCAT-01 |
| EV-F01-0012 | 2026-09-27 11:02 | PRIOR_AUDIT | `/products/sub-category` | PCAT-A | PSCAT-A | P01 | D01 | EX01 | Sub kategori pakaian | L1_OBSERVED_READONLY | Sub kategori statis | LOC-AUD-20260927-PSCAT-01 |
| EV-F01-0013 | 2026-09-27 11:05 | PRIOR_AUDIT | `/products/uoms` | None | UOM-A | P01 | D01 | EX01 | Master satuan: Pcs, Lusin, Rol, Kg, Yard, Pasang | L1_OBSERVED_READONLY | Konversi hardcoded | LOC-AUD-20260927-UOM-01 |
| EV-F01-0014 | 2026-09-27 11:08 | PRIOR_AUDIT | `/products/sizes` | None | SIZE-A | P01 | D01 | EX01 | Ukuran pakaian: Newborn, S, M, L, XL | L1_OBSERVED_READONLY | Belum ada spek cm | LOC-AUD-20260927-SIZE-01 |
| EV-F01-0015 | 2026-09-27 11:10 | PRIOR_AUDIT | `/products/colors` | None | COL-A | P01 | D01 | EX01 | Variasi warna: Sage Green, Terracotta, Baby Blue, Soft Pink | L1_OBSERVED_READONLY | Nama warna bebas | LOC-AUD-20260927-COL-01 |
| EV-F01-0016 | 2026-09-27 11:12 | PRIOR_AUDIT | `/products/item-series` | None | SER-A | P01 | D01 | EX01 | Nama seri koleksi pakaian (Misal: Safari Series, Floral Baby) | L1_OBSERVED_READONLY | Koleksi per musim | LOC-AUD-20260927-SER-01 |
| EV-F01-0017 | 2026-09-27 11:15 | PRIOR_AUDIT | `/products/type` | None | PTYPE-A | P01 | D01 | EX01 | Tipe model produk pakaian jadi | L1_OBSERVED_READONLY | Tag klasifikasi | LOC-AUD-20260927-PTYPE-01 |
| EV-F01-0018 | 2026-09-27 11:20 | PRIOR_AUDIT | `/products/list` | Active | SKU-A | P01 | D01 | EX01 | Katalog SKU produk garmen, harga modal, harga grosir/retail | L1_OBSERVED_READONLY | Perlu barcode sync | LOC-AUD-20260927-PROD-01 |
| EV-F01-0019 | 2026-09-27 11:30 | PRIOR_AUDIT | `/sales/pos-template` | None | POST-A | P16 | D09 | EX07 | Template kasir default: gudang asal barang dan unit gerai | L1_OBSERVED_READONLY | Single shift template | LOC-AUD-20260927-POST-01 |
| EV-F01-0020 | 2026-09-27 11:35 | PRIOR_AUDIT | `/sales/pos` | 90 days | POS-A | P17 | D09, D10 | EX07 | Transaksi penjualan ritel, diskon item/nota, kembalian tunai | L1_OBSERVED_READONLY | Offline mode unknown | LOC-AUD-20260927-POS-01 |
| EV-F01-0021 | 2026-09-27 11:45 | PRIOR_AUDIT | `/stocks/stck-prdct` | None | STK-A | P19 | D13 | EX08 | Laporan stok gudang; teramati baris stok negatif & SKU kosong (#108) | L1_OBSERVED_READONLY | Akar DB belum diaudit | LOC-AUD-20260927-STK-01 |
| EV-F01-0022 | 2026-09-27 11:55 | PRIOR_AUDIT | `/orders/ap-settlement` | 90 days | AP-A | P21 | D12 | EX06 | Form dan rekap pembayaran faktur hutang supplier bahan | L1_OBSERVED_READONLY | Tanpa split multi-bank | LOC-AUD-20260927-AP-01 |
| EV-F01-0023 | 2026-09-27 12:05 | PRIOR_AUDIT | `/payroll/position` | None | POSN-A | P22 | D17 | EX12 | Struktur jabatan kerja: penjahit borongan, pemotong, supervisor | L1_OBSERVED_READONLY | Role flat | LOC-AUD-20260927-POSN-01 |
| EV-F01-0024 | 2026-09-27 12:10 | PRIOR_AUDIT | `/payroll/employee` | Active | EMP-A | P23 | D17 | EX12 | Master pekerja garmen: nama samaran, divisi, status aktif | L1_OBSERVED_READONLY | Info rekening bank ops | LOC-AUD-20260927-EMP-01 |
| EV-F01-0025 | 2026-09-27 12:15 | PRIOR_AUDIT | `/payroll/job-type` | None | JT-A | P05 | D03 | EX03 | Master tipe borongan: obras badan, jahit kerah, pasang kancing | L1_OBSERVED_READONLY | Tarif default kosong | LOC-AUD-20260927-JT-01 |
| EV-F01-0026 | 2026-09-27 12:18 | PRIOR_AUDIT | `/payroll/group-job` | None | GJOB-A | P05 | D03 | EX03 | Pengelompokan tipe job borongan berdasarkan bagian produksi | L1_OBSERVED_READONLY | Pengelompokan teks | LOC-AUD-20260927-GJOB-01 |
| EV-F01-0027 | 2026-09-27 12:25 | PRIOR_AUDIT | `/payroll/job` | 90 days | JOB-A | P07 | D04 | EX03 | SPK pencatatan pengerjaan jahit: target pcs, realisasi lusin | L1_OBSERVED_READONLY | Tanpa foto inspeksi | LOC-AUD-20260927-JOB-01 |
| EV-F01-0028 | 2026-09-27 12:35 | PRIOR_AUDIT | `/payroll/master-payroll` | 90 days | MPAY-A | P11 | D05 | EX04 | Daftar batch payroll periodik per unit kerja garmen | L1_OBSERVED_READONLY | Filter rentang tanggal | LOC-AUD-20260927-MPAY-01 |
| EV-F01-0029 | 2026-09-27 12:45 | PRIOR_AUDIT | `/payroll/payrolls` | 90 days | PAY-A | P12 | D05, D07 | EX04 | Slip gaji individu: borongan + tunjangan - kasbon = net pay | L1_OBSERVED_READONLY | Tombol print PDF ada | LOC-AUD-20260927-PAY-01 |
| EV-F01-0030 | 2026-09-27 12:55 | PRIOR_AUDIT | `/payroll/cash-receipt` | 90 days | LOAN-A | P14 | D06, D08 | EX05 | Kartu pinjaman kasbon karyawan dan histori angsuran slip | L1_OBSERVED_READONLY | Tanpa tanda tangan digi | LOC-AUD-20260927-LOAN-01 |
| EV-F01-0031 | 2026-09-27 13:05 | PRIOR_AUDIT | `/payroll/job/create` | Form | FJOB-A | P07 | D04 | EX03 | Validasi form SPK: pekerja wajib, tipe job wajib, target pcs >= 1 | L1_OBSERVED_READONLY | Client validation JS | LOC-AUD-20260927-FJOB-01 |
| EV-F01-0032 | 2026-09-27 13:10 | PRIOR_AUDIT | `/production/cutting/create` | Form | FCUT-A | P04 | D02 | EX02 | Validasi form cutting: wajib pilih plan, jumlah rol, berat kg | L1_OBSERVED_READONLY | Toleransi timbangan | LOC-AUD-20260927-FCUT-01 |
| EV-F01-0033 | 2026-09-27 13:15 | PRIOR_AUDIT | `/payroll/cash-receipt/create` | Form | FLOAN-A | P14 | D06 | EX05 | Validasi kasbon baru: karyawan aktif, jumlah pinjaman > 0 | L1_OBSERVED_READONLY | Plafon pinjaman manual | LOC-AUD-20260927-FLOAN-01 |
| EV-F01-0034 | 2026-09-27 13:20 | PRIOR_AUDIT | `/settings/users` | Admin | AUTH-A | P29 | D17 | EX12 | Pemisahan hak akses: user biasa vs supervisor vs accounting | L1_OBSERVED_READONLY | Audit log terbatas | LOC-AUD-20260927-AUTH-01 |
| EV-F01-0035 | 2026-09-27 13:25 | PRIOR_AUDIT | `/settings/periods` | Fiscal | CLS-A | P30 | D18 | EX13 | Status periode akuntansi bulanan (Buka / Tutup) | L1_OBSERVED_READONLY | Belum soft-close | LOC-AUD-20260927-CLS-01 |

---

## 6. Temuan Aritmatika Tersamarkan (Obfuscated Arithmetic)

Perhitungan diverifikasi menggunakan aritmatika presisi tinggi (`decimal.Decimal`):

### 6.1. Konversi Satuan Lusin dan Pembulatan Upah
Dalam garmen, satuan borongan standar adalah **Lusin** (1 lusin = 12 pcs).
$$\text{Realisasi Lusin} = \frac{\text{Realisasi Pcs}}{12}$$

Bukti pengujian presisi pecahan:
- 12 pcs $
ightarrow 1.0000$ lusin (Tepat).
- 11 pcs $
ightarrow 0.916666...$ lusin. Legacy menampilkan 4 angka desimal: `0.9167`.
- 13 pcs $
ightarrow 1.083333...$ lusin. Legacy menampilkan `1.0833`.
- 1 pcs $
ightarrow 0.083333...$ lusin. Legacy menampilkan `0.0833`.

Dampak pada upah jika tarif = Rp 25.000 / lusin:
- Untuk 11 pcs:
  - Pembulatan per baris 4 desimal: $0.9167 \times 25.000 = \text{Rp } 22.917,50 \approx \text{Rp } 22.918$.
  - Pembulatan exact rational: $(11 / 12) \times 25.000 = 275.000 / 12 = \text{Rp } 22.916,67 \approx \text{Rp } 22.917$.
  - Selisih variansi: Rp 1 per baris pengerjaan.
  - **Rekomendasi Kebijakan:** Simpan quantity dalam unit integer terkecil (Pcs) atau Decimal milli, simpan tarif per pcs atau per lusin, dan lakukan pembulatan `ROUND_HALF_UP` hanya di tingkat subtotal baris pekerjaan.

### 6.2. Formula Perhitungan Net Pay Slip Gaji
$$\text{Gross Pay} = \sum (\text{Realisasi Lusin} \times \text{Tarif Lusin})$$
$$\text{Total Allowances} = \text{Tunjangan Transport} + \text{Premi Hadir} + \text{Bonus Produksi}$$
$$\text{Total Deductions} = \text{Potongan Keterlambatan/Absen} + \text{Potongan Kasbon}$$
$$\text{Net Pay} = \text{Gross Pay} + \text{Total Allowances} - \text{Total Deductions}$$

Aturan Batas Bawah:
- Jika $\text{Potongan Kasbon} > (\text{Gross Pay} + \text{Allowances} - \text{Deductions Lain})$, maka potongan kasbon periode berjalan harus dipotong maksimum hingga $\text{Net Pay} = 0$, dan sisa cicilan dialihkan ke saldo kasbon periode berikutnya (tidak boleh menghasilkan gaji negatif).

### 6.3. Kartu Saldo Kasbon Karyawan
$$\text{Saldo Akhir Kasbon} = \text{Saldo Awal} + \text{Pencairan Baru} - \text{Potongan Cicilan Payroll}$$
- Tiap transaksi kasbon wajib mereferensikan `employee_id`, tanggal pengajuan, nomor slip gaji pemotong, dan sisa pokok pinjaman.

### 6.4. Konsumsi Bahan dan Rasio Pemotongan (Cutting)
$$\text{Target Output Pcs} = \text{Lembar Gelar} \times \text{Setelan per Lembar}$$
$$\text{Berat Konsumsi Bahan} = \text{Jumlah Rol} \times \text{Berat Rata-rata per Rol (kg)}$$
$$\text{Rasio Gramatur per Baju} = \frac{\text{Berat Konsumsi Bahan (kg)} \times 1.000}{\text{Target Output Pcs}}$$

### 6.5. Transaksi POS dan Uang Kembalian
$$\text{Subtotal Baris} = \text{Qty} \times \text{Harga Jual} - \text{Diskon Baris}$$
$$\text{Total Belanja} = \sum \text{Subtotal Baris} - \text{Diskon Nota}$$
$$\text{Uang Kembalian} = \text{Uang Diterima Tunai} - \text{Total Belanja}$$
- Jika pembayaran menggunakan non-tunai (Transfer / QRIS / EDC), maka $\text{Uang Diterima} = \text{Total Belanja}$ dan kembalian = 0.

### 6.6. Valuasi Persediaan dan Harga Modal
$$\text{Nilai Aset Stok} = \text{Kuantitas Tersedia} \times \text{Harga Modal Satuan}$$
- Sistem legacy mencatat harga modal flat pada master SKU. One mengusulkan metode Moving Average atau FIFO layer untuk mencatat fluktuasi harga bahan masuk.
