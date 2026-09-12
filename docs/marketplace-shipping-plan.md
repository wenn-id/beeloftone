# Marketplace shipping

Source: Beeloft One blueprint, finished-goods workflow on page 9.

## Contract

- A shipment takes a positive quantity from one active marketplace pack and records its carrier,
  tracking number, and ship date. Several partial shipments may use a pack while their active total
  does not exceed the pack quantity.
- Shipped quantity leaves packed stock at the staging location. Sellable, reserved, available,
  picked, and production WIP are unchanged. On-hand finished-goods total decreases by the shipped
  quantity.
- Admin/operator ship. Admin corrects a whole shipment. Every active role can read.
- An active shipment blocks correction of its pack. Correction restores packed stock at the same
  staging location and preserves the original record. POST writes keep Idempotency-Key recovery.

## Boundaries

No label purchase or printing, carrier API, tracking events, delivery confirmation, multi-pack
consolidation, marketplace sync, Jubelio/WMS write, return, refund, stock opname, or adjustment is
included. The next milestone is customer return and inventory adjustment after shipment.
