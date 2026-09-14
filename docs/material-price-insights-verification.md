# Verifikasi pergerakan harga bahan, v0.69

Tanggal: 14 September 2026. Base `df6a56a`; branch `feature/global-audit-trail` pada worktree lokal.
Semua pengujian memakai database sementara dan tidak mengubah data operasional.

## Backend

Dua acceptance test memeriksa kenaikan harga untuk pasangan material–supplier yang sama, perhitungan nominal dan
persentase, minimum/maksimum/rata-rata, urutan riwayat, pengecualian PO pending/ditolak/dibatalkan, satu observasi,
filter, pagination, role, validasi, backup, schema, dan sifat GET read-only.

Tes terarah lulus **2 tes** dalam 1,616 detik. Regresi backend penuh lulus **311 tes** dalam 237,449 detik.

## Browser dan visual

QA Edge memeriksa akses viewer, error/retry, karakter HTML sebagai teks, harga tunggal, empty state, drill-down
PO, lebar 390 px, zoom teks 200%, dan overflow horizontal.

Seluruh Edge QA lulus tanpa error JavaScript, termasuk laporan harga bahan dan seluruh modul lama. Screenshot
kartu pada lebar 390 px memperlihatkan harga, supplier, status satu observasi, dan riwayat PO tanpa overflow.

## Release checks

Client tests, syntax **55 file JavaScript**, kompilasi Python, dan `pip check` lulus. OpenAPI serta paket memakai
versi 0.69.0 dan kontrak memuat route baru. Database baru mencapai schema 48; `integrity_check` mengembalikan
`ok` dan `foreign_key_check` kosong. `git diff --check` serta pemeriksaan string UI tanpa em dash lulus.

## Batas

Rata-rata tidak dibobot kuantitas. Diskon, ongkir, pajak, dan syarat pembayaran tidak dinormalisasi. Runtime
connector Jubelio/Mekari tidak dicakup.
