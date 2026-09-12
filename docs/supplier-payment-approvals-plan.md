# Supplier payment approvals milestone

Source: Beeloft One Concept Blueprint, Phase 4 unified approvals. This milestone adds supplier
payment requests to the management queue while keeping them linked to the purchasing ledger.

## Contract

- A payment request belongs to one approved PO and records its internal reference, supplier invoice
  reference, invoice date, due date, amount, reason, creator, and timestamp.
- The PO must have active accepted receipts. Pending and approved request amounts together cannot
  exceed the accepted receipt value calculated from locked PO prices.
- Admin and operator can submit. Admin approves or rejects; the creator can cancel their own pending
  request. Every decision requires an expected revision and reason.
- Rejected and cancelled amounts return to the PO's available payment value. Approved means ready
  for payment and does not execute a bank transfer or accounting journal.
- Receipt reversal is blocked when the remaining accepted value would no longer cover pending and
  approved payment requests.
- Request and decision records are append-only. The unified inbox reads this ledger with supplier,
  PO, invoice, due date, amount, reason, creator, and decision status.

## Deliberate limits

This milestone does not add payment execution, a paid/failed bank state, cash accounts, journal
entries, tax, withholding, invoice attachments, credit notes, multi-PO invoices, comments,
notifications, configurable thresholds, or multiple approval levels.
