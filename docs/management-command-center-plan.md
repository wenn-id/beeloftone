# Management command center milestone

Source: Beeloft One Concept Blueprint, Phase 1 and Recommended V1. Management needs one place to see
what is happening, why it matters, and which decision requires attention today. The domain ledgers and
vendor snapshots already exist, so this milestone adds a read model and workspace over those sources.

## Contract

- `GET /api/command-center` combines production, pending approvals, replenishment risk, Jubelio sales
  and stock reconciliation, Mekari finance/payables/receivables, and integration health.
- Every vendor section includes the source snapshot timestamp or `null` when no snapshot exists.
- The response never treats a missing vendor snapshot as verified current data.
- Exceptions have a stable ID, priority, domain, explanation, and drill-down action.
- Critical production and cash obligations appear before warning-level stock, data-quality, approval,
  and integration items.
- All active application roles may read the command center. Existing endpoint permissions continue to
  govern writes reached through drill-down.
- The dashboard provides retry behavior, keyboard-accessible controls, escaped source text, responsive
  reflow, and usable layout at 200% text size.

## Deliberate limits

The read model is generated on request and does not cache, schedule, or persist a management snapshot.
Replenishment uses the established default planning assumptions. This milestone does not add charts,
custom widgets, department-specific dashboards, saved filters, notifications, or automatic actions.
