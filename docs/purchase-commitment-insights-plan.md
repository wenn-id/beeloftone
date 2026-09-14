# Purchase commitment insights

## Tujuan

Menjawab kebutuhan blueprint mengenai open purchase commitments dan hubungan PO approved dengan konsekuensi
keuangan. Laporan menggunakan ledger purchasing yang sudah ada tanpa membuat payable, transfer, atau jurnal.

## Aturan

- Populasi adalah PO approved yang masih berstatus aktif (`issued`) dan dibuat paling lambat pada `as_of`
  menurut tanggal Jakarta.
- PO pending, ditolak, dibatalkan, dan ditutup tidak masuk populasi.
- Komitmen terbuka adalah nilai PO dikurangi nilai penerimaan bahan layak pakai aktif.
- Receipt yang dikoreksi, bahan hold, dan bahan reject tidak dihitung sebagai penerimaan layak pakai.
- PO aktif dengan komitmen nol diberi status `fulfilled` agar dapat ditutup oleh tim.
- PO terbuka diklasifikasikan `overdue`, `due_soon`, atau `scheduled` dari `expected_date`.
- Payment submitted, approved, dan nilai penerimaan yang belum diajukan ditampilkan terpisah. Approved belum
  dianggap sebagai bukti transfer bank.

## Antarmuka

- `GET /api/purchase-commitment-insights` menerima `as_of`, `due_soon_days`, `query`, `status`, `limit`, dan
  `offset`.
- Dialog menyediakan loading, error/retry, ringkasan, empty state, pagination, rincian bahan, dan drill-down PO.
- Semua nilai ledger di-escape. Dialog harus dapat dipakai pada lebar 390 px dan zoom teks 200%.

## Batas

Status transaksi memakai ledger saat laporan dimuat. `as_of` tidak merekonstruksi penerimaan, koreksi, penutupan,
atau approval pembayaran pada masa lalu. Laporan tidak mencatat settlement bank atau jurnal akuntansi.
