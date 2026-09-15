# Verifikasi fondasi People, v0.76

Tanggal: 15 September 2026. Branch `feature/global-audit-trail` pada worktree lokal. Semua pengujian memakai
database sementara dan tidak mengubah data operasional.

## Acceptance coverage

Tes mencakup employee master, normalisasi kode, pencarian dan filter, idempotency, role admin, perubahan dan
history revisi, konflik revisi serta no-op. Kehadiran mencakup hadir, cuti, absen, jam kerja, lembur, ringkasan,
koreksi oleh operator, history, input jam invalid, tanggal mendatang, role viewer, dan rentang tanggal invalid.

Migrasi schema 49 ke 50 dijalankan dua kali untuk membuktikan idempotency. Trigger immutable, backup,
`integrity_check`, `foreign_key_check`, kategori global audit, kontrak OpenAPI, dan kompatibilitas seluruh regresi
backend juga diverifikasi.

## Hasil

Acceptance test khusus lulus **3 tes dalam 2,452 detik**. Regresi backend penuh lulus **325 tes dalam 603,219
detik**. Kompilasi Python, `pip check`, client checks, dan syntax **59 file JavaScript** lulus.

Kontrak tersimpan sama persis dengan OpenAPI runtime dan memuat versi 0.76.0 serta tujuh endpoint People. Database
baru memakai schema 50 dengan empat tabel workforce; `integrity_check` mengembalikan `ok` dan
`foreign_key_check` kosong. Wheel `beeloft_one-0.76.0-py3-none-any.whl` berhasil dibuat dan memuat
`beeloft/workforce.sql`. `git diff --check` lulus.

## Batas

Belum ada UI People atau alert workforce di Command Center. Runtime connector Mekari/Jubelio tetap tidak dicakup.
