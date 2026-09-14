# Verifikasi label QR dan scan bundle, v0.56

Tanggal: 14 September 2026. Base `4cffeea`; branch `feature/global-audit-trail` pada worktree lokal.
Semua pengujian memakai database sementara dan tidak menyentuh database operasional.

## Cakupan backend

Tiga acceptance test baru memeriksa kode QR stabil, lookup melalui QR dan Bundle ID, pencarian tanpa peka
huruf besar/kecil, role admin/operator/viewer, status bundle yang sudah dikoreksi, penolakan input tidak
valid/tidak dikenal/tanpa autentikasi, SVG yang valid dan aksesibel, escaping metadata, security header,
serta larangan mencetak ulang label bundle yang sudah dikoreksi.

Seluruh suite backend Python 3.12 lulus: **284 test dalam 394,801 detik** (`python -m unittest
discover -s tests -p 'test_*.py'`). `compileall` dan pemeriksaan dependency virtual environment proyek
juga lulus.

## Browser dan client

Acceptance browser memeriksa fokus otomatis, scan keyboard dengan Enter, pemulihan setelah GET gagal,
akses viewer, pemuatan gambar QR, isi label, tombol cetak, aturan print-only, layout mobile 390 px, dan
skala teks 200%. Seluruh regression suite Edge/Playwright lulus tanpa error JavaScript. Seluruh **47
file** JavaScript juga lulus pemeriksaan syntax.

## Pemeriksaan rilis

Kontrak `docs/openapi.json` memuat versi 0.56.0 dan endpoint scan/label. Schema tetap 45 karena kode scan
dihitung dari UUID bundle dan lookup bersifat read-only. `compileall`, dependency check, seluruh syntax
JavaScript, dan `git diff --check` diverifikasi sebelum commit.

## Batas

Scan membuka lineage bundle dan belum menjadi event serah-terima dua pihak atau perpindahan WIP. Kamera
browser, pencetakan massal, template printer khusus, serta split/merge bundle belum dicakup.
