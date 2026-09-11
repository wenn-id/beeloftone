# Materials verification — v0.9.0

Verified locally on 2026-09-11, branch `feature/core-materials`, based on `9511b7d`.

- Baseline: 44 backend tests passed before changes.
- Red check: all five initial material tests failed with missing `/api/materials` route (404).
- Final backend: **50 tests passed**, including six material acceptance tests. Coverage includes exact fractional stock, pcs validation, roles/authentication, idempotency, reversal chains, concurrent overdraw prevention, cursor pagination, batch filter, populated schema 3 migration, immutable records, transaction rollback and restored backup.
- Node client checks: passed.
- `pip check`: no broken requirements.
- Full Edge/Playwright browser suite: passed with no JavaScript errors. Existing production flows plus material master, receipt, issue from order, lost-response retry, history, admin reversal, operator/viewer restrictions and escaped material names.
- Layout: materials page checked at 320/390/768 px; material dialog checked with 200% text. Browser QA caught inaccurate select labels and an overflowing close button at enlarged text. Explicit labels and wrapping dialog headings fixed both; full suite passed afterward.
- Independent reviewer found no actionable correctness issues in schema, API, ledger, permissions or UI response guards. Generic conflict wording was expanded to cover material/batch identifiers.

Tests used disposable databases. Python dependencies came from the parent project's virtualenv;
`PYTHONPATH` was set to the worktree for script runners to ensure source imports stayed in this worktree.
The existing main checkout, demo database and GitHub branch were not modified by the feature.
No dependencies were added, no CI workflow was added, and no public deployment was performed.

Run checks from a normally installed worktree:

```powershell
./start.ps1 -SetupOnly
./.venv/Scripts/python.exe -m unittest discover -s tests -v
node tests/test_client.mjs
./.venv/Scripts/python.exe tests/run_browser.py --node PATH_NODE --playwright-module PATH_PLAYWRIGHT
./.venv/Scripts/python.exe -m pip check
```

The browser runner creates its own demo database. Optional `BEELOFT_QA_SCREENSHOTS` points to an
existing directory for material screenshots only; it does not export credentials or database files.

Limitations remain those in `materials-plan.md`: this is a first materials increment in Phase 2,
not completion of the full blueprint. Real production acceptance and external integrations remain outstanding.
