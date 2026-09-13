# Mekari payable snapshot milestone

Source: Beeloft One Concept Blueprint, Phase 1 read-only Mekari sync and recommended V1 key payables.
Mekari remains the authoritative finance system; Beeloft exposes management visibility.

## Contract

- An admin-only worker endpoint accepts one complete payable snapshot with an explicit position date,
  source timestamps, cursor, reason, and at most 1,000 invoices. Requests are idempotent.
- Each invoice carries vendor invoice and supplier identifiers, supplier name, invoice and due dates,
  normalized status, IDR original and paid amounts, and source update time.
- Open invoices have no payment, partial invoices have a payment below the original amount, paid
  invoices are fully paid, and void invoices have no payment. Invalid combinations are rejected.
- Beeloft derives outstanding amounts. Overdue means an unpaid invoice due before the position date;
  the seven-day bucket includes unpaid invoices due from the position date through day seven.
- Every import creates a successful `mekari/payables` run in the same transaction. Connector failures
  remain recordable through the generic integration run endpoint.
- Batch, invoice records, and run are immutable. Failed writes roll back the complete import.
- All roles can inspect the latest summary, supplier aggregation, history, and detail.

## Deliberate limits

This milestone does not call Mekari, store credentials, schedule a worker, create or approve a
payment, alter an invoice, make an accounting entry, or reconcile Beeloft supplier payment requests.
