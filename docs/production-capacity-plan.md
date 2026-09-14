# Perencanaan kapasitas produksi

## Tujuan

Menerjemahkan saldo WIP aktif menjadi kebutuhan menit per work center agar planner dapat melihat overload dan
risiko target sebelum menjanjikan jadwal produksi. Dasar hitung dapat diaudit dari work center, standar waktu
SKU, kalender kerja, order, dan saldo tahap yang tersimpan.

## Model kapasitas

- Work center terikat ke satu tahap: `cutting`, `sewing`, `finishing`, `qc`, atau `rework`.
- Kapasitas hari kerja disimpan dalam menit. Senin sampai Jumat memakai kapasitas harian; Sabtu dan Minggu
  bernilai nol.
- Override kalender terbaru mengganti kapasitas satu tanggal. Nilai nol digunakan untuk libur, sedangkan nilai
  lebih besar dapat mencatat lembur.
- Setiap SKU memiliki standar menit per pcs dan work center untuk tiap tahap. Work center harus aktif dan
  tahapnya harus sama dengan tahap standar.
- Work center, standar routing, dan kalender memakai revisi append-only. Perubahan membutuhkan revisi terakhir
  agar edit bersamaan tidak saling menimpa.

## Perhitungan

Laporan memakai saldo produksi saat request dimuat. Setiap pcs mendapat beban pada tahap tempatnya berada dan
semua tahap yang masih harus dilalui:

```text
planned/cutting -> cutting -> sewing -> finishing -> qc
sewing          -> sewing -> finishing -> qc
finishing       -> finishing -> qc
qc              -> qc
rework          -> rework -> qc
```

Populasi mencakup order aktif yang sudah dibuat pada `as_of` menurut tanggal Jakarta dan memiliki target paling
lambat pada akhir horizon. Beban per work center adalah `kuantitas × menit standar`. Order diurutkan menurut
target; kebutuhan kumulatif dibandingkan dengan kapasitas kalender yang tersedia sampai target tersebut.

Status work center:

- `overloaded`: beban seluruh horizon melebihi kapasitas.
- `deadline_risk`: kapasitas horizon cukup, tetapi kebutuhan kumulatif sebelum salah satu target tidak cukup.
- `near_capacity`: utilisasi mencapai batas peringatan.
- `available`: memiliki beban dan kapasitas masih cukup.
- `idle`: tidak memiliki beban dalam horizon.

Gap ditampilkan ketika standar tahap belum tersedia atau standar menunjuk work center nonaktif. Filter satu
work center hanya menghitung work center tersebut dan tidak menampilkan gap yang belum dapat dipetakan ke sana.

## Antarmuka dan API

Pilih **Kapasitas produksi** untuk mengelola master sebagai admin dan membaca laporan sebagai semua role aktif.
Dialog menyediakan loading, error/retry, empty state, pagination, detail kalender, rincian beban SKU, dan
drill-down order.

- `GET/POST /api/work-centers`
- `POST /api/work-centers/{id}/changes`
- `GET /api/routing-standards`
- `GET/POST /api/products/{product_id}/routing-standards/{stage}`
- `GET/POST /api/work-centers/{id}/calendar`
- `GET /api/capacity-plan`

Mutasi master hanya untuk admin dan memerlukan `Idempotency-Key`. Laporan dapat dibaca admin, operator, dan
viewer. Schema database versi 49.

## Batas

Laporan tidak menjadwalkan urutan kerja per jam, membagi operator secara otomatis, atau merekonstruksi saldo WIP
historis. Utilisasi adalah estimasi standar berdasarkan posisi ledger saat ini. Setup time, perpindahan antarline,
efisiensi operator, absensi, dan maintenance perlu dimasukkan lewat standar atau override kapasitas yang sudah
disepakati tim. Runtime connector Jubelio dan Mekari tetap ditunda sampai akses API resmi tersedia.
