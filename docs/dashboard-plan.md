# Langkah 2: dashboard produksi lokal

Lanjut dari backend v0.1.0 atas permintaan pengguna. Seluruh produksi internal. Pertahankan Python/FastAPI/SQLite dan API yang ada; sajikan aplikasi browser dari server yang sama. Tidak ada migrasi data atau deployment cloud pada langkah ini.

## Urutan kerja

- [x] Tambah endpoint papan produksi dengan ringkasan seluruh order, pencarian, filter status, dan pagination. Ringkasan tidak boleh hanya menghitung halaman yang sedang dibuka.
- [x] Buat tampilan masuk memakai API key yang sudah tersedia. Key hanya berada di memori halaman, tidak ditanam dalam source atau disimpan ke localStorage.
- [x] Tampilkan daftar order yang dapat dibuka ke detail jumlah per tahap dan riwayat.
- [x] Hubungkan form perpindahan, rework/reject, dan pembalikan ke endpoint yang sudah ada. Role tetap ditegakkan backend.
- [x] Tambah form master SKU dan order multi-SKU untuk admin agar database kosong bisa mulai digunakan dari dashboard.
- [x] Buat loading/empty/error states, retry dengan key yang sama saat hasil simpan belum pasti, serta layout mobile dan keyboard.
- [x] Uji backend dan alur frontend yang kritis, dokumentasikan hasil, lalu perbarui panduan menjalankan.

## Aturan pelaksanaan

Pengguna menyetujui Antislop sejak awal implementasi. Visual mengikuti warna tinta gelap dan aksen emas pada blueprint Beeloft yang diberikan, dengan angka tahap sebagai fokus kerja. Arah dan alasan desain disimpan di `DESIGN.md`. Tidak ada gambar dekoratif atau grafik bisnis yang belum ada datanya.
