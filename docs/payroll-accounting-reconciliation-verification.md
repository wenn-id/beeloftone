# Verifikasi rekonsiliasi akuntansi payroll, v0.82

Tanggal: 15 September 2026. Branch `feature/global-audit-trail` pada worktree lokal. Semua pengujian memakai
database sementara dan tidak mengubah data operasional.

## Acceptance coverage

Backend memeriksa alur menunggu pembayaran, menunggu posting, posted, reversed, debit/kredit tidak seimbang,
nominal jurnal berbeda, exact decimal, keputusan terbaru per ID payroll, filter, pencarian, pagination, validasi,
akses viewer, idempotency, ledger immutable, backup, migrasi schema 52 → 53, integrity, dan foreign key.

Browser memeriksa akses dari kesehatan integrasi, error/retry, status posted, exception jurnal, menunggu posting,
filter, pencarian referensi jurnal yang memuat karakter HTML, viewer read-only, lebar 390 px, dan zoom teks 200%.

## Hasil

Acceptance rekonsiliasi serta regresi approval, payment, snapshot, dan kesehatan integrasi lulus **19 tes**.
Regresi backend penuh lulus **340 tes dalam 705,321 detik**.

Regresi browser lengkap lulus di Microsoft Edge dengan exit code 0 tanpa error JavaScript. Alur accounting baru
dan seluruh modul lama lulus. Client checks serta syntax **64 file JavaScript** lulus. Kompilasi Python dan
`pip check` bersih.

OpenAPI tersimpan sama persis dengan runtime versi 0.82.0. Database baru memakai schema 53,
`integrity_check` mengembalikan `ok`, dan `foreign_key_check` kosong. Wheel
`beeloft_one-0.82.0-py3-none-any.whl` berhasil dibuat dan memuat migrasi accounting, migrasi payroll approval,
serta UI baru. SHA-256: `eadc07397633efec18d9013f1690f725694822909886ebd74032a65d334aedfd`.
`git diff --check` lulus.

## Batas

Rekonsiliasi tidak memanggil API Mekari, membuat atau mem-posting jurnal, menyimpan chart of accounts atau baris
jurnal, maupun menyimpan data payroll per karyawan. Runtime connector Mekari tetap ditunda.
