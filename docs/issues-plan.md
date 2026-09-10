# Kendala produksi — v0.3

Lanjutan yang diminta pengguna: catat hambatan yang membuat produksi sulit ditindaklanjuti.
Gunakan UI dan pola transaksi yang sudah disetujui, tanpa dependensi tambahan.

- Kendala melekat ke satu SKU order dan satu tahap, berisi keterangan serta PIC aktif.
- Admin/operator boleh mencatat dan menyelesaikan; pelaku dan waktu keduanya tersimpan.
- Penyelesaian wajib berisi tindakan yang dilakukan. Catatan selesai tidak bisa ditimpa.
- Kendala tidak mengubah jumlah barang atau otomatis menghentikan perpindahan.
- Dashboard menunjukkan jumlah kendala terbuka per order serta filter khusus.
- Detail menampilkan riwayat kendala, terbaru dahulu, dengan pagination stabil berdasarkan urutan pembuatan.
- Migrasi transaksional schema 1 ke 2; backup demo sebelum migrasi.
- Verifikasi: konservasi saldo, izin, input, retry, resolusi bersamaan, migrasi data lama, dan alur browser/mobile.
