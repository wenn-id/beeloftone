-- P01 (#48): jenis pekerjaan, kelompok jasa, template jasa berversi, tarif
-- upah berversi dengan tanggal berlaku, dan histori penerapan template ke SKU.
--
-- Mengikuti pola event-sourced M02 (#44): tabel identitas immutable + tabel
-- *_events append-only, sehingga histori tetap terbaca setelah master atau
-- tarif nonaktif. Kontrak pemilihan tarif/snapshot: docs/p01-rate-resolver.md.
--
-- Asumsi demo (DEMO_ASSUMPTION, D04/D05/D17 belum final):
--  * scope tarif adalah jenis pekerjaan; scope product/employee menunggu D04;
--  * tanggal acuan pemilihan tarif adalah tanggal pekerjaan (bukan kirim/
--    approval), zona Asia/Jakarta;
--  * nominal tarif disimpan SATU kali (amount_minor + rate_basis); nilai lawan
--    selalu derived eksak, bukan dua angka bebas;
--  * menit standar (routing) tetap terpisah dari tarif upah.

BEGIN IMMEDIATE;

-- ---------------------------------------------------------------------------
-- Jenis pekerjaan (work type). Kode stabil dan immutable.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS service_work_types (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL UNIQUE COLLATE NOCASE
        CHECK(code=upper(trim(code)) AND length(code) BETWEEN 1 AND 40),
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS service_work_type_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    work_type_id TEXT NOT NULL REFERENCES service_work_types(id),
    revision INTEGER NOT NULL CHECK(revision>0),
    name TEXT NOT NULL CHECK(name=trim(name) AND length(name) BETWEEN 1 AND 160),
    -- Kelompok jasa opsional; keanggotaan berversi dan terlacak di histori.
    -- Tanpa REFERENCES: validasi relasi ditegakkan di store agar pesan
    -- kesalahan eksplisit (404/422), bukan ABORT generik (mengikuti M01).
    service_group_id TEXT,
    active INTEGER NOT NULL CHECK(active IN (0,1)),
    reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    UNIQUE(work_type_id,revision)
) STRICT;
CREATE INDEX IF NOT EXISTS service_work_type_events_current
    ON service_work_type_events(work_type_id,sequence DESC);

-- ---------------------------------------------------------------------------
-- Kelompok jasa/pekerjaan (service group).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS service_groups (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL UNIQUE COLLATE NOCASE
        CHECK(code=upper(trim(code)) AND length(code) BETWEEN 1 AND 40),
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS service_group_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    group_id TEXT NOT NULL REFERENCES service_groups(id),
    revision INTEGER NOT NULL CHECK(revision>0),
    name TEXT NOT NULL CHECK(name=trim(name) AND length(name) BETWEEN 1 AND 160),
    active INTEGER NOT NULL CHECK(active IN (0,1)),
    reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    UNIQUE(group_id,revision)
) STRICT;
CREATE INDEX IF NOT EXISTS service_group_events_current
    ON service_group_events(group_id,sequence DESC);

-- ---------------------------------------------------------------------------
-- Template jasa: cetakan beberapa komponen pekerjaan yang diterapkan ke SKU.
-- Versi disimpan append-only; perubahan template membuat revisi baru dan
-- TIDAK mengubah penerapan lama (lihat service_template_applications).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS service_templates (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL UNIQUE COLLATE NOCASE
        CHECK(code=upper(trim(code)) AND length(code) BETWEEN 1 AND 40),
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS service_template_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    template_id TEXT NOT NULL REFERENCES service_templates(id),
    revision INTEGER NOT NULL CHECK(revision>0),
    name TEXT NOT NULL CHECK(name=trim(name) AND length(name) BETWEEN 1 AND 160),
    note TEXT NOT NULL CHECK(length(note) <= 1000),
    -- Snapshot komponen: array {work_type_id, work_type_code} saat revisi
    -- dibuat. Kode dibekukan agar histori tetap terbaca setelah work type
    -- diubah namanya/nonaktif (identitas kode immutable).
    components TEXT NOT NULL CHECK(json_valid(components)
        AND json_type(components) = 'array'
        AND json_array_length(components) BETWEEN 1 AND 100),
    active INTEGER NOT NULL CHECK(active IN (0,1)),
    reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    UNIQUE(template_id,revision)
) STRICT;
CREATE INDEX IF NOT EXISTS service_template_events_current
    ON service_template_events(template_id,sequence DESC);

-- ---------------------------------------------------------------------------
-- Tarif upah berversi per jenis pekerjaan. Satu rentang tarif per work type;
-- setiap revisi membawa nominal, basis satuan authoritative, dan interval
-- efektif setengah-terbuka [effective_from, effective_to).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS service_rates (
    id TEXT PRIMARY KEY,
    -- Satu rentang tarif per jenis pekerjaan; scope product/employee menunggu D04.
    work_type_id TEXT NOT NULL UNIQUE REFERENCES service_work_types(id),
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS service_rate_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    rate_id TEXT NOT NULL REFERENCES service_rates(id),
    revision INTEGER NOT NULL CHECK(revision>0),
    -- Basis authoritative nominal tersimpan. Nominal lawan selalu derived
    -- eksak (lihat docs/p01-rate-resolver.md); menirim pcs dan lusin sekaligus
    -- ditolak di validasi.
    rate_basis TEXT NOT NULL CHECK(rate_basis IN ('lusin','pcs')),
    amount_minor INTEGER NOT NULL CHECK(amount_minor > 0),
    currency TEXT NOT NULL CHECK(currency = 'IDR'),
    -- Tanggal bisnis ISO; interval [from, to). NULL effective_to = terbuka.
    effective_from TEXT NOT NULL CHECK(date(effective_from) = effective_from),
    effective_to TEXT CHECK(effective_to IS NULL OR date(effective_to) = effective_to),
    active INTEGER NOT NULL CHECK(active IN (0,1)),
    -- Referensi kebijakan kalkulasi yang dipakai (bisa berubah antar revisi).
    calculation_policy_ref TEXT NOT NULL,
    reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    UNIQUE(rate_id,revision),
    CHECK(effective_to IS NULL OR effective_from < effective_to)
) STRICT;
CREATE INDEX IF NOT EXISTS service_rate_events_current
    ON service_rate_events(rate_id,sequence DESC);
CREATE INDEX IF NOT EXISTS service_rate_events_effective
    ON service_rate_events(rate_id,active,effective_from);

-- ---------------------------------------------------------------------------
-- Histori penerapan template ke SKU (append-only). Versi template dan
-- komponen dibekukan di sini; perubahan template sesudahnya TIDAK mengubah
-- baris lama. bom_revision menghubungkan ke BOM berversi existing ketika
-- penerapan juga menerbitkan revisi BOM (mekanisme #43, bukan ledger kedua).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS service_template_applications (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    product_id TEXT NOT NULL REFERENCES products(id),
    template_id TEXT NOT NULL REFERENCES service_templates(id),
    template_revision INTEGER NOT NULL CHECK(template_revision>0),
    -- Snapshot komponen saat diterapkan: [{work_type_id, work_type_code}].
    components TEXT NOT NULL CHECK(json_valid(components)
        AND json_type(components) = 'array'
        AND json_array_length(components) BETWEEN 1 AND 100),
    -- Sisi bahan: tautan opsional ke template BOM (#43) dan revisi BOM
    -- berversi yang diterbitkannya. Tidak membuat ledger bahan kedua.
    bom_template_id TEXT,
    bom_revision INTEGER,
    reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;
CREATE INDEX IF NOT EXISTS service_template_applications_product
    ON service_template_applications(product_id,sequence DESC);

-- Histori immutable: koreksi/penonaktifan tidak boleh menulis ulang baris lama.
CREATE TRIGGER IF NOT EXISTS service_work_type_events_no_update BEFORE UPDATE ON service_work_type_events
BEGIN SELECT RAISE(ABORT,'service_work_type_events history is immutable'); END;
CREATE TRIGGER IF NOT EXISTS service_work_type_events_no_delete BEFORE DELETE ON service_work_type_events
BEGIN SELECT RAISE(ABORT,'service_work_type_events history is immutable'); END;
CREATE TRIGGER IF NOT EXISTS service_group_events_no_update BEFORE UPDATE ON service_group_events
BEGIN SELECT RAISE(ABORT,'service_group_events history is immutable'); END;
CREATE TRIGGER IF NOT EXISTS service_group_events_no_delete BEFORE DELETE ON service_group_events
BEGIN SELECT RAISE(ABORT,'service_group_events history is immutable'); END;
CREATE TRIGGER IF NOT EXISTS service_template_events_no_update BEFORE UPDATE ON service_template_events
BEGIN SELECT RAISE(ABORT,'service_template_events history is immutable'); END;
CREATE TRIGGER IF NOT EXISTS service_template_events_no_delete BEFORE DELETE ON service_template_events
BEGIN SELECT RAISE(ABORT,'service_template_events history is immutable'); END;
CREATE TRIGGER IF NOT EXISTS service_rate_events_no_update BEFORE UPDATE ON service_rate_events
BEGIN SELECT RAISE(ABORT,'service_rate_events history is immutable'); END;
CREATE TRIGGER IF NOT EXISTS service_rate_events_no_delete BEFORE DELETE ON service_rate_events
BEGIN SELECT RAISE(ABORT,'service_rate_events history is immutable'); END;
CREATE TRIGGER IF NOT EXISTS service_template_applications_no_update BEFORE UPDATE ON service_template_applications
BEGIN SELECT RAISE(ABORT,'service_template_applications history is immutable'); END;
CREATE TRIGGER IF NOT EXISTS service_template_applications_no_delete BEFORE DELETE ON service_template_applications
BEGIN SELECT RAISE(ABORT,'service_template_applications history is immutable'); END;

PRAGMA user_version = 60;

COMMIT;
