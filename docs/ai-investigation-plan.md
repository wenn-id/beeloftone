# AI investigation milestone

Source: Beeloft One Concept Blueprint, Phase 6 AI Brain. This first Phase 6 milestone provides a
read-only natural-language investigation layer over the operational ledger before any approved tool
actions are introduced.

## Contract

- A question is routed to overview, production, stockout, approvals, or contribution margin.
- A mentioned SKU, product name, order reference, or order title narrows the corresponding read model.
- Each response separates its answer, facts, findings, recommendations, source evidence, and known
  limitations. The engine and external-model status are explicit.
- Recommendations are previews with `approval_required: true` and `executable: false`.
- The endpoint performs no ledger write and can be used by admin, operator, or viewer.
- Processing is deterministic and local. No question or ledger data leaves the application.

## Deliberate limits

Language routing is keyword based and currently targets Indonesian operational questions. Evidence
uses active ledger state rather than a historical snapshot. Broad margin analysis is capped at 100
orders, while displayed findings and recommendation previews are capped to keep the response useful.
The milestone does not persist an investigation, learn from feedback, call an external language model,
or execute any proposed action. Persisted proposals, human approval, and guarded execution belong to
the next Phase 6 milestone.
