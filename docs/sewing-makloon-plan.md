# Sewing and makloon traceability

Source: Beeloft One blueprint, production system page 8. This milestone follows
bundle identity with vendor/operator, quantity out, cost, defects, missing
quantity, and turnaround time.

## Contract

- A sewing job allocates a positive quantity from one active bundle. Several
  partial jobs may use one bundle, but active allocation cannot exceed its qty.
- Assignment type is `internal` or `makloon`; assignee is the operator, line, or
  vendor name recorded at dispatch time. Cost is an exact total IDR amount.
- Dispatch does not move WIP because cutting already placed the pieces in sewing.
- Completion partitions quantity out into completed, defect, and missing. The sum
  must equal quantity out. Completed pieces move sewing to finishing. Defect and
  missing pieces move sewing to reject so every order remains quantity-balanced;
  the job retains the split between those two outcomes.
- Turnaround is the day difference between sent and returned dates.
- Admin/operator dispatch and complete. Admin corrects the whole job. Correction
  reverses all linked WIP movements and preserves the original record.
- An active job blocks correction of its bundle. Correct the job first.
- Every active role can read job lists and details. POST writes retain the existing
  Idempotency-Key recovery behavior.

## Boundaries

This version uses a free-text assignee snapshot and does not create a vendor
master, capacity schedule, invoice, payment, piece-rate formula, partial receipt,
rework decision, attachment, message, or barcode scan. One job is completed once
for its full quantity. A corrected job is replaced with a new job if necessary.

The next production milestone is finishing: thread trimming, ironing, labels,
hangtags, packaging, and completion quantity.
