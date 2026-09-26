# A6.8 — Final consistency, polish and cleanup

Baseline: `main` @ `65e5635a548e4a18bf462b2be0c5b063e88e849e` (PR #106). Exact-main CI run #173
(`36238346252`, push to `main`) was `completed / success` before any change. Branch
`ui/apple27-a6-8-final-polish`. Version `0.114.0`. Schema `PRAGMA user_version = 55`, no migration.
OpenAPI diff: `info.version` only (221 paths, 85 schemas).

A6.8 is not a workspace migration. It is the product-wide pass A6.1–A6.7 deferred: the shared
dialog and `formDialog()` chrome, the remaining high-visibility legacy sheets, one approval tone
map, and proven dead CSS. No route, schema, payload, query parameter, page size, cursor, status
meaning, role gate, `expected_revision`, idempotency key, same-actor check, request fence, analytics
formula or backup behaviour changed, and no request was added.

## Debt inventory (audited on exact main)

Every finding maps to a screenshot or a runtime measurement from the before sweep
(`review/a68-visual-gate/before/`, 16 workspaces × 1440 / 1024 / 768 / 390 / 320@200 %, light and
dark, plus 19 dialogs).

| # | Finding | Class | Decision |
|---|---|---|---|
| 1 | PO detail, supplier payment and material batch dialogs scrolled sideways at 320 px / 200 % (rem margins and padding spent ~130 px of a 320 px phone on chrome) | P0 | fixed: px insets |
| 2 | PR sheet "PO terkait" chip rendered a bare dot with no word for an issued PO (payload reports `approved`, `poStatus` has no such key) | P0 | fixed: `linkedPoStatus()` |
| 3 | Command Center "Rincian order, unit & refund" table overhung its card by 20 px on both sides (`margin:0 -20px` assumed a 20 px inset the A5 card no longer has) | P0 | fixed (before/after below) |
| 4 | Command Center first-pass-yield figure (~160 px) collided with its fixed 120 px ring at 320 px / 200 % | P0 | fixed (before/after below) |
| 5 | PO detail + receipts + incoming QC + supplier returns + closure still rendered `.form-info` / `.material-event` / `.actions` walls | P1 | migrated |
| 6 | Production change approval and payroll approval (both opened from the A6.7 Inbox) still legacy | P1 | migrated |
| 7 | Supplier payment approval still legacy | P1 | migrated |
| 8 | Order-scoped "PR untuk order ini" still used the pre-A6.7 filter form and cards | P1 | migrated |
| 9 | Shared dialog: fixed 650 px for every workflow, close control off the title baseline, heading scrolled away on long sheets | P1 | modernised |
| 10 | `formDialog()`: legacy label / note / footer styling beside A6 fields | P1 | modernised (CSS only) |
| 11 | Two approval tone conventions: A6.3 painted *waiting* warning; A6.5 / A6.7 painted it info | P2 | unified |
| 12 | 21 legacy selectors with no emitter left | P3 | removed |
| — | Heading rhythm: every A6 page measured 28 px / 700 title, 15 px subtitle, 20 px heading → first content, 1360 px max-width | — | already coherent; unchanged |
| — | Subtitle measure 64ch (A6.0) vs 72ch (A6.5–A6.7) | — | intentional: the 72ch pages carry 60–110-character subtitles |
| — | Refresh weight: secondary on Produksi / Master SKU / Inbox, quiet on pages with an alternate secondary (Bahan baku, Integrasi, PR, Budget) | — | consistent rule (quiet when it sits beside a real alternate), pinned by A6.1/A6.2/A6.7; unchanged |
| — | Record density: People 108 px, Integrasi 84, Audit 122, PR 95, Budget 118, Inbox 141–163 px | — | every list fits ≥6 records per 1000 px viewport; unchanged |
| — | Dark mode: no light surface left in any workspace (only glyph-sized status dots are light, by design) | — | no change |

## Shared dialog

One `<dialog id="dialog">` with `#dialog-title`, `#dialog-content`, `#close-dialog` (still
`aria-label="Tutup dialog"`). `openDialog()`, `closeDialog()`, `dialogVersion`, the M3 animated
close, Escape via `cancel`, return focus, `modalBusy`, `unresolved`, `guardPending()` and reauth are
byte-for-byte unchanged; `openDialog()` only gained an optional third argument that sets
`data-size`.

- **Widths.** `data-size` is `compact` (520 px) for a form whose only field is the reason and for
  the recovery form, `wide` (880 px) for the one fulfilment ledger (PO detail), and `standard`
  (650 px, the historical width) for everything else. Assignment is deterministic in
  `openDialog()` / `formDialog()`; no dialog picks an arbitrary width. A6.3's People screens keep
  their approved 960 px.
- **Viewport.** `max-width` and `max-height` are viewport-derived; insets are px (12 px / 24 px
  desktop, 8 px / 16 px ≤650 px) so 200 % text never eats the sheet. Vertical scrolling is internal,
  horizontal never.
- **Heading.** Sticky, opaque (`--material-floating-solid`), ruled, close control centred on the
  title. No blur anywhere in the dialog.

## formDialog()

CSS only, scoped to `#action-form`. Every hook keeps its name and every collector keeps reading by
`name`: `#action-form`, `#form-fields`, `.form-grid`, `.form-info`, `#form-error`, `.form-actions`,
`[data-action=cancel-form]`, `#reauth`, `#save-form`. Legacy `<label>Text<control></label>` fields
read like A6.0's `.field` (small label above a quiet control); A6 fields in the same grid are left to
A6.0 (`:not(.field>*)`). The context note is an info panel with a real border; the error is the
same inline danger panel the A6.6/A6.7 queues use; the footer is cancel → reauth → one primary,
right-aligned, wrapping to full-width buttons on a phone with the 44 px floor ≤980 px. The
uncertain state is unchanged: same transaction, same-actor guard, disabled fieldset, "Coba ulang
penyimpanan" as the primary, Escape refused.

## Remaining legacy workflows — decisions

Migrated by name onto A6.7's request grammar (added to `MIGRATED_RENDERERS`), with four small
additions to that grammar: `requestAttention`, `requestRecord`, `requestRecords`,
`requestQuantities`.

| Surface | Renderer(s) | What is preserved |
|---|---|---|
| PO detail | `purchaseOrderDialog`, `purchaseReceiptsHTML`, `qualityIntakesHTML`, `renderPOClosure` | identity/status → supplier → commercial facts → lines (received, remaining, held, rejected, receivable, returned, return_pending as seven separate facts; no merged progress) → payments (`payment_pending / approved / remaining` sentence verbatim; "Approved berarti siap dibayar…") → decisions → approval history → cancellation → closure (eligibility and permanent-close copy unchanged) → receipts (active / corrected, batch history link) → QC arrivals |
| Incoming QC + supplier returns | `qualityIntakeDialog`, `renderSupplierReturns` | five quantities, admin-only accept / reject / cancel / correct gates, correction rule, physical-return truth, final history on a closed PO |
| Supplier payment approval | `supplierPaymentRequestDialog` | "Persetujuan tidak menjalankan transfer bank."; approval ≠ paid |
| Production change approval | `productionChangeRequestDialog` | old/new due date and owner side by side, stale sentence + "Permintaan sudah stale" warning chip, revision, role gates, decision history incl. "Perubahan order diterapkan…" |
| Payroll approval | `payrollApprovalRequestDialog` | aggregate only (headcount + five totals; no employee identity), stale / source-changed sentences, Mekari status as its own fact, "Keputusan tidak mengubah Mekari…" |
| PR untuk order ini | `orderPurchaseRequestsDialog` | order scope, 25-row `before=sequence` cursor, ids, Buat PR hidden for viewers |

Deliberately left legacy (still failing the containment contract if they emit A6 markup):
`purchaseOrderForm`, `purchaseReceiptForm`, `qualityDecisionForm`, `supplierPaymentForm`,
`payrollApprovalForm` and every Produksi / warehouse / marketplace child dialog. They all render
through `formDialog()`, so the new chrome already brings them to product parity; rewriting their
business markup would be scope explosion.

## Status-tone consolidation

`approvalTone = {submitted:info, pending:info, approved:success, rejected:danger, cancelled:neutral}`
is the ONE approval map. `workforceRequestTone` (A6.3) and `aiActionTone` (A6.5) are now that map;
`requestTone` (A6.7 timeline) derives from it. The only visible change: a waiting leave / overtime
request reads info instead of warning. Stale / source-changed is never a sixth status; it keeps its
sentence and a warning chip beside the status chip. Integration health, AI severity, QC, PO
lifecycle, fulfilment, Mekari payroll status and production overdue keep their own maps.

## CSS

### DEAD CSS REMOVED

Proven by searching every shipped runtime source (`index.html`, `app.mjs`, `workspace.mjs`,
`client.mjs`, `appearance.js`) for `class="…"`, `className`, `classList` and selector-string use —
zero emitters each — and pinned by `DeadCssTest`. Rules shared with a live selector (e.g.
`.card,.sku-block`) kept the live half.

`.order-grid`, `.table-head`, `.cell`, `.cell-label`, `.progress-cell`, `.status-cell`,
`.progress-note` (pre-A6.1 board table); `.detail-top`, `.detail-meta`, `.stages`, `.stage`,
`.stage-number`, `.exceptions`, `.sku-balances`, `.order-settings`, `.ledger-heading`,
`.issues-summary` (the class — the `#issues-summary` id and its A6.1 rules stay),
`.issue-resolution` (pre-A6.1 detail); `.material-balance`, `.sku-block` (incl.
`#batch-list .sku-block`), `.sku-heading` (pre-A6.2 cards). ~6.3 kB.

### RUNTIME LEGACY HOOKS STILL REQUIRED

`.state` (appendRows / clearPageLoading / shared-UI suite), `.list-host` (M6 replacement fade),
`.reason` (pre-wrap business text), `.line-input` and `.bom-line` (line collectors),
`.bundle-label` (print label), `.material-event` (Produksi / warehouse child dialogs, PO price rows),
`.form-grid` / `.form-actions` / `.form-info` (`formDialog()`), `.history-item`,
`.requirement-values`, `.filter-form`, `.hint`, `.actions`, `.status-label`, `.page-heading` /
`.eyebrow` (Command Center and child dialogs). These are compatibility hooks, not visual debt.

### Ownership

One A6.8 block at the end of `style.css` (marker `#dialog{--dialog-inset:12px;--dialog-pad:24px;`),
reaching only `#dialog`, `#action-form`, `#form-fields`, `#form-error`, `#pr-error`, `#pr-status`,
`.request-*` and the one Command Center ring rule. No primitive redefined, `workspace-primitives.css`
and `workspace.css` untouched, no blur / transition / keyframe. The only edit above the block is the
`.table-scroll` bleed fix. Duplicate phase declarations were audited; none were promoted, because
the repeated rules (touch floor, labelled filters on phones) are scoped by page id on purpose and
their semantics are not universal.

## Shell corrections (with evidence)

The shell itself (A5.2 / A5.3) was not touched. Two Command Center regressions the product sweep
found were fixed in `style.css`, each with before/after evidence and a targeted pin in
`RegressionTest`:

- marketplace table overhang — `review/a68-visual-gate/before-after/command-center-marketplace-*`;
- first-pass-yield ring at 320 / 200 % — `…/command-center-fpy-ring-320-200-{BEFORE,AFTER}.png`
  (at 1440 and 390 the ring is unchanged, 140 / 120 px).

## Responsive, accessibility and modes

- **Widths.** All 16 destinations + order detail + all 12 analytics reports: no document or
  section-edge overflow at 1440, 390 and 320 @ 200 % (automated); 1024 and 768 audited in the
  review sweep. Internal table overflow stays inside its data surface. Twelve representative sheets
  fit at 1440 / 390 / 320 @ 200 % and keep ≥300 px width at 320 px.
- **Keyboard / focus.** Tab / Shift+Tab stay inside the native modal with a visible ring at every
  stop; Enter opens, Space activates, Escape closes and returns focus to the opener; "Tutup dialog"
  returns focus the same way. No focus-trap library.
- **Labels / names / headings.** Every field keeps a visible label; new buttons keep contextual
  names (`Rincian QC <ref>`, `Rincian pembayaran <ref>`, `Riwayat batch <ref>`); sheet headings
  never skip below the dialog's h2 (section h3, record h4).
- **Live regions.** No nested live region inside any workspace or sheet, except the five pre-A6
  polite body hosts (see deferred debt).
- **Dark.** No light surface in any workspace; dialog title ≥7:1 and metadata ≥4.5:1 in dark.
- **Forced colors.** Dialog border, heading rule, chip words + edges, record-list and table
  boundaries, button text and focus survive; no A6.8 forced-colors block is needed.
- **Reduced motion.** No running animation after navigation or in a dialog; the dialog closes at
  once. **Reduced transparency** is emulated through Chromium CDP: the command bar's blur is
  withdrawn and content stays opaque.

## Performance

RAF 6 / cancelAnimationFrame 4 / setTimeout 7 / setInterval 0 — unchanged. No polling, no idle
work, no per-row fetch. Each migrated sheet makes exactly the requests it made before (PO detail 2,
the others 1); the Inbox still makes one list request per load and never calls
`/api/approvals/summary`.

## INTENTIONALLY DEFERRED NON-VISUAL TECH DEBT

- The five pre-A6 polite body hosts (`#analytics-body`, `#integrations-body`,
  `#purchase-requests-body`, `#marketing-budgets-body`, `#approvals-body`) wrap their page's own
  `role=status` / `role=alert` regions; the nearest root announces, so messages are not doubled in
  practice, but the hosts could be narrowed. They are pinned by the A6.4 / A6.7 contracts, so
  changing them is an accessibility change, not polish.
- The legacy fulfilment forms keep their `field()` / `materialReason` markup (visual parity comes
  from the `formDialog()` chrome).
- The PR detail payload reports an issued PO as `approved`; the UI maps it. A payload alignment
  would be an API change.

## Tests

- `tests/test_apple27_final_polish_contract.py` — new, 34 static tests: shell, workspace
  coverage, shared dialog, form write safety, the migrated sheets by name, tone map, dead CSS,
  regressions, timer budget, version / docs.
- `tests/browser_final_polish.cjs` — new, registered after A6.7 in `browser_smoke.cjs`; writes its
  review set to `$BEELOFT_A68_REVIEW` or `<qa-shots>/a68-visual-gate`.
- Adjusted, each keeping its original meaning: the foundation allow-list (+14 named renderers), the
  A6.7 CSS slice (now bounded by the A6.8 marker) and its boundary test (the legacy FORMS still must
  not migrate), the A6.1 / A6.2 "kept" lists (three proven-dead selectors now asserted as having no
  emitter), the version pins, and one `browser_incoming_qc` locator (`.material-event` →
  `[data-qc-decision]`, same heading filter).
