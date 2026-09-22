# Apple-27 A1 — Visual & Material Foundation

Baseline: `36c287a2d386f59c42a974e6a05f71694a841537` (merged A0, PR #88).
Branch: `ui/apple27-a1-material-foundation`. Application 0.99.0; schema 55.
[DESIGN.md](../DESIGN.md) establishes the current direction; the
[A0 audit](apple27-native-parity-audit.md) remains the architecture authority.

## Token ownership

`beeloft/static/style.css` has one canonical foundation and one dark palette override.
Responsive root blocks change spacing only. Foundation tokens feed semantic materials,
then existing shared primitives; workspace-specific composition remains unchanged.

`--font-ui` uses `-apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, "Noto Sans",
sans-serif`. Apple platforms use the installed system UI font, Windows uses Segoe UI,
and other platforms use system fallbacks. No downloaded font or proprietary Apple
asset is shipped. Audit monospace remains separate; the hand-authored SVG sprite
continues to use `currentColor` without optical or path changes.

| Type role (`--type-*`) | Size | Shared use |
| --- | --- | --- |
| page-title | 1.75rem | h1 |
| section-title | 1.125rem | h2, dialog heading |
| card-title | 1rem | h3 |
| body | .9375rem | body |
| control | .875rem | buttons, fields |
| caption | .8125rem | hints |
| data | 2rem | summary figures |
| metadata | .75rem | eyebrows |

Existing workspace type variants remain where they express an established hierarchy.
Sizes stay relative to root text size; A1 does not mechanically replace every selector.

## Color and solid materials

`--color-canvas`, `content`, `content-subtle`, `content-raised` and `content-sunken`
define neutral grounds. `label-primary`, `label-secondary` and `label-tertiary` define
foreground emphasis. `separator` and `separator-strong` separate structure;
`control-border` provides stronger field edges. `accent`, `accent-hover`, `accent-soft`,
`on-accent` and `focus` cover selection, actions and focus. Danger, warning and success
each have foreground, soft ground and edge roles; existing state text remains present.

Light uses a neutral `#f5f5f7` canvas, white content and `#f0f0f3` subtle ground.
Dark is intentionally tuned: `#151517` canvas, `#202023` content, `#29292d` subtle
ground and `#303034` raised ground. Labels, accent, semantic states, focus, edges and
shadows have explicit dark values, rather than inversion. The contract test checks
4.5:1 for labels on the neutral grounds and state text on its soft ground, plus 3:1
for focus and field borders on content/subtle/raised grounds.

| Material (`--material-*`) | Source | Existing consumer |
| --- | --- | --- |
| canvas | color-canvas | body/workspace canvas |
| content | color-content | cards, lists, forms, states |
| content-subtle | color-content-subtle | secondary panels, hover |
| raised | color-content-raised | raised cards |
| functional-chrome-solid | color-content | masthead, sidebar |
| floating-solid | color-content-raised | native dialog, notice |

Every material resolves to an opaque color in both themes. `--chrome-tint`,
`--chrome-border`, `--chrome-highlight` and `--chrome-shadow` establish optical roles
for A4. Tint and highlight do not activate an optical renderer in A1. Borders and
solid grounds remain sufficient without those future effects.

Solid surfaces are the valid baseline and permanent fallback for unavailable effects,
disabled transparency, performance limits or accessibility needs. A4 may add supported,
optional translucency over these roles. A1 adds no `backdrop-filter`, blur, refraction,
WebGL/WebGPU, or speculative transparency preference query.

## Geometry and elevation

`--radius-prominent:24px` shapes floating dialogs; `--radius-content:20px` shapes
existing cards; `--radius-control:12px` shapes buttons, fields and navigation;
`--radius-compact:8px` shapes badges; `--radius-pill:999px` remains for circular icons,
avatars and meters. Nested panels keep their existing 14px (and smaller inner) radii
within 20px cards. The hierarchy is Beeloft's tuning, not a private Apple constant.

`--shadow-content`, `--shadow-raised` and `--shadow-floating` provide increasingly
separated, quiet elevation with explicit dark tuning. Separators do the structural
work; ordinary cards do not gain floating shadows.

Shared controls use `--control-height:40px`, `--control-height-compact:36px`,
`--touch-target-min:44px`, `--control-radius:var(--radius-control)` and
`--control-padding-x:.875rem`. Touch layouts preserve larger targets, including the
menu and header actions. Focus rings appear immediately and keep control geometry.
Form semantics and native interaction stay unchanged.

## Compatibility and phase boundary

Legacy names are aliases, not another palette: `--canvas/--bg/--app-bg` resolve to
material canvas; `--surface/--surface-subtle` to content materials; `--ink/--ink-2/--muted`
to label roles; `--line*` to separators; `--primary*` to accent roles. State, radius
and shadow aliases follow the same direction. Production's existing scoped `--muted`
alias still selects the secondary label, without introducing a private color.

Visible changes are the calmer neutral palette, native font order, stronger theme-aware
focus/field edges, rounded rectangular controls, larger dialog shell radius and quieter
shadows. Command Center, Production and the remaining workspaces retain their layout,
content, routes, permissions and formulas. Application JS, client transport and markup
are unchanged, including PR #87's inert close and capture submit guards.

All six motion durations and three easings remain unchanged, with the existing reduced
motion path. A1 implements no lens, spring controller, sheet/popover, new navigation,
glass or business behavior. A2/A3/A4 require their own phase authorization.

## Validation

`tests/test_apple27_foundation_contract.py` checks canonical ownership, native fonts,
relative type roles, opaque materials, dark parity, alias direction, geometry,
elevation, contrast and excluded renderers/assets. Existing motion contract tests
remain the authority for unchanged timing and lifecycle.

Browser contracts retain structural, focus and dialog safeguards. Only the intentional
radius/palette expectations change. Populated synthetic QA covers all 27 destinations,
1440 light/dark, 1024, 768, 390, 320 and 320 at 200% text, including reduced motion and
the closing-dialog regression. Review screenshots and logs are local temporary artifacts,
not repository assets. Final run results are recorded after verification.
