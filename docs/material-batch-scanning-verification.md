# Verifikasi label QR dan scan batch bahan, v0.58

Tanggal: 14 September 2026. Base `962936f`; branch `feature/global-audit-trail` pada worktree lokal.
Semua pengujian memakai database sementara dan tidak menyentuh database operasional.

## Cakupan backend

Tiga acceptance test baru memeriksa kode QR stabil, lookup melalui QR dan referensi tanpa peka huruf
besar/kecil, original received quantity, status receipt aktif/dikoreksi, role admin/operator/viewer,
penolakan input tidak valid/tidak dikenal/tanpa autentikasi, SVG yang valid dan aksesibel, escaping metadata,
security header, serta larangan mencetak ulang label setelah receipt dikoreksi.

Seluruh suite backend Python 3.12 lulus: **292 test dalam 532,702 detik** (`python -m unittest
discover -s tests -p 'test_*.py'`).

## Browser dan client

Acceptance browser memeriksa fokus otomatis, scan keyboard dengan Enter, pemulihan setelah GET gagal,
akses viewer, pemuatan gambar QR, escaping nama bahan, tombol cetak, dan layout mobile/200%.

Seluruh regression suite Edge/Playwright lulus tanpa error JavaScript, termasuk semua alur produksi,
materials, purchasing, marketplace, approval, integrasi snapshot lokal, dan audit trail yang sudah ada.

## Pemeriksaan rilis

Kontrak `docs/openapi.json` memuat versi 0.58.0 dan endpoint scan/label batch. Schema tetap 46 karena kode
scan berasal dari UUID batch dan lookup tidak menulis ledger baru. `pip check`, kompilasi Python, client test,
pemeriksaan syntax seluruh **47 file** JavaScript, dan `git diff --check` lulus sebelum commit.

## Batas

Scan tidak mencatat pergerakan bahan. Kamera, pencetakan massal, template printer khusus, transfer lokasi
batch, serta connector runtime Jubelio/Mekari belum dicakup.
