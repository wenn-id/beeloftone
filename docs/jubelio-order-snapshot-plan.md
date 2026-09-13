# Jubelio order and sales snapshot milestone

Source: Beeloft One Concept Blueprint, Phase 1 read-only Jubelio sync and recommended V1 sales/order
scope. This milestone consumes the SKU mapping boundary and records vendor order facts without creating
production or fulfillment transactions in Beeloft.

## Contract

- An admin-only worker endpoint accepts one complete order snapshot with source timestamps, cursor,
  reason, and at most 500 orders. Each order contains at most 100 SKU lines. The request is idempotent.
- Worker input uses normalized order states: `pending`, `processing`, `completed`, and `cancelled`.
  Every line carries an external item ID, external SKU, positive unit count, and exact gross revenue.
- An order is accepted only when every line's two external identifiers resolve to the same active
  Beeloft product mapping. One unsafe line quarantines the whole order, preventing partial unit or
  revenue totals.
- Each import creates an observable `jubelio/orders` sync run in the same transaction. Counts describe
  orders read, accepted, and quarantined. Any quarantine makes the run fail visibly.
- Batch, accepted orders, lines, quarantine records, and sync run are immutable. Failed writes roll
  back the entire import. Quarantine retains the normalized source payload for audit.
- The latest snapshot summary reports state counts, completed units and gross revenue, marketplace
  totals, accepted orders, and quarantine. Pending, processing, and cancelled orders do not count as
  completed sales.
- All roles can inspect history, detail, and the latest summary. These reads do not create production
  orders, reservations, shipments, settlements, or inventory movements.

## Deliberate limits

This milestone does not authenticate to Jubelio, call its API, schedule a worker, import customer PII,
or merge vendor orders into Beeloft's internal fulfillment ledger. Returns remain a separate roadmap
scope because their lifecycle and stock effects need an independent immutable boundary.
