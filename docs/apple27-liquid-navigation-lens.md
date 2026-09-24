# A5.3 — Liquid navigation lens (motion review candidate)

Baseline: `bc984aa5e04b1ba9d9f18f430049cab8afa2e488`, PR #96, A5.2 version 0.104.0,
schema 55. Branch: `ui/apple27-a5-3-liquid-navigation-lens`.
The exact-main CI was still running after core tests passed. Work originally stopped;
the user's subsequent “lanjut saja” authorized continuing. That exact SHA subsequently
completed successfully: [post-merge CI](https://github.com/wenn-id/beeloftone/actions/runs/35976419698).

## Reference study, before implementation

Only `C:/Users/acer/Downloads/IMG_6301.MP4` was used. Original file and extracted
frames remain local under `data/a53/reference/`; they are not publication assets.
Measurements use original frame timestamps and pixels, before any rotation or resizing.

- 1170 × 2532, 1,252 decoded frames; video duration 21.653333 s, container 21.660862 s.
- Nominal rate 60000/1001; reported average 3756/65 = 57.784615 fps (decoded timestamp cadence ≈57.787 fps).
  Median frame interval 16.667 ms; range 16.666–133.333 ms; 25 intervals exceed 20 ms.
- Representative released transition: Community → Calls, approximately 18.11–18.79 s.
  Frame 1057 (18.091667 s) is rest; frames 1063/1065 are early pull;
  1070 (18.310000 s) is near peak/between destinations; 1075 is travel/contraction;
  1083 (18.526667 s) is late contraction; 1099 (18.793333 s) is settled.
- Manual outer-silhouette bounds (about ±4 px): Community rest 267 × 166 px,
  peak 335 × 204 px, Calls rest 258 × 164 px. Raw peak is about +25% longitudinal
  and +23% cross-axis relative to the starting lens. Rest lens width is about
  1.28 tab pitches and height about 90% of the bar. The whole bar also expands
  approximately 5% when engaged; relative to that bar the lens expansion is about 20%.
- Initial expansion is visible around 18.11–18.13 s (frames 1058–1059), before the
  stronger directional pull and refractive edge at 18.16–18.19 s. Peak follows initial
  expansion by roughly 180–210 ms, or directional pull by 120–150 ms. Clear contraction
  follows peak by about 80–220 ms. Visual settle lies around 18.71–18.79 s, approximately
  600–690 ms after initial expansion.
  These are visual intervals, not touch-event timestamps; the video contains no input log.
- Leading edge advances before the trailing edge catches up. The body remains fused
  across the gap. Trailing curvature is tighter, with a slightly fuller leading side.
  No large rebound is apparent; an overshoot smaller than the measurement uncertainty
  cannot be distinguished from the bar's own movement.
- Early sequences around 1.9–13 s show sustained dragging and consecutive reversals
  without resting between destinations. Later transitions show release and contraction.
- Rim refraction is strongest at the curved ends, with white/cyan/blue separation and
  narrow warm fringes. The center remains comparatively quiet. The source visibly
  magnifies/refracts icons and portions of labels at the edge; their layout positions
  remain anchored. Beeloft must keep these glyphs sharp and unscaled instead.

Horizontal source X becomes sidebar Y; source cross-axis Y becomes sidebar X.
The wide, short sidebar row and its 12 px gutters require less cross-axis expansion
than the source's compact tab. The mapping will cap that expansion rather than clip it.
Timing continues to emerge from the frozen A3 spring, not from these measured durations.

This is a web perceptual approximation of the supplied video, not Apple's native compositor.
Human motion approval is required; this document does not grant it.

## Human review correction — 24 September 2026

The first motion candidate was not approved. Review identified a missing visible long-travel
sequence and disconnected highlights in the 25 fps recording. The shell/layout stays frozen.

The correction keeps the same body pseudo-element alive at rest and in flight, instead of
swapping between parent paint and a newly promoted pseudo-element. The dark A5.2 selector also
needed matching specificity: otherwise it kept painting the parent underneath the optical body.
Browser assertions now reject any nontransparent parent fill or background image during flight.
The approval-only backdrop filter is disabled during travel and returns at rest; the outgoing
ordinary lens paints above the sticky card's background. Position, hit testing and A3 are intact.

The optical cap is now 35% longitudinal / 9% cross-axis, signed offset 8.5% of rendered height,
taper 25% of height, rim opacity 0.80 and rim thickness 1.5 px. The reference's compact capsule
and the approved sidebar row have different aspect ratios; these values are a review candidate,
not a claim of measured shape equivalence. No spring timing or constants were changed.

New evidence is under `data/a53/revision/`. It supersedes the first `motion-light.mp4` /
`motion-dark.mp4` for motion review. Windows GDI recording requested at 60 fps yielded black
frames and was rejected. Cropping the compositor's visible capture area to 260 × 1000 while
keeping `innerWidth=1440` makes direct CDP capture practical at high frame cadence. Captured
images retain original compositor timestamps; the encoded files are variable frame rate,
without motion interpolation or a false constant-60-fps label. The accompanying 120 Hz clips
are generated from the real A3 renderer under a controlled test clock, clearly labelled as
such. They are not recordings of real-time browser throughput.

Final revision validation and measured capture results are recorded with the review evidence.

## Implementation

Version 0.105.0; schema stays 55. The existing empty, aria-hidden span is unchanged.
Its persistent body pseudo-element paints at rest and in flight; the second paints a masked rim. Neither
can receive input. `aria-current` changes synchronously before A2 schedules measurement.

The pure `navigationLensOptics(vy, running)` function lives beside the existing renderer.
With `d = clamp(vy / 400, -1, 1)` while running (otherwise zero), and `a = abs(d)`:

| Presentation output | Formula / cap |
| --- | --- |
| Longitudinal optical scale | `1 + .35*a` |
| Cross-axis optical scale | `1 + .09*a` |
| Signed leading offset | `.085*d * A3 rendered height` |
| Unequal end curvature | top `radius + .25*d*height`, bottom `radius - .25*d*height` |
| Rim opacity | `.80*a` |
| Specular center | `50 + 50*d` percent along Y |

The A3 7% renderer deformation is still calculated and written unchanged to the span.
These additional scales affect its pseudo-elements, not that measured rectangle. Combined
vertical elongation is bounded by `1.07 * 1.35 = 1.4445` times physical height. Normal vertical
travel has a maximum combined width increase of about 8.5%; at A3's maximum speed its
cross-axis narrowing brings this down to about 5.2%. It cannot become a path-length bridge.

Positive velocity makes the bottom edge lead; negative velocity makes the top lead.
Offset, curvature and the light position pass continuously through zero speed. Retargeting
does not consult target direction to flip the optics and stores no extra animation state.

The rim combines a white/cyan specular gradient and a narrowly masked cool/warm fringe.
No glyph is copied, scaled or refracted. Light/dark body paint reuses the approved A5.2
values. There is no blur on an ordinary lens, and no animated filter anywhere in this change.
The existing approval-only filter is withdrawn during flight and restored at rest.

The single existing style write appends the optical properties only during flight.
At settle it writes the original A3 resting style string, removing the entire suffix:
no dynamic inline properties, no pseudo transform, no 3D transform or will-change. The same body pseudo-element stays present, avoiding a paint-owner swap.
Canonical CSS defaults are scale 1, offsets/taper/rim 0, light center 50%.
Rest geometry, A5.2 material tokens and radius remain unchanged; the paint owner is now the persistent pseudo-element.

Thirteen existing selection, measurement, integration, retarget, rebase and lifecycle functions were
compared with the baseline after newline normalization and are byte-identical. Mass 1,
stiffness 520, damping 40, 1/120 s substeps, 32 ms cap, >200 ms stall handling,
settle thresholds and the old 7% morph constants remain unchanged. PR #95's deterministic
velocity proof and PR #96's queued-measurement drain were not edited.

## Context, stacking and accessibility

Approval uses the same node and existing viewport-space rebase. Its existing material
remains scoped to the CTA. The CTA's old `overflow:hidden` sliced a travelling object
before arrival, so **only while it contains the in-flight shared lens** it becomes visible.
Sidebar scrolling and the outer window retain their clips. The label, icon, focus outline,
CTA copy and Analitik disclosure paint above the lens; the existing shimmer stays above it.
The outgoing lens is lifted above the sticky card paint during flight; nav labels retain their higher stacking level. No sidebar composition, destinations, keyboard behavior or A5.2 shimmer was changed.

Reduced motion uses A3's immediate placement and does not generate optical pseudo-content.
Reduced transparency keeps shape motion and supplies an opaque solid body without rim.
Forced colors suppress both pseudo-elements and retain the system Highlight outline.
Without backdrop-filter support the optical body uses the existing solid fallback.
Mobile navigation retains immediate drawer closure; opening it places the lens at the
current target instead of holding navigation open for an animation.

## Mutation evidence

Mutations were applied to isolated source strings or temporary static-file copies; the
working application was never served in a mutated state. The originals pass again afterward.

| Mutation | Failing proof |
| --- | --- |
| Speed forced to zero | positive in-flight stretch/bulge/rim |
| Direction inverted | downward leading offset and end curvature |
| Asymmetry removed | nonzero signed offset and unequal curvature |
| Chromatic rim permanent | canonical zero-velocity rest |
| Rest reset disabled | exact production-renderer resting string |
| Duplicate lens node | static one-node count |
| Ordinary backdrop filter restored | parsed CSS selector scope |
| Velocity zeroed on retarget | unchanged PR #95 deterministic velocity equality |

Raw evidence: `data/a53/mutations-js.json`, `data/a53/mutations-static.json`.

## Performance measurements — first candidate, before human correction

Chromium 153, 1440 × 1000, real RAF timestamps on this Windows host. No virtual clock,
recording or other browser test was running during this comparison; the Python suite
was still running. Baseline serves the exact main `app.mjs` and `workspace.css`; candidate
serves the final source. Each scenario has one warm-up plus three measured repeats per theme.
The table combines the three repeats across light/dark (six samples per scenario).

| Scenario | A5.2 median / max ms | A5.3 median / max ms | Intervals >32 ms, A5.2 → A5.3 |
| --- | --- | --- | --- |
| One row | 6.9 / 14.2 | 7.0 / 21.0 | 0 → 0 |
| Long travel | 6.9 / 14.2 | 7.0 / 14.1 | 0 → 0 |
| Eight destinations | 7.0 / 14.6 | 7.0 / 34.8 | 0 → 1 |
| Reversal | 6.9 / 14.1 | 7.0 / 20.9 | 0 → 0 |
| Ordinary → approval | 7.0 / 21.0 | 7.0 / 21.1 | 0 → 0 |
| Approval → ordinary | 7.0 / 14.7 | 7.0 / 14.2 | 0 → 0 |

Warm-up is retained in the raw JSON as `repeat:-1`. Candidate light warm-up had three
additional >32 ms intervals: 41.7 ms one-row, 42.0 ms approval-in, 41.4 ms approval-out.
Baseline warm-up had none. Both versions had zero observed long tasks, zero pending RAF
after settle, and `will-change:auto` in every sample, including warm-up. The measured
outliers are not proof of an attributable regression or proof of its absence. There is
no sustained cadence collapse in these samples, but candidate first-use stalls remain
a measured limitation. No 60 fps claim is made from either these callbacks or the videos.

Raw timestamps/styles: `data/a53/baseline-warm-performance.json` and
`data/a53/candidate-warm-performance.json`; helper: `data/a53/measure.cjs`.
Earlier pilot measurements are retained separately and are not substituted for this table.

## Local review evidence — first candidate (superseded)

All files below are ignored local QA evidence. The reference is not added to Git.

- `data/a53/review/index.html`: review player, scenario buttons, comparison videos and strips.
- `data/a53/motion-light.mp4`, `data/a53/motion-dark.mp4`: actual browser captures, 25 fps.
  Both include one-row up/down, long up/down, reversal, four rapid targets and approval
  crossing in both directions. `data/a53/recordings.json` contains approximate event times.
- `data/a53/review/original-orientation.mp4`: horizontal source beside vertical Beeloft.
- `data/a53/review/normalized-comparison.mp4`: source rotated 90° counterclockwise as a
  comparison aid. No source measurement uses the rotated image. Footage is not time-stretched.
- `data/a53/review/frame-strip-light.png`, `frame-strip-dark.png`: approximate normalized
  phases, with original source timestamps and controlled A3 clock timestamps shown separately.
  Percentages represent each transition's own duration, not identical elapsed time.
- `data/a53/review/axis-comparison-light.png`, `axis-comparison-dark.png`: rest/peak/settle
  shape comparison with uniform scaling and source rotation only.
- `data/a53/review/frame-strip-timestamps.json`, `data/a53/frames-light.json`,
  `data/a53/frames-dark.json`: exact selected frames and test-clock style/geometry samples.

The available Playwright recording path produces 25 fps. It is supplemented by the
timestamped 60 Hz controlled-clock strips; these are deterministic renderer samples,
not a claimed 60 fps screen recording. The original reference is variable frame rate.

## Changed files

- `beeloft/static/app.mjs`: private optical mapping and suffix on the existing render write.
- `beeloft/static/workspace.css`: in-flight body/rim, stacking, scoped CTA clip and fallbacks.
- `tests/test_navigation_liquid_lens.cjs`: deterministic optical and exact renderer-reset proof.
- `tests/test_apple27_liquid_lens_contract.py`: five structure, physics, fallback and version contracts.
- `tests/browser_navigation_liquid_lens.cjs`: browser motion, contexts, accessibility and idle proof.
- `tests/browser_smoke.cjs`: registers the new module after the unchanged A3 module.
- `tests/browser_functional_glass.cjs`: counts and verifies the added A5.3 fallback groups;
  existing material/contrast/filter checks remain intact.
- `beeloft/api.py`, `pyproject.toml`, `docs/openapi.json`: version 0.105.0 only.
- `README.md`: Python test count 640 → 645.
- `docs/apple27-liquid-navigation-lens.md`: this report.

No business logic, schema migration, dashboard composition, route, session/pending-write
behavior or A3 controller/test was changed. Pre-existing untracked A5.2 documentation
and screenshots are outside this change. HEAD remains the baseline SHA; no commit was made.

## Validation — first candidate

- Python: **645 tests passed in 1194.145 s**, `data/a53/python-full-final.log`.
- Apple-27 static contracts: **69 passed**, `data/a53/contracts-final.log`.
- Deterministic A3 spring, optical mapping, client tests, syntax, `pip check`,
  `compileall` and whitespace checks: passed, `data/a53/final-checks.log`.
- Focused liquid browser module: **20/20 normal**, `data/a53/repeated-normal.json`;
  **20/20 with CDP CPU slowdown 4×**, `data/a53/repeated-cpu4.json`.
  This throttles the browser renderer, not the operating system.
- A4 glass and the subsequent A5.2/dashboard/utility modules: passed together after
  integrating the new fallback groups, `data/a53/browser-tail-focused.log`.
- Full browser runs: **two complete green passes of all 87 browser modules**
  (86 inherited plus this phase's new liquid-lens module). Run 5 17:31:03–17:46:23
  and run 6 17:46:23–17:58:55 (+07), 15m20s and 12m32s; every module emits its PASS
  summary, including A2 lens, A3 spring, A4 functional glass, A5.2 workspace and
  A5.3 liquid lens (`A5.3 liquid lens PASS: one node, bounded optical silhouette,
  both directions, momentum reversal, rapid retarget, CTA/rebase/clipping, analytics,
  focus, responsive/text zoom, fallbacks, exact rest, zero idle RAF`).
  Evidence: `data/a53/browser-full-5.log`, `data/a53/browser-full-6.log`,
  `data/a53/browser-full-5.time`, `data/a53/browser-full-6.time`. Runs 1–4 stopped
  early for the reasons recorded below and are not counted as passes.
- Build: wheel and source archive 0.105.0 passed; all nine packaged static assets
  equal tested source. OpenAPI structural diff is version-only; schema remains 55.
  Evidence: `data/a53/build-final.log`, `data/a53/package-validation.json`,
  `data/a53/final-source-validation.json`.

Earlier failed attempts remain in the local logs. The initial Python run found only
the README's stale 640 count; it was corrected to 645 before the complete passing run.
Initial browser attempts exposed a heading test running against stale loaded CSS and
the old A4 fallback-group counts. A separate full attempt aborted on `route.fetch`
with a local socket hang-up during the unchanged lost-response movement test.
A later attempt passed A2/A3/A5.3 but timed out during an A4 sidebar pixel read;
Windows recorded sleep/resume events during that run and the observation window
included a large wall-clock gap. No timeout assertion was weakened to count it as a pass.
Failed attempts are not counted as completed full-suite passes.

## Remaining visible differences

- A5.2's wide, short row is preserved. Rotating the source's compact capsule cannot make
  its resting aspect ratio match this row without redesigning the approved sidebar.
- Cross-axis expansion is smaller than the source's approximately 23%; the 12 px sidebar
  gutters and text readability determine the optical 9% cap. The source's whole toolbar
  expands under interaction; Beeloft's sidebar remains stationary.
- On the controlled 60 Hz one-row sample, deformation peaks at 50 ms and A3 settles at
  333 ms, versus roughly 180–210 ms from initial expansion to peak and 600–690 ms to visually settle in the
  selected reference transition. A3 was deliberately not retimed.
- The source magnifies and chromatically refracts glyphs at the lens edges. Beeloft keeps
  text and icons sharp, and approximates that edge light with a restrained 1 px gradient rim.
- Source dragging can hold deformation for seconds. Beeloft responds to discrete existing
  navigation actions; there is no drag interaction or continuous idle lens animation.
  Beeloft changes semantic selection and starts destination loading immediately; the source
  can retain the Community view during a held drag until release.
- The body retains the approved soft blue A5.2 material and existing approval material;
  it does not reproduce the source application's black selected fill or native refraction.
- CSS border-radius and transform deformation approximate the source's continuously
  refracted curved contour. The rim has no environment-dependent ray tracing.

These differences require human motion review. Passing tests is not motion-parity approval.

## A5.3 motion revision — final convergence candidate

This section supersedes the first-candidate motion evidence above. The corrected paint path
uses the same pseudo-element body and rim both at rest and in flight, so Chromium does not
retain a stale resting capsule while promoting a second moving surface. The approved shell,
sidebar geometry, destinations, A2 lens controller, A3 spring, and `aria-current` behavior
remain unchanged.

The moving lens now derives its bounded stretch, horizontal bulge, directional offset,
leading/trailing corner taper, and rim highlight from the existing signed spring velocity.
Approval entry and exit keep the same shared lens: the sticky CTA stops clipping it during
flight, the capsule crosses above the card, and the CTA lens does not stack a second backdrop
filter over the moving surface. The static reduced-motion fallback and focus/accessibility
states remain intact.

### Final review artifacts

- `data/a53/revision/review.html`: local selector for all 14 light/dark live scenarios,
  the generated-clock clips, and the six-phase close-cropped light/dark long-travel strips.
- `data/a53/revision/raw-compositor-frames.zip`: every locally captured JPEG and its original
  Chromium compositor timestamp, navigation event, and RAF/style samples.
- `data/a53/revision/actual-{light,dark}-{adjacent,long-down,long-up,reversal,rapid-four,approval-in,approval-out}.mp4`:
  direct compositor samples encoded as variable-frame-rate video. No frame interpolation or
  timestamp rewriting was used; all samples were monotonic in this final capture.
- `data/a53/revision/generated-{light,dark}-{long-down,approval-out}.mp4` and
  `long-strip-{light,dark}.png`: explicit A3 test-clock samples at 120 Hz, including rest,
  early pull, peak stretch, mid-travel, contraction, and settle. These demonstrate controlled
  renderer states; they are not a live screen recording or a claim about live device cadence.
- `data/a53/revision/hfr-summary.json`: frame counts and original interval measurements for
  each scenario. Encoded actual-video averages range from 32.0 to 98.5 fps; moving-sample
  median intervals are 9.0–12.2 ms, with one observed maximum gap of 52.9 ms. No 60 fps claim
  is made for any individual variable-rate capture.

### Final convergence verification

- A5.3 optical mapping unit check and the five static A5.3 contracts pass.
- A5.3 liquid-lens browser cases, A4 functional-glass checks, all 27 navigation destinations,
  responsive/text-zoom states, A2 lens, A3 spring, and the A5.2 workspace passed in the first
  complete browser run: `data/a53/revision/browser-full-1.log` (exit 0).
- The second complete browser run passed the same suite: `data/a53/revision/browser-full-2.log`
  (exit 0 at 21:21 +07).
- The optical mapping also passed 20 repeated runs normally and 20 under 4× CDP CPU slowdown;
  no controller or A3 constants changed.
- The 0.105.0 source distribution and wheel rebuilt successfully; packaged UI asset hashes
  match the tested source. OpenAPI is version-only, schema remains 55, and `git diff --check`
  is clean.

Remaining differences are the ones above: A3's approved spring timing is preserved instead of
being retuned to the reference, and the implementation uses a restrained CSS rim while keeping
text sharp rather than reproducing native chromatic refraction. Human motion approval is still
required.
