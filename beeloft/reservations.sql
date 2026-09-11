BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS material_reservation_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    batch_id TEXT NOT NULL REFERENCES material_batches(id),
    order_id TEXT NOT NULL REFERENCES orders(id),
    kind TEXT NOT NULL CHECK(kind IN ('reserve','release','consume')),
    quantity_milli INTEGER NOT NULL CHECK(quantity_milli!=0 AND abs(quantity_milli)<=1000000000),
    movement_id TEXT UNIQUE REFERENCES material_movements(id),
    reason TEXT NOT NULL CHECK(length(trim(reason)) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    CHECK((kind='reserve' AND quantity_milli>0 AND movement_id IS NULL)
        OR (kind='release' AND quantity_milli<0 AND movement_id IS NULL)
        OR (kind='consume' AND quantity_milli<0 AND movement_id IS NOT NULL))
) STRICT;
CREATE INDEX IF NOT EXISTS reservation_batch_order ON material_reservation_events(batch_id,order_id);
CREATE INDEX IF NOT EXISTS reservation_order_history ON material_reservation_events(order_id,sequence);
CREATE TRIGGER IF NOT EXISTS reservation_nonnegative BEFORE INSERT ON material_reservation_events
WHEN COALESCE((SELECT SUM(quantity_milli) FROM material_reservation_events WHERE batch_id=NEW.batch_id AND order_id=NEW.order_id),0)+NEW.quantity_milli<0
BEGIN SELECT RAISE(ABORT,'Reservation cannot be negative'); END;
CREATE TRIGGER IF NOT EXISTS reservation_within_stock BEFORE INSERT ON material_reservation_events
WHEN NEW.kind='reserve' AND COALESCE((SELECT SUM(quantity_milli) FROM material_reservation_events WHERE batch_id=NEW.batch_id),0)+NEW.quantity_milli>
    COALESCE((SELECT SUM(quantity_milli) FROM material_movements WHERE batch_id=NEW.batch_id),0)
BEGIN SELECT RAISE(ABORT,'Reservation exceeds stock'); END;
CREATE TRIGGER IF NOT EXISTS reservation_consume_matches BEFORE INSERT ON material_reservation_events
WHEN NEW.kind='consume' AND NOT EXISTS(SELECT 1 FROM material_movements m WHERE m.id=NEW.movement_id
    AND m.kind='issue' AND m.batch_id=NEW.batch_id AND m.order_id=NEW.order_id AND m.quantity_milli<=NEW.quantity_milli)
BEGIN SELECT RAISE(ABORT,'Reservation consumption must match issue'); END;
CREATE TRIGGER IF NOT EXISTS reservation_no_update BEFORE UPDATE ON material_reservation_events
BEGIN SELECT RAISE(ABORT,'Reservation history cannot be updated'); END;
CREATE TRIGGER IF NOT EXISTS reservation_no_delete BEFORE DELETE ON material_reservation_events
BEGIN SELECT RAISE(ABORT,'Reservation history cannot be deleted'); END;
PRAGMA user_version=6;
COMMIT;
