BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS issues (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    line_id TEXT NOT NULL REFERENCES order_lines(id),
    stage TEXT NOT NULL,
    description TEXT NOT NULL CHECK(length(trim(description)) BETWEEN 1 AND 1000),
    owner_id TEXT NOT NULL REFERENCES users(id),
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    resolution TEXT,
    resolved_by TEXT REFERENCES users(id),
    resolved_at TEXT,
    FOREIGN KEY(line_id,stage) REFERENCES balances(line_id,stage),
    CHECK((resolution IS NULL AND resolved_by IS NULL AND resolved_at IS NULL)
       OR (resolution IS NOT NULL AND length(trim(resolution)) BETWEEN 1 AND 1000
           AND resolved_by IS NOT NULL AND resolved_at IS NOT NULL))
) STRICT;
CREATE INDEX IF NOT EXISTS issues_line ON issues(line_id,sequence);
CREATE TRIGGER IF NOT EXISTS issues_no_delete BEFORE DELETE ON issues
BEGIN SELECT RAISE(ABORT,'Issue history cannot be deleted'); END;
CREATE TRIGGER IF NOT EXISTS issues_resolution_only BEFORE UPDATE ON issues
WHEN OLD.resolved_at IS NOT NULL OR NEW.resolved_at IS NULL
 OR NEW.sequence IS NOT OLD.sequence OR NEW.id IS NOT OLD.id OR NEW.line_id IS NOT OLD.line_id
 OR NEW.stage IS NOT OLD.stage OR NEW.description IS NOT OLD.description OR NEW.owner_id IS NOT OLD.owner_id
 OR NEW.created_by IS NOT OLD.created_by OR NEW.created_at IS NOT OLD.created_at
BEGIN SELECT RAISE(ABORT,'Only the first resolution is allowed'); END;
PRAGMA user_version=2;
COMMIT;
