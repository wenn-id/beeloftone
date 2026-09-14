# Verifikasi serah-terima bundle dua pihak, v0.57

Tanggal: 14 September 2026. Base `ff97175`; branch `feature/global-audit-trail` pada worktree lokal.
Semua pengujian memakai database sementara dan tidak menyentuh database operasional.

## Cakupan backend

Lima acceptance test baru memeriksa pengiriman dan penerimaan idempotent, akun pengirim/penerima yang
berbeda, perubahan custody setelah penerimaan, satu handoff pending per bundle, pembatalan oleh admin,
role viewer, lokasi asal berantai, histori cursor, pencarian global audit, race dua penerima, rollback,
backup, trigger immutable, dan migrasi schema 45 → 46. Penerimaan juga dipastikan tidak mengubah saldo WIP.

Seluruh suite backend Python 3.12 lulus: **289 test dalam 566,074 detik** (`python -m unittest
discover -s tests -p 'test_*.py'`).

## Browser dan client

Acceptance browser memeriksa alur dari scan Bundle ID, pengiriman oleh admin, konfirmasi oleh operator,
lokasi custody, histori dan retry setelah respons GET gagal, escaping tujuan, serta tombol yang sesuai role.

Seluruh regression suite Edge/Playwright lulus tanpa error JavaScript, termasuk alur produksi,
marketplace, integrasi, approval, dan audit trail yang sudah ada.

## Pemeriksaan rilis

Kontrak `docs/openapi.json` memuat versi 0.57.0 dan empat endpoint handoff. Database baru dan hasil
migrasi memakai schema 46. `pip check`, kompilasi Python, client test, pemeriksaan syntax seluruh **47 file**
JavaScript, dan `git diff --check` lulus sebelum commit.

## Batas

Custody bundle tidak memindahkan saldo WIP atau membuat job sewing. Lokasi masih berupa teks bebas. Kamera,
tanda tangan, foto, notifikasi, split/merge bundle, dan sinkronisasi offline belum dicakup.
