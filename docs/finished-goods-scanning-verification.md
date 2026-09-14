# Verifikasi label QR dan scan barang jadi, v0.59

Tanggal: 14 September 2026. Base `afbee2f`; branch `feature/global-audit-trail` pada worktree lokal.
Semua pengujian memakai database sementara dan tidak menyentuh database operasional.

## Cakupan backend

Acceptance test memeriksa kode QR stabil, lookup melalui QR dan referensi tanpa peka huruf besar/kecil,
status aktif/dikoreksi, role admin/operator/viewer, input tidak valid/tidak dikenal/tanpa autentikasi, SVG
yang valid dan aksesibel, escaping metadata, security header, serta larangan mencetak ulang label receipt
yang sudah dikoreksi.

Seluruh suite backend Python 3.12 lulus: **295 test dalam 586,559 detik** (`python -m unittest
discover -s tests -p 'test_*.py'`).

## Browser dan client

Acceptance browser memeriksa fokus otomatis, scan keyboard dengan Enter, pemulihan setelah GET gagal,
akses viewer, pemuatan gambar QR, isi label, tombol cetak, aturan print-only, serta layout mobile/200%.

Seluruh regression suite Edge/Playwright lulus tanpa error JavaScript, termasuk alur scan barang jadi lalu
transfer, reservasi, picking, packing, shipping, retur, adjustment, dan stock opname. Client test juga lulus.

## Pemeriksaan rilis

Kontrak `docs/openapi.json` memuat versi 0.59.0 dan endpoint scan/label barang jadi. Schema tetap 46 karena
kode scan berasal dari UUID receipt dan lookup tidak menulis ledger baru. `pip check`, kompilasi Python,
pemeriksaan syntax seluruh **48 file** JavaScript, dan `git diff --check` lulus sebelum commit.

## Batas

Scan tidak membuat pergerakan stok. Kamera, pencetakan massal, template printer khusus, serta connector
runtime Jubelio/Mekari belum dicakup.
