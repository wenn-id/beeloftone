# P01: kesiapan template bahan/jasa dan tarif

Persiapan [#48](https://github.com/wenn-id/beeloftone/issues/48), diperiksa pada
22 September 2026, commit `8a2e2ac46c71bf528180562688fb4d4adaf686f0`,
v0.97.0/schema 55. **BLOCKED_M01_M02: belum implementasi atau business accepted.**

Issue #48 mensyaratkan penerimaan M01 #43 dan M02 #44 sebelum implementasi yang
bergantung padanya. Keduanya masih terbuka; PR #79/#80 hanya menyerahkan
[kesiapan M01](m01-master-readiness.md) dan [M02](m02-master-readiness.md).
[F02](f02-shared-contracts.md) masih DRAFT, sign-off PENDING, dan D04 dalam
[register keputusan F01](f01-decisions-evidence.md) masih OPEN. Merge dokumen
persiapan tidak mengesahkan aturan tarif atau menyelesaikan #48.

## Pemetaan HEAD ke hasil kerja P01

| Area | Perilaku existing dan sumber | Gap terhadap P01 |
|---|---|---|
| Template bahan | `BomSave` dan `Store.save_bom` menyimpan komponen per SKU di `bom_revisions`; append-only, alasan/actor, revision guard dan idempotency ([bom.sql](../beeloft/bom.sql), [test_bom.py](../tests/test_bom.py)) | Gunakan versi BOM ini, bukan tabel bahan paralel. Belum identitas template legacy, status nonaktif atau tanggal berlaku template |
| Estimasi bahan | `material_requirements` membaca BOM terbaru untuk tiap line order, termasuk order lama; respons menyebut revision dan missing BOM ([store.py](../beeloft/store.py)) | Histori BOM immutable tidak berarti estimasi order dibekukan. Perubahan estimasi tidak menulis ulang ledger stok/pemakaian; jangan menyamakannya dengan snapshot tarif transaksi yang disahkan |
| Jenis kerja/kelompok jasa/SKU | Sewing terhubung ke SKU lewat bundle, cutting dan order line; finishing menyimpan checklist ([models.py](../beeloft/models.py), [sewing.sql](../beeloft/sewing.sql)) | Belum master jenis pekerjaan, kelompok jasa, hubungan beberapa pekerjaan per SKU atau template jasa berversi. Beberapa job sewing bukan bukti satu SKU mendukung beberapa jenis pekerjaan |
| Tarif dan histori upah | `SewingJobCreate.cost` menerima total biaya Decimal dua desimal; `create_sewing_job` menyimpan `cost_minor`. `assignee` masih teks, bukan FK employee | Belum basis pcs/lusin, pemilih tarif berdasarkan tanggal, rate revision atau charge employee. Total biaya job bukan tarif per unit; `completed_quantity` bukan otomatis qty layak dibayar |
| Kapasitas | `RoutingStandardSave.minutes_per_unit` dan `save_routing_standard` menyimpan revisi menit per pcs untuk product/stage/work center ([production_capacity.sql](../beeloft/production_capacity.sql), [test_production_capacity.py](../tests/test_production_capacity.py)) | Pertahankan menit standar sebagai input kapasitas tersendiri. Stage/work center bukan pengganti jenis kerja atau kelompok jasa; tarif tidak diturunkan dari menit |
| Biaya aktual | `production_cost` menjumlah konsumsi bahan berharga PO dan total biaya job sewing yang belum direversal, termasuk job open ([test_production_cost.py](../tests/test_production_cost.py)) | Belum charge upah approved. Penyambungan P03/H01/I01 harus mencegah biaya job lama dan charge baru untuk jasa sama dihitung dua kali |

Alur API baseline: `GET/POST /api/products/{product_id}/bom`,
`GET /api/products/{product_id}/bom-history`,
`GET /api/orders/{order_id}/material-requirements`,
`GET/POST /api/products/{product_id}/routing-standards/{stage}` dan
`POST /api/bundles/{bundle_id}/sewing-jobs` ([api.py](../beeloft/api.py)).
Write BOM/routing admin-only; sewing create/complete admin/operator dan reversal
admin-only, ditegakkan `Store._write`. Read memerlukan autentikasi. Izin tersebut
adalah baseline teknis, bukan keputusan role perusahaan D17 untuk tarif upah.

UI Master SKU sudah membuka BOM/form/riwayat; form sewing menerima biaya total
([app.mjs](../beeloft/static/app.mjs): `bomDialog`, `bomForm`, `bomHistoryDialog`,
`sewingJobForm`). Belum UI template jasa/tarif. Inspeksi ini bukan browser
acceptance P01.

## Keputusan dan bukti sebelum implementasi

| Referensi / penentu | Jawaban yang diperlukan |
|---|---|
| M01/M02, D01 / EX01; produksi + pemilik master | Penerimaan ID SKU, unit dasar/konversi, unit usaha serta employee/pihak. Definisi jenis pekerjaan dan kelompok jasa, keunikan kode/scope, hubungan kelompok-pekerjaan-SKU, serta perilaku aktif/nonaktif dan koreksi histori |
| D04 / EX03/EX04; produksi + payroll | Basis tarif pcs/lusin; scope produk/jenis kerja/unit/employee bila diperlukan; currency, presisi nominal dan batas nilai. Pilih tanggal acuan (kirim, realisasi, approval atau lainnya), aturan batas tanggal berlaku, tarif hilang/overlap dan backdate |
| D04; payroll | Hasil yang disetujui untuk 1, 11, 12, 13 pcs, pembulatan pecahan lusin dan uang, mode/skalanya serta tahap per baris/karyawan/periode. Konversi fisik 12 pcs = 1 lusin tidak menentukan upah 13 pcs |
| D04/D05; produksi + payroll | Kapan versi template/tarif dipilih dan dibekukan; pengaruh nonaktif pada job baru, job berjalan, approval tertunda dan koreksi. P03 menentukan qty layak dibayar terpisah dari target/aktual, termasuk reject/rework; P01 tidak menebaknya |
| D13 bersama P03/H01/I01; accounting + payroll | Batas biaya sewing existing dan charge jasa baru; satu sumber nilai untuk costing/payroll, keterkaitan reversal dan larangan menghitung jasa sama dua kali |
| D17 / EX12; pemilik role | Hak baca nominal/histori, tambah/ubah/nonaktif/approve tarif serta scope unit. Jangan mewariskan akses tarif sensitif ke semua pembaca BOM tanpa keputusan |
| F02 / A0 dan A1/A2/A3 | Kontrak domain diterima, fungsi/file bersama dialokasikan dan nomor migrasi ditetapkan dari HEAD integrasi. D18/D19 diperlukan bila template/rate diimpor dari legacy |

Setiap keputusan mencantumkan jawaban, scope, approver, tanggal berlaku dan bukti
aman dipublikasikan. D03 diperlukan bila ada formula lembar/berat/pemakaian;
paket ini tidak menambah formula tersebut atau koreksi target order.

## Kontrak handoff yang diusulkan

Bagian ini **PROPOSED**, bukan endpoint, DDL atau policy yang sudah diterima.
Gunakan kosakata [tarif efektif dan charge F02](f02-shared-contracts.md), lalu
isi keputusan di atas sebelum membekukan nama field/schema:

- P01 menyediakan identitas jenis kerja, kelompok jasa, penerapan beberapa
  pekerjaan pada SKU, revision template dan status/riwayat. Referensi komponen
  bahan tetap menuju versi BOM existing; perubahan jasa tidak mengubah BOM.
- Tarif membawa scope yang disepakati, basis unit, nominal/currency, revision,
  tanggal berlaku dan referensi policy. Interval `[from,to)` adalah usulan F02,
  belum keputusan D04. Missing/overlap harus eksplisit, tanpa fallback diam-diam
  ke nol, rate terakhir atau menit standar.
- P03/H01 menerima revision template/rate dan input kebijakan yang dipakai saat
  finalisasi charge, beserta tanggal acuan, qty layak dibayar dan nominal final.
  Perubahan master setelahnya tidak menghitung ulang transaksi disahkan; koreksi
  mengikuti audit/reversal. Detail titik finalisasi menunggu D04/D05.
- Costing I01 dan payroll H01 membaca charge yang sama. Qty target, aktual dan
  layak dibayar tetap berbeda; menit kapasitas tetap di routing existing.

## Skenario acceptance setelah gerbang terbuka

Semua contoh berikut sintetis. Hasil uang dan kebijakan yang belum diketahui
tetap unresolved, bukan expected value yang boleh dianggap disahkan.

| Kasus | Input / tindakan | Bukti yang harus diperoleh |
|---|---|---|
| Beberapa pekerjaan | SKU `DEMO-SKU` memakai `DEMO-JAHIT` dan `DEMO-PASANG-LABEL`, masing-masing tarif/revision sendiri | Kedua pekerjaan dapat dibaca/dipilih melalui UI/API; penyimpanan satu tidak menimpa yang lain; duplikat sesuai kontrak ditolak server |
| Pcs/lusin | 1, 11, 12, 13 pcs; nominal contoh lusin `120.00` | Qty fisik tetap asal; payable/uang mengikuti expected result D04, termasuk pembulatan per baris vs total. Gunakan `QTY-RATE-01` di fixture F02 |
| Tarif berganti | R1 `120.00` mulai 1 September, R2 `144.00` mulai 16 September; kirim tanggal 15, realisasi tanggal 16, approval tanggal 17 | `RATE-02` di fixture F02; pemilihan mengikuti tanggal acuan D04. Uji sebelum/tepat/setelah batas, job melintasi batas serta backdate sesuai policy |
| Histori disahkan | Finalisasi transaksi dengan R1, simpan R2, ubah template, lalu baca ulang histori dan laporan | Revision/input/nominal final R1 tetap; retry tidak membuat charge ganda; koreksi berjejak tanpa update/delete transaksi asal |
| Tarif hilang/overlap | Tidak ada tarif pada tanggal acuan atau dua interval bertabrakan untuk scope sama | Server dan UI memberi hasil eksplisit sesuai D04; tidak membuat nominal nol atau memilih rate arbitrer. Error tidak meninggalkan mutasi parsial |
| Template nonaktif | Nonaktifkan template/pekerjaan sebelum job baru dan ketika job lama masih berjalan; buka histori dan koreksi | Job baru/approval tertunda mengikuti D01/D04; histori tetap terbaca dan koreksi sah mengikuti policy. Perlakuan tiap state harus disetujui |
| Pemisahan kapasitas/biaya | Ubah tarif tanpa mengubah menit; ubah menit tanpa mengubah tarif | Kapasitas tidak berubah akibat edit upah; histori charge tidak berubah akibat routing; tidak ada perhitungan payroll kedua di costing |

Fixture yang dirujuk: [f02-contracts.json](../tests/fixtures/f02-contracts.json).
`QTY-RATE-01` dan `RATE-02` masih `BLOCKED_F01`; tes validitas fixture tidak
membuktikan acceptance tarif di tabel ini.

Mutasi nanti harus mempertahankan `_write`, actor/role server, idempotency,
revision guard, transaksi atomik dan audit. Uji dua penyimpan bersamaan, retry
key sama/berbeda, revision basi, rollback kegagalan audit serta akses terlarang.
UI perlu pemilihan SKU/pekerjaan yang jelas, riwayat efektif, loading/kosong/error,
retry, keyboard dan pesan tarif hilang/nonaktif. Nomor migrasi belum dipesan;
koordinasikan A0 lalu uji DB baru, upgrade schema 55, rerun, FK/integrity,
control totals qty/uang dan backup/restore sintetis. Jangan mengubah ID/FK,
cost job atau ledger lama untuk memasukkan asumsi tarif.

## Bukti baseline dan handoff

Dari root repo, PowerShell dengan Python 3.12 dan dependencies terpasang:

```powershell
$env:PYTHONPATH = 'tests'
python -m unittest test_f02_contracts test_bom test_sewing_jobs test_production_capacity test_production_cost -v
```

Eksekusi 22 September 2026 dengan Python 3.12.13: **23 tes lulus** dalam
47.454 detik; `uv pip check --python .venv/Scripts/python.exe` lulus untuk
22 package. Tes mencakup BOM, biaya job, kapasitas, costing, izin/retry/revision
serta migrasi baseline; bukan fitur tarif baru. Browser acceptance baru belum
dijalankan karena UI tidak berubah.

Branch: `docs/p01-template-rate-readiness`. File berubah: dokumen ini dan tautan
README. Commit akhir dicatat di PR. Tidak ada perubahan API/model/store/UI/schema,
versi atau dependency. Risiko tersisa: D04/D05 belum disahkan, dependensi master
belum diterima, dan integrasi charge/biaya lama belum ada. Reviewer yang diperlukan:
A1 produksi/payroll, A2 master/biaya, A3 izin/impor bila terkait, A0 kontrak/migrasi
dan pemilik bisnis produksi/payroll. Review dan sign-off masih PENDING; PR draft
dan #48 tetap terbuka sampai dependensi diterima, implementasi dan acceptance
selesai. Merge persiapan ini tidak memenuhi Definition of Done P01.
