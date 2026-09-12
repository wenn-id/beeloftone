# Verifikasi shipping marketplace, v0.28

Tanggal: 12 September 2026. Base `31e08be`; branch `feature/marketplace-shipping` pada worktree lokal.
Pengujian memakai database sementara dan tidak menyentuh data bisnis.

## Cakupan backend

Lima acceptance test baru memeriksa pengiriman parsial, stok packed yang keluar gudang, carrier dan
nomor resi, lineage, WIP yang tetap, total inventori yang berkurang, role, koreksi, blok koreksi
pack, validasi tanggal dan jumlah, transaksi bersamaan, rollback, pagination, backup, direct-write
guard, ledger immutable, serta migrasi schema 22 → 23. Seluruh regression suite berisi **162 tests**
dan lulus dalam **173,853 detik**.

## Browser dan client

Browser QA mengirim 2 dari pack 3 pcs. Inventori menjadi 8 sellable, 1 picked, 1 packed, 2 shipped,
2 reserved, 6 available, 8 hold, dan total gudang turun dari 20 menjadi 18. Respons create sengaja
diputus setelah server menyimpan; reload dan retry dengan key yang sama tetap menghasilkan satu
catatan. Koreksi pack ditolak selama pengiriman aktif. Viewer hanya membaca; admin mengoreksi
pengiriman dan inventori kembali menjadi 3 packed, 0 shipped, dan total 20 tanpa mengubah WIP.

Seluruh browser suite lulus melalui Edge/Playwright tanpa error JavaScript. Daftar kosong, kegagalan
GET, escaping teks, viewport 390 × 844, skala teks 200%, dan pemulihan request turut diperiksa.
`node --check` untuk aplikasi serta browser test dan `node tests/test_client.mjs` lulus. Screenshot
`beeloft-marketplace-shipment-mobile.png` diperiksa pada ukuran asli; status, jumlah, marketplace,
carrier/resi, tanggal, staging, lineage, alasan, aktor, dan tombol terbaca tanpa overflow.

## Batas

Belum ada pembelian/cetak label, carrier API, event tracking, konfirmasi delivery, konsolidasi
beberapa pack, sinkronisasi marketplace/Jubelio, retur pelanggan, refund, stock opname, atau
adjustment. Langkah berikutnya memakai pengiriman aktif sebagai sumber retur dan inventory
adjustment.
