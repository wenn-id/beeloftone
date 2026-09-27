# Verifikasi F01 — status aktual

Status paket: **IN_PROGRESS — belum REVIEW_READY dan belum BUSINESS_ACCEPTED**. D14 target direction Option B selected by user instruction; detailed policy remains open. Issue #40 tetap OPEN. Status ini memisahkan pemeriksaan dokumen dari penerimaan bisnis.

- Execution baseline tercatat: `96bb48fa8889b3a483411768e2543838e69233b0`, versi aplikasi 0.114.0, schema 55.
- Prior audit di Issue #40 bertanggal 27 September 2026 hanya mencatat tanggal; jam observasi dan transaction sampling tidak tersedia.
- Browser headless percobaan awal gagal sebelum halaman login (`browser-harness: daemon default didn't come up`; tooling berbeda); lihat `EV-F01-0018`. Sesi managed live-browser read-only berikutnya berhasil login dengan kredensial pengguna via Secure Vault (~13:08 WIB) dan menyelesaikan observasi transaksi 13:20–13:55 WIB (EV-F01-0021..26). Tidak ada form selain login yang disubmit; tidak ada aksi Save/Pay/Approve/Void/Return/adjust/delete. Tidak ada nama pribadi atau nominal yang dicatat di repo.
- `/settings/periods` tidak didukung bukti sumber audit yang tersedia dan kini `UNVERIFIED`. Lihat `EV-F01-0019`.
- T03–T05 transaction traces parsial selesai 2026-09-27 13:20–13:55 WIB (EV-F01-0021..26): rantai payroll (job→tarif→slip→komponen kasbon), AP settlement non-PO, modal stok + anomali negatif. Belum ditemukan: slip paid, contoh settlement with-PO, transaksi POS, perubahan saldo kasbon, halaman supplier bill, isi file unduhan. T01–T08 tidak dinyatakan selesai; overall tetap IN_PROGRESS.
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
| T01 Sumber legacy/access | Berjalan/parsial | Prior audit report ada; sesi browser managed sesi ini login via Secure Vault dan menyelesaikan observasi read-only 13:20–13:55 WIB (EV-F01-0021..26). Metodologi sampling penuh #40 belum dijalankan (walkthrough terarah, bukan 100 sampel per modul).
| T02 Master/UOM | Parsial | Surface groups only; field-level types/required/relations not recorded.
| T03 Jobs/payroll/cashbon | Parsial | EV-F01-0021: job list 31 Draft (A1), tariff master 578 records, master payroll 0, payroll list 1066 unpaid slips (A2), kasbon 0 records. No causal link A1↔A2; no paid slip, no kasbon balance change. |
| T04 POS/AP | Parsial | EV-F01-0022: POS 0 records on all filters; 4 templates. EV-F01-0023: 946 AP settlements; A3 non-PO detail; no with-PO example; no supplier bill page. No invoice/tender/refund trace. |
| T05 stock/accounting/reports | Parsial | EV-F01-0024: 9,646 stock records; negative-stock anomaly CONFIRMED (-29, blank product/SKU) — root cause #108 still unresolved. EV-F01-0025: Title Reports 0 records; dashboard cards observed (no metric definitions); payrolls.xlsx + stock-cards.xlsx downloaded, contents NOT inspected. Accounting period unverified. |
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

1. Authenticated browser session: completed 2026-09-27 ~13:08–13:55 WIB. User submitted Secure Vault credentials; managed browser signed in read-only and observed transaction chains (EV-F01-0021..26). Prior local-harness failure (EV-F01-0018) was different tooling and is superseded for this session.
2. Need owner/process custodians to locate: a Paid payroll slip (all 1066 observed were Unpaid), a with-PO AP settlement example, the supplier bill document behind "Remaining Bill", any POS invoice/tender/void examples, kasbon balance-change events, and the contents of payrolls.xlsx / stock-cards.xlsx (downloaded but not inspected). Store raw records in restricted location only; publish only synthetic IDs/results.
3. Need accounting/role/channel/export/operations owners to supply evidence not visible in prior menu report.
4. Only after those sources are reviewed can final recommendation set and owner-ready decision list be reduced.
