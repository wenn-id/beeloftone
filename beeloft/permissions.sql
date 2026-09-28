-- O01 (#45): izin per fungsi, cakupan unit usaha, profil akses demo berversi,
-- dan audit trail perubahan hak akses.

BEGIN IMMEDIATE;

-- Tabel izin granular pengguna
CREATE TABLE IF NOT EXISTS user_permissions (
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
        'manage_access'
    )),
    granted_by TEXT NOT NULL REFERENCES users(id),
    granted_at TEXT NOT NULL,
    PRIMARY KEY(user_id, permission)
) STRICT;

CREATE INDEX IF NOT EXISTS idx_user_permissions_user ON user_permissions(user_id);

-- Tabel penugasan unit usaha pengguna
CREATE TABLE IF NOT EXISTS user_business_units (
    user_id TEXT NOT NULL REFERENCES users(id),
    business_unit_id TEXT NOT NULL REFERENCES business_units(id),
    granted_by TEXT NOT NULL REFERENCES users(id),
    granted_at TEXT NOT NULL,
    PRIMARY KEY(user_id, business_unit_id)
) STRICT;

CREATE INDEX IF NOT EXISTS idx_user_business_units_user ON user_business_units(user_id);

-- Tabel konfigurasi profil akses (all_units, preset demo, no_self_approval)
CREATE TABLE IF NOT EXISTS user_access_profiles (
    user_id TEXT PRIMARY KEY REFERENCES users(id),
    all_units INTEGER NOT NULL DEFAULT 1 CHECK(all_units IN (0, 1)),
    preset TEXT CHECK(preset IS NULL OR length(trim(preset)) BETWEEN 1 AND 80),
    no_self_approval INTEGER NOT NULL DEFAULT 0 CHECK(no_self_approval IN (0, 1)),
    updated_by TEXT NOT NULL REFERENCES users(id),
    updated_at TEXT NOT NULL
) STRICT;

-- Tabel riwayat audit mutasi hak akses dan cakupan
CREATE TABLE IF NOT EXISTS user_access_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    user_id TEXT NOT NULL REFERENCES users(id),
    action TEXT NOT NULL CHECK(action IN (
        'grant_permission', 'revoke_permission', 'set_permissions',
        'set_preset', 'assign_unit', 'unassign_unit', 'set_units',
        'set_all_units', 'change_role', 'disable_user'
    )),
    target_type TEXT NOT NULL CHECK(target_type IN (
        'permission', 'permissions', 'business_unit', 'units', 'preset', 'all_units', 'role', 'status'
    )),
    target_value TEXT NOT NULL,
    before_value TEXT,
    after_value TEXT,
    reason TEXT NOT NULL CHECK(length(trim(reason)) BETWEEN 1 AND 1000),
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL
) STRICT;

CREATE INDEX IF NOT EXISTS idx_user_access_events_user ON user_access_events(user_id, sequence DESC);
CREATE INDEX IF NOT EXISTS idx_user_access_events_actor ON user_access_events(actor_id, sequence DESC);

PRAGMA user_version = 60;
COMMIT;
