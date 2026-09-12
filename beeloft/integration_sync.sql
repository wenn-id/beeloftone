CREATE TABLE IF NOT EXISTS integration_sync_runs (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    system TEXT NOT NULL CHECK(system IN ('jubelio','mekari')),
    scope TEXT NOT NULL CHECK(scope IN (
        'orders','finished_goods','returns','listings',
        'finance_summary','payables','receivables','payroll'
    )),
    status TEXT NOT NULL CHECK(status IN ('succeeded','failed')),
    started_at TEXT NOT NULL,
    finished_at TEXT NOT NULL CHECK(finished_at>=started_at),
    records_read INTEGER NOT NULL CHECK(records_read BETWEEN 0 AND 1000000000),
    records_written INTEGER NOT NULL CHECK(records_written BETWEEN 0 AND 1000000000),
    external_cursor TEXT NOT NULL CHECK(external_cursor=trim(external_cursor) AND length(external_cursor)<=1000),
    error TEXT NOT NULL CHECK(error=trim(error) AND length(error)<=1000),
    reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    CHECK((status='succeeded' AND error='') OR (status='failed' AND length(error)>0))
);

CREATE INDEX IF NOT EXISTS idx_integration_sync_system_scope_sequence
    ON integration_sync_runs(system,scope,sequence DESC);
CREATE INDEX IF NOT EXISTS idx_integration_sync_status_sequence
    ON integration_sync_runs(status,sequence DESC);

CREATE TRIGGER IF NOT EXISTS integration_sync_runs_no_update
BEFORE UPDATE ON integration_sync_runs BEGIN
    SELECT RAISE(ABORT,'Integration sync runs are immutable');
END;
CREATE TRIGGER IF NOT EXISTS integration_sync_runs_no_delete
BEFORE DELETE ON integration_sync_runs BEGIN
    SELECT RAISE(ABORT,'Integration sync runs are immutable');
END;

PRAGMA user_version=33;
