# Bundle two-party handoff milestone

Source: Beeloft One Concept Blueprint, Phase 3 physical/digital traceability and production handoff.
Bundle identity and QR lookup already exist. This milestone records who released a physical bundle, who
received it, and where custody moved.

## Contract

- An admin or operator creates a handoff from the bundle's current custody location to a named destination.
- The initial custody location is `Cutting`; every later origin is derived from the latest accepted handoff.
- Each bundle can have at most one pending handoff.
- A different active admin or operator accepts the physical bundle. Acceptance changes custody; creation alone
  does not.
- The sender cannot accept their own handoff. Only an admin can cancel a pending handoff.
- Corrected bundles cannot start or accept handoffs, and a pending handoff blocks bundle correction.
- Creation, acceptance, and cancellation use the existing actor-scoped idempotency contract and global audit
  trail.
- Handoff, acceptance, and cancellation rows are immutable. History is newest first with cursor pagination.
- Bundle detail and scan results expose current custody and the pending handoff. The dashboard provides the
  same create, accept, cancel, and history flow while keeping viewer access read-only.

## Deliberate limits

Custody is independent from the aggregate WIP ledger. Acceptance does not create a production movement or
sewing job. Locations are controlled text rather than a location master, and the release does not add camera
scanning, signatures, photos, notifications, split/merge bundles, or offline synchronization.
