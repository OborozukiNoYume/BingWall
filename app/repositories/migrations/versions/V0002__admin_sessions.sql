CREATE TABLE IF NOT EXISTS admin_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_user_id INTEGER NOT NULL,
    session_token_hash TEXT NOT NULL,
    session_version INTEGER NOT NULL,
    issued_at_utc TEXT NOT NULL,
    expires_at_utc TEXT NOT NULL,
    revoked_at_utc TEXT,
    last_seen_at_utc TEXT,
    client_ip TEXT,
    user_agent TEXT,
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    FOREIGN KEY (admin_user_id) REFERENCES admin_users (id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_admin_sessions_token_hash
    ON admin_sessions (session_token_hash);

CREATE INDEX IF NOT EXISTS idx_admin_sessions_user_expires
    ON admin_sessions (admin_user_id, expires_at_utc);
