# Beeloft One

Pelacakan produksi internal, versi 0.15.0. Dashboard dan API memakai database lokal yang sama: order, posisi barang per tahap, perpindahan parsial, QC, serta riwayat koreksi.

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

Belum mencakup barang hilang di tengah produksi, partial cancellation, perubahan jumlah target setelah order dibuat, bundle/barcode, attachment kendala, atau integrasi Jubelio/Mekari. Schema sekarang versi 10. Migrasi 9 → 10 menambahkan hubungan penerimaan batch ke PO. Migrasi 8 → 9 menambahkan master pemasok, PO, dan catatan pembatalannya. Migrasi 7 → 8 menambahkan PR dan riwayat keputusan. Migrasi 6 → 7 menambahkan ledger pemakaian aktual dan waste cutting. Migrasi 5 → 6 menambahkan ledger reservasi. Migrasi 4 → 5 menambahkan versi BOM. Migrasi 3 → 4 menambahkan master bahan, batch, dan ledger bahan. Saat startup, migrasi 1 → 2 menambahkan tabel kendala dan 2 → 3 menambahkan riwayat tenggat/PIC. Setiap migrasi berjalan dalam satu transaksi tanpa mengubah catatan produksi lama. Buat backup dengan versi aplikasi lama sebelum upgrade. Backup demo sebelum upgrade v0.4 tersedia lokal di `data/backups/demo-before-v04.sqlite3`.

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

Klik **Laporan aktivitas** di navigasi. Halaman membuka tanggal hari ini menurut Jakarta;
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


## Rentang tanggal dan CSV (v0.6)

Pada **Laporan aktivitas**, isi **Dari tanggal** dan **Sampai tanggal**, pilih jenis aktivitas,
lalu **Tampilkan aktivitas**. Kedua tanggal ikut dihitung menurut waktu Jakarta. Gunakan tanggal
yang sama untuk satu hari. Rentang maksimal 366 hari. Waktu pada setiap baris sekarang menyertakan
tanggal agar catatan lintas hari dapat dibedakan.

**Unduh CSV** mengambil seluruh hasil yang sesuai filter yang telah dimuat, bukan hanya 50 baris
di layar. Maksimal 10.000 catatan; hasil lebih besar ditolak dengan petunjuk mempersempit filter,
tanpa mengunduh file parsial. Setiap unduhan membaca satu snapshot database; catatan baru yang masuk
sesudah laporan ditampilkan dapat ikut unduhan. Unduhan yang masih diproses dibatalkan dari UI bila
pengguna mengubah filter, keluar akun atau berpindah halaman.

CSV memakai UTF-8 dengan BOM, pemisah koma, dan kolom berbahasa Indonesia. Jika Excel menampilkan
satu kolom, impor lewat **Data → From Text/CSV**, pilih UTF-8 dan pemisah koma. Kolom jumlah tetap
numerik; teks yang diawali tanda formula diberi awalan apostrof. Catatan dengan koma, kutip,
baris baru, serta aksen tetap terjaga. File kosong tetap memuat header kolom.

Kolom: ID kejadian, waktu Jakarta, jenis, referensi/nama order, SKU, jumlah, tahap asal/tujuan,
gudang bersih per kejadian, catatan, pencatat, PIC/kendala asal, tenggat dan PIC sebelum/sesudah.
Ringkasan layar mencakup semua jenis dalam rentang. CSV hanya berisi kejadian sesuai filter jenis;
jumlahkan kolom Gudang bersih pcs untuk arus gudang pada baris yang diekspor.

API lama `day=YYYY-MM-DD` tetap didukung. Untuk rentang gunakan kedua parameter
`start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`; jangan gabungkan dengan `day`.
Respons JSON menambah `start_date` dan `end_date`; `day` dipertahankan sebagai tanggal awal.
Pagination memakai rentang/jenis yang sama beserta cursor sebelumnya.
`GET /api/activity.csv` menerima tanggal/rentang dan `kind` yang sama, tanpa pagination.
Semua role membutuhkan X-API-Key seperti laporan JSON. Tidak ada perubahan schema atau data.

Verifikasi rilis: `docs/export-verification.md`.


## Filter PIC dan posisi barang (v0.7)

Papan produksi sekarang memiliki **PIC order** dan **Posisi barang**. Gabungkan keduanya dengan
status dan pencarian. Contoh: PIC Produksi Demo, posisi Sewing, status Aktif akan menampilkan
order PIC tersebut yang masih memiliki pcs di sewing. Order dengan banyak tahap dapat muncul
di beberapa pilihan posisi, karena filter membaca saldo positif saat ini, bukan riwayat lewat tahap.

Pilihan PIC berasal dari seluruh order, termasuk PIC nonaktif yang masih tercantum pada order.
Label akun nonaktif ditampilkan. Ini PIC order, bukan PIC kendala atau akun yang mencatat perpindahan.
Jika PIC order berubah, order mengikuti PIC terbaru setelah muat ulang. Pilihan yang sedang dipakai
tetap terlihat meski PIC itu tidak lagi memiliki order, dengan hasil kosong sampai filter diganti.

Kembali dari detail order mempertahankan filter. Ganti filter memulai dari halaman pertama.
**Reset filter** mengosongkan pencarian dan mengembalikan semua status, PIC serta posisi.
Klik ringkasan kendala terbuka menghapus filter lain lalu menampilkan semua order berkendala.
Ringkasan angka di atas selalu mencakup seluruh database, bukan hanya hasil filter.

Filter posisi bekerja pada order: minimal satu SKU order harus memiliki saldo di tahap tersebut.
Pencarian SKU dan filter posisi dicocokkan pada order yang sama, tidak harus pada baris SKU yang sama.
Saldo nol tidak cocok. Gudang/reject dapat dipilih, termasuk pada order selesai.

API `GET /api/production-board` menambah `owner_id` (kosong berarti semua) dan `stage`
(`all`, `planned`, `cutting`, `sewing`, `finishing`, `qc`, `rework`, `reject`, `warehouse`).
Respons menambah `owners` berisi id, name dan active dari seluruh PIC yang memiliki order,
tanpa dipengaruhi filter/pagination. Ketentuan autentikasi dan role baca tetap sama.
Tidak ada perubahan schema/database atau dependency baru.

Verifikasi: `docs/board-filters-verification.md`.


## Cadangan dari dashboard (v0.8)

Masuk sebagai admin → **Cadangan data** → **Unduh cadangan database**. Periksa unduhan browser
untuk memastikan file `.sqlite3` telah tersimpan. Nama file memuat waktu UTC. Simpan salinan di
lokasi pribadi yang berbeda dari disk produksi agar tetap tersedia jika disk utama rusak.

Cadangan mencakup seluruh database: order, produk, saldo, perpindahan, kendala, riwayat perubahan,
akun, hash kunci akses dan receipt transaksi. Kunci asli tidak ada dalam file; simpan kunci yang
sudah dimiliki agar dapat masuk setelah pemulihan. Operator/viewer tidak boleh mengunduh database
utuh, meskipun dapat membaca data produksi lewat halaman biasa.

Cadangan memakai SQLite backup API, termasuk perubahan yang sudah commit di WAL, dan dapat
diambil saat server berjalan. Data setelah snapshot tidak masuk file tersebut. Tidak ada perubahan
data sumber. File sementara server dibersihkan setelah isinya siap dikirim, juga saat operasi gagal.
Setiap klik menghasilkan snapshot baru; tidak membutuhkan Idempotency-Key. Kegagalan ruang disk
atau pembuatan salinan menghasilkan 503, tanpa file parsial. UI dapat dicoba ulang.

### Memeriksa cadangan tanpa mengganti database produksi

1. Salin file unduhan ke lokasi uji baru, misalnya `data/restore-check.sqlite3`. Jangan menimpa database aktif atau satu-satunya arsip cadangan.
2. Dari folder proyek jalankan `.\.venv\Scripts\python.exe -m beeloft --db data/restore-check.sqlite3 serve --port 8766`.
3. Buka `http://127.0.0.1:8766/`, masuk dengan kunci yang aktif saat snapshot diambil, lalu cocokkan order, saldo dan riwayat penting. Gunakan salinan uji karena menjalankan versi aplikasi lebih baru dapat memigrasikan schema.
4. Hentikan server uji dengan Ctrl+C setelah selesai. File produksi tidak diganti oleh proses ini.

API: `GET /api/backup` memakai X-API-Key admin aktif. Respons `application/vnd.sqlite3`,
Content-Disposition attachment dan Cache-Control no-store; role lain 403, key invalid/nonaktif 401.
Endpoint tidak menerima pilihan path atau nama database dari pemanggil.

Untuk database besar, gunakan CLI `backup` pada server: unduhan dashboard menampung file di memori
server dan browser serta mengikuti timeout client 15 detik. Rilis ini belum menyediakan pemulihan
langsung melalui dashboard, penjadwalan otomatis, enkripsi arsip atau sinkronisasi ke cloud.

Verifikasi: `docs/backup-download-verification.md`.

## Bahan baku dan batch (v0.9 — Phase 2 roadmap)

Status seluruh fase blueprint dan batas increment ini ada di [roadmap bahan](docs/materials-plan.md).
Produksi menjadi prioritas awal sesuai kebutuhan pelacakan internal. Integrasi Jubelio/Mekari
pada Phase 1 belum dikerjakan; tahap bahan ini tidak berarti seluruh Phase 2 selesai.

1. Admin membuka **Bahan baku → Master bahan → Tambah bahan**. Pilih satuan dasar meter (m), kilogram (kg), atau pcs.
2. Admin/operator memilih **Terima batch bahan**: bahan, referensi batch unik, pemasok, lokasi/rak, tanggal diterima, jumlah layak pakai dan alasan.
3. Buka order produksi → **Keluarkan bahan ke order**. Pilih batch dengan saldo positif dan catat jumlah yang benar-benar dikeluarkan dari rak.
4. **Riwayat bahan order** menunjukkan batch yang dipakai beserta pencatat/alasan. Klik referensi batch di halaman Bahan baku untuk riwayat penerimaan, pengeluaran, dan pembalikannya.
5. Admin memilih **Koreksi catatan bahan**, lalu mengisi alasan. Pembalikan mengembalikan seluruh jumlah catatan; untuk jumlah berbeda, catat transaksi baru setelah koreksi.

Contoh: terima 10,125 m lalu keluarkan 2,125 m ke order → saldo rak 8 m. Membalik pengeluaran
tersebut → saldo kembali 10,125 m. Pengeluaran tidak mengubah pcs maupun tahap WIP order.
Pada increment v0.9 ini belum ada pencatatan konsumsi aktual, hasil cutting atau waste; angka meter
dan kilogram tidak dijumlahkan.

Kode/nama/satuan master dan metadata batch tidak dapat diedit. Penerimaan yang keliru harus
dibalik, lalu diterima sebagai batch baru dengan referensi berbeda. Pembalikan penerimaan ditolak
jika bahan masih dikeluarkan ke order; pastikan bahan fisik kembali dan balik pengeluarannya dahulu.
Catatan pembalik tidak bisa dibalik lagi. Batch bersaldo nol tetap tampil untuk audit.
Lokasi adalah lokasi penerimaan; perpindahan fisik antarrak belum tersedia.

Jumlah m/kg menerima maksimal tiga desimal; pcs wajib bulat, maksimal 1.000.000 satuan per
transaksi. Angka di database berupa bilangan bulat per seribu satuan agar tidak mengalami
pembulatan floating point. Tidak ada konversi roll ke meter. Penerimaan hanya mencatat bahan
yang diterima layak pakai; barang hold/reject, reservasi, BOM, PR/PO, biaya dan master pemasok
belum masuk tahap ini. Saldo rak bukan ketersediaan setelah reservasi atau jaminan cukup untuk semua order.

Semua role dapat membaca. Hanya admin membuat master dan membalik catatan; admin/operator
menerima/mengeluarkan bahan. Catatan tetap menyimpan ID/nama pencatat meskipun akun kemudian
dinonaktifkan. Waktu pencatatan memakai UTC, tampil di UI dalam waktu Jakarta. Tanggal penerimaan
diisi pengguna dan tidak mengganti waktu audit. Riwayat bahan terpisah dari Laporan aktivitas produksi.

API tambahan, dengan X-API-Key dan Idempotency-Key pada semua POST:

| Endpoint | Isi / hasil |
|---|---|
| `POST /api/materials` | `code`, `name`, `unit` (`m`, `kg`, `pcs`) |
| `GET /api/materials` | Master bahan, `limit`/`offset` |
| `POST /api/material-batches` | `material_id`, `reference`, `supplier`, `location`, `received_date`, `quantity`, `reason` |
| `GET /api/material-batches` | Batch dan saldo; filter `material_id`, `limit`/`offset` |
| `GET /api/material-batches/{id}` | Detail batch, `balance`, `receipt_id` |
| `POST /api/material-issues` | `batch_id`, `order_id`, `quantity`, `reason` |
| `POST /api/material-movements/{id}/reverse` | `reason` |
| `GET /api/material-batches/{id}/movements` | Riwayat batch terbaru dahulu |
| `GET /api/orders/{id}/material-movements` | Riwayat pengeluaran/pembalikan order terbaru dahulu |

Kirim jumlah sebagai **string desimal**, misalnya `"2.125"`; bukan JSON float atau angka dengan koma.
Respons saldo dan jumlah juga string tiga desimal. Jumlah positif menambah stok rak; negatif
mengurangi stok rak. Normalisasi desimal membuat `"2"` dan `"2.000"` payload yang sama untuk retry.
Riwayat menerima `limit` (1–500, default 100) dan `before` dari sequence terakhir; halaman pertama
tanpa `before`. Field `reversed_by` tetap menunjukkan pembalikan walau catatan pembalik berada
di halaman lain. Setiap baca memperoleh snapshot tersendiri; muat ulang untuk perubahan terbaru.

Schema 3 → 4 menambahkan tabel bahan tanpa mengubah pcs, order, atau riwayat produksi lama.
Backup memakai versi lama sebelum upgrade. Cadangan database sekarang juga menyertakan semua
master, batch dan catatan bahan. Pengujian tetap memakai database sementara.

Pengerjaan v0.9 berada di worktree lokal `.worktrees/core-materials`, branch `feature/core-materials`.
Jalankan `./start.ps1 -Demo` dari worktree tersebut untuk membuat demo terpisah; tidak memakai
database demo pada checkout main. Demo awal belum berisi bahan; tambahkan dari dashboard.

Hasil pengujian: [verifikasi bahan](docs/materials-verification.md).

## BOM dan kebutuhan bahan (v0.10 — Phase 2 roadmap)

Admin membuka **Master SKU → BOM → Isi BOM**. Tambahkan bahan dan jumlah yang dibutuhkan
untuk membuat **1 pcs** SKU, lalu isi alasan. Contoh: 1,25 m kain dan 2 pcs kancing per produk.
Satu BOM memuat 1–100 bahan unik. Satuan mengikuti master; m/kg maksimal tiga desimal, pcs
wajib bulat. Jumlah maksimal 1.000.000 satuan per pcs. Tidak ada konversi satuan atau tambahan
waste otomatis. Gunakan angka standar yang sudah disepakati di produksi.

**Ubah BOM** membuat versi baru; isi versi lama tetap tersedia di **Riwayat BOM**, beserta
alasan dan akun pengubah. Perubahan tanpa perbedaan ditolak. Jika form sudah tertinggal karena
tab lain menyimpan versi baru, tutup form, buka BOM lagi dan periksa sebelum menyimpan ulang.
Tidak ada hapus/nonaktif BOM pada tahap ini. Operator/viewer dapat membaca BOM dan riwayat,
tetapi hanya admin aktif yang boleh menyimpan. BOM audit terpisah dari laporan aktivitas produksi.

Buka order → **Kebutuhan bahan**. Perhitungan menggabungkan bahan yang sama di seluruh SKU:

| Angka | Perhitungan |
|---|---|
| Kebutuhan total | Jumlah target masing-masing SKU × BOM per pcs, lalu dijumlahkan per bahan |
| Dikeluarkan bersih | Pengeluaran bahan ke order dikurangi pembalikannya |
| Sisa kebutuhan | Maksimum(kebutuhan total − dikeluarkan bersih, 0) |
| Stok rak saat ini | Saldo semua batch bahan tersebut setelah penerimaan, pengeluaran dan koreksi |
| Kekurangan | Maksimum(sisa kebutuhan − stok rak, 0) |

Jika kebutuhan 20 m, sudah dikeluarkan 4,125 m dan stok rak 10,875 m, sisa kebutuhan 15,875 m
dan kekurangan 5 m. Jika pengeluaran dikembalikan melalui pembalikan, dikeluarkan bersih
berkurang dan stok rak bertambah. Pengeluaran melebihi kebutuhan tidak membuat sisa negatif.
Bahan yang sudah dikeluarkan tetapi tidak ada dalam BOM saat ini tetap tampil dengan label
**Dikeluarkan di luar BOM saat ini**. Ini tidak otomatis dianggap kesalahan transaksi.

**Estimasi memakai BOM terbaru saat dimuat**, termasuk untuk order lama. Daftar dasar perhitungan
menunjukkan SKU, target dan versi BOM sumber. Ini belum snapshot BOM saat order dibuat.
Target tetap penuh meskipun sebagian pcs sudah selesai/reject; posisi WIP tidak mengurangi
kebutuhan teoritis. Bahan dikeluarkan belum berarti sudah dikonsumsi. Gunakan hasil sebagai
bantuan perencanaan dan cocokkan dengan kondisi fisik.

SKU tanpa BOM memunculkan peringatan **Perhitungan belum lengkap**. Angka yang ada hanya
mencakup SKU yang sudah memiliki BOM; BOM kosong tidak dianggap butuh nol bahan. Tidak ada
penanda seluruh order cukup jika datanya belum lengkap. Stok belum direservasi, bisa dipakai
order lain, dan tidak boleh menjumlahkan indikator cukup antarorder sebagai jaminan stok bersama.
Tombol **Hitung ulang kebutuhan** mengambil snapshot terbaru. Membaca estimasi tidak menulis
stok, mengunci order, atau memulai produksi.

API dengan X-API-Key; POST juga memakai Idempotency-Key:

- `GET /api/products/{id}/bom`: versi terbaru; `revision=0`, `components=[]` jika belum ada.
- `POST /api/products/{id}/bom`: `expected_revision`, `reason`, `components` berisi `material_id` dan `quantity` string, misalnya `"1.250"`. API menormalisasi angka dan mengurutkan komponen untuk retry konsisten. Revisi dari versi terakhir harus dipakai persis; nomornya global sehingga dapat meloncat antar-SKU.
- `GET /api/products/{id}/bom-history?limit=100&before=REVISION`: terbaru dahulu; hilangkan `before` pada halaman pertama.
- `GET /api/orders/{id}/material-requirements`: `basis=latest_bom`, `complete`, `missing_bom`, `sources`, dan `materials` dengan `required`, `issued`, `remaining`, `stock`, `shortage`, `outside_bom`. Semua jumlah bahan berupa string desimal tiga angka; tidak ada total lintas satuan.

Migrasi schema 4 → 5 hanya menambahkan riwayat BOM. Data produksi/bahan lama tetap; tidak
ada BOM contoh yang dibuat otomatis. Backup sebelum upgrade, seperti versi sebelumnya.
Perhitungan agregasi memakai integer Python dan tampilan jumlah memakai BigInt sehingga
angka besar tidak kehilangan desimal. Saat ini pembacaan stok memindai ledger bahan;
evaluasi saldo teragregasi bila volume transaksi menyebabkan halaman lambat.

Tetap di worktree `feature/core-materials`, tanpa push GitHub. Setelah BOM dasar ini,
tahap berikutnya adalah reservasi bahan per order sebelum memperluas ke konsumsi aktual dan PR/PO.
Rencana: [BOM](docs/bom-plan.md). Hasil pengujian: [verifikasi BOM](docs/bom-verification.md).

## Reservasi bahan per order (v0.11 — Phase 2 roadmap)

Bagian ini memperbarui batas v0.9/v0.10 di atas: stok bahan sekarang dapat direservasi secara
manual per batch dan order. Perhitungan kebutuhan sekarang mengurangi reservasi milik order lain
dari bahan yang dapat dipakai order ini. Riwayat versi sebelumnya tetap dicantumkan sebagai konteks rilis.

Admin: buka order → **Reservasi bahan → Tambah reservasi**. Pilih batch dan isi jumlah tambahan
beserta alasan. Jumlah tersebut menjadi jatah order tanpa mengubah stok fisik. **Lepaskan reservasi**
mengurangi jatah tersisa dan membebaskan bahan untuk order lain. Kedua tindakan menerima jumlah
positif dan memakai satuan master, maksimal tiga desimal; pcs bulat. Jumlah adalah perubahan
(tambahkan/lepaskan), bukan penggantian total. Minimal 0,001 m/kg atau 1 pcs, maksimal 1.000.000 satuan.

Halaman bahan menampilkan **saldo batch**, **direservasi**, dan **bebas**. Stok bebas = saldo fisik
dikurangi seluruh reservasi batch. Order hanya dapat mengeluarkan jatah sendiri + stok bebas.
Admin/operator tetap memakai **Keluarkan bahan ke order**; sistem menghabiskan jatah sendiri
terlebih dahulu sebelum memakai stok bebas, dalam transaksi yang sama dengan pengeluaran.
Tidak perlu melepas jatah secara manual sebelum pengeluaran. Alokasi order lain tidak dapat diambil.

Contoh: batch 10 m, order A reservasi 6 m → bebas 4 m. Order B maksimal mengeluarkan 4 m.
Jika A mengeluarkan 2 m, stok menjadi 8 m, jatah A 4 m, bebas tetap 4 m. Jika A kemudian melepas
1 m, jatah A menjadi 3 m dan bebas 5 m. Penulisan bersamaan tidak bisa menjanjikan stok yang sama
dua kali. Retry dengan key/payload yang sama tidak menggandakan jatah.

**Pembalikan pengeluaran mengembalikan stok bebas**, tanpa membuat ulang reservasi yang sudah
terpakai. Buat reservasi baru bila bahan perlu dialokasikan lagi. Penerimaan tidak dapat dibalik
jika batch masih mempunyai reservasi atau pengeluaran yang belum dikembalikan. Lepaskan seluruh
jatah tersisa dan cocokkan kondisi fisik sebelum koreksi penerimaan. Semua catatan tetap utuh.

Reservasi tidak otomatis mengikuti BOM, tidak kedaluwarsa, dan tidak otomatis dilepas saat order
selesai. Admin perlu meninjau jatah tersisa, termasuk bila BOM berkurang atau bahan tidak lagi
dipakai. Alokasi di luar BOM diperbolehkan dengan alasan dan terlihat dalam rincian kebutuhan.
Belum ada reservasi otomatis/FIFO, persetujuan alokasi, atau penguncian produksi berdasarkan BOM.

**Kebutuhan bahan** sekarang memuat reservasi sendiri, reservasi order lain, stok bebas dan
jumlah yang bisa dipakai order ini. Rumus kekurangan menjadi:

```text
Sisa kebutuhan = max(kebutuhan total − dikeluarkan bersih, 0)
Bisa dipakai order ini = stok bebas + reservasi order ini
Kekurangan = max(sisa kebutuhan − bisa dipakai order ini, 0)
```

Stok fisik tetap tampil sebagai pembanding, bukan jumlah bebas. Reservasi sendiri tidak mengurangi
kebutuhan total atau dikeluarkan bersih karena bahan belum berpindah. Estimasi tetap memakai BOM
terbaru; stok bebas dapat berubah sesudah dimuat. Peringatan BOM belum lengkap tetap berlaku.

Semua role membaca jatah/riwayat. Hanya admin aktif menambah/melepas reservasi. Admin/operator
mengeluarkan bahan dengan pembatasan yang sama. Riwayat reservasi menyimpan batch, order, jumlah
bertanda, alasan, akun dan waktu Jakarta: penambahan (+), pelepasan (-), pemakaian oleh pengeluaran
(-). Catatan pemakaian memiliki ID perpindahan terkait; tidak dapat diedit/dihapus.

API tambahan memakai X-API-Key, POST juga Idempotency-Key:

- `POST /api/material-reservations`: `batch_id`, `order_id`, `action` (`reserve`/`release`), `quantity` string positif dan `reason`.
- `GET /api/orders/{id}/material-reservations?limit=100&offset=0`: batch yang pernah dialokasikan untuk order, termasuk jatah tersisa nol.
- `GET /api/orders/{id}/reservation-history?limit=100&before=SEQUENCE`: riwayat terbaru dahulu, hilangkan `before` di halaman pertama.
- `GET /api/material-batches?order_id=ID`: menambahkan konteks order untuk setiap batch. Parameter tetap opsional; ID tidak ditemukan ditolak 404.

Respons batch menambah `reserved` (semua order), `available` (bebas), `reserved_for_order`,
`available_to_order`. Dua field terakhir pada daftar tanpa konteks order bernilai nol dan stok bebas.
Detail batch tunggal juga tanpa konteks order. Daftar reservasi order memakai arti field yang sama,
bukan mengganti `reserved` dengan jatah sendiri. Semua jumlah tetap string tiga desimal.
Respons kebutuhan menambah `reserved_own`, `reserved_other`, `available`, `available_to_order`;
`stock` tetap stok fisik, `shortage` kini memperhitungkan reservasi lain. `outside_bom` juga dapat
menandai bahan yang direservasi di luar BOM saat ini.

Schema 5 → 6 menambahkan event reservasi. Semua stok lama awalnya bebas, karena tidak ada alokasi
historis yang diada-adakan. Backup sekarang menyertakan ledger reservasi. Tetap buat backup
dengan aplikasi lama sebelum upgrade. Pengujian dilakukan di database sementara.

Pengerjaan tetap di `feature/core-materials`, tanpa push atau merge main. Berikutnya: pencatatan
konsumsi aktual dan waste cutting, sebelum perluasan PR/PO. Rencana dan verifikasi ada di
[reservasi](docs/reservations-plan.md) dan [hasil uji](docs/reservations-verification.md).

## Pemakaian aktual dan waste cutting (v0.12 — Phase 2 roadmap)

Pada detail order, buka **Pemakaian & waste** untuk melihat setiap pengeluaran bahan dan
melaporkan jumlah yang benar-benar terpakai serta jumlah yang menjadi waste cutting. Pelaporan
boleh bertahap; sisa yang belum dilaporkan ditampilkan terpisah dari saldo fisik. Setiap catatan
menyimpan batch, alasan, akun dan waktu, sehingga operator tidak perlu menebak pemakaian dari
perpindahan WIP.

Jumlah pemakaian dan waste memakai satuan batch (m/kg maksimal tiga desimal, pcs bulat), minimal
satu di antaranya positif, dan total bersih tidak boleh melebihi pengeluaran bahan terkait.
Admin/operator dapat mencatat. Hanya admin yang dapat membalik catatan pemakaian, dan pembalikan
selalu membuat catatan pasangan yang immutable. Pengeluaran bahan tidak dapat dibalik ke rak selama
masih ada pemakaian atau waste bersih; balik catatan pemakaian dahulu lalu catat koreksi baru.

Pencatatan pemakaian tidak mengubah saldo batch, reservasi, atau jumlah WIP. Waste tidak masuk
sebagai stok yang dapat dipakai ulang. Belum ada pengembalian sebagian, sisa kain reusable,
tautan ke output cutting, perhitungan biaya, atau forecast waste. Semua pembacaan boleh dilakukan
oleh seluruh role; POST memakai `X-API-Key` dan `Idempotency-Key`.

API tambahan:

- `POST /api/material-consumption`: `issue_id`, `used`, `waste`, `reason`.
- `POST /api/material-consumption/{id}/reverse`: `reason` admin-only.
- `GET /api/orders/{id}/material-consumption?limit=100&offset=0`: ringkasan pengeluaran, pemakaian,
  waste dan sisa belum dilaporkan per batch.
- `GET /api/orders/{id}/consumption-history?limit=100&before=SEQUENCE`: ledger terbaru dahulu;
  hilangkan `before` pada halaman pertama.

Schema 6 → 7 menambahkan ledger pemakaian tanpa mensintesis histori lama. Backup sebelum upgrade
tetap wajib. Rencana: [pemakaian](docs/consumption-plan.md). Hasil uji: [verifikasi pemakaian](docs/consumption-verification.md).

## Permintaan pembelian (v0.13 — Phase 2 roadmap)

Pembelian dimulai dari PR, sesuai blueprint halaman 7. Buka **Permintaan pembelian → Buat PR**,
atau dari detail produksi buka **PR untuk order ini** agar order terpilih otomatis.
Isi referensi unik, tanggal dibutuhkan, estimasi total rupiah, alasan dan bahan yang diminta.
Order bersifat opsional untuk permintaan umum. Pengajuan langsung berstatus **Menunggu keputusan**.

Satu PR berisi 1–100 bahan berbeda; gabungkan bahan yang sama menjadi satu baris. Jumlah positif
maksimal 1.000.000 satuan per bahan, m/kg maksimal tiga desimal dan pcs bulat. Estimasi total
seluruh PR wajib positif, maksimal Rp1.000.000.000.000,00, dengan dua desimal. Angka ini diisi
manual sebagai estimasi pengajuan; belum ada harga pemasok, pajak, ongkir, kurs atau biaya aktual.
Nilai tersimpan sebagai integer per 0,01 rupiah dan API mengembalikannya sebagai string.

| Pelaku | Tindakan |
|---|---|
| Admin/operator | Mengajukan PR |
| Admin | Menyetujui/menolak pengajuan; membatalkan PR yang menunggu atau sudah disetujui |
| Operator pemohon | Membatalkan PR miliknya sendiri yang masih menunggu keputusan |
| Semua role aktif | Membaca daftar, rincian dan riwayat; filter status dan order |

Setiap keputusan wajib beralasan dan memakai revisi terakhir. Jika tab lain sudah mengambil
keputusan, tutup form dan muat ulang rincian. Retry dengan key/payload yang sama mengembalikan
hasil awal; tidak menciptakan keputusan baru. Catatan pengajuan dan riwayat tidak dapat diedit
atau dihapus. Untuk koreksi, batalkan lalu ajukan referensi baru. PR ditolak/dibatalkan bersifat final.

Untuk operasi sendiri, admin dapat menyetujui pengajuannya sendiri. Semua nilai memerlukan
keputusan admin; belum ada aturan ambang nilai atau pemisahan pemohon dan pemberi persetujuan.
Pengaturan tersebut dan antrean persetujuan lintas modul masuk Phase 4.

PR yang disetujui **belum otomatis menjadi PO ke pemasok**. Pengajuan tidak mengubah stok, reservasi,
WIP atau hasil perhitungan kekurangan BOM. Buka daftar PR yang masih aktif sebelum mengajukan
bahan lagi; dua pengajuan dengan referensi berbeda tidak otomatis dianggap duplikat.
Ringkasan kebutuhan tetap memakai BOM terbaru, sedangkan rincian PR menyimpan bahan/jumlah yang
diajukan. Tidak ada pengajuan otomatis berdasarkan BOM atau asumsi bahwa bahan sudah dipesan.

API dengan X-API-Key; semua POST juga memakai Idempotency-Key:

- `POST /api/purchase-requests`: `reference`, `order_id` (opsional/null), `required_date`,
  `estimated_value` string seperti `"123456.78"`, `reason`, dan `lines` berisi
  `material_id` serta `quantity` string.
- `GET /api/purchase-requests?status=all&limit=100&before=SEQUENCE&order_id=ID`:
  terbaru dahulu; before/order_id opsional. Status: all/submitted/approved/rejected/cancelled.
- `GET /api/purchase-requests/{id}`: rincian, revisi terakhir dan riwayat keputusan.
- `POST /api/purchase-requests/{id}/decisions`: `status` approved/rejected/cancelled,
  `expected_revision` dari rincian terakhir dan `reason`.

Revisi adalah sequence global keputusan, sehingga nomornya dapat meloncat antar-PR.
Migrasi 7 → 8 mempertahankan data lama; PR historis tidak dibuat otomatis. Backup aplikasi
mencakup PR dan seluruh keputusan. Rencana: [PR](docs/purchase-requests-plan.md).
Hasil pengujian: [verifikasi PR](docs/purchase-requests-verification.md).
Tahap berikutnya: master pemasok dan PO yang merujuk PR disetujui, termasuk harga dan tanggal datang.

## Pemasok dan PO (v0.14 — Phase 2 roadmap)

Dari **Permintaan pembelian → Master pemasok**, admin memilih **Tambah pemasok** dan mengisi
kode unik, nama, kontak/alamat opsional serta alasan. Kode dinormalisasi ke huruf besar.
Identitas master disimpan permanen; jika salah, buat kode baru untuk pembelian berikutnya.
Semua role aktif dapat membaca master pemasok dan daftar/rincian PO.

Buka PR yang sudah disetujui → **Buat PO dari PR**. Pilih satu pemasok, isi referensi PO unik,
perkiraan tanggal datang, syarat pembelian, harga satuan setiap bahan dan alasan.
Seluruh bahan dan jumlah mengikuti PR. Harga, identitas pemasok, revisi PR, jumlah dan syarat
terkunci saat dicatat. **Daftar PO** menyediakan filter aktif/dibatalkan; rincian PR juga
menautkan semua PO terkait termasuk yang pernah dibatalkan.

Harga satuan berupa rupiah positif, maksimal Rp1.000.000.000,00, dua desimal.
Nilai baris = jumlah PR × harga satuan, dibulatkan half-up ke 0,01 rupiah; total adalah
penjumlahan nilai baris yang sudah dibulatkan. Tiap nilai baris setelah pembulatan minimal Rp0,01.
Form menampilkan total selama harga diisi; server menghitung ulang dengan aritmetika desimal.
Contoh 2,125 m × Rp12,34 = Rp26,22. Tidak ada penjumlahan jumlah lintas satuan.

**Total PO tidak boleh melebihi estimasi PR yang sudah disetujui.** Jika nilainya perlu naik,
buat pengajuan baru dengan estimasi yang sesuai dan persetujuan baru. PO yang sudah ada harus
dibatalkan dahulu sebelum PR asalnya dapat dibatalkan. Belum ada pajak, ongkir, diskon, kurs,
atau persetujuan harga PO secara terpisah; syarat pembelian berupa catatan bebas.

Hanya admin membuat pemasok, mencatat PO dan membatalkan PO. Maksimal satu PO aktif untuk satu PR.
Untuk koreksi PO, **Batalkan PO** dengan alasan lalu buat PO pengganti dengan referensi baru.
PO asli dan pembatalan tetap utuh. PR tetap disetujui setelah PO dibatalkan, sehingga dapat dipakai
untuk pengganti atau dibatalkan tersendiri. Tidak ada pembatalan sebagian atau pembukaan ulang PO.
Retry dengan key/payload sama mempertahankan respons awal meskipun status sesudahnya berubah.

Status aktif/issued berarti **tercatat internal**. Aplikasi tidak mengirim PO atau pembatalan ke pemasok.
Pembuatan PO belum menambah stok maupun mengurangi kekurangan BOM. Mulai v0.15, penerimaan
dicatat dari rincian PO seperti dijelaskan di bawah. Pembayaran, split pemasok atau split PR
belum tersedia. Batch penerimaan manual tetap tidak terkait PO.

API memakai X-API-Key; POST juga Idempotency-Key:

- `POST /api/suppliers`: `code`, `name`, `contact`/ `address` opsional, `reason`.
- `GET /api/suppliers?limit=100&offset=0`.
- `POST /api/purchase-orders`: `reference`, `request_id`, `expected_revision` dari PR,
  `supplier_id`, `expected_date`, `terms`, `reason` dan `prices` berisi
  `material_id`/`unit_price` string untuk tepat semua bahan PR. Quantity diambil server dari PR.
- `GET /api/purchase-orders?limit=100&before=SEQUENCE&status=all&request_id=ID`:
  before dan request_id opsional; status all/issued/cancelled.
- `GET /api/purchase-orders/{id}`: snapshot pemasok, baris, total, sumber PR dan pembatalan.
- `POST /api/purchase-orders/{id}/cancel`: `reason`.

Rincian PR menambahkan `purchase_orders` dengan id/referensi/status. Schema 8 → 9 bersifat
tambahan, tanpa mengarang pemasok dari teks batch lama. Backup/restore mencakup tabel baru.
Rencana dan batas: [PO](docs/purchase-orders-plan.md); hasil uji: [verifikasi PO](docs/purchase-orders-verification.md).


## Penerimaan dari PO (v0.15)

Buka **Permintaan pembelian → Daftar PO → Rincian PO → Terima bahan dari PO**.
Admin dan operator memilih satu bahan dari PO, mengisi referensi batch unik, lokasi/rak,
tanggal diterima, jumlah layak pakai dan alasan. Pemasok diambil dari PO secara otomatis.
Satu pencatatan membuat satu batch dan menambah stok dalam transaksi yang sama; kiriman
bertahap atau lot berbeda dicatat sebagai batch berikutnya. Viewer hanya membaca.

Jumlah tidak boleh melebihi sisa pesanan per bahan. Satuan pcs harus bulat, m/kg maksimal
tiga desimal. Rincian PO menampilkan jumlah dipesan, diterima bersih, sisa, status penerimaan
(belum/sebagian/lengkap) dan seluruh riwayat batch. Pengeluaran bahan ke produksi tidak
mengurangi jumlah diterima pada PO. PO aktif tetap berstatus `issued` ketika lengkap;
kemajuan penerimaan ada di `fulfillment`.

Dari riwayat penerimaan, buka batch untuk melihat ledger atau melakukan koreksi admin.
Pembalikan penerimaan mengurangi stok dan mengembalikan sisa pesanan secara bersamaan.
Batch yang masih dikeluarkan atau direservasi tidak dapat dibalik. Koreksi catatan harus
sesuai kondisi bahan fisik. PO tidak dapat dibatalkan selama ada penerimaan aktif.
Seluruh penerimaan harus dibalik sebelum pembatalan PO; belum ada penutupan sisa pesanan
atau retur sebagian ke pemasok.

API baru: `POST /api/purchase-orders/{id}/receipts` dengan `material_id`, `reference`,
`location`, `received_date`, `quantity` string dan `reason`. Memakai X-API-Key dan
Idempotency-Key, mengembalikan batch yang dibuat. Retry key/payload yang sama tetap
mengembalikan hasil awal, tanpa menambah stok lagi. GET PO menambahkan `fulfillment`,
`lines[].received`, `lines[].remaining`, dan `receipts` termasuk koreksinya. GET batch
menambahkan `purchase_order_id`/`purchase_order_reference` (null untuk penerimaan manual).

Penerimaan manual lama tetap tersedia dan tidak otomatis dipasangkan ke PO. Migrasi tidak
mengarang hubungan dari nama pemasok atau referensi batch. Backup/restore memuat hubungan baru.
Barang hold/reject belum masuk pencatatan ini; hanya bahan yang sudah diperiksa layak pakai.
Tahap berikutnya: pemeriksaan bahan masuk dengan jumlah diterima, diterima layak, hold/reject,
dan keputusan pelepasan stok. Bukti pengujian: [verifikasi penerimaan PO](docs/po-receipts-verification.md).
