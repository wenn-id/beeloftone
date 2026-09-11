BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS suppliers (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL UNIQUE CHECK(length(trim(code)) BETWEEN 1 AND 160),
    name TEXT NOT NULL CHECK(length(trim(name)) BETWEEN 1 AND 160),
    contact TEXT NOT NULL CHECK(length(contact)<=500),
    address TEXT NOT NULL CHECK(length(address)<=1000),
    reason TEXT NOT NULL CHECK(length(trim(reason)) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;
CREATE TABLE IF NOT EXISTS purchase_orders (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    reference TEXT NOT NULL UNIQUE CHECK(length(trim(reference)) BETWEEN 1 AND 160),
    request_id TEXT NOT NULL REFERENCES purchase_requests(id),
    request_revision INTEGER NOT NULL REFERENCES purchase_request_events(sequence),
    supplier_id TEXT NOT NULL REFERENCES suppliers(id),
    supplier TEXT NOT NULL CHECK(json_valid(supplier)),
    expected_date TEXT NOT NULL,
    terms TEXT NOT NULL CHECK(length(trim(terms)) BETWEEN 1 AND 1000),
    lines TEXT NOT NULL CHECK(json_valid(lines) AND json_array_length(lines) BETWEEN 1 AND 100),
    total_minor INTEGER NOT NULL CHECK(total_minor BETWEEN 1 AND 100000000000000),
    reason TEXT NOT NULL CHECK(length(trim(reason)) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;
CREATE INDEX IF NOT EXISTS purchase_orders_request ON purchase_orders(request_id,sequence);
CREATE TABLE IF NOT EXISTS purchase_order_cancellations (
    id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL UNIQUE REFERENCES purchase_orders(id),
    reason TEXT NOT NULL CHECK(length(trim(reason)) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;
CREATE TRIGGER IF NOT EXISTS purchase_order_valid_request BEFORE INSERT ON purchase_orders
WHEN NOT EXISTS(SELECT 1 FROM purchase_request_events e JOIN purchase_requests p ON p.id=e.request_id
    WHERE p.id=NEW.request_id AND e.sequence=NEW.request_revision AND e.status='approved'
    AND e.sequence=(SELECT MAX(sequence) FROM purchase_request_events WHERE request_id=p.id)
    AND NEW.total_minor<=p.estimated_value_minor)
BEGIN SELECT RAISE(ABORT,'PO requires current approved PR and approved budget'); END;
CREATE TRIGGER IF NOT EXISTS purchase_order_single_active BEFORE INSERT ON purchase_orders
WHEN EXISTS(SELECT 1 FROM purchase_orders p WHERE p.request_id=NEW.request_id
    AND NOT EXISTS(SELECT 1 FROM purchase_order_cancellations c WHERE c.order_id=p.id))
BEGIN SELECT RAISE(ABORT,'PR already has an active PO'); END;
CREATE TRIGGER IF NOT EXISTS purchase_request_active_po BEFORE INSERT ON purchase_request_events
WHEN NEW.status='cancelled' AND EXISTS(SELECT 1 FROM purchase_orders p WHERE p.request_id=NEW.request_id
    AND NOT EXISTS(SELECT 1 FROM purchase_order_cancellations c WHERE c.order_id=p.id))
BEGIN SELECT RAISE(ABORT,'Cancel active PO before cancelling PR'); END;
CREATE TRIGGER IF NOT EXISTS supplier_no_update BEFORE UPDATE ON suppliers
BEGIN SELECT RAISE(ABORT,'Suppliers cannot be updated'); END;
CREATE TRIGGER IF NOT EXISTS supplier_no_delete BEFORE DELETE ON suppliers
BEGIN SELECT RAISE(ABORT,'Suppliers cannot be deleted'); END;
CREATE TRIGGER IF NOT EXISTS purchase_order_no_update BEFORE UPDATE ON purchase_orders
BEGIN SELECT RAISE(ABORT,'Purchase orders cannot be updated'); END;
CREATE TRIGGER IF NOT EXISTS purchase_order_no_delete BEFORE DELETE ON purchase_orders
BEGIN SELECT RAISE(ABORT,'Purchase orders cannot be deleted'); END;
CREATE TRIGGER IF NOT EXISTS purchase_order_cancel_no_update BEFORE UPDATE ON purchase_order_cancellations
BEGIN SELECT RAISE(ABORT,'PO cancellations cannot be updated'); END;
CREATE TRIGGER IF NOT EXISTS purchase_order_cancel_no_delete BEFORE DELETE ON purchase_order_cancellations
BEGIN SELECT RAISE(ABORT,'PO cancellations cannot be deleted'); END;
PRAGMA user_version=9;
COMMIT;
