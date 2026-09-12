# Production cost reporting milestone

Source: Beeloft One Concept Blueprint, Phase 5 Economics & Forecasting. This first Phase 5 milestone
builds a cost read model from operational ledgers that already have verified lineage.

## Contract

- Material cost uses net active material consumption, including waste, multiplied by the locked unit
  price on the Purchase Order linked to the source batch. Each line rounds to integer IDR minor units.
- Sewing cost sums active internal and makloon job costs for the order. Corrected jobs are excluded.
- The report exposes known material and sewing costs, target quantity, active finished-goods receipts,
  cost per target unit, and cost per finished unit.
- A total is complete only when the order has material consumption, every consumed batch has a PO
  price, and every active issue is fully reported as used or waste. Otherwise `total_cost` and unit
  costs are null and structured coverage gaps identify the missing source.
- The report is computed from immutable operational ledgers. It creates no accounting transaction
  and needs no schema migration.

## Deliberate limits

This milestone does not include internal labor, finishing, QC, packaging, freight, overhead,
inventory valuation, sales revenue, contribution margin, accounting journals, or Mekari/Jubelio
integration. Those require additional source ledgers or verified external contracts.
