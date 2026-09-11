# Pemakaian aktual dan waste cutting — Phase 2

Base `6894034`, local worktree `feature/core-materials`; no GitHub push/main merge. Blueprint page 8 captures actual material consumption and cutting scrap/waste.

Record actual usage against an existing, unreversed material issue. Each record contains productive used quantity and unusable waste quantity, reason, actor and UTC time. Both decimal strings nonnegative, at least one positive; m/kg at most three decimals and pcs whole. Sum of net records cannot exceed the original issue quantity. Partial reporting is allowed. Waste means unusable material, not reusable remnant; remaining quantity is **not yet reported**, not a certified physical remainder.

Admin/operator record; admin reverses entire usage record with a reason. Reverse records are immutable and cannot be reversed again. An issue with any net usage/waste cannot be reversed into rack stock until those usage entries are corrected. Issue-reversal vs usage and concurrent usage run through the same serialized write transaction/idempotency receipt. Historical issue receipts still replay after subsequent actions.

Order view lists material issues, issued/used/waste/unreported quantities and batch identity, including reversed issues marked as such. History uses descending sequence cursor, recording exact before/reversal links. Rack balances, reservations and WIP pcs are unaffected by usage recording. Usage is not automatically inferred from cutting movements. No partial return, byproduct inventory, cutting-output link, cost calculation or waste forecast in this increment.

Schema 7 adds usage ledger, no historical usage synthesized. Inputs max 1,000,000 per used/waste field, total constrained by issued amount. Reuse decimal integer storage and existing transaction/UI form recovery. All reads require authentication, all roles may read.

- [x] Write/run failing tests for partial consumption, waste, amount limits/units, roles, immutable reversal, issue reversal guard, retry, concurrent usage, rollback and migration/backup.
- [x] Implement models/schema/store/API and integrate issue reversal guard.
- [x] Add order usage dialog, recording/reversal forms and paged history; test in browser including retry/roles/mobile.
- [x] Full checks, independent review, README/OpenAPI/verifications and local commit.
