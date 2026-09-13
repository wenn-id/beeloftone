CREATE TABLE IF NOT EXISTS mekari_receivable_snapshot_batches (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    sync_run_id TEXT NOT NULL UNIQUE REFERENCES integration_sync_runs(id),
    snapshot_at TEXT NOT NULL,
    as_of TEXT NOT NULL,
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS mekari_receivable_snapshot_records (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    batch_id TEXT NOT NULL REFERENCES mekari_receivable_snapshot_batches(id),
    external_receivable_id TEXT NOT NULL,
    reference TEXT NOT NULL COLLATE NOCASE,
    external_customer_id TEXT NOT NULL,
    customer_name TEXT NOT NULL,
    invoice_date TEXT NOT NULL,
    due_date TEXT NOT NULL CHECK(due_date>=invoice_date),
    status TEXT NOT NULL CHECK(status IN ('open','partially_paid','paid','void')),
    currency TEXT NOT NULL CHECK(currency='IDR'),
    original_amount_minor INTEGER NOT NULL CHECK(original_amount_minor BETWEEN 1 AND 100000000000000000),
    received_amount_minor INTEGER NOT NULL CHECK(received_amount_minor BETWEEN 0 AND original_amount_minor),
    updated_at TEXT NOT NULL,
    UNIQUE(batch_id,external_receivable_id),
    UNIQUE(batch_id,external_customer_id,reference),
    CHECK((status='open' AND received_amount_minor=0)
       OR (status='partially_paid' AND received_amount_minor>0 AND received_amount_minor<original_amount_minor)
       OR (status='paid' AND received_amount_minor=original_amount_minor)
       OR (status='void' AND received_amount_minor=0))
) STRICT;

CREATE INDEX IF NOT EXISTS idx_mekari_receivable_snapshot_batch_due
    ON mekari_receivable_snapshot_records(batch_id,due_date,sequence);
CREATE INDEX IF NOT EXISTS idx_mekari_receivable_snapshot_customer
    ON mekari_receivable_snapshot_records(batch_id,external_customer_id);

CREATE TRIGGER IF NOT EXISTS mekari_receivable_snapshot_batches_no_update
BEFORE UPDATE ON mekari_receivable_snapshot_batches BEGIN
    SELECT RAISE(ABORT,'Mekari receivable snapshot batches are immutable');
END;
CREATE TRIGGER IF NOT EXISTS mekari_receivable_snapshot_batches_no_delete
BEFORE DELETE ON mekari_receivable_snapshot_batches BEGIN
    SELECT RAISE(ABORT,'Mekari receivable snapshot batches are immutable');
END;
CREATE TRIGGER IF NOT EXISTS mekari_receivable_snapshot_records_no_update
BEFORE UPDATE ON mekari_receivable_snapshot_records BEGIN
    SELECT RAISE(ABORT,'Mekari receivable snapshot records are immutable');
END;
CREATE TRIGGER IF NOT EXISTS mekari_receivable_snapshot_records_no_delete
BEFORE DELETE ON mekari_receivable_snapshot_records BEGIN
    SELECT RAISE(ABORT,'Mekari receivable snapshot records are immutable');
END;

PRAGMA user_version=41;
