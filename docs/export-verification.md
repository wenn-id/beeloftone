# Verifikasi laporan rentang tanggal dan CSV — v0.6

Tanggal: 10 September 2026. Windows, Python 3.12, Edge headless.

- Seluruh 38 tes backend/API/CLI lulus. Tiga tes ekspor baru mencakup kedua batas tanggal, kompatibilitas day, rentang invalid, seluruh hasil melampaui halaman UI, CSV kosong, semua role, penolakan tanpa akses, UTF-8 BOM, koma/kutip/baris baru, teks menyerupai formula, serta penolakan hasil di atas batas.
- Tes aktivitas ditambah pemeriksaan penerimaan gudang dan pembalikannya lintas hari dalam satu rentang (hasil bersih nol); empat tes aktivitas dijalankan ulang dan lulus.
- Tes client JavaScript lulus, termasuk unduhan Blob dengan header autentikasi dan error JSON akses ditolak.
- Browser acceptance runner lulus: filter tanggal awal/akhir, hari kosong, file benar-benar diunduh, nama file sesuai filter, isi catatan dan BOM terjaga. Alur produksi, kendala, koreksi, perubahan PIC/jadwal, recovery, role dan navigasi tetap lulus.
- Review kode independen tidak menemukan masalah yang memerlukan perbaikan; reviewer menjalankan ulang tiga tes ekspor.
- `python -m pip check`: tidak ada dependensi rusak; tidak menambah dependency aplikasi.
- Visual QA desktop 1440px serta mobile 390px terang/gelap: tanggal awal/akhir, jenis aktivitas, tombol tampil/unduh dan waktu kejadian terbaca. Tidak ada overflow horizontal.
- Preview lokal v0.6 berjalan kembali dengan database demo yang sama. Fitur ini hanya membaca data; schema tetap 3.

CSV memakai satu snapshot database untuk seluruh hasil. Batas 10.000 baris diperiksa sebelum
mengirim file, sehingga hasil tidak dipotong diam-diam. Maksimal rentang 366 hari. Teks berawalan
formula diberi apostrof, sementara jumlah tetap numerik. API key tidak disertakan dalam file.

Belum diuji dengan aplikasi Excel desktop atau load test dataset skala besar. CSV dapat diimpor
sebagai UTF-8 dengan delimiter koma. Unduhan adalah snapshot baru dan dapat berisi catatan yang
masuk setelah daftar di layar dimuat. Belum ada XLSX/PDF atau penjadwalan laporan otomatis.

Screenshot: `../../beeloft-laporan-csv.png`. Paket sumber: `../../beeloft-one-laporan-csv.zip`.
Kontrak API: `openapi.json` versi 0.6.0. Panduan penggunaan: `../README.md`.
