# Alert kapasitas di Command Center

## Tujuan

Membawa risiko dari perencanaan kapasitas v0.72 ke antrean keputusan utama. Planner dan management dapat melihat
overload, risiko deadline, atau master standar yang belum lengkap tanpa membuka laporan kapasitas terlebih dahulu.

## Dasar hitung

Pada setiap `GET /api/command-center`, sistem menghitung rencana kapasitas dengan parameter tetap:

- tanggal awal mengikuti tanggal Jakarta saat request;
- horizon 14 hari kalender;
- batas peringatan utilisasi 80%;
- seluruh work center dan tahap aktif;
- saldo WIP saat request, standar routing terbaru, dan override kalender terbaru.

Top-level `capacity` memuat rentang horizon, kebutuhan dan ketersediaan menit, jumlah work center per status, order
berisiko, jumlah gap, kuantitas yang kehilangan standar, serta flag kelengkapan kapasitas.

## Prioritas alert

- `production-capacity-risk` berprioritas kritis jika ada work center overload atau order yang tidak cukup
  kapasitas sebelum target.
- `production-capacity-near` berprioritas perhatian jika belum ada risiko lebih tinggi tetapi utilisasi work
  center mencapai 80%.
- `production-capacity-coverage` berprioritas perhatian jika kebutuhan tahap tidak mempunyai standar aktif atau
  menunjuk work center nonaktif. Alert ini dapat muncul bersama risiko kapasitas karena angka beban belum lengkap.

Setiap alert membuka laporan **Kapasitas produksi**. Risiko produksi, stockout, dan utang kritis tetap diurutkan
sebelum alert berprioritas perhatian.

## Antarmuka

Command Center menambah kartu **Kapasitas produksi** dengan beban 14 hari, kapasitas tersedia, work center yang
perlu perhatian, order berisiko, kelengkapan standar, dan tanggal akhir horizon. Nilai dinamis di-escape sebelum
dirender. Tampilan memakai komponen kartu yang sama dengan snapshot bisnis lain.

## Batas

Horizon dan threshold Command Center masih tetap, belum menjadi preferensi pengguna. Perhitungan memakai saldo
WIP saat request dan bukan finite scheduler per jam. Setup, maintenance, absensi, dan efisiensi harus sudah masuk
ke standar atau kalender. Tidak ada schema baru, penjadwalan otomatis, atau runtime connector Jubelio/Mekari.
