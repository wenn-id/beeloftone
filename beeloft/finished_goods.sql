BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS finished_goods_receipts (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    reference TEXT NOT NULL UNIQUE COLLATE NOCASE CHECK(reference=trim(reference) AND length(reference) BETWEEN 1 AND 160),
    final_qc_record_id TEXT NOT NULL REFERENCES final_qc_records(id),
    scanned_sku TEXT NOT NULL CHECK(scanned_sku=trim(scanned_sku) AND length(scanned_sku) BETWEEN 1 AND 160),
    location TEXT NOT NULL CHECK(location=trim(location) AND length(location) BETWEEN 1 AND 160),
    sellable_quantity INTEGER NOT NULL CHECK(sellable_quantity>=0),
    hold_quantity INTEGER NOT NULL CHECK(hold_quantity>=0),
    received_date TEXT NOT NULL CHECK(date(received_date)=received_date),
    reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    CHECK(sellable_quantity+hold_quantity>0)
) STRICT;
CREATE INDEX IF NOT EXISTS finished_goods_receipts_qc ON finished_goods_receipts(final_qc_record_id,sequence);
CREATE TABLE IF NOT EXISTS finished_goods_receipt_reversals (
    receipt_id TEXT PRIMARY KEY REFERENCES finished_goods_receipts(id),
    reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;
CREATE TRIGGER IF NOT EXISTS finished_goods_source_valid BEFORE INSERT ON finished_goods_receipts
WHEN NOT EXISTS(SELECT 1 FROM final_qc_records q JOIN finishing_records f ON f.id=q.finishing_record_id
    JOIN movements m ON m.id=f.movement_id JOIN order_lines l ON l.id=m.line_id
    JOIN products p ON p.id=l.product_id WHERE q.id=NEW.final_qc_record_id
      AND NEW.received_date>=q.inspection_date AND NEW.scanned_sku=p.sku COLLATE NOCASE
      AND NOT EXISTS(SELECT 1 FROM final_qc_record_reversals r WHERE r.record_id=q.id))
OR NEW.sellable_quantity+NEW.hold_quantity + COALESCE((SELECT SUM(
    x.sellable_quantity+x.hold_quantity) FROM finished_goods_receipts x
    WHERE x.final_qc_record_id=NEW.final_qc_record_id AND NOT EXISTS(
      SELECT 1 FROM finished_goods_receipt_reversals r WHERE r.receipt_id=x.id)),0)
   > COALESCE((SELECT accepted_quantity FROM final_qc_records WHERE id=NEW.final_qc_record_id),0)
BEGIN SELECT RAISE(ABORT,'Invalid finished goods source, SKU, date, or allocation'); END;
CREATE TRIGGER IF NOT EXISTS finished_goods_reversal_valid BEFORE INSERT ON finished_goods_receipt_reversals
WHEN NOT EXISTS(SELECT 1 FROM finished_goods_receipts WHERE id=NEW.receipt_id)
OR EXISTS(SELECT 1 FROM finished_goods_receipt_reversals WHERE receipt_id=NEW.receipt_id)
BEGIN SELECT RAISE(ABORT,'Invalid finished goods receipt reversal'); END;
CREATE TRIGGER IF NOT EXISTS finished_goods_blocks_final_qc_reversal BEFORE INSERT ON final_qc_record_reversals
WHEN EXISTS(SELECT 1 FROM finished_goods_receipts x WHERE x.final_qc_record_id=NEW.record_id
    AND NOT EXISTS(SELECT 1 FROM finished_goods_receipt_reversals r WHERE r.receipt_id=x.id))
BEGIN SELECT RAISE(ABORT,'Active finished goods receipt blocks final QC reversal'); END;
CREATE TRIGGER IF NOT EXISTS finished_goods_receipts_no_update BEFORE UPDATE ON finished_goods_receipts
BEGIN SELECT RAISE(ABORT,'Immutable finished goods receipt'); END;
CREATE TRIGGER IF NOT EXISTS finished_goods_receipts_no_delete BEFORE DELETE ON finished_goods_receipts
BEGIN SELECT RAISE(ABORT,'Immutable finished goods receipt'); END;
CREATE TRIGGER IF NOT EXISTS finished_goods_reversals_no_update BEFORE UPDATE ON finished_goods_receipt_reversals
BEGIN SELECT RAISE(ABORT,'Immutable finished goods reversal'); END;
CREATE TRIGGER IF NOT EXISTS finished_goods_reversals_no_delete BEFORE DELETE ON finished_goods_receipt_reversals
BEGIN SELECT RAISE(ABORT,'Immutable finished goods reversal'); END;
PRAGMA user_version=18;
COMMIT;
