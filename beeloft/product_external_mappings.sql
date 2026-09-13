CREATE TABLE IF NOT EXISTS product_external_mapping_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    product_id TEXT NOT NULL REFERENCES products(id),
    system TEXT NOT NULL CHECK(system='jubelio'),
    revision INTEGER NOT NULL CHECK(revision>0),
    status TEXT NOT NULL CHECK(status IN ('mapped','unmapped')),
    external_id TEXT NOT NULL CHECK(external_id=trim(external_id) AND length(external_id)<=160),
    external_sku TEXT NOT NULL COLLATE NOCASE CHECK(external_sku=trim(external_sku) AND length(external_sku)<=160),
    reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    UNIQUE(product_id,system,revision),
    CHECK((status='mapped' AND length(external_id)>0 AND length(external_sku)>0)
       OR (status='unmapped' AND external_id='' AND external_sku=''))
) STRICT;

CREATE INDEX IF NOT EXISTS idx_product_external_mapping_product
    ON product_external_mapping_events(product_id,system,sequence DESC);
CREATE INDEX IF NOT EXISTS idx_product_external_mapping_external
    ON product_external_mapping_events(system,external_sku,external_id,sequence DESC);

CREATE TRIGGER IF NOT EXISTS product_external_mapping_events_no_update
BEFORE UPDATE ON product_external_mapping_events BEGIN
    SELECT RAISE(ABORT,'Product external mapping history is immutable');
END;
CREATE TRIGGER IF NOT EXISTS product_external_mapping_events_no_delete
BEFORE DELETE ON product_external_mapping_events BEGIN
    SELECT RAISE(ABORT,'Product external mapping history is immutable');
END;

PRAGMA user_version=34;
