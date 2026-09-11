# Cutting output and source material

Base `f405417`, branch `feature/cutting-output`, existing local worktree.
Blueprint page 8: Cutting captures material input, cut output, size breakdown,
scrap/waste and actual consumption. This increment connects the existing quantity
and material ledgers before adding bundling. It continues Phase 2 Core Operations.

## Scope

Admin/operator record one cutting run for an order: unique reference, one material
issue from that order, positive material used, nonnegative waste, positive output pcs
for one or more of its SKU/size lines, and reason. The run consumes only unreported
material and moves those output pcs from cutting to sewing, in one transaction.
There is no second reduction of rack stock. This form is for previously unrecorded
usage and movements; it does not attach records that were already entered separately.

One material issue per run keeps source batch traceability explicit. There is no
automatic conversion from meters to pcs and no inferred allocation of material or
waste to each size. Output numbers are actual operator input, bounded by WIP stock.
The existing standalone consumption and movement flows remain available.

Admin correction reverses all linked output movements and the material consumption
in the same transaction, then records an immutable reversal. Every SKU must still
have enough quantity in sewing. Linked records cannot be reversed independently
through the API. If any step fails, the whole correction rolls back. Original run
details remain readable and are marked corrected. Corrected quantities are historical,
not active output totals. No physical reversal is implied by a correction.

## Implementation

- Schema 13 adds immutable cutting runs and reversals. Runs reference one consumption
  event and a JSON array of movement IDs; bounded to the same 100 lines as an order.
  Insert guards verify same-order source, unused valid cutting→sewing movements and
  actual ledger reversals before a correction can be marked complete.
- Store reuses the existing material-consumption validation and production transfer
  helper. Writes retain admin/operator role checks, idempotency, and SQLite atomicity.
- API provides create/list by order, detail, and admin reversal.
- Existing order page gains Hasil cutting. Forms use native fields and existing
  replay/reload handling; detail links source batch and production order. Linked
  movement/consumption histories lead to the run instead of independent correction.
- Test API conservation, multi-size output, partial runs, overages, races, rollback,
  permissions, correction, migration, persistence/backup and cursor pagination;
  run browser QA for source selection, retry, roles, correction and mobile layout.

## Boundaries and next step

This remains quantity tracking: a run is an output event, not a physical bundle.
Same-SKU pieces remain interchangeable in WIP balance checks. No multi-material run,
cost allocation, scrap valuation, missing-pieces flow or external vendor is introduced.
The next production step on blueprint page 8 is bundling: bundle ID, SKU/size,
quantity and production order reference, followed by bundle movement traceability.
