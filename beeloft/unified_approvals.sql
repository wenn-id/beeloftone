BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS production_change_requests (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    reference TEXT NOT NULL UNIQUE CHECK(length(trim(reference)) BETWEEN 1 AND 160),
    order_id TEXT NOT NULL REFERENCES orders(id),
    old_due_date TEXT NOT NULL,
    new_due_date TEXT NOT NULL,
    old_owner_id TEXT NOT NULL REFERENCES users(id),
    new_owner_id TEXT NOT NULL REFERENCES users(id),
    expected_revision INTEGER NOT NULL CHECK(expected_revision>=0),
    reason TEXT NOT NULL CHECK(length(trim(reason)) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    CHECK(old_due_date!=new_due_date OR old_owner_id!=new_owner_id)
) STRICT;
CREATE INDEX IF NOT EXISTS production_change_requests_order
ON production_change_requests(order_id,sequence);

CREATE TABLE IF NOT EXISTS production_change_request_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL REFERENCES production_change_requests(id),
    status TEXT NOT NULL CHECK(status IN ('submitted','approved','rejected','cancelled')),
    reason TEXT NOT NULL CHECK(length(trim(reason)) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    order_change_id TEXT REFERENCES order_changes(id),
    created_at TEXT NOT NULL,
    CHECK((status='approved')=(order_change_id IS NOT NULL))
) STRICT;
CREATE INDEX IF NOT EXISTS production_change_request_event_history
ON production_change_request_events(request_id,sequence);

CREATE TRIGGER IF NOT EXISTS production_change_request_source_valid
BEFORE INSERT ON production_change_requests
WHEN NOT EXISTS(
    SELECT 1 FROM orders o JOIN users old ON old.id=NEW.old_owner_id
    JOIN users proposed ON proposed.id=NEW.new_owner_id
    JOIN users requester ON requester.id=NEW.actor_id
    WHERE o.id=NEW.order_id AND o.due_date=NEW.old_due_date AND o.owner_id=NEW.old_owner_id
      AND proposed.active=1 AND proposed.role IN ('admin','operator')
      AND requester.active=1 AND requester.role IN ('admin','operator')
      AND NEW.expected_revision=(SELECT COALESCE(MAX(sequence),0) FROM order_changes WHERE order_id=o.id)
)
BEGIN SELECT RAISE(ABORT,'Invalid production change request source'); END;

CREATE TRIGGER IF NOT EXISTS production_change_request_one_pending
BEFORE INSERT ON production_change_requests
WHEN EXISTS(
    SELECT 1 FROM production_change_requests r
    WHERE r.order_id=NEW.order_id AND
      (SELECT status FROM production_change_request_events e WHERE e.request_id=r.id
       ORDER BY e.sequence DESC LIMIT 1)='submitted'
)
BEGIN SELECT RAISE(ABORT,'Production order already has a pending change request'); END;

CREATE TRIGGER IF NOT EXISTS production_change_request_transition
BEFORE INSERT ON production_change_request_events
WHEN NOT COALESCE(
    (NEW.status='submitted' AND NEW.order_change_id IS NULL AND
     NOT EXISTS(SELECT 1 FROM production_change_request_events WHERE request_id=NEW.request_id))
    OR
    (NEW.status IN ('approved','rejected','cancelled') AND
     (SELECT status FROM production_change_request_events WHERE request_id=NEW.request_id
      ORDER BY sequence DESC LIMIT 1)='submitted'),0)
BEGIN SELECT RAISE(ABORT,'Invalid production change request transition'); END;

CREATE TRIGGER IF NOT EXISTS production_change_request_event_valid
BEFORE INSERT ON production_change_request_events
WHEN NOT COALESCE(
    (NEW.status='submitted' AND NEW.order_change_id IS NULL AND EXISTS(
      SELECT 1 FROM production_change_requests r JOIN users u ON u.id=NEW.actor_id
      WHERE r.id=NEW.request_id AND r.actor_id=NEW.actor_id AND r.reason=NEW.reason
        AND u.active=1 AND u.role IN ('admin','operator')))
    OR
    (NEW.status IN ('approved','rejected') AND EXISTS(
      SELECT 1 FROM users u WHERE u.id=NEW.actor_id AND u.active=1 AND u.role='admin')
      AND (NEW.status='rejected' OR EXISTS(
        SELECT 1 FROM production_change_requests r JOIN order_changes c ON c.id=NEW.order_change_id
        JOIN orders o ON o.id=r.order_id WHERE r.id=NEW.request_id AND c.order_id=r.order_id
          AND c.old_due_date=r.old_due_date AND c.new_due_date=r.new_due_date
          AND c.old_owner_id=r.old_owner_id AND c.new_owner_id=r.new_owner_id
          AND c.reason=r.reason AND c.actor_id=NEW.actor_id
          AND o.due_date=r.new_due_date AND o.owner_id=r.new_owner_id)))
    OR
    (NEW.status='cancelled' AND NEW.order_change_id IS NULL AND EXISTS(
      SELECT 1 FROM production_change_requests r JOIN users u ON u.id=NEW.actor_id
      WHERE r.id=NEW.request_id AND u.active=1
        AND (u.role='admin' OR (u.role='operator' AND r.actor_id=NEW.actor_id))))
,0)
BEGIN SELECT RAISE(ABORT,'Invalid production change request event'); END;

CREATE TRIGGER IF NOT EXISTS production_change_request_no_update
BEFORE UPDATE ON production_change_requests
BEGIN SELECT RAISE(ABORT,'Production change requests cannot be updated'); END;
CREATE TRIGGER IF NOT EXISTS production_change_request_no_delete
BEFORE DELETE ON production_change_requests
BEGIN SELECT RAISE(ABORT,'Production change requests cannot be deleted'); END;
CREATE TRIGGER IF NOT EXISTS production_change_request_event_no_update
BEFORE UPDATE ON production_change_request_events
BEGIN SELECT RAISE(ABORT,'Production change request history cannot be updated'); END;
CREATE TRIGGER IF NOT EXISTS production_change_request_event_no_delete
BEFORE DELETE ON production_change_request_events
BEGIN SELECT RAISE(ABORT,'Production change request history cannot be deleted'); END;

PRAGMA user_version=26;
COMMIT;
