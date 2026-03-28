from dataclasses import dataclass
from dataclasses import field
from datetime import date


@dataclass(frozen=True, slots=True)
class CollectedDownloadVariant:
    variant_key: str
    source_url: str
    width: int | None
    height: int | None


@dataclass(frozen=True, slots=True)
class CollectedImageMetadata:
    market_code: str
    wallpaper_date: date
    source_key: str
    title: str | None
    copyright_text: str | None
    origin_page_url: str | None
    origin_image_url: str
    source_url_hash: str
    is_downloadable: bool
    source_name: str
    origin_width: int | None
    origin_height: int | None
    raw_extra_json: str
    download_variants: tuple[CollectedDownloadVariant, ...] = field(default_factory=tuple)


BingImageMetadata = CollectedImageMetadata


@dataclass(frozen=True, slots=True)
class DownloadedImage:
    content: bytes
    mime_type: str | None


@dataclass(frozen=True, slots=True)
class CollectionRunSummary:
    task_id: int
    task_status: str
    success_count: int
    duplicate_count: int
    failure_count: int
    error_summary: str | None
