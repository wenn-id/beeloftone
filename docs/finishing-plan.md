# Finishing traceability

Source: Beeloft One blueprint, production system page 8. This milestone follows
sewing output through thread trimming, ironing, labels, hangtags, packaging, and
the quantity completed for QC.

## Contract

- A finishing record consumes a positive quantity from the completed output of
  one active sewing job. Several partial records may use one job, but their active
  total cannot exceed the sewing job's completed quantity.
- Thread trimming, ironing, labels, hangtags, and packaging are explicit required
  confirmations. Saving a completion moves its quantity from finishing to QC.
- Completion date cannot precede the sewing return date. The record keeps lineage
  through the sewing job, bundle, cutting result, and material batch.
- Admin/operator record completions. Admin corrects the whole record. Correction
  reverses its linked WIP movement and preserves the original record.
- An active finishing record blocks correction of its sewing job. Correct finishing
  first. Linked movements cannot be corrected separately.
- Every active role can read lists and details. POST writes retain the existing
  Idempotency-Key recovery behavior.

## Boundaries

This version records completed checklist confirmations rather than work-in-progress
timestamps for each finishing activity. It does not track individual workers,
stations, supplies, packaging SKUs, duration per activity, partial checkbox state,
attachments, barcode scans, or finishing defects/rework. Those exceptions continue
through the existing issue and QC flows.

The next production milestone is final QC: measurement, visual inspection, pass,
rework, reject, and acceptance quantity.
