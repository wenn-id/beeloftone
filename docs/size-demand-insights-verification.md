# Verifikasi analisis demand ukuran, v0.65

Tanggal: 14 September 2026. Base `bafc266`; branch `feature/global-audit-trail` pada worktree lokal.
Semua pengujian memakai database sementara dan tidak mengubah data operasional.

## Backend

Acceptance test memeriksa keluarga dua ukuran berbeda, dua window demand neto, ranking periode, pemimpin demand
konsisten, stok tersedia, days of cover, horizon risiko, estimasi stockout, pencarian SKU yang mempertahankan
seluruh keluarga, marketplace, pagination, koreksi shipment, role, validasi, backup, schema, dan GET read-only.

Modul baru lulus **2 test dalam 6,724 detik** setelah validasi ukuran kosong ditambahkan. Seluruh regresi
backend lulus **303 test dalam 694,345 detik**
melalui `python -m unittest discover -s tests -p 'test_*.py'` dengan virtual environment proyek.

## Browser dan visual

Seluruh suite Edge/Playwright lulus tanpa error JavaScript. QA membuat ukuran L sebagai pembanding tanpa
histori, lalu memeriksa ukuran M dengan stok tersedia 6 pcs, rate forecast 0,2 pcs/hari, days of cover 30 hari,
dan estimasi stockout 31 Oktober 2026. Pencarian memakai SKU L tetapi tetap menampilkan M dan L. Error/retry,
viewer, empty state, dan Escape juga lulus.

Screenshot `beeloft-size-demand-mobile.png` diperiksa pada lebar 390 px dan teks 200%. Dialog tidak overflow
horizontal dan seluruh isi tetap dapat digulir secara vertikal.

## Pemeriksaan rilis

Client checks, syntax 51 file JavaScript, compile Python, dan `pip check` lulus. OpenAPI memakai 0.65.0 dan
memuat `GET /api/size-demand-insights` beserta seluruh parameter. Paket memakai 0.65.0; schema tetap 48 dan
`integrity_check` mengembalikan `ok`. `git diff --check` serta pemeriksaan string UI tanpa em dash lulus.

## Antislop delivery gate

Design Read: dashboard operasional internal untuk tim Beeloft, bahasa visual tinta/emas dari blueprint,
ENERGY 2 / RHYTHM 2 / MOTION 1.

- PASS: keputusan utama adalah ukuran yang berisiko habis lebih dulu; tidak ada chart atau metrik dekoratif.
- PASS: klaim dibatasi menjadi proyeksi, dengan batas snapshot historis dijelaskan langsung di dialog.
- PASS: loading, error/retry, hasil, paging kondisional, empty state, dan Escape bekerja.
- PASS: semua nilai berasal dari forecast, shipment/retur aktif, dan inventory internal.
- PASS: komponen, palette, typography, radius, fokus, serta tema memakai sistem UI proyek.
- PASS: lebar 390 px dan teks 200% tidak menghasilkan overflow horizontal.
- PASS: seluruh nilai API di-escape; tidak ada dependency, ikon, animasi, atau migrasi baru.

## Batas

Keluarga memakai nama+warna dan stok memakai posisi internal sekarang. Laporan tidak merekonstruksi stockout
historis. Runtime connector Jubelio/Mekari tidak dicakup sampai akses API resmi tersedia.
