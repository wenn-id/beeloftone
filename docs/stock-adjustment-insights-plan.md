# Stock adjustment insights

## Tujuan

Menjawab pertanyaan blueprint tentang adjustment stok yang tidak normal memakai ledger barang jadi yang sudah
ada. Hasil harus menjelaskan alasan setiap flag dan mengarahkan pengguna ke catatan asal tanpa mengubah stok.

## Aturan

- Periode memakai `adjusted_date`; status aktif atau dikoreksi memakai posisi ledger saat laporan dimuat.
- Adjustment berisiko tinggi bila jumlah absolut mencapai ambang atau porsinya terhadap penerimaan mencapai
  ambang persentase.
- Adjustment perlu ditinjau bila berulang pada kombinasi SKU, lokasi, dan status stok yang sama atau sudah
  dikoreksi, selama tidak masuk risiko tinggi.
- Sumber manual dibedakan dari adjustment yang dibuat oleh stock opname.
- Ringkasan mengikuti filter pencarian, lokasi, status stok, sumber, dan status catatan. Filter klasifikasi
  diterapkan setelah ringkasan agar pengguna tetap melihat konteks periode.
- Endpoint dan UI hanya membaca. Tidak ada adjustment, koreksi, write-off, approval, atau audit event baru.

## Antarmuka

- `GET /api/stock-adjustment-insights` menerima tanggal akhir, panjang periode, tiga ambang audit, pencarian,
  lokasi, status stok, sumber, status catatan, klasifikasi, limit, dan offset.
- Dialog menyediakan loading, error dengan retry, ringkasan, empty state, pagination, serta drill-down ke
  adjustment asal.
- Semua nilai ledger di-escape. Dialog harus tetap dapat dipakai pada lebar 390 px dan zoom teks 200%.

## Batas

Flag adalah sinyal audit, bukan bukti kehilangan atau fraud. Nilai rupiah tidak dihitung karena valuasi stok per
lot belum tersedia. Runtime connector Jubelio/Mekari tetap ditunda sampai akses API resmi tersedia.
