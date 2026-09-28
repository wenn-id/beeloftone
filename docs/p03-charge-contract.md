# P03: kontrak service charge upah jasa

Kontrak ini mendefinisikan **service charge** `p03_service_charges` — satu-satunya
sumber nilai upah jasa untuk konsumen downstream: **H01** [#55](https://github.com/wenn-id/beeloftone/issues/55)
(payroll native) dan **I01** [#53](https://github.com/wenn-id/beeloftone/issues/53) (costing/valuasi).
Skema dan aturan di bawah adalah kontrak stabil: implementasi P03 [#52](https://github.com/wenn-id/beeloftone/issues/52)
mengikuti ini, dan konsumen diharapkan membaca persis bentuk ini.

## 1. Tujuan: satu sumber nilai

- `p03_service_charges` adalah **SATU-SATUNYA** sumber nilai upah jasa untuk
  payroll (#55) dan costing (#53).
- Konsumen **DILARANG** menghitung ulang upah dari master tarif (`service_rate_events`)
  atau dari snapshot tarif lain. Nominal authoritative hanya `final_amount_minor`
  pada baris charge.
- P03 tidak membuat payroll, slip gaji, atau posting jurnal; P03 hanya membuat
  charge jasa dari realisasi yang disetujui, lalu mengunci nilainya selamanya.

## 2. Skema `p03_service_charges`

Schema 61 (`beeloft/employee_jobs.sql`). Tabel `STRICT`; tanpa kolom nullable
yang bebas — setiap kolom nullable punya makna kontrak (lihat tabel).

| Field | Tipe | Keterangan |
|---|---|---|
| `id` | TEXT PK | ID charge, format `CHG-<12 hex>` |
| `source_namespace` | TEXT NOT NULL | Selalu `p03.service_charge` (charge reversal: `p03.service_charge.reversal`) |
| `source_id` | TEXT NOT NULL | `job_id` sumber charge |
| `source_line_id` | TEXT NOT NULL | `realization_id` sumber charge |
| `employee_id` | TEXT NOT NULL | FK `workforce_employees(id)` |
| `sku` | TEXT NOT NULL | SKU produk yang dikerjakan (label costing) |
| `work_type_id` | TEXT NOT NULL | FK `service_work_types(id)` |
| `job_id` | TEXT NOT NULL | FK `p03_jobs(id)` |
| `realization_id` | TEXT NOT NULL | FK `p03_job_realizations(id)` |
| `payable_qty_pcs` | INTEGER NOT NULL | Kuantitas dibayar (pcs); reversal menyimpan nilai negatif |
| `rate_snapshot` | TEXT NOT NULL | JSON snapshot tarif (lihat §4); reversal menambahkan `reversal_of` + `reversal_reason` |
| `template_version` | TEXT NULL | Saat ini NULL; slot kontrak untuk versi template saat dikerjakan |
| `calculation_policy_ref` | TEXT NOT NULL | Referensi policy perhitungan, demo: `DEMO-P03-20260928-1` |
| `final_amount_minor` | INTEGER NOT NULL | Nominal final (minor IDR, integer); SATU sumber nilai konsumen |
| `approved_at` | TEXT NOT NULL | Timestamp UTC persetujuan realisasi |
| `approved_by` | TEXT NOT NULL | FK `users(id)` yang menyetujui (SoD: bukan pembuat realisasi) |
| `reversal_of_charge_id` | TEXT NULL | NULL untuk charge normal; terisi = charge ini reversal dari ID tersebut |
| `consumed_by` | TEXT NULL | Mekanisme klaim: konsumen mengisi saat memakai charge (lihat §9) |
| `created_at` | TEXT NOT NULL | Timestamp insert |

`UNIQUE (source_namespace, source_id, source_line_id)` — satu realisasi = tepat
satu charge (lihat §6). Guardrail imutabilitas: trigger SQL menolak `UPDATE` dan
`DELETE` langsung pada tabel ini; koreksi hanya via reversal bertaut (§7).
Realisasi yang sudah `approved`/`rejected` juga terkunci (trigger) — tidak dapat
diubah langsung; koreksinya lewat reversal charge.

## 3. Source identity terstruktur

Tiap charge membawa identitas sumber kanonikal tiga kolom:

- `source_namespace` = `p03.service_charge` (konstanta `Store.P03_SOURCE_NAMESPACE`)
- `source_id` = `job_id`
- `source_line_id` = `realization_id`

Kombinasi ketiganya `UNIQUE` di DB: *satu realization/work component tidak
ditagih dua kali*, dijamin di lapisan tulis, bukan di fungsi hitung.

**Beda dari Idempotency-Key request.** Header `Idempotency-Key` (RequestKey) adalah
identitas *request* jaringan: retry request yang sama mengembalikan respons
sebelumnya tanpa mengeksekusi ulang. Source identity adalah identitas *sumber
bisnis*: approval replay untuk sumber yang sama (mis. double-click tombol
approve, atau dua admin menyetujui bersamaan) mengembalikan charge **existing**
tanpa membuat charge baru (§6). Keduanya orthogonal dan sama-sama diimplementasi.

## 4. Isi `rate_snapshot` (JSON)

Snapshot tarif dibekukan pada saat approval dari resolver P01
(`docs/p01-rate-resolver.md` § "Shape `Store.resolve_service_rate()`") plus
`snapshot_at`. Field wajib minimal:

```jsonc
{
  "work_type_id": "…uuid…",
  "work_type_code": "DEMO-JAHIT",          // immutable
  "work_type_name": "Jahit",               // label saat approval
  "rate_revision": "DEMO-JAHIT#2",         // ref immutable "<kode>#<revision>"
  "rate_revision_number": 2,              // immutable
  "rate_basis": "lusin",                  // basis authoritative nominal tersimpan
  "amount_minor": 2500000,                // nominal pada rate_basis (minor)
  "currency": "IDR",
  "effective_from": "2026-09-01",         // immutable
  "effective_to": null,                   // immutable; null = terbuka
  "rate_per_lusin_minor": 2500000,        // derived eksak; basis kalkulasi authoritative
  "calculation_policy_ref": "DEMO-P03-20260928-1",
  "effective_date": "2026-09-27",         // tanggal acuan yang dipakai memilih
  "timezone": "Asia/Jakarta",             // zona tanggal bisnis
  "snapshot_at": "2026-09-28T08:30:12.345678Z"
}
```

`rate_per_lusin_minor` adalah basis kalkulasi authoritative: basis `'lusin'` →
`amount_minor`; basis `'pcs'` → `amount_minor * 12`. Tidak ada nominal ganda
yang disimpan bebas; pecahan per pcs selalu derived eksak (`Fraction`), bukan
kolom tersimpan.

Perubahan master setelah finalisasi (revisi tarif baru, tarif nonaktif, work type
nonaktif) **tidak** membatalkan snapshot transaksi lama dan **tidak** menghitung
ulang charge yang sudah ada.

## 5. Aturan perhitungan

Upah dihitung oleh **satu** fungsi murni `beeloft.contracts.wage_for_realization`:

```
wage_for_realization(pcs=payable_qty_pcs,
                     rate_per_lusin_minor=<dari snapshot>,
                     rate_revision=<dari snapshot>,
                     policy=DEMO-P03-20260928-1)
```

Kontrak aritmatika (lihat `contracts.py`):

1. Eksak sampai akhir: `upah = pcs × rate_per_lusin / 12` dihitung sebagai integer
   `pcs * rate_per_lusin_minor / 12` (pecahan berulang dipertahankan, mis. 13/12
   pcs tetap 13/12 sampai akhir).
2. **SATU pembulatan di akhir**: hasil dibulatkan sekali ke kelipatan
   `policy.wage_rounding_multiple_minor` (demo: 100 minor = Rp1) dengan mode
   `policy.wage_money_rounding` (`HALF_UP`, `wage_rounding_stage="final_per_realization"`).
3. Tidak ada Decimal perantara yang memotong pecahan berulang.

Output fungsi: `pcs`, `lusin_exact` (string Fraction), `rate_per_lusin_minor`,
`rate_revision`, `wage_minor`, `calculation_policy_ref`, `rounding_mode`.

### Contoh charge lengkap (fiktif, angka sintetis)

Realisasi `RLZ-FAKE12345678` pada job `JOB-FAKE87654321`, karyawan `KAR-001`
(Jahit, revisi `DEMO-JAHIT#2`, tarif 25.000/lusin = 2.500.000 minor):

- `payable_qty_pcs` = 481
- `481 × 2.500.000 / 12` = 1.002.083,33… minor (pecahan 481/12)
- satu pembulatan HALF_UP ke kelipatan 100 → 1.002.100 minor

```json
{
  "id": "CHG-FAKEA1B2C3D4",
  "source_namespace": "p03.service_charge",
  "source_id": "JOB-FAKE87654321",
  "source_line_id": "RLZ-FAKE12345678",
  "employee_id": "KAR-001",
  "sku": "DEMO-KEMEJA-M",
  "work_type_id": "wt-uuid-jahit",
  "job_id": "JOB-FAKE87654321",
  "realization_id": "RLZ-FAKE12345678",
  "payable_qty_pcs": 481,
  "rate_snapshot": {
    "work_type_id": "wt-uuid-jahit",
    "work_type_code": "DEMO-JAHIT",
    "work_type_name": "Jahit",
    "rate_revision": "DEMO-JAHIT#2",
    "rate_revision_number": 2,
    "rate_basis": "lusin",
    "amount_minor": 2500000,
    "currency": "IDR",
    "effective_from": "2026-09-01",
    "effective_to": null,
    "rate_per_lusin_minor": 2500000,
    "calculation_policy_ref": "DEMO-P03-20260928-1",
    "effective_date": "2026-09-27",
    "timezone": "Asia/Jakarta",
    "snapshot_at": "2026-09-28T08:30:12.345678Z"
  },
  "template_version": null,
  "calculation_policy_ref": "DEMO-P03-20260928-1",
  "final_amount_minor": 1002100,
  "approved_at": "2026-09-28T08:30:12.400000Z",
  "approved_by": "user-admin-1",
  "reversal_of_charge_id": null,
  "consumed_by": null,
  "created_at": "2026-09-28T08:30:12.405000Z"
}
```

## 6. Aturan replay / idempotency

Approval realisasi hanya valid dari status `submitted` → `approved`; SoD:
penyetuju tidak boleh penyetuju pengajuan sendiri (`_guard_self_approval`).

- **Approval replay untuk sumber yang sama** (realisasi sudah `submitted`, charge
  untuk `(namespace, job_id, rid)` sudah ada) → kembalikan charge **existing**,
  bukan HTTP 409 dan bukan duplikat. Respons identik dengan approval pertama.
- **Concurrent approval** → satu pemenang insert; yang kalah kena
  `sqlite3.IntegrityError` dari constraint `UNIQUE`, lalu mengambil charge
  existing dan mengembalikannya (pola try-insert → fetch-existing di
  `Store.approve_job_realization`).
- `GET /api/service-charges/by-source?namespace=…&source_id=…&source_line_id=…`
  tersedia untuk lookup eksplisit sebelum approval ulang (404 bila belum ada).

Retry request jaringan tetap ditangani Idempotency-Key seperti endpoint lain
(§3) — lapisan terpisah dari source identity bisnis.

## 7. Aturan koreksi: reversal bertaut

Charge **immutable**: trigger DB menolak update/delete langsung. Koreksi hanya
via **reversal bertaut**:

1. `POST /api/service-charges/{charge_id}/reverse` membuat charge **baru**
   dengan `reversal_of_charge_id` = charge asli, `final_amount_minor` negatif
   (kebalikan persis nominal asli), `payable_qty_pcs` negatif, namespace
   `p03.service_charge.reversal`, dan snapshot yang diperkaya
   `reversal_of` + `reversal_reason`.
2. Charge asli dan reversal **tidak boleh di-reversal lagi** (satu level saja;
   double reversal ditolak 409).
3. **`reason` wajib diisi** (422 bila kosong).
4. Jika `consumed_by` terisi → reversal **ditolak 409**: charge sudah diklaim
   konsumen (payroll/costing), koreksi menjadi tanggung jawab mekanisme
   konsumen. Realisasi yang direversal tidak dibuka kembali.

Semantik untuk konsumen: nilai efektif = `SUM(final_amount_minor)` per sumber,
dengan charge reversal membatalkan tepat satu charge asli. **Jangan**
memfilter reversal secara diam-diam; agregasi harus menyertakan keduanya.

## 8. Asumsi DEMO (DEMO_ASSUMPTION — BUKAN keputusan bisnis final)

Policy `DEMO-P03-20260928-1` (`Store.P03_DEMO_POLICY_REF`, `contracts.DEMO_POLICY`)
mencakup asumsi berikut. Semua ini adalah asumsi demo dan menunggu keputusan
bisnis; **bukan aturan final**:

(a) **Tanggal acuan tarif = `work_date` realisasi** (zona `Asia/Jakarta`), bukan
    tanggal approval. Resolver memakai interval `[effective_from, effective_to)`;
    nol kandidat → 422 eksplisit, overlap → 409 eksplisit (tidak ada fallback
    diam-diam; lihat `docs/p01-rate-resolver.md`).

(b) **Realisasi approved dibayar penuh**: `payable_qty_pcs = qty_pcs` realisasi.
    Tidak ada potongan parsial atau kualitas parsial pada layer ini.

(c) **Realisasi rejected = tidak dibayar, tanpa charge.** Reject wajib menyertakan
    `reason`; status menjadi `rejected` dan terkunci.

(d) **Rework = realisasi baru pada job yang sama.** Tarif di-resolve ulang pada
    tanggal rework (dapat menghasilkan snapshot revisi berbeda dari realisasi
    sebelumnya); tidak ada pembaruan tarif retroaktif pada charge lama.

(e) **Pembulatan HALF_UP ke rupiah penuh (kelipatan 100 minor) di akhir per
    realisasi** — satu pembulatan, satu realisasi satu charge; tidak ada
    pembulatan per lusin, per pcs, atau per potongan intermediate.

Label: setiap charge demo membawa `calculation_policy_ref = "DEMO-P03-20260928-1"`,
sehingga konsumen tahu persis asumsi mana yang dipakai dan bisa diganti per
versi kebijakan tanpa mengubah kode.

## 9. Handoff eksplisit untuk #53 (costing) dan #55 (payroll)

### Untuk #53 — valuasi/costing

- Baca `p03_service_charges.final_amount_minor` per `(sku, work_type_id, periode)`
  sebagai input biaya jasa produksi. Agregasi harus menyertakan reversal
  (nilai efektif = SUM per sumber).
- **Jangan re-resolve tarif** dari master dan **jangan** menghitung ulang dari
  `rate_snapshot` — snapshot hanya untuk audit/traceability, bukan untuk
  perhitungan ulang.
- Periode = `approved_at` (UTC); charge reversal jatuh di periode approval-nya
  sendiri, bukan periode charge asli.

### Untuk #55 — payroll

- Agregat `final_amount_minor` per `employee_id` per periode **dari charge yang
  belum di-reversal** (net per karyawan; reversal mengurangi tepat pada charge
  yang dibatalkannya).
- Hanya charge yang belum di-reversal dan belum diklaim yang diambil ke payroll
  run; mekanisme klaim di bawah mencegah double-count antar run.

### Mekanisme klaim `consumed_by`

`consumed_by` adalah kolom klaim: konsumen **mengisinya saat memakai charge**
(mis. `payroll-run#<id>` atau `costing-run#<id>`) untuk menandai charge sudah
diserap. Detail update dan concurrency klaim diatur di issue masing-masing
(#53, #55). Konsekuensi kontrak: charge dengan `consumed_by` terisi **tidak
dapat di-reversal** (§7 ayat 4) — koreksi setelah konsumsi menjadi tanggung
jawab konsumen.

### Masking nominal

Baca charge (`GET`, list, by-source) memisahkan akses nominal: tanpa permission
`view_salary`, `rate_snapshot` dan `final_amount_minor` dikembalikan `null`.
Konsumen mesin memakai kredensial berizin sesuai perannya.

## 10. Endpoint terkait

13 endpoint API (tag `Employee Jobs`, `beeloft/api.py`):

| # | Method & path | Store | Permission |
|---|---|---|---|
| 1 | `POST /api/employee-jobs` | `create_employee_job` | `create_transaction` |
| 2 | `GET /api/employee-jobs` | `list_employee_jobs` | (autentikasi) |
| 3 | `GET /api/employee-jobs/{job_id}` | `get_employee_job` | (autentikasi) |
| 4 | `PATCH /api/employee-jobs/{job_id}` | `update_employee_job` (optimistic `expected_revision`) | `create_transaction` |
| 5 | `POST /api/employee-jobs/{job_id}/realizations` | `create_job_realization` | `create_transaction` |
| 6 | `PATCH /api/employee-jobs/{job_id}/realizations/{rid}` | `update_job_realization` (optimistic `expected_revision`) | `create_transaction` |
| 7 | `POST /api/employee-jobs/{job_id}/realizations/{rid}/submit` | `submit_job_realization` (draft→submitted) | `create_transaction` |
| 8 | `POST /api/employee-jobs/{job_id}/realizations/{rid}/approve` | `approve_job_realization` (**membuat charge**) | `approve_transaction` |
| 9 | `POST /api/employee-jobs/{job_id}/realizations/{rid}/reject` | `reject_job_realization` (`reason` wajib) | `approve_transaction` |
| 10 | `POST /api/service-charges/{charge_id}/reverse` | `reverse_service_charge` (`reason` wajib) | `approve_transaction` |
| 11 | `GET /api/service-charges` | `list_service_charges` (filter `employee_id`, `job_id`) | (autentikasi) |
| 12 | `GET /api/service-charges/by-source` | `find_charge_by_source` (query `namespace`, `source_id`, `source_line_id`) | (autentikasi) |
| 13 | `GET /api/service-charges/{charge_id}` | `get_service_charge` | (autentikasi) |

Catatan rute: `by-source` didaftarkan sebelum `/{charge_id}` agar tidak tertangkap
sebagai path param. Semua request tulis mendukung `Idempotency-Key`.

## Batas cakupan

- P03 tidak mencatat stok/produksi (`sewing_jobs` dsb. tetap satu-satunya
  pencatatan produksi); job karyawan adalah penugasan kerja, bukan pencatatan
  ganda.
- `remaining_qty_pcs` selalu derived (`target − SUM(approved,submitted) −
  adjustments`), bukan kolom bebas.
- D04 (scope tarif product/employee) belum final: scope tarif saat ini jenis
  pekerjaan; lihat `docs/f01-owner-decisions.md` D04 dan `docs/p01-rate-resolver.md`.
- Kewajiban sign-off bisnis tetap terbuka: asumsi DEMO di §8 menunggu keputusan
  final pemilik; perubahan kebijakan versi baru tidak menyentuh charge lama.
