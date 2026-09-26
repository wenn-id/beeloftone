# A6.0 — Modern workspace foundation

Baseline: `72d252b238ed816aefc754e514067fed742094a9`, PR #98, A5.2/A5.3 version 0.105.0,
schema 55, post-merge CI #157 PASS. Branch: `ui/apple27-a6-0-modern-workspace-foundation`.
A6.0 version 0.106.0; schema stays 55, no migration.

A5.2's macOS workspace and Liquid Glass environment are approved and frozen, A5.3's liquid
navigation lens and the sidebar approval utility are merged. What is still old is everything
*inside* the window: Produksi through Budget marketing are drawn in an enterprise
admin-dashboard language — bordered filter forms stacked above the content, dark uppercase
table header bands, `.state` boxes reading "Tidak ada data.", and buttons that all carry the
same visual weight.

A6.0 does not fix those pages. It builds the one shared system that later phases fix them
*with*, and it is deliberately inert until they do.

## Purpose and boundary

A6.0 is foundation-only:

- it adds one stylesheet of inner-workspace content primitives, `beeloft/static/workspace-primitives.css`;
- it adds a non-production fixture to review them in, `tests/fixtures/a60-workspace-primitives.html`;
- it changes **no** production workspace, **no** backend or business semantics, **no** schema,
  **no** route, and nothing in the approved shell.

The stylesheet is additive by construction. Every selector in it is a class name that no shipped
page uses, verified against `style.css`, `workspace.css`, `index.html` and `app.mjs`. Loading it
therefore changes the rendering of zero production pages today — that is asserted, not asserted-ish,
by `ZeroProductionImpactTest.test_primitives_are_inert_against_every_shipped_surface`, which fails
the build if any A6 name starts appearing in shipped markup outside a deliberate migration.

Three names in the phase brief's inventory were already owned by shipped surfaces. Taking them
would have silently redesigned those surfaces, including the frozen Command Center, so they use
cohesive alternatives instead:

| Brief name         | Used instead     | Why |
| ------------------ | ---------------- | --- |
| `.attention-panel` | `.attention-note` | Command Center owns `.attention-panel` (`style.css`, `#command-center-view`) |
| `.form-grid`       | `.field-grid`     | Legacy dialog forms own `.form-grid` |
| `.form-actions`    | `.field-actions`  | Legacy dialog forms own `.form-actions` |

The `.field*` family is the better name regardless: the grid, the fields, the help, the error and
the action row now read as one thing.

## Command Center is the quality floor, not the template

Command Center is now the minimum quality bar — no workspace may end up looking older than it.
It is emphatically not the layout to copy. The two have different jobs:

| | Command Center | Operational workspace |
| --- | --- | --- |
| Job | executive overview, decision-making | workflow, task, data |
| Reads | KPI → KPI → hero chart → modules | context → action → workflow/data → detail |
| Primary object | the number | the record |
| Density | generous, presentational | compact, operational |

So the workspace grammar is **context → action → workflow/data → detail**. A metric strip is
allowed where metrics genuinely help an operator decide what to do next; it is not a KPI row, it
is not four cards by default, and it never fabricates a trend or a comparison to fill space.

## Primitive inventory

57 primitives, all in `beeloft/static/workspace-primitives.css`.

**Page and heading** — `.workspace-page`, `.workspace-heading`, `.workspace-heading-copy`,
`.workspace-eyebrow`, `.workspace-title`, `.workspace-subtitle`, `.workspace-actions`,
`.workspace-section-title`, `.workspace-meta`

**Metrics** — `.metric-strip`, `.metric-card` (+ `-info` `-success` `-warning` `-danger`),
`.metric-icon`, `.metric-label`, `.metric-value`, `.metric-detail`

**Command bar** — `.command-bar`, `.command-search`, `.command-filters`, `.command-filter`
(+ `-quiet`), `.command-actions`

**Filters** — `.segmented-filter`, `.filter-chip`, `.filter-chip-count`

**Data surface** — `.data-surface` (+ `-scroll`), `.data-toolbar`, `.data-header`, `.data-row`,
`.data-cell` (+ `-numeric` `-tight`), `.data-primary`, `.data-secondary`, `.data-meta`,
`.data-actions`, `.data-column-secondary`

**Status** — `.status-chip` (+ `-info` `-success` `-warning` `-danger` `-neutral`), `.status-dot`

**Progress** — `.progress-meter`, `.progress-track` (+ `-success` `-warning` `-danger`),
`.progress-fill`, `.progress-value`

**Panels** — `.info-panel`, `.utility-panel`, `.attention-note` (+ `-critical` `-info`),
`.attention-note-copy`, `.attention-note-title`, `.attention-note-reason`

**States** — `.empty-state`, `.error-state` (each + `-title` `-copy` `-action`), `.loading-state`,
`.skeleton-line` (+ `-short`)

**Records and timeline** — `.record-list`, `.record-row`, `.record-row-copy`, `.record-row-aside`,
`.timeline`, `.timeline-item` (+ `-info` `-success` `-warning` `-danger`), `.timeline-time`,
`.timeline-event`, `.timeline-actor`, `.timeline-detail`

**Detail** — `.detail-grid`, `.detail-field`

**Scan foundation** — `.scan-surface`, `.scan-target`, `.scan-state`, `.scan-recent`, `.scan-fallback`

**Forms** — `.field-grid` (+ `-single`), `.field` (+ `-wide`), `.field-label` (+ `-optional`),
`.field-help`, `.field-error`, `.field-actions` (+ `-end`), `.field-check`

**Actions** — `.action-primary`, `.action-secondary`, `.action-quiet`, `.action-destructive`,
`.icon-action` (+ `-danger`)

## Tokens

23 new semantic tokens, none colliding with an A1 foundation or A5 shell token
(`PrimitiveInventoryTest.test_tokens_do_not_collide_with_the_shell_or_the_foundation`).

**Geometry and rhythm**, theme-invariant: `--workspace-control-height` (34px),
`--workspace-control-radius`, `--workspace-surface-radius`, `--workspace-panel-radius`,
`--workspace-panel-gap`, `--workspace-section-gap`, `--workspace-row-height`,
`--workspace-cell-x`, `--workspace-cell-y`

**Materials**, resolving to the A1 opaque materials: `--workspace-surface`,
`--workspace-surface-secondary`, `--workspace-toolbar`

**Structure and interaction**, tuned per theme: `--workspace-divider`, `--workspace-edge`,
`--workspace-hover`, `--workspace-selected`, `--workspace-shadow`

**Translucent grades**, read only inside the `@supports` gate: `--workspace-surface-tint`,
`--workspace-surface-secondary-tint`, `--workspace-toolbar-tint`, `--workspace-toolbar-highlight`,
`--workspace-toolbar-blur`, `--workspace-toolbar-saturation`

Two deliberate decisions worth recording:

- **34px is its own step**, not the shell's 40px `--control-height` and not the 36px compact step.
  A toolbar that manipulates a table should read denser than a page's primary buttons. Coarse
  pointers get the full 44px back (see accessibility).
- **Text consumes `--ink` / `--ink-2` / `--muted`**, never the raw `--color-label-*` roles those
  aliases normally point at. A5.2 re-tunes exactly those three aliases for the workspace
  environment in both themes — light `--ink:#102045` / `--muted:#4a6080`, dark `--ink:#f1f6ff` /
  `--ink-2:#e3edfa` / `--muted:#c0d0e4` — because workspace text sits on a translucent canvas over
  the wallpaper rather than on a flat page. Consuming the aliases is what keeps A6 text identical
  to neighbouring shipped surfaces instead of introducing a second, dimmer palette in dark mode.

## Material hierarchy

Everything outside the single `@supports` block is **solid** and is the real, finished rendering.
Translucency is a bounded enhancement applied afterwards, withdrawn under
`prefers-reduced-transparency`, and overridden entirely under `forced-colors`. This is A1/A4's
policy reused, not a second policy.

| Layer | Material | Alpha |
| --- | --- | --- |
| Page content | transparent, environment-aware canvas | — |
| Primary data surface | near-opaque; legibility first | 0.92 |
| Secondary panel | controlled translucency | 0.80 |
| Command bar | restrained Liquid Glass, `blur(18px) saturate(1.25)` | 0.78 |

There is exactly **one** blurred surface in the whole file — `.command-bar` — asserted by
`MotionAndPerformanceTest.test_repeated_surfaces_are_never_backdrop_roots`. No row, chip, cell,
metric card, panel, list item or timeline item is ever a backdrop root.

## Table and list strategy

Tables stay tables. What A6 replaces is the frame, not the element.

- one rounded near-opaque surface, `overflow:hidden`, thin `--workspace-divider` hairlines, no grid lines;
- a quiet header: `--muted` ink on the subtle material, medium weight, **sentence case** — the
  dark uppercase `letter-spacing:.07em` band is the single strongest "old admin panel" signal in
  the product and is exactly what this removes;
- rows at a comfortable 52px minimum that grow when a secondary line is present, hover and
  `aria-selected` states, status and progress integrated into cells, contextual actions in the row;
- three text weights per row: `.data-primary` (the business identifier), `.data-secondary`
  (SKU/metadata), `.data-meta` (quiet timestamps and numbers).

`.data-surface` is `position:relative`, and that is load-bearing rather than cosmetic: the surface
clips and scrolls, `.visually-hidden` is `position:absolute`, so without a positioned ancestor every
screen-reader-only label inside a header cell or icon-only action resolves against the initial
containing block, escapes the clip, and adds its offset to the root scroller. That was a measured
horizontal document overflow at 390px and 320px, not a theoretical one.

`.record-list` / `.record-row` is the non-table member of the same family, for workspaces a table
would misrepresent: integrations, approval requests, people, activity, recommendations. `.timeline`
is the foundation for activity, audit trail and sync history — the rail is drawn once on the list
and the marker is a pseudo-element, so a 500-row audit page paints one border and no extra nodes.

## Form and control strategy

`.field-grid` → `.field` → (`.field-label`, control, `.field-help` | `.field-error`) →
`.field-actions`. Consistent control geometry, label above field, help and error owned by the field
rather than floating near it. Errors are carried by `aria-invalid` and `aria-describedby`, not by a
class, so the semantics do the work and the tint follows.

Nothing in the form primitives is positioned or sized relative to the page, which is what makes
§28 hold: A6.x can drop a `.field-grid` into a sheet, a popover or the existing `<dialog>` without
rewriting a single visual rule. A6.0 deliberately does not implement the sheet system.

Filter controls belong to one family. `.command-filter` puts label and select inside a single
bordered shell so four filters read as four controls rather than eight boxes, and
`.command-filter-quiet` hides the label text visually while keeping the `<label>` real.

## Action hierarchy

Four weights, so a page cannot end up with six controls of equal priority:

| Primitive | Use | Treatment |
| --- | --- | --- |
| `.action-primary` | the one genuinely primary action | accent fill, compact, native-like — not a full-width SaaS CTA |
| `.action-secondary` | Muat ulang, Export, Buka detail | neutral surface, hairline border |
| `.action-quiet` | Reset, low-emphasis navigation | transparent until hover |
| `.action-destructive` | operations that actually destroy | soft danger tint + danger edge, never red-for-emphasis |
| `.icon-action` | low-frequency contextual row actions | 28px square, quiet, 44px on coarse pointers |

Confirmation behaviour is unchanged; `.action-destructive` is presentation only.

## Status and progress grammar

One chip system: `.status-chip` with a low-saturation tint and a readable foreground drawn from the
existing semantic tokens, plus `.status-dot` — which is not decoration. The dot is the redundant,
non-colour channel that keeps state readable under `forced-colors` and for colour-blind operators.
No status meaning is changed anywhere; the chips are a re-presentation of labels the pages already
produce.

One progress grammar: a 5px `.progress-track` with `.progress-fill` and the number beside it.
Brand blue is the default because "in progress" is the normal case; `-success` only where the data
genuinely means completion, `-warning`/`-danger` only where it genuinely means trouble. There is no
native element that can be styled to this reliably across engines, so the track is a `div` carrying
the real `progressbar` role with live `aria-valuenow`/`min`/`max` and a name.

## Responsive behaviour

A6.0 introduces **no new breakpoint** and reuses the shell's own 1240 / 980 / 650
(`test_responsive_rules_reuse_the_shells_own_breakpoints`).

- **≤1240** — tighten rhythm before dropping anything: cells to 12px, rows to 48px.
- **≤980** — `.data-column-secondary` may leave (opt-in per page), `.data-surface` scrolls
  horizontally, and `.data-surface>table` takes a **`44rem` minimum width**. The floor is in `rem`
  and not `px` on purpose: at 200% text the columns grow with the text instead of re-crushing at
  twice the size. Without it, `width:100%` plus `overflow-wrap:anywhere` let a column collapse to
  about one character per line — measured at 390px, `SKU-CMB-30-NVY` broke across five lines.
- **≤650** — search takes its own row, filters and actions span the width, `.record-row` wraps
  (tile and title stay together on line one, the status/meta/action group falls to line two),
  detail and field grids go single-column, the timeline stacks.

Tables are **not** globally converted to cards. A surface whose data relationships need a table
scrolls; a page that can preserve meaning stacked opts into `.record-list` deliberately. Each A6.x
migration chooses.

`.record-row-copy` uses `flex:1 1 0`, not `auto`. Flexbox breaks lines using each item's
*hypothetical* main size before flex-shrink is applied, so `min-width:0` cannot keep a
content-sized item on the line; at 320px/200% the copy's max-content base did not fit beside the
tile and wrapped below it, orphaning the tile on its own row. A zero basis always fits, then grows.

## Accessibility

- **Focus** — one grammar, `outline:2px solid var(--focus)`. Offset is `-2px` inside surfaces that
  clip their own overflow, where an outset ring would be cropped invisible. Covered on rows, record
  rows, chips, icon actions, filter selects and toolbar controls. `outline:none` appears once, on
  the inner filter control whose ring is drawn on the shared wrapper instead, and
  `test_focus_is_never_suppressed_without_a_replacement` proves every suppression has a
  `:focus-visible` replacement.
- **Forced colours** — system keywords only, no product hex. Surfaces, bars, chips, rows, headers,
  progress, attention notes and the timeline rail all gain real borders; `.progress-fill` becomes
  `Highlight`; chip selection stays distinguishable; the status dot stays painted. Nothing depends
  on a background colour to carry meaning.
- **Reduced transparency** — withdraws the enhancement and never enables one. Dense data surfaces
  return to the fully opaque `--material-content`, because table readability is not a place to
  trade anything away.
- **Reduced motion** — every transition in the file is inside
  `@media(prefers-reduced-motion:no-preference)`. Movement is removed, state is not: selection,
  progress values and focus all survive.
- **Touch targets** — a pointer question, not a width question. `@media(pointer:coarse)` restores
  `--workspace-control-height` to `--touch-target-min` and takes chips and icon actions to 44px, so
  a 1024px tablet gets real targets while the approved compact desktop density is preserved.
- **200% text** — verified at 320px with `font-size:32px` on the root; no horizontal overflow, the
  tile stays beside the title, the table scrolls, and all workspace text scales.
- **Semantics** — native `table`/`thead`/`th[scope]`/`tbody`/`tr`/`td`, `button`, `select`, `input`,
  `label`, `form`, `dl`/`dt`/`dd`, `ul`/`li`. No `role="table"`, `role="row"`, `role="button"` or
  other div-role recreation. The single ARIA role used is `progressbar`, which has no styleable
  native equivalent, and it carries real values.

## Light and dark

Dark is tuned, not inverted, and not an afterthought. Dividers and hover become light alpha because
that is how a dark surface shows structure; the tints hold the dark content colour slightly off full
opacity so the wallpaper reads as depth rather than haze behind the data. Nine theme-sensitive
tokens are asserted to differ between themes, and the three geometry tokens are asserted *not* to be
redeclared in dark. Theming is by `:root[data-theme=dark]` attribute — the product's existing
mechanism — and `prefers-color-scheme` is deliberately absent so nothing can disagree with the toggle.

WCAG contrast is computed arithmetically in Python for both themes, for `--ink`, `--ink-2` and
`--muted` over both workspace surfaces, and for all four status-chip foregrounds over their own soft
tints. All ≥4.5:1.

## Performance rules

- `backdrop-filter` on the command bar and nowhere else. Never on rows, chips, cells or list items —
  material lives at container level.
- No `@keyframes`, no `animation`, no `requestAnimationFrame`, no `setTimeout`, no `setInterval`, no
  script of any kind. A6.0 adds zero JavaScript: the lens budget pinned by earlier phases is
  re-asserted unchanged (6 RAF / 7 setTimeout / 0 setInterval application-wide; 3 RAF / 3 cancel in
  the lens region).
- The loading treatment is opacity on the existing `aria-busy` lifecycle flag plus a **static**
  skeleton. No shimmer, because a shimmer needs keyframes.
- Transitions use only the product's `--motion-*` and `--ease-standard` tokens; a raw `150ms`
  anywhere fails the contract test.

## QA fixture

`tests/fixtures/a60-workspace-primitives.html` is evidence, not a feature.

It lives under `tests/` and deliberately **not** under `beeloft/static/`, so it is never mounted by
the `StaticFiles` route, never packaged by `package-data = static/*`, never reachable from the
application and never part of any navigation. Browser QA opens it over `file://`. It loads the three
real shipped stylesheets by relative path, so what is reviewed is the actual cascade the product
renders rather than a copy of it. All data in it is obviously synthetic; no production page gains
fake data from this file. `QaFixtureTest.test_the_fixture_is_not_production` enforces all of this.

It demonstrates the page heading, metric cards, command bar, segmented filters, data table, status
chips, progress, empty state, error state, loading state, attention states, form controls, timeline,
record rows, detail grid, scan foundation and the full action hierarchy.

Human visual approval was given on the fixture at 1440 light, 1440 dark, 1024 light, 768 light,
390 light and 320 at 200% text.

## DO / DON'T

**DO** workflow-first layouts: context → action → workflow/data → detail.
**DON'T** copy Command Center to every page — no hero charts, health rings, four-KPI rows or
marketplace modules because Command Center has them.

**DO** compact command bars that feel like a native toolbar.
**DON'T** stack giant form fields above the content and call it a filter.

**DO** modern data surfaces with quiet headers and thin dividers.
**DON'T** remove tables just because cards look modern.

**DO** use the metric strip where metrics genuinely help an operator decide.
**DON'T** force four metrics onto every workspace, or fabricate a trend to fill a card.

**DO** give one action per view primary weight.
**DON'T** give every button equal visual priority, and don't use red for emphasis.

**DO** put semantic tint on the icon tile and the status chip.
**DON'T** tint whole cards — a strip of five metrics must not become five coloured panels.

**DO** keep `backdrop-filter` at container level.
**DON'T** put it on a row, a chip or a cell.

**DO** explain empty states, and offer the action only when the workflow and the viewer's
permission actually allow it.
**DON'T** ship "Tidak ada data." in a bordered box, and don't invent a CTA a viewer cannot use.

**DO** reuse the existing request lifecycle for loading presentation.
**DON'T** add polling, fake delays or a spinner animation.

## Migration contract for A6.x

Later phases **consume** these primitives. They do not each invent a visual system.

| Phase | Scope | Consumes immediately |
| --- | --- | --- |
| A6.1 | Produksi | heading, metric strip, command bar, segmented filter, data surface, status chips, progress, row actions, empty/error/loading |
| A6.2 | Bahan baku + Master SKU | data surface, command bar, detail grid, field primitives, info panel |
| A6.3 | People + Scan workflows | record list, scan surface foundation, field primitives, metric strip |
| A6.4 | Analytics | metric strip, data surface, info panel, segmented filter |
| A6.5 | Tanya Beeloft + Integrasi | record list, attention note, utility panel, status chips |
| A6.6 | Activity + Audit + Backup | timeline, record list, data surface, command bar |
| A6.7 | Purchasing + Budget marketing | record list, detail grid, field primitives, action hierarchy, status chips |
| A6.8 | Consistency / responsive / accessibility audit | the whole system, across every migrated page |

Rules for every A6.x migration:

1. Reuse a primitive or extend this file — never add page-specific modern CSS to unrelated legacy
   selectors.
2. When a page adopts a primitive, remove the legacy class it replaces in the same change, so the
   two languages never coexist on one surface.
3. Never change filter semantics, status meaning, column meaning, error text or request lifecycle
   while changing presentation.
4. Do not add a motion system. A3 and A5.3 own motion.
5. Re-run the A6.0 contract and browser tests; the zero-impact test will legitimately need its
   allowance updated as pages migrate, and that update is the record of what was migrated.

## Status after A6.8 (program complete)

A6.1–A6.8 are complete; the Apple-27 modernization program ends here and there is no A6.9. Every
primary sidebar destination and the Produksi order detail is an A6 workspace page (Command Center
stays the frozen A5 golden composition). A6.8 added no primitive and did not edit this file's
stylesheet: it modernised the one shared `#dialog` and `formDialog()` chrome in a contained block
at the end of `style.css`, moved the remaining high-visibility sheets (PO fulfilment, incoming QC,
supplier payment, production change, payroll approval, "PR untuk order ini") onto A6.7's request
grammar by name, merged the approval-status tones into one map, and removed 21 legacy selectors
proven dead. Details, the legacy-hook inventory and the deferred non-visual debt are in
`docs/apple27-final-consistency-polish.md`. Later work is a bug, feature, workflow, performance,
security or release-stabilisation change, not an A6 phase.

## Changed files

- `beeloft/static/workspace-primitives.css` — new, the whole primitive system.
- `beeloft/static/index.html` — one `<link>`, loaded after the shell.
- `tests/fixtures/a60-workspace-primitives.html` — new, non-production review fixture.
- `tests/test_apple27_modern_workspace_foundation_contract.py` — new, 31 static contract tests.
- `tests/browser_a60_workspace_foundation.cjs` — new, focused browser module.
- `tests/browser_smoke.cjs` — one registration line.
- `tests/test_apple27_liquid_lens_contract.py` — pinned version expectation 0.105.0 → 0.106.0.
- `pyproject.toml`, `beeloft/api.py`, `docs/openapi.json` — version 0.106.0 only.
- `docs/apple27-modern-workspace-foundation.md` — this report.
