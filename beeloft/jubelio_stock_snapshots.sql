CREATE TABLE IF NOT EXISTS jubelio_stock_snapshot_batches (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    sync_run_id TEXT NOT NULL UNIQUE REFERENCES integration_sync_runs(id),
    snapshot_at TEXT NOT NULL,
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS jubelio_stock_snapshot_items (
    id TEXT PRIMARY KEY,
    batch_id TEXT NOT NULL REFERENCES jubelio_stock_snapshot_batches(id),
    product_id TEXT NOT NULL REFERENCES products(id),
    external_id TEXT NOT NULL,
    external_sku TEXT NOT NULL COLLATE NOCASE,
    sellable_quantity INTEGER NOT NULL CHECK(sellable_quantity BETWEEN 0 AND 1000000000),
    reserved_quantity INTEGER NOT NULL CHECK(reserved_quantity BETWEEN 0 AND sellable_quantity),
    UNIQUE(batch_id,product_id),
    UNIQUE(batch_id,external_id),
    UNIQUE(batch_id,external_sku)
) STRICT;

CREATE TABLE IF NOT EXISTS jubelio_stock_quarantine_items (
    id TEXT PRIMARY KEY,
    batch_id TEXT NOT NULL REFERENCES jubelio_stock_snapshot_batches(id),
    external_id TEXT NOT NULL,
    external_sku TEXT NOT NULL COLLATE NOCASE,
    sellable_quantity INTEGER NOT NULL CHECK(sellable_quantity BETWEEN 0 AND 1000000000),
    reserved_quantity INTEGER NOT NULL CHECK(reserved_quantity BETWEEN 0 AND sellable_quantity),
    issue TEXT NOT NULL CHECK(issue IN ('unmapped','mapping_mismatch')),
    detail TEXT NOT NULL CHECK(length(trim(detail)) BETWEEN 1 AND 1000),
    UNIQUE(batch_id,external_id),
    UNIQUE(batch_id,external_sku)
) STRICT;

CREATE INDEX IF NOT EXISTS idx_jubelio_stock_snapshot_product
    ON jubelio_stock_snapshot_items(product_id,batch_id);
CREATE INDEX IF NOT EXISTS idx_jubelio_stock_quarantine_batch
    ON jubelio_stock_quarantine_items(batch_id);

CREATE TRIGGER IF NOT EXISTS jubelio_stock_snapshot_batches_no_update BEFORE UPDATE ON jubelio_stock_snapshot_batches
BEGIN SELECT RAISE(ABORT,'Jubelio stock snapshot batches are immutable'); END;
CREATE TRIGGER IF NOT EXISTS jubelio_stock_snapshot_batches_no_delete BEFORE DELETE ON jubelio_stock_snapshot_batches
BEGIN SELECT RAISE(ABORT,'Jubelio stock snapshot batches are immutable'); END;
CREATE TRIGGER IF NOT EXISTS jubelio_stock_snapshot_items_no_update BEFORE UPDATE ON jubelio_stock_snapshot_items
BEGIN SELECT RAISE(ABORT,'Jubelio stock snapshot items are immutable'); END;
CREATE TRIGGER IF NOT EXISTS jubelio_stock_snapshot_items_no_delete BEFORE DELETE ON jubelio_stock_snapshot_items
BEGIN SELECT RAISE(ABORT,'Jubelio stock snapshot items are immutable'); END;
CREATE TRIGGER IF NOT EXISTS jubelio_stock_quarantine_items_no_update BEFORE UPDATE ON jubelio_stock_quarantine_items
BEGIN SELECT RAISE(ABORT,'Jubelio stock quarantine items are immutable'); END;
CREATE TRIGGER IF NOT EXISTS jubelio_stock_quarantine_items_no_delete BEFORE DELETE ON jubelio_stock_quarantine_items
BEGIN SELECT RAISE(ABORT,'Jubelio stock quarantine items are immutable'); END;

PRAGMA user_version=35;
