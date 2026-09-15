# Alert People di Command Center

## Tujuan

Membawa kelengkapan pencatatan kehadiran dan status absen ke antrean keputusan manajemen tanpa menambah sumber
data baru. Snapshot harus berasal dari employee master dan ledger kehadiran lokal yang sudah immutable.

## Dasar hitung

Setiap `GET /api/command-center` memakai tanggal Jakarta saat request. Sistem mengambil seluruh karyawan aktif,
mencocokkan tepat satu catatan kehadiran pada tanggal tersebut, lalu menghitung jumlah tercatat, belum tercatat,
hadir, cuti, absen, menit kerja, dan lembur. Catatan milik karyawan nonaktif tidak masuk snapshot aktif.

## Prioritas alert

- Seluruh roster aktif tanpa catatan menghasilkan alert `workforce-incomplete` berprioritas kritis.
- Sebagian roster aktif belum dicatat menghasilkan alert yang sama berprioritas perhatian.
- Minimal satu status absen menghasilkan alert `workforce-absence` berprioritas perhatian.
- Cuti dan lembur hanya ditampilkan pada snapshot karena belum ada aturan bisnis yang menjadikannya exception.

Kedua alert membuka layar People dengan tanggal hari ini, status semua, dan pencarian kosong.

## Antarmuka

Kartu **People** memakai pola snapshot Command Center yang sudah ada. Status selalu ditulis sebagai teks, angka
berasal dari API, tombol memakai target sentuh standar, dan kartu ikut reflow satu kolom pada layar kecil.

## Batas

Belum ada roster shift, jam kerja terjadwal, threshold lembur, jenis cuti, atau approval cuti/lembur. Schema tetap
50 dan runtime connector Mekari/Jubelio tidak dicakup.
