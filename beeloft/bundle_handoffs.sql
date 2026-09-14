BEGIN IMMEDIATE;

CREATE TABLE IF NOT EXISTS bundle_handoffs (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    bundle_id TEXT NOT NULL REFERENCES bundles(id),
    from_location TEXT NOT NULL CHECK(from_location=trim(from_location) AND length(from_location) BETWEEN 1 AND 160),
    to_location TEXT NOT NULL CHECK(to_location=trim(to_location) AND length(to_location) BETWEEN 1 AND 160
        AND lower(to_location)<>lower(from_location)),
    reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
    sender_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;
CREATE INDEX IF NOT EXISTS bundle_handoffs_bundle_sequence
    ON bundle_handoffs(bundle_id,sequence DESC);

CREATE TABLE IF NOT EXISTS bundle_handoff_acceptances (
    handoff_id TEXT PRIMARY KEY REFERENCES bundle_handoffs(id),
    receiver_id TEXT NOT NULL REFERENCES users(id),
    reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS bundle_handoff_cancellations (
    handoff_id TEXT PRIMARY KEY REFERENCES bundle_handoffs(id),
    actor_id TEXT NOT NULL REFERENCES users(id),
    reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
    created_at TEXT NOT NULL
) STRICT;

CREATE TRIGGER IF NOT EXISTS bundle_handoff_valid BEFORE INSERT ON bundle_handoffs
WHEN NOT EXISTS(SELECT 1 FROM bundles b WHERE b.id=NEW.bundle_id
    AND NOT EXISTS(SELECT 1 FROM bundle_reversals r WHERE r.bundle_id=b.id))
OR EXISTS(SELECT 1 FROM bundle_handoffs h WHERE h.bundle_id=NEW.bundle_id
    AND NOT EXISTS(SELECT 1 FROM bundle_handoff_acceptances a WHERE a.handoff_id=h.id)
    AND NOT EXISTS(SELECT 1 FROM bundle_handoff_cancellations c WHERE c.handoff_id=h.id))
OR lower(NEW.from_location)<>lower(COALESCE((SELECT h.to_location FROM bundle_handoffs h
    JOIN bundle_handoff_acceptances a ON a.handoff_id=h.id WHERE h.bundle_id=NEW.bundle_id
    ORDER BY h.sequence DESC LIMIT 1),'Cutting'))
BEGIN SELECT RAISE(ABORT,'Bundle handoff requires active bundle and current custody'); END;

CREATE TRIGGER IF NOT EXISTS bundle_handoff_acceptance_valid BEFORE INSERT ON bundle_handoff_acceptances
WHEN NOT EXISTS(SELECT 1 FROM bundle_handoffs h JOIN users u ON u.id=NEW.receiver_id
    WHERE h.id=NEW.handoff_id AND h.sender_id<>NEW.receiver_id AND u.active=1
      AND u.role IN ('admin','operator')
      AND NOT EXISTS(SELECT 1 FROM bundle_handoff_cancellations c WHERE c.handoff_id=h.id)
      AND NOT EXISTS(SELECT 1 FROM bundle_reversals r WHERE r.bundle_id=h.bundle_id))
BEGIN SELECT RAISE(ABORT,'Bundle handoff acceptance requires another active operator'); END;

CREATE TRIGGER IF NOT EXISTS bundle_handoff_cancellation_valid BEFORE INSERT ON bundle_handoff_cancellations
WHEN NOT EXISTS(SELECT 1 FROM bundle_handoffs h JOIN users u ON u.id=NEW.actor_id
    WHERE h.id=NEW.handoff_id AND u.active=1 AND u.role='admin'
      AND NOT EXISTS(SELECT 1 FROM bundle_handoff_acceptances a WHERE a.handoff_id=h.id))
BEGIN SELECT RAISE(ABORT,'Only pending bundle handoff can be cancelled by admin'); END;

CREATE TRIGGER IF NOT EXISTS bundle_handoff_blocks_bundle_reversal BEFORE INSERT ON bundle_reversals
WHEN EXISTS(SELECT 1 FROM bundle_handoffs h WHERE h.bundle_id=NEW.bundle_id
    AND NOT EXISTS(SELECT 1 FROM bundle_handoff_acceptances a WHERE a.handoff_id=h.id)
    AND NOT EXISTS(SELECT 1 FROM bundle_handoff_cancellations c WHERE c.handoff_id=h.id))
BEGIN SELECT RAISE(ABORT,'Pending bundle handoff blocks bundle reversal'); END;

CREATE TRIGGER IF NOT EXISTS bundle_handoffs_no_update BEFORE UPDATE ON bundle_handoffs
BEGIN SELECT RAISE(ABORT,'Immutable bundle handoff'); END;
CREATE TRIGGER IF NOT EXISTS bundle_handoffs_no_delete BEFORE DELETE ON bundle_handoffs
BEGIN SELECT RAISE(ABORT,'Immutable bundle handoff'); END;
CREATE TRIGGER IF NOT EXISTS bundle_handoff_acceptances_no_update BEFORE UPDATE ON bundle_handoff_acceptances
BEGIN SELECT RAISE(ABORT,'Immutable bundle handoff acceptance'); END;
CREATE TRIGGER IF NOT EXISTS bundle_handoff_acceptances_no_delete BEFORE DELETE ON bundle_handoff_acceptances
BEGIN SELECT RAISE(ABORT,'Immutable bundle handoff acceptance'); END;
CREATE TRIGGER IF NOT EXISTS bundle_handoff_cancellations_no_update BEFORE UPDATE ON bundle_handoff_cancellations
BEGIN SELECT RAISE(ABORT,'Immutable bundle handoff cancellation'); END;
CREATE TRIGGER IF NOT EXISTS bundle_handoff_cancellations_no_delete BEFORE DELETE ON bundle_handoff_cancellations
BEGIN SELECT RAISE(ABORT,'Immutable bundle handoff cancellation'); END;

PRAGMA user_version=46;
COMMIT;
