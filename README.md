# Beeloft One

Pelacakan produksi internal, versi 0.5.0. Dashboard dan API memakai database lokal yang sama: order, posisi barang per tahap, perpindahan parsial, QC, serta riwayat koreksi.

## Coba di Windows

Buka PowerShell di folder proyek ini, kemudian:

```powershell
.\start.ps1 -Demo
```

Script memasang dependencies ke `.venv`, membuat `data/demo.sqlite3` jika belum ada, dan menjalankan server lokal. Pada pembuatan database, terminal menampilkan API key admin, operator, dan viewer. Simpan key tersebut; database hanya menyimpan hash-nya.

Buka [dashboard lokal](http://127.0.0.1:8000/), masukkan API key pada kolom **Kunci akses**, lalu buka order dari daftar. Data contoh berisi satu order 500 pcs dengan posisi: planned 100, cutting 100, sewing 150, finishing 50, QC 0, rework 20, warehouse 80, reject 0. Jumlah tetap 500 pcs. [Dokumentasi API](http://127.0.0.1:8000/docs) tetap tersedia untuk pengembangan.

## Memakai dashboard

1. Admin: buka **Master SKU → Tambah SKU**. Gunakan kode berbeda untuk setiap kombinasi warna/ukuran.
2. Pilih **Buat order produksi**, isi PIC, target selesai, dan satu atau beberapa baris SKU.
3. Buka order dari daftar untuk melihat saldo per tahap. Admin/operator memilih **Catat perpindahan** pada SKU yang dikerjakan.
4. Isi tahap asal, tahap tujuan dan jumlah aktual yang diserahkan. Rework/reject wajib menyertakan alasan.
5. Periksa **Riwayat perpindahan**. Admin dapat memilih **Koreksi** untuk pembalikan seluruh transaksi yang keliru.

Daftar mendukung pencarian referensi/judul/SKU/produk dan filter aktif, lewat target, atau selesai. Ringkasan di atas selalu menghitung seluruh database. Muat ulang untuk mengambil data terbaru; belum ada pembaruan otomatis dari perangkat lain. Mode gelap/terang tersedia dan layout menyesuaikan layar HP.

Kunci akses hanya berada di memori halaman, sehingga reload meminta masuk kembali. Preferensi tema disimpan di localStorage. Draft request yang sedang disimpan disimpan di sessionStorage **tanpa API key** agar reload tab yang sama dapat memulihkan request dengan identitas yang sama. Setelah masuk dengan akun pencatat yang sama, pilih **Coba ulang penyimpanan** jika hasil sebelumnya belum pasti. Data request dihapus setelah terkonfirmasi. Browser harus mengizinkan sessionStorage untuk menyimpan.

Jangan membuat ulang transaksi yang belum terkonfirmasi dengan akun lain. Jika akun dicabut saat hasil simpan belum pasti, minta admin mencocokkan riwayat sebelum melakukan tindakan baru. Pemulihan otomatis terbatas pada tab/sessionStorage yang masih tersedia; menutup tab permanen atau menghapus penyimpanan browser dapat menghilangkan draft pemulihan. Login ini menggunakan API key lokal, belum login email/password atau SSO.

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
| admin | Membaca, membuat SKU/order, mengubah tenggat/PIC order, memindahkan barang, membalik transaksi, mencatat/menyelesaikan kendala |
| operator | Membaca, mencatat perpindahan barang, mencatat/menyelesaikan kendala |
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

Penghubung dashboard: `GET /api/production-board?q=luna&status=active&limit=25&offset=0`. Status dapat berupa `all`, `active`, `overdue`, `closed`, atau `blocked` (ada kendala terbuka). Respons berisi `summary` seluruh order (tidak terpengaruh filter/pagination), `total` hasil pencarian, dan `orders` pada halaman tersebut. `in_progress` menghitung cutting, sewing, finishing, QC dan rework; `rework` merupakan bagian dari angka tersebut. Pencarian mencakup referensi, judul, SKU dan nama produk. `closed` mencakup order selesai dengan reject. Endpoint ini tetap mewajibkan API key.

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

Tes client JavaScript memerlukan Node 22+: `node tests/test_client.mjs`. Untuk pengujian browser opsional, gunakan Playwright yang tersedia di komputer dan Edge: `python tests/run_browser.py --node PATH_NODE --playwright-module PATH_MODUL_PLAYWRIGHT`. Runner membuat database/server sementara, melakukan uji melalui browser, kemudian menghentikan server dan membersihkan data. Gunakan `--channel chrome` bila memakai Chrome. Playwright hanya alat QA, bukan dependency aplikasi.

## Batas fondasi ini

Server hanya mendengarkan localhost. Rilis ini untuk pengembangan/uji lokal, belum deployment bersama untuk tim. Sebelum dipakai banyak perangkat: siapkan HTTPS, login browser/SSO, kebijakan akses yang lebih rinci, backup terjadwal dengan uji restore, serta validasi alur di lapangan. SQLite cukup untuk uji lokal; evaluasi PostgreSQL saat perlu beberapa instance aplikasi atau penulisan bersamaan lebih tinggi.

Belum mencakup BOM, stok/konsumsi kain, barang hilang di tengah produksi, partial cancellation, perubahan jumlah target setelah order dibuat, bundle/barcode, attachment kendala, atau integrasi Jubelio/Mekari. Schema sekarang versi 3. Saat startup, migrasi 1 → 2 menambahkan tabel kendala dan 2 → 3 menambahkan riwayat tenggat/PIC. Setiap migrasi berjalan dalam satu transaksi tanpa mengubah catatan produksi lama. Buat backup dengan versi aplikasi lama sebelum upgrade. Backup demo sebelum upgrade v0.4 tersedia lokal di `data/backups/demo-before-v04.sqlite3`.

Desain: `docs/design.md`. Rencana dan status implementasi: `docs/implementation-plan.md`.


## Kendala produksi (v0.3)

Buka order → pada SKU pilih **Catat kendala** → pilih tahap, PIC, dan isi hambatan.
Admin/operator dapat mencatat serta menyelesaikan kendala; viewer hanya membaca.
PIC harus aktif saat ditugaskan. Akun PIC yang kemudian dinonaktifkan tetap terlihat dan diberi keterangan.
Admin/operator lain dapat menyelesaikan kendala tersebut; nama pelaku dan waktu tersimpan.

Pilih **Selesaikan kendala**, lalu isi tindakan yang sudah dilakukan. Deskripsi awal dan
penyelesaian pertama tidak bisa ditimpa atau dihapus. Jika catatan keliru, jelaskan koreksi
dalam penyelesaian dan buat catatan baru jika perlu. Belum ada ubah PIC, buka ulang, atau lampiran.
Kendala adalah catatan tindak lanjut; tidak memindahkan saldo, mengunci perpindahan, atau mengubah status selesai order.
Order selesai yang masih punya kendala tetap muncul dalam filter kendala terbuka.

Papan produksi menampilkan jumlah kendala terbuka global dan badge per order. Klik jumlahnya
untuk melihat semua order terkait. Detail menampilkan catatan terbaru dahulu, 100 per halaman.
Gunakan Muat ulang order untuk melihat catatan atau penyelesaian baru dari pengguna lain.

API tambahan (autentikasi dan Idempotency-Key mengikuti transaksi lain):

- `POST /api/issues`: `line_id`, `stage`, `owner_id`, `description` (1–1000 karakter).
- `POST /api/issues/{id}/resolve`: `resolution` (1–1000 karakter).
- `GET /api/orders/{id}/issues?limit=100`: daftar beserta PIC, pencatat dan penyelesaian.
  Halaman berikutnya memakai `before=sequence_terakhir` agar catatan baru tidak menggeser halaman.
- `GET /api/production-board?status=blocked`: order dengan kendala terbuka.
  `open_issues` pada respons board adalah jumlah global; pada setiap order adalah jumlah per order.

Laporan pengujian: `docs/issues-verification.md`.


## Ubah tenggat dan PIC order (v0.4)

Admin membuka order → **Ubah tenggat / PIC** → isi tenggat/PIC baru dan alasan perubahan.
Nilai saat ini sudah terisi. PIC harus akun admin/operator aktif. Satu atau kedua nilai boleh
diubah; perubahan tanpa perbedaan ditolak. Jumlah target, posisi barang, dan PIC pada kendala
tidak ikut berubah. Order yang sudah selesai juga dapat dikoreksi, dengan riwayat yang sama.
Penanda lewat target pada dashboard mengikuti tenggat terbaru.

Semua role dapat membuka **Riwayat tenggat / PIC**. Riwayat menampilkan nilai sebelum/sesudah,
alasan, akun pengubah dan waktu Jakarta; terbaru dahulu dengan tombol memuat 100 catatan berikutnya.
Tidak ada hapus atau edit riwayat. Jika perlu mengembalikan nilai, buat perubahan baru dengan alasannya.

Jika muncul pesan jadwal/PIC sudah diubah, tutup form, muat ulang order, periksa nilai terbaru,
lalu ajukan perubahan lagi. Ini mencegah draft dari tab lama menimpa perubahan orang lain.
Jika hasil penyimpanan belum pasti karena koneksi terputus, gunakan **Coba ulang penyimpanan**.

API: `POST /api/orders/{id}/changes` dengan `owner_id`, `due_date`, `reason` (1–1000 karakter),
dan `expected_revision` dari `GET /api/orders/{id}`. Respons adalah order terbaru (HTTP 201).
Revision tidak harus berurutan per order; gunakan persis angka yang diterima.
Idempotency-Key dan payload yang sama mengembalikan hasil pertama meski order sudah berubah lagi.
Revision yang tertinggal ditolak 409; role selain admin ditolak 403.
`GET /api/orders/{id}/changes?limit=100&before=SEQUENCE_TERAKHIR` membaca riwayat.
Parameter `before` dihilangkan pada halaman pertama. Migrasi menetapkan revision awal 0
pada order lama melalui riwayat kosong; catatan perubahan hanya dibuat untuk edit setelah upgrade.

Verifikasi rilis: `docs/order-changes-verification.md`.


## Aktivitas harian (v0.5)

Klik **Aktivitas harian** di navigasi. Halaman membuka tanggal hari ini menurut Jakarta;
pilih tanggal dan jenis aktivitas untuk menelusuri pencatatan. Semua role dapat membaca.
Setiap catatan menampilkan waktu, akun pencatat, referensi order, SKU bila terkait, dan alasan.
Klik nama order untuk melihat posisi barang serta riwayat lengkapnya.

Jenis yang tersedia: order dibuat, perpindahan barang, koreksi perpindahan, kendala dicatat,
kendala selesai, serta tenggat/PIC diubah. Bukan log administrasi akun atau master SKU.
Ringkasan tanggal selalu mencakup semua jenis, meski daftar difilter atau dipaginasi.

**Gudang bersih** adalah jumlah masuk gudang dikurangi pembalikan penerimaan yang dicatat
pada tanggal tersebut. Misalnya masuk 10 pcs Senin, dibalik Selasa: Senin tetap +10,
Selasa -10. Angka ini bukan stok gudang saat ini, bukan target, dan bukan jumlah barang unik
yang pernah bergerak di semua tahap. Posisi saat ini tersedia di papan produksi.
Kendala dicatat/selesai adalah jumlah kejadian pada tanggal pilihan, bukan sisa kendala terbuka.
Hari kosong menampilkan nol dan pesan tidak ada aktivitas.

`GET /api/activity?day=2026-09-10&kind=all&limit=50` memerlukan X-API-Key.
Hari dihitung dari 00:00 Jakarta (17:00 UTC hari sebelumnya), sampai sebelum 00:00 berikutnya.
`day` yang dihilangkan berarti hari ini. Jenis: `all`, `movement`, `reversal`, `issue_opened`,
`issue_resolved`, `order_created`, `order_changed`. `limit` 1–500, default 50.
Respons berisi `day`, `timezone`, `summary`, `total` yang cocok dengan jenis, `items`, dan
`next_before`. Untuk halaman berikutnya, sertakan kedua nilai `before_time`/`before_id` dari
`next_before` beserta tanggal/jenis yang sama; berhenti jika null. Waktu cursor harus menyertakan
zona waktu. Urutan terbaru dahulu, dengan event ID sebagai pembeda timestamp yang sama.

Gunakan **Tampilkan aktivitas** untuk memuat ulang catatan baru. Halaman lanjutan tidak menyisipkan
catatan terbaru ke awal daftar; ringkasan dan jumlah total diperbarui ketika dimuat.
Laporan membaca catatan yang sudah ada tanpa menulis data atau mengubah schema versi 3.
Untuk order lama, perubahan tenggat/PIC hanya tercatat sejak fitur v0.4 digunakan.

Verifikasi: `docs/activity-verification.md`.
