# Verifikasi analisis dead stock, v0.66

Tanggal: 14 September 2026. Base `b362630`; branch `feature/global-audit-trail` pada worktree lokal.
Semua pengujian memakai database sementara dan tidak mengubah data operasional.

## Backend

Acceptance test memeriksa saldo available per receipt, reserved stock, umur lot, shipment/retur neto, kandidat
dead stock, stok baru tanpa penjualan, stok bergerak, rate, days of cover, histori terakhir, koreksi shipment,
filter, marketplace, status, pagination, role, validasi, backup, schema, dan GET read-only.

`tests/test_dead_stock_insights.py` lulus **2 tes** dalam 10,528 detik. Regresi backend penuh lulus
**305 tes** dalam 1099,907 detik.

## Browser dan visual

QA browser memakai SKU yang shipment aktifnya sudah dikoreksi tetapi masih mempunyai 6 pcs available dan lot
berumur 105 hari. Error/retry, viewer, kandidat, penjualan neto kosong, status tanpa hasil, lebar 390 px, teks
200%, dan overflow horizontal diperiksa. Screenshot disimpan pada folder QA v0.66.

Seluruh Edge QA lulus tanpa error JavaScript, termasuk alur dead stock dan seluruh modul lama. Pemeriksaan
visual screenshot 390 px pada zoom 200% memastikan dialog tetap terbaca, dapat digulir, dan tidak mempunyai
overflow horizontal.

## Release checks

Client tests, syntax **52 file JavaScript**, kompilasi Python, dan `pip check` lulus. OpenAPI serta paket
memakai versi 0.66.0. Database baru mencapai schema 48; `integrity_check` mengembalikan `ok` dan
`foreign_key_check` kosong. `git diff --check` dan pemeriksaan string UI tanpa em dash lulus.

## Batas

Posisi stok bersifat current-state dan nilai rupiah belum dihitung. Laporan memberi kandidat untuk diperiksa,
bukan membuat adjustment atau write-off. Runtime connector Jubelio/Mekari tidak dicakup.
