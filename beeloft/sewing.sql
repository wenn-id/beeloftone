BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS sewing_jobs (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    reference TEXT NOT NULL UNIQUE COLLATE NOCASE CHECK(reference=trim(reference) AND length(reference) BETWEEN 1 AND 160),
    bundle_id TEXT NOT NULL REFERENCES bundles(id),
    assignment_type TEXT NOT NULL CHECK(assignment_type IN ('internal','makloon')),
    assignee TEXT NOT NULL CHECK(assignee=trim(assignee) AND length(assignee) BETWEEN 1 AND 160),
    quantity_out INTEGER NOT NULL CHECK(quantity_out>0),
    cost_minor INTEGER NOT NULL CHECK(cost_minor>=0),
    sent_date TEXT NOT NULL CHECK(date(sent_date)=sent_date),
    reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;
CREATE INDEX IF NOT EXISTS sewing_jobs_bundle ON sewing_jobs(bundle_id,sequence);
CREATE TABLE IF NOT EXISTS sewing_job_results (
    job_id TEXT PRIMARY KEY REFERENCES sewing_jobs(id),
    completed_quantity INTEGER NOT NULL CHECK(completed_quantity>=0),
    defect_quantity INTEGER NOT NULL CHECK(defect_quantity>=0),
    missing_quantity INTEGER NOT NULL CHECK(missing_quantity>=0),
    returned_date TEXT NOT NULL CHECK(date(returned_date)=returned_date),
    completion_movement_id TEXT UNIQUE REFERENCES movements(id),
    reject_movement_id TEXT UNIQUE REFERENCES movements(id),
    reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    CHECK((completed_quantity=0)=(completion_movement_id IS NULL)),
    CHECK((defect_quantity+missing_quantity=0)=(reject_movement_id IS NULL))
) STRICT;
CREATE TABLE IF NOT EXISTS sewing_job_reversals (
    job_id TEXT PRIMARY KEY REFERENCES sewing_jobs(id),
    reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;
CREATE TRIGGER IF NOT EXISTS sewing_job_source_valid BEFORE INSERT ON sewing_jobs
WHEN NOT EXISTS(SELECT 1 FROM bundles b WHERE b.id=NEW.bundle_id
    AND NOT EXISTS(SELECT 1 FROM bundle_reversals x WHERE x.bundle_id=b.id))
OR NEW.quantity_out + COALESCE((SELECT SUM(j.quantity_out) FROM sewing_jobs j
    WHERE j.bundle_id=NEW.bundle_id
      AND NOT EXISTS(SELECT 1 FROM sewing_job_reversals x WHERE x.job_id=j.id)),0)
   > COALESCE((SELECT quantity FROM bundles WHERE id=NEW.bundle_id),0)
BEGIN SELECT RAISE(ABORT,'Sewing job requires active unallocated bundle quantity'); END;
CREATE TRIGGER IF NOT EXISTS sewing_job_result_valid BEFORE INSERT ON sewing_job_results
WHEN NOT EXISTS(SELECT 1 FROM sewing_jobs j WHERE j.id=NEW.job_id
    AND NOT EXISTS(SELECT 1 FROM sewing_job_reversals x WHERE x.job_id=j.id)
    AND NEW.returned_date>=j.sent_date
    AND NEW.completed_quantity+NEW.defect_quantity+NEW.missing_quantity=j.quantity_out)
OR (NEW.completed_quantity>0 AND NOT EXISTS(
    SELECT 1 FROM sewing_jobs j JOIN bundles b ON b.id=j.bundle_id
    JOIN movements source ON source.id=b.output_movement_id
    JOIN movements m ON m.id=NEW.completion_movement_id
    WHERE j.id=NEW.job_id AND m.line_id=source.line_id AND m.from_stage='sewing'
      AND m.to_stage='finishing' AND m.quantity=NEW.completed_quantity AND m.reversal_of IS NULL
      AND NOT EXISTS(SELECT 1 FROM movements r WHERE r.reversal_of=m.id)))
OR (NEW.defect_quantity+NEW.missing_quantity>0 AND NOT EXISTS(
    SELECT 1 FROM sewing_jobs j JOIN bundles b ON b.id=j.bundle_id
    JOIN movements source ON source.id=b.output_movement_id
    JOIN movements m ON m.id=NEW.reject_movement_id
    WHERE j.id=NEW.job_id AND m.line_id=source.line_id AND m.from_stage='sewing'
      AND m.to_stage='reject' AND m.quantity=NEW.defect_quantity+NEW.missing_quantity
      AND m.reversal_of IS NULL AND NOT EXISTS(SELECT 1 FROM movements r WHERE r.reversal_of=m.id)))
BEGIN SELECT RAISE(ABORT,'Invalid sewing result or linked WIP movements'); END;
CREATE TRIGGER IF NOT EXISTS sewing_job_reversal_valid BEFORE INSERT ON sewing_job_reversals
WHEN NOT EXISTS(SELECT 1 FROM sewing_jobs WHERE id=NEW.job_id)
OR EXISTS(SELECT 1 FROM sewing_job_reversals WHERE job_id=NEW.job_id)
OR EXISTS(SELECT 1 FROM sewing_job_results x WHERE x.job_id=NEW.job_id AND
    ((x.completion_movement_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM movements WHERE reversal_of=x.completion_movement_id))
     OR (x.reject_movement_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM movements WHERE reversal_of=x.reject_movement_id))))
BEGIN SELECT RAISE(ABORT,'Sewing job result movements must be reversed together'); END;
CREATE TRIGGER IF NOT EXISTS sewing_job_blocks_bundle_reversal BEFORE INSERT ON bundle_reversals
WHEN EXISTS(SELECT 1 FROM sewing_jobs j WHERE j.bundle_id=NEW.bundle_id
    AND NOT EXISTS(SELECT 1 FROM sewing_job_reversals x WHERE x.job_id=j.id))
BEGIN SELECT RAISE(ABORT,'Active sewing job blocks bundle reversal'); END;
CREATE TRIGGER IF NOT EXISTS sewing_jobs_no_update BEFORE UPDATE ON sewing_jobs
BEGIN SELECT RAISE(ABORT,'Immutable sewing job'); END;
CREATE TRIGGER IF NOT EXISTS sewing_jobs_no_delete BEFORE DELETE ON sewing_jobs
BEGIN SELECT RAISE(ABORT,'Immutable sewing job'); END;
CREATE TRIGGER IF NOT EXISTS sewing_results_no_update BEFORE UPDATE ON sewing_job_results
BEGIN SELECT RAISE(ABORT,'Immutable sewing result'); END;
CREATE TRIGGER IF NOT EXISTS sewing_results_no_delete BEFORE DELETE ON sewing_job_results
BEGIN SELECT RAISE(ABORT,'Immutable sewing result'); END;
CREATE TRIGGER IF NOT EXISTS sewing_reversals_no_update BEFORE UPDATE ON sewing_job_reversals
BEGIN SELECT RAISE(ABORT,'Immutable sewing reversal'); END;
CREATE TRIGGER IF NOT EXISTS sewing_reversals_no_delete BEFORE DELETE ON sewing_job_reversals
BEGIN SELECT RAISE(ABORT,'Immutable sewing reversal'); END;
PRAGMA user_version=15;
COMMIT;
