# Global audit trail milestone

Source: Beeloft One Concept Blueprint, Recommended V1. The product already keeps domain ledgers, but
an admin still needs one searchable record of who changed business data and who approved a decision.

## Contract

- Every committed write routed through `Store._write` creates one `audit_events` row inside the same
  database transaction.
- An idempotent retry returns the original result and does not create another audit row. Validation,
  authorization, conflict, or domain failures create no row.
- Each event snapshots the operation, category, subject identity and reference, actor ID/name/role,
  request key, sanitized input, scalar outcome, and UTC timestamp.
- Approval decisions have their own category. Other categories cover master data, production,
  materials, purchasing, warehouse, marketplace, AI, and integrations.
- Bulk vendor arrays are represented by record counts. Credential-shaped fields are redacted.
- Audit rows are append-only: database triggers reject update and delete.
- Admins can list and inspect events using search, category, actor, Jakarta date range, and cursor
  pagination. Other roles receive 403 and do not see the navigation control.
- The browser escapes all values and remains usable at 390 px and 200% text size.

## Deliberate limits

The first release audits authenticated business writes that use the central idempotent transaction
path. Account provisioning and disabling from the CLI, session login/logout, and OIDC security events
remain outside this ledger. Search is backed by indexed dimensions plus SQLite substring matching;
full-text indexing and archival policies can be added when operational volume requires them.
