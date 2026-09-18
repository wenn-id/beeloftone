# Workspace Navigation Architecture

Program: Beeloft One — Workspace Navigation Architecture Roadmap, Version 1.0
Milestone: A (Workspace navigation foundation)
Baseline: `main` @ `8e972773b7a5572758564dc4fd23e5e4adba76c4`
Branch: `refactor/workspace-navigation-foundation`
Date: 18 September 2026

This document is the contract for how primary navigation activates a workspace
page. It was created in Milestone A and must be updated whenever the contract
changes. The current-state evidence behind this contract lives in
`docs/workspace-navigation-inventory.md`.

## 1. Core rule

A primary sidebar destination establishes context in the main workspace. A modal
is reserved for one focused secondary task: create, edit, review, confirmation,
or record detail.

No primary sidebar click may use the global `<dialog id="dialog">` as its main
screen. A dialog answers one question — *what record is being created, edited,
reviewed, confirmed, scanned, or inspected* — and never hosts an entire roster,
report, queue, master-data surface, or dashboard.

## 2. Activation path

Every workspace destination resolves through one helper, `activateWorkspace()` in
`beeloft/static/app.mjs`. It owns exactly five responsibilities:

1. Hide every other section in `workspace-main`, bumping each hidden section's
   feature-local request counter on the way out.
2. Reveal the target section.
3. Record the active `view` name that the target renderer's async guards check.
4. Move `aria-current="page"` to the selected sidebar item.
5. Close the mobile drawer and settle keyboard focus.

Callers keep ownership of their own data load and rendering. The helper never
fetches, renders, or holds business state.

```js
activateWorkspace('board-home');                 // primary sidebar destination
activateWorkspace('board-home', 'detail-view');  // internal section sharing a sidebar item
```

Two tables coordinate the lookup and are the only place navigation state is
declared:

| Table | Purpose |
|---|---|
| `workspaceDestinations` | Sidebar item id → owned section. Navigation coordination only; no business logic. |
| `workspaceSections` | Every `workspace-main` section, its `view` name, and its `invalidate()` counter bump. |

`invalidate()` is the stale-response contract: before a section is hidden, its
feature-local request counter is bumped so a late response cannot repaint the
newly active page. This deliberately reuses the proven per-feature counters
(`boardRequest`, `detailRequest`, `activityRequest`, `commandCenterRequest`,
`materialsRequest`) rather than a global cancellation rewrite.

Destinations integrated in Milestone A: `command-center`, `board-home`,
`materials`, `activity`, plus the internal `detail-view` section reached from the
board. Later milestones extend the two tables; they do not add parallel
activation paths.

## 3. Navigation foundation contract

| Checkpoint | Requirement | Enforced by |
|---|---|---|
| Single active page | Exactly one `workspace-main` section is visible after navigation. | `activateWorkspace()` hides all others |
| Active navigation | The matching sidebar item receives `aria-current="page"`. | `activeNavigation()` |
| Mobile drawer | Drawer closes after selecting a destination; focus moves to the new page heading. | `activateWorkspace()` + sidebar delegation |
| Async safety | A late response from the previous page cannot repaint the current page. | `invalidate()` + per-renderer `epoch`/counter checks |
| Transaction safety | Navigation does not silently discard unresolved writes or pending retry state. | `guardPending()`, `modalBusy`, `unresolved`, `sessionStorage` drafts |
| Dialog discipline | Primary navigation never opens the global dialog as the main screen. | Architecture regression `browser_navigation_foundation.cjs` |

### 3.1 Mobile drawer and focus

On narrow viewports the sidebar is a drawer (`body.nav-open`). `activateWorkspace()`
closes it and, when no focused secondary dialog is open, moves focus to the newly
visible section's `h1` (tabindex set to `-1` so the heading is programmatically
focusable without joining the tab order). When a focused secondary dialog is
open, focus is remembered on the menu toggle via `dialogReturnFocus` instead.

The sidebar click delegation defers to the helper: page destinations have already
closed the drawer and moved focus before the delegation's microtask runs, so the
delegation only closes the drawer and records focus for legacy dialog
destinations that do not route through the helper yet. Desktop never sets
`nav-open`, so desktop navigation does not steal focus.

### 3.2 What Milestone A deliberately did not change

- Business presentation of Command Center, Production, Materials, and Activity.
- Per-feature request counters, `epoch`, and `dialogVersion`.
- `guardPending()`, pending-draft recovery in `sessionStorage`, idempotency keys,
  `X-Beeloft-Actor` binding, and cross-account session safety.
- Any `*Dialog()` renderer. Legacy modal destinations are migrated in later
  milestones; until then they keep working exactly as before.

## 4. Page state contract

Every workspace renderer — existing and future — must distinguish these states
and never show two at once:

| State | Requirement |
|---|---|
| LOADING | Explicit loading state; no stale empty/error content shown alongside. |
| EMPTY | Successful request with no data. |
| FILTER EMPTY | Data exists generally, but current filters match nothing. |
| ERROR | Request failure with a retry path where the previous feature had retry. |
| AUTH FAILURE | Preserve the existing session-expiry flow (`fail()` → 401 logout). |
| READ ONLY | Page remains usable; mutations follow existing role restrictions. |

Opening or revisiting a page must never trigger a mutation.

## 5. Dialog contract

A dialog remains the correct shell for a focused secondary task: Tambah karyawan,
Edit attendance, approval confirmation, run detail, audit-event detail, create PR,
edit BOM, production-order mutation forms, label/print confirmation, and record
detail.

A dialog must not be the entire People roster, Analytics report, Integration
dashboard, Approval inbox, or Master SKU workspace. Those become pages in
Milestones B–F.

## 6. Adding a destination (later milestones)

1. Add the `<section id="<name>-view">` to `workspace-main` in `index.html`.
2. Extend `workspaceDestinations` with the sidebar item id and the section id.
3. Extend `workspaceSections` with the section id, its `view` name, and an
   `invalidate()` that bumps the feature-local counter the new renderer guards on.
4. Wire the sidebar item's click handler to call `activateWorkspace('<nav-id>')`
   and then load data — never to `openDialog()` as the primary experience.
5. Record the destination in `docs/workspace-navigation-inventory.md` and move its
   migration status from `LEGACY_DIALOG` to `MIGRATED_PAGE`.

## 7. Regression coverage

Milestone A adds `tests/browser_navigation_foundation.cjs`, registered in
`tests/browser_smoke.cjs`. It proves: exactly one visible page per navigation,
`aria-current` follows the destination, the drawer closes with heading focus on
mobile, repeated navigation does not duplicate handlers or content, a delayed
response cannot repaint a later destination, no primary page opens the global
dialog, and 320px at 200% text does not overflow.

Pending-transaction and exact-once coverage remains in `browser_smoke.cjs`
(lost-response reload/retry, `sessionStorage` draft survival, idempotency key
retention) and is unchanged by this milestone.
