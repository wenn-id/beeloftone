# Paket Review Keputusan Bisnis F01 — Beeloft One

Status Dokumen: **PROPOSED / REVIEW_READY** (Menunggu Pengesahan Pemilik Bisnis)
Versi: `F01-OWNER-20260927-1`
Baseline Eksekusi: `96bb48fa8889b3a483411768e2543838e69233b0` (v0.114.0, schema 55)
Tanggal Penyusunan: 27 September 2026 WIB
Induk Issue: [#40](https://github.com/wenn-id/beeloftone/issues/40)

---

## 1. Panduan untuk Pemilik Bisnis

Dokumen ini disusun khusus sebagai paket peninjauan (review package) bagi pemilik bisnis (Business Owner) Beeloft Baby dan pemangku kepentingan proses bisnis untuk menetapkan keputusan definitif (**D01–D20**).

Keputusan dalam dokumen ini diperlukan agar arsitektur transaksi bersama (**F02 / Issue #41**) dan gelombang implementasi teknis (**W1–W7**) dapat dibangun di atas aturan bisnis yang mengikat, tanpa spekulasi pengembang.

### Status Keputusan Saat Ini
- **Status Sekarang:** Seluruh keputusan berstatus `PROPOSED` (Usulan Berdasarkan Bukti Audit).
- **Syarat Menjadi `BUSINESS_ACCEPTED`:** Pemilik bisnis menyetujui rekomendasi atau memilih alternatif kebijakan yang tersedia, mencatatkan nama/inisial pemberi persetujuan, tanggal efektif, dan nomor referensi persetujuan pada tabel sign-off di Bagian 10.

---

## 2. Domain A: Produksi, Potong, Jahit & Bahan (D02, D03)

### Keputusan D02: Status & Alur Otorisasi Planning Produksi
- **Temuan Bukti:** Audit form `/production/planning` dan riwayat pengerjaan menunjukkan pembuatan rencana potong menetapkan target pcs dan PIC penjahit.
- **Masalah Kebijakan:** Apa yang terjadi jika target produksi diubah setelah kain sebagian sudah dipotong dan menjadi WIP di meja jahit?
- **Pola Teramati (SUPPORTED_PATTERN):** Target awal tidak boleh ditimpa langsung (`in-place update`) jika sudah ada run cutting yang dimulai. Perubahan target harus dicatat sebagai revisi rencana dengan alasan dan otorisasi supervisor produksi.
- **Pilihan Kebijakan bagi Pemilik:**
  - *Opsi 1 (Direkomendasikan):* Kunci target asli setelah cutting dimulai. Perubahan kuantitas dilakukan via pembuatan Rencana Tambahan (Split Run) atau revisi terkontrol dengan log perubahan.
  - *Opsi 2:* Izinkan pembatalan parsial sisa target yang belum masuk cutting, tetapi kunci kuantitas yang sudah berstatus bundle di penjahit.
- **Rekomendasi Agent:** Pilih Opsi 1 untuk menjaga integritas saldo WIP dan pelaporan yield bahan.

### Keputusan D03: Formula Pemotongan Bahan (Cutting) & Konversi Satuan
- **Temuan Bukti:** Form `/production/cutting/create` memuat parameter: rol, berat kain (kg), lembar gelar, setelan per lembar, dan berat produk (gram).
- **Rumus Usulan:**
  $$\text{Target Pcs} = \text{Lembar} \times \text{Setelan per Lembar}$$
  $$\text{Toleransi Susut Bahan} = \frac{\text{Berat Aktual (kg)} \times 1.000 - (\text{Output Pcs} \times \text{Gramatur Produk})}{\text{Berat Aktual (kg)} \times 1.000} \times 100\%$$
- **Masalah Kebijakan:** Apakah sisa kain perca/ujung rol (waste) diakui sebagai beban biaya langsung (scrap expense) atau dikembalikan ke gudang sebagai kain perca kiloan?
- **Pilihan Kebijakan bagi Pemilik:**
  - *Opsi 1 (Direkomendasikan):* Catat berat sisa potongan secara terpisah. Sisa layak pakai dikembalikan ke stok perca; sisa rusak masuk biaya limbah produksi (scrap).
  - *Opsi 2:* Seluruh selisih berat rol dikurangkan langsung sebagai biaya bahan produksi tanpa pencatatan stok perca.

---

## 3. Domain B: Upah Pekerjaan Borongan, Payroll & Kasbon (D04, D05, D06, D07, D08)

### Keputusan D04: Basis Tarif Borongan & Pembulatan Pecahan Lusin
- **Temuan Bukti:** Satuan borongan legacy menggunakan **Lusin** (1 lusin = 12 pcs). Bukti pecahan: 11 pcs = 0.9167 lusin; 13 pcs = 1.0833 lusin.
- **Masalah Kebijakan:** Pembulatan upah dilakukan di setiap baris pekerjaan (line item) atau dijumlahkan dulu baru dibulatkan di total slip?
- **Analisis Selisih:** Pada tarif Rp 25.000/lusin untuk 11 pcs, pembulatan 4 desimal per baris menghasilkan Rp 22.918, sedangkan perkalian exact pecahan menghasilkan Rp 22.917 (selisih Rp 1).
- **Pilihan Kebijakan bagi Pemilik:**
  - *Opsi 1 (Direkomendasikan):* Simpan tarif per lusin, hitung upah per baris pengerjaan menggunakan `ROUND_HALF_UP` ke satuan rupiah penuh (`scale=0`), kemudian jumlahkan ke gross pay. Ini menjamin kecocokan persis antara apa yang dilihat pekerja di slip fisik dengan total akumulasi.
  - *Opsi 2:* Akumulasikan pecahan lusin presisi tinggi hingga subtotal periode, baru dibulatkan di akhir.

### Keputusan D05: Kelayakan Bayar Upah, Reject & Rework
- **Temuan Bukti:** Penjahit mencatat realisasi pengerjaan SPK. Di lapangan sering terjadi barang reject (cacat jahitan) atau rework (perbaikan).
- **Masalah Kebijakan:** Apakah jahitan cacat/reject dibayar upahnya? Apakah pekerjaan perbaikan (rework) mendapatkan upah tambahan?
- **Pilihan Kebijakan bagi Pemilik:**
  - *Opsi 1 (Direkomendasikan):* Hanya kuantitas **Payable Pcs** (LOLOS QC) yang dibayar upahnya. Pekerjaan rework akibat kelalaian operator yang sama tidak mendapatkan upah tambahan. Rework yang ditugaskan ke operator lain dibayar sesuai tarif job rework khusus.
  - *Opsi 2:* Semua barang yang dikerjakan dibayar, denda cacat dipotongkan via komponen potongan gaji terpisah.

### Keputusan D06: Komponen Slip Gaji & Perlindungan Upah
- **Temuan Bukti:** Komponen slip legacy: Gaji Kotor (Gross Borongan), Tunjangan Transport, Premi Hadir, Bonus Produksi, Potongan, Cashbon Payment, dan Net Pay.
- **Masalah Kebijakan:** Bagaimana aturan pemotongan jika pekerja tidak masuk atau memiliki pinjaman kasbon besar sehingga Net Pay berpotensi negatif?
- **Pilihan Kebijakan bagi Pemilik:**
  - *Opsi 1 (Direkomendasikan):* **Batas Bawah Nol.** Gaji bersih (Net Pay) tidak boleh negatif. Jika cicilan kasbon melebihi sisa gaji, sistem otomatis memotong maksimum hingga Net Pay = Rp 0. Sisa cicilan yang belum terpotong dialihkan ke periode penggajian berikutnya.
  - *Opsi 2:* Gaji bersih diperbolehkan bernilai negatif dan menjadi piutang berjalan karyawan.

### Keputusan D07: Periode Cutoff Penggajian & Penanganan Pekerjaan Terlambat
- **Temuan Bukti:** Siklus payroll mingguan/dua mingguan.
- **Masalah Kebijakan:** SPK jahit yang diserahkan melewati tanggal batas cutoff periode berjalan masuk ke mana?
- **Pilihan Kebijakan bagi Pemilik:**
  - *Opsi 1 (Direkomendasikan):* Pekerjaan yang diajukan/diapprove setelah jam cutoff otomatis dimasukkan ke slip periode berikutnya (tidak ada pembukaan mundur periode yang sudah tutup).
  - *Opsi 2:* Membuka kembali (reopen) slip periode berjalan untuk memasukkan susulan.

### Keputusan D08: Aturan Pinjaman Kasbon & Pelunasan Mandiri
- **Temuan Bukti:** Form `/payroll/cash-receipt` mencatat pencairan pinjaman dan pemotongan otomatis via payroll.
- **Masalah Kebijakan:** Apakah karyawan diperbolehkan melunasi kasbon langsung secara tunai/transfer di luar payroll?
- **Pilihan Kebijakan bagi Pemilik:**
  - *Opsi 1 (Direkomendasikan):* Boleh. Pelunasan manual dicatat via kuitansi penerimaan kasbon kas masuk (`direct cash receipt`), yang seketika mengurangi saldo kartu pinjaman karyawan tanpa menunggu siklus payroll berikutnya.
  - *Opsi 2:* Pelunasan hanya boleh terjadi melalui pemotongan slip gaji.

---

## 4. Domain C: Master Data, Satuan & Struktur Usaha (D01)

### Keputusan D01: Standarisasi Taksonomi & Penghapusan Kolom Usang
- **Temuan Bukti:** Master produk memiliki kategori, subkategori, tipe, seri, warna, ukuran, dan UOM. Bahan memiliki 3 tingkat kategori.
- **Rekomendasi Pembersihan Kolom:**
  - Kolom legacy yang diusulkan dihapus (`RETIRE_PROPOSED`): Field catatan bebas yang tidak terpakai, duplikasi nama vendor di level SKU.
  - Seluruh variasi warna dan ukuran dijadikan master terkelola, bukan teks bebas, untuk mencegah typo barcode.
- **Pilihan Kebijakan bagi Pemilik:** Menyetujui daftar penghapusan kolom di `docs/f01-field-map.csv`.

---

## 5. Domain D: Penjualan, POS, Diskon & Pembayaran (D09, D10, D11)

### Keputusan D09: Pengelolaan Template Gerai Kasir (POS Template)
- **Temuan Bukti:** Menu `/sales/pos-template` mengaitkan unit usaha toko ritel dengan gudang sumber barang default.
- **Rekomendasi:** Pertahankan konsep POS Template di Beeloft One untuk membatasi kasir toko hanya memotong stok dari gudang toko fisik mereka sendiri, bukan gudang utama pabrik.

### Keputusan D10: Hierarki Diskon & Pembulatan Nilai Penjualan
- **Temuan Bukti:** Kasir mendukung diskon per item (persen) dan diskon total belanja (nominal rupiah).
- **Rekomendasi:** Diskon per baris dihitung lebih dahulu, kemudian diskon nota dialokasikan secara proporsional ke baris barang untuk keperluan pencatatan akuntansi dan margin penjualan.

### Keputusan D11: Penanganan Kembalian, Selisih Bayar & Retur Kasir
- **Temuan Bukti:** Pembayaran tunai menghitung uang kembalian. Pembayaran non-tunai (EDC/QRIS) harus tepat sesuai total belanja.
- **Rekomendasi:** Retur barang di kasir POS wajib mereferensikan nomor struk asli. Barang retur masuk status `INSPECTED_RETURN` di gudang toko, bukan langsung menjadi stok siap jual sebelum diperiksa kelayakannya.

---

## 6. Domain E: Pembelian, Hutang Supplier & AP Settlement (D12)

### Keputusan D12: Aturan Pencatatan Tagihan & Pelunasan Faktur (AP Settlement)
- **Temuan Bukti:** Menu `/orders/ap-settlement` mencatat pembayaran faktur supplier bahan kain/aksesoris.
- **Masalah Kebijakan:** Bolehkah AP Settlement dibuat untuk pengeluaran operasional umum yang tidak memiliki Purchase Order (Non-PO)?
- **Pilihan Kebijakan bagi Pemilik:**
  - *Opsi 1 (Direkomendasikan):* Bedakan jelas antara **AP Pembelian Bahan (With PO)** yang wajib mencocokkan Surat Jalan/Penerimaan Barang (3-Way Matching: PO - Receipt - Invoice) dengan **Pengeluaran Biaya Operasional (Non-PO)** yang memerlukan otorisasi manajer keuangan.
  - *Opsi 2:* Seluruh pengeluaran wajib dibuatkan PO formal terlebih dahulu.

---

## 7. Domain F: Valuasi Persediaan, COGS & Akuntansi (D13, D14, D15)

### Keputusan D13: Metode Valuasi Persediaan Bahan & Produk Jadi
- **Temuan Bukti:** Legacy mencatat harga modal statis (Capital) pada master barang.
- **Masalah Kebijakan:** Bagaimana Beeloft One menilai persediaan saat harga bahan kain naik-turun antar batch kedatangan?
- **Pilihan Kebijakan bagi Pemilik:**
  - *Opsi 1 (Direkomendasikan):* **Metode Rata-Rata Bergerak (Moving Average).** Setiap ada penerimaan PO bahan dengan harga berbeda, harga pokok rata-rata per satuan diperbarui secara otomatis. Sederhana, akurat, dan sesuai standar UMKM garmen Indonesia.
  - *Opsi 2:* Metode FIFO (First-In, First-Out) berbasis lot penerimaan.
  - *Opsi 3:* Standard Costing (biaya standar tetap yang dievaluasi tiap semester).

### Keputusan D14 & D15: Batasan Akuntansi Buku Besar & Periode Fiskal
- **Temuan Bukti:** Menu akuntansi native (COA, Jurnal Umum, Neraca) tidak tampak di menu legacy yang diaudit (pencatatan eksternal menggunakan spreadsheet/Mekari).
- **Rekomendasi:** Beeloft One menerapkan Buku Besar subledger terpadu dengan penutupan periode bulanan terkunci. Transaksi yang bertanggal pada bulan yang sudah ditutup ditolak otomatis oleh sistem.

---

## 8. Domain G: Tata Kelola Akses, Integrasi & Operasional (D16, D17, D18, D19, D20)

### Keputusan D16: Standardisasi Judul Laporan (Title Reports)
- **Rekomendasi:** Pertahankan tabel konfigurasi judul laporan cetak (`/support/title-report`) untuk memuat Kop Surat resmi perusahaan, logo, alamat, dan nomor kontak pada seluruh cetakan PDF (Slip Gaji, Invoice POS, Surat Jalan Cutting, dan PO).

### Keputusan D17: Pemisahan Tugas (Segregation of Duties)
- **Rekomendasi Mutlak:** Pemohon pengeluaran kas atau pembuat slip gaji tidak boleh menyetujui pengajuannya sendiri (Anti Self-Approval).

### Keputusan D18: Strategi Integrasi Kanal Penjualan Eksternal
- **Rekomendasi:** Pisahkan kanal penjualan langsung (POS Toko) yang bersifat instan dengan sinkronisasi marketplace (Shopee/TikTok/Tokopedia) yang beroperasi melalui batch ingestion berkala dan karantina order jika ada SKU yang belum terpetakan.

### Keputusan D19: Strategi Migrasi Data Legacy ke Beeloft One
- **Pilihan Kebijakan bagi Pemilik:**
  - *Opsi 1 (Direkomendasikan):* **Cutoff Saldo Awal (Opening Balance Migration).** Migrasikan master data (produk, bahan, karyawan, supplier), saldo akhir kasbon karyawan, dan saldo fisik persediaan per tanggal cutoff. Transaksi historis lama disimpan sebagai arsip baca di database terpisah. Ini mencegah duplikasi data transaksi dan beban rekonsiliasi yang rumit.
  - *Opsi 2:* Replay seluruh histori transaksi tahun berjalan dari awal tahun buku.

### Keputusan D20: Target Pemulihan Operasional (RPO / RTO)
- **Rekomendasi:** Cadangan data (backup) otomatis setiap 24 jam dengan retensi 30 hari. Target pemulihan (RTO) maksimum 2 jam jika terjadi gangguan server.

---

## 9. Tindak Lanjut Khusus Anomali Stok Negatif (#108)

- **Fakta:** Teramati 1 baris stok minus dengan SKU/identitas kosong pada tabel `/stocks/stck-prdct` legacy.
- **Kebijakan Migrasi:** Baris data yang tidak memiliki SKU sah atau bersaldo negatif dilarang diimpor ke buku besar Beeloft One. Seluruh data anomali harus masuk ke tabel karantina (`quarantine_exceptions`) untuk diperiksa fisik sebelum diakui saldonya.

---

## 10. Formulir Persetujuan Resmi Pemilik Bisnis (Sign-Off Gate)

| Peran Pemilik Bisnis | Nama / Identitas | Tanggal Persetujuan | Status | Referensi Dokumen / Memo |
|---|---|---|---|---|
| Pemilik Bisnis / Direksi | [Menunggu Penetapan] | [YYYY-MM-DD] | PENDING | [No. Memo / Tanda Tangan] |
| Kepala Produksi & QC | [Menunggu Penetapan] | [YYYY-MM-DD] | PENDING | [No. Memo / Tanda Tangan] |
| Kepala HR & Payroll | [Menunggu Penetapan] | [YYYY-MM-DD] | PENDING | [No. Memo / Tanda Tangan] |
| Kepala Keuangan & Akuntansi | [Menunggu Penetapan] | [YYYY-MM-DD] | PENDING | [No. Memo / Tanda Tangan] |
| Koordinator Teknis (A0) | Agent Koordinator | 2026-09-27 | REVIEW_READY | F01-EXEC-20260927-1 |
