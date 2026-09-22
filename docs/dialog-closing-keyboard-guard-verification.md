# Dialog closing interaction guard verification

Date: 22 September 2026. Repository: `wenn-id/beeloftone`.
Baseline: `7a76b415e6750fc06a80a050fe801ec3a5c46613`, latest `origin/main` after fetch.
Branch: `fix/dialog-closing-interaction-guard`.

The originating finding is section 6 of the Apple-27 A0 audit, stored in local
commit `f559d91083e310ab30a98f7251fa8d6160ee9363` on
`docs/apple27-native-parity-a0` (`docs/apple27-native-parity-audit.md`). That
documentation branch is not merged and is not an ancestor of this fix. Inspect
it with `git show f559d91083e310ab30a98f7251fa8d6160ee9363:docs/apple27-native-parity-audit.md`.
Apple-27 A1 is not started.

## Reproduction and root cause

The new [browser regression](../tests/browser_dialog_closing.cjs) opens a valid
New Order form, focuses `#save-form`, presses Escape, records the still-open
closing dialog, then immediately presses Enter using normal browser keyboard
input. POST interception responds with 422 before server dispatch. The test
asserts zero attempted requests and checks the exact order reference in the
synthetic database. It failed against the baseline before the product fix.

| Observation | Baseline | Fixed |
|---|---|---|
| Focus before Escape | `save-form` | `save-form` |
| Native dialog during exit | `open: true` | `open: true` |
| Closing classes | `motion-exit is-closing` | `motion-exit is-closing` |
| Dialog inert | false | true |
| Focus during exit | `save-form`, inside dialog | outside dialog |
| Attempted POST after Escape/Enter | **1: regression fails** | **0: regression passes** |
| Persisted probe orders | 0 (request intercepted) | 0 |

`closeDialog()` and the native `cancel` listener accept dismissal after checking
`modalBusy` and `unresolved`, increment `dialogVersion`, and start
`closeDialogAnimated()`. Native `dialog.close()` runs after the opacity transition
or its bounded fallback timer. During that window the baseline dialog retained
an active form and focused submit button. CSS `pointer-events: none` suppressed
pointer hit testing but did not disable keyboard activation. `formDialog()`
checked `modalBusy` before dispatch; its version check after the response stopped
late painting, not a new submission. No server mutation was allowed during the
failing reproduction.

## Centralized lifecycle change

The [global dialog coordinator](../beeloft/static/app.mjs) sets `dialog.inert = true`
immediately after an accepted close reaches `closeDialogAnimated()`, before
either the animated or reduced-motion path. Native inert semantics disable user
focus and activation across the entire dialog, including secondary buttons.
A modal dialog must be explicitly inerted on itself because `showModal()` dialogs
escape ancestor inertness. See [MDN's inert reference](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Global_attributes/inert).

One capture-phase `submit` listener prevents default and stops propagation while
the dialog is inert. This covers scripted `requestSubmit()`, which can still
dispatch a submit event on inert content. The listener uses the same semantic
state and runs before business submit handlers; it does nothing on an interactive
dialog. No individual form handler, payload or transaction guard changes.

`resetDialogMotionState()` clears inert together with the existing exit timer,
listener and classes. Native `close` still owns cleanup and existing focus
restoration. `openDialog()` also resets the state before `showModal()` when the
dialog is closed, so a close/reopen in one task need not wait for the queued
native close event. The opacity transition, fallback duration, `dialogVersion`,
busy/unresolved checks, native confirmed-write close, `navigateFromDialog()` and
session teardown retain their existing paths.

## Regression coverage

The new module is registered in the normal browser runner. It exercises:

- Escape/Enter with the before/after evidence above.
- Close button/Enter, Escape/Space, rapid pointer clicks on submit and the
  secondary Remove SKU button, Tab and Shift+Tab during exit. No form action or
  mutation is dispatched.
- Attempts to focus each dialog control and scripted `requestSubmit()` during
  exit. Focus cannot re-enter and business submit handlers do not run.
- Repeated close/reopen cycles, opening a different SKU form after cleanup,
  and restoring focus to the original New Order trigger after native close.
- Reduced motion: immediate native close, then Enter emits no write. Enter may
  activate the restored New Order trigger, opening a fresh empty form normally.
- A real intentional write from a reopened form: hold its POST, press Escape,
  verify the busy dialog remains interactive and is not closing, release the
  request, and verify one synthetic order commits and closes normally.

The existing [dialog-motion module](../tests/browser_motion_dialogs.cjs) is retained
and gains an assertion that refused unresolved-transaction dismissal does not
inert recovery controls. Its entry/exit transition events, Cancel/Escape,
interrupted entry, direct native close, repeated cycles, stale-response guard,
reduced motion, print, dark mode and 320px/200% checks remain intact. Existing
navigation tests cover `navigateFromDialog()` behavior and mobile recovery's
return focus to `#menu-toggle`; session modules cover teardown and actor recovery.

## Verification commands and environment

All runtime checks use disposable synthetic databases. Python is 3.12.14 with
the repository's pinned `requirements.txt` in the isolated environment created
for A0, `%TEMP%/beeloft-a0-audit/venv`. `PYTHONPATH` is the repository root.
Node is 24.18.0; bundled Playwright is 1.62.1 with Chromium 151.0.7922.34.

| Command | Result |
|---|---|
| `python -m unittest discover -s tests -v` | PASS: 574 tests in 1081.291s, exit 0 |
| `python -m pip check` | PASS |
| `python -m compileall -q beeloft` | PASS |
| `node --check beeloft/static/app.mjs` | PASS |
| `node --check beeloft/static/client.mjs` | PASS |
| `node --check tests/browser_dialog_closing.cjs` | PASS |
| `node tests/test_client.mjs` | PASS |
| `python scripts/regenerate_openapi.py` | PASS; 221 paths / 85 schemas, version-only diff |
| Disposable `Store` initialization and `PRAGMA user_version` query | PASS: 55 |
| `python tests/run_browser.py --channel chromium --playwright-module <bundled-path>` with `BEELOFT_QA_ONLY=dialog` | PASS: existing dialog motion plus focused closing regression |
| Same browser command with `BEELOFT_QA_ONLY` unset | PASS full suite, exit 0, including the final regression module and no-JS-errors assertion |

The module argument resolves
`C:/Users/acer/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright`;
plain default lookup cannot resolve Playwright in this checkout. The original
repository venv has stale dependencies, and default `python` is unsupported
3.11.9, so neither is used for acceptance. CI uses Node 22 / Playwright 1.63.0;
these are local results, not a CI claim. Safari, Firefox, real mobile browsers
and screen-reader speech were not exercised. Logs are in the OS temp audit
directory: `dialog-before-final.log`, `dialog-focused.log`,
`dialog-unittest.log`, and `dialog-browser-full.log`.

## Version and scope

Application version advances **0.97.0 → 0.98.0**, following the repository's
minor-version convention for frontend safety fixes (for example #64 and #67).
`pyproject.toml`, README, FastAPI version metadata and regenerated OpenAPI agree.
API paths and schemas are unchanged; `api.py` changes only release metadata.

**PRAGMA user_version remains 55. No migration added.** No API client, endpoint,
payload, idempotency key, actor binding, auth, validation, domain calculation or
database behavior changes. No new dependency, visual redesign or A1 work.
