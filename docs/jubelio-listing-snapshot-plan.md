# Jubelio listing snapshot milestone

Source: Beeloft One Concept Blueprint, Phase 1 read-only Jubelio sync and marketplace listing scope.
This milestone records vendor listing facts without treating them as Beeloft product, price, or stock changes.

## Contract

- An admin-only worker endpoint accepts one complete listing snapshot with source timestamps, cursor,
  reason, and at most 1,000 listings. Requests are idempotent.
- Each listing carries its vendor listing ID and reference, marketplace, title, normalized status,
  positive listed price, update time, external item ID, and external SKU.
- A listing is accepted only when both external identifiers resolve to one active Beeloft product
  mapping. Unmapped and inconsistent pairs are quarantined as complete records.
- Each import creates an observable `jubelio/listings` sync run in the same transaction. Counts report
  records read and accepted; any quarantine makes the run fail visibly.
- Batch, accepted listings, quarantine records, and sync run are immutable. Failed writes roll back
  the complete import, while quarantine retains the normalized payload for audit.
- The latest summary reports listing status, active product coverage, active price range, marketplace
  totals, accepted listings, and quarantine records. All roles can inspect summary, history, and detail.

## Deliberate limits

This milestone does not authenticate to Jubelio, call its API, schedule a worker, alter a vendor
listing, or update Beeloft product, internal price, or stock records.
