# Jejak stok barang jadi, v0.62

Blueprint halaman 9 dan Phase 3 halaman 15 meminta traceability penerimaan, inventory reconciliation,
dan fulfillment. Ledger masing-masing tahap sudah tersedia. Milestone ini menyatukannya per lot
penerimaan, menggunakan transaksi baca yang sama untuk riwayat dan saldo saat ini.

## Cakupan

- Endpoint GET /api/finished-goods-receipts/{receipt_id}/traceability, untuk semua akun aktif.
- Penerimaan, pergerakan lokasi/status, reservasi, pick, pack, shipment, retur, adjustment, dan stock opname.
- Koreksi dan pelepasan reservasi tampil sebagai event terpisah. Status catatan asal tetap terlihat.
- Referensi induk pada tahap fulfillment, bukti scan asal bila tersedia, alasan, tanggal transaksi,
  waktu pencatatan, pelaku, dan tombol menuju rincian domain yang sudah tersedia.
- Cursor waktu pencatatan/event ID mencegah pergeseran halaman saat catatan baru ditambahkan.
- Saldo sekarang dan tautan ke batch bahan, bundle, serta final QC. Saldo tidak dijumlahkan dari kartu
  event karena adjustment hasil stock opname dan hitungan fisiknya mempunyai arti yang berbeda.

## Tampilan dan batas

Gunakan dialog, baris riwayat, warna tinta/emas, dan fokus keyboard yang sudah ada sesuai DESIGN.md
(ENERGY 2 / RHYTHM 2 / MOTION 1). Identitas lot dan saldo sekarang menjadi fokus, riwayat di bawahnya.
Tidak ada dependency atau migrasi; schema tetap 48. Report tidak mengubah stok maupun audit.

Riwayat satu lot dirakit di memori dengan pembaca domain yang sudah ada. Belum diuji untuk lot dengan
ribuan event; SQL union dan paging di database menjadi langkah saat ukuran riwayat membutuhkannya.
Saldo/status adalah posisi pada request terbaru, bukan snapshot historis yang dibekukan antarpaging.
Timeline dimulai dari penerimaan barang jadi; aktivitas produksi sebelumnya dibuka melalui tautan asal.
Transaksi finansial/settlement dan runtime connector Jubelio/Mekari di luar milestone ini.
