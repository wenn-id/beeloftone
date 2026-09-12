# AI approved actions milestone

Source: Beeloft One Concept Blueprint, Phase 6 AI Brain. This milestone turns two supported
recommendation previews into persistent proposals with human approval and guarded execution.

## Contract

- Admin/operator can submit a production-order or purchase-request proposal from a current stockout
  investigation. Viewer remains read-only.
- The server reruns the investigation while creating the proposal and derives quantity from its own
  recommendation. Clients cannot choose or increase the recommended quantity.
- The immutable proposal captures source parameters, recommendation, fingerprint, complete action
  payload, reason, requester, and timestamp. Decision events are append-only.
- Only admin can approve or reject. The requester can cancel a pending proposal. Every decision is
  revision checked and idempotent.
- Approval reruns the investigation. A missing or changed recommendation rejects the action as stale.
- A valid approval creates the domain record and approval event atomically, then links the resulting
  entity to the proposal.
- Production approval creates an order directly. Purchase approval creates a submitted PR that still
  requires the existing purchasing approval.

## Deliberate limits

Supported actions are limited to one-SKU production orders and one-material purchase requests from
stockout analysis. Users still provide references, dates, PIC, estimated purchase value, and reason.
No free-form tool invocation, bulk execution, schedule change, external-system write, multi-step AI
policy, notification, or automatic approval is included.
