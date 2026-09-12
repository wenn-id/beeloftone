BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS finished_goods_stock_counts (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    reference TEXT NOT NULL UNIQUE COLLATE NOCASE CHECK(reference=trim(reference) AND length(reference) BETWEEN 1 AND 160),
    receipt_id TEXT NOT NULL REFERENCES finished_goods_receipts(id),
    scanned_sku TEXT NOT NULL CHECK(scanned_sku=trim(scanned_sku) AND length(scanned_sku) BETWEEN 1 AND 160),
    location TEXT NOT NULL CHECK(location=trim(location) AND length(location) BETWEEN 1 AND 160),
    stock_status TEXT NOT NULL CHECK(stock_status IN ('sellable','hold','damaged')),
    expected_quantity INTEGER NOT NULL CHECK(expected_quantity BETWEEN 0 AND 1000000000),
    counted_quantity INTEGER NOT NULL CHECK(counted_quantity BETWEEN 0 AND 1000000000),
    counted_date TEXT NOT NULL CHECK(date(counted_date)=counted_date),
    reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;
CREATE INDEX IF NOT EXISTS finished_goods_stock_counts_receipt ON finished_goods_stock_counts(receipt_id,sequence);
CREATE TABLE IF NOT EXISTS finished_goods_stock_count_reversals (
    count_id TEXT PRIMARY KEY REFERENCES finished_goods_stock_counts(id),
    reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;
CREATE UNIQUE INDEX IF NOT EXISTS finished_goods_adjustments_stock_count
    ON finished_goods_adjustments(stock_count_id) WHERE stock_count_id IS NOT NULL;

CREATE TRIGGER IF NOT EXISTS finished_goods_stock_count_source_valid BEFORE INSERT ON finished_goods_stock_counts
WHEN NOT EXISTS(SELECT 1 FROM finished_goods_receipts x
    JOIN final_qc_records q ON q.id=x.final_qc_record_id
    JOIN finishing_records f ON f.id=q.finishing_record_id JOIN sewing_jobs j ON j.id=f.job_id
    JOIN bundles b ON b.id=j.bundle_id JOIN movements source ON source.id=b.output_movement_id
    JOIN order_lines l ON l.id=source.line_id JOIN products p ON p.id=l.product_id
    WHERE x.id=NEW.receipt_id AND NEW.counted_date>=x.received_date
      AND NEW.scanned_sku=p.sku COLLATE NOCASE
      AND NOT EXISTS(SELECT 1 FROM finished_goods_receipt_reversals r WHERE r.receipt_id=x.id))
OR NEW.expected_quantity<>COALESCE((SELECT SUM(l.quantity) FROM finished_goods_stock_ledger l
    WHERE l.receipt_id=NEW.receipt_id AND l.location=NEW.location COLLATE NOCASE
      AND l.stock_status=NEW.stock_status),0)
OR NEW.stock_status='sellable' AND NEW.counted_quantity<COALESCE((SELECT r.quantity
    FROM finished_goods_reserved_stock r WHERE r.receipt_id=NEW.receipt_id
      AND r.location=NEW.location COLLATE NOCASE),0)
BEGIN SELECT RAISE(ABORT,'Invalid finished goods stock count source, scan, date, or quantity'); END;

CREATE TRIGGER IF NOT EXISTS finished_goods_stock_count_reversal_valid
BEFORE INSERT ON finished_goods_stock_count_reversals
WHEN NOT EXISTS(SELECT 1 FROM finished_goods_stock_counts c JOIN finished_goods_receipts x ON x.id=c.receipt_id
    WHERE c.id=NEW.count_id AND NOT EXISTS(
      SELECT 1 FROM finished_goods_stock_count_reversals r WHERE r.count_id=c.id)
      AND NOT EXISTS(SELECT 1 FROM finished_goods_receipt_reversals r WHERE r.receipt_id=x.id))
BEGIN SELECT RAISE(ABORT,'Invalid finished goods stock count reversal'); END;

DROP TRIGGER IF EXISTS finished_goods_adjustment_reversal_valid;
CREATE TRIGGER finished_goods_adjustment_reversal_valid BEFORE INSERT ON finished_goods_adjustment_reversals
WHEN NOT EXISTS(SELECT 1 FROM finished_goods_adjustments a JOIN finished_goods_receipts x ON x.id=a.receipt_id
    WHERE a.id=NEW.adjustment_id AND NOT EXISTS(
      SELECT 1 FROM finished_goods_adjustment_reversals r WHERE r.adjustment_id=a.id)
      AND NOT EXISTS(SELECT 1 FROM finished_goods_receipt_reversals r WHERE r.receipt_id=x.id))
OR EXISTS(SELECT 1 FROM finished_goods_adjustments a WHERE a.id=NEW.adjustment_id
    AND a.stock_count_id IS NOT NULL AND NOT EXISTS(
      SELECT 1 FROM finished_goods_stock_count_reversals r WHERE r.count_id=a.stock_count_id))
OR COALESCE((SELECT quantity_delta FROM finished_goods_adjustments WHERE id=NEW.adjustment_id),0)>0
   AND (SELECT COALESCE(SUM(l.quantity),0)-CASE WHEN a.stock_status='sellable' THEN COALESCE(r.quantity,0) ELSE 0 END
      FROM finished_goods_adjustments a JOIN finished_goods_receipts x ON x.id=a.receipt_id
      JOIN final_qc_records q ON q.id=x.final_qc_record_id JOIN finishing_records f ON f.id=q.finishing_record_id
      JOIN sewing_jobs j ON j.id=f.job_id JOIN bundles b ON b.id=j.bundle_id
      JOIN movements source ON source.id=b.output_movement_id JOIN order_lines ol ON ol.id=source.line_id
      LEFT JOIN finished_goods_stock_ledger l ON l.receipt_id=x.id AND l.product_id=ol.product_id
        AND l.location=a.location COLLATE NOCASE AND l.stock_status=a.stock_status
      LEFT JOIN finished_goods_reserved_stock r ON r.receipt_id=x.id AND r.product_id=ol.product_id
        AND r.location=a.location COLLATE NOCASE WHERE a.id=NEW.adjustment_id GROUP BY a.id)<
   COALESCE((SELECT quantity_delta FROM finished_goods_adjustments WHERE id=NEW.adjustment_id),0)
BEGIN SELECT RAISE(ABORT,'Invalid finished goods adjustment reversal'); END;

CREATE TRIGGER IF NOT EXISTS finished_goods_stock_count_reverse_adjustment
AFTER INSERT ON finished_goods_stock_count_reversals
BEGIN
  INSERT INTO finished_goods_adjustment_reversals(adjustment_id,reason,actor_id,created_at)
  SELECT id,NEW.reason,NEW.actor_id,NEW.created_at FROM finished_goods_adjustments
  WHERE stock_count_id=NEW.count_id;
END;

DROP TRIGGER IF EXISTS finished_goods_reversal_valid;
CREATE TRIGGER finished_goods_reversal_valid BEFORE INSERT ON finished_goods_receipt_reversals
WHEN NOT EXISTS(SELECT 1 FROM finished_goods_receipts WHERE id=NEW.receipt_id)
OR EXISTS(SELECT 1 FROM finished_goods_receipt_reversals WHERE receipt_id=NEW.receipt_id)
OR EXISTS(SELECT 1 FROM warehouse_movements w WHERE w.receipt_id=NEW.receipt_id
    AND NOT EXISTS(SELECT 1 FROM warehouse_movement_reversals r WHERE r.movement_id=w.id))
OR EXISTS(SELECT 1 FROM marketplace_reservations m WHERE m.receipt_id=NEW.receipt_id
    AND NOT EXISTS(SELECT 1 FROM marketplace_reservation_releases r WHERE r.reservation_id=m.id))
OR EXISTS(SELECT 1 FROM finished_goods_adjustments a WHERE a.receipt_id=NEW.receipt_id
    AND NOT EXISTS(SELECT 1 FROM finished_goods_adjustment_reversals r WHERE r.adjustment_id=a.id))
OR EXISTS(SELECT 1 FROM finished_goods_stock_counts c WHERE c.receipt_id=NEW.receipt_id
    AND NOT EXISTS(SELECT 1 FROM finished_goods_stock_count_reversals r WHERE r.count_id=c.id))
BEGIN SELECT RAISE(ABORT,'Invalid finished goods receipt reversal'); END;

CREATE TRIGGER IF NOT EXISTS finished_goods_stock_counts_no_update BEFORE UPDATE ON finished_goods_stock_counts
BEGIN SELECT RAISE(ABORT,'Immutable finished goods stock count'); END;
CREATE TRIGGER IF NOT EXISTS finished_goods_stock_counts_no_delete BEFORE DELETE ON finished_goods_stock_counts
BEGIN SELECT RAISE(ABORT,'Immutable finished goods stock count'); END;
CREATE TRIGGER IF NOT EXISTS finished_goods_stock_count_reversals_no_update BEFORE UPDATE ON finished_goods_stock_count_reversals
BEGIN SELECT RAISE(ABORT,'Immutable finished goods stock count reversal'); END;
CREATE TRIGGER IF NOT EXISTS finished_goods_stock_count_reversals_no_delete BEFORE DELETE ON finished_goods_stock_count_reversals
BEGIN SELECT RAISE(ABORT,'Immutable finished goods stock count reversal'); END;
PRAGMA user_version=25;
COMMIT;
