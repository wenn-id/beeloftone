# Riwayat implementasi Beeloft One

Dokumen ini menyimpan riwayat implementasi Beeloft One versi demi versi, dari v0.3 sampai v0.82.
Isinya dipindahkan dari `README.md` tanpa mengubah urutan atau isi teknisnya, supaya README dapat
menjadi halaman ringkas. Untuk gambaran produk dan cara menjalankan aplikasi, lihat
[README](../README.md); untuk manual operasional lengkap, lihat [panduan operasional](operations.md).

Setiap bagian di bawah memakai penomoran versi rilis internal dan menautkan rencana serta bukti
pengujian milestone tersebut.

## Cakupan fungsional v0.82.0

Pelacakan operasi internal, versi 0.82.0. Dashboard dan API memakai database lokal yang sama: employee master, kehadiran, cuti, absen, lembur, serta permintaan dan approval cuti/lembur; management command center; order, posisi barang per tahap, WIP ageing dan sinyal hambatan; perencanaan kapasitas work center berbasis menit, standar routing SKU, dan kalender kerja; tren yield dan defect final QC per line atau vendor serta alert kualitas dan risiko kapasitas di Command Center; batch bahan dengan label QR, scan, dan jejak produksi lengkap; hasil cutting, identitas dan label QR bundle, scan serta serah-terima bundle dua pihak; job sewing/makloon, finishing, final QC, penerimaan dan label QR barang jadi; scan untuk membuka aksi dan memverifikasi pergerakan gudang; jejak stok lengkap per lot; reservasi marketplace, picking dengan verifikasi SKU/QR lot, packing, shipping, settlement penjualan, retur pelanggan; analisis retur per SKU/ukuran/marketplace, demand dan risiko stockout per ukuran, dead stock, adjustment, stock opname, serta adjustment tidak normal; kinerja supplier, pergerakan harga bahan per supplier, komitmen pembelian terbuka; biaya produksi aktual, margin kontribusi, forecast demand, risiko stockout, rekomendasi produksi dan pembelian bahan; inbox approval, investigasi bisnis berbahasa Indonesia, tindakan AI yang memerlukan approval, riwayat investigasi dan feedback tim; status sinkronisasi Jubelio/Mekari, mapping SKU, snapshot Jubelio, ringkasan keuangan, utang usaha, piutang usaha, payroll agregat Mekari, approval batch payroll, rekonsiliasi pembayaran, dan rekonsiliasi akuntansi payroll; serta global audit trail untuk perubahan bisnis dan approval.

## Riwayat migrasi schema

Schema sekarang versi 53. Belum mencakup partial cancellation, perubahan jumlah target setelah order dibuat, attachment kendala, atau konektor aktif ke Jubelio/Mekari. Schema sekarang versi 53. Migrasi 52 → 53 menambahkan metadata jurnal agregat payroll pada snapshot Mekari secara immutable. Migrasi 51 → 52 menambahkan permintaan dan ledger keputusan approval batch payroll immutable. Migrasi 50 → 51 menambahkan permintaan dan ledger keputusan cuti/lembur immutable. Migrasi 49 → 50 menambahkan employee master dan ledger kehadiran immutable. Migrasi 48 → 49 menambahkan master work center, standar routing SKU, override kalender, dan rencana kapasitas. Migrasi 47 → 48 menambahkan bukti SKU/QR lot pada pergerakan gudang beserta guard kecocokan terhadap receipt. Migrasi 46 → 47 menambahkan bukti SKU/QR lot pada pick marketplace beserta guard kecocokan terhadap receipt. Migrasi 45 → 46 menambahkan ledger pengiriman, penerimaan, dan pembatalan handoff bundle beserta lokasi custody. Migrasi 44 → 45 menambahkan global audit trail immutable untuk perubahan bisnis dan approval. Migrasi 43 → 44 menambahkan mapping identitas OIDC dan state login sekali pakai. Migrasi 42 → 43 menambahkan session browser berbasis cookie dan proteksi CSRF. Migrasi 41 → 42 menambahkan snapshot payroll agregat Mekari per periode. Migrasi 40 → 41 menambahkan snapshot piutang usaha Mekari dan status jatuh tempo. Migrasi 39 → 40 menambahkan snapshot utang usaha Mekari dan status jatuh tempo. Migrasi 38 → 39 menambahkan snapshot ringkasan keuangan Mekari per periode. Migrasi 37 → 38 menambahkan snapshot listing marketplace Jubelio dan karantina identifier yang tidak aman. Migrasi 36 → 37 menambahkan snapshot retur Jubelio, baris SKU, dan karantina whole-return. Migrasi 35 → 36 menambahkan snapshot order dan baris SKU Jubelio beserta karantina whole-order. Migrasi 34 → 35 menambahkan batch snapshot stok Jubelio, item yang diterima, serta karantina identifier yang tidak aman. Migrasi 33 → 34 menambahkan mapping SKU eksternal Jubelio dan riwayat revisi immutable. Migrasi 32 → 33 menambahkan ledger run sinkronisasi immutable dan peta source of truth. Migrasi 31 → 32 menambahkan riwayat investigasi AI, feedback, dan linkage tindakan. Migrasi 30 → 31 menambahkan proposal tindakan AI beserta keputusan approval. Migrasi 29 → 30 menambahkan settlement penjualan marketplace, koreksi immutable, snapshot cakupan retur, dan guard pengiriman. Migrasi 28 → 29 menambahkan request dan approval budget marketing dengan periode, channel, objective, nominal, role guard, dan ledger keputusan immutable. Migrasi 27 → 28 menambahkan request dan approval pembayaran supplier, batas nilai penerimaan aktif, serta guard koreksi receipt. Migrasi 26 → 27 menambahkan approval penerbitan PO, backfill PO historis sebagai approved, serta guard penerimaan/QC. Migrasi 25 → 26 menambahkan ledger permintaan perubahan produksi, keputusan immutable, penerapan perubahan order atomik, revision guard, serta inbox approval gabungan dengan PR. Migrasi 24 → 25 menambahkan ledger stock opname barang jadi, snapshot saldo sistem, jumlah fisik, adjustment selisih yang terhubung, koreksi immutable, scan SKU, serta guard reserved stock. Migrasi 23 → 24 menambahkan ledger retur pelanggan dan adjustment barang jadi, alasan retur terstruktur, status hasil inspeksi, stok per receipt, koreksi immutable, serta guard shipment/reservasi/saldo. Migrasi 22 → 23 menambahkan ledger shipping marketplace, carrier/resi, stok keluar gudang, koreksi immutable, dan guard jumlah/tanggal/pack. Migrasi 21 → 22 menambahkan ledger packing marketplace, stok `packed` di staging, koreksi immutable, dan guard jumlah/tanggal/pick. Migrasi 20 → 21 menambahkan ledger picking marketplace, stok `picked` di lokasi staging, koreksi immutable, dan guard jumlah/tanggal/release. Migrasi 19 → 20 menambahkan ledger reservasi marketplace, pemisahan available/reserved, pelepasan, dan guard stok terlindungi. Migrasi 18 → 19 menambahkan ledger transfer lokasi dan keputusan hold, status damaged, inventori per lokasi, koreksi immutable, serta guard saldo sumber/tujuan. Migrasi 17 → 18 menambahkan atribut defect final QC, ledger penerimaan barang jadi, pembagian sellable/hold, inventory per SKU, koreksi immutable, dan guard alokasi. Migrasi 16 → 17 menambahkan ledger final QC, temuan pengukuran/visual, hasil accepted/rework/reject, tiga perpindahan atomik, dan guard sumber finishing. Migrasi 15 → 16 menambahkan ledger finishing, lima checklist wajib, lineage hasil sewing, perpindahan ke QC, koreksi atomik, dan guard alokasi. Migrasi 14 → 15 menambahkan ledger job sewing/makloon, hasil selesai/defect/missing, biaya, turnaround, koreksi atomik, dan guard alokasi bundle. Migrasi 13 → 14 menambahkan identitas bundle, alokasi terhadap output cutting, koreksi immutable, dan guard over-allocation. Migrasi 12 → 13 menambahkan hasil cutting yang menghubungkan pemakaian bahan, waste, dan perpindahan pcs ke sewing, beserta koreksi atomik. Migrasi 11 → 12 menambahkan retur supplier, penutupan PO, dan guard riwayat final. Migrasi 10 → 11 menambahkan antrean QC kedatangan PO, keputusan layak pakai/reject, dan guard pembatalan/koreksi. Migrasi 9 → 10 menambahkan hubungan penerimaan batch ke PO. Migrasi 8 → 9 menambahkan master pemasok, PO, dan catatan pembatalannya. Migrasi 7 → 8 menambahkan PR dan riwayat keputusan. Migrasi 6 → 7 menambahkan ledger pemakaian aktual dan waste cutting. Migrasi 5 → 6 menambahkan ledger reservasi. Migrasi 4 → 5 menambahkan master bahan, batch, dan ledger bahan. Migrasi 3 → 4 menambahkan versi BOM. Saat startup, migrasi 1 → 2 menambahkan tabel kendala dan 2 → 3 menambahkan riwayat tenggat/PIC. Setiap migrasi berjalan dalam satu transaksi tanpa mengubah catatan produksi lama. Buat backup dengan versi aplikasi lama sebelum upgrade. Backup demo sebelum upgrade v0.4 tersedia lokal di `data/backups/demo-before-v04.sqlite3`.

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

Status seluruh fase blueprint dan batas increment ini ada di [roadmap bahan](materials-plan.md).
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

Hasil pengujian: [verifikasi bahan](materials-verification.md).

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
Rencana: [BOM](bom-plan.md). Hasil pengujian: [verifikasi BOM](bom-verification.md).

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
[reservasi](reservations-plan.md) dan [hasil uji](reservations-verification.md).

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
tetap wajib. Rencana: [pemakaian](consumption-plan.md). Hasil uji: [verifikasi pemakaian](consumption-verification.md).

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
mencakup PR dan seluruh keputusan. Rencana: [PR](purchase-requests-plan.md).
Hasil pengujian: [verifikasi PR](purchase-requests-verification.md).
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
Rencana dan batas: [PO](purchase-orders-plan.md); hasil uji: [verifikasi PO](purchase-orders-verification.md).


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
dan keputusan pelepasan stok. Bukti pengujian: [verifikasi penerimaan PO](po-receipts-verification.md).

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
Rencana dan bukti: [incoming QC plan](incoming-qc-plan.md) dan [verifikasi incoming QC](incoming-qc-verification.md).

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

Rencana: [supplier returns plan](supplier-returns-plan.md).
Bukti pengujian: [supplier returns verification](supplier-returns-verification.md).

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

Rencana: [cutting plan](cutting-plan.md).
Bukti pengujian: [cutting verification](cutting-verification.md).

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

Rencana: [bundling plan](bundles-plan.md).
Bukti pengujian: [bundling verification](bundles-verification.md).

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

Rencana: [sewing/makloon plan](sewing-makloon-plan.md).
Bukti pengujian: [sewing/makloon verification](sewing-makloon-verification.md).

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

Rencana: [finishing plan](finishing-plan.md).
Bukti pengujian: [finishing verification](finishing-verification.md).

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

Rencana: [final QC plan](final-qc-plan.md).
Bukti pengujian: [final QC verification](final-qc-verification.md).

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

Rencana: [finished goods plan](finished-goods-plan.md).
Bukti pengujian: [finished goods verification](finished-goods-verification.md).

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

Rencana: [warehouse movements plan](warehouse-movements-plan.md).
Bukti pengujian: [warehouse movements verification](warehouse-movements-verification.md).

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

Rencana: [marketplace reservations plan](marketplace-reservations-plan.md).
Bukti pengujian: [marketplace reservations verification](marketplace-reservations-verification.md).

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

Rencana: [marketplace picking plan](marketplace-picking-plan.md).
Bukti pengujian: [marketplace picking verification](marketplace-picking-verification.md).

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

Rencana: [marketplace packing plan](marketplace-packing-plan.md).
Bukti pengujian: [marketplace packing verification](marketplace-packing-verification.md).

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

Rencana: [marketplace shipping plan](marketplace-shipping-plan.md).
Bukti pengujian: [marketplace shipping verification](marketplace-shipping-verification.md).

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

Rencana: [returns and adjustments plan](returns-adjustments-plan.md).
Bukti pengujian: [returns and adjustments verification](returns-adjustments-verification.md).

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

Rencana: [inventory reconciliation plan](inventory-reconciliation-plan.md).
Bukti pengujian: [inventory reconciliation verification](inventory-reconciliation-verification.md).

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

Rencana: [unified approvals plan](unified-approvals-plan.md).
Bukti pengujian: [unified approvals verification](unified-approvals-verification.md).

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

Rencana: [purchase order approvals plan](purchase-order-approvals-plan.md).
Bukti pengujian: [purchase order approvals verification](purchase-order-approvals-verification.md).

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

Rencana: [supplier payment approvals plan](supplier-payment-approvals-plan.md).
Bukti pengujian: [supplier payment approvals verification](supplier-payment-approvals-verification.md).

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

Rencana: [marketing budget approvals plan](marketing-budget-approvals-plan.md).
Bukti pengujian: [marketing budget approvals verification](marketing-budget-approvals-verification.md).

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

Rencana: [production cost reporting plan](production-cost-reporting-plan.md).
Bukti pengujian: [production cost reporting verification](production-cost-reporting-verification.md).

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

Rencana: [contribution margin plan](contribution-margin-plan.md).
Bukti pengujian: [contribution margin verification](contribution-margin-verification.md).

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

Rencana: [demand forecast plan](demand-forecast-plan.md).
Bukti pengujian: [demand forecast verification](demand-forecast-verification.md).

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

Rencana: [stockout and purchase recommendations plan](stockout-purchase-recommendations-plan.md).
Bukti pengujian: [stockout and purchase recommendations verification](stockout-purchase-recommendations-verification.md).

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

Rencana: [AI investigation plan](ai-investigation-plan.md).
Bukti pengujian: [AI investigation verification](ai-investigation-verification.md).

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

Rencana: [AI approved actions plan](ai-approved-actions-plan.md).
Bukti pengujian: [AI approved actions verification](ai-approved-actions-verification.md).

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

Rencana: [AI investigation memory plan](ai-investigation-memory-plan.md).
Bukti pengujian: [AI investigation memory verification](ai-investigation-memory-verification.md).

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

Rencana: [integration sync health plan](integration-sync-health-plan.md).
Bukti pengujian: [integration sync health verification](integration-sync-health-verification.md).

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

Rencana: [Jubelio SKU mapping plan](jubelio-sku-mapping-plan.md).
Bukti pengujian: [Jubelio SKU mapping verification](jubelio-sku-mapping-verification.md).

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

Rencana: [Jubelio stock snapshot plan](jubelio-stock-snapshot-plan.md).
Bukti pengujian: [Jubelio stock snapshot verification](jubelio-stock-snapshot-verification.md).

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

Rencana: [Jubelio order snapshot plan](jubelio-order-snapshot-plan.md).
Bukti pengujian: [Jubelio order snapshot verification](jubelio-order-snapshot-verification.md).

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

Rencana: [Jubelio return snapshot plan](jubelio-return-snapshot-plan.md).
Bukti pengujian: [Jubelio return snapshot verification](jubelio-return-snapshot-verification.md).


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

Rencana: [Jubelio listing snapshot plan](jubelio-listing-snapshot-plan.md).
Bukti pengujian: [Jubelio listing snapshot verification](jubelio-listing-snapshot-verification.md).


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

Rencana: [Mekari finance snapshot plan](mekari-finance-snapshot-plan.md).
Bukti pengujian: [Mekari finance snapshot verification](mekari-finance-snapshot-verification.md).


## Snapshot utang usaha Mekari (v0.49)

Worker dapat mengirim snapshot invoice supplier Mekari melalui endpoint admin. Setiap record membawa
identifier invoice dan supplier, tanggal invoice dan jatuh tempo, status, nilai awal, nilai dibayar,
mata uang IDR, serta waktu pembaruan sumber. Status terbuka, dibayar sebagian, lunas, dan dibatalkan
divalidasi terhadap nilai pembayaran agar saldo tidak saling bertentangan.

Setiap impor otomatis membuat run sinkronisasi `mekari/payables`. Batch, invoice, dan run disimpan
atomik serta immutable. Retry dengan `Idempotency-Key` yang sama tidak menggandakan data. Server
menghitung saldo belum dibayar, overdue terhadap tanggal posisi snapshot, dan kewajiban jatuh tempo
dalam tujuh hari tanpa mengubah status invoice vendor.

Buka **Integrasi → Utang Mekari** untuk melihat total kewajiban, invoice overdue, kebutuhan kas tujuh
hari, agregat supplier, record invoice, riwayat, dan detail sumber. Layar ini read-only dan tidak
membayar invoice atau membuat jurnal Mekari.

API terkait:

- `POST /api/integrations/mekari/payable-snapshots`.
- `GET /api/integrations/mekari/payable-snapshots`.
- `GET /api/integrations/mekari/payable-snapshots/{batch_id}`.
- `GET /api/integrations/mekari/payables-summary`.

Schema 39 → 40 menambahkan batch dan record snapshot utang Mekari. Versi ini belum mengambil data
langsung dari API Mekari, menyimpan credential, menjadwalkan worker, atau menjalankan pembayaran.

Rencana: [Mekari payable snapshot plan](mekari-payable-snapshot-plan.md).
Bukti pengujian: [Mekari payable snapshot verification](mekari-payable-snapshot-verification.md).


## Snapshot piutang usaha Mekari (v0.50)

Worker dapat mengirim snapshot invoice pelanggan Mekari melalui endpoint admin. Setiap record membawa
identifier invoice dan pelanggan, tanggal invoice dan jatuh tempo, status, nilai awal, nilai diterima,
mata uang IDR, serta waktu pembaruan sumber. Status terbuka, diterima sebagian, lunas, dan dibatalkan
divalidasi terhadap nilai penerimaan agar saldo tidak saling bertentangan.

Setiap impor otomatis membuat run sinkronisasi `mekari/receivables`. Batch, invoice, dan run disimpan
atomik serta immutable. Retry dengan `Idempotency-Key` yang sama tidak menggandakan data. Server
menghitung saldo belum diterima, overdue terhadap tanggal posisi snapshot, dan penerimaan yang jatuh
tempo dalam tujuh hari tanpa mengubah status invoice sumber.

Buka **Integrasi → Piutang Mekari** untuk melihat total piutang, invoice overdue, penerimaan tujuh hari,
agregat pelanggan, record invoice, riwayat, dan detail sumber. Layar ini read-only dan tidak menagih
pelanggan atau membuat jurnal Mekari.

API terkait:

- `POST /api/integrations/mekari/receivable-snapshots`.
- `GET /api/integrations/mekari/receivable-snapshots`.
- `GET /api/integrations/mekari/receivable-snapshots/{batch_id}`.
- `GET /api/integrations/mekari/receivables-summary`.

Schema 40 → 41 menambahkan batch dan record snapshot piutang Mekari. Versi ini belum mengambil data
langsung dari API Mekari, menyimpan credential, menjadwalkan worker, atau menjalankan penagihan.

Rencana: [Mekari receivable snapshot plan](mekari-receivable-snapshot-plan.md).
Bukti pengujian: [Mekari receivable snapshot verification](mekari-receivable-snapshot-verification.md).


## Snapshot payroll agregat Mekari (v0.51)

Worker dapat mengirim snapshot ringkasan payroll per periode melalui endpoint admin. Setiap periode
membawa ID payroll sumber, rentang tanggal, status, jumlah karyawan, gaji bruto, potongan karyawan,
kontribusi perusahaan, tanggal pembayaran, dan waktu pembaruan sumber. Beeloft menghitung gaji neto
serta total biaya perusahaan dengan aritmetika desimal eksak.

Setiap impor otomatis membuat run sinkronisasi `mekari/payroll`. Batch, periode payroll, dan run
disimpan atomik serta immutable. Retry dengan `Idempotency-Key` yang sama tidak menggandakan data.
Status dibayar wajib memiliki tanggal pembayaran; status lain tidak boleh memilikinya.

Buka **Integrasi → Payroll Mekari** untuk melihat status dan biaya periode terbaru, hitungan status
dalam snapshot, riwayat, serta detail sumber. Kontrak sengaja hanya menerima agregat dan tidak memuat
nama, NIK, rekening, absensi, atau rincian potongan per karyawan. Layar ini read-only dan tidak
menghitung, menyetujui, atau membayar payroll.

API terkait:

- `POST /api/integrations/mekari/payroll-snapshots`.
- `GET /api/integrations/mekari/payroll-snapshots`.
- `GET /api/integrations/mekari/payroll-snapshots/{batch_id}`.
- `GET /api/integrations/mekari/payroll-summary`.

Schema 41 → 42 menambahkan batch dan periode snapshot payroll Mekari. Versi ini belum mengambil data
langsung dari API Mekari, menyimpan credential, menjadwalkan worker, menjalankan approval, atau
membuat jurnal akuntansi.

Rencana: [Mekari payroll snapshot plan](mekari-payroll-snapshot-plan.md).
Bukti pengujian: [Mekari payroll snapshot verification](mekari-payroll-snapshot-verification.md).


## Session browser aman (v0.52)

Dashboard menukar API key dengan session browser delapan jam melalui `POST /api/session`. Token session
dan token CSRF dibuat acak; database hanya menyimpan hash keduanya. Setiap request session memastikan
akun masih aktif, sedangkan request yang mengubah data wajib membawa token CSRF. Logout mencabut session
di server dan menghapus kedua cookie. Reload memulihkan identitas lewat `GET /api/me` selama session
masih berlaku.

API key pada header `X-API-Key` tetap didukung untuk worker dan integrasi non-browser. Endpoint terkait:

- `POST /api/session`.
- `POST /api/session/logout`.
- `GET /api/me`.

Schema 42 → 43 menambahkan session browser yang dapat dicabut. Ini menyiapkan batas autentikasi browser
untuk integrasi identitas berikutnya. Rilis ini belum menjalankan discovery OIDC, redirect/callback,
pemetaan klaim, login penyedia identitas, MFA, atau SSO.

Rencana: [Browser session plan](browser-session-plan.md).
Bukti pengujian: [Browser session verification](browser-session-verification.md).


## Login OIDC / SSO (v0.53)

Beeloft mendukung Authorization Code Flow dengan PKCE untuk satu penyedia identitas OIDC. Login dimulai
dari `/api/sso/login`; callback memverifikasi signature ID token melalui JWKS serta memeriksa issuer,
audience, expiry, nonce, dan authorized party. State dan nonce disimpan sebagai hash dengan masa berlaku
sepuluh menit. Cookie state `HttpOnly` mengikat callback ke browser yang memulai login.

Identitas OIDC tidak otomatis membuat akun atau menentukan role. Admin menautkan pasangan issuer dan
claim `sub` ke user Beeloft yang sudah ada. Akun nonaktif tetap ditolak. Contoh penautan:

```powershell
.\.venv\Scripts\python.exe -m beeloft --db data\beeloft.sqlite3 oidc-link `
  --issuer "https://identity.example" --subject "SUB_DARI_PROVIDER" --user-id "ID_USER_BEELOFT"
```

Lepaskan mapping yang keliru dengan subcommand `oidc-unlink` dan issuer/subject yang sama. Sebelum
menjalankan server, isi konfigurasi sebagai environment variable:

```powershell
$env:BEELOFT_OIDC_ISSUER="https://identity.example"
$env:BEELOFT_OIDC_CLIENT_ID="CLIENT_ID"
$env:BEELOFT_OIDC_CLIENT_SECRET="CLIENT_SECRET"
$env:BEELOFT_OIDC_REDIRECT_URI="https://beeloft.example/api/sso/callback"
$env:BEELOFT_OIDC_LABEL="Akun perusahaan"
```

Issuer dan endpoint provider wajib HTTPS; redirect HTTP hanya diterima untuk loopback lokal. Client
secret tidak disimpan di database. Implementasi menerima ID token RS256 atau ES256 dan autentikasi
token endpoint `client_secret_post` atau `client_secret_basic`. Endpoint terkait:

- `GET /api/sso`.
- `GET /api/sso/login`.
- `GET /api/sso/callback`.

Schema 43 → 44 menambahkan mapping identitas dan transaksi login OIDC. Rilis ini belum menyediakan
auto-provision, mapping role dari claim provider, multi-provider, refresh token, MFA internal, atau
halaman admin untuk mengelola mapping.

Rencana: [OIDC SSO plan](oidc-sso-plan.md).
Bukti pengujian: [OIDC SSO verification](oidc-sso-verification.md).


## Management command center (v0.54)

Menu **Command center** menyatukan angka yang sebelumnya tersebar di papan produksi, inbox approval,
rekomendasi stok, kesehatan integrasi, snapshot penjualan Jubelio, serta snapshot keuangan Mekari.
Ringkasan teratas menunjukkan order aktif, keputusan yang menunggu, jumlah exception, dan laba bersih
periode terakhir. Daftar perhatian mengurutkan kondisi kritis lebih dahulu dan membawa pengguna ke
filter atau dialog sumbernya.

Angka vendor selalu menampilkan waktu snapshot sumber. Data yang belum pernah disinkronkan tetap
ditandai belum tersedia dan scope integrasi masuk antrean perhatian; aplikasi tidak mengubahnya menjadi
nol yang terlihat seolah sudah terverifikasi. Command center bersifat read-only dan tersedia bagi semua
role aktif. Hak membuat pencatatan atau keputusan tetap diperiksa oleh endpoint domain tujuan.

API terkait:

- `GET /api/command-center`.

Schema tetap 44 karena milestone ini hanya membentuk read model dari ledger yang sudah ada. Agregasi
replenishment memakai default operasional: histori 28 hari, lead time 14 hari, review 30 hari, dan safety
stock 7 hari. Parameter tersebut belum dapat diubah dari Command Center; analisis khusus tetap tersedia
melalui menu **Rekomendasi stok**.

Rencana: [Management command center plan](management-command-center-plan.md).
Bukti pengujian: [Management command center verification](management-command-center-verification.md).


## Global audit trail (v0.55)

Menu **Audit trail** memberi admin satu riwayat lintas modul untuk perubahan bisnis manual, impor
snapshot, dan keputusan approval. Setiap event menyimpan operasi, objek dan referensi, snapshot nama
serta role pelaku, `Idempotency-Key`, input perubahan, hasil tersimpan, dan waktu UTC yang ditampilkan
dalam waktu Jakarta. Event ditulis di transaksi yang sama dengan data bisnis. Transaksi gagal tidak
menghasilkan event dan retry request yang sama mengembalikan hasil lama tanpa menggandakan audit.

Daftar dapat dicari melalui operasi, referensi, pelaku, request key, atau isi perubahan; filter tersedia
untuk kategori, pelaku, dan rentang tanggal maksimal 366 hari. Detail input dan hasil bersifat read-only.
Payload impor vendor berbentuk daftar disimpan sebagai jumlah record agar audit tidak membuat salinan
penuh snapshot vendor, dan field credential dikenali lalu disamarkan. Akses daftar dan detail hanya
untuk admin karena isinya melintasi seluruh domain bisnis.

API terkait:

- `GET /api/audit-events`.
- `GET /api/audit-events/{event_id}`.

Schema 44 → 45 menambahkan tabel `audit_events`, indeks pencarian, dan trigger yang menolak update
atau delete. Audit ini mencakup write domain yang melalui API transaksi pusat. Provisioning akun,
perubahan akses dari CLI, login, logout, dan event keamanan OIDC belum masuk global audit trail.

Rencana: [Global audit trail plan](global-audit-trail-plan.md).
Bukti pengujian: [Global audit trail verification](global-audit-trail-verification.md).


## Label QR dan scan bundle (v0.56)

Setiap bundle aktif sekarang memiliki kode stabil `BEELOFT:BUNDLE:{id}` dan label QR SVG yang dapat
dicetak dari rincian bundle. Label menampilkan Bundle ID, SKU, ukuran, jumlah, dan referensi order.
Kode QR memuat ID internal yang tidak berubah meski Bundle ID mengandung variasi huruf besar/kecil.
Label dibuat lokal oleh aplikasi dan tidak mengirim isi bundle ke layanan QR eksternal.

Menu **Scan bundle** tersedia untuk seluruh role aktif. Scanner USB/Bluetooth dapat mengisi kolom seperti
keyboard dan membuka rincian saat mengirim Enter. Pengguna juga dapat mengetik Bundle ID secara manual.
Hasil scan menampilkan lineage cutting, batch bahan, order, alokasi sewing, dan status aktif/dikoreksi.
Bundle yang sudah dikoreksi tetap dapat ditelusuri tetapi labelnya tidak dapat dicetak ulang.

API terkait:

- `GET /api/bundles/scan?code=...`.
- `GET /api/bundles/{bundle_id}/label.svg`.

Schema label tetap berasal dari v0.56 karena scan code dihitung dari ID bundle existing. Scan tetap berupa
lookup; serah-terima dicatat lewat tindakan terpisah. Kamera browser, split/merge, dan pencetakan banyak
label sekaligus belum didukung.

Rencana: [Bundle scan and label plan](bundle-scanning-plan.md).
Bukti pengujian: [Bundle scan and label verification](bundle-scanning-verification.md).


## Serah-terima bundle dua pihak (v0.57)

Dari rincian atau hasil scan bundle, admin/operator dapat memilih **Serahkan bundle**, mengisi tujuan,
dan menjelaskan perpindahan fisiknya. Bundle kemudian berstatus menunggu penerima. Admin/operator dengan
akun berbeda memilih **Konfirmasi terima** setelah mencocokkan Bundle ID, jumlah, dan kondisi fisik.
Lokasi custody baru berubah setelah konfirmasi tersebut.

Hanya satu handoff pending yang diperbolehkan untuk setiap bundle. Pengirim tidak dapat mengonfirmasi
handoff miliknya sendiri. Admin dapat membatalkan handoff yang masih pending; seluruh catatan pengiriman,
penerimaan, dan pembatalan bersifat immutable dan masuk global audit trail. Viewer dapat membaca lokasi
dan riwayat, tanpa tombol tindakan.

API terkait:

- `GET /api/bundles/{bundle_id}/handoffs`.
- `POST /api/bundles/{bundle_id}/handoffs`.
- `POST /api/bundle-handoffs/{handoff_id}/accept`.
- `POST /api/bundle-handoffs/{handoff_id}/cancel`.

Custody bundle merupakan jejak fisik terpisah dari ledger WIP. Menerima handoff tidak memindahkan saldo
tahap atau membuat job sewing. Bundle yang masih memiliki handoff pending tidak dapat dikoreksi sampai
handoff diterima atau dibatalkan. Schema 45 → 46 menambahkan ledger dan guard tersebut.

Rencana: [Bundle handoff plan](bundle-handoffs-plan.md).
Bukti pengujian: [Bundle handoff verification](bundle-handoffs-verification.md).


## Label QR dan scan batch bahan (v0.58)

Setiap batch bahan memiliki kode stabil `BEELOFT:MATERIAL-BATCH:{id}`. Dari layar **Bahan baku**, seluruh
role aktif dapat memilih **Scan batch bahan**, memindai QR memakai scanner USB/Bluetooth seperti keyboard,
atau mengetik referensi batch. Hasilnya membuka rincian batch, saldo, reservasi, riwayat penerimaan dan
pengeluaran, lokasi rak, serta hubungan PO/QC jika tersedia.

Rincian batch aktif menampilkan label QR 80 mm yang memuat referensi batch, kode dan nama bahan, jumlah
awal diterima, satuan, lokasi, dan tanggal penerimaan. Label dibuat lokal tanpa layanan QR eksternal.
Batch yang penerimaannya sudah dikoreksi tetap dapat ditemukan melalui scan untuk menjaga histori, tetapi
labelnya tidak dapat dicetak ulang.

API terkait:

- `GET /api/material-batches/scan?code=...`.
- `GET /api/material-batches/{batch_id}/label.svg`.

Rilis ini tidak mengubah schema database; schema tetap 46. Scanner kamera, pencetakan banyak label,
template printer khusus, dan perpindahan lokasi batch belum dicakup. Connector runtime Jubelio/Mekari
tetap ditunda sampai akses API resmi tersedia.

Rencana: [Material batch scanning plan](material-batch-scanning-plan.md).
Bukti pengujian: [Material batch scanning verification](material-batch-scanning-verification.md).

## Label QR dan scan barang jadi (v0.59)

Setiap penerimaan barang jadi memiliki kode stabil `BEELOFT:FINISHED-GOODS:{id}`. Tombol **Scan barang
jadi** tersedia dari navigasi operasional untuk seluruh role. Operator dapat memindai label memakai scanner
USB/Bluetooth atau mengetik referensi penerimaan, lalu langsung melihat lokasi dan status stok lot tersebut.

Rincian penerimaan aktif menampilkan label QR 80 mm dengan referensi penerimaan, SKU, ukuran, jumlah awal,
lokasi, tanggal terima, dan order produksi. Dari rincian yang sama admin/operator dapat melanjutkan ke
transfer lokasi, reservasi marketplace, adjustment, atau stock opname sesuai stok dan role. Penerimaan yang
sudah dikoreksi tetap dapat ditemukan untuk audit, tetapi labelnya tidak dapat dicetak ulang.

API terkait:

- `GET /api/finished-goods-receipts/scan?code=...`.
- `GET /api/finished-goods-receipts/{receipt_id}/label.svg`.

Rilis ini tidak mengubah schema database; schema tetap 46. Scan hanya mencari identitas dan tidak membuat
pergerakan stok. Kamera, pencetakan banyak label, template printer khusus, dan connector runtime
Jubelio/Mekari belum dicakup.

Rencana: [Finished-goods scanning plan](finished-goods-scanning-plan.md).
Bukti pengujian: [Finished-goods scanning verification](finished-goods-scanning-verification.md).

## Verifikasi scan saat picking (v0.60)

Setiap pencatatan pick baru wajib memuat `scanned_code`. Nilainya harus cocok dengan SKU reservasi atau kode
QR lot `BEELOFT:FINISHED-GOODS:{receipt_id}`. Validasi dilakukan di API dan trigger database sebelum stok
reserved berpindah dari rak sellable ke lokasi staging.

Form **Catat pick marketplace** memfokuskan kolom **SKU / QR lot** untuk scanner USB/Bluetooth. Kode yang
salah ditolak sebelum penyimpanan. Rincian pick menampilkan bukti scan bersama lokasi asal, staging, tanggal,
aktor, receipt, final QC, dan batch bahan. Catatan pick dari schema lama tetap tersedia dan diberi penanda bahwa
bukti scan belum diwajibkan saat catatan tersebut dibuat.

API terkait tetap `POST /api/marketplace-reservations/{reservation_id}/picks`, dengan field tambahan wajib
`scanned_code`. Schema 46 → 47 menambahkan kolom dan guard kecocokan scan. Connector runtime Jubelio/Mekari
tetap ditunda sampai akses API resmi tersedia.

Rencana: [Marketplace pick scanning plan](marketplace-pick-scanning-plan.md).
Bukti pengujian: [Marketplace pick scanning verification](marketplace-pick-scanning-verification.md).

## Verifikasi scan saat pergerakan gudang (v0.61)

Setiap transfer lokasi, pelepasan hold, dan penandaan damaged baru wajib membawa `scanned_code`
berisi SKU atau QR lot penerimaan barang jadi. Kecocokan tidak peka huruf besar/kecil setelah spasi
di tepi dibuang. Form langsung memfokuskan kolom scan dan menolak kode yang tidak sesuai sebelum
mengirim request.

Nilai scan disimpan di ledger pergerakan immutable dan global audit trail. SQLite memeriksa kembali
kode terhadap lineage penerimaan, sehingga penulisan langsung tidak dapat melewati aturan API.
Catatan lama dipertahankan dengan nilai null dan ditandai pada rincian sebagai transaksi yang dibuat
sebelum scan diwajibkan.

`POST /api/finished-goods-receipts/{id}/warehouse-movements` sekarang mewajibkan `scanned_code`.
Migrasi schema 47 → 48 menambahkan kolom dan guard secara atomik, termasuk pemulihan startup bila
kolom sudah sempat terbentuk sebelum nomor schema diperbarui. Runtime connector Jubelio/Mekari tetap
ditunda sampai akses API resmi tersedia.

Rencana: [Warehouse movement scanning plan](warehouse-movement-scanning-plan.md).
Bukti pengujian: [Warehouse movement scanning verification](warehouse-movement-scanning-verification.md).

## Jejak stok barang jadi per lot (v0.62)

Buka penerimaan barang jadi, termasuk lewat scan QR, lalu pilih **Jejak stok lengkap**. Satu layar
menampilkan posisi stok saat ini serta riwayat penerimaan, transfer/keputusan hold, reservasi,
picking, packing, pengiriman, retur, adjustment, dan stock opname. Koreksi dan pelepasan reservasi
tetap tampil terpisah dari catatan asalnya.

Setiap catatan memuat referensi, jumlah, status, alasan, pelaku, tanggal transaksi dan waktu pencatatan,
beserta tautan ke rincian. Scan pada catatan asal ditampilkan jika tersedia. Tautan batch bahan,
bundle, dan final QC menghubungkan lot dengan asal produksinya.

API: `GET /api/finished-goods-receipts/{receipt_id}/traceability?limit=100`. Respons berisi
`receipt`, `events`, `total`, dan `next_before`. Kirim pasangan `before_time` dan `before_event`
dari cursor untuk halaman berikutnya. Urutan memakai waktu pencatatan terbaru, bukan tanggal transaksi
yang dapat diisi mundur. Semua akun aktif dapat membaca; tidak ada perubahan stok, audit, atau schema.

Jumlah tiap event memiliki arti berbeda sehingga tidak boleh dijumlahkan menjadi saldo. Posisi sekarang
diambil dari ledger inventori. Riwayat disusun per lot di memori; lot dengan ribuan event belum diuji.
Runtime connector Jubelio/Mekari tetap ditunda.

Rencana: [Finished goods traceability plan](finished-goods-traceability-plan.md).
Bukti: [Finished goods traceability verification](finished-goods-traceability-verification.md).

## Jejak produksi per batch bahan (v0.63)

Buka batch bahan, termasuk lewat scan QR, lalu pilih **Jejak produksi lengkap**. Satu layar menghubungkan
penerimaan dan saldo batch dengan reservasi, pengeluaran, pemakaian/waste, cutting, bundle dan handoff,
sewing, finishing, final QC, hingga penerimaan barang jadi. Koreksi setiap tahap tetap tampil sebagai
catatan terpisah sehingga riwayat fisik dan digital tidak putus.

Setiap catatan memuat referensi, jumlah beserta satuannya, status, alasan, pelaku, tanggal transaksi,
waktu pencatatan, dan tautan ke rincian domain. Ringkasan batch menampilkan saldo available/reserved,
lokasi, pemasok, serta tautan PO dan QC penerimaan bila tersedia.

API: `GET /api/material-batches/{batch_id}/traceability?limit=100`. Respons berisi `batch`, `events`,
`total`, dan `next_before`. Halaman berikutnya memakai pasangan `before_time` dan `before_event`.
Semua akun aktif dapat membaca. Endpoint tidak mengubah stok, audit, maupun schema database.

Jumlah bahan dan output pcs tidak dijumlahkan karena satuannya berbeda. Riwayat satu batch dirakit
di memori dari ledger yang sudah ada. Cutting tetap memakai satu sumber batch per run sesuai kontrak
saat ini. Runtime connector Jubelio/Mekari tetap ditunda sampai akses API resmi tersedia.

Rencana: [Material batch traceability plan](material-batch-traceability-plan.md).
Bukti: [Material batch traceability verification](material-batch-traceability-verification.md).

## Analisis retur per SKU, ukuran, dan marketplace (v0.64)

Pilih **Analisis retur** dari navigasi utama. Tentukan akhir dan panjang periode, lalu saring berdasarkan
marketplace atau identitas produk. Laporan membentuk kohort dari shipment aktif dalam periode tersebut
dan menghitung retur aktif yang sudah diterima sampai tanggal laporan. Setiap baris mewakili satu kombinasi
SKU dan marketplace agar perbedaan channel tetap terlihat.

Alasan terstruktur tetap ditampilkan satu per satu. Ringkasan mengelompokkan terlalu kecil/besar sebagai
sinyal sizing, barang/warna tidak sesuai sebagai sinyal halaman produk, defect sebagai kualitas, dan other
sebagai alasan lain. Rate retur adalah jumlah pcs yang kembali dibagi jumlah pcs yang dikirim dalam kohort.
Shipment tanpa retur tetap muncul sebagai pembanding; catatan shipment atau retur yang sudah dikoreksi tidak
dihitung.

API: `GET /api/return-insights`. Parameter `as_of`, `window_days`, `query`, `marketplace`, `limit`, dan
`offset` tersedia. Default memakai periode 90 hari dan maksimum 365 hari. Semua akun aktif dapat membaca.
Endpoint tidak mengubah stok, audit, atau schema database; schema tetap versi 48.

Hasil hanya memakai alasan yang dipilih saat retur dicatat. Sistem belum membaca teks catatan bebas, ulasan
pelanggan, foto, isi halaman produk, atau pola fit per model. Korelasi tetap harus diperiksa tim sebelum
mengubah ukuran atau listing. Runtime connector Jubelio/Mekari tetap ditunda sampai akses API resmi tersedia.

Rencana: [Return insights plan](return-insights-plan.md).
Bukti: [Return insights verification](return-insights-verification.md).

## Analisis demand dan risiko stockout per ukuran (v0.65)

Pilih **Analisis ukuran** untuk membandingkan SKU dengan nama produk dan warna yang sama. Laporan memakai
dua periode demand neto, formula forecast 70% periode terbaru dan 30% periode sebelumnya, serta stok tersedia
saat ini. Days of cover menentukan ukuran yang diproyeksikan habis lebih dulu dan apakah tanggalnya berada
dalam horizon risiko yang dipilih.

Label **Pemimpin demand konsisten** hanya muncul ketika satu ukuran berada di peringkat demand pertama pada
kedua periode dan mempunyai demand positif. Pencarian satu SKU tetap menampilkan seluruh keluarga ukurannya.
Filter marketplace membatasi sumber demand, sedangkan stok selalu memakai seluruh inventori internal saat
laporan dimuat. Keluarga dengan kurang dari dua ukuran terisi dan berbeda tidak ditampilkan karena tidak
mempunyai pembanding.

API: `GET /api/size-demand-insights`. Parameter `as_of`, `window_days`, `lookahead_days`, `query`,
`marketplace`, `limit`, dan `offset` tersedia. Default memakai dua window 28 hari dan horizon risiko 30 hari.
Semua akun aktif dapat membaca. Endpoint tidak mengubah stok, audit, atau schema database; schema tetap 48.

Produk dikelompokkan memakai nama dan warna karena master keluarga produk terpisah belum tersedia. Proyeksi
memakai posisi stok sekarang, bukan rekonstruksi snapshot historis. Karena itu laporan menunjukkan risiko
habis lebih dulu dan pola demand berulang, bukan bukti bahwa stockout benar-benar terjadi pada masa lalu.
Promosi, musiman, lead time per SKU, transfer channel, dan runtime connector Jubelio/Mekari belum masuk.

Rencana: [Size demand insights plan](size-demand-insights-plan.md).
Bukti: [Size demand insights verification](size-demand-insights-verification.md).

## Analisis dead stock (v0.66)

Pilih **Dead stock** untuk mencari stok sellable yang masih tersedia tetapi tidak bergerak. Satu SKU menjadi
kandidat ketika umur lot tersedia tertuanya sudah mencapai ambang hari yang dipilih dan demand netonya nol
dalam periode yang sama. Retur aktif mengurangi demand shipment asal; shipment dan retur yang sudah dikoreksi
tidak dihitung.

Laporan juga membedakan **Stok baru tanpa penjualan** yang belum mencapai ambang umur dan **Masih bergerak**
yang mempunyai demand neto positif. Setiap SKU menampilkan jumlah tersedia, jumlah lot aktif, umur lot tertua,
shipment, retur, demand neto, rate, days of cover, dan tanggal penjualan neto terakhir. Reserved stock tidak
masuk jumlah tersedia.

API: `GET /api/dead-stock-insights`. Parameter `as_of`, `inactivity_days`, `query`, `marketplace`, `status`,
`limit`, dan `offset` tersedia. Default ambang 90 hari dan status kandidat dead stock. Filter marketplace hanya
membatasi histori demand; posisi stok tetap berasal dari seluruh inventori internal saat laporan dimuat.
Semua akun aktif dapat membaca. Endpoint tidak mengubah stok, audit, atau schema; schema tetap 48.

Stok memakai posisi saat ini dan tidak direkonstruksi pada tanggal historis `as_of`. Nilai rupiah belum
ditampilkan karena valuasi stok per lot belum tersedia. Umur stok memakai receipt aktif tertua yang masih
mempunyai saldo available; keputusan diskon, bundling, transfer, atau write-off tetap diperiksa manusia.
Runtime connector Jubelio/Mekari tetap ditunda sampai akses API resmi tersedia.

Rencana: [Dead stock insights plan](dead-stock-insights-plan.md).
Bukti: [Dead stock insights verification](dead-stock-insights-verification.md).

## Audit adjustment stok (v0.67)

Pilih **Audit adjustment** untuk memeriksa adjustment barang jadi dalam periode tertentu. Laporan menandai
catatan bila jumlah absolut melewati ambang, porsinya terhadap jumlah penerimaan melewati ambang, adjustment
berulang pada SKU, lokasi, dan status stok yang sama, atau catatannya sudah dikoreksi.

Klasifikasi **Risiko tinggi** berarti jumlah atau porsi penerimaan melewati ambang. **Perlu tinjauan** berarti
ada pengulangan atau koreksi tanpa sinyal kuantitas besar. **Normal** berarti tidak ada sinyal yang melewati
ambang. Pengguna dapat mengatur ambang jumlah, persentase, dan pengulangan; lalu memfilter referensi/SKU,
lokasi, status stok, sumber manual atau stock opname, status aktif atau dikoreksi, dan klasifikasi.

Setiap hasil menunjukkan kuantitas bertanda, porsi penerimaan, jumlah dan volume absolut pada bucket yang sama,
sumber, status koreksi, tanggal, pencatat, alasan flag, serta tautan ke adjustment asal. Ringkasan tidak menebak
nilai rupiah dan tidak mengubah stok. Koreksi memakai status ledger saat laporan dimuat, sedangkan periode memakai
tanggal bisnis adjustment.

API: `GET /api/stock-adjustment-insights`. Semua akun aktif dapat membaca. Endpoint bersifat read-only dan
schema tetap 48. Runtime connector Jubelio/Mekari tetap ditunda sampai akses API resmi tersedia.

Rencana: [Stock adjustment insights plan](stock-adjustment-insights-plan.md).
Bukti: [Stock adjustment insights verification](stock-adjustment-insights-verification.md).

## Kinerja supplier (v0.68)

Pilih **Kinerja supplier** untuk melihat PO yang tanggal perkiraan datangnya berada dalam periode laporan.
Supplier ditandai perlu perhatian bila ada PO terlambat tanpa kedatangan aktif, kedatangan pertama terlambat,
PO lewat jadwal yang belum lengkap, PO ditutup dengan kekurangan, bahan reject, atau bahan yang masih hold.

Ketepatan datang memakai tanggal kedatangan aktif pertama dibandingkan `expected_date` PO. Receipt yang sudah
dikoreksi dan kedatangan QC yang dibatalkan tidak dihitung. Status pemenuhan PO serta hasil QC memakai posisi
ledger saat laporan dimuat. Kuantitas pesanan, penerimaan layak pakai, dan QC selalu dipisahkan per satuan bahan;
meter, kilogram, dan pcs tidak dijumlahkan menjadi satu angka.

Setiap supplier menampilkan jumlah PO, kedatangan tepat waktu/terlambat, PO terlambat tanpa kedatangan,
kekurangan, volume per satuan, usable/reject/hold per satuan, alasan sinyal, dan daftar PO untuk drill-down.
Filter tersedia untuk tanggal akhir, periode 7–730 hari, status supplier, kode/nama supplier, dan referensi PO.

API: `GET /api/supplier-performance-insights`. Semua akun aktif dapat membaca. Endpoint bersifat read-only,
schema tetap 48, dan tidak menulis penilaian permanen terhadap supplier. Runtime connector Jubelio/Mekari tetap
ditunda sampai akses API resmi tersedia.

Rencana: [Supplier performance insights plan](supplier-performance-insights-plan.md).
Bukti: [Supplier performance insights verification](supplier-performance-insights-verification.md).

## Pergerakan harga bahan (v0.69)

Pilih **Harga bahan** untuk membandingkan harga unit pada PO approved selama periode 7–730 hari. Setiap tren
dibentuk dari pasangan material dan supplier yang sama sehingga pergantian supplier tidak keliru dibaca sebagai
kenaikan atau penurunan harga. PO pending, ditolak, dan dibatalkan tidak masuk perhitungan.

Harga awal dan terbaru mengikuti tanggal PO dicatat, bukan `expected_date`. Setiap hasil menunjukkan perubahan
nominal dan persentase, harga minimum, maksimum, rata-rata, serta riwayat PO terbaru lebih dulu. Pasangan yang
baru mempunyai satu harga diberi status terpisah karena belum memiliki pembanding.

Filter tersedia untuk tanggal akhir, periode pencatatan, status naik/turun/tetap/satu harga, material, supplier,
dan referensi PO. Setiap observasi menyediakan tautan ke rincian PO asal.

API: `GET /api/material-price-insights`. Semua akun aktif dapat membaca. Endpoint bersifat read-only, mata uang
IDR, schema tetap 48, dan tidak mengubah harga PO atau master bahan. Runtime connector Jubelio/Mekari tetap
ditunda sampai akses API resmi tersedia.

Rencana: [Material price insights plan](material-price-insights-plan.md).
Bukti: [Material price insights verification](material-price-insights-verification.md).

## Komitmen pembelian terbuka (v0.70)

Pilih **Komitmen PO** untuk melihat nilai PO approved aktif yang belum menjadi penerimaan bahan layak pakai.
Setiap PO diklasifikasikan sebagai terlambat, segera jatuh tempo, terjadwal, atau sudah diterima lengkap tetapi
belum ditutup. PO pending, ditolak, dibatalkan, dan ditutup tidak masuk laporan.

Nilai PO, penerimaan layak pakai, dan komitmen terbuka ditampilkan bersama posisi pengajuan pembayaran supplier.
Payment menunggu approval, payment approved, dan nilai penerimaan yang belum diajukan dipisahkan karena approval
belum membuktikan transfer bank. Rincian bahan mempertahankan satuan masing-masing dan menyediakan tautan ke PO.

Filter tersedia untuk tanggal posisi, batas segera jatuh tempo 1–90 hari, status jadwal, PO, PR, supplier, dan
material. Perhitungan memakai posisi ledger saat laporan dimuat; `as_of` membatasi tanggal pembuatan PO di Jakarta dan
menentukan status jadwal, bukan merekonstruksi status historis.

API: `GET /api/purchase-commitment-insights`. Semua akun aktif dapat membaca. Endpoint bersifat read-only,
mata uang IDR, dan schema tetap 48. Runtime connector Jubelio/Mekari tetap ditunda sampai akses API resmi
tersedia.

Rencana: [Purchase commitment insights plan](purchase-commitment-insights-plan.md).
Bukti: [Purchase commitment insights verification](purchase-commitment-insights-verification.md).

## WIP ageing dan sinyal hambatan (v0.71)

Pilih **WIP ageing** untuk melihat seluruh kuantitas produksi aktif menurut tahap, lama sejak aktivitas produksi
terakhir, order yang melewati tenggat, kendala terbuka, dan rework. Umur dihitung dari movement produksi terbaru
per order; order yang belum pernah bergerak memakai tanggal pembuatannya.

Filter tersedia untuk tanggal posisi, batas tidak bergerak 1–365 hari, status perhatian, tahap aktif, PIC, order,
SKU, produk, dan isi kendala. Ringkasan tahap menunjukkan kuantitas aktif serta kuantitas pada order yang tidak
bergerak. Tahap dengan kuantitas stalled terbesar disebut sinyal hambatan agar tim tahu area yang perlu diperiksa.

Laporan memakai saldo ledger saat request dimuat. `as_of` menentukan umur dan status tenggat serta mengecualikan
order yang dibuat sesudah tanggal tersebut; laporan tidak merekonstruksi posisi historis. Sinyal hambatan tetap
bukan ukuran kapasitas; perhitungan kapasitas berbasis master waktu tersedia pada laporan berikutnya.

API: `GET /api/wip-ageing-insights`. Semua akun aktif dapat membaca. Endpoint bersifat read-only dan schema tetap
48. Runtime connector Jubelio/Mekari tetap ditunda sampai akses API resmi tersedia.

Rencana: [WIP ageing insights plan](wip-ageing-insights-plan.md).
Bukti: [WIP ageing insights verification](wip-ageing-insights-verification.md).

## Perencanaan kapasitas produksi (v0.72)

Pilih **Kapasitas produksi** untuk membandingkan kebutuhan menit dari WIP aktif dengan kapasitas work center.
Admin lebih dulu membuat work center per tahap, mengisi standar menit per pcs untuk tiap SKU dan tahap, lalu
mencatat override kalender untuk libur atau lembur. Senin sampai Jumat memakai kapasitas harian work center;
Sabtu dan Minggu bernilai nol sampai diberi override.

Rute tersisa dihitung dari posisi pcs saat ini sampai QC. Work center diklasifikasikan sebagai overload, risiko
deadline, mendekati kapasitas, masih tersedia, atau tanpa beban. Risiko deadline membandingkan kebutuhan order
secara kumulatif dengan kapasitas yang tersedia sampai target masing-masing. Gap standar atau work center nonaktif
ditampilkan agar planner tidak menganggap laporan yang belum lengkap sebagai kapasitas yang aman.

Filter tersedia untuk tanggal awal, horizon 1–90 hari, batas peringatan utilisasi, status, tahap, dan work center.
Semua akun aktif dapat membaca laporan; perubahan master hanya untuk admin. Laporan memakai saldo ledger saat
request dan tidak merekonstruksi WIP historis atau membuat jadwal kerja per jam.

API: `GET /api/capacity-plan`, `GET/POST /api/work-centers`, `POST /api/work-centers/{id}/changes`,
`GET /api/routing-standards`, `GET/POST /api/products/{product_id}/routing-standards/{stage}`, dan
`GET/POST /api/work-centers/{id}/calendar`. Schema database 49. Runtime connector Jubelio/Mekari tetap ditunda
sampai akses API resmi tersedia.

Rencana: [Production capacity plan](production-capacity-plan.md).
Bukti: [Production capacity verification](production-capacity-verification.md).

## Tren kualitas produksi dan vendor (v0.73)

Pilih **Kualitas produksi** untuk membandingkan hasil final QC per line internal atau vendor makloon dengan
periode sebelumnya yang sama panjang. Laporan menghitung first-pass yield serta persentase rework dan reject dari
catatan final QC aktif. Catatan yang sudah dikoreksi tidak ikut dihitung.

Penanggung jawab berstatus perlu perhatian ketika persentase gabungan rework dan reject mencapai batas atau
naik melewati ambang perubahan. Setiap hasil menyertakan jenis defect, sumber penanggung jawab, SKU, dan lima
catatan final QC terbaru untuk drill-down. Filter tersedia untuk tanggal akhir, panjang periode 7–365 hari,
batas kualitas, ambang perubahan, jenis pengerjaan, status, serta pencarian vendor, line, SKU, order, dan defect.

API: `GET /api/production-quality-insights`. Semua akun aktif dapat membaca dan endpoint bersifat read-only.
Schema database tetap 49. Runtime connector Jubelio/Mekari tetap ditunda sampai akses API resmi tersedia.

Rencana: [Production quality insights plan](production-quality-insights-plan.md).
Bukti: [Production quality insights verification](production-quality-insights-verification.md).

## Alert kualitas di Command Center (v0.74)

Command Center sekarang menghitung ringkasan kualitas dari final QC aktif selama 30 hari terakhir. Snapshot
**Kualitas produksi** menampilkan jumlah pcs diperiksa, first-pass yield, persentase rework + reject, dan jumlah
line/vendor yang perlu perhatian.

Jika suatu line internal atau vendor makloon mencapai 5% rework + reject atau memburuk setidaknya 1 poin dari
periode 30 hari sebelumnya, line/vendor dengan risiko tertinggi masuk antrean **Perlu perhatian**. Alert memuat
angka dan basis perbandingan serta membuka layar **Kualitas produksi** untuk melihat defect, sumber, SKU, dan
final QC terkait. Catatan final QC yang sudah dikoreksi tetap dikeluarkan.

Perubahan ini memperkaya respons `GET /api/command-center` dan tidak menambah endpoint atau tabel. Schema tetap
49. Runtime connector Jubelio/Mekari tetap ditunda sampai akses API resmi tersedia.

Rencana: [Command Center quality alerts plan](command-center-quality-alerts-plan.md).
Bukti: [Command Center quality alerts verification](command-center-quality-alerts-verification.md).

## Alert kapasitas di Command Center (v0.75)

Command Center sekarang menghitung rencana kapasitas 14 hari dari saldo WIP, standar routing SKU, kapasitas harian
work center, dan override kalender. Snapshot **Kapasitas produksi** menampilkan total beban dan menit tersedia,
jumlah work center yang perlu perhatian, order berisiko, serta kelengkapan standar.

Overload atau risiko kapasitas sebelum deadline menjadi alert kritis. Utilisasi minimal 80% menjadi alert
perhatian jika belum ada risiko yang lebih tinggi. Gap standar atau work center nonaktif menjadi alert data agar
kapasitas nol tidak dianggap aman. Tombol alert dan kartu membuka **Kapasitas produksi** untuk melihat work center,
kalender, order, dan SKU penyebab beban.

Perubahan ini memperkaya respons `GET /api/command-center` dan tidak menambah endpoint atau tabel. Schema tetap
49. Runtime connector Jubelio/Mekari tetap ditunda sampai akses API resmi tersedia.

Rencana: [Command Center capacity alerts plan](command-center-capacity-alerts-plan.md).
Bukti: [Command Center capacity alerts verification](command-center-capacity-alerts-verification.md).

## Fondasi People dan kehadiran (v0.76)

Employee master lokal menyimpan kode karyawan tetap, nama, departemen, status aktif, alasan perubahan, aktor, dan
revisi. Admin membuat atau mengubah data karyawan. Semua perubahan bersifat append-only dan benturan edit ditolak
dengan `expected_revision`.

Admin dan operator dapat mencatat satu status per karyawan per hari melalui
`POST /api/workforce/employees/{employee_id}/attendance`: hadir dengan jam masuk/pulang dan menit lembur, atau
cuti/absen tanpa jam kerja. Koreksi menambah revisi baru pada catatan yang sama. `GET /api/workforce/attendance`
menyediakan filter tanggal, status, karyawan, departemen, pencarian, pagination, serta ringkasan jumlah orang,
status, menit kerja, dan menit lembur. Endpoint history employee dan attendance membuka jejak revisinya.

Schema 50 menambah empat tabel immutable. Employee master masuk kategori audit `master_data`; attendance masuk
`production`. Data gaji, pajak, rekening, dan perhitungan payroll tidak disimpan di modul ini. Payroll agregat
tetap mengikuti snapshot Mekari, dan runtime connector Mekari/Jubelio tetap ditunda sampai API resmi tersedia.

Rencana: [Workforce foundation plan](workforce-foundation-plan.md).
Bukti: [Workforce foundation verification](workforce-foundation-verification.md).

## Layar People (v0.77)

Buka **People** untuk melihat roster karyawan aktif per tanggal. Karyawan yang belum memiliki catatan tetap muncul
dengan status **Belum dicatat**, sehingga lubang pencatatan terlihat tanpa membandingkan dua laporan. Ringkasan
menampilkan karyawan aktif, belum dicatat, hadir, cuti, absen, dan total menit lembur dari data pada filter.

Admin dapat membuat, mengubah, menonaktifkan, dan melihat riwayat employee master. Admin dan operator dapat
mencatat hadir dengan jam masuk/pulang serta lembur, atau cuti/absen tanpa jam kerja. Koreksi menambah revisi baru
dan riwayat menampilkan alasan, pelaku, serta waktu setiap revisi. Viewer dapat membaca roster, master, dan riwayat
tanpa tombol perubahan. Filter status dan pencarian diproses dari data API; layar tidak membuat status perkiraan.

UI memakai endpoint People v0.76 dan tidak mengubah schema 50. Roster shift, jenis cuti rinci, approval cuti/lembur,
data gaji per karyawan, serta runtime connector Mekari/Jubelio tetap belum dicakup.

Rencana: [People UI plan](workforce-ui-plan.md).
Bukti: [People UI verification](workforce-ui-verification.md).

## Alert People di Command Center (v0.78)

Command Center sekarang memuat snapshot roster tanggal Jakarta: jumlah karyawan aktif, sudah dan belum dicatat,
hadir, cuti, absen, menit kerja, serta menit lembur. Catatan kehadiran karyawan nonaktif tetap tersimpan dalam
riwayat tetapi tidak dihitung sebagai cakupan roster aktif.

Jika seluruh karyawan aktif belum dicatat, alert **Kehadiran belum lengkap** bersifat kritis. Jika hanya sebagian
yang belum dicatat, alert menjadi perhatian. Status absen menghasilkan alert terpisah; lembur tetap ditampilkan
sebagai fakta tanpa threshold buatan. Tombol pada alert dan kartu snapshot membuka roster People hari yang sama
dengan filter bersih, termasuk ketika pengguna sebelumnya membuka tanggal atau status lain.

Perubahan ini memperkaya `GET /api/command-center` tanpa menambah endpoint atau tabel. Schema tetap 50. Runtime
connector Jubelio/Mekari tetap ditunda sampai API resmi tersedia.

Rencana: [Command Center People alerts plan](command-center-workforce-alerts-plan.md).
Bukti: [Command Center People alerts verification](command-center-workforce-alerts-verification.md).

## Approval cuti dan lembur (v0.79)

Layar People sekarang memiliki daftar permintaan cuti dan lembur. Admin dan operator dapat mengajukan untuk
karyawan aktif; admin menyetujui atau menolak, sedangkan pemohon operator dapat membatalkan permintaannya sendiri
selama masih menunggu. Cuti mendukung rentang maksimal 366 hari dan lembur menyimpan tanggal serta menit yang
diminta. Permintaan aktif yang tanggalnya bertumpang tindih ditolak.

Setiap pengajuan dan keputusan tersimpan sebagai ledger immutable dengan idempotency key, revision guard, aktor,
alasan, dan waktu. Cuti dan lembur masuk ke unified approval inbox sebagai jenis People tersendiri serta ikut dalam
jumlah keputusan di Command Center. Approval tidak otomatis mencatat kehadiran karena izin dan kejadian aktual
memiliki sumber data yang berbeda.

Schema 50 → 51 menambahkan permintaan dan event keputusan People. Saldo cuti, jenis cuti rinci, roster shift,
payroll per karyawan, dan runtime connector Jubelio/Mekari tetap ditunda.

Rencana: [Workforce approvals plan](workforce-approvals-plan.md).
Bukti: [Workforce approvals verification](workforce-approvals-verification.md).

## Approval batch payroll Mekari (v0.80)

Periode payroll berstatus **Ditinjau** pada snapshot Mekari terbaru sekarang dapat diajukan ke approval manajemen.
Kartu periode membedakan status sumber Mekari dari keputusan Beeloft. Admin/operator dapat mengajukan, admin
menyetujui atau menolak, dan operator pemohon dapat membatalkan pengajuannya sendiri selama masih menunggu.

Permintaan masuk ke unified approval inbox dengan periode, jumlah karyawan, gaji neto, dan total biaya perusahaan.
Jika snapshot baru menghapus periode atau mengubah status, tanggal, jumlah karyawan, nilai, atau waktu pembaruannya,
permintaan lama ditandai stale dan tidak dapat disetujui. Penolakan atau pembatalan tetap dapat menutup permintaan
lama agar periode terbaru dapat diajukan.

Request dan riwayat keputusan tersimpan sebagai ledger immutable dengan idempotency key, revision guard, aktor,
alasan, dan waktu. Schema 51 → 52 menambahkan ledger approval payroll. Keputusan Beeloft tidak mengubah status
Mekari, menghitung payroll, menjalankan pembayaran, atau membuat jurnal. Runtime connector Mekari tetap ditunda.

Rencana: [Payroll approvals plan](payroll-approvals-plan.md).
Bukti: [Payroll approvals verification](payroll-approvals-verification.md).

## Rekonsiliasi pembayaran payroll (v0.81)

Pilih **Integrasi → Pembayaran payroll** untuk mencocokkan approval batch payroll terbaru dengan snapshot Mekari
terbaru. Batch approved dibedakan menjadi **Menunggu pembayaran**, **Sudah dibayar**, atau **Perlu perhatian**.
Pembayaran hanya dinyatakan selesai ketika Mekari melaporkan status `paid` dan tanggal pembayaran.

Rekonsiliasi membandingkan periode, mata uang, jumlah karyawan, gaji bruto, potongan karyawan, dan kontribusi
perusahaan terhadap konteks yang disetujui. Periode yang hilang, nominal/konteks yang berubah, payroll yang
dibatalkan, atau status yang kembali draft menjadi exception. Jika ada pengajuan yang lebih baru untuk ID payroll
yang sama, keputusan terbaru menggantikan approval lama sebagai dasar rekonsiliasi.

Ringkasan menampilkan jumlah batch approved, menunggu, dibayar, exception, total gaji neto approved, dan total
gaji neto yang sudah dilaporkan dibayar. Filter status, pencarian approval/ID payroll, pagination, dan drill-down
ke audit approval tersedia untuk semua akun aktif. Endpoint ini read-only, schema tetap 52, serta tidak mengirim
uang, mengubah Mekari, menyimpan rekening/gaji per karyawan, atau membuat jurnal. Runtime connector Mekari tetap
ditunda.

API: `GET /api/payroll-payment-reconciliation`.

Rencana: [Payroll payment reconciliation plan](payroll-payment-reconciliation-plan.md).
Bukti: [Payroll payment reconciliation verification](payroll-payment-reconciliation-verification.md).

## Rekonsiliasi akuntansi payroll (v0.82)

Pilih **Integrasi → Akuntansi payroll** untuk mencocokkan batch payroll approved dengan pembayaran dan metadata
jurnal pada snapshot Mekari terbaru. Status dibedakan menjadi **Menunggu pembayaran**, **Menunggu posting**,
**Sudah diposting**, atau **Perlu perhatian**.

Snapshot payroll dapat membawa status jurnal `draft`, `posted`, atau `reversed`, referensi jurnal, tanggal posting,
total debit/kredit, dan waktu pembaruan. Rekonsiliasi menandai periode sumber yang hilang atau berubah, payroll
yang belum dibayar, jurnal yang belum diposting, jurnal reversed, debit/kredit tidak seimbang, serta nilai jurnal
yang berbeda dari total biaya perusahaan yang disetujui. Nilai uang dibandingkan sebagai exact decimal.

Ringkasan, filter status, pencarian approval/ID payroll/referensi jurnal, pagination, dan drill-down approval dapat
dibaca semua akun aktif. Schema 52 → 53 menyimpan satu metadata jurnal agregat immutable per periode snapshot.
Endpoint ini tidak memanggil Mekari, membuat chart of accounts, mem-posting jurnal, atau menyimpan baris jurnal dan
data payroll per karyawan. Runtime connector Mekari tetap ditunda sampai API resmi tersedia.

API: `GET /api/payroll-accounting-reconciliation`.

Rencana: [Payroll accounting reconciliation plan](payroll-accounting-reconciliation-plan.md).
Bukti: [Payroll accounting reconciliation verification](payroll-accounting-reconciliation-verification.md).


## Stabilisasi keamanan dan transaksi (v0.83)

Rilis stabilisasi tanpa fitur produk baru dan tanpa connector vendor.

Dependensi Starlette dinaikkan dari `0.52.1` ke `1.6.0`, dengan batas deklaratif
`starlette>=1.3.1,<2` dan `fastapi>=0.134,<1`. Rilis di bawah 1.3.1 terkena setidaknya satu dari
CVE-2026-48710 (BadHost, host header meracuni `request.url.path`), CVE-2026-48818 (SSRF dan kebocoran
NTLMv2 lewat UNC path pada `StaticFiles` di Windows), CVE-2026-48817 (metode HTTP arbitrer ke
`HTTPEndpoint`), CVE-2026-54282 (authority poisoning), dan CVE-2026-54283 (limit `request.form()`
diabaikan). Aplikasi ini memang memakai `StaticFiles` pada `/static`. Regresi UNC path diuji tanpa
bergantung pada Windows dan tanpa request SMB nyata: penolakan harus terjadi sebelum `realpath`,
`abspath`, atau `stat` dipanggil.

Retry pencatatan yang belum pasti tidak lagi dapat diselesaikan oleh akun lain. Sebelumnya receipt
idempotency memakai primary key `(actor_id, key)` dan dicari dengan `WHERE actor_id=? AND key=?`,
sehingga tab yang masih menyimpan draft akun A dapat mengirim retry memakai session akun B, tidak
menemukan receipt, dan menjalankan mutasi bisnis untuk kedua kalinya dengan atribusi akun B. Cookie
session dipakai bersama seluruh tab sedangkan draft pending bersifat per tab, jadi tab lama tidak
pernah diberi tahu bahwa akunnya sudah berganti.

Sekarang satu idempotency key mengikat satu transaksi logis pada seluruh database. `Store._write()`
mencari receipt per key, menolak 403 bila pemiliknya berbeda, tetap menolak 409 untuk payload berbeda,
dan tetap mengembalikan respons pertama secara byte-identical untuk akun pencatat asli. Akun nonaktif
tetap ditolak 401 lebih dahulu dan penurunan role tetap menolak replay. Atribusi audit tidak berubah:
replay tidak menambah event, dan tidak ada event yang berpindah akun.

403 dipilih, bukan 409, karena klien sudah memperlakukan 401/403 sebagai penolakan yang
mempertahankan draft dan menampilkan tombol Masuk ulang. Sisi klien menyimpan `actor_id` di dalam
draft pending dan memeriksa identitas server sebelum mengirim retry, tetapi penegakan invarian tetap
di server.

Kepemilikan key hanya menolong bila key-nya sudah pernah dipakai, sehingga submit **pertama** sebuah
form masih dapat berjalan di bawah session yang sudah berganti: key masih baru dan server melihat
request yang sah dari akun yang sedang memegang cookie bersama. Kondisi itu direproduksi dan memang
menghasilkan mutasi beserta event audit dengan atribusi akun yang salah, baik pada perpindahan
produksi maupun pada penyimpanan investigasi AI. Karena itu setiap pencatatan dari dashboard sekarang
menyatakan akun penyusunnya melalui header `X-Beeloft-Actor`, dan server memverifikasinya pada
dependency `actor()` lalu menolak 403 sebelum handler mana pun berjalan. Penolakan tidak meninggalkan
mutasi, event audit, maupun receipt, jadi key yang sama masih dapat dipakai oleh akun yang sah.

Header itu tidak pernah memberi akses; nilainya hanya dapat menolak request. Login dan logout dikirim
tanpa idempotency key sehingga tidak pernah membawa binding, dan tombol Masuk ulang tetap dapat keluar
dari session milik akun lain. Klien API key yang tidak mengirim header tidak berubah perilakunya.

Migrasi 53 → 54 menjadikan `requests.key` primary key tunggal. Receipt paling awal per key
dipertahankan sebagai pemilik, receipt duplikat historis diarsipkan immutable di
`request_key_conflicts` beserta waktu deteksi, sehingga jejak database yang pernah terkena bug ini
tidak hilang. Insert kedua dengan key sama kini melanggar constraint dan menjadi 409 walau pemeriksaan
di Python suatu saat hilang.

Rencana: [security transaction P1 plan](security-transaction-p1-plan.md).
Bukti: [security transaction P1 verification](security-transaction-p1-verification.md).


## Selesai rework dan inspeksi ulang final QC (v0.84)

Temuan audit P1: pcs yang dikirim final QC ke rework dapat dikembalikan ke QC, tetapi tidak dapat
diinspeksi ulang secara sah. Pengembaliannya hanya berupa perpindahan generik `rework -> qc` tanpa
lineage, sedangkan alokasi final QC dihitung terhadap `finishing_records.quantity` yang sudah habis
dipakai inspeksi awal. Inspeksi kedua atas pcs yang secara fisik berada di QC selalu ditolak 409 oleh
guard Python maupun trigger `final_qc_source_valid`, sehingga pcs itu terjebak permanen.

Perbaikan tidak melonggarkan `qc_remaining_quantity`. Entitas immutable baru `rework_completions`
mencatat setiap pengembalian rework ke QC beserta catatan final QC penghasil rework tersebut, dan
memiliki satu perpindahan `rework -> qc` sendiri. `final_qc_records` mendapat `rework_completion_id`
(NULL untuk inspeksi awal) dan `inspection_round`, sehingga sebuah catatan final QC menyatakan dirinya
inspeksi awal dari finishing atau inspeksi ulang dari catatan selesai rework tertentu.
`finishing_record_id` tetap ada pada inspeksi ulang, jadi seluruh join lineage yang sudah dipakai
hydrator final QC, trigger SKU barang jadi, biaya produksi, margin kontribusi, dan enam file `.sql`
lain tidak berubah.

Alokasi kini punya denominator yang benar di setiap lapis: inspeksi awal hanya boleh memakai jumlah
finishing yang belum diperiksa dan inspeksi ulang tidak memakainya lagi; selesai rework tidak boleh
melebihi rework aktif dari catatan sumbernya; inspeksi ulang tidak boleh melebihi jumlah yang
dikembalikan catatan selesai rework-nya. Tidak ada batas satu siklus, sehingga rantai QC1 → selesai
rework → QC2 → selesai rework → QC3 legal. Accepted dari inspeksi ulang diterima menjadi barang jadi
lewat endpoint dan aturan yang sama seperti inspeksi awal. Tanggal selesai rework tidak boleh mendahului
inspeksi sumbernya dan tanggal inspeksi ulang tidak boleh mendahului selesai rework-nya.

Koreksi dibongkar dari hilir ke hulu, ditegakkan ganda oleh trigger dan Python: selesai rework aktif
memblokir koreksi final QC sumbernya, inspeksi ulang aktif memblokir koreksi selesai rework-nya, dan
perpindahan milik catatan selesai rework tidak dapat dibalik terpisah. Tidak ada baris ledger yang
diubah atau dihapus; koreksi hanya menambah baris pembalik.

`("qc","rework")` dan `("rework","qc")` dihapus dari `TRANSITIONS`, sehingga `POST /api/movements`
menolak 422, `GET /api/stages` tidak lagi mengiklankannya, dan form "Catat perpindahan" tidak menawarkan
keputusan atau pengembalian rework tanpa lineage. Keputusan baru dicatat melalui Final QC. Pembalikan
tidak memakai `TRANSITIONS`, jadi koreksi perpindahan `qc -> rework` yang sudah ada tetap berjalan.
Baris `rework -> qc` historis tetap terbaca lengkap dengan lineage kosong.

`production_quality_insights` mempertahankan arti `first_pass_yield_percent` dengan populasi inspeksi
awal saja, karena satu pcs fisik tidak boleh masuk populasi `accepted / inspected` dua kali. Seluruh
field lama, breakdown defect/sumber/SKU, dan field `previous_*` tidak berubah nilainya. Hasil inspeksi
ulang ditambahkan sebagai `reinspection_record_count`, `reinspected_quantity`,
`reinspection_accepted_quantity`, `reinspection_rework_quantity`, `reinspection_reject_quantity`,
`reinspection_nonconforming_quantity`, dan `reinspection_nonconforming_rate_percent`, dengan kontrak
`first_pass_yield_basis: "initial_inspections_only"`. Agar barang yang gagal lagi setelah rework tidak
terlihat sehat, ditambahkan alasan perhatian `reinspection_above_warning` yang memakai denominator
inspeksi ulang sendiri, dan command center mengekspor angka inspeksi ulang beserta satu kalimat pada
kartu perhatian kualitas.

Database schema 54 dapat memuat perpindahan `rework -> qc` lama tanpa lineage. Migrasi tidak menebak
inspeksi sumbernya. Keadaan itu dilaporkan apa adanya lewat `untraced_rework_return_quantity` dan
`rework_completable_quantity`, tombol selesai rework disembunyikan dengan penjelasan, dan API menjawab
409 yang menunjuk riwayat perpindahan order. Remediasinya adalah koreksi perpindahan lama oleh admin,
setelah itu selesai rework dan inspeksi ulang tercatat normal.

Dashboard tidak lagi memakai "Catat perpindahan" untuk alur ini. Dari final QC dengan rework tersisa
tersedia **Catat selesai rework**, lalu dari catatan selesai rework tersedia **Inspeksi ulang**.
Riwayat final QC membedakan **Inspeksi awal**, **Inspeksi ulang #1**, **Inspeksi ulang #2**, dan
tampilan rincian menautkan catatan selesai rework serta inspeksi sebelumnya. Tampilan order mendapat
tombol **Selesai rework**, dan baris yang sisa saldonya berada di rework diarahkan ke alur ini alih-alih
ke pembalikan. Viewer tetap read-only. Barang yang tidak dapat diperbaiki dibuang dengan mencatat selesai
rework lalu mengisi jumlah reject pada inspeksi ulang, sehingga pembuangan punya catatan inspeksi.

Migrasi 54 → 55 menambahkan `rework_completions`, `rework_completion_reversals`, dua kolom pada
`final_qc_records`, empat trigger invarian, empat trigger immutability, dan penulisan ulang
`final_qc_source_valid` agar memvalidasi kedua jenis inspeksi.

API: `POST`/`GET /api/final-qc-records/{id}/rework-completions`,
`GET /api/orders/{id}/rework-completions`, `GET /api/rework-completions/{id}`,
`POST /api/rework-completions/{id}/qc-records`, `POST /api/rework-completions/{id}/reverse`.

Rencana: [QC rework reinspection plan](qc-rework-reinspection-plan.md).
Bukti: [QC rework reinspection verification](qc-rework-reinspection-verification.md).


## Perbaikan audit P2: kegagalan logout dan total approval (v0.85)

Rilis perbaikan tanpa fitur produk baru, tanpa connector vendor, dan tanpa perubahan schema. Schema
database tetap 55.

Logout tidak lagi menyamarkan kegagalan sebagai layar login. Sebelumnya `logout()` menelan setiap
kegagalan dengan `catch{}` lalu selalu memanggil `clearWorkspace()` pada blok `finally`. Cookie
`beeloft_session` hanya dihapus pada jalur sukses dan baris `browser_sessions` tidak pernah dicabut,
sehingga `restoreSession()` pada reload membuka kembali akun sebelumnya. Sekarang hanya 200 dan 401 yang
diterima sebagai bukti bahwa session sudah tidak aktif; CSRF 403, 5xx, timeout, dan kegagalan jaringan
memicu pemeriksaan langsung ke `/api/me`. Pemeriksaan itu mempertahankan identitas yang menjawab, bukan
sekadar fakta bahwa server menjawab: cookie session dipakai bersama seluruh tab, jadi ruang kerja lama
hanya dipertahankan bila session masih milik akun yang membukanya. Bila session sudah berpindah ke akun
lain dan masih aktif, ruang kerja lama dibongkar supaya tidak ada tampilan bercampur identitas, dan
peringatannya menyebut akun yang sekarang memegang session. Ruang kerja yang dipertahankan diberi banner
`#session-warning` beserta tombol **Coba keluar lagi**, dan pesannya membedakan "logout belum berhasil
dengan akun yang sama", "session sudah berpindah akun", dan "logout belum terkonfirmasi" tanpa pernah
menjanjikan session sudah dicabut ketika browser offline. Server yang sudah
mencabut lalu kehilangan responsnya tetap dikenali, jadi tidak ada jalan buntu permanen. Klik ganda
memakai ulang satu promise dalam penerbangan; `aria-busy`, `inert`, dan `disabled` dipulihkan di seluruh
jalur. Tombol **Masuk ulang** pada dialog transaksi pending melaporkan kegagalan ke `#form-error` atau
`#ai-message` karena banner di belakang dialog modal tidak dapat ditekan. Draft pending, idempotency key,
dan binding `X-Beeloft-Actor` dari perbaikan P1 tidak berubah.

Total approval tidak lagi bergantung pada halaman daftar. Command Center memakai
`store.approvals(limit=500, status="pending")` lalu menghitung `len()` dan `sum()` dari halaman itu, dan
`brain._approvals()` melakukan hal yang sama dengan `store.approvals(500,0,'pending','all')`. Karena
daftar diurutkan menurun, angka yang dilaporkan adalah 500 item terbaru: pada 610 pengajuan pending
jawabannya berhenti di 500, dan pada populasi campuran nominalnya ikut salah karena item tanpa nominal
mendorong item bernominal keluar halaman. `Store.approvals_summary(status, kind)` menjadi satu-satunya
sumber angka ringkasan, mengagregasi di database dengan proyeksi minimal dan subquery berkorelasi pada
event terakhir sehingga pengajuan dengan beberapa event tidak dihitung berulang. Nilai `*_minor`
diproyeksikan lalu diakumulasi dengan integer Python, bukan dengan `SUM()` SQLite yang akumulatornya
integer 64-bit dan dapat overflow untuk data yang masih sah menurut schema; `payroll_batch` memakai
`gross_pay_minor + employer_contributions_minor`, dan `ai_action` menjumlahkan string `'.2f'` dari
`action_payload` dengan `Decimal` alih-alih `CAST(... AS REAL)`. Sembilan kind inbox tercakup, item tanpa
nominal tetap dihitung pada count tanpa menambah amount, dan seluruh query berjalan dalam satu transaksi
baca. Kartu perhatian "Keputusan menunggu", jawaban serta facts AI intent `approvals`, dan jawaban
overview memakai sumber yang sama. Evidence investigasi memisahkan `summary` dari `sample` dengan
`sample_size` dan `truncated`, sehingga detail boleh terpotong tanpa membuat angka menyesatkan;
investigasi yang sudah tersimpan tidak dihitung ulang.

API: `GET /api/approvals/summary` ditambahkan dengan filter `status` dan `kind` yang sama seperti daftar.
`GET /api/approvals` tidak berubah bentuk, pagination, urutan, maupun permission-nya, dan batas `limit`
tetap 500. `/api/command-center` mendapat satu field additive `approvals.pending_without_amount`;
`approvals.by_kind` tetap enam kunci seperti sebelumnya.

P3 tetap di luar rilis ini: breakdown approval belum mencakup cuti, lembur, dan payroll; tanggal ekstrem
masih dapat menghasilkan 500; dan logout dengan API key tanpa cookie masih menghasilkan 500 pada server.

Rencana: [audit P2 plan](audit-p2-plan.md).
Bukti: [audit P2 verification](audit-p2-verification.md).

## Perbaikan audit P1: identitas subject OIDC yang persis (v0.88)

Rilis perbaikan tanpa fitur produk baru, tanpa connector vendor, dan tanpa perubahan schema. Schema
database tetap 55.

Klaim `sub` dipangkas dengan `.strip()` sesudah verifikasi tanda tangan dan sekali lagi sebelum lookup
identitas. Dua subject yang hanya dibedakan spasi awal/akhir karena itu dapat menunjuk akun yang sama:
setelah `employee-123` ditautkan ke seorang admin, token bertanda tangan yang sah dengan
`sub = " employee-123 "` menjawab callback `303`, membuat cookie session, dan `/api/me` mengembalikan
admin yang sama, walaupun subject itu belum pernah ditautkan. OIDC memakai pasangan issuer/subject apa
adanya (OIDC Core §5.7 dan §14), jadi pemangkasan seperti itu mengubah arti identitas.

Subject sekarang divalidasi sebagai string 1–500 karakter dan dipakai persis. `OidcClient.exchange`
tidak lagi memakai `str(...)` maupun `.strip()`, dan `Store._oidc_identity_values`, yang dipakai
bersama oleh link, unlink, dan authenticate, tidak lagi memangkas subject. Subject dengan spasi
awal/akhir ditolak — 422 pada operasi identitas CLI/API dan 401 pada klaim token — bukan dinormalkan,
sehingga tidak ada dua subject berbeda yang dapat bertabrakan; nilai seperti itu memang tidak dapat
disimpan persis oleh constraint `oidc_identities`. Normalisasi issuer pada konfigurasi tidak berubah.

Mapping lama yang tersimpan dalam bentuk terpangkas tidak dapat dibalik otomatis dan perlu ditinjau
terhadap nilai subject yang sebenarnya dari penyedia sebelum dipakai lagi.

Bukti: [audit OIDC subject verification](audit-oidc-subject-verification.md).

## Perbaikan audit P2: respons mapping yang tertunda (v0.89)

Rilis perbaikan tanpa fitur produk baru, tanpa connector vendor, dan tanpa perubahan schema. Schema
database tetap 55.

`productMappingForm()` dan `unmapProductForm()` menunggu GET mapping hanya dengan pemeriksaan sesi.
Selama sesi belum berganti, respons yang tiba setelah dialog asalnya ditutup tetap menggambar form
berikutnya: buka mapping, klik `Ubah mapping` atau `Lepaskan mapping`, tutup dialog, lalu buka
`Tambah SKU` dan ketik draft — respons lama yang menyusul mengganti dialog aktif dan draft ketikan
hilang. Jalur unmap bahkan dapat memanggil `productMappingDialog()` lagi dari respons lama.

Kedua fungsi sekarang menyimpan `dialogVersion` sebelum `await` dan keluar tanpa menggambar apa pun
bila sesi berganti, versi dialog berubah, atau dialog sudah tertutup — pola yang sama dengan
`productMappingDialog()` di dekatnya. Respons lama dibuang diam-diam, sehingga dialog aktif dan draft
yang sedang diketik tidak lagi digantikan, dan logout tidak dapat memunculkan dialog mapping di layar
login.

Bukti: [audit P2 mapping dialog race verification](audit-p2-mapping-dialog-race-verification.md).

## Perbaikan audit P2: rasio margin null pada investigasi (v0.90)

Rilis perbaikan tanpa fitur produk baru, tanpa connector vendor, dan tanpa perubahan schema. Schema
database tetap 55.

`_margin()` menyusun detail finding dengan menggabungkan `contribution_margin_rate` dan string tanpa
memeriksa nilai null. Rasio itu memang `None` ketika pendapatan bersih tidak positif: settlement sah
dengan omzet kotor Rp1000 dan diskon penjual Rp1000 menghasilkan laporan margin berstatus `complete`,
pendapatan bersih `0.00`, dan rasio `null`. Satu order seperti itu sudah cukup membuat
`POST /api/ai/investigate` menjawab `500` untuk pertanyaan margin, baik yang menyebut referensi order
maupun pertanyaan margin umum yang menyertakan order tersebut.

Finding sekarang menampilkan nominal margin apa adanya dan mengganti rasio yang tidak dapat dihitung
dengan keterangan `Rasio margin belum tersedia (pendapatan bersih Rp0.00).` Rasio tidak pernah
ditampilkan sebagai nol, dan order berstatus `complete` tetap ikut dihitung pada agregat margin.
Test `tests/test_ai_investigation.py` menambahkan kasus pendapatan bersih nol untuk pertanyaan
terfokus dan pertanyaan margin umum.

Bukti: [audit margin null ratio verification](audit-margin-null-ratio-verification.md).

## Perbaikan audit P2: agregat produksi pada jawaban fokus (v0.91)

Rilis perbaikan tanpa fitur produk baru, tanpa connector vendor, dan tanpa perubahan schema. Schema
database tetap 55.

`_production()` memakai ringkasan `production_board` apa adanya untuk jawaban fokus. Ringkasan itu
memang global supaya KPI board tidak bergoyang ketika daftar difilter, jadi pertanyaan tentang satu
order ikut menjawab angka order lain: satu order fokus 10 pcs yang belum jatuh tempo bersama satu
order terlambat berisi 500 pcs di cutting dijawab `Ada 2 order aktif, 1 terlambat, 0 kendala terbuka,
dan 500 pcs sedang diproses.` Bila hasil fokus melewati satu halaman, angka yang bocor juga bisa
berasal dari populasi yang lebih luas daripada halaman pertama daftar.

Jawaban dan facts sekarang memakai `production_scope()`: agregat atas order yang dipilih saja,
dihitung di database atas seluruh populasi yang cocok sehingga hasil di atas satu halaman tetap utuh.
SQL populasi dipakai bersama `production_board()`, jadi definisi filternya tidak dapat menyimpang.
Kontrak KPI `/api/production-board` tidak berubah - ringkasannya tetap global - dan agregat yang
mendasari jawaban disimpan pada `evidence.production_scope` di samping `evidence.production_board`.

Bukti: [audit focused production aggregate verification](audit-p2-focused-production-aggregate-verification.md).

## Perbaikan audit P2: tombol login lokal yang salah dikunci (v0.92)

Rilis perbaikan tanpa fitur produk baru, tanpa connector vendor, dan tanpa perubahan schema. Schema
database tetap 55.

Handler `login-form` memilih tombolnya dengan `querySelector('button')`. Tombol SSO berada lebih
dahulu di dalam form yang sama dan tetap elemen pertama ketika SSO tidak dikonfigurasi, jadi yang
dinonaktifkan dan diberi label `Memeriksa akses…` adalah tombol provider: tombol submit tetap aktif
selama request login berjalan, dua klik mengirim dua `POST /api/session` yang berlomba menggantikan
cookie session, dan blok `finally` menimpa label provider menjadi `Buka ruang produksi` — permanen,
dan terlihat sebagai tombol yang salah ketika SSO aktif.

Pemilihan sekarang dipersempit ke `button[type="submit"]` sehingga hanya tombol submit yang dikunci,
diberi label proses, dan dipulihkan labelnya dari salinan nilai sebelumnya. Satu login dalam
penerbangan dijaga `loginRequest` dengan pola yang sama seperti `logoutRequest`, karena
penonaktifan tombol saja tidak menutup jalur `form.requestSubmit()` yang tetap memicu `submit` event
ketika tombol defaultnya nonaktif. Alur SSO dan `POST /api/session` tidak berubah.

Bukti: [audit login submit verification](audit-p2-login-submit-verification.md).

## Perbaikan audit P2: authorization endpoint OIDC ber-query (v0.93)

Rilis perbaikan tanpa fitur produk baru, tanpa connector vendor, dan tanpa perubahan schema. Schema
database tetap 55.

`OidcClient.authorization_request` menyusun URL otorisasi dengan
`metadata['authorization_endpoint'] + '?' + query`. Ketika metadata memuat authorization endpoint yang
sudah memiliki query bawaan — mis. `https://identity.example/authorize?p=tenant-policy` — hasilnya
`…?p=tenant-policy?response_type=code&…`: tanda `?` kedua tidak pernah menjadi pemisah query, sehingga
`response_type` tidak ada sebagai parameter tersendiri melainkan menempel pada nilai `p`. Provider yang
memakai parameter policy/tenant karena itu tidak pernah menerima permintaan otorisasi yang benar, dan
RFC 6749 §3.1 mensyaratkan query bawaan endpoint dipertahankan saat parameter tambahan ditambahkan.

URL sekarang dirakit dengan `urllib.parse`: `urlsplit` memecah endpoint, query bawaan dipertahankan
apa adanya, dan parameter OAuth — `response_type`, `client_id`, `redirect_uri`,
`scope=openid profile email`, `state`, `nonce`, `code_challenge`, `code_challenge_method=S256` —
disambung sebagai parameter query tersendiri sebelum `urlunsplit` menyusun ulang URL. Endpoint tanpa
query, endpoint dengan `?` kosong, dan endpoint dengan satu atau lebih parameter policy/tenant
menghasilkan URL yang sama benarnya. Nilai parameter, validasi metadata, dan alur callback tidak
berubah.

Bukti: [audit oidc authorization query verification](audit-p2-oidc-authorization-query-verification.md).

## Perbaikan audit P2: encoding client_secret_basic OAuth (v0.94)

Rilis perbaikan tanpa fitur produk baru, tanpa connector vendor, dan tanpa perubahan schema. Schema
database tetap 55.

`UrlTransport.form_post` menyusun header `Authorization` client_secret_basic dari `id:secret` mentah
sebelum Base64. RFC 6749 §2.3.1 mewajibkan username dan password di-form-encode (Appendix B) sebelum
digabung, sementara provider membacanya dengan memisah pada titik dua pertama lalu mem-form-decode
kedua bagian. Kredensial seperti `client:id` / `secret+percent%value` karena itu dibaca provider
sebagai `client` / `id:secret percent%value`, nilai yang memuat `+` atau `%` berubah arti, dan login
gagal pada provider yang hanya mendukung Basic.

Setiap nilai sekarang di-encode terpisah dengan `urllib.parse.quote_plus`, baru digabung dengan `:`
dan di-Base64, sehingga titik dua di dalam nilai menjadi `%3A` dan pemisah pertama yang dibaca
provider selalu pemisah yang benar. Jalur `client_secret_post` tidak berubah: secret tetap dikirim di
body form lewat `urlencode` dan header `Authorization` tidak dikirim.

Bukti: [audit oidc client secret basic verification](audit-p2-oidc-client-secret-basic-verification.md).


## Perbaikan audit P3: state callback OIDC non-ASCII (v0.95)

Rilis perbaikan tanpa fitur produk baru, tanpa connector vendor, dan tanpa perubahan schema. Schema
database tetap 55.

`/api/sso/callback` membandingkan cookie `beeloft_oidc_state` dengan parameter `state` memakai
`secrets.compare_digest()` atas `str` mentah. Fungsi itu menolak `str` yang memuat karakter non-ASCII
dengan `TypeError`, dan kedua nilai sepenuhnya dikendalikan pengirim request. Dengan SSO aktif,
`/api/sso/callback?code=x&state=%C3%A9` karena itu dijawab HTTP 500 dengan traceback — juga callback
yang `state`-nya sah tetapi datang bersama cookie ber-byte non-ASCII — padahal state seperti itu
tidak pernah diterbitkan aplikasi dan semestinya ditolak sebagai state tidak sah.

State sekarang diperiksa lebih dahulu terhadap alfabet yang memang diterbitkan `secrets.token_urlsafe`
(huruf, angka, `-`, `_`), lalu dibandingkan sebagai byte ASCII dengan `secrets.compare_digest` seperti
sebelumnya. Kedua sisi diperiksa, sehingga state maupun cookie di luar alfabet ditolak 401 dengan
pesan yang sama seperti state ASCII yang tidak cocok, berhenti sebelum attempt login tersimpan
dikonsumsi. Callback yang sah tidak berubah: tetap 303 ke `/` dengan cookie session, dan state tetap
sekali pakai.

Bukti: [audit oidc state non-ASCII verification](audit-p3-oidc-state-non-ascii-verification.md).

## Perbaikan audit P3: hidrasi order pada metadata focus investigasi (v0.96)

Rilis perbaikan tanpa fitur produk baru, tanpa connector vendor, dan tanpa perubahan schema. Schema
database tetap 55.

`investigate()` menjalankan `_focus()` untuk semua intent sebelum dispatch, dan `_focus()` memanggil
`store.orders()` yang menghidrasi setiap order lewat `_order()`: revision, lines, balances per line,
dan hitungan kendala terbuka. Biayanya tumbuh sekitar lima statement per order, padahal jawaban
approval hanya memakai agregat dan contoh approval, dan pencocokan focus sendiri hanya memakai kolom
identitas. Pada populasi sintetis satu baris per order, pertanyaan `approval persetujuan` mengeksekusi
528 statement untuk 100 order, 5.028 untuk 1.000 order, dan 25.028 untuk 5.000 order.

`_focus()` sekarang membaca `store.product_identities()` dan `store.order_identities()`: satu
statement masing-masing, hanya kolom yang dipakai untuk mencocokkan SKU dan referensi order.
Kontrak metadata `focus` tidak berubah. `_margin()` bekerja atas id order — lewat
`store.order_ids_for_products()` untuk fokus produk — sehingga detail hanya dimuat oleh
`contribution_margin()` untuk order yang benar-benar dilaporkan, dengan pemotongan 100 order dan flag
`evidence.truncated` yang sama. Jalur approval kini berbiaya 28 statement konstan pada ketiga ukuran
populasi di atas, tanpa cache, service, atau dependency baru.

`order_ids_for_products()` mengirim id produk sebagai satu parameter JSON dan membandingkannya lewat
`json_each()`, bukan satu placeholder per id. Jumlah produk yang cocok tidak dibatasi dan satu nama
produk dapat dipakai seluruh varian SKU-nya, jadi daftar placeholder akan melewati
`SQLITE_LIMIT_VARIABLE_NUMBER` pada katalog besar dan menjawab pertanyaan margin dengan HTTP 500.

Bukti: [audit approval focus hydration verification](audit-p3-approval-focus-hydration-verification.md).

## Perbaikan lifecycle dialog: blokir interaksi selama keluar (v0.98)

Setelah Escape atau tombol tutup diterima, dialog menjadi `inert` seketika;
animasi keluar tetap berjalan sebelum penutupan native. Sebelumnya
`pointer-events: none` masih membiarkan Enter mengirim formulir yang sedang
menutup. Satu listener submit capture juga memblokir `requestSubmit()` selama
inert. Cleanup close dan pembukaan berikutnya memulihkan interaksi, tanpa
mengubah guard busy/unresolved, transaksi, atau fokus kembali.

Regresi browser membuktikan satu POST sebelum perbaikan menjadi nol setelahnya,
menguji keyboard/pointer/fokus, reduced motion, buka ulang, serta penyimpanan
normal yang tetap berhasil. Versi aplikasi 0.98.0; schema tetap 55, tanpa migrasi.

Bukti: [dialog closing keyboard guard verification](dialog-closing-keyboard-guard-verification.md).

## Apple-27 A1: fondasi visual dan material (v0.99)

DESIGN.md menetapkan program Apple-27 sebagai arah aktif, dengan rekonstruksi Shopeers
sebagai konteks historis. Satu fondasi semantik mengatur font sistem native, palet
light/dark, material solid, radius, elevasi, dan geometri kontrol bersama. Alias lama
tetap mengarah ke sumber yang sama. Dialog memakai radius prominent, tombol memakai
radius kontrol, dan fokus/tepi formulir mengikuti tema.

Komposisi workspace, SVG, JavaScript, gerak M1–M6 dan guard dialog #87 tetap utuh.
Tidak ada glass, lens, spring, perubahan API/bisnis atau migrasi database.
Versi aplikasi 0.99.0; schema tetap 55.

Bukti dan kontrak: [Apple-27 design foundation](apple27-design-foundation.md).

## Apple-27 A2: satu selection lens navigasi (v0.100)

Satu permukaan dekoratif mengikuti `aria-current` pada sidebar, anak Analitik,
dan Inbox approval. Geometri diukur dari tombol yang sedang dirender, dengan
penanganan scroll, resize, skala teks, disclosure, drawer, serta pergantian sesi
dan role. Styling terpilih sebelumnya tetap menjadi fallback jika lens tidak
dapat ditampilkan. Tidak ada spring, animasi perjalanan, glass, perubahan bisnis
atau migrasi. Versi aplikasi 0.100.0; schema tetap 55.

Bukti dan kontrak: [Apple-27 navigation lens](apple27-navigation-lens.md).
