# Incoming material QC

Base `ab9fe20`, branch `feature/core-materials`, local worktree. Blueprint page 7 calls for
usable quantity, lot/QC, putaway and reservation; this increment isolates QC before putaway.

## Design

An arrival from an active PO is recorded as a QC intake and remains on hold. The intake keeps
the PO material, quantity, arrival reference, location, date, actor and reason. Held quantity
counts against the PO's remaining receivable amount, but does not enter material stock or
reservations.

An admin can make partial decisions. `accept` creates a new usable batch and links its receipt
to the PO; `reject` creates no stock and opens the same quantity as a PO replacement allowance.
Undecided quantity remains held. Decisions and cancellations are immutable. A correction is
another ledger event: accepted material must pass the existing stock/reservation/consumption
reversal guards, while a rejected quantity can return to hold only if the replacement allowance
is still available.

Existing direct PO receipts remain supported for material already accepted at intake. Existing
manual receipts remain independent and are not inferred as QC or PO events. PO cancellation
requires no active usable receipt and no held quantity.

## Tasks

- [x] Add schema 11, immutable QC intake/decision/cancellation tables, PO quota views and SQL guards.
- [x] Add typed API inputs, intake/detail/decision/reversal/cancellation routes, and transaction-safe store methods.
- [x] Add PO QC UI, partial accept/reject actions, batch links, role controls, and responsive states.
- [x] Add API/browser tests for hold accounting, replacement quota, retries, races, rollback, migration,
  backup, stock/reservation guards, source links, mobile and 200% scaling.
- [x] Run full verification, update README/OpenAPI/evidence, request independent review, and commit locally.
- [x] Supplier returns and formal PO closure after QC — see `supplier-returns-plan.md` (v0.17).
