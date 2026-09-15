# Verifikasi layar People, v0.77

Tanggal: 15 September 2026. Branch `feature/global-audit-trail` pada worktree lokal. Semua pengujian memakai
database sementara dan tidak mengubah data operasional.

## Acceptance coverage

Browser acceptance mencakup retry saat API gagal, data kosong, escaping teks, pembuatan dan penonaktifan karyawan,
pencatatan hadir, koreksi menjadi cuti, dua revisi kehadiran, serta hak admin/operator/viewer. Layout diperiksa pada
lebar 390 px, zoom teks 200%, dan tema gelap.

## Hasil

Acceptance browser People dan regresi browser lengkap lulus di Microsoft Edge. Seluruh alur dashboard setelah
People juga selesai tanpa error JavaScript. Screenshot dialog pada lebar 390 px dalam tema gelap diperiksa secara
visual: field, tombol, teks, dan ringkasan dua kolom tidak terpotong atau keluar dari dialog.

Regresi backend penuh lulus **325 tes dalam 536,799 detik**. Tes target workforce dan shell web setelah perubahan
terakhir lulus **4 tes dalam 2,542 detik**. Client checks dan pemeriksaan syntax **60 file JavaScript** lulus;
kompilasi Python serta `pip check` juga bersih.

Kontrak tersimpan sama persis dengan OpenAPI runtime versi 0.77.0. Database baru tetap memakai schema 50;
`integrity_check` mengembalikan `ok` dan `foreign_key_check` kosong. Wheel
`beeloft_one-0.77.0-py3-none-any.whl` berhasil dibuat dan memuat aset dashboard serta `workforce.sql`.

Dua belas pasangan warna teks utama pada tema terang dan gelap diperiksa dengan contrast checker. Seluruhnya
lulus rasio minimum 4,5:1 untuk teks normal; rasio terendah 5,76:1. `git diff --check` lulus.

## Batas

Schema tetap 50. Runtime connector Mekari/Jubelio tidak dicakup.
