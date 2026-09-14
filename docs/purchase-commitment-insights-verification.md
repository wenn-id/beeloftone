# Verifikasi komitmen pembelian, v0.70

Tanggal: 14 September 2026. Base `6397f33`; branch `feature/global-audit-trail` pada worktree lokal.
Semua pengujian memakai database sementara dan tidak mengubah data operasional.

## Backend

Dua acceptance test memeriksa penerimaan parsial, nilai komitmen, posisi payment, status terlambat/segera jatuh
tempo/terjadwal/diterima lengkap, pengecualian PO pending, ditolak, dan ditutup, pencarian material, pagination,
role, validasi, backup, schema, serta sifat GET read-only.

Tes terarah lulus **2 tes** dalam 1,502 detik. Regresi backend penuh lulus **313 tes** dalam 239,988 detik.

## Browser dan visual

QA Edge memeriksa akses viewer, error/retry, nilai komitmen, karakter HTML sebagai teks, empty state, drill-down
PO, lebar 390 px, zoom teks 200%, dan overflow horizontal.

Seluruh Edge QA lulus tanpa error JavaScript, termasuk laporan komitmen pembelian dan seluruh modul lama.
Screenshot kartu pada lebar 390 px memperlihatkan nilai PO, penerimaan, komitmen, posisi payment, dan rincian
bahan tanpa overflow.

## Release checks

Client tests, syntax **56 file JavaScript**, kompilasi Python, dan `pip check` lulus. OpenAPI serta paket memakai
versi 0.70.0 dan kontrak memuat route baru. Database baru mencapai schema 48; `integrity_check` mengembalikan
`ok` dan `foreign_key_check` kosong. `git diff --check` serta pemeriksaan string UI tanpa em dash lulus.

## Batas

Laporan memakai posisi ledger saat request, bukan snapshot historis. Payment approved belum berarti dana sudah
ditransfer. Runtime connector Jubelio/Mekari tidak dicakup.
