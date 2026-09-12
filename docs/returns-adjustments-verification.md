# Verifikasi retur pelanggan dan adjustment barang jadi, v0.29

Tanggal: 12 September 2026. Base `31f528e`; branch `feature/marketplace-returns-adjustments` pada
worktree lokal. Pengujian memakai database sementara dan tidak menyentuh data bisnis.

## Cakupan backend

Enam acceptance test baru memeriksa retur parsial dan alasan terstruktur, lokasi/status hasil
inspeksi, adjustment bertanda positif/negatif, lineage receipt–shipment–order, WIP yang tetap,
stok per receipt, reserved-stock guard, role, koreksi, transaksi bersamaan, rollback, pagination,
backup, ledger immutable, direct-write guard, serta migrasi schema 23 → 24. Seluruh regression suite
berisi **168 tests** dan lulus dalam **164,202 detik**.

## Browser dan client

Browser QA mengembalikan 1 dari 2 pcs shipment ke status hold, lalu mencatat adjustment +3 sellable
pada lokasi stock opname. Total gudang berubah mengikuti dua ledger tersebut. Koreksi shipment
ditolak selama retur aktif; koreksi adjustment ditolak selama stok tambahannya terikat reservasi.
Setelah dependensi dilepaskan, admin mengoreksi kedua catatan dan saldo kembali tepat ke posisi awal.

Respons create retur sengaja diputus setelah server menyimpan; reload dan retry dengan key yang sama
tetap menghasilkan satu catatan. Viewer hanya membaca, operator mencatat, dan admin mengoreksi.
Seluruh browser suite lulus melalui Edge/Playwright tanpa error JavaScript. Daftar kosong, kegagalan
GET, escaping teks, viewport 390 × 844, skala teks 200%, dan pemulihan request turut diperiksa.
`node --check` untuk aplikasi dan browser test serta `node tests/test_client.mjs` lulus. Screenshot
`beeloft-customer-return-mobile.png` dan `beeloft-adjustment-mobile.png` diperiksa pada ukuran asli;
status, jumlah, lokasi, alasan, lineage, aktor, serta tombol terbaca tanpa overflow.

## Batas

Belum ada refund, exchange shipment, return label, carrier event, foto, approval, jurnal keuangan,
anomaly score, atau sinkronisasi marketplace/Jubelio. Adjustment adalah ledger per receipt dan bukan
rekonsiliasi otomatis dengan sistem eksternal.
