BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS qc_intakes (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    purchase_order_id TEXT NOT NULL REFERENCES purchase_orders(id),
    material_id TEXT NOT NULL REFERENCES materials(id),
    reference TEXT NOT NULL UNIQUE COLLATE NOCASE,
    location TEXT NOT NULL,
    received_date TEXT NOT NULL,
    quantity_milli INTEGER NOT NULL CHECK(quantity_milli BETWEEN 1 AND 1000000000),
    reason TEXT NOT NULL CHECK(length(trim(reason)) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;
CREATE INDEX IF NOT EXISTS qc_intakes_po ON qc_intakes(purchase_order_id,sequence);
CREATE TABLE IF NOT EXISTS qc_decisions (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    intake_id TEXT NOT NULL REFERENCES qc_intakes(id),
    kind TEXT NOT NULL CHECK(kind IN ('accept','reject')),
    quantity_milli INTEGER NOT NULL CHECK(quantity_milli!=0 AND abs(quantity_milli)<=1000000000),
    batch_id TEXT UNIQUE REFERENCES material_batches(id),
    reversal_of TEXT UNIQUE REFERENCES qc_decisions(id),
    reason TEXT NOT NULL CHECK(length(trim(reason)) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    CHECK((reversal_of IS NULL AND quantity_milli>0 AND ((kind='accept' AND batch_id IS NOT NULL) OR (kind='reject' AND batch_id IS NULL)))
       OR (reversal_of IS NOT NULL AND quantity_milli<0 AND batch_id IS NULL))
) STRICT;
CREATE INDEX IF NOT EXISTS qc_decisions_intake ON qc_decisions(intake_id,sequence);
CREATE TABLE IF NOT EXISTS qc_intake_cancellations (
    intake_id TEXT PRIMARY KEY REFERENCES qc_intakes(id),
    reason TEXT NOT NULL CHECK(length(trim(reason)) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;
CREATE VIEW IF NOT EXISTS qc_totals AS
SELECT q.id, q.purchase_order_id, q.material_id,
    COALESCE(SUM(CASE WHEN d.kind='accept' THEN d.quantity_milli ELSE 0 END),0) AS accepted,
    COALESCE(SUM(CASE WHEN d.kind='reject' THEN d.quantity_milli ELSE 0 END),0) AS rejected,
    CASE WHEN c.intake_id IS NULL THEN q.quantity_milli-COALESCE(SUM(d.quantity_milli),0) ELSE 0 END AS held
FROM qc_intakes q LEFT JOIN qc_decisions d ON d.intake_id=q.id
LEFT JOIN qc_intake_cancellations c ON c.intake_id=q.id GROUP BY q.id;
CREATE VIEW IF NOT EXISTS po_material_committed AS
SELECT purchase_order_id,material_id,SUM(quantity_milli) AS quantity_milli FROM (
    SELECT x.purchase_order_id,b.material_id,m.quantity_milli FROM purchase_order_receipts x
    JOIN material_batches b ON b.id=x.batch_id JOIN material_movements m ON m.batch_id=b.id AND m.kind='receipt'
    WHERE NOT EXISTS(SELECT 1 FROM material_movements WHERE reversal_of=m.id)
    UNION ALL SELECT purchase_order_id,material_id,held FROM qc_totals
) GROUP BY purchase_order_id,material_id;
DROP TRIGGER IF EXISTS po_receipt_valid;
CREATE TRIGGER po_receipt_valid BEFORE INSERT ON purchase_order_receipts
WHEN EXISTS(SELECT 1 FROM purchase_order_cancellations WHERE order_id=NEW.purchase_order_id)
 OR NOT EXISTS(SELECT 1 FROM purchase_orders p, json_each(p.lines) l
    JOIN material_batches b ON b.id=NEW.batch_id
    JOIN material_movements m ON m.batch_id=b.id AND m.kind='receipt'
    WHERE p.id=NEW.purchase_order_id AND json_extract(l.value,'$.material_id')=b.material_id
    AND NOT EXISTS(SELECT 1 FROM material_movements WHERE reversal_of=m.id)
    AND m.quantity_milli+COALESCE((SELECT quantity_milli FROM po_material_committed
        WHERE purchase_order_id=p.id AND material_id=b.material_id),0)
        <=CAST(ROUND(json_extract(l.value,'$.quantity')*1000) AS INTEGER))
BEGIN SELECT RAISE(ABORT,'Receipt exceeds PO including held material'); END;
CREATE TRIGGER IF NOT EXISTS qc_intake_valid BEFORE INSERT ON qc_intakes
WHEN EXISTS(SELECT 1 FROM purchase_order_cancellations WHERE order_id=NEW.purchase_order_id)
 OR NOT EXISTS(SELECT 1 FROM purchase_orders p,json_each(p.lines) l WHERE p.id=NEW.purchase_order_id
    AND json_extract(l.value,'$.material_id')=NEW.material_id
    AND NEW.quantity_milli+COALESCE((SELECT quantity_milli FROM po_material_committed
        WHERE purchase_order_id=p.id AND material_id=NEW.material_id),0)
        <=CAST(ROUND(json_extract(l.value,'$.quantity')*1000) AS INTEGER))
BEGIN SELECT RAISE(ABORT,'Intake exceeds remaining PO including held material'); END;
CREATE TRIGGER IF NOT EXISTS qc_decision_valid BEFORE INSERT ON qc_decisions
WHEN EXISTS(SELECT 1 FROM qc_intake_cancellations WHERE intake_id=NEW.intake_id)
 OR EXISTS(SELECT 1 FROM qc_intakes q JOIN purchase_order_cancellations c ON c.order_id=q.purchase_order_id WHERE q.id=NEW.intake_id)
 OR (NEW.reversal_of IS NULL AND NEW.quantity_milli>(SELECT held FROM qc_totals WHERE id=NEW.intake_id))
 OR (NEW.reversal_of IS NULL AND NEW.kind='accept' AND NOT EXISTS(SELECT 1 FROM qc_intakes q
    JOIN material_batches b ON b.id=NEW.batch_id AND b.material_id=q.material_id
    JOIN material_movements m ON m.batch_id=b.id AND m.kind='receipt'
    WHERE q.id=NEW.intake_id AND m.quantity_milli=NEW.quantity_milli
      AND NOT EXISTS(SELECT 1 FROM material_movements WHERE reversal_of=m.id)
      AND NOT EXISTS(SELECT 1 FROM purchase_order_receipts WHERE batch_id=NEW.batch_id)))
 OR (NEW.reversal_of IS NOT NULL AND NOT EXISTS(SELECT 1 FROM qc_decisions d WHERE d.id=NEW.reversal_of
    AND d.intake_id=NEW.intake_id AND d.kind=NEW.kind AND d.reversal_of IS NULL AND d.quantity_milli=-NEW.quantity_milli))
 OR (NEW.reversal_of IS NOT NULL AND NEW.kind='accept' AND NOT EXISTS(SELECT 1 FROM qc_decisions d
    JOIN material_movements m ON m.batch_id=d.batch_id AND m.kind='receipt'
    JOIN material_movements r ON r.reversal_of=m.id
    WHERE d.id=NEW.reversal_of))
BEGIN SELECT RAISE(ABORT,'Invalid QC decision or insufficient held quantity'); END;
CREATE TRIGGER IF NOT EXISTS qc_reject_reverse_capacity BEFORE INSERT ON qc_decisions
WHEN NEW.kind='reject' AND NEW.reversal_of IS NOT NULL
 AND EXISTS(SELECT 1 FROM qc_intakes q JOIN purchase_orders p ON p.id=q.purchase_order_id,json_each(p.lines) l
    WHERE q.id=NEW.intake_id AND json_extract(l.value,'$.material_id')=q.material_id
    AND COALESCE((SELECT quantity_milli FROM po_material_committed WHERE purchase_order_id=p.id AND material_id=q.material_id),0)-NEW.quantity_milli
        >CAST(ROUND(json_extract(l.value,'$.quantity')*1000) AS INTEGER))
BEGIN SELECT RAISE(ABORT,'Replacement already fills rejected quantity'); END;
CREATE TRIGGER IF NOT EXISTS qc_cancel_valid BEFORE INSERT ON qc_intake_cancellations
WHEN EXISTS(SELECT 1 FROM qc_totals WHERE id=NEW.intake_id AND accepted+rejected!=0)
BEGIN SELECT RAISE(ABORT,'Reverse active QC decisions before cancelling intake'); END;
CREATE TRIGGER IF NOT EXISTS po_cancel_held BEFORE INSERT ON purchase_order_cancellations
WHEN EXISTS(SELECT 1 FROM qc_totals WHERE purchase_order_id=NEW.order_id AND held>0)
BEGIN SELECT RAISE(ABORT,'Resolve held material before cancelling PO'); END;
CREATE TRIGGER IF NOT EXISTS qc_intake_no_update BEFORE UPDATE ON qc_intakes BEGIN SELECT RAISE(ABORT,'Immutable intake'); END;
CREATE TRIGGER IF NOT EXISTS qc_intake_no_delete BEFORE DELETE ON qc_intakes BEGIN SELECT RAISE(ABORT,'Immutable intake'); END;
CREATE TRIGGER IF NOT EXISTS qc_decision_no_update BEFORE UPDATE ON qc_decisions BEGIN SELECT RAISE(ABORT,'Immutable decision'); END;
CREATE TRIGGER IF NOT EXISTS qc_decision_no_delete BEFORE DELETE ON qc_decisions BEGIN SELECT RAISE(ABORT,'Immutable decision'); END;
CREATE TRIGGER IF NOT EXISTS qc_cancel_no_update BEFORE UPDATE ON qc_intake_cancellations BEGIN SELECT RAISE(ABORT,'Immutable cancellation'); END;
CREATE TRIGGER IF NOT EXISTS qc_cancel_no_delete BEFORE DELETE ON qc_intake_cancellations BEGIN SELECT RAISE(ABORT,'Immutable cancellation'); END;
PRAGMA user_version=11;
COMMIT;
