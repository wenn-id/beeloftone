BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS purchase_requests (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    reference TEXT NOT NULL UNIQUE CHECK(length(trim(reference)) BETWEEN 1 AND 160),
    order_id TEXT REFERENCES orders(id),
    required_date TEXT NOT NULL,
    estimated_value_minor INTEGER NOT NULL CHECK(estimated_value_minor BETWEEN 1 AND 100000000000000),
    lines TEXT NOT NULL CHECK(json_valid(lines) AND json_array_length(lines) BETWEEN 1 AND 100),
    reason TEXT NOT NULL CHECK(length(trim(reason)) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;
CREATE INDEX IF NOT EXISTS purchase_requests_order ON purchase_requests(order_id,sequence);
CREATE TABLE IF NOT EXISTS purchase_request_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL REFERENCES purchase_requests(id),
    status TEXT NOT NULL CHECK(status IN ('submitted','approved','rejected','cancelled')),
    reason TEXT NOT NULL CHECK(length(trim(reason)) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;
CREATE INDEX IF NOT EXISTS purchase_request_event_history ON purchase_request_events(request_id,sequence);
CREATE TRIGGER IF NOT EXISTS purchase_request_transition BEFORE INSERT ON purchase_request_events
WHEN NOT COALESCE((
    (NEW.status='submitted' AND NOT EXISTS(SELECT 1 FROM purchase_request_events WHERE request_id=NEW.request_id))
    OR (NEW.status IN ('approved','rejected','cancelled') AND
        (SELECT status FROM purchase_request_events WHERE request_id=NEW.request_id ORDER BY sequence DESC LIMIT 1)='submitted')
    OR (NEW.status='cancelled' AND
        (SELECT status FROM purchase_request_events WHERE request_id=NEW.request_id ORDER BY sequence DESC LIMIT 1)='approved')
),0)
BEGIN SELECT RAISE(ABORT,'Invalid purchase request transition'); END;
CREATE TRIGGER IF NOT EXISTS purchase_request_no_update BEFORE UPDATE ON purchase_requests
BEGIN SELECT RAISE(ABORT,'Purchase requests cannot be updated'); END;
CREATE TRIGGER IF NOT EXISTS purchase_request_no_delete BEFORE DELETE ON purchase_requests
BEGIN SELECT RAISE(ABORT,'Purchase requests cannot be deleted'); END;
CREATE TRIGGER IF NOT EXISTS purchase_request_event_no_update BEFORE UPDATE ON purchase_request_events
BEGIN SELECT RAISE(ABORT,'Purchase request history cannot be updated'); END;
CREATE TRIGGER IF NOT EXISTS purchase_request_event_no_delete BEFORE DELETE ON purchase_request_events
BEGIN SELECT RAISE(ABORT,'Purchase request history cannot be deleted'); END;
PRAGMA user_version=8;
COMMIT;
