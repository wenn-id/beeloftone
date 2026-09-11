# Warehouse transfers and hold decisions

Source: Beeloft One blueprint, warehouse page 9.

## Contract

- Every movement keeps the finished-goods receipt as its stock source. Inventory is derived from
  the original receipt plus active movement events; no mutable balance column is introduced.
- A transfer moves a positive quantity between two different locations without changing status.
  Supported statuses are sellable, hold, and damaged.
- A hold decision moves hold stock to sellable (`hold_release`) or damaged (`hold_damage`). It may
  keep the same location or move to another location in the same event.
- Source location/status must have enough stock. Movement date cannot precede receipt date.
- Admin/operator record movements. Admin corrects a whole movement when its target bucket still
  has enough stock. Every active role can read movements and inventory.
- An active movement blocks correction of its finished-goods receipt. References and POST retries
  retain the existing uniqueness and Idempotency-Key behavior.

## Boundaries

This milestone does not reserve marketplace stock, integrate Jubelio/WMS, print labels, manage
bins, pick, pack, ship, receive returns, perform stock opname, or post arbitrary adjustments.
The next warehouse milestone is marketplace reservation and fulfillment allocation.
