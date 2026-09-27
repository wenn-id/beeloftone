# Panduan Demo Beeloft One — Presentasi ke Bos (Senin, 28 Sep 2026 malam)

> **Semua data demo adalah sintetis** dan terpisah dari backoffice produksi.
> Pekerjaan audit PR #109 tidak tersentuh; demo dikerjakan di branch
> `demo/presentasi-bos-20260928`.

## 1. Menjalankan demo

```bash
cd beeloftone
git checkout demo/presentasi-bos-20260928
python -m venv .venv && .venv/bin/pip install -r requirements.txt   # sekali saja

# Buat database demo dari nol (cetak 3 API key demo — simpan yang admin)
.venv/bin/python -m beeloft --db data/demo.sqlite3 demo

# Jalankan server (mode demo — endpoint /demo & /api/demo/* hanya aktif di sini)
BEELOFT_DEMO=1 .venv/bin/python -m beeloft --db data/demo.sqlite3 serve --port 8000
```

Buka **http://127.0.0.1:8000/demo**, tempel API key **Admin Demo**, klik **Muat data demo**.

## 2. Reset ke kondisi awal

```bash
.venv/bin/python -m beeloft --db data/demo.sqlite3 demo --fresh
```

Menghapus database demo lalu membangun ulang skenario dari nol (~2 detik).
API key ikut dibuat ulang — pakai key admin yang baru di halaman `/demo`.

## 3. Skenario & angka kunci (semua sudah konsisten)

| Alur | Angka |
|---|---|
| Produksi | Order `DEMO-PROD-001`: 1.200 pcs → cutting 1.200 → jahit 1.200 → finishing 1.200 → QC 1.200 → gudang **1.180** (20 reject QC) |
| Payroll | Sari (obras) 480 pcs = 40 lusin × Rp1.800 = **Rp72.000**; Budi (jahit) 360 pcs = 30 lusin × Rp2.500 = **Rp75.000**; Dewi (jahit) 360 pcs = **Rp75.000**. Total bruto **Rp222.000** |
| Kasbon | Budi kasbon **Rp30.000** → netto Budi **Rp45.000**; total netto **Rp192.000** |
| Penjualan | Contoh live: 50 pcs × Rp85.000 = **Rp4.250.000** (Transfer simulasi) → stok 1.180 → 1.130 |

Aturan sementara (bukan aturan produksi): upah = (pcs ÷ 12) × tarif/lusin;
penjualan demo dicatat sebagai adjustment stok keluar + transaksi demo.

## 4. Urutan presentasi ±7 menit

1. **Produksi (2 mnt)** — Funnel di `/demo`: 1.200 rencana → 1.180 barang jadi;
   20 pcs reject QC tercatat. Rantai asli: order → cutting run → bundle →
   sewing job → finishing → QC → penerimaan barang jadi.
2. **Payroll (2,5 mnt)** — Hasil jahitan per pekerja → bruto Rp222.000.
   Buka slip Budi: kasbon Rp30.000 → netto Rp45.000.
   *Live:* catat pembayaran kasbon Rp10.000 → netto jadi Rp55.000.
3. **Penjualan (2 mnt)** — *Live:* jual 50 pcs @ Rp85.000 (Transfer simulasi) →
   stok & omzet langsung ter-update; ringkasan tampil.
4. **Penutup (0,5 mnt)** — Asumsi sementara + rencana: General Ledger native
   tetap arah produk, belum syarat demo ini.

## 5. Yang bisa ditunjukkan vs yang belum

**Bisa (sudah berjalan):** rantai produksi penuh per tahap, perhitungan upah
borongan dari hasil pekerjaan nyata, slip + potongan kasbon live, transaksi
penjualan live dengan dampak stok, ringkasan omzet, seluruh halaman `/demo`
tanpa error.

**Rencana (belum dibangun, dinyatakan eksplisit di halaman demo):**
General Ledger akuntansi native, posting jurnal otomatis, COA, tutup periode.
Aplikasi utama (`/`) tetap memuat data demo yang sama bila bos ingin drill-down.

## 6. Batasan demo

- Database demo (`data/demo.sqlite3`) terpisah; tidak menyentuh database produksi.
- Skema produksi tidak berubah (tetap schema 55); tabel `demo_*` dibuat terpisah.
- Jangan pakai API key demo untuk hal lain; key hanya tampil saat pembuatan.
