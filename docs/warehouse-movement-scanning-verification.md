# Verifikasi scan pergerakan gudang, v0.61

Tanggal: 14 September 2026. Base `2d4bd2e`; branch `feature/global-audit-trail` pada worktree lokal.
Seluruh pengujian memakai database sementara dan tidak menyentuh data operasional.

## Cakupan backend

Acceptance test memeriksa scan SKU dan QR lot tanpa peka huruf besar/kecil, penolakan kode salah/kosong,
penyimpanan bukti scan, global audit, idempotent retry, role, saldo, koreksi, concurrent movement,
direct-write guard, backup, migrasi legacy schema 47 → 48, serta pemulihan migrasi parsial.

Seluruh suite backend Python 3.12 lulus: **295 test dalam 266,022 detik** (`python -m unittest
discover -s tests -p 'test_*.py'`). Acceptance pergerakan gudang juga dijalankan terpisah dan lulus.

## Browser dan client

Seluruh regression suite Edge/Playwright lulus tanpa error JavaScript. Acceptance gudang memeriksa fokus
scanner, feedback kode salah sebelum request, QR lot valid, lost-response reload/retry, bukti scan pada
rincian, transfer, release/damaged, role, koreksi, serta layout mobile/200%. Client test lulus.

## Pemeriksaan rilis

Kontrak `docs/openapi.json` memuat versi 0.61.0 dan mewajibkan `scanned_code` pada payload pergerakan.
Database baru mencapai schema 48 dengan trigger scan aktif. `pip check`, kompilasi Python, pemeriksaan
syntax seluruh **48 file** JavaScript, dan `git diff --check` lulus sebelum commit.

## Batas

Master bin, scan lokasi tujuan, kamera, serta connector runtime Jubelio/Mekari belum dicakup.
