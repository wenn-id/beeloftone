# Verifikasi picking marketplace, v0.26

Tanggal: 12 September 2026. Base `55d6032`; branch `feature/marketplace-picking` pada worktree lokal.
Pengujian memakai database sementara dan tidak menyentuh data bisnis.

## Cakupan backend

Lima acceptance test baru memeriksa pick parsial, stok staging `picked`, sisa reservasi, available
yang tetap, lineage, WIP yang tetap, role, koreksi, blok pelepasan reservasi, validasi tanggal dan
jumlah, transaksi bersamaan, rollback, pagination, backup, direct-write guard, ledger immutable,
serta migrasi schema 20 → 21. Seluruh regression suite berisi **152 tests** dan lulus dalam
**114,641 detik**.

## Browser dan client

Browser QA mengambil 4 dari reservasi 6 pcs. Inventori berubah dari 12 sellable menjadi 8
sellable, 4 picked di staging, 2 reserved, 6 available, dan total tetap 20 bersama 8 hold. Respons
create sengaja diputus setelah server menyimpan; reload dan retry dengan key yang sama tetap
menghasilkan satu catatan. Pelepasan reservasi ditolak selama pick aktif. Viewer hanya membaca;
admin mengoreksi pick dan inventori kembali menjadi 12 sellable, 0 picked, 6 reserved, dan 6
available tanpa mengubah WIP.

Seluruh browser suite lulus dua kali melalui Edge/Playwright tanpa error JavaScript. Daftar kosong,
kegagalan GET, escaping teks, viewport 390 × 844, skala teks 200%, dan pemulihan request turut
diperiksa. `node --check` untuk aplikasi serta browser test dan `node tests/test_client.mjs` lulus.
Screenshot `beeloft-marketplace-pick-mobile.png` diperiksa pada ukuran asli; status, jumlah,
marketplace, order eksternal, rute rak ke staging, tanggal, lineage, alasan, aktor, dan tombol
terbaca tanpa overflow.

## Batas

Belum ada pemindaian barcode, picker assignment, wave/tote, packing, shipping, retur pelanggan,
atau sinkronisasi API marketplace/Jubelio. Langkah berikutnya menerima stok `picked` sebagai sumber
konfirmasi packing.
