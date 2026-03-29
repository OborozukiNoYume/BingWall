ALTER TABLE image_resources
    ADD COLUMN variant_key TEXT NOT NULL DEFAULT '';

DROP INDEX IF EXISTS uq_image_resources_wallpaper_resource_type;

CREATE UNIQUE INDEX IF NOT EXISTS uq_image_resources_wallpaper_resource_variant
    ON image_resources (wallpaper_id, resource_type, variant_key);
