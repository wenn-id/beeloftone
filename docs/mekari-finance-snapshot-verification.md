# Verifikasi snapshot ringkasan keuangan Mekari, v0.48

Tanggal: 13 September 2026. Base `47e0046`; branch `feature/mekari-finance-summary-snapshot` pada worktree lokal.
Semua pengujian memakai database sementara.

## Cakupan backend

Empat acceptance test baru memeriksa impor dan retry idempotent, run sinkronisasi yang jujur,
perhitungan desimal untuk pendapatan bersih, laba kotor, laba bersih, dan posisi likuiditas, periode
terbaru, validasi tanggal/nilai/duplikat, role guard, daftar dan detail batch, rollback atomik, trigger
serta constraint immutable, backup, dan migrasi schema 38 ke 39.

Seluruh suite backend lulus: **252 test dalam 578,251 detik** (`python -m unittest discover -s tests
-p 'test_*.py' -v`). Waktu proses end-to-end runner adalah 580,577 detik.

## Browser dan client

Edge/Playwright memeriksa ringkasan manajemen, riwayat dan detail batch, cursor sumber, escaping nilai
vendor, hak baca viewer, ketiadaan tombol impor/jurnal manual, mobile 390 px, skala teks 200%, dan
ketiadaan error JavaScript. Seluruh regression suite browser lulus dan screenshot mobile diperiksa.

## Pemeriksaan rilis

Kontrak OpenAPI memuat versi 0.48.0 dan empat operasi finance snapshot/summary pada tiga path. Database
baru dan hasil migrasi memakai schema 39. Tiga dependency aplikasi memenuhi batas versi yang
dideklarasikan. Kompilasi Python 3.12, syntax 41 file JavaScript, client test, browser final, dan
pemeriksaan diff lulus sebelum commit rilis.

## Batas

Snapshot masuk melalui endpoint worker lokal; aplikasi belum memanggil API Mekari atau menyimpan
credential. Data hanya untuk tampilan manajemen dan tidak membuat jurnal, pembayaran, atau koreksi.
