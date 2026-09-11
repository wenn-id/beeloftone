# Supplier and Purchase Order Implementation Plan

Base b914e73, feature/core-materials worktree; local commit, no push.
Continue blueprint page 7 steps 3–4 and Phase 2 purchasing, per user's approved roadmap.
Use existing FastAPI/SQLite transaction, decimal and browser retry patterns. No new dependencies.

## Design

Admin creates an immutable supplier master: unique uppercase code, name, optional contact/address
and required reason. All active roles read. Correct errors using a new supplier code at this stage.
Admin creates an issued PO from one currently approved PR, with the PR's current revision.
Exactly all PR material lines/quantities go to one supplier; request includes a price for each
material, unique PO reference, expected receipt date, purchase terms and reason. No quantity overrides.
Prices are positive IDR strings, max 1,000,000,000.00 per unit, two decimals. Quantities retain three
decimals. Round each line half-up to 0.01 rupiah, require each rounded line positive and sum totals
in integer minor units. Total may not exceed the approved PR estimate. To increase budget,
cancel/recreate the PR and obtain a fresh approval. No taxes, freight, discounts or other currencies.

Lock supplier snapshot, PR revision and lines/prices/terms at issue. One active PO per PR.
Admin cancels a whole PO with a reason; original remains intact and a replacement PO with a new
reference can then be issued against the still-approved PR. Active PO blocks PR cancellation.
Concurrent PO creation, PO/PR cancellation, and request retries are serialized in existing _write.
No external transmission: issued means recorded internally, not delivered to supplier.
PO does not add stock, reduce BOM shortage, change reservations or move WIP. Receipt linkage,
partial fulfillment, split suppliers and payments remain subsequent increments.

Schema 9 adds supplier, purchase_orders and immutable cancellation records; preserves schema 8 data.
UI: master supplier and PO list under purchasing, issue PO from PR detail, locked-price form, PO
detail/total/source PR and cancellation reason. Use existing styles and guarded dialog/retry state.

## Tasks

- [x] Write failing API tests: exact rounding, approved budget, full PR coverage, supplier/roles,
  retry, cancellation, competing PO and PR cancel, rollback, migration/backup/cursor.
- [x] Implement schema 9/models/store/API and PR cancellation guard and linked PO summaries.
- [x] Implement supplier/PO dialogs; browser tests for creation/retry, permission, errors, cancellation,
  source links, mobile and 200% scaling.
- [x] Run backend/client/browser verification, independent review, update README/OpenAPI/evidence.
- [x] Commit locally. Next: receipt against PO and received/remaining quantities.
