# Verifikasi snapshot listing Jubelio, v0.47

Tanggal: 13 September 2026. Base `16514f2`; branch `feature/jubelio-listing-snapshot` pada worktree lokal.
Semua pengujian memakai database sementara.

## Cakupan backend

Empat acceptance test baru memeriksa impor dan retry idempotent, run sinkronisasi yang jujur, status
listing, cakupan produk aktif, rentang harga aktif, agregat marketplace, karantina per listing untuk
identifier tidak aman, validasi waktu/nilai/duplikat, role guard, daftar dan detail batch, rollback
atomik, trigger dan constraint immutable, backup, serta migrasi schema 37 ke 38.

Seluruh suite backend lulus: **248 test dalam 156,548 detik** (`python -m unittest discover -s tests
-p 'test_*.py' -v`). Waktu proses end-to-end runner adalah 157,634 detik.

## Browser dan client

Edge/Playwright memeriksa impor campuran listing valid dan unknown, status gagal parsial, ringkasan
status dan harga, escaping nilai vendor, riwayat dan detail batch, cursor sumber, hak baca viewer,
ketiadaan tombol impor manual, mobile 390 px, skala teks 200%, dan ketiadaan error JavaScript.
Seluruh regression suite browser lulus dan screenshot ringkasan listing mobile diperiksa secara visual.

## Pemeriksaan rilis

Kontrak OpenAPI memuat versi 0.47.0 dan empat operasi listing snapshot/summary pada tiga path. Database
baru dan hasil migrasi memakai schema 38. Tiga dependency aplikasi memenuhi batas versi yang
dideklarasikan. Kompilasi Python 3.12, syntax 40 file JavaScript, client test, browser final, dan
pemeriksaan diff lulus sebelum commit rilis.

## Batas

Snapshot masuk melalui endpoint worker lokal; aplikasi belum memanggil API Jubelio atau menyimpan
credential. Data vendor tidak mengubah listing, master produk, harga internal, atau stok Beeloft.
