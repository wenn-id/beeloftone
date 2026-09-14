# Marketplace pick scan verification milestone

Source: Beeloft One Concept Blueprint, page 9 barcode control for picking and Phase 3 warehouse integration.
Reservations already bind marketplace demand to one finished-goods receipt, SKU, location, and quantity. This
milestone requires the physical item or lot to be verified before reserved stock moves to staging.

## Contract

- Every new pick requires `scanned_code` containing either the reserved SKU or the stable finished-goods lot
  code `BEELOFT:FINISHED-GOODS:{receipt UUID}`.
- Matching is case-insensitive after surrounding whitespace is removed. Missing or mismatched values return
  validation errors without changing inventory.
- The SQLite guard repeats the match against the reservation lineage, preventing direct-write bypass.
- The accepted value is stored on the immutable pick and in its global audit event. Pick details expose it to
  every role; existing role rules for creating and correcting picks remain unchanged.
- Existing picks migrate intact with a null scan value and are identified as records created before scan was
  required. New inserts cannot use null.
- The browser focuses the scan input, gives immediate mismatch feedback, preserves idempotent retry behavior,
  and remains usable on a 390 px viewport at 200% text.

## Deliberate limits

This is item/lot verification for an existing reservation. It does not introduce wave picking, tote IDs,
picker assignment, camera scanning, or a Jubelio/WMS write. Connector runtimes remain deferred until official
API access is available.
