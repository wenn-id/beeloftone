# Verifikasi penerimaan barang jadi — v0.23

Tanggal: 11 September 2026. Base `90545a2`; branch `feature/warehouse` pada worktree lokal.
Pengujian memakai database sementara dan tidak menyentuh data bisnis.

## Cakupan backend

Lima acceptance test baru memeriksa penerimaan parsial, pembagian sellable/hold, scan SKU,
lineage produksi, inventori per SKU, WIP yang tetap, role, koreksi utuh, blok koreksi final QC,
tanggal dan over-allocation, transaksi bersamaan, rollback, pagination, backup, direct-write guard,
ledger immutable, serta migrasi schema 17 → 18. Seluruh regression suite berisi **137 tests** dan
lulus dalam **95,098 detik**.

## Browser dan client

Browser QA menerima 15 dari 20 pcs accepted: 12 sellable dan 3 hold di lokasi gudang yang dicatat.
Respons create sengaja diputus setelah server menyimpan; reload dan retry dengan key yang sama
tetap menghasilkan satu catatan. Viewer hanya membaca. Koreksi final QC ditolak selama penerimaan
aktif, lalu koreksi penerimaan mengosongkan inventori tanpa mengubah saldo WIP gudang 20 pcs.
Daftar kosong, kegagalan GET, retry, Escape, escaping teks, viewport 390 × 844, dan skala teks 200%
lulus tanpa error JavaScript.

`node --check beeloft/static/app.mjs`, pemeriksaan file browser, dan `node tests/test_client.mjs`
lulus. Screenshot `beeloft-finished-goods-mobile.png` diperiksa pada ukuran asli; pembagian stok,
lokasi, SKU hasil scan, lineage, catatan, dan aksi terbaca tanpa overflow horizontal.

## Batas

Inventori merupakan ringkasan ledger internal Beeloft. Belum ada sinkronisasi Jubelio/WMS,
master barcode, label, transfer lokasi, pelepasan hold, reservasi marketplace, pick/pack/ship,
retur, stock opname, atau adjustment.
