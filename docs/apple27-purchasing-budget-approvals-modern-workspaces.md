# A6.7 — Permintaan pembelian + Budget marketing + Inbox approval modern workspaces

Baseline: `main` @ `2173ce9db466cd5037c1ea60c6e70f3aec049cb5` (PR #105, exact-main CI green).
Version `0.113.0`. Schema `PRAGMA user_version = 55`, no migration. OpenAPI diff: `info.version` only.

A6.7 migrates `#purchase-requests-view`, `#marketing-budgets-view` and `#approvals-view` onto the
A6.0 workspace primitives, together with the dialogs that *are* their request-to-decision workflow.
It is presentation-only: no route, schema, query parameter, page size, cursor, role gate, request
fence, decision payload, `expected_revision` or approval rule changed, and no request was added.

## One queue idiom

The three pages share one composition — heading → scope note → one command bar → a subhead with the
count of records on screen → **one record list** → "load more" — and differ only in their records.

- **Host.** Each list host keeps `class="list-host"` and nothing else, because the M6 motion
  contract reads that class back after every replacement fade. Rows go into one `ul.record-list`
  inside the host (`queueAppend`), and the next page joins the same list.
- **States.** Loading and empty live inside the host, wrapped in the `.state` hook that
  `appendRows()`, `clearPageLoading()` and the shared-UI suite recognise; the legacy `.state` card is
  withdrawn by `.queue-state`, and the A6 `loading-state` / `empty-state` inside it draws the box.
  A failed load keeps the legacy lifecycle: the message in the page's `role="alert"` host (now a
  danger panel) and the load-more control as the one retry.
- **Record.** Reference (`h3`) → what it is about → status chip(s) with who asked and when on the
  same line → the domain's context → the amount and the one open action on the right. Every business
  string is escaped. The count says only what is on screen (`25 PR ditampilkan`); the lists return
  pages, not totals, so it never claims more.
- **Tones.** Status chips reuse A6.5's `approvalTone` (pending = info, approved = success, rejected =
  danger, cancelled = neutral). The chip text and its A6.0 dot always carry the meaning.

## Permintaan pembelian

- **Identity.** Eyebrow `Purchasing · permintaan pembelian`, title `Permintaan pembelian`, subtitle
  "Ajukan kebutuhan bahan dan tinjau keputusannya sebelum dipesan ke pemasok." The scope note keeps
  the legacy sentence and adds where a PO is made (from an approved PR's detail).
- **Actions.** Master pemasok (quiet), Daftar PO (secondary) — both moved from the body to the
  heading — Muat ulang PR (quiet), Buat PR (the one primary, still hidden for viewers).
- **Queue.** `GET /api/purchase-requests?limit=25&status=…` with `before=<last sequence>`; the five
  statuses, "Muat PR berikutnya", "Coba muat PR lagi", the `purchaseRequestsRendered` fence and the
  filter-only fade are unchanged. Row: reference, order reference or "Permintaan umum" · needed date,
  status chip, requester · Jakarta time, estimate (`estimasi total`), "Rincian PR" (`Rincian <ref>`).
- **Buat PR.** A6 fields with the legacy names and limits, `#pr-order`, and A6.2's `.bom-line` rows
  (the collector's hook). Duplicate materials, the 100-line cap, the one-line minimum, unit-dependent
  `step`/`min` and the payload `{reference, required_date, order_id|null, estimated_value, reason,
  lines}` are unchanged.
- **PR sheet.** `reference · status` stays one line; then the order (or "Permintaan umum"), a status
  chip, facts (Dibutuhkan, Estimasi total, Bahan diminta), the requested materials, the requester's
  reason, the approval rule verbatim, the decisions this viewer may take, *PO terkait*, navigation,
  and the append-only history as a timeline. Every gate is the legacy one; one primary per sheet
  (Setujui PR, or Buat PO dari PR on an approved PR without an active PO), Tolak is destructive,
  Batalkan is neutral. The decision form is the shared A6 reason field; its body is still
  `{reason, status, expected_revision}`.
- **Master pemasok / Tambah pemasok.** A record list of supplier identities (no status chip is
  invented), "Kontak belum diisi" / "Alamat belum diisi" kept, admin-only add placed before the list.
- **Daftar PO.** The same queue grammar in the dialog: status (auto-loads), refresh, 25-row
  `before` cursor. Approval status, fulfilment and a QC hold are three chips in their own words.

## Budget marketing

Eyebrow `Marketing · pengajuan budget`, title `Budget marketing`; the ceiling-only truth stays in the
scope note. Actions: Inbox approval, Muat ulang (quiet), Ajukan budget (primary, hidden for viewers).
The queue is `GET /api/marketing-budget-requests?limit=25&status=…` with the `before` cursor; rows
show reference, campaign · channel, status, requester · time, the campaign period and the requested
ceiling (`plafon`). The form keeps every name and limit; the sheet shows channel, period, ceiling,
requester and time, the objective and reason as written, "Persetujuan hanya mengesahkan plafon dan
belum mencatat belanja.", the role-gated decisions and the history.

## Inbox approval

Eyebrow `Antrean keputusan · lintas domain`, title `Inbox approval`, the one-queue sentence as the
subtitle, the source note ("Keputusan diambil di rincian tiap approval."), and the four domain lists
— Semua PR, Semua budget marketing, Permintaan People, Payroll Mekari — as one quiet, labelled group.
The queue is still `GET /api/approvals?limit=25&offset=…&status=pending&kind=all` with offset paging,
the nine kinds, "Coba lagi" and the replacement-only fade; the aggregate summary endpoint is **not**
called. A record carries a neutral kind chip (the kind glyph repeats it), the approval status chip,
reference and title, the context line its kind always printed (a stale production change keeps
"Permintaan sudah stale." with a warning glyph; payroll keeps "· sumber berubah"), the reason (two
lines here, all of it in the detail), the amount when it has one, and "Buka approval"
(`Rincian approval <ref>`), which opens the owning domain's own detail.

## Scope boundary

Migrated by name (`MIGRATED_RENDERERS`): `loadApprovals`, `approvalContextHTML`,
`loadMarketingBudgets`, `marketingBudgetForm`, `marketingBudgetRequestDialog`, `loadPurchaseRequests`,
`purchaseRequestForm`, `purchaseRequestDialog`, `suppliersDialog`, `supplierForm`,
`purchaseOrdersDialog`, and the queue / request grammar (`queue*`, `request*`).

Still legacy, deliberately, and still failing the foundation contract if they emit A6 markup:

- the **PO fulfilment workflow**: `purchaseOrderForm`, `purchaseOrderDialog` and everything nested in
  it — receipts, incoming QC and its decisions, supplier returns, closure, cancellation — and supplier
  payments (`supplierPaymentForm`, `supplierPaymentRequestDialog`); five acceptance suites own it;
- the **production change request** and **payroll approval request** details the Inbox opens (a
  Produksi child dialog, and payroll internals A6.5 left blocked);
- the order-scoped **"PR untuk order ini"** dialog, which A6.1 lists among Produksi's child dialogs;
- `formDialog()`'s chrome (`.form-info`, `.form-grid`, `.form-actions`) and the `materialReason`
  constant those legacy dialogs still render.

## Global

- **CSS.** One block at the end of `style.css`, marker
  `#purchase-requests-view,#marketing-budgets-view,#approvals-view{max-width:1360px`, reaching only
  A6.7 ids and the `.queue-*` / `.request-*` names. `.approval-*` and `.decision-*` belong to the
  frozen Command Center and are not used. No primitive is redefined; no blur, transition or keyframe.
- **Responsive.** ≤980px restores the 44px touch floor; ≤650px turns filters into labelled full-width
  fields, lets a chip or a history stamp wrap inside its own box, and reads the amount from the left.
  The browser module checks document overflow, section-edge overflow **and** text that spills out of
  its own box, at 1440, 390 and 320px / 200% text, plus every sheet and form at 390 and 320 / 200%.
- **Themes and accessibility.** Dark through the A6 tokens; no forced-colors block (every surface has
  a real border and meaning lives in text). Buttons keep their accessible names; the new "Buka PO"
  is labelled `Buka PO <ref>`, so the name contains the visible label.
- **Performance.** RAF 6 / cancelAnimationFrame 4 / setTimeout 7 / setInterval 0, unchanged; one
  request per load, as before; no polling.
- **Tests.** Static `tests/test_apple27_purchasing_budget_approvals_contract.py` (35 tests);
  behavioural `tests/browser_purchasing_budget_approvals_modern_workspaces.cjs` (run after A6.6; seeds
  its own queues, writes 34 review shots to `$BEELOFT_A67_REVIEW` or `<qa-shots>/a67-visual-gate`).
  Adjusted: the foundation allowance, the A6.6 CSS slice (now bounded by the A6.7 marker), the A6.5 /
  A6.6 "A6.7 stays unmigrated" checks (now: none of A6.7 lives in their blocks), the version pins, and
  five browser suites that named the old headings or `.material-event` rows
  (`browser_navigation_foundation`, `browser_motion_workspace`, `browser_marketing_budgets`,
  `browser_shared_ui`, `browser_unified_approvals`).

## Deferred to A6.8

Cross-product consistency (the two approval-tone conventions A6.3 and A6.5 left, spacing between
phases), `formDialog()`'s chrome, the legacy selectors this phase makes inert, and a decision on the
remaining legacy fulfilment and child dialogs listed above.
