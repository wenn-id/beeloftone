BEGIN IMMEDIATE;

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL CHECK(length(trim(name)) > 0),
    role TEXT NOT NULL CHECK(role IN ('admin', 'operator', 'viewer')),
    key_hash TEXT NOT NULL UNIQUE,
    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0, 1)),
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS products (
    id TEXT PRIMARY KEY,
    sku TEXT NOT NULL UNIQUE COLLATE NOCASE,
    name TEXT NOT NULL,
    color TEXT NOT NULL,
    size TEXT NOT NULL,
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS orders (
    id TEXT PRIMARY KEY,
    reference TEXT NOT NULL UNIQUE COLLATE NOCASE,
    title TEXT NOT NULL,
    owner_id TEXT NOT NULL REFERENCES users(id),
    due_date TEXT NOT NULL,
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS order_lines (
    id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(id),
    product_id TEXT NOT NULL REFERENCES products(id),
    quantity INTEGER NOT NULL CHECK(quantity > 0 AND quantity <= 1000000000),
    UNIQUE(order_id, product_id)
) STRICT;

CREATE TABLE IF NOT EXISTS balances (
    line_id TEXT NOT NULL REFERENCES order_lines(id),
    stage TEXT NOT NULL CHECK(stage IN ('planned', 'cutting', 'sewing', 'finishing', 'qc', 'rework', 'reject', 'warehouse')),
    quantity INTEGER NOT NULL CHECK(quantity >= 0),
    PRIMARY KEY(line_id, stage)
) STRICT;

CREATE TABLE IF NOT EXISTS movements (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    line_id TEXT NOT NULL REFERENCES order_lines(id),
    from_stage TEXT NOT NULL,
    to_stage TEXT NOT NULL CHECK(to_stage != from_stage),
    quantity INTEGER NOT NULL CHECK(quantity > 0),
    reason TEXT NOT NULL,
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    reversal_of TEXT UNIQUE REFERENCES movements(id),
    FOREIGN KEY(line_id, from_stage) REFERENCES balances(line_id, stage),
    FOREIGN KEY(line_id, to_stage) REFERENCES balances(line_id, stage)
) STRICT;
CREATE INDEX IF NOT EXISTS movements_line ON movements(line_id, sequence);
CREATE INDEX IF NOT EXISTS orders_due ON orders(due_date);

CREATE TABLE IF NOT EXISTS requests (
    actor_id TEXT NOT NULL REFERENCES users(id),
    key TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    response TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY(actor_id, key)
) STRICT;

CREATE TRIGGER IF NOT EXISTS movements_no_update BEFORE UPDATE ON movements
BEGIN SELECT RAISE(ABORT, 'Movement history is immutable'); END;
CREATE TRIGGER IF NOT EXISTS movements_no_delete BEFORE DELETE ON movements
BEGIN SELECT RAISE(ABORT, 'Movement history is immutable'); END;

PRAGMA user_version = 1;
COMMIT;
