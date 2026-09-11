BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS bundles (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    reference TEXT NOT NULL UNIQUE COLLATE NOCASE CHECK(reference=trim(reference) AND length(reference) BETWEEN 1 AND 160),
    cutting_run_id TEXT NOT NULL REFERENCES cutting_runs(id),
    output_movement_id TEXT NOT NULL REFERENCES movements(id),
    quantity INTEGER NOT NULL CHECK(quantity > 0),
    reason TEXT NOT NULL CHECK(length(trim(reason)) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;
CREATE INDEX IF NOT EXISTS bundles_run ON bundles(cutting_run_id,sequence);
CREATE INDEX IF NOT EXISTS bundles_output ON bundles(output_movement_id,sequence);
CREATE TABLE IF NOT EXISTS bundle_reversals (
    bundle_id TEXT PRIMARY KEY REFERENCES bundles(id),
    reason TEXT NOT NULL CHECK(length(trim(reason)) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;
CREATE TRIGGER IF NOT EXISTS bundle_source_valid BEFORE INSERT ON bundles
WHEN NOT EXISTS(
    SELECT 1 FROM cutting_runs r JOIN movements m ON m.id=NEW.output_movement_id
    WHERE r.id=NEW.cutting_run_id
      AND EXISTS(SELECT 1 FROM json_each(r.movement_ids) x WHERE x.value=m.id)
      AND m.from_stage='cutting' AND m.to_stage='sewing' AND m.reversal_of IS NULL
      AND NOT EXISTS(SELECT 1 FROM cutting_run_reversals WHERE run_id=r.id)
      AND NOT EXISTS(SELECT 1 FROM movements WHERE reversal_of=m.id)
)
OR NEW.quantity + COALESCE((
    SELECT SUM(b.quantity) FROM bundles b
    WHERE b.output_movement_id=NEW.output_movement_id
      AND NOT EXISTS(SELECT 1 FROM bundle_reversals x WHERE x.bundle_id=b.id)
),0) > COALESCE((SELECT quantity FROM movements WHERE id=NEW.output_movement_id),0)
BEGIN SELECT RAISE(ABORT,'Bundle requires active unallocated cutting output'); END;
CREATE TRIGGER IF NOT EXISTS bundle_blocks_cutting_output_reversal BEFORE INSERT ON movements
WHEN NEW.reversal_of IS NOT NULL AND EXISTS(
    SELECT 1 FROM bundles b
    WHERE b.output_movement_id=NEW.reversal_of
      AND NOT EXISTS(SELECT 1 FROM bundle_reversals x WHERE x.bundle_id=b.id)
)
BEGIN SELECT RAISE(ABORT,'Active bundle blocks cutting output reversal'); END;
CREATE TRIGGER IF NOT EXISTS bundles_no_update BEFORE UPDATE ON bundles
BEGIN SELECT RAISE(ABORT,'Immutable bundle'); END;
CREATE TRIGGER IF NOT EXISTS bundles_no_delete BEFORE DELETE ON bundles
BEGIN SELECT RAISE(ABORT,'Immutable bundle'); END;
CREATE TRIGGER IF NOT EXISTS bundle_reversals_no_update BEFORE UPDATE ON bundle_reversals
BEGIN SELECT RAISE(ABORT,'Immutable bundle reversal'); END;
CREATE TRIGGER IF NOT EXISTS bundle_reversals_no_delete BEFORE DELETE ON bundle_reversals
BEGIN SELECT RAISE(ABORT,'Immutable bundle reversal'); END;
PRAGMA user_version=14;
COMMIT;
