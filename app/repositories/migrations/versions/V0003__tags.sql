CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tag_key TEXT NOT NULL UNIQUE,
    tag_name TEXT NOT NULL,
    tag_category TEXT,
    status TEXT NOT NULL DEFAULT 'enabled'
        CHECK (status IN ('enabled', 'disabled')),
    sort_weight INTEGER NOT NULL DEFAULT 0,
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tags_status_sort
    ON tags (status, sort_weight DESC, tag_name ASC);

CREATE TABLE IF NOT EXISTS wallpaper_tags (
    wallpaper_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    created_at_utc TEXT NOT NULL,
    created_by TEXT,
    PRIMARY KEY (wallpaper_id, tag_id),
    FOREIGN KEY (wallpaper_id) REFERENCES wallpapers (id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_wallpaper_tags_tag_wallpaper
    ON wallpaper_tags (tag_id, wallpaper_id);
