# Bundling Design

## Context

The Beeloft One blueprint places bundling after cutting and before sewing or
makloon execution. A bundle gives a physical group of cut pieces a stable
identity: bundle ID, SKU/size, quantity, and production order reference.

Version 0.18 already records each cutting output as a `cutting` to `sewing`
movement linked to its material consumption and source batch. Bundling must
preserve that ledger. Creating a bundle allocates identity to pieces already in
sewing; it does not create another production movement or change WIP balances.

## Goal

Add an immutable, traceable bundle ledger that divides active cutting output by
SKU into uniquely identified physical bundles without double-counting WIP.

## Scope

- Admin and operator can create a bundle from one active output of a cutting
  run.
- A bundle has a unique physical reference, one SKU/size, a positive integer
  quantity, a reason, actor, and timestamps.
- One cutting output can be divided into several bundles. The sum of active
  bundles cannot exceed that output quantity.
- All active roles can list bundles for an order and open bundle details.
- Admin can correct a bundle as a whole. Correction releases only the identity
  allocation; it does not move WIP.
- An active bundle prevents correction of its source cutting run.
- The release includes schema migration 13 to 14, API, dashboard UI, OpenAPI,
  documentation, automated tests, and browser QA.

Barcode generation, label printing, scanning, bundle split/merge, bundle-stage
movements, vendor/makloon assignment, cost, defects, missing pieces, and
turnaround time are outside this increment.

## Chosen Architecture

Bundling is an identity overlay on the existing cutting output movement. Each
bundle references both its cutting run and the specific output movement. This
keeps the source material chain intact:

`material batch -> material issue -> cutting run -> cutting output -> bundle`

The existing production balance remains authoritative for aggregate WIP. The
bundle ledger is authoritative for identified pieces within that WIP. Later
bundle movement work can use the bundle ID without migrating free-standing or
synthetic bundle records.

Two alternatives were rejected:

- Moving pieces from cutting to sewing when creating a bundle would duplicate
  the movement already recorded by the cutting run and require redesigning the
  version 0.18 contract.
- Allowing bundles without a cutting source would be simpler but would break
  traceability to the material batch and actual cutting consumption.

## Data Model

Schema version 14 adds `bundles`:

| Column | Contract |
|---|---|
| `sequence` | Autoincrement cursor for newest-first pagination |
| `id` | UUID primary business identifier |
| `reference` | Required, trimmed, 1-160 characters, unique case-insensitively |
| `cutting_run_id` | Required source cutting run |
| `output_movement_id` | Required `cutting` to `sewing` movement contained in that run |
| `quantity` | Positive integer pieces |
| `reason` | Required, trimmed, 1-1000 characters |
| `actor_id` | User who recorded the bundle |
| `created_at` | UTC audit timestamp |

Schema version 14 also adds `bundle_reversals`:

| Column | Contract |
|---|---|
| `bundle_id` | Primary key and reference to the corrected bundle |
| `reason` | Required, trimmed, 1-1000 characters |
| `actor_id` | Admin who recorded the correction |
| `created_at` | UTC audit timestamp |

Both tables are immutable: update and delete operations fail at the SQLite
layer. A bundle is active when it has no `bundle_reversals` row.

Database triggers enforce these invariants even for direct SQL writes:

1. The cutting run exists and has no cutting-run reversal.
2. `output_movement_id` belongs to the run's `movement_ids` array.
3. The source movement is active, belongs to the same order, and is a
   `cutting` to `sewing` movement.
4. Active bundle quantities for one output, including the new quantity, do not
   exceed the movement quantity.
5. A reversal movement for a cutting output cannot be inserted while that
   output has an active bundle.

SQLite `BEGIN IMMEDIATE` serializes competing bundle writes, so two requests
cannot both consume the same remaining output.

## API Contract

All endpoints require `X-API-Key`. POST endpoints also require
`Idempotency-Key` and retain the existing replay semantics.

### Create a bundle

`POST /api/cutting-runs/{run_id}/bundles`

```json
{
  "reference": "BDL-CUT-001-M-01",
  "output_movement_id": "movement-uuid",
  "quantity": 12,
  "reason": "Bundle pertama ukuran M"
}
```

Admin and operator may create. The server rejects an unknown or corrected run,
an output outside the run, a corrected output, a duplicate reference, a
non-integer or non-positive quantity, and a quantity larger than the current
unbundled amount. A successful request returns the bundle detail with HTTP 201.

### List order bundles

`GET /api/orders/{order_id}/bundles?limit=100&before=SEQUENCE`

All active roles may read. Results are newest first. `limit` is 1-500 and
defaults to 100. `before` is omitted on the first page.

### Read one bundle

`GET /api/bundles/{bundle_id}`

The response contains bundle identity, quantity, status, actor, reason,
order ID/reference, cutting run ID/reference, cutting output movement ID,
SKU, product, color, size, source material batch, and an optional correction.

### Correct one bundle

`POST /api/bundles/{bundle_id}/reverse`

```json
{
  "reason": "Bundle ID salah ditempel"
}
```

Only admin may correct. A bundle can be corrected once. The original record
remains visible with status `corrected`; its quantity no longer contributes to
the allocated amount. Retry with the original idempotency key and payload
returns the original response.

### Cutting-run response additions

Each item in `GET /api/cutting-runs/{run_id}` `outputs` adds:

- `bundled_quantity`: sum of active bundles for the output.
- `unbundled_quantity`: output quantity minus active bundles.

The cutting-run detail also adds `bundles`, newest first, so the UI can present
the source and allocations with one read. Historical corrected bundles remain
in this list and are visibly marked.

## Store Behavior and Errors

The store validates the same invariants before insertion to return Indonesian
domain errors rather than raw SQLite messages. Expected statuses are:

- 403 for a role without write permission.
- 404 for an unknown order, cutting run, output, or bundle.
- 409 for duplicate references, corrected sources, over-allocation, repeat
  correction, concurrent state changes, or cutting correction blocked by an
  active bundle.
- 422 for malformed input or an output that does not belong to the requested
  cutting run.

Bundle creation and its idempotency receipt are one transaction. Correction
and its idempotency receipt are also one transaction. Any failure rolls back
the full write.

## Dashboard Experience

The visual direction remains the existing Beeloft operational ledger: dark ink,
restrained gold, light paper surfaces, dense readable records, ENERGY 2,
RHYTHM 2, MOTION 1.

- Order detail adds `Bundle` beside `Hasil cutting`.
- The order bundle dialog has loading, empty, populated, and error states, with
  cursor pagination.
- Cutting-run detail shows bundled and unbundled quantities on every SKU output.
- Admin/operator get `Buat bundle` only where unbundled quantity is positive.
- Bundle creation preselects the chosen output, shows SKU/size and remaining
  pieces, and requires the physical Bundle ID, quantity, and reason.
- Bundle detail links back to the production order, cutting run, and source
  material batch. Admin gets `Koreksi bundle` while it is active.
- Viewer sees all records without write controls. Operator cannot see correction
  controls.

The existing native dialog pattern provides focus containment and Escape
handling. Controls keep the 44px touch target, status uses text in addition to
color, and the layout must have no horizontal overflow at mobile width or 200%
zoom. Every control must perform a real action, and browser QA must report no
JavaScript console errors.

## Correction Semantics

Correcting a bundle means the recorded physical identity or allocation was
wrong. It does not claim that pieces physically moved between stages. The
aggregate WIP ledger therefore does not change.

When a cutting run has active bundles, its correction is rejected before any
movement or material reversal is written. The operator must correct all active
bundles first, then correct the cutting run. This order preserves the complete
audit chain and prevents a bundle from pointing at inactive output.

## Migration and Compatibility

Migration 13 to 14 creates empty bundle tables and guards. It does not invent
bundles for historical cutting output. Existing databases, movements, cutting
runs, backups, and API responses remain valid; response additions are additive.
Backup and restore automatically include the new tables because they use the
SQLite backup API.

The application version becomes 0.19.0 and OpenAPI is regenerated from the
running application.

## Verification

Backend tests cover:

- Creating partial and multiple bundles from one output.
- Multi-size isolation within one cutting run.
- Idempotent replay and conflicting key reuse.
- Role restrictions and input validation.
- Cross-run output rejection and duplicate references.
- Over-allocation and two-request allocation races.
- Whole correction and repeat-correction rejection.
- WIP totals remaining unchanged on create and correction.
- Cutting correction blocked until all active bundles are corrected.
- Transaction rollback when the request receipt fails.
- SQLite immutability and direct-write guards.
- Migration from schema 13, persistence, backup, and cursor pagination.

Browser QA covers bundle creation from cutting detail, order listing, source
links, exact retry after an uncertain response, role-specific controls,
correction, empty/loading/error states, keyboard operation, mobile layout,
200% zoom, and console errors.

The final verification runs the complete backend suite, JavaScript syntax and
client checks, dependency checks, OpenAPI validation, browser suite, and
`git diff --check`.

## Next Roadmap Step

After bundle identity is stable, the next increment is sewing or makloon
execution: assign a bundle to a vendor/operator and record quantity out, cost,
defects, missing quantity, and turnaround time without losing the material and
cutting lineage established here.
