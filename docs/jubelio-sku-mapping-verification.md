# Verifikasi mapping SKU Jubelio, v0.43

Tanggal: 13 September 2026. Base `897a1d8`; branch `feature/jubelio-sku-mapping` pada worktree lokal.
Semua pengujian memakai database sementara.

## Cakupan backend

Lima acceptance test baru memeriksa empty state, penyimpanan dan retry idempotent, daftar berdasarkan
status, detail, riwayat bercursor, revision guard, perubahan dan pelepasan mapping, penggunaan ulang
identifier setelah dilepas, larangan identifier aktif ganda, race dua penulis, validasi, role,
rollback, trigger immutable, backup, serta migrasi schema 33 ke 34.

Seluruh suite backend lulus: **232 test dalam 317,621 detik** (`python -m unittest discover -s tests
-p 'test_*.py' -v`). Waktu proses end-to-end runner adalah 318,449 detik.

## Browser dan client

Edge/Playwright menjalankan seluruh browser regression suite. Admin membuka mapping dari Master SKU,
menyimpan identifier Jubelio dengan respons pertama hilang setelah commit, lalu memperoleh event yang
sama melalui retry. Detail, escaping, riwayat, coverage di layar Integrasi, hak baca viewer, ketiadaan
kontrol tulis bagi viewer, mobile 390 px, skala teks 200%, dan ketiadaan error JavaScript diperiksa.

## Pemeriksaan rilis

Kontrak OpenAPI memuat versi 0.43.0 dan empat operasi mapping. Database baru dan hasil migrasi memakai
schema 34. Dependency, kompilasi Python/JavaScript, client test, browser final, dan kebersihan Git
diperiksa sebelum commit rilis.

## Batas

Identifier belum diverifikasi ke akun Jubelio dan belum dipakai untuk lalu lintas vendor. Mapping
tidak mengubah stok atau status sync; ia hanya memberi connector identitas yang eksplisit dan dapat
diaudit.
