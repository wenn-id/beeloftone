# Verifikasi margin kontribusi, v0.36

Tanggal: 13 September 2026. Base `c939a5b`; branch `feature/contribution-margin` pada worktree
lokal. Pengujian memakai database sementara dan tidak menyentuh data bisnis.

## Cakupan backend

Acceptance test memeriksa settlement per pengiriman, nominal IDR eksak, idempotency, satu settlement
aktif, koreksi immutable, role, tanggal, pagination, lineage, backup, keputusan bersamaan, migrasi
schema 29 → 30, dan guard SQL untuk pengiriman yang masih mempunyai retur atau settlement aktif.

Laporan memeriksa omzet, diskon, refund, pendapatan neto, biaya jual variabel, biaya produksi
teralokasi dengan pembulatan HALF_UP, margin, rasio margin, penjualan parsial, serta coverage gap.
Perubahan jumlah retur setelah settlement membuat margin incomplete sampai settlement diganti. Seluruh
regression suite berisi **201 tests** dan lulus dalam **212,725 detik**.

## Browser dan client

Edge/Playwright menjalankan alur dari bahan berharga PO, cutting, sewing, finishing, final QC,
penerimaan barang jadi, reservasi, pick, pack, ship, hingga settlement. QA memeriksa margin Rp315,00
dari pendapatan neto Rp480,00, biaya jual Rp65,00, dan biaya produksi teralokasi Rp100,00. Error
retry, respons POST terputus, reload dengan idempotency key yang sama, viewer, escaping, mobile, dan
skala teks 200% lulus. Seluruh browser regression suite selesai tanpa error JavaScript.

## Batas

Pajak, payment gateway yang dicatat terpisah, iklan, overhead tetap, biaya penanganan retur,
write-off stok, jurnal, dan integrasi marketplace/Mekari belum dihitung. Alokasi biaya produksi
mengikuti cakupan laporan biaya produksi v0.35. Schema sekarang versi 30.
