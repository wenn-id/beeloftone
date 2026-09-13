# Verifikasi snapshot stok barang jadi Jubelio, v0.44

Tanggal: 13 September 2026. Base `d8d1e20`; branch `feature/jubelio-stock-snapshot` pada worktree
lokal. Semua pengujian memakai database sementara.

## Cakupan backend

Empat acceptance test baru memeriksa impor dan retry idempotent, pembuatan run sinkronisasi yang
jujur, rekonsiliasi available, karantina identifier unknown dan tidak konsisten, validasi kuantitas
dan duplikat, role guard, daftar dan detail batch, rollback atomik, trigger immutable, backup, serta
migrasi schema 34 ke 35.

Seluruh suite backend lulus: **236 test dalam 215,972 detik** (`python -m unittest discover -s tests
-p 'test_*.py' -v`).

## Browser dan client

Edge/Playwright memeriksa impor campuran record valid dan unknown, status gagal parsial, perbandingan
stok per SKU, escaping nilai karantina, riwayat dan detail batch, cursor sumber, hak baca viewer,
ketiadaan tombol impor manual, mobile 390 px, skala teks 200%, dan ketiadaan error JavaScript.
Seluruh regression suite browser lulus dan screenshot rekonsiliasi mobile diperiksa secara visual.

## Pemeriksaan rilis

Kontrak OpenAPI memuat versi 0.44.0 dan empat operasi snapshot/rekonsiliasi pada tiga path. Database
baru dan hasil migrasi memakai schema 35. Tiga dependency aplikasi memenuhi batas versi yang
dideklarasikan. Kompilasi Python, syntax 37 file JavaScript, client test, browser final, dan pemeriksaan
diff lulus sebelum commit rilis.

## Batas

Snapshot masuk melalui endpoint worker lokal; aplikasi belum memanggil API Jubelio atau menyimpan
credential. Rekonsiliasi tidak menyesuaikan stok internal secara otomatis.
