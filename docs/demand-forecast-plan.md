# Demand forecast milestone

Source: Beeloft One Concept Blueprint, Phase 5 Economics & Forecasting. This milestone turns the
existing marketplace shipment and return ledger into a traceable per-SKU demand forecast.

## Contract

- The caller selects an explicit `as_of` date, historical window length, and forecast horizon.
- History consists of two adjacent windows of equal length. The recent daily rate has weight 70%
  and the previous daily rate has weight 30%.
- Active marketplace shipments provide gross demand. Active returns dated on or before `as_of`
  reduce demand in the original shipment's period.
- Corrected shipments and corrected returns are excluded. Products without observed demand remain
  visible with a distinct `no_history` status.
- Results expose the source quantities, daily rates, trend, method weights, date boundaries, and a
  two-decimal forecast quantity so users can audit the calculation.

## Deliberate limits

This forecast does not include inventory, inbound purchase orders, supplier lead time, MOQ, safety
stock, promotions, seasonality, or external marketplace demand. It is a read model over the current
active ledger. `as_of` filters business dates but does not reconstruct the historical moment when a
correction was recorded. Stockout and purchase recommendations remain a separate roadmap milestone.
