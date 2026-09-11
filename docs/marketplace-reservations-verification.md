# Verifikasi reservasi marketplace — v0.25

Tanggal: 11 September 2026. Base `e472e95`; branch `feature/marketplace-reservations` pada worktree lokal.
Pengujian memakai database sementara dan tidak menyentuh data bisnis.

## Cakupan backend

Lima acceptance test baru memeriksa reservasi parsial, available/reserved, marketplace dan order
eksternal, lineage, WIP serta stok fisik yang tetap, role, pelepasan utuh, blok transfer/koreksi,
validasi tanggal/lokasi/saldo, transaksi bersamaan, rollback, pagination, backup, direct-write
guard, ledger immutable, serta migrasi schema 19 → 20. Seluruh regression suite berisi
**147 tests** dan lulus dalam **106,922 detik**.

## Browser dan client

Browser QA mereservasi 5 dari 12 pcs sellable sehingga tersedia 7 dan reserved 5. Respons create
sengaja diputus setelah server menyimpan; reload dan retry dengan key yang sama tetap menghasilkan
satu catatan. Transfer 8 pcs dan koreksi penerimaan ditolak selama reservasi aktif. Viewer hanya
membaca; operator melepas reservasi dan saldo kembali menjadi available 12, reserved 0 tanpa
mengubah stok fisik atau WIP gudang. Daftar kosong, kegagalan GET, escaping teks, viewport
390 × 844, dan skala teks 200% lulus tanpa error JavaScript.

`node --check` untuk aplikasi dan browser test serta `node tests/test_client.mjs` lulus. Screenshot
`beeloft-marketplace-reservation-mobile.png` diperiksa pada ukuran asli; marketplace, order
eksternal, jumlah, lokasi, tanggal, lineage, alasan, aktor, dan aksi terbaca tanpa overflow.

## Batas

Tidak ada sinkronisasi API marketplace atau Jubelio/WMS. Partial release, impor order, pick, pack,
ship, retur pelanggan, stock opname, dan adjustment stok belum tersedia.
