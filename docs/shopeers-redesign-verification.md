# Shopeers visual reconstruction verification

Branch: `ui/shopeers-redesign`

## Golden reference

The Shopeers AI-powered B2B eCommerce analytics dashboard by Dipa Inhouse:
<https://dribbble.com/shots/26628350-Shopeers-AI-Powered-B2B-eCommerce-Analytics-Dashboard>

That shot is the visual specification for this change. It was absent from the branch, so it was retrieved from the
original source and measured before any implementation work.

**The artwork is deliberately not redistributed in this repository.** To reproduce the comparisons below, save the
shot from the link above to `docs/reference/shopeers-dashboard-reference.png`; that path is git-ignored.

The artboard measures 1441 x 1033 inside a 1600 x 1200 presentation matte, so the reference describes a
1440px-wide full-bleed application; the grey surround is Dribbble matting and is not reproduced.

## Measured reference versus delivered implementation

Values were sampled from the reference with Pillow and read back from the running app with
`getBoundingClientRect` / `getComputedStyle` at a 1440 x 1024 viewport.

| Property | Reference | Delivered |
| --- | --- | --- |
| Header height | 72px | 72px |
| Sidebar width | 256px | 256px |
| Content padding | 32px | 32px |
| Working column | 1120px | 1120px |
| KPI card | 263 x 131, 22px gap | 264 x 130, 22px gap |
| Decision column | 687px | 687px |
| Operational rail | 411px | 411px |
| Grid gap | 22px | 22px |
| Card radius | 16px | 16px |
| Navigation row | 40px, 10px radius | 40px, 10px radius |
| Button shape | 40px pill | 40px pill |
| Canvas | `#f4f5f8` | `#f4f5f8` |
| Card border | `#ebecef` | `#ebecef` |
| Primary | `#2d5efb` | `#2d5efb` |
| Active navigation surface | `#eef3fd` | `#eef3fd` |
| Navigation edge marker | `#3c5dff`, 3px | `#3c5dff`, 3px |
| Page title | ~26px / 700 | 26px / 700 |
| KPI figure | ~32px / 800 | 32px / 800 |

## Visual comparison passes

1. **Macro layout.** Rendered a desktop screenshot and compared it with the reference. Corrected the shell
   framing, the sidebar/brand column and its shared vertical rule, the KPI proportions, and the main grid ratio.
2. **Visual system.** Retuned tokens, typography, radii, border and shadow intensity, the primary blue, neutral
   surfaces, and icon sizing. Fixed a horizontal overflow at 200% text zoom (an inline account element that could
   not shrink, and status labels that could not wrap).
3. **Pixel-level polish.** Aligned both grid columns to the same top edge by visually hiding the rail's section
   heading, compacted the decision rows from 103px to 81px, tightened card padding and metric rhythm, corrected
   the mobile header (legacy `≤650px` rules were stacking the wordmark and stretching the avatar), and replaced
   the text arrows in back controls with sprite icons.
4. **Further passes.** Reworked the hero card so it is always populated from real data, widened its chart slot,
   pinned the approval CTA to the bottom of the sidebar as in the reference, coloured the breakdown glyphs, and
   allowed bar-chart labels to wrap to two lines instead of truncating.

## Command Center mapping

| Reference surface | Beeloft data |
| --- | --- |
| Four KPI cards | `production.active_orders`, `approvals.pending_count`, `status.attention_count`, `finance.current.net_profit`, with footers and chips from `overdue_orders`, `open_issues`, `pending_amount`, `critical_count`, `integrations.attention_count`, `snapshot_at` |
| Hero analytics card + nested breakdown | `status.attention_count` with a bar chart of real exception counts per `attention[].kind`, and a Kritis / Perlu perhatian / Informasi split with bars proportional to real counts |
| List / table surface | `Perlu perhatian` — the `attention[]` queue, critical first, with a column header, dashed row rules, a severity tile, and the existing action button |
| Gauge | `quality.first_pass_yield_percent` (integer display; the exact value stays in the metric list) |
| Progress / meter treatments | `rework_quantity / in_progress_quantity` and `capacity.required_minutes / available_minutes` |
| Three-up breakdown | `workforce.present / leave / absent` |
| Status area | `integrations.systems[].health` badges |
| AI panel | Tanya Beeloft, opened through the existing `ai-brain` action |

No trend line, target, period-over-period delta, placeholder identity, or new business metric was invented.
Where the reference shows a time series that Beeloft has no dataset for, the slot carries the closest real
distribution or ratio instead.

## Scope safeguards

- **The Shopeers reconstruction commit itself modifies no test file and no backend file.** It changes no Python
  module, API response schema, database schema, accounting rule, inventory rule, or production rule. It touches
  only `beeloft/static/index.html`, `beeloft/static/style.css`, `beeloft/static/app.mjs`, `.gitignore`,
  `DESIGN.md`, and `docs/`.
- **The pull request as a whole does contain test updates**, inherited from the earlier redesign commit
  (`169d937`) on this branch. Those updates adapted the acceptance suite to that commit's responsive
  sidebar/navigation changes and cover `tests/test_web.py` plus eleven `tests/browser_*.cjs` modules:
  `browser_smoke`, `browser_management_command_center`, `browser_ai_investigation`, `browser_bom`,
  `browser_bundle_scanning`, `browser_payroll_approvals`, `browser_product_external_mappings`,
  `browser_production_quality_insights`, `browser_reservations`, `browser_returns_adjustments`, and
  `browser_workforce_approvals`. That commit changes no backend or business-rule file either, so the PR as a
  whole still leaves the backend, schema, and business rules untouched.
- `showCommandCenter()` still requests `/api/command-center` once, keeps its request/epoch/view race guards, uses
  only existing response fields, and keeps every `data-action` value, drill-down, and ordering.
- `app.mjs` changes are limited to markup produced for presentation plus new pure render helpers
  (`svgIcon`, `commandGauge`, `commandMeter`, `commandSplit3`, `commandBars`, `commandHeroBars`,
  `attentionDomainRows`) and the matching reset of the new hero container.
- All element IDs, accessible names, `data-command-snapshot` / `data-command-attention` attributes, heading
  semantics, `hidden`-based visibility, and the `.attention-panel` wider than `.snapshot-panel` relationship are
  preserved.
- Navigation destinations are unchanged: the same 24 buttons with the same IDs, labels, and handlers. The twelve
  analytics destinations moved into an expanded disclosure group and remain visible and clickable.

## Verification results

- Python: `python -m unittest discover -s tests` — **340 tests passed** in 204s on the final code.
- Browser: the **complete Playwright acceptance suite passed end to end** on the final code, all 58 modules,
  with `assert.deepEqual(errors, [])` confirming no JavaScript errors.
- JavaScript: `node --check` on `app.mjs` and `client.mjs`; `node tests/test_client.mjs` passed (escaping, dates,
  exact-write retry, read-only requests, auth header, structured errors, CSV access).
- Responsive: no horizontal overflow at 320, 390, 768, 1024, and 1440 CSS pixels.
- 200% text zoom: no horizontal overflow at 390px. The base font size is now expressed in `rem`, so text zoom
  scales the interface instead of being pinned by an absolute `px` body size.
- Keyboard: focus rings on all controls, drawer Escape dismissal with focus return to `Menu`, focus return after
  dialog close, and the first sidebar `.nav-item` focusable.
- Dark theme: full token set re-declared for `[data-theme='dark']` and captured during QA.
- `pip check` reported no broken requirements; `compileall` and `git diff --check` are clean.
- Contrast: primary `#2d5efb` measures 5.11:1 on white in both directions; muted text `#6b7385` measures 4.75:1,
  so secondary copy meets WCAG AA even though the reference's lighter grey would not.

### Defect found and fixed outside the redesign surface

`tests/browser_workforce_approvals.cjs` asserts that the People approvals dialog does not overflow at 200% text
zoom. That assertion **failed identically on the unmodified branch code** in this environment, because the CSS
targets Segoe UI and the fallback font here is wider, so single-word labels in the dense metric strip forced
layout overflow. It is fixed by letting those labels break and by reducing the strip's padding on narrow
viewports. Verified by running the module against unmodified and modified code in isolation.

## Screenshots

- [Command Center desktop](screenshots/command-center-desktop.png)
- [Command Center mobile](screenshots/command-center-mobile.png)
- [Command Center at 200% text zoom](screenshots/command-center-200-text.png)

All three are regenerated by the acceptance suite itself, so they always reflect the tested build.

## Regression report

No functional, API, permission, accessibility, JavaScript, or overflow regressions were detected. The one
initially observed browser failure — focus return after closing the People dialog from the mobile drawer — did not
reproduce on re-runs or in faithful isolation; it stems from a pre-existing microtask race between the sidebar
handler and the dialog opening, which this change does not touch.
