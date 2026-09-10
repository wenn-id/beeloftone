# Beeloft One

Fondasi pelacakan produksi internal, versi 0.1.0. Backend sudah menyimpan data di database lokal; antarmuka yang tersedia adalah dokumentasi API interaktif. Belum ada dashboard untuk operator.

## Coba di Windows

Buka PowerShell di folder proyek ini, kemudian:

```powershell
.\start.ps1 -Demo
```

Script memasang dependencies ke `.venv`, membuat `data/demo.sqlite3` jika belum ada, dan menjalankan server lokal. Pada pembuatan database, terminal menampilkan API key admin, operator, dan viewer. Simpan key tersebut; database hanya menyimpan hash-nya.

Buka [dokumentasi API lokal](http://127.0.0.1:8000/docs), klik **Authorize**, masukkan API key admin, lalu coba `GET /api/orders`. Data contoh berisi satu order 500 pcs dengan posisi: planned 100, cutting 100, sewing 150, finishing 50, QC 0, rework 20, warehouse 80, reject 0. Jumlah tetap 500 pcs.

Hentikan server dengan Ctrl+C. Menjalankan script lagi memakai database yang sama. Semua data contoh diberi nama DEMO/CONTOH. Untuk database kosong terpisah, jalankan `./start.ps1` tanpa `-Demo`.

Jika PowerShell memblokir script lokal, jalankan untuk proses itu saja:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start.ps1 -Demo
```

Pilihan lain: `./start.ps1 -Python C:\path\python.exe -Port 8010`. Dibutuhkan Python 3.12+. Script juga dapat menemukan Python bawaan Codex pada komputer ini. Instalasi pertama membutuhkan internet.

## Menjalankan tanpa script

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
.\.venv\Scripts\python.exe -m beeloft user --name "Pemilik" --role admin
.\.venv\Scripts\python.exe -m beeloft serve
```

Database default: `data/beeloft.sqlite3`, relatif terhadap working directory. Bisa diubah dengan `--db PATH` sebelum subcommand atau environment variable `BEELOFT_DB`.

## Yang bisa dikerjakan

- Membuat master SKU; warna dan ukuran dicatat per SKU.
- Membuat order dengan referensi unik, PIC internal, tenggat, dan beberapa SKU.
- Melihat jumlah setiap SKU di setiap tahap, ringkasan order dan penanda terlambat.
- Memindahkan sebagian jumlah ke tahap berikutnya; satu order bisa berada di banyak tahap sekaligus.
- Mencatat rework/reject dengan alasan dan mengirim hasil rework kembali ke QC.
- Membalik transaksi keliru sebagai admin, dengan alasan dan hubungan ke transaksi asal.
- Menelusuri waktu UTC, akun pencatat, SKU, tahap asal/tujuan, jumlah dan alasan dalam riwayat.
- Menolak input ganda, saldo kurang, jumlah non-integer, tahap tidak sah dan akses di luar role.

```text
planned -> cutting -> sewing -> finishing -> qc -> warehouse
                                            | -> reject
                                            | -> rework -> qc
```

`planned` adalah target pcs yang belum masuk cutting, bukan stok kain. `warehouse` adalah penerimaan gudang internal, belum stok jual Jubelio. Saldo tahap adalah posisi sekarang, bukan jumlah kumulatif yang pernah melewati tahap itu. Status `closed_with_reject` berarti semua pcs sudah diterima gudang atau reject, bukan target barang layak jual sudah terpenuhi.

## Akun dan hak akses

| Role | Hak |
|---|---|
| admin | Membaca, membuat SKU/order, memindahkan barang, membalik transaksi |
| operator | Membaca dan mencatat perpindahan barang |
| viewer | Membaca saja |

Semua akun dalam database ini dapat melihat semua order. PIC ditentukan per order, bukan per bundle atau per tahap. Akun pencatat perpindahan tidak otomatis berarti penerima barang. Belum ada konfirmasi serah-terima dua pihak.

Pembuatan/pencabutan akun dilakukan oleh pemegang akses lokal komputer:

```powershell
.\.venv\Scripts\python.exe -m beeloft user --name "Tim Cutting" --role operator
.\.venv\Scripts\python.exe -m beeloft --db data/demo.sqlite3 user --name "Admin demo tambahan" --role admin
.\.venv\Scripts\python.exe -m beeloft disable-user ID_PENGGUNA
```

Jangan memakai satu key bersama jika perlu jejak per orang. Key yang hilang tidak dapat ditampilkan kembali: buat akun baru lalu nonaktifkan akun lama. Akun nonaktif tetap tersimpan agar referensi riwayat tidak putus.

## Memakai API

Semua `/api/*` memerlukan header `X-API-Key`. Setiap POST juga wajib membawa `Idempotency-Key`, misalnya UUID. Key berlaku per pengguna, lintas endpoint. Ulangi **key dan payload yang sama** ketika respons terputus. Respons replay sama dengan respons pertama (HTTP 201); tidak ada pencatatan tambahan. Key yang sama dengan payload/aksi berbeda menghasilkan 409. Untuk tindakan baru, gunakan key baru.

1. `GET /api/users`: ambil ID admin/operator sebagai PIC.
2. `POST /api/products`: buat SKU, lalu simpan `id` hasilnya.
3. `POST /api/orders`: gunakan ID SKU dan PIC. Ambil `lines[].id` hasilnya.
4. `POST /api/movements`: gunakan ID baris order, bukan ID SKU.
5. `GET /api/orders/{id}` dan `/api/orders/{id}/movements`: periksa saldo dan riwayat.

Contoh body order; ganti nilai ID dengan respons API:

```json
{
  "reference": "PROD-2026-001",
  "title": "Luna Blue batch September",
  "owner_id": "ID_OPERATOR",
  "due_date": "2026-09-30",
  "lines": [{"product_id": "ID_SKU", "quantity": 500}]
}
```

Contoh perpindahan:

```json
{
  "line_id": "ID_BARIS_ORDER",
  "from_stage": "planned",
  "to_stage": "cutting",
  "quantity": 200,
  "reason": "Mulai cutting batch pertama"
}
```

Koreksi: `POST /api/movements/{id}/reverse` dengan `{"reason":"Salah input jumlah"}`. Pembalikan mengembalikan **seluruh jumlah transaksi asal**, hanya sekali. Jika jumlah yang benar berbeda, setelah pembalikan buat perpindahan baru. Pembalikan ditolak apabila saldo tahap tujuan sudah tidak cukup; telusuri transaksi lanjutannya terlebih dahulu. Riwayat asli tidak dihapus. Ini ledger kuantitas per SKU, belum pelacakan identitas potong/bundle tertentu.

Daftar SKU/order/riwayat memakai `?limit=100&offset=0`, maksimal 500 per halaman. Riwayat diurutkan dari yang paling lama. Tenggat dinilai menurut tanggal Jakarta; timestamp audit memakai UTC. `401` berarti key hilang/tidak valid, `403` role salah, `404` objek hilang, `409` konflik, `422` input tidak sah, `503` database sibuk (retry key yang sama).

Kontrak request tersedia di `docs/openapi.json` dan `/openapi.json`. Skema respons belum diberi model OpenAPI khusus; contoh dan acceptance test menjadi acuan struktur respons versi ini.

## Backup dan pemulihan

```powershell
.\.venv\Scripts\python.exe -m beeloft --db data/beeloft.sqlite3 backup data/backups/beeloft-2026-09-10.sqlite3
```

Backup memakai SQLite backup API sehingga konsisten meskipun server masih berjalan. File tujuan harus baru; file lama tidak ditimpa. Backup memuat data operasional serta hash API key, jadi simpan dengan akses terbatas.

Untuk mencoba pemulihan: hentikan server, lalu jalankan `python -m beeloft --db data/backups/beeloft-2026-09-10.sqlite3 serve`. Periksa saldo/riwayat melalui API dengan key yang berlaku pada saat backup. Buat salinan backup jika hendak melanjutkan penulisan tanpa mengubah arsip. Jangan menyalin hanya file SQLite aktif secara manual karena ada file WAL pendamping.

## Pengujian

```powershell
.\start.ps1 -SetupOnly
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pip check
```

Tes memakai database sementara dan API/CLI sungguhan. Mencakup konservasi jumlah, concurrent transfers, retry ganda, rollback kegagalan penyimpanan, izin pengguna, input tidak sah, QC, pembalikan, persistence dan backup. Tidak memakai data bisnis.

## Batas fondasi ini

Server hanya mendengarkan localhost. Rilis ini untuk pengembangan/uji lokal, belum deployment bersama untuk tim. Sebelum dipakai banyak perangkat: siapkan HTTPS, login browser/SSO, kebijakan akses yang lebih rinci, backup terjadwal dengan uji restore, serta validasi alur di lapangan. SQLite cukup untuk uji lokal; evaluasi PostgreSQL saat perlu beberapa instance aplikasi atau penulisan bersamaan lebih tinggi.

Belum mencakup BOM, stok/konsumsi kain, barang hilang di tengah produksi, partial cancellation, perubahan target/tenggat/PIC setelah order dibuat, bundle/barcode, attachment kendala, integrasi Jubelio/Mekari, atau dashboard khusus. Migrasi schema saat ini versi 1; perubahan berikutnya harus menambah migrasi yang menjaga data lama.

Desain: `docs/design.md`. Rencana dan status implementasi: `docs/implementation-plan.md`.
