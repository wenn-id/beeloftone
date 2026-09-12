# Customer returns and finished-goods adjustments

Source: Beeloft One blueprint, warehouse and commerce workflow on page 9.

## Contract

- A return takes a positive quantity from one active marketplace shipment. Partial returns are
  allowed while their active total does not exceed the shipment quantity.
- A return records one structured reason (`too_small`, `too_big`, `wrong_item`, `defect`,
  `color_mismatch`, or `other`), a warehouse location, and an inspected stock status (`sellable`,
  `hold`, or `damaged`). It restores on-hand finished goods without changing production WIP.
- A finished-goods adjustment belongs to one active receipt and records a signed count difference
  for one location and status. Negative adjustments cannot overdraw physical stock or reserved
  sellable stock. Positive adjustments increase on-hand stock.
- Admin/operator record returns and adjustments. Admin corrects a whole record. Every active role
  can read. Active returns block shipment correction. All writes are immutable and idempotent.

## Boundaries

No refund, exchange shipment, return label, carrier event, photo attachment, approval workflow,
financial journal, automated anomaly score, marketplace sync, or Jubelio/WMS write is included.
