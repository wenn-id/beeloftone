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

## 9. M2 delta — workspace navigation and sidebar motion

Baseline: `65fb28884b58f498a73094c794bd170405c982ac` (M1 merged as PR #19).
Branch: `ui/motion-workspace-navigation`.

M2 attaches presentation to the navigation lifecycle that Milestone G already
centralised. `activateWorkspace()` remains the single writer for section
visibility; the animation wraps that lifecycle rather than adding a router.

| Change | Where | Intention |
|---|---|---|
| Reduced-motion helper | `reducedMotion()` over one `matchMedia` query | The JavaScript branch §6.1 recorded as missing and M1 deferred. M2 is where it is first needed: entry motion is skipped entirely rather than merely shortened. |
| Page entry | `playEntryMotion()` called from `activateWorkspace()` | The target section fades in from `opacity:0` and `translateY(6px)` over `--motion-enter`. Only the target moves; the outgoing section is already hidden, so nothing slides out and there is no full-screen horizontal movement. |
| Entry lifecycle | `motion-enter` → style flush → (`requestAnimationFrame`) → `is-ready` → token-timed cleanup | The class lands only after the section is revealed, `view` is set and `aria-current` has moved. The initial state is then forced to be computed, and the transition starts on the following frame, as §5 requires. Data fetches are not delayed: the loader has already been called by the time the class is applied. |
| Drawer entry | `sidebar(true)` → `playEntryMotion($('app-sidebar'))` | The mobile panel enters as a small surface with the same frame-later pattern. |
| Drawer accessibility | `syncSidebarInert()` toggled with `nav-open`, plus a `change` listener on the breakpoint | The closed drawer is unrendered (the mechanism this product already ships) **and** inert, so no hidden control is reachable. Desktop never sets it. |
| Selected navigation | `.nav-item[aria-current=page]` transition | The selected tint and its icon settle over `--motion-base` (180ms) instead of the 120ms hover value, so choosing a destination reads as a state change rather than a hover. Press feedback keeps `--motion-instant`. |
| Reduced-motion contract | `.motion-enter,.motion-exit{transform:none!important}` added to the `reduce` block | §11's literal contract for the motion classes, covering the case where the preference changes while an entry is in flight. |

### 9.1 The entry runs only when the destination actually changes

Two cases deliberately receive no entry, both required by §16:

- **Shared analytics host.** All twelve Analitik children map to `analytics-view`.
  Switching between two reports would otherwise replay a whole-page fade for a
  change that is only a report swap. `activateWorkspace()` therefore compares the
  incoming section against the last one it entered.
- **The first activation after a session start.** There is no previous context to
  replace, so animating the login-to-workspace transition would be decoration.
  `clearWorkspace()` resets the record, which also guarantees a class from one
  account cannot survive into another.

### 9.2 Drawer: what is implemented, and what is not

§6 describes an off-canvas drawer — closed at `translateX(-8px to -12px)` with
`opacity:0`, a 220ms entry, a 160–180ms exit and `inert` — and states that a
genuinely smooth drawer needs an accessibility-safe off-canvas state rather than
"just opacity on `display:none`".

**Implemented:** the entry motion (the frame-later pattern means the transition
really runs, which is the failure that sentence warns about), the `inert`
guarantee for the closed state, and a test that sweeps the tab order to prove no
control inside a closed drawer is reachable.

**Not implemented, deliberately:** the off-canvas repositioning and the animated
close. The mobile sidebar in this product is an in-flow row that pushes the page
down, not a floating panel. Converting it to a fixed overlay is a mobile layout
change, not a motion change: it alters what users see when they open navigation
and needs the masthead's real height as an anchor — the masthead wraps past
`--header-h` at narrow widths, so `top` cannot simply be `var(--header-h)`. An
animated close has the same problem in reverse: the panel occupies flow space
while it fades, so the page would reflow 180ms late, after the heading focus has
already moved.

The trade-off is recorded here so the decision is explicit rather than silently
skipped. If the off-canvas model is wanted, it should be its own change with its
own review, and this milestone's entry motion and `inert` handling carry over
unchanged.

### 9.3 Regression coverage

`tests/browser_motion_workspace.cjs` is new and registered in
`tests/browser_smoke.cjs`. It asserts the milestone's focused cases:

| Case | Asserted |
|---|---|
| Produksi → People → Approval quickly, with the board response held open | Only the final page is active, the late response cannot repaint the page the user left, one `aria-current`, no animation class left behind |
| 390px drawer navigation | The drawer entry plays and cleans up, the drawer settles closed, focus lands on the new page heading, and the closed drawer returns to inert |
| 320px / 200% | No document overflow while the drawer and page entries are in flight |
| Reduced motion | No entry class is ever applied, the target is immediately opaque, and `aria-current` is identical |
| Pending recovery | The guard is unchanged, the recovery dialog opens, the owning page is preserved, and no motion state is added |

It also asserts that a report switch inside the shared analytics host never
replays the entry, that the first activation after login carries no motion state,
that desktop navigation moves focus nowhere, and that no control inside a closed
drawer is reachable across a 40-step tab sweep.

Two details exist because code review caught a real gap in the first cut of this
module. The entry must be proven to **transition**, not merely to change classes:
a class mutation is recorded even when an engine coalesces both class updates into
a single style recalculation, and in that case the target simply appears with no
transition at all. The module therefore requires `transitionrun` and
`transitionend` for opacity on both the page and the drawer entry, and
`playEntryMotion()` forces the initial state to be computed before `is-ready` is
added so that the coalescing case cannot occur in the first place. Removing the
entry transition from the stylesheet makes the module fail on exactly that
assertion, which is how the assertion was verified to be load-bearing rather than
decorative.

Local verification (19 September 2026, Linux, Python 3.14.5, Playwright 1.63.0 /
Chromium 1243): 509 unit tests PASS; `compileall`, `node --check` on both modules
and `node tests/test_client.mjs` PASS; the full browser suite PASS with no
JavaScript errors, including both motion modules.

Next: M3 (dialogs and overlays), only after M2 is reviewed and merged.

## 10. M3 delta — dialogs and overlays

Baseline: `31447f6` (M2 merged as PR #20). Branch: `ui/motion-dialogs-overlays`.

M3 is the milestone the specification calls highest-risk, because the exit is the
task most likely to break transaction recovery or focus. Nothing in the close
*decision* or the close *lifecycle* was rewritten: the animation wraps the existing
guarded close and the native `close()` call, so `modalBusy`, `unresolved`,
`guardPending`, `dialogVersion` and the `close`-listener focus restoration all keep
their current meaning.

| Change | Where | Intention |
|---|---|---|
| Dialog entry | `dialog[open]` + `@keyframes dialog-enter` | opacity 0, `scale(.975)`, `translateY(8px)` → resting over `--motion-dialog` (260ms), inside the 240-260ms band. CSS-only, so a reopen replays it and a content swap does not, without any script. |
| Backdrop entry | `dialog[open]::backdrop` + `@keyframes dialog-backdrop-enter` | opacity 0 → target over `--motion-enter` (220ms). The layer table puts the backdrop at 180-220ms, which rules out `--motion-dialog` (260ms) despite the token table naming both layers together. |
| Safe close helper | `closeDialogAnimated()` | Marks the dialog `is-closing`, waits for the exit transition, then calls native `close()`, so the `close` listener stays the single focus-restoration path and `dialogReturnFocus` behaviour is untouched. |
| Cleanup | `resetDialogMotionState()` from the `close` listener | Every close path — the helper, the eight in-dialog controls that call `close()` directly, and session teardown — clears the pending timer, the transition listener and both motion classes. See §10.4. |
| Exit | `dialog.is-closing` | opacity 0, `scale(.985)`, `translateY(4px)` over `--motion-fast` with `--ease-exit`, and `pointer-events:none`: a dialog on its way out is presentation, not an interaction surface. |
| Unified close decision | `dialogCloseBlocked()` | Close button, `Batal` and Escape now share one `modalBusy`/`unresolved` check. Escape calls `preventDefault()` unconditionally and routes through the helper, which closes the §6.4 drift where two copies of the same decision could diverge. |
| Reduced motion | `reducedMotion()` branch + the `reduce` block | Closes immediately through the same `close()`; `dialog, dialog::backdrop` join the explicit §11 list. The list is load-bearing, not decoration: the `*` catch-all matches elements, never pseudo-elements, so the backdrop would otherwise keep animating for a reduced-motion user. |
| Print | existing `@media print` block | Animation, transition, opacity and transform are neutralised on `dialog[open]` and its backdrop, so a printed bundle or receipt label is never captured at the entry keyframe or half-faded. |

### 10.1 Two exit failures the first cuts had, and what fixed them

Both were found by measuring the transition lifecycle rather than the settled
outcome, which is why the module asserts `transitionrun` and `transitionend` instead
of a final class list.

**The timer raced its own transition.** The first cut closed the dialog from a
`setTimeout` of the same length as the exit transition. Measured: `transitionrun`
fired, `transitionend` never did. The timer calls `close()` in the same millisecond
the transition is due to finish, the element is hidden, and the transition ends as
`transitioncancel` with its last frame dropped — the exit would have been *declared*
rather than performed. The helper now closes on the `transitionend` for `opacity` on
the dialog itself, filtered by `event.target` so a backdrop or descendant event
cannot end the close, and keeps a `--motion-fast + 60ms` timer as the safety net for
a transition that never runs at all.

**A close during the entry produced no exit.** Stopping the entry animation and
applying the closing values in one style recalculation makes the engine generate no
transition: the dialog simply vanished when the safety timer fired, 183ms later and
past the budget, while the backdrop — which owns its own entry animation — carried
on fading in behind it. The helper therefore stops both entry animations first
(`motion-exit`), flushes the resting state with the same `void node.offsetHeight`
idiom `playEntryMotion()` already uses, and only then applies `is-closing`. This is
not reachable with an ordinary Playwright click, which waits for the element to
settle; the module dispatches that close synthetically, and the assertion was
verified to fail without the ordering.

Measured end to end, the dialog settles closed 129-149ms after the close begins
depending on whether the entry was still running — 120ms of transition plus event
delivery and the flush, inside the contract's 160ms ceiling in both cases.

### 10.2 Which close callers migrated, and which deliberately did not

`ui/motion-dialogs-overlays` migrates the two paths where the operator is watching
the dialog leave, and leaves the other thirteen immediate.

| Path | Sites | Treatment | Reason |
|---|---|---|---|
| Close button, `Batal` | `closeDialog()` | **Animated** | The operator's explicit close of a settled secondary task: the case the milestone exists for. `Batal` arrives through the same `data-action` registry entry, so it inherits the guard unchanged. |
| Escape / `cancel` | `cancel` listener | **Animated** | Now routed through the same decision and the same helper instead of a second inline copy. |
| Navigation from a dialog | `navigateFromDialog()` | Immediate | Closing is a step of a page change, not the event; a lingering modal would hang over the page it just activated. |
| Session reset | `clearWorkspace()` | Immediate | Teardown of a discarded session: nothing to soften, and tests assert the dialog is gone on the same turn. |
| Post-write success chain | `formDialog` | Immediate | The chain continues synchronously into `openDetail()` or a follow-up dialog. Closing immediately lets the next dialog `showModal()` fresh, which is what replays its entry; an animated close would have the follow-up cancel the pending exit and reuse the same surface with no entry at all. |
| Order-detail hand-offs | eight `*-order` buttons | Immediate | Each is preceded by `guardPending()` and immediately activates a workspace page. |
| Read-only context switch | `[data-ai-history]` | Immediate | Closes the investigation dialog, activates `ai-view`, scrolls to history. |
| Dialog-to-dialog replace | material batch scan | Immediate | The history dialog replaces the scan dialog in the same turn; the surface is reused, not dismissed. |

### 10.3 The exit keeps the dialog modal for its exit budget

The contract closes the native dialog *after* the exit runs, so for roughly 145ms
after the close button is pressed the page behind is still inert and the closed
control is not yet gone. That is the price of an animated modal exit and it is what
the specification asks for, but it is a real behaviour change and it has one test
consequence worth recording: a `fill()` issued during that window silently does
nothing, because the input is inside a modal-blocked subtree. Clicks are unaffected
— they wait for the element to receive the event — so only the one call site that
typed into the page straight after a close needed to wait for the dialog to settle
(`tests/browser_smoke.cjs`, before the dashboard evidence screenshot, which also now
captures a settled dashboard instead of a half-faded dialog). Every other close site
in the suite is separated from its next input by a click or a `waitFor`, and all
168 Escape presses were checked.

### 10.4 Two review findings that changed this milestone

Both came from automated review on the PR and both were verified against the
running product rather than taken on the report's word.

**An abandoned exit could break the next dialog.** The exit left the dialog
`open` and clickable, and eight controls inside `#dialog-content` call `close()`
directly rather than through the helper. A direct close during the exit therefore
left `motion-exit`/`is-closing` and the pending timer behind. The classes were not
cosmetic: the next dialog opened invisible and non-interactive, and the surviving
timer closed it about 180ms later. Cleanup now hangs off the native `close`
event — the one thing every close path shares — so the timer, the transition
listener and both classes are cleared no matter who closed the dialog. The
regression case reproduces the abandoned exit and then opens a second dialog
inside the abandoned window; removing the cleanup makes the whole browser suite
fail before that case is even reached, because the SKU form in the shared smoke
body can no longer be clicked.

**The late-response case was not testing the guard it named.** The first cut
released the held response *after* the dialog had finished closing, so the
assertion only exercised the `!$('dialog').open` check and would have passed even
if the `dialogVersion` guard were broken. The response is now released inside the
exit window and the test proves it: the route handler reads back `dialog.open`
while the exit is running and the case asserts it was still `true`, so the
generation guard is what has to reject the response. A `MutationObserver` on the
surface confirms nothing touched it once the close began. A first attempt asserted
the open state read inside the observer callback and failed on the entry write —
mutation callbacks run a microtask after the record, by which point `showModal()`
has already run, so the log is cleared after the dialog settles instead.

### 10.5 Regression coverage

`tests/browser_motion_dialogs.cjs` is new and registered in `tests/browser_smoke.cjs`.
It asserts lifecycle flags and settled outcomes rather than animation timings:

| Case | Asserted |
|---|---|
| Dialog entry from Produksi | `animationstart` and `animationend` for `dialog-enter`; the backdrop resolves `dialog-backdrop-enter` with a non-zero token duration |
| Close button | `is-closing` is applied, the exit really starts and finishes an `opacity` transition, exactly one `close` event, no class left behind, focus back on the trigger |
| Reopen | The entry replays, which proves the element left the `[open]` state rather than merely being covered |
| Escape | Same exit and same single close as the button, proving it no longer bypasses the helper |
| Close during the entry | The entry is provably still running when the close is dispatched, and the exit still transitions, completes, closes once and leaves no class — the case that silently produced no exit before the ordering fix |
| Batal | Same helper, same single close |
| Three open/close cycles | Exactly three close events, no stacked handler, no residue |
| Unresolved write | Escape is refused, no `is-closing` is ever applied, the dialog stays open, and the retry then settles the draft |
| Direct close during the exit | The closing classes clear immediately, and a dialog opened inside the abandoned exit window survives — it is neither closed by a surviving timer nor rendered non-interactive |
| Late dialog response | The held response settles while the dialog is still open, and nothing touches the surface once the close has begun — the request-generation guard, not the `open` attribute, is what rejects it |
| Reduced motion | No animation runs, the dialog is opaque immediately, the close is immediate, no `is-closing` is ever applied, focus still returns through the same path |
| Print | Computed `animation-name: none`, opacity 1 and no transform on an open dialog |
| 320px / 200% | No document overflow while the entry runs, and the dialog fits when settled |
| Dark theme | The same entry and exit lifecycle |

### 10.6 Verification

Local verification (19 September 2026, Linux, Python 3.14.5, Playwright 1.63.0 /
Chromium 1243): 509 unit tests PASS; `compileall`, `node --check` on both modules and
`node tests/test_client.mjs` PASS; the full browser suite PASS with no JavaScript
errors, including all three motion modules. As in M0-M2, `python -m pip check` and
`python -m build` are unavailable in this checkout; CI's Core job covers the first,
and a wheel check is only meaningful once CI has the published HEAD.

Next: M4 (data states and notifications), only after M3 is reviewed and merged.

## 11. M4 delta — data states and notifications

Baseline: `49addbb` (M3 merged as PR #21). Branch: `ui/motion-data-states`.

M4 is the first milestone that changes what the operator sees *during* a request
rather than only after it. The §08 distinction is the whole milestone: a page that
already has data keeps it while the next request runs, and only a genuine
replacement fades. Every state keeps its existing semantics — no loader gained or
lost a clear, a retry, or a guard.

| Change | Where | Intention |
|---|---|---|
| Notice entry | `.notice.motion-enter` via `playEntryMotion()` | opacity 0 + `translateY(8px)` → rest over `--motion-enter` (220ms, inside the 180-220ms band). Reuses the M2 helper, so the frame-later flush and the cleanup are the ones already proven. |
| Notice exit | `.notice.motion-exit` via `hideNotice()` | opacity 0 + `translateY(4px)` over `--motion-base` (180ms) — the token table names `--motion-base` for the toast exit — then `hidden`. Driven by `transitionend`, with the same safety net as the dialog exit. |
| Notice timer | `notify()` unchanged in meaning | Six seconds from the message, never from the animation. A new message cancels an in-flight exit so a stale timer cannot hide it early. |
| Refresh treatment | `markRefreshing()` / `settleRefreshing()` | A container that already has children keeps them, gains `is-refreshing` (opacity .78) and `aria-busy="true"`, and is never locked. Returns whether it preserved anything, so the caller chooses between the first-load state and the refresh state. |
| List replacement | `.list-host.motion-enter` via `playEntryMotion(node, '--motion-base')` | Opacity only, over the token the table names for a refresh fade. No row stagger and no movement, so a filter, a search or a page change reads as one change of content. |
| Empty state | same replacement fade, applied to the message | An empty result is a semantic state, not a loading placeholder: the list empties and the message enters as one unit, only when there were rows to replace. The rule covers `.state` as well as `.list-host`, and the module asserts the message's opacity transition starts and finishes — otherwise the class would be applied to an element with nothing to transition, which is the "declared rather than performed" failure this programme already tests for. |
| Errors | untouched paths, plus `settleRefreshing()` | An error is written immediately at full opacity, the dim is removed first, and the rows the operator already had stay on screen. |
| Reduced motion | the §11 block and the JS branch | The dimming is state and stays; the fades do not run; `hideNotice()` applies `hidden` immediately. `.notice` is now named in the reduced-motion block, as §11 spells out. |

### 11.1 Where the distinction is implemented, and how it is derived

Three pages distinguish a refresh from a first load: **Produksi** (the §05 golden
screen), **Master SKU**, and **Bahan baku**. They are the pages that have a manual
refresh control over a list with the same loader shape, which is what makes the
helper reusable rather than one page's special case.

The board does not ask its nine callers which kind of load this is. It compares the
query it is about to send against `boardQuery`, the query it last rendered, and
treats a change as a replacement. That keeps the decision in one place, needs no
call-site changes, and stays correct for the filter, search, pagination and reset
paths alike, because each of them changes the query and a plain refresh does not.
Bahan baku derives `materialsQuery` the same way from its material filter.

### 11.2 What this milestone deliberately did not do

**No changed-row tint.** §18 lists it as optional and it is the only bullet that
adds a *new* signal to a successful mutation rather than reducing a reset. It also
needs a per-row lifecycle that nothing else in the programme has, so it is left
out rather than half-built; if it is wanted it reads as its own change.

**No per-keystroke fade on Master SKU.** Its search filters a cached array on every
`input` event, so a container fade per keystroke would read as flicker, which is
the opposite of the specification's north star. The search stays instant; the page
keeps the refresh treatment on its refresh control.

**No propagation to the remaining list pages.** Approval, purchase request,
marketing budget, integration and command centre loaders share the same shape but
each carries its own clear contract, and §05 asks for the grammar to be proven on
Produksi before it is propagated. M6 owns "cross-section propagation"; the helper
is in place for it, and the three pages above prove it generalises.

### 11.3 Regression coverage

`tests/browser_motion_data_states.cjs` is new and registered in `tests/browser_smoke.cjs`.
It asserts lifecycle flags and settled outcomes rather than animation timings:

| Case | Asserted |
|---|---|
| Notice lifecycle | The entry really starts and finishes an opacity transition and leaves no motion class; the message is still visible four seconds in; it leaves through the exit state, finishes that transition, applies `hidden`, and leaves no class |
| Manual refresh | The existing rows stay on screen, the list is not hidden, `is-refreshing` and `aria-busy="true"` are set, opacity lands inside the documented 0.72-0.82 band, the filters stay usable, the existing pagination guard is unchanged, and the whole state is removed when the load settles |
| Filter replacement | Only a replacement fades: a plain refresh produces no `motion-enter` and no row restyling, while a filter change starts and finishes an opacity transition on the container and animates no individual row |
| Empty result | The list empties and the empty state enters as one unit, then cleans up |
| Error during refresh | The dim is removed, the message is fully legible with no motion class, the previous rows are still there, and the board is not left reporting busy |
| A query that failed first | A filter whose first attempt fails still fades the list when the same query finally renders |
| Reduced motion | The refreshing state and the dim are still reported and visible, with `0s` transition; a replaced list never fades; the notice never transitions or moves |
| 320px / 200% and dark theme | No document overflow while a list is replaced, and the same refresh state in the dark theme |

Two of the milestone's assertions were verified as load-bearing rather than
decorative: removing the refresh branch from the board fails the module on "a
refresh does not hide the list" — the exact visual reset §08 exists to remove.

### 11.4 Three review findings that changed this milestone

All three came from automated review on the PR and all three were reproduced against
the running product before being fixed. Two of them are about what the tracking
variables actually mean.

**The recorded query must be the rendered one.** `boardQuery` and `materialsQuery`
were written when the request was *sent*, before its staleness guard and before
anything was painted. A request that failed or was superseded therefore recorded a
query the screen never showed, and the later attempt with that same query compared
equal to it, read as a plain reload, and skipped the replacement fade entirely. Both
loaders now compute `replacing` and record the query inside the success branch,
after the guard. Reproduced and confirmed: with the old shape, a filter whose first
attempt fails never fades when it finally renders.

**A failed board load left `#summary` marked busy forever.** The catch cleared the
list's own marker but not the summary's `aria-busy`, so assistive technology was
told the summary was still updating until some later load happened to clear it.
This is pre-existing rather than introduced here, but M4 is the milestone that
promotes `aria-busy` to the board's documented completion signal — the doc and two
adapted tests now depend on it — so leaving it stuck contradicts the contract this
milestone writes. The command centre's own summary already cleared its marker on
error; the board now matches it.

### 11.5 Tests that assumed the old refresh

Preserving content on reload removes a signal three tests were leaning on: before
this milestone, `#order-list` was hidden for the whole of a board load, so
`!order-list.hidden` meant "the board finished loading". It no longer does, which
is the point of the milestone. Each site was updated to the board's own busy
marker, which is the idiom the production premium module already used:

| File | Was | Now |
|---|---|---|
| `browser_production_premium_ui.cjs` | A held reload was expected to show the loading placeholder and hide the list | A held reload is expected to keep the rows visible and mark the list busy, with the pagination guard unchanged — and a separate block asserts the placeholder and the hidden list for a load with nothing to preserve, so the distinction itself stays covered |
| `browser_smoke.cjs` | `!order-list.hidden` after a retry | `#summary[aria-busy]` detached |
| `browser_navigation_foundation.cjs` | `!order-list.hidden` on re-entering the board | `#summary[aria-busy]` detached |

The placeholder assertion was not simply deleted: the premium module had the only
coverage of that first-load state on the board, so it now asserts both states
side by side instead of one.

### 11.6 Verification

Local verification (19 September 2026, Linux, Python 3.14.5, Playwright 1.63.0 /
Chromium 1243): 509 unit tests PASS; `compileall`, `node --check` on both modules and
`node tests/test_client.mjs` PASS; the full browser suite PASS with no JavaScript
errors, including all four motion modules. As in M0-M3, `python -m pip check` and
`python -m build` are unavailable in this checkout and are recorded as gaps, not
passes.

Next: M5 (microinteractions and theme), only after M4 is reviewed and merged.
