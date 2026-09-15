# Verifikasi alert kapasitas di Command Center, v0.75

Tanggal: 15 September 2026. Branch `feature/global-audit-trail` pada worktree lokal. Semua pengujian memakai
database sementara dan tidak mengubah data operasional.

## Backend

Acceptance test memeriksa kondisi kosong, horizon 14 hari, kebutuhan dan ketersediaan menit, empat gap standar,
kuantitas tanpa standar, kapasitas lengkap, overload work center, order berisiko sebelum target, prioritas dan isi
alert, target aksi, role aktif, serta autentikasi. Tes terarah lulus **5 tes**. Regresi backend penuh lulus
**322 tes dalam 681,652 detik**.

## Browser dan visual

QA Edge memeriksa kartu kapasitas, alert risiko dan coverage gap, navigasi alert ke laporan kapasitas, data
overload nyata dari WIP dan standar routing, escaping, akses viewer, mobile 390 px, zoom teks 200%, serta seluruh
modul lama. Seluruh suite Edge lulus dalam **229,953 detik** tanpa error JavaScript.

## Release checks

Client test dan syntax **59 file JavaScript** lulus. Kompilasi Python dan `pip check` lulus. OpenAPI serta paket
memakai versi 0.75.0 dan tetap memuat `GET /api/command-center`. Database baru tetap memakai schema 49;
`integrity_check` mengembalikan `ok` dan `foreign_key_check` kosong. `git diff --check` serta pemeriksaan string UI
baru tanpa em dash lulus.

## Batas

Horizon tetap 14 hari dan threshold tetap 80%. Alert tidak menyusun jadwal per jam atau mengubah master kapasitas.
Runtime connector Jubelio/Mekari tidak dicakup.
