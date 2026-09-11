BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS marketplace_picks (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    reference TEXT NOT NULL UNIQUE COLLATE NOCASE CHECK(reference=trim(reference) AND length(reference) BETWEEN 1 AND 160),
    reservation_id TEXT NOT NULL REFERENCES marketplace_reservations(id),
    quantity INTEGER NOT NULL CHECK(quantity>0),
    staging_location TEXT NOT NULL CHECK(staging_location=trim(staging_location) AND length(staging_location) BETWEEN 1 AND 160),
    picked_date TEXT NOT NULL CHECK(date(picked_date)=picked_date),
    reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;
CREATE INDEX IF NOT EXISTS marketplace_picks_reservation ON marketplace_picks(reservation_id,sequence);
CREATE TABLE IF NOT EXISTS marketplace_pick_reversals (
    pick_id TEXT PRIMARY KEY REFERENCES marketplace_picks(id),
    reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;
CREATE TRIGGER IF NOT EXISTS marketplace_pick_source_valid BEFORE INSERT ON marketplace_picks
WHEN NOT EXISTS(SELECT 1 FROM marketplace_reservations m JOIN finished_goods_receipts x ON x.id=m.receipt_id
    WHERE m.id=NEW.reservation_id AND NEW.picked_date>=m.reserved_date
      AND NOT EXISTS(SELECT 1 FROM marketplace_reservation_releases r WHERE r.reservation_id=m.id)
      AND NOT EXISTS(SELECT 1 FROM finished_goods_receipt_reversals r WHERE r.receipt_id=x.id))
OR NEW.quantity + COALESCE((SELECT SUM(p.quantity) FROM marketplace_picks p
    WHERE p.reservation_id=NEW.reservation_id AND NOT EXISTS(
      SELECT 1 FROM marketplace_pick_reversals r WHERE r.pick_id=p.id)),0)
   > COALESCE((SELECT quantity FROM marketplace_reservations WHERE id=NEW.reservation_id),0)
BEGIN SELECT RAISE(ABORT,'Invalid marketplace pick source, date, or quantity'); END;
CREATE TRIGGER IF NOT EXISTS marketplace_pick_reversal_valid BEFORE INSERT ON marketplace_pick_reversals
WHEN NOT EXISTS(SELECT 1 FROM marketplace_picks p JOIN marketplace_reservations m ON m.id=p.reservation_id
    WHERE p.id=NEW.pick_id AND NOT EXISTS(SELECT 1 FROM marketplace_pick_reversals r WHERE r.pick_id=p.id)
      AND NOT EXISTS(SELECT 1 FROM marketplace_reservation_releases r WHERE r.reservation_id=m.id))
BEGIN SELECT RAISE(ABORT,'Invalid marketplace pick reversal'); END;
DROP TRIGGER IF EXISTS marketplace_reservation_release_valid;
CREATE TRIGGER marketplace_reservation_release_valid BEFORE INSERT ON marketplace_reservation_releases
WHEN NOT EXISTS(SELECT 1 FROM marketplace_reservations m JOIN finished_goods_receipts x ON x.id=m.receipt_id
    WHERE m.id=NEW.reservation_id AND NEW.released_date>=m.reserved_date
      AND NOT EXISTS(SELECT 1 FROM marketplace_reservation_releases r WHERE r.reservation_id=m.id)
      AND NOT EXISTS(SELECT 1 FROM finished_goods_receipt_reversals r WHERE r.receipt_id=x.id))
OR EXISTS(SELECT 1 FROM marketplace_picks p WHERE p.reservation_id=NEW.reservation_id
    AND NOT EXISTS(SELECT 1 FROM marketplace_pick_reversals r WHERE r.pick_id=p.id))
BEGIN SELECT RAISE(ABORT,'Invalid marketplace reservation release'); END;
CREATE TRIGGER IF NOT EXISTS marketplace_picks_no_update BEFORE UPDATE ON marketplace_picks
BEGIN SELECT RAISE(ABORT,'Immutable marketplace pick'); END;
CREATE TRIGGER IF NOT EXISTS marketplace_picks_no_delete BEFORE DELETE ON marketplace_picks
BEGIN SELECT RAISE(ABORT,'Immutable marketplace pick'); END;
CREATE TRIGGER IF NOT EXISTS marketplace_pick_reversals_no_update BEFORE UPDATE ON marketplace_pick_reversals
BEGIN SELECT RAISE(ABORT,'Immutable marketplace pick reversal'); END;
CREATE TRIGGER IF NOT EXISTS marketplace_pick_reversals_no_delete BEFORE DELETE ON marketplace_pick_reversals
BEGIN SELECT RAISE(ABORT,'Immutable marketplace pick reversal'); END;
PRAGMA user_version=21;
COMMIT;
