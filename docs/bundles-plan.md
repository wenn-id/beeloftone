# Bundle identity and cutting traceability

Base `52533c7`, branch `feature/bundles`, local worktree. Blueprint page 8 calls
for a Bundle ID, SKU/size, quantity, and production-order reference after cutting.
This increment adds that identity layer while keeping the existing WIP ledger as
the source of truth for production position.

## Scope

Admin and operator create a bundle from one active cutting output. A bundle has a
unique reference, one output movement, one SKU/size, a positive integer quantity,
an order and cutting-run link, the source material batch, a reason, actor, and time.
Several partial bundles may share an output, but their active total cannot exceed
the output quantity. Corrected bundles no longer consume that allocation.

Creating or correcting a bundle does not move WIP. Cutting already moved the pcs
from cutting to sewing; the bundle only identifies part of those pcs. Physical
packing must match the saved quantity and reference. Every active role can read
the list and lineage. Admin/operator create, while only admin corrects.

Correction applies to the whole bundle and stores a separate immutable reversal.
The original bundle stays visible. A corrected reference is not reused. Active
bundles block correction of the source cutting run; correct those bundles first,
then retry the cutting correction if the physical record supports it.

## Implementation

- Schema 14 adds immutable bundle and bundle-reversal tables. SQLite triggers
  verify that the output belongs to an active cutting run, prevent over-allocation,
  and block direct reversal of an output with an active bundle.
- Store writes use the existing immediate transaction, role checks, and
  Idempotency-Key receipt. A repeated key and identical payload returns the first
  result without creating another bundle.
- The API creates bundles from cutting runs, lists them by order, reads full source
  lineage, and records admin correction.
- The order dashboard lists bundles. Cutting details show bundled and unbundled
  quantities and expose creation only while allocation remains.
- Automated checks cover WIP conservation, partial allocation, race conditions,
  rollback, permissions, migration, backup, immutable history, retry recovery,
  keyboard use, mobile width, and 200% text size.

## Boundaries and next step

Version 0.19 does not generate barcodes, labels, or print files and does not scan
physical bundles. It does not split or merge a saved bundle, move a bundle between
production stages, assign a sewing vendor, allocate cost, or record defects and
missing pieces. Quantity balances remain per SKU, so the application does not yet
prove that a particular Bundle ID reached a later stage.

The next blueprint step is sewing/makloon traceability: send identified bundles to
an internal line or vendor, record receipt, and compare sent, returned, defect, and
missing quantities without breaking the WIP conservation rules.
