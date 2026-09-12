# Purchase Order issuance approvals milestone

Source: Beeloft One Concept Blueprint, Phase 4 unified approvals. This milestone adds Purchase Order
issuance to the existing management queue and keeps purchasing records in their domain ledger.

## Contract

- Creating a PO from an approved PR records a submitted approval event. It does not authorize the
  supplier order to receive material yet.
- Admin and operator can prepare a PO. Admin approves or rejects it; the creator can cancel their
  own pending submission. Every action requires a reason and expected approval revision.
- Approval history is append-only. A terminal rejected or cancelled submission permits a replacement
  PO from the same PR; a pending, active, or closed PO continues to block duplicates.
- Direct receipt and incoming-QC creation require an approved, active PO. Application checks and
  SQLite triggers enforce the same boundary.
- The unified inbox reads the PO ledger beside PR and production-change ledgers. Its PO cards include
  the amount, supplier, source PR, material count, expected date, reason, submitter, and timestamp.
- Existing POs receive one approved migration event using their original actor and timestamp. Their
  active, cancelled, or closed business status remains unchanged.

## Deliberate limits

This milestone does not add configurable amount thresholds, multiple approval levels, different
approvers per department, supplier dispatch, documents, comments, reminders, notifications, or
supplier-payment approval. Those policies need operating rules and verified external contracts.
