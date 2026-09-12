BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS marketplace_returns (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    reference TEXT NOT NULL UNIQUE COLLATE NOCASE CHECK(reference=trim(reference) AND length(reference) BETWEEN 1 AND 160),
    shipment_id TEXT NOT NULL REFERENCES marketplace_shipments(id),
    quantity INTEGER NOT NULL CHECK(quantity>0),
    return_reason TEXT NOT NULL CHECK(return_reason IN ('too_small','too_big','wrong_item','defect','color_mismatch','other')),
    return_location TEXT NOT NULL CHECK(return_location=trim(return_location) AND length(return_location) BETWEEN 1 AND 160),
    stock_status TEXT NOT NULL CHECK(stock_status IN ('sellable','hold','damaged')),
    returned_date TEXT NOT NULL CHECK(date(returned_date)=returned_date),
    reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;
CREATE INDEX IF NOT EXISTS marketplace_returns_shipment ON marketplace_returns(shipment_id,sequence);
CREATE TABLE IF NOT EXISTS marketplace_return_reversals (
    return_id TEXT PRIMARY KEY REFERENCES marketplace_returns(id),
    reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;
CREATE TABLE IF NOT EXISTS finished_goods_adjustments (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    reference TEXT NOT NULL UNIQUE COLLATE NOCASE CHECK(reference=trim(reference) AND length(reference) BETWEEN 1 AND 160),
    receipt_id TEXT NOT NULL REFERENCES finished_goods_receipts(id),
    location TEXT NOT NULL CHECK(location=trim(location) AND length(location) BETWEEN 1 AND 160),
    stock_status TEXT NOT NULL CHECK(stock_status IN ('sellable','hold','damaged')),
    quantity_delta INTEGER NOT NULL CHECK(quantity_delta BETWEEN -1000000000 AND 1000000000 AND quantity_delta<>0),
    adjusted_date TEXT NOT NULL CHECK(date(adjusted_date)=adjusted_date),
    reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;
CREATE INDEX IF NOT EXISTS finished_goods_adjustments_receipt ON finished_goods_adjustments(receipt_id,sequence);
CREATE TABLE IF NOT EXISTS finished_goods_adjustment_reversals (
    adjustment_id TEXT PRIMARY KEY REFERENCES finished_goods_adjustments(id),
    reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;

DROP VIEW IF EXISTS finished_goods_stock_ledger;
CREATE VIEW finished_goods_stock_ledger AS
WITH receipt_products AS (
    SELECT x.id,x.location,x.sellable_quantity,x.hold_quantity,l.product_id
    FROM finished_goods_receipts x JOIN final_qc_records q ON q.id=x.final_qc_record_id
    JOIN finishing_records f ON f.id=q.finishing_record_id JOIN sewing_jobs j ON j.id=f.job_id
    JOIN bundles b ON b.id=j.bundle_id JOIN movements source ON source.id=b.output_movement_id
    JOIN order_lines l ON l.id=source.line_id
    WHERE NOT EXISTS(SELECT 1 FROM finished_goods_receipt_reversals r WHERE r.receipt_id=x.id)
)
SELECT id AS receipt_id,product_id,location,'sellable' AS stock_status,sellable_quantity AS quantity FROM receipt_products
UNION ALL SELECT id,product_id,location,'hold',hold_quantity FROM receipt_products
UNION ALL SELECT rp.id,rp.product_id,w.from_location,w.from_status,-w.quantity
    FROM warehouse_movements w JOIN receipt_products rp ON rp.id=w.receipt_id
    WHERE NOT EXISTS(SELECT 1 FROM warehouse_movement_reversals r WHERE r.movement_id=w.id)
UNION ALL SELECT rp.id,rp.product_id,w.to_location,w.to_status,w.quantity
    FROM warehouse_movements w JOIN receipt_products rp ON rp.id=w.receipt_id
    WHERE NOT EXISTS(SELECT 1 FROM warehouse_movement_reversals r WHERE r.movement_id=w.id)
UNION ALL SELECT rp.id,rp.product_id,m.location,'sellable',-p.quantity FROM marketplace_picks p
    JOIN marketplace_reservations m ON m.id=p.reservation_id JOIN receipt_products rp ON rp.id=m.receipt_id
    WHERE NOT EXISTS(SELECT 1 FROM marketplace_pick_reversals r WHERE r.pick_id=p.id)
      AND NOT EXISTS(SELECT 1 FROM marketplace_reservation_releases r WHERE r.reservation_id=m.id)
UNION ALL SELECT rp.id,rp.product_id,p.staging_location,'picked',p.quantity FROM marketplace_picks p
    JOIN marketplace_reservations m ON m.id=p.reservation_id JOIN receipt_products rp ON rp.id=m.receipt_id
    WHERE NOT EXISTS(SELECT 1 FROM marketplace_pick_reversals r WHERE r.pick_id=p.id)
      AND NOT EXISTS(SELECT 1 FROM marketplace_reservation_releases r WHERE r.reservation_id=m.id)
UNION ALL SELECT rp.id,rp.product_id,p.staging_location,'picked',-k.quantity FROM marketplace_packs k
    JOIN marketplace_picks p ON p.id=k.pick_id JOIN marketplace_reservations m ON m.id=p.reservation_id
    JOIN receipt_products rp ON rp.id=m.receipt_id
    WHERE NOT EXISTS(SELECT 1 FROM marketplace_pack_reversals r WHERE r.pack_id=k.id)
      AND NOT EXISTS(SELECT 1 FROM marketplace_pick_reversals r WHERE r.pick_id=p.id)
      AND NOT EXISTS(SELECT 1 FROM marketplace_reservation_releases r WHERE r.reservation_id=m.id)
UNION ALL SELECT rp.id,rp.product_id,p.staging_location,'packed',k.quantity FROM marketplace_packs k
    JOIN marketplace_picks p ON p.id=k.pick_id JOIN marketplace_reservations m ON m.id=p.reservation_id
    JOIN receipt_products rp ON rp.id=m.receipt_id
    WHERE NOT EXISTS(SELECT 1 FROM marketplace_pack_reversals r WHERE r.pack_id=k.id)
      AND NOT EXISTS(SELECT 1 FROM marketplace_pick_reversals r WHERE r.pick_id=p.id)
      AND NOT EXISTS(SELECT 1 FROM marketplace_reservation_releases r WHERE r.reservation_id=m.id)
UNION ALL SELECT rp.id,rp.product_id,p.staging_location,'packed',-s.quantity FROM marketplace_shipments s
    JOIN marketplace_packs k ON k.id=s.pack_id JOIN marketplace_picks p ON p.id=k.pick_id
    JOIN marketplace_reservations m ON m.id=p.reservation_id JOIN receipt_products rp ON rp.id=m.receipt_id
    WHERE NOT EXISTS(SELECT 1 FROM marketplace_shipment_reversals r WHERE r.shipment_id=s.id)
      AND NOT EXISTS(SELECT 1 FROM marketplace_pack_reversals r WHERE r.pack_id=k.id)
      AND NOT EXISTS(SELECT 1 FROM marketplace_pick_reversals r WHERE r.pick_id=p.id)
      AND NOT EXISTS(SELECT 1 FROM marketplace_reservation_releases r WHERE r.reservation_id=m.id)
UNION ALL SELECT rp.id,rp.product_id,t.return_location,t.stock_status,t.quantity FROM marketplace_returns t
    JOIN marketplace_shipments s ON s.id=t.shipment_id JOIN marketplace_packs k ON k.id=s.pack_id
    JOIN marketplace_picks p ON p.id=k.pick_id JOIN marketplace_reservations m ON m.id=p.reservation_id
    JOIN receipt_products rp ON rp.id=m.receipt_id
    WHERE NOT EXISTS(SELECT 1 FROM marketplace_return_reversals r WHERE r.return_id=t.id)
      AND NOT EXISTS(SELECT 1 FROM marketplace_shipment_reversals r WHERE r.shipment_id=s.id)
UNION ALL SELECT rp.id,rp.product_id,a.location,a.stock_status,a.quantity_delta FROM finished_goods_adjustments a
    JOIN receipt_products rp ON rp.id=a.receipt_id
    WHERE NOT EXISTS(SELECT 1 FROM finished_goods_adjustment_reversals r WHERE r.adjustment_id=a.id);

DROP VIEW IF EXISTS finished_goods_reserved_stock;
CREATE VIEW finished_goods_reserved_stock AS
SELECT x.id AS receipt_id,l.product_id,m.location,
    SUM(m.quantity-COALESCE((SELECT SUM(p.quantity) FROM marketplace_picks p
      WHERE p.reservation_id=m.id AND NOT EXISTS(
        SELECT 1 FROM marketplace_pick_reversals r WHERE r.pick_id=p.id)),0)) AS quantity
FROM marketplace_reservations m JOIN finished_goods_receipts x ON x.id=m.receipt_id
JOIN final_qc_records q ON q.id=x.final_qc_record_id JOIN finishing_records f ON f.id=q.finishing_record_id
JOIN sewing_jobs j ON j.id=f.job_id JOIN bundles b ON b.id=j.bundle_id
JOIN movements source ON source.id=b.output_movement_id JOIN order_lines l ON l.id=source.line_id
WHERE NOT EXISTS(SELECT 1 FROM marketplace_reservation_releases r WHERE r.reservation_id=m.id)
  AND NOT EXISTS(SELECT 1 FROM finished_goods_receipt_reversals r WHERE r.receipt_id=x.id)
GROUP BY x.id,l.product_id,m.location COLLATE NOCASE;

DROP TRIGGER IF EXISTS marketplace_reservation_source_valid;
CREATE TRIGGER marketplace_reservation_source_valid BEFORE INSERT ON marketplace_reservations
WHEN NOT EXISTS(SELECT 1 FROM finished_goods_receipts x WHERE x.id=NEW.receipt_id
    AND NEW.reserved_date>=x.received_date AND NOT EXISTS(
      SELECT 1 FROM finished_goods_receipt_reversals r WHERE r.receipt_id=x.id))
OR NEW.quantity >
   COALESCE((SELECT SUM(l.quantity) FROM finished_goods_stock_ledger l
      WHERE l.receipt_id=NEW.receipt_id AND l.location=NEW.location COLLATE NOCASE
        AND l.stock_status='sellable'),0)
   - COALESCE((SELECT r.quantity FROM finished_goods_reserved_stock r
      WHERE r.receipt_id=NEW.receipt_id AND r.location=NEW.location COLLATE NOCASE),0)
BEGIN SELECT RAISE(ABORT,'Invalid marketplace reservation source, date, or quantity'); END;

DROP TRIGGER IF EXISTS warehouse_movement_source_valid;
CREATE TRIGGER warehouse_movement_source_valid BEFORE INSERT ON warehouse_movements
WHEN NOT EXISTS(SELECT 1 FROM finished_goods_receipts x WHERE x.id=NEW.receipt_id
    AND NEW.moved_date>=x.received_date AND NOT EXISTS(
      SELECT 1 FROM finished_goods_receipt_reversals r WHERE r.receipt_id=x.id))
OR NEW.quantity >
   COALESCE((SELECT SUM(l.quantity) FROM finished_goods_stock_ledger l
      WHERE l.receipt_id=NEW.receipt_id AND l.location=NEW.from_location COLLATE NOCASE
        AND l.stock_status=NEW.from_status),0)
   - CASE WHEN NEW.from_status='sellable' THEN COALESCE((SELECT r.quantity
      FROM finished_goods_reserved_stock r WHERE r.receipt_id=NEW.receipt_id
        AND r.location=NEW.from_location COLLATE NOCASE),0) ELSE 0 END
BEGIN SELECT RAISE(ABORT,'Invalid warehouse movement source, date, or quantity'); END;

DROP TRIGGER IF EXISTS warehouse_movement_reversal_valid;
CREATE TRIGGER warehouse_movement_reversal_valid BEFORE INSERT ON warehouse_movement_reversals
WHEN NOT EXISTS(SELECT 1 FROM warehouse_movements w JOIN finished_goods_receipts x ON x.id=w.receipt_id
    WHERE w.id=NEW.movement_id AND NOT EXISTS(
      SELECT 1 FROM warehouse_movement_reversals r WHERE r.movement_id=w.id)
    AND NOT EXISTS(SELECT 1 FROM finished_goods_receipt_reversals r WHERE r.receipt_id=x.id))
OR COALESCE((SELECT SUM(l.quantity) FROM warehouse_movements w JOIN finished_goods_stock_ledger l
      ON l.receipt_id=w.receipt_id AND l.location=w.to_location COLLATE NOCASE
        AND l.stock_status=w.to_status WHERE w.id=NEW.movement_id),0)
   - COALESCE((SELECT r.quantity FROM warehouse_movements w JOIN finished_goods_reserved_stock r
      ON r.receipt_id=w.receipt_id AND r.location=w.to_location COLLATE NOCASE
      WHERE w.id=NEW.movement_id AND w.to_status='sellable'),0)
   < COALESCE((SELECT quantity FROM warehouse_movements WHERE id=NEW.movement_id),1)
BEGIN SELECT RAISE(ABORT,'Invalid warehouse movement reversal'); END;

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
BEGIN SELECT RAISE(ABORT,'Invalid finished goods receipt reversal'); END;

CREATE TRIGGER IF NOT EXISTS marketplace_return_source_valid BEFORE INSERT ON marketplace_returns
WHEN NOT EXISTS(SELECT 1 FROM marketplace_shipments s JOIN marketplace_packs k ON k.id=s.pack_id
    WHERE s.id=NEW.shipment_id AND NEW.returned_date>=s.shipped_date
      AND NOT EXISTS(SELECT 1 FROM marketplace_shipment_reversals r WHERE r.shipment_id=s.id)
      AND NOT EXISTS(SELECT 1 FROM marketplace_pack_reversals r WHERE r.pack_id=k.id))
OR NEW.quantity + COALESCE((SELECT SUM(t.quantity) FROM marketplace_returns t
    WHERE t.shipment_id=NEW.shipment_id AND NOT EXISTS(
      SELECT 1 FROM marketplace_return_reversals r WHERE r.return_id=t.id)),0)
   > COALESCE((SELECT quantity FROM marketplace_shipments WHERE id=NEW.shipment_id),0)
BEGIN SELECT RAISE(ABORT,'Invalid marketplace return source, date, or quantity'); END;
CREATE TRIGGER IF NOT EXISTS marketplace_return_reversal_valid BEFORE INSERT ON marketplace_return_reversals
WHEN NOT EXISTS(SELECT 1 FROM marketplace_returns t JOIN marketplace_shipments s ON s.id=t.shipment_id
    WHERE t.id=NEW.return_id AND NOT EXISTS(SELECT 1 FROM marketplace_return_reversals r WHERE r.return_id=t.id)
      AND NOT EXISTS(SELECT 1 FROM marketplace_shipment_reversals r WHERE r.shipment_id=s.id))
OR (SELECT COALESCE(SUM(l.quantity),0)-CASE WHEN t.stock_status='sellable' THEN COALESCE(r.quantity,0) ELSE 0 END
      FROM marketplace_returns t JOIN marketplace_shipments s ON s.id=t.shipment_id
      JOIN marketplace_packs k ON k.id=s.pack_id JOIN marketplace_picks p ON p.id=k.pick_id
      JOIN marketplace_reservations m ON m.id=p.reservation_id JOIN finished_goods_receipts x ON x.id=m.receipt_id
      JOIN final_qc_records q ON q.id=x.final_qc_record_id JOIN finishing_records f ON f.id=q.finishing_record_id
      JOIN sewing_jobs j ON j.id=f.job_id JOIN bundles b ON b.id=j.bundle_id
      JOIN movements source ON source.id=b.output_movement_id JOIN order_lines ol ON ol.id=source.line_id
      LEFT JOIN finished_goods_stock_ledger l ON l.receipt_id=x.id AND l.product_id=ol.product_id
        AND l.location=t.return_location COLLATE NOCASE AND l.stock_status=t.stock_status
      LEFT JOIN finished_goods_reserved_stock r ON r.receipt_id=x.id AND r.product_id=ol.product_id
        AND r.location=t.return_location COLLATE NOCASE WHERE t.id=NEW.return_id GROUP BY t.id)<
   COALESCE((SELECT quantity FROM marketplace_returns WHERE id=NEW.return_id),0)
BEGIN SELECT RAISE(ABORT,'Invalid marketplace return reversal'); END;

CREATE TRIGGER IF NOT EXISTS finished_goods_adjustment_source_valid BEFORE INSERT ON finished_goods_adjustments
WHEN NOT EXISTS(SELECT 1 FROM finished_goods_receipts x WHERE x.id=NEW.receipt_id
    AND NEW.adjusted_date>=x.received_date AND NOT EXISTS(
      SELECT 1 FROM finished_goods_receipt_reversals r WHERE r.receipt_id=x.id))
OR NEW.quantity_delta<0 AND (SELECT COALESCE(SUM(l.quantity),0)-
      CASE WHEN NEW.stock_status='sellable' THEN COALESCE(r.quantity,0) ELSE 0 END
    FROM finished_goods_receipts x JOIN final_qc_records q ON q.id=x.final_qc_record_id
    JOIN finishing_records f ON f.id=q.finishing_record_id JOIN sewing_jobs j ON j.id=f.job_id
    JOIN bundles b ON b.id=j.bundle_id JOIN movements source ON source.id=b.output_movement_id
    JOIN order_lines ol ON ol.id=source.line_id LEFT JOIN finished_goods_stock_ledger l
      ON l.receipt_id=x.id AND l.product_id=ol.product_id AND l.location=NEW.location COLLATE NOCASE AND l.stock_status=NEW.stock_status
    LEFT JOIN finished_goods_reserved_stock r ON r.receipt_id=x.id AND r.product_id=ol.product_id
      AND r.location=NEW.location COLLATE NOCASE WHERE x.id=NEW.receipt_id GROUP BY x.id)<-NEW.quantity_delta
BEGIN SELECT RAISE(ABORT,'Invalid finished goods adjustment source, date, or quantity'); END;
CREATE TRIGGER IF NOT EXISTS finished_goods_adjustment_reversal_valid BEFORE INSERT ON finished_goods_adjustment_reversals
WHEN NOT EXISTS(SELECT 1 FROM finished_goods_adjustments a JOIN finished_goods_receipts x ON x.id=a.receipt_id
    WHERE a.id=NEW.adjustment_id AND NOT EXISTS(
      SELECT 1 FROM finished_goods_adjustment_reversals r WHERE r.adjustment_id=a.id)
      AND NOT EXISTS(SELECT 1 FROM finished_goods_receipt_reversals r WHERE r.receipt_id=x.id))
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

DROP TRIGGER IF EXISTS marketplace_shipment_reversal_valid;
CREATE TRIGGER marketplace_shipment_reversal_valid BEFORE INSERT ON marketplace_shipment_reversals
WHEN NOT EXISTS(SELECT 1 FROM marketplace_shipments s JOIN marketplace_packs k ON k.id=s.pack_id
    WHERE s.id=NEW.shipment_id AND NOT EXISTS(
      SELECT 1 FROM marketplace_shipment_reversals r WHERE r.shipment_id=s.id)
      AND NOT EXISTS(SELECT 1 FROM marketplace_pack_reversals r WHERE r.pack_id=k.id))
OR EXISTS(SELECT 1 FROM marketplace_returns t WHERE t.shipment_id=NEW.shipment_id
    AND NOT EXISTS(SELECT 1 FROM marketplace_return_reversals r WHERE r.return_id=t.id))
BEGIN SELECT RAISE(ABORT,'Invalid marketplace shipment reversal'); END;

CREATE TRIGGER IF NOT EXISTS marketplace_returns_no_update BEFORE UPDATE ON marketplace_returns
BEGIN SELECT RAISE(ABORT,'Immutable marketplace return'); END;
CREATE TRIGGER IF NOT EXISTS marketplace_returns_no_delete BEFORE DELETE ON marketplace_returns
BEGIN SELECT RAISE(ABORT,'Immutable marketplace return'); END;
CREATE TRIGGER IF NOT EXISTS marketplace_return_reversals_no_update BEFORE UPDATE ON marketplace_return_reversals
BEGIN SELECT RAISE(ABORT,'Immutable marketplace return reversal'); END;
CREATE TRIGGER IF NOT EXISTS marketplace_return_reversals_no_delete BEFORE DELETE ON marketplace_return_reversals
BEGIN SELECT RAISE(ABORT,'Immutable marketplace return reversal'); END;
CREATE TRIGGER IF NOT EXISTS finished_goods_adjustments_no_update BEFORE UPDATE ON finished_goods_adjustments
BEGIN SELECT RAISE(ABORT,'Immutable finished goods adjustment'); END;
CREATE TRIGGER IF NOT EXISTS finished_goods_adjustments_no_delete BEFORE DELETE ON finished_goods_adjustments
BEGIN SELECT RAISE(ABORT,'Immutable finished goods adjustment'); END;
CREATE TRIGGER IF NOT EXISTS finished_goods_adjustment_reversals_no_update BEFORE UPDATE ON finished_goods_adjustment_reversals
BEGIN SELECT RAISE(ABORT,'Immutable finished goods adjustment reversal'); END;
CREATE TRIGGER IF NOT EXISTS finished_goods_adjustment_reversals_no_delete BEFORE DELETE ON finished_goods_adjustment_reversals
BEGIN SELECT RAISE(ABORT,'Immutable finished goods adjustment reversal'); END;
PRAGMA user_version=24;
COMMIT;
