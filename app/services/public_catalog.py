from __future__ import annotations

from datetime import UTC
from datetime import datetime
import math
from sqlite3 import Row

from app.api.errors import ApiError
from app.repositories.public_repository import PublicRepository
from app.schemas.common import Pagination
from app.schemas.public import PublicMarketFilterOption
from app.schemas.public import PublicSiteInfoData
from app.schemas.public import PublicSortFilterOption
from app.schemas.public import PublicWallpaperDetailData
from app.schemas.public import PublicWallpaperFiltersData
from app.schemas.public import PublicWallpaperListData
from app.schemas.public import PublicWallpaperListQuery
from app.schemas.public import PublicWallpaperSummary

MARKET_LABELS: dict[str, str] = {
    "de-DE": "Deutsch (Deutschland)",
    "en-GB": "English (United Kingdom)",
    "en-US": "English (United States)",
    "fr-FR": "Français (France)",
    "ja-JP": "日本語（日本）",
    "zh-CN": "中文（中国）",
}


class PublicCatalogService:
    def __init__(self, repository: PublicRepository) -> None:
        self.repository = repository

    def list_wallpapers(
        self, *, query: PublicWallpaperListQuery
    ) -> tuple[PublicWallpaperListData, Pagination]:
        current_time_utc = utc_now_isoformat()
        rows, total = self.repository.list_visible_wallpapers(
            query=query,
            current_time_utc=current_time_utc,
        )
        items = [self._build_wallpaper_summary(row) for row in rows]
        total_pages = math.ceil(total / query.page_size) if total else 0
        pagination = Pagination(
            page=query.page,
            page_size=query.page_size,
            total=total,
            total_pages=total_pages,
        )
        return PublicWallpaperListData(items=items), pagination

    def get_wallpaper_detail(self, *, wallpaper_id: int) -> PublicWallpaperDetailData:
        row = self.repository.get_visible_wallpaper_by_id(
            wallpaper_id=wallpaper_id,
            current_time_utc=utc_now_isoformat(),
        )
        if row is None:
            raise ApiError(
                status_code=404,
                error_code="PUBLIC_WALLPAPER_NOT_FOUND",
                message="壁纸不存在或不可公开访问",
            )

        image_url = build_public_image_url(relative_path=str(row["relative_path"]))
        return PublicWallpaperDetailData(
            id=int(row["id"]),
            title=present_title(row),
            subtitle=_optional_text(row["subtitle"]),
            description=_optional_text(row["description"]),
            copyright_text=_optional_text(row["copyright_text"]),
            market_code=str(row["market_code"]),
            wallpaper_date=str(row["wallpaper_date"]),
            preview_url=image_url,
            download_url=image_url if bool(row["is_downloadable"]) else None,
            is_downloadable=bool(row["is_downloadable"]),
            width=_optional_int(row["width"]),
            height=_optional_int(row["height"]),
            source_name=str(row["source_name"]),
        )

    def get_filters(self) -> PublicWallpaperFiltersData:
        market_codes = self.repository.list_visible_market_codes(
            current_time_utc=utc_now_isoformat()
        )
        return PublicWallpaperFiltersData(
            markets=[
                PublicMarketFilterOption(
                    code=market_code,
                    label=MARKET_LABELS.get(market_code, market_code),
                )
                for market_code in market_codes
            ],
            sort_options=[PublicSortFilterOption(value="date_desc", label="最新优先")],
        )

    def get_site_info(
        self, *, site_name: str, site_description: str, default_market_code: str
    ) -> PublicSiteInfoData:
        return PublicSiteInfoData(
            site_name=site_name,
            site_description=site_description,
            default_market_code=default_market_code,
        )

    def _build_wallpaper_summary(self, row: Row) -> PublicWallpaperSummary:
        wallpaper_id = int(row["id"])
        return PublicWallpaperSummary(
            id=wallpaper_id,
            title=present_title(row),
            subtitle=_optional_text(row["subtitle"]) or _optional_text(row["copyright_text"]),
            market_code=str(row["market_code"]),
            wallpaper_date=str(row["wallpaper_date"]),
            thumbnail_url=build_public_image_url(relative_path=str(row["relative_path"])),
            detail_url=f"/wallpapers/{wallpaper_id}",
        )


def present_title(row: Row) -> str:
    title = _optional_text(row["title"])
    if title:
        return title
    copyright_text = _optional_text(row["copyright_text"])
    if copyright_text:
        return copyright_text
    return f"{row['source_name']} {row['wallpaper_date']}"


def build_public_image_url(*, relative_path: str) -> str:
    return f"/images/{relative_path.lstrip('/')}"


def utc_now_isoformat() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    msg = f"Unsupported integer value type: {type(value)!r}"
    raise TypeError(msg)
