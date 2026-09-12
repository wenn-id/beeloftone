# Finished-goods stock opname and reconciliation

Source: Beeloft One blueprint, Warehouse Integration in the implementation roadmap and the
warehouse controls on page 9.

## Contract

- A stock count belongs to one active finished-goods receipt, one warehouse location, and one
  physical stock status (`sellable`, `hold`, or `damaged`).
- The operator scans the SKU and enters the physical count. The server captures the current system
  quantity in the same transaction and calculates `variance = counted - expected`.
- A non-zero variance creates a linked finished-goods adjustment. A zero variance remains a useful
  immutable count record without changing stock or production WIP.
- A count that would reduce sellable stock below active reservations is rejected. Concurrent counts
  use the current receipt balance, so a stale count cannot silently overwrite a newer result.
- Admin/operator record counts; admin corrects a whole count. Every active role can read. Corrections
  retain the original count and atomically reverse its linked adjustment.

## Boundaries

This milestone counts one receipt/location/status at a time. It does not freeze a whole warehouse,
assign count teams, support blind double counts, import scanner files, approve variances, value stock,
score abnormal adjustments, or reconcile with Jubelio/WMS.
