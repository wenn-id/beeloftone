BEGIN IMMEDIATE;
CREATE TRIGGER IF NOT EXISTS warehouse_movement_scan_valid BEFORE INSERT ON warehouse_movements
WHEN NEW.scanned_code IS NULL OR NOT EXISTS(
    SELECT 1 FROM finished_goods_receipts x
    JOIN final_qc_records q ON q.id=x.final_qc_record_id
    JOIN finishing_records f ON f.id=q.finishing_record_id
    JOIN sewing_jobs j ON j.id=f.job_id
    JOIN bundles b ON b.id=j.bundle_id
    JOIN movements source ON source.id=b.output_movement_id
    JOIN order_lines l ON l.id=source.line_id
    JOIN products p ON p.id=l.product_id
    WHERE x.id=NEW.receipt_id AND NEW.scanned_code COLLATE NOCASE IN (
        p.sku,'BEELOFT:FINISHED-GOODS:' || x.id))
BEGIN SELECT RAISE(ABORT,'Warehouse movement requires matching SKU or finished-goods QR'); END;
PRAGMA user_version=48;
COMMIT;
