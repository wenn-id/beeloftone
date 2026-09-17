# Rework completion and Final QC re-inspection milestone

Source: Codex audit P1 finding — *a unit sent from Final QC to rework can be moved back to QC, but cannot
legally be inspected again.*

## Reproduced pre-fix failure

Captured against `origin/main` (schema 54, application 0.83.0) before any change:

1. finishing record `FIN` puts 20 pcs into `qc`;
2. Final QC `QC-1` inspects all 20 — accepted 12, rework 8, reject 0;
3. `POST /api/movements` with `rework -> qc` returns the 8 rework pcs;
4. order balances are consistent: `qc = 8`, `rework = 0`, `warehouse = 12`;
5. `GET /api/finishing-records/{id}` reports `qc_inspected_quantity = 20`, `qc_remaining_quantity = 0`;
6. `POST /api/finishing-records/{id}/qc-records` for those 8 pcs fails:

```
HTTP 409 {"detail":"Jumlah inspeksi melebihi finishing yang belum diperiksa. Muat ulang data terbaru."}
```

The 8 pcs are physically in QC and are permanently uninspectable. Both the Python guard in
`Store.create_final_qc_record` and the SQLite trigger `final_qc_source_valid` reject the second inspection,
because both cap the sum of every Final QC row against `finishing_records.quantity`.

## Why relaxing `qc_remaining_quantity` is the wrong fix

Raising or removing that cap would make the ledger unfalsifiable: nothing would then tie an inspection to the
pieces it is allowed to inspect, an operator could inspect 200 pcs against a 20 pc finishing record, and the
`rework -> qc` movement would stay an anonymous stage transfer with no link to the inspection that produced
the rework. It would also silently corrupt first-pass yield, because the same physical piece would enter the
`accepted / inspected` population twice.

The audit of every consumer (`final_qc_records`, `finishing_records.qc_remaining_quantity`, `qc -> rework`,
`rework -> qc`, finished-goods receipts, `production_quality_insights`, both traceability walks, and the
reversal chain) showed the cap is not the problem. The missing concept is **which rework was completed, from
which inspection**. So the fix adds that entity and keeps every cap — each cap simply gets the correct
denominator.

## Domain model

```text
finishing_records
   │  (finishing -> qc)
   ▼
final_qc_records            inspection_round = 1, rework_completion_id IS NULL   ← initial inspection
   ├─ accepted_quantity  → qc -> warehouse → finished_goods_receipts
   ├─ reject_quantity    → qc -> reject
   └─ rework_quantity    → qc -> rework
                              │
                              ▼
                        rework_completions        (rework -> qc, immutable, references its source QC record)
                              │
                              ▼
                        final_qc_records          inspection_round = n+1, rework_completion_id = completion  ← re-inspection
                              ├─ accepted → finished_goods_receipts
                              ├─ reject
                              └─ rework  → next rework_completions … (unbounded cycles)
```

### `rework_completions`

| column | meaning |
| --- | --- |
| `sequence`, `id` | surrogate key and public id |
| `reference` | unique operator-facing reference |
| `final_qc_record_id` | **source Final QC record** that produced the rework being completed |
| `quantity` | pcs returned to QC by this completion |
| `completed_date` | business date the rework finished |
| `movement_id` | the single `rework -> qc` movement this completion owns (`UNIQUE`) |
| `reason`, `actor_id`, `created_at` | ledger metadata |

`rework_completion_reversals(record_id, reason, actor_id, created_at)` is the correction table, matching the
repository-wide record + reversal pattern. Both tables get `*_no_update` / `*_no_delete` triggers.

`rework_completion_id` is added without a declarative `REFERENCES` clause. The `ALTER TABLE` runs before
`rework_completions` exists, and with `foreign_keys=ON` a column pointing at a missing parent table makes
*every* insert into `final_qc_records` fail — including inserts with a NULL value — without
`PRAGMA foreign_key_check` reporting anything. Referential integrity is instead complete by construction:
`final_qc_source_valid` refuses any `rework_completion_id` that does not name an active rework completion,
and both tables are append-only, so a parent row can never be removed or altered afterwards.

### `final_qc_records` additions

| column | meaning |
| --- | --- |
| `rework_completion_id` | `NULL` for an initial inspection; the source completion for a re-inspection |
| `inspection_round` | `1` for an initial inspection; source round `+ 1` for a re-inspection |

`finishing_record_id` stays `NOT NULL` on re-inspections and always points at the same finishing record as
the lineage it descends from. That keeps every existing join — the 13-table `_final_qc_record` hydrator, the
finished-goods SKU trigger, `production_cost`, `contribution_margin`, and the six other `.sql` files that hop
`finished_goods_receipts → final_qc_records → finishing_records → … → products` — working unchanged, while
`rework_completion_id` carries the new lineage. Derived read fields: `inspection_kind`
(`initial` / `reinspection`), `rework_completion_reference`, `source_final_qc_record_id`,
`source_final_qc_reference`, `rework_completed_quantity`, `rework_remaining_quantity`.

## Invariants

**I1 — quantity conservation.** Every hop is a `movements` row written through `Store._transfer`, which
decrements the source balance, increments the target, and aborts unless
`SUM(balances) = order_lines.quantity`. A rework completion mints exactly one `rework -> qc` movement of
`quantity`; a re-inspection mints at most three movements out of `qc` summing to `inspected`. No path creates
or destroys pcs.

**I2 — initial inspection allocation.** `finishing_records.qc_inspected_quantity` and the trigger allocation
cap sum only rows with `rework_completion_id IS NULL`. A re-inspection never consumes finishing capacity
again. For every existing database this is a no-op, because today all rows are initial inspections.

**I3 — rework completion allocation.** For a source Final QC record `Q`:
`SUM(active completions of Q) + new.quantity <= Q.rework_quantity`.

Stage balances are pooled per order line, not per record, so allocation correctness rests entirely on
these record-level caps; `_transfer` is the backstop that refuses anything the pool cannot cover.

**I4 — re-inspection allocation.** For a completion `C`:
`SUM(accepted + rework + reject of active QC rows with rework_completion_id = C) + new.inspected <= C.quantity`.

**I5 — repeated cycles.** Nothing caps `inspection_round`. `QC1 → 8 rework → completion #1 → QC2 (3 accepted
+ 5 rework) → completion #2 → QC3 (5 accepted)` is legal, and so is any longer chain.

**I6 — warehouse lineage.** A re-inspection is an ordinary `final_qc_records` row, so
`POST /api/final-qc-records/{id}/finished-goods-receipts` accepts it with the same
`accepted_quantity` budget, the same SKU scan check, and the same date rule as an initial inspection.

**I7 — corrections unwind in dependency order.** Enforced twice, in triggers and in Python:

- an active rework completion blocks reversal of its source Final QC record;
- an active re-inspection blocks reversal of its rework completion;
- a completion's `rework -> qc` movement must be reversed together with the completion, and cannot be
  reversed on its own through `POST /api/movements/{id}/reverse`;
- after the downstream rows are corrected, the upstream rows correct normally.

No ledger row is ever updated or deleted; corrections only append reversal rows and compensating movements.

**I8 — dates.** `completion.completed_date >= source_qc.inspection_date`;
`reinspection.inspection_date >= completion.completed_date`; and the pre-existing
`inspection_date >= finishing.completed_date` still holds for every round, so lineage stays chronological
across cycles.

**I9 — traceability.** From a re-inspection the API resolves
`reinspection → rework completion → previous Final QC → finishing → sewing → bundle → cutting → material
batch`. `GET /api/rework-completions/{id}` and the enriched Final QC payload expose each hop, and
`material_batch_traceability` emits `rework_completion` / `rework_completion_correction` events between the
Final QC and finished-goods events.

## Generic `rework -> qc` movement

Both `("qc", "rework")` and `("rework", "qc")` are removed from `models.TRANSITIONS`, so
`POST /api/movements` now answers 422 for either route and `GET /api/stages` advertises neither. New
rework decisions must be recorded through Final QC, and all new rework returns must go through
`POST /api/final-qc-records/{id}/rework-completions`. Reversals do not consult `TRANSITIONS`, so correcting
an existing `qc -> rework` movement still works. Historical `rework -> qc` rows stay readable in
`GET /api/orders/{id}/movements`, the activity report, and traceability; nothing is deleted or rewritten.

`rework` therefore has no outgoing generic transition at all. That is deliberate: an unsalvageable piece
leaves rework the same way a salvaged one does — a rework completion returns it to QC, and the
re-inspection records it as `reject_quantity`. The disposal is then attributable to a named inspection
instead of an anonymous stage transfer. The movement form detects a line whose remaining balance sits in
rework and points the operator at that flow rather than at reversals.

### Databases migrated from schema 54

An existing database may already contain a generic `rework -> qc` movement written before this rule. Those
pieces are physically in QC while their Final QC record still reports outstanding rework, so neither the
initial-inspection route nor a rework completion can consume them. The migration deliberately does **not**
invent lineage for them, because nothing in the data says which inspection each returned piece came from.
Instead the state is reported honestly. `rework_completable_quantity` is
`min(rework_remaining_quantity, rework stage balance)` — the exact bound `_transfer` enforces — so a
line with no remaining `rework` balance reports zero. Because that balance is pooled per line, a record
can still show capacity from pieces that cannot be attributed to that record.
The UI hides "Catat selesai rework" and shows the warning per record, gated on
`rework_remaining_quantity > rework_completable_quantity`, never on the line-wide
`untraced_rework_return_quantity`, which serves only to explain a reduced bound.
`create_rework_completion` answers 409 naming the real cause.

Because stage balances are pooled per line, a later inspection that puts fresh pieces into rework also
lifts the block on an earlier record: its completion can genuinely run against the pieces that are
there. The attribution of untraced pieces is unknowable, and quantity stays conserved because the sum
of all completions can never exceed the stage balance.
The remediation is the repository's normal correction path — an admin reverses the untraced movement from
the order's movement history, which returns the pieces to rework, after which the proper completion and
re-inspection are recorded. This is documented in `operations.md`.

## Quality analytics

`production_quality_insights` keeps `first_pass_yield_percent = accepted / inspected` over **initial
inspections only**, so the metric keeps meaning one physical piece is counted once. `record_count`,
`inspected_quantity`, `accepted_quantity`, `rework_quantity`, `reject_quantity`,
`nonconforming_quantity`, `nonconforming_rate_percent`, `rework_rate_percent`, `reject_rate_percent`, the
defect-type and responsible-source breakdowns, and every `previous_*` field keep their current values and
their initial-inspection basis. Re-inspections are reported additively as `reinspection_record_count`,
`reinspected_quantity`, `reinspection_accepted_quantity`, `reinspection_rework_quantity`,
`reinspection_reject_quantity`, `reinspection_nonconforming_quantity`, and
`reinspection_nonconforming_rate_percent` at group, SKU, and summary level, and the response contract gains
`first_pass_yield_basis: "initial_inspections_only"`. `recent_records` rows gain `inspection_kind` and
`inspection_round` so the UI can label them.

Two consequences are intentional rather than incidental:

- **Repeat failures must stay actionable.** Keeping re-inspections out of `nonconforming_quantity` would
  otherwise mean goods that fail *again* after rework can never raise a flag. So an additive attention
  reason `reinspection_above_warning` fires when `reinspection_nonconforming_rate_percent` reaches
  `warning_percent`, using the re-inspection denominator only, and the command centre re-exports
  `reinspected_quantity`, `reinspection_nonconforming_quantity`, and
  `reinspection_nonconforming_rate_percent` plus a sentence on the quality attention card. Existing
  reasons, values, and thresholds are untouched. Attention groups are ranked by the worse of the two
  failure rates, so a group whose entire reworked batch failed again outranks one with a small initial
  rate — the command centre reads the first item. For data without re-inspections the re-inspection
  rate is `0.00`, so the existing order is unchanged.
- **The reported population grows.** A window containing only re-inspections now produces a group whose
  initial-basis metrics are legitimately zero, rather than dropping the data. Values of existing fields do
  not change; the set of listed groups and SKUs can. Such a group is still classified `attention` when its
  re-inspection failure rate warrants it.

## API

| method | route | role |
| --- | --- | --- |
| `POST` | `/api/final-qc-records/{record_id}/rework-completions` | admin, operator |
| `GET` | `/api/final-qc-records/{record_id}/rework-completions` | any |
| `GET` | `/api/orders/{order_id}/rework-completions` | any |
| `GET` | `/api/rework-completions/{completion_id}` | any |
| `POST` | `/api/rework-completions/{completion_id}/qc-records` | admin, operator |
| `POST` | `/api/rework-completions/{completion_id}/reverse` | admin |

Every mutating route goes through `Store._write`, so it keeps `Idempotency-Key` semantics (including the
single-actor binding), `X-Beeloft-Actor` browser binding, role authorization, one atomic
`BEGIN IMMEDIATE` transaction, an `audit_events` row, and immutable ledger behaviour.

## UI

- Final QC detail with outstanding rework offers **Catat selesai rework** (never the generic
  "Catat perpindahan"), showing `rework_completed_quantity` / `rework_remaining_quantity`.
- A completed rework record offers **Inspeksi ulang**, capped by its remaining un-reinspected quantity.
- The Final QC history distinguishes **Inspeksi awal**, **Inspeksi ulang #1**, **Inspeksi ulang #2**, …
- The re-inspection detail view links to its rework completion and to the previous Final QC record.
- Viewer role sees every list and detail read-only, with no write buttons.

## Deliberate limits

Rework labour and cost stay outside `production_cost`, which still lists `quality_control` in
`excluded_costs`. Rework is not scheduled against work centres beyond the existing
`rework -> qc` capacity route. There is no per-piece serial tracking: allocation is by quantity against a
named source record, which is the same granularity as the rest of the WIP ledger. Legacy untraced
`rework -> qc` returns are reported and remediable but not auto-converted into rework completions, because
their source inspection is genuinely unknown. Defect-type and responsible-source breakdowns stay on the
initial-inspection basis; a re-inspection failure surfaces through its own attention reason and totals, not
through those breakdowns.
