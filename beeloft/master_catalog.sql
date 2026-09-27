BEGIN IMMEDIATE;
-- Migrasi 56 — M01 master katalog (issue #43): master produk, bahan, dan satuan.
--
-- Prinsip yang dijaga:
-- * ID/SKU/kode existing tidak diubah; kolom klasifikasi baru semuanya nullable
--   sehingga upgrade database lama tidak menulis ulang histori.
-- * "Range" legacy pada UOM disimpan verbatim sebagai metadata (range_text) dengan
--   makna BELUM TERVERIFIKASI — dilarang dipakai sebagai faktor konversi.
-- * Konversi pcs/lusin mengikuti kontrak F02 (beeloft/contracts.py): qty dasar
--   produk selalu pcs integer; lusin adalah tampilan turunan yang eksak.
-- * Satuan bahan (m/kg/mili-presisi) tidak diubah; uom master adalah registri,
--   bukan pengganti CHECK unit pada materials.
-- * created_by NULL = baris seed oleh migrasi sistem (tidak ada akun pengguna
--   yang dapat dirujuk saat migrasi berjalan).

CREATE TABLE IF NOT EXISTS uoms (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL UNIQUE COLLATE NOCASE,
    name TEXT NOT NULL,
    range_text TEXT,
    note TEXT,
    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
    created_by TEXT REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS product_categories (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL UNIQUE COLLATE NOCASE,
    name TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
    created_by TEXT REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS product_subcategories (
    id TEXT PRIMARY KEY,
    category_id TEXT NOT NULL REFERENCES product_categories(id),
    code TEXT NOT NULL UNIQUE COLLATE NOCASE,
    name TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
    created_by TEXT REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;
CREATE INDEX IF NOT EXISTS product_subcategories_category ON product_subcategories(category_id);

CREATE TABLE IF NOT EXISTS product_types (
    id TEXT PRIMARY KEY,
    subcategory_id TEXT NOT NULL REFERENCES product_subcategories(id),
    code TEXT NOT NULL UNIQUE COLLATE NOCASE,
    name TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
    created_by TEXT REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;
CREATE INDEX IF NOT EXISTS product_types_subcategory ON product_types(subcategory_id);

CREATE TABLE IF NOT EXISTS product_series (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL UNIQUE COLLATE NOCASE,
    name TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
    created_by TEXT REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS colors (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL UNIQUE COLLATE NOCASE,
    name TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
    created_by TEXT REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS sizes (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL UNIQUE COLLATE NOCASE,
    name TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
    created_by TEXT REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS material_classes (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL UNIQUE COLLATE NOCASE,
    name TEXT NOT NULL,
    level INTEGER NOT NULL CHECK(level IN (1,2,3)),
    parent_id TEXT REFERENCES material_classes(id),
    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
    created_by TEXT REFERENCES users(id),
    created_at TEXT NOT NULL,
    CHECK((level = 1 AND parent_id IS NULL) OR (level > 1 AND parent_id IS NOT NULL))
) STRICT;
CREATE INDEX IF NOT EXISTS material_classes_parent ON material_classes(parent_id, level);

-- Template bahan: cetakan komponen yang dipakai untuk menerbitkan revisi BOM
-- baru (append-only di bom_revisions). Template tidak menggantikan mekanisme
-- BOM berversi; "apply" selalu membuat revisi baru dengan optimistic locking.
CREATE TABLE IF NOT EXISTS bom_templates (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL UNIQUE COLLATE NOCASE,
    name TEXT NOT NULL,
    product_type_id TEXT REFERENCES product_types(id),
    components TEXT NOT NULL CHECK(json_valid(components)
        AND json_type(components) = 'array'
        AND json_array_length(components) BETWEEN 1 AND 100),
    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
    created_by TEXT REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;

-- Seed satuan dasar. LSN adalah satuan tampilan turunan (12 pcs eksak per
-- kontrak F02), bukan satuan penyimpanan: qty dasar produk tetap pcs.
INSERT INTO uoms(id, code, name, range_text, note, active, created_by, created_at)
SELECT 'uom-m', 'M', 'Meter', NULL, NULL, 1, NULL, strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
WHERE NOT EXISTS (SELECT 1 FROM uoms WHERE code = 'M');
INSERT INTO uoms(id, code, name, range_text, note, active, created_by, created_at)
SELECT 'uom-kg', 'KG', 'Kilogram', NULL, NULL, 1, NULL, strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
WHERE NOT EXISTS (SELECT 1 FROM uoms WHERE code = 'KG');
INSERT INTO uoms(id, code, name, range_text, note, active, created_by, created_at)
SELECT 'uom-pcs', 'PCS', 'Pieces', NULL, 'Satuan dasar produk (kontrak F02: integer pcs).', 1, NULL,
    strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
WHERE NOT EXISTS (SELECT 1 FROM uoms WHERE code = 'PCS');
INSERT INTO uoms(id, code, name, range_text, note, active, created_by, created_at)
SELECT 'uom-lsn', 'LSN', 'Lusin', '12 pcs',
    'Tampilan turunan eksak dari pcs (kontrak F02 pcs_to_lusin); bukan satuan penyimpanan, bukan faktor konversi fisik.',
    1, NULL, strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
WHERE NOT EXISTS (SELECT 1 FROM uoms WHERE code = 'LSN');

-- Kolom klasifikasi produk dan bahan ditambahkan kondisional dari store.py
-- (mengikuti pola migrasi 55) agar pola upgrade-rollback pada test tetap
-- idempoten: kolom nullable, produk/bahan lama tetap valid tanpa klasifikasi.
-- Tanpa REFERENCES (mengikuti pola migrasi 55): validasi relasi ditegakkan di
-- lapisan store agar pesan kesalahannya eksplisit (404/422), bukan ABORT generik.
CREATE INDEX IF NOT EXISTS products_catalog_filter ON products(active, category_id);

-- Harga referensi (minor) terpisah dari harga aktual PO/receipt yang tetap
-- tinggal di purchase_orders; bukan pengganti histori biaya.
CREATE INDEX IF NOT EXISTS materials_catalog_filter ON materials(active, class_id);

-- Trigger lama memblokir SEMUA update pada materials. Identitas bahan
-- (id/kode/nama/satuan/pencatat/waktu) tetap immutable; kolom master baru
-- (klasifikasi, deskripsi, harga referensi, status aktif) boleh diperbarui.
DROP TRIGGER IF EXISTS materials_no_update;
DROP TRIGGER IF EXISTS materials_identity_immutable;
CREATE TRIGGER materials_identity_immutable BEFORE UPDATE ON materials
WHEN OLD.id IS NOT NEW.id
    OR OLD.code IS NOT NEW.code
    OR OLD.name IS NOT NEW.name
    OR OLD.unit IS NOT NEW.unit
    OR OLD.created_by IS NOT NEW.created_by
    OR OLD.created_at IS NOT NEW.created_at
BEGIN
    SELECT RAISE(ABORT, 'Identitas bahan (kode/nama/satuan/pencatat) tidak dapat diubah');
END;

PRAGMA user_version = 56;
COMMIT;
