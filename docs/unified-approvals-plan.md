# Unified approvals milestone

Source: Beeloft One Concept Blueprint, Phase 4 and recommended V1. This milestone puts two
high-value workflows in one decision queue: existing purchase requests and production schedule/PIC
change requests.

## Contract

- The unified inbox is a read model over domain-owned approval records. Purchase and production
  history remain in their own ledgers.
- Admin/operator can request a production due-date or PIC change. The order does not change until
  an admin approves it.
- A request captures the order revision, due date and PIC seen by the requester. Approval is rejected
  if that revision is stale or the proposed PIC is no longer active.
- Only one production change request may be pending for an order. A terminal request allows a new
  request.
- Admin approves or rejects. The requester may cancel their own pending request. Every decision is
  append-only and requires a reason.
- Approval applies the order change and writes the existing order-change audit record in the same
  transaction. Its ID is linked back to the approval.
- All active roles can read the inbox and details. Viewer cannot request or decide.
- Queue filters cover pending/approved/rejected/cancelled and purchasing/production. Pagination uses
  limit and offset because records come from two independent ledgers.

## Deliberate limits

No configurable thresholds, multi-step approvers, delegation, comments, attachments, reminders,
notifications, supplier-payment approval, marketing-budget approval, or external Mekari/Jubelio
write is included. Those require validated policy and integration contracts; the queue and domain
decision pattern built here can add them without changing existing records.
