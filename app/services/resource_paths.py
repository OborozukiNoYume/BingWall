from __future__ import annotations

from datetime import date
import re

from app.domain.resource_variants import RESOURCE_TYPE_ORIGINAL
from app.domain.resource_variants import ResourceType

SAFE_NAME_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")


def build_resource_relative_path(
    *,
    source_type: str,
    wallpaper_date: date,
    market_code: str,
    resource_type: ResourceType,
    file_ext: str,
    width: int | None,
    height: int | None,
    variant_key: str = "",
) -> str:
    safe_source_type = _sanitize_name(source_type, fallback="unknown-source")
    safe_market_code = _sanitize_name(market_code, fallback="unknown-market")
    safe_file_ext = _sanitize_name(file_ext.lower(), fallback="jpg")
    resolution_label = build_resolution_label(
        width=width,
        height=height,
        variant_key=variant_key,
    )
    filename = build_resource_filename(
        wallpaper_date=wallpaper_date,
        market_code=safe_market_code,
        resource_type=resource_type,
        resolution_label=resolution_label,
    )
    return (
        f"{safe_source_type}/{wallpaper_date.year:04d}/{wallpaper_date.month:02d}/"
        f"{filename}.{safe_file_ext}"
    )


def build_resolution_label(
    *,
    width: int | None,
    height: int | None,
    variant_key: str = "",
) -> str:
    if width is not None and height is not None and width > 0 and height > 0:
        return f"{width}x{height}"
    if variant_key:
        return _sanitize_name(variant_key.lower(), fallback="unknown")
    return "unknown"


def build_resource_filename(
    *,
    wallpaper_date: date,
    market_code: str,
    resource_type: ResourceType,
    resolution_label: str,
) -> str:
    prefix = f"{wallpaper_date.day:02d}_{market_code}"
    if resource_type == RESOURCE_TYPE_ORIGINAL:
        return f"{prefix}_{resolution_label}"
    return f"{prefix}_{resource_type}_{resolution_label}"


def _sanitize_name(value: str, *, fallback: str) -> str:
    sanitized = SAFE_NAME_PATTERN.sub("-", value).strip("-._")
    if not sanitized:
        return fallback
    return sanitized
