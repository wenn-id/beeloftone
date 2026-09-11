# Marketplace stock reservations

Source: Beeloft One blueprint, finished-goods workflow on page 9.

## Contract

- A reservation allocates positive available sellable stock from one finished-goods receipt and
  location to a marketplace plus an external order reference.
- Active reservations reduce available quantity but do not change physical sellable quantity or
  production WIP. Reserved and available totals are derived from immutable ledgers.
- Several reservations may use one stock bucket while their active total does not exceed its
  physical sellable balance. Reservation date cannot precede the receipt date.
- Admin/operator reserve and release a whole active reservation. Every active role can read.
  References and POST retries retain existing uniqueness and Idempotency-Key behavior.
- Active reservations block source receipt correction and prevent warehouse transfers or movement
  corrections from consuming the reserved portion.

## Boundaries

Marketplace names and order references are snapshots; no marketplace API or Jubelio/WMS sync is
performed. Partial release, channel order import, pick, pack, ship, returns, stock opname, and
adjustments remain later increments. The next milestone is pick allocation from reserved stock.
