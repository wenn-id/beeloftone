# Marketplace picking

Source: Beeloft One blueprint, finished-goods workflow on page 9.

## Contract

- A pick allocates a positive quantity from one active marketplace reservation and records its
  staging location and pick date. Several partial picks may use a reservation while their active
  total does not exceed the reservation quantity.
- Picked quantity leaves sellable stock at the reservation location and appears as picked stock at
  staging. Remaining reserved and available quantities stay distinct. Production WIP is unchanged.
- Admin/operator pick. Admin corrects a whole pick. Every active role can read.
- An active pick blocks release of its reservation. Correction restores reserved sellable stock and
  preserves the original record. POST writes keep Idempotency-Key recovery behavior.

## Boundaries

No barcode scan requirement, picker assignment, wave/batch picking, tote identity, packing, shipping,
carrier integration, marketplace sync, or Jubelio/WMS write is included. The next milestone is pack
confirmation from picked stock.
