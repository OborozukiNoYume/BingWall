CREATE TABLE IF NOT EXISTS wallpapers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL,
    source_key TEXT NOT NULL,
    market_code TEXT NOT NULL,
    wallpaper_date TEXT NOT NULL,
    title TEXT,
    subtitle TEXT,
    copyright_text TEXT,
    source_name TEXT NOT NULL,
    published_at_utc TEXT,
    location_text TEXT,
    description TEXT,
    content_status TEXT NOT NULL DEFAULT 'draft'
        CHECK (content_status IN ('draft', 'enabled', 'disabled', 'deleted')),
    is_public INTEGER NOT NULL DEFAULT 0 CHECK (is_public IN (0, 1)),
    is_downloadable INTEGER NOT NULL DEFAULT 1 CHECK (is_downloadable IN (0, 1)),
    publish_start_at_utc TEXT,
    publish_end_at_utc TEXT,
    default_resource_id INTEGER,
    origin_page_url TEXT,
    origin_image_url TEXT,
    origin_width INTEGER,
    origin_height INTEGER,
    resource_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (resource_status IN ('pending', 'ready', 'failed')),
    raw_extra_json TEXT,
    sort_weight INTEGER NOT NULL DEFAULT 0,
    deleted_at_utc TEXT,
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    UNIQUE (source_type, wallpaper_date, market_code),
    CHECK (content_status != 'enabled' OR resource_status = 'ready')
);

CREATE INDEX IF NOT EXISTS idx_wallpapers_public_listing
    ON wallpapers (content_status, resource_status, wallpaper_date);

CREATE INDEX IF NOT EXISTS idx_wallpapers_market_date
    ON wallpapers (market_code, wallpaper_date);

CREATE INDEX IF NOT EXISTS idx_wallpapers_created_at_utc
    ON wallpapers (created_at_utc);

CREATE TABLE IF NOT EXISTS image_resources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wallpaper_id INTEGER NOT NULL,
    resource_type TEXT NOT NULL,
    storage_backend TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    filename TEXT NOT NULL,
    file_ext TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    file_size_bytes INTEGER,
    width INTEGER,
    height INTEGER,
    source_url TEXT,
    source_url_hash TEXT,
    content_hash TEXT,
    downloaded_at_utc TEXT,
    integrity_check_result TEXT,
    image_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (image_status IN ('pending', 'ready', 'failed')),
    failure_reason TEXT,
    last_processed_at_utc TEXT,
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    FOREIGN KEY (wallpaper_id) REFERENCES wallpapers (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_image_resources_wallpaper_resource_type
    ON image_resources (wallpaper_id, resource_type);

CREATE INDEX IF NOT EXISTS idx_image_resources_status_processed
    ON image_resources (image_status, last_processed_at_utc);

CREATE INDEX IF NOT EXISTS idx_image_resources_source_url_hash
    ON image_resources (source_url_hash);

CREATE INDEX IF NOT EXISTS idx_image_resources_content_hash
    ON image_resources (content_hash);

CREATE TABLE IF NOT EXISTS collection_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_type TEXT NOT NULL,
    source_type TEXT NOT NULL,
    trigger_type TEXT NOT NULL,
    triggered_by TEXT,
    task_status TEXT NOT NULL
        CHECK (task_status IN ('queued', 'running', 'succeeded', 'partially_failed', 'failed')),
    request_snapshot_json TEXT,
    started_at_utc TEXT,
    finished_at_utc TEXT,
    success_count INTEGER NOT NULL DEFAULT 0 CHECK (success_count >= 0),
    duplicate_count INTEGER NOT NULL DEFAULT 0 CHECK (duplicate_count >= 0),
    failure_count INTEGER NOT NULL DEFAULT 0 CHECK (failure_count >= 0),
    error_summary TEXT,
    retry_of_task_id INTEGER,
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    FOREIGN KEY (retry_of_task_id) REFERENCES collection_tasks (id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_collection_tasks_status_created
    ON collection_tasks (task_status, created_at_utc);

CREATE INDEX IF NOT EXISTS idx_collection_tasks_trigger_created
    ON collection_tasks (trigger_type, created_at_utc);

CREATE TABLE IF NOT EXISTS collection_task_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    source_item_key TEXT,
    action_name TEXT NOT NULL,
    result_status TEXT NOT NULL,
    dedupe_hit_type TEXT,
    db_write_result TEXT,
    file_write_result TEXT,
    failure_reason TEXT,
    occurred_at_utc TEXT NOT NULL,
    FOREIGN KEY (task_id) REFERENCES collection_tasks (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_collection_task_items_task_occurred
    ON collection_task_items (task_id, occurred_at_utc);

CREATE INDEX IF NOT EXISTS idx_collection_task_items_result_status
    ON collection_task_items (result_status);

CREATE TABLE IF NOT EXISTS admin_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role_name TEXT NOT NULL,
    status TEXT NOT NULL,
    last_login_at_utc TEXT,
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_user_id INTEGER NOT NULL,
    action_type TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    before_state_json TEXT,
    after_state_json TEXT,
    request_source TEXT,
    trace_id TEXT NOT NULL,
    created_at_utc TEXT NOT NULL,
    FOREIGN KEY (admin_user_id) REFERENCES admin_users (id) ON DELETE RESTRICT
);
