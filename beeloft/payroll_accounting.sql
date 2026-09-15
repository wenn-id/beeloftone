BEGIN IMMEDIATE;

CREATE TABLE IF NOT EXISTS mekari_payroll_snapshot_postings (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    period_id TEXT NOT NULL UNIQUE REFERENCES mekari_payroll_snapshot_periods(id),
    status TEXT NOT NULL CHECK(status IN ('draft','posted','reversed')),
    journal_reference TEXT NOT NULL CHECK(journal_reference=trim(journal_reference) AND length(journal_reference) BETWEEN 1 AND 160),
    posting_date TEXT,
    debit_total_minor INTEGER NOT NULL CHECK(debit_total_minor BETWEEN 1 AND 100000000000000000),
    credit_total_minor INTEGER NOT NULL CHECK(credit_total_minor BETWEEN 1 AND 100000000000000000),
    updated_at TEXT NOT NULL,
    CHECK((status='draft' AND posting_date IS NULL)
       OR (status IN ('posted','reversed') AND posting_date IS NOT NULL))
) STRICT;

CREATE INDEX IF NOT EXISTS mekari_payroll_snapshot_posting_status
    ON mekari_payroll_snapshot_postings(status,sequence DESC);

CREATE TRIGGER IF NOT EXISTS mekari_payroll_snapshot_postings_no_update
BEFORE UPDATE ON mekari_payroll_snapshot_postings
BEGIN SELECT RAISE(ABORT,'Mekari payroll accounting snapshots are immutable'); END;
CREATE TRIGGER IF NOT EXISTS mekari_payroll_snapshot_postings_no_delete
BEFORE DELETE ON mekari_payroll_snapshot_postings
BEGIN SELECT RAISE(ABORT,'Mekari payroll accounting snapshots are immutable'); END;

PRAGMA user_version=53;
COMMIT;
