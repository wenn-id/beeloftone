# Mekari receivable snapshot milestone

Source: Beeloft One Concept Blueprint, Phase 1 read-only Mekari sync and recommended V1 key receivables.
Mekari remains the authoritative finance system; Beeloft exposes management visibility.

## Contract

- An admin-only worker endpoint accepts one complete receivable snapshot with an explicit position
  date, source timestamps, cursor, reason, and at most 1,000 invoices. Requests are idempotent.
- Each invoice carries receivable and customer identifiers, customer name, invoice and due dates,
  normalized status, IDR original and received amounts, and source update time.
- Open invoices have no receipt, partial invoices have a receipt below the original amount, paid
  invoices are fully received, and void invoices have no receipt. Invalid combinations are rejected.
- Beeloft derives outstanding amounts. Overdue means an unpaid invoice due before the position date;
  the seven-day bucket includes unpaid invoices due from the position date through day seven.
- Every import creates a successful `mekari/receivables` run in the same transaction. Connector
  failures remain recordable through the generic integration run endpoint.
- Batch, invoice records, and run are immutable. Failed writes roll back the complete import.
- All roles can inspect the latest summary, customer aggregation, history, and detail.

## Deliberate limits

This milestone does not call Mekari, store credentials, schedule a worker, contact a customer,
alter an invoice, make an accounting entry, or reconcile Beeloft marketplace settlements.
