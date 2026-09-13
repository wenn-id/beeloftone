# Jubelio SKU mapping milestone

Source: Beeloft One Concept Blueprint, Phase 0 data map and recommended V1 product/SKU mapping.
This milestone gives the future Jubelio connector an explicit identity boundary before vendor records
are imported.

## Contract

- Every Beeloft product can have one current Jubelio mapping containing an opaque external record ID
  and the vendor SKU code. A product without a mapping remains explicitly `unmapped`.
- Current external IDs and SKU codes are unique across Beeloft products. Comparisons for external SKU
  codes are case-insensitive; values are otherwise preserved as entered.
- Admins can connect, replace, or release a mapping with an Idempotency-Key, expected revision, and
  reason. Operator and viewer roles can inspect the current mapping and its history.
- Every change is an immutable event with actor and timestamp. A stale revision, no-op update,
  duplicate identifier, or release of an already-unmapped product is rejected.
- Mapping coverage is exposed in Jubelio integration health as mapped, unmapped, and total products.
  Coverage is readiness metadata and does not affect or claim vendor sync health.
- Lists support mapped/unmapped status and offset pagination. History uses a stable sequence cursor.

## Deliberate limits

This milestone does not call Jubelio, verify that an identifier exists in the vendor account, import
orders/sales/stock/returns, or change Beeloft inventory. Those actions require a verified API contract
and credentials. The mapping ledger is the prerequisite a connector will use to reject unknown SKUs
instead of guessing by product text.
