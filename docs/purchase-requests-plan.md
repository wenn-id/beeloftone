# Purchase Requests Implementation Plan

Execution: inline, following the user's instruction to continue the PDF roadmap in a worktree.
Base: 311d537. Source: blueprint pages 7 and 15, treated as product context.

Goal: track manual material purchase requests and admin decisions before implementing supplier POs.
Architecture: existing FastAPI/SQLite transaction and retry path; immutable requests and decision events.
Tech stack: Python, SQLite, vanilla browser JavaScript; no new dependencies.

## Scope and decisions

PR includes unique reference, optional production order, required date, 1–100 distinct materials,
positive quantities (m/kg three decimals; pcs whole), reason and one total estimated value in IDR
(positive string, max 1,000,000,000,000.00; two decimals; stored as integer minor units).
The estimate is entered explicitly for the whole request; it is not a supplier quote or cost posting.
Admin/operator submit; all active roles read. Admin approves or rejects submitted PRs, and can cancel
submitted/approved PRs. Requesters can cancel only their own submitted PRs. Single-operator workflow
allows admin self-approval; value-threshold routing and segregation of duties await Phase 4.
Decisions require the current revision and reason. Rejected/cancelled PRs are terminal.
Correction: cancel/reject and submit a new reference. No edit/delete or fabricated historical PRs.
Requests do not alter rack balances, reservations, BOM shortage or WIP; an approved PR is not a PO.

## Tasks

- [x] Add failing API checks: lifecycle, permission, exact quantities/value, duplicates, retries,
  stale/concurrent decisions, rollback, pagination, migration and backup.
- [x] Add schema 8, request models and Store/API methods using existing transaction machinery.
- [x] Add purchase request list/filter, multi-material form, order links and decision/history dialogs.
  Reuse form retry recovery and current visual styles. Verify browser roles, retry, stale decisions,
  empty/error states, keyboard, mobile/200% and escaping.
- [x] Run full backend/client/browser checks, independent review, update README/OpenAPI and evidence.
- [x] Commit locally in feature/core-materials. Next increment: supplier master and PO from approved PR.
