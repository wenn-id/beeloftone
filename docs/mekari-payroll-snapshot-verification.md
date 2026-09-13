# Verifikasi snapshot payroll agregat Mekari, v0.51

Tanggal: 13 September 2026. Base `feeb5ad`; branch `feature/mekari-payroll-snapshot` pada worktree
lokal. Semua pengujian memakai database sementara.

## Cakupan backend

Empat acceptance test baru memeriksa impor dan retry idempotent, run sinkronisasi, aritmetika
exact-decimal, status approval/pembayaran, tanggal pembayaran, pemilihan periode terbaru, validasi
tanggal/nilai/status/duplikat, role guard, daftar dan detail batch, rollback atomik, trigger serta
constraint immutable, backup, dan migrasi schema 41 ke 42.

Seluruh suite backend lulus: **264 test dalam 461,496 detik** (`python -m unittest discover -s tests
-p 'test_*.py'`). Waktu proses end-to-end runner adalah 464,230 detik.

## Browser dan client

Edge/Playwright memeriksa ringkasan status dan biaya payroll, periode terbaru, riwayat dan detail batch,
cursor sumber, escaping ID eksternal, hak baca viewer, ketiadaan identitas karyawan dan tombol impor/
approval/pembayaran/jurnal, mobile 390 px, skala teks 200%, dan ketiadaan error JavaScript. Seluruh
regression suite browser lulus dan screenshot mobile diperiksa secara visual.

## Pemeriksaan rilis

Kontrak OpenAPI memuat versi 0.51.0 dan empat operasi payroll snapshot/summary pada tiga path. Database
baru dan hasil migrasi memakai schema 42. Tiga dependency aplikasi memenuhi batas versi yang
dideklarasikan. Kompilasi Python 3.12, syntax 44 file JavaScript, client test, browser final, dan
pemeriksaan diff lulus sebelum commit rilis.

## Batas

Snapshot hanya memuat angka agregat per periode dan masuk melalui endpoint worker lokal. Aplikasi belum
memanggil API Mekari, menyimpan credential, menghitung atau menyetujui payroll, menjalankan pembayaran,
atau membuat jurnal akuntansi.
