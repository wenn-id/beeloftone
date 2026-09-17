BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS rework_completions (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    reference TEXT NOT NULL UNIQUE COLLATE NOCASE CHECK(reference=trim(reference) AND length(reference) BETWEEN 1 AND 160),
    final_qc_record_id TEXT NOT NULL REFERENCES final_qc_records(id),
    quantity INTEGER NOT NULL CHECK(quantity>0),
    completed_date TEXT NOT NULL CHECK(date(completed_date)=completed_date),
    movement_id TEXT NOT NULL UNIQUE REFERENCES movements(id),
    reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;
CREATE INDEX IF NOT EXISTS rework_completions_final_qc ON rework_completions(final_qc_record_id,sequence);
CREATE TABLE IF NOT EXISTS rework_completion_reversals (
    record_id TEXT PRIMARY KEY REFERENCES rework_completions(id),
    reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;
CREATE INDEX IF NOT EXISTS final_qc_records_rework_completion ON final_qc_records(rework_completion_id,sequence);
CREATE TRIGGER IF NOT EXISTS rework_completion_source_valid BEFORE INSERT ON rework_completions
WHEN NOT EXISTS(SELECT 1 FROM final_qc_records q WHERE q.id=NEW.final_qc_record_id
    AND q.rework_quantity>0 AND NEW.completed_date>=q.inspection_date
    AND NOT EXISTS(SELECT 1 FROM final_qc_record_reversals r WHERE r.record_id=q.id))
OR NEW.quantity + COALESCE((SELECT SUM(c.quantity) FROM rework_completions c
    WHERE c.final_qc_record_id=NEW.final_qc_record_id AND NOT EXISTS(
      SELECT 1 FROM rework_completion_reversals r WHERE r.record_id=c.id)),0)
   > COALESCE((SELECT rework_quantity FROM final_qc_records WHERE id=NEW.final_qc_record_id),0)
OR NOT EXISTS(SELECT 1 FROM final_qc_records q JOIN finishing_records f ON f.id=q.finishing_record_id
    JOIN movements source ON source.id=f.movement_id JOIN movements m ON m.id=NEW.movement_id
    WHERE q.id=NEW.final_qc_record_id AND m.line_id=source.line_id AND m.from_stage='rework'
      AND m.to_stage='qc' AND m.quantity=NEW.quantity AND m.reversal_of IS NULL
      AND NOT EXISTS(SELECT 1 FROM movements r WHERE r.reversal_of=m.id))
BEGIN SELECT RAISE(ABORT,'Invalid rework completion source, allocation, date, or movement'); END;
CREATE TRIGGER IF NOT EXISTS rework_completion_reversal_valid BEFORE INSERT ON rework_completion_reversals
WHEN NOT EXISTS(SELECT 1 FROM rework_completions WHERE id=NEW.record_id)
OR EXISTS(SELECT 1 FROM rework_completion_reversals WHERE record_id=NEW.record_id)
OR NOT EXISTS(SELECT 1 FROM rework_completions c JOIN movements r ON r.reversal_of=c.movement_id
    WHERE c.id=NEW.record_id)
BEGIN SELECT RAISE(ABORT,'Rework completion movement must be reversed with its record'); END;
CREATE TRIGGER IF NOT EXISTS final_qc_blocks_rework_completion_reversal BEFORE INSERT ON rework_completion_reversals
WHEN EXISTS(SELECT 1 FROM final_qc_records q WHERE q.rework_completion_id=NEW.record_id
    AND NOT EXISTS(SELECT 1 FROM final_qc_record_reversals r WHERE r.record_id=q.id))
BEGIN SELECT RAISE(ABORT,'Active reinspection blocks rework completion reversal'); END;
CREATE TRIGGER IF NOT EXISTS rework_completion_blocks_final_qc_reversal BEFORE INSERT ON final_qc_record_reversals
WHEN EXISTS(SELECT 1 FROM rework_completions c WHERE c.final_qc_record_id=NEW.record_id
    AND NOT EXISTS(SELECT 1 FROM rework_completion_reversals r WHERE r.record_id=c.id))
BEGIN SELECT RAISE(ABORT,'Active rework completion blocks final QC reversal'); END;
CREATE TRIGGER IF NOT EXISTS rework_completions_no_update BEFORE UPDATE ON rework_completions
BEGIN SELECT RAISE(ABORT,'Immutable rework completion'); END;
CREATE TRIGGER IF NOT EXISTS rework_completions_no_delete BEFORE DELETE ON rework_completions
BEGIN SELECT RAISE(ABORT,'Immutable rework completion'); END;
CREATE TRIGGER IF NOT EXISTS rework_completion_reversals_no_update BEFORE UPDATE ON rework_completion_reversals
BEGIN SELECT RAISE(ABORT,'Immutable rework completion reversal'); END;
CREATE TRIGGER IF NOT EXISTS rework_completion_reversals_no_delete BEFORE DELETE ON rework_completion_reversals
BEGIN SELECT RAISE(ABORT,'Immutable rework completion reversal'); END;
DROP TRIGGER IF EXISTS final_qc_source_valid;
CREATE TRIGGER final_qc_source_valid BEFORE INSERT ON final_qc_records
WHEN (NEW.rework_completion_id IS NULL)<>(NEW.inspection_round=1)
OR NOT EXISTS(SELECT 1 FROM finishing_records f WHERE f.id=NEW.finishing_record_id
    AND NEW.inspection_date>=f.completed_date
    AND NOT EXISTS(SELECT 1 FROM finishing_record_reversals r WHERE r.record_id=f.id))
OR (NEW.rework_completion_id IS NULL AND
    NEW.accepted_quantity+NEW.rework_quantity+NEW.reject_quantity + COALESCE((
      SELECT SUM(q.accepted_quantity+q.rework_quantity+q.reject_quantity) FROM final_qc_records q
      WHERE q.finishing_record_id=NEW.finishing_record_id AND q.rework_completion_id IS NULL
        AND NOT EXISTS(SELECT 1 FROM final_qc_record_reversals r WHERE r.record_id=q.id)),0)
    > COALESCE((SELECT quantity FROM finishing_records WHERE id=NEW.finishing_record_id),0))
OR (NEW.rework_completion_id IS NOT NULL AND NOT EXISTS(
    SELECT 1 FROM rework_completions c JOIN final_qc_records q ON q.id=c.final_qc_record_id
    WHERE c.id=NEW.rework_completion_id AND q.finishing_record_id=NEW.finishing_record_id
      AND NEW.inspection_date>=c.completed_date AND NEW.inspection_round=q.inspection_round+1
      AND NOT EXISTS(SELECT 1 FROM rework_completion_reversals r WHERE r.record_id=c.id)
      AND NOT EXISTS(SELECT 1 FROM final_qc_record_reversals r WHERE r.record_id=q.id)))
OR (NEW.rework_completion_id IS NOT NULL AND
    NEW.accepted_quantity+NEW.rework_quantity+NEW.reject_quantity + COALESCE((
      SELECT SUM(q.accepted_quantity+q.rework_quantity+q.reject_quantity) FROM final_qc_records q
      WHERE q.rework_completion_id=NEW.rework_completion_id AND NOT EXISTS(
        SELECT 1 FROM final_qc_record_reversals r WHERE r.record_id=q.id)),0)
    > COALESCE((SELECT quantity FROM rework_completions WHERE id=NEW.rework_completion_id),0))
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
BEGIN SELECT RAISE(ABORT,'Invalid final QC source, allocation, round, date, or movements'); END;
PRAGMA user_version=55;
COMMIT;
