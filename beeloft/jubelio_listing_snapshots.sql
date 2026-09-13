CREATE TABLE IF NOT EXISTS jubelio_listing_snapshot_batches (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    sync_run_id TEXT NOT NULL UNIQUE REFERENCES integration_sync_runs(id),
    snapshot_at TEXT NOT NULL,
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS jubelio_listing_snapshot_records (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    batch_id TEXT NOT NULL REFERENCES jubelio_listing_snapshot_batches(id),
    product_id TEXT NOT NULL REFERENCES products(id),
    external_listing_id TEXT NOT NULL,
    listing_reference TEXT NOT NULL COLLATE NOCASE,
    external_id TEXT NOT NULL,
    external_sku TEXT NOT NULL COLLATE NOCASE,
    marketplace TEXT NOT NULL COLLATE NOCASE,
    listing_title TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('active','inactive','draft','blocked')),
    listed_price_minor INTEGER NOT NULL CHECK(listed_price_minor BETWEEN 1 AND 100000000000000),
    updated_at TEXT NOT NULL,
    UNIQUE(batch_id,external_listing_id),
    UNIQUE(batch_id,marketplace,listing_reference)
) STRICT;

CREATE TABLE IF NOT EXISTS jubelio_listing_quarantine_records (
    id TEXT PRIMARY KEY,
    batch_id TEXT NOT NULL REFERENCES jubelio_listing_snapshot_batches(id),
    external_listing_id TEXT NOT NULL,
    listing_reference TEXT NOT NULL,
    marketplace TEXT NOT NULL,
    status TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    payload_json TEXT NOT NULL CHECK(json_valid(payload_json)),
    issue TEXT NOT NULL CHECK(issue IN ('unmapped','mapping_mismatch')),
    detail TEXT NOT NULL CHECK(length(trim(detail)) BETWEEN 1 AND 1000),
    UNIQUE(batch_id,external_listing_id),
    UNIQUE(batch_id,marketplace,listing_reference)
) STRICT;

CREATE INDEX IF NOT EXISTS idx_jubelio_listing_snapshot_batch
    ON jubelio_listing_snapshot_records(batch_id,sequence);
CREATE INDEX IF NOT EXISTS idx_jubelio_listing_snapshot_product
    ON jubelio_listing_snapshot_records(product_id,batch_id);
CREATE INDEX IF NOT EXISTS idx_jubelio_listing_quarantine_batch
    ON jubelio_listing_quarantine_records(batch_id);

CREATE TRIGGER IF NOT EXISTS jubelio_listing_snapshot_batches_no_update BEFORE UPDATE ON jubelio_listing_snapshot_batches
BEGIN SELECT RAISE(ABORT,'Jubelio listing snapshot batches are immutable'); END;
CREATE TRIGGER IF NOT EXISTS jubelio_listing_snapshot_batches_no_delete BEFORE DELETE ON jubelio_listing_snapshot_batches
BEGIN SELECT RAISE(ABORT,'Jubelio listing snapshot batches are immutable'); END;
CREATE TRIGGER IF NOT EXISTS jubelio_listing_snapshot_records_no_update BEFORE UPDATE ON jubelio_listing_snapshot_records
BEGIN SELECT RAISE(ABORT,'Jubelio listing snapshots are immutable'); END;
CREATE TRIGGER IF NOT EXISTS jubelio_listing_snapshot_records_no_delete BEFORE DELETE ON jubelio_listing_snapshot_records
BEGIN SELECT RAISE(ABORT,'Jubelio listing snapshots are immutable'); END;
CREATE TRIGGER IF NOT EXISTS jubelio_listing_quarantine_records_no_update BEFORE UPDATE ON jubelio_listing_quarantine_records
BEGIN SELECT RAISE(ABORT,'Jubelio listing quarantine records are immutable'); END;
CREATE TRIGGER IF NOT EXISTS jubelio_listing_quarantine_records_no_delete BEFORE DELETE ON jubelio_listing_quarantine_records
BEGIN SELECT RAISE(ABORT,'Jubelio listing quarantine records are immutable'); END;

PRAGMA user_version=38;
