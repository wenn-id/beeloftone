# Jubelio finished-goods stock snapshot milestone

Source: Beeloft One Concept Blueprint, Phase 1 read-only Jubelio sync and recommended V1 sellable
stock scope. This milestone consumes the SKU identity boundary from v0.43 and adds the first vendor
data snapshot without allowing vendor data to mutate Beeloft's production ledger.

## Contract

- An admin-only worker endpoint accepts one complete finished-goods snapshot with source timestamps,
  cursor, reason, and at most 500 records. The request is idempotent.
- Every record includes a Jubelio record ID, Jubelio SKU, sellable quantity, and reserved quantity.
  Quantities are nonnegative and reserved cannot exceed sellable.
- A record is accepted only when both external identifiers resolve to the same active Beeloft product
  mapping. Unknown identifiers and inconsistent pairs are quarantined instead of guessed.
- Each import creates an observable `jubelio/finished_goods` sync run in the same transaction. Counts
  reflect the input, accepted records, and quarantine. Any quarantine makes the run fail visibly.
- Batch metadata, accepted records, quarantine, and sync run are immutable. Failed writes roll back
  the entire import.
- Reconciliation uses only the latest batch and compares Jubelio available quantity with Beeloft
  finished-goods available quantity. It reports matched, mismatched, missing, and quarantined rows.
- All roles can inspect batch history, batch detail, and reconciliation. These reads never change
  Beeloft inventory.

## Deliberate limits

This milestone does not authenticate to Jubelio, call its API, schedule a worker, or adjust Beeloft
stock. The endpoint is the stable ingestion boundary for a future connector. Automatic adjustment is
deferred because a mismatch needs operational review and an auditable stock-opname decision.
