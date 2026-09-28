# X01 — Kontrak Impor & Dry-Run Importer (Issue #51)

Kontrak versi `X01-20260928-1`. Implementasi: `beeloft/import_contracts.py`
(kontrak murni), `beeloft/import_jobs.sql` (skema 63), `Store.import_dry_run` /
`Store.apply_import_job`, endpoint `/api/import/*`, halaman UI "Impor data".

## Prinsip

1. **Dry-run tidak mengubah apa pun.** POST `/api/import/dry-run` hanya
   memvalidasi dan menyimpan metadata job. Master, stok, jurnal, dan saldo
   tidak tersentuh.
2. **Apply adalah tindakan terpisah** dengan permission server tersendiri
   (`import_data`), Idempotency-Key wajib, dan guard produksi.
3. **Apply per-batch atomik.** Seluruh batch (semua baris + metadata job)
   berjalan dalam satu transaksi tulis: commit hanya bila semua baris sukses;
   satu baris gagal → rollback total, tanpa efek parsial domain maupun
   metadata. Tiap baris tetap dieksekusi lewat fungsi service domain existing
   (bukan insert langsung) — `Store.transaction()` bergabung ke koneksi batch
   yang sama selama apply.
4. **Identitas sumber mengikuti F02**, bukan nama orang/produk:
   `source_namespace()` + `canonical_source_key()` (system, account,
   entity_type, source_id, source_line_id).
5. **Histori/opening balance/transaksi aktif eksplisit** via strategi job;
   tidak ada fallback yang menghitung keduanya (anti double-count).
6. **Domain yang belum tersedia tidak dibuatkan tabel pengganti**:
   payroll → `UNSUPPORTED` (owner #52), POS/AP/template jasa → `NOT_READY`.

## Format CSV

- UTF-8, boleh BOM; delimiter koma; header wajib.
- Maks 10.000 baris, maks 5 MB (lebih dari itu ditolak, tidak di-truncate diam-diam).
- Kolom identitas per baris: `source_id` (wajib), `source_line_id` (opsional),
  `source_revision` (default 1), `row_kind` (`active` | `history` | `opening_balance`).
- Satu job = satu adapter. Contoh header kategori produk:
  `source_id,source_line_id,source_revision,row_kind,code,name`

## Adapter yang working

`uom`, `product_category`, `product_subcategory`, `product_type`,
`product_series`, `color`, `size`, `material_class`, `business_unit`,
`storage`, `position`, `employee`, `customer`, `supplier`, `product`,
`material`.

Catatan khusus:
- Produk: UOM selalu dipaksa `PCS` (kontrak M01); SKU unik.
- Material: unit hanya `m`/`kg`/`pcs`; nominal `reference_price` teks desimal
  → integer minor, negatif ditolak.
- Karyawan: `business_unit_code` dicek terhadap unit scope user (403 bila di
  luar cakupan).
- Supplier: identitas immutable; field `reason` wajib.

## Strategi histori (eksplisit, tanpa fallback)

| Strategi | `row_kind=history` | `row_kind=opening_balance` |
|---|---|---|
| `active_only` | ditolak (`history_not_in_scope`) | ditolak |
| `replay_history` | di-apply sebagai replay eksplisit | ditolak |
| `opening_balance` | diarsipkan sebagai metadata, **tidak pernah** di-apply | di-apply sebagai saldo awal |

## Alur job

1. **Upload / tempel CSV** → pilih adapter, strategi, isi `source_system` +
   `source_account` (identitas sumber, bukan nama).
2. **Dry-run** → server mengembalikan `control_totals`
   (`will_create`/`will_map`/`rejected`/`quarantined`/`archived`) + daftar
   reject terstruktur (`reason` + `fix` per baris).
3. **Preview** → periksa totals dan tabel reject di UI.
4. **Apply** (tombol terpisah, konfirmasi eksplisit) → per-batch atomik.
   Job yang sudah applied di-apply ulang = no-op terverifikasi
   (`idempotent_replay: true`).

## Konflik identitas & revisi

- Upload ulang identitas yang sama dengan payload identik → `will_map`
  (no-op, tidak membuat duplikat).
- Payload berbeda, revisi sama → `source_conflict` (ditolak).
- Revisi lebih tinggi: tanpa `auto_apply_revisions` → `quarantined`
  (`revision_bump_pending_review`); dengan flag aktif → jalur update eksplisit
  memakai idempotency key revision-scoped (tidak bertabrakan dengan key create).
- Hanya baris yang termaterialisasi (mapped/applied) yang mengklaim identitas
  sumber; baris job yang gagal/rollback tidak menghalangi upload ulang.

## Kegagalan apply & resume

- Satu baris gagal → seluruh batch rollback; job dicatat `failed` dengan
  `checkpoint_next_row` = baris yang gagal (observability) + event
  `apply_failed` pada transaksi terpisah.
- Resume = apply ulang **seluruh batch dari awal** (tidak ada efek parsial
  yang perlu dilanjutkan); baris yang gagal dicoba lagi, bukan dilewati
  diam-diam.

## Guard produksi

Apply dan dry-run menolak (403) bila `BEELOFT_PRODUCTION=1` atau nama file
database mengandung `prod`. Importer menyiapkan migrasi, bukan menjalankan
migrasi produksi.

## Batas yang diketahui

- Watermark/delta (`build_watermark`) baru fondasi; cutover inkremental
  menyusul di #61.
- `column_map`, `id_map`, `reference_mode` didukung di kontrak dan dikirim
  dari UI lewat tiga textarea JSON di halaman Impor data (boleh kosong =
  default: header kanonis, mode code).
