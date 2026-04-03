ALTER TABLE wallpapers
    ADD COLUMN canonical_key TEXT;

UPDATE wallpapers
SET canonical_key = CASE
    WHEN source_type = 'bing' THEN REPLACE(source_key, ':' || market_code || ':', ':')
    ELSE source_key
END
WHERE canonical_key IS NULL;

CREATE TABLE IF NOT EXISTS wallpaper_localizations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wallpaper_id INTEGER NOT NULL,
    market_code TEXT NOT NULL,
    source_key TEXT NOT NULL,
    title TEXT,
    subtitle TEXT,
    description TEXT,
    copyright_text TEXT,
    published_at_utc TEXT,
    location_text TEXT,
    origin_page_url TEXT,
    portrait_image_url TEXT,
    raw_extra_json TEXT,
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    FOREIGN KEY (wallpaper_id) REFERENCES wallpapers (id) ON DELETE CASCADE,
    UNIQUE (wallpaper_id, market_code)
);

CREATE INDEX IF NOT EXISTS idx_wallpaper_localizations_market
    ON wallpaper_localizations (market_code, wallpaper_id);

CREATE INDEX IF NOT EXISTS idx_wallpaper_localizations_wallpaper
    ON wallpaper_localizations (wallpaper_id, market_code);

CREATE TEMP TABLE bing_wallpaper_merge_map AS
SELECT
    w.id AS duplicate_id,
    primary_rows.primary_id AS primary_id
FROM wallpapers AS w
INNER JOIN (
    SELECT canonical_key, MIN(id) AS primary_id
    FROM wallpapers
    WHERE source_type = 'bing'
    GROUP BY canonical_key
) AS primary_rows
    ON primary_rows.canonical_key = w.canonical_key
WHERE w.source_type = 'bing'
  AND w.id != primary_rows.primary_id;

INSERT OR IGNORE INTO wallpaper_localizations (
    wallpaper_id,
    market_code,
    source_key,
    title,
    subtitle,
    description,
    copyright_text,
    published_at_utc,
    location_text,
    origin_page_url,
    portrait_image_url,
    raw_extra_json,
    created_at_utc,
    updated_at_utc
)
SELECT
    COALESCE(merge_map.primary_id, w.id) AS wallpaper_id,
    w.market_code,
    w.source_key,
    w.title,
    w.subtitle,
    w.description,
    w.copyright_text,
    w.published_at_utc,
    w.location_text,
    w.origin_page_url,
    w.portrait_image_url,
    w.raw_extra_json,
    w.created_at_utc,
    w.updated_at_utc
FROM wallpapers AS w
LEFT JOIN bing_wallpaper_merge_map AS merge_map
    ON merge_map.duplicate_id = w.id
WHERE w.source_type = 'bing';

DELETE FROM image_resources
WHERE id IN (
    SELECT duplicate_resources.id
    FROM image_resources AS duplicate_resources
    INNER JOIN bing_wallpaper_merge_map AS merge_map
        ON merge_map.duplicate_id = duplicate_resources.wallpaper_id
    INNER JOIN image_resources AS primary_resources
        ON primary_resources.wallpaper_id = merge_map.primary_id
       AND primary_resources.resource_type = duplicate_resources.resource_type
       AND COALESCE(primary_resources.variant_key, '') = COALESCE(duplicate_resources.variant_key, '')
);

UPDATE image_resources
SET wallpaper_id = (
    SELECT primary_id
    FROM bing_wallpaper_merge_map
    WHERE duplicate_id = image_resources.wallpaper_id
)
WHERE wallpaper_id IN (SELECT duplicate_id FROM bing_wallpaper_merge_map);

INSERT OR IGNORE INTO wallpaper_tags (
    wallpaper_id,
    tag_id,
    created_at_utc,
    created_by
)
SELECT
    merge_map.primary_id,
    wallpaper_tags.tag_id,
    wallpaper_tags.created_at_utc,
    wallpaper_tags.created_by
FROM wallpaper_tags
INNER JOIN bing_wallpaper_merge_map AS merge_map
    ON merge_map.duplicate_id = wallpaper_tags.wallpaper_id;

DELETE FROM wallpaper_tags
WHERE wallpaper_id IN (SELECT duplicate_id FROM bing_wallpaper_merge_map);

UPDATE download_events
SET wallpaper_id = (
    SELECT primary_id
    FROM bing_wallpaper_merge_map
    WHERE duplicate_id = download_events.wallpaper_id
)
WHERE wallpaper_id IN (SELECT duplicate_id FROM bing_wallpaper_merge_map);

UPDATE audit_logs
SET target_id = CAST((
    SELECT primary_id
    FROM bing_wallpaper_merge_map
    WHERE duplicate_id = CAST(audit_logs.target_id AS INTEGER)
) AS TEXT)
WHERE target_type = 'wallpaper'
  AND CAST(target_id AS INTEGER) IN (SELECT duplicate_id FROM bing_wallpaper_merge_map);

DELETE FROM wallpapers
WHERE id IN (SELECT duplicate_id FROM bing_wallpaper_merge_map);

UPDATE wallpapers
SET default_resource_id = (
        SELECT id
        FROM image_resources
        WHERE wallpaper_id = wallpapers.id
          AND resource_type = 'original'
        ORDER BY id ASC
        LIMIT 1
    )
WHERE source_type = 'bing';

DROP TABLE bing_wallpaper_merge_map;

CREATE UNIQUE INDEX IF NOT EXISTS uq_wallpapers_source_canonical_key
    ON wallpapers (source_type, canonical_key);
