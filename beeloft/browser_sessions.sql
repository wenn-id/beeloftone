CREATE TABLE IF NOT EXISTS browser_sessions (
    token_hash TEXT PRIMARY KEY,
    csrf_hash TEXT NOT NULL,
    user_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL CHECK(expires_at>created_at)
) STRICT;

CREATE INDEX IF NOT EXISTS idx_browser_sessions_user_expiry
    ON browser_sessions(user_id,expires_at);

PRAGMA user_version=43;
