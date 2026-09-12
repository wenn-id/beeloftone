CREATE TABLE IF NOT EXISTS ai_action_proposals (
  sequence INTEGER PRIMARY KEY AUTOINCREMENT,
  id TEXT NOT NULL UNIQUE,
  action_kind TEXT NOT NULL CHECK(action_kind IN ('create_production_order','create_purchase_request')),
  subject_id TEXT NOT NULL,
  reference TEXT NOT NULL UNIQUE CHECK(reference=trim(reference) AND length(reference) BETWEEN 1 AND 160),
  source_payload TEXT NOT NULL CHECK(json_valid(source_payload)),
  recommendation TEXT NOT NULL CHECK(json_valid(recommendation)),
  recommendation_fingerprint TEXT NOT NULL,
  action_payload TEXT NOT NULL CHECK(json_valid(action_payload)),
  reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
  actor_id TEXT NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ai_action_proposal_events (
  sequence INTEGER PRIMARY KEY AUTOINCREMENT,
  proposal_id TEXT NOT NULL REFERENCES ai_action_proposals(id),
  status TEXT NOT NULL CHECK(status IN ('submitted','approved','rejected','cancelled')),
  reason TEXT NOT NULL CHECK(reason=trim(reason) AND length(reason) BETWEEN 1 AND 1000),
  actor_id TEXT NOT NULL REFERENCES users(id),
  executed_entity_type TEXT CHECK(executed_entity_type IN ('production_order','purchase_request')),
  executed_entity_id TEXT,
  created_at TEXT NOT NULL,
  CHECK((status='approved')=(executed_entity_type IS NOT NULL AND executed_entity_id IS NOT NULL))
);

CREATE INDEX IF NOT EXISTS ai_action_proposals_actor_idx ON ai_action_proposals(actor_id,sequence DESC);
CREATE INDEX IF NOT EXISTS ai_action_proposal_events_proposal_idx ON ai_action_proposal_events(proposal_id,sequence DESC);

CREATE TRIGGER IF NOT EXISTS ai_action_proposals_immutable_update BEFORE UPDATE ON ai_action_proposals BEGIN
  SELECT RAISE(ABORT,'AI action proposals are immutable');
END;
CREATE TRIGGER IF NOT EXISTS ai_action_proposals_immutable_delete BEFORE DELETE ON ai_action_proposals BEGIN
  SELECT RAISE(ABORT,'AI action proposals are immutable');
END;
CREATE TRIGGER IF NOT EXISTS ai_action_proposal_events_immutable_update BEFORE UPDATE ON ai_action_proposal_events BEGIN
  SELECT RAISE(ABORT,'AI action proposal events are immutable');
END;
CREATE TRIGGER IF NOT EXISTS ai_action_proposal_events_immutable_delete BEFORE DELETE ON ai_action_proposal_events BEGIN
  SELECT RAISE(ABORT,'AI action proposal events are immutable');
END;
CREATE TRIGGER IF NOT EXISTS ai_action_proposal_event_lifecycle BEFORE INSERT ON ai_action_proposal_events BEGIN
  SELECT CASE
    WHEN NEW.status='submitted' AND EXISTS(SELECT 1 FROM ai_action_proposal_events WHERE proposal_id=NEW.proposal_id)
      THEN RAISE(ABORT,'AI action proposal already submitted')
    WHEN NEW.status!='submitted' AND COALESCE((SELECT status FROM ai_action_proposal_events
      WHERE proposal_id=NEW.proposal_id ORDER BY sequence DESC LIMIT 1),'')!='submitted'
      THEN RAISE(ABORT,'AI action proposal is not pending')
  END;
END;

PRAGMA user_version=31;
