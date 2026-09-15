# Verifikasi alert kualitas di Command Center, v0.74

Tanggal: 15 September 2026. Branch `feature/global-audit-trail` pada worktree lokal. Semua pengujian memakai
database sementara dan tidak mengubah data operasional.

## Backend

Acceptance test memeriksa snapshot kosong, agregat yield/rework/reject, perbandingan dua periode 30 hari, pemilihan
vendor dengan risiko tertinggi, isi alert, prioritas, target aksi, escaping input melalui kontrak data, role aktif,
serta autentikasi. Tes terarah lulus **4 tes**. Regresi backend penuh lulus **321 tes dalam 841,409 detik**.

## Browser dan visual

QA Edge memeriksa kartu kualitas pada Command Center, alert line internal dengan karakter HTML, angka yield dan
rework + reject, navigasi alert ke analisis kualitas, drill-down final QC, akses viewer, mobile 390 px, zoom teks
200%, serta seluruh modul lama. Seluruh suite Edge lulus dalam **225,599 detik** tanpa error JavaScript.

## Release checks

Client test dan syntax **59 file JavaScript** lulus. Kompilasi Python dan `pip check` lulus. OpenAPI serta paket
memakai versi 0.74.0 dan tetap memuat `GET /api/command-center`. Database baru tetap memakai schema 49;
`integrity_check` mengembalikan `ok` dan `foreign_key_check` kosong. `git diff --check` serta pemeriksaan string UI
baru tanpa em dash lulus.

## Batas

Hanya kelompok kualitas dengan risiko tertinggi yang menjadi alert Command Center. Threshold masih tetap 5% dan
1 poin. Runtime connector Jubelio/Mekari tidak dicakup.
