# A3 spring continuity CI investigation after A5

Investigation baseline: `72177a232b59d182ce4909c92c0b095a9c5bdc93` (`origin/main`, verified after fetch).
Branch: `investigate/a5-spring-continuity-ci`.
A4 comparison: detached worktree at `077a2090289f920232b4a40367e229d7baad14ca`.
Application version remains **0.103.0**, schema **55**.

## CI evidence and scope

- [CI #144](https://github.com/wenn-id/beeloftone/actions/runs/35830537235) passed on A5 runtime commit `7ca3d1088068045335255e6369b25ccb3e9ecf66`.
- [CI #145](https://github.com/wenn-id/beeloftone/actions/runs/35832731756) failed at the velocity-continuity coast assertion, reporting 0.0px, on `01239dfe51f442c71bbe702666d990df8358f74e`.
- [CI #146](https://github.com/wenn-id/beeloftone/actions/runs/35832869313) passed core tests and failed the same browser assertion, reporting 0.4px, on merged main.

Git confirms the only change between #144 and #145 is `docs/apple27-command-center-golden.md`.
The docs follow-up and merged main have identical trees. The A3 browser module is byte-identical
between A4 and A5. The controller region used for the deterministic replay is also identical:
SHA-256 `3f915fd2b51984c84de720a90c7e498717ab95df15d3d66d8f9ba71083ba9749`.

## Method

The original assertions ran unchanged in an interleaved sequence: A4, A5, A4, A5.
Each run used a fresh browser context and an isolated demo database/server for its baseline.
Temporary instrumentation was appended only to the browser's intercepted module response;
it did not edit either production file. It wrapped retarget and integrator calls to record
before/after state, wall-clock times, RAF timestamps, and destination changes. A temporary
copy of the browser test collected those records alongside its existing DOM samples.
Both baselines receive identical probes. Their overhead and the local environment mean these
rates compare the two baselines; they are not estimates of the CI failure probability.

The environment was Windows on an Intel i5-12500H, Node 24.18.0, Playwright **1.63.0**,
and bundled Chromium **153.0.8010.12**. Playwright matches CI; Windows and Node differ from
the Ubuntu/Node 22 CI runner. Python used the existing pinned audit virtual environment.
Normal means no CPU throttling; moderate means Chromium CDP CPU rate 2; heavier means rate 4.
These are reproducible renderer slowdowns, not claims of measured whole-machine CPU utilization.
A rate-8 pilot hit the normal-travel intermediate-sample assertion before case D on both baselines,
so the main heavy comparison uses rate 4. No other test suites ran concurrently with the matrix.

Raw evidence and temporary runners are in
`C:\Users\acer\AppData\Local\Temp\beeloft-spring-ci`.
`comparison.jsonl` records every run, case-D sample index and lens rectangle, frame timestamps,
physical velocities, target state, and retarget/step events. `analyze.py` produces distributions;
`verify_traces.py` independently checks the measured integrator updates against the spring law.
The pilot is separate from the 20-run matrix.

## Repeated comparison results

All entries are 20 module attempts. Every failure in this matrix was case D's
`coast > 15` assertion; failed attempts stopped there, and successful attempts completed
the remaining cases. There were no failures at other assertions in this matrix.
Coast and `beforeStep` columns are minimum / median / maximum, in CSS pixels.

| Load | Baseline | Pass | Coast failure | Coast min / median / max | `beforeStep` min / median / max |
| --- | --- | ---: | ---: | --- | --- |
| Normal (1x) | A4 | 20/20 | 0/20 | 40.022 / 47.075 / 48.204 | 32.099 / 34.197 / 73.028 |
| Normal (1x) | A5 | 20/20 | 0/20 | 44.550 / 47.869 / 48.308 | 33.356 / 34.347 / 36.259 |
| Moderate (2x) | A4 | 16/20 | 4/20 | 0.000 / 25.564 / 45.460 | 33.356 / 73.103 / 121.854 |
| Moderate (2x) | A5 | 19/20 | 1/20 | 11.510 / 25.094 / 46.769 | 33.362 / 73.185 / 115.444 |
| Heavy (4x) | A4 | 0/20 | 20/20 | 0.000 / 0.000 / 0.000 | 83.054 / 151.588 / 179.920 |
| Heavy (4x) | A5 | 0/20 | 20/20 | 0.000 / 0.000 / 0.000 | 120.893 / 164.787 / 179.458 |

The next table uses milliseconds. The RAF-gap column is the distribution of each run's
largest case-D integrator timestamp gap. Reference latency is from retarget returning to
`samples[index + 1]`; click-to-reference includes navigation and the pending sync frame.

| Load / baseline | Largest RAF gap min / median / max | Reference latency min / median / max | Click-to-reference min / median / max |
| --- | --- | --- | --- |
| 1x A4 | 7.100 / 13.750 / 14.300 | 0.300 / 0.750 / 1.900 | 7.800 / 10.950 / 16.200 |
| 1x A5 | 7.100 / 7.300 / 14.100 | 0.200 / 0.500 / 1.100 | 6.900 / 10.250 / 18.900 |
| 2x A4 | 13.900 / 34.700 / 55.600 | 0.900 / 1.950 / 3.000 | 17.300 / 36.000 / 58.900 |
| 2x A5 | 13.900 / 27.800 / 69.500 | 0.400 / 1.550 / 3.000 | 16.300 / 32.850 / 73.400 |
| 4x A4 | 76.200 / 104.250 / 138.700 | 0.400 / 4.350 / 6.100 | 67.000 / 92.250 / 122.500 |
| 4x A5 | 69.500 / 104.050 / 145.800 | 1.400 / 4.150 / 8.300 | 73.400 / 98.300 / 123.800 |

Normal intervals were about 6.94ms (the local 144Hz cadence). Gaps above 14.5ms appeared
45 times in moderate A4, 41 in moderate A5, 279 in heavy A4, and 282 in heavy A5. This is
evidence of missed nominal frame opportunities, not a compositor trace proving the exact
number of dropped presentation frames. The controller caps integration at 32ms as designed.
**No case-D >200ms stall path occurred in any of the 120 runs.**

All 120 reversals preserved every physical position, dimension, and velocity field exactly.
Each changed `targetCy` from 667 to 40. The measured `vy` before and immediately after retarget
was positive, with the following minimum / median / maximum in px/s:

| Load / baseline | `vy` before = `vy` after |
| --- | --- |
| 1x A4 | 5495.774 / 5526.883 / 5925.716 |
| 1x A5 | 5510.441 / 5519.989 / 5850.971 |
| 2x A4 | 4334.086 / 5546.974 / 5843.847 |
| 2x A5 | 5130.649 / 5564.140 / 5937.393 |
| 4x A4 | 2183.311 / 3000.947 / 4354.170 |
| 4x A5 | 2183.311 / 2995.915 / 3957.532 |

An independent recomputation of all **4,097 non-settling integrator callbacks** matched
the captured position and velocity updates exactly (maximum numerical difference 0).
That check includes the real substep size and frame cap; the explicit settle path is
excluded from the force-law comparison.

## Why rendered distance is not the invariant

The test interrupts after sample index 4. That is a frame count, not a fixed physical position,
velocity, or elapsed time. Before applying the reverse destination, the pending motion callback
can also advance toward the old destination. A slower cadence therefore changes both the state
at reversal and the distance that later rendered samples can observe.

A replay executes the actual controller source with deterministic RAF timestamps and the real
render function, using the same 627px vertical destination change and 40px-to-34px size change.
It applies the reversal after four integration frames. Both baselines produce identical results:

| Cadence | Physical `cy` at reversal | `vy` before and after retarget | Rendered coast |
| --- | ---: | ---: | ---: |
| 144Hz | 154.656px | 5517.451px/s | 48.005px |
| 120Hz | 193.594px | 5871.716px/s | 40.840px |
| 60Hz | 380.060px | 5095.112px/s | 15.093px |
| 30Hz | 579.466px | 2018.675px/s | 0.000px |

This is not an exact replay of undocumented CI timestamps. It proves that the existing threshold
has almost no margin at 60Hz and can fail with perfectly preserved velocity at slower cadences.
The measured rectangle also includes the velocity-driven size morph, so its top edge is not
the physical center used by the integrator.

In all 120 traces, `samples[index + 1]` occurred after retarget but before the
next integration step. It had **not** already consumed the coast after retarget. Thus a delayed
first reference sample is not required to explain the observed failures. Subsequent frame
intervals can pass through the velocity sign change before another rendered observation.

For example, A4 moderate run 1 failed with 2.993px coast. Its `beforeStep` was 80.857px;
the reversal preserved `cy = 409.9525271640676` and `vy = 4737.746141918528` exactly while
changing `targetCy` from 667 to 40. The reference sample was read 2.3ms after retarget returned.
The next RAF interval was 20.8ms: its substeps ended at `vy = -1331.3424659775606`.
The next observed top edge was only 2.993px farther down. No velocity reset or >200ms stall
occurred; the sampled trajectory agrees with the force law.

## Classification and A5 visual cost

**Outcome B: test observation defect, exposed by frame cadence and scheduler load.**
Current main reproduces, but A4 also reproduces: the normal rates match, moderate A5 is not
worse in this sample, and both fail every heavy attempt. Their coast and frame-gap
distributions do not identify an additional A5 rendering cost as the cause. There is no
evidence of a spring-controller regression (Outcome D).

The conditional presentation-ablation step was not triggered: A5 did not reproduce more
often than A4. No ambient, chart, DOM, or shadow probe was applied, and no A5 presentation
change is proposed. This does not establish that every A5 dataset has identical paint cost.
The repeated matrix uses demo data, whereas the full suite accumulates additional records;
the CI runner's exact frame history was not captured. Those limits do not affect the direct
state invariant or the mutation proof.

## Test-only correction and mutation proof

`tests/test_navigation_spring.cjs` executes the shipped controller region in Node's built-in
VM with a test-owned RAF queue. It adds no dependency and exposes no state in the application.
It establishes real integrated motion on all four physical axes, then checks:

1. Retarget preserves current position, dimensions, and velocity exactly, while replacing
   target geometry and identity.
2. Retarget keeps the existing pending frame and timestamp instead of restarting the clock.
3. The next 1/240-second integration step matches an independently calculated semi-implicit
   Euler update with mass 1, stiffness 520, and damping 40, using the preserved state and new target.
4. The spring settles exactly at the latest target, writes that rectangle, and leaves no pending RAF.

The check runs with 144Hz, 60Hz, and uneven 7/33/18/80ms pre-reversal histories. These timestamps
exercise the production controller itself; the force law is not replaced by a test implementation.
`tests/browser_navigation_spring.cjs` invokes this check in case D and retains its real browser
reversal, geometry validity, and exact arrival check. Cases A/B continue to assert many rendered
intermediate positions and velocity deformation. Cases C and E–L remain unchanged, covering
rapid retarget, both approval rebases, collapse, scroll, resize, frame gaps, mobile drawer,
reduced motion, mid-flight preference changes, session reset, and zero idle RAF.

Mutations were applied only to in-memory copies of the real source passed to the final test.
Each mutant ran 20 times; the unmodified control passed 20/20. No mutation was written to production.

| Mutation | Detected |
| --- | ---: |
| Ordinary retarget zeros `vx` and `vy` | 20/20 |
| Ordinary retarget zeros only `vy` | 20/20 |
| Cancel/restart from rest, all velocities zero | 20/20 |
| Reversal teleports current position to the target | 20/20 |
| Retarget restores stale destination and identity | 20/20 |
| Settle writes the old vertical destination | 20/20 |
| Velocity reset deferred until the next integration callback | 20/20 |
| Retarget resets the frame timestamp | 20/20 |

No spring parameter, settle threshold, substep, frame cap, stall threshold, morph cap, or
morph speed changed. The old 15px assertion was replaced by a stronger direct invariant,
not lowered to a smaller distance.

## Validation and final status

Final uninstrumented spring-module runs passed **20/20 normal** and **20/20 moderate**.
Each used a fresh page and the existing isolated demo servers; no debug code was appended.
The temporary runner ran the complete final module, including its deterministic physical check.
No failures or page JavaScript errors were recorded. Evidence: `final-repeats.jsonl` and
`final-repeats.log` in the evidence directory above.

The final validation gate is complete. `python -m unittest discover -s tests -v` ran
**637 tests, all OK** (`python-full.log`). `python -m pip check` reported no broken
requirements and `python -m compileall -q beeloft` was clean. `node --check` accepted
`beeloft/static/app.mjs` and `beeloft/static/client.mjs`; `node tests/test_client.mjs`
and a standalone `node tests/test_navigation_spring.cjs` both passed. Because the change
is test-only, the full Chromium suite ran twice against the final files
(`browser-full-1.log`, `browser-full-2.log`), each ending in the full
`Browser QA PASS` line with no JavaScript errors. Both runs include the A3 spring module
and its `preserved momentum` case. Application version remains **0.103.0**, schema **55**,
and `git diff --check` is clean; no production file or OpenAPI definition changed.

Environment commands use
`C:\Users\acer\AppData\Local\Temp\beeloft-a0-audit\venv\Scripts\python.exe` and
`--playwright-module C:\Users\acer\AppData\Local\Temp\beeloft-spring-ci\node_modules\playwright`.
The script runner needs the checkout on `PYTHONPATH`; an initial invocation without it stopped
before starting any browser checks (`ModuleNotFoundError: beeloft`). Setting `PYTHONPATH`
to the checkout corrects the local invocation without changing the repository.

## Files changed and working-tree status

Branch `investigate/a5-spring-continuity-ci` at `72177a232b59d182ce4909c92c0b095a9c5bdc93`,
not pushed, no PR opened. Three entries, all test or documentation:

| Path | Status | Content |
| --- | --- | --- |
| `tests/test_navigation_spring.cjs` | new | Deterministic velocity-continuity proof; runs the shipped controller region under a test-owned RAF clock at 144Hz, 60Hz, and uneven 7/33/18/80ms histories. |
| `tests/browser_navigation_spring.cjs` | modified | Case D no longer asserts a fixed rendered coast; it calls the deterministic check, keeps the real browser reversal, and asserts exact arrival at the latest target. Cases A/B/C and E–L unchanged. |
| `docs/apple27-spring-continuity-ci.md` | new | This report. |

`git diff --check` is clean. Version `0.103.0` (`beeloft/api.py`) and schema `55`
(`beeloft/store.py`) are untouched. No spring constant, settle threshold, substep,
frame cap, stall threshold, morph cap, or morph speed was modified. The `coast > 15`
assertion was replaced by a stronger invariant, not lowered.
