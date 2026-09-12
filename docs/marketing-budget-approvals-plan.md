# Marketing budget approvals milestone

Source: Beeloft One Concept Blueprint, Phase 4 unified approvals. This milestone adds campaign
budget requests to the management queue as the final approval domain named in that phase.

## Contract

- A request records a unique internal reference, campaign name, channel, start and end dates,
  amount in IDR, objective, reason, creator, and timestamp.
- Admin and operator can submit. Admin approves or rejects; the creator can cancel their own pending
  request. Every decision requires an expected revision and reason.
- The campaign end date cannot precede its start date. Amounts use exact integer minor units and are
  limited to a positive maximum of Rp1,000,000,000,000.
- Request and decision records are append-only. The unified inbox reads the same ledger with the
  campaign, channel, period, objective, amount, reason, creator, and current status.
- Approved means the campaign ceiling is authorized. It does not record spend or move money.

## Deliberate limits

This milestone does not add campaign execution, vendors, media plans, purchase orders, actual spend,
budget consumption, invoices, reimbursements, accounting journals, attachments, comments,
notifications, configurable thresholds, or multiple approval levels.
