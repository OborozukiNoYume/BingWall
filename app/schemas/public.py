from typing import Literal
import re

from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator


class PublicWallpaperListQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    market_code: str | None = Field(default=None, min_length=2, max_length=32)
    keyword: str | None = Field(default=None, max_length=100)
    tag_keys: str | None = Field(default=None, max_length=500)
    resolution_min_width: int | None = Field(default=None, ge=1)
    resolution_min_height: int | None = Field(default=None, ge=1)
    sort: Literal["date_desc"] = "date_desc"

    @field_validator("keyword")
    @classmethod
    def normalize_keyword(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("tag_keys")
    @classmethod
    def normalize_tag_keys(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parts = [item.strip() for item in value.split(",") if item.strip()]
        if not parts:
            return None
        invalid = [
            item for item in parts if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", item) is None
        ]
        if invalid:
            raise ValueError("tag_keys contains invalid tag key")
        return ",".join(parts)


class PublicWallpaperSummary(BaseModel):
    id: int
    title: str
    subtitle: str | None
    market_code: str
    wallpaper_date: str
    thumbnail_url: str
    detail_url: str


class PublicWallpaperListData(BaseModel):
    items: list[PublicWallpaperSummary]


class PublicWallpaperDetailData(BaseModel):
    id: int
    title: str
    subtitle: str | None
    description: str | None
    copyright_text: str | None
    market_code: str
    wallpaper_date: str
    preview_url: str
    download_url: str | None
    is_downloadable: bool
    width: int | None
    height: int | None
    source_name: str


PublicDownloadChannel = Literal["public_detail"]
PublicDownloadResultStatus = Literal["redirected", "degraded"]


class PublicDownloadEventRequest(BaseModel):
    wallpaper_id: int = Field(ge=1)
    resource_id: int | None = Field(default=None, ge=1)
    download_channel: PublicDownloadChannel


class PublicDownloadEventData(BaseModel):
    redirect_url: str
    event_id: int | None
    recorded: bool
    result_status: PublicDownloadResultStatus


class PublicMarketFilterOption(BaseModel):
    code: str
    label: str


class PublicSortFilterOption(BaseModel):
    value: Literal["date_desc"]
    label: str


class PublicTagFilterOption(BaseModel):
    id: int
    tag_key: str
    tag_name: str
    tag_category: str | None


class PublicWallpaperFiltersData(BaseModel):
    markets: list[PublicMarketFilterOption]
    tags: list[PublicTagFilterOption]
    sort_options: list[PublicSortFilterOption]


class PublicSiteInfoData(BaseModel):
    site_name: str
    site_description: str
    default_market_code: str


class PublicTagListData(BaseModel):
    items: list[PublicTagFilterOption]
