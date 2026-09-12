BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS marketplace_packs (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    reference TEXT NOT NULL UNIQUE COLLATE NOCASE CHECK(reference=trim(reference) AND length(reference) BETWEEN 1 AND 160),
    pick_id TEXT NOT NULL REFERENCES marketplace_picks(id),
    quantity INTEGER NOT NULL CHECK(quantity>0),
    packed_date TEXT NOT NULL CHECK(date(packed_date)=packed_date),
    reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;
CREATE INDEX IF NOT EXISTS marketplace_packs_pick ON marketplace_packs(pick_id,sequence);
CREATE TABLE IF NOT EXISTS marketplace_pack_reversals (
    pack_id TEXT PRIMARY KEY REFERENCES marketplace_packs(id),
    reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;
CREATE TRIGGER IF NOT EXISTS marketplace_pack_source_valid BEFORE INSERT ON marketplace_packs
WHEN NOT EXISTS(SELECT 1 FROM marketplace_picks p JOIN marketplace_reservations m ON m.id=p.reservation_id
    JOIN finished_goods_receipts x ON x.id=m.receipt_id WHERE p.id=NEW.pick_id
      AND NEW.packed_date>=p.picked_date
      AND NOT EXISTS(SELECT 1 FROM marketplace_pick_reversals r WHERE r.pick_id=p.id)
      AND NOT EXISTS(SELECT 1 FROM marketplace_reservation_releases r WHERE r.reservation_id=m.id)
      AND NOT EXISTS(SELECT 1 FROM finished_goods_receipt_reversals r WHERE r.receipt_id=x.id))
OR NEW.quantity + COALESCE((SELECT SUM(k.quantity) FROM marketplace_packs k
    WHERE k.pick_id=NEW.pick_id AND NOT EXISTS(
      SELECT 1 FROM marketplace_pack_reversals r WHERE r.pack_id=k.id)),0)
   > COALESCE((SELECT quantity FROM marketplace_picks WHERE id=NEW.pick_id),0)
BEGIN SELECT RAISE(ABORT,'Invalid marketplace pack source, date, or quantity'); END;
CREATE TRIGGER IF NOT EXISTS marketplace_pack_reversal_valid BEFORE INSERT ON marketplace_pack_reversals
WHEN NOT EXISTS(SELECT 1 FROM marketplace_packs k JOIN marketplace_picks p ON p.id=k.pick_id
    WHERE k.id=NEW.pack_id AND NOT EXISTS(SELECT 1 FROM marketplace_pack_reversals r WHERE r.pack_id=k.id)
      AND NOT EXISTS(SELECT 1 FROM marketplace_pick_reversals r WHERE r.pick_id=p.id))
BEGIN SELECT RAISE(ABORT,'Invalid marketplace pack reversal'); END;
DROP TRIGGER IF EXISTS marketplace_pick_reversal_valid;
CREATE TRIGGER marketplace_pick_reversal_valid BEFORE INSERT ON marketplace_pick_reversals
WHEN NOT EXISTS(SELECT 1 FROM marketplace_picks p JOIN marketplace_reservations m ON m.id=p.reservation_id
    WHERE p.id=NEW.pick_id AND NOT EXISTS(SELECT 1 FROM marketplace_pick_reversals r WHERE r.pick_id=p.id)
      AND NOT EXISTS(SELECT 1 FROM marketplace_reservation_releases r WHERE r.reservation_id=m.id))
OR EXISTS(SELECT 1 FROM marketplace_packs k WHERE k.pick_id=NEW.pick_id
    AND NOT EXISTS(SELECT 1 FROM marketplace_pack_reversals r WHERE r.pack_id=k.id))
BEGIN SELECT RAISE(ABORT,'Invalid marketplace pick reversal'); END;
CREATE TRIGGER IF NOT EXISTS marketplace_packs_no_update BEFORE UPDATE ON marketplace_packs
BEGIN SELECT RAISE(ABORT,'Immutable marketplace pack'); END;
CREATE TRIGGER IF NOT EXISTS marketplace_packs_no_delete BEFORE DELETE ON marketplace_packs
BEGIN SELECT RAISE(ABORT,'Immutable marketplace pack'); END;
CREATE TRIGGER IF NOT EXISTS marketplace_pack_reversals_no_update BEFORE UPDATE ON marketplace_pack_reversals
BEGIN SELECT RAISE(ABORT,'Immutable marketplace pack reversal'); END;
CREATE TRIGGER IF NOT EXISTS marketplace_pack_reversals_no_delete BEFORE DELETE ON marketplace_pack_reversals
BEGIN SELECT RAISE(ABORT,'Immutable marketplace pack reversal'); END;
PRAGMA user_version=22;
COMMIT;
