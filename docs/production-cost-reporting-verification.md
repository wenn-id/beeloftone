# Verifikasi laporan biaya produksi, v0.35

Tanggal: 13 September 2026. Base `e81efd8`; branch `feature/production-cost-reporting` pada
worktree lokal. Pengujian memakai database sementara dan tidak menyentuh data bisnis.

## Cakupan backend

Acceptance test memeriksa biaya bahan dari konsumsi aktif (`used + waste`) memakai harga satuan PO
yang terkunci, pembulatan HALF_UP per baris ke dua angka desimal, biaya jahit internal/makloon aktif,
koreksi job, subtotal biaya yang sudah diketahui, biaya per target dan hasil jadi, role viewer,
autentikasi, order yang tidak ada, serta perhitungan ulang sesudah backup dipulihkan.

Coverage dinyatakan lengkap hanya bila order memiliki sumber pengeluaran bahan, seluruh batch yang
dikonsumsi memiliki harga PO, dan seluruh pengeluaran aktif sudah dilaporkan sebagai terpakai atau
waste. Kondisi kosong, batch tanpa harga, dan sisa pengeluaran yang belum dilaporkan menghasilkan
gap terstruktur serta `total_cost: null`; subtotal yang diketahui tetap tersedia. Seluruh regression
suite berisi **197 tests** dan lulus dalam **231,786 detik**.

## Browser dan client

Browser QA membuka laporan dari order produksi dan memeriksa biaya bahan dan jahit yang eksak,
coverage gap yang eksplisit, retry setelah error, hak baca viewer, escaping teks, viewport mobile,
dan skala teks 200%. Seluruh Edge/Playwright suite lulus tanpa error JavaScript. Pemeriksaan syntax
untuk aplikasi dan seluruh browser test, serta unit test client, juga lulus.

## Batas

Total saat ini mencakup bahan yang dapat ditelusuri ke harga PO dan biaya jahit internal/makloon.
Upah tenaga kerja internal, finishing, QC, packaging, freight, overhead, jurnal, dan integrasi
eksternal belum masuk perhitungan. Endpoint bersifat read-only dan schema tetap pada versi 29.
