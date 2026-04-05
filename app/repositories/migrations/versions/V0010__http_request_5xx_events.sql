CREATE TABLE IF NOT EXISTS http_request_5xx_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    method TEXT NOT NULL,
    path TEXT NOT NULL,
    status_code INTEGER NOT NULL,
    trace_id TEXT NOT NULL,
    error_type TEXT NULL,
    occurred_at_utc TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_http_request_5xx_events_occurred
    ON http_request_5xx_events (occurred_at_utc DESC, id DESC);
