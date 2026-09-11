# Supplier returns and PO closure

Base `5cd0661`, branch `feature/supplier-returns`, local worktree.
Continues the next item in `incoming-qc-plan.md`. Blueprint pages 6–7 call for
records of physical events and purchased versus usable quantities; page 15 groups
purchasing, materials and QC in Phase 2. Returns and closure are this implementation's
next increment within that phase, not separately named phases in the PDF.

## Behavior

- Admin records partial physical returns from an intake's rejected quantity, with a
  unique shipment reference, dispatch date, quantity, reason, actor and timestamp.
  A return creates no usable stock and no additional PO replacement allowance.
- Returns are immutable. Admin can reverse a whole mistaken entry before PO closure
  or cancellation, then record the correct shipment. A reject correction cannot make
  rejected quantity smaller than already returned quantity.
- An admin closes an issued PO only after at least one active usable receipt, zero QC
  hold and zero reject awaiting return. Full and partial fulfillment both qualify.
  Ordered quantity, price and unreceived shortfall remain visible. Receivable becomes
  zero and receipts, QC, returns and their corrections become final. Usable material
  remains available for ordinary production issues, reservations and consumption.
- A PO without active usable receipts uses cancellation instead. Cancellation also
  requires no hold or unreturned reject. Legacy cancelled POs may record outstanding
  returns after migration, but those returns are final. Closed POs continue to block
  duplicate ordering/cancellation of their source PR.
- Every write uses existing atomic transactions, admin role checks and idempotency.
  Schema 12 adds two ledger tables, a totals view and database guards. No dependency
  or external integration is added. No supplier message or payment is sent.
- Existing native dialogs, quantity formats and theme rules from `DESIGN.md` apply.
  Return history is in QC detail; return totals and closure are in PO detail, and the
  PO list supports a closed filter. Forms use the existing reload/retry mechanism.

## Verification

- Backend: partial return/reversal, quota conservation, races, rollback, permissions,
  SQL guards, closure/shortfall, usable stock, source PR, migration, persistence, backup.
- Browser: end-to-end return, lost-response reload/retry, correction, roles, closure,
  closed filter, safe text rendering, mobile and 200% text scaling.
- Full backend/client regression, JS syntax, package check, OpenAPI export and review.

## Boundaries

No reopening a final PO, return of already accepted stock, credit note, payment,
supplier acknowledgement, shipping integration or printed return document yet.
Further roadmap work should continue Phase 2 production traceability and warehouse
handoff according to the blueprint, rather than treat these exclusions as new phases.
