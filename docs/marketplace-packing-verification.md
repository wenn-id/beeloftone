# Verifikasi packing marketplace, v0.27

Tanggal: 12 September 2026. Base `8a6f670`; branch `feature/marketplace-packing` pada worktree lokal.
Pengujian memakai database sementara dan tidak menyentuh data bisnis.

## Cakupan backend

Lima acceptance test baru memeriksa pack parsial, perpindahan stok `picked` ke `packed`, lineage,
WIP dan total inventori yang tetap, role, koreksi, blok koreksi pick, validasi tanggal dan jumlah,
transaksi bersamaan, rollback, pagination, backup, direct-write guard, ledger immutable, serta
migrasi schema 21 → 22. Seluruh regression suite berisi **157 tests** dan lulus dalam **149,203
detik**.

## Browser dan client

Browser QA mem-pack 3 dari pick 4 pcs. Inventori menjadi 8 sellable, 1 picked, 3 packed, 2
reserved, 6 available, 8 hold, dan total tetap 20. Respons create sengaja diputus setelah server
menyimpan; reload dan retry dengan key yang sama tetap menghasilkan satu catatan. Koreksi pick
ditolak selama pack aktif. Viewer hanya membaca; admin mengoreksi pack dan inventori kembali
menjadi 4 picked serta 0 packed tanpa mengubah sellable, reserved, available, atau WIP.

Seluruh browser suite lulus melalui Edge/Playwright tanpa error JavaScript. Daftar kosong, kegagalan
GET, escaping teks, viewport 390 × 844, skala teks 200%, dan pemulihan request turut diperiksa.
`node --check` untuk aplikasi serta browser test dan `node tests/test_client.mjs` lulus. Screenshot
`beeloft-marketplace-pack-mobile.png` diperiksa pada ukuran asli; status, jumlah, marketplace, order
eksternal, staging, tanggal, lineage, alasan, aktor, dan tombol terbaca tanpa overflow.

## Batas

Belum ada pemindaian barcode, bahan kemasan, dimensi/berat, label, carrier, konsolidasi beberapa
pick, shipping, retur pelanggan, atau sinkronisasi API marketplace/Jubelio. Langkah berikutnya
menerima stok `packed` sebagai sumber konfirmasi pengiriman.
