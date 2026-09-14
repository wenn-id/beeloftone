# Warehouse movement scan verification milestone

Source: Beeloft One Concept Blueprint, page 9 barcode control for warehouse transfers and Phase 3 warehouse
integration. Finished-goods receipts already have a stable lot QR and warehouse movements already preserve
their receipt lineage. This milestone requires that physical source to be verified before stock moves.

## Contract

- Every new location transfer, hold release, and damaged decision requires `scanned_code` containing either
  the receipt SKU or stable code `BEELOFT:FINISHED-GOODS:{receipt UUID}`.
- Matching is case-insensitive after surrounding whitespace is removed. Missing or mismatched values fail
  without changing inventory.
- SQLite repeats the lineage match so direct writes cannot bypass the API rule.
- The accepted scan is stored on the immutable movement and in its global audit event. Existing movement
  read and correction permissions do not change.
- Existing movements migrate intact with a null value and their detail identifies them as predating the rule.
- The browser focuses the scan input, rejects a mismatch immediately, keeps idempotent retry behavior, and
  remains usable at a 390 px viewport with 200% text.

## Deliberate limits

This verifies an existing Beeloft receipt at movement time. It does not introduce bin master data, destination
bin scans, camera integration, or a Jubelio/WMS write. Connector runtimes remain deferred until official API
access is available.
