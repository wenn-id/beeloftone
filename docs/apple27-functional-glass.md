# Apple-27 A4: functional Liquid-Glass-like material

Baseline: **`bb29dac1099e05f96d40ea958feef1a3cfd430a1`** — the fetched `origin/main` when this phase
started, which merged A3 / [PR #91](https://github.com/wenn-id/beeloftone/pull/91). Main had not
advanced past the supplied SHA. Branch: `ui/apple27-a4-functional-glass`. Application **0.102.0** in
all three places that declare it. Schema **55**, no migration.

**This is a web approximation.** It is a CSS translucency-and-blur treatment on three surfaces. It is
not Apple's private or native compositor, not the Liquid Glass renderer, and there is no refraction,
dispersion, chromatic aberration, dynamic optical distortion, shader, WebGL or WebGPU anywhere in it —
all of those are asserted absent. What A4 delivers is a *bounded optical material on functional
chrome*, with the solid A1 rendering intact underneath it.

A4 changes **no JavaScript at all.** `beeloft/static/app.mjs` and `client.mjs` are byte-identical to
the A3 baseline, so the A3 spring is not merely "unchanged by agreement" — there was nothing to
change. The only runtime file A4 touches is `beeloft/static/style.css`.

## 1. Solid-first architecture

The order is the whole design. A1's solid materials are the unconditional base declaration; the
optical layer is one `@supports` group that an engine without backdrop filtering never reads.

```text
BASE RULES (no query of any kind)
  .masthead      background: var(--material-functional-chrome-solid); 1px var(--chrome-border)
  .app-sidebar   background: var(--material-functional-chrome-solid); 1px var(--chrome-border)
  .sidebar-actions            background: var(--surface)  + 16px fade to var(--surface)
  .nav-selection-lens         background: var(--color-accent-soft); 1px var(--color-separator-strong)
  #approvals[aria-current]    solid accent-soft selected fallback
        |
        v
@supports ((backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px)))
        translucent tint -> bounded blur + saturation -> optical edge -> highlight -> quiet shadow
        |
        +-- @media (max-width: 980px)                    drawer edge retuned
        +-- @media (prefers-reduced-transparency: reduce) everything above returns to solid
        |
        v
@media (forced-colors: active)   filters and decoration off, system colours, outlined selection
```

Deleting the `@supports` group leaves a complete, polished, opaque shell — not a degraded one. That is
asserted directly: `test_the_base_material_needs_no_supports_query_to_be_usable` checks that no
unconditional declaration references `var(--chrome-tint…)` or `var(--lens-glass…)` and that each of
the three surfaces still declares a background and a border on its own.

The block is placed *after* the responsive rules so the drawer's geometry at ≤980px is already settled
before the material lands on it, and before the accessibility overrides so those still win.

## 2. Feature detection

```css
@supports ((backdrop-filter:blur(1px)) or (-webkit-backdrop-filter:blur(1px))){ … }
```

Exactly one gate holds the entire optical layer, and it names both properties because the `or` is a
support test rather than a vendor preference. Both spellings are then declared on every glassed
surface, standard second so it wins where both are understood. There is **no** scripted user-agent
detection, no `navigator.vendor`, no Chromium assumption; the contract asserts their absence.

`prefers-reduced-transparency` is deliberately *not* the gate. Its availability is limited, so using
it as the switch would leave engines that do not implement it with glass they cannot opt out of. It is
only ever used to withdraw the enhancement — which the A1 contract now enforces as a usage rule.

## 3. Optical tokens

A1 reserved `--chrome-tint`, `--chrome-border`, `--chrome-highlight` and `--chrome-shadow`. A4
activates them rather than forking a second palette, and adds only the parameters the material needs.
`--chrome-border` keeps its A1 meaning — the opaque structural edge shared with the notice and the
dialog — so the translucent boundary is its own role instead of a redefinition. `--chrome-highlight`
and `--chrome-shadow` are consumed exactly as they were declared.

Every token below is either `--chrome-*` or `--lens-glass-*`; the contract asserts there is no third
family.

| Token | Light | Dark | Role |
| --- | --- | --- | --- |
| `--chrome-tint` | `#ffffffd1` (α .82) | `#202023d1` (α .82) | translucent functional-chrome foreground |
| `--chrome-tint-dense` | `#ffffffeb` (α .92) | `#202023f0` (α .94) | sticky approval plate, same family, denser grade |
| `--chrome-glass-edge` | `#1d1d1f24` (14% ink) | `#ffffff24` (14% white) | 1px material boundary that reads what is behind it |
| `--chrome-highlight` | `#ffffffb3` *(A1)* | `#ffffff14` *(A1)* | 1px inset specular |
| `--chrome-shadow` | `var(--shadow-raised)` *(A1)* | dark-tuned *(A1)* | quiet separation under the masthead |
| `--chrome-blur` | `20px` | — | theme-invariant |
| `--chrome-saturation` | `1.3` | — | theme-invariant |
| `--lens-glass-tint` | `#e6f0ffd6` (α .84) | `#2a3f5ccc` (α .80) | selection body |
| `--lens-glass-edge` | `#0064d13d` (24% accent) | `#78b4ff52` (32% accent) | optical rim |
| `--lens-glass-highlight` | `#ffffffe0` | `#ffffff1f` | 1px inset specular |
| `--lens-glass-shadow` | `0 1px 2px #1d1d1f12, 0 4px 12px #0064d114` | `0 1px 2px #00000033, 0 4px 12px #00000040` | restrained lift |
| `--lens-glass-blur` | `14px` | — | smaller budget; applied in the approval context only (§7) |
| `--lens-glass-saturation` | `1.4` | — | theme-invariant, approval context only |
| `--lens-glass-cta-tint` | `#eff5fff2` (α .95) | `#22354ef0` (α .94) | denser grade for the approval card |
| `--lens-glass-cta-edge` | `#ffffff70` | `#ffffff4d` | rim on a dark saturated backdrop |
| `--lens-glass-cta-highlight` | `#ffffffe8` | `#ffffff52` | specular on that rim |

These are Beeloft optical tuning values. No claim is made that any of them matches an Apple constant.

**Blur radius and saturation are deliberately theme-invariant**, like A1's motion tokens, and the
contract asserts each is declared exactly once. That is not an oversight: it is what makes a theme
toggle unable to re-render or snap the optical filter (§9). Every *colour* role has an explicitly
tuned dark value, and the contract asserts that none of them equals its light counterpart — dark glass
here is tuned, never inverted.

The contract also pins the band: chrome blur must be 12–28px, lens blur 8–18px, lens blur strictly
smaller than chrome blur, and saturation >1 and ≤1.6. A 60px blur fails it.

## 4. Masthead

```css
.masthead{
  background:var(--chrome-tint);border-bottom-color:var(--chrome-glass-edge);
  -webkit-backdrop-filter:blur(var(--chrome-blur)) saturate(var(--chrome-saturation));
  backdrop-filter:blur(var(--chrome-blur)) saturate(var(--chrome-saturation));
  box-shadow:inset 0 1px 0 var(--chrome-highlight),var(--chrome-shadow);
}
```

A thin translucent plane. `position:sticky`, `top:0`, `z-index:20`, the three-column grid, the 72px
height contract, the brand, the workspace pill, the account controls, the theme and logout semantics
and the menu-toggle are all untouched — A4 is material treatment, not masthead recomposition.

This is the one glass surface with a genuinely changing backdrop, because workspace content scrolls
underneath it while it is sticky.

## 5. Sidebar

```css
.app-sidebar{
  background:var(--chrome-tint);border-right-color:var(--chrome-glass-edge);
  -webkit-backdrop-filter:blur(var(--chrome-blur)) saturate(var(--chrome-saturation));
  backdrop-filter:blur(var(--chrome-blur)) saturate(var(--chrome-saturation));
  box-shadow:inset -1px 0 0 var(--chrome-highlight);
}
```

**One material container for the whole column, not one material per row.** Hover stays a local opaque
token affordance, and the selected state stays the lens. Sticky desktop behaviour, independent
scrolling, the mobile drawer, `isolation`, the 256px column and every geometry A2/A3 measure are
unchanged; `backdrop-filter` does not affect layout, and the sidebar was already a positioned element,
so it remains the lens's containing block.

It carries **no separation shadow** — it is flush against the content column, where a shadow would be
noise rather than depth. The inset highlight sits just inside its own right edge so the boundary reads
as material thickness instead of a drawn line. At ≤980px the drawer is a horizontal panel, so the same
1px highlight moves to the edge that now reads as its lit top.

## 6. The sticky approval plate

`.sidebar-actions` was `background:var(--surface)` with a 16px fade above it. Against solid chrome that
was invisible; against glass it would have been an opaque rectangle that made the material look broken.

Both declarations now use `--chrome-tint-dense` — the same family, one grade denser — so the plate
reads as a slightly denser region of the same glass rather than a white card. Its purpose is preserved
exactly: at α .92 a navigation label scrolling behind it transmits at 8%, so the approval area stays
readable. **No second `backdrop-filter`:** one blurred surface per column, which is also the cheaper
choice. The contract asserts `.sidebar-actions` carries the dense tint and no filter, and deleting
those two declarations fails it.

## 7. The selection lens

```css
.nav-selection-lens{
  background:var(--lens-glass-tint);border-color:var(--lens-glass-edge);
  box-shadow:inset 0 1px 0 var(--lens-glass-highlight),var(--lens-glass-shadow);
}
```

The prominent glass object: the same single node A2 measures and A3 integrates, still anchored at
`left:0; top:0`, still `transition:none; animation:none`. No pseudo-element was added — the capsule
reads from its tint, its optical rim and one 1px inset specular, and the "liquid" quality already comes
from A3's spring and velocity stretch. There is no travelling shine, and the contract asserts that if a
pseudo-element is ever added it must be `pointer-events:none` with no animation.

### Why the travelling lens is translucent but not filtered

`.app-sidebar` has a `backdrop-filter`, which makes it a **backdrop root**. A filter on the lens can
therefore only sample what is painted beneath the lens *within* that root — which, in the navigation
column, is the sidebar's own flat tint. So a filter there produces **no visible blur at all**, while
still forcing the whole 256px column to be re-sampled on every frame the lens moves.

That cost was not theoretical. It dropped one frame early in each travel, and that was enough to
collapse A3's velocity-continuity measurement from ~15px of coast to under 1px — which is how the
regression was found: **A3's own browser contract failed.** The evidence is in §16.

The lens is therefore translucent in both contexts and *filtered only inside the approval card*, where
the blur has the CTA gradient and its dot texture to act on. Nothing was lost visually in the
navigation column, because the tint, the optical rim, the inset highlight, the shadow and A3's
velocity-derived deformation are what gave the lens its material there in the first place. This is also
what the phase brief's performance rule asks for: **one blurred surface per column, not nested blur
surfaces.**

The asymmetry between the two contexts is real, it is left visible, and no wallpaper was introduced to
disguise it. `test_no_filtered_surface_is_nested_inside_another_filtered_surface` now pins the rule so
the nested filter cannot come back unnoticed.

### Approval context

```css
.sidebar-cta>.nav-selection-lens{
  background:var(--lens-glass-cta-tint);border-color:var(--lens-glass-cta-edge);
  box-shadow:inset 0 1px 0 var(--lens-glass-cta-highlight),var(--lens-glass-shadow);
}
```

A tint swap on the **same DOM node** — no duplicate lens, no ghost, no second highlight object, and the
filter is inherited from the shared rule rather than redeclared. `.sidebar-cta` itself keeps its opaque
gradient: it is business content inside the chrome and is not glassified.

The denser grade is required, not decorative. The selected approval label is `--color-accent`, and over
a dark saturated gradient a lighter lens transmits too much of it: at α .94 the measured ratio was
**4.497:1**, below the 4.5 floor. The shipped value is a whiter, denser grade at α .95, measured at
**4.729:1**. The independent conservative model in `browser_motion_consistency.cjs` — which composites
the tint over *every* stop of the gradient and keeps the worst — reports 4.67:1.

## 8. Dark mode

Tuned, not inverted. The dark tint is the A1 dark content colour held at α .82 so the canvas reads
through it as depth rather than as smoke; the edge and highlight flip to light hairlines because that is
how a dark material catches light; the lens keeps a genuinely blue body so it stays distinct from the
hover state, from the chrome it sits on, and from the CTA gradient. Measured selected-label contrast on
the painted lens: **5.51:1** in the navigation column and **5.73:1** in the approval card.

## 9. Theme switching

No new glass timeline. The existing `html.is-theming` rule still animates exactly three properties —
`background-color`, `color`, `border-color` — and the contract asserts that list literally. Blur radius
is never transitioned, and because it is theme-invariant there is nothing for a toggle to re-render.

Measured across 31 consecutive frames of a real toggle: the chrome's filter string stayed
`blur(20px) saturate(1.3)` and the lens's stayed `blur(14px) saturate(1.4)` for every frame, and the
chrome's background alpha was `.82` throughout — **zero frames where it became opaque.** There is no
opaque → transparent → dark-glass flash; the tint colour simply crossfades with everything else.

## 10. Reduced motion

Motion and transparency are separate accessibility dimensions. The reduced-motion block does not touch
a single optical property — the contract asserts it contains no `backdrop-filter`, `background`,
`--chrome-tint` or `--lens-glass` — so a reduced-motion user still sees a selected glass lens. It just
snaps: measured travel between consecutive frames is exactly 0, the lens is on its target on the very
next frame, no compositor hint is requested, and idle frame work stays at zero.

## 11. Reduced transparency

Where the preference is available, the nested
`@media (prefers-reduced-transparency: reduce)` group returns `.masthead`, `.app-sidebar`,
`.sidebar-actions` and both lens contexts to the A1 solid materials with `backdrop-filter:none`,
`-webkit-backdrop-filter:none` and `box-shadow:none`.

It is **not the only route to solid chrome**, and the contract has a test by that name. Availability is
limited, so the real guarantee is the unconditional baseline outside the gate.

Behaviour was verified by emulating the feature through the devtools protocol (Playwright 1.63 has no
`reducedTransparency` option), and the structural guarantee is additionally read out of the browser's
own parsed stylesheet, so it does not depend on that emulation being available.

## 12. Forced colours

```css
@media(forced-colors:active){ … }
```

Outside the `@supports` group, so it also corrects the solid baseline's decorative edges. Both filter
spellings, every decorative highlight and every shadow are switched off; the surfaces fall back to
`Canvas` with `CanvasText` boundaries so the chrome keeps real edges.

The selection survives as an **outline** rather than a fill: `background:transparent` with
`border:2px solid Highlight`. A forced `Highlight` fill would have put the label on a system colour it
was never contrasted against; an outline keeps the label on the system foreground. `aria-current` is
untouched, and the focus ring remains the topmost indicator — verified with keyboard-driven focus so
`:focus-visible` genuinely matches.

## 13. Fallback hierarchy

| Environment | Result |
| --- | --- |
| No `backdrop-filter` support | Solid A1 chrome and solid accent-soft lens, automatically — the base rules are all that exist |
| Support + `prefers-reduced-transparency: reduce` | Solid, via the nested withdrawal |
| `forced-colors: active` | System colours, no filters, outlined selection |
| Support + reduced motion | **Glass kept**, travel removed |
| Normal supported environment | Bounded glass |

## 14. Content stays opaque

The core A4 boundary. `backdrop-filter` reaches exactly four selector atoms: `.masthead`,
`.app-sidebar`, `.nav-selection-lens` and `.sidebar-cta>.nav-selection-lens`. Nothing else — no
`.workspace-main`, card, KPI card, table, chart, form body, production row, scanner result, state
surface, dialog, notice, `.sidebar-cta` or Command Center panel.

This is asserted twice and two different ways: statically, as the set of selectors receiving an active
filter compared against the authorised set; and in the browser, by walking every element under
`.workspace-main` plus the dialog, notice, cards and tables and requiring the computed filter list to
be empty. No `filter: blur()` exists anywhere in the stylesheet either.

## 15. No invented backdrop

No wallpaper, scenic asset, stock photo or ambient gradient was added, and no business content
background was changed. The contract asserts the stylesheet contains no `url()` other than the
pre-existing in-document SVG paint-server reference, and that the static directory still contains no
image or font assets at all.

The consequence is worth stating plainly: **in light mode the material reads very quietly.** The
application's content is near-white on a near-white canvas, so a translucent white plane over it
composites to very nearly the same colour — the measured masthead pixel is `[253,253,254]` against a
`[245,245,247]` canvas. The material announces itself through its optical edge and highlight, and
through the blur when coloured content scrolls under the sticky masthead. Dark mode reads slightly more
because its canvas and content differ more. Behind the sidebar there is only the flat canvas, so that
column is subtler still. That is the honest result of the application's real painting hierarchy, and
A5 — not A4 — owns the stronger environmental depth the approved Command Center visual needs.

## 16. Measurements

Local, single-sample, headless Chromium 153.0.8010.12 on this container, against the disposable demo
fixture. Not CI, not Safari or Firefox verification, and not a hardware budget.

**The blur is real, and it is bounded.** A 3px repeating stripe pattern in the accent colour was placed
behind the sticky masthead and six samples were taken 1px apart across it:

| Chrome state | Luminance spread across the stripe pattern |
| --- | --- |
| Filtered (shipped) | **0.0069** |
| Same element with `backdrop-filter:none` | **0.2479** |

A 36× difference, so the smoothing is the engine's and not an artefact of the tint. Over that same
full-width accent pattern — far more saturated than anything the product actually paints across the
whole header — the masthead's quietest label held **5.20:1** and the brand **14.71:1**.

Selected-label contrast on the painted lens, sampled from real pixels:

| Destination | Light | Dark |
| --- | --- | --- |
| Command center (40px row) | 4.98:1 | 5.60:1 |
| Kapasitas produksi (34px analytics child) | 4.98:1 | 5.60:1 |
| Inbox approval (reparented into the CTA) | 4.73:1 | 5.73:1 |

`browser_motion_consistency.cjs` additionally re-checks all 27 destinations in both palettes against a
deliberately pessimistic composited model.

### Performance

A4's rule is: blur large static chrome sparingly, blur the small moving lens modestly, never blur
content trees, and never nest blur surfaces. In practice that is two full-size static surfaces
(1440×72 and 256×928) plus one 224×40 surface that is filtered only in the approval context.

#### The nested-filter regression, and how it was found

The first published attempt filtered the lens in **both** contexts. `browser_navigation_spring.cjs`
then failed its velocity-continuity assertion — `coast > 15` px — reporting 0.3–0.8px. That is A3's
contract catching an A4 performance regression, which is exactly what it is for.

Attributed by measurement rather than assumption. The module alone, alternating against a detached
worktree at the unmodified baseline `bb29dac`:

| Side | Result |
| --- | --- |
| A4 as first published | **3 failures / 3 runs** |
| Baseline `bb29dac` (no `backdrop-filter` at all) | **3 passes / 3 runs** |

Then isolating which surface was responsible, two runs each:

| Configuration | Result |
| --- | --- |
| Chrome filter + lens filter (as first published) | fail, fail |
| Lens filter removed, chrome filter kept | fail, pass |
| Chrome filter removed, lens filter kept | pass, pass |

And measuring the mechanism directly — one long travel, three samples per configuration:

| Configuration | Median frame gap | Max frame gap | Coast (needs > 15px) |
| --- | --- | --- | --- |
| Chrome 20px + lens 14px | 16.7ms | **33.4ms** | 0.5 / 0.7 / 0.5px |
| Chrome 16px + lens 12px | 16.7ms | 16.8–33.4ms | 15.1 / 15.3 / 0.7px |
| Chrome 12px + lens 10px | 16.7ms | 16.8–33.3ms | 15.1 / 15.2 / 15.2px |
| Sidebar filter off, masthead kept | 16.7ms | 16.8ms | 15.2 / 15.1 / 15.1px |
| Lens filter off, chrome kept | 16.7ms | 16.7–33.3ms | 15.2 / 15.2 / 15.1px |
| All filters off (control) | 16.7ms | 16.8ms | 15.2 / 15.1 / 15.1px |

The median frame gap never moves: this is not a general frame-rate collapse. It is **exactly one
dropped frame** early in the travel, and because A3's threshold sits at 15px with the measurement
landing at 15.1–15.2px, a single dropped frame is enough to flip it. Two things follow, and both are
worth recording:

1. **A4's fix.** The lens's filter was doing no visible work in the navigation column anyway (it
   samples the sidebar's flat backdrop root), so scoping it to the approval context removes the nested
   filter from the common path at no visual cost. Four consecutive runs of the module then passed.
   Simply shrinking the blur radii would have papered over the cause while weakening the material
   everywhere, so it was rejected.
2. **A pre-existing fragility worth a separate look.** A3's assertion has ~0.1–0.2px of margin above
   its threshold in this environment, so it is sensitive to any single dropped frame from any cause.
   That is not A4's to change here, and the assertion was left exactly as A3 wrote it.

An eight-destination burst with a click every 45ms, measured with a `PerformanceObserver` on `longtask`
and by frame-timestamp deltas:

| Condition | Frames | Median gap | Max gap | Gaps > 32ms | Long tasks |
| --- | --- | --- | --- | --- | --- |
| Glass enabled | 65 | 16.7ms | 16.8ms | 0 | none |
| Same burst with the filters forced off (control) | 66 | 16.7ms | 16.8ms | 0 | none |

Identical within measurement noise, with no long task reported in either. That is a single local
sample on a headless container, and **no 60fps claim is made from it** — what it does show is that the
optical layer did not introduce a measurable regression against its own control on this machine.

Idle cost is unchanged and is asserted rather than described: the browser modules wrap
`requestAnimationFrame`/`cancelAnimationFrame` before the application loads and compare pending and
executed counts across a 500ms settled window, under both motion preferences. Both counts are
unchanged and pending is zero — a settled filtered lens still performs **zero** frame work. The A3
spring remains the only continuous frame work during travel.

Not measured: GPU memory, paint traces, populated marketplace data, real mobile hardware, battery, and
Safari or Firefox performance. Those remain A12's, as the A0 audit scheduled.

## 17. Visual review

Fifteen screenshots at 1440 light/dark, 1024 light and 390 light/dark drawer, each for Command Center,
the Kapasitas produksi analytics child and Inbox approval, plus a 1440 video of Command Center →
Produksi → People → Kapasitas produksi → Inbox approval → Command Center followed by a theme toggle in
both directions. All are local temporary artefacts and are **not committed**.

Reviewed for the specific failure modes:

| Watched for | Result |
| --- | --- |
| Glass flicker | None; the filter string never changes at runtime |
| Muddy text | None; every measured label is ≥4.5:1 and dark labels stay crisp |
| Blur popping during spring travel | None; frame pacing matches the no-glass control exactly |
| Approval reparent flash | None; the same node changes tint in place |
| Dark-mode halo | None; the shadow is restrained and the highlight is 1px |
| Sidebar/footer seam | None; the dense tint and the existing 16px fade read as one material, and the last navigation row fades behind it instead of being cut by a plate |
| Theme-switch flash | None; 0 of 31 frames opaque, filter constant |

## 18. Version and contract

| Source | Before | After |
| --- | --- | --- |
| `pyproject.toml` `project.version` | 0.101.0 | **0.102.0** |
| `beeloft/api.py` `FastAPI(version=…)` | 0.101.0 | **0.102.0** |
| `docs/openapi.json` `info.version` | 0.101.0 | **0.102.0** |

A3's three-way binding in `test_openapi_contract.py` is what enforces this. `docs/openapi.json` was
regenerated with `python scripts/regenerate_openapi.py`, and the regenerated contract differs from the
baseline in **exactly one leaf value**, verified by walking both documents:

```text
total leaf differences: 1
  $.info.version: '0.101.0' -> '0.102.0'
```

221 paths, 253 operations, 85 component schemas, `securitySchemes`, top-level `security`, `tags`,
`servers`, the OpenAPI version and every `info` field other than `version` are identical. Schema
remains `PRAGMA user_version = 55`; there is no migration. `README.md` also had a stale "Versi aplikasi
0.100.0" left by A2 that no test binds; it now states 0.102.0.

## 19. Verification

`tests/test_apple27_functional_glass_contract.py` (22 tests) parses the stylesheet into a real rule
tree rather than searching it as text, because the questions worth asking are structural — which
selector received a filter, and inside which at-rules. It asserts the solid base declarations, the
single gate and both vendor paths, the authorised target set, the content exclusions, the
reduced-transparency and forced-colors paths, the token families and their light/dark parity, the
bounded blur/saturation band, genuinely translucent tints, the absent GPU/refraction renderer, the
unchanged A3 spring and morph constants, the pinned frame/timer inventory, and that the physics
renderer still writes only `transform`/`width`/`height` plus its temporary compositor hint.

It also pins the nested-filter rule from §16 in
`test_no_filtered_surface_is_nested_inside_another_filtered_surface`: restoring the filter on the
travelling lens fails four separate assertions.

**Twenty-six deliberate mutations were each confirmed to fail it**, including: glass escaping the gate
onto the base masthead; the `-webkit` path dropped; a card, and separately the dialog, becoming glass;
the reduced-transparency block deleted; the forced-colors block deleted; a 60px blur; the moving lens
blurring more than the static chrome; a CSS transition on the lens; the theme transition animating the
blur radius; the solid chrome baseline replaced by the tint; the solid lens fallback replaced by the
glass tint; the transparency preference used as the gate; a fully opaque tint; dark glass inherited
from light; a per-theme blur radius; `filter:blur` on content; a wallpaper asset; a retuned spring, a
retuned settle tolerance and a retuned morph cap; an optical `setInterval`; the renderer writing the
material per frame; a mouse-follow optical highlight; a second ghost lens node; a user-agent sniff
replacing the gate; an animated shine travelling across the lens; script writing an optical custom
property; and the sticky plate left opaque over the glass.

`tests/browser_functional_glass.cjs` measures the rendered result. It decodes element screenshots
inside the page, so a sample is the composited output of the filter, the tint, the border and
everything beneath. It covers: the unconditional solid baseline read from the parsed stylesheet; the
single gate with both properties; translucent, blurred, bounded masthead and sidebar in both themes;
the blur proof and bounded-translucency probe above; the lens in both contexts with measured 4.5:1
labels and distinguishable from hover and from the chrome; one lens node with stable identity across
Budget marketing → Inbox approval → Command Center; A3's intermediate frames, exact settle and
released compositor hint with glass on; rapid retarget correctness; zero idle frames; reduced motion
keeping the material while removing travel; reduced transparency restoring solid; the mobile drawer's
material, `inert` state, `aria-expanded` and focus restoration; and forced colours. For an engine
without backdrop filtering it asserts the solid contract instead of failing, and it never branches on
a browser name.

### Adapted existing contracts

A1's, A2's and A3's blanket "no glass exists" exclusions were **narrowed, not hollowed out.** The
mutation run above was repeated against all four modules to prove it: the rewritten A1 assertions catch
9 of the mutations, A2 catches 4 and A3 catches 7, independently of the A4 module.

- `test_apple27_foundation_contract.py` — the blanket `backdrop-filter` ban became a containment check
  with three parts: exactly one `@supports` group exists; no surface is translucent outside it (checked
  by excising the group with brace matching and re-scanning); and no content or dialog selector appears
  among the filtered ones. `filter: blur`, `@import` and `@font-face` stay banned outright. The
  `prefers-reduced-transparency` exclusion became a usage rule: the query appears once and only
  withdraws the enhancement. A note records why the opaque guarantee now lives in the `--material-*`
  roles rather than in `--chrome-tint`.
- `test_apple27_navigation_lens_contract.py` — asserts what A2's ban was actually protecting: the lens's
  solid accent-soft surface is unconditional, so a browser without filtering still renders a complete
  selected destination.
- `test_apple27_navigation_spring_contract.py` — the exclusion became the narrower and more important
  claim that the lens's own rule is unfiltered and that **no optical property is ever written by
  script**, so the integrator never competes with a material declaration. Its one-lens check now
  compares the *set* of lens selector atoms, because A4 legitimately groups the lens with the chrome in
  its fallback blocks; the set is still exactly two.
- `browser_motion_consistency.cjs` — this one was materially wrong after A4 rather than merely
  outdated. It read `getComputedStyle(lens).backgroundColor` and ignored the alpha, which would have
  silently inflated every contrast ratio for all 27 destinations. It now composites the tint over its
  real backing — the sidebar over the canvas normally, and in the approval context over *every* stop of
  the CTA gradient, keeping whichever gives the worst result — and branches the masthead assertion on
  whether glass is active while still requiring chrome and canvas to stay distinct. Confirmed to fail
  (1.842:1) when the lens tint is dropped to α .55, a value the static contract still permits.

## 20. What A4 did not touch, and the A4/A5 boundary

Backend endpoints, database schema, migrations, business formulas, money arithmetic, production, QC and
rework, approvals, auth/session/OIDC, idempotency, actor binding, pending recovery, stale-response
guards, role authorization and audit behaviour are all unchanged. `beeloft/api.py` is touched in one
place only, for the version string. Glass is presentation.

PR #87's dialog lifecycle is untouched: `inert` guard, capture-phase submit guard, `modalBusy`,
`unresolved`, `dialogVersion` and return focus are all as they were, and A4 changes no dialog
presentation at all.

A3's physics is frozen and, because no JavaScript changed, trivially so: `mass:1, stiffness:520,
damping:40`, `LENS_SETTLE_DISTANCE`, `LENS_SETTLE_SPEED`, `LENS_MAX_SUBSTEP`, `LENS_MAX_FRAME`,
`LENS_STALL`, `LENS_MORPH_MAX`, `LENS_MORPH_SPEED`, velocity preservation, cross-context rebase,
reduced-motion cancellation, idle RAF behaviour and centre-based state are all exactly as A3 left them.

**Explicitly not implemented, and left to later phases:** the Command Center golden conversion and its
stronger environmental depth (A5); workspace recomposition; floating or bottom navigation; a new
sheet/popover architecture (A7); new control primitives (A6); a new navigation IA; a new motion system;
WebGL, WebGPU, shaders, an actual refraction renderer or a chromatic-aberration engine.

A5 may need to revisit `--chrome-tint`'s α .82. That value was chosen so the masthead's quietest label
survives the most saturated surface the product paints *today*; a richer Command Center backdrop is
exactly the change that would make it worth re-measuring.
