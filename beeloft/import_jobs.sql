-- X01 (#51): kontrak impor dan dry-run importer.
--
-- 1. Melonggarkan CHECK permission pada user_permissions untuk izin baru
--    'import_data' (rebuild tabel; SQLite tidak mendukung ALTER CHECK).
-- 2. Tabel metadata job impor. INI BUKAN TABEL DOMAIN: baris-baris di sini
--    mencatat *rencana dan hasil* impor (dry-run, reject report, checkpoint),
--    bukan master/stok/jurnal/saldo. Perubahan data domain tetap terjadi
--    hanya lewat fungsi service domain (Store.create_*/change_*) saat apply.
-- 3. Watermark delta per job (cutover #61 BELUM diklaim selesai).

BEGIN IMMEDIATE;

-- --- 1. Rebuild user_permissions: tambah 'import_data' -----------------------
CREATE TABLE user_permissions_new (
    user_id TEXT NOT NULL REFERENCES users(id),
    permission TEXT NOT NULL CHECK(permission IN (
        'read_operational',
        'create_transaction',
        'approve_transaction',
        'record_payment',
        'post_ledger',
        'export_data',
        'view_salary',
        'view_margin_profit',
        'manage_access',
        'import_data'
    )),
    granted_by TEXT NOT NULL REFERENCES users(id),
    granted_at TEXT NOT NULL,
    PRIMARY KEY(user_id, permission)
) STRICT;

INSERT INTO user_permissions_new(user_id, permission, granted_by, granted_at)
    SELECT user_id, permission, granted_by, granted_at FROM user_permissions;

DROP TABLE user_permissions;

ALTER TABLE user_permissions_new RENAME TO user_permissions;

CREATE INDEX IF NOT EXISTS idx_user_permissions_user ON user_permissions(user_id);

-- --- 2. Metadata job impor ---------------------------------------------------
CREATE TABLE IF NOT EXISTS import_jobs (
    id TEXT PRIMARY KEY,
    job_ref TEXT NOT NULL UNIQUE,
    adapter TEXT NOT NULL,
    strategy TEXT NOT NULL CHECK(strategy IN ('replay_history','opening_balance','active_only')),
    status TEXT NOT NULL CHECK(status IN ('dry_run','ready','applying','applied','applied_partial','failed'))
        DEFAULT 'dry_run',
    source_system TEXT NOT NULL,
    source_account TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_sha256 TEXT NOT NULL,
    row_count INTEGER NOT NULL CHECK(row_count >= 0),
    control_totals_json TEXT NOT NULL DEFAULT '{}',
    checkpoint_json TEXT NOT NULL DEFAULT '{}',
    watermark_json TEXT NOT NULL DEFAULT '{}',
    id_map_json TEXT NOT NULL DEFAULT '{}',
    reference_mode_json TEXT NOT NULL DEFAULT '{}',
    auto_apply_revisions INTEGER NOT NULL DEFAULT 0 CHECK(auto_apply_revisions IN (0,1)),
    apply_key TEXT,
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    applied_at TEXT,
    applied_by TEXT REFERENCES users(id)
) STRICT;

CREATE INDEX IF NOT EXISTS idx_import_jobs_status ON import_jobs(status);
CREATE INDEX IF NOT EXISTS idx_import_jobs_adapter ON import_jobs(adapter);

CREATE TABLE IF NOT EXISTS import_job_rows (
    job_id TEXT NOT NULL REFERENCES import_jobs(id),
    row_no INTEGER NOT NULL CHECK(row_no >= 1),
    system TEXT NOT NULL,
    account TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_line_id TEXT,
    source_revision INTEGER NOT NULL DEFAULT 1 CHECK(source_revision >= 1),
    row_kind TEXT NOT NULL DEFAULT 'active'
        CHECK(row_kind IN ('active','history','opening_balance')),
    payload_json TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('ok','mapped','rejected','quarantined','archived','applied','failed'))
        DEFAULT 'ok',
    reject_reason TEXT,
    reject_detail TEXT,
    internal_id TEXT,
    idempotency_key TEXT,
    applied_at TEXT,
    PRIMARY KEY(job_id, row_no)
) STRICT;

CREATE INDEX IF NOT EXISTS idx_import_job_rows_identity
    ON import_job_rows(system, account, entity_type, source_id, source_line_id);

CREATE TABLE IF NOT EXISTS import_job_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    job_id TEXT NOT NULL REFERENCES import_jobs(id),
    event TEXT NOT NULL CHECK(event IN (
        'created','dry_run_completed','apply_started','row_applied',
        'apply_failed','apply_completed','resumed'
    )),
    detail_json TEXT NOT NULL DEFAULT '{}',
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;

CREATE INDEX IF NOT EXISTS idx_import_job_events_job
    ON import_job_events(job_id, sequence);

-- Event job bersifat append-only: audit trail impor tidak boleh diubah/hapus.
CREATE TRIGGER IF NOT EXISTS import_job_events_no_update
BEFORE UPDATE ON import_job_events
BEGIN
    SELECT RAISE(ABORT, 'import_job_events immutable');
END;

CREATE TRIGGER IF NOT EXISTS import_job_events_no_delete
BEFORE DELETE ON import_job_events
BEGIN
    SELECT RAISE(ABORT, 'import_job_events immutable');
END;

PRAGMA user_version = 63;
COMMIT;
