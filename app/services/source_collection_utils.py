from __future__ import annotations

from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from urllib.parse import parse_qs
from urllib.parse import urlparse

from app.domain.collection import CollectedImageMetadata
from app.domain.resource_variants import RESOURCE_TYPE_ORIGINAL
from app.services.image_variants import LoadedImage
from app.services.resource_paths import build_resource_relative_path
from app.services.resource_paths import resolve_resource_path_key


def build_source_relative_path(
    *,
    source_type: str,
    market_code: str,
    wallpaper_date: date,
    source_key: str,
    canonical_key: str | None,
    origin_image_url: str,
) -> str:
    file_ext = extract_file_ext_from_source_url(origin_image_url)
    return build_resource_relative_path(
        source_type=source_type,
        wallpaper_date=wallpaper_date,
        market_code=market_code,
        path_key=resolve_resource_path_key(
            source_type=source_type,
            market_code=market_code,
            source_key=source_key,
            canonical_key=canonical_key,
        ),
        resource_type=RESOURCE_TYPE_ORIGINAL,
        file_ext=file_ext,
        width=None,
        height=None,
    )


def cleanup_path(path: Path) -> None:
    if path.exists():
        path.unlink()


def guess_mime_type(*, file_ext: str, fallback: str | None) -> str:
    if fallback and fallback.startswith("image/"):
        return fallback
    return {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
    }.get(file_ext.lower(), "application/octet-stream")


def extract_file_ext_from_source_url(source_url: str) -> str:
    parsed_url = urlparse(source_url)
    query_id = parse_qs(parsed_url.query).get("id", [])
    candidates = [*query_id, parsed_url.path]
    for candidate in candidates:
        suffix = Path(candidate).suffix.lstrip(".").lower()
        if suffix:
            return suffix
    return "jpg"


def default_variant_file_ext(*, loaded_image: LoadedImage) -> str:
    if "A" in loaded_image.image.getbands() or "transparency" in loaded_image.image.info:
        return "png"
    return "jpg"


def task_type_for_trigger(trigger_type: str) -> str:
    if trigger_type == "cron":
        return "scheduled_collect"
    return "manual_collect"


def task_status_from_counts(*, success_count: int, duplicate_count: int, failure_count: int) -> str:
    if failure_count == 0:
        return "succeeded"
    if success_count > 0 or duplicate_count > 0:
        return "partially_failed"
    return "failed"


def utc_now_isoformat() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def filter_metadata_items(
    *,
    metadata_items: list[CollectedImageMetadata],
    date_from: date | None,
    date_to: date | None,
) -> list[CollectedImageMetadata]:
    if date_from is None or date_to is None:
        return metadata_items
    return [item for item in metadata_items if date_from <= item.wallpaper_date <= date_to]


def resolve_fetch_date_window(
    *,
    date_from: date | None,
    date_to: date | None,
    latest_available_fallback_days: int | None,
) -> tuple[date | None, date | None]:
    if not should_use_latest_available_fallback(
        date_from=date_from,
        date_to=date_to,
        latest_available_fallback_days=latest_available_fallback_days,
    ):
        return date_from, date_to
    assert date_from is not None
    assert latest_available_fallback_days is not None
    return date_from - timedelta(days=latest_available_fallback_days - 1), date_to


def select_metadata_items_for_collection(
    *,
    metadata_items: list[CollectedImageMetadata],
    date_from: date | None,
    date_to: date | None,
    latest_available_fallback_days: int | None,
) -> tuple[list[CollectedImageMetadata], date | None]:
    filtered_items = filter_metadata_items(
        metadata_items=metadata_items,
        date_from=date_from,
        date_to=date_to,
    )
    if filtered_items:
        return filtered_items, None
    if not should_use_latest_available_fallback(
        date_from=date_from,
        date_to=date_to,
        latest_available_fallback_days=latest_available_fallback_days,
    ):
        return filtered_items, None
    assert date_from is not None
    fallback_candidates = [item for item in metadata_items if item.wallpaper_date <= date_from]
    if not fallback_candidates:
        return [], None
    fallback_date = max(item.wallpaper_date for item in fallback_candidates)
    return (
        [item for item in fallback_candidates if item.wallpaper_date == fallback_date],
        fallback_date,
    )


def should_use_latest_available_fallback(
    *,
    date_from: date | None,
    date_to: date | None,
    latest_available_fallback_days: int | None,
) -> bool:
    return (
        latest_available_fallback_days is not None
        and latest_available_fallback_days > 1
        and date_from is not None
        and date_to is not None
        and date_from == date_to
    )


def date_to_isoformat(value: date | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()
