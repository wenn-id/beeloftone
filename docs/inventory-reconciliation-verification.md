# Verifikasi stock opname dan rekonsiliasi barang jadi, v0.30

Tanggal: 12 September 2026. Base `aabd255`; branch `feature/inventory-reconciliation` pada
worktree lokal. Pengujian memakai database sementara dan tidak menyentuh data bisnis.

## Cakupan backend

Lima acceptance test baru memeriksa snapshot saldo sistem dan selisih, stock opname tanpa selisih,
lineage penerimaan–Final QC–batch–order, adjustment turunan, retry idempotent, role, scan SKU,
tanggal/status invalid, reserved-stock guard, koreksi, backup, ledger immutable, direct-write guard,
serta migrasi schema 24 → 25. Seluruh regression suite berisi **173 tests** dan lulus dalam
**85,110 detik**.

## Browser dan client

Browser QA menghitung fisik 7 pcs terhadap saldo sistem 8 pcs pada lokasi sellable. Sistem
menyimpan selisih -1 dan membuat adjustment terhubung. Koreksi langsung adjustment ditolak;
admin mengoreksi stock opname dan saldo kembali tepat ke 8 pcs dengan riwayat asli tetap ada.

Respons create sengaja diputus setelah server menyimpan. Reload dan retry dengan key yang sama
tetap menghasilkan satu catatan. Viewer hanya membaca, operator mencatat, dan admin mengoreksi.
Seluruh browser suite lulus melalui Edge/Playwright tanpa error JavaScript. Daftar kosong,
kegagalan GET, escaping teks, viewport 390 × 844, skala teks 200%, dan pemulihan request turut
diperiksa. `node --check` untuk aplikasi dan browser test, `node tests/test_client.mjs`, serta
`pip check` lulus. Kontrak `docs/openapi.json` diperbarui ke v0.30.0.

## Batas

Belum ada sesi freeze gudang, tim penghitung, blind double count, impor scanner, approval,
valuasi persediaan, anomaly score, atau rekonsiliasi otomatis dengan Jubelio/WMS. Satu catatan
menghitung satu penerimaan, lokasi, dan status stok.
