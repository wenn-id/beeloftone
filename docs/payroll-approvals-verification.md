# Verifikasi approval batch payroll Mekari, v0.80

Tanggal: 15 September 2026. Branch `feature/global-audit-trail` pada worktree lokal. Semua pengujian memakai
database sementara dan tidak mengubah data operasional.

## Acceptance coverage

Backend memeriksa sumber snapshot terbaru berstatus `reviewing`, pengajuan idempotent, satu request pending per ID
payroll sumber, nilai agregat exact-decimal, daftar dan unified inbox, role admin/operator/viewer, revision guard,
keputusan terminal, status sumber yang tidak berubah, deteksi snapshot baru, pencegahan approval stale, audit,
trigger immutable, backup, serta migrasi schema 51 → 52.

Browser memeriksa kartu status Mekari dan approval Beeloft, pengajuan operator dengan pemulihan respons jaringan
yang hilang, viewer read-only, keputusan admin dari unified inbox, stale warning, escaping ID sumber, lebar 390 px,
dan zoom teks 200%.

## Hasil

Acceptance payroll dan regression snapshot payroll lulus **8 tes** setelah perubahan terakhir. Regresi backend
penuh lulus **333 tes dalam 694,729 detik**.

Regresi browser lengkap lulus di Microsoft Edge dengan exit code 0 tanpa error JavaScript. Alur payroll baru dan
seluruh modul lama lulus. Client checks serta syntax **62 file JavaScript** lulus. Kompilasi Python dan `pip check`
bersih.

OpenAPI tersimpan sama persis dengan runtime versi 0.80.0. Database baru memakai schema 52, `integrity_check`
mengembalikan `ok`, dan `foreign_key_check` kosong. Wheel `beeloft_one-0.80.0-py3-none-any.whl` berhasil dibuat dan
memuat `payroll_approvals.sql`, migrasi sebelumnya, UI, serta metadata versi. SHA-256 wheel:
`c270a6f9526b8679ecb7c2e2354f7cd57a0e457a999e55c043cdcd1c0f21720d`. `git diff --check` lulus.

## Batas

Approval Beeloft tidak memanggil API Mekari, mengubah status snapshot, menghitung payroll, menyimpan data gaji per
karyawan, menjalankan pembayaran, membuat jurnal, atau mengelola pajak. Runtime connector Mekari tetap ditunda.
