# Verifikasi alert People di Command Center, v0.78

Tanggal: 15 September 2026. Branch `feature/global-audit-trail` pada worktree lokal. Semua pengujian memakai
database sementara dan tidak mengubah data operasional.

## Acceptance coverage

Backend memeriksa roster kosong seluruhnya, roster sebagian lengkap, hadir, cuti, absen, kerja, lembur, karyawan
nonaktif, prioritas alert, isi pesan, target aksi, dan hilangnya alert setelah roster lengkap. Browser memeriksa
snapshot, dua alert, akses viewer, reset filter lama, drill-down ke dua status People, retry, mobile, dan zoom 200%.

## Hasil

Acceptance backend khusus lulus **6 tes dalam 6,762 detik**. Regresi backend penuh lulus **326 tes dalam 580,989
detik**.

Regresi browser lengkap lulus di Microsoft Edge tanpa error JavaScript. Alur memeriksa snapshot People, alert
roster belum lengkap dan absen, viewer read-only, reset filter People lama, drill-down, retry API, lebar 390 px,
serta zoom teks 200%. Screenshot Command Center diperiksa secara visual; kartu People mengikuti susunan satu kolom
dan tidak keluar dari viewport. Komponen memakai token warna yang sudah lolos pemeriksaan kontras pada v0.77 dan
milestone ini tidak menambah warna baru.

Client checks dan syntax **60 file JavaScript** lulus. Kompilasi Python dan `pip check` bersih. OpenAPI tersimpan
sama persis dengan runtime versi 0.78.0. Database baru tetap schema 50, `integrity_check` mengembalikan `ok`, dan
`foreign_key_check` kosong. Wheel `beeloft_one-0.78.0-py3-none-any.whl` berhasil dibuat dan memuat Command Center
serta aset dashboard. `git diff --check` lulus.

## Batas

Schema tetap 50. Tidak ada threshold lembur, roster shift, approval cuti/lembur, atau runtime connector vendor.
