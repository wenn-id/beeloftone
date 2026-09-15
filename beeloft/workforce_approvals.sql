BEGIN IMMEDIATE;

CREATE TABLE IF NOT EXISTS workforce_requests (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    reference TEXT NOT NULL UNIQUE CHECK(reference=upper(trim(reference)) AND length(reference) BETWEEN 1 AND 40),
    employee_id TEXT NOT NULL REFERENCES workforce_employees(id),
    kind TEXT NOT NULL CHECK(kind IN ('leave','overtime')),
    start_date TEXT NOT NULL CHECK(date(start_date) IS NOT NULL AND start_date=date(start_date)),
    end_date TEXT NOT NULL CHECK(date(end_date) IS NOT NULL AND end_date=date(end_date)),
    overtime_minutes INTEGER NOT NULL CHECK(overtime_minutes BETWEEN 0 AND 720),
    reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    CHECK(start_date<=end_date),
    CHECK((kind='leave' AND overtime_minutes=0)
       OR (kind='overtime' AND start_date=end_date AND overtime_minutes>0))
) STRICT;
CREATE INDEX IF NOT EXISTS workforce_requests_employee_dates
    ON workforce_requests(employee_id,start_date,end_date,sequence DESC);

CREATE TABLE IF NOT EXISTS workforce_request_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL REFERENCES workforce_requests(id),
    status TEXT NOT NULL CHECK(status IN ('submitted','approved','rejected','cancelled')),
    reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;
CREATE INDEX IF NOT EXISTS workforce_request_event_history
    ON workforce_request_events(request_id,sequence DESC);

CREATE TRIGGER IF NOT EXISTS workforce_request_transition
BEFORE INSERT ON workforce_request_events
WHEN NOT COALESCE(
    (NEW.status='submitted' AND
     NOT EXISTS(SELECT 1 FROM workforce_request_events WHERE request_id=NEW.request_id))
    OR
    (NEW.status IN ('approved','rejected','cancelled') AND
     (SELECT status FROM workforce_request_events WHERE request_id=NEW.request_id
      ORDER BY sequence DESC LIMIT 1)='submitted'),0)
BEGIN SELECT RAISE(ABORT,'Invalid workforce request transition'); END;

CREATE TRIGGER IF NOT EXISTS workforce_request_event_valid
BEFORE INSERT ON workforce_request_events
WHEN NOT COALESCE(
    (NEW.status='submitted' AND EXISTS(
      SELECT 1 FROM workforce_requests r JOIN users u ON u.id=NEW.actor_id
      WHERE r.id=NEW.request_id AND r.actor_id=NEW.actor_id AND r.reason=NEW.reason
        AND u.active=1 AND u.role IN ('admin','operator')))
    OR
    (NEW.status IN ('approved','rejected') AND EXISTS(
      SELECT 1 FROM users u WHERE u.id=NEW.actor_id AND u.active=1 AND u.role='admin'))
    OR
    (NEW.status='cancelled' AND EXISTS(
      SELECT 1 FROM workforce_requests r JOIN users u ON u.id=NEW.actor_id
      WHERE r.id=NEW.request_id AND u.active=1 AND u.role='operator'
        AND r.actor_id=NEW.actor_id))
,0)
BEGIN SELECT RAISE(ABORT,'Invalid workforce request event'); END;

CREATE TRIGGER IF NOT EXISTS workforce_requests_no_update
BEFORE UPDATE ON workforce_requests
BEGIN SELECT RAISE(ABORT,'Workforce requests are immutable'); END;
CREATE TRIGGER IF NOT EXISTS workforce_requests_no_delete
BEFORE DELETE ON workforce_requests
BEGIN SELECT RAISE(ABORT,'Workforce requests are immutable'); END;
CREATE TRIGGER IF NOT EXISTS workforce_request_events_no_update
BEFORE UPDATE ON workforce_request_events
BEGIN SELECT RAISE(ABORT,'Workforce request history is immutable'); END;
CREATE TRIGGER IF NOT EXISTS workforce_request_events_no_delete
BEFORE DELETE ON workforce_request_events
BEGIN SELECT RAISE(ABORT,'Workforce request history is immutable'); END;

PRAGMA user_version=51;
COMMIT;
