# Verifikasi approval cuti dan lembur, v0.79

Tanggal: 15 September 2026. Branch `feature/global-audit-trail` pada worktree lokal. Semua pengujian memakai
database sementara dan tidak mengubah data operasional.

## Acceptance coverage

Backend memeriksa pengajuan cuti dan lembur, rentang tanggal dan menit, karyawan aktif, benturan tanggal,
idempotency, revision guard, filter dan pencarian, role admin/operator/viewer, keputusan terminal, audit, backup,
migrasi 50 → 51, serta pemisahan approval dari ledger kehadiran. Trigger SQLite memeriksa transisi, aktor, dan
immutability.

Browser memeriksa pengajuan cuti dan lembur dari layar People, pemulihan respons jaringan yang hilang, viewer
read-only, approval admin melalui unified inbox, pembatalan oleh operator pemohon, escaping, layout mobile, dan
zoom teks 200%.

## Hasil

Regresi backend penuh lulus **329 tes dalam 713,333 detik**. Setelah aturan pembatalan terakhir dikunci agar hanya
operator pemohon yang dapat membatalkan, acceptance backend khusus diulang dan lulus **3 tes dalam 2,828 detik**.

Regresi browser lengkap lulus di Microsoft Edge dengan exit code 0 tanpa error JavaScript. Alur People approval,
unified inbox, keputusan admin, pembatalan operator, viewer, retry, escaping, mobile, dan zoom 200% semuanya lulus.
Screenshot lebar 390 px diperiksa secara visual dan tidak keluar dari viewport.

Client checks lulus. Syntax **61 file JavaScript** lulus, termasuk pengecekan ulang aset utama dan acceptance People
setelah perubahan terakhir. Kompilasi Python dan `pip check` bersih. OpenAPI tersimpan sama persis dengan runtime
versi 0.79.0. Database baru memakai schema 51, `integrity_check` mengembalikan `ok`, dan `foreign_key_check` kosong.
Wheel `beeloft_one-0.79.0-py3-none-any.whl` berhasil dibuat; migrasi `workforce_approvals.sql`, UI, dan metadata
versi ikut terpaket. `git diff --check` lulus.

## Batas

Approval tidak membuat catatan kehadiran otomatis. Saldo dan jenis cuti rinci, jadwal shift, attachment, delegasi
approver, payroll per karyawan, pembayaran, serta runtime connector Jubelio/Mekari belum termasuk milestone ini.
