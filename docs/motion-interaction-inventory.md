# Motion & Interaction Inventory

Program: Beeloft One — Motion & Interaction Specification, Version 1.0
Current milestone: M0 (motion audit and instrumentation)
Baseline: `main` @ `0efb1115b099ae299a27d508a043ba550eb779d7` (PR #17)
Branch: `ui/motion-audit-m0`
Date: 19 September 2026

This document is the M0 artefact required by §15 of the motion specification. It
records the current motion and lifecycle surface so M1-M6 can be implemented
against evidence rather than labels. It is an audit: no visible motion was added
and no product code was changed.

Method: every timing, state class, close path and focus transition below was read
directly from the baseline commit — `beeloft/static/style.css`,
`beeloft/static/index.html`, `beeloft/static/app.mjs`, `beeloft/static/client.mjs`,
and `tests/`. Counts are exact at this SHA. Line numbers are this revision's, and
will drift with later milestones; the selectors, ids and function names are the
stable identifiers.

## 1. Executive finding

The product is already almost motionless. The entire baseline contains **three CSS
transition declarations (two active transitions and one reduced-motion suppressor)
and no keyframes at all**. Everything the specification asks for in M1-M6 is
therefore net-new construction, not replacement of an existing animation system.
The main risks are not "too much existing motion"; they are the six structural gaps
in §6 that a naive motion layer would trip over.

The specification's north star — "if a user notices a lot of animation, the system
is probably over-animated" — is currently satisfied by default. Every milestone
adds motion budget that does not exist today.

## 2. Complete transition and animation inventory (`style.css`)

### 2.1 Every motion declaration in the file

| Line | Selector | Declaration | Duration / curve | Purpose |
|---|---|---|---|---|
| `style.css:183` | `.nav-caret` | `transition:transform .15s ease` | 150ms, `ease` | Analytics disclosure caret rotates between open and closed |
| `style.css:505` | `@media(prefers-reduced-motion:reduce) *` | `transition:none!important` | N/A | Suppresses every transition when reduced motion is requested |
| `style.css:507` | `button,.nav-item,.nav-summary` | `transition:background-color .12s ease,border-color .12s ease,color .12s ease` | 120ms, `ease` | Hover and selected tint on every control and nav row |

That is the complete list. It includes two active colour-or-rotation transitions,
both under 200ms and neither moving layout, plus the reduced-motion suppressor.

### 2.2 Motion-adjacent rules that are not transitions

| Line | Rule | Role |
|---|---|---|
| `style.css:99` | `button:active{transform:none}` | Explicit press suppressor. Buttons currently have **no** press transform; M1 must add it without colliding with this rule. |
| `style.css:184` | `.nav-collapse:not([open]) .nav-caret{transform:rotate(0)}` | The disclosure's settled state. The `-180deg` resting value is at `style.css:183`. |
| `style.css:80` | `[hidden]{display:none!important}` | Single writer for all hidden state. Motion cannot use a second hiding mechanism without breaking this contract. |
| `style.css:452-453` | `.app-sidebar{...display:none...}` / `.nav-open .app-sidebar{display:flex}` | Mobile drawer is **display-driven**, so the closed drawer is already absent from tab order (see §6.3). |
| `style.css:221-222` | `.state{...}` | Loading/empty/error surface. Static; no pulse, no shimmer, no skeleton animation. |
| `style.css:428` | `.notice{border-radius:12px;box-shadow:var(--shadow-lg)}` | Toast surface. No transition today. |

### 2.3 The current reduced-motion contract

```css
/* style.css:505-508 */
@media(prefers-reduced-motion:reduce){*{transition:none!important}}
@media(prefers-reduced-motion:no-preference){
  button,.nav-item,.nav-summary{transition:background-color .12s ease,border-color .12s ease,color .12s ease}
}
```

Two properties hold, and both must survive every milestone:

1. The `no-preference` block is the **only** place routine control transitions are
   declared. Everything else is inert by construction.
2. `reduce` is a blanket suppressor with `!important`. It is sufficient today
   because the only motion is colour and caret rotation — both non-semantic.

It is **not** sufficient for M2-M4. The specification's §11 contract disables
`animation`, `transition` and `transform` on explicit motion classes, and requires
that essential state feedback remains visible without movement. A `*{transition:none}`
catch-all would also strip any future focus or busy indicator that depends on a
transition to appear at all.

### 2.4 Verified absent (negative evidence)

At this SHA the following do not exist anywhere in the product:

| Absent | Verification |
|---|---|
| `@keyframes` | No match in `style.css`, `index.html` or `app.mjs`. |
| `animation:` property | No match. No entry, exit or looping animation exists. |
| `will-change` | No match. |
| `backdrop-filter` / `blur()` | No match. No backdrop blur anywhere, including the dialog. |
| `filter:` transitions | No match. |
| `scroll-behavior` | No match; scrolling is instant. |
| JS-authored style mutation | No `style.transition`, `style.transform`, `style.opacity` or `style.animation` assignment in `app.mjs`. |
| `requestAnimationFrame` | No match in `app.mjs`. There is no frame loop of any kind. |
| JS reduced-motion branch | No `matchMedia('prefers-reduced-motion')` in `app.mjs` or `client.mjs`. |

The last row is the most consequential gap in the audit: **reduced motion is a
CSS-only concern today**. Any JS that must skip motion — the M3 animated close
helper, the M2 entry scheduler — has no existing preference check to reuse and
must introduce one.

## 3. Lifecycle inventory

### 3.1 Section visibility — the primary page lifecycle

`activateWorkspace(navId, sectionId)` at `app.mjs:126-142` is the single writer
for workspace section visibility. It owns five responsibilities:

| Line | Action |
|---|---|
| `app.mjs:127-131` | Iterate `workspaceSections`; for every non-target section call `invalidate()` then set `.hidden = true` |
| `app.mjs:133` | Reveal the target: `$(sectionId).hidden = false` |
| `app.mjs:134` | Record the active `view` name the renderers guard on |
| `app.mjs:135` | `activeNavigation(navId)` moves `aria-current="page"` |
| `app.mjs:136-140` | Close the mobile drawer; if a dialog is open record `dialogReturnFocus=$('menu-toggle')`, otherwise focus the section `h1` |

Coordination tables, and the only place navigation state is declared:

- `workspaceDestinations` (`app.mjs:69`) — 27 sidebar ids mapped to 17 sections.
- `workspaceSections` (`app.mjs:103-122`) — 17 sections, each with its `view` name
  and an `invalidate()` that bumps a feature-local request counter.

There is **no** entry, exit or cross-fade today: `hidden` flips and the target
appears on the same frame. This is the exact seam M2 attaches to, and the reason
the specification insists on wrapping the existing lifecycle rather than adding a
router.

### 3.2 Dialog lifecycle

| Element | Location | Behaviour |
|---|---|---|
| Single dialog shell | `index.html` (`<dialog id="dialog">`) | One global native dialog for every focused secondary task. |
| `openDialog(title, content)` | `app.mjs:742-750` | Closes the drawer and records return focus (`744-745`), bumps `dialogVersion` (`747`), writes title/content (`748`), then the **only** `showModal()` call site in the product (`749`). |
| `closeDialog()` | `app.mjs:830-833` | The one guarded close. Refuses while `modalBusy` or `unresolved`, notifying the operator instead (`831`). |
| Close button | `app.mjs:834` | `$('close-dialog').onclick = closeDialog`. |
| Escape / cancel | `app.mjs:835` | `cancel` listener re-implements the busy guard inline and calls `event.preventDefault()` — it does **not** route through `closeDialog()`. |
| Focus restore | `app.mjs:836` | `close` listener returns focus to `dialogReturnFocus` if it is still visible. This is the only focus restoration path. |
| Generation counter | `app.mjs:20` | `dialogVersion`, bumped by `openDialog()` and `clearWorkspace()`; loaders compare it before painting. |
| Busy flags | `app.mjs:19` | `modalBusy` (write in flight) and `unresolved` (write unconfirmed). |

### 3.3 Mobile drawer

| Element | Location | Behaviour |
|---|---|---|
| `sidebar(open, restoreFocus)` | `app.mjs:54-58` | Toggles `body.nav-open` (`55`) and `#menu-toggle[aria-expanded]` (`56`); restores focus to the toggle on close (`57`). |
| Toggle | `app.mjs:59` | `$('menu-toggle').onclick`. |
| Escape | `app.mjs:60` | Document-level keydown closes the drawer and restores focus. |
| Close on navigation | `app.mjs:136-140` | `activateWorkspace()` closes it and sets heading focus. |
| Close on dialog open | `app.mjs:744-747` | `openDialog()` closes it and defers focus to `dialogReturnFocus`. |
| Visual state | `style.css:452-453` | `display:none` closed → `display:flex` open, inside the touch-width media query. |

`inert` appears at exactly three sites today — set on `login-view` at
`app.mjs:288` and cleared at `app.mjs:324` and `app.mjs:375` during
authentication. The sidebar is **not** inert.

### 3.4 Notice (toast)

| Element | Location | Behaviour |
|---|---|---|
| `notify(message)` | `app.mjs:184-187` | Unhides `#notice` (`185`) and (re)arms `noticeTimer` for **6000ms** (`186`). |
| Timer handle | `app.mjs:22` | `let noticeTimer;` |
| Markup | `index.html:315` | `<div id="notice" class="notice" role="status" hidden>` |
| Session reset | `app.mjs:261` | `clearWorkspace()` hides the notice. |
| Presentation | `style.css:428` | Fixed bottom-right surface; no transition. |

Enter and exit are instant. The 6000ms semantic timer and the `role="status"`
region are the contract M4 must preserve; only presentation may animate.

### 3.5 Loading, busy and status regions

| Element | Location | Behaviour |
|---|---|---|
| `message(id, text, error)` | `app.mjs:188-191` | Writes a status region: `hidden = !text` (`189`) and toggles `.error` (`190`). Called **151** times. |
| Loading placeholders | `class="state"` markup | 250 occurrences in `app.mjs`, 12 in `index.html`. Static text ("Memuat …"), no skeleton or pulse. |
| `clearDialogLoading()` | `app.mjs:199-201` | Removes leftover "Memuat/Menghitung/Menggabungkan" placeholders from `#dialog-content` on first-load failure or empty result. |
| `clearPageLoading(id)` | `app.mjs:206-209` | Same, for a workspace page container. |
| `aria-busy` | 3 set / 5 clear | `main` during login (`288`, `324`, `375`); `#command-center-summary` (`532`, `563`, `647`); `#summary` (`657`, `675`). |
| `progress` | `app.mjs:687` | One native `<progress>` on the production board, value already known. |

Initial load is a text placeholder; refresh is a full repaint. The specification's
§8 distinction (preserve content during refresh, `aria-busy` + optional dimming)
does not exist yet, and no `is-refreshing` equivalent is present.

### 3.6 `hidden` writers

`app.mjs` contains **121** `.hidden=` assignments across 28 distinct ids plus the
loop-driven section toggle in `activateWorkspace()`. `index.html` carries 79 lines
containing `hidden`. They group into five lifecycles:

| Lifecycle | Representative targets | Owner |
|---|---|---|
| Section visibility | every `workspaceSections` id | `activateWorkspace()` (`130`, `133`) |
| Status regions | 151 `message()` calls | `message()` (`189`) |
| Pagination / load-more | `activity-more`, `material-trace-more`, per-dialog `Muat … sebelumnya` buttons | each cursor loader, gated on `rows.length < N` |
| Session and identity | `workspace`, `login-view`, `menu-toggle`, `logout`, `session-warning`, `session-retry`, `sso-login`, `sso-separator` | login / `clearWorkspace()` (`app.mjs:253-262`) |
| Role and state gating | `new-order`, `new-product`, `new-employee`, `new-purchase-request`, `new-marketing-budget`, `receive-material`, `reauth`, `ai-reauth`, `backup`, `audit-trail` | role checks at load time |

Only the first two are motion-relevant. The rest must keep flipping silently;
animating a role gate or an identity element would delay state the operator needs
immediately.

### 3.7 Theme

`theme(value)` (`app.mjs:46-50`) sets `document.documentElement.dataset.theme`,
updates the toggle label and persists to `localStorage`. Initial application runs
at `app.mjs:51`, before the app renders; the toggle handler is `app.mjs:52`.

Colour change is instant and global: there is no transition class, no crossfade,
and no per-surface staging. The specification's §10 recommendation (a short-lived
class on selected surfaces, never on first paint) is unimplemented, and the
current behaviour is exactly the "do not keep global colour transitions active"
default it asks to preserve.

## 4. Dialog close-path inventory (input for M3)

Every direct `$('dialog').close()` call site at this SHA, with its guard status.
This is the inventory the specification requires before any animated close helper
is designed.

| Line | Owner | Purpose | Guarded by `modalBusy`/`unresolved`? |
|---|---|---|---|
| `app.mjs:147` | `navigateFromDialog(show)` | Close the focused dialog before activating its owning page | No — navigation, not a close decision. Verified safe: callers run after a confirmed read or write. |
| `app.mjs:256` | `clearWorkspace()` | Session reset: discard dialog, drafts and identity together | No — intentional unconditional teardown. Must stay immediate. |
| `app.mjs:832` | `closeDialog()` | The operator's explicit close (X button) | **Yes** — the only guarded path. |
| `app.mjs:877` | `formDialog` success chain | Close after a **confirmed** write | No — the write already settled, so `modalBusy`/`unresolved` are cleared immediately before. |
| `app.mjs:1326` | `#production-request-order` | Close dialog, then `openDetail()` | No — preceded by `guardPending()`. |
| `app.mjs:1600` | `#cutting-order` | Same | No — preceded by `guardPending()`. |
| `app.mjs:1729` | `#bundle-order` | Same | No — preceded by `guardPending()`. |
| `app.mjs:1806` | `#sewing-order` | Same | No — preceded by `guardPending()`. |
| `app.mjs:1867` | `#finishing-order` | Same | No — preceded by `guardPending()`. |
| `app.mjs:1932` | `#final-qc-order` | Same | No — preceded by `guardPending()`. |
| `app.mjs:2002` | `#rework-completion-order` | Same | No — preceded by `guardPending()`. |
| `app.mjs:2091` | `#finished-goods-order` | Same | No — preceded by `guardPending()`. |
| `app.mjs:3168` | `[data-ai-history]` | Close the investigation dialog, activate `ai-view`, scroll to history | No — read-only context switch. |
| `app.mjs:4802` | `materialBatchScanDialog` success | Replace the scan dialog with the history dialog | No — `modalBusy` just cleared on the confirmed scan. |

Two structural facts follow, and M3 must handle both:

1. **Thirteen of fourteen close sites bypass `closeDialog()`.** Only the X button
   goes through the guarded helper. The other thirteen are lifecycle transitions
   whose guard is either already satisfied (post-write, post-`guardPending()`) or
   deliberately absent (session reset).
2. **Escape is a fifteenth, separate path.** The `cancel` listener
   (`app.mjs:835`) duplicates the busy check inline instead of calling
   `closeDialog()`. The specification requires cancel/Escape to route through the
   same allowed-close decision; today there are two copies of that decision that
   can drift.

Any animated close must also respect the `close` listener at `app.mjs:836`, which
is the single focus-restoration hook and only runs on the native `close` event.

## 5. Existing tests with timing or focus assumptions

The full suite is 509 unit tests plus the browser modules. The following have
assumptions that a motion layer can invalidate.

### 5.1 Timing assumptions

| File | Sites | Assumption |
|---|---|---|
| `tests/browser_navigation_foundation.cjs` | `175`, `204`, `234`, `281` | After releasing a held stale response, `waitForTimeout(150)` is enough for the aborted response to land and be discarded. These assert **absence** of a repaint, so an added entry animation does not break them — but any motion that delays the *discard* past 150ms would. |
| `tests/browser_smoke.cjs` | `145`, `184` | `waitForTimeout(100)` after a delayed/failed products response, asserting the pending draft survives and search stays disabled. |
| `tests/browser_workspace_utilities.cjs` | `48`, `102` | `waitForTimeout(150)` after a stale scan / stale backup response, asserting no repaint and no download. |

None of these assert animation timestamps. They are stale-response races, and the
specification's §13 test style ("assert semantic outcomes and transition
lifecycle, not exact pixel animation curves") already matches how they are written.

### 5.2 Focus assumptions

| File | Site | Assertion |
|---|---|---|
| `tests/browser_navigation_foundation.cjs` | `296-299` | After mobile drawer navigation, `document.activeElement === section.querySelector('h1')`. |
| `tests/browser_navigation_foundation.cjs` | `377-379` | Same heading-focus contract for every role, width and theme. |
| `tests/browser_navigation_foundation.cjs` | `427` | After pending-write recovery, `document.activeElement.id === 'menu-toggle'`. |
| `tests/browser_navigation_foundation.cjs` | `373` | `window.navigationModalOpens === 0` — no `showModal()` during primary navigation. |

The heading-focus assertions are the ones most exposed to M2: the specification
requires "do not move focus because of animation", and any entry animation that
awaits a frame before revealing the target must still land focus on the heading.

### 5.3 Dialog state assumptions (M3 exposure)

| File | Site | Assertion | Risk |
|---|---|---|---|
| `tests/browser_logout_failure.cjs` | `212` | Dialog **stays open** while a write is unresolved | An animated close must never fire on this path. |
| `tests/browser_logout_failure.cjs` | `264` | Dialog closed after account switch (`clearWorkspace()`) | Must remain immediate, not animated. |
| `tests/browser_navigation_foundation.cjs` | `422` | `waitForFunction(() => !dialog.open)` after retry | Tolerant of a ≤160ms exit, but only if the close finally happens. |
| `tests/browser_shared_ui.cjs` | `124` | `dialog[open]` waitFor | Tolerant of a delayed open. |
| `tests/browser_ai_investigation_logout.cjs` | `105`, `142` | No dialog remains open after session events | Session teardown must not be animated. |
| `tests/browser_management_command_center.cjs` | `154` | Integration health is not a dialog | Unaffected, listed for completeness. |

### 5.4 Reduced-motion coverage

Exactly one browser module emulates the preference:
`tests/browser_production_premium_ui.cjs:47` sets `reducedMotion:'reduce'`, runs a
layout sweep, and restores `no-preference` at `:207`. There is **no** existing test
that exercises a motion path under reduced motion, because there are no motion
paths to exercise. Every milestone that adds one must add its reduced-motion
assertion alongside it.

### 5.5 Diagnostic instrumentation precedent

`tests/browser_navigation_foundation.cjs:340-343, 389-391` patches
`HTMLDialogElement.prototype.showModal` inside the page to count calls, then
restores it. This is the established pattern for asserting that a lifecycle step
did **not** happen, and it is the model M0's "diagnostics if required" clause
points at. Counters installed this way are test-local and are not shipped.

## 6. Gaps the motion program must close

Recorded here because each one is a prerequisite for a later milestone, and none
is visible from the specification alone.

### 6.1 No JS reduced-motion check

`matchMedia('prefers-reduced-motion')` appears nowhere in the JavaScript. M2's
"skip transform/opacity motion and reveal immediately" and M3's "on reduced motion,
call `dialog.close()` immediately" both require a JS branch. **M1 owns introducing
it**, together with the token set, so later milestones share one implementation.

### 6.2 The reduced-motion catch-all is too blunt for the new patterns

`style.css:505` strips **all** transitions globally with `!important`. Once entry
motion, dialog motion and toast motion exist, the specification's §11 contract
requires motion classes to be disabled while essential state feedback stays
visible. The catch-all must be refined into the explicit class list from §11 —
without weakening the guarantee that reduced-motion users see every state change.

### 6.3 The drawer is display-driven, which changes the M2 approach

`style.css:452-453` hides the closed drawer with `display:none`, so it is already
non-interactive and non-tabbable — the outcome the specification's inert
requirement is protecting. That mechanism is incompatible with a transform-based
slide: the drawer cannot animate from `display:none`. M2 must therefore choose
between:

- keeping `display`-driven visibility (safest for accessibility, no drawer slide), or
- converting to off-canvas `transform` **and** adding `inert` (or an equivalent
  proven mechanism) toggled with `nav-open`, before any focus can enter it.

The specification explicitly requires the second option's safety property if the
first is abandoned. `inert` currently exists only on `login-view`.

### 6.4 Escape duplicates the close guard

`app.mjs:831` (X button) and `app.mjs:835` (Escape) hold two copies of the same
`modalBusy || unresolved` decision. M3's contract — "Cancel/Escape must route
through the same allowed-close decision, not bypass it" — cannot be satisfied
while both exist. Unifying them is M3 work, not M0 work, because the recovery and
`preventDefault` semantics must be preserved exactly.

### 6.5 No refresh-with-data concept exists

Every reload currently repaints the container. There is no state that distinguishes
"initial load" from "refresh with existing data", so M4's `is-refreshing`
treatment, `aria-busy` + dimming, and empty-state crossfade are all new structure
over the 151 `message()` call sites and the 250 `.state` placeholders.

### 6.6 Tokens have no insertion point yet

`style.css:40-56` is the theme-invariant `:root` block (`--sidebar-w`, `--r-card`,
`--shadow-*`); `style.css:57-69` is the dark override and re-declares only what
differs by theme. Motion and easing tokens are theme-invariant, so **M1 adds them
once to `style.css:40-56`** and does not duplicate them in the dark block. The
file's own header comment (`style.css:1-4`) states that foundation tokens live in
one place; motion tokens must follow that rule.

## 7. M0 verification

| Check | Result |
|---|---|
| Visible motion added | None. This document is the only change. |
| Product code changed | None — `style.css`, `index.html`, `app.mjs`, `client.mjs` untouched. |
| Diagnostic instrumentation added | None required; findings came from direct inspection. |
| `python -m unittest discover -s tests -v` | PASS — 509 tests, no failures. |
| `python -m compileall -q beeloft` | PASS. |
| `node --check beeloft/static/app.mjs` / `client.mjs` | PASS. |
| `node tests/test_client.mjs` | PASS. |
| `python tests/run_browser.py --channel chromium` | PASS — full suite, no JavaScript errors. |

Two of the specification's standard commands could not run in this environment and
are recorded as gaps rather than passes:

- `python -m pip check` — this checkout's virtual environment was created without
  `pip`, so the command is unavailable. CI's Core job runs it on the PR.
- `python -m build` — the `build` frontend is not installed here, and packaging is
  not currently a CI gate (`.github/workflows/ci.yml` has Core and Browser jobs
  only). M0 changes no packaged asset, so nothing is at risk; later milestones that
  touch `style.css` or `app.mjs` must confirm the wheel contains the exact static
  assets used in tests before claiming done.

Local runs used Playwright 1.63.0 with Chromium 1243, matching the CI pin. They are
supporting evidence only: the specification's gate is CI on the published PR HEAD,
and the PR body records those results separately.

Per the specification's §20 execution protocol and §15 hard stop, M1-M6 remain
unimplemented until M0 is reviewed and merged.

## 8. M1 delta — foundation and tactile controls

Baseline: `191de6d28ead2a8039888c4df3c97f44d422ef03` (M0 merged as PR #18).
Branch: `ui/motion-foundation-tactile-controls`.

M1 touches presentation only. No endpoint, schema, calculation, role rule,
idempotency or focus contract changed, and no page transition, drawer motion or
dialog exit was added — those are M2 and M3.

| Change | Where | Intention |
|---|---|---|
| Nine motion and easing tokens | theme-invariant `:root`, declared once | The specification's canonical set becomes the single source for timing and easing. Declared in full even though M1 consumes four of them (`--motion-instant`, `--motion-fast`, `--motion-base`, `--ease-standard`), so M2-M4 inherit the same vocabulary instead of inventing local values. |
| Two ad-hoc transitions normalised | `.nav-caret`; `button,.nav-item,.nav-summary` | `.12s ease` → `--motion-fast` + `--ease-standard` (duration unchanged). The caret's `.15s ease` → `--motion-base` + `--ease-standard`; 180ms sits inside the 150–180ms band the specification allows this control, and it is the nearest token to the old value. |
| Press feedback | `button:active:not(:disabled){scale:.985}` inside the `no-preference` query | The tactile layer the milestone exists for, applied to every button — including the sidebar rows, the approval CTA and the dialog's close control, which are all `<button>` elements. |
| Focus polish | `:focus-visible` | The ring no longer forces `border-radius:var(--r-nav)`. Overriding the radius made every pill control snap to the 10px nav radius while focused; the ring now follows the control's own shape. Visibility was already immediate and remains so. |
| Reduced-motion refinement | `@media(prefers-reduced-motion:reduce)` | The blanket suppressor gains `animation:none!important` and the new press pattern is gated inside `no-preference`, so a reduced-motion user receives **no** movement at all rather than a faster one. |

### 8.1 How the press pattern avoids a transform collision

`scale` — the individual property — carries the press, not `transform`. A control
that owns a `transform` therefore keeps it while pressed, which is what §4 asks
for and what the caret's rotation requires. The old
`button:active{transform:none}` suppressor was dead: nothing else in the sheet
gives a button a transform, and it was removed rather than left beside the new
rule. Disabled and busy controls are excluded, so a control that accepts no input
never animates as though it had.

### 8.2 Why M1 does not add a JavaScript reduced-motion check

§6.1 records that no JavaScript reads the preference and suggests M1 introduce it.
M1 does not, deliberately: its only new pattern is CSS-only, so a JS helper would
be unreachable code, and §20 asks for the smallest complete milestone. M2 is the
first milestone whose entry motion genuinely branches in script; the helper
belongs there, where it can be exercised.

### 8.3 What M1 deliberately left alone

- The `no-preference` gate on the caret's rotation is unchanged; M5 owns further
  disclosure behaviour.
- The `reduce` block still does not strip `transform`, because the caret's
  rotation expresses state rather than decoration. Stripping it would remove
  meaning, which §11 forbids.
- No hover-lift, no card scale on non-interactive surfaces, and no motion on the
  many `hidden` writers that carry role, session and pagination state.

### 8.4 Regression coverage

`tests/browser_motion_foundation.cjs` is new and registered in
`tests/browser_smoke.cjs`. It asserts the settled outcome of each pattern rather
than a timing curve: the token values resolve on `:root`; a pressed board control
settles below its resting scale while its computed `transform` stays `none`; a
disabled control never takes the press; every button transition duration resolves
to a token; a keyboard-focused pill keeps its own radius and its ring is visible
without any transition on `outline`; and under `reducedMotion: reduce` a press
produces no scale and no transition while the disclosure caret still reports open
and closed. Produksi is asserted first, then the shared controls, matching the
milestone's stated validation order.

Local verification (19 September 2026, Linux, Python 3.14.5, Playwright 1.63.0 /
Chromium 1243): 509 unit tests PASS; `compileall`, `node --check` on both modules
and `node tests/test_client.mjs` PASS; the full browser suite PASS with no
JavaScript errors. The published PR records CI on the actual HEAD; local passes
alone do not establish the gate. As in M0, `python -m pip check` and
`python -m build` are unavailable in this checkout; CI's Core job covers the first.

Next: M2 (workspace navigation and sidebar motion), only after M1 is reviewed and
merged.
