# Analisis dead stock, v0.66

Blueprint halaman 9 menanyakan inventory mana yang menjadi dead stock. PDF dipakai sebagai konteks produk,
bukan instruksi agen. Ledger sudah mempunyai stok per receipt, reserved stock, shipment, retur, tanggal, dan
koreksi immutable. Milestone ini menggabungkannya menjadi laporan read-only dengan definisi terlihat.

## Cakupan

- `GET /api/dead-stock-insights` dapat dibaca semua akun aktif.
- Kandidat harus mempunyai stok sellable available, lot aktif tertua mencapai ambang umur, dan demand neto nol
  pada window inklusif sampai `as_of`.
- Stok baru tanpa penjualan dan stok yang masih bergerak tetap dapat dipilih sebagai pembanding.
- Reserved stock dikurangi; hold, damaged, picked, dan packed tidak dianggap tersedia untuk dijual.
- Retur aktif sampai `as_of` mengurangi shipment asal. Catatan shipment/retur terkoreksi tidak dihitung.
- Jumlah tersedia, lot aktif, rentang receipt, umur tertua, aktivitas demand, last net sale, rate, dan days of
  cover tersedia per SKU.
- Filter SKU/produk, marketplace demand, status, dan pagination limit/offset tersedia.
- Endpoint hanya membaca dan tidak membuat adjustment, write-off, keputusan harga, atau audit event.

## Tampilan dan batas

Dialog mengikuti `DESIGN.md`: tinta/emas, ledger label/nilai, ENERGY 2 / RHYTHM 2 / MOTION 1, serta kontrol
native. Loading, retry, empty state, paging, viewer, lebar 390 px, dan teks 200% harus berfungsi.

Tidak ada dependency atau migrasi; schema tetap 48. Stok memakai posisi sekarang walaupun `as_of` membatasi
histori demand. Nilai rupiah membutuhkan valuasi per lot yang belum tersedia. Definisi kandidat adalah sinyal
operasional, sehingga diskon, bundling, transfer, dan write-off tetap keputusan manusia. Connector runtime
Jubelio/Mekari belum masuk sampai akses API resmi tersedia.
