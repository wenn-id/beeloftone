# Alert kualitas di Command Center

## Tujuan

Membawa sinyal kualitas v0.73 ke antrean keputusan utama agar management tidak perlu membuka laporan terpisah
untuk mengetahui adanya line atau vendor yang perlu perhatian. Ini melaksanakan contoh blueprint tentang kenaikan
defect vendor yang langsung dapat dibuka dari Command Center.

## Kontrak keputusan

Pada setiap `GET /api/command-center`, sistem menghitung laporan kualitas dengan parameter tetap:

- tanggal akhir mengikuti tanggal Jakarta saat request;
- periode aktif 30 hari dan pembanding 30 hari sebelumnya;
- batas peringatan rework + reject 5%;
- ambang perubahan 1 poin persentase;
- hanya final QC aktif; catatan terkoreksi dikeluarkan.

Top-level `quality` memuat rentang periode, jumlah pcs diperiksa, first-pass yield, rework rate, reject rate,
gabungan rework + reject, jumlah line/vendor, dan jumlah yang perlu perhatian. Nilai nol ditampilkan dengan jujur
ketika belum ada final QC pada periode tersebut.

Jika ada kelompok berstatus `attention`, satu alert mewakili line/vendor berisiko tertinggi sesuai urutan laporan
kualitas. Alert menyebut jenis pengerjaan, nama assignee, rasio rework + reject, volume pemeriksaan, dan kenaikan
terhadap periode sebelumnya atau batas yang terlampaui. Prioritasnya `warning`; kondisi produksi, stockout, dan
utang kritis tetap tampil lebih dahulu.

## Antarmuka

Command Center menambah kartu **Kualitas produksi**. Tombol kartu dan tombol alert membuka dialog laporan
**Kualitas produksi**, sehingga pengguna dapat melihat jenis defect, sumber penanggung jawab, SKU, dan final QC
terbaru. Semua nilai dinamis di-escape sebelum dirender.

## Batas

Command Center hanya menampilkan satu alert kualitas agar antrean tetap ringkas; laporan lengkap dapat memuat
lebih banyak line/vendor. Threshold v0.74 masih tetap di sistem dan belum menjadi preferensi pengguna. Hasil
mencerminkan final QC yang sudah dicatat, bukan output yang belum diperiksa. Tidak ada tindakan koreksi otomatis,
schema baru, atau runtime connector Jubelio/Mekari.
