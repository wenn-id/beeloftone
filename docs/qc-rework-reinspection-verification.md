# Verifikasi selesai rework dan inspeksi ulang final QC, v0.84

Tanggal: 16 September 2026. Base `f9f85d2`; branch `fix/qc-rework-reinspection-p1`.
Semua pengujian memakai database sementara dan tidak menyentuh database operasional.

## Kegagalan sebelum perbaikan

Direproduksi lebih dahulu pada `origin/main` (schema 54, aplikasi 0.83.0): finishing memasukkan 20 pcs
ke QC, inspeksi awal mencatat 12 diterima + 8 rework, perpindahan generik `rework -> qc` mengembalikan
8 pcs sehingga saldo order menjadi `qc = 8`, `rework = 0`, `warehouse = 12`, tetapi finishing sudah
melaporkan `qc_inspected_quantity = 20` dan `qc_remaining_quantity = 0`. Inspeksi kedua atas 8 pcs itu
ditolak:

```
POST /api/finishing-records/{id}/qc-records
HTTP 409 {"detail":"Jumlah inspeksi melebihi finishing yang belum diperiksa. Muat ulang data terbaru."}
```

Penolakan datang dari dua tempat sekaligus: guard Python di `Store.create_final_qc_record` dan trigger
`final_qc_source_valid`. Keduanya membandingkan jumlah seluruh catatan final QC dengan
`finishing_records.quantity`, sehingga 8 pcs yang secara fisik berada di QC tidak dapat diinspeksi lagi.

## Model lineage final

Perbaikan tidak melonggarkan `qc_remaining_quantity`. Entitas baru `rework_completions` mencatat
pengembalian rework ke QC beserta catatan final QC sumbernya, dan `final_qc_records` mendapat
`rework_completion_id` (NULL untuk inspeksi awal) serta `inspection_round`. `finishing_record_id` tetap
`NOT NULL` pada inspeksi ulang, sehingga seluruh join lineage yang sudah ada — hydrator final QC,
trigger SKU barang jadi, `production_cost`, `contribution_margin`, dan enam file `.sql` lain yang
menelusuri `finished_goods_receipts → final_qc_records → finishing_records → … → products` — tidak
berubah. Rincian invarian I1–I9 ada di `qc-rework-reinspection-plan.md`.

## Data lama yang sudah mengembalikan rework tanpa lineage

Database schema 54 dapat memuat perpindahan `rework -> qc` generik. Pcs-nya sudah di QC sementara catatan
final QC-nya masih melaporkan rework belum selesai, jadi keduanya tidak dapat dipakai: inspeksi awal
ditolak oleh alokasi finishing, dan selesai rework ditolak karena saldo tahap rework sudah nol. Migrasi
sengaja tidak menebak lineage untuk baris seperti itu. Keadaannya dilaporkan apa adanya lewat
`untraced_rework_return_quantity` dan `rework_completable_quantity` pada payload final QC; UI
menyembunyikan tombol **Catat selesai rework** dan menampilkan penyebabnya; API menjawab 409 dengan pesan
yang menyebut jumlah perpindahan tanpa lineage dan menunjuk riwayat perpindahan order. Remediasinya
diverifikasi berjalan penuh: admin mengoreksi perpindahan lama, pcs kembali ke rework, lalu selesai rework
dan inspeksi ulang tercatat normal dengan total order tetap 20 pcs. Baris lama beserta pembaliknya tetap
terbaca. `test_legacy_untraced_rework_return_is_reported_and_remediable` mengunci seluruh rantai ini.

## Schema dan migrasi

Schema 54 → 55 lewat `beeloft/rework_completions.sql` dan dua `ALTER TABLE` yang dijaga
`PRAGMA table_info`: tabel `rework_completions` dan
`rework_completion_reversals`, kolom `rework_completion_id` + `inspection_round` pada
`final_qc_records`, index `final_qc_records_rework_completion`, trigger
`rework_completion_source_valid`, `rework_completion_reversal_valid`,
`final_qc_blocks_rework_completion_reversal`, `rework_completion_blocks_final_qc_reversal`, empat
trigger immutability, dan penulisan ulang `final_qc_source_valid` agar memvalidasi inspeksi awal
maupun inspeksi ulang. Seluruh 59 asersi versi schema pada test diperbarui ke 55 secara mekanis; tidak
ada asersi yang dilemahkan.

`rework_completion_id` sengaja tanpa klausa `REFERENCES`. `ALTER TABLE` berjalan sebelum
`rework_completions` dibuat, dan dengan `foreign_keys=ON` kolom yang menunjuk tabel induk yang belum ada
menolak **setiap** insert ke `final_qc_records`, termasuk insert bernilai null, tanpa terdeteksi
`PRAGMA foreign_key_check`. Integritas referensial tetap utuh lewat trigger: `final_qc_source_valid`
menolak `rework_completion_id` yang tidak menunjuk catatan selesai rework aktif — diuji langsung di level
database — dan kedua tabel append-only sehingga baris induk tidak dapat dihapus atau diubah.

Fixture schema 54 pada `test_rollback_backup_guards_and_migration_from_54` menghapus tabel, trigger, index,
dan **kedua kolom** lineage, sehingga cabang `ALTER TABLE` benar-benar dijalankan seperti pada database
produksi. Database lama yang sudah memuat perpindahan `rework -> qc` tanpa lineage dimigrasikan dan
diperiksa: `PRAGMA user_version` = 55, `integrity_check` = ok, `quick_check` = ok, `foreign_key_check`
kosong, dan pembukaan ulang berkali-kali tidak mengubah apa pun. Baris historis tetap terbaca lewat
`GET /api/orders/{id}/movements` dengan `rework_completion_id` bernilai null. Backup dari database hasil
migrasi juga bersih. Tidak ada baris historis yang dihapus atau ditulis ulang.

## Bukti kekekalan jumlah

Satu order 20 pcs, satu SKU. `Store._transfer` membatalkan transaksi kecuali
`SUM(balances) = order_lines.quantity`, jadi setiap baris di bawah ini adalah invarian yang benar-benar
ditegakkan, bukan hanya hasil pengamatan.

| Langkah | planned | cutting | sewing | finishing | qc | rework | reject | warehouse | total |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| finishing 20 pcs masuk QC | 0 | 0 | 0 | 0 | 20 | 0 | 0 | 0 | 20 |
| inspeksi awal 12 / 8 / 0 | 0 | 0 | 0 | 0 | 0 | 8 | 0 | 12 | 20 |
| selesai rework #1 (8 pcs) | 0 | 0 | 0 | 0 | 8 | 0 | 0 | 12 | 20 |
| inspeksi ulang #1: 3 / 5 / 0 | 0 | 0 | 0 | 0 | 0 | 5 | 0 | 15 | 20 |
| selesai rework #2 (5 pcs) | 0 | 0 | 0 | 0 | 5 | 0 | 0 | 15 | 20 |
| inspeksi ulang #2: 5 / 0 / 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 20 | 20 |
| terima barang jadi 5 pcs | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 20 | 20 |

Net per tahap dari delapan perpindahan yang dicetak: `qc = +20 −12 −8 +8 −3 −5 +5 −5 = 0`,
`rework = +8 −8 +5 −5 = 0`, `warehouse = +12 +3 +5 = 20`. Penerimaan barang jadi hanya
mengklasifikasikan stok gudang dan tidak memindahkan WIP. Pembongkaran koreksi dari hilir ke hulu
mengembalikan seluruh 20 pcs ke `qc` lalu ke `finishing`, tetap dengan total 20.

## Efek pada metrik kualitas

`production_quality_insights` mempertahankan `first_pass_yield_percent = accepted / inspected` dengan
populasi **inspeksi awal saja**. Untuk contoh 20 pcs di atas, `record_count = 1`,
`inspected_quantity = 20`, `accepted_quantity = 12`, `first_pass_yield_percent = 60.00`,
`rework_rate_percent = 40.00` — nilainya identik sebelum dan sesudah inspeksi ulang dicatat. Breakdown
`defect_types`, `responsible_sources`, `skus`, serta seluruh field `previous_*` juga tetap berbasis
inspeksi awal. Hasil inspeksi ulang dilaporkan secara tambahan sebagai `reinspection_record_count`,
`reinspected_quantity`, `reinspection_accepted_quantity`, `reinspection_rework_quantity`,
`reinspection_reject_quantity`, `reinspection_nonconforming_quantity`, dan
`reinspection_nonconforming_rate_percent` pada level grup, SKU, dan summary. Kontrak respons mendapat
`first_pass_yield_basis: "initial_inspections_only"` dan `reinspections: "reported_separately"`; tidak
ada field lama yang berubah arti atau nilai.

Memisahkan inspeksi ulang dari populasi yield tidak boleh berarti kegagalan berulang menjadi tak terlihat.
Karena itu ditambahkan satu alasan perhatian baru, `reinspection_above_warning`, yang memakai denominator
inspeksi ulang sendiri dan menyala ketika `reinspection_nonconforming_rate_percent` mencapai
`warning_percent`. Alasan, ambang, dan nilai yang sudah ada tidak berubah. `command_center.py` kini
mengekspor `reinspected_quantity`, `reinspection_nonconforming_quantity`, dan
`reinspection_nonconforming_rate_percent`, serta menambahkan satu kalimat pada kartu perhatian kualitas.
Diuji pada jendela yang hanya memuat inspeksi ulang dengan 8 dari 8 pcs gagal lagi: grupnya berstatus
`attention` dengan alasan `reinspection_above_warning`, `first_pass_yield_percent` tetap berbasis inspeksi
awal, dan command center melaporkan angka inspeksi ulangnya. Jendela seperti itu memang menambah satu grup
ke daftar — nilai field lama tidak berubah, tetapi populasi grup dan SKU dapat bertambah, dan itu memang
disengaja agar datanya tidak hilang.

## Perpindahan `rework -> qc` generik

`("rework","qc")` dihapus dari `models.TRANSITIONS`. `POST /api/movements` menjawab 422 untuk rute itu,
`GET /api/stages` tidak lagi mengiklankannya, dan form "Catat perpindahan" tidak lagi menawarkan rework
sebagai tahap asal. Pengembalian rework baru hanya melalui
`POST /api/final-qc-records/{id}/rework-completions`. Pembalikan tidak memakai `TRANSITIONS`, sehingga
koreksi perpindahan `qc -> rework` yang sudah ada tetap berjalan; `test_production.py` sekarang
menegaskan keduanya.

Akibatnya `rework` tidak punya transisi keluar generik sama sekali. Ini disengaja: pcs yang tidak dapat
diperbaiki keluar dari rework lewat jalur yang sama seperti pcs yang berhasil — selesai rework
mengembalikannya ke QC, lalu inspeksi ulang mencatatnya sebagai `reject_quantity`, sehingga pembuangan
punya catatan inspeksi. Baris yang sisa saldonya berada di rework tidak lagi diarahkan ke pembalikan: form
perpindahan mengenali kondisi itu dan menunjuk alur selesai rework, dan tampilan order mendapat tombol
**Selesai rework** di samping **Final QC**.

## Cakupan test

Empat belas acceptance test baru di `tests/test_rework_reinspection.py` memeriksa siklus inspeksi awal →
rework → selesai rework → inspeksi ulang → diterima, siklus rework berulang tanpa batas, selesai rework
sebagian, inspeksi ulang sebagian, penolakan kelebihan selesai rework, penolakan kelebihan inspeksi
ulang, dua selesai rework bersamaan yang tidak dapat melebihi satu sumber rework, dua inspeksi ulang
bersamaan yang tidak dapat melebihi satu catatan selesai rework, penerimaan barang jadi dari inspeksi
ulang, koreksi hulu yang terkunci oleh hilir aktif, pembongkaran koreksi dalam urutan terbalik yang
benar, aturan tanggal termasuk siklus berulang, izin admin/operator/viewer, retry idempoten
byte-identical, retry setelah respons hilang pada session browser, binding `X-Beeloft-Actor`, migrasi
dari schema 54 termasuk cabang `ALTER TABLE`, backup/restore, penolakan insert langsung oleh trigger
database termasuk `rework_completion_id` yang tidak menunjuk catatan mana pun, first-pass yield yang tetap
berbasis inspeksi awal, kegagalan inspeksi ulang yang tetap memunculkan perhatian, serta database lama
dengan pengembalian rework tanpa lineage beserta remediasinya.

Seluruh suite backend Python 3.12 lulus: **386 test dalam 198,001 detik** (`python -m unittest
discover -s tests`), naik dari 372 test pada base.

## Browser dan client

Modul acceptance baru `tests/browser_rework_reinspection.cjs` menjalankan alur nyata di Chromium:
finishing → final QC → rework → selesai rework → inspeksi ulang → diterima → penerimaan barang jadi,
dengan siklus rework kedua, pembuktian kekekalan jumlah pada setiap langkah, penolakan pengembalian
rework generik di API dan di form perpindahan beserta arahan ke alur selesai rework, pintu masuk
**Selesai rework** pada tampilan order, label "Inspeksi awal" / "Inspeksi ulang #1" /
"Inspeksi ulang #2" pada riwayat, tautan induk pada tampilan rincian, jejak lineage sampai batch bahan,
viewer read-only, koreksi berurutan dari hilir ke hulu, retry setelah respons hilang, serta pemeriksaan
overflow pada 390×844 dan teks 200%.

Seluruh **64 modul** browser Playwright lulus tanpa error JavaScript, termasuk alur produksi,
marketplace, integrasi, approval, dan audit trail yang sudah ada.

## Pemeriksaan rilis

Kontrak `docs/openapi.json` diregenerasi ke versi 0.84.0 dan memuat lima path baru
(`/api/final-qc-records/{record_id}/rework-completions`, `/api/orders/{order_id}/rework-completions`,
`/api/rework-completions/{completion_id}`, `/api/rework-completions/{completion_id}/qc-records`,
`/api/rework-completions/{completion_id}/reverse`) untuk enam operasi, serta schema
`ReworkCompletionCreate`. Selain penambahan itu dan nomor versi, kontrak identik dengan base.
`pip check`, `python -m compileall beeloft`, `node --check` untuk **67 file** JavaScript, client test,
`git diff --check`, serta `integrity_check` dan `foreign_key_check` pada database hasil migrasi lulus
sebelum commit.

## Batas

Biaya dan tenaga kerja rework tetap di luar `production_cost`, yang masih mencantumkan
`quality_control` pada `excluded_costs`. Rework belum dijadwalkan ke work center di luar rute kapasitas
`rework -> qc` yang sudah ada. Tidak ada pelacakan serial per pcs: alokasi dihitung per jumlah terhadap
catatan sumber bernama, sama seperti seluruh ledger WIP lainnya. Pengembalian rework lama tanpa lineage
dilaporkan dan dapat diremediasi, tetapi tidak dikonversi otomatis menjadi catatan selesai rework karena
inspeksi sumbernya memang tidak diketahui. Breakdown jenis defect dan sumber penanggung jawab tetap
berbasis inspeksi awal; kegagalan inspeksi ulang muncul lewat alasan perhatian dan totalnya sendiri.
Temuan audit Codex lain tidak dikerjakan pada perubahan ini.
