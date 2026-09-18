# Production visual refinement

Baseline: `df3694c21dbc9ad44dc7c2c7114bba4a34040418` (merged main).
Branch: `ui/premium-production-refinement`.

## Diagnosis recorded before implementation

The 1440 × 900 baseline places the first order near y=750. Four 130px KPIs have
large gaps between their labels and figures. The filter panel takes three rows,
including an oversized search button. Filters, explanatory text, table and
pagination read as separate surfaces. Zero issues receives a full-width red
alert treatment. At 390px, four single-column KPI cards push the search below
the viewport. The existing typeface, blue accent, SVG vocabulary, chip radius,
native controls, role checks and mobile navigation should stay.

Reading: an operational workspace for Indonesian production teams, using the
existing Beeloft design language; ENERGY 2 / RHYTHM 2 / MOTION 1.

## Design decisions

- A Production-only 1360px maximum column keeps wide screens readable while
  remaining fluid on laptops.
- The existing Segoe UI/system font gains a 30px heading and compact metadata
  to separate page, section, record and supporting information without a font dependency.
- Compact KPIs retain the four original definitions and tabular figures; a soft
  blue WIP surface emphasizes the central operational quantity without inventing data.
- Existing 18px decorative sprite glyphs gain small blue tiles for visual weight.
- Zero issues uses a neutral control with a success glyph; positive counts use
  amber with explicit text because the endpoint provides a count, not severity.
- One bordered working surface contains the two-row desktop toolbar, explanatory
  text, order list and pagination. Its low shadow separates it from the canvas.
- Search precedes its submit button in DOM order; filters follow, with a tertiary
  reset action. All labels and the stage explanation remain available.
- A softly grounded table header and ruled rows improve scanning; container queries
  reflow records when the available workspace or enlarged text needs more space.
- Existing light/dark tokens and the 20/12/10/8px radius system stay authoritative.
- Production metadata uses the existing `--ink-2` text token: the original muted
  token falls below 4.5:1 on the canvas, WIP tint and row-hover surface. Native
  input focus also gains a visible outline using the shared focus token.

## Scope

No API, schema, metric definition, transaction, session, actor binding, pending
draft, idempotency, QC or rework logic changes. Command Center, sidebar, login,
Materials, People, Approvals, Analytics and unrelated dialogs are not redesigned.
All application CSS added here is scoped to `#board-view`.

## Before/after review

All captures and tests use disposable synthetic/demo databases. No operational
database was read or modified. The review database contains 29 CONTOH/DEMO orders
with varying quantities, owners, dates and stage balances. The zero/positive
issue captures use count-only intercepted responses; all other displayed fields
remain the real demo endpoint response. These are test fixtures, not Beeloft data.

The eight committed viewport screenshots are in `docs/screenshots/production-premium/`:

| View | Before | After |
| --- | --- | --- |
| 1440 × 900 light | `before-1440-light.png` | `after-1440-light.png` |
| 1440 × 900 dark | `before-1440-dark.png` | `after-1440-dark.png` |
| 390 × 844 mobile | `before-390.png` | `after-390.png` |
| Zero issues | Included in baseline | `after-zero-issues.png` |
| Active issues | Local baseline matrix | `after-active-issues.png` |

The task's local `outputs/production-premium/` directory additionally contains a
before/after contact sheet, full baseline and final viewport matrices, loading,
empty, HTTP error, viewer, scrolled mobile toolbar/list, 200% text toolbar/list,
and 320/390px create-dialog captures. All image dimensions are at most 2000px.
Reduced motion was enabled for the final review captures so theme transitions
cannot leave misleading intermediate colors in screenshots.

The first desktop order now starts around y=662 instead of y=751. At 390px,
two KPI rows replace four; at 320px, cards use one column to protect text space.
The desktop working column remains fluid until reaching its 1360px cap.

## Responsive, theme and accessibility checks

- Chromium layout assertions pass at 1920px (bounded width), and at 1440, 1280,
  1024, 768, 390 and 320px in light and dark mode.
- At 200% text size, checked 1440, 390 and 320px in both themes. The test uses
  `document.documentElement.style.fontSize = '200%'`, matching the repository's
  text-resizing convention, rather than screenshot scaling or CSS transform zoom.
- No page-level horizontal overflow or clipped Production controls, figures,
  labels or record cells in those checks. No overflow hiding was introduced.
- Container queries reflow KPI and order grids based on the space available
  after the sidebar and enlarged text. The sidebar itself is unchanged.
- Text contrast assertions require 4.5:1 for the sampled Production text,
  including figures, units, toolbar controls, metadata, status chips and order
  titles. Both themes pass, including the hovered row encountered in testing.
- Native labels, decorative non-focusable SVGs, keyboard order, visible focus,
  44px mobile control heights, Escape dismissal, and reduced motion pass.
- The create-order dialog fits at enlarged text; 320/390px dialog captures were
  also reviewed. No dialog styling or transaction handlers changed.
- Dark surfaces resolve the existing canvas/surface/primary/status tokens.
  Table headers, controls, KPI tiles and hover surfaces retain separation.

## Functional invariants and regression coverage

`tests/browser_production_premium_ui.cjs` is registered in `browser_smoke.cjs`,
which is invoked by `python tests/run_browser.py --channel chromium`.

The new module checks API-to-KPI value/unit equality, sprite sourcing and
decoration, max width, KPI hierarchy, compact toolbar geometry, tertiary reset,
one list surface, shrink-wrapped chips, zero/positive issue presentation and
shortcut behavior, search/reset, status/PIC/stage query parameters, real
next/previous pagination, refresh, opening records, viewer restrictions,
loading/empty/503/recovery, expired-session handling, themes, reflow and focus.

The existing full browser suite exercises actual order creation, lost-response
retry, actor binding, changed sessions, pending drafts, logout failure,
QC/rework/reinspection and unrelated workspaces. No business test was removed.

Intentional test update: the shared UI test's former `width > 200px` assertion
required the superseded single-column mobile KPI composition. It now checks
two complete, non-overlapping rows within the summary bounds, plus unclipped
labels/figures. Existing border, filter, dialog, role and Command Center checks
remain. The original glyph size/alignment assertions are unchanged.

Command Center before/after screenshots differ only in a small timestamp region
at x=1266..1274, y=168..177. Its layout, content surfaces and sidebar are untouched.

## Tests actually run

Environment: Windows, CPython 3.12.13, Node 24.18.0, Playwright 1.63.0 and its
bundled Chromium. Python dependencies are isolated in a task-local environment.

| Command/check | Result |
| --- | --- |
| `python -m unittest discover -s tests -v` | PASS, 507 tests in 862.132s, exit 0 |
| `python -m pip check` | PASS, no broken requirements |
| `python -m compileall -q beeloft` | PASS |
| `node --check beeloft/static/app.mjs` | PASS |
| `node --check beeloft/static/client.mjs` | PASS |
| `node tests/test_client.mjs` | PASS, client/CSV/date-boundary groups |
| `python tests/run_browser.py --channel chromium` | PASS, complete suite, 70 PASS reports, no JS errors, exit 0 |
| Focused Production browser module | PASS against source and installed wheel |
| `python -m build` | PASS, wheel and sdist built |
| Install wheel outside checkout | PASS, separate `wheel-env/Lib/site-packages/beeloft` |
| Packaged HTTP asset verification | PASS, index/CSS/app/client bytes equal source and installed resources |
| `git diff --check` | PASS |

The first complete browser attempt passed the existing modules and found four
low-contrast cases in the newly added Production check. The scoped metadata
token fix resolves them; the complete suite was rerun afterward.

## Antislop delivery review

- Hard gate PASS: real demo/API metrics, functional controls, explicit states,
  keyboard checks, contrast assertions, and responsive overflow checks.
- Purpose gate PASS: every major visual choice is explained above; no added
  charts, marketing claims, icons from dependencies, gradients or animation.
- Liveliness PASS: ENERGY 2 / RHYTHM 2 / MOTION 1; stronger WIP emphasis, tighter
  summary rhythm, and a distinct operational list surface use Beeloft's vocabulary.
- Quality locks PASS: existing tokens/radius ladder, native controls, both themes,
  scoped CSS, synthetic-only evidence and preserved operational behavior.

## Limitations and intentional exceptions

- This is Chromium verification; Firefox/WebKit were not run.
- The row layout deliberately reflows earlier than the old table, according to
  container width and font size. At 320px KPIs return to one column.
- The zero-issue shortcut still opens the blocked-order filter, preserving the
  existing navigation even when its result is empty.
- HTTP errors retain the previous page-count text with pagination disabled, as
  before. This refinement does not change request/session state semantics.
- Visual approval is still a human review step. Patterns have not been applied
  to any other workspace. No push, PR, merge or deployment is performed.
