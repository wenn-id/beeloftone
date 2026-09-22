# Apple-27 A2: shared navigation selection lens

Baseline: `f8040e97df2fd4dec6def0cafa1bcf268907e01a`, fetched `origin/main`,
including A1 / PR #89. Branch: `ui/apple27-a2-shared-selection-lens`.
Application: **0.100.0**. Schema: **55**, no migration. The repository advances
the minor version for visible milestones; 0.99 does not imply a 1.0 release.

## Ownership and appearance

`aria-current="page"` remains the only selected-destination authority.
`activeNavigation()` writes semantics before requesting presentation work; page
activation, focus, request dispatch and transaction guards never await the lens.
The lens reads the attribute, including when different analytics destinations use
the same `analytics-view`. It writes no navigation, session or business state.

Exactly one empty `span#nav-selection-lens.nav-selection-lens` is declared as the
first child of `aside#app-sidebar`, before `.sidebar-nav`. It is hidden initially,
`aria-hidden="true"`, has no tabindex or label and cannot receive pointer events.
The existing button text/icons and focus rings remain on the interactive controls.

Design read: the existing Indonesian operations workspace, in the approved A1
native-system visual language; ENERGY 2 / RHYTHM 2 / MOTION 1. The accent-soft solid
fill identifies the selected destination. A separator-strong border gives the
surface an edge, and the A1 control radius matches the measured button footprint.
No palette, typography, composition or new content is introduced.

## Geometry and paint contexts

`getActiveNavigationTarget()` reads the semantic element. One canonical
`measureNavigationTarget()` rejects disconnected, outside-sidebar, hidden, inert,
collapsed-details, unrendered, invisible, non-finite and zero-size targets. It hides
the lens if the target is entirely outside the sidebar scrollport or occluded by
the sticky footer. It does not scroll or select another destination.

The lens is absolutely positioned. Desktop sidebar positioning remains sticky;
the mobile sidebar becomes `position:relative; top:auto` instead of static so the
same root-relative measurement works inside the in-flow drawer. Sidebar isolation
keeps the decoration's paint order local. For any positioning context C:

```text
x = targetRect.left - contextRect.left - C.clientLeft + C.scrollLeft
y = targetRect.top  - contextRect.top  - C.clientTop  + C.scrollTop
width  = targetRect.width
height = targetRect.height
```

Padding is already included in rectangle displacement; subtracting it again would
be incorrect. Target sizes are rendered measurements, never inferred row heights.
The drawer's existing ancestor translation cancels in the rectangle subtraction.
Reads finish before the renderer writes geometry. `applyNavigationLensGeometry()`
is the separate instant-render seam reserved for A3.

**Approval stacking decision:** a single root paint context cannot place a solid
root sibling above the sticky footer/card backgrounds but below the button inside
that footer's stacking context. While `#approvals` is selected, the *same existing
node* is reparented as the first child of `.sidebar-actions > .sidebar-cta`.
That positioned card becomes C; normal destinations use `#app-sidebar` as C.
This deliberately uses two existing positioning contexts instead of redesigning
the footer, removing its sticky behavior, duplicating text or making another lens.
The measured target is always the actual `#approvals` button. Card background,
then lens at z-index 1, then button text/focus at z-index 2 preserves paint order.
Other destinations move the same node back to the sidebar. Both contexts use the
same measurement API and renderer; geometry carries the context explicitly.

The approval button's fill/border/shadow become transparent only when the lens is
ready and the button owns `aria-current`. Its selected text uses the A1 accent and
font emphasis. The inactive CTA retains its appearance and accessible name.

## Fallback and lifecycle

Only successful measurement/rendering adds `.nav-lens-ready` to the sidebar.
Only selectors scoped by this class suppress the legacy selected background and
left marker. Hidden/unavailable targets and caught presentation errors remove the
class, hide the lens and clear its inline geometry. The legacy selected styling
continues to work without the lens; approval has an explicit solid accent-soft
selected fallback so it remains distinguishable from the inactive primary CTA.
Its selected text color and emphasis depend on aria-current in both modes.

| Trigger | Presentation response |
| --- | --- |
| Semantic navigation | Coalesce one frame, read the *latest* aria-current and instantly render it. No queued snapshot of an old target. |
| Analytics collapse/reopen | Native details toggle schedules measurement. A collapsed child keeps its semantics but hides the lens; reopening restores its measured decoration. No summary selection. |
| Sidebar scroll | One passive listener schedules one frame; viewport-to-content coordinates include both scroll axes and borders. The sticky approval target is measured in its own current context. |
| Resize and text scaling | Window resize plus one ResizeObserver on the sidebar, nav, action/card surfaces and 27 persistent destination buttons. Font reflow and changed preceding rows invalidate geometry. |
| Existing button press ends/cancels | Remeasure the selected button after its existing scale feedback settles. No press behavior or motion token changes. |
| Role visibility | A bounded MutationObserver watches hidden/style attributes within the sidebar and ignores lens writes. Size changes also trigger ResizeObserver. |
| Mobile drawer | Existing inert synchronization requests layout after opening; closing immediately cancels the queued frame and hides the lens. Existing expanded/focus/Escape and page-entry behavior remain intact. |
| Login/session replacement | Clear old decoration at enterWorkspace; the existing showBoard activation schedules after role visibility and workspace rendering. |
| clearWorkspace/logout | Immediately cancel any scheduled lens frame, remove ready state and clear/hide geometry. Failed logout retains the valid existing session through unchanged session logic. |
| Reduced motion | Identical instant geometry. No alternate timing or travel animation exists. |

Observers and listeners are installed once on persistent shell elements for the
document lifetime, rather than once per login or target. They retain no account or
business data. Hidden workspace/drawer notifications take the immediate hide path
without scheduling a frame. Lens writes cannot resize the observed boxes, and its
attribute records are ignored, preventing observer feedback.

## Idle work and phase boundary

The scheduler owns one nullable RAF handle. It clears the handle at callback entry,
reads current semantics then stops. It never schedules itself, uses no interval or
polling timer, and does not reuse business request generations. Rapid activation
therefore ends on the final semantic destination. Teardown cancels the pending frame.

The static test checks that the lens block has one RAF call site, no recursive
scheduling and no timers/physics. The browser test instruments RAF/cancelRAF and
checks zero pending callbacks and an unchanged executed count across a 500ms idle
window, under both motion preferences. This includes ordinary application RAF work.

A2 stops at instant rendering. A3 may replace the apply step with a physical
controller while preserving target measurement and visibility lifecycle, including
the context supplied with geometry. No spring, velocity, integrator, animated lens
travel, elasticity, bounce, Liquid Glass, blur, backdrop-filter, refraction, GPU
renderer, bottom navigation, workspace redesign or new route is implemented.
Page/dialog/toast/refresh/scanner/progress/theme motion remains unchanged.

## Verification

`test_apple27_navigation_lens_contract.py` covers markup/decorative ownership,
scoped fallback, geometry separation, semantic ordering and the bounded scheduler.
`browser_navigation_lens.cjs` runs through the disposable demo runner and covers
regular destinations, same-host analytics, disclosure, sticky approval, scroll,
border/horizontal offsets, hover, keyboard/focus, desktop/mobile boundaries,
320px/200% text, failure fallback, rapid navigation, role/session reset, reduced
motion and idle RAF work. It saves nine local screenshots: Command Center,
capacity analytics and Inbox approval at 1440 light/dark and 390 light drawer open.

Existing A1 tests now allow the authorized lens while retaining their exclusions
for optical effects, physics and external assets. The motion consistency test
measures selected text contrast against the actual lens surface when ready and
the legacy button background otherwise; existing timing and page-motion assertions
remain unchanged.

| Validation | Result |
| --- | --- |
| `python -m unittest discover -s tests -v` | PASS: 585 tests in 1216.158s, exit 0. |
| `python -m pip check` | PASS: no broken requirements. |
| `python -m compileall -q beeloft` | PASS. |
| `node --check beeloft/static/app.mjs` | PASS. |
| `node --check beeloft/static/client.mjs` | PASS. |
| `node tests/test_client.mjs` | PASS: escaping, dates, exact retries, actor/auth headers, structured errors and CSV. |
| `python tests/run_browser.py --channel chromium` with bundled `--playwright-module` | PASS: full unfiltered suite, exit 0, all existing and new modules, final no-JS-errors assertion. |
| `python -m build` with local `--outdir` | PASS: 0.100.0 wheel and sdist. |
| Packaged static assets | PASS: all four static files byte-identical in both wheel and sdist to tested source. |
| Disposable database | PASS: `PRAGMA user_version = 55`. |
| `git diff --check` | PASS. |

Scoped visual delivery checks:

- PASS, geometry and resilience: browser assertions cover sidebar scrolling,
  approval, 981/980 boundary, mobile drawer and 320px/200% text with no overflow.
- PASS, purpose and existing identity: one accent-soft selection surface uses A1
  material/radius tokens; no content, icon, navigation structure or layout redesign.
- PASS, keyboard and semantics: native navigation/disclosure, visible focus,
  single aria-current, decorative noninteractive lens and preserved mobile focus.
- PASS, light/dark readability: A1 contrast tests and all-destination browser
  contrast assertions use the visible selected surface; nine screenshots reviewed.
- PASS, state and behavior: full browser suite covers empty/loading/error,
  role/session changes, pending recovery and existing business interactions;
  A2 failure injection also proves navigation works with a missing lens.
- PASS, motion boundary: final geometry on the next frame under both preferences,
  no lens animation, and zero pending/executed RAF work across the idle window.

### Local environment and artifacts

Validation uses Python 3.12.14 / Starlette 1.6.0 in the existing isolated
`%TEMP%/beeloft-a0-audit/venv`, with repository-root `PYTHONPATH`, Node 24.18.0 and
bundled Playwright 1.62.1 / Chromium. Browser invocation supplies the absolute
bundled Playwright module because this repository has no installed local Node
dependencies. These are local results, not CI, Safari or Firefox verification.
All runtime records are disposable synthetic fixtures.

Logs, wheel/sdist and screenshots are local in `%TEMP%/beeloft-a2-qa`.
Screenshot filenames use `a2-lens-{1440-light,1440-dark,390-light}-` followed by
`{command-center,capacity-plan,approvals}.png` (nine images). Each was visually
inspected for alignment, readable text and correct paint order. The mobile
approval screenshot scrolls to the bottom of the existing in-flow drawer.
Screenshots are not committed.

The initial complete Python run found one documentation mismatch (581 stated
tests versus 585 discovered); README now includes the four new contracts. The
initial complete browser run passed every module but exposed a test-instrumentation
cleanup error: a late RAF callback read a deleted window counter. The instrumentation
now closes over its own counter, so releasing its global handle cannot break a
pending callback or the application callback it wraps. Both suites were rerun.

### Changed files

- `beeloft/static/index.html`, `style.css`, `app.mjs`: single lens, presentation
  styles, measurement and bounded lifecycle hooks.
- `tests/test_apple27_navigation_lens_contract.py`, `browser_navigation_lens.cjs`:
  new static and browser contracts; `browser_smoke.cjs` registers the browser module.
- `tests/test_apple27_foundation_contract.py`, `browser_motion_consistency.cjs`:
  adapt the old lens exclusion and selected-surface measurement to authorized A2.
- `pyproject.toml`, `README.md`, `docs/version-history.md`: 0.100.0 and test count.
- `docs/apple27-navigation-lens.md`: implementation and validation record;
  `docs/apple27-native-parity-audit.md`: update only the programme roadmap section.

No backend, SQL, migration or client transport source changed. A2 is complete
on the `ui/apple27-a2-shared-selection-lens` branch for PR review; no merge or
deployment occurred. The 13 changed/new files listed above contain only A2
work. Final logs:
`unittest-final.log`, `browser-final.log`, `build-final.log`, `package-final.log`
and `package-schema-check.log` in the local artifact directory. A3 has not started.
