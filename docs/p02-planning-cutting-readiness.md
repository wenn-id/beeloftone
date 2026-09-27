# P02: kesiapan parity planning dan cutting

Persiapan [#49](https://github.com/wenn-id/beeloftone/issues/49), diperiksa pada
22 September 2026, commit `fc5858e0d5baef39e251f79a6c44b1f53e3e323a`,
v0.97.0/schema 55. **BLOCKED_M01_F02: belum implementasi parity atau business accepted.**

#43 (M01) dan #41 (F02) masih terbuka. [M01](m01-master-readiness.md) baru
memetakan kesiapan; [F02](f02-shared-contracts.md) masih DRAFT dengan sign-off
PENDING. D02/D03 dan contoh EX02 dalam [F01](f01-decisions-evidence.md) belum
disahkan. Issue #49 mensyaratkan penerimaan dependensi sebelum implementasi;
PR #77/#79 yang merged tidak membuka gerbang itu. Perubahan ini memperkuat
tes perilaku existing dan menyiapkan handoff, bukan menetapkan formula cutting.

## Pemetaan HEAD

| Area | Baseline dan sumber | Gap terhadap P02 |
|---|---|---|
| Target planning | `OrderCreate` menerima baris SKU dengan integer pcs, PIC akun aktif dan tenggat. `_create_order` mengisi saldo `planned`; target adalah jumlah qty line ([models.py](../beeloft/models.py), [store.py](../beeloft/store.py)) | Belum draft/release/approval awal planning atau revisi target/partial cancellation. PIC user bukan employee M02 |
| Status order | `_order` menghitung `active`, `completed`, `closed_with_reject` dari saldo warehouse/reject; overdue dari tenggat | Status turunan WIP bukan status persetujuan planning. `planned` adalah tahap saldo, bukan bukti order telah disetujui |
| Perubahan/approval | Admin bisa mengubah PIC/tenggat langsung dengan revision dan alasan. Admin/operator dapat mengajukan perubahan; keputusan `submitted` ke `approved/rejected/cancelled`, approval memakai `_apply_order_change` dan guard revisi order ([test_order_changes.py](../tests/test_order_changes.py), [test_unified_approvals.py](../tests/test_unified_approvals.py)) | Approval hanya perubahan PIC/tenggat. Tidak mencakup target, komposisi, pemakaian atau pengesahan cutting; perlu D02/D17 untuk scope dan pemisahan tugas |
| Bahan aktual/waste | `create_cutting_run` memakai satu issue dari order yang sama, `_consume_material` dan `_transfer` untuk setiap output; satu transaksi `_write` ([cutting.sql](../beeloft/cutting.sql)) | Tetap gunakan ledger tersebut. Belum multi-issue per run atau alokasi bahan/waste per ukuran; kebutuhan itu harus dibuktikan F01 |
| Satuan/parameter | Bahan `m/kg/pcs`, string Decimal sampai tiga desimal; bahan pcs dan output SKU wajib bulat. Unit berasal dari bahan pada issue, bukan input unit cutting | Belum jumlah rol, berat tambahan, lembar, komposisi model sebagai parameter rencana atau setelan per lembar. Tidak ada rumus konversi bahan ke pcs; jangan menurunkannya dari label |
| Referensi PO | Detail batch mendapat `purchase_order_id/reference` melalui receipt PO bila tersedia; run menunjuk issue/batch ([store.py](../beeloft/store.py): `_material_batch`, `_cutting_run`) | Bukan referensi PO langsung pada planning/cutting. D03 harus menentukan apakah PO pembelian bahan, pesanan pelanggan atau dokumen lain; batch manual boleh tanpa PO pada baseline |
| Detail/ekspor | `cuttingForm` dan `cuttingRunDialog` menampilkan bahan, unit, used/waste, output SKU/ukuran, bundle dan reversal ([app.mjs](../beeloft/static/app.mjs)). `/api/activity.csv` mengekspor event order/pergerakan/kendala ([activity.sql](../beeloft/activity.sql), [reports.py](../beeloft/reports.py)) | CSV aktivitas memuat output sebagai movement, bukan laporan cutting lengkap: tidak ada parameter operasional, issue/batch, used/waste atau hubungan run. Acceptance detail/ekspor P02 belum terpenuhi |

Jalur API existing: `POST /api/orders`, `POST /api/orders/{order_id}/changes`,
`POST /api/orders/{order_id}/change-requests`,
`POST /api/production-change-requests/{request_id}/decisions`,
`GET/POST /api/orders/{order_id}/cutting-runs`,
`GET /api/cutting-runs/{run_id}`, `POST /api/cutting-runs/{run_id}/reverse`
([api.py](../beeloft/api.py)). Order/direct change admin-only; cutting create
admin/operator, reversal admin-only; read harus terautentikasi. Pemohon boleh
membatalkan pengajuan sendiri, approval/reject oleh admin. Ini baseline teknis,
bukan sign-off matriks role perusahaan.

## Keputusan yang diperlukan

| Referensi / penentu | Jawaban dan bukti aman dipublikasikan |
|---|---|
| D02 / EX02; produksi + planner | State planning, siapa mengajukan/menyetujui/melepas ke cutting, titik penguncian target dan komposisi. Buktikan kebutuhan perubahan target setelah WIP atau partial cancellation sebelum menambahkannya; tetapkan saldo yang boleh berubah serta audit/reversal |
| D03 / EX02; produksi + gudang bahan | Arti setiap kolom rol/berat/lembar/setelan, unit/presisi/batas, wajib/opsional, input atau hasil hitung; contoh campuran model/ukuran dengan hasil per baris yang disetujui. Tetapkan formula dan pembulatan, termasuk sisa layak pakai vs waste |
| D03; produksi + pembelian | Jenis dan identitas PO yang dimaksud, relasi ke order/run/batch, wajib atau opsional, PO hilang/nonaktif, satu atau beberapa PO. Jangan menganggap reference teks sebagai FK valid |
| M01/F02, D01 | Penerimaan ID SKU/bahan, satuan dasar dan konversi berversi. Rol/lembar tidak diberi faktor tetap secara spekulatif; histori unit dan input asal harus dapat ditelusuri |
| D16/D17; pemilik laporan/role | Kolom detail/ekspor, filter, tanggal acuan, perlakuan run corrected dan format hasil; hak baca/catat/approve/koreksi/ekspor serta scope unit |
| A0 bersama A1/A2/A3 | Kontrak lintas domain diterima, pembagian fungsi/file bersama dan nomor migrasi dari HEAD integrasi. D18/D19 diperlukan bila planning/cutting legacy diimpor |

Semua jawaban menyebut scope, approver, tanggal berlaku dan referensi bukti.
Qty target, output aktual dan qty layak dibayar tetap terpisah; P02 tidak
menentukan upah atau formula reject/rework P03/H01.

## Rekonsiliasi sintetis yang dapat dijalankan sekarang

Tes existing `test_multi_size_output_and_rollback_when_one_size_is_short` dalam
[test_cutting.py](../tests/test_cutting.py) diperkuat tanpa menambah jumlah tes.
Fixture menyiapkan 30 pcs ukuran M dan 10 pcs ukuran L di tahap cutting,
mengeluarkan 3.000 m bahan, kemudian mencatat used 2.125 m dan waste 0.375 m.
Output 40 pcs adalah input aktual fixture, **bukan hasil rumus meter ke pcs**.

| Titik pemeriksaan | Hasil baseline yang diuji |
|---|---|
| Output terakhir melebihi saldo satu pcs | 409; seluruh order tetap identik, unreported 3.000 m, tidak ada cutting run. Output diurutkan menurut line ID seperti normalisasi API agar kegagalan terjadi setelah baris pertama diproses |
| Simpan dan retry key sama | Respons identik; output M=30/L=10, saldo sewing tiap line sama dengan target, jumlah seluruh saldo tahap tiap line tetap target |
| Rekonsiliasi bahan | 3.000 = 2.125 used + 0.375 waste + 0.500 unreported. Unreported adalah sisa pencatatan, bukan verifikasi bahan fisik masih tersedia |
| Stok rak | Tetap 1.000 m setelah cutting: fixture batch 10.000 m sebelumnya mengeluarkan 6.000 m ke order lain dan 3.000 m ke order campuran. Tidak ada pengurangan stok kedua |
| Reversal dan retry | Respons identik; order kembali ke keadaan sebelum run, used/waste net nol, unreported 3.000 m, stok rak tetap 1.000 m. Histori output 40 pcs tetap terbaca dengan tautan reversal pada setiap output |

Tes cutting lain mencakup role, bahan pcs pecahan, beda order, penggunaan
berlebih, race, rollback receipt, larangan reversal terpisah, backup dan migrasi.
[Tes consumption](../tests/test_consumption.py) memeriksa presisi/nilai invalid;
[tes material](../tests/test_materials.py) menolak unit `roll` pada master.
Baseline tidak bisa mengenali angka yang secara semantik kg tetapi dimasukkan
sebagai m: input cutting mengikuti unit issue. Validasi konversi operasional
baru menunggu kontrak D03; tes lama tidak membuktikan acceptance formula baru.

## Acceptance setelah dependensi diterima

1. Implementasikan state/approval planning sesuai D02. Uji larangan operasi
   sebelum status yang disahkan, revisi basi, approval bersamaan dan pembatalan.
   Perubahan target/partial cancellation hanya bila dibutuhkan F01, dengan
   konservasi qty per line dan jejak audit, bukan overwrite saldo WIP.
2. Tambahkan parameter D03 pada kontrak/model/UI dan penyimpanan berversi yang
   disepakati. Uji contoh EX02, pecahan/overflow, unit salah, field wajib hilang,
   komposisi campuran dan referensi PO invalid. Expected result per baris serta
   pembulatan berasal dari contoh disetujui, bukan hanya total agregat.
3. Catat konsumsi dan output melalui transaksi existing. Pertahankan batas
   unreported dan saldo cutting, idempotency, actor/role server, audit dan
   rollback atomik. Retry key sama stabil; key berbeda/reference duplikat tidak
   membuat run ganda. Uji salah satu ukuran kurang setelah ukuran lain diproses.
4. Reversal mengoreksi seluruh output dan konsumsi sekaligus. Bundle aktif atau
   saldo sewing yang sudah bergerak dapat memblokirnya; rollback harus utuh.
   Jangan mengartikan reversal pencatatan sebagai pengembalian stok fisik.
5. Detail dan ekspor memuat parameter operasional, unit, input/hasil, output
   tiap SKU, issue/batch/PO sesuai kontrak, actor/revision serta status reversal.
   Rekonsiliasi ekspor dengan detail dan ledger; histori corrected tetap terbaca
   tetapi tidak dihitung sebagai output aktif. Uji akses, filter/paginasi,
   kosong/error/retry, keyboard dan keamanan CSV.
6. Koordinasikan schema dengan A0; nomor belum dipesan. Uji DB baru, upgrade
   schema 55/rerun, FK/integrity, saldo per line/batch, control totals dan
   backup/restore. Run lama tanpa parameter baru tetap terbaca tanpa default
   operasional tebakan; pertahankan konsumsi/pergerakan lama yang tidak terikat run.

## Verifikasi dan handoff

Dari root repo, Python 3.12 dengan dependencies terpasang, PowerShell:

```powershell
$env:PYTHONPATH = 'tests'
python -m unittest test_f02_contracts test_cutting test_consumption test_materials test_order_changes test_unified_approvals test_activity_export test_bundles -v
```

Eksekusi 22 September 2026 dengan Python 3.12.13: **43 tes lulus** dalam
82.173 detik. `uv pip check --python .venv/Scripts/python.exe` lulus untuk
22 package. Browser acceptance tidak dijalankan karena UI tidak berubah;
hasil tes baseline bukan sign-off EX02.

Branch: `docs/p02-planning-cutting-readiness`. File berubah: dokumen ini,
README dan `tests/test_cutting.py`. Commit akhir dicatat di PR. Runtime
API/model/store/UI, dependency, v0.97.0/schema 55 tidak berubah. Risiko tersisa:
kontrak planning/parameter/PO/ekspor dan formula D02/D03 belum disahkan.
Reviewer yang diperlukan: A1 produksi, A2 bahan/PO/stok, A3 ekspor/QA/izin,
A0 kontrak/migrasi serta pemilik produksi/gudang. Review/sign-off **PENDING**;
PR draft dan #49 tetap terbuka sampai dependensi diterima, implementasi parity
selesai dan acceptance disahkan. Merge persiapan ini bukan penyelesaian P02.

## Implementasi #49 (27 September 2026)

Branch `feat/p02-planning-cutting-49`. Schema **57 (provisional, dikoordinasikan
dengan #44/A0 saat rebase)**. Status: draft → approved → closed; cutting hanya
untuk rencana approved; approval satu langkah oleh admin dengan revision guard.
Kode rencana = referensi order (1:1 dengan order).

### Field mapping: manual vs dihitung

| Field | Sumber | Keterangan |
|---|---|---|
| `plan_code` | dihitung | = `orders.reference` |
| `plan.note`, `plan.start_date` | manual (opsional) | form order |
| `plan.status` / `revision` / `approved_by` | dihitung | transisi approve/close via API admin |
| target per SKU | dihitung | snapshot `order_lines.quantity` |
| realisasi per SKU | dihitung | arus bersih movement cutting→sewing (netto koreksi) |
| sisa target | dihitung | target − realisasi |
| `cut_date` | manual (wajib) | tanggal cutting |
| `po_reference` | manual (opsional) | bila diisi, divalidasi ke `purchase_orders` (bukan cancelled) |
| `weight_kg` | manual (opsional) | berat total, maks 3 desimal |
| `rolls[].roll_no/weight_kg/sheets/note` | manual (opsional) | nomor rol unik per run; tiap baris wajib berat atau lembar |
| `output_params[].setelan_per_lembar` | manual (opsional) | pcs per lembar (integer ≥ 1) |
| `output_params[].product_weight_gram` | manual (opsional) | berat produk per pcs, gram, maks 3 desimal |
| `output_params[].material_used_gram` | manual (opsional) | pemakaian aktual bahan per SKU, gram, maks 3 desimal |
| estimasi pcs per SKU | dihitung | total lembar × setelan/lembar; **estimasi berlabel**, bukan aktual |
| `estimate_basis` | dihitung | `policy_ref="DEMO-20260928-1"` + rumus |
| output aktual (pcs) | manual (wajib) | input eksplisit; tercatat ke ledger existing tepat sekali |
| used/waste bahan | manual (wajib) | input eksplisit via issue, maks 3 desimal |

Qty layak bayar **tidak** dibuat; P02 tidak menghitung payroll/upah.

### Asumsi demo & batas produksi

- Aturan demo ditandai `DEMO_ASSUMPTION`, dibungkus `ContractPolicy`
  `DEMO-20260928-1`; lihat tabel DA-01..DA-09 di
  [f02-shared-contracts.md](f02-shared-contracts.md#asumsi-demo-sementara-demo_assumption).
- Estimasi berat produk tidak menjadi konsumsi/waste otomatis.
- Tidak ada konversi kg↔meter.
- Over-output (melebihi saldo cutting) ditolak; concurrent request aman via
  idempotency-key + guard saldo atomik.
- Reversal run cutting: ditolak bila ada bundle aktif atau output sudah
  terkoreksi terpisah; bila lolos, koreksi konsumsi + seluruh output atomik dan
  realisasi rencana kembali turun (netto).
- Run lama (pra-57) tetap terbaca tanpa parameter baru; tidak ada default
  operasional tebakan.
- PO bersifat opsional; batch manual tanpa PO tetap didukung.
- Order lama di-backfill sebagai rencana `approved` (grandfathered); order baru
  mulai dari `draft`.

### Bukti

- `tests/test_planning_cutting.py`: 20 tes (lifecycle rencana, gate cutting,
  parameter, estimasi, target/realisasi/sisa, idempotency, over-output,
  reversal, PO, CSV, migrasi 56→57).
- `GET /api/orders/{id}/plan`, `POST .../plan/approve|close`,
  `GET /api/orders/{id}/cutting-runs/export.csv`.
