# Verifikasi snapshot order dan penjualan Jubelio, v0.45

Tanggal: 13 September 2026. Base `c07a78d`; branch `feature/jubelio-order-snapshot` pada worktree lokal.
Semua pengujian memakai database sementara.

## Cakupan backend

Empat acceptance test baru memeriksa impor dan retry idempotent, run sinkronisasi yang jujur, ringkasan
unit dan pendapatan order selesai, pengecualian order dibatalkan dari penjualan, karantina seluruh order
ketika satu SKU tidak aman, validasi status/waktu/nilai/duplikat, role guard, daftar dan detail batch,
rollback atomik, trigger immutable, backup, serta migrasi schema 35 ke 36.

Seluruh suite backend lulus: **240 test dalam 473,692 detik** (`python -m unittest discover -s tests
-p 'test_*.py' -v`). Waktu proses end-to-end runner adalah 477,914 detik.

## Browser dan client

Edge/Playwright memeriksa impor campuran order valid dan unknown, status gagal parsial, ringkasan
penjualan dan marketplace, escaping nilai vendor, riwayat dan detail batch, cursor sumber, hak baca
viewer, ketiadaan tombol impor manual, mobile 390 px, skala teks 200%, dan ketiadaan error JavaScript.
Seluruh regression suite browser lulus dan screenshot ringkasan order mobile diperiksa secara visual.

## Pemeriksaan rilis

Kontrak OpenAPI memuat versi 0.45.0 dan empat operasi order snapshot/summary pada tiga path. Database
baru dan hasil migrasi memakai schema 36. Tiga dependency aplikasi memenuhi batas versi yang
dideklarasikan. Kompilasi Python 3.12, syntax 38 file JavaScript, client test, browser final, dan
pemeriksaan diff lulus sebelum commit rilis.

## Batas

Snapshot masuk melalui endpoint worker lokal; aplikasi belum memanggil API Jubelio atau menyimpan
credential. Data ini tidak membuat order produksi, fulfillment, settlement, atau perubahan stok.
