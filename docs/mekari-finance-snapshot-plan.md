# Mekari management finance snapshot milestone

Source: Beeloft One Concept Blueprint, Phase 1 read-only Mekari sync and recommended V1 management
finance summary. Mekari remains the accounting source of truth; Beeloft presents normalized facts.

## Contract

- An admin-only worker endpoint accepts one complete snapshot with source timestamps, cursor, reason,
  and at most 120 reporting periods. Requests are idempotent.
- Each period carries a source report ID, date range, IDR revenue, sales returns, cost of goods sold,
  operating expenses, other income and expenses, cash, receivables, and payables.
- Monetary input is non-negative, exact to two decimals, and capped below SQLite integer limits. Sales
  returns cannot exceed gross revenue. Source IDs and date ranges are unique within a snapshot.
- Beeloft derives net revenue, gross profit, net profit, and net liquidity from the source values. It
  does not accept separate derived totals that could contradict their components.
- Every import creates a successful `mekari/finance_summary` run in the same transaction. Connector
  failures remain recordable through the generic integration run endpoint.
- Batch, periods, and run are immutable. Failed writes roll back the complete import.
- All roles can inspect the latest management summary, snapshot history, and details.

## Deliberate limits

This milestone does not authenticate to Mekari, call its API, schedule a worker, import journal lines,
create accounting entries or payments, or replace detailed payable and receivable workflows.
