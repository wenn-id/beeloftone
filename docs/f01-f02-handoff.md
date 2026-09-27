# Handoff F01 ke F02 (#41)

D14 target scope: **Opsi B dipilih pengguna** (native full accounting); detail kebijakan dan penerimaan D14 tetap OPEN. Pernyataan ini tidak mengubah kontrak F02 atau fixture `tests/fixtures/f02-contracts.json`.

Status: **DRAFT / BLOCKED ON LEGACY EVIDENCE**. Ini bukan final business contract dan tidak menyatakan F02 accepted.

| Dxx | rule_version | Pxx | EXxx/case_ids | evidence_ids | F02 scenario | decision_status | impact | remaining_blocker |
|---|---|---|---|---|---|---|---|---|
| D01 | `D01-RULE-20260927-1` | P01-P03 | EX01 / SYN-D01 | `EV-F01-0008`, `EV-F01-0009`, `EV-F01-0012` | master/UOM | PROPOSED | Target behavior may affect contracts, data, permission or accounting | BLOCKED_BY_FIELD_AND_TRANSACTION_EVIDENCE; synthetic case is not an acceptance oracle |
| D02 | `D02-RULE-20260927-1` | P03-P10 | EX02 / SYN-D02 | `EV-F01-0011` | planning revision | PROPOSED | Target behavior may affect contracts, data, permission or accounting | NEEDS_LEGACY_TRACE; synthetic case is not an acceptance oracle |
| D03 | `D03-RULE-20260927-1` | P04,P09 | EX03 / SYN-D03 | `EV-F01-0011` | cutting quantity | PROPOSED | Target behavior may affect contracts, data, permission or accounting | NEEDS_TRANSACTION_TRACE; synthetic case is not an acceptance oracle |
| D04 | `D04-RULE-20260927-1` | P03,P07,P11-P12,P22 | EX04 / SYN-D04 | `EV-F01-0003`, `EV-F01-0009`, `EV-F01-0010` | QTY-RATE-01 / RATE-02 | PROPOSED | Target behavior may affect contracts, data, permission or accounting | NEEDS_SLIP_AND_HISTORY_TRACE; synthetic case is not an acceptance oracle |
| D05 | `D05-RULE-20260927-1` | P11-P13,P22 | EX05 / SYN-D05 | `EV-F01-0003` | CHARGE-01 | PROPOSED | Target behavior may affect contracts, data, permission or accounting | NEEDS_OWNER_AND_LEGACY_CASES; synthetic case is not an acceptance oracle |
| D06 | `D06-RULE-20260927-1` | P20-P23 | EX06 / SYN-D06 | `EV-F01-0002` | PAYROLL-01 | PROPOSED | Target behavior may affect contracts, data, permission or accounting | NEEDS_SLIP_TRACE; synthetic case is not an acceptance oracle |
| D07 | `D07-RULE-20260927-1` | P11,P22-P23 | EX07 / SYN-D07 | `EV-F01-0002` | PERIOD-01 | PROPOSED | Target behavior may affect contracts, data, permission or accounting | NEEDS_LINKED_SLIP_AND_PAYMENT_TRACE; synthetic case is not an acceptance oracle |
| D08 | `D08-RULE-20260927-1` | P24 | EX08 / SYN-D08 | `EV-F01-0004` | LOAN-01 | PROPOSED | Target behavior may affect contracts, data, permission or accounting | NEEDS_LINKED_CASHBON_PAYROLL_TRACE; synthetic case is not an acceptance oracle |
| D09 | `D09-RULE-20260927-1` | P15-P19 | EX09 / SYN-D09 | `EV-F01-0005`, `EV-F01-0015` | SRC-01..05 | PROPOSED | Target behavior may affect contracts, data, permission or accounting | NEEDS_CHANNEL_TRACE; synthetic case is not an acceptance oracle |
| D10 | `D10-RULE-20260927-1` | P17-P18 | EX10 / SYN-D10 | `EV-F01-0005` | PAY-01 | PROPOSED | Target behavior may affect contracts, data, permission or accounting | NEEDS_POS_TRANSACTION_TRACE; synthetic case is not an acceptance oracle |
| D11 | `D11-RULE-20260927-1` | P16-P19 | EX11 / SYN-D11 | `EV-F01-0006` | PAY-01 | PROPOSED | Target behavior may affect contracts, data, permission or accounting | NEEDS_POS_PAYMENT_TRACE; synthetic case is not an acceptance oracle |
| D12 | `D12-RULE-20260927-1` | P06-P07,P25 | EX12 / SYN-D12 | `EV-F01-0007` | supplier-payment | PROPOSED | Target behavior may affect contracts, data, permission or accounting | NEEDS_AP_TRANSACTION_TRACE; synthetic case is not an acceptance oracle |
| D13 | `D13-RULE-20260927-1` | P08-P14,P26 | EX13 / SYN-D13 | `EV-F01-0013`, `EV-F01-0016` | stock/valuation | PROPOSED | Target behavior may affect contracts, data, permission or accounting | NEEDS_COST_AND_ANOMALY_TRACE; synthetic case is not an acceptance oracle |
| D14 | `D14-RULE-20260927-1` | P23,P27 | EX14 / SYN-D14 | `EV-F01-0001`, `EV-F01-0017` | ledger scope | PROPOSED | Target behavior may affect contracts, data, permission or accounting | OWNER_SCOPE_DECISION_POSSIBLE_WITH_EVIDENCE_CAVEAT; synthetic case is not an acceptance oracle |
| D15 | `D15-RULE-20260927-1` | P27,P30 | EX15 / SYN-D15 | `EV-F01-0019`, `EV-F01-0002` | period close | PROPOSED | Target behavior may affect contracts, data, permission or accounting | NEEDS_ACCOUNTING_WORKFLOW_EVIDENCE; synthetic case is not an acceptance oracle |
| D16 | `D16-RULE-20260927-1` | P30,P34 | EX16 / SYN-D16 | `EV-F01-0014`, `EV-F01-0015` | report/export | PROPOSED | Target behavior may affect contracts, data, permission or accounting | NEEDS_REPORT_AND_DOWNLOAD_TRACE; synthetic case is not an acceptance oracle |
| D17 | `D17-RULE-20260927-1` | P20,P29 | EX17 / SYN-D17 | `EV-F01-0012`, `EV-F01-0015` | permission | PROPOSED | Target behavior may affect contracts, data, permission or accounting | NEEDS_ROLE_OWNER_AND_ACCESS_EVIDENCE; synthetic case is not an acceptance oracle |
| D18 | `D18-RULE-20260927-1` | P15-P19,P31 | EX18 / SYN-D18 | `EV-F01-0001`, `EV-F01-0015` | integration sync | PROPOSED | Target behavior may affect contracts, data, permission or accounting | NEEDS_CHANNEL_AND_VENDOR_TRACE; synthetic case is not an acceptance oracle |
| D19 | `D19-RULE-20260927-1` | P32 | EX19 / SYN-D19 | `EV-F01-0016`, `EV-F01-0017` | migration/cutoff | PROPOSED | Target behavior may affect contracts, data, permission or accounting | NEEDS_EXPORT_AND_PROFILE; synthetic case is not an acceptance oracle |
| D20 | `D20-RULE-20260927-1` | P33 | EX20 / SYN-D20 | `EV-F01-0001`, `EV-F01-0018` | recovery/cutover | PROPOSED | Target behavior may affect contracts, data, permission or accounting | NEEDS_OPERATIONS_AND_UAT_EVIDENCE; synthetic case is not an acceptance oracle |

## Handoff boundaries

- Do not infer approval from this matrix. `docs/f02-shared-contracts.md` and `tests/fixtures/f02-contracts.json` remain unchanged.
- Rules ready for technical contract after owner acceptance: preserve explicit separation of observed fields vs derived behavior; each rule still needs versioned expected results.
- Blockers: no linked transaction traces for payroll/cashbon, POS, or AP; no source documents, role matrix, accounting workflow, migration profile, or operations sign-off.
- #41 may continue source inventory, but must mark decision-derived assertions as provisional until D01–D20 are approved.


## D14 direction-to-roadmap handoff (not final contract)

| Capability | Proven existing in One at schema 55 | Gap / next package |
|---|---|---|
| Operational event ledgers and reversals | Domain-specific immutable records, movements, reversals; source inventory in `f02-ownership.csv`; examples in inventory table `f01-decisions-evidence.md` | Preserve as operational source ledgers. #41 must establish stable event identity/revision and one-time posting link; producers land in domain issues. |
| Costing and stock operations | Production-cost calculation and inventory operational movements; see `docs/a01-ledger-readiness.md`, `tests/test_production_cost.py` | No complete policy/financial inventory valuation or journalized WIP/COGS; #53 I01 + #46 A01 and #59 A02 after D13. |
| External accounting evidence | Read-only Mekari finance snapshot aggregate and payroll posting metadata/reconciliation; `beeloft/mekari_finance_snapshots.sql`, `beeloft/payroll_accounting.sql`, relevant tests | External snapshots are not native One balances/journals and must not be double-counted. #51 X01 remains connector/snapshot scope. |
| Native COA, period, journal header/lines, source registry, atomic posting | Not found in schema-55 ownership inventory; `docs/a01-ledger-readiness.md` explicitly records absence | #46 A01 after #41 F02 and #44 M02, with D14/D15 detailed policy. No implementation in this F01 docs revision. |
| Native bank/payment/AR/AP ledgers and event posting | Existing operational approvals/settlements do not prove cash movement, allocation or GL posting | #54 B02, #55/#56, #57/#58 producer subledgers; #46 posting contract then #59 reconciliation. |
| Trial balance, statements, reconcile, close/reopen and period lock | Not found in schema 55 inventory; period locking explicitly “belum diimplementasikan” in F02 | #59 A02 after #46 and domain dependencies; trial balance/BS/P&L and reconciliation derive from posted journal lines. |
| No duplicate operational/financial ledger | Current operational ledgers already track physical/domain state | #41 source identity/revision + idempotency and #46 unique source-to-journal effect; financial journal is a projection, not a second quantity/state ledger. Existing sewing cost and future charge must not double count. |

**Selected architecture direction:** prepare transaction/accounting foundations early (#41/#46), make operational producers emit traceable events, build full statements and close controls in dependency order (#59), and retain exports for transition/review. A/B direction is settled by user instruction only. COA/timing/tax/currency/rounding/period/roles/migration/report detail remains open. Roadmap A2/A3 are responsibility-role labels, not recorded business approvers.
