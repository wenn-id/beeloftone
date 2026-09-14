# Verifikasi perencanaan kapasitas produksi, v0.72

Tanggal: 15 September 2026. Branch `feature/global-audit-trail` pada worktree lokal. Semua pengujian memakai
database sementara dan tidak mengubah data operasional.

## Backend

Acceptance test memeriksa rute tersisa dari saldo multi-tahap, standar menit dengan tiga desimal, kapasitas hari
kerja, libur melalui override, utilisasi, overload, risiko kapasitas sebelum target, filter, pagination, gap
standar, work center nonaktif, revisi optimistis, idempotensi, role, validasi, migrasi dari schema 48, trigger
append-only, backup, dan sifat laporan GET yang read-only.

Tes terarah lulus **3 tes**. Regresi backend penuh lulus **318 tes** dalam 230,560 detik.

## Browser dan visual

QA Edge memeriksa form master work center dan standar waktu untuk admin, akses laporan untuk viewer, loading
error/retry, overload dan risiko deadline, escaping karakter HTML, empty state, drill-down order, lebar 390 px,
zoom teks 200%, dan overflow horizontal. Seluruh suite Edge lulus tanpa error JavaScript, termasuk modul lama.

## Release checks

Client test dan syntax **58 file JavaScript** lulus. Kompilasi Python dan `pip check` lulus. OpenAPI serta paket
memakai versi 0.72.0 dan memuat route kapasitas. Database baru dan migrasi dari schema 48 mencapai schema 49;
`integrity_check` mengembalikan `ok` dan `foreign_key_check` kosong. `git diff --check` serta pemeriksaan string UI
baru tanpa em dash lulus.

## Batas

Perhitungan memakai saldo ledger saat request, bukan snapshot historis. Kapasitas belum menjadi finite scheduler
per jam dan belum memasukkan absensi, setup, maintenance, atau efisiensi selain nilai master dan override kalender.
Runtime connector Jubelio/Mekari tidak dicakup.
