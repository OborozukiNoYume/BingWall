from __future__ import annotations

from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta
import math
from sqlite3 import Row
from collections import defaultdict

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
    "en-AU": "English (Australia)",
    "en-CA": "English (Canada)",
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
        self,
        *,
        query: PublicWallpaperListQuery,
        default_market_code: str,
        accept_language: str | None,
    ) -> tuple[PublicWallpaperListData, Pagination]:
        current_time_utc = utc_now_isoformat()
        rows, total = self.repository.list_visible_wallpapers(
            query=query,
            current_time_utc=current_time_utc,
        )
        localizations_by_wallpaper = self._load_localizations(rows)
        items = [
            self._build_wallpaper_summary(
                row,
                self._choose_localization(
                    wallpaper_id=int(row["id"]),
                    localizations_by_wallpaper=localizations_by_wallpaper,
                    requested_market_code=query.market_code,
                    default_market_code=default_market_code,
                    accept_language=accept_language,
                ),
            )
            for row in rows
        ]
        total_pages = math.ceil(total / query.page_size) if total else 0
        pagination = Pagination(
            page=query.page,
            page_size=query.page_size,
            total=total,
            total_pages=total_pages,
        )
        return PublicWallpaperListData(items=items), pagination

    def get_wallpaper_detail(
        self,
        *,
        wallpaper_id: int,
        default_market_code: str,
        accept_language: str | None,
    ) -> PublicWallpaperDetailData:
        current_time_utc = utc_now_isoformat()
        row = self.repository.get_visible_wallpaper_by_id(
            wallpaper_id=wallpaper_id,
            current_time_utc=current_time_utc,
        )
        wallpaper_row = self._require_visible_wallpaper(row)
        return self._build_wallpaper_detail(
            wallpaper_row,
            self._choose_localization(
                wallpaper_id=int(wallpaper_row["id"]),
                localizations_by_wallpaper=self._load_localizations([wallpaper_row]),
                requested_market_code=None,
                default_market_code=default_market_code,
                accept_language=accept_language,
            ),
            self.repository.list_visible_download_resources(
                wallpaper_id=int(wallpaper_row["id"]),
                current_time_utc=current_time_utc,
            ),
        )

    def get_today_wallpaper(
        self,
        *,
        default_market_code: str,
        accept_language: str | None,
    ) -> PublicWallpaperDetailData:
        current_time_utc = utc_now_isoformat()
        row = None
        for candidate_date in (utc_today(), utc_yesterday()):
            row = self.repository.get_visible_wallpaper_for_date(
                current_time_utc=current_time_utc,
                wallpaper_date=candidate_date.isoformat(),
                default_market_code=default_market_code,
            )
            if row is not None:
                break
        wallpaper_row = self._require_visible_wallpaper(row)
        return self._build_wallpaper_detail(
            wallpaper_row,
            self._choose_localization(
                wallpaper_id=int(wallpaper_row["id"]),
                localizations_by_wallpaper=self._load_localizations([wallpaper_row]),
                requested_market_code=None,
                default_market_code=default_market_code,
                accept_language=accept_language,
            ),
            self.repository.list_visible_download_resources(
                wallpaper_id=int(wallpaper_row["id"]),
                current_time_utc=current_time_utc,
            ),
        )

    def get_latest_wallpaper_by_market(
        self,
        *,
        market_code: str,
        default_market_code: str,
        accept_language: str | None,
    ) -> PublicWallpaperDetailData:
        current_time_utc = utc_now_isoformat()
        row = self.repository.get_latest_visible_wallpaper_for_market(
            current_time_utc=current_time_utc,
            market_code=market_code,
        )
        wallpaper_row = self._require_visible_wallpaper(row)
        return self._build_wallpaper_detail(
            wallpaper_row,
            self._choose_localization(
                wallpaper_id=int(wallpaper_row["id"]),
                localizations_by_wallpaper=self._load_localizations([wallpaper_row]),
                requested_market_code=market_code,
                default_market_code=default_market_code,
                accept_language=accept_language,
            ),
            self.repository.list_visible_download_resources(
                wallpaper_id=int(wallpaper_row["id"]),
                current_time_utc=current_time_utc,
            ),
        )

    def get_wallpaper_by_date(
        self,
        *,
        wallpaper_date: date,
        default_market_code: str,
        accept_language: str | None,
    ) -> PublicWallpaperDetailData:
        current_time_utc = utc_now_isoformat()
        row = self.repository.get_visible_wallpaper_for_date(
            current_time_utc=current_time_utc,
            wallpaper_date=wallpaper_date.isoformat(),
            default_market_code=default_market_code,
        )
        wallpaper_row = self._require_visible_wallpaper(row)
        return self._build_wallpaper_detail(
            wallpaper_row,
            self._choose_localization(
                wallpaper_id=int(wallpaper_row["id"]),
                localizations_by_wallpaper=self._load_localizations([wallpaper_row]),
                requested_market_code=None,
                default_market_code=default_market_code,
                accept_language=accept_language,
            ),
            self.repository.list_visible_download_resources(
                wallpaper_id=int(wallpaper_row["id"]),
                current_time_utc=current_time_utc,
            ),
        )

    def get_random_wallpaper(
        self,
        *,
        default_market_code: str,
        accept_language: str | None,
    ) -> PublicWallpaperDetailData:
        current_time_utc = utc_now_isoformat()
        row = self.repository.get_random_visible_wallpaper(current_time_utc=current_time_utc)
        wallpaper_row = self._require_visible_wallpaper(row)
        return self._build_wallpaper_detail(
            wallpaper_row,
            self._choose_localization(
                wallpaper_id=int(wallpaper_row["id"]),
                localizations_by_wallpaper=self._load_localizations([wallpaper_row]),
                requested_market_code=None,
                default_market_code=default_market_code,
                accept_language=accept_language,
            ),
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

    def _build_wallpaper_summary(
        self,
        row: Row,
        localization_row: Row | None,
    ) -> PublicWallpaperSummary:
        wallpaper_id = int(row["id"])
        return PublicWallpaperSummary(
            id=wallpaper_id,
            title=present_title(row, localization_row=localization_row),
            subtitle=present_subtitle(row, localization_row=localization_row),
            market_code=resolved_market_code(row, localization_row=localization_row),
            resolved_market_code=resolved_market_code(row, localization_row=localization_row),
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
        localization_row: Row | None,
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
            title=present_title(row, localization_row=localization_row),
            subtitle=present_detail_text(
                row,
                localization_row=localization_row,
                key="subtitle",
            ),
            description=present_detail_text(
                row,
                localization_row=localization_row,
                key="description",
            ),
            copyright_text=present_detail_text(
                row,
                localization_row=localization_row,
                key="copyright_text",
            ),
            market_code=resolved_market_code(row, localization_row=localization_row),
            resolved_market_code=resolved_market_code(row, localization_row=localization_row),
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

    def _load_localizations(self, rows: list[Row]) -> dict[int, list[Row]]:
        wallpaper_ids = tuple(int(row["id"]) for row in rows)
        localization_map: dict[int, list[Row]] = defaultdict(list)
        for row in self.repository.list_wallpaper_localizations(wallpaper_ids=wallpaper_ids):
            localization_map[int(row["wallpaper_id"])].append(row)
        return localization_map

    def _choose_localization(
        self,
        *,
        wallpaper_id: int,
        localizations_by_wallpaper: dict[int, list[Row]],
        requested_market_code: str | None,
        default_market_code: str,
        accept_language: str | None,
    ) -> Row | None:
        localization_rows = localizations_by_wallpaper.get(wallpaper_id, [])
        if not localization_rows:
            return None
        by_market = {str(row["market_code"]): row for row in localization_rows}
        candidate_markets = [
            candidate
            for candidate in (
                requested_market_code,
                *resolve_accept_language_markets(accept_language),
                default_market_code,
            )
            if candidate
        ]
        for candidate_market in candidate_markets:
            localization = by_market.get(candidate_market)
            if localization is not None:
                return localization
        return localization_rows[0]

    def _require_visible_wallpaper(self, row: Row | None) -> Row:
        if row is None:
            raise ApiError(
                status_code=404,
                error_code="PUBLIC_WALLPAPER_NOT_FOUND",
                message="壁纸不存在或不可公开访问",
            )
        return row


def present_title(row: Row, *, localization_row: Row | None = None) -> str:
    title = _optional_text(localization_row["title"]) if localization_row is not None else None
    if title:
        return title
    title = _optional_text(row["title"])
    if title:
        return title
    copyright_text = present_detail_text(
        row,
        localization_row=localization_row,
        key="copyright_text",
    )
    if copyright_text:
        return copyright_text
    return f"{row['source_name']} {row['wallpaper_date']}"


def present_subtitle(row: Row, *, localization_row: Row | None = None) -> str | None:
    subtitle = present_detail_text(row, localization_row=localization_row, key="subtitle")
    if subtitle:
        return subtitle
    return present_detail_text(row, localization_row=localization_row, key="copyright_text")


def present_detail_text(
    row: Row,
    *,
    localization_row: Row | None,
    key: str,
) -> str | None:
    if localization_row is not None:
        localized_value = _optional_text(localization_row[key])
        if localized_value:
            return localized_value
    return _optional_text(row[key])


def resolved_market_code(row: Row, *, localization_row: Row | None) -> str:
    if localization_row is not None:
        return str(localization_row["market_code"])
    return str(row["market_code"])


def utc_now_isoformat() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def utc_today() -> date:
    return datetime.now(tz=UTC).date()


def utc_yesterday() -> date:
    return utc_today() - timedelta(days=1)


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


def resolve_accept_language_markets(header_value: str | None) -> tuple[str, ...]:
    if not header_value:
        return ()
    exact_by_lower = {market.lower(): market for market in MARKET_LABELS}
    language_matches: dict[str, list[str]] = defaultdict(list)
    for market in MARKET_LABELS:
        language_matches[market.split("-", 1)[0].lower()].append(market)

    scored: list[tuple[float, int, str]] = []
    for index, raw_part in enumerate(header_value.split(",")):
        part = raw_part.strip()
        if not part:
            continue
        language = part
        quality = 1.0
        if ";" in part:
            language, _, attrs = part.partition(";")
            language = language.strip()
            attrs = attrs.strip()
            if attrs.startswith("q="):
                try:
                    quality = float(attrs[2:])
                except ValueError:
                    quality = 0.0
        if not language or quality <= 0:
            continue
        lowered = language.lower()
        if lowered in exact_by_lower:
            scored.append((quality, -index, exact_by_lower[lowered]))
            continue
        prefix = lowered.split("-", 1)[0]
        for market in language_matches.get(prefix, []):
            scored.append((quality, -index, market))

    scored.sort(reverse=True)
    resolved: list[str] = []
    for _quality, _neg_index, market in scored:
        if market not in resolved:
            resolved.append(market)
    return tuple(resolved)


def _present_variant_key(*, variant_key: str | None, width: int | None, height: int | None) -> str:
    if variant_key:
        return variant_key
    if width is not None and height is not None:
        return f"{width}x{height}"
    return "default"
