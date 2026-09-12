BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS marketplace_sale_settlements (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    reference TEXT NOT NULL UNIQUE COLLATE NOCASE CHECK(reference=trim(reference) AND length(reference) BETWEEN 1 AND 160),
    shipment_id TEXT NOT NULL REFERENCES marketplace_shipments(id),
    return_quantity INTEGER NOT NULL CHECK(return_quantity>=0),
    gross_revenue_minor INTEGER NOT NULL CHECK(gross_revenue_minor>0 AND gross_revenue_minor<=100000000000000),
    seller_discount_minor INTEGER NOT NULL CHECK(seller_discount_minor>=0 AND seller_discount_minor<=100000000000000),
    customer_refund_minor INTEGER NOT NULL CHECK(customer_refund_minor>=0 AND customer_refund_minor<=100000000000000),
    marketplace_fee_minor INTEGER NOT NULL CHECK(marketplace_fee_minor>=0 AND marketplace_fee_minor<=100000000000000),
    shipping_cost_minor INTEGER NOT NULL CHECK(shipping_cost_minor>=0 AND shipping_cost_minor<=100000000000000),
    other_variable_cost_minor INTEGER NOT NULL CHECK(other_variable_cost_minor>=0 AND other_variable_cost_minor<=100000000000000),
    settled_date TEXT NOT NULL CHECK(date(settled_date)=settled_date),
    reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;
CREATE INDEX IF NOT EXISTS marketplace_sale_settlements_shipment
    ON marketplace_sale_settlements(shipment_id,sequence);

CREATE TABLE IF NOT EXISTS marketplace_sale_settlement_reversals (
    settlement_id TEXT PRIMARY KEY REFERENCES marketplace_sale_settlements(id),
    reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;

CREATE TRIGGER IF NOT EXISTS marketplace_sale_settlement_source_valid
BEFORE INSERT ON marketplace_sale_settlements
WHEN NOT EXISTS(
    SELECT 1 FROM marketplace_shipments s
    WHERE s.id=NEW.shipment_id AND NEW.settled_date>=s.shipped_date
      AND NOT EXISTS(SELECT 1 FROM marketplace_shipment_reversals r WHERE r.shipment_id=s.id)
)
OR NEW.return_quantity<>(
    SELECT COALESCE(SUM(t.quantity),0) FROM marketplace_returns t
    WHERE t.shipment_id=NEW.shipment_id
      AND NOT EXISTS(SELECT 1 FROM marketplace_return_reversals r WHERE r.return_id=t.id)
)
OR EXISTS(
    SELECT 1 FROM marketplace_sale_settlements e
    WHERE e.shipment_id=NEW.shipment_id
      AND NOT EXISTS(SELECT 1 FROM marketplace_sale_settlement_reversals r WHERE r.settlement_id=e.id)
)
BEGIN SELECT RAISE(ABORT,'Invalid marketplace sale settlement source, date, return coverage, or duplicate'); END;

CREATE TRIGGER IF NOT EXISTS marketplace_sale_settlement_reversal_valid
BEFORE INSERT ON marketplace_sale_settlement_reversals
WHEN NOT EXISTS(
    SELECT 1 FROM marketplace_sale_settlements e
    WHERE e.id=NEW.settlement_id
      AND NOT EXISTS(SELECT 1 FROM marketplace_sale_settlement_reversals r WHERE r.settlement_id=e.id)
)
BEGIN SELECT RAISE(ABORT,'Invalid marketplace sale settlement reversal'); END;

DROP TRIGGER IF EXISTS marketplace_shipment_reversal_valid;
CREATE TRIGGER marketplace_shipment_reversal_valid BEFORE INSERT ON marketplace_shipment_reversals
WHEN NOT EXISTS(SELECT 1 FROM marketplace_shipments s JOIN marketplace_packs k ON k.id=s.pack_id
    WHERE s.id=NEW.shipment_id AND NOT EXISTS(
      SELECT 1 FROM marketplace_shipment_reversals r WHERE r.shipment_id=s.id)
      AND NOT EXISTS(SELECT 1 FROM marketplace_pack_reversals r WHERE r.pack_id=k.id))
OR EXISTS(SELECT 1 FROM marketplace_sale_settlements e WHERE e.shipment_id=NEW.shipment_id
    AND NOT EXISTS(SELECT 1 FROM marketplace_sale_settlement_reversals r WHERE r.settlement_id=e.id))
BEGIN SELECT RAISE(ABORT,'Invalid marketplace shipment reversal'); END;

CREATE TRIGGER IF NOT EXISTS marketplace_sale_settlements_no_update
BEFORE UPDATE ON marketplace_sale_settlements
BEGIN SELECT RAISE(ABORT,'Immutable marketplace sale settlement'); END;
CREATE TRIGGER IF NOT EXISTS marketplace_sale_settlements_no_delete
BEFORE DELETE ON marketplace_sale_settlements
BEGIN SELECT RAISE(ABORT,'Immutable marketplace sale settlement'); END;
CREATE TRIGGER IF NOT EXISTS marketplace_sale_settlement_reversals_no_update
BEFORE UPDATE ON marketplace_sale_settlement_reversals
BEGIN SELECT RAISE(ABORT,'Immutable marketplace sale settlement reversal'); END;
CREATE TRIGGER IF NOT EXISTS marketplace_sale_settlement_reversals_no_delete
BEFORE DELETE ON marketplace_sale_settlement_reversals
BEGIN SELECT RAISE(ABORT,'Immutable marketplace sale settlement reversal'); END;

PRAGMA user_version=30;
COMMIT;
