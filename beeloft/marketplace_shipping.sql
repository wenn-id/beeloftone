BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS marketplace_shipments (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    reference TEXT NOT NULL UNIQUE COLLATE NOCASE CHECK(reference=trim(reference) AND length(reference) BETWEEN 1 AND 160),
    pack_id TEXT NOT NULL REFERENCES marketplace_packs(id),
    quantity INTEGER NOT NULL CHECK(quantity>0),
    carrier TEXT NOT NULL CHECK(carrier=trim(carrier) AND length(carrier) BETWEEN 1 AND 160),
    tracking_number TEXT NOT NULL CHECK(tracking_number=trim(tracking_number) AND length(tracking_number) BETWEEN 1 AND 160),
    shipped_date TEXT NOT NULL CHECK(date(shipped_date)=shipped_date),
    reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    UNIQUE(carrier,tracking_number)
) STRICT;
CREATE INDEX IF NOT EXISTS marketplace_shipments_pack ON marketplace_shipments(pack_id,sequence);
CREATE TABLE IF NOT EXISTS marketplace_shipment_reversals (
    shipment_id TEXT PRIMARY KEY REFERENCES marketplace_shipments(id),
    reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;
CREATE TRIGGER IF NOT EXISTS marketplace_shipment_source_valid BEFORE INSERT ON marketplace_shipments
WHEN NOT EXISTS(SELECT 1 FROM marketplace_packs k JOIN marketplace_picks p ON p.id=k.pick_id
    JOIN marketplace_reservations m ON m.id=p.reservation_id
    JOIN finished_goods_receipts x ON x.id=m.receipt_id WHERE k.id=NEW.pack_id
      AND NEW.shipped_date>=k.packed_date
      AND NOT EXISTS(SELECT 1 FROM marketplace_pack_reversals r WHERE r.pack_id=k.id)
      AND NOT EXISTS(SELECT 1 FROM marketplace_pick_reversals r WHERE r.pick_id=p.id)
      AND NOT EXISTS(SELECT 1 FROM marketplace_reservation_releases r WHERE r.reservation_id=m.id)
      AND NOT EXISTS(SELECT 1 FROM finished_goods_receipt_reversals r WHERE r.receipt_id=x.id))
OR NEW.quantity + COALESCE((SELECT SUM(s.quantity) FROM marketplace_shipments s
    WHERE s.pack_id=NEW.pack_id AND NOT EXISTS(
      SELECT 1 FROM marketplace_shipment_reversals r WHERE r.shipment_id=s.id)),0)
   > COALESCE((SELECT quantity FROM marketplace_packs WHERE id=NEW.pack_id),0)
BEGIN SELECT RAISE(ABORT,'Invalid marketplace shipment source, date, or quantity'); END;
CREATE TRIGGER IF NOT EXISTS marketplace_shipment_reversal_valid BEFORE INSERT ON marketplace_shipment_reversals
WHEN NOT EXISTS(SELECT 1 FROM marketplace_shipments s JOIN marketplace_packs k ON k.id=s.pack_id
    WHERE s.id=NEW.shipment_id AND NOT EXISTS(
      SELECT 1 FROM marketplace_shipment_reversals r WHERE r.shipment_id=s.id)
      AND NOT EXISTS(SELECT 1 FROM marketplace_pack_reversals r WHERE r.pack_id=k.id))
BEGIN SELECT RAISE(ABORT,'Invalid marketplace shipment reversal'); END;
DROP TRIGGER IF EXISTS marketplace_pack_reversal_valid;
CREATE TRIGGER marketplace_pack_reversal_valid BEFORE INSERT ON marketplace_pack_reversals
WHEN NOT EXISTS(SELECT 1 FROM marketplace_packs k JOIN marketplace_picks p ON p.id=k.pick_id
    WHERE k.id=NEW.pack_id AND NOT EXISTS(SELECT 1 FROM marketplace_pack_reversals r WHERE r.pack_id=k.id)
      AND NOT EXISTS(SELECT 1 FROM marketplace_pick_reversals r WHERE r.pick_id=p.id))
OR EXISTS(SELECT 1 FROM marketplace_shipments s WHERE s.pack_id=NEW.pack_id
    AND NOT EXISTS(SELECT 1 FROM marketplace_shipment_reversals r WHERE r.shipment_id=s.id))
BEGIN SELECT RAISE(ABORT,'Invalid marketplace pack reversal'); END;
CREATE TRIGGER IF NOT EXISTS marketplace_shipments_no_update BEFORE UPDATE ON marketplace_shipments
BEGIN SELECT RAISE(ABORT,'Immutable marketplace shipment'); END;
CREATE TRIGGER IF NOT EXISTS marketplace_shipments_no_delete BEFORE DELETE ON marketplace_shipments
BEGIN SELECT RAISE(ABORT,'Immutable marketplace shipment'); END;
CREATE TRIGGER IF NOT EXISTS marketplace_shipment_reversals_no_update BEFORE UPDATE ON marketplace_shipment_reversals
BEGIN SELECT RAISE(ABORT,'Immutable marketplace shipment reversal'); END;
CREATE TRIGGER IF NOT EXISTS marketplace_shipment_reversals_no_delete BEFORE DELETE ON marketplace_shipment_reversals
BEGIN SELECT RAISE(ABORT,'Immutable marketplace shipment reversal'); END;
PRAGMA user_version=23;
COMMIT;
