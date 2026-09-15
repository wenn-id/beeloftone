# Verifikasi rekonsiliasi pembayaran payroll, v0.81

Tanggal: 15 September 2026. Branch `feature/global-audit-trail` pada worktree lokal. Semua pengujian memakai
database sementara dan tidak mengubah data operasional.

## Acceptance coverage

Backend memeriksa transisi sumber reviewing → approved → paid, tanggal pembayaran, exact-decimal, exception
sumber hilang, nominal berubah, status dibatalkan, keputusan terbaru per ID payroll, filter, pencarian,
pagination, validasi query, dan akses viewer.

Browser memeriksa akses dari kesehatan integrasi, error/retry, status paid, exception nominal, filter, pencarian
ID yang memuat karakter HTML, viewer read-only, lebar 390 px, dan zoom teks 200%.

## Hasil

Acceptance rekonsiliasi dan regresi approval/snapshot payroll lulus **11 tes**. Regresi backend penuh lulus
**336 tes dalam 715,007 detik**.

Regresi browser lengkap lulus di Microsoft Edge dengan exit code 0 tanpa error JavaScript. Alur rekonsiliasi
baru dan seluruh modul lama lulus. Client checks serta syntax **63 file JavaScript** lulus. Kompilasi Python dan
`pip check` bersih.

OpenAPI tersimpan sama persis dengan runtime versi 0.81.0. Database baru tetap memakai schema 52,
`integrity_check` mengembalikan `ok`, dan `foreign_key_check` kosong. Wheel
`beeloft_one-0.81.0-py3-none-any.whl` berhasil dibuat dan memuat migration terdahulu serta UI baru. SHA-256:
`7a915aaead62c0ed872b06eb188c24b131b5c743b2bc2195c8ee54f9e9358190`. `git diff --check` lulus.

## Batas

Rekonsiliasi tidak memanggil API Mekari, mengirim uang, mengubah status payroll, menyimpan data gaji per karyawan,
atau membuat jurnal. Runtime connector Mekari tetap ditunda.
