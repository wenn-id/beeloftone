# WIP ageing dan sinyal hambatan

## Tujuan

Menjawab kebutuhan blueprint mengenai WIP ageing, keterlambatan, dan lokasi order aktif dengan data ledger yang
sudah tersedia. Laporan membantu tim menemukan order dan tahap yang perlu diperiksa tanpa mengklaim kapasitas
mesin yang belum dimodelkan.

## Aturan

- Populasi adalah order dengan saldo positif pada `planned`, `cutting`, `sewing`, `finishing`, `qc`, atau
  `rework`, dan dibuat paling lambat pada `as_of` menurut tanggal Jakarta.
- Posisi tahap memakai saldo ledger saat request dimuat; `as_of` tidak membentuk snapshot historis.
- Umur order dihitung dari movement produksi terbaru. Order tanpa movement memakai tanggal pembuatan.
- `stalled` berarti umur sama dengan atau melebihi `idle_days`; `overdue` mengikuti tenggat sebelum `as_of`.
- `blocked` memakai issue terbuka dan `rework` memakai saldo tahap rework saat ini.
- Sinyal hambatan adalah tahap dengan kuantitas terbesar pada order stalled. Ini indikator pemeriksaan, bukan
  perhitungan kapasitas.

## Antarmuka

- `GET /api/wip-ageing-insights` menerima `as_of`, `idle_days`, `query`, `owner_id`, `stage`, `status`, `limit`,
  dan `offset`.
- Dialog menyediakan ringkasan order, rollup tahap, loading, error/retry, empty state, pagination, rincian SKU,
  kendala terbuka, serta drill-down order.
- Semua nilai ledger di-escape. Dialog harus dapat dipakai pada lebar 390 px dan zoom teks 200%.

## Batas

Ledger belum mengidentifikasi umur setiap unit yang tersisa di dalam satu tahap. Movement terbaru per order
dipakai sebagai sinyal operasional yang konsisten. Kapasitas membutuhkan master line/stasiun, kalender kerja,
jam tersedia, dan standar waktu proses sebelum dapat dihitung dengan benar.
