# Reservasi bahan per batch/order — Phase 2

Base `3b2f693`, worktree `feature/core-materials`, local only. Blueprint materials reservation (page 7), material planning (page 8), roadmap Phase 2.

Admin may add/release a positive amount of reservation per existing batch and order, with reason and idempotency key. No automatic allocation/BOM linkage or expiration. Reservations are additive explicit transactions, not last-write-wins totals. Immutable reservation events: reserve (+), release (-), issue consumption (- with movement ID). Remaining reservation per batch/order cannot become negative; all batch reservations cannot exceed physical rack balance. Creating/releasing reservation never moves physical stock.

An issue by admin/operator can use own reservation + free stock, never another order's reservation. It consumes min(issue quantity, own reservation) in the same transaction as stock movement and request receipt. Receipt reversal is blocked while any reservation remains; reversing an issue returns stock to free inventory, without recreating a consumed reservation. Admin must explicitly reserve again. No release/expiry on order completion or BOM change; allocations persist until issued or released and the UI explains this.

Batch read returns balance (physical), reserved (all orders), available (free), reserved_for_order and available_to_order for optional order_id. Order reservations view shows remaining allocation including zero history entries, with cursor-paged immutable events and actor/time/reason. Requirement estimates add own reservation, other reservation, free and usable-for-this-order. Shortage = max(remaining requirement − own reservation − free stock, 0). Materials reserved outside latest BOM remain visible. Keep existing stock field as physical balance. Read-only viewers can see all; only admin controls allocations; operators retain existing issue permission.

Schema 6 adds events, no changes to prior history. Use integer thousandths and existing transaction/idempotency path. No dependency additions, deployment, push or main merge.

- [x] Tests: cross-order protection, own partial consumption, free issues, release, retries, atomic rollback, concurrent reserve/issue, reversal, roles, migration, requirements.
- [x] Implement schema/models/store/API; update existing issue/reversal paths and requirement calculation.
- [x] Dashboard admin reserve/release, batch free/reserved, order allocation/history and requirement labels; browser role/retry/layout checks.
- [x] Full verification, independent review, README/OpenAPI, local commit.
