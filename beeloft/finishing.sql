BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS finishing_records (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    reference TEXT NOT NULL UNIQUE COLLATE NOCASE CHECK(reference=trim(reference) AND length(reference) BETWEEN 1 AND 160),
    job_id TEXT NOT NULL REFERENCES sewing_jobs(id),
    quantity INTEGER NOT NULL CHECK(quantity>0),
    thread_trimmed INTEGER NOT NULL CHECK(thread_trimmed=1),
    ironed INTEGER NOT NULL CHECK(ironed=1),
    labels_attached INTEGER NOT NULL CHECK(labels_attached=1),
    hangtags_attached INTEGER NOT NULL CHECK(hangtags_attached=1),
    packaged INTEGER NOT NULL CHECK(packaged=1),
    completed_date TEXT NOT NULL CHECK(date(completed_date)=completed_date),
    movement_id TEXT NOT NULL UNIQUE REFERENCES movements(id),
    reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;
CREATE INDEX IF NOT EXISTS finishing_records_job ON finishing_records(job_id,sequence);
CREATE TABLE IF NOT EXISTS finishing_record_reversals (
    record_id TEXT PRIMARY KEY REFERENCES finishing_records(id),
    reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;
CREATE TRIGGER IF NOT EXISTS finishing_record_source_valid BEFORE INSERT ON finishing_records
WHEN NOT EXISTS(SELECT 1 FROM sewing_jobs j JOIN sewing_job_results x ON x.job_id=j.id
    WHERE j.id=NEW.job_id AND NEW.completed_date>=x.returned_date
      AND NOT EXISTS(SELECT 1 FROM sewing_job_reversals r WHERE r.job_id=j.id))
OR NEW.quantity + COALESCE((SELECT SUM(f.quantity) FROM finishing_records f
    WHERE f.job_id=NEW.job_id AND NOT EXISTS(
      SELECT 1 FROM finishing_record_reversals r WHERE r.record_id=f.id)),0)
   > COALESCE((SELECT completed_quantity FROM sewing_job_results WHERE job_id=NEW.job_id),0)
OR NOT EXISTS(SELECT 1 FROM sewing_jobs j JOIN bundles b ON b.id=j.bundle_id
    JOIN movements source ON source.id=b.output_movement_id JOIN movements m ON m.id=NEW.movement_id
    WHERE j.id=NEW.job_id AND m.line_id=source.line_id AND m.from_stage='finishing'
      AND m.to_stage='qc' AND m.quantity=NEW.quantity AND m.reversal_of IS NULL
      AND NOT EXISTS(SELECT 1 FROM movements r WHERE r.reversal_of=m.id))
BEGIN SELECT RAISE(ABORT,'Invalid finishing source, allocation, date, or movement'); END;
CREATE TRIGGER IF NOT EXISTS finishing_reversal_valid BEFORE INSERT ON finishing_record_reversals
WHEN NOT EXISTS(SELECT 1 FROM finishing_records WHERE id=NEW.record_id)
OR EXISTS(SELECT 1 FROM finishing_record_reversals WHERE record_id=NEW.record_id)
OR NOT EXISTS(SELECT 1 FROM finishing_records f JOIN movements r ON r.reversal_of=f.movement_id
    WHERE f.id=NEW.record_id)
BEGIN SELECT RAISE(ABORT,'Finishing movement must be reversed with its record'); END;
CREATE TRIGGER IF NOT EXISTS finishing_blocks_sewing_reversal BEFORE INSERT ON sewing_job_reversals
WHEN EXISTS(SELECT 1 FROM finishing_records f WHERE f.job_id=NEW.job_id
    AND NOT EXISTS(SELECT 1 FROM finishing_record_reversals r WHERE r.record_id=f.id))
BEGIN SELECT RAISE(ABORT,'Active finishing record blocks sewing reversal'); END;
CREATE TRIGGER IF NOT EXISTS finishing_records_no_update BEFORE UPDATE ON finishing_records
BEGIN SELECT RAISE(ABORT,'Immutable finishing record'); END;
CREATE TRIGGER IF NOT EXISTS finishing_records_no_delete BEFORE DELETE ON finishing_records
BEGIN SELECT RAISE(ABORT,'Immutable finishing record'); END;
CREATE TRIGGER IF NOT EXISTS finishing_reversals_no_update BEFORE UPDATE ON finishing_record_reversals
BEGIN SELECT RAISE(ABORT,'Immutable finishing reversal'); END;
CREATE TRIGGER IF NOT EXISTS finishing_reversals_no_delete BEFORE DELETE ON finishing_record_reversals
BEGIN SELECT RAISE(ABORT,'Immutable finishing reversal'); END;
PRAGMA user_version=16;
COMMIT;
