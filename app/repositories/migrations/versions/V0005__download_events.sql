CREATE TABLE IF NOT EXISTS download_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wallpaper_id INTEGER NOT NULL,
    resource_id INTEGER,
    request_id TEXT NOT NULL,
    market_code TEXT,
    download_channel TEXT NOT NULL,
    client_ip_hash TEXT,
    user_agent TEXT,
    result_status TEXT NOT NULL
        CHECK (result_status IN ('redirected', 'blocked', 'degraded')),
    redirect_url TEXT,
    occurred_at_utc TEXT NOT NULL,
    created_at_utc TEXT NOT NULL,
    FOREIGN KEY (wallpaper_id) REFERENCES wallpapers (id) ON DELETE CASCADE,
    FOREIGN KEY (resource_id) REFERENCES image_resources (id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_download_events_wallpaper_occurred
    ON download_events (wallpaper_id, occurred_at_utc);

CREATE INDEX IF NOT EXISTS idx_download_events_resource_occurred
    ON download_events (resource_id, occurred_at_utc);

CREATE INDEX IF NOT EXISTS idx_download_events_result_occurred
    ON download_events (result_status, occurred_at_utc);

CREATE INDEX IF NOT EXISTS idx_download_events_market_occurred
    ON download_events (market_code, occurred_at_utc);
