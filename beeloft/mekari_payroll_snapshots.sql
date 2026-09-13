CREATE TABLE IF NOT EXISTS mekari_payroll_snapshot_batches (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    sync_run_id TEXT NOT NULL UNIQUE REFERENCES integration_sync_runs(id),
    snapshot_at TEXT NOT NULL,
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS mekari_payroll_snapshot_periods (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    batch_id TEXT NOT NULL REFERENCES mekari_payroll_snapshot_batches(id),
    external_payroll_id TEXT NOT NULL,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL CHECK(period_end>=period_start),
    status TEXT NOT NULL CHECK(status IN ('draft','reviewing','approved','paid','cancelled')),
    currency TEXT NOT NULL CHECK(currency='IDR'),
    employee_count INTEGER NOT NULL CHECK(employee_count BETWEEN 0 AND 1000000),
    gross_pay_minor INTEGER NOT NULL CHECK(gross_pay_minor BETWEEN 0 AND 100000000000000000),
    employee_deductions_minor INTEGER NOT NULL CHECK(employee_deductions_minor BETWEEN 0 AND gross_pay_minor),
    employer_contributions_minor INTEGER NOT NULL CHECK(employer_contributions_minor BETWEEN 0 AND 100000000000000000),
    payment_date TEXT CHECK(payment_date IS NULL OR payment_date>=period_start),
    updated_at TEXT NOT NULL,
    UNIQUE(batch_id,external_payroll_id),
    UNIQUE(batch_id,period_start,period_end),
    CHECK((status='paid' AND payment_date IS NOT NULL)
       OR (status!='paid' AND payment_date IS NULL))
) STRICT;

CREATE INDEX IF NOT EXISTS idx_mekari_payroll_snapshot_batch
    ON mekari_payroll_snapshot_periods(batch_id,period_end DESC,sequence DESC);

CREATE TRIGGER IF NOT EXISTS mekari_payroll_snapshot_batches_no_update
BEFORE UPDATE ON mekari_payroll_snapshot_batches BEGIN
    SELECT RAISE(ABORT,'Mekari payroll snapshot batches are immutable');
END;
CREATE TRIGGER IF NOT EXISTS mekari_payroll_snapshot_batches_no_delete
BEFORE DELETE ON mekari_payroll_snapshot_batches BEGIN
    SELECT RAISE(ABORT,'Mekari payroll snapshot batches are immutable');
END;
CREATE TRIGGER IF NOT EXISTS mekari_payroll_snapshot_periods_no_update
BEFORE UPDATE ON mekari_payroll_snapshot_periods BEGIN
    SELECT RAISE(ABORT,'Mekari payroll snapshot periods are immutable');
END;
CREATE TRIGGER IF NOT EXISTS mekari_payroll_snapshot_periods_no_delete
BEFORE DELETE ON mekari_payroll_snapshot_periods BEGIN
    SELECT RAISE(ABORT,'Mekari payroll snapshot periods are immutable');
END;

PRAGMA user_version=42;
