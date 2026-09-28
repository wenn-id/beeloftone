# Handoff X01 — Kontrak Impor & Dry-Run Importer (Issue #51)

## Ringkasan

Kontrak impor CSV + dry-run importer untuk persiapan migrasi data legacy.
Dry-run tidak mengubah data domain; apply adalah tindakan terpisah,
per-batch atomik, lewat service domain existing, dengan guard produksi.

- **Base:** `72e408d2` (`origin/main`, 28 Sep 2026) — setelah P03 #52 (#124).
- **Final:** branch `feat/x01-dry-run-importer-51` di atas `72e408d2`
  (implementasi + perbaikan lanjutan; detail commit tercatat di PR).
- **Skema DB:** 63 (`beeloft/import_jobs.sql`).
  - Rebuild `user_permissions`: nilai `import_data` ditambahkan ke CHECK.
  - Tabel metadata baru: `import_jobs`, `import_job_rows`, `import_job_events`
    (immutable via trigger). Tidak ada tabel domain pengganti.
- **Versi:** 0.121.0 (`pyproject.toml`, `FastAPI(version=...)`,
  `docs/openapi.json` — 316 paths / 137 schemas).

## Adapter yang working (16)

`uom`, `product_category`, `product_subcategory`, `product_type`,
`product_series`, `color`, `size`, `material_class`, `business_unit`,
`storage`, `position`, `employee`, `customer`, `supplier`, `product`,
`material`.

## Format CSV

UTF-8 (BOM boleh), delimiter koma, header wajib; maks 10.000 baris / 5 MB
(ditolak bila lebih, tidak di-truncate diam-diam). Kolom identitas per baris:
`source_id` (wajib), `source_line_id`, `source_revision` (default 1),
`row_kind` (`active`|`history`|`opening_balance`). Satu job = satu adapter.
Seluruh fixture dan contoh sintetis; tidak ada data nyata.

## Keputusan atomicity: per-batch atomik

`Store._import_batch()` membuka satu transaksi tulis untuk seluruh apply.
`Store.transaction()` bergabung ke koneksi batch yang sama bila dipanggil di
dalamnya (thread-local, hanya aktif selama apply impor), sehingga panggilan
service domain via `_write()` tetap lewat jalur normal (role check,
idempotency, audit) tetapi commit/rollback sebagai satu kesatuan:

- Semua baris sukses → commit (termasuk metadata job + receipt idempotency).
- Satu baris gagal → rollback total; tidak ada efek parsial domain maupun
  metadata. Kegagalan dicatat sebagai event `apply_failed` + status `failed`
  dengan `checkpoint_next_row` (observability) pada transaksi terpisah.
- Resume = apply ulang seluruh batch dari awal; baris gagal dicoba lagi
  (tidak dilewati diam-diam). Job applied yang di-apply ulang = no-op
  terverifikasi (`idempotent_replay`).

Perilaku di luar batch tidak berubah: flag thread-local hanya diisi oleh
importer, sehingga 1300+ tes existing tidak terpengaruh (terverifikasi full
suite).

## Yang belum didukung (sengaja)

- `payroll`, `payroll_cash_receipt` → `UNSUPPORTED`, owner #52.
- `pos_invoice`, `pos_payment`, `ap_settlement`, `service_template` →
  `NOT_READY`. Tidak dibuatkan tabel pengganti.
- Watermark/delta (`build_watermark`) baru fondasi kontrak; **cutover
  inkremental bukan bagian issue ini — menyusul di #61.**

## Tes

- `tests/test_x01_importer.py`: 49 tes (kontrak murni, dry-run, apply,
  konflik/revisi, guard produksi, permission, API).
- `tests/test_permissions.py`: diperbarui (10 permission, skema 63,
  gate UI `import_data`).
- Full suite: **1354 tes OK** via `~/workspace/.venv-beeloft`
  (`python -m unittest discover -s tests`, 28 Sep 2026).

## Sign-off

- Sign-off bisnis (termasuk business acceptance F02 A1/A2/A3): **PENDING**,
  tidak dikarang.
- PR dibuat sebagai **DRAFT**, tidak di-merge otomatis.

## Handoff ke #61

Fondasi yang bisa dipakai #61: `import_jobs`/`import_job_rows` menyimpan
`watermark_json`; `build_watermark()` tersedia di kontrak; identitas sumber
F02 konsisten (`source_namespace`/`canonical_source_key`). Yang belum ada:
logika delta/cutover, adapter POS/AP/payroll, dan UI mapping kolom lanjutan.
