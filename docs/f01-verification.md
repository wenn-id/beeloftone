# Verifikasi F01 — status aktual

Status paket: **IN_PROGRESS — belum REVIEW_READY dan belum BUSINESS_ACCEPTED**. D14 target direction Option B selected by user instruction; detailed policy remains open. Issue #40 tetap OPEN. Status ini memisahkan pemeriksaan dokumen dari penerimaan bisnis.

- Execution baseline tercatat: `96bb48fa8889b3a483411768e2543838e69233b0`, versi aplikasi 0.114.0, schema 55.
- Prior audit di Issue #40 bertanggal 27 September 2026 hanya mencatat tanggal; jam observasi dan transaction sampling tidak tersedia.
- Browser headless percobaan awal gagal sebelum halaman login (`browser-harness: daemon default didn't come up`; tooling berbeda); lihat `EV-F01-0018`. Sesi managed live-browser read-only berikutnya berhasil login dengan kredensial pengguna via Secure Vault (~13:08 WIB) dan menyelesaikan observasi transaksi fase 1 ~13:08–13:22 WIB (jangkauan "13:20–13:55" yang dilaporkan sebelumnya DICABUT – tidak konsisten dengan metadata penyelesaian 13:22:21 WIB) serta verifikasi fase 2 ~13:27–13:32 WIB (EV-F01-0027). Tidak ada form selain login yang disubmit; tidak ada aksi Save/Pay/Approve/Void/Return/adjust/delete. Tidak ada nama pribadi atau nominal yang dicatat di repo.
- `/settings/periods` tidak didukung bukti sumber audit yang tersedia dan kini `UNVERIFIED`. Lihat `EV-F01-0019`.
- T03–T05 transaction traces parsial: fase 1 ~13:08–13:22 WIB + fase 2 ~13:27–13:32 WIB (EV-F01-0021..27): rantai payroll (1.066 = angka filter Unpaid; 271 slip Paid ditemukan), AP settlement non-PO (sampling with-PO 20 baris: semua "-"), modal stok + anomali negatif, POS 1.288 records unfiltered + B1 detail. Belum ditemukan: contoh settlement with-PO, perubahan saldo kasbon, halaman supplier bill, isi file unduhan (UNVERIFIED – no file tooling in session). T01–T08 tidak dinyatakan selesai; overall tetap IN_PROGRESS.
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
| T01 Sumber legacy/access | Berjalan/parsial | Prior audit report ada; sesi browser managed sesi ini login via Secure Vault dan menyelesaikan observasi read-only fase 1 ~13:08–13:22 WIB (jangkauan "13:20–13:55" DICABUT) + verifikasi fase 2 ~13:27–13:32 WIB (EV-F01-0021..27). Metodologi sampling penuh #40 belum dijalankan (walkthrough terarah, bukan 100 sampel per modul).
| T02 Master/UOM | Parsial | Surface groups only; field-level types/required/relations not recorded.
| T03 Jobs/payroll/cashbon | Parsial | EV-F01-0021, corrected EV-F01-0027: job list 31 Draft (A1), tariff master 578 records, master payroll 0 on Unpaid/Paid scope, payroll list 1,066 = Unpaid-filtered count (page 1 of 43 verified; pages 2–43 not viewed) + 271 Paid slips via Paid filter (page 1 verified), A2 = PR-260925-0025, kasbon 0 records on Draft/Unpaid/Paid scope. No causal link A1–A2; no kasbon balance change. Paid/Unpaid status is NOT proof of real-world payment. |
| T04 POS/AP | Parsial | EV-F01-0022, corrected EV-F01-0027: POS 1,288 records unfiltered (phase-1 emptiness was a filter artifact); B1 = POS-2312-IMBEX-000404 detail; one Rp.0 invoice detail never loaded; 4 templates; no void/return examples. EV-F01-0023/27: 946 AP settlements; A3 non-PO detail; with-PO hunt 20 rows (pages 1–2) all "-" + 2 non-PO dialogs; no supplier bill page. |
| T05 stock/accounting/reports | Parsial | EV-F01-0024: 9,646 stock records; negative-stock anomaly CONFIRMED (-29, blank product/SKU) — root cause #108 still unresolved. EV-F01-0025, corrected EV-F01-0027: Title Reports 2 records (Main/Not Main, 2024-12-20); dashboard cards observed (no metric definitions); payrolls.xlsx + stock-cards.xlsx READ with local tooling 2026-09-27 (EV-F01-0028): payrolls = 1031 line-item rows (CODE = slip codes PR-260925-XXXX, STATUS all Draft vs UI slip-level Unpaid unreconciled, DISETUJUI blank, 8 job types, fractional Realisasi Lusin, no date column); stock-cards = 9646 rows matching UI, -29 anomaly = last data row (Pusat Beeloft/B6 Reseller, blank product/SKU), "Test  unit " BU 985 rows; names/amounts redacted, raw files private. Accounting period unverified. |
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

1. Authenticated browser session: phase 1 completed 2026-09-27 ~13:08–13:22 WIB (metadata penyelesaian 06:22:21Z); phase 2 verification ~13:27–13:32 WIB (EV-F01-0027). User submitted Secure Vault credentials; managed browser signed in read-only and observed transaction chains (EV-F01-0021..26). Prior local-harness failure (EV-F01-0018) was different tooling and is superseded for this session.
2. Need owner/process custodians to locate: deeper with-PO AP settlement sampling beyond the 20-row scope, the supplier bill document behind "Remaining Bill", POS void/return/refund examples, kasbon balance-change events, and slip-level Download remains unresponsive (no per-slip file captured); the two bulk exports are read (EV-F01-0028) but their line-vs-slip status dimensions and 1031-vs-1066 count difference are not reconciled. Phase 2 already found 271 Paid slips and 1,288 unfiltered POS records, so those are no longer "not found". Store raw records in restricted location only; publish only synthetic IDs/results.
3. Need accounting/role/channel/export/operations owners to supply evidence not visible in prior menu report.
4. Only after those sources are reviewed can final recommendation set and owner-ready decision list be reduced.
