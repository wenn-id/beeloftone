# Beeloft One

Pelacakan produksi internal, versi 0.48.0. Dashboard dan API memakai database lokal yang sama: order, posisi barang per tahap, hasil cutting, identitas bundle, job sewing/makloon, finishing, final QC, penerimaan barang jadi, pergerakan gudang, reservasi marketplace, picking, packing, shipping, settlement penjualan, retur pelanggan, adjustment, stock opname, biaya produksi aktual, margin kontribusi, forecast demand, risiko stockout, rekomendasi produksi dan pembelian bahan, inbox approval, investigasi bisnis berbahasa Indonesia, tindakan AI yang memerlukan approval, riwayat investigasi dan feedback tim, status sinkronisasi Jubelio/Mekari, mapping SKU, serta snapshot stok, order, penjualan, retur, dan listing Jubelio serta ringkasan keuangan Mekari.

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

Koreksi: `POST /api/movements/{id}/reverse` dengan `{"reason":"Salah input jumlah"}`. Pembalikan mengembalikan **seluruh jumlah transaksi asal**, hanya sekali. Jika jumlah yang benar berbeda, setelah pembalikan buat perpindahan baru. Pembalikan ditolak apabila saldo tahap tujuan sudah tidak cukup; telusuri transaksi lanjutannya terlebih dahulu. Riwayat asli tidak dihapus. Perpindahan tetap memakai saldo per SKU; identitas bundle dicatat lewat alur Bundling dan belum mengikuti perpindahan antar tahap.

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

Belum mencakup partial cancellation, perubahan jumlah target setelah order dibuat, barcode/cetak/scan bundle, attachment kendala, atau konektor aktif ke Jubelio/Mekari. Schema sekarang versi 39. Migrasi 38 → 39 menambahkan snapshot ringkasan keuangan Mekari per periode. Migrasi 37 → 38 menambahkan snapshot listing marketplace Jubelio dan karantina identifier yang tidak aman. Migrasi 36 → 37 menambahkan snapshot retur Jubelio, baris SKU, dan karantina whole-return. Migrasi 35 → 36 menambahkan snapshot order dan baris SKU Jubelio beserta karantina whole-order. Migrasi 34 → 35 menambahkan batch snapshot stok Jubelio, item yang diterima, serta karantina identifier yang tidak aman. Migrasi 33 → 34 menambahkan mapping SKU eksternal Jubelio dan riwayat revisi immutable. Migrasi 32 → 33 menambahkan ledger run sinkronisasi immutable dan peta source of truth. Migrasi 31 → 32 menambahkan riwayat investigasi AI, feedback, dan linkage tindakan. Migrasi 30 → 31 menambahkan proposal tindakan AI beserta keputusan approval. Migrasi 29 → 30 menambahkan settlement penjualan marketplace, koreksi immutable, snapshot cakupan retur, dan guard pengiriman. Migrasi 28 → 29 menambahkan request dan approval budget marketing dengan periode, channel, objective, nominal, role guard, dan ledger keputusan immutable. Migrasi 27 → 28 menambahkan request dan approval pembayaran supplier, batas nilai penerimaan aktif, serta guard koreksi receipt. Migrasi 26 → 27 menambahkan approval penerbitan PO, backfill PO historis sebagai approved, serta guard penerimaan/QC. Migrasi 25 → 26 menambahkan ledger permintaan perubahan produksi, keputusan immutable, penerapan perubahan order atomik, revision guard, serta inbox approval gabungan dengan PR. Migrasi 24 → 25 menambahkan ledger stock opname barang jadi, snapshot saldo sistem, jumlah fisik, adjustment selisih yang terhubung, koreksi immutable, scan SKU, serta guard reserved stock. Migrasi 23 → 24 menambahkan ledger retur pelanggan dan adjustment barang jadi, alasan retur terstruktur, status hasil inspeksi, stok per receipt, koreksi immutable, serta guard shipment/reservasi/saldo. Migrasi 22 → 23 menambahkan ledger shipping marketplace, carrier/resi, stok keluar gudang, koreksi immutable, dan guard jumlah/tanggal/pack. Migrasi 21 → 22 menambahkan ledger packing marketplace, stok `packed` di staging, koreksi immutable, dan guard jumlah/tanggal/pick. Migrasi 20 → 21 menambahkan ledger picking marketplace, stok `picked` di lokasi staging, koreksi immutable, dan guard jumlah/tanggal/release. Migrasi 19 → 20 menambahkan ledger reservasi marketplace, pemisahan available/reserved, pelepasan, dan guard stok terlindungi. Migrasi 18 → 19 menambahkan ledger transfer lokasi dan keputusan hold, status damaged, inventori per lokasi, koreksi immutable, serta guard saldo sumber/tujuan. Migrasi 17 → 18 menambahkan atribut defect final QC, ledger penerimaan barang jadi, pembagian sellable/hold, inventory per SKU, koreksi immutable, dan guard alokasi. Migrasi 16 → 17 menambahkan ledger final QC, temuan pengukuran/visual, hasil accepted/rework/reject, tiga perpindahan atomik, dan guard sumber finishing. Migrasi 15 → 16 menambahkan ledger finishing, lima checklist wajib, lineage hasil sewing, perpindahan ke QC, koreksi atomik, dan guard alokasi. Migrasi 14 → 15 menambahkan ledger job sewing/makloon, hasil selesai/defect/missing, biaya, turnaround, koreksi atomik, dan guard alokasi bundle. Migrasi 13 → 14 menambahkan identitas bundle, alokasi terhadap output cutting, koreksi immutable, dan guard over-allocation. Migrasi 12 → 13 menambahkan hasil cutting yang menghubungkan pemakaian bahan, waste, dan perpindahan pcs ke sewing, beserta koreksi atomik. Migrasi 11 → 12 menambahkan retur supplier, penutupan PO, dan guard riwayat final. Migrasi 10 → 11 menambahkan antrean QC kedatangan PO, keputusan layak pakai/reject, dan guard pembatalan/koreksi. Migrasi 9 → 10 menambahkan hubungan penerimaan batch ke PO. Migrasi 8 → 9 menambahkan master pemasok, PO, dan catatan pembatalannya. Migrasi 7 → 8 menambahkan PR dan riwayat keputusan. Migrasi 6 → 7 menambahkan ledger pemakaian aktual dan waste cutting. Migrasi 5 → 6 menambahkan ledger reservasi. Migrasi 4 → 5 menambahkan master bahan, batch, dan ledger bahan. Migrasi 3 → 4 menambahkan versi BOM. Saat startup, migrasi 1 → 2 menambahkan tabel kendala dan 2 → 3 menambahkan riwayat tenggat/PIC. Setiap migrasi berjalan dalam satu transaksi tanpa mengubah catatan produksi lama. Buat backup dengan versi aplikasi lama sebelum upgrade. Backup demo sebelum upgrade v0.4 tersedia lokal di `data/backups/demo-before-v04.sqlite3`.

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

## QC bahan masuk (v0.16)

Kedatangan bahan dari PO bisa dicatat dulu sebagai **hold** melalui **Rincian PO → Catat
kedatangan untuk QC**. Hold mengurangi sisa bahan yang boleh datang, tetapi belum menjadi
saldo batch atau bahan yang dapat direservasi. Satu kedatangan menyimpan referensi, lokasi
hold, tanggal, jumlah, aktor dan alasan secara immutable. Operator dapat mencatat kedatangan;
viewer hanya membaca.

Admin memutuskan hold sebagian atau seluruhnya sebagai **Terima layak pakai** atau **Tolak
bahan**. Keputusan layak pakai membuat batch stok baru dan memasangkan receipt ke PO.
Reject tidak membuat stok dan membuka jatah pengganti pada PO. Sisa yang belum diputuskan
tetap hold. Rincian PO menampilkan hold, layak, reject, jumlah yang masih bisa datang, serta
daftar kedatangan dan keputusan QC.

Untuk koreksi, admin memilih **Koreksi keputusan**. Koreksi layak pakai harus membalik receipt
batch melalui ledger stok; batch yang sudah dikeluarkan, direservasi, atau masih memiliki
pemakaian tidak dapat dikoreksi. Koreksi reject hanya boleh jika jatah pengganti belum terisi.
Pembatalan kedatangan hanya boleh tanpa keputusan aktif. PO tidak dapat dibatalkan saat masih
memiliki bahan hold atau receipt aktif. Guard SQLite juga menjaga aturan ini jika ada penulisan
langsung ke database.

API tambahan:

- `POST /api/purchase-orders/{id}/qc-intakes`: `material_id`, `reference`, `location`,
  `received_date`, `quantity`, `reason`.
- `GET /api/qc-intakes/{id}`: jumlah datang, hold, layak, reject, riwayat keputusan,
  pembatalan, dan sumber PO.
- `POST /api/qc-intakes/{id}/decisions`: `kind` accept/reject, `quantity`, alasan;
  acceptance juga memerlukan referensi dan lokasi batch siap pakai.
- `POST /api/qc-decisions/{id}/reverse` dan `POST /api/qc-intakes/{id}/cancel`.

Schema 10 → 11 menambahkan intake, decision, cancellation, kuota hold/reject dan guard
pembatalan/koreksi. Retry memakai Idempotency-Key yang sama dan tidak menambah stok dua kali.
Penerimaan manual lama dan penerimaan PO langsung tetap kompatibel. Hanya bahan layak pakai
yang masuk stok. Retur pemasok dan penutupan PO ditambahkan pada v0.17 di bawah; pembayaran belum tersedia.
Rencana dan bukti: [incoming QC plan](docs/incoming-qc-plan.md) dan [verifikasi incoming QC](docs/incoming-qc-verification.md).

## Retur supplier dan penutupan PO (v0.17)

Admin membuka **Permintaan pembelian → Daftar PO → Rincian PO → Rincian QC → Catat retur supplier**.
Isi referensi pengiriman, tanggal barang dikirim kembali, jumlah aktual, dan alasan.
Hanya bahan reject dari kedatangan tersebut yang dapat diretur; jumlah boleh parsial.
**Sudah diretur** dan **Belum diretur** serta riwayat pengiriman terlihat di rincian QC.
Operator/viewer dapat membaca, sementara pencatatan dan koreksi hanya untuk admin.

Retur tidak mengubah stok layak pakai. Jatah pengganti sudah terbuka ketika QC menolak bahan;
pengiriman retur tidak membuka jatah tambahan. Bahan yang sudah diterima layak pakai belum
dapat diretur lewat alur ini. Referensi pengiriman unik, tanggal tidak boleh sebelum kedatangan,
dan jumlah tidak boleh melampaui reject yang belum diretur. Barang pcs memakai jumlah bulat.

Jika salah catat, pilih **Koreksi retur** dan isi alasan. Koreksi membalik seluruh catatan;
buat retur baru untuk jumlah yang benar. Riwayat asli tetap tersimpan. Koreksi reject QC
ditolak apabila jumlah reject setelah koreksi lebih kecil daripada bahan yang sudah diretur.
Pastikan pencatatan sesuai perpindahan fisik.

Setelah hold QC dan reject belum diretur sama-sama nol, admin dapat memilih **Tutup PO**
di rincian PO. PO harus memiliki penerimaan layak pakai aktif; jika belum ada, gunakan
pembatalan. Form penutupan menampilkan jumlah diterima dan sisa yang tidak akan diterima,
serta meminta alasan. Penutupan permanen: tidak ada penerimaan/kedatangan baru maupun
koreksi penerimaan, QC, atau retur. Jumlah pesanan, harga, nilai PO, dan sisa yang tidak
diterima tetap tersimpan; jumlah yang bisa datang menjadi nol. Stok layak pakai tetap
bisa direservasi, dikeluarkan, dan dicatat pemakaiannya untuk produksi.

Status **Ditutup** berbeda dari **Dibatalkan** dan tersedia pada filter daftar PO.
PO ditutup tetap mengunci PR asal terhadap pembatalan atau penerbitan PO pengganti;
pembelian tambahan memakai PR baru. Pembatalan PO juga memerlukan semua retur selesai.
Untuk kompatibilitas migrasi, PO yang sudah dibatalkan pada versi lama tetapi masih
memiliki reject dapat mencatat retur; catatan retur pada PO tersebut langsung final.

API baru mengikuti autentikasi, role admin, dan Idempotency-Key yang sama:

- `POST /api/qc-intakes/{id}/returns`: `reference`, `returned_date`, `quantity`, `reason`.
- `POST /api/supplier-returns/{id}/reverse`: `reason`.
- `POST /api/purchase-orders/{id}/close`: `reason`.
- `GET /api/qc-intakes/{id}` menambahkan `returned`, `return_pending`, `returns`, dan `po_closed`.
- Rincian PO menambahkan `closure`, status `closed`, serta `returned`/`return_pending` per bahan.
  `remaining` tetap menunjukkan kekurangan terhadap pesanan; `receivable` nol ketika ditutup/dibatalkan.
- `GET /api/purchase-orders?status=closed` menampilkan PO ditutup.

Schema 11 → 12 mempertahankan data lama dan menambahkan ledger retur, catatan penutupan,
serta guard SQLite. Buat backup sebelum upgrade. Belum ada buka ulang PO, credit note,
pembayaran, cetak surat retur, konfirmasi pemasok, atau pengiriman pesan ke pemasok.

Rencana: [supplier returns plan](docs/supplier-returns-plan.md).
Bukti pengujian: [supplier returns verification](docs/supplier-returns-verification.md).

## Hasil cutting dan bahan asal (v0.18)

Di detail order, pilih **Hasil cutting** lalu **Catat hasil cutting**. Pilih satu pengeluaran
bahan order yang masih punya jumlah belum dilaporkan, isi referensi, bahan terpakai, waste,
alasan, dan hasil pcs per SKU. Sistem memindahkan hasil itu dari tahap cutting ke sewing,
menyimpan batch bahan asal, dan mencatat pemakaian serta waste dalam transaksi yang sama.
Jumlah bahan tidak otomatis dikonversi menjadi pcs; operator tetap memasukkan hasil nyata.

Satu hasil cutting memakai satu pengeluaran bahan. Hasil untuk beberapa ukuran/SKU dalam order
boleh dicatat bersama. SKU harus berasal dari order yang sama dan jumlahnya tidak boleh melebihi
saldo cutting. Bahan terpakai + waste tidak boleh melebihi jumlah pengeluaran yang belum
dilaporkan. Pengeluaran, pemakaian, atau perpindahan yang sudah dihubungkan ke hasil cutting
tidak dapat dikoreksi sendiri; gunakan **Koreksi hasil cutting** agar output pcs dan catatan
bahan kembali bersama-sama. Koreksi membutuhkan saldo sewing yang cukup untuk seluruh output.

Operator dapat mencatat, admin dapat mencatat dan mengoreksi, viewer hanya membaca. Riwayat
hasil cutting bisa dibuka dari detail order, riwayat perpindahan, riwayat pemakaian, dan batch
bahan asal. Referensi hasil cutting unik. Retry memakai Idempotency-Key yang sama, termasuk
ketika respons hilang setelah server sudah menyimpan.

API baru:

- `POST /api/orders/{id}/cutting-runs`: `reference`, `issue_id`, `used`, `waste`, `reason`, `outputs[]`.
- `GET /api/orders/{id}/cutting-runs?limit=100&before=sequence`.
- `GET /api/cutting-runs/{id}`.
- `POST /api/cutting-runs/{id}/reverse`: `reason` (admin).

Schema 12 → 13 menambahkan ledger hasil cutting/koreksi serta guard database untuk sumber
material, output yang belum dibalik, koreksi atomik, dan riwayat immutable. Belum ada
alokasi biaya per ukuran, multi-material dalam satu run, barcode, scrap
valuation, atau alur vendor/makloon.

Rencana: [cutting plan](docs/cutting-plan.md).
Bukti pengujian: [cutting verification](docs/cutting-verification.md).

## Bundling (v0.19)

Buka detail order → **Hasil cutting** → rincian hasil, lalu pilih **Buat bundle** pada
SKU/ukuran yang masih memiliki jumlah belum dibundel. Isi Bundle ID unik, jumlah pcs,
dan alasan/catatan. Satu bundle selalu menunjuk satu output cutting dan satu SKU/ukuran;
beberapa bundle parsial boleh memakai output yang sama selama total bundle aktif tidak
melebihi jumlah output tersebut. Menu **Bundle** pada order menampilkan daftar dan sumbernya.

Bundle adalah identitas fisik di atas catatan hasil cutting. Membuat atau mengoreksi bundle
tidak memindahkan saldo WIP: pcs sudah berpindah dari cutting ke sewing saat hasil cutting
dicatat. Pastikan label fisik, SKU/ukuran, dan jumlah sesuai sebelum menyimpan. Semua role
dapat membaca; admin dan operator dapat membuat; hanya admin dapat memilih **Koreksi bundle**.
Koreksi berlaku untuk seluruh catatan dan melepaskan alokasi, sedangkan bundle asli tetap
terlihat sebagai **Sudah dikoreksi**. Bundle aktif harus dikoreksi sebelum hasil cutting asal
dapat dikoreksi.

API baru memakai `X-API-Key`; semua POST juga memakai `Idempotency-Key`:

- `POST /api/cutting-runs/{id}/bundles`: `reference`, `output_movement_id`, `quantity`, `reason`.
- `GET /api/orders/{id}/bundles?limit=100&before=sequence`.
- `GET /api/bundles/{id}`: identitas, SKU/ukuran, order, hasil cutting, dan batch bahan asal.
- `POST /api/bundles/{id}/reverse`: `reason` (admin).

Jika respons penyimpanan hilang, masuk kembali dengan akun pencatat yang sama dan gunakan
**Coba ulang penyimpanan**. Key dan payload yang sama mengembalikan hasil pertama tanpa
menggandakan bundle. Schema 13 → 14 menambah ledger bundle dan guard langsung di SQLite;
migrasi tidak membuat bundle untuk hasil cutting lama.

Versi ini belum membuat barcode/label, mencetak atau memindai bundle, split/merge, atau
pergerakan bundle antar tahap di luar job sewing. Alur sewing/makloon tersedia pada bagian berikutnya.

Rencana: [bundling plan](docs/bundles-plan.md).
Bukti pengujian: [bundling verification](docs/bundles-verification.md).

## Sewing dan makloon (v0.20)

Buka detail order → **Bundle** → rincian bundle, lalu pilih **Kirim ke sewing**. Isi referensi
job unik, jenis penugasan internal atau makloon, nama pelaksana/vendor, jumlah keluar, biaya
total rupiah, tanggal kirim, dan alasan. Satu bundle dapat dialokasikan ke beberapa job parsial,
tetapi total job aktif tidak boleh melebihi jumlah bundle. Pengiriman hanya mengalokasikan
identitas bundle; saldo WIP tetap di sewing karena perpindahan dari cutting sudah terjadi saat
hasil cutting dicatat.

Admin atau operator menyelesaikan job melalui **Catat hasil sewing**. Seluruh jumlah keluar
harus dibagi tepat menjadi selesai, defect, dan missing. Jumlah selesai berpindah dari sewing
ke finishing, sedangkan defect dan missing berpindah ke reject agar jumlah order tetap seimbang.
Rincian job menyimpan kedua jenis selisih secara terpisah dan menghitung turnaround sebagai
selisih hari kalender antara tanggal kirim dan tanggal kembali.

Semua role aktif dapat melihat daftar serta rincian. Admin/operator dapat mengirim dan menerima
hasil; hanya admin dapat memilih **Koreksi job sewing**. Koreksi membalik seluruh perpindahan
hasil secara atomik dan mempertahankan riwayat asli. Bundle tidak dapat dikoreksi selama masih
memiliki job aktif. Perpindahan yang dibuat oleh hasil sewing juga tidak dapat dibalik sendiri
dari riwayat order.

API baru memakai `X-API-Key`; semua POST juga memakai `Idempotency-Key`:

- `POST /api/bundles/{id}/sewing-jobs`: `reference`, `assignment_type`, `assignee`,
  `quantity_out`, `cost`, `sent_date`, dan `reason`.
- `GET /api/orders/{id}/sewing-jobs?limit=100&before=sequence`.
- `GET /api/sewing-jobs/{id}`.
- `POST /api/sewing-jobs/{id}/complete`: `completed_quantity`, `defect_quantity`,
  `missing_quantity`, `returned_date`, dan `reason`.
- `POST /api/sewing-jobs/{id}/reverse`: `reason` (admin).

Biaya adalah total job dalam IDR, disimpan presisi dua desimal. Nama pelaksana/vendor merupakan
snapshot teks bebas; versi ini belum menyediakan master vendor, formula ongkos per pcs, invoice,
pembayaran, penerimaan sebagian, keputusan rework, attachment, atau pemindaian barcode. Job
diselesaikan satu kali untuk seluruh jumlahnya; jika dikoreksi, catat job pengganti.

Schema 14 → 15 menambahkan ledger job, hasil, koreksi, hubungan perpindahan WIP, dan guard SQLite.
Migrasi tidak mengarang job untuk bundle lama. Alur finishing tersedia pada bagian berikutnya.

Rencana: [sewing/makloon plan](docs/sewing-makloon-plan.md).
Bukti pengujian: [sewing/makloon verification](docs/sewing-makloon-verification.md).

## Finishing (v0.21)

Buka detail job sewing yang sudah selesai, lalu pilih **Catat finishing**. Isi referensi unik,
jumlah selesai, tanggal selesai, alasan, dan konfirmasi lima langkah: benang dirapikan, disetrika,
label terpasang, hangtag terpasang, serta sudah dikemas. Semua konfirmasi wajib lengkap sebelum
disimpan. Jumlah yang dicatat langsung berpindah dari finishing ke QC.

Satu job sewing dapat menghasilkan beberapa catatan finishing parsial. Total catatan aktif tidak
boleh melebihi jumlah selesai dari job sewing, dan tanggal finishing tidak boleh mendahului tanggal
hasil sewing diterima. Rincian mempertahankan hubungan ke job sewing, bundle, hasil cutting, serta
batch bahan asal. Menu **Finishing** pada order menampilkan seluruh catatan terbaru dahulu.

Semua role aktif dapat membaca. Admin/operator dapat mencatat; hanya admin dapat memilih
**Koreksi finishing**. Koreksi mengembalikan seluruh jumlah catatan dari QC ke finishing secara
atomik dan mempertahankan checklist serta riwayat asli. Job sewing tidak dapat dikoreksi selama
masih memiliki catatan finishing aktif. Perpindahan finishing juga tidak dapat dikoreksi sendiri
dari riwayat order.

API baru memakai `X-API-Key`; semua POST juga memakai `Idempotency-Key`:

- `POST /api/sewing-jobs/{id}/finishing-records`: `reference`, `quantity`, lima nilai checklist,
  `completed_date`, dan `reason`.
- `GET /api/orders/{id}/finishing-records?limit=100&before=sequence`.
- `GET /api/finishing-records/{id}`.
- `POST /api/finishing-records/{id}/reverse`: `reason` (admin).

Versi ini mencatat konfirmasi selesai, belum timestamp setiap aktivitas atau status checkbox
parsial. Belum ada pekerja/stasiun per langkah, bahan habis pakai finishing, SKU kemasan, durasi
per aktivitas, attachment, pemindaian barcode, atau defect/rework khusus finishing. Pengecualian
tetap dapat dicatat melalui kendala dan alur QC yang sudah ada.

Schema 15 → 16 menambahkan ledger finishing/koreksi, hubungan movement, guard SQLite, dan migrasi
tanpa mengarang catatan historis. Alur final QC tersedia pada bagian berikutnya.

Rencana: [finishing plan](docs/finishing-plan.md).
Bukti pengujian: [finishing verification](docs/finishing-verification.md).

## Final QC (v0.22)

Buka rincian finishing aktif lalu pilih **Catat final QC**. Isi referensi unik, catatan pengukuran,
catatan pemeriksaan visual, jenis defect, sumber penanggung jawab, disposition, tanggal inspeksi,
alasan, dan jumlah untuk tiga hasil: diterima, rework, serta reject. Setidaknya satu hasil harus
positif dan totalnya tidak boleh melebihi jumlah finishing yang belum diperiksa.

Penyimpanan menjalankan seluruh hasil dalam satu transaksi. Jumlah diterima berpindah dari QC ke
gudang, rework berpindah ke posisi rework, dan reject berpindah ke reject. Satu finishing dapat
diperiksa lewat beberapa catatan parsial. Tanggal inspeksi tidak boleh mendahului tanggal selesai
finishing. Rincian mempertahankan lineage sampai finishing, job sewing, bundle, cutting, dan batch
bahan asal.

Semua role aktif dapat membaca. Admin/operator dapat mencatat; hanya admin dapat memilih
**Koreksi final QC**. Koreksi mengembalikan seluruh hasil dari gudang/rework/reject ke QC secara
atomik dan mempertahankan temuan asli. Finishing tidak dapat dikoreksi selama memiliki final QC
aktif. Perpindahan hasil QC juga tidak dapat dibalik sendiri dari riwayat order.

API baru memakai `X-API-Key`; semua POST juga memakai `Idempotency-Key`:

- `POST /api/finishing-records/{id}/qc-records`: `reference`, `measurement_notes`, `visual_notes`,
  `defect_type`, `responsible_source`, `disposition`, `accepted_quantity`, `rework_quantity`,
  `reject_quantity`, `inspection_date`, dan `reason`.
- `GET /api/orders/{id}/final-qc-records?limit=100&before=sequence`.
- `GET /api/final-qc-records/{id}`.
- `POST /api/final-qc-records/{id}/reverse`: `reason` (admin).

Temuan pengukuran, visual, jenis defect, sumber, dan disposition masih berupa catatan wajib.
Versi ini belum memiliki template ukuran, toleransi per SKU, sampling plan, master kode defect,
foto, tanda tangan approval, atau instruksi rework terstruktur. Rework yang sudah selesai dapat kembali ke QC melalui perpindahan yang tersedia;
pencatatan inspeksi ulang perlu mengikuti sumber fisik yang benar.

Schema 16 → 17 menambahkan ledger final QC/koreksi, hubungan tiga movement, guard SQLite, dan
migrasi tanpa mengarang inspeksi historis. Penerimaan barang jadi tersedia pada bagian berikutnya.

Rencana: [final QC plan](docs/final-qc-plan.md).
Bukti pengujian: [final QC verification](docs/final-qc-verification.md).

## Penerimaan barang jadi (v0.23)

Buka rincian final QC aktif lalu pilih **Terima barang jadi**. Pindai atau masukkan SKU persis,
isi lokasi gudang dan tanggal penerimaan, lalu bagi jumlah ke stok sellable dan hold. Beberapa
penerimaan parsial boleh memakai satu final QC selama total aktif tidak melebihi jumlah accepted.
Menu **Barang jadi** pada order menampilkan riwayat penerimaan dan ringkasan inventori per SKU.

Penerimaan tidak memindahkan WIP karena hasil accepted sudah berpindah dari QC ke gudang. Catatan
ini mengklasifikasikan stok gudang menjadi sellable dan hold. Admin/operator dapat menerima;
semua role aktif dapat membaca; hanya admin dapat memilih **Koreksi penerimaan**. Koreksi
melepaskan alokasi sellable/hold tanpa mengubah WIP dan mempertahankan catatan asli. Final QC
tidak dapat dikoreksi selama masih memiliki penerimaan aktif.

API baru memakai `X-API-Key`; semua POST juga memakai `Idempotency-Key`:

- `POST /api/final-qc-records/{id}/finished-goods-receipts`: `reference`, `scanned_sku`,
  `location`, `sellable_quantity`, `hold_quantity`, `received_date`, dan `reason`.
- `GET /api/orders/{id}/finished-goods-receipts?limit=100&before=sequence`.
- `GET /api/finished-goods-receipts/{id}`.
- `POST /api/finished-goods-receipts/{id}/reverse`: `reason` (admin).
- `GET /api/finished-goods-inventory`: total sellable, hold, dan damaged aktif per SKU.

Schema 17 → 18 menambahkan atribut defect/source/disposition pada final QC, ledger penerimaan dan
koreksi, validasi tanggal/SKU/alokasi, ringkasan inventori, serta guard SQLite. Migrasi tidak
mengarang penerimaan untuk stok gudang lama. Jubelio/WMS belum dihubungkan dan stok marketplace
tidak diubah. Transfer lokasi dan keputusan hold tersedia pada bagian berikutnya.

Rencana: [finished goods plan](docs/finished-goods-plan.md).
Bukti pengujian: [finished goods verification](docs/finished-goods-verification.md).

## Transfer gudang dan keputusan hold (v0.24)

Buka order → **Barang jadi** → rincian penerimaan. **Transfer lokasi** memindahkan jumlah antar
lokasi tanpa mengubah status sellable, hold, atau damaged. **Lepaskan hold** mengubah hold menjadi
sellable; **Tandai damaged** memisahkan hold sebagai barang rusak. Keputusan hold boleh sekaligus
memindahkan barang ke lokasi tujuan. Menu **Gudang** menampilkan saldo per SKU, lokasi, dan status,
beserta riwayat pergerakan terbaru dahulu.

Setiap pergerakan mempertahankan penerimaan barang jadi sebagai sumber. Saldo dihitung dari
penerimaan awal dan ledger pergerakan aktif. Jumlah tidak boleh melebihi saldo lokasi/status asal,
dan tanggal tidak boleh mendahului penerimaan. Admin/operator dapat mencatat; semua role aktif
dapat membaca; hanya admin dapat mengoreksi. Koreksi mengembalikan seluruh jumlah ke lokasi dan
status asal jika stok tujuan belum dipakai. Penerimaan asal tidak dapat dikoreksi selama memiliki
pergerakan aktif.

API baru memakai `X-API-Key`; semua POST juga memakai `Idempotency-Key`:

- `POST /api/finished-goods-receipts/{id}/warehouse-movements`: `reference`, `kind`, lokasi asal
  dan tujuan, `stock_status` untuk transfer, `quantity`, `moved_date`, dan `reason`.
- `GET /api/orders/{id}/warehouse-movements?limit=100&before=sequence`.
- `GET /api/warehouse-movements/{id}`.
- `POST /api/warehouse-movements/{id}/reverse`: `reason` (admin).
- `GET /api/warehouse-inventory`: saldo aktif per SKU, lokasi, dan status.

Schema 18 → 19 menambahkan ledger pergerakan/koreksi dan guard SQLite terhadap sumber tidak aktif,
tanggal salah, overdraw, serta koreksi yang membuat saldo tujuan negatif. Migrasi tidak mengarang
lokasi atau keputusan untuk penerimaan lama. Jubelio/WMS, master barcode, label/bin, reservasi
marketplace, pick/pack/ship, retur, stock opname, dan adjustment belum dicakup. Reservasi
marketplace tersedia pada bagian berikutnya.

Rencana: [warehouse movements plan](docs/warehouse-movements-plan.md).
Bukti pengujian: [warehouse movements verification](docs/warehouse-movements-verification.md).

## Reservasi marketplace (v0.25)

Buka rincian penerimaan barang jadi lalu pilih **Reservasi marketplace**. Pilih bucket sellable,
isi marketplace, referensi order eksternal, jumlah, dan tanggal reservasi. Menu **Reservasi jual**
pada order menampilkan alokasi terbaru dan ringkasan `available`, `reserved`, serta sellable fisik.
Satu bucket dapat dipakai beberapa reservasi selama total aktif tidak melebihi available.

Reservasi tidak mengurangi stok fisik atau WIP. Jumlah reserved mengurangi available pada SKU dan
lokasi yang sama. Admin/operator dapat membuat serta melepas seluruh reservasi; semua role aktif
dapat membaca. Reservasi aktif melindungi stok dari transfer, koreksi pergerakan, dan koreksi
penerimaan. Pelepasan menyimpan alasan serta tanggal dan mengembalikan alokasi menjadi available.

API baru memakai `X-API-Key`; semua POST juga memakai `Idempotency-Key`:

- `POST /api/finished-goods-receipts/{id}/marketplace-reservations`: `reference`, `marketplace`,
  `external_order_reference`, `location`, `quantity`, `reserved_date`, dan `reason`.
- `GET /api/orders/{id}/marketplace-reservations?limit=100&before=sequence`.
- `GET /api/marketplace-reservations/{id}`.
- `POST /api/marketplace-reservations/{id}/release`: `released_date` dan `reason`.

Schema 19 → 20 menambahkan ledger reservasi/pelepasan dan guard SQLite terhadap sumber tidak aktif,
tanggal salah, over-allocation, transfer stok reserved, serta koreksi yang mengurangi reserved.
Marketplace dan referensi order disimpan sebagai snapshot; belum ada sinkronisasi API marketplace
atau Jubelio/WMS. Partial release, impor order, pick, pack, ship, retur, stock opname, dan adjustment
belum dicakup. Roadmap berikutnya adalah alokasi pick dari stok reserved.

Rencana: [marketplace reservations plan](docs/marketplace-reservations-plan.md).
Bukti pengujian: [marketplace reservations verification](docs/marketplace-reservations-verification.md).

## Picking marketplace (v0.26)

Buka reservasi marketplace aktif lalu pilih **Catat pick**. Isi referensi pick, jumlah, lokasi staging,
tanggal, dan alasan. Pick parsial diperbolehkan selama total pick aktif tidak melebihi jumlah
reservasi. Menu **Picking** pada order menampilkan catatan terbaru dan jalur dari rak sellable ke
lokasi staging.

Pick mengurangi sellable fisik dan reserved pada jumlah yang sama, sehingga available tidak
berubah. Barang muncul sebagai stok `picked` di lokasi staging dan tetap dihitung dalam total
inventori barang jadi. Pencatatan tidak mengubah WIP produksi. Admin/operator dapat mencatat;
semua role aktif dapat membaca; hanya admin dapat memilih **Koreksi pick**. Koreksi mengembalikan
barang ke reserved sellable. Reservasi tidak dapat dilepas selama masih memiliki pick aktif.

API baru memakai `X-API-Key`; semua POST juga memakai `Idempotency-Key`:

- `POST /api/marketplace-reservations/{id}/picks`: `reference`, `quantity`, `staging_location`,
  `picked_date`, dan `reason`.
- `GET /api/orders/{id}/marketplace-picks?limit=100&before=sequence`.
- `GET /api/marketplace-picks/{id}`.
- `POST /api/marketplace-picks/{id}/reverse`: `reason` (admin).

Schema 20 → 21 menambahkan ledger pick/koreksi dan guard SQLite terhadap reservasi tidak aktif,
tanggal salah, over-pick, serta pelepasan reservasi yang masih mempunyai pick aktif. Belum ada
barcode, picker assignment, wave/tote, packing, shipping, retur pelanggan, atau sinkronisasi API
marketplace/Jubelio. Konfirmasi packing tersedia pada bagian berikutnya.

Rencana: [marketplace picking plan](docs/marketplace-picking-plan.md).
Bukti pengujian: [marketplace picking verification](docs/marketplace-picking-verification.md).

## Packing marketplace (v0.27)

Buka pick marketplace aktif lalu pilih **Catat pack**. Isi referensi pack, jumlah, tanggal, dan
alasan. Pack parsial diperbolehkan selama total pack aktif tidak melebihi jumlah pick. Menu
**Packing** pada order menampilkan catatan terbaru, lokasi staging, dan sumber pick.

Packing mengubah stok `picked` menjadi `packed` pada lokasi staging yang sama. Sellable fisik,
reserved, available, total inventori, dan WIP produksi tidak berubah. Admin/operator dapat mencatat;
semua role aktif dapat membaca; hanya admin dapat memilih **Koreksi pack**. Koreksi mengembalikan
barang menjadi `picked`. Pick tidak dapat dikoreksi selama masih memiliki pack aktif.

API baru memakai `X-API-Key`; semua POST juga memakai `Idempotency-Key`:

- `POST /api/marketplace-picks/{id}/packs`: `reference`, `quantity`, `packed_date`, dan `reason`.
- `GET /api/orders/{id}/marketplace-packs?limit=100&before=sequence`.
- `GET /api/marketplace-packs/{id}`.
- `POST /api/marketplace-packs/{id}/reverse`: `reason` (admin).

Schema 21 → 22 menambahkan ledger pack/koreksi dan guard SQLite terhadap pick tidak aktif, tanggal
salah, over-pack, serta koreksi pick yang masih mempunyai pack aktif. Belum ada barcode, bahan
kemasan, dimensi/berat, atau label. Konfirmasi pengiriman tersedia pada bagian berikutnya.

Rencana: [marketplace packing plan](docs/marketplace-packing-plan.md).
Bukti pengujian: [marketplace packing verification](docs/marketplace-packing-verification.md).

## Shipping marketplace (v0.28)

Buka pack marketplace aktif lalu pilih **Catat pengiriman**. Isi referensi pengiriman, jumlah,
carrier, nomor resi, tanggal kirim, dan alasan. Pengiriman parsial diperbolehkan selama total aktif
tidak melebihi jumlah pack. Menu **Shipping** pada order menampilkan riwayat terbaru dan informasi
carrier/resi.

Barang yang dikirim keluar dari stok `packed`, sehingga total inventori di gudang berkurang.
Sellable, reserved, available, picked, dan WIP produksi tidak berubah. Admin/operator dapat
mencatat; semua role aktif dapat membaca; hanya admin dapat memilih **Koreksi pengiriman**. Koreksi
mengembalikan barang menjadi `packed` pada lokasi staging asal. Pack tidak dapat dikoreksi selama
masih memiliki pengiriman aktif.

API baru memakai `X-API-Key`; semua POST juga memakai `Idempotency-Key`:

- `POST /api/marketplace-packs/{id}/shipments`: `reference`, `quantity`, `carrier`,
  `tracking_number`, `shipped_date`, dan `reason`.
- `GET /api/orders/{id}/marketplace-shipments?limit=100&before=sequence`.
- `GET /api/marketplace-shipments/{id}`.
- `POST /api/marketplace-shipments/{id}/reverse`: `reason` (admin).

Schema 22 → 23 menambahkan ledger pengiriman/koreksi dan guard SQLite terhadap pack tidak aktif,
tanggal salah, over-ship, serta koreksi pack yang masih mempunyai pengiriman aktif. Belum ada
pembelian/cetak label, carrier API, event tracking, konfirmasi delivery, konsolidasi beberapa pack,
atau sinkronisasi marketplace/Jubelio. Retur pelanggan dan adjustment tersedia pada bagian berikutnya.

Rencana: [marketplace shipping plan](docs/marketplace-shipping-plan.md).
Bukti pengujian: [marketplace shipping verification](docs/marketplace-shipping-verification.md).

## Retur pelanggan dan adjustment barang jadi (v0.29)

Buka pengiriman aktif lalu pilih **Catat retur**. Retur boleh parsial selama total aktif tidak
melebihi jumlah pengiriman. Setiap catatan menyimpan alasan terstruktur, lokasi penerimaan, tanggal,
dan hasil pemeriksaan `sellable`, `hold`, atau `damaged`. Stok kembali ke gudang sesuai hasil
pemeriksaan tanpa mengubah WIP produksi. Pengiriman tidak dapat dikoreksi selama masih memiliki
retur aktif.

Buka penerimaan barang jadi aktif lalu pilih **Catat adjustment** untuk mencatat selisih stock
opname pada satu lokasi dan status. Angka positif menambah stok; angka negatif mengurangi stok.
Pengurangan tidak boleh melampaui saldo fisik atau memakai stok sellable yang terikat reservasi.
Admin/operator dapat mencatat kedua transaksi; semua role aktif dapat membaca; hanya admin dapat
mengoreksi seluruh catatan. Riwayat asli tetap tersimpan.

API baru memakai `X-API-Key`; semua POST juga memakai `Idempotency-Key`:

- `POST /api/marketplace-shipments/{id}/returns`: `reference`, `quantity`, `return_reason`,
  `return_location`, `stock_status`, `returned_date`, dan `reason`.
- `GET /api/orders/{id}/marketplace-returns?limit=100&before=sequence` dan
  `GET /api/marketplace-returns/{id}`.
- `POST /api/marketplace-returns/{id}/reverse`: `reason` (admin).
- `POST /api/finished-goods-receipts/{id}/adjustments`: `reference`, `location`, `stock_status`,
  `quantity_delta`, `adjusted_date`, dan `reason`.
- `GET /api/orders/{id}/finished-goods-adjustments?limit=100&before=sequence` dan
  `GET /api/finished-goods-adjustments/{id}`.
- `POST /api/finished-goods-adjustments/{id}/reverse`: `reason` (admin).

Schema 23 → 24 menambahkan empat tabel ledger/koreksi, view stok dan reserved stock per receipt,
serta guard SQLite terhadap over-return, overdraw, tanggal salah, koreksi yang memakai stok reserved,
dan koreksi shipment/penerimaan yang masih memiliki transaksi aktif. Belum ada refund, exchange,
label retur, foto, approval, jurnal keuangan, anomaly score, atau sinkronisasi marketplace/Jubelio.

Rencana: [returns and adjustments plan](docs/returns-adjustments-plan.md).
Bukti pengujian: [returns and adjustments verification](docs/returns-adjustments-verification.md).

## Stock opname dan rekonsiliasi barang jadi (v0.30)

Buka penerimaan barang jadi aktif lalu pilih **Catat stock opname**. Operator memindai SKU,
menentukan lokasi dan status `sellable`, `hold`, atau `damaged`, lalu memasukkan jumlah fisik.
Server mengambil saldo sistem pada penerimaan yang sama dalam transaksi pencatatan dan menyimpan
saldo tersebut bersama jumlah fisik serta selisihnya.

Selisih bukan nol otomatis membuat adjustment barang jadi yang terhubung. Selisih nol tetap
disimpan sebagai bukti hitung tanpa mengubah stok. Jumlah fisik `sellable` tidak boleh lebih kecil
dari stok yang masih reserved. Adjustment hasil stock opname hanya dapat dikoreksi melalui catatan
stock opname agar kedua ledger tetap sinkron. Admin/operator dapat mencatat, semua role aktif dapat
membaca, dan hanya admin dapat mengoreksi.

API baru memakai `X-API-Key`; semua POST juga memakai `Idempotency-Key`:

- `POST /api/finished-goods-receipts/{id}/stock-counts`: `reference`, `scanned_sku`, `location`,
  `stock_status`, `counted_quantity`, `counted_date`, dan `reason`.
- `GET /api/orders/{id}/finished-goods-stock-counts?limit=100&before=sequence` dan
  `GET /api/finished-goods-stock-counts/{id}`.
- `POST /api/finished-goods-stock-counts/{id}/reverse`: `reason` (admin).

Schema 24 → 25 menambahkan ledger hitung dan koreksi, snapshot saldo sistem per penerimaan,
hubungan adjustment, serta guard SQLite terhadap SKU/tanggal/saldo yang salah, pencatatan pada
penerimaan nonaktif, koreksi langsung adjustment turunan, dan perubahan stok reserved. Versi ini
belum mempunyai sesi freeze gudang, tim penghitung, blind double count, impor scanner, approval,
valuasi, anomaly score, atau rekonsiliasi otomatis dengan Jubelio/WMS.

Rencana: [inventory reconciliation plan](docs/inventory-reconciliation-plan.md).
Bukti pengujian: [inventory reconciliation verification](docs/inventory-reconciliation-verification.md).

## Unified approval inbox: PR dan perubahan produksi (v0.31)

Pilih **Inbox approval** untuk melihat keputusan purchasing dan produksi dalam satu antrean. Filter
tersedia untuk status dan jenis approval. Kartu PR menampilkan estimasi nilai, tanggal kebutuhan,
order sumber, dan jumlah bahan. Kartu produksi menampilkan perubahan tenggat dan PIC yang diajukan.

Admin/operator dapat mengajukan perubahan produksi dari detail order. Pengajuan menyimpan tenggat,
PIC, dan revision order saat itu tanpa langsung mengubah order. Admin menyetujui atau menolak;
pemohon dapat membatalkan permintaan sendiri selama masih menunggu. Persetujuan menerapkan perubahan
dan menulis riwayat tenggat/PIC dalam transaksi yang sama. Jika order berubah lebih dahulu,
permintaan ditandai stale dan tidak dapat disetujui.

API baru memakai `X-API-Key`; semua POST juga memakai `Idempotency-Key`:

- `GET /api/approvals?status=pending&kind=all&limit=100&offset=0`.
- `POST /api/orders/{id}/change-requests`: `reference`, `owner_id`, `due_date`,
  `expected_revision`, dan `reason`.
- `GET /api/orders/{id}/change-requests?limit=100&before=sequence` dan
  `GET /api/production-change-requests/{id}`.
- `POST /api/production-change-requests/{id}/decisions`: `status`, `expected_revision`, dan
  `reason`.

Schema 25 → 26 menambahkan ledger permintaan dan keputusan produksi, validasi sumber/aktor di
SQLite, batas satu permintaan pending per order, hubungan ke audit perubahan order, serta read model
inbox gabungan. Versi ini belum mempunyai threshold nilai, approval bertingkat, delegasi, komentar,
lampiran, reminder/notifikasi, pembayaran supplier, marketing budget, atau write ke Mekari/Jubelio.

Rencana: [unified approvals plan](docs/unified-approvals-plan.md).
Bukti pengujian: [unified approvals verification](docs/unified-approvals-verification.md).

## Approval penerbitan Purchase Order (v0.32)

PO yang dibuat dari PR approved sekarang berstatus **Menunggu keputusan**. Admin/operator dapat
mengajukan PO, tetapi hanya admin yang dapat menyetujui atau menolak. Pembuat dapat membatalkan
pengajuan sendiri selama masih pending. PO rejected atau pengajuan yang dibatalkan tidak mengunci
PR sehingga PO pengganti dapat dibuat.

PO pending tampil di **Inbox approval** bersama PR dan perubahan produksi. Kartunya menampilkan
nilai PO, pemasok, PR sumber, jumlah bahan, dan perkiraan tanggal datang. Rincian PO menyimpan
riwayat pengajuan serta keputusan secara immutable. Penerimaan langsung, kedatangan QC,
pembatalan PO aktif, dan penutupan PO baru tersedia sesudah approval.

API terkait:

- `POST /api/purchase-orders` membuat pengajuan PO berstatus pending.
- `POST /api/purchase-orders/{id}/decisions` menerima `status` approved/rejected/cancelled,
  `expected_revision`, dan `reason`.
- `GET /api/purchase-orders?status=pending` dan `GET /api/approvals?kind=purchase_order`.

Schema 26 → 27 menambahkan ledger approval PO dan trigger yang mewajibkan keputusan approved
sebelum receipt, QC intake, cancellation aktif, atau closure. Migrasi memberi satu event approved
pada setiap PO historis, termasuk yang sudah ditutup atau dibatalkan, sehingga alur lama tetap valid.

Rencana: [purchase order approvals plan](docs/purchase-order-approvals-plan.md).
Bukti pengujian: [purchase order approvals verification](docs/purchase-order-approvals-verification.md).

## Approval pembayaran supplier (v0.33)

PO approved yang sudah mempunyai bahan layak pakai dapat membuat pengajuan pembayaran supplier.
Pengajuan menyimpan referensi internal, referensi invoice, tanggal invoice, jatuh tempo, nominal,
alasan, dan pembuat. Admin/operator dapat mengajukan; hanya admin yang dapat menyetujui atau
menolak. Pembuat dapat membatalkan pengajuannya sendiri selama masih pending.

Nominal pending dan approved sama-sama mengurangi sisa yang dapat diajukan. Batasnya memakai nilai
bahan layak pakai yang benar-benar diterima berdasarkan harga PO, sehingga penerimaan parsial tidak
membuka seluruh nilai PO. Koreksi receipt ditolak bila akan membuat nilai penerimaan lebih kecil
daripada total request pembayaran yang masih aktif.

Pengajuan tampil di **Inbox approval** sebagai jenis **Finance · pembayaran supplier**. Approved
berarti siap dibayar dan tercatat dalam audit; aplikasi belum mengeksekusi transfer bank atau jurnal
akuntansi.

API terkait:

- `POST /api/purchase-orders/{id}/payment-requests`.
- `GET /api/purchase-orders/{id}/payment-requests?limit=100&before=sequence`.
- `GET /api/supplier-payment-requests/{id}`.
- `POST /api/supplier-payment-requests/{id}/decisions`.
- `GET /api/approvals?kind=supplier_payment`.

Schema 27 → 28 menambahkan ledger request/keputusan pembayaran yang immutable, perhitungan nilai
penerimaan, revision guard, kontrol role, nominal kumulatif, dan perlindungan koreksi receipt.

Rencana: [supplier payment approvals plan](docs/supplier-payment-approvals-plan.md).
Bukti pengujian: [supplier payment approvals verification](docs/supplier-payment-approvals-verification.md).

## Approval budget marketing (v0.34)

Pilih **Budget marketing** untuk melihat dan mengajukan plafon kampanye. Pengajuan mencatat referensi,
nama kampanye, channel, tanggal mulai dan selesai, nominal, objective, alasan, serta pembuat.
Admin/operator dapat mengajukan. Hanya admin yang dapat menyetujui atau menolak; pembuat dapat
membatalkan pengajuannya sendiri selama masih menunggu keputusan.

Pengajuan masuk **Inbox approval** sebagai jenis **Marketing · budget kampanye**. Keputusan memakai
revision guard dan riwayat append-only. Approved berarti plafon telah disahkan; aplikasi belum
mencatat realisasi belanja, invoice platform iklan, pembayaran, atau jurnal akuntansi.

API terkait:

- `GET /api/marketing-budget-requests?status=all&limit=100&before=sequence`.
- `POST /api/marketing-budget-requests`.
- `GET /api/marketing-budget-requests/{id}`.
- `POST /api/marketing-budget-requests/{id}/decisions`.
- `GET /api/approvals?kind=marketing_budget`.

Schema 28 → 29 menambahkan ledger pengajuan dan keputusan budget marketing yang immutable, kontrol
role, validasi periode/nominal, idempotency, dan integrasi ke inbox approval gabungan.

Rencana: [marketing budget approvals plan](docs/marketing-budget-approvals-plan.md).
Bukti pengujian: [marketing budget approvals verification](docs/marketing-budget-approvals-verification.md).

## Biaya produksi aktual per order (v0.35)

Buka order lalu pilih **Biaya aktual**. Laporan menghitung bahan yang sudah dilaporkan sebagai
terpakai atau waste memakai harga satuan PO dari batch asal, kemudian menambahkan biaya job sewing
atau makloon yang masih aktif. Semua nominal dihitung dalam sen IDR dan baru diformat saat respons.

Laporan menampilkan biaya bahan, sewing/makloon, total biaya, biaya per target pcs, biaya per barang
jadi yang sudah diterima, rincian batch, dan job sumber. Koreksi pemakaian atau job langsung tercermin
pada pembacaan berikutnya karena laporan dihitung dari ledger aktif, bukan menyimpan salinan total.

`total_cost` hanya tersedia jika seluruh pengeluaran bahan telah dilaporkan dan setiap pemakaian
mempunyai harga PO. Batch manual tanpa PO, pengeluaran yang belum dilaporkan, atau order yang belum
mempunyai pemakaian menghasilkan status `incomplete` dan `coverage_gaps` terstruktur. `known_cost`
tetap menunjukkan subtotal sumber yang tersedia tanpa mengklaimnya sebagai biaya total.

API terkait: `GET /api/orders/{id}/production-cost`. Schema tetap versi 29 karena laporan ini adalah
read model dari ledger bahan, PO, sewing, dan barang jadi yang sudah ada.

Cakupan saat ini belum memasukkan tenaga kerja internal, finishing, QC, kemasan, freight, overhead,
biaya pembayaran, atau jurnal Mekari. Karena itu istilah biaya aktual pada milestone ini berarti biaya
bahan dan sewing/makloon yang sudah mempunyai sumber nominal, bukan full landed cost perusahaan.

Rencana: [production cost reporting plan](docs/production-cost-reporting-plan.md).
Bukti pengujian: [production cost reporting verification](docs/production-cost-reporting-verification.md).

## Margin kontribusi per order (v0.36)

Setelah pengiriman marketplace aktif, buka rincian pengiriman lalu pilih **Catat settlement**. Catatan
menyimpan omzet kotor, diskon penjual, refund pelanggan, fee marketplace, biaya kirim yang ditanggung
penjual, biaya variabel lain, tanggal settlement, dan jumlah retur aktif saat pencatatan. Nominal
disimpan sebagai integer sen IDR dan riwayat tidak dapat diubah atau dihapus.

Buka order lalu pilih **Margin kontribusi**. Pendapatan neto adalah omzet dikurangi diskon dan refund.
Biaya jual variabel menjumlahkan fee marketplace, biaya kirim, dan biaya variabel lain. Biaya
produksi dialokasikan proporsional terhadap jumlah terjual neto dibanding barang jadi yang telah
diterima. Margin kontribusi adalah pendapatan neto dikurangi biaya jual variabel dan biaya produksi
teralokasi.

Margin final hanya tersedia jika biaya produksi lengkap dan setiap pengiriman aktif mempunyai
settlement yang masih sesuai dengan jumlah retur. Retur baru atau koreksi retur membuat settlement
berstatus usang sampai admin mengoreksi catatan lama dan membuat penggantinya. Dengan begitu laporan
tidak diam-diam memakai refund yang belum diperbarui.

API terkait:

- `POST /api/marketplace-shipments/{id}/sale-settlements`.
- `GET /api/orders/{id}/sale-settlements?limit=100&before=sequence`.
- `GET /api/marketplace-sale-settlements/{id}`.
- `POST /api/marketplace-sale-settlements/{id}/reverse`.
- `GET /api/orders/{id}/contribution-margin`.

Schema 29 → 30 menambahkan ledger settlement dan pembalikan immutable, snapshot jumlah retur,
validasi satu settlement aktif per pengiriman, serta guard agar pengiriman tidak dikoreksi selama
settlement masih aktif.

Pajak, payment gateway terpisah, iklan, overhead tetap, biaya penanganan retur, write-off stok, dan
jurnal Mekari belum dihitung. Harga pokok yang dialokasikan masih mengikuti cakupan biaya produksi
v0.35.

Rencana: [contribution margin plan](docs/contribution-margin-plan.md).
Bukti pengujian: [contribution margin verification](docs/contribution-margin-verification.md).

## Forecast demand per SKU (v0.37)

Pilih **Forecast demand** dari navigasi utama. Tentukan tanggal akhir data, panjang periode historis,
horizon forecast, serta filter marketplace atau SKU bila diperlukan. Laporan membagi riwayat menjadi
dua periode yang sama panjang. Rata-rata harian periode terbaru berbobot 70% dan periode sebelumnya
30%, lalu rate gabungan dikalikan dengan jumlah hari horizon.

Demand berasal dari shipment marketplace aktif. Retur aktif yang sudah terjadi sampai tanggal
`as_of` mengurangi demand pada periode tanggal shipment asal. Shipment yang telah dikoreksi tidak
dihitung. Produk tanpa shipment tetap ditampilkan dengan status **Belum ada riwayat demand**, sehingga
angka nol tidak disamarkan sebagai hasil observasi.

API terkait: `GET /api/demand-forecast`. Parameter `as_of`, `window_days`, `horizon_days`, `query`,
`marketplace`, `limit`, dan `offset` tersedia. Default memakai dua window 28 hari dan horizon 30 hari.
Hasil menyertakan shipment, retur, demand neto, rate historis, rate forecast, tren, serta estimasi pcs
dua desimal. Schema tetap versi 30 karena laporan dihitung dari ledger penjualan yang sudah ada.

Forecast ini belum menjadi rekomendasi pembelian. Stok tersedia, barang dalam perjalanan, lead time,
MOQ, safety stock, promosi, musiman, dan data eksternal marketplace belum masuk perhitungan. Tanggal
`as_of` membatasi tanggal bisnis pada ledger yang saat ini aktif; laporan tidak merekonstruksi kapan
sebuah koreksi dicatat pada masa lalu.

Rencana: [demand forecast plan](docs/demand-forecast-plan.md).
Bukti pengujian: [demand forecast verification](docs/demand-forecast-verification.md).

## Risiko stockout dan rekomendasi pembelian (v0.38)

Pilih **Rekomendasi stok** untuk membandingkan forecast demand dengan stok jual, produksi berjalan,
lead time, periode review, safety stock, dan kelipatan batch. Sistem menampilkan days of cover,
estimasi tanggal stockout, reorder point, target stok, serta jumlah produksi baru yang disarankan untuk
setiap SKU.

Stok tersedia adalah barang sellable yang belum terreservasi. Estimasi stockout hanya memakai stok
tersedia agar risiko jangka pendek tetap terlihat. Inventory position untuk rekomendasi produksi
menambahkan order produksi yang masih berada di planned/WIP dan jatuh tempo di dalam horizon. Target
stok adalah pembulatan ke atas demand selama lead time + review period + safety stock. Kekurangan
terhadap inventory position dibulatkan ke kelipatan batch yang dipilih.

Rekomendasi produksi baru diterjemahkan menjadi kebutuhan bahan memakai BOM terbaru. Laporan juga
memasukkan sisa kebutuhan order produksi yang berjalan, lalu mengurangi stok bahan, PR terbuka, dan
sisa PO terbuka yang tanggal kebutuhannya berada di dalam horizon. Produk tanpa riwayat demand atau
BOM ditandai eksplisit agar sistem tidak mengubah data yang hilang menjadi rekomendasi nol yang
terlihat pasti.

API terkait: `GET /api/replenishment-recommendations`. Parameter `as_of`, `window_days`,
`lead_time_days`, `review_period_days`, `safety_stock_days`, `batch_multiple`, `query`, `marketplace`,
`limit`, dan `offset` tersedia. Default memakai lead time 14 hari, review 30 hari, safety stock 7
hari, serta batch 1 pcs. Schema tetap versi 30 karena fitur ini adalah read model.

Angka merupakan dukungan keputusan dan belum membuat order produksi atau PR secara otomatis. Tanggal
selesai produksi, kapasitas, harga, supplier, MOQ bahan, kalender kerja, promosi, musiman, dan data
eksternal marketplace belum menentukan hasil. `as_of` membatasi histori demand; stok dan pipeline
memakai posisi ledger aktif saat laporan dimuat.

Rencana: [stockout and purchase recommendations plan](docs/stockout-purchase-recommendations-plan.md).
Bukti pengujian: [stockout and purchase recommendations verification](docs/stockout-purchase-recommendations-verification.md).

## Investigasi bisnis dengan bahasa natural (v0.39)

Pilih **Tanya Beeloft** dari navigasi utama lalu ajukan pertanyaan tentang kondisi produksi, risiko
stockout, approval tertunda, margin kontribusi, atau prioritas bisnis. Sistem mengenali intent dengan
aturan lokal, mencari SKU atau referensi order yang disebut, lalu menyusun jawaban, fakta pendukung,
temuan, rekomendasi, sumber, dan batas analisis dari read model yang sudah tersedia.

Analisis berjalan sepenuhnya di proses aplikasi. Pertanyaan dan data ledger tidak dikirim ke model
atau layanan eksternal. Endpoint `POST /api/ai/investigate` bersifat hanya baca walaupun memakai body
JSON untuk membawa pertanyaan dan asumsi perencanaan. Semua role dapat memakai fitur ini karena hak
bacanya sama dengan laporan sumber.

Rekomendasi selalu diberi `approval_required: true` dan `executable: false`. Versi ini tidak membuat
order produksi, PR, keputusan approval, atau transaksi lain. Pengguna tetap harus memeriksa bukti dan
menjalankan workflow domain yang sesuai. Pemetaan bahasa masih berbasis kata kunci; pertanyaan ambigu
dapat masuk kategori yang salah.

Rencana: [AI investigation plan](docs/ai-investigation-plan.md).
Bukti pengujian: [AI investigation verification](docs/ai-investigation-verification.md).

## Proposal dan eksekusi tindakan AI (v0.40)

Admin/operator dapat memilih **Ajukan untuk approval** pada rekomendasi pembuatan order produksi atau
purchase request. Form melengkapi data operasional yang tidak boleh ditebak sistem, seperti referensi,
PIC, target selesai, tanggal kebutuhan, estimasi nilai, dan alasan. Pengajuan menyimpan snapshot
pertanyaan, asumsi perencanaan, rekomendasi, payload tindakan, pengaju, dan waktu dalam ledger
immutable. Belum ada order atau PR yang dibuat pada tahap ini.

Proposal masuk ke **Inbox approval** sebagai jenis **AI Brain · tindakan**. Viewer dapat membaca tetapi
tidak memutuskan. Admin dapat menyetujui, menolak, atau membatalkan; pemohon dapat membatalkan
proposalnya sendiri selama masih menunggu. Sebelum approval dijalankan, sistem menghitung ulang
rekomendasi dari ledger aktif. Perubahan stok, demand, produksi, BOM, PR, atau PO yang mengubah hasil
menjadikan proposal stale dan membatalkan seluruh eksekusi.

Approval order produksi membuat satu order beserta saldo planned dalam transaksi yang sama dengan
event keputusan. Approval purchase request membuat PR berstatus submitted, sehingga keputusan
pembeliannya tetap berjalan melalui approval purchasing yang sudah ada. Setiap hasil tindakan
ditautkan kembali ke proposal dan dapat dibuka dari riwayat approval.

API terkait:

- `POST /api/ai/action-proposals`.
- `GET /api/ai/action-proposals?status=...`.
- `GET /api/ai/action-proposals/{id}`.
- `POST /api/ai/action-proposals/{id}/decisions`.

Schema 30 → 31 menambahkan proposal dan event keputusan append-only. Versi ini belum menjalankan
perubahan jadwal, approval massal, integrasi eksternal, atau tindakan bebas di luar dua workflow yang
sudah memiliki guard domain.

Rencana: [AI approved actions plan](docs/ai-approved-actions-plan.md).
Bukti pengujian: [AI approved actions verification](docs/ai-approved-actions-verification.md).

## Riwayat investigasi dan feedback AI (v0.41)

**Tanya Beeloft** kini menyimpan setiap analisis sebagai snapshot immutable. Pertanyaan, asumsi,
intent, jawaban, fakta, temuan, rekomendasi, bukti, pengaju, dan waktu tetap dapat dibaca meski ledger
bisnis kemudian berubah. Penyimpanan memakai Idempotency-Key, termasuk ketika respons jaringan hilang
setelah server selesai mencatat.

Semua role dapat membuka **Riwayat investigasi**, mencari pertanyaan, memfilter jenis analisis, dan
memberikan feedback **Jawaban membantu** atau **Perlu diperbaiki** beserta alasan. Feedback bersifat
append-only. Ringkasan menghitung respons terbaru setiap pengguna agar perubahan penilaian tidak
menggandakan jumlah responden.

Proposal order produksi atau purchase request yang diajukan dari hasil tersimpan ditautkan kembali ke
investigasi asal. Server membandingkan asumsi dan rekomendasi snapshot dengan hasil terbaru ketika
proposal dibuat. Jika sudah berubah, proposal ditolak dan pengguna diminta menjalankan investigasi
baru. Pemeriksaan ulang saat approval dari v0.40 tetap berlaku.

API terkait:

- `POST /api/ai/investigations` untuk menjalankan dan menyimpan satu snapshot.
- `GET /api/ai/investigations?intent=...&q=...` untuk riwayat bercursor.
- `GET /api/ai/investigations/{id}` untuk snapshot, feedback, dan tindakan tertaut.
- `POST /api/ai/investigations/{id}/feedback` untuk event feedback.
- `POST /api/ai/investigate` tetap tersedia sebagai preview kompatibel yang tidak menyimpan data.

Schema 31 → 32 menambahkan ledger investigasi, feedback, dan linkage tindakan. Feedback belum melatih
model atau mengubah aturan rekomendasi secara otomatis.

Rencana: [AI investigation memory plan](docs/ai-investigation-memory-plan.md).
Bukti pengujian: [AI investigation memory verification](docs/ai-investigation-memory-verification.md).

## Status sinkronisasi Jubelio dan Mekari (v0.42)

Pilih **Integrasi** untuk melihat batas data setiap sistem dan kondisi sinkronisasi terakhir. Jubelio
menjadi sumber order marketplace, stok barang jadi/fulfillment, retur marketplace, dan listing.
Mekari menjadi sumber ringkasan keuangan, utang, piutang, dan payroll. Beeloft tetap menjadi ledger
operasional produksi internal.

Setiap scope menampilkan status **Belum pernah sinkron**, **Sehat**, **Terlambat**, atau **Gagal**,
jumlah record dibaca/ditulis/ditolak, cursor sumber, waktu mulai/selesai, pelaku, serta error terakhir.
Status sistem merangkum seluruh scope dan tidak menyebut integrasi sehat ketika salah satu scope belum
pernah berjalan atau gagal. Ambang terlambat default 24 jam dapat diubah melalui API.

Run hanya dapat dicatat oleh admin melalui endpoint worker. Ledger bersifat append-only dan request
POST idempotent. Dashboard sengaja tidak menyediakan tombol untuk menandai sync manual sebagai sukses.
Versi ini belum menyimpan credential vendor, memanggil API Jubelio/Mekari, menjadwalkan worker, atau
mengimpor data vendor. Kontrak endpoint worker:

- `GET /api/integrations?stale_after_minutes=1440` untuk source map dan health terkini.
- `POST /api/integration-sync-runs` untuk mencatat hasil satu run yang benar-benar dijalankan worker.
- `GET /api/integration-sync-runs?system=...&scope=...&status=...` untuk ledger bercursor.
- `GET /api/integration-sync-runs/{id}` untuk detail run immutable.

Schema 32 → 33 menambahkan ledger observability integrasi tanpa mengubah transaksi operasional lama.

Rencana: [integration sync health plan](docs/integration-sync-health-plan.md).
Bukti pengujian: [integration sync health verification](docs/integration-sync-health-verification.md).

## Mapping SKU Beeloft ke Jubelio (v0.43)

Buka **Master SKU → Jubelio** untuk menghubungkan satu SKU Beeloft dengan ID record dan kode SKU
yang diberikan Jubelio. Mapping ini menjadi identitas eksplisit untuk connector read-only; worker tidak
perlu menebak kecocokan dari nama, warna, atau ukuran produk.

Mapping aktif bersifat unik. Satu ID atau SKU Jubelio tidak dapat dipakai oleh dua SKU Beeloft pada
saat yang sama. Admin dapat memperbarui atau melepas mapping dengan alasan dan revision guard. Setiap
perubahan menjadi event immutable, sehingga nilai lama, pelaku, alasan, dan waktunya tetap dapat
ditelusuri semua role. Retry dengan Idempotency-Key yang sama tidak menggandakan revisi.

Layar **Integrasi** menampilkan jumlah SKU yang sudah dan belum dipetakan. Angka ini menunjukkan
kesiapan identitas, bukan bukti koneksi vendor aktif atau keberhasilan sinkronisasi. Versi ini belum
memanggil API Jubelio, memvalidasi identifier ke server Jubelio, atau mengimpor order/stok/retur.

API terkait:

- `GET /api/product-external-mappings?system=jubelio&status=...`.
- `GET /api/products/{product_id}/external-mappings/jubelio`.
- `POST /api/products/{product_id}/external-mappings/jubelio`.
- `GET /api/products/{product_id}/external-mappings/jubelio/history`.

Schema 33 → 34 menambahkan ledger mapping SKU tanpa mengubah master produk atau transaksi lama.

Rencana: [Jubelio SKU mapping plan](docs/jubelio-sku-mapping-plan.md).
Bukti pengujian: [Jubelio SKU mapping verification](docs/jubelio-sku-mapping-verification.md).

## Snapshot dan rekonsiliasi stok Jubelio (v0.44)

Worker dapat mengirim snapshot penuh stok barang jadi Jubelio melalui endpoint admin. Setiap item
harus membawa ID record dan kode SKU yang sama-sama cocok dengan satu mapping aktif. Record yang tidak
punya mapping atau membawa pasangan identifier yang berbeda masuk karantina dan tidak ikut dihitung.

Setiap impor otomatis membuat run sinkronisasi `jubelio/finished_goods`. Run dinyatakan berhasil
hanya jika semua record diterima; adanya satu record karantina membuat status gagal dengan jumlah
baca, tulis, dan tolak yang sebenarnya. Batch, item, karantina, dan run dicatat atomik serta immutable.
Retry dengan `Idempotency-Key` yang sama mengembalikan batch pertama tanpa menggandakan data.

Buka **Integrasi → Rekonsiliasi stok Jubelio** untuk membandingkan available terbaru dari Jubelio
(`sellable - reserved`) dengan available ledger barang jadi Beeloft per SKU. Hasil menunjukkan cocok,
selisih, SKU internal yang hilang dari snapshot, serta record karantina. Tampilan ini read-only dan
tidak mengubah stok Beeloft.

API terkait:

- `POST /api/integrations/jubelio/finished-goods-snapshots`.
- `GET /api/integrations/jubelio/finished-goods-snapshots`.
- `GET /api/integrations/jubelio/finished-goods-snapshots/{batch_id}`.
- `GET /api/integrations/jubelio/finished-goods-reconciliation`.

Schema 34 → 35 menambahkan ledger snapshot stok dan karantina tanpa mengubah ledger inventori lama.
Versi ini belum mengambil data langsung dari API Jubelio, menyimpan credential, menjadwalkan worker,
atau menulis penyesuaian stok otomatis.

Rencana: [Jubelio stock snapshot plan](docs/jubelio-stock-snapshot-plan.md).
Bukti pengujian: [Jubelio stock snapshot verification](docs/jubelio-stock-snapshot-verification.md).

## Snapshot order dan penjualan Jubelio (v0.45)

Worker dapat mengirim snapshot penuh order Jubelio melalui endpoint admin. Setiap baris membawa ID
item, SKU eksternal, jumlah unit, dan pendapatan kotor. Pasangan ID dan SKU harus menunjuk ke satu
mapping aktif yang sama. Jika satu baris tidak aman, seluruh order masuk karantina agar unit dan nilai
penjualan tidak tercatat sebagian.

Setiap impor otomatis membuat run sinkronisasi `jubelio/orders`. Run berstatus gagal bila ada order
yang dikarantina dan menyimpan jumlah order dibaca serta diterima yang sebenarnya. Batch, order,
baris, payload karantina, dan run disimpan atomik serta immutable. Retry dengan `Idempotency-Key` yang
sama tidak menggandakan snapshot.

Buka **Integrasi → Order & penjualan Jubelio** untuk melihat jumlah order per status, unit dan
pendapatan kotor dari order selesai, agregat per marketplace, record diterima, serta karantina. Data
ini read-only dan tidak membuat order produksi, reservasi, shipment, settlement, atau perubahan stok
Beeloft.

API terkait:

- `POST /api/integrations/jubelio/order-snapshots`.
- `GET /api/integrations/jubelio/order-snapshots`.
- `GET /api/integrations/jubelio/order-snapshots/{batch_id}`.
- `GET /api/integrations/jubelio/order-summary`.

Schema 35 → 36 menambahkan ledger snapshot order dan karantina whole-order. Versi ini belum mengambil
data langsung dari API Jubelio, menyimpan credential, menjadwalkan worker, atau mengimpor data pelanggan.

Rencana: [Jubelio order snapshot plan](docs/jubelio-order-snapshot-plan.md).
Bukti pengujian: [Jubelio order snapshot verification](docs/jubelio-order-snapshot-verification.md).

## Snapshot retur Jubelio (v0.46)

Worker dapat mengirim snapshot penuh retur Jubelio melalui endpoint admin. Setiap retur membawa
referensi retur dan order vendor, marketplace, status, nilai refund, serta baris SKU. ID item dan SKU
eksternal pada setiap baris harus menunjuk ke satu mapping aktif yang sama. Jika satu baris tidak aman,
seluruh retur masuk karantina agar unit dan refund tidak tercatat sebagian.

Setiap impor otomatis membuat run sinkronisasi `jubelio/returns`. Run berstatus gagal bila ada retur
yang dikarantina dan menyimpan jumlah retur dibaca serta diterima yang sebenarnya. Batch, retur,
baris, payload karantina, dan run disimpan atomik serta immutable. Retry dengan `Idempotency-Key` yang
sama tidak menggandakan snapshot.

Buka **Integrasi → Retur Jubelio** untuk melihat status retur, unit yang sudah diterima, refund yang
sudah selesai, agregat marketplace dan SKU, record diterima, serta karantina. Unit hanya dihitung pada
status `received` dan `refunded`; nilai refund hanya dihitung pada status `refunded`. Snapshot ini
tidak membuat retur internal, refund, settlement, atau perubahan stok Beeloft.

API terkait:

- `POST /api/integrations/jubelio/return-snapshots`.
- `GET /api/integrations/jubelio/return-snapshots`.
- `GET /api/integrations/jubelio/return-snapshots/{batch_id}`.
- `GET /api/integrations/jubelio/return-summary`.

Schema 36 → 37 menambahkan ledger snapshot retur dan karantina whole-return. Versi ini belum mengambil
data langsung dari API Jubelio, menyimpan credential, menjadwalkan worker, atau mengimpor data pelanggan.

Rencana: [Jubelio return snapshot plan](docs/jubelio-return-snapshot-plan.md).
Bukti pengujian: [Jubelio return snapshot verification](docs/jubelio-return-snapshot-verification.md).


## Snapshot listing Jubelio (v0.47)

Worker dapat mengirim snapshot penuh listing marketplace Jubelio melalui endpoint admin. Setiap listing
membawa ID dan referensi listing, marketplace, judul, status, harga tayang, waktu pembaruan, serta ID
item dan SKU eksternal. Pasangan ID item dan SKU harus menunjuk ke satu mapping aktif yang sama.
Record tanpa mapping atau dengan pasangan identifier berbeda masuk karantina.

Setiap impor otomatis membuat run sinkronisasi `jubelio/listings`. Run berstatus gagal bila ada listing
yang dikarantina dan menyimpan jumlah record dibaca serta diterima yang sebenarnya. Batch, listing,
payload karantina, dan run disimpan atomik serta immutable. Retry dengan `Idempotency-Key` yang sama
tidak menggandakan snapshot.

Buka **Integrasi → Listing Jubelio** untuk melihat cakupan produk aktif, jumlah listing aktif, nonaktif,
draft, dan diblokir, rentang harga listing aktif, agregat marketplace, record diterima, serta karantina.
Snapshot ini read-only dan tidak mengubah master produk, harga internal, atau stok Beeloft.

API terkait:

- `POST /api/integrations/jubelio/listing-snapshots`.
- `GET /api/integrations/jubelio/listing-snapshots`.
- `GET /api/integrations/jubelio/listing-snapshots/{batch_id}`.
- `GET /api/integrations/jubelio/listing-summary`.

Schema 37 → 38 menambahkan ledger snapshot listing dan karantina per record. Versi ini belum mengambil
data langsung dari API Jubelio, menyimpan credential, menjadwalkan worker, atau mengubah listing vendor.

Rencana: [Jubelio listing snapshot plan](docs/jubelio-listing-snapshot-plan.md).
Bukti pengujian: [Jubelio listing snapshot verification](docs/jubelio-listing-snapshot-verification.md).


## Snapshot ringkasan keuangan Mekari (v0.48)

Worker dapat mengirim snapshot laporan keuangan berkala Mekari melalui endpoint admin. Setiap periode
membawa pendapatan kotor, retur penjualan, harga pokok, beban operasional, pendapatan dan beban lain,
saldo kas, piutang, serta utang dalam IDR. Server menghitung pendapatan bersih, laba kotor, laba bersih,
dan posisi likuiditas dengan aritmetika desimal eksak.

Setiap impor otomatis membuat run sinkronisasi `mekari/finance_summary`. Batch, periode laporan, dan run
disimpan atomik serta immutable. Retry dengan `Idempotency-Key` yang sama mengembalikan snapshot awal
tanpa menggandakan data. Periode duplikat, rentang tanggal terbalik, nilai tidak valid, dan retur yang
melebihi pendapatan kotor ditolak sebelum pencatatan.

Buka **Integrasi → Keuangan Mekari** untuk melihat angka periode terbaru dan seluruh periode dalam
snapshot, kemudian telusuri riwayat serta detail sumber. Layar ini read-only. Mekari tetap menjadi
sumber accounting ledger; Beeloft tidak membuat jurnal, pembayaran, atau koreksi akuntansi.

API terkait:

- `POST /api/integrations/mekari/finance-snapshots`.
- `GET /api/integrations/mekari/finance-snapshots`.
- `GET /api/integrations/mekari/finance-snapshots/{batch_id}`.
- `GET /api/integrations/mekari/finance-summary`.

Schema 38 → 39 menambahkan batch dan periode snapshot keuangan Mekari. Versi ini belum mengambil data
langsung dari API Mekari, menyimpan credential, menjadwalkan worker, atau menulis ke accounting ledger.

Rencana: [Mekari finance snapshot plan](docs/mekari-finance-snapshot-plan.md).
Bukti pengujian: [Mekari finance snapshot verification](docs/mekari-finance-snapshot-verification.md).
