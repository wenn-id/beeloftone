# Verifikasi supplier dan purchase order (v0.14)

Base `b914e73` · branch `feature/core-materials` · dikerjakan di worktree lokal.

## Bukti otomatis

- `python -m unittest discover -s tests -q` → **76 tests OK**.
- `node tests/test_client.mjs` → **Client checks PASS** dan **CSV client checks PASS**.
- `node --check beeloft/static/app.mjs` → **PASS**.
- `python -m pip check` → **No broken requirements found**.
- `git diff --check` → **PASS** (hanya peringatan normal Git tentang konversi LF/CRLF).
- OpenAPI dibuat ulang dari `create_app()` dan memuat versi `0.14.0`, `/api/suppliers`, serta `/api/purchase-orders`.

## Browser QA

`tests/run_browser.py --channel msedge` lulus untuk seluruh suite: materials, BOM, reservations,
consumption, purchase requests, purchase orders, dan smoke. Suite PO mencakup master pemasok,
PO dari PR yang disetujui, pembulatan total, penolakan melewati anggaran, retry setelah respons
hilang dan reload, role operator/viewer, tautan PO↔PR, pembatalan, mobile 320–768 px, serta skala
font 200%.

Screenshot QA tersimpan di folder output lokal `beeloft-one-qa`:

- `beeloft-po-form-mobile.png`
- `beeloft-purchase-order.png`

Keduanya diperiksa dan tidak menunjukkan overflow horizontal pada dialog.

## Review

Permintaan independent review untuk increment ini dikirim ke reviewer terpisah, tetapi layanan
review mengembalikan batas penggunaan akun sebelum menghasilkan laporan. Tidak ada temuan review
yang bisa ditindaklanjuti; verifikasi di atas adalah hasil yang tersedia.

## Batas increment

PO hanya pencatatan internal. Belum ada pengiriman ke pemasok, penerimaan barang, partial fulfillment,
atau pengurangan stok. Langkah roadmap berikutnya adalah receipt yang terhubung ke PO dengan jumlah
diterima dan sisa.
