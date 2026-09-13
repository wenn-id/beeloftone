# Mekari payroll snapshot milestone

Source: Beeloft One Concept Blueprint, Finance, HR & Payroll. Payroll calculation and records remain
in Mekari HR/payroll; Beeloft reads aggregate results and status for management visibility.

## Contract

- An admin-only worker endpoint accepts one complete payroll snapshot with source timestamps, cursor,
  reason, and at most 120 periods. Requests are idempotent.
- Each period carries a source payroll ID, date range, normalized status, employee count, IDR gross
  pay, employee deductions, employer contributions, optional payment date, and source update time.
- Net pay and total employer cost are derived with exact decimal arithmetic. Deductions cannot exceed
  gross pay. Only a paid period has a payment date.
- Every import creates a successful `mekari/payroll` run in the same transaction. Connector failures
  remain recordable through the generic integration run endpoint.
- Batch, period records, and run are immutable. Failed writes roll back the complete import.
- All roles can inspect the latest aggregate summary, history, and detail.

## Deliberate limits

The contract excludes employee names, identifiers, bank accounts, attendance rows, leave, overtime,
tax detail, and individual deductions. It does not call Mekari, calculate or approve payroll, initiate
payments, make accounting entries, store credentials, or schedule a worker.
