# Verifikasi unduhan cadangan — v0.8

Tanggal: 10 September 2026. Windows, Python 3.12, Edge headless.

- Seluruh **44 tes backend/API/CLI lulus**. Tiga tes baru mencakup unduhan database, pembandingan semua tabel dengan sumber, integrity_check, foreign_key_check, pembukaan database hasil unduhan sebagai aplikasi, autentikasi setelah pemulihan, role admin/operator/viewer, akun nonaktif, kegagalan penyimpanan dan retry.
- Tes client JavaScript dan CSV lulus setelah fungsi penyimpanan Blob dipakai bersama oleh unduhan CSV serta database.
- Browser acceptance lulus: admin membuka dialog, simulasi error 503 terlihat, percobaan berikutnya mengunduh file SQLite dengan header yang benar; key asli tidak ada di file. Tombol tidak terlihat untuk operator/viewer. Seluruh alur produksi dan laporan sebelumnya tetap lulus.
- Review kode independen: tanpa temuan yang memerlukan perbaikan; reviewer menjalankan ulang tiga tes backup.
- `python -m pip check`: tidak ada dependensi rusak atau dependency baru.
- Visual QA dialog desktop 1440px dan mobile 390px: isi cadangan, petunjuk dan tombol terbaca. Pemeriksaan overflow halaman pada 320/390/768px lulus.
- Preview v0.8 dijalankan dengan database demo yang sama. Screenshot hanya membuka dialog tanpa meminta unduhan. Tidak ada perubahan schema/data sumber.

Endpoint memakai SQLite backup API, menghasilkan satu file lengkap termasuk perubahan yang sudah
commit di WAL. Folder sementara dibersihkan setelah pembacaan file maupun kegagalan. Respons no-store,
dan pemeriksaan admin dilakukan sebelum membuat cadangan. File memang mencakup hash key dan seluruh
data; UI menjelaskan isi serta perlunya menyimpan di lokasi pribadi. Kunci asli tetap diperlukan untuk login.

Batas: unduhan ditampung di memori server dan browser, timeout client 15 detik. Untuk database besar
gunakan CLI backup. Belum ada pemulihan lewat dashboard, backup otomatis, enkripsi atau cloud storage.
Panduan README memeriksa salinan cadangan melalui server uji terpisah tanpa menimpa database produksi.

Screenshot: `../../beeloft-cadangan-data.png`. Paket sumber: `../../beeloft-one-cadangan.zip`.
OpenAPI diperbarui ke 0.8.0. Cadangan/database/API key tidak disertakan dalam paket sumber.
