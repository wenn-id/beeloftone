# Supplier performance insights

## Tujuan

Menjawab kebutuhan blueprint mengenai ketepatan supplier serta usable versus purchased quantity dari ledger PO,
penerimaan bahan, dan incoming QC yang sudah tersedia. Laporan memberi bukti dan tautan sumber tanpa membuat
rating permanen atau mengubah transaksi.

## Aturan

- Populasi laporan adalah PO approved, tidak dibatalkan, dengan `expected_date` dalam periode.
- Ketepatan awal membandingkan tanggal kedatangan aktif pertama dengan `expected_date`. Receipt yang dikoreksi
  dan intake QC yang dibatalkan tidak dihitung.
- Supplier perlu perhatian bila memiliki PO terlambat tanpa kedatangan, kedatangan awal terlambat, PO lewat
  jadwal yang belum lengkap, penutupan dengan kekurangan, reject, atau hold aktif.
- Ordered dan received berasal dari baris PO. Hasil QC berasal dari intake aktif dan dikelompokkan per satuan.
- Meter, kilogram, dan pcs tidak dijumlahkan. Usable/reject rate dihitung di dalam setiap satuan.
- Status pemenuhan, koreksi, dan QC memakai posisi ledger saat laporan dimuat.

## Antarmuka

- `GET /api/supplier-performance-insights` menerima `as_of`, `window_days`, `query`, `status`, `limit`, dan
  `offset`.
- Dialog menyediakan loading, error/retry, ringkasan, empty state, pagination, dan drill-down ke PO.
- Semua nilai ledger di-escape. Dialog harus dapat dipakai pada lebar 390 px dan zoom teks 200%.

## Batas

Kedatangan pertama tidak sama dengan tanggal pemenuhan lengkap. Riwayat sebelum ledger dibuat tidak ditebak.
Laporan tidak menghitung harga trend, membuat keputusan supplier, atau memanggil connector vendor.
