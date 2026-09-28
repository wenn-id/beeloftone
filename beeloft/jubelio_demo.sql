CREATE TABLE IF NOT EXISTS jubelio_demo_state (
    id TEXT PRIMARY KEY CHECK(id='singleton'),
    is_demo INTEGER NOT NULL CHECK(is_demo IN (0,1)),
    demo_enabled INTEGER NOT NULL DEFAULT 0 CHECK(demo_enabled IN (0,1)),
    anchor_at TEXT NOT NULL DEFAULT '',
    current_scenario INTEGER NOT NULL DEFAULT 0 CHECK(current_scenario BETWEEN 0 AND 2),
    is_locked INTEGER NOT NULL DEFAULT 0 CHECK(is_locked IN (0,1)),
    lock_token TEXT NOT NULL DEFAULT '',
    lock_expires_at TEXT NOT NULL DEFAULT '',
    active_operation_id TEXT NOT NULL DEFAULT '',
    lock_started_at TEXT NOT NULL DEFAULT '',
    last_synced_at TEXT NOT NULL DEFAULT '',
    last_status TEXT NOT NULL DEFAULT 'idle' CHECK(last_status IN ('idle','running','failed','succeeded')),
    last_error TEXT NOT NULL DEFAULT '',
    last_summary_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(last_summary_json)),
    updated_at TEXT NOT NULL,
    CHECK((is_locked=0 AND lock_token='' AND active_operation_id='' AND lock_started_at='') OR
          (is_locked=1 AND lock_token<>'' AND active_operation_id<>'' AND lock_started_at<>''))
) STRICT;

CREATE TABLE IF NOT EXISTS jubelio_demo_operations (
    id TEXT PRIMARY KEY,
    request_key TEXT NOT NULL UNIQUE,
    actor_id TEXT NOT NULL REFERENCES users(id),
    fingerprint TEXT NOT NULL,
    kind TEXT NOT NULL CHECK(kind IN ('sync','next_scenario')),
    scenario INTEGER NOT NULL CHECK(scenario BETWEEN 1 AND 2),
    anchor_at TEXT NOT NULL,
    started_at TEXT NOT NULL,
    snapshot_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('running','failed','succeeded')),
    error TEXT NOT NULL DEFAULT '',
    summary_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(summary_json)),
    response_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(response_json)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS jubelio_demo_operation_scopes (
    operation_id TEXT NOT NULL REFERENCES jubelio_demo_operations(id),
    scope TEXT NOT NULL CHECK(scope IN ('finished_goods','orders','returns','listings')),
    status TEXT NOT NULL CHECK(status IN ('pending','running','failed','attention','succeeded')),
    batch_id TEXT NOT NULL DEFAULT '',
    records_read INTEGER NOT NULL DEFAULT 0 CHECK(records_read>=0),
    accepted_count INTEGER NOT NULL DEFAULT 0 CHECK(accepted_count>=0),
    rejected_count INTEGER NOT NULL DEFAULT 0 CHECK(rejected_count>=0),
    error TEXT NOT NULL DEFAULT '',
    attempts INTEGER NOT NULL DEFAULT 0 CHECK(attempts>=0),
    updated_at TEXT NOT NULL,
    PRIMARY KEY(operation_id,scope)
) STRICT;

CREATE INDEX IF NOT EXISTS jubelio_demo_operations_status
    ON jubelio_demo_operations(status,created_at);

INSERT OR IGNORE INTO jubelio_demo_state(id,is_demo,demo_enabled,anchor_at,current_scenario,is_locked,
    lock_token,lock_expires_at,active_operation_id,lock_started_at,last_synced_at,last_status,last_error,
    last_summary_json,updated_at)
VALUES('singleton',0,0,'',0,0,'','','','','','idle','','{}',strftime('%Y-%m-%dT%H:%M:%f','now')||'+00:00');

PRAGMA user_version=64;
