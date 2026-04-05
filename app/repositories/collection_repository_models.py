from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WallpaperCreateInput:
    source_type: str
    source_key: str
    canonical_key: str
    market_code: str
    wallpaper_date: str
    title: str | None
    subtitle: str | None
    description: str | None
    copyright_text: str | None
    source_name: str
    published_at_utc: str | None
    location_text: str | None
    origin_page_url: str | None
    origin_image_url: str
    origin_width: int | None
    origin_height: int | None
    is_downloadable: bool
    portrait_image_url: str | None
    raw_extra_json: str
    created_at_utc: str


@dataclass(frozen=True, slots=True)
class WallpaperLocalizationUpsertInput:
    wallpaper_id: int
    market_code: str
    source_key: str
    title: str | None
    subtitle: str | None
    description: str | None
    copyright_text: str | None
    published_at_utc: str | None
    location_text: str | None
    origin_page_url: str | None
    portrait_image_url: str | None
    raw_extra_json: str
    created_at_utc: str


@dataclass(frozen=True, slots=True)
class ResourceCreateInput:
    wallpaper_id: int
    resource_type: str
    storage_backend: str
    relative_path: str
    filename: str
    file_ext: str
    mime_type: str
    source_url: str | None
    source_url_hash: str | None
    created_at_utc: str
    variant_key: str = ""


@dataclass(frozen=True, slots=True)
class TaskItemCreateInput:
    task_id: int
    source_item_key: str | None
    action_name: str
    result_status: str
    dedupe_hit_type: str | None
    db_write_result: str | None
    file_write_result: str | None
    failure_reason: str | None
    occurred_at_utc: str
