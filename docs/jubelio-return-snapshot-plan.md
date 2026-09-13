# Jubelio return snapshot milestone

Source: Beeloft One Concept Blueprint, Phase 1 read-only Jubelio sync and recommended V1 marketplace
return scope. This milestone records vendor return facts without treating them as inspected inventory
or creating return transactions in Beeloft.

## Contract

- An admin-only worker endpoint accepts one complete return snapshot with source timestamps, cursor,
  reason, and at most 500 returns. Each return contains at most 100 SKU lines. The request is idempotent.
- Worker input uses normalized return states: `requested`, `in_transit`, `received`, `refunded`,
  `rejected`, and `cancelled`. Only `refunded` carries a positive refund amount; other states carry zero.
- Every line contains an external item ID, external SKU, and positive quantity. A return is accepted only
  when both identifiers on every line resolve to the same active Beeloft product mapping. One unsafe
  line quarantines the whole return.
- Each import creates an observable `jubelio/returns` sync run in the same transaction. Counts describe
  returns read, accepted, and quarantined. Any quarantine makes the run fail visibly.
- Batch, accepted returns, lines, quarantine records, and sync run are immutable. Failed writes roll
  back the entire import. Quarantine retains the normalized source payload for audit.
- The latest summary counts received units only for `received` and `refunded` states. Refund totals only
  include `refunded` records. It reports status, marketplace, product, accepted return, and quarantine
  details without altering Beeloft data.
- All roles can inspect history, detail, and the latest summary.

## Deliberate limits

This milestone does not authenticate to Jubelio, call its API, schedule a worker, import customer PII,
or match a vendor return to a Beeloft shipment. It does not create internal return stock, approve a
refund, or write a settlement. Those effects require explicit operational review and lineage.
