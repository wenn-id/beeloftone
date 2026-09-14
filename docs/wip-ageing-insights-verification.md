# Verifikasi WIP ageing, v0.71

Tanggal: 15 September 2026. Base `24285b8`; branch `feature/global-audit-trail` pada worktree lokal.
Semua pengujian memakai database sementara dan tidak mengubah data operasional.

## Backend

Dua acceptance test memeriksa umur dari movement terbaru dan tanggal order, saldo multi-tahap, order overdue,
issue terbuka, rework, rollup tahap, sinyal hambatan, pencarian, filter status/tahap/PIC, pagination, pengecualian
order selesai dan order masa depan, role, validasi, backup, schema, serta sifat GET read-only.

Tes terarah lulus **2 tes**. Regresi backend penuh lulus **315 tes** dalam 222,180 detik.

## Browser dan visual

QA Edge memeriksa akses viewer, error/retry, posisi tahap, karakter HTML sebagai teks, empty state, drill-down
order, lebar 390 px, zoom teks 200%, dan overflow horizontal.

Seluruh Edge QA lulus tanpa error JavaScript, termasuk laporan WIP dan seluruh modul lama. Kartu WIP pada lebar
390 px memperlihatkan posisi, umur, sinyal, SKU, dan kendala tanpa overflow; zoom teks 200% juga lulus.

## Release checks

Client tests, syntax **57 file JavaScript**, kompilasi Python, dan `pip check` lulus. OpenAPI serta paket memakai
versi 0.71.0 dan kontrak memuat route baru. Database baru tetap schema 48; `integrity_check` mengembalikan `ok`
dan `foreign_key_check` kosong. `git diff --check` serta pemeriksaan string UI baru tanpa em dash lulus.

## Batas

Umur adalah umur order sejak aktivitas produksi terakhir, bukan umur setiap unit yang tersisa pada tiap tahap.
Posisi menggunakan saldo ledger saat request. Sinyal hambatan bukan ukuran kapasitas. Runtime connector
Jubelio/Mekari tidak dicakup.
