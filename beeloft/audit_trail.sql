CREATE TABLE IF NOT EXISTS audit_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL CHECK(category IN (
        'master_data','production','materials','purchasing','warehouse','marketplace',
        'approval','ai','integration'
    )),
    operation TEXT NOT NULL CHECK(operation=trim(operation) AND length(operation) BETWEEN 1 AND 200),
    actor_id TEXT NOT NULL REFERENCES users(id),
    actor_name TEXT NOT NULL CHECK(length(trim(actor_name)) BETWEEN 1 AND 160),
    actor_role TEXT NOT NULL CHECK(actor_role IN ('admin','operator','viewer')),
    subject_type TEXT NOT NULL CHECK(subject_type=trim(subject_type) AND length(subject_type) BETWEEN 1 AND 160),
    subject_id TEXT NOT NULL CHECK(subject_id=trim(subject_id) AND length(subject_id)<=500),
    subject_reference TEXT NOT NULL CHECK(subject_reference=trim(subject_reference) AND length(subject_reference)<=500),
    request_key TEXT NOT NULL CHECK(request_key=trim(request_key) AND length(request_key) BETWEEN 1 AND 128),
    changes_json TEXT NOT NULL CHECK(json_valid(changes_json)),
    outcome_json TEXT NOT NULL CHECK(json_valid(outcome_json)),
    created_at TEXT NOT NULL
) STRICT;

CREATE INDEX IF NOT EXISTS idx_audit_events_category_sequence
    ON audit_events(category,sequence DESC);
CREATE INDEX IF NOT EXISTS idx_audit_events_actor_sequence
    ON audit_events(actor_id,sequence DESC);
CREATE INDEX IF NOT EXISTS idx_audit_events_subject_sequence
    ON audit_events(subject_type,subject_id,sequence DESC);

CREATE TRIGGER IF NOT EXISTS audit_events_no_update
BEFORE UPDATE ON audit_events BEGIN
    SELECT RAISE(ABORT,'Audit events are immutable');
END;
CREATE TRIGGER IF NOT EXISTS audit_events_no_delete
BEFORE DELETE ON audit_events BEGIN
    SELECT RAISE(ABORT,'Audit events are immutable');
END;

PRAGMA user_version=45;
