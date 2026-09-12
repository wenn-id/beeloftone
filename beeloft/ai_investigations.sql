CREATE TABLE IF NOT EXISTS ai_investigations (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    question TEXT NOT NULL CHECK(question=trim(question) AND length(question) BETWEEN 2 AND 1000),
    intent TEXT NOT NULL CHECK(intent IN ('overview','production','stockout','approvals','margin')),
    source_payload TEXT NOT NULL CHECK(json_valid(source_payload)),
    result_snapshot TEXT NOT NULL CHECK(json_valid(result_snapshot)),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ai_investigation_feedback (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    investigation_id TEXT NOT NULL REFERENCES ai_investigations(id),
    rating TEXT NOT NULL CHECK(rating IN ('helpful','not_helpful')),
    reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ai_investigation_actions (
    investigation_id TEXT NOT NULL REFERENCES ai_investigations(id),
    proposal_id TEXT NOT NULL UNIQUE REFERENCES ai_action_proposals(id),
    created_at TEXT NOT NULL,
    PRIMARY KEY(investigation_id,proposal_id)
);

CREATE INDEX IF NOT EXISTS idx_ai_investigations_intent_sequence
    ON ai_investigations(intent,sequence DESC);
CREATE INDEX IF NOT EXISTS idx_ai_investigation_feedback_investigation_sequence
    ON ai_investigation_feedback(investigation_id,sequence DESC);
CREATE INDEX IF NOT EXISTS idx_ai_investigation_actions_investigation
    ON ai_investigation_actions(investigation_id);

CREATE TRIGGER IF NOT EXISTS ai_investigations_no_update
BEFORE UPDATE ON ai_investigations BEGIN
    SELECT RAISE(ABORT,'AI investigations are immutable');
END;
CREATE TRIGGER IF NOT EXISTS ai_investigations_no_delete
BEFORE DELETE ON ai_investigations BEGIN
    SELECT RAISE(ABORT,'AI investigations are immutable');
END;
CREATE TRIGGER IF NOT EXISTS ai_investigation_feedback_no_update
BEFORE UPDATE ON ai_investigation_feedback BEGIN
    SELECT RAISE(ABORT,'AI investigation feedback is immutable');
END;
CREATE TRIGGER IF NOT EXISTS ai_investigation_feedback_no_delete
BEFORE DELETE ON ai_investigation_feedback BEGIN
    SELECT RAISE(ABORT,'AI investigation feedback is immutable');
END;
CREATE TRIGGER IF NOT EXISTS ai_investigation_actions_no_update
BEFORE UPDATE ON ai_investigation_actions BEGIN
    SELECT RAISE(ABORT,'AI investigation action links are immutable');
END;
CREATE TRIGGER IF NOT EXISTS ai_investigation_actions_no_delete
BEFORE DELETE ON ai_investigation_actions BEGIN
    SELECT RAISE(ABORT,'AI investigation action links are immutable');
END;

PRAGMA user_version=32;
