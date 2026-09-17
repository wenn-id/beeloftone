# UI unification verification

## What was verified against

- Baseline: `main @ 7a13ddaf159e5318928ac4fc02449ca26d805a20`.
- Branch: `ui/unify-sections-command-center`.
- Final HEAD at the time of this document: see the commit list below; the last commit is the
  one that adds these documents and the review artefacts.
- All runs used a disposable SQLite database created fresh by `python -m beeloft … demo` plus
  a synthetic enrichment pass. No business database was opened at any point.

## Screenshot workflow

An earlier attempt produced full-page screenshots tall enough to break the review tooling.
The workflow was rebuilt to be viewport-bounded and is now the only method used:

- Desktop captures are exactly **1440x900**; mobile captures are exactly **390x844**.
- No image is a full-page capture. A surface taller than the viewport is walked by scrolling
  its own scroll container and emitted as numbered sections (`--s1`, `--s2`, `--s3`).
- Every produced PNG is measured from its IHDR header. The final run: **467 images, all
  1440x900 or 390x844, zero over 2000px in either dimension**.
- Surfaces reachable only through the delegated `[data-action]` dispatcher are opened by
  injecting a throwaway probe button and clicking it, so the real production listener runs.
- Review was done in small batches. Each surface was reviewed from a per-surface contact
  sheet placing its four modes side by side at ~48% scale (desktop light, desktop dark,
  mobile 390, viewer read-only), with drill-down to the full 1440x900 image whenever
  something looked wrong. 78 per-surface sheets, all under 2000px.

## Manual review coverage

**78 of 78 inventory surfaces were reviewed**, each in desktop light, desktop dark, mobile
390px, and viewer/read-only. For every surface the review looked at content hierarchy,
surface nesting, filters and forms, status badges, loading/empty/error state, action
hierarchy, overflow and wrapping, dialog behaviour, and focus affordance where interactive.

| Group | Surfaces | PASS | FIXED | Not applicable |
| --- | --- | --- | --- | --- |
| A. Shell and core pages | 5 | 2 | 3 | — |
| B. Produksi chain | 19 | 18 | 1 | — |
| C. Gudang and marketplace | 11 | 11 | 0 | — |
| D. Bahan baku and purchasing | 7 | 5 | 2 | — |
| E. People and approval | 10 | 8 | 2 | — |
| F. Analitik | 12 | 11 | 1 | — |
| G. AI, integrasi, utilities | 14 | 14 | 0 | 1 viewer panel |
| **Total** | **78** | **69** | **9** | **1 mode** |

Capture result for the final run: 467 images, 0 failures, 0 page errors, 1 correctly skipped
panel (`Cadangan data` has no viewer rendering because the nav entry is admin-only).

## Defects found by looking at the render, and fixed

Nine surfaces changed as a result of the review rather than the plan, carrying ten distinct
defects — the board alone accounted for three. The first two were
introduced by this branch's own CSS and caught only by measuring the rendered result — the
class was present and "looked" applied in the source.

1. **Order status chip stretched to fill its cell.** A `.detail-meta span` rule blockified the
   chip. Measured `display: block`, width 243px in a 243px slot. Scoped the rule to the label
   slot; the chip is now `inline-flex` at 128px. Asserted in the new browser module.
2. **Status chips flattened inside list rows.** `.material-event p` (0,1,1) out-specified
   `.status-label` (0,1,0), so chips emitted as `<p class="status-label">` lost their type
   scale and neutral tone. The body-copy rule now excludes chips and badges.
3. **Approval inbox showed a loading placeholder above its own data.** Reproduced with five
   rows behind "Memuat approval…". Cursor lists painted the placeholder into the list
   container and then appended with `insertAdjacentHTML`, so it was only ever replaced on the
   empty branch. Row appends now go through `appendRows()`; 38 call sites.
4. **A failed first load showed loading and error at once.** The placeholder stayed while the
   error and retry rendered below it. The 21 list error handlers now call
   `clearDialogLoading()`.
5. **KPI cards lost their right border below 650px** — on the board and on the Command
   Center. `.summary div:nth-child(2)` and `#command-center-summary div` from the old layer
   out-specified the new card grid.
6. **`ledger-heading` was centred on mobile only**, because its column override preceded the
   base rule that set `align-items: center`. The override now sits with the component.
7. **Capacity plan's admin master section** packed two unrelated mini-forms into one
   two-column grid, so their action rows became grid cells and drew rules across the middle.
   Split into two grouped toolbars.
8. **Approval inbox filter** sat on the dialog ground instead of in a toolbar.
9. **Purchase requests, purchase orders and marketing budget** rendered their status select as
   a bare label+select. Wrapped in `.filter-form`.
10. **Board and activity KPI cards had no glyph**, so they read as a different component from
    the dashboard KPI cards they share a grid with.

Also corrected during consolidation: `.order-title` needed an explicit `display: block`,
because the reference span is nested inside that button and an inline-flex button laid the
reference and title out side by side. Restored with a comment explaining why.

## Command Center non-regression

The dashboard was the reference throughout and was re-checked after every step. Verified in
all four modes: four KPI cards each with a glyph, both numbered bands and their step badges,
the hero card with the real daily trend and the order funnel, the marketplace comparison
table with share bars, the ranked product list, the snapshot rail with label/value rows and
sources, the decision queue with its mark tiles, and the decision queue still wider than the
rail on desktop. Asserted mechanically in `tests/browser_shared_ui.cjs`.

## Dark, mobile and viewer verification

- **Dark** — checked on all 78 surfaces. Surfaces resolve the dark token set rather than
  inverting: the assertion computes the luminance of a card background and requires it to be
  dark, on both the dashboard and a non-dashboard section.
- **Mobile 390px** — checked on all 78 surfaces. No page-level horizontal overflow; KPI cards
  reflow to full width and keep complete borders; filter controls reflow inside the toolbar;
  dialogs fit the viewport and do not scroll sideways. Also verified at 200% text zoom on the
  board with no horizontal overflow.
- **Viewer/read-only** — checked on 77 surfaces (the 78th has no viewer rendering).
  Mutation controls are absent while the surfaces themselves are unchanged. Spot examples:
  order detail loses "Ubah tenggat / PIC", "Catat perpindahan" and "Koreksi"; the employee
  master keeps "Riwayat" but loses "Ubah" and "Tambah karyawan"; materials loses "Terima
  batch bahan"; the audit trail renders a permission error with a retry.
- Two viewer panels exist in the artefacts for forms (`Terima batch bahan`, `Buat PR`) only
  because the harness fires `data-action` directly. A real viewer cannot reach them: the nav
  entry is hidden and the server rejects the write.

## Implementation review of the final diff

| Check | Result |
| --- | --- |
| Duplicate design tokens still active | None. One `:root` and one `:root[data-theme=dark]`. |
| Dead legacy overrides | Removed; the four tokens nothing referenced are gone. |
| `!important` added | None. The 10 occurrences are pre-existing (`[hidden]` and the print block). |
| Excessive specificity | The new layer is class-anchored; the only type selectors are `label>input`, `label>select` and `label>textarea`. |
| Accidental global selectors | None reaching the dialog, scanner or print path. |
| Print-label regression | `bundle-label` CSS and markup and the `@media print` block are byte-identical to `main`. |
| Dialog regression | Dialog radius 20px, ruled heading, fits viewport, no sideways scroll — asserted. |
| Mobile-only overrides conflicting with desktop | Three found and fixed; the mobile override now sits with its component. |
| Command Center changed by shared selectors | No. Verified visually and by assertion. |
| Primary cards 20px | `--r-card: 20px`, asserted at runtime. |
| Inputs 12px | Asserted at runtime. |
| Navigation 10px | `--r-nav: 10px`, asserted at runtime. |
| Badges/chips 8px | `--r-chip: 8px`, asserted at runtime. |
| Buttons pill | `--r-pill: 999px`; asserted as radius ≥ half the control height. |
| Dark theme uses existing tokens | Yes; no new colour value was introduced. |

Diff scope: `beeloft/static/style.css`, `beeloft/static/app.mjs`, `pyproject.toml` (version),
`tests/` and `docs/`. No backend, schema, model, endpoint or report formula was touched.

## Browser regression modules added

Both are registered in `tests/browser_smoke.cjs` and run by
`python tests/run_browser.py`.

**`tests/browser_shared_ui.cjs`** — asserts the radius ladder; page heading with eyebrow and
actions; four KPI cards; the filter toolbar as a bordered 20px surface on the board and
inside a dialog; list container with head, rows and pagination; status chips shrink-wrapped
rather than filling their slot; order metadata, stages and SKU cards as surfaces; dialog
chrome with a ruled heading that fits the viewport without sideways scroll; metric lists;
loading, empty and error as three distinguishable states (a held response for loading, a
forced empty response, a forced 503 proving no loading text is left beside the error); the
Command Center layout unchanged; dark tokens resolving dark; 390px reflow with no horizontal
overflow; nested surfaces stepping their radius down; and a viewer losing mutation controls
while keeping the same surfaces. It pins its own viewport and acting account so it does not
inherit state from the module before it.

**`tests/browser_kpi_glyphs.cjs`** — asserts the board and activity glyphs come from the
inline sprite (`#i-…`, resolved against the document), are `aria-hidden` and non-focusable,
match the dashboard glyph colour and scale, sit at the end of the label row, and are distinct
per metric; that labels are unchanged and values still equal `/api/production-board`; that no
image asset, emoji or external stylesheet was introduced; and that the glyphs survive dark
mode and 390px at 200% text zoom without horizontal overflow.

Assertions read computed style and geometry rather than pixel snapshots. No existing test or
assertion was weakened; two locator strategies inside the new modules were made data-robust
(searching for the demo order rather than assuming it is on page one, and forcing an empty
response rather than assuming a filter matches nothing).

## Commands run, and their results

Focused first, then the full set.

| Command | Result |
| --- | --- |
| Focused: the two new modules against a disposable demo database | PASS, no page errors |
| `python -m pip check` | `No broken requirements found.` |
| `python -m compileall -q beeloft` | clean |
| `node --check beeloft/static/app.mjs` | clean |
| `node --check beeloft/static/client.mjs` | clean |
| `node tests/test_client.mjs` | PASS (escaping, dates, exact write retry, actor binding, CSV, 422 detail) |
| `python -m unittest discover -s tests -v` | **507 tests, OK** |
| `python tests/run_browser.py --node node --playwright-module playwright --channel chromium` | **PASS — all modules including the two new ones, ending "no JS errors"** |
| `python -m build` | wheel and sdist built |
| Installed-package smoke test from outside the checkout | **15/15 checks OK** |

The browser suite was run against Chromium as CI does. Playwright is pinned to the CI
version; the browser binary is the bundled Chromium headless shell.

### Packaging

`python -m build` produces `beeloft_one-0.87.0-py3-none-any.whl` and the matching sdist. Both
contain all four static assets (`app.mjs`, `client.mjs`, `index.html`, `style.css`) and all 58
`.sql` files. The wheel was installed into a clean virtualenv, and the app was started from a
temporary directory with a disposable demo database — the import path was asserted to be
`site-packages`, not the checkout. Served and verified over HTTP: `/` returns the index with
the inline icon sprite and references to the packaged assets; `/static/style.css` carries the
shared surface layer, the filter toolbar, exactly one `:root` block and the intact radius
ladder; `/static/app.mjs` carries `appendRows`, `clearDialogLoading`, the board KPI glyph
table and the filter toolbar class; `/static/client.mjs` still exports the escaper. Nothing
depends on a file that exists only in the working tree.

### Version

Bumped `0.86.0` → `0.87.0`. Repository convention is unambiguous: every merged change bumps
the minor version by one, including the audit-fix PRs (#3 → 0.83.0, #4 → 0.84.0, #6 → 0.85.0,
#7 → 0.86.0). This release ships changed static assets, so it needs a distinguishable version.
Database schema is unchanged; `PRAGMA user_version` remains 55; no migration was added. The
highest version is set by `beeloft/rework_completions.sql`, `beeloft/store.py` reads it to
drive migrations, and a freshly created database reports 55 on this branch exactly as it does
on the baseline. No `.sql` file, `beeloft/store.py`, or `beeloft/models.py` was modified.

## Intentional exceptions

1. **Command Center attention amounts stay raw.** Three attention sentences interpolate an
   unformatted decimal, e.g. `1 invoice senilai Rp43200000.00 overdue.` The string is composed
   in `beeloft/command_center.py` (lines 93, 97, 164) and the attention item exposes only a
   free-form `detail` field — there is no structured amount beside it. The frontend renders
   `detail` verbatim through `e(row.detail)`. Formatting it in the UI would mean
   pattern-matching backend prose for `Rp<digits>`, which is fragile (it breaks silently if
   the wording changes, and would rewrite any other `Rp` occurrence) and means the UI
   reinterprets business copy. Fixing it properly is a backend change — format at composition
   time, or expose a structured `amount` next to `detail` — which is an API/copy change and out
   of scope here. Recorded as a contract request in the plan document.

   Worth noting that this is genuinely isolated: every *structured* IDR value in the same
   dashboard and across the workspace is correctly formatted. The same underlying figure
   renders as `Rp43.200.000,00` in `Utang Mekari`, which is what confirmed the diagnosis.

2. **`Cadangan data` has no viewer rendering.** Admin-only; the nav entry is hidden. Recorded
   as skipped rather than passed.

3. **Materials has no KPI row.** There is no summary endpoint for it, and inventing one would
   mean inventing figures.

## Environment limitations

- **Missing arrow glyph.** `→` (U+2192) renders as a replacement box in the review container
  because the available fonts (Noto Sans family) do not include arrows; the product's font
  stack starts with Segoe UI, which does. This affects 14 places in `app.mjs` and shows up in
  the artefacts as a tofu box. It is a container font gap, not a product defect, and the
  character was deliberately not changed.
- **Playwright system dependencies.** `playwright install --with-deps` cannot run here (the
  image is not Debian/Ubuntu), so the browser binary was installed without OS packages. The
  bundled Chromium headless shell launches and the whole suite runs, so this did not limit
  coverage.
- **Reviewer scale.** Per-surface contact sheets place the four modes at ~48% of native size.
  That is sufficient for hierarchy, surface nesting, spacing, chips and overflow, and any
  surface that looked doubtful was opened at full 1440x900. Fine-grained claims in this
  document (chip width, computed display, luminance, radius) come from measurement in the
  browser, not from reading a thumbnail.
- **Working artefact set.** The complete 467-image run and the 78 per-surface contact sheets
  live outside the repository at `/projects/sandbox/uiwork/shots/final` and
  `/projects/sandbox/uiwork/sheets`. Only the compact selection in `docs/ui-review/` is
  committed.

## Committed review artefacts

`docs/ui-review/` — 29 images, all within limits, all from synthetic data (`CONTOH`/`DEMO`
records, demo accounts). No API key, token, real name or business data appears in any of them.

- `sheets/contact-sheet-before-1..3.png` and `sheets/contact-sheet-after-1..3.png` — twelve
  representative surfaces, before and after, desktop light.
- `before/` — six baseline captures of the surfaces that changed most.
- `after/` — sixteen selected captures: Command Center (light, band 02, dark, mobile),
  production board (light, dark, mobile), order detail (light, dark), materials, People
  (light, mobile), approvals, analytics/capacity, AI dialog, integrations, and a dialog
  metric list.
