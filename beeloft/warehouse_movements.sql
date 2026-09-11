BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS warehouse_movements (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    reference TEXT NOT NULL UNIQUE COLLATE NOCASE CHECK(reference=trim(reference) AND length(reference) BETWEEN 1 AND 160),
    receipt_id TEXT NOT NULL REFERENCES finished_goods_receipts(id),
    kind TEXT NOT NULL CHECK(kind IN ('transfer','hold_release','hold_damage')),
    from_location TEXT NOT NULL CHECK(from_location=trim(from_location) AND length(from_location) BETWEEN 1 AND 160),
    to_location TEXT NOT NULL CHECK(to_location=trim(to_location) AND length(to_location) BETWEEN 1 AND 160),
    from_status TEXT NOT NULL CHECK(from_status IN ('sellable','hold','damaged')),
    to_status TEXT NOT NULL CHECK(to_status IN ('sellable','hold','damaged')),
    quantity INTEGER NOT NULL CHECK(quantity>0),
    moved_date TEXT NOT NULL CHECK(date(moved_date)=moved_date),
    reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    CHECK((kind='transfer' AND from_status=to_status AND from_location<>to_location COLLATE NOCASE)
       OR (kind='hold_release' AND from_status='hold' AND to_status='sellable')
       OR (kind='hold_damage' AND from_status='hold' AND to_status='damaged'))
) STRICT;
CREATE INDEX IF NOT EXISTS warehouse_movements_receipt ON warehouse_movements(receipt_id,sequence);
CREATE TABLE IF NOT EXISTS warehouse_movement_reversals (
    movement_id TEXT PRIMARY KEY REFERENCES warehouse_movements(id),
    reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;
CREATE TRIGGER IF NOT EXISTS warehouse_movement_source_valid BEFORE INSERT ON warehouse_movements
WHEN NOT EXISTS(SELECT 1 FROM finished_goods_receipts x WHERE x.id=NEW.receipt_id
    AND NEW.moved_date>=x.received_date AND NOT EXISTS(
      SELECT 1 FROM finished_goods_receipt_reversals r WHERE r.receipt_id=x.id))
OR NEW.quantity >
   COALESCE((SELECT CASE
      WHEN NEW.from_location=x.location COLLATE NOCASE AND NEW.from_status='sellable' THEN x.sellable_quantity
      WHEN NEW.from_location=x.location COLLATE NOCASE AND NEW.from_status='hold' THEN x.hold_quantity
      ELSE 0 END FROM finished_goods_receipts x WHERE x.id=NEW.receipt_id),0)
   + COALESCE((SELECT SUM(w.quantity) FROM warehouse_movements w
      WHERE w.receipt_id=NEW.receipt_id AND w.to_location=NEW.from_location COLLATE NOCASE
        AND w.to_status=NEW.from_status AND NOT EXISTS(
          SELECT 1 FROM warehouse_movement_reversals r WHERE r.movement_id=w.id)),0)
   - COALESCE((SELECT SUM(w.quantity) FROM warehouse_movements w
      WHERE w.receipt_id=NEW.receipt_id AND w.from_location=NEW.from_location COLLATE NOCASE
        AND w.from_status=NEW.from_status AND NOT EXISTS(
          SELECT 1 FROM warehouse_movement_reversals r WHERE r.movement_id=w.id)),0)
BEGIN SELECT RAISE(ABORT,'Invalid warehouse movement source, date, or quantity'); END;
CREATE TRIGGER IF NOT EXISTS warehouse_movement_reversal_valid BEFORE INSERT ON warehouse_movement_reversals
WHEN NOT EXISTS(SELECT 1 FROM warehouse_movements w JOIN finished_goods_receipts x ON x.id=w.receipt_id
    WHERE w.id=NEW.movement_id AND NOT EXISTS(
      SELECT 1 FROM warehouse_movement_reversals r WHERE r.movement_id=w.id)
    AND NOT EXISTS(SELECT 1 FROM finished_goods_receipt_reversals r WHERE r.receipt_id=x.id))
OR COALESCE((SELECT CASE
      WHEN w.to_location=x.location COLLATE NOCASE AND w.to_status='sellable' THEN x.sellable_quantity
      WHEN w.to_location=x.location COLLATE NOCASE AND w.to_status='hold' THEN x.hold_quantity
      ELSE 0 END FROM warehouse_movements w JOIN finished_goods_receipts x ON x.id=w.receipt_id
      WHERE w.id=NEW.movement_id),0)
   + COALESCE((SELECT SUM(other.quantity) FROM warehouse_movements w
      JOIN warehouse_movements other ON other.receipt_id=w.receipt_id
        AND other.to_location=w.to_location COLLATE NOCASE AND other.to_status=w.to_status
      WHERE w.id=NEW.movement_id AND NOT EXISTS(
        SELECT 1 FROM warehouse_movement_reversals r WHERE r.movement_id=other.id)),0)
   - COALESCE((SELECT SUM(other.quantity) FROM warehouse_movements w
      JOIN warehouse_movements other ON other.receipt_id=w.receipt_id
        AND other.from_location=w.to_location COLLATE NOCASE AND other.from_status=w.to_status
      WHERE w.id=NEW.movement_id AND NOT EXISTS(
        SELECT 1 FROM warehouse_movement_reversals r WHERE r.movement_id=other.id)),0)
   < COALESCE((SELECT quantity FROM warehouse_movements WHERE id=NEW.movement_id),1)
BEGIN SELECT RAISE(ABORT,'Invalid warehouse movement reversal'); END;
DROP TRIGGER IF EXISTS finished_goods_reversal_valid;
CREATE TRIGGER finished_goods_reversal_valid BEFORE INSERT ON finished_goods_receipt_reversals
WHEN NOT EXISTS(SELECT 1 FROM finished_goods_receipts WHERE id=NEW.receipt_id)
OR EXISTS(SELECT 1 FROM finished_goods_receipt_reversals WHERE receipt_id=NEW.receipt_id)
OR EXISTS(SELECT 1 FROM warehouse_movements w WHERE w.receipt_id=NEW.receipt_id
    AND NOT EXISTS(SELECT 1 FROM warehouse_movement_reversals r WHERE r.movement_id=w.id))
BEGIN SELECT RAISE(ABORT,'Invalid finished goods receipt reversal'); END;
CREATE TRIGGER IF NOT EXISTS warehouse_movements_no_update BEFORE UPDATE ON warehouse_movements
BEGIN SELECT RAISE(ABORT,'Immutable warehouse movement'); END;
CREATE TRIGGER IF NOT EXISTS warehouse_movements_no_delete BEFORE DELETE ON warehouse_movements
BEGIN SELECT RAISE(ABORT,'Immutable warehouse movement'); END;
CREATE TRIGGER IF NOT EXISTS warehouse_movement_reversals_no_update BEFORE UPDATE ON warehouse_movement_reversals
BEGIN SELECT RAISE(ABORT,'Immutable warehouse movement reversal'); END;
CREATE TRIGGER IF NOT EXISTS warehouse_movement_reversals_no_delete BEFORE DELETE ON warehouse_movement_reversals
BEGIN SELECT RAISE(ABORT,'Immutable warehouse movement reversal'); END;
PRAGMA user_version=19;
COMMIT;
