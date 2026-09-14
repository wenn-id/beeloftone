# Material price insights

## Tujuan

Menjawab kebutuhan blueprint mengenai pergerakan harga bahan dari harga unit yang sudah terkunci pada PO.
Laporan memperlihatkan perubahan beserta dokumen sumber tanpa mengubah transaksi atau menebak harga di luar
ledger.

## Aturan

- Populasi laporan adalah PO approved, tidak dibatalkan, dengan tanggal pencatatan dalam periode.
- Satu seri hanya membandingkan material dan supplier yang sama.
- Harga awal dan terbaru memakai urutan pencatatan PO. `expected_date` ditampilkan sebagai konteks kedatangan.
- PO pending, ditolak, dan dibatalkan tidak menjadi observasi.
- Satu observasi diberi status `single_observation`; dua atau lebih observasi dapat menjadi `increased`,
  `decreased`, atau `stable`.
- Persentase perubahan membandingkan harga terbaru terhadap harga awal. Rata-rata tidak dibobot kuantitas.

## Antarmuka

- `GET /api/material-price-insights` menerima `as_of`, `window_days`, `query`, `status`, `limit`, dan `offset`.
- Dialog menyediakan loading, error/retry, ringkasan, empty state, pagination, dan drill-down ke PO.
- Semua nilai ledger di-escape. Dialog harus dapat dipakai pada lebar 390 px dan zoom teks 200%.

## Batas

Laporan memakai mata uang IDR dan tidak menormalkan diskon, ongkir, pajak, atau syarat pembayaran. Harga rata-rata
adalah rata-rata observasi PO, bukan weighted average berdasarkan jumlah. Runtime connector vendor tidak dipanggil.
