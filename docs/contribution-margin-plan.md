# Contribution margin milestone

Source: Beeloft One Concept Blueprint, Phase 5 Economics & Forecasting. This milestone adds the
missing commercial ledger required to calculate contribution margin from traceable internal data.

## Contract

- One active settlement may exist for each active marketplace shipment. A replacement requires an
  immutable correction of the previous settlement.
- A settlement captures gross revenue, seller discount, customer refund, marketplace fee, seller
  shipping cost, other variable cost, settlement date, and the active returned quantity at capture.
- Net revenue is gross revenue minus seller discount and customer refund. Variable selling cost is
  marketplace fee plus seller shipping cost and other variable cost.
- Production cost is allocated with HALF_UP rounding from the order total according to net sold
  quantity divided by active finished quantity.
- Contribution margin is net revenue minus variable selling cost and allocated production cost.
- Margin is complete only when production cost is complete, finished quantity exists, every active
  shipment has a settlement, and each settlement still covers the current returned quantity.

## Deliberate limits

Tax, separately reported payment gateway fees, advertising, fixed overhead, return handling,
inventory write-off, accounting journals, and external marketplace/Mekari synchronization remain
outside this milestone. Production allocation inherits the source coverage declared by the v0.35
production cost report.
