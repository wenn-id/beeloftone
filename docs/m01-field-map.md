# M01 — Kamus Field Legacy → Target (Issue #43)

Pemetaan bukti lapangan F01 ke model master katalog M01. Hanya mencakup
ruang lingkup #43: produk, bahan, klasifikasi, satuan, harga referensi, dan
pemetaan BOM. Unit usaha, lokasi, pihak, employee, position, dan metode bayar
adalah ruang lingkup #44.

## Prinsip

- **ID/SKU/kode stabil**: nilai yang sudah dipakai transaksi tidak diubah.
  Nonaktifkan (active=0), jangan hapus fisik.
- **Produk dihitung dalam PCS**. Lusin (`LSN`) hanya tampilan turunan eksak:
  `pcs_to_lusin()` / `lusin_to_pcs()` dari `beeloft/contracts.py` (F02).
  13 pcs = 13/12 lusin; round-trip kembali ke 13 pcs.
- **Bahan memakai unit/presisi existing** (`m`, `kg`, `pcs`; `quantity_milli`
  integer, m/kg maks 3 desimal, pcs wajib bulat). Tidak ada konversi paksa.
- **Legacy `Range` hanya metadata** (`uoms.range_text`, verbatim) dengan
  makna belum terverifikasi — bukan faktor konversi.
- **Harga referensi bahan** (`materials.reference_price_minor`, IDR) terpisah
  dari harga aktual PO/receipt dan histori biaya (`material_price_insights`
  hanya membaca PO yang sudah di-approve).
- **Template bahan** memakai BOM berversi existing (`bom_revisions`,
  append-only, optimistic lock `expected_revision`).

## Produk

| Legacy (F01)              | Target M01                              | Catatan |
|---------------------------|-----------------------------------------|---------|
| SKU                       | `products.sku` (UNIQUE NOCASE)          | Immutable, tidak diubah migrasi 56 |
| Nama                      | `products.name`                         | Dapat diubah |
| Warna (teks bebas)        | `products.color` (legacy) + `colors` master + `products.color_id` | Teks lama dipertahankan; master baru opsional |
| Ukuran (teks bebas)       | `products.size` (legacy) + `sizes` master + `products.size_id` | Sama seperti warna |
| —                         | `product_categories` → `product_subcategories` → `product_types` | Hierarki wajib konsisten; subkategori harus di bawah kategori terpilih |
| —                         | `product_series`                        | Seri produk opsional |
| —                         | `products.uom_code` DEFAULT `PCS`       | Selain PCS ditolak 422 |
| —                         | `products.active` DEFAULT 1             | Nonaktif memblokir order/BOM baru (422); riwayat tetap terbaca |

## Bahan

| Legacy (F01)              | Target M01                              | Catatan |
|---------------------------|-----------------------------------------|---------|
| Kode bahan                | `materials.code` (UNIQUE NOCASE)        | Immutable |
| Nama                      | `materials.name`                        | Dapat diubah |
| Satuan (`m`/`kg`/`pcs`)   | `materials.unit` (CHECK tetap)          | Tidak diubah; bukan pcs |
| —                         | `material_classes` (level 1–3) + `materials.class_id` | Level 1 tanpa parent; level 2–3 wajib punya parent |
| —                         | `materials.description`                 | Deskripsi bebas |
| Harga acuan (jika ada)    | `materials.reference_price_minor` (IDR) | Minor unit; `null` bila belum ada. Independen dari harga PO aktual |
| —                         | `materials.active` DEFAULT 1            | Nonaktif memblokir BOM/template/PR/receipt baru (422); riwayat tetap |

## Satuan

| Legacy (F01)              | Target M01                              | Catatan |
|---------------------------|-----------------------------------------|---------|
| Satuan pcs/lusin/meter/kg | `uoms` (seed: `PCS`, `LSN`, `M`, `KG`)  | Seed migrasi 56 |
| Kolom "Range" lama        | `uoms.range_text`                       | Verbatim; makna belum terverifikasi, bukan faktor konversi |
| Lusin                     | `uoms.code='LSN'`                       | Display turunan eksak dari pcs; tidak dapat dipilih sebagai satuan produk |

## Template BOM

| Konsep                    | Target M01                              | Catatan |
|---------------------------|-----------------------------------------|---------|
| Cetakan komponen bahan    | `bom_templates` (code unik, komponen JSON, `product_type_id` opsional) | Komponen memvalidasi bahan aktif + presisi unit |
| Penerapan ke SKU          | `POST /api/bom-templates/{id}/apply`    | Menerbitkan revisi baru di `bom_revisions`; template bertipe hanya untuk produk bertipe sama |
| Revisi BOM                | `bom_revisions` (existing, append-only) | `expected_revision` untuk optimistic lock; apply identik ditolak 409 |

## Status & validasi

- Master nonaktif: tulis baru yang mereferensikannya → 422/409; baca
  histori tidak terpengaruh.
- Klasifikasi yang dinonaktifkan setelah dipakai: tetap terbaca di produk
  lama; edit metadata lain (nama/status) tidak terhalang; referensi *baru*
  ke klasifikasi nonaktif ditolak.
- Seluruh tulis master katalog: admin-only (operator/viewer → 403); baca:
  authenticated.
