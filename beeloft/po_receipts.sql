BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS purchase_order_receipts (
    batch_id TEXT PRIMARY KEY REFERENCES material_batches(id),
    purchase_order_id TEXT NOT NULL REFERENCES purchase_orders(id)
) STRICT;
CREATE INDEX IF NOT EXISTS po_receipts_order ON purchase_order_receipts(purchase_order_id);
CREATE TRIGGER IF NOT EXISTS po_receipt_valid BEFORE INSERT ON purchase_order_receipts
WHEN EXISTS(SELECT 1 FROM purchase_order_cancellations WHERE order_id=NEW.purchase_order_id)
 OR NOT EXISTS(SELECT 1 FROM purchase_orders p, json_each(p.lines) l
    JOIN material_batches b ON b.id=NEW.batch_id
    JOIN material_movements m ON m.batch_id=b.id AND m.kind='receipt'
    WHERE p.id=NEW.purchase_order_id AND json_extract(l.value,'$.material_id')=b.material_id
    AND NOT EXISTS(SELECT 1 FROM material_movements WHERE reversal_of=m.id)
    AND m.quantity_milli+COALESCE((SELECT SUM(r.quantity_milli) FROM purchase_order_receipts x
        JOIN material_batches rb ON rb.id=x.batch_id
        JOIN material_movements r ON r.batch_id=rb.id AND r.kind='receipt'
        WHERE x.purchase_order_id=p.id AND rb.material_id=b.material_id
        AND NOT EXISTS(SELECT 1 FROM material_movements WHERE reversal_of=r.id)),0)
        <=CAST(ROUND(json_extract(l.value,'$.quantity')*1000) AS INTEGER))
BEGIN SELECT RAISE(ABORT,'Receipt exceeds active PO or does not match its material'); END;
CREATE TRIGGER IF NOT EXISTS po_cancel_received BEFORE INSERT ON purchase_order_cancellations
WHEN EXISTS(SELECT 1 FROM purchase_order_receipts x
    JOIN material_movements m ON m.batch_id=x.batch_id AND m.kind='receipt'
    WHERE x.purchase_order_id=NEW.order_id
    AND NOT EXISTS(SELECT 1 FROM material_movements WHERE reversal_of=m.id))
BEGIN SELECT RAISE(ABORT,'Reverse receipts before cancelling PO'); END;
CREATE TRIGGER IF NOT EXISTS po_receipts_no_update BEFORE UPDATE ON purchase_order_receipts
BEGIN SELECT RAISE(ABORT,'PO receipt links cannot be updated'); END;
CREATE TRIGGER IF NOT EXISTS po_receipts_no_delete BEFORE DELETE ON purchase_order_receipts
BEGIN SELECT RAISE(ABORT,'PO receipt links cannot be deleted'); END;
PRAGMA user_version=10;
COMMIT;
