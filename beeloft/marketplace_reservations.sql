BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS marketplace_reservations (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    reference TEXT NOT NULL UNIQUE COLLATE NOCASE CHECK(reference=trim(reference) AND length(reference) BETWEEN 1 AND 160),
    receipt_id TEXT NOT NULL REFERENCES finished_goods_receipts(id),
    marketplace TEXT NOT NULL CHECK(marketplace=trim(marketplace) AND length(marketplace) BETWEEN 1 AND 160),
    external_order_reference TEXT NOT NULL CHECK(external_order_reference=trim(external_order_reference) AND length(external_order_reference) BETWEEN 1 AND 160),
    location TEXT NOT NULL CHECK(location=trim(location) AND length(location) BETWEEN 1 AND 160),
    quantity INTEGER NOT NULL CHECK(quantity>0),
    reserved_date TEXT NOT NULL CHECK(date(reserved_date)=reserved_date),
    reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;
CREATE INDEX IF NOT EXISTS marketplace_reservations_receipt ON marketplace_reservations(receipt_id,sequence);
CREATE TABLE IF NOT EXISTS marketplace_reservation_releases (
    reservation_id TEXT PRIMARY KEY REFERENCES marketplace_reservations(id),
    released_date TEXT NOT NULL CHECK(date(released_date)=released_date),
    reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;
CREATE TRIGGER IF NOT EXISTS marketplace_reservation_source_valid BEFORE INSERT ON marketplace_reservations
WHEN NOT EXISTS(SELECT 1 FROM finished_goods_receipts x WHERE x.id=NEW.receipt_id
    AND NEW.reserved_date>=x.received_date AND NOT EXISTS(
      SELECT 1 FROM finished_goods_receipt_reversals r WHERE r.receipt_id=x.id))
OR NEW.quantity >
   COALESCE((SELECT CASE WHEN NEW.location=x.location COLLATE NOCASE THEN x.sellable_quantity ELSE 0 END
      FROM finished_goods_receipts x WHERE x.id=NEW.receipt_id),0)
   + COALESCE((SELECT SUM(w.quantity) FROM warehouse_movements w WHERE w.receipt_id=NEW.receipt_id
      AND w.to_location=NEW.location COLLATE NOCASE AND w.to_status='sellable' AND NOT EXISTS(
        SELECT 1 FROM warehouse_movement_reversals r WHERE r.movement_id=w.id)),0)
   - COALESCE((SELECT SUM(w.quantity) FROM warehouse_movements w WHERE w.receipt_id=NEW.receipt_id
      AND w.from_location=NEW.location COLLATE NOCASE AND w.from_status='sellable' AND NOT EXISTS(
        SELECT 1 FROM warehouse_movement_reversals r WHERE r.movement_id=w.id)),0)
   - COALESCE((SELECT SUM(m.quantity) FROM marketplace_reservations m WHERE m.receipt_id=NEW.receipt_id
      AND m.location=NEW.location COLLATE NOCASE AND NOT EXISTS(
        SELECT 1 FROM marketplace_reservation_releases r WHERE r.reservation_id=m.id)),0)
BEGIN SELECT RAISE(ABORT,'Invalid marketplace reservation source, date, or quantity'); END;
CREATE TRIGGER IF NOT EXISTS marketplace_reservation_release_valid BEFORE INSERT ON marketplace_reservation_releases
WHEN NOT EXISTS(SELECT 1 FROM marketplace_reservations m JOIN finished_goods_receipts x ON x.id=m.receipt_id
    WHERE m.id=NEW.reservation_id AND NEW.released_date>=m.reserved_date
      AND NOT EXISTS(SELECT 1 FROM marketplace_reservation_releases r WHERE r.reservation_id=m.id)
      AND NOT EXISTS(SELECT 1 FROM finished_goods_receipt_reversals r WHERE r.receipt_id=x.id))
BEGIN SELECT RAISE(ABORT,'Invalid marketplace reservation release'); END;
DROP TRIGGER IF EXISTS warehouse_movement_source_valid;
CREATE TRIGGER warehouse_movement_source_valid BEFORE INSERT ON warehouse_movements
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
   - CASE WHEN NEW.from_status='sellable' THEN COALESCE((SELECT SUM(m.quantity)
      FROM marketplace_reservations m WHERE m.receipt_id=NEW.receipt_id
        AND m.location=NEW.from_location COLLATE NOCASE AND NOT EXISTS(
          SELECT 1 FROM marketplace_reservation_releases r WHERE r.reservation_id=m.id)),0) ELSE 0 END
BEGIN SELECT RAISE(ABORT,'Invalid warehouse movement source, date, or quantity'); END;
DROP TRIGGER IF EXISTS warehouse_movement_reversal_valid;
CREATE TRIGGER warehouse_movement_reversal_valid BEFORE INSERT ON warehouse_movement_reversals
WHEN NOT EXISTS(SELECT 1 FROM warehouse_movements w JOIN finished_goods_receipts x ON x.id=w.receipt_id
    WHERE w.id=NEW.movement_id AND NOT EXISTS(
      SELECT 1 FROM warehouse_movement_reversals r WHERE r.movement_id=w.id)
    AND NOT EXISTS(SELECT 1 FROM finished_goods_receipt_reversals r WHERE r.receipt_id=x.id))
OR COALESCE((SELECT CASE
      WHEN w.to_location=x.location COLLATE NOCASE AND w.to_status='sellable' THEN x.sellable_quantity
      WHEN w.to_location=x.location COLLATE NOCASE AND w.to_status='hold' THEN x.hold_quantity
      ELSE 0 END FROM warehouse_movements w JOIN finished_goods_receipts x ON x.id=w.receipt_id
      WHERE w.id=NEW.movement_id),0)
   + COALESCE((SELECT SUM(other.quantity) FROM warehouse_movements w JOIN warehouse_movements other
      ON other.receipt_id=w.receipt_id AND other.to_location=w.to_location COLLATE NOCASE
        AND other.to_status=w.to_status WHERE w.id=NEW.movement_id AND NOT EXISTS(
          SELECT 1 FROM warehouse_movement_reversals r WHERE r.movement_id=other.id)),0)
   - COALESCE((SELECT SUM(other.quantity) FROM warehouse_movements w JOIN warehouse_movements other
      ON other.receipt_id=w.receipt_id AND other.from_location=w.to_location COLLATE NOCASE
        AND other.from_status=w.to_status WHERE w.id=NEW.movement_id AND NOT EXISTS(
          SELECT 1 FROM warehouse_movement_reversals r WHERE r.movement_id=other.id)),0)
   - COALESCE((SELECT SUM(m.quantity) FROM warehouse_movements w JOIN marketplace_reservations m
      ON m.receipt_id=w.receipt_id AND m.location=w.to_location COLLATE NOCASE
      WHERE w.id=NEW.movement_id AND w.to_status='sellable' AND NOT EXISTS(
        SELECT 1 FROM marketplace_reservation_releases r WHERE r.reservation_id=m.id)),0)
   < COALESCE((SELECT quantity FROM warehouse_movements WHERE id=NEW.movement_id),1)
BEGIN SELECT RAISE(ABORT,'Invalid warehouse movement reversal'); END;
DROP TRIGGER IF EXISTS finished_goods_reversal_valid;
CREATE TRIGGER finished_goods_reversal_valid BEFORE INSERT ON finished_goods_receipt_reversals
WHEN NOT EXISTS(SELECT 1 FROM finished_goods_receipts WHERE id=NEW.receipt_id)
OR EXISTS(SELECT 1 FROM finished_goods_receipt_reversals WHERE receipt_id=NEW.receipt_id)
OR EXISTS(SELECT 1 FROM warehouse_movements w WHERE w.receipt_id=NEW.receipt_id
    AND NOT EXISTS(SELECT 1 FROM warehouse_movement_reversals r WHERE r.movement_id=w.id))
OR EXISTS(SELECT 1 FROM marketplace_reservations m WHERE m.receipt_id=NEW.receipt_id
    AND NOT EXISTS(SELECT 1 FROM marketplace_reservation_releases r WHERE r.reservation_id=m.id))
BEGIN SELECT RAISE(ABORT,'Invalid finished goods receipt reversal'); END;
CREATE TRIGGER IF NOT EXISTS marketplace_reservations_no_update BEFORE UPDATE ON marketplace_reservations
BEGIN SELECT RAISE(ABORT,'Immutable marketplace reservation'); END;
CREATE TRIGGER IF NOT EXISTS marketplace_reservations_no_delete BEFORE DELETE ON marketplace_reservations
BEGIN SELECT RAISE(ABORT,'Immutable marketplace reservation'); END;
CREATE TRIGGER IF NOT EXISTS marketplace_reservation_releases_no_update BEFORE UPDATE ON marketplace_reservation_releases
BEGIN SELECT RAISE(ABORT,'Immutable marketplace reservation release'); END;
CREATE TRIGGER IF NOT EXISTS marketplace_reservation_releases_no_delete BEFORE DELETE ON marketplace_reservation_releases
BEGIN SELECT RAISE(ABORT,'Immutable marketplace reservation release'); END;
PRAGMA user_version=20;
COMMIT;
