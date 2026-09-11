# Verifikasi reservasi v0.11.0

2026-09-11, worktree `feature/core-materials`, dasar `3b2f693`.

- Red check: five reservation tests failed against missing route/behavior before implementation.
- Full backend suite: **61 tests passed**. Five reservation scenarios cover cross-order protection, own allocation plus free stock, partial consumption, release, receipt reversal restriction, issue reversal to free stock, key replay/conflict, issue retry, shortage math, reservations outside BOM, roles, cursor history, rollback of stock and reservation events, concurrent reserve versus issue, schema upgrade and restored backup.
- After adding assertions for reserved-issue retry and reservation-only materials outside BOM, the reservation suite passed again.
- Node client checks and JavaScript syntax check passed; `pip check` reported no broken requirements.
- Full Edge/Playwright suite passed: production, materials, BOM and reservation flows, with no JavaScript errors. Reservation checks include response lost after commit/retry exactly once, other-order issue maximum, consuming own allocation, release, event history, admin-only controls and operator/viewer reads.
- Reservation dialog tested at 320/390/768 px and 200% text. Desktop screenshot inspected; no overflow in tested states.
- Independent review found no actionable issues. Reviewer additionally ran a seeded 160-step reserve/release/issue/reversal probe against an independent balance model without discrepancies.
- `git diff --check` passed.

Tests used disposable databases and existing Python/Node/Edge/Playwright runtimes. Python script
runners set `PYTHONPATH` to this worktree when borrowing the parent virtualenv. No dependencies
added; no real/demo database migration, GitHub push, main merge, or external deployment.

Behavior limits are deliberate: manual allocations per batch/order, no BOM auto-allocation,
expiration or completion auto-release. Reversed issues return free stock and never silently
restore consumed reservations. Requirement estimates remain based on the latest BOM and the
database snapshot when read. See `reservations-plan.md` and README.
