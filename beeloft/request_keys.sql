BEGIN IMMEDIATE;

-- Receipt idempotency dipindahkan dari namespace per akun ke namespace global.
-- Sebelum migrasi ini PK tabel requests adalah (actor_id,key), sehingga satu idempotency key
-- dapat hidup sekali per akun. Akibatnya retry transaksi yang belum pasti oleh akun berbeda
-- tidak menemukan receipt dan menjalankan mutasi bisnis untuk kedua kalinya.

-- Receipt duplikat historis diarsipkan, bukan dibuang, supaya jejak akun yang pernah memakai
-- key yang sama tetap dapat ditelusuri bersama audit_events.request_key.
CREATE TABLE IF NOT EXISTS request_key_conflicts (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL,
    actor_id TEXT NOT NULL REFERENCES users(id),
    fingerprint TEXT NOT NULL,
    response TEXT NOT NULL,
    created_at TEXT NOT NULL,
    detected_at TEXT NOT NULL
) STRICT;

CREATE INDEX IF NOT EXISTS request_key_conflict_key
    ON request_key_conflicts(key,sequence);

CREATE TRIGGER IF NOT EXISTS request_key_conflicts_no_update
BEFORE UPDATE ON request_key_conflicts
BEGIN SELECT RAISE(ABORT,'Request key conflict archive is immutable'); END;
CREATE TRIGGER IF NOT EXISTS request_key_conflicts_no_delete
BEFORE DELETE ON request_key_conflicts
BEGIN SELECT RAISE(ABORT,'Request key conflict archive is immutable'); END;

CREATE TABLE IF NOT EXISTS requests_v54 (
    key TEXT NOT NULL PRIMARY KEY,
    actor_id TEXT NOT NULL REFERENCES users(id),
    fingerprint TEXT NOT NULL,
    response TEXT NOT NULL,
    created_at TEXT NOT NULL
) STRICT;

-- Receipt paling awal per key adalah transaksi yang mengoriginasi key tersebut.
INSERT INTO requests_v54(key,actor_id,fingerprint,response,created_at)
SELECT key,actor_id,fingerprint,response,created_at FROM requests r
WHERE r.rowid=(SELECT r2.rowid FROM requests r2 WHERE r2.key=r.key
               ORDER BY r2.created_at,r2.rowid LIMIT 1);

INSERT INTO request_key_conflicts(key,actor_id,fingerprint,response,created_at,detected_at)
SELECT key,actor_id,fingerprint,response,created_at,
       strftime('%Y-%m-%dT%H:%M:%f','now')||'+00:00'
FROM requests r
WHERE r.rowid<>(SELECT r2.rowid FROM requests r2 WHERE r2.key=r.key
                ORDER BY r2.created_at,r2.rowid LIMIT 1);

DROP TABLE requests;
ALTER TABLE requests_v54 RENAME TO requests;

CREATE INDEX IF NOT EXISTS request_actor ON requests(actor_id,created_at);

PRAGMA user_version=54;
COMMIT;
