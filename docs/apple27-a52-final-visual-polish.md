# A5.2 final visual polish - review evidence

Human visual approval was granted on 2026-09-24. This evidence accompanies the
A5.2 code review. A6 remains separate work.

## Captures

- [1440 light, equal-width comparison](screenshots/apple27-a52-polish/a52-reference-comparison.png)
- [1440 dark screenshot](screenshots/apple27-a52-polish/a52-1440-dark.png)
- [Complete light shimmer loop](screenshots/apple27-a52-polish/a52-shimmer-light.mp4)
- [Complete dark shimmer loop](screenshots/apple27-a52-polish/a52-shimmer-dark.mp4)
- [Review page](screenshots/apple27-a52-polish/review.html)

App screenshots are 1440 x 1000. The reference and app have equal displayed width;
aspect ratios are preserved. Both clips capture approximately 18 seconds of the
actual 17-second animation, including fade-out, quiet interval and reset. They
crop the left 260px without enhancing the effect. Encoded duration is 18.00s
(light, 450 frames) and 17.96s (dark, 449 frames). Populated captures use the
existing synthetic QA report, not live user data; the app ships no fake metrics.

## Exact material changes

Changes below are relative to the submitted revision #3.

| Light token | Revision #3 | Final polish |
| --- | --- | --- |
| `--workspace-body` | `#f5f9ff99` | `#f7faff80` |
| `--workspace-wash` | `linear-gradient(140deg,#ffffff75,#ffffff1f 65%)` | `linear-gradient(140deg,#ffffff4d,#ffffff12 65%)` |
| `--chrome-tint` | `#ffffff99` | `#ffffff7a` |
| `--chrome-glass-edge` | `#ffffff70` | `#ffffff99` |
| `--workspace-module` | `#ffffffb3` | `#ffffff9e` |
| `--workspace-module-edge` | `#ffffff85` | `#ffffff59` |
| `--toolbar-tint` | `#ffffff52` | `#ffffff33` |
| `--toolbar-edge` | shared chrome edge `#ffffff70` | dedicated `#ffffff26` |
| `--toolbar-highlight` | shared chrome highlight `#ffffffb8` | dedicated `#ffffff66` |
| `--module-shadow` | `inset 0 1px 0 #ffffff9c,0 4px 14px #263f5a05` | `inset 0 1px 0 #ffffff80,0 4px 14px #263f5a04` |

| Dark token | Revision #3 | Final polish |
| --- | --- | --- |
| `--workspace-body` | `#152334ce` | `#152334ad` |
| `--chrome-tint` | `#102640a8` | `#10264080` |
| `--workspace-module` | `#1a2d43bd` | `#1a2d438c` |
| `--toolbar-tint` | `#d3e8ff0e` | `#d3e8ff0a` |
| `--toolbar-edge` | shared chrome edge `#d1e7ff3d` | dedicated `#d1e7ff1a` |
| `--toolbar-highlight` | shared chrome highlight `#d1e7ff42` | dedicated `#d1e7ff29` |

Chrome and module tints transmit more of the unchanged landscape. Lowering both
the dark scene backing and module alpha prevents one opaque navy layer from
hiding the increased transparency of another. Dense tables and dialogs retain
their existing solid surface; reduced transparency restores solid materials.
Chrome blur stays 24px / 115% saturation; the scene blur stays 16px. No card or
ordinary moving lens gains a backdrop filter.

| Element | Exact final treatment |
| --- | --- |
| Toolbar family | Workspace, search, online, attention, account, logout, theme and appearance use the dedicated edge/highlight tokens above. Height 42px, radius 20px, soft shadow `0 2px 6px #2b4d7205` and focus-visible styling are unchanged. |
| Shell | Shadow changes from `0 22px 64px #142c4617,0 3px 12px #142c460a,inset 0 1px 0 #ffffffa6` to `0 24px 64px #142c4612,0 3px 12px #142c4608,inset 0 1px 0 #ffffffbd`; the light perimeter uses the brighter chrome edge above. |
| Sidebar group headings | Remain in the DOM, visually clipped to 1px with `clip-path:inset(50%)`, absolute positioning and overflow hidden. Group padding changes `3px 0 6px` to `14px 0 6px`; destinations, grouping and lens logic stay unchanged. |
| Approval utility, light | `linear-gradient(130deg,#eef7ff5c,#9ec7f34d)`, border `#ffffff55`, shadow `inset 0 1px 0 #ffffff94,0 4px 12px #294e7808`. Sticky backing changes `#eaf0f8` to `#d7e6f3` to prevent navigation text showing through the utility. |
| Approval utility, dark | `linear-gradient(130deg,#4070a333,#5196d91f)`, border `#c8e1ff24`, shadow `inset 0 1px 0 #c8e1ff38,0 4px 12px #06142312`; sticky backing stays `#243a53`. |
| Utility accent | Restores the existing decorative inbox glyph in a 22px tile at top 10 / right 12. Light fill `#d6eaff85`, ink `#1578dd`, highlight `#ffffffb3`; dark fill `#6aaaff21`, ink `#a9d2ff`, highlight `#c8e1ff42`. No new icon or action. |
| FPY ring | Static diagonal SVG gradient: light `#2377ee` / `#438ff6` / `#126ded`; dark `#6dadff` / `#9acaff` / `#579fff`; stops at 0 / .48 / 1. Radius, stroke width, dasharray, FPY value, denominator, period and accessible label are unchanged. Forced colors retains a solid Highlight stroke. |
| Hero balance | Desktop columns change `1.12fr 140px 1.35fr` to `1.06fr 140px 1.41fr`; existing gap, height and order remain. The trend gains about 21px at 1440. |
| Light shimmer | Gradient changes `linear-gradient(transparent,#ffffff99 48%,transparent)` to `linear-gradient(transparent 26%,#ffffffc2 48%,transparent 70%)`. The local peak alpha rises from 60% to 76% while the lit region narrows; the full rim is not brightened. |
| Dark shimmer | Gradient remains `linear-gradient(transparent,#c8e8ff66 48%,transparent)`. Both themes retain `17s linear -3s`, peak animation opacity .38, the same travel, 65% active / 35% quiet and invisible reset. Reduced motion remains a static rim. |

The KPI, two-module and four-module row geometry is identical to revision #3:
KPI y 174.39 / h 100.27, hero y 303.66 / h 185.5, middle y 501.16 / h 240, lower row
y 753.16 / h 214.19 at 1440. The only JavaScript-file change is static gradient markup
inside the existing SVG. All data/behavior code and `index.html` are byte-identical
to revision #3 when that gradient definition is removed.

## Remaining visible differences

- The retained logo, system font and original alpine scene differ from the artwork.
  Browser compositing does not reproduce its painted refraction and lighting.
- The retained real source captions and controls make the 1440 x 1000 view taller
  than the reference at equal width; the 900px-high view scrolls for lower content.
- Operational totals, real integration sources, FPY, capacity context and a single
  daily sales series remain in place of the reference's illustrated line names,
  health score, activity, growth percentages and paired channel bars.
- The sidebar utility keeps a backing beneath its translucent blue treatment so
  scrolling navigation cannot show through its text. Its position and purpose
  differ from the reference's product identity tile.

## Verification

64 Apple-27 contract tests and the unchanged deterministic spring test pass.
Focused Chromium checks pass for A2 navigation, A4 glass, Command Center golden
and A5.2 workspace, including eight widths, 320px/200% text, fallback materials,
focus, recovery guards and zero idle JS RAF. No spring tests were edited.
[Rendered Command Center contrast](screenshots/apple27-a52-polish/a52-contrast.json)
has a minimum of **4.525:1**; the A4 lens minimum is **5.014:1**, against
an unchanged 4.5:1 threshold. Wheel/sdist build and nine-file asset parity pass;
`git diff --check` passes. The full historical suite was not rerun for this polish.

The frozen A2/A3 source hash remains
`22cba20a874dd3e2630ff783a1f31f1d6f0a9d7c44eb99865a46f5aa2e205045`.
Version 0.104.0 and schema 55 remain;
A2/A3 constants and spring tests are unchanged. No backend, session, pending-write,
traffic-light, search, status or wallpaper-persistence behavior was edited.
