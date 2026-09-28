-- M02 (#44): unit usaha, storage/lokasi, pihak (customer/supplier), employee,
-- position dan metode pembayaran. Skema event-sourced mengikuti pola workforce:
-- tabel identitas immutable + tabel *_events berversi, sehingga histori tetap
-- terbaca setelah master nonaktif.
--
-- Asumsi demo (DEMO_ASSUMPTION, D01/D17 belum final):
--  * kode unit global unik; kode storage unik per unit (nama sama di unit
--    berbeda tetap bisa dibedakan);
--  * position dibuat terpisah dari department dan TIDAK dihubungkan otomatis;
--  * metode pembayaran adalah master konfigurasi saja, tidak mengeksekusi
--    pembayaran nyata.

BEGIN IMMEDIATE;

-- ---------------------------------------------------------------------------
-- Business unit
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS business_units (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL UNIQUE COLLATE NOCASE
        CHECK(code=upper(trim(code)) AND length(code) BETWEEN 1 AND 40),
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS business_unit_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    unit_id TEXT NOT NULL REFERENCES business_units(id),
    revision INTEGER NOT NULL CHECK(revision>0),
    name TEXT NOT NULL CHECK(name=trim(name) AND length(name) BETWEEN 1 AND 160),
    active INTEGER NOT NULL CHECK(active IN (0,1)),
    reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    UNIQUE(unit_id,revision)
) STRICT;
CREATE INDEX IF NOT EXISTS business_unit_events_current
    ON business_unit_events(unit_id,sequence DESC);

-- ---------------------------------------------------------------------------
-- Storage / gudang / lokasi. business_unit_id adalah bagian identitas yang
-- immutable: hubungan unit dieksplisitkan sekali saat buat dan tidak boleh
-- dipindah secara diam-diam.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS storages (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL CHECK(code=upper(trim(code)) AND length(code) BETWEEN 1 AND 40),
    business_unit_id TEXT NOT NULL REFERENCES business_units(id),
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    -- Kode unik PER unit: "GUDANG-A" di dua unit adalah dua lokasi berbeda.
    UNIQUE(code,business_unit_id)
) STRICT;

CREATE TABLE IF NOT EXISTS storage_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    storage_id TEXT NOT NULL REFERENCES storages(id),
    revision INTEGER NOT NULL CHECK(revision>0),
    name TEXT NOT NULL CHECK(name=trim(name) AND length(name) BETWEEN 1 AND 160),
    kind TEXT NOT NULL CHECK(kind IN ('warehouse','retail','production','other')),
    active INTEGER NOT NULL CHECK(active IN (0,1)),
    reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    UNIQUE(storage_id,revision)
) STRICT;
CREATE INDEX IF NOT EXISTS storage_events_current
    ON storage_events(storage_id,sequence DESC);

-- Catatan: keunikan kode storage per unit dijaga UNIQUE(code,business_unit_id)
-- di atas; keunikan NAMA per unit dijaga di _write (cek pada storage_events
-- terbaru) karena kolom nama hidup di tabel event, bukan di tabel identitas.

-- ---------------------------------------------------------------------------
-- Customer (pihak). Hanya data yang dibutuhkan proses: nama + kontak/alamat
-- opsional. Tidak ada nomor identitas pribadi.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS customers (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL UNIQUE COLLATE NOCASE
        CHECK(code=upper(trim(code)) AND length(code) BETWEEN 1 AND 40),
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS customer_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    customer_id TEXT NOT NULL REFERENCES customers(id),
    revision INTEGER NOT NULL CHECK(revision>0),
    name TEXT NOT NULL CHECK(name=trim(name) AND length(name) BETWEEN 1 AND 160),
    contact TEXT NOT NULL CHECK(contact=trim(contact) AND length(contact) BETWEEN 0 AND 500),
    address TEXT NOT NULL CHECK(address=trim(address) AND length(address) BETWEEN 0 AND 1000),
    active INTEGER NOT NULL CHECK(active IN (0,1)),
    reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    UNIQUE(customer_id,revision)
) STRICT;
CREATE INDEX IF NOT EXISTS customer_events_current
    ON customer_events(customer_id,sequence DESC);

-- ---------------------------------------------------------------------------
-- Position / jabatan. Sengaja TIDAK ada kolom department: position dan
-- department adalah dua hal berbeda dan tidak disamakan otomatis (D17/EX17).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS positions (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL UNIQUE COLLATE NOCASE
        CHECK(code=upper(trim(code)) AND length(code) BETWEEN 1 AND 40),
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS position_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    position_id TEXT NOT NULL REFERENCES positions(id),
    revision INTEGER NOT NULL CHECK(revision>0),
    name TEXT NOT NULL CHECK(name=trim(name) AND length(name) BETWEEN 1 AND 160),
    active INTEGER NOT NULL CHECK(active IN (0,1)),
    reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    UNIQUE(position_id,revision)
) STRICT;
CREATE INDEX IF NOT EXISTS position_events_current
    ON position_events(position_id,sequence DESC);

-- ---------------------------------------------------------------------------
-- Metode pembayaran: master konfigurasi. Tidak ada eksekusi pembayaran,
-- tidak ada akun/rekening nyata (D11/D12 belum final).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS payment_methods (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL UNIQUE COLLATE NOCASE
        CHECK(code=upper(trim(code)) AND length(code) BETWEEN 1 AND 40),
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS payment_method_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    payment_method_id TEXT NOT NULL REFERENCES payment_methods(id),
    revision INTEGER NOT NULL CHECK(revision>0),
    name TEXT NOT NULL CHECK(name=trim(name) AND length(name) BETWEEN 1 AND 160),
    kind TEXT NOT NULL CHECK(kind IN ('cash','bank_transfer','qris','ewallet','other')),
    active INTEGER NOT NULL CHECK(active IN (0,1)),
    reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    UNIQUE(payment_method_id,revision)
) STRICT;
CREATE INDEX IF NOT EXISTS payment_method_events_current
    ON payment_method_events(payment_method_id,sequence DESC);

-- ---------------------------------------------------------------------------
-- Supplier: tambah status aktif. Kolom additive dengan default 1 sehingga
-- supplier existing menjadi aktif tanpa mengubah identitas/baris lama.
-- Trigger imutabilitas F02 diganti agar hanya kolom aktif yang dapat diubah;
-- identitas (kode/nama/kontak/alamat) tetap terkunci.
-- ALTER dan DROP/CREATE trigger dijalankan lewat runner Python (guard kolom)
-- karena ADD COLUMN tidak idempoten: test membangun skema lengkap lalu
-- memutar balik user_version untuk mensimulasikan DB lama.
-- ---------------------------------------------------------------------------

-- ---------------------------------------------------------------------------
-- Employee: tautan position + business_unit, dan mapping ID employee legacy.
-- Ditambahkan ke tabel event (bukan identitas) agar perubahan terekam versi.
-- ALTER dijalankan lewat runner Python (guard kolom) — ADD COLUMN tidak
-- idempoten saat test membangun skema lengkap lalu memutar balik user_version.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS workforce_employee_legacy_ids (
    id TEXT PRIMARY KEY,
    employee_id TEXT NOT NULL REFERENCES workforce_employees(id),
    legacy_id TEXT NOT NULL CHECK(length(trim(legacy_id)) BETWEEN 1 AND 160),
    source_system TEXT NOT NULL CHECK(length(trim(source_system)) BETWEEN 1 AND 160),
    reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    UNIQUE(legacy_id,source_system)
) STRICT;
CREATE INDEX IF NOT EXISTS workforce_employee_legacy_ids_employee
    ON workforce_employee_legacy_ids(employee_id);

-- Job sewing: assignee teks tetap (makloon/vendor), internal boleh menautkan
-- employee_id stabil. Relasi ke payroll dibaca lewat ID, bukan nama bebas.
-- PO: unit usaha tempat pembelian berlangsung (opsional; payload lama tetap
-- sah). Kedua ALTER dijalankan lewat runner Python dengan guard kolom.
-- ---------------------------------------------------------------------------

-- ---------------------------------------------------------------------------
-- Pemetaan lokasi teks existing -> identitas storage stabil. Overlay baca:
-- tabel transaksi TIDAK diubah, saldo dan riwayat pergerakan utuh. Backfill
-- hanya mencatat pemetaan deterministik; kasus ambigu dibiarkan pending
-- dan dipetakan secara eksplisit oleh admin.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS storage_location_mappings (
    id TEXT PRIMARY KEY,
    storage_id TEXT REFERENCES storages(id),
    source_table TEXT NOT NULL CHECK(length(trim(source_table)) BETWEEN 1 AND 160),
    source_column TEXT NOT NULL CHECK(length(trim(source_column)) BETWEEN 1 AND 160),
    source_ref TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    match_status TEXT NOT NULL CHECK(match_status IN ('pending','confirmed','ambiguous')),
    match_basis TEXT NOT NULL CHECK(match_basis IN ('none','unique_name','explicit','ambiguous_name')),
    reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    UNIQUE(source_table,source_column,source_ref)
) STRICT;
CREATE INDEX IF NOT EXISTS storage_location_mappings_status
    ON storage_location_mappings(match_status);
CREATE INDEX IF NOT EXISTS storage_location_mappings_storage
    ON storage_location_mappings(storage_id);

-- Tabel ini sengaja tanpa trigger immutability: pemetaan eksplisit harus
-- bisa memperbarui baris pending/ambiguous menjadi confirmed. Jejak
-- persetujuan (siapa/kapan/mengapa) dijaga oleh audit_events melalui _write,
-- sama seperti master lain; raw_text tetap menyimpan teks asli sebagai bukti.

PRAGMA user_version=57;
COMMIT;
