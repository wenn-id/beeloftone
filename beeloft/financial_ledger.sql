-- A01 (#46): ledger keuangan dan kontrak posting.
--
-- Buku besar keuangan NATIVE Beeloft One. Terpisah dari ledger kuantitas/
-- operasional existing (movements/balances): jurnal ini mencatat NILAI uang
-- (integer minor, kontrak F02), bukan pcs atau stok fisik. Jangan menduplikasi
-- stok, biaya tenaga kerja, atau snapshot Mekari ke dalam jurnal.
--
-- DEMO_ASSUMPTION (kebijakan demo berversi DEMO-POST-20260928-1):
-- COA sintetis di bawah ini BUKAN kebijakan resmi Beeloft; metode biaya,
-- timing pengakuan, dan pajak belum ditetapkan pemilik accounting (D13/D14).
-- Jangan menyatakan akun/metode di sini sebagai aturan produksi.
--
-- Scope buku/periode: jurnal mencatat business_unit_id opsional sebagai
-- konteks. Unit usaha BELUM tentu badan hukum terpisah; konsolidasi dan
-- eliminasi antar-unit di luar cakupan A01.

BEGIN IMMEDIATE;

-- ---------------------------------------------------------------------------
-- Chart of Accounts
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS coa_accounts (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL UNIQUE CHECK(code=trim(code) AND length(code) BETWEEN 1 AND 20),
    name TEXT NOT NULL CHECK(name=trim(name) AND length(name) BETWEEN 1 AND 160),
    type TEXT NOT NULL CHECK(type IN ('asset','liability','equity','revenue','expense')),
    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;
CREATE INDEX IF NOT EXISTS coa_accounts_type ON coa_accounts(type, code);

-- ---------------------------------------------------------------------------
-- Periode akuntansi
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS accounting_periods (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL UNIQUE CHECK(code=trim(code) AND length(code) BETWEEN 1 AND 20),
    start_date TEXT NOT NULL CHECK(start_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    end_date TEXT NOT NULL CHECK(end_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','closed')),
    revision INTEGER NOT NULL DEFAULT 1 CHECK(revision > 0),
    reason TEXT NOT NULL DEFAULT '' CHECK(reason=trim(reason)),
    closed_by TEXT REFERENCES users(id),
    closed_at TEXT,
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    CHECK(start_date <= end_date)
) STRICT;

-- ---------------------------------------------------------------------------
-- Journal header
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS journals (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    period_id TEXT NOT NULL REFERENCES accounting_periods(id),
    journal_date TEXT NOT NULL CHECK(journal_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    description TEXT NOT NULL CHECK(description=trim(description)
        AND length(description) BETWEEN 1 AND 1000),
    business_unit_id TEXT REFERENCES business_units(id),
    -- Identitas sumber terstruktur (kontrak F02): satu event sumber hanya
    -- boleh terposting sekali. source_line_id '' berarti level header.
    source_system TEXT NOT NULL CHECK(source_system=trim(source_system)
        AND length(source_system) BETWEEN 1 AND 80),
    source_account TEXT NOT NULL CHECK(source_account=trim(source_account)
        AND length(source_account) BETWEEN 1 AND 80),
    source_entity_type TEXT NOT NULL CHECK(source_entity_type=trim(source_entity_type)
        AND length(source_entity_type) BETWEEN 1 AND 80),
    source_id TEXT NOT NULL CHECK(source_id=trim(source_id)
        AND length(source_id) BETWEEN 1 AND 160),
    source_line_id TEXT NOT NULL DEFAULT ''
        CHECK(source_line_id=trim(source_line_id) AND length(source_line_id) <= 160),
    source_revision INTEGER NOT NULL DEFAULT 1 CHECK(source_revision > 0),
    -- Referensi kebijakan/aturan posting yang dipakai (mis. DEMO-POST-20260928-1
    -- atau revisi aturan produksi kelak). Wajib tercatat untuk audit.
    policy_ref TEXT NOT NULL CHECK(policy_ref=trim(policy_ref)
        AND length(policy_ref) BETWEEN 1 AND 80),
    -- Reversal bertaut: reversal_of menunjuk jurnal asal. Jurnal asal tidak
    -- boleh diedit/dihapus; koreksi hanya lewat reversal baru.
    reversal_of TEXT UNIQUE REFERENCES journals(id),
    reversal_reason TEXT NOT NULL DEFAULT '' CHECK(reversal_reason=trim(reversal_reason)),
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    UNIQUE(source_system, source_account, source_entity_type,
           source_id, source_line_id, source_revision)
) STRICT;
CREATE INDEX IF NOT EXISTS journals_period ON journals(period_id, journal_date);
CREATE INDEX IF NOT EXISTS journals_source ON journals(source_system, source_account,
    source_entity_type, source_id);

-- ---------------------------------------------------------------------------
-- Journal lines: nilai uang integer minor (kontrak F02). Tepat satu sisi
-- (debit ATAU kredit) positif per baris; jurnal posted wajib total debit =
-- total kredit secara eksak (dicek di lapisan aplikasi dalam transaksi).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS journal_lines (
    id TEXT PRIMARY KEY,
    journal_id TEXT NOT NULL REFERENCES journals(id) ON DELETE RESTRICT,
    line_no INTEGER NOT NULL CHECK(line_no > 0),
    account_id TEXT NOT NULL REFERENCES coa_accounts(id),
    debit_minor INTEGER NOT NULL DEFAULT 0 CHECK(debit_minor >= 0),
    credit_minor INTEGER NOT NULL DEFAULT 0 CHECK(credit_minor >= 0),
    description TEXT NOT NULL DEFAULT '' CHECK(description=trim(description)),
    CHECK((debit_minor > 0) != (credit_minor > 0)),
    UNIQUE(journal_id, line_no)
) STRICT;
CREATE INDEX IF NOT EXISTS journal_lines_account ON journal_lines(account_id);

-- ---------------------------------------------------------------------------
-- Guardrail: jurnal tidak dapat diubah/dihapus setelah tercatat.
-- Koreksi hanya melalui jurnal reversal baru (reversal_of). Pengecualian
-- tunggal: pengisian reversal_of (NULL -> id jurnal asal) segera setelah
-- jurnal reversal dibuat — ini penautan, bukan pengeditan isi.
-- ---------------------------------------------------------------------------
CREATE TRIGGER IF NOT EXISTS journals_no_update
BEFORE UPDATE ON journals
WHEN NOT (OLD.reversal_of IS NULL AND NEW.reversal_of IS NOT NULL
    AND OLD.code=NEW.code AND OLD.period_id=NEW.period_id
    AND OLD.journal_date=NEW.journal_date AND OLD.description=NEW.description
    AND OLD.business_unit_id IS NEW.business_unit_id
    AND OLD.source_system=NEW.source_system AND OLD.source_account=NEW.source_account
    AND OLD.source_entity_type=NEW.source_entity_type AND OLD.source_id=NEW.source_id
    AND OLD.source_line_id=NEW.source_line_id AND OLD.source_revision=NEW.source_revision
    AND OLD.policy_ref=NEW.policy_ref AND OLD.created_by=NEW.created_by
    AND OLD.created_at=NEW.created_at)
BEGIN
    SELECT RAISE(ABORT, 'Jurnal tidak dapat diubah. Buat jurnal reversal baru.');
END;

CREATE TRIGGER IF NOT EXISTS journals_no_delete
BEFORE DELETE ON journals
BEGIN
    SELECT RAISE(ABORT, 'Jurnal tidak dapat dihapus. Buat jurnal reversal baru.');
END;

CREATE TRIGGER IF NOT EXISTS journal_lines_no_update
BEFORE UPDATE ON journal_lines
BEGIN
    SELECT RAISE(ABORT, 'Baris jurnal tidak dapat diubah.');
END;

CREATE TRIGGER IF NOT EXISTS journal_lines_no_delete
BEFORE DELETE ON journal_lines
BEGIN
    SELECT RAISE(ABORT, 'Baris jurnal tidak dapat dihapus.');
END;

-- COA: kode boleh dinonaktifkan, identitas (kode/nama/tipe) tidak berubah.
CREATE TRIGGER IF NOT EXISTS coa_accounts_no_identity_update
BEFORE UPDATE ON coa_accounts
WHEN NEW.code <> OLD.code OR NEW.name <> OLD.name OR NEW.type <> OLD.type
BEGIN
    SELECT RAISE(ABORT, 'Identitas akun (kode/nama/tipe) tidak dapat diubah. Hanya status aktif.');
END;

PRAGMA user_version=59;

COMMIT;
