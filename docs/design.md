# Beeloft One: fondasi produksi internal

## Kebutuhan yang sudah disepakati

Produksi sulit dilacak dan seluruh tahap dikerjakan internal. Mulai coding fondasi untuk order produksi, posisi jumlah per tahap, perpindahan parsial, dan riwayat pencatatan. Rilis ini berupa backend lokal beserta API interaktif bawaan FastAPI.

## Keputusan

- Satu aplikasi Python 3.12+, FastAPI, dan SQLite. Database dan transaksi memakai pustaka standar `sqlite3`; tidak ada ORM atau microservices.
- Satu order berisi beberapa baris SKU/varian. Setiap baris punya target pcs bilangan bulat dan saldo per tahap. Ukuran dan warna dibedakan oleh SKU.
- Tahap: planned -> cutting -> sewing -> finishing -> qc -> warehouse. QC dapat mengirim ke rework atau reject; rework kembali ke QC.
- `planned` menghitung target pcs yang belum masuk cutting, bukan stok kain. Ledger kain/BOM dan konsumsi aktual berada di tahap pengembangan berikutnya.
- Warehouse berarti penerimaan internal; belum menyinkronkan stok jual Jubelio.
- Perpindahan bersifat atomik: validasi saldo, kurangi sumber, tambah tujuan, simpan pelaku dan waktu dalam satu transaksi. Jumlah semua tahap selalu sama dengan target.
- Catatan perpindahan tidak diedit/dihapus. Koreksi oleh admin membuat catatan pembalik dengan alasan; pembalikan ditolak jika saldo tujuan sudah tidak cukup. Sistem ini melacak kuantitas per SKU, bukan identitas setiap potong.
- Setiap request pembuatan order, perpindahan, dan pembalikan memakai `Idempotency-Key`. Pengulangan payload yang sama mengembalikan hasil awal tanpa menulis lagi; pemakaian key yang sama dengan payload lain ditolak.
- API key unik per pengguna disimpan sebagai hash, terikat nama dan role. Admin mengelola master dan membuat order, operator mencatat perpindahan, viewer hanya membaca. Pelaku berasal dari autentikasi, tidak dari input nama bebas.
- PIC internal diberikan saat order dibuat. Daftar order mengembalikan saldo dan penanda terlambat berdasarkan tanggal Jakarta. Semua timestamp audit disimpan UTC.
- Database lokal persisten dengan foreign keys, CHECK constraints, versioned migration, transaksi `BEGIN IMMEDIATE`, dan pembacaan snapshot yang konsisten.
- Default server hanya 127.0.0.1. Penggunaan banyak perangkat memerlukan deployment dengan HTTPS, pengelolaan akun dan backup yang dipersiapkan tersendiri.

## Cakupan rilis

Master SKU, PIC/pengguna melalui CLI, order multi-SKU, saldo tahap, perpindahan parsial, QC rework/reject dengan alasan, koreksi berjejak, daftar/detail order, riwayat, role checks, ekspor OpenAPI, CLI backup konsisten, dokumentasi menjalankan dan contoh API.

Belum mencakup dashboard khusus, login browser, BOM/kain, penjadwalan kapasitas, handover dua pihak, attachment, integrasi vendor, finance, atau AI. Data contoh hanya masuk ke database demo terpisah bila pengguna menjalankan perintah demo.

## Kriteria lulus

1. Order 500 pcs dapat terbagi ke beberapa tahap tanpa kehilangan/menambah jumlah.
2. Dua transfer 80 pcs yang bersamaan dari saldo 100 menghasilkan satu sukses, satu konflik, saldo akhir 20/80.
3. Mengulang request sukses tidak menambah transaksi; key beda payload menghasilkan konflik.
4. Transfer negatif, pecahan, bool, saldo tidak cukup, lompatan tahap, atau role salah ditolak tanpa perubahan.
5. Reject/rework memerlukan alasan; koreksi menyimpan hubungan ke transaksi asal.
6. Restart mempertahankan data; backup dapat dibuka dengan saldo/riwayat yang sama.
7. Semua pemeriksaan berjalan terhadap API dan database sungguhan yang terisolasi dari data pengguna.

## Referensi implementasi

- [FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [SQLite transactions](https://www.sqlite.org/lang_transaction.html)
