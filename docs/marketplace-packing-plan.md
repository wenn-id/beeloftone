# Marketplace packing

Source: Beeloft One blueprint, finished-goods workflow on page 9.

## Contract

- A pack records a positive quantity from one active marketplace pick and its packing date. Several
  partial packs may use a pick while their active total does not exceed the picked quantity.
- Packed quantity leaves `picked` stock and appears as `packed` stock at the same staging location.
  Sellable, reserved, available, and production WIP do not change.
- Admin/operator pack. Admin corrects a whole pack. Every active role can read.
- An active pack blocks correction of its source pick. Correction restores `picked` stock and keeps
  the original record. POST writes keep Idempotency-Key recovery behavior.

## Boundaries

No barcode scan requirement, packing-material ledger, dimensions, weight, label printing, carrier,
multi-pick consolidation, shipping, marketplace sync, or Jubelio/WMS write is included. The next
milestone is shipment confirmation from packed stock.
