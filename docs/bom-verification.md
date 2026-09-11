# Verifikasi BOM v0.10.0

2026-09-11, worktree `feature/core-materials`, dasar commit `117b24f`.

- Baseline v0.9: 50 backend tests passed.
- Red: four initial BOM tests failed because routes/revision responses did not exist. Decimal display test failed because its formatter did not exist.
- Final: **56 backend tests passed**, including six BOM tests covering shared materials, fractional quantities, net issues/reversals, missing BOM, material outside current BOM, revision history and cursor, conflicting retry, stale/concurrent writes, role validation, schema upgrade, rollback, immutable history and aggregates exceeding SQLite's integer range.
- Node client checks passed, including exact display of `1000000000000000.125` and negative fractions.
- Full Edge/Playwright browser suite passed with no JavaScript errors. BOM cases: missing BOM warning, creation from order, uncertain committed save/retry without duplication, requirement/shortage calculation, concurrent tab conflict, complete old/new version contents and viewer read-only behavior. Existing production/material flows still pass.
- Dialogs checked at 320/390/768 px and 200% text; desktop requirements and mobile history screenshots inspected. No overflow in tested states.
- Independent review found no actionable correctness issues. Reviewer also verified concurrent saves returned one 201 and one 409.
- `pip check`: no broken requirements. `git diff --check`: no whitespace errors.

All application checks used temporary databases. No production/demo database was migrated by this increment. Main checkout and GitHub remain unchanged. No new dependency, CI workflow, external integration or deployment.

Runtime used for QA: parent `.venv/Scripts/python.exe` with `PYTHONPATH` set to the worktree so script imports use local source; Node 24 and locally installed Edge via Playwright. A normally installed worktree can use README test commands.

This release implements a live latest-BOM estimate. It does not preserve an order-time BOM snapshot, reserve inventory, estimate waste, consume materials, or certify stock sufficiency across multiple orders. See `bom-plan.md` and README for formulas and scope.
