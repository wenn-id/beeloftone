BEGIN IMMEDIATE;

CREATE TABLE IF NOT EXISTS payroll_approval_requests (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    reference TEXT NOT NULL UNIQUE CHECK(reference=upper(trim(reference)) AND length(reference) BETWEEN 1 AND 40),
    source_period_id TEXT NOT NULL REFERENCES mekari_payroll_snapshot_periods(id),
    reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;
CREATE INDEX IF NOT EXISTS payroll_approval_request_source
    ON payroll_approval_requests(source_period_id,sequence DESC);

CREATE TABLE IF NOT EXISTS payroll_approval_request_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL REFERENCES payroll_approval_requests(id),
    status TEXT NOT NULL CHECK(status IN ('submitted','approved','rejected','cancelled')),
    reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;
CREATE INDEX IF NOT EXISTS payroll_approval_request_history
    ON payroll_approval_request_events(request_id,sequence DESC);

CREATE TRIGGER IF NOT EXISTS payroll_approval_request_transition
BEFORE INSERT ON payroll_approval_request_events
WHEN NOT COALESCE(
    (NEW.status='submitted' AND
     NOT EXISTS(SELECT 1 FROM payroll_approval_request_events WHERE request_id=NEW.request_id))
    OR
    (NEW.status IN ('approved','rejected','cancelled') AND
     (SELECT status FROM payroll_approval_request_events WHERE request_id=NEW.request_id
      ORDER BY sequence DESC LIMIT 1)='submitted'),0)
BEGIN SELECT RAISE(ABORT,'Invalid payroll approval transition'); END;

CREATE TRIGGER IF NOT EXISTS payroll_approval_request_event_valid
BEFORE INSERT ON payroll_approval_request_events
WHEN NOT COALESCE(
    (NEW.status='submitted' AND EXISTS(
      SELECT 1 FROM payroll_approval_requests r JOIN users u ON u.id=NEW.actor_id
      WHERE r.id=NEW.request_id AND r.actor_id=NEW.actor_id AND r.reason=NEW.reason
        AND u.active=1 AND u.role IN ('admin','operator')))
    OR
    (NEW.status IN ('approved','rejected') AND EXISTS(
      SELECT 1 FROM users u WHERE u.id=NEW.actor_id AND u.active=1 AND u.role='admin'))
    OR
    (NEW.status='cancelled' AND EXISTS(
      SELECT 1 FROM payroll_approval_requests r JOIN users u ON u.id=NEW.actor_id
      WHERE r.id=NEW.request_id AND u.active=1 AND u.role='operator'
        AND r.actor_id=NEW.actor_id))
,0)
BEGIN SELECT RAISE(ABORT,'Invalid payroll approval event'); END;

CREATE TRIGGER IF NOT EXISTS payroll_approval_requests_no_update
BEFORE UPDATE ON payroll_approval_requests
BEGIN SELECT RAISE(ABORT,'Payroll approval requests are immutable'); END;
CREATE TRIGGER IF NOT EXISTS payroll_approval_requests_no_delete
BEFORE DELETE ON payroll_approval_requests
BEGIN SELECT RAISE(ABORT,'Payroll approval requests are immutable'); END;
CREATE TRIGGER IF NOT EXISTS payroll_approval_request_events_no_update
BEFORE UPDATE ON payroll_approval_request_events
BEGIN SELECT RAISE(ABORT,'Payroll approval history is immutable'); END;
CREATE TRIGGER IF NOT EXISTS payroll_approval_request_events_no_delete
BEFORE DELETE ON payroll_approval_request_events
BEGIN SELECT RAISE(ABORT,'Payroll approval history is immutable'); END;

PRAGMA user_version=52;
COMMIT;
