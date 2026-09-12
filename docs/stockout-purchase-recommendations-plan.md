# Stockout and purchase recommendations milestone

Source: Beeloft One Concept Blueprint, Phase 5 Economics & Forecasting. This final Phase 5 read model
connects demand, sellable inventory, production, BOM, material stock, purchase requests, and purchase
orders into an auditable replenishment decision.

## Contract

- Stockout risk uses current unreserved sellable stock and the weighted daily demand rate from v0.37.
- Reorder point covers lead time plus safety-stock days. Target stock covers lead time, review period,
  and safety-stock days.
- Production due inside the planning horizon contributes to inventory position. A new production
  recommendation fills the remaining target-stock gap and rounds up to the selected batch multiple.
- Material demand combines remaining BOM requirements for relevant active production with the BOM
  requirements of newly recommended production.
- Current material stock, active PR quantities, and remaining active PO quantities inside the horizon
  reduce the new purchase recommendation.
- Missing history and missing BOM remain explicit coverage states. Every result exposes its source
  quantities and planning parameters.

## Deliberate limits

The report does not create production orders or purchase requests. It does not schedule production,
predict completion dates, choose suppliers, price purchases, apply material MOQ, model capacity or
working calendars, or consume promotion and external marketplace data. Demand history respects
`as_of`; inventory and pipeline use the active ledger at calculation time. Corrections are not
reconstructed bitemporally.
