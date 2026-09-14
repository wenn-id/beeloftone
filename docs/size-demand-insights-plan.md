# Analisis demand ukuran, v0.65

Blueprint halaman 9 menanyakan ukuran mana yang berulang kali habis lebih dulu. PDF dipakai sebagai konteks
produk, bukan instruksi agen. Ledger belum mempunyai snapshot stok harian historis, sehingga milestone ini
menjawab bagian yang dapat dibuktikan: pola demand per ukuran dan risiko stockout dari stok saat ini.

## Cakupan

- `GET /api/size-demand-insights` dapat dibaca semua akun aktif.
- Produk dengan nama dan warna yang sama menjadi satu keluarga; hanya keluarga dengan minimal dua nilai
  ukuran terisi dan berbeda yang ditampilkan.
- Demand neto memakai dua window yang sama dengan forecast SKU: periode terbaru berbobot 70%, sebelumnya 30%.
- Peringkat demand lama dan terbaru menunjukkan ukuran yang konsisten memimpin kedua periode.
- Stok tersedia, forecast harian, days of cover, risk rank, dan estimasi tanggal stockout tersedia per ukuran.
- Horizon pengguna membedakan stok habis, risiko dalam horizon, risiko setelah horizon, dan belum ada demand.
- Pencarian SKU/ukuran mempertahankan semua ukuran dalam keluarga; filter marketplace hanya membatasi demand.
- Pagination memakai limit/offset. Endpoint hanya membaca dan tidak membuat transaksi atau audit event.

## Tampilan dan batas

Dialog mengikuti `DESIGN.md`: tinta/emas, ledger label/nilai, ENERGY 2 / RHYTHM 2 / MOTION 1, serta kontrol
native. Loading, retry, empty state, paging, akses viewer, lebar 390 px, dan teks 200% wajib bekerja.

Tidak ada dependency atau migrasi; schema tetap 48. Nama+warna adalah identitas keluarga sementara sampai
master style tersedia. Stok adalah posisi internal saat laporan dimuat dan bukan snapshot historis pada akhir
setiap window. Klaim UI dibatasi menjadi risiko/proyeksi. Promosi, musiman, lead time SKU, dan connector runtime
Jubelio/Mekari belum masuk sampai datanya tersedia.
