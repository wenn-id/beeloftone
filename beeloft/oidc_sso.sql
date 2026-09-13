CREATE TABLE IF NOT EXISTS oidc_identities (
    issuer TEXT NOT NULL,
    subject TEXT NOT NULL,
    user_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    last_login_at TEXT,
    PRIMARY KEY(issuer,subject),
    UNIQUE(issuer,user_id),
    CHECK(issuer=trim(issuer) AND length(issuer) BETWEEN 8 AND 500),
    CHECK(subject=trim(subject) AND length(subject) BETWEEN 1 AND 500)
) STRICT;

CREATE TABLE IF NOT EXISTS oidc_login_attempts (
    state_hash TEXT PRIMARY KEY,
    nonce_hash TEXT NOT NULL,
    code_verifier TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL CHECK(expires_at>created_at),
    CHECK(length(state_hash)=64),
    CHECK(length(nonce_hash)=64),
    CHECK(length(code_verifier) BETWEEN 43 AND 128)
) STRICT;

CREATE INDEX IF NOT EXISTS idx_oidc_identities_user ON oidc_identities(user_id);
CREATE INDEX IF NOT EXISTS idx_oidc_login_attempts_expiry ON oidc_login_attempts(expires_at);

PRAGMA user_version=44;
