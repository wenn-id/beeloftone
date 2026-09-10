# Verifikasi filter PIC dan posisi — v0.7

Tanggal: 10 September 2026. Windows, Python 3.12, Edge headless.

- Seluruh **41 tes backend/API/CLI lulus**. Tiga tes baru memeriksa kombinasi PIC/posisi/pencarian/status, saldo nol, perubahan posisi setelah perpindahan, summary global, PIC nonaktif, pergantian PIC, pilihan PIC lintas filter, pagination, validasi dan akses semua role.
- Tes client JavaScript lulus, termasuk retry dan unduhan CSV dengan autentikasi.
- Browser acceptance lulus: pilih PIC + sewing, hanya order terkait muncul; angka ringkasan tetap global; kembali dari detail mempertahankan filter; QC kosong; reset mengembalikan semua order. Alur lama tetap lulus.
- Uji browser awal menemukan nama akses select PIC tidak cocok dengan label yang dimaksud. Kedua select diberi aria-label eksplisit; uji ulang lulus.
- Review kode independen: tanpa temuan yang memerlukan perbaikan; tiga tes fitur dijalankan ulang oleh reviewer.
- `python -m pip check`: tidak ada dependensi rusak atau dependency baru.
- Visual QA desktop 1440px dan mobile 390px mode gelap: filter, label, tombol serta hasil terlihat. Pemeriksaan overflow pada 320/390/768px lulus.
- Preview v0.7 berjalan kembali dengan database demo yang sama. Tidak ada migrasi atau mutasi data dalam fitur ini; schema tetap 3.

Filter posisi mencocokkan saldo positif pada minimal satu SKU dalam order. Semua filter diterapkan
pada order; pencarian SKU dan posisi tidak harus cocok dengan baris SKU yang sama. Ringkasan dan
pilihan PIC mencakup semua order. Hasil hanya diperbarui saat filter diganti atau halaman dimuat ulang.

Screenshot: `../../beeloft-filter-produksi.png`.
Paket sumber: `../../beeloft-one-filter-produksi.zip`.
Panduan: `../README.md`. OpenAPI diperbarui menjadi 0.7.0.
