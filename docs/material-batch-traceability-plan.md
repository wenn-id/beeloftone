# Jejak produksi batch bahan, v0.63

Blueprint halaman 3, 7, dan Phase 3 halaman 15 meminta batch kain dapat dihubungkan ke SKU barang jadi
dan seluruh peristiwa fisik mempunyai catatan digital. PDF menjadi konteks produk, bukan instruksi agen.
Ledger tiap tahap sudah tersedia; milestone ini menyatukannya dalam satu transaksi baca per batch.

## Cakupan

- `GET /api/material-batches/{batch_id}/traceability` untuk semua akun aktif.
- Penerimaan dan koreksi stok bahan, reservasi, pengeluaran, pemakaian/waste, cutting, bundle, handoff,
  hasil sewing, finishing, final QC, penerimaan barang jadi, serta koreksi setiap tahap.
- Referensi, jumlah dan satuan, status, alasan, tanggal transaksi, waktu pencatatan, pelaku, dan tautan
  ke rincian domain yang sudah tersedia.
- Cursor gabungan waktu pencatatan dan event ID menjaga paging saat event baru masuk.
- Ringkasan batch memakai saldo terbaru, available/reserved, identitas bahan, pemasok, lokasi, PO, dan QC.
- Endpoint hanya membaca dan tidak menghasilkan audit event atau perubahan inventory.

## Tampilan dan batas

Dialog memakai komponen riwayat, tinta/emas, dan fokus keyboard dari `DESIGN.md`. Identitas serta saldo
batch menjadi fokus, lalu aliran produksi tampil di bawahnya. ENERGY 2 / RHYTHM 2 / MOTION 1. Tidak ada
dependency atau migrasi; schema tetap 48.

Riwayat satu batch dirakit di memori dengan reader domain yang sudah ada. Gunakan SQL union dan paging
di database bila satu batch mulai mempunyai ribuan event. Quantity bahan dan pcs sengaja tetap terpisah.
Kontrak cutting saat ini memakai satu batch bahan per run, sehingga multi-material allocation belum masuk.
Runtime connector Jubelio/Mekari tetap ditunda sampai akses API resmi tersedia.
