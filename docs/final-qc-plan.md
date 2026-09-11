# Final QC traceability

Source: Beeloft One blueprint, production system page 8. This milestone follows
finishing output through measurement, visual inspection, pass, rework, reject,
and accepted quantity.

## Contract

- A final QC record inspects a positive quantity from one active finishing record.
  Several partial inspections may use one finishing record, but their active total
  cannot exceed its quantity.
- Measurement notes and visual inspection notes are required. Accepted, rework,
  and reject quantities must sum to the inspected quantity and at least one outcome
  must be positive.
- Accepted pieces move QC to warehouse, rework pieces move QC to rework, and reject
  pieces move QC to reject in one transaction. Inspection date cannot precede the
  finishing completion date.
- Admin/operator record inspections. Admin corrects the whole record. Correction
  reverses all linked WIP movements and preserves the original record.
- An active final QC record blocks correction of its finishing source. Correct QC
  first. Linked movements cannot be corrected separately.
- Every active role can read lists and details. POST writes retain the existing
  Idempotency-Key recovery behavior.

## Boundaries

Measurement and visual findings are structured as required notes rather than
measurement templates or per-piece defects. This version does not store photos,
sampling plans, tolerances by SKU, defect codes, inspectors as a separate master,
rework instructions, or approval signatures. Rework returns through the existing
rework-to-QC movement and can be inspected from a later finishing/QC source only
after the physical process is represented correctly.

The next milestone is finished-goods warehouse receipt and release traceability.
