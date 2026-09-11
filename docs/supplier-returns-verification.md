# Verifikasi retur supplier dan penutupan PO — v0.17

Tanggal: 11 September 2026. Base `5cd0661`; branch `feature/supplier-returns`.
Pengerjaan dan pengujian memakai worktree lokal serta database sementara.

## Hasil

- Baseline sebelum perubahan: 86 backend tests OK.
- Tes fitur awal gagal karena endpoint retur/closure belum tersedia dan pembatalan
  lama masih mengizinkan reject yang belum diretur. Setelah implementasi, skenario ini lulus.
- Verifikasi akhir: `python -m unittest discover -s tests -q` → **96 tests OK**, 58,111 detik.
- Sepuluh tes retur/closure mencakup retur parsial, koreksi penuh, retry, konflik referensi,
  validasi jumlah/tanggal, izin admin, rollback, race retur/retur dan closure/koreksi,
  guard SQLite, larangan koreksi reject di bawah jumlah retur, penutupan dengan sisa,
  filter status, PR asal, penggunaan stok setelah closure, migrasi schema 11,
  retur legacy PO dibatalkan, persistence dan backup.
- `node tests/test_client.mjs` → Client checks PASS; CSV client checks PASS.
- `node --check beeloft/static/app.mjs` → PASS.
- `python -m pip check` → No broken requirements found.
- OpenAPI diekspor ulang dari database sementara; versi 0.17.0 dan ketiga endpoint
  baru diverifikasi. Status filter PO memuat `closed`.
- `git diff --check` → PASS; peringatan normal konversi LF/CRLF tidak mengubah isi.

## Browser

Runner `tests/run_browser.py` memakai Playwright dan Edge dengan server/database
sementara. Seluruh suite lama serta `browser_supplier_returns.cjs` lulus, tanpa
JavaScript error. Suite baru memeriksa:

- Operator/viewer hanya membaca; admin mencatat retur dan menutup PO.
- Retur parsial, maksimum jumlah input, teks referensi dengan karakter HTML,
  respons hilang setelah server menyimpan, reload dan retry tanpa duplikasi.
- Koreksi retur kembali ke rincian QC; saldo rak tetap; retur akhir menyelesaikan sisa.
- Tombol closure hanya muncul setelah hold/retur selesai; shortfall terlihat sebelum
  dan sesudah closure; penerimaan/koreksi QC/retur tidak ditawarkan sesudah closure.
- Filter Ditutup, pembacaan oleh viewer, layout 320/390/768 px dan skala teks 200%.

Screenshot form retur mobile dan rincian PO ditutup diperiksa secara visual:
label, angka, referensi, alasan, serta tombol terbaca tanpa overflow. Screenshot
tersimpan lokal di folder `outputs/beeloft-one-qa`, di luar repository.

## Review dan batas

Review kode independen terhadap store/API/UI, migration guards, idempotency, izin,
PR, dan ledger tidak menemukan masalah yang perlu ditindaklanjuti. Setelah review,
indikator PO ditutup ditambahkan ke batch agar tombol koreksi penerimaan langsung
juga tersembunyi; suite backend/browser dijalankan ulang setelah perubahan tersebut.

Penutupan PO permanen. Belum mencakup reopening, retur stok yang sudah diterima layak,
credit note/pembayaran, cetak surat retur, atau konfirmasi dari pemasok. Retur yang
dicatat pada PO legacy yang sudah dibatalkan langsung final. Tidak ada data bisnis,
pesan pemasok, main, atau remote GitHub yang diubah dalam langkah ini.
