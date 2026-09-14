# Bundle QR labels and scan lookup milestone

Source: Beeloft One Concept Blueprint, production bundle identity and Phase 3 physical/digital traceability.
Existing bundles already connect cutting output, SKU/size, production order, raw-material batch, and sewing
allocation. This milestone makes that identity usable on the production floor.

## Contract

- Every bundle exposes the stable scan code `BEELOFT:BUNDLE:{bundle UUID}`.
- `GET /api/bundles/scan` accepts that QR value or a case-insensitive Bundle ID and returns the existing
  bundle detail without creating a second inventory or WIP record.
- All active roles can scan because the result follows the existing bundle read permission. Invalid,
  unknown, and unauthenticated scans fail explicitly.
- `GET /api/bundles/{id}/label.svg` generates a QR locally at request time. The SVG includes an accessible
  title/description, a medium error-correction QR, and response hardening headers.
- The printable label also shows Bundle ID, SKU, size, quantity, and production-order reference.
- Corrected bundles remain traceable through scan lookup, while their labels cannot be printed again.
- The workspace scan field receives focus automatically, supports keyboard-style scanners and Enter, keeps
  errors in the dialog for retry, escapes source text, and remains usable at 390 px and 200% text size.
- Print media hides the application and prints only the 80 mm bundle label.

## Deliberate limits

Scanning is a lookup, not a two-party handoff confirmation, production movement, or audit event. The first
release does not use the browser camera, batch-print many labels, provision printer templates, or split/merge
bundles. QR generation adds the pure-Python `qrcode` dependency and does not call an external service.
