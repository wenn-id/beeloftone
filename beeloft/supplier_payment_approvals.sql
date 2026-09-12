BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS supplier_payment_requests (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    reference TEXT NOT NULL UNIQUE CHECK(length(trim(reference)) BETWEEN 1 AND 160),
    purchase_order_id TEXT NOT NULL REFERENCES purchase_orders(id),
    invoice_reference TEXT NOT NULL CHECK(length(trim(invoice_reference)) BETWEEN 1 AND 160),
    invoice_date TEXT NOT NULL,
    due_date TEXT NOT NULL,
    amount_minor INTEGER NOT NULL CHECK(amount_minor BETWEEN 1 AND 100000000000000),
    reason TEXT NOT NULL CHECK(length(trim(reason)) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    UNIQUE(purchase_order_id,invoice_reference),
    CHECK(invoice_date<=due_date)
) STRICT;
CREATE INDEX IF NOT EXISTS supplier_payment_requests_po
ON supplier_payment_requests(purchase_order_id,sequence);

CREATE TABLE IF NOT EXISTS supplier_payment_request_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL REFERENCES supplier_payment_requests(id),
    status TEXT NOT NULL CHECK(status IN ('submitted','approved','rejected','cancelled')),
    reason TEXT NOT NULL CHECK(length(trim(reason)) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;
CREATE INDEX IF NOT EXISTS supplier_payment_request_history
ON supplier_payment_request_events(request_id,sequence);

CREATE VIEW IF NOT EXISTS supplier_payment_po_received AS
SELECT p.id AS purchase_order_id,COALESCE(SUM(CAST((
    COALESCE((SELECT SUM(m.quantity_milli) FROM purchase_order_receipts x
        JOIN material_batches b ON b.id=x.batch_id
        JOIN material_movements m ON m.batch_id=b.id AND m.kind='receipt'
        WHERE x.purchase_order_id=p.id
          AND b.material_id=json_extract(line.value,'$.material_id')
          AND NOT EXISTS(SELECT 1 FROM material_movements WHERE reversal_of=m.id)),0)
    *CAST(ROUND(CAST(json_extract(line.value,'$.unit_price') AS NUMERIC)*100) AS INTEGER)+500
    )/1000 AS INTEGER)),0) AS received_value_minor
FROM purchase_orders p,json_each(p.lines) line GROUP BY p.id;

CREATE TRIGGER IF NOT EXISTS supplier_payment_request_source_valid
BEFORE INSERT ON supplier_payment_requests
WHEN NOT EXISTS(
    SELECT 1 FROM purchase_orders p JOIN users u ON u.id=NEW.actor_id
    WHERE p.id=NEW.purchase_order_id
      AND u.active=1 AND u.role IN ('admin','operator')
      AND (SELECT status FROM purchase_order_approval_events WHERE order_id=p.id
           ORDER BY sequence DESC LIMIT 1)='approved'
      AND NOT EXISTS(SELECT 1 FROM purchase_order_cancellations WHERE order_id=p.id)
      AND EXISTS(SELECT 1 FROM purchase_order_receipts x
          JOIN material_movements m ON m.batch_id=x.batch_id AND m.kind='receipt'
          WHERE x.purchase_order_id=p.id
            AND NOT EXISTS(SELECT 1 FROM material_movements WHERE reversal_of=m.id))
      AND NEW.amount_minor+COALESCE((
          SELECT SUM(r.amount_minor) FROM supplier_payment_requests r
          WHERE r.purchase_order_id=p.id AND
            (SELECT status FROM supplier_payment_request_events e WHERE e.request_id=r.id
             ORDER BY e.sequence DESC LIMIT 1) IN ('submitted','approved')),0)
          <=(SELECT received_value_minor FROM supplier_payment_po_received WHERE purchase_order_id=p.id)
)
BEGIN SELECT RAISE(ABORT,'Invalid supplier payment request source or amount'); END;

CREATE TRIGGER IF NOT EXISTS supplier_payment_request_transition
BEFORE INSERT ON supplier_payment_request_events
WHEN NOT COALESCE(
    (NEW.status='submitted' AND NOT EXISTS(
      SELECT 1 FROM supplier_payment_request_events WHERE request_id=NEW.request_id))
    OR
    (NEW.status IN ('approved','rejected','cancelled') AND
      (SELECT status FROM supplier_payment_request_events WHERE request_id=NEW.request_id
       ORDER BY sequence DESC LIMIT 1)='submitted'),0)
BEGIN SELECT RAISE(ABORT,'Invalid supplier payment request transition'); END;

CREATE TRIGGER IF NOT EXISTS supplier_payment_request_event_valid
BEFORE INSERT ON supplier_payment_request_events
WHEN NOT COALESCE(
    (NEW.status='submitted' AND EXISTS(
      SELECT 1 FROM supplier_payment_requests r JOIN users u ON u.id=NEW.actor_id
      WHERE r.id=NEW.request_id AND r.actor_id=NEW.actor_id AND r.reason=NEW.reason
        AND u.active=1 AND u.role IN ('admin','operator')))
    OR
    (NEW.status IN ('approved','rejected') AND EXISTS(
      SELECT 1 FROM users u WHERE u.id=NEW.actor_id AND u.active=1 AND u.role='admin'))
    OR
    (NEW.status='cancelled' AND EXISTS(
      SELECT 1 FROM supplier_payment_requests r JOIN users u ON u.id=NEW.actor_id
      WHERE r.id=NEW.request_id AND u.active=1
        AND (u.role='admin' OR (u.role='operator' AND r.actor_id=NEW.actor_id)))),0)
BEGIN SELECT RAISE(ABORT,'Invalid supplier payment request event'); END;

CREATE TRIGGER IF NOT EXISTS supplier_payment_request_preserve_receipt
BEFORE INSERT ON material_movements
WHEN NEW.reversal_of IS NOT NULL AND EXISTS(
    SELECT 1 FROM material_movements original
    JOIN purchase_order_receipts x ON x.batch_id=original.batch_id
    WHERE original.id=NEW.reversal_of AND original.kind='receipt'
      AND COALESCE((SELECT SUM(r.amount_minor) FROM supplier_payment_requests r
          WHERE r.purchase_order_id=x.purchase_order_id AND
            (SELECT status FROM supplier_payment_request_events e WHERE e.request_id=r.id
             ORDER BY e.sequence DESC LIMIT 1) IN ('submitted','approved')),0)
          >(SELECT COALESCE(SUM(CAST((
              COALESCE((SELECT SUM(other.quantity_milli) FROM purchase_order_receipts other_link
                  JOIN material_batches other_batch ON other_batch.id=other_link.batch_id
                  JOIN material_movements other ON other.batch_id=other_batch.id AND other.kind='receipt'
                  WHERE other_link.purchase_order_id=p.id AND other.id!=original.id
                    AND other_batch.material_id=json_extract(line.value,'$.material_id')
                    AND NOT EXISTS(SELECT 1 FROM material_movements WHERE reversal_of=other.id)),0)
              *CAST(ROUND(CAST(json_extract(line.value,'$.unit_price') AS NUMERIC)*100) AS INTEGER)+500
              )/1000 AS INTEGER)),0)
            FROM purchase_orders p,json_each(p.lines) line WHERE p.id=x.purchase_order_id)
)
BEGIN SELECT RAISE(ABORT,'Active supplier payment exceeds remaining received value'); END;

CREATE TRIGGER IF NOT EXISTS supplier_payment_request_no_update
BEFORE UPDATE ON supplier_payment_requests
BEGIN SELECT RAISE(ABORT,'Supplier payment requests cannot be updated'); END;
CREATE TRIGGER IF NOT EXISTS supplier_payment_request_no_delete
BEFORE DELETE ON supplier_payment_requests
BEGIN SELECT RAISE(ABORT,'Supplier payment requests cannot be deleted'); END;
CREATE TRIGGER IF NOT EXISTS supplier_payment_event_no_update
BEFORE UPDATE ON supplier_payment_request_events
BEGIN SELECT RAISE(ABORT,'Supplier payment approval history cannot be updated'); END;
CREATE TRIGGER IF NOT EXISTS supplier_payment_event_no_delete
BEFORE DELETE ON supplier_payment_request_events
BEGIN SELECT RAISE(ABORT,'Supplier payment approval history cannot be deleted'); END;

PRAGMA user_version=28;
COMMIT;
