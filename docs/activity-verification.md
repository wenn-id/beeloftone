# Verifikasi aktivitas harian — v0.5

Tanggal: 10 September 2026. Windows, Python 3.12, Edge headless.

Fitur membaca kejadian produksi lintas order menurut tanggal Jakarta. Ringkasan seluruh
tanggal terpisah dari filter jenis; daftar terbaru dahulu memakai cursor waktu + event ID.
Tidak ada perubahan schema atau endpoint tulis baru.

- `python -m unittest discover -s tests -v`: **35 tes lulus**. Empat tes baru mencakup batas 00:00 Jakarta, hari kosong, semua jenis kejadian, pembalikan gudang pada hari berbeda, ringkasan independen filter, cursor dengan timestamp sama dan catatan baru, autentikasi serta input invalid.
- `node tests/test_client.mjs`: **lulus**.
- `python tests/run_browser.py --node ... --playwright-module ...`: **lulus**. Alur baru: tanggal default dari server, filter jenis, catatan perubahan berisi karakter HTML, ringkasan sesuai API, tanggal kosong, kembali ke tanggal aktif, buka order dari aktivitas, dan akses viewer. Alur order/kendala/perpindahan/koreksi/recovery sebelumnya tetap lulus.
- `python -m pip check`: tidak ada dependensi rusak; tidak menambahkan dependensi.
- Review kode independen: tidak ada temuan yang memerlukan perubahan; reviewer menjalankan ulang keempat tes aktivitas.
- Visual QA desktop 1440px dan mobile 390px, terang/gelap: kolom tanggal awalnya sempit, diperbaiki menjadi satu kolom pada HP. Capture ulang menunjukkan tanggal lengkap serta tombol dan catatan terbaca, tanpa overflow. Screenshot akhir menonaktifkan animasi agar tidak menangkap transisi tema yang belum selesai.
- Preview server v0.5 berhasil berjalan di `http://127.0.0.1:8765/`; aktivitas demo ditampilkan melalui GET tanpa mutasi. Database tetap schema 3.

Screenshot: `../../beeloft-aktivitas.png`. Paket sumber: `../../beeloft-one-aktivitas.zip`.
Kontrak API diperbarui di `openapi.json`.

Batas: rekap per hari pencatatan, belum rentang tanggal atau ekspor. Tidak menghitung barang
unik di semua tahap. Gudang bersih adalah arus masuk dikurangi pembalikan pada hari terpilih,
bukan saldo saat ini. Halaman lanjutan melihat catatan lebih lama; muat ulang untuk aktivitas baru.
Belum menjalankan load test dengan riwayat skala besar atau deployment lintas perangkat.
