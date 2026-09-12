# AI investigation memory milestone

Source: Beeloft One Concept Blueprint, Phase 6 AI Brain and the governance goal of durable Beeloft
decision data. This milestone turns an investigation result into traceable operational memory.

## Contract

- Every role can run and persist an authorized investigation with an Idempotency-Key. The immutable
  snapshot contains the source parameters, complete result, actor, and timestamp.
- Investigation history supports intent and question filters plus a stable sequence cursor. Detail
  returns the original evidence even after the current business ledger changes.
- Every role can append helpful or not-helpful feedback with a reason. History remains immutable;
  summary counts the latest response from each actor.
- A production-order or purchase-request proposal created from a saved result links back to that
  investigation. Proposal creation rejects changed assumptions, missing recommendations, or a
  recommendation whose current fingerprint differs from the snapshot.
- Existing approval-time revalidation, role checks, transactional execution, and audit history stay
  in force.
- The original `POST /api/ai/investigate` remains a compatible non-persistent preview endpoint.

## Deliberate limits

Feedback is decision data only. It does not train a model, adjust recommendation rules, or trigger an
action. The analysis engine remains local rules over Beeloft ledgers; no external model or company data
transfer is added. History is shared across authenticated roles because the underlying investigation
sources are already readable by those roles. Data retention and per-department visibility can be
added when Beeloft defines those policies.
