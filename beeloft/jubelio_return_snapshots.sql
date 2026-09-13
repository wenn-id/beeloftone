CREATE TABLE IF NOT EXISTS jubelio_return_snapshot_batches (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    sync_run_id TEXT NOT NULL UNIQUE REFERENCES integration_sync_runs(id),
    snapshot_at TEXT NOT NULL,
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS jubelio_return_snapshot_records (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    batch_id TEXT NOT NULL REFERENCES jubelio_return_snapshot_batches(id),
    external_return_id TEXT NOT NULL,
    external_return_reference TEXT NOT NULL COLLATE NOCASE,
    external_order_id TEXT NOT NULL,
    external_order_reference TEXT NOT NULL,
    marketplace TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('requested','in_transit','received','refunded','rejected','cancelled')),
    updated_at TEXT NOT NULL,
    refund_amount_minor INTEGER NOT NULL CHECK(refund_amount_minor BETWEEN 0 AND 100000000000000),
    CHECK((status='refunded' AND refund_amount_minor>0) OR (status<>'refunded' AND refund_amount_minor=0)),
    UNIQUE(batch_id,external_return_id),
    UNIQUE(batch_id,external_return_reference)
) STRICT;

CREATE TABLE IF NOT EXISTS jubelio_return_snapshot_lines (
    id TEXT PRIMARY KEY,
    return_id TEXT NOT NULL REFERENCES jubelio_return_snapshot_records(id),
    product_id TEXT NOT NULL REFERENCES products(id),
    external_id TEXT NOT NULL,
    external_sku TEXT NOT NULL COLLATE NOCASE,
    quantity INTEGER NOT NULL CHECK(quantity BETWEEN 1 AND 1000000000),
    UNIQUE(return_id,product_id),
    UNIQUE(return_id,external_id),
    UNIQUE(return_id,external_sku)
) STRICT;

CREATE TABLE IF NOT EXISTS jubelio_return_quarantine_records (
    id TEXT PRIMARY KEY,
    batch_id TEXT NOT NULL REFERENCES jubelio_return_snapshot_batches(id),
    external_return_id TEXT NOT NULL,
    external_return_reference TEXT NOT NULL,
    external_order_reference TEXT NOT NULL,
    marketplace TEXT NOT NULL,
    status TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    payload_json TEXT NOT NULL CHECK(json_valid(payload_json)),
    issue TEXT NOT NULL CHECK(issue IN ('unmapped','mapping_mismatch')),
    detail TEXT NOT NULL CHECK(length(trim(detail)) BETWEEN 1 AND 1000),
    UNIQUE(batch_id,external_return_id),
    UNIQUE(batch_id,external_return_reference)
) STRICT;

CREATE INDEX IF NOT EXISTS idx_jubelio_return_snapshot_batch
    ON jubelio_return_snapshot_records(batch_id,sequence);
CREATE INDEX IF NOT EXISTS idx_jubelio_return_snapshot_product
    ON jubelio_return_snapshot_lines(product_id,return_id);
CREATE INDEX IF NOT EXISTS idx_jubelio_return_quarantine_batch
    ON jubelio_return_quarantine_records(batch_id);

CREATE TRIGGER IF NOT EXISTS jubelio_return_snapshot_batches_no_update BEFORE UPDATE ON jubelio_return_snapshot_batches
BEGIN SELECT RAISE(ABORT,'Jubelio return snapshot batches are immutable'); END;
CREATE TRIGGER IF NOT EXISTS jubelio_return_snapshot_batches_no_delete BEFORE DELETE ON jubelio_return_snapshot_batches
BEGIN SELECT RAISE(ABORT,'Jubelio return snapshot batches are immutable'); END;
CREATE TRIGGER IF NOT EXISTS jubelio_return_snapshot_records_no_update BEFORE UPDATE ON jubelio_return_snapshot_records
BEGIN SELECT RAISE(ABORT,'Jubelio return snapshots are immutable'); END;
CREATE TRIGGER IF NOT EXISTS jubelio_return_snapshot_records_no_delete BEFORE DELETE ON jubelio_return_snapshot_records
BEGIN SELECT RAISE(ABORT,'Jubelio return snapshots are immutable'); END;
CREATE TRIGGER IF NOT EXISTS jubelio_return_snapshot_lines_no_update BEFORE UPDATE ON jubelio_return_snapshot_lines
BEGIN SELECT RAISE(ABORT,'Jubelio return snapshot lines are immutable'); END;
CREATE TRIGGER IF NOT EXISTS jubelio_return_snapshot_lines_no_delete BEFORE DELETE ON jubelio_return_snapshot_lines
BEGIN SELECT RAISE(ABORT,'Jubelio return snapshot lines are immutable'); END;
CREATE TRIGGER IF NOT EXISTS jubelio_return_quarantine_records_no_update BEFORE UPDATE ON jubelio_return_quarantine_records
BEGIN SELECT RAISE(ABORT,'Jubelio return quarantine records are immutable'); END;
CREATE TRIGGER IF NOT EXISTS jubelio_return_quarantine_records_no_delete BEFORE DELETE ON jubelio_return_quarantine_records
BEGIN SELECT RAISE(ABORT,'Jubelio return quarantine records are immutable'); END;

PRAGMA user_version=37;
