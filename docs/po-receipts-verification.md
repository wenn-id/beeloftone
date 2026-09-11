# Penerimaan bahan dari PO — v0.15

Base: `0235701`, branch `feature/core-materials`, worktree lokal. Mengikuti purchasing
pada blueprint halaman 7: penerimaan bahan layak pakai, batch, lokasi dan hubungan ke PO.

## Perilaku

Satu penerimaan membuat satu batch dan ledger penerimaan dengan hubungan PO dalam transaksi
yang sama. Admin/operator mencatat; viewer membaca. Pemasok berasal dari snapshot PO.
Jumlah diterima bersih dihitung dari penerimaan yang belum dibalik, bukan saldo rak setelah
pengeluaran. Sisa per bahan membatasi penerimaan berikutnya. PO yang dibatalkan menolak
penerimaan, dan PO dengan penerimaan aktif menolak pembatalan. Koreksi admin memakai ledger
lama dengan pemeriksaan stok, reservasi dan pemakaian yang sudah ada.

Schema 10 menambahkan tabel hubungan immutable serta guard database. Penerimaan manual lama
tetap tanpa hubungan PO. Tidak ada perubahan pcs produksi atau pemasok historis.

## Bukti pengujian

- RED: empat tes fitur baru gagal sebelum implementasi karena endpoint/tabel belum tersedia.
- `python -m unittest discover -s tests -q`: **80 tests OK**.
- Tes baru mencakup pecahan, penerimaan parsial/lengkap, over-receipt, role, rollback,
  retry setelah koreksi/pembatalan, transaksi bersamaan, reservasi/pengeluaran yang menghalangi
  koreksi, migrasi dari schema 9, backup/restore, dan satuan pcs.
- `tests/run_browser.py --channel msedge`: **semua suite PASS**, tanpa JavaScript error.
- Browser menguji partial → complete → koreksi, koneksi terputus setelah commit dan retry
  sesudah reload, tautan batch/PO, stok otomatis diperbarui, role, lebar 320/390/768 px dan
  font 200%. Penerimaan kedua dikoreksi melalui API; penerimaan pertama dikoreksi melalui UI.
- `node tests/test_client.mjs`: **Client checks PASS**, **CSV client checks PASS**.
- `node --check beeloft/static/app.mjs`: **PASS**.
- `python -m pip check`: **No broken requirements found**.
- OpenAPI dibuat ulang dari aplikasi v0.15.0, termasuk endpoint receipt dan model input.

Suite Python mengeluarkan warning Pydantic tentang metadata alias `Idempotency-Key` pada
salah satu run; seluruh tes autentikasi/idempotency tetap lulus.

## Review dan visual

Reviewer terpisah menemukan daftar stok belum diperbarui setelah receipt dari dialog PO.
Sudah diperbaiki dan diverifikasi lewat browser: tutup dialog setelah menerima, batch baru
langsung muncul di daftar stok. Review lanjutan tidak menemukan masalah produk lain.
Uji 200% menemukan minimum lebar dropdown memperlebar grid; kolom dan anak grid kini dapat
menyusut. Tes browser lulus setelah perbaikan.

Screenshot `beeloft-po-receipt-mobile.png` dan `beeloft-po-receipts.png` di folder output
`beeloft-one-qa` sudah diperiksa. Form dan rincian menggunakan dialog yang dapat digulir.

## Berikutnya

Pemeriksaan bahan masuk dengan accepted/hold/reject dan pelepasan stok. Increment ini hanya
menerima bahan yang sudah layak pakai; belum ada retur sebagian, penutupan sisa PO, pembayaran,
atau pengiriman dokumen ke pemasok.
