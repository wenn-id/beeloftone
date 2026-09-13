CREATE TABLE IF NOT EXISTS mekari_finance_snapshot_batches (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    sync_run_id TEXT NOT NULL UNIQUE REFERENCES integration_sync_runs(id),
    snapshot_at TEXT NOT NULL,
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS mekari_finance_snapshot_periods (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    batch_id TEXT NOT NULL REFERENCES mekari_finance_snapshot_batches(id),
    source_report_id TEXT NOT NULL,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL CHECK(period_end>=period_start),
    currency TEXT NOT NULL CHECK(currency='IDR'),
    gross_revenue_minor INTEGER NOT NULL CHECK(gross_revenue_minor BETWEEN 0 AND 100000000000000000),
    sales_returns_minor INTEGER NOT NULL CHECK(sales_returns_minor BETWEEN 0 AND gross_revenue_minor),
    cost_of_goods_sold_minor INTEGER NOT NULL CHECK(cost_of_goods_sold_minor BETWEEN 0 AND 100000000000000000),
    operating_expenses_minor INTEGER NOT NULL CHECK(operating_expenses_minor BETWEEN 0 AND 100000000000000000),
    other_income_minor INTEGER NOT NULL CHECK(other_income_minor BETWEEN 0 AND 100000000000000000),
    other_expenses_minor INTEGER NOT NULL CHECK(other_expenses_minor BETWEEN 0 AND 100000000000000000),
    cash_balance_minor INTEGER NOT NULL CHECK(cash_balance_minor BETWEEN 0 AND 100000000000000000),
    receivables_balance_minor INTEGER NOT NULL CHECK(receivables_balance_minor BETWEEN 0 AND 100000000000000000),
    payables_balance_minor INTEGER NOT NULL CHECK(payables_balance_minor BETWEEN 0 AND 100000000000000000),
    UNIQUE(batch_id,source_report_id),
    UNIQUE(batch_id,period_start,period_end)
) STRICT;

CREATE INDEX IF NOT EXISTS idx_mekari_finance_snapshot_batch
    ON mekari_finance_snapshot_periods(batch_id,period_end DESC,sequence DESC);

CREATE TRIGGER IF NOT EXISTS mekari_finance_snapshot_batches_no_update
BEFORE UPDATE ON mekari_finance_snapshot_batches BEGIN
    SELECT RAISE(ABORT,'Mekari finance snapshot batches are immutable');
END;
CREATE TRIGGER IF NOT EXISTS mekari_finance_snapshot_batches_no_delete
BEFORE DELETE ON mekari_finance_snapshot_batches BEGIN
    SELECT RAISE(ABORT,'Mekari finance snapshot batches are immutable');
END;
CREATE TRIGGER IF NOT EXISTS mekari_finance_snapshot_periods_no_update
BEFORE UPDATE ON mekari_finance_snapshot_periods BEGIN
    SELECT RAISE(ABORT,'Mekari finance snapshot periods are immutable');
END;
CREATE TRIGGER IF NOT EXISTS mekari_finance_snapshot_periods_no_delete
BEFORE DELETE ON mekari_finance_snapshot_periods BEGIN
    SELECT RAISE(ABORT,'Mekari finance snapshot periods are immutable');
END;

PRAGMA user_version=39;
