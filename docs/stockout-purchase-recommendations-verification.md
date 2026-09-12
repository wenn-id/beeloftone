# Verifikasi stockout dan rekomendasi pembelian, v0.38

Tanggal: 13 September 2026. Base `a293e6c`; branch
`feature/stockout-purchase-recommendations` pada worktree lokal. Pengujian memakai database sementara
dan tidak menyentuh data bisnis.

## Cakupan backend

Empat acceptance test baru memeriksa forecast, stok sellable/reservasi, days of cover, tanggal
stockout, reorder point, target stok, produksi berjalan, horizon berdasarkan due date, batch multiple,
BOM terbaru, kebutuhan bahan produksi aktif, stok bahan, PR, sisa PO, PR di luar horizon, produk tanpa
riwayat, BOM yang hilang, pencarian, pagination, viewer, validasi parameter, backup, dan schema 30.

Contoh utama memakai rate demand 0,5143 pcs/hari, stok tersedia 4 pcs, dan produksi berjalan 80 pcs.
Hasilnya adalah coverage 7,78 hari, estimasi stockout 23 November 2026, reorder point 139 pcs, target
stok 232 pcs, serta rekomendasi produksi 156 pcs setelah pembulatan batch 12. BOM 1 meter per pcs
menghasilkan kebutuhan bahan 253,875 meter setelah kebutuhan produksi aktif ikut dihitung.

PR 50 meter menurunkan rekomendasi beli sebesar 50 meter. Setelah PR menjadi PO dan 10 meter
diterima, stok 10 meter ditambah sisa PO 40 meter mempertahankan cakupan yang sama tanpa menghitung
pipeline dua kali. PR bertanggal di luar horizon tidak mengurangi rekomendasi.

Seluruh regression suite backend berisi **209 tests** dan lulus dalam **258,591 detik**.

## Browser dan client

Edge/Playwright menjalankan seluruh browser regression suite. QA memverifikasi risiko stockout SKU
`COST-UI`, stok tersedia 5 pcs, produksi berjalan 5 pcs, rate 0,5000 pcs/hari, stockout 23 Desember
2026, rekomendasi produksi baru 20 pcs, kebutuhan produksi berjalan 5 meter, dan rekomendasi beli
total 25 meter. Error retry, viewer, escaping, mobile, skala teks 200%, dan ketiadaan error JavaScript
semuanya lulus.

## Pemeriksaan rilis

Kontrak `docs/openapi.json` memuat versi 0.38.0 dan endpoint
`GET /api/replenishment-recommendations`. Schema tetap versi 30 karena seluruh hasil dihitung dari
ledger yang sudah ada.

## Batas

Laporan belum membuat order produksi atau PR otomatis. Kapasitas, jadwal selesai rinci, supplier,
harga, MOQ bahan, kalender kerja, promosi, musiman, dan data eksternal marketplace belum dihitung.
Historis demand mengikuti `as_of`; stok dan pipeline memakai posisi aktif saat laporan dimuat.
