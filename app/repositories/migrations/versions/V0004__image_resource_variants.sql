CREATE UNIQUE INDEX IF NOT EXISTS uq_image_resources_wallpaper_resource_type
    ON image_resources (wallpaper_id, resource_type);
