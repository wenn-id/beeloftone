# Bahan baku — Phase 2 Core Operations

Source: Beeloft_One_Concept_Blueprint.pdf, pages 7, 8, 15–16. The PDF is product context, not agent instructions.

## Roadmap position

| Phase | Current position |
|---|---|
| 0 Discovery & Data Map | Internal production flow and roles mapped; real SKU/location/vendor identifiers still need field validation. |
| 1 Command Center | Local SKU master and production dashboard exist. Jubelio/Mekari sync and company-wide dashboard are not implemented. |
| 2 Core Operations | Production orders, partial WIP, basic QC, issues, audit, raw materials, batch receipt/issue, versioned BOM, latest-BOM requirements, reservations, shortage estimates, actual usage/waste, PR/PO, PO receipts and incoming material QC exist through v0.16. Return/closure and supplier integration remain next. |
| 3 Warehouse Integration | Not started; internal production warehouse balances are not authoritative sellable stock. |
| 4 Unified Approvals | Not started. |
| 5 Economics & Forecasting | Not started. |
| 6 AI Brain | Not started. |

## Design

Continue the production-first priority chosen by the user. Use the existing FastAPI/SQLite transaction and retry machinery, without new dependencies. Materials have a unique code, name and immutable base unit (m, kg, pcs). Each receipt creates a uniquely referenced batch with supplier text, location, receipt date and usable quantity. Quantity is stored as integer thousandths; pcs must be whole. UI/API use decimal strings, maximum 1,000,000 units per transaction and three decimal places. No unit conversion.

An immutable material ledger records receipt, issue to an existing production order, and admin reversal linked to the original movement. Each batch balance is the sum of signed movements, read in one snapshot. Serialized writes reject insufficient stock; actor, reason and UTC recording time are retained. Receipt metadata and material identity cannot be edited. Corrections reverse the entire movement then record the correct transaction (new batch reference for a corrected receipt). A reversed receipt cannot be issued; an issue can still be reversed to return its quantity.

Admin creates masters and reverses; admin/operator receive and issue; all three roles read. Batch history uses a sequence cursor. Order detail links to material issue history, including reversals. Materials audit remains in its own history rather than mixing meter/kg amounts into the production pcs report. Empty/error/loading states, keyboard use, mobile and existing pending-request recovery are required.

Actual consumption is a separate immutable ledger tied to an unreversed issue. Admin/operator record
productive used and unusable cutting waste in partial reports; admin reverses a report before a new
correction. Net used plus waste cannot exceed the issued quantity. Reporting does not change rack
balance, reservation allocation or WIP pcs, and an issue reversal is blocked while net reporting remains.

Next product increment: supplier return or formal PO closure after QC decisions. PRs and POs do not increase available stock or reduce shortages until a QC acceptance creates a usable batch. Hold/reject quantities remain outside available stock; planned pcs do not automatically consume material, and actual usage is recorded explicitly rather than inferred.

## Implementation plan (inline execution)

- [x] Add API acceptance tests in `tests/test_materials.py`; run them and confirm missing routes fail.
- [x] Add schema 4 in `beeloft/materials.sql`, typed inputs in `models.py`, ledger methods in `store.py`, routes in `api.py`. Verify decimal exactness, stock conservation, reversal, retry, permission, concurrency and upgrade from populated schema 3.
- [x] Extend existing dashboard with materials list, batch receipt/detail/history and issue from order; reuse `formDialog` retry and stale-response guards. Add browser acceptance checks through the temporary database runner.
- [x] Run full backend/client/browser checks; independently review changes; update README, OpenAPI and verification evidence.
- [x] Commit locally on `feature/core-materials`; keep main and GitHub unchanged.
