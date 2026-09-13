CREATE TABLE IF NOT EXISTS jubelio_order_snapshot_batches (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    sync_run_id TEXT NOT NULL UNIQUE REFERENCES integration_sync_runs(id),
    snapshot_at TEXT NOT NULL,
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS jubelio_order_snapshot_orders (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    batch_id TEXT NOT NULL REFERENCES jubelio_order_snapshot_batches(id),
    external_order_id TEXT NOT NULL,
    external_order_reference TEXT NOT NULL COLLATE NOCASE,
    marketplace TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('pending','processing','completed','cancelled')),
    ordered_at TEXT NOT NULL,
    gross_revenue_minor INTEGER NOT NULL CHECK(gross_revenue_minor BETWEEN 0 AND 100000000000000),
    UNIQUE(batch_id,external_order_id),
    UNIQUE(batch_id,external_order_reference)
) STRICT;

CREATE TABLE IF NOT EXISTS jubelio_order_snapshot_lines (
    id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES jubelio_order_snapshot_orders(id),
    product_id TEXT NOT NULL REFERENCES products(id),
    external_id TEXT NOT NULL,
    external_sku TEXT NOT NULL COLLATE NOCASE,
    quantity INTEGER NOT NULL CHECK(quantity BETWEEN 1 AND 1000000000),
    gross_revenue_minor INTEGER NOT NULL CHECK(gross_revenue_minor BETWEEN 0 AND 100000000000000),
    UNIQUE(order_id,product_id),
    UNIQUE(order_id,external_id),
    UNIQUE(order_id,external_sku)
) STRICT;

CREATE TABLE IF NOT EXISTS jubelio_order_quarantine_records (
    id TEXT PRIMARY KEY,
    batch_id TEXT NOT NULL REFERENCES jubelio_order_snapshot_batches(id),
    external_order_id TEXT NOT NULL,
    external_order_reference TEXT NOT NULL,
    marketplace TEXT NOT NULL,
    status TEXT NOT NULL,
    ordered_at TEXT NOT NULL,
    payload_json TEXT NOT NULL CHECK(json_valid(payload_json)),
    issue TEXT NOT NULL CHECK(issue IN ('unmapped','mapping_mismatch')),
    detail TEXT NOT NULL CHECK(length(trim(detail)) BETWEEN 1 AND 1000),
    UNIQUE(batch_id,external_order_id),
    UNIQUE(batch_id,external_order_reference)
) STRICT;

CREATE INDEX IF NOT EXISTS idx_jubelio_order_snapshot_batch
    ON jubelio_order_snapshot_orders(batch_id,sequence);
CREATE INDEX IF NOT EXISTS idx_jubelio_order_snapshot_product
    ON jubelio_order_snapshot_lines(product_id,order_id);
CREATE INDEX IF NOT EXISTS idx_jubelio_order_quarantine_batch
    ON jubelio_order_quarantine_records(batch_id);

CREATE TRIGGER IF NOT EXISTS jubelio_order_snapshot_batches_no_update BEFORE UPDATE ON jubelio_order_snapshot_batches
BEGIN SELECT RAISE(ABORT,'Jubelio order snapshot batches are immutable'); END;
CREATE TRIGGER IF NOT EXISTS jubelio_order_snapshot_batches_no_delete BEFORE DELETE ON jubelio_order_snapshot_batches
BEGIN SELECT RAISE(ABORT,'Jubelio order snapshot batches are immutable'); END;
CREATE TRIGGER IF NOT EXISTS jubelio_order_snapshot_orders_no_update BEFORE UPDATE ON jubelio_order_snapshot_orders
BEGIN SELECT RAISE(ABORT,'Jubelio order snapshots are immutable'); END;
CREATE TRIGGER IF NOT EXISTS jubelio_order_snapshot_orders_no_delete BEFORE DELETE ON jubelio_order_snapshot_orders
BEGIN SELECT RAISE(ABORT,'Jubelio order snapshots are immutable'); END;
CREATE TRIGGER IF NOT EXISTS jubelio_order_snapshot_lines_no_update BEFORE UPDATE ON jubelio_order_snapshot_lines
BEGIN SELECT RAISE(ABORT,'Jubelio order snapshot lines are immutable'); END;
CREATE TRIGGER IF NOT EXISTS jubelio_order_snapshot_lines_no_delete BEFORE DELETE ON jubelio_order_snapshot_lines
BEGIN SELECT RAISE(ABORT,'Jubelio order snapshot lines are immutable'); END;
CREATE TRIGGER IF NOT EXISTS jubelio_order_quarantine_records_no_update BEFORE UPDATE ON jubelio_order_quarantine_records
BEGIN SELECT RAISE(ABORT,'Jubelio order quarantine records are immutable'); END;
CREATE TRIGGER IF NOT EXISTS jubelio_order_quarantine_records_no_delete BEFORE DELETE ON jubelio_order_quarantine_records
BEGIN SELECT RAISE(ABORT,'Jubelio order quarantine records are immutable'); END;

PRAGMA user_version=36;
