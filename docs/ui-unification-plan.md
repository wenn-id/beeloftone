# UI unification plan

## Baseline

- Branch cut from `main @ 7a13ddaf159e5318928ac4fc02449ca26d805a20` ("Fix remaining P3 audit
  findings", PR #7), which was also `origin/main` at the time. All P1/P2/P3 audit fixes on
  that commit are preserved; nothing in this work touches the store, the API, or the
  idempotency, actor-binding, logout, or rework/QC rules those audits established.
- Working branch: `ui/unify-sections-command-center`.

## The problem

`style.css` carried two complete foundations stacked on top of each other: the
pre-reconstruction palette and component layer, then the Command Center reconstruction that
re-declared almost all of it. Every surface therefore resolved its shape and colour through
two competing layers.

The consequence was not only duplication. The Command Center had been rebuilt into a coherent
system — 20px cards, a KPI card with a glyph and a chip, a filter toolbar, a list surface with
a micro header, label/value rails, numbered bands — but the other ~73 surfaces still rendered
from the older vocabulary: `material-event`, `form-info`, `requirement-values`,
`product-item`, `history-item`, `workforce-*`, `sku-block`, `detail-meta`. Those classes were
styled as flat rules directly on the canvas. Moving from the dashboard to any other section
changed the visual system rather than the content.

In three places the older layer actually won, producing visible defects: KPI cards lost their
right border below 650px (on the board and on the dashboard), and `ledger-heading` was left
centred on mobile only.

## Visual reference

The Command Center as it already renders on `main` is the reference — not a redesign, and not
DESIGN.md read in the abstract. Where a comment or a legacy value disagreed with what the
dashboard actually renders, the render won. DESIGN.md's explicit, settled decisions were
treated as binding, in particular:

- The radius ladder is deliberate and must not be "harmonised": primary surfaces 20px,
  inputs 12px, navigation rows 10px, chips and badges 8px, buttons pill.
- A surface nested inside a surface steps down (14px, then 11px) on a sunken ground, the way
  the hero card's breakdown panel relates to the hero card.
- KPI card = label plus a blue glyph on the first line, then the figure, then an optional
  semantic chip and a caption.
- Red / amber / green are reserved for real semantic state and always paired with text.
- Dark theme follows the existing token set rather than inverting the light theme.

## Strategy: consolidate, do not add a second system

The lever was that the divergent surfaces already shared a small vocabulary. Re-expressing
those same classes in the Command Center's tokens unified roughly seventy surfaces without
touching their markup. That is why the bulk of the change is CSS, and why the JavaScript diff
is small and surgical.

Three ordered moves:

1. **Collapse the duplicate foundation.** Declare tokens once. Delete the base declarations
   the reconstruction already restates so each component has one source of truth. Remove the
   dead tokens nothing referenced (`--radius-control`, `--radius-card`, `--space-1..6`,
   `--control-line`). Fix the three places where the old layer out-specified the new one.
   Keep every rule that was still load-bearing — verified individually, and one
   (`.order-title { display:block }`) was restored with a comment after the render proved it
   was doing real work.

2. **Re-express the shared vocabulary.** One clearly-marked block, appended after the
   reconstruction so it wins on order rather than on `!important`. Record lists become
   surfaces; metric pairs become the dashboard's label/value rail; the People ledger strip
   becomes a stat card grid; dialog chrome gains the page-heading rhythm. Two genuinely new
   shared classes were added because no existing class covered the role: `.filter-form` (a
   filter toolbar inside a dialog) and `.inline-alert` (a toned notice).

3. **Fix what only markup can fix.** Small, targeted JavaScript: a helper so list appends
   drop the loading placeholder, a helper so a failed load clears it, the `filter-form` class
   on the filter forms, grouping for two long forms that shared one grid, and the KPI glyph.

## Sequencing

1. Inspect the repository, run it on synthetic data, and screenshot the Command Center as the
   golden reference before changing anything.
2. Map every surface, including everything reachable only through the `data-action`
   dispatcher, and record the inventory.
3. Consolidate tokens and superseded overrides. Verify the dashboard renders identically.
4. Re-express the shared vocabulary in CSS.
5. Targeted markup fixes for loading states, filter toolbars, form grouping.
6. Close the KPI glyph gap.
7. Review all 78 surfaces in four modes; fix what the render shows.
8. Add browser regression cover for the shared layer.
9. Full verification and packaging.

Commits are kept logical and separable: token consolidation, the shared surface layer, the
markup fixes, the glyph, then the tests — so a reviewer can read the visual change apart from
the behavioural change.

## Non-goals

- No new design direction. No new colour, radius, spacing, or type value was introduced.
- No copying dashboard content into other sections. No invented KPI, trend, target, delta, or
  placeholder identity. Where a section has no summary endpoint (materials), no summary row
  was fabricated.
- No framework migration, no restructuring of `app.mjs` for tidiness, no `!important` to
  paper over specificity, no global selectors that reach into the dialog, scanner, or label
  print path.
- Dialogs stay dialogs. Nothing was promoted to a route.
- No change to navigation order or the default landing view.
- No mass reformatting: only code touched by the unification was cleaned.

## Business invariants preserved

Verified by the existing suite plus the new modules, and by reading the diff:

- No backend, schema, model, endpoint, or report formula changed. The diff is confined to
  `beeloft/static/style.css`, `beeloft/static/app.mjs`, and `tests/`.
- Every navigation destination and capability still exists; nothing was added or removed.
- Filters, pagination, sorting, and the scope of every summary are unchanged. No figure moved
  to a different card; no paginated page length is presented as a total.
- Role gating and read-only behaviour are unchanged, and are now asserted for a viewer.
- Exact money formatting, quantities, units, and Jakarta dates are unchanged. Snapshot labels,
  period ranges, and data-limitation notes are unchanged.
- CSV export, backup download, and the QR/label print path are untouched — the print
  stylesheet and the label markup are byte-identical to `main`.
- Empty and error handling, including the audit-driven 422 messages, is preserved; loading,
  empty, and error are now three distinguishable states rather than three that could blur.
- Transaction protection is untouched: idempotency keys, actor binding, per-account pending
  drafts, no double mutation on retry, honest logout failure, and stale-workspace teardown.
- Ids, `name`s, `data-action`s, and accessible labels were preserved, so no existing test
  locator had to be weakened.
- Opening a screen still issues no mutation.

## Contract requests recorded, not made

One presentation problem cannot be fixed in the frontend without interpreting backend prose,
so it is recorded here rather than silently changed:

- `beeloft/command_center.py` composes three attention sentences that interpolate a raw
  decimal amount (`f'… senilai Rp{payable_summary["overdue_amount"]} overdue.'`). The
  attention item carries `detail` as free-form text and no structured amount, so the UI
  renders it verbatim. Formatting it properly belongs in the backend (either format at
  composition time, or expose a structured `amount` beside `detail`). That is an API/copy
  change and is out of scope for this task.
