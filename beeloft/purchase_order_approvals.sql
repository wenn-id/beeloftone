BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS purchase_order_approval_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT NOT NULL REFERENCES purchase_orders(id),
    status TEXT NOT NULL CHECK(status IN ('submitted','approved','rejected','cancelled')),
    reason TEXT NOT NULL CHECK(length(trim(reason)) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;
CREATE INDEX IF NOT EXISTS purchase_order_approval_history
ON purchase_order_approval_events(order_id,sequence);

INSERT INTO purchase_order_approval_events(order_id,status,reason,actor_id,created_at)
SELECT id,'approved','Migrasi: PO historis diperlakukan sudah disetujui.',actor_id,created_at
FROM purchase_orders
WHERE NOT EXISTS(SELECT 1 FROM purchase_order_approval_events e WHERE e.order_id=purchase_orders.id);

CREATE TRIGGER IF NOT EXISTS purchase_order_approval_transition
BEFORE INSERT ON purchase_order_approval_events
WHEN NOT COALESCE(
    (NEW.status='submitted' AND NOT EXISTS(
      SELECT 1 FROM purchase_order_approval_events WHERE order_id=NEW.order_id))
    OR
    (NEW.status IN ('approved','rejected','cancelled') AND
      (SELECT status FROM purchase_order_approval_events WHERE order_id=NEW.order_id
       ORDER BY sequence DESC LIMIT 1)='submitted'),0)
BEGIN SELECT RAISE(ABORT,'Invalid purchase order approval transition'); END;

CREATE TRIGGER IF NOT EXISTS purchase_order_approval_event_valid
BEFORE INSERT ON purchase_order_approval_events
WHEN NOT COALESCE(
    (NEW.status='submitted' AND EXISTS(
      SELECT 1 FROM purchase_orders p JOIN users u ON u.id=NEW.actor_id
      WHERE p.id=NEW.order_id AND p.actor_id=NEW.actor_id AND p.reason=NEW.reason
        AND u.active=1 AND u.role IN ('admin','operator')))
    OR
    (NEW.status IN ('approved','rejected') AND EXISTS(
      SELECT 1 FROM users u WHERE u.id=NEW.actor_id AND u.active=1 AND u.role='admin'))
    OR
    (NEW.status='cancelled' AND EXISTS(
      SELECT 1 FROM purchase_orders p JOIN users u ON u.id=NEW.actor_id
      WHERE p.id=NEW.order_id AND u.active=1
        AND (u.role='admin' OR (u.role='operator' AND p.actor_id=NEW.actor_id)))),0)
BEGIN SELECT RAISE(ABORT,'Invalid purchase order approval event'); END;

DROP TRIGGER IF EXISTS purchase_order_single_active;
CREATE TRIGGER purchase_order_single_active BEFORE INSERT ON purchase_orders
WHEN EXISTS(SELECT 1 FROM purchase_orders p WHERE p.request_id=NEW.request_id
    AND COALESCE((SELECT status FROM purchase_order_approval_events e WHERE e.order_id=p.id
        ORDER BY e.sequence DESC LIMIT 1),'approved') IN ('submitted','approved')
    AND NOT EXISTS(SELECT 1 FROM purchase_order_cancellations c WHERE c.order_id=p.id))
BEGIN SELECT RAISE(ABORT,'PR already has an active PO'); END;

DROP TRIGGER IF EXISTS purchase_request_active_po;
CREATE TRIGGER purchase_request_active_po BEFORE INSERT ON purchase_request_events
WHEN NEW.status='cancelled' AND EXISTS(SELECT 1 FROM purchase_orders p WHERE p.request_id=NEW.request_id
    AND COALESCE((SELECT status FROM purchase_order_approval_events e WHERE e.order_id=p.id
        ORDER BY e.sequence DESC LIMIT 1),'approved') IN ('submitted','approved')
    AND NOT EXISTS(SELECT 1 FROM purchase_order_cancellations c WHERE c.order_id=p.id))
BEGIN SELECT RAISE(ABORT,'Cancel active PO before cancelling PR'); END;

CREATE TRIGGER IF NOT EXISTS purchase_order_approval_required_for_cancel
BEFORE INSERT ON purchase_order_cancellations
WHEN COALESCE((SELECT status FROM purchase_order_approval_events WHERE order_id=NEW.order_id
      ORDER BY sequence DESC LIMIT 1),'')!='approved'
BEGIN SELECT RAISE(ABORT,'PO approval required before cancellation'); END;
CREATE TRIGGER IF NOT EXISTS purchase_order_approval_required_for_close
BEFORE INSERT ON purchase_order_closures
WHEN COALESCE((SELECT status FROM purchase_order_approval_events WHERE order_id=NEW.order_id
      ORDER BY sequence DESC LIMIT 1),'')!='approved'
BEGIN SELECT RAISE(ABORT,'PO approval required before closure'); END;
CREATE TRIGGER IF NOT EXISTS purchase_order_approval_required_for_receipt
BEFORE INSERT ON purchase_order_receipts
WHEN COALESCE((SELECT status FROM purchase_order_approval_events WHERE order_id=NEW.purchase_order_id
      ORDER BY sequence DESC LIMIT 1),'')!='approved'
BEGIN SELECT RAISE(ABORT,'PO approval required before receipt'); END;
CREATE TRIGGER IF NOT EXISTS purchase_order_approval_required_for_intake
BEFORE INSERT ON qc_intakes
WHEN COALESCE((SELECT status FROM purchase_order_approval_events WHERE order_id=NEW.purchase_order_id
      ORDER BY sequence DESC LIMIT 1),'')!='approved'
BEGIN SELECT RAISE(ABORT,'PO approval required before QC intake'); END;

CREATE TRIGGER IF NOT EXISTS purchase_order_approval_no_update
BEFORE UPDATE ON purchase_order_approval_events
BEGIN SELECT RAISE(ABORT,'Purchase order approval history cannot be updated'); END;
CREATE TRIGGER IF NOT EXISTS purchase_order_approval_no_delete
BEFORE DELETE ON purchase_order_approval_events
BEGIN SELECT RAISE(ABORT,'Purchase order approval history cannot be deleted'); END;

PRAGMA user_version=27;
COMMIT;
