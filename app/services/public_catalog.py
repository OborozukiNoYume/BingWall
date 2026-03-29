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
from app.schemas.public import PublicTagFilterOption
from app.schemas.public import PublicTagListData
from app.schemas.public import PublicWallpaperDownloadVariant
from app.schemas.public import PublicWallpaperDetailData
from app.schemas.public import PublicWallpaperFiltersData
from app.schemas.public import PublicWallpaperListData
from app.schemas.public import PublicWallpaperListQuery
from app.schemas.public import PublicWallpaperSummary
from app.services.resource_locator import ResourceLocator

MARKET_LABELS: dict[str, str] = {
    "de-DE": "Deutsch (Deutschland)",
    "en-GB": "English (United Kingdom)",
    "en-US": "English (United States)",
    "fr-FR": "Français (France)",
    "ja-JP": "日本語（日本）",
    "zh-CN": "中文（中国）",
}


class PublicCatalogService:
    def __init__(self, repository: PublicRepository, *, resource_locator: ResourceLocator) -> None:
        self.repository = repository
        self.resource_locator = resource_locator

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
        current_time_utc = utc_now_isoformat()
        row = self.repository.get_visible_wallpaper_by_id(
            wallpaper_id=wallpaper_id,
            current_time_utc=current_time_utc,
        )
        wallpaper_row = self._require_visible_wallpaper(row)
        return self._build_wallpaper_detail(
            wallpaper_row,
            self.repository.list_visible_download_resources(
                wallpaper_id=int(wallpaper_row["id"]),
                current_time_utc=current_time_utc,
            ),
        )

    def get_today_wallpaper(self, *, default_market_code: str) -> PublicWallpaperDetailData:
        current_time_utc = utc_now_isoformat()
        row = self.repository.get_visible_wallpaper_for_today(
            current_time_utc=current_time_utc,
            current_date=utc_today_isoformat(),
            default_market_code=default_market_code,
        )
        wallpaper_row = self._require_visible_wallpaper(row)
        return self._build_wallpaper_detail(
            wallpaper_row,
            self.repository.list_visible_download_resources(
                wallpaper_id=int(wallpaper_row["id"]),
                current_time_utc=current_time_utc,
            ),
        )

    def get_random_wallpaper(self) -> PublicWallpaperDetailData:
        current_time_utc = utc_now_isoformat()
        row = self.repository.get_random_visible_wallpaper(current_time_utc=current_time_utc)
        wallpaper_row = self._require_visible_wallpaper(row)
        return self._build_wallpaper_detail(
            wallpaper_row,
            self.repository.list_visible_download_resources(
                wallpaper_id=int(wallpaper_row["id"]),
                current_time_utc=current_time_utc,
            ),
        )

    def get_filters(self) -> PublicWallpaperFiltersData:
        market_codes = self.repository.list_visible_market_codes(
            current_time_utc=utc_now_isoformat()
        )
        tag_rows = self.repository.list_visible_tags(current_time_utc=utc_now_isoformat())
        return PublicWallpaperFiltersData(
            markets=[
                PublicMarketFilterOption(
                    code=market_code,
                    label=MARKET_LABELS.get(market_code, market_code),
                )
                for market_code in market_codes
            ],
            tags=[self._build_public_tag_option(row) for row in tag_rows],
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

    def list_tags(self) -> PublicTagListData:
        rows = self.repository.list_visible_tags(current_time_utc=utc_now_isoformat())
        return PublicTagListData(items=[self._build_public_tag_option(row) for row in rows])

    def _build_wallpaper_summary(self, row: Row) -> PublicWallpaperSummary:
        wallpaper_id = int(row["id"])
        return PublicWallpaperSummary(
            id=wallpaper_id,
            title=present_title(row),
            subtitle=_optional_text(row["subtitle"]) or _optional_text(row["copyright_text"]),
            market_code=str(row["market_code"]),
            wallpaper_date=str(row["wallpaper_date"]),
            thumbnail_url=self.resource_locator.build_required_url(
                storage_backend=_optional_text(row["storage_backend"]),
                relative_path=str(row["relative_path"]),
            ),
            detail_url=f"/wallpapers/{wallpaper_id}",
        )

    def _build_public_tag_option(self, row: Row) -> PublicTagFilterOption:
        return PublicTagFilterOption(
            id=int(row["id"]),
            tag_key=str(row["tag_key"]),
            tag_name=str(row["tag_name"]),
            tag_category=_optional_text(row["tag_category"]),
        )

    def _build_wallpaper_detail(
        self,
        row: Row,
        download_variant_rows: list[Row],
    ) -> PublicWallpaperDetailData:
        preview_url = self.resource_locator.build_required_url(
            storage_backend=_optional_text(row["preview_storage_backend"]),
            relative_path=str(row["preview_relative_path"]),
        )
        download_variants = [
            PublicWallpaperDownloadVariant(
                resource_id=int(variant_row["id"]),
                variant_key=_present_variant_key(
                    variant_key=_optional_text(variant_row["variant_key"]),
                    width=_optional_int(variant_row["width"]),
                    height=_optional_int(variant_row["height"]),
                ),
                width=_optional_int(variant_row["width"]),
                height=_optional_int(variant_row["height"]),
                download_url=self.resource_locator.build_required_url(
                    storage_backend=_optional_text(variant_row["storage_backend"]),
                    relative_path=str(variant_row["relative_path"]),
                ),
            )
            for variant_row in download_variant_rows
        ]
        default_download = download_variants[0] if download_variants else None
        return PublicWallpaperDetailData(
            id=int(row["id"]),
            title=present_title(row),
            subtitle=_optional_text(row["subtitle"]),
            description=_optional_text(row["description"]),
            copyright_text=_optional_text(row["copyright_text"]),
            market_code=str(row["market_code"]),
            wallpaper_date=str(row["wallpaper_date"]),
            preview_url=preview_url,
            download_url=(
                default_download.download_url
                if bool(row["is_downloadable"]) and default_download is not None
                else None
            ),
            download_variants=download_variants if bool(row["is_downloadable"]) else [],
            is_downloadable=bool(row["is_downloadable"]),
            width=default_download.width
            if default_download is not None
            else _optional_int(row["width"]),
            height=default_download.height
            if default_download is not None
            else _optional_int(row["height"]),
            source_name=str(row["source_name"]),
        )

    def _require_visible_wallpaper(self, row: Row | None) -> Row:
        if row is None:
            raise ApiError(
                status_code=404,
                error_code="PUBLIC_WALLPAPER_NOT_FOUND",
                message="壁纸不存在或不可公开访问",
            )
        return row


def present_title(row: Row) -> str:
    title = _optional_text(row["title"])
    if title:
        return title
    copyright_text = _optional_text(row["copyright_text"])
    if copyright_text:
        return copyright_text
    return f"{row['source_name']} {row['wallpaper_date']}"


def utc_now_isoformat() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def utc_today_isoformat() -> str:
    return datetime.now(tz=UTC).date().isoformat()


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


def _present_variant_key(*, variant_key: str | None, width: int | None, height: int | None) -> str:
    if variant_key:
        return variant_key
    if width is not None and height is not None:
        return f"{width}x{height}"
    return "default"
