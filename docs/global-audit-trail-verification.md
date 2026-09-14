# Verifikasi global audit trail, v0.55

Tanggal: 14 September 2026. Branch `feature/global-audit-trail` pada worktree lokal. Semua pengujian
memakai database sementara dan tidak menyentuh database operasional.

## Cakupan backend

Acceptance test memeriksa pencatatan atomik dan tepat sekali, retry serta konflik idempotensi, snapshot
pelaku, kategori approval, pencarian/filter/pagination, ringkasan payload vendor, penyamaran credential,
role guard, validasi rentang tanggal, detail event, trigger immutable, backup, dan migrasi schema 44 → 45.

Seluruh suite backend Python 3.12 lulus: **281 test dalam 797,576 detik** (`python -m unittest
discover -s tests -p 'test_*.py'`). `compileall` dan pemeriksaan dependency virtual environment proyek
juga lulus.

## Browser dan client

Acceptance browser memeriksa kegagalan GET dan retry, pencarian/filter kategori, drill-down detail,
escaping teks sumber, visibilitas khusus admin, respons 403 untuk viewer, layout mobile 390 px, dan
skala teks 200%. Seluruh regression suite Edge/Playwright lulus tanpa error JavaScript. Seluruh **46
file** JavaScript juga lulus pemeriksaan syntax.

## Pemeriksaan rilis

Kontrak `docs/openapi.json` memuat versi 0.55.0 dan endpoint daftar/detail audit. Schema database 45,
`compileall`, pemeriksaan dependency, syntax JavaScript, dan `git diff --check` diverifikasi sebelum
commit.

## Batas

Audit mencakup write bisnis idempotent melalui API pusat. Provisioning/disable akun lewat CLI,
login/logout browser, dan event keamanan OIDC belum masuk ledger. Daftar besar dari impor vendor
disimpan sebagai hitungan record, sedangkan payload sumber tetap berada di tabel snapshot domain.
