# Verifikasi kinerja supplier, v0.68

Tanggal: 14 September 2026. Base `7b33744`; branch `feature/global-audit-trail` pada worktree lokal.
Semua pengujian memakai database sementara dan tidak mengubah data operasional.

## Backend

Dua acceptance test memeriksa supplier sehat dan perlu perhatian, kedatangan tepat waktu, PO terlambat tanpa
kedatangan, PO belum lengkap, QC accept/reject, volume per satuan, receipt terkoreksi, intake dibatalkan, filter,
pagination, role, validasi, backup, schema, dan sifat GET read-only. Tes terarah lulus **2 tes** dalam 1,276 detik.

Regresi backend penuh lulus **309 tes** dalam 545,790 detik.

## Browser dan visual

QA Edge memakai tiga PO aktif/ditutup dari supplier yang sama. Dua tidak mempunyai kedatangan aktif setelah
koreksi/pembatalan; satu mempunyai QC 1 m layak dan 2 m reject lalu ditutup dengan kekurangan. Error/retry,
viewer, karakter HTML sebagai teks, empty state, drill-down PO, lebar 390 px, zoom 200%, dan overflow diperiksa.

Seluruh Edge QA lulus tanpa error JavaScript, termasuk laporan kinerja supplier dan seluruh modul lama.
Screenshot kartu supplier pada lebar 390 px memperlihatkan volume per satuan, usable/reject rate, sinyal, dan
daftar PO terbaca tanpa overflow. Zoom teks 200% juga lulus pemeriksaan overflow horizontal.

## Release checks

Client tests, syntax **54 file JavaScript**, kompilasi Python, dan `pip check` lulus. OpenAPI serta paket memakai
versi 0.68.0 dan kontrak memuat route baru. Database baru mencapai schema 48; `integrity_check` mengembalikan
`ok` dan `foreign_key_check` kosong. `git diff --check` serta pemeriksaan string UI tanpa em dash lulus.

## Batas

Kinerja adalah ringkasan ledger dan bukan rating kontraktual supplier. Tanggal kedatangan pertama tidak mengukur
waktu pemenuhan lengkap. Runtime connector Jubelio/Mekari tidak dicakup.
