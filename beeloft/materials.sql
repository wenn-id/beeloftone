BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS materials (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL UNIQUE COLLATE NOCASE,
    name TEXT NOT NULL,
    unit TEXT NOT NULL CHECK(unit IN ('m','kg','pcs')),
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;
CREATE TABLE IF NOT EXISTS material_batches (
    id TEXT PRIMARY KEY,
    material_id TEXT NOT NULL REFERENCES materials(id),
    reference TEXT NOT NULL UNIQUE COLLATE NOCASE,
    supplier TEXT NOT NULL,
    location TEXT NOT NULL,
    received_date TEXT NOT NULL,
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;
CREATE TABLE IF NOT EXISTS material_movements (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    batch_id TEXT NOT NULL REFERENCES material_batches(id),
    kind TEXT NOT NULL CHECK(kind IN ('receipt','issue','reversal')),
    quantity_milli INTEGER NOT NULL CHECK(quantity_milli != 0 AND abs(quantity_milli) <= 1000000000),
    order_id TEXT REFERENCES orders(id),
    reversal_of TEXT UNIQUE REFERENCES material_movements(id),
    reason TEXT NOT NULL CHECK(length(trim(reason)) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    CHECK((kind='receipt' AND quantity_milli>0 AND order_id IS NULL AND reversal_of IS NULL)
       OR (kind='issue' AND quantity_milli<0 AND order_id IS NOT NULL AND reversal_of IS NULL)
       OR (kind='reversal' AND reversal_of IS NOT NULL))
) STRICT;
CREATE UNIQUE INDEX IF NOT EXISTS material_receipt_once ON material_movements(batch_id) WHERE kind='receipt';
CREATE INDEX IF NOT EXISTS material_batch_history ON material_movements(batch_id,sequence);
CREATE INDEX IF NOT EXISTS material_order_history ON material_movements(order_id,sequence);
CREATE TRIGGER IF NOT EXISTS material_stock_nonnegative BEFORE INSERT ON material_movements
WHEN COALESCE((SELECT SUM(quantity_milli) FROM material_movements WHERE batch_id=NEW.batch_id),0)+NEW.quantity_milli<0
BEGIN SELECT RAISE(ABORT,'Insufficient material stock'); END;
CREATE TRIGGER IF NOT EXISTS material_reversal_matches BEFORE INSERT ON material_movements
WHEN NEW.kind='reversal' AND NOT EXISTS(SELECT 1 FROM material_movements m
    WHERE m.id=NEW.reversal_of AND m.kind!='reversal' AND m.batch_id=NEW.batch_id
    AND m.order_id IS NEW.order_id AND m.quantity_milli=-NEW.quantity_milli)
BEGIN SELECT RAISE(ABORT,'Invalid material reversal'); END;
CREATE TRIGGER IF NOT EXISTS materials_no_update BEFORE UPDATE ON materials
BEGIN SELECT RAISE(ABORT,'Material identity cannot be updated'); END;
CREATE TRIGGER IF NOT EXISTS materials_no_delete BEFORE DELETE ON materials
BEGIN SELECT RAISE(ABORT,'Material identity cannot be deleted'); END;
CREATE TRIGGER IF NOT EXISTS material_batches_no_update BEFORE UPDATE ON material_batches
BEGIN SELECT RAISE(ABORT,'Batch receipt cannot be updated'); END;
CREATE TRIGGER IF NOT EXISTS material_batches_no_delete BEFORE DELETE ON material_batches
BEGIN SELECT RAISE(ABORT,'Batch receipt cannot be deleted'); END;
CREATE TRIGGER IF NOT EXISTS material_movements_no_update BEFORE UPDATE ON material_movements
BEGIN SELECT RAISE(ABORT,'Material history cannot be updated'); END;
CREATE TRIGGER IF NOT EXISTS material_movements_no_delete BEFORE DELETE ON material_movements
BEGIN SELECT RAISE(ABORT,'Material history cannot be deleted'); END;
PRAGMA user_version=4;
COMMIT;
