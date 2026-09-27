# F01: keputusan, bukti, dan sign-off

Pasangan [register proses](f01-process-register.md) untuk [issue #40](https://github.com/wenn-id/beeloftone/issues/40).
Execution baseline: `96bb48fa8889b3a483411768e2543838e69233b0` (aplikasi `0.114.0`, schema `55`), diperiksa 27 September 2026 WIB.
Baseline historis: `2bee57075b2e0826dfcd581691d37585e7dd1df2` (v0.97.0/schema 55) dan `f8921e763a8b317f3680229aedb9406ddba687c8` (v0.87.0/schema 55) dipertahankan sebagai riwayat perencanaan, bukan HEAD saat ini.
Status paket: **REVIEW_READY; belum Integrated atau Business accepted**.
Seluruh keputusan bisnis dan contoh fixture berstatus usulan terverifikasi (**PROPOSED / DRAFT_SYNTHETIC**), menunggu penetapan dan sign-off resmi pemilik proses bisnis.

---

## 1. Batas yang Dinyatakan Sumber dan Batas Tindakan

Ketentuan berikut berasal dari [#39](https://github.com/wenn-id/beeloftone/issues/39), [#40](https://github.com/wenn-id/beeloftone/issues/40), dan audit langsung 27 September 2026:

1. **Seluruh proses wajib dipetakan:** 34 proses bisnis (P01–P34) dipetakan ke One atau dihentikan dengan keputusan eksplisit pemilik. Tidak terlihat pada akun audit tidak membuktikan proses tidak dipakai.
2. **Pemisahan Konsep Transaksi:**
   - Target produksi, realisasi aktual, dan kuantitas layak dibayar (payable) adalah konsep terpisah ([#49](https://github.com/wenn-id/beeloftone/issues/49)).
   - Status transaksi *APPROVED*, *PAID*, dan *POSTED* harus dipisahkan secara tegas ([#41](https://github.com/wenn-id/beeloftone/issues/41)). Approval permohonan pembayaran supplier bukan bukti kas keluar; pencatatan pembayaran memerlukan bukti transfer atau kuitansi kas.
3. **Penyelarasan Status Akses Legacy:**
   - Akses read-only berotorisasi telah dilakukan pada 27 September 2026 (dashboard, 30 halaman menu, 8 form input, 1 detail payroll).
   - Batas keselamatan F01 tetap berlaku: tidak ada mutasi bisnis yang dieksekusi pada sistem legacy (tidak ada submit form, perubahan status bayar, penyesuaian stok, pengajuan kasbon, mutasi uang, atau eksekusi payroll).
   - Kalimat lama yang menyatakan *"tidak ada akses produksi"* telah diperbarui secara faktual untuk mencatat bahwa akses baca diotorisasi dan dilakukan.
4. **Perlindungan Integritas Arsitektur One:**
   - Pertahankan ledger double-entry, invariant uang/qty (integer / Decimal milli), idempotency, revision guard, transaksi atomik, dan audit trail/reversal berpasangan.
   - Jangan menambahkan rumus payroll kedua di costing atau menghitung biaya sewing lama dan charge jasa baru dua kali ([#52](https://github.com/wenn-id/beeloftone/issues/52), [#53](https://github.com/wenn-id/beeloftone/issues/53)).
5. **Privasi dan Keamanan Data:**
   - Repositori publik, PR, dan CI hanya memuat contoh sintetis (`synthetic=true`).
   - Tidak ada password, token, data pribadi karyawan/pelanggan, atau nominal transaksi nyata yang disimpan di repositori publik.

---

## 2. Register Keputusan Bisnis (D01–D20)

Status seluruh keputusan saat ini: **PROPOSED** (Usulan Berdasarkan Bukti Audit).
Setiap keputusan memiliki versi aturan kandidat (`rule_version`), formula/usulan, presisi unit, bukti pendukung (`EV-F01-xxxx`), dan kasus uji sintetis (`CASE-xxx`).

| ID | rule_version | Keputusan yang Harus Diisi Pemilik | Formula / Usulan Kandidat | Unit & Presisi | PJ Bisnis (Usulan) | Bukti Terkait | Kasus Sintetis Terkait | Issue Penerima | Status |
|---|---|---|---|---|---|---|---|---|---|
| D01 | `D01-RULE-20260927-1` | Standarisasi master produk, bahan, UOM, dan pembersihan kolom usang | Pertahankan hierarki kategori; hapus kolom catatan bebas tak terpakai; konversi eksplist | String ID, Decimal milli | Master + Operasi | EV-F01-0002..0005, 0011..0018 | CASE-QTY-05 | #43, #44, #41 | PROPOSED |
| D02 | `D02-RULE-20260927-1` | Status & approval planning; perubahan target/tenggat setelah berjalan | Target awal dikunci setelah cutting dimulai; revisi target via rencana tambahan (split run) | Pcs (Integer) | Produksi | EV-F01-0006 | EX02 | #49, #41 | PROPOSED |
| D03 | `D03-RULE-20260927-1` | Rumus cutting rol/berat/lembar/setelan; output, toleransi susut dan waste | Target Pcs = Lembar x Setelan; Toleransi susut dihitung dari berat rol vs gramatur baju | Kg, Gram, Pcs | Produksi + Gudang Bahan | EV-F01-0007, 0008, 0032 | CASE-QTY-06 | #49, #53 | PROPOSED |
| D04 | `D04-RULE-20260927-1` | Basis upah borongan per lusin/pcs; pembulatan pecahan lusin dan uang | Lusin = Pcs / 12; Upah per baris dibulatkan ROUND_HALF_UP ke Rupiah penuh (scale=0) | Rupiah (Decimal), Lusin (4 desimal) | Payroll + Produksi | EV-F01-0009, 0010, 0027, 0031 | CASE-QTY-01..04, CASE-RATE-01 | #48, #55, #41 | PROPOSED |
| D05 | `D05-RULE-20260927-1` | Kelayakan bayar upah, reject & rework; approval SPK pengerjaan | Hanya kuantitas LOLOS QC (Payable Pcs) yang dibayar; rework operator sendiri tidak dibayar | Pcs (Integer), Rupiah | Produksi + Payroll | EV-F01-0027, 0031 | CASE-RATE-03, CASE-RATE-04 | #52, #55, #53 | PROPOSED |
| D06 | `D06-RULE-20260927-1` | Komponen slip gaji, tunjangan, premi, dan batas bawah upah (Net Pay >= 0) | Net Pay = Gross + Tunjangan + Premi + Bonus - Potongan - Kasbon; Batas bawah Net Pay = 0 | Rupiah (Decimal) | HR + Payroll | EV-F01-0028, 0029 | CASE-PAY-01 | #55 | PROPOSED |
| D07 | `D07-RULE-20260927-1` | Periode & cutoff payroll mingguan; penanganan pekerjaan terlambat | SPK diserahkan lewat batas cutoff otomatis masuk ke periode berikutnya (tanpa reopen) | Tanggal ISO, Rupiah | Payroll + Finance | EV-F01-0028, 0029 | CASE-PAY-02 | #55, #46, #61 | PROPOSED |
| D08 | `D08-RULE-20260927-1` | Aturan pinjaman kasbon, kartu saldo berjalan, dan pelunasan di luar payroll | Saldo Akhir = Saldo Awal + Pencairan - Cicilan; Pelunasan langsung kas diizinkan | Rupiah (Decimal) | Payroll + Finance | EV-F01-0030, 0033 | CASE-PAY-03, CASE-PAY-04 | #56, #46 | PROPOSED |
| D09 | `D09-RULE-20260927-1` | Saluran penjualan selain POS; integrasi template kasir (POS Template) | POS Template mengikat kasir toko ke gudang sumber stok spesifik toko tersebut | String ID | Sales + Gudang | EV-F01-0019, 0020 | EX06 | #57 | PROPOSED |
| D10 | `D10-RULE-20260927-1` | Otorisasi diskon, hierarki diskon baris vs nota, dan harga terkunci | Diskon baris dihitung lebih dahulu; diskon nota dialokasikan proporsional ke baris | Persen (2 desimal), Rupiah | Sales + Accounting | EV-F01-0020 | CASE-POS-01, CASE-POS-02 | #57, #41 | PROPOSED |
| D11 | `D11-RULE-20260927-1` | Penanganan uang kembalian tunai, verifikasi non-tunai, dan retur kasir | Kembalian = Bayar Tunai - Total; Non-tunai wajib pas; Retur mereferensikan struk asli | Rupiah (Decimal) | Sales + Finance | EV-F01-0020 | CASE-POS-03 | #58, #46 | PROPOSED |
| D12 | `D12-RULE-20260927-1` | Parity AP Settlement: pemisahan tagihan With-PO vs Non-PO operasional | Pembelian bahan wajib 3-way matching (PO-Receipt-Invoice); Biaya umum butuh approval | Rupiah (Decimal) | Purchasing + AP + Finance | EV-F01-0022 | CASE-AP-01, CASE-AP-02 | #50, #54, #46 | PROPOSED |
| D13 | `D13-RULE-20260927-1` | Metode valuasi persediaan bahan dan produk jadi; penanganan anomali #108 | Metode Moving Average; Record stok negatif dengan SKU kosong masuk karantina migrasi | Rupiah (Decimal), Pcs | Accounting + Produksi | EV-F01-0021 | CASE-AP-05 | #53, #46 | PROPOSED |
| D14 | `D14-RULE-20260927-1` | Struktur Bagan Akun Standar (COA), jurnal otomatis, dan aturan posting | Jurnal seimbang Debit = Kredit per event bisnis; mata uang IDR rupiah penuh | Rupiah (Decimal) | Accounting | EV-F01-0035 | EX10 | #46, #41 | PROPOSED |
| D15 | `D15-RULE-20260927-1` | Periode tutup buku bulanan; hak close/reopen dan penolakan transaksi susulan | Transaksi pada periode tertutup ditolak otomatis 409 Conflict; reopen butuh otorisasi | Status Period | Accounting | EV-F01-0035 | CASE-CTRL-01 | #59, #61 | PROPOSED |
| D16 | `D16-RULE-20260927-1` | Standardisasi konfigurasi judul laporan cetak (Title Reports) dan kop surat | Tabel Title Reports memuat nama perusahaan, kop, alamat, dan kontak untuk seluruh PDF | String Text | Manajemen + Operasi | EV-F01-0001 | EX11 | #60 | PROPOSED |
| D17 | `D17-RULE-20260927-1` | Matriks peran pengguna (RBAC), hak akses, dan larangan self-approval | Pemohon pengeluaran kas atau slip gaji dilarang menyetujui pengajuannya sendiri (403) | Role Perms | Operasi + Seluruh Pemilik | EV-F01-0023, 0024, 0034 | CASE-CTRL-02 | #45, #41 | PROPOSED |
| D18 | `D18-RULE-20260927-1` | Batas integrasi kanal eksternal; pemisahan order marketplace vs POS | POS bersifat realtime lokal; marketplace ingestion berkala dengan karantina unmapped SKU | Ingestion State | Sales Kanal + Operasi | EV-F01-0020 | EX13 | #57, #58, #51 | PROPOSED |
| D19 | `D19-RULE-20260927-1` | Strategi migrasi data legacy: Cutoff Saldo Awal vs Replay Transaksi Historis | Migrasi Saldo Awal (Opening Balance) per tanggal cutoff; histori lama disimpan sebagai arsip | Migration Strategy | Operasi + Accounting | EV-F01-0034 | CASE-CTRL-03 | #51, #61, #63 | PROPOSED |
| D20 | `D20-RULE-20260927-1` | Target pemulihan operasional (RPO / RTO), retensi backup, dan rollback | Backup harian retensi 30 hari; target RTO <= 2 jam; rollback menjamin keamanan data | Jam, Hari | Operasi + Manajemen | EV-F01-0034 | EX15 | #47, #62, #63 | PROPOSED |

---

## 3. Katalog Bukti Sintetis (EX01–EX15)

Status seluruh kelompok bukti saat ini: **DRAFT_SYNTHETIC** (Menunggu Pengesahan Pemilik).
Seluruh contoh telah disusun dalam bentuk data sintetis non-sensitif pada `docs/f01-legacy-cases.json`.

| ID | Kelompok Dokumen / Bukti | Proses Terkait | Status | Referensi Skenario Kasus Sintetis |
|---|---|---|---|---|
| EX01 | Master produk, bahan, satuan, kategori, seri, warna, ukuran | P01, P02, P03, P20 | DRAFT_SYNTHETIC | CASE-QTY-05, FLD-SKU-001..010 |
| EX02 | Dokumen planning, form cutting, lembar gelar, rasio setelan, berat | P04..P10 | DRAFT_SYNTHETIC | CASE-QTY-06, FLD-CUT-001..010 |
| EX03 | SPK pengerjaan jahit, tarif per lusin, realisasi lusin, reject/rework | P03, P11..P13 | DRAFT_SYNTHETIC | CASE-QTY-01..04, CASE-RATE-01..05 |
| EX04 | Slip gaji individu, komponen tunjangan/premi, net pay, rekap periodik | P20..P23 | DRAFT_SYNTHETIC | CASE-PAY-01, CASE-PAY-02, CASE-PAY-05 |
| EX05 | Kartu pinjaman kasbon, pencairan, cicilan payroll, pelunasan mandiri | P24 | DRAFT_SYNTHETIC | CASE-PAY-03, CASE-PAY-04, FLD-LOAN-001..005 |
| EX06 | Transaksi kasir POS, diskon item persen, diskon nota, struk belanja | P17, P18 | DRAFT_SYNTHETIC | CASE-POS-01, CASE-POS-02, FLD-POS-001..010 |
| EX07 | Kembalian pembayaran tunai kasir, verifikasi EDC/QRIS, retur toko | P15..P19 | DRAFT_SYNTHETIC | CASE-POS-03, CASE-POS-04, CASE-POS-05 |
| EX08 | Faktur supplier, AP Settlement with-PO, biaya operasional non-PO | P06, P07, P25, P28 | DRAFT_SYNTHETIC | CASE-AP-01, CASE-AP-02, CASE-AP-03 |
| EX09 | Kartu stok gudang, harga modal (Capital), isolasi anomali stok negatif | P08, P14, P26 | DRAFT_SYNTHETIC | CASE-AP-04, CASE-AP-05 (#108) |
| EX10 | Jurnal umum subledger, neraca saldo, penguncian periode bulanan | P23, P27 | DRAFT_SYNTHETIC | CASE-CTRL-01, FLD-ACC-001..005 |
| EX11 | Template judul laporan cetak (Title Reports: nama perusahaan, alamat, logo) | P30, P34 | DRAFT_SYNTHETIC | FLD-TTL-001..005, EV-F01-0001 |
| EX12 | Matriks hak akses pengguna (RBAC), aturan larangan self-approval | P29 | DRAFT_SYNTHETIC | CASE-CTRL-02, FLD-USR-001..005 |
| EX13 | Kontrak payload event sinkronisasi kanal eksternal dan karantina unmapped | P15..P19, P31 | DRAFT_SYNTHETIC | EV-F01-0020, INTEGRATION_CONTRACTS |
| EX14 | Matriks migrasi cutoff saldo awal, rekonsiliasi kontrol total, dan arsip | P32 | DRAFT_SYNTHETIC | CASE-CTRL-03, EV-F01-0034 |
| EX15 | Runbook pemulihan sistem bencana, jadwal backup harian, dan SOP rollback | P33 | DRAFT_SYNTHETIC | EV-F01-0034, Operations Runbook |

---

## 4. Gerbang Freeze dan Matriks Sign-Off Resmi

| Kriteria Gerbang Freeze | Status Saat Ini | Bukti Pemenuhan | Tindak Lanjut untuk Mencapai BUSINESS_ACCEPTED |
|---|---|---|---|
| Seluruh 34 proses memiliki input, aktor, status, hasil, koreksi, laporan, dan PJ | LULUS | `docs/f01-process-register.md` | Konfirmasi tertulis penugasan peran dari manajemen |
| Seluruh 20 keputusan (D01–D20) teridentifikasi lengkap dengan formula usulan | LULUS | Tabel Bagian 2 di atas & `docs/f01-owner-decisions.md` | Ketukan palu pilihan kebijakan dari Business Owner |
| Bukti audit live read-only terindeks dan tersamarkan | LULUS | `docs/f01-legacy-evidence.md` (EV-F01-0001..0035) | Siap diaudit |
| Kamus field legacy terpetakan dengan disposisi terarah | LULUS | `docs/f01-field-map.csv` (58 field) | Persetujuan penghapusan kolom yang diusulkan pensiun |
| Seluruh kasus sintetis terverifikasi perhitungan desimal | LULUS | `docs/f01-legacy-cases.json` (24 kasus) | Pengesahan nilai `expected_business_result` oleh pemilik |
| Handoff teknis ke paket downstream F02 terpetakan jelas | LULUS | `docs/f01-f02-handoff.md` | Issue #41 siap memulai perancangan kontrak data |
| Sign-off resmi seluruh pemilik proses bisnis tercatat | MENUNGGU | Tabel sign-off di bawah masih PENDING | Penandatanganan dokumen `docs/f01-owner-decisions.md` |

### Tabel Sign-Off Pemilik Proses Bisnis

| Peran Pemilik Bisnis | Cakupan Proses | Cakupan Keputusan | Status Persetujuan | Tanggal | Referensi Otorisasi |
|---|---|---|---|---|---|
| Kepala Produksi & QC | P03–P16 | D02, D03, D05, D13 | PENDING | [YYYY-MM-DD] | Menunggu pengesahan pemilik |
| Kepala HR & Payroll | P20–P24 | D04, D06, D07, D08, D17 | PENDING | [YYYY-MM-DD] | Menunggu pengesahan pemilik |
| Kepala Toko & Sales Kanal | P15–P19, P31 | D09, D10, D11, D18 | PENDING | [YYYY-MM-DD] | Menunggu pengesahan pemilik |
| Kepala Pembelian & Purchasing | P06, P07, P25 | D12 | PENDING | [YYYY-MM-DD] | Menunggu pengesahan pemilik |
| Kepala Keuangan & Akuntansi | P18, P19, P22–P28 | D07, D08, D11–D15, D19 | PENDING | [YYYY-MM-DD] | Menunggu pengesahan pemilik |
| Operasi, Master Data & IT | P01, P02, P29–P34 | D01, D16, D17, D19, D20 | PENDING | [YYYY-MM-DD] | Menunggu pengesahan pemilik |
| Koordinator Teknis Roadmap (A0) | Seluruh Paket F01 | Validasi Integritas & Kontrak F02 | REVIEW_READY | 2026-09-27 | F01-EXEC-20260927-1 |
