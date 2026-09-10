# Verifikasi perubahan tenggat/PIC — v0.4

Tanggal: 10 September 2026. Lingkungan: Windows, Python 3.12, Edge headless.

Perubahan: admin dapat mengganti tenggat/PIC order dengan alasan wajib. Nilai lama/baru,
pelaku dan waktu disimpan dalam riwayat yang tidak dapat ditimpa. Revision mencegah perubahan
dari draft lama; receipt transaksi mempertahankan retry yang sama setelah hasil simpan terputus.

- `python -m unittest discover -s tests -v`: **31 tes lulus**. Lima tes baru mencakup perubahan dan board, riwayat serta cursor, retry, input/role/PIC nonaktif, edit bersamaan, rollback jika audit gagal, dan migrasi data v2 ke v3.
- `node tests/test_client.mjs`: **lulus**.
- `python tests/run_browser.py --node ... --playwright-module ...`: **lulus**. Uji baru mencakup form dengan nilai awal, perubahan tenggat/PIC, alasan dengan karakter HTML, riwayat, penolakan draft lama setelah edit dari tab lain, muat ulang nilai terbaru, dan tombol edit tersembunyi untuk operator/viewer. Alur sebelumnya tetap lulus, termasuk kendala, perpindahan, retry setelah respons hilang, koreksi dan responsive layout.
- `python -m pip check`: tidak ada dependensi rusak. Tidak ada dependensi baru.
- Review kode independen: tidak ada temuan yang memerlukan perbaikan; lima tes fitur dijalankan ulang oleh reviewer.
- Pemeriksaan visual form pada desktop 1440px dan mobile 390px: teks, input, fokus dan tombol terbaca, tanpa overflow horizontal. Screenshot memakai draft contoh yang tidak dikirim.
- Preview dihentikan, backup konsisten dibuat melalui SQLite backup API, lalu server v0.4 dijalankan. Semua baris users/products/orders/order_lines/balances/movements/requests/issues identik dengan backup sebelum upgrade. Schema menjadi 3.

Backup lokal: `../data/backups/demo-before-v04.sqlite3` (tidak masuk ZIP sumber).
Screenshot: `../../beeloft-jadwal-pic.png`. ZIP sumber: `../../beeloft-one-jadwal-pic.zip`.
OpenAPI diperbarui ke 0.4.0.

Batas: uji lokal, belum deployment lintas perangkat. Riwayat perubahan baru mulai dicatat setelah
upgrade. Perubahan PIC order tidak mengubah PIC kendala. Jumlah target dan saldo tahap tidak dapat
diubah melalui form ini. Untuk melihat perubahan akun lain, muat ulang order.
