BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS marketing_budget_requests (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    reference TEXT NOT NULL UNIQUE CHECK(length(trim(reference)) BETWEEN 1 AND 160),
    campaign_name TEXT NOT NULL CHECK(length(trim(campaign_name)) BETWEEN 1 AND 160),
    channel TEXT NOT NULL CHECK(length(trim(channel)) BETWEEN 1 AND 160),
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    amount_minor INTEGER NOT NULL CHECK(amount_minor BETWEEN 1 AND 100000000000000),
    objective TEXT NOT NULL CHECK(length(trim(objective)) BETWEEN 1 AND 1000),
    reason TEXT NOT NULL CHECK(length(trim(reason)) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    CHECK(start_date<=end_date)
) STRICT;

CREATE TABLE IF NOT EXISTS marketing_budget_request_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL REFERENCES marketing_budget_requests(id),
    status TEXT NOT NULL CHECK(status IN ('submitted','approved','rejected','cancelled')),
    reason TEXT NOT NULL CHECK(length(trim(reason)) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;
CREATE INDEX IF NOT EXISTS marketing_budget_request_history
ON marketing_budget_request_events(request_id,sequence);

CREATE TRIGGER IF NOT EXISTS marketing_budget_request_actor_valid
BEFORE INSERT ON marketing_budget_requests
WHEN NOT EXISTS(SELECT 1 FROM users WHERE id=NEW.actor_id AND active=1 AND role IN ('admin','operator'))
BEGIN SELECT RAISE(ABORT,'Invalid marketing budget requester'); END;

CREATE TRIGGER IF NOT EXISTS marketing_budget_request_transition
BEFORE INSERT ON marketing_budget_request_events
WHEN NOT COALESCE(
    (NEW.status='submitted' AND NOT EXISTS(
      SELECT 1 FROM marketing_budget_request_events WHERE request_id=NEW.request_id))
    OR
    (NEW.status IN ('approved','rejected','cancelled') AND
      (SELECT status FROM marketing_budget_request_events WHERE request_id=NEW.request_id
       ORDER BY sequence DESC LIMIT 1)='submitted'),0)
BEGIN SELECT RAISE(ABORT,'Invalid marketing budget request transition'); END;

CREATE TRIGGER IF NOT EXISTS marketing_budget_request_event_valid
BEFORE INSERT ON marketing_budget_request_events
WHEN NOT COALESCE(
    (NEW.status='submitted' AND EXISTS(
      SELECT 1 FROM marketing_budget_requests r JOIN users u ON u.id=NEW.actor_id
      WHERE r.id=NEW.request_id AND r.actor_id=NEW.actor_id AND r.reason=NEW.reason
        AND u.active=1 AND u.role IN ('admin','operator')))
    OR
    (NEW.status IN ('approved','rejected') AND EXISTS(
      SELECT 1 FROM users u WHERE u.id=NEW.actor_id AND u.active=1 AND u.role='admin'))
    OR
    (NEW.status='cancelled' AND EXISTS(
      SELECT 1 FROM marketing_budget_requests r JOIN users u ON u.id=NEW.actor_id
      WHERE r.id=NEW.request_id AND u.active=1
        AND (u.role='admin' OR (u.role='operator' AND r.actor_id=NEW.actor_id)))),0)
BEGIN SELECT RAISE(ABORT,'Invalid marketing budget request event'); END;

CREATE TRIGGER IF NOT EXISTS marketing_budget_request_no_update
BEFORE UPDATE ON marketing_budget_requests
BEGIN SELECT RAISE(ABORT,'Marketing budget requests cannot be updated'); END;
CREATE TRIGGER IF NOT EXISTS marketing_budget_request_no_delete
BEFORE DELETE ON marketing_budget_requests
BEGIN SELECT RAISE(ABORT,'Marketing budget requests cannot be deleted'); END;
CREATE TRIGGER IF NOT EXISTS marketing_budget_event_no_update
BEFORE UPDATE ON marketing_budget_request_events
BEGIN SELECT RAISE(ABORT,'Marketing budget approval history cannot be updated'); END;
CREATE TRIGGER IF NOT EXISTS marketing_budget_event_no_delete
BEFORE DELETE ON marketing_budget_request_events
BEGIN SELECT RAISE(ABORT,'Marketing budget approval history cannot be deleted'); END;

PRAGMA user_version=29;
COMMIT;
