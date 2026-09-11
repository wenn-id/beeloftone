BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS supplier_returns (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    intake_id TEXT NOT NULL REFERENCES qc_intakes(id),
    reference TEXT UNIQUE COLLATE NOCASE,
    returned_date TEXT,
    quantity_milli INTEGER NOT NULL CHECK(quantity_milli!=0 AND abs(quantity_milli)<=1000000000),
    reversal_of TEXT UNIQUE REFERENCES supplier_returns(id),
    reason TEXT NOT NULL CHECK(length(trim(reason)) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    CHECK((reversal_of IS NULL AND quantity_milli>0 AND reference IS NOT NULL
        AND length(trim(reference)) BETWEEN 1 AND 160 AND returned_date IS NOT NULL)
        OR (reversal_of IS NOT NULL AND quantity_milli<0 AND reference IS NULL AND returned_date IS NULL))
) STRICT;
CREATE INDEX IF NOT EXISTS supplier_returns_intake ON supplier_returns(intake_id,sequence);
CREATE TABLE IF NOT EXISTS purchase_order_closures (
    order_id TEXT PRIMARY KEY REFERENCES purchase_orders(id),
    reason TEXT NOT NULL CHECK(length(trim(reason)) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;
CREATE VIEW IF NOT EXISTS qc_return_totals AS
SELECT q.id,q.purchase_order_id,q.rejected,COALESCE(SUM(r.quantity_milli),0) AS returned,
    q.rejected-COALESCE(SUM(r.quantity_milli),0) AS return_pending
FROM qc_totals q LEFT JOIN supplier_returns r ON r.intake_id=q.id GROUP BY q.id;
CREATE TRIGGER IF NOT EXISTS supplier_return_valid BEFORE INSERT ON supplier_returns
WHEN EXISTS(SELECT 1 FROM qc_intake_cancellations WHERE intake_id=NEW.intake_id)
 OR EXISTS(SELECT 1 FROM qc_intakes q JOIN purchase_order_closures c ON c.order_id=q.purchase_order_id WHERE q.id=NEW.intake_id)
 OR (NEW.reversal_of IS NULL AND (NEW.quantity_milli>(SELECT return_pending FROM qc_return_totals WHERE id=NEW.intake_id)
    OR NEW.returned_date<(SELECT received_date FROM qc_intakes WHERE id=NEW.intake_id)))
 OR (NEW.reversal_of IS NOT NULL AND (NOT EXISTS(SELECT 1 FROM supplier_returns r WHERE r.id=NEW.reversal_of
    AND r.intake_id=NEW.intake_id AND r.reversal_of IS NULL AND r.quantity_milli=-NEW.quantity_milli)
    OR EXISTS(SELECT 1 FROM qc_intakes q JOIN purchase_order_cancellations c ON c.order_id=q.purchase_order_id WHERE q.id=NEW.intake_id)))
BEGIN SELECT RAISE(ABORT,'Invalid return, insufficient reject quantity, or final PO'); END;
CREATE TRIGGER IF NOT EXISTS qc_reverse_returned BEFORE INSERT ON qc_decisions
WHEN NEW.kind='reject' AND NEW.reversal_of IS NOT NULL
 AND -NEW.quantity_milli>(SELECT return_pending FROM qc_return_totals WHERE id=NEW.intake_id)
BEGIN SELECT RAISE(ABORT,'Reverse supplier return before correcting rejected quantity'); END;
CREATE TRIGGER IF NOT EXISTS po_cancel_unreturned BEFORE INSERT ON purchase_order_cancellations
WHEN EXISTS(SELECT 1 FROM qc_return_totals WHERE purchase_order_id=NEW.order_id AND return_pending>0)
 OR EXISTS(SELECT 1 FROM purchase_order_closures WHERE order_id=NEW.order_id)
BEGIN SELECT RAISE(ABORT,'Resolve returns before cancelling; closed PO is final'); END;
CREATE TRIGGER IF NOT EXISTS po_close_valid BEFORE INSERT ON purchase_order_closures
WHEN EXISTS(SELECT 1 FROM purchase_order_cancellations WHERE order_id=NEW.order_id)
 OR EXISTS(SELECT 1 FROM qc_totals WHERE purchase_order_id=NEW.order_id AND held>0)
 OR EXISTS(SELECT 1 FROM qc_return_totals WHERE purchase_order_id=NEW.order_id AND return_pending>0)
 OR NOT EXISTS(SELECT 1 FROM purchase_order_receipts x JOIN material_movements m ON m.batch_id=x.batch_id AND m.kind='receipt'
    WHERE x.purchase_order_id=NEW.order_id AND NOT EXISTS(SELECT 1 FROM material_movements WHERE reversal_of=m.id))
BEGIN SELECT RAISE(ABORT,'Closure requires active receipt, resolved QC and completed returns'); END;
CREATE TRIGGER IF NOT EXISTS po_closed_receipt BEFORE INSERT ON purchase_order_receipts
WHEN EXISTS(SELECT 1 FROM purchase_order_closures WHERE order_id=NEW.purchase_order_id)
BEGIN SELECT RAISE(ABORT,'PO is closed'); END;
CREATE TRIGGER IF NOT EXISTS po_closed_intake BEFORE INSERT ON qc_intakes
WHEN EXISTS(SELECT 1 FROM purchase_order_closures WHERE order_id=NEW.purchase_order_id)
BEGIN SELECT RAISE(ABORT,'PO is closed'); END;
CREATE TRIGGER IF NOT EXISTS po_closed_qc BEFORE INSERT ON qc_decisions
WHEN EXISTS(SELECT 1 FROM qc_intakes q JOIN purchase_order_closures c ON c.order_id=q.purchase_order_id WHERE q.id=NEW.intake_id)
BEGIN SELECT RAISE(ABORT,'PO is closed'); END;
CREATE TRIGGER IF NOT EXISTS po_closed_intake_cancel BEFORE INSERT ON qc_intake_cancellations
WHEN EXISTS(SELECT 1 FROM qc_intakes q JOIN purchase_order_closures c ON c.order_id=q.purchase_order_id WHERE q.id=NEW.intake_id)
BEGIN SELECT RAISE(ABORT,'PO is closed'); END;
CREATE TRIGGER IF NOT EXISTS po_closed_receipt_reverse BEFORE INSERT ON material_movements
WHEN NEW.reversal_of IS NOT NULL AND EXISTS(SELECT 1 FROM material_movements m
    JOIN purchase_order_receipts x ON x.batch_id=m.batch_id JOIN purchase_order_closures c ON c.order_id=x.purchase_order_id
    WHERE m.id=NEW.reversal_of AND m.kind='receipt')
BEGIN SELECT RAISE(ABORT,'Closed PO receipt cannot be reversed'); END;
CREATE TRIGGER IF NOT EXISTS supplier_returns_no_update BEFORE UPDATE ON supplier_returns
BEGIN SELECT RAISE(ABORT,'Immutable supplier return'); END;
CREATE TRIGGER IF NOT EXISTS supplier_returns_no_delete BEFORE DELETE ON supplier_returns
BEGIN SELECT RAISE(ABORT,'Immutable supplier return'); END;
CREATE TRIGGER IF NOT EXISTS po_closure_no_update BEFORE UPDATE ON purchase_order_closures
BEGIN SELECT RAISE(ABORT,'Immutable PO closure'); END;
CREATE TRIGGER IF NOT EXISTS po_closure_no_delete BEFORE DELETE ON purchase_order_closures
BEGIN SELECT RAISE(ABORT,'Immutable PO closure'); END;
PRAGMA user_version=12;
COMMIT;
