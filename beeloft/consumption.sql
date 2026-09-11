BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS material_consumption (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    issue_id TEXT NOT NULL REFERENCES material_movements(id),
    used_milli INTEGER NOT NULL CHECK(abs(used_milli)<=1000000000),
    waste_milli INTEGER NOT NULL CHECK(abs(waste_milli)<=1000000000),
    reversal_of TEXT UNIQUE REFERENCES material_consumption(id),
    reason TEXT NOT NULL CHECK(length(trim(reason)) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    CHECK((reversal_of IS NULL AND used_milli>=0 AND waste_milli>=0 AND used_milli+waste_milli>0)
        OR (reversal_of IS NOT NULL AND used_milli<=0 AND waste_milli<=0 AND used_milli+waste_milli<0))
) STRICT;
CREATE INDEX IF NOT EXISTS consumption_issue_history ON material_consumption(issue_id,sequence);
CREATE TRIGGER IF NOT EXISTS consumption_valid_issue BEFORE INSERT ON material_consumption
WHEN NOT EXISTS(SELECT 1 FROM material_movements m WHERE m.id=NEW.issue_id AND m.kind='issue'
    AND NOT EXISTS(SELECT 1 FROM material_movements r WHERE r.reversal_of=m.id))
BEGIN SELECT RAISE(ABORT,'Consumption requires an unreversed issue'); END;
CREATE TRIGGER IF NOT EXISTS consumption_within_issue BEFORE INSERT ON material_consumption
WHEN COALESCE((SELECT SUM(used_milli+waste_milli) FROM material_consumption WHERE issue_id=NEW.issue_id),0)+NEW.used_milli+NEW.waste_milli>
    (SELECT -quantity_milli FROM material_movements WHERE id=NEW.issue_id)
BEGIN SELECT RAISE(ABORT,'Consumption exceeds issued amount'); END;
CREATE TRIGGER IF NOT EXISTS consumption_reversal_matches BEFORE INSERT ON material_consumption
WHEN NEW.reversal_of IS NOT NULL AND NOT EXISTS(SELECT 1 FROM material_consumption c WHERE c.id=NEW.reversal_of
    AND c.reversal_of IS NULL AND c.issue_id=NEW.issue_id AND c.used_milli=-NEW.used_milli AND c.waste_milli=-NEW.waste_milli)
BEGIN SELECT RAISE(ABORT,'Invalid consumption reversal'); END;
CREATE TRIGGER IF NOT EXISTS consumption_no_update BEFORE UPDATE ON material_consumption
BEGIN SELECT RAISE(ABORT,'Consumption history cannot be updated'); END;
CREATE TRIGGER IF NOT EXISTS consumption_no_delete BEFORE DELETE ON material_consumption
BEGIN SELECT RAISE(ABORT,'Consumption history cannot be deleted'); END;
PRAGMA user_version=7;
COMMIT;
