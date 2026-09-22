# Apple-27 A3: navigation spring and velocity controller

Baseline: `52546b924d44697cf97278c695f812a67a91588d`, the fetched `origin/main` at the time this
phase started, which merged A2 / [PR #90](https://github.com/wenn-id/beeloftone/pull/90). Main
had not advanced past the supplied SHA. Branch: `ui/apple27-a3-navigation-spring`. Application
**0.101.0** in all three places that declare it — package, runtime and stored OpenAPI contract —
which A3 also repairs; see *Version-metadata repair carried by A3* below. Schema **55**, no
migration. The repository advances the minor version for a visible milestone; 0.101 does not imply
a release or a semantic-version promise.

A3 gives the single A2 lens physics. It adds no Liquid Glass, no `backdrop-filter`, no blur,
refraction or GPU renderer, no bottom navigation, no new navigation structure, no page-transition
system and no animation dependency. A4 owns glass.

## What changed, and what deliberately did not

A2 measured the selected destination and wrote the result instantly. A3 replaces only that last
step, at the seam A2 reserved for it:

```text
aria-current="page"
  -> getActiveNavigationTarget()
  -> measureNavigationTarget()        unchanged: geometry, validity, visibility, two contexts
  -> retargetNavigationLens()         A3: decides snap or physical travel
  -> spring integrator                A3: one cancellable requestAnimationFrame loop
  -> renderNavigationLensMotion()     A3: one style write per frame
  -> settle                           A3: exact target geometry, zero velocity, loop stopped
```

`applyNavigationLensGeometry()` is gone; `retargetNavigationLens()` took its place. Measurement,
validity rejection, the occlusion rules, the fallback lifecycle, the `.nav-lens-ready` class and
both positioning contexts are A2's and are unchanged.

`aria-current` remains the only authority on which destination is selected. `activeNavigation()`
still removes the previous attribute, sets the new one and only then *requests* presentation
work. Nothing semantic waits for the spring: workspace visibility, request invalidation, `view`,
analytics identity, focus, mobile drawer closing, API requests and transaction state all remain
immediate. The lens may still be visibly travelling after the new page is already active and
already loading. That is intended, and the browser module asserts it.

The spring never chooses a destination. Its state records which target it is currently chasing so
it can tell a destination change from a layout correction; that field is a consequence of
navigation, never a source of it.

## Spring model and constants

One central configuration, in `beeloft/static/app.mjs`:

```js
const navigationLensSpring = {mass:1, stiffness:520, damping:40};
```

These are Beeloft tuning values. They are not claimed Apple constants, and no private Apple
spring was reproduced or inferred.

Force law, integrated with semi-implicit Euler — acceleration is read at the current position,
velocity is advanced first, then position uses that new velocity:

```text
F = -stiffness * (value - target) - damping * velocity
a = F / mass
velocity += a * step
value    += velocity * step
```

Derived behaviour: undamped frequency `sqrt(k/m)` = 22.80 rad/s, damping ratio
`c / (2*sqrt(k*m))` = **0.877** — high damping, deliberately just below critical. Analytic
overshoot at that ratio is 0.32%; at 60Hz sampling no overshoot is observable at all. The
envelope decay `c / 2m` is 20 s⁻¹, which is what actually sets the settling time, so stiffness
inside the authorised 500–540 band changes the feel far less than damping does.

The four axes — centre x, centre y, width, height — use the same configuration and the same
integrator. There is no separate size timeline.

## Physical state

```js
{initialized, context, targetId, running, lastTimestamp,
 cx, cy, width, height,
 vx, vy, vWidth, vHeight,
 targetCx, targetCy, targetWidth, targetHeight}
```

Position and dimensions are CSS pixels; velocities are CSS pixels per second. State is
centre-based rather than top-left, so a move and a resize share one origin and a height change
grows symmetrically instead of dragging one edge. `context` is the positioning element the
coordinates belong to. No navigation, session, role or business value is stored here.

`initialized` answers one question: does the lens have valid, visible physical history? It is
true only after a successful render and is cleared whenever the object stops being real — hidden,
detached, collapsed, drawer closed, session replaced.

## Retarget contract

`retargetNavigationLens(geometry, targetId)` writes the four target values and then chooses:

| Condition | Behaviour |
| --- | --- |
| No valid visible physical history (`initialized` false) | Snap: write exact geometry. |
| `prefers-reduced-motion: reduce` | Snap: write exact geometry. |
| Same destination, spring already settled | Snap: this is a layout correction, not a journey. |
| Same destination, spring still in flight | Replace the target geometry only; velocity untouched. |
| Different destination | Replace the target geometry only; velocity untouched; keep integrating. |

The critical rule is what the function does *not* contain: no write to `vx`, `vy`, `vWidth` or
`vHeight`, and no write to `cx`, `cy`, `width` or `height`. A new destination can only move the
target. Velocity is zeroed in exactly two places — `settleNavigationLensMotion()`, where the
object genuinely stopped, and the explicit `reset` branch of `cancelNavigationLensMotion()`,
where the object stopped being valid. The static contract asserts that set is exactly those two
functions, and a mutation that zeroes velocity on retarget fails both the static and the browser
contract.

Consequence for the required sequence — Produksi, People, Kapasitas produksi, Command Center,
each chosen before the previous motion settled — is one continuous object whose destination keeps
changing. There is no animation queue, no "finish A before B", and no restart from the previous
button. The latest semantic destination always wins.

### Same-frame coalescing

A2's one-shot measurement frame is preserved and still holds its own handle. Several semantic
updates inside one task therefore produce one measurement of the *latest* `aria-current`, so the
lens is never walked through destinations that were never rendered for a frame. A destination
that arrives while the spring is already visibly travelling retargets from the current physical
state instead.

## Frame time, substeps and stalls

Elapsed time comes from the frame timestamp in seconds; 60Hz is never assumed. The first frame
after a start only establishes the baseline and integrates nothing.

| Guard | Value | Reason |
| --- | --- | --- |
| Maximum integration substep | 1/120 s | Keeps the explicit integrator stable and frame-rate independent. |
| Maximum integrated frame | 32 ms | A dropped frame slows the motion slightly instead of jumping. |
| Stall threshold | 200 ms | Above this the interval is refused: the spring settles exactly at its target. |

The stall threshold is what makes a resumed background tab, a long task or a locked screen safe:
requestAnimationFrame is throttled or paused there, so the first frame after resuming carries a
huge delta, and integrating it would invent enormous velocity. Settling is a deliberate choice
over simulating a stale interval. A timestamp that moves backwards or is not finite takes the
same path. No always-running visibility listener is needed, and none was added.

After integration the step also rejects non-finite values and non-positive dimensions by settling
exactly, so `NaN`, `Infinity` and a negative width can never reach the DOM. The browser module
injects +3000 ms and −3000 ms timestamp jumps mid-flight and asserts an exact settle in both.

## Settle condition and idle work

A frame settles only when, for all four axes, distance to target is below **0.25 CSS px** *and*
speed is below **2 CSS px/s**. Distance alone would stop a lens that is still moving fast through
its target; speed alone would stop it in the wrong place.

On settling the controller writes the exact target geometry, zeroes all four velocities, clears
the motion frame handle, sets `running` false and drops the compositor hint. No fractional drift
is left behind.

While settled there is **zero** recurring frame work: no requestAnimationFrame, no interval, no
polling, no physics timer. The loop exists only while the lens is physically unsettled. A layout
change may still schedule A2's one-shot measurement frame; the two jobs hold separate handles,
`navigationLensSyncFrame` and `navigationLensMotionFrame`, so neither can cancel or inherit the
other's frame.

## Rendering and deformation

The lens is anchored at `left:0; top:0` by CSS, so the transform the controller writes *is* its
local coordinate. Position moves with a transform rather than with `left`/`top`; width and height
are written as lengths so the 1px border and the A1 control radius stay crisp instead of being
scaled. One `cssText` write per frame carries all of it, which also keeps the sidebar's existing
attribute MutationObserver to a single ignored record per frame.

Compositor promotion is requested only for the duration of the movement, and both halves of that
request are withdrawn when the lens arrives:

| State | Transform written | `will-change` |
| --- | --- | --- |
| Travelling | `translate3d(x, y, 0)` | `transform` |
| Settled | `translate(x, y)` | absent |

Dropping `will-change` alone would not have been enough. A 3D transform is itself a promotion
heuristic in current engines, so a lens left at `translate3d(...)` at rest could hold its own
layer indefinitely — which is exactly what releasing the hint was meant to prevent. Switching the
resting position to a 2D `translate` closes that gap. This is a deliberately conservative choice
based on documented engine behaviour, not on a measured layer count: an attempt to count layers
through the CDP `LayerTree` domain produced no snapshot in this headless configuration, so no
layer measurement is claimed here. What *is* asserted, in the browser module, is the observable
behaviour: a travelling lens carries both the 3D transform and the hint, and a settled lens
carries neither. `will-change` appears nowhere in the stylesheet, and no containment or layer hack
was added.

Deformation is derived from velocity, after physics, at render time only:

```text
vertical = |vy| >= |vx|
stretch  = min(0.07, |dominant velocity| / 3000 * 0.07)
width    = width  * (vertical ? 1 - stretch/2 : 1 + stretch)
height   = height * (vertical ? 1 + stretch : 1 - stretch/2)
```

The lens elongates along the dominant axis of travel and narrows very slightly across it, so
mostly vertical sidebar movement reads as a taller, slightly narrower object at speed. The cap is
7%. The 3000 px/s reference was chosen from measured peak speeds in this sidebar — an adjacent
40px hop peaks near 400 px/s and the longest measured travel near 6000 px/s — so the stretch
actually reads velocity across the real range instead of sitting at its cap. Measured peaks:
0.9% for an adjacent hop, 3% mid-sidebar, 7% for the longest travel.

Because the value is a local render quantity it is never fed back into target geometry, spring
state, measurement or semantic state, so it cannot compound. As velocity approaches zero the
stretch approaches zero, and at settle it is exactly zero: **the resting DOM rectangle equals
the selected button's rectangle.** The only residue is floating-point: the rendered edge is
derived as `centre − size/2` from a centre that was `edge + size/2`, which is exact to within one
unit in the last place (about 3×10⁻¹⁴ px at these magnitudes). Assertions use a 0.05px render
tolerance for that reason, not to hide a discrepancy.

There is no wobble, jelly, bounce or second timeline, and no scripted pointer-down compression
phase. The existing global press grammar `button:active:not(:disabled){scale:.985}` is untouched
and still gives the control its own press response; velocity-derived lens morph complements it.

## Cross-context continuity

A2 uses one lens node in two positioning contexts: `#app-sidebar` normally, and
`.sidebar-actions > .sidebar-cta` while `#approvals` is selected. Local coordinates are not
comparable between them, so reparenting without conversion would teleport the lens. Before the
node moves, the current physical centre is converted through viewport coordinates:

```text
viewportX = oldRect.left + old.clientLeft - old.scrollLeft + cx
viewportY = oldRect.top  + old.clientTop  - old.scrollTop  + cy

cx = viewportX - newRect.left - new.clientLeft + new.scrollLeft
cy = viewportY - newRect.top  - new.clientTop  + new.scrollTop
```

`vx`, `vy`, `vWidth`, `vHeight` and `running` are untouched by the conversion, and the new
target geometry is already measured in the new context. This is not a new animation; it is the
same physical object in a new basis. Deformation is unaffected because it is derived from the
preserved velocity, so identical speed and direction produce identical stretch on either side.

Both directions were reviewed visually and are asserted: on the frame the reparent happens the
lens is still within render tolerance of where it was in viewport space, and it then travels
normally inside the new context. The same DOM node survives — verified by identity, not by
counting. No clone, ghost, cross-fade or approval-specific second indicator was created. Where
stacking briefly occludes part of the lens as it crosses the sticky CTA boundary, that is left
truthful rather than hidden behind a duplicate.

## Layout corrections versus destination changes

A geometry change for the destination that is already selected is a correction, not a journey:

- settled, and geometry changed by resize, text reflow or scroll — snap exactly to the corrected
  geometry, with no decorative travel and no spring started;
- still in flight, and the same destination's geometry moved — update the target without touching
  velocity, so the spring cannot chase a stale destination.

Sidebar scrolling therefore keeps the selected indicator exactly on its button; it does not
spring behind the scrolling content. A responsive breakpoint change corrects alignment without
inventing movement.

## Cancellation lifecycle

| Event | Response |
| --- | --- |
| Target becomes non-measurable or leaves the accepted viewport contract | Cancel motion, reset physical history, hide the lens, restore the legacy selected styling. Snap when it becomes valid again — never fly in from a stale invisible position. |
| Analytics disclosure closes over the selected child | Cancel immediately, reset history, hide; `aria-current` is preserved. Reopening snaps straight to the child. |
| Mobile drawer navigation | The drawer still closes immediately; the hidden, inert sidebar cancels motion. No close is delayed so the animation can be watched. Reopening snaps to the current destination. |
| `enterWorkspace`, drawer reappearance, session replacement | No meaningful previous history exists: snap. |
| `clearWorkspace`, logout, identity switch | Cancel both frames and reset position, velocity, target identity, context and visibility. No previous account's momentum can survive into a new session. |
| Role change (admin-only destination then a viewer login) | Same reset. No hidden target, stale velocity, stale context or transient flight from the old destination. |
| Presentation error anywhere in measurement, retarget or a motion frame | Caught, lens hidden, `.nav-lens-ready` removed, legacy selected background and marker remain usable. Navigation never fails because physics failed. |

Only presentation errors are caught in the controller; business and navigation errors are not.

## Reduced motion

The existing `reducedMotionQuery` is the authority. Under `prefers-reduced-motion: reduce`,
semantic navigation is immediate as always and the lens is written directly at the latest target:
zero travel, zero velocity, zero deformation, no integrator frame scheduled at all. The lens's
appearance is state and stays visible; only its travel is suppressed.

A change *to* reduce while the spring is running cancels it on the spot and snaps to the latest
valid target with velocity zero and no pending frame — A3 adds the `change` subscription the A0
audit noted was missing for the lens. When the preference returns to no-preference, no old travel
is replayed; the next semantic navigation may animate. No near-zero fake duration is used as a
completion signal anywhere.

## Accessibility

The lens remains `aria-hidden="true"`, `pointer-events:none`, non-focusable, empty and
unlabelled. Motion conveys nothing that `aria-current` does not already expose. `aria-current`
still owns the selected text colour, icon colour and font emphasis, and none of them wait for the
lens to arrive; no label or icon is cloned into the moving surface. The focus ring stays above
the lens, and keyboard activation retargets exactly like pointer activation because both change
the same semantic destination.

## What A3 did not touch

All six motion durations and three easings keep their A1 values, and the A3 contract asserts them
literally. `playEntryMotion()`, `clearEntryMotion()`, dialog enter and exit, notice, refresh,
list replacement, scanner feedback, progress settling and theme motion are unchanged, and none of
them appear in the lens region. No new scripted `setTimeout` was introduced, so the token/declared
exception contract in `test_motion_contract.py` is untouched, and no new scripted motion class was
added. PR #87's dialog inert-on-close guard is unchanged.

Backend APIs, schema, migrations, business formulas, money arithmetic, production semantics, QC
and rework, approval semantics, auth/session/OIDC, idempotency, actor binding, pending recovery,
stale-response protection, role authorization and audit behaviour are all untouched. Motion is
presentation only. Schema remains `PRAGMA user_version = 55`.

`beeloft/api.py` is touched in exactly one place, and not for motion: the version string the
application reports about itself, as part of the metadata repair recorded in the next section. No
route, handler, dependency, guard, model or response changed.

## Version-metadata repair carried by A3

A3 also repairs a metadata drift that A2 introduced, as a separate bookkeeping change with no
behavioural content.

The repository announces its version in three places, and the convention through 0.98.0 was that
all three move together. A2 ([PR #90](https://github.com/wenn-id/beeloftone/pull/90)) bumped only
the first:

| Source | After A2 (#90) | After A3 |
| --- | --- | --- |
| `pyproject.toml` `project.version` | 0.100.0 | **0.101.0** |
| `beeloft/api.py` `FastAPI(version=…)` | 0.99.0 | **0.101.0** |
| `docs/openapi.json` `info.version` | 0.99.0 | **0.101.0** |

So the built package called itself 0.100.0 while the running API and its published contract both
still called themselves 0.99.0 — a full minor version behind, and two versions behind by the time
A3 started. No test failed, because `test_openapi_contract.py` only bound the stored document to
the runtime; both were equally stale, so they agreed with each other.

`beeloft/api.py` now declares 0.101.0 and `docs/openapi.json` was regenerated with
`python scripts/regenerate_openapi.py`, which is the documented release step for it.

**The regenerated contract differs from the contract on main in exactly one leaf value.** This was
verified by walking both documents and collecting every leaf-level difference, not by reading the
textual diff:

```text
total leaf differences: 1
  $.info.version: '0.99.0' -> '0.101.0'
```

Checked independently by category, all identical: 221 paths, 253 operations (every method, path,
`operationId`, parameter, request body and response), 85 component schemas, `securitySchemes`,
top-level `security`, `tags`, `servers`, the OpenAPI version itself (3.1.0), the top-level key set,
and every `info` field other than `version`. No endpoint, schema, operation, security or tag
changed, and no request or response behaviour changed: the only thing A3 altered here is the
version string the application reports about itself.

`tests/test_openapi_contract.py` gains `VersionMetadataConsistencyTest`, which binds all three
sources to one value and additionally requires each to be a full `major.minor.patch` triple so
`0.101` and `0.101.0` cannot drift apart as strings. Five deliberate scenarios were each confirmed
to fail it, including A2's exact one:

| Scenario | Result |
| --- | --- |
| Package version bumped alone — A2's drift | FAIL |
| Runtime version bumped alone | FAIL |
| Stored contract bumped alone | FAIL |
| Package and runtime bumped, regeneration forgotten | FAIL |
| A two-component version such as `0.101` | FAIL |

The pre-existing guard that the stored document's paths match the runtime is unchanged and still
passes. A future visible milestone can therefore no longer bump one of the three alone.

## Verification

`tests/test_apple27_navigation_spring_contract.py` (21 tests) asserts architecture rather than
pixels: one lens and no ghost or duplicated approval indicator, semantics ahead of presentation,
one central spring configuration in the authorised high-damping regime, a real damped-spring
force law integrated with semi-implicit Euler, seconds-based time with bounded substeps and a
stall guard, the centre/velocity/target state shape, a retarget path that writes no velocity and
no position, velocity zeroed only where the object stops or dies, context rebase by coordinate
conversion, separate measurement and motion handles, a settle path that clears the frame and
writes exact geometry, no interval or second animation mechanism, no layout read inside the
physics functions, capped render-only deformation that never feeds back, transform rendering with
`will-change` only while running, no CSS travel on the lens, no glass or GPU renderer, the
reduced-motion snap and mid-flight cancellation, the preserved failure fallback, and the
unchanged A1 motion tokens and press grammar.

Fifteen deliberate mutations were each confirmed to fail that contract — zeroing velocity on
retarget, aliasing the two frame handles, cartoon-bounce damping, a CSS transition on the lens,
a `backdrop-filter`, a fixed 16.6ms step, a settle that leaves residual velocity, deformation fed
back into the target, a `setInterval` physics timer, a settle that does not stop the loop,
reduced motion travelling anyway, a layout read inside the loop, a retuned A1 token, removed
press feedback, and a permanent `will-change` in CSS.

`tests/browser_navigation_spring.cjs` runs through the existing disposable demo runner and reads
the real rendered rectangle across real frames:

| Case | Asserted |
| --- | --- |
| A. Normal travel | `aria-current` and the active section change before any frame runs; the first frame is still at the old destination; intermediate positions exist across many distinct rendered positions; final geometry equals the target; no `NaN`, `Infinity` or non-positive dimension is ever written. |
| Deformation | Between two identically sized destinations, peak height is 1–7% above target and width dips slightly below it; nothing survives the settle. |
| B. Size morph | A 40px row to a 34px analytics child passes through intermediate heights and converges on the child's real geometry. |
| C. Rapid retarget | Four destinations, three frames each: every click lands semantically at once, one lens, one `aria-current`, the latest destination wins the final write, no stale destination is written, no frame left pending. |
| D. Velocity continuity | Travelling down, then sent back up while fast: momentum carries the lens measurably past the point where it was told to turn around, it does come back, and no frame teleports. |
| E. Approval context | Reparenting into and out of `.sidebar-cta` moves nothing in viewport space on the reparent frame, the same node survives, travel continues inside the new context, final geometry is correct both ways, and no second indicator exists. |
| F. Analytics collapse | Collapsing hides the lens and leaves no pending frame while `aria-current` survives; reopening snaps straight to the child. |
| G. Sidebar scroll | Five consecutive frames after a scroll stay exactly on the button, and no spring is started. |
| H. Resize | A viewport change corrects alignment within a handful of frames instead of a journey. |
| Frame gaps | +3000 ms and −3000 ms timestamp jumps mid-flight both settle exactly at the target. |
| I. Mobile drawer | The drawer still closes immediately, the hidden drawer cancels motion, and reopening shows the lens already on the current destination. |
| J. Reduced motion | Five destinations including the approval context are placed on the very next frame, do not move afterwards, hold no compositor hint, spend no integrator frames, and perform zero frame work across a 500 ms idle window. |
| K. Preference change in flight | Switching to reduce mid-travel snaps to the latest target, releases the hint, leaves no pending frame, and restoring the preference replays nothing. |
| Session teardown | Logout clears geometry and both frames; a viewer login starts settled on its own destination with no flight from the admin-only one. |
| L. Idle | A settled lens performs zero frame work across 500 ms. |

Seven deliberate mutations were confirmed to fail that module, including one that initially
slipped through: the first velocity-continuity assertion compared a span that still contained a
pre-retarget frame, so zeroing velocity passed it. It was replaced with the momentum-coast
measurement above, and both the zeroing mutation and a full restart-from-rest mutation then
failed. The other caught mutations are instant apply with no spring, reparenting without
coordinate conversion, ignoring reduced motion, and a settle that never stops the loop.

`browser_navigation_lens.cjs` keeps A2's coverage with three adaptations: "aligned" now also
requires the compositor hint to be released, so every A2 geometry assertion still describes a
*resting* lens; the analytics distinctness check reads the rendered rectangle because position is
now a transform rather than an inline `top`; and the next-frame instant-geometry assertion is
scoped to reduced motion, where no travel exists. Its rapid-navigation and idle-RAF assertions
are unchanged. `test_apple27_navigation_lens_contract.py` keeps A2's markup, fallback, geometry
and measurement assertions and now names `retargetNavigationLens` as the renderer; its physics
exclusion became a bounded-measurement assertion, with the physics contract living in the A3
file. `test_apple27_foundation_contract.py`'s spring exclusion became a containment check: the
integrator, its configuration and the word `velocity` must not appear outside the lens region,
and exactly one spring configuration exists in the application. A2's historical validation is
not rewritten as if it had been spring-based.

### Performance observations

Local, single-sample, synthetic, headless Chromium on this container. Not a hardware budget, not
CI, and not Safari or Firefox verification.

Measured with the shipped integrator (numerically in a harness mirroring it, and against the real
renderer in the browser module):

| Travel | Frames at 60Hz | Within 1 px | Fully settled (0.25 px / 2 px/s) | Peak speed | Peak stretch |
| --- | --- | --- | --- | --- | --- |
| 40 px, adjacent row | 19 | 217 ms | 317 ms | 375 px/s | 0.9% |
| 90 px | 21 | 250 ms | 350 ms | 843 px/s | 2.0% |
| 240 px | 23 | 283 ms | 383 ms | 2248 px/s | 5.2% |
| 640 px, longest usable | 24 | 317 ms | 400 ms | 5993 px/s | 7% (capped) |
| 45 px carrying 1200 px/s inherited | 14 | 150 ms | 233 ms | 822 px/s | 1.9% |

So an ordinary adjacent movement is perceptually settled at roughly 220 ms and numerically exact
at roughly 320 ms, and longer travel takes somewhat longer, as intended. Settling time is
dominated by the damping envelope, not by a duration: nothing in the controller is tuned to a
fixed length, and an interrupted movement finishes sooner or later depending on the momentum it
inherited. At 30, 50, 60, 90, 120 and 144Hz the same 240 px travel settles within 354–400 ms with
no overshoot and no divergence, which is the frame-rate independence the substep cap exists for.

Per-frame cost while a spring runs: one lens, one motion frame callback, four scalar integrations
per substep (at most four substeps), one style write and one ignored observer record. No layout
is read in the loop, no row or page animation participates, and no second element is touched.
A rapid four-destination sequence produced no error and left no pending frame. Idle cost was
measured the way A2 measures it — wrapping `requestAnimationFrame`/`cancelAnimationFrame` before
the application loads and comparing pending and executed counts across a 500 ms window, which
includes ordinary application frame work — and both counts were unchanged under both motion
preferences, with zero pending. A resize correction cost fewer than 8 frames against roughly 20
for a real journey.

Frame-level smoothness was reviewed as recorded video, and the per-frame sample series in the
browser module shows continuous rendered positions with no gaps. That is not the same as a
profiler-verified 60fps claim, and none is made here; long-task profiling under populated
marketplace data belongs with the A4/A5 measurement work the A0 audit already scheduled.

### Motion quality review

Recorded locally at desktop 1440 in light and dark, and at 390 with the drawer, as video rather
than screenshots, because the subject is motion. The reviewed sequence was Command Center,
Produksi, People, Kapasitas produksi, Inbox approval, Command Center, followed by a rapid
Produksi, People, Analitik, Command Center sequence with each selection made before the previous
motion completed. Videos are local temporary artifacts and are not committed.

Review outcome: one physical object that responds immediately, accelerates softly, damps hard and
arrives without a cartoon bounce or a robotic fixed-duration slide. Interruption reads as the
same object changing its mind and keeping its momentum, not as a restarted animation. The
velocity stretch is visible as liveliness at speed and is gone at rest; it was kept rather than
rejected. The approval reparent reads as continuous in both directions. The subtle occlusion
while the lens crosses the sticky CTA boundary is visible on close inspection and was accepted as
truthful one-object behaviour.

### Full validation

Recorded in the final report for this branch together with the environment used. Local Python
3.12.13 with the pinned `requirements.txt`, Node 22.23.2 and Playwright 1.63.0 / Chromium, run
from a disposable environment outside the repository; the browser suite uses the existing runner's
temporary demo database and loopback server. All runtime records are disposable synthetic
fixtures. These are local results, not CI, Safari or Firefox verification.

### Pre-existing flake observed while validating, not introduced here

Two full browser runs on this branch failed inside `browser_dialog_closing.cjs` — PR #87's
regression module, which A3 does not modify and which runs *before* both lens modules. The
assertions that tripped were `Escape/Space leaves no focus in the inert subtree` and
`focus() cannot re-enter any closing control`, both inside the same loop.

The mechanism is a race between the harness and the animated exit, not a product defect. That loop
presses Escape, confirms the dialog is mid-exit and inert, then sends a second input that must be
refused. The exit lasts `--motion-fast` (120ms) with a 180ms fallback. If the intervening CDP
round-trip takes longer than that window, the exit has already completed and the native close has
restored focus to the `#new-order` trigger, so Space activates that trigger and legitimately opens
a fresh dialog — focus is then inside a dialog that is no longer closing, and the assertion fails
even though the guard behaved correctly.

It was attributed by measurement rather than assumption. Running that module alone, interleaved
between this branch and a detached worktree at the unmodified baseline
`52546b924d44697cf97278c695f812a67a91588d` under the same load, produced **4 failures in 6 runs on
each side**, and the baseline reproduced the identical `Escape/Space` assertion. Under light load
both sides pass. No lens motion is running at that point in the module — the only navigation
happens once at its start, the loop itself never navigates, and every iteration waits 350ms before
acting — so the spring adds no frame work to that window.

A3 therefore leaves the module untouched: repairing another phase's test fragility is outside this
scope and was not authorised. It is recommended as a small separate change, since it will redden CI
intermittently on any loaded runner. The suggested fix is to assert against the state captured at
the moment the input is delivered, or to hold the exit open for the duration of the probe, rather
than to lengthen a timeout.

## A3 / A4 boundary

A3 ends at physics and shape response. The lens is still the A1/A2 solid material: an
accent-soft fill with a separator-strong border and the A1 control radius. The "liquid" quality
in A3 comes from the spring and the velocity-derived stretch, not from glass.

A4 owns optical rendering and must not be started from this phase: `backdrop-filter`, blur,
refraction, chromatic aberration, dynamic optical distortion, shaders, WebGL and WebGPU are all
absent here and are asserted absent. A4 will also need the solid fallback, reduced-transparency
and forced-colors paths the A0 audit specified, and should reuse this controller rather than
introduce a second motion mechanism beside it.
