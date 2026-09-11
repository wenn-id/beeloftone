BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS bom_revisions (
    revision INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id TEXT NOT NULL REFERENCES products(id),
    components TEXT NOT NULL CHECK(json_valid(components) AND json_array_length(components) BETWEEN 1 AND 100),
    reason TEXT NOT NULL CHECK(length(trim(reason)) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;
CREATE INDEX IF NOT EXISTS bom_product_revision ON bom_revisions(product_id,revision);
CREATE TRIGGER IF NOT EXISTS bom_no_update BEFORE UPDATE ON bom_revisions
BEGIN SELECT RAISE(ABORT,'BOM history cannot be updated'); END;
CREATE TRIGGER IF NOT EXISTS bom_no_delete BEFORE DELETE ON bom_revisions
BEGIN SELECT RAISE(ABORT,'BOM history cannot be deleted'); END;
PRAGMA user_version=5;
COMMIT;
