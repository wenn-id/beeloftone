# Verifikasi status sinkronisasi integrasi, v0.42

Tanggal: 13 September 2026. Base `ef6e10f`; branch `feature/integration-sync-health` pada worktree
lokal. Semua pengujian memakai database sementara.

## Cakupan backend

Empat acceptance test baru memeriksa source-of-truth map dan kondisi belum pernah sinkron, pencatatan
run sukses/gagal yang idempotent, filter dan cursor riwayat, derivasi health per scope/sistem, validasi
scope dan waktu, role admin, rollback, trigger immutable, backup, serta migrasi schema 32 ke 33.

Seluruh suite backend lulus: **227 test dalam 310,898 detik** (`python -m unittest discover -s tests
-p 'test_*.py' -v`). Waktu proses end-to-end runner adalah 313,240 detik.

## Browser dan client

Edge/Playwright menjalankan seluruh browser regression suite. Layar Integrasi diuji saat API pertama
gagal lalu pulih lewat retry, saat semua scope belum pernah sinkron, dan setelah worker mencatat run
orders sukses serta finished-goods gagal. Pengujian memastikan status sistem gagal, source of truth,
jumlah record, error, cursor, filter riwayat, dan detail run ditampilkan dengan benar.

Dashboard tidak memiliki kontrol untuk membuat run manual. Escaping HTML, mobile 390 px, skala teks
200%, seluruh modul lama, dan ketiadaan error JavaScript ikut diperiksa.

## Pemeriksaan rilis

Kontrak `docs/openapi.json` memuat versi 0.42.0 dan empat operasi integrasi. Database baru dan hasil
migrasi memakai schema 33. `pip check`, kompilasi seluruh Python, pemeriksaan sintaks 35 file
JavaScript, client test, dan `git diff --check` lulus. Edge/Playwright juga mengulang seluruh browser
regression suite pada build rilis final tanpa error JavaScript.

## Batas

Belum ada koneksi vendor, credential, scheduler, atau impor data Jubelio/Mekari. Status hanya berasal
dari hasil run nyata yang kelak dicatat worker admin melalui endpoint. Karena itu database baru dengan
semua scope `never_synced` adalah kondisi yang benar, bukan keberhasilan semu.
