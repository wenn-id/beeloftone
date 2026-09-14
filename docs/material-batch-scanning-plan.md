# Material batch QR label and scan milestone

Source: Beeloft One Concept Blueprint, Phase 3 raw-material scanning and physical/digital traceability.
Material batches already own receipt, location, reservation, issue, consumption, purchase-order, and QC
lineage. This milestone makes that identity usable from a physical label without adding vendor connectors.

## Contract

- Every material batch exposes the stable code `BEELOFT:MATERIAL-BATCH:{batch UUID}`.
- `GET /api/material-batches/scan` accepts that code or a case-insensitive batch reference and returns the
  existing batch detail.
- All active roles can scan and print because the actions follow existing material read permissions.
- The batch detail exposes original received quantity and whether its receipt is active or corrected.
- `GET /api/material-batches/{id}/label.svg` generates an accessible QR locally with hardened response headers.
- The printable label shows batch reference, material code/name, original quantity/unit, location, and receipt
  date. Corrected receipts remain scannable but cannot generate another label.
- The materials screen supports keyboard scanners and Enter, keeps lookup errors available for retry, escapes
  source data, prints only the 80 mm label, and remains usable on a 390 px viewport at 200% text size.

## Deliberate limits

Scanning is a lookup and does not create a material movement, reservation, issue, or audit event. This release
does not use a browser camera, batch-print labels, move a batch between locations, or call Jubelio/Mekari. Runtime
connectors remain deferred until official API access is available.
