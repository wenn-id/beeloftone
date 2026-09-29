# Desain Arsitektur: Mode Jubelio Demo Beeloft One

**Status:** Disetujui  
**Tanggal:** 2026-09-28  
**Branch:** `feat/jubelio-demo-connector`  
**Base:** `origin/main` (commit `72e408d2b9505c30234e1a09de70fb7d7c54fca4`)

---

## 1. Latar Belakang & Tujuan

Sambil menunggu kredensial dan akses live API Jubelio, Beeloft One harus dapat didemonstrasikan secara menyeluruh seolah integrasi commerce Jubelio sudah aktif berjalan. Aliran sinkronisasi harus nyata: data masuk ke database, Command Center terisi, analitik marketplace menyajikan performa kanal dan produk terlaris, rekonsiliasi stok berfungsi, detail order dan retur dapat ditelusuri, dan sinkronisasi skenario berikutnya memperbarui data tanpa restart server.

Mode demo ini adalah **simulasi fungsional terintegrasi**, bukan hardcoded mockup atau sekadar badge statis.

---

## 2. Prinsip & Batasan Utama

1. **Jalur Ingestion Eksisting:**
   Simulasi hanya menghasilkan payload yang disuntikkan melalui kontrak snapshot internal yang sudah ada:
   - `/api/integrations/jubelio/order-snapshots` (`JubelioOrderSnapshotImport`)
   - `/api/integrations/jubelio/finished-goods-snapshots` (`JubelioStockSnapshotImport`)
   - `/api/integrations/jubelio/return-snapshots` (`JubelioReturnSnapshotImport`)
   - `/api/integrations/jubelio/listing-snapshots` (`JubelioListingSnapshotImport`)
   Tidak ada pembuatan tabel order/stok paralel atau dashboard paralel. Semua read model existing membaca tabel snapshot aktual.

2. **Kelengkapan Snapshot per Batch:**
   Karena read model Beeloft One membaca batch terbaru (`ORDER BY sequence DESC LIMIT 1`), setiap batch snapshot baru harus memuat keadaan **lengkap** untuk scope yang digantikannya (bukan hanya delta pesanan baru yang menyebabkan pesanan lama hilang dari tampilan).

3. **Pemisahan Sumber Data & Batasan Domain:**
   Snapshot Jubelio terisolasi dari buku besar produksi internal Beeloft One. Stok Jubelio tidak memutasi stok fisik internal secara langsung, dan pesanan marketplace tidak otomatis memicu transaksi produksi atau jurnal keuangan kecuali melalui layanan rekonsiliasi domain yang sah.

4. **Karantina & Pemetaan SKU:**
   Item snapshot yang tidak memiliki pemetaan aktif di `product_external_mapping_events` masuk karantina secara sah. Ketika admin memetakan SKU tersebut melalui Master SKU (`POST /api/products/{id}/external-mappings/jubelio`) dan melakukan sinkronisasi ulang, item tersebut diterima di batch baru. Record karantina historis tetap utuh (immutable).

5. **Proteksi Konkurensi Tingkat Database:**
   Pencegahan eksekusi ganda atau lompatan skenario ganda ditegakkan di level database melalui kunci transaksional (bukan hanya flag memori Python).

6. **Isolasi Database Demo:**
   Mode demo hanya dapat diaktifkan pada database yang ditandai sebagai database demo (misal `data/demo.sqlite3` atau tabel penanda `jubelio_demo_state`). Database non-demo akan menolak aktivasi secara tegas.

---

## 3. Komponen Sistem

### 3.1 `beeloft/jubelio_demo.py`
Modul inti penyedia simulasi:
- **`JubelioDemoDataset`**: Generator dataset deterministik pakaian anak:
  - 30 SKU produk anak (Luna, Milo, Kiko, Caca, Bimo) dengan variasi warna (Navy, Sage, Terracotta, Mustard, Dusty Pink) dan ukuran (S, M, L).
  - 28 SKU terpetakan ke external_id & external_sku Jubelio; 2 SKU sengaja unmapped untuk skenario karantina.
  - 120 baseline order dengan rentang 30 hari hingga tanggal acuan demo tetap (`2026-09-28T00:00:00Z`) di kanal Shopee, Tokopedia, dan TikTok Shop.
  - Snapshot stok barang jadi sellable & reserved per SKU.
  - Snapshot listing marketplace (aktif, nonaktif).
  - Snapshot retur (3-5 retur yang merujuk pesanan dan produk asal).
- **`JubelioScenarioRunner`**:
  - **Skenario 1 (Baseline)**: Menyuntikkan baseline lengkap 120 order, stok awal, listing, dan retur. Menghasilkan status sukses pada stock/listing dan attention/karantina pada order/stock yang memuat SKU unmapped.
  - **Skenario 2 (Pembaruan Konsisten)**: Memajukan waktu simulasi, menambah 25 order baru, mengubah status order pending menjadi processing/completed, memperbarui stok sellable mengikuti penjualan, dan menambah retur baru.
  - **Resync / Re-evaluasi Karantina**: Membentuk snapshot batch baru yang menyertakan data yang sudah dipetakan sehingga keluar dari karantina pada batch terbaru.
- **`JubelioDemoManager`**:
  - Mengelola tabel status `jubelio_demo_state`.
  - Mengatur database lock untuk konkurensi.
  - Mengorkestrasi pemanggilan method `Store.import_jubelio_*_snapshot` dengan Actor admin dan RequestKey deterministik.

### 3.2 Tabel Status Demo (`jubelio_demo_state`)
```sql
CREATE TABLE IF NOT EXISTS jubelio_demo_state (
    id TEXT PRIMARY KEY,
    is_demo INTEGER NOT NULL CHECK(is_demo IN (0,1)),
    current_scenario INTEGER NOT NULL CHECK(current_scenario >= 0),
    is_locked INTEGER NOT NULL CHECK(is_locked IN (0,1)),
    lock_expires_at TEXT NOT NULL DEFAULT '',
    last_synced_at TEXT NOT NULL DEFAULT '',
    last_status TEXT NOT NULL DEFAULT 'idle',
    last_error TEXT NOT NULL DEFAULT '',
    last_summary_json TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL
) STRICT;
```

### 3.3 Endpoint API Demo Internal
- `GET /api/integrations/jubelio/demo/status`: Menampilkan status demo, skenario aktif, status lock, dan ringkasan sinkronisasi terakhir. (Akses: Semua pengguna terautentikasi).
- `POST /api/integrations/jubelio/demo/activate`: Mengaktifkan mode demo pada database demo, membuat produk dan pemetaan SKU awal jika belum ada. (Akses: Admin).
- `POST /api/integrations/jubelio/demo/sync`: Menjalankan sinkronisasi manual untuk skenario saat ini. Idempoten terhadap retry. (Akses: Admin).
- `POST /api/integrations/jubelio/demo/next-scenario`: Menaikkan skenario ke tingkat berikutnya dan menjalankan sinkronisasi. Dilindungi database lock. (Akses: Admin).
- `POST /api/integrations/jubelio/demo/reset`: Mengembalikan skenario demo ke skenario 1 (hanya pada database demo). (Akses: Admin).

### 3.4 Antarmuka Pengguna (`beeloft/static/app.mjs`)
- Di halaman Integrasi (`#integrations-view`):
  - Badge ringkas pada sistem Jubelio: `Jubelio Demo · Simulasi`.
  - Panel Kontrol Demo:
    - Status skenario (misal: "Skenario 1: Baseline 120 Order" / "Skenario 2: Pembaruan Transaksi").
    - Indikator status (Idle, Menyinkronkan..., Selesai, Ada Karantina).
    - Tombol aksi: "Sinkronkan sekarang", "Jalankan skenario berikutnya", "Reset skenario".
    - Indikator hasil per scope (Orders, Finished Goods, Returns, Listings).
  - Notifikasi dan refresh otomatis: saat sinkronisasi selesai, kartu integrasi dan cache Command Center otomatis diperbarui.

---

## 4. Alur Demonstrasi 5 Menit

1. **Menit 1: Membuka Integrasi & Status Demo**
   - Buka menu *Integrasi*. Terlihat sistem *Jubelio* dengan badge `Jubelio Demo · Simulasi`.
   - Klik *Sinkronkan sekarang* (Skenario 1).
   - Sinkronisasi memproses 4 scope: Order (120), Stok (30 SKU), Listing (30), Retur (4).
   - Muncul perhatian karantina: 2 SKU belum dipetakan.

2. **Menit 2: Command Center & Performa Marketplace**
   - Buka *Command center*.
   - Performa marketplace langsung terisi grafik omzet, perbandingan kanal (Shopee, Tokopedia, TikTok Shop), dan produk terlaris.
   - Angka omzet dan unit cocok 100% dengan agregat order di detail penjualan.

3. **Menit 3: Rekonsiliasi Stok & Detail Transaksi**
   - Buka *Rekonsiliasi stok Jubelio*. Terlihat perbandingan stok Jubelio sellable vs stok internal Beeloft One.
   - Buka *Retur Jubelio* dan telusuri salah satu retur yang terhubung ke nomor order asal.

4. **Menit 4: Pemetaan SKU Karantina & Resync**
   - Buka *Master SKU*. Temukan SKU yang belum terpetakan (`DEMO-BIMO-PANTS-L`).
   - Petakan SKU ke identifier Jubelio.
   - Kembali ke *Integrasi*, klik *Sinkronkan sekarang*. Karantina terselesaikan, status integrasi menjadi sehat (*Succeeded*).

5. **Menit 5: Skenario Berikutnya (Next Scenario)**
   - Klik *Jalankan skenario berikutnya*.
   - 25 order baru masuk, status beberapa order sebelumnya berubah menjadi *completed*, stok berkurang secara konsisten.
   - Command Center dan Order summary merefleksikan perubahan secara instan tanpa restart.
