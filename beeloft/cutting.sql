BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS cutting_runs (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    reference TEXT NOT NULL UNIQUE COLLATE NOCASE CHECK(length(trim(reference)) BETWEEN 1 AND 160),
    order_id TEXT NOT NULL REFERENCES orders(id),
    consumption_id TEXT NOT NULL UNIQUE REFERENCES material_consumption(id),
    movement_ids TEXT NOT NULL CHECK(json_valid(movement_ids) AND json_type(movement_ids)='array'
        AND json_array_length(movement_ids) BETWEEN 1 AND 100),
    reason TEXT NOT NULL CHECK(length(trim(reason)) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;
CREATE INDEX IF NOT EXISTS cutting_runs_order ON cutting_runs(order_id,sequence);
CREATE TABLE IF NOT EXISTS cutting_run_reversals (
    run_id TEXT PRIMARY KEY REFERENCES cutting_runs(id),
    reason TEXT NOT NULL CHECK(length(trim(reason)) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;
CREATE TRIGGER IF NOT EXISTS cutting_source_valid BEFORE INSERT ON cutting_runs
WHEN NOT EXISTS(SELECT 1 FROM material_consumption c JOIN material_movements i ON i.id=c.issue_id
    WHERE c.id=NEW.consumption_id AND c.reversal_of IS NULL AND c.used_milli>0 AND i.order_id=NEW.order_id
    AND NOT EXISTS(SELECT 1 FROM material_consumption WHERE reversal_of=c.id))
 OR (SELECT COUNT(DISTINCT value) FROM json_each(NEW.movement_ids))!=json_array_length(NEW.movement_ids)
 OR EXISTS(SELECT 1 FROM json_each(NEW.movement_ids) x WHERE NOT EXISTS(SELECT 1 FROM movements m
    JOIN order_lines l ON l.id=m.line_id WHERE m.id=x.value AND l.order_id=NEW.order_id
    AND m.from_stage='cutting' AND m.to_stage='sewing' AND m.reversal_of IS NULL
    AND NOT EXISTS(SELECT 1 FROM movements WHERE reversal_of=m.id)))
 OR EXISTS(SELECT 1 FROM cutting_runs r,json_each(r.movement_ids) old,json_each(NEW.movement_ids) fresh WHERE old.value=fresh.value)
BEGIN SELECT RAISE(ABORT,'Cutting requires unused output movements and active consumption from the same order'); END;
CREATE TRIGGER IF NOT EXISTS cutting_reversal_valid BEFORE INSERT ON cutting_run_reversals
WHEN NOT EXISTS(SELECT 1 FROM cutting_runs r JOIN material_consumption c ON c.reversal_of=r.consumption_id WHERE r.id=NEW.run_id)
 OR EXISTS(SELECT 1 FROM cutting_runs r,json_each(r.movement_ids) x WHERE r.id=NEW.run_id
    AND NOT EXISTS(SELECT 1 FROM movements WHERE reversal_of=x.value))
BEGIN SELECT RAISE(ABORT,'Reverse all outputs and consumption before recording cutting reversal'); END;
CREATE TRIGGER IF NOT EXISTS cutting_no_update BEFORE UPDATE ON cutting_runs
BEGIN SELECT RAISE(ABORT,'Immutable cutting run'); END;
CREATE TRIGGER IF NOT EXISTS cutting_no_delete BEFORE DELETE ON cutting_runs
BEGIN SELECT RAISE(ABORT,'Immutable cutting run'); END;
CREATE TRIGGER IF NOT EXISTS cutting_reversal_no_update BEFORE UPDATE ON cutting_run_reversals
BEGIN SELECT RAISE(ABORT,'Immutable cutting reversal'); END;
CREATE TRIGGER IF NOT EXISTS cutting_reversal_no_delete BEFORE DELETE ON cutting_run_reversals
BEGIN SELECT RAISE(ABORT,'Immutable cutting reversal'); END;
PRAGMA user_version=13;
COMMIT;
