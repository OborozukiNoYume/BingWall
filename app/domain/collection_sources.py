from __future__ import annotations

from typing import Literal

CollectionSourceType = Literal["bing", "nasa_apod"]

COLLECTION_SOURCE_TYPES: tuple[CollectionSourceType, ...] = ("bing", "nasa_apod")
COLLECTION_SOURCE_DISPLAY_NAMES: dict[CollectionSourceType, str] = {
    "bing": "Bing",
    "nasa_apod": "NASA APOD",
}
COLLECTION_SOURCE_DEFAULT_MARKETS: dict[CollectionSourceType, str] = {
    "bing": "en-US",
    "nasa_apod": "global",
}
COLLECTION_SOURCE_MAX_MANUAL_DAYS: dict[CollectionSourceType, int] = {
    "bing": 8,
    "nasa_apod": 8,
}


def normalize_market_code(*, source_type: CollectionSourceType, market_code: str) -> str:
    normalized = market_code.strip()
    if not normalized:
        raise ValueError("地区不能为空")
    if source_type == "bing":
        if "-" not in normalized:
            raise ValueError("Bing 地区格式不正确")
        return normalized
    if normalized != "global":
        raise ValueError("NASA APOD 仅支持 global 地区")
    return normalized
