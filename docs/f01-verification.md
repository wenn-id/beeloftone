# Verifikasi F01 — status aktual

Status paket: **IN_PROGRESS — belum REVIEW_READY dan belum BUSINESS_ACCEPTED**. D14 target direction Option B selected by user instruction; detailed policy remains open. Issue #40 tetap OPEN. Status ini memisahkan pemeriksaan dokumen dari penerimaan bisnis.

- Execution baseline tercatat: `96bb48fa8889b3a483411768e2543838e69233b0`, versi aplikasi 0.114.0, schema 55.
- Prior audit di Issue #40 bertanggal 27 September 2026 hanya mencatat tanggal; jam observasi dan transaction sampling tidak tersedia.
- Browser headless gagal sebelum halaman login (`browser-harness: daemon default didn't come up`); desktop capture memberi `windows: []`. Tidak ada login, kredensial diketik, atau transaksi diperiksa dalam sesi revisi ini. Lihat `EV-F01-0018`.
- `/settings/periods` tidak didukung bukti sumber audit yang tersedia dan kini `UNVERIFIED`. Lihat `EV-F01-0019`.
- T03/T04 transaction traces belum dilakukan: jobs/payroll/payment/cashbon, POS/tenders/returns, AP/PO/receipt/payment. T01–T08 tidak dinyatakan selesai.
- Contoh JSON adalah ilustrasi sintetis; tidak menetapkan expected business results atau perilaku legacy.

## D14 decision and code-scope verification

- Direction selected: native complete accounting in One (COA, journals, GL, trial balance, balance sheet, P&L, reconciliation, period close), with staged foundation/producers/reports and export for transition. This records only user-selected scope; no named approver/title/signature or detailed policy sign-off.
- Repository baseline inventory examined: `docs/a01-ledger-readiness.md`, `docs/f02-shared-contracts.md`, `docs/f02-ownership.csv`, `beeloft/payroll_accounting.sql`, `beeloft/mekari_finance_snapshots.sql`, payroll reconciliation plan/verification and referenced tests, at `96bb48fa8889b3a483411768e2543838e69233b0`.
- Existing: operational domain ledgers/reversals; production-cost calculation; immutable read-only external Mekari finance snapshots; external payroll posting metadata and reconciliation; approval workflows separate from payment/posting.
- Missing per schema-55 inventory: native COA, accounting period master/lock, native journal header/lines/source registry, native trial balance, balance sheet/P&L, cash/bank/AR/AP accounting, close/reopen. Do not duplicate operational ledgers; post each eligible source event once. #41 contracts, #46 A01 foundation, domain producers #53–#58, #59 A02 reconciliation/statements/period controls.
- User's direction does not approve accounting policies, detailed D14, other D decisions, legacy behavior or final F01 acceptance.

## Checkpoint

| Tugas | Status aktual | Bukti / gap |
|---|---|---|
| T00 Baseline/worktree | Terverifikasi | Baseline SHA/version/schema; branch terisolasi.
| T01 Sumber legacy/access | Parsial/terhalang | Prior audit report ada; no new browser access; timestamps/sampling details missing.
| T02 Master/UOM | Parsial | Surface groups only; field-level types/required/relations not recorded.
| T03 Jobs/payroll/cashbon | Belum | No linked transaction trace or slip values.
| T04 POS/AP | Belum | No invoice/tender/refund or PO/receipt/settlement trace.
| T05 stock/accounting/reports | Parsial | Issue #108 UI report; cost method/report file/accounting period unverified.
| T06 roles/integration/migration/ops | Belum | No role matrix/vendor list/export/profile/runbook evidence.
| T07 synthetic cases | Parsial | Scenarios are questions/illustrations only; no legacy oracle.
| T08 document verification | Berjalan | Re-run structural/consistency/privacy checks after this revision; not UAT.
| T09 owner acceptance/freeze | Pending | No decision or sign-off recorded.
| T10 F02 handoff | Draft | Provisional handoff; do not use as final business contract.

## Verification commands to run on the final PR head

Record exit codes and output only after running them on the final head. The prior green CI run was attached to an earlier PR head and does not verify the revision now in progress.

- `python3 /tmp/validate_f01_current.py` — structural checks (IDs, CSV/JSON, references, proposal/approval statuses).
- `git diff --check` — whitespace.
- `python3 -m unittest tests/test_readme_test_count.py tests/test_openapi_contract.py` — repository contract subset; run again after final revision.
- `gh pr checks 109 -R wenn-id/beeloftone` — exact-head CI status; CodeRabbit skips Draft review.

No zero-PII assertion until a fresh manual content review of the final diff. Static regex alone is insufficient. No runtime/schema/API changes are intended; verify allowlist on final diff.

## Blockers / next evidence

1. Safe authenticated browser session did not start. Resume read-only via approved UI session; do not type previously exposed credentials. If blocked, identify authorized way to launch signed-in session/rotate credential, then inspect the exact sample groups listed in `f01-legacy-evidence.md`.
2. Need owner/process custodians to locate candidate job→payroll→paid evidence, linked cashbon balance events, POS invoices/tenders/refunds, and AP settlement→PO/receipt/invoice/payment. Store raw records in restricted location only; publish only synthetic IDs/results.
3. Need accounting/role/channel/export/operations owners to supply evidence not visible in prior menu report.
4. Only after those sources are reviewed can final recommendation set and owner-ready decision list be reduced.
