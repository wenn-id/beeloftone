# Panduan Mode Jubelio Demo (Beeloft One)

Dokumen ini menjelaskan cara mengaktifkan, menjalankan, dan mempresentasikan simulasi integrasi Jubelio di Beeloft One tanpa memerlukan kredensial vendor atau akses jaringan langsung ke Jubelio.

---

## 1. Perintah Aktivasi

### Opsi A: Quick Start Demo
Jalankan PowerShell di root direktori:
```powershell
.\start.ps1 -Demo
```
Script membuat database contoh baru bila belum ada, menyiapkan akun demo, menandai database (`is_demo = 1`), lalu menjalankan server di <http://127.0.0.1:8000/>. Script tidak mengaktifkan konektor atau menyinkronkan data otomatis.

### Opsi B: Menggunakan Perintah CLI
```powershell
python -m beeloft --db data/demo.sqlite3 demo
python -m beeloft --db data/demo.sqlite3 serve
```

### Aktivasi melalui Dashboard Web
1. Masuk sebagai **Admin Demo** menggunakan API key yang ditampilkan CLI saat database dibuat.
2. Buka menu **Integrasi**.
3. Pada panel **Jubelio Demo · Simulasi**, klik **Aktifkan demo**, lalu **Sinkronkan sekarang** untuk mengisi baseline.
4. Klik **Jalankan skenario berikutnya** untuk menerapkan pembaruan deterministik.

Jika perlu database presentasi baru, buat file database baru menggunakan CLI `demo` dengan path baru. Tidak tersedia web reset; snapshot immutable tetap tersimpan.
*Catatan Keamanan:* Mode demo **hanya dapat diaktifkan pada database yang ditandai untuk demo**. Database operasional non-demo akan menolak aktivasi secara tegas dengan error HTTP 400.

---

## 2. Alur Demonstrasi 5 Menit

| Menit | Layar / Menu | Aksi & Narasi | Hasil yang Terlihat |
|---|---|---|---|
| **00:00 - 01:00** | **Integrasi** | Tunjukkan kartu *Jubelio* dengan badge `Jubelio Demo · Simulasi`. Klik **Sinkronkan sekarang**. | Status proses berjalan aman. Muncul catatan: 112 pesanan diterima, 8 dikarantina karena 2 SKU belum dipetakan. |
| **01:00 - 02:00** | **Command center** | Buka menu *Command center*. | Bagian *Performa marketplace* langsung menyajikan omzet, breakdown kanal (Shopee, Tokopedia, TikTok Shop), dan produk terlaris. Angka omzet dan unit konsisten dengan transaksi. |
| **02:00 - 03:00** | **Integrasi** (Detail) | Buka tombol dialog: <br>1. *Order & penjualan Jubelio* (tunjukkan daftar order dan filter). <br>2. *Rekonsiliasi stok Jubelio* (tunjukkan perbandingan stok Jubelio sellable vs stok internal). | Data transaksi lengkap dari detail hingga agregat; retur terhubung ke pesanan asal. |
| **03:00 - 04:00** | **Master SKU** & Resync | 1. Buka *Master SKU*, temukan SKU unmapped (`DEMO-BIMO-PANTS-L`). <br>2. Klik *Petakan*, isi identifier Jubelio. <br>3. Kembali ke *Integrasi*, klik *Sinkronkan sekarang*. | Karantina terselesaikan! Batch baru dievaluasi ulang, status sinkronisasi menjadi *Succeeded* tanpa merusak record historis. |
| **04:00 - 05:00** | **Skenario Berikutnya** | Klik tombol **Jalankan skenario berikutnya**. | Skenario 2 memproses 25 pesanan baru, status pesanan lama bertransisi (*pending* -> *completed*), stok berkurang mengikuti penjualan, tanpa perlu me-restart aplikasi. |

---

## 3. Pencegahan Kesalahan & Batasan Sistem

- **Idempotensi & Pencegahan Duplikasi:** Mengklik tombol sinkronisasi berkali-kali tidak akan menggandakan pesanan atau stok. Idempotency-Key diikat pada request.
- **Kunci Konkurensi Database:** Kunci transaksional tingkat database mencegah dua proses atau request simultan memajukan skenario secara ganda.
- **Isolasi Domain:** Snapshot Jubelio bersifat *inbound snapshot*. Transaksi pesanan marketplace tidak otomatis memotong stok fisik gudang internal atau membuat jurnal keuangan tanpa rekonsiliasi formal.
- **Karantina Immutable:** Data karantina lama tetap tersimpan sebagai bukti audit dan tidak pernah dihapus atau diubah di tempat. Batch baru akan mencatat status terpetakan.

---

## 4. Rencana Transisi ke API Jubelio Asli

Ketika kredensial resmi API Jubelio telah tersedia:
1. **Adapter Vendor Baru:** Buat adapter live di `beeloft/integrations/jubelio_client.py` yang menangani autentikasi token Jubelio dan pagination API vendor.
2. **Normalizer:** Petakan payload respon resmi Jubelio ke kontrak internal Beeloft One yang sama persis (`JubelioOrderSnapshotImport`, `JubelioStockSnapshotImport`, dll.).
3. **Penyimpanan Snapshot:** Seluruh endpoint dan penyimpanan database snapshot existing (`/api/integrations/jubelio/*-snapshots`) tetap dipakai apa adanya tanpa perubahan skema.
4. **Pemisahan Mode:** Worker live akan mengirim snapshot ke endpoint ingestion internal, sementara mode demo tetap tersedia sebagai lingkungan pengujian sandbox/presentasi offline.
