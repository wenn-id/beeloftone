# Verifikasi snapshot utang usaha Mekari, v0.49

Tanggal: 13 September 2026. Base `f01aa3a`; branch `feature/mekari-payable-snapshot` pada worktree lokal.
Semua pengujian memakai database sementara.

## Cakupan backend

Empat acceptance test baru memeriksa impor dan retry idempotent, run sinkronisasi, saldo exact-decimal,
status pembayaran, overdue, batas jatuh tempo 0–7 hari, agregat supplier, validasi tanggal/nilai/status/
duplikat, role guard, daftar dan detail batch, rollback atomik, trigger serta constraint immutable,
backup, dan migrasi schema 39 ke 40.

Seluruh suite backend lulus: **256 test dalam 170,373 detik** (`python -m unittest discover -s tests
-p 'test_*.py' -v`). Waktu proses end-to-end runner adalah 171,414 detik.

## Browser dan client

Edge/Playwright memeriksa invoice overdue dan jatuh tempo dekat, nilai kewajiban, agregat supplier,
riwayat dan detail batch, cursor sumber, escaping nilai vendor, hak baca viewer, ketiadaan tombol bayar/
impor/jurnal, mobile 390 px, skala teks 200%, dan ketiadaan error JavaScript. Seluruh regression suite
browser lulus dan screenshot mobile diperiksa secara visual.

## Pemeriksaan rilis

Kontrak OpenAPI memuat versi 0.49.0 dan empat operasi payable snapshot/summary pada tiga path. Database
baru dan hasil migrasi memakai schema 40. Tiga dependency aplikasi memenuhi batas versi yang
dideklarasikan. Kompilasi Python 3.12, syntax 42 file JavaScript, client test, browser final, dan
pemeriksaan diff lulus sebelum commit rilis.

## Batas

Snapshot masuk melalui endpoint worker lokal; aplikasi belum memanggil API Mekari atau menyimpan
credential. Data tidak membayar invoice, mengubah status vendor, atau membuat jurnal akuntansi.
