# Verifikasi scan picking marketplace, v0.60

Tanggal: 14 September 2026. Base `f0331ca`; branch `feature/global-audit-trail` pada worktree lokal.
Seluruh pengujian memakai database sementara dan tidak menyentuh data operasional.

## Cakupan backend

Acceptance test memeriksa scan SKU dan QR lot tanpa peka huruf besar/kecil, penolakan kode salah/kosong,
penyimpanan bukti scan, idempotent retry, role, saldo, koreksi, concurrent pick, direct-write guard, backup,
serta migrasi catatan lama schema 46 → 47 tanpa kehilangan pick.

Seluruh suite backend Python 3.12 lulus: **295 test dalam 265,440 detik** (`python -m unittest
discover -s tests -p 'test_*.py'`). Acceptance picking juga diulang setelah finalisasi migrasi dan lulus.

## Browser dan client

Acceptance browser memeriksa fokus scanner, feedback kode salah sebelum request, QR lot yang valid,
lost-response reload/retry, bukti scan pada detail, role, serta layout mobile/200%.

Seluruh regression suite Edge/Playwright lulus tanpa error JavaScript, termasuk penerimaan dan scan barang
jadi, validasi scan picking, lost-response retry, packing, shipping, retur, reconciliation, approval, dan audit.
Client test lulus.

## Pemeriksaan rilis

Kontrak `docs/openapi.json` memuat versi 0.60.0 dengan `scanned_code` wajib pada payload pick. Database baru
dan migrasi legacy mencapai schema 47. `pip check`, kompilasi Python, pemeriksaan syntax seluruh **48 file**
JavaScript, dan `git diff --check` lulus sebelum commit.

## Batas

Wave/tote picking, picker assignment, kamera, serta connector runtime Jubelio/Mekari belum dicakup.
