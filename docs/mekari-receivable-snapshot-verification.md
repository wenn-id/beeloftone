# Verifikasi snapshot piutang usaha Mekari, v0.50

Tanggal: 13 September 2026. Base `7376919`; branch `feature/mekari-receivable-snapshot` pada worktree
lokal. Semua pengujian memakai database sementara.

## Cakupan backend

Empat acceptance test baru memeriksa impor dan retry idempotent, run sinkronisasi, saldo exact-decimal,
status penerimaan, overdue, batas jatuh tempo 0–7 hari, agregat pelanggan, validasi tanggal/nilai/status/
duplikat, role guard, daftar dan detail batch, rollback atomik, trigger serta constraint immutable,
backup, dan migrasi schema 40 ke 41.

Seluruh suite backend lulus: **260 test dalam 452,544 detik** (`python -m unittest discover -s tests
-p 'test_*.py' -v`). Waktu proses end-to-end runner adalah 455,408 detik.

## Browser dan client

Edge/Playwright memeriksa invoice overdue dan jatuh tempo dekat, nilai penerimaan, agregat pelanggan,
riwayat dan detail batch, cursor sumber, escaping nilai pelanggan, hak baca viewer, ketiadaan tombol
tagih/impor/jurnal, mobile 390 px, skala teks 200%, dan ketiadaan error JavaScript. Seluruh regression
suite browser lulus dan screenshot mobile diperiksa secara visual.

## Pemeriksaan rilis

Kontrak OpenAPI memuat versi 0.50.0 dan empat operasi receivable snapshot/summary pada tiga path.
Database baru dan hasil migrasi memakai schema 41. Tiga dependency aplikasi memenuhi batas versi yang
dideklarasikan. Kompilasi Python 3.12, syntax 43 file JavaScript, client test, browser final, dan
pemeriksaan diff lulus sebelum commit rilis.

## Batas

Snapshot masuk melalui endpoint worker lokal; aplikasi belum memanggil API Mekari atau menyimpan
credential. Data tidak menagih pelanggan, mengubah status invoice, atau membuat jurnal akuntansi.
