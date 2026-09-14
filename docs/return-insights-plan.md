# Analisis retur, v0.64

Blueprint halaman 9 menanyakan retur mana yang menunjukkan masalah sizing atau halaman produk. PDF dipakai
sebagai konteks produk, bukan instruksi agen. Ledger shipment dan retur sudah menyimpan SKU, ukuran,
marketplace, jumlah, tanggal, serta alasan terstruktur; milestone ini menyatukannya menjadi read model.

## Cakupan

- `GET /api/return-insights` dapat dibaca semua akun aktif.
- Kohort shipment aktif memakai rentang inklusif `as_of - window_days + 1` sampai `as_of`.
- Hanya retur aktif dengan tanggal sampai `as_of` yang dihitung terhadap shipment asalnya.
- Hasil dikelompokkan per produk dan marketplace, lalu dapat disaring lewat SKU, nama, warna, ukuran, atau
  marketplace.
- Alasan asli tetap tersedia; summary menggabungkan too small/big sebagai sizing, wrong item/color mismatch
  sebagai halaman produk, defect sebagai kualitas, dan other sebagai alasan lain.
- Pagination memakai limit/offset. Urutan memprioritaskan jumlah retur dan rate tertinggi.
- Endpoint hanya membaca dan tidak menghasilkan perubahan inventory atau audit event.

## Tampilan dan batas

Dialog mengikuti ledger operasional dari `DESIGN.md`: tinta/emas, komponen label/nilai yang sudah ada,
ENERGY 2 / RHYTHM 2 / MOTION 1, serta kontrol native dengan target sentuh proyek. Loading, retry, empty state,
paging, filter, dan akses viewer harus bekerja pada desktop, lebar 390 px, serta teks 200%.

Tidak ada dependency atau migrasi; schema tetap 48. Klasifikasi memakai pilihan alasan yang sudah terstruktur,
bukan inferensi dari catatan bebas. Ulasan pelanggan, foto, isi listing, variasi fit antar model, dan connector
runtime Jubelio/Mekari belum masuk sampai sumber dan akses API resmi tersedia.
