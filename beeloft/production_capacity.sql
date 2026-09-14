BEGIN IMMEDIATE;

CREATE TABLE IF NOT EXISTS production_work_centers (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL UNIQUE COLLATE NOCASE
        CHECK(code=upper(trim(code)) AND length(code) BETWEEN 1 AND 40),
    stage TEXT NOT NULL CHECK(stage IN ('cutting','sewing','finishing','qc','rework')),
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS production_work_center_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    work_center_id TEXT NOT NULL REFERENCES production_work_centers(id),
    revision INTEGER NOT NULL CHECK(revision>0),
    name TEXT NOT NULL CHECK(name=trim(name) AND length(name) BETWEEN 1 AND 160),
    daily_minutes INTEGER NOT NULL CHECK(daily_minutes BETWEEN 1 AND 100000),
    active INTEGER NOT NULL CHECK(active IN (0,1)),
    reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    UNIQUE(work_center_id,revision)
) STRICT;
CREATE INDEX IF NOT EXISTS production_work_center_events_current
    ON production_work_center_events(work_center_id,sequence DESC);

CREATE TABLE IF NOT EXISTS production_routing_standard_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    product_id TEXT NOT NULL REFERENCES products(id),
    stage TEXT NOT NULL CHECK(stage IN ('cutting','sewing','finishing','qc','rework')),
    revision INTEGER NOT NULL CHECK(revision>0),
    work_center_id TEXT NOT NULL REFERENCES production_work_centers(id),
    minutes_per_unit_milli INTEGER NOT NULL CHECK(minutes_per_unit_milli BETWEEN 1 AND 100000000),
    reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    UNIQUE(product_id,stage,revision)
) STRICT;
CREATE INDEX IF NOT EXISTS production_routing_standard_events_current
    ON production_routing_standard_events(product_id,stage,sequence DESC);

CREATE TRIGGER IF NOT EXISTS production_routing_standard_stage_guard
BEFORE INSERT ON production_routing_standard_events
WHEN NOT EXISTS (
    SELECT 1 FROM production_work_centers c
    WHERE c.id=NEW.work_center_id AND c.stage=NEW.stage
)
BEGIN SELECT RAISE(ABORT,'Routing standard stage must match work center stage'); END;

CREATE TABLE IF NOT EXISTS production_capacity_calendar_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    work_center_id TEXT NOT NULL REFERENCES production_work_centers(id),
    work_date TEXT NOT NULL CHECK(date(work_date) IS NOT NULL AND work_date=date(work_date)),
    revision INTEGER NOT NULL CHECK(revision>0),
    available_minutes INTEGER NOT NULL CHECK(available_minutes BETWEEN 0 AND 100000),
    reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    UNIQUE(work_center_id,work_date,revision)
) STRICT;
CREATE INDEX IF NOT EXISTS production_capacity_calendar_events_current
    ON production_capacity_calendar_events(work_center_id,work_date,sequence DESC);

CREATE TRIGGER IF NOT EXISTS production_work_centers_no_update
BEFORE UPDATE ON production_work_centers
BEGIN SELECT RAISE(ABORT,'Production work centers are immutable'); END;
CREATE TRIGGER IF NOT EXISTS production_work_centers_no_delete
BEFORE DELETE ON production_work_centers
BEGIN SELECT RAISE(ABORT,'Production work centers are immutable'); END;
CREATE TRIGGER IF NOT EXISTS production_work_center_events_no_update
BEFORE UPDATE ON production_work_center_events
BEGIN SELECT RAISE(ABORT,'Production work center history is immutable'); END;
CREATE TRIGGER IF NOT EXISTS production_work_center_events_no_delete
BEFORE DELETE ON production_work_center_events
BEGIN SELECT RAISE(ABORT,'Production work center history is immutable'); END;
CREATE TRIGGER IF NOT EXISTS production_routing_standard_events_no_update
BEFORE UPDATE ON production_routing_standard_events
BEGIN SELECT RAISE(ABORT,'Production routing standard history is immutable'); END;
CREATE TRIGGER IF NOT EXISTS production_routing_standard_events_no_delete
BEFORE DELETE ON production_routing_standard_events
BEGIN SELECT RAISE(ABORT,'Production routing standard history is immutable'); END;
CREATE TRIGGER IF NOT EXISTS production_capacity_calendar_events_no_update
BEFORE UPDATE ON production_capacity_calendar_events
BEGIN SELECT RAISE(ABORT,'Production capacity calendar history is immutable'); END;
CREATE TRIGGER IF NOT EXISTS production_capacity_calendar_events_no_delete
BEFORE DELETE ON production_capacity_calendar_events
BEGIN SELECT RAISE(ABORT,'Production capacity calendar history is immutable'); END;

PRAGMA user_version=49;
COMMIT;
