# Finished-goods QR label and scan milestone

Source: Beeloft One Concept Blueprint, Phase 3 finished-goods handoff, inventory reconciliation, and
physical/digital traceability. Finished-goods receipts already connect final QC, production lineage, SKU,
warehouse balances, reservations, adjustments, and stock counts. This milestone makes each receipt usable
as the physical identity of its warehouse lot without adding vendor connectors.

## Contract

- Every receipt exposes the stable code `BEELOFT:FINISHED-GOODS:{receipt UUID}`.
- `GET /api/finished-goods-receipts/scan` accepts that code or a case-insensitive receipt reference and
  returns the existing receipt detail and its current inventory buckets.
- All active roles can scan and print through existing read access. Existing role checks continue to control
  transfer, reservation, adjustment, stock-count, and correction actions.
- `GET /api/finished-goods-receipts/{id}/label.svg` generates an accessible QR locally with hardened headers.
- The printable label shows receipt reference, SKU, size, original received quantity, initial location,
  receipt date, and production order. Corrected receipts remain scannable but cannot generate another label.
- The workspace scan form supports keyboard scanners and Enter, preserves lookup errors for retry, escapes
  source data, prints only the 80 mm label, and works at a 390 px viewport with 200% text.

## Deliberate limits

Scanning is a lookup and does not create a warehouse movement, reservation, pick, adjustment, stock count,
or audit event. This release does not use a browser camera, batch-print labels, or change inventory rules.
Jubelio and Mekari connector runtimes remain deferred until official API access is available.
