# Verifikasi PR v0.13.0

Base 311d537; local feature/core-materials worktree. Test data uses temporary databases.
Blueprint reference: pages 7 and 15; scope is manual PR and local admin decisions, before PO.

## Results

- Red: four API acceptance tests initially failed on missing PR endpoints (404).
- Green: 71 backend tests passed, including five PR tests. Covers exact quantity/IDR storage,
  duplicate materials and references, validation/permissions/revocation, stale and concurrent
  decisions, immutable history, request and decision rollback, retry after later state changes,
  cursor/status/order filtering, migration 7 to 8 and backup restore.
- Browser: full existing suites plus PR passed using Edge and the disposable database/server runner.
  PR covers empty/load-error/retry, multi-material form, order preselection, committed request
  retried after page reload, viewer/operator/admin access, stale decision from another tab,
  approved filter, cancellation, escaping, 320/390/768px and 390px at 200% text scaling.
- Client checks, JavaScript syntax, pip check and git diff --check passed.
- Independently reviewed schema/models/store/API/UI/retry and migration. No actionable findings.
  Reviewer ran the four PR tests present at review time; the final full run also includes the
  subsequently added maximum estimate/decision validation/revocation test.
- Inspected desktop detail and mobile form screenshots. Content wraps within dialog; long forms
  scroll vertically. Existing application colors, labels, focus and form controls are reused.

## Commands (from worktree)

```powershell
$env:PYTHONPATH=(Get-Location).Path
& '../../.venv/Scripts/python.exe' -m unittest discover -s tests -q
node tests/test_client.mjs
node --check beeloft/static/app.mjs
& '../../.venv/Scripts/python.exe' -m pip check
git diff --check
& '../../.venv/Scripts/python.exe' tests/run_browser.py --node PATH_TO_NODE --playwright-module PATH_TO_PLAYWRIGHT --channel msedge
```

The shared installed FastAPI/Pydantic stack sometimes emits an UnsupportedFieldAttributeWarning
for query parameter aliases in concurrent app-construction tests; the suite passes. The same
warning was observed on the preceding main-branch verification, before this increment.

## Product limits

All estimates need admin approval regardless of value; admin self-approval supports the current
single-operator workflow. No value-threshold routing, PO, supplier quote, incoming stock promise,
automatic shortage-to-PR conversion or automated duplicate-demand detection. Requests with distinct
references may overlap demand, so operators review active PRs before submitting another.
