BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS final_qc_records (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    reference TEXT NOT NULL UNIQUE COLLATE NOCASE CHECK(reference=trim(reference) AND length(reference) BETWEEN 1 AND 160),
    finishing_record_id TEXT NOT NULL REFERENCES finishing_records(id),
    measurement_notes TEXT NOT NULL CHECK(measurement_notes=trim(measurement_notes) AND length(measurement_notes) BETWEEN 1 AND 1000),
    visual_notes TEXT NOT NULL CHECK(visual_notes=trim(visual_notes) AND length(visual_notes) BETWEEN 1 AND 1000),
    accepted_quantity INTEGER NOT NULL CHECK(accepted_quantity>=0),
    rework_quantity INTEGER NOT NULL CHECK(rework_quantity>=0),
    reject_quantity INTEGER NOT NULL CHECK(reject_quantity>=0),
    inspection_date TEXT NOT NULL CHECK(date(inspection_date)=inspection_date),
    accepted_movement_id TEXT UNIQUE REFERENCES movements(id),
    rework_movement_id TEXT UNIQUE REFERENCES movements(id),
    reject_movement_id TEXT UNIQUE REFERENCES movements(id),
    reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    CHECK(accepted_quantity+rework_quantity+reject_quantity>0),
    CHECK((accepted_quantity=0)=(accepted_movement_id IS NULL)),
    CHECK((rework_quantity=0)=(rework_movement_id IS NULL)),
    CHECK((reject_quantity=0)=(reject_movement_id IS NULL))
) STRICT;
CREATE INDEX IF NOT EXISTS final_qc_records_finishing ON final_qc_records(finishing_record_id,sequence);
CREATE TABLE IF NOT EXISTS final_qc_record_reversals (
    record_id TEXT PRIMARY KEY REFERENCES final_qc_records(id),
    reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;
CREATE TRIGGER IF NOT EXISTS final_qc_source_valid BEFORE INSERT ON final_qc_records
WHEN NOT EXISTS(SELECT 1 FROM finishing_records f WHERE f.id=NEW.finishing_record_id
    AND NEW.inspection_date>=f.completed_date
    AND NOT EXISTS(SELECT 1 FROM finishing_record_reversals r WHERE r.record_id=f.id))
OR NEW.accepted_quantity+NEW.rework_quantity+NEW.reject_quantity + COALESCE((
    SELECT SUM(q.accepted_quantity+q.rework_quantity+q.reject_quantity) FROM final_qc_records q
    WHERE q.finishing_record_id=NEW.finishing_record_id AND NOT EXISTS(
      SELECT 1 FROM final_qc_record_reversals r WHERE r.record_id=q.id)),0)
   > COALESCE((SELECT quantity FROM finishing_records WHERE id=NEW.finishing_record_id),0)
OR (NEW.accepted_quantity>0 AND NOT EXISTS(SELECT 1 FROM finishing_records f
    JOIN movements source ON source.id=f.movement_id JOIN movements m ON m.id=NEW.accepted_movement_id
    WHERE f.id=NEW.finishing_record_id AND m.line_id=source.line_id AND m.from_stage='qc'
      AND m.to_stage='warehouse' AND m.quantity=NEW.accepted_quantity AND m.reversal_of IS NULL
      AND NOT EXISTS(SELECT 1 FROM movements r WHERE r.reversal_of=m.id)))
OR (NEW.rework_quantity>0 AND NOT EXISTS(SELECT 1 FROM finishing_records f
    JOIN movements source ON source.id=f.movement_id JOIN movements m ON m.id=NEW.rework_movement_id
    WHERE f.id=NEW.finishing_record_id AND m.line_id=source.line_id AND m.from_stage='qc'
      AND m.to_stage='rework' AND m.quantity=NEW.rework_quantity AND m.reversal_of IS NULL
      AND NOT EXISTS(SELECT 1 FROM movements r WHERE r.reversal_of=m.id)))
OR (NEW.reject_quantity>0 AND NOT EXISTS(SELECT 1 FROM finishing_records f
    JOIN movements source ON source.id=f.movement_id JOIN movements m ON m.id=NEW.reject_movement_id
    WHERE f.id=NEW.finishing_record_id AND m.line_id=source.line_id AND m.from_stage='qc'
      AND m.to_stage='reject' AND m.quantity=NEW.reject_quantity AND m.reversal_of IS NULL
      AND NOT EXISTS(SELECT 1 FROM movements r WHERE r.reversal_of=m.id)))
BEGIN SELECT RAISE(ABORT,'Invalid final QC source, allocation, date, or movements'); END;
CREATE TRIGGER IF NOT EXISTS final_qc_reversal_valid BEFORE INSERT ON final_qc_record_reversals
WHEN NOT EXISTS(SELECT 1 FROM final_qc_records WHERE id=NEW.record_id)
OR EXISTS(SELECT 1 FROM final_qc_record_reversals WHERE record_id=NEW.record_id)
OR EXISTS(SELECT 1 FROM final_qc_records q WHERE q.id=NEW.record_id AND
   ((q.accepted_movement_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM movements WHERE reversal_of=q.accepted_movement_id))
 OR (q.rework_movement_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM movements WHERE reversal_of=q.rework_movement_id))
 OR (q.reject_movement_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM movements WHERE reversal_of=q.reject_movement_id))))
BEGIN SELECT RAISE(ABORT,'Final QC movements must be reversed with the record'); END;
CREATE TRIGGER IF NOT EXISTS final_qc_blocks_finishing_reversal BEFORE INSERT ON finishing_record_reversals
WHEN EXISTS(SELECT 1 FROM final_qc_records q WHERE q.finishing_record_id=NEW.record_id
    AND NOT EXISTS(SELECT 1 FROM final_qc_record_reversals r WHERE r.record_id=q.id))
BEGIN SELECT RAISE(ABORT,'Active final QC record blocks finishing reversal'); END;
CREATE TRIGGER IF NOT EXISTS final_qc_records_no_update BEFORE UPDATE ON final_qc_records
BEGIN SELECT RAISE(ABORT,'Immutable final QC record'); END;
CREATE TRIGGER IF NOT EXISTS final_qc_records_no_delete BEFORE DELETE ON final_qc_records
BEGIN SELECT RAISE(ABORT,'Immutable final QC record'); END;
CREATE TRIGGER IF NOT EXISTS final_qc_reversals_no_update BEFORE UPDATE ON final_qc_record_reversals
BEGIN SELECT RAISE(ABORT,'Immutable final QC reversal'); END;
CREATE TRIGGER IF NOT EXISTS final_qc_reversals_no_delete BEFORE DELETE ON final_qc_record_reversals
BEGIN SELECT RAISE(ABORT,'Immutable final QC reversal'); END;
PRAGMA user_version=17;
COMMIT;
