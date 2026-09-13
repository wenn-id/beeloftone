# Integration sync health milestone

Source: Beeloft One Concept Blueprint, Phase 0–1 source-of-truth map and integration guardrails.
This milestone makes the future Jubelio and Mekari data boundary explicit before credentials or vendor
traffic are introduced.

## Contract

- `GET /api/integrations` returns the fixed source-of-truth map and derived health for Jubelio and
  Mekari. Every scope is visible even when it has never synchronized.
- Jubelio owns marketplace orders, finished-goods stock and fulfillment, marketplace returns, and
  listings. Mekari owns finance summaries, payables, receivables, and payroll. Beeloft owns internal
  production execution.
- An admin worker records one immutable run through `POST /api/integration-sync-runs`. The request is
  idempotent and captures start/end time, counts, cursor, outcome, error, reason, and actor.
- Successful runs cannot carry an error. Failed runs must carry one. Counts cannot be negative, times
  require a timezone, and each scope must belong to its stated system.
- Health derives from the latest run per scope: `never_synced`, `healthy`, `stale`, or `failed`.
  System health exposes incomplete coverage instead of treating one successful scope as full health.
- History supports system, scope, and status filters plus a stable sequence cursor. Every authenticated
  role can inspect health and history; only admins can append worker results.

## Deliberate limits

This milestone does not connect to either vendor, store credentials, schedule polling, import vendor
records, or claim successful synchronization. Those steps require verified vendor API contracts,
scopes, rate limits, and production credentials. The new surface is the observable boundary that a
future connector must write after it performs real work.
