BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS order_changes (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    order_id TEXT NOT NULL REFERENCES orders(id),
    old_due_date TEXT NOT NULL,
    new_due_date TEXT NOT NULL,
    old_owner_id TEXT NOT NULL REFERENCES users(id),
    new_owner_id TEXT NOT NULL REFERENCES users(id),
    reason TEXT NOT NULL CHECK(length(trim(reason)) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    CHECK(old_due_date != new_due_date OR old_owner_id != new_owner_id)
) STRICT;
CREATE INDEX IF NOT EXISTS order_changes_order ON order_changes(order_id,sequence);
CREATE TRIGGER IF NOT EXISTS order_changes_no_update BEFORE UPDATE ON order_changes
BEGIN SELECT RAISE(ABORT,'Order change history cannot be updated'); END;
CREATE TRIGGER IF NOT EXISTS order_changes_no_delete BEFORE DELETE ON order_changes
BEGIN SELECT RAISE(ABORT,'Order change history cannot be deleted'); END;
PRAGMA user_version=3;
COMMIT;
