# Verifikasi snapshot retur Jubelio, v0.46

Tanggal: 13 September 2026. Base `96fdf2d`; branch `feature/jubelio-return-snapshot` pada worktree lokal.
Semua pengujian memakai database sementara.

## Cakupan backend

Empat acceptance test baru memeriksa impor dan retry idempotent, run sinkronisasi yang jujur, unit yang
sudah diterima, refund yang sudah selesai, agregat marketplace dan SKU, karantina seluruh retur ketika
satu SKU tidak aman, aturan status/refund, validasi waktu/nilai/duplikat, role guard, daftar dan detail
batch, rollback atomik, trigger dan constraint immutable, backup, serta migrasi schema 36 ke 37.

Seluruh suite backend lulus: **244 test dalam 272,737 detik** (`python -m unittest discover -s tests
-p 'test_*.py' -v`). Waktu proses end-to-end runner adalah 276,536 detik.

## Browser dan client

Edge/Playwright memeriksa impor campuran retur valid dan unknown, status gagal parsial, ringkasan unit
dan refund, escaping nilai vendor, riwayat dan detail batch, cursor sumber, hak baca viewer, ketiadaan
tombol impor manual, mobile 390 px, skala teks 200%, dan ketiadaan error JavaScript.
Seluruh regression suite browser lulus dan screenshot ringkasan retur mobile diperiksa secara visual.

## Pemeriksaan rilis

Kontrak OpenAPI memuat versi 0.46.0 dan empat operasi return snapshot/summary pada tiga path. Database
baru dan hasil migrasi memakai schema 37. Tiga dependency aplikasi memenuhi batas versi yang
dideklarasikan. Kompilasi Python 3.12, syntax 39 file JavaScript, client test, browser final, dan
pemeriksaan diff lulus sebelum commit rilis.

## Batas

Snapshot masuk melalui endpoint worker lokal; aplikasi belum memanggil API Jubelio atau menyimpan
credential. Data vendor tidak membuat retur, refund, settlement, atau perubahan stok internal.
