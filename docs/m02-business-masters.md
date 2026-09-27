# M02: implementasi unit usaha, gudang, pihak dan employee

Implementasi [#44](https://github.com/wenn-id/beeloftone/issues/44) di atas
`docs/m02-master-readiness.md`. Hasil kerja ini tidak mengulang audit F01/F02
atau meminta sign-off bisnis; kontrak F02 dipakai sebagaimana adanya.

Branch: `feat/m02-business-masters-44`. Versi aplikasi `0.115.0`, skema `57`.

## Apa yang dibangun

| Master | Identitas | Catatan |
|---|---|---|
| Unit usaha | `business_units` + `business_unit_events` | Kode unik global, nama diubah lewat revisi |
| Lokasi/gudang | `storages` + `storage_events` | Kode unik per unit; nama unik per unit, nama sama di unit lain sah |
| Pelanggan | `customers` + `customer_events` | Contact/address opsional |
| Jabatan | `positions` + `position_events` | Sengaja tanpa kolom department; jabatan dan departemen tidak disamakan |
| Metode pembayaran | `payment_methods` + `payment_method_events` | Master konfigurasi; tidak menjalankan pembayaran |
| Pemasok | `suppliers` (existing) | Hanya status aktif yang ditambah; identitas tetap immutable |
| Employee | `workforce_employees` (existing) | Tambah `position_id`/`business_unit_id` pada event + mapping legacy ID |

Semua master memakai pola identity + events yang sudah ada: `active` hidup di
tabel event, sehingga histori tetap terbaca setelah master dinonaktifkan, dan
mutasi lewat `Store._write` (idempotency, role check, audit + receipt dalam satu
transaksi). Tidak dibuat sistem identitas kedua.

## Aturan domain

- Menonaktifkan unit usaha ditolak (409) selama masih ada lokasi aktif yang
  menempel; relasi unit-lokasi eksplisit tidak boleh yatim piatu.
- Lokasi baru pada unit nonaktif ditolak (422).
- Nama lokasi sama dalam satu unit ditolak (409); nama sama di unit berbeda
  adalah dua identitas berbeda dan tetap dapat dibedakan lewat `label`
  (`"Nama · KODEUNIT"`).
- Transaksi baru menolak master nonaktif: penerimaan bahan menolak
  `storage_id`/`supplier_id` nonaktif (422), employee baru menolak jabatan
  nonaktif (422). Histori lama dan koreksi transaksi lama tidak terpengaruh.
- Job sewing internal boleh menautkan `employee_id`; makloon/vendor tetap
  memakai `assignee` teks dan tidak boleh ditautkan ke employee (422).
- Supplier: hanya status aktif yang dapat diubah. Trigger F02 diganti agar
  identitas (kode/nama/kontak/alamat) tetap terkunci di level database.
- Metode pembayaran adalah master/konfigurasi saja. Tidak ada eksekusi
  pembayaran, invoice, atau settlement — itu tetap di luar M02.

## Pemetaan lokasi teks ke identitas storage

`storage_location_mappings` adalah overlay baca: baris transaksi tidak pernah
diubah, saldo dan riwayat pergerakan utuh. Sumber teks lokasi diambil dari 12
kolom (batch bahan, penerimaan/transfer barang jadi, warehouse movement
from/to, reservasi, staging pick, handoff from/to, retur, adjustment, opname,
QC intake).

Aturan pencocokan deterministik:

- tepat satu lokasi aktif dengan nama yang cocok (casefold, trim) →
  `confirmed`/`unique_name`;
- tidak ada yang cocok → `pending`;
- nama sama di lebih dari satu unit → `ambiguous`. Unit pemilik tidak pernah
  ditebak; kolom `storage_id` dibiarkan kosong sampai admin memetakan eksplisit.

`recompute_location_mappings` mempertahankan baris `match_basis='explicit'`
yang sudah dipetakan admin. Pemetaan eksplisit mengubah `match_status` menjadi
`confirmed` tanpa menyentuh teks asli. Jalur ini membuktikan butir 3 acceptance:
saldo tidak dihitung ulang, bukti lokasi asal tetap ada.

## Kompatibilitas DB lama dan payload lama

Migrasi 57 (`beeloft/business_masters.sql` + runner di `store.py`):

- Semua `CREATE TABLE IF NOT EXISTS`; tabel baru additive.
- `ALTER TABLE ... ADD COLUMN` dijalankan lewat runner Python dengan cek
  `PRAGMA table_info` karena `ADD COLUMN` tidak idempoten — test suite lain
  membangun skema lengkap lalu memutar balik `user_version` untuk mensimulasikan
  DB lama, dan runner harus bisa migrasi ulang tanpa error.
- Supplier existing default `active=1`; kolom baru employee nullable; teks
  lokasi pada batch lama tidak diubah.
- Payload lama tetap sah: `storage_id`, `supplier_id`, `business_unit_id`,
  `employee_id`, `position_id` semuanya opsional. Endpoint menerima body tanpa
  field baru.

## Endpoint

24 path baru di `docs/openapi.json` (221 → 247), tag `Business Masters`:
list/one/history/create/change untuk unit, storage, customer, position, payment
method; plus `POST /api/suppliers/{id}/changes`, legacy ID employee, dan
recompute/list/map/summary untuk pemetaan lokasi. Semua mutasi admin-only
(403 untuk operator/viewer); baca terbuka untuk semua role.

## UI

`beeloft/static/index.html` + `app.mjs`: nav "Master bisnis" dengan tab per
jenis master dan tab "Pemetaan lokasi". Pencarian instan di sisi klien, keadaan
loading/kosong/error/retry, dan penolakan nonaktif ditampilkan lewat pesan
server. Form memakai `formDialog` yang sama dengan fitur lain (idempotency +
reauth). Tombol "Ubah" hanya muncul untuk admin.

## Verifikasi

`tests/test_business_masters.py` (37 test) mencakup: integritas migrasi dan
idempotensi, rewind `user_version` lalu migrasi ulang, master berversi + guard
revisi basi + no-change, histori tetap terbaca setelah nonaktif, nama lokasi
sama di unit berbeda, unit nonaktif tidak menerima lokasi baru, immutabilitas
identitas supplier, relasi employee + legacy ID + jabatan nonaktif, jabatan
bukan departemen, penolakan master nonaktif pada transaksi baru, pemetaan
ambigu/pending/confirmed/eksplisit, dan izin per role.

Eksekusi lengkap `python -m pytest tests/` → hasil tercatat di PR. Tidak ada
data pribadi nyata; seluruh fixture sintetis.

## Relasi handoff untuk modul yang belum dibangun

- POS (#57): relasi unit–storage sudah disiapkan (`storages.business_unit_id`,
  `UNIQUE(code,business_unit_id)`). POS belum dibangun; ini kontrak relasi saja.
- Payroll (#55): `workforce_employee_legacy_ids` menyimpan ID stabil per sistem
  sumber; job internal menautkan `employee_id` ke `workforce_employees`. M02
  tidak masuk ke payroll.
- Masters produk/material/UOM (#43): tidak diubah. Binding lokasi ke batch bahan
  sengaja berupa overlay baca, bukan kolom baru di `material_batches`.

## Status integrasi

#43 belum merged saat PR ini disiapkan, tetapi cabangnya
(`origin/feat/m01-master-catalog-43`) sudah mengambil migrasi 56 secara definitif
(`Migrasi 56 — M01 master katalog` di `beeloft/master_catalog.sql`). Karena urutan
integrasi #43 dulu lalu #44, dan kedua cabang tidak boleh memakai nomor migrasi
yang sama — bila #43 merge lebih dulu, sebuah DB di versi 56 akan membuat branch
runner `if version < 56` meloncati pembuatan tabel master M02 seluruhnya — migrasi
ini dinaikkan ke **57** sejak awal. Nomor 57 dipakai di `PRAGMA user_version` di
`business_masters.sql`, branch runner `if version < 57` di `store.py`, tuple versi
yang diterima `Store.__init__`, dan assertion `user_version` pada seluruh suite.
Konflik file bersama (`store.py`, `models.py`, `api.py`, `app.mjs`) diselesaikan
dengan menjaga kedua fitur; urutan integrasi #43 dulu, lalu #44.

### Resep resolusi konflik (dry-run `git merge-tree` terhadap `origin/feat/m01-master-catalog-43`)

75 file konflik, 77 file auto-merge. `beeloft/api.py` dan `docs/openapi.json`
auto-merge bersih. Semua konflik jatuh ke kelas berikut, masing-masing diselesaikan
dengan union (kedua fitur dipertahankan):

| Kelas | File | Resolusi |
|---|---|---|
| Assertion `user_version` | ~70 file test | Kedua cabang mengangkat angka yang sama dari basis 55 (#43 ke 56, #44 ke 57). Ambil **57**: kedua migrasi berjalan, ladder 55 → 56 → 57. |
| Assertion `max(versions)` | 10 contract test | Ambil **57** (SQL file dengan `PRAGMA user_version` tertinggi setelah union). |
| Ladder migrasi | `beeloft/store.py` | Simpan kedua branch: `if version < 56` (#43, `master_catalog.sql`) lalu `if version < 57` (M02, `business_masters.sql`) setelahnya. Union tuple versi diterima `Store.__init__`. |
| Model Pydantic | `beeloft/models.py` | Union kedua set model; tidak ada nama yang bentrok (#43 memakai prefix katalog, M02 memakai prefix master). |
| Renderer UI | `beeloft/static/app.mjs` | Union kedua set fungsi. |
| Section HTML | `beeloft/static/index.html` | Union kedua section. |
| Kontrak containment A6.0 | `tests/test_apple27_modern_workspace_foundation_contract.py` | `MIGRATED_SECTIONS` dan `MIGRATED_RENDERERS` butuh tambahan renderer katalog #43; union dengan blok M02 yang sudah ada. |
| Csv kepemilikan | `docs/f02-ownership.csv` | Union kedua set baris. |
| Jumlah test | `README.md` | Ambil hasil rerun suite setelah union; jangan ambil angka salah satu cabang. |

Tidak ada overlap semantik: #43 mengubah tabel `products`/`materials`, M02 tidak
menyentuhnya (pemetaan lokasi M02 membaca `material_batches.location` read-only
sebagai overlay, tanpa kolom di tabel milik #43). `suppliers.active` hanya ditambah
M02. Setelah resolusi, jalankan full suite (termasuk upgrade dari DB 54 dan dari
DB pasca-migrasi-#43) sebelum merge.
