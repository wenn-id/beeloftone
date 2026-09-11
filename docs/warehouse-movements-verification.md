# Verifikasi transfer gudang dan keputusan hold — v0.24

Tanggal: 11 September 2026. Base `a234f2e`; branch `feature/warehouse-movements` pada worktree lokal.
Pengujian memakai database sementara dan tidak menyentuh data bisnis.

## Cakupan backend

Lima acceptance test baru memeriksa transfer lokasi tanpa mengubah status, pelepasan hold menjadi
sellable, pemisahan damaged, inventori per lokasi dan per SKU, lineage ke penerimaan/Final QC,
WIP yang tetap, role, koreksi berurutan, blok koreksi penerimaan, validasi tanggal/status/saldo,
transaksi bersamaan, rollback, pagination, backup, direct-write guard, ledger immutable, serta
migrasi schema 18 → 19. Seluruh regression suite berisi **142 tests** dan lulus dalam
**98,985 detik**.

## Browser dan client

Browser QA memindahkan 5 pcs sellable antar lokasi, melepas 3 pcs hold menjadi sellable, dan
memisahkan 2 pcs hold sebagai damaged. Respons transfer sengaja diputus setelah server menyimpan;
reload dan retry dengan key yang sama tetap menghasilkan satu catatan. Viewer hanya membaca.
Admin mengoreksi pergerakan dan saldo kembali menjadi 12 sellable, 8 hold, 0 damaged, sementara
WIP gudang tetap 20 pcs. Daftar kosong, kegagalan GET, retry, escaping teks, viewport 390 × 844,
dan skala teks 200% lulus tanpa error JavaScript.

`node --check` untuk aplikasi dan browser test serta `node tests/test_client.mjs` lulus. Screenshot
`beeloft-warehouse-movement-mobile.png` diperiksa pada ukuran asli; rute lokasi/status, jumlah,
tanggal, lineage, alasan, aktor, dan aksi terbaca tanpa overflow horizontal.

## Batas

Ledger belum mengalokasikan stok ke marketplace atau order penjualan. Belum ada sinkronisasi
Jubelio/WMS, master barcode, label/bin, pick/pack/ship, retur pelanggan, stock opname, atau
adjustment stok bebas.
