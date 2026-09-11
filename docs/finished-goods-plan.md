# Finished goods completion and warehouse receipt

Source: Beeloft One blueprint, production system page 8 and warehouse page 9.
This milestone records finished quantity received into separate sellable and hold
inventory after final QC pass.

## Contract

- A finished-goods receipt allocates a positive quantity from the accepted output
  of one active final QC record. Several partial receipts may use one QC record,
  but their active total cannot exceed its accepted quantity.
- The receiver scans or enters the exact SKU, records a location and receipt date,
  then splits quantity into sellable and hold. Their sum is the received quantity.
- Receipt does not move WIP because accepted QC pieces already moved to warehouse.
  It classifies the warehouse quantity into operational inventory states.
- Admin/operator receive. Admin corrects a whole receipt. Correction releases its
  allocation without changing WIP and preserves the original record.
- An active receipt blocks correction of its final QC source. Every active role can
  read receipt lists, details, and the SKU inventory summary. POST writes retain
  the existing Idempotency-Key recovery behavior.
- Final QC now also captures the blueprint's defect type, responsible source, and
  disposition alongside accepted, rework, and reject outcomes.

## Boundaries

Beeloft remains the internal record in this release. Jubelio/WMS is not connected
and no marketplace stock is mutated. Barcode master data, label generation,
putaway transfers, hold release, reservations, pick/pack/ship, returns, stock
opname, and adjustments remain later warehouse increments.

The next milestone is warehouse transfers and controlled release from hold.
