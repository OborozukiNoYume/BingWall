from typing import Literal

from pydantic import BaseModel
from pydantic import Field


class PublicWallpaperListQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    market_code: str | None = Field(default=None, min_length=2, max_length=32)
    resolution_min_width: int | None = Field(default=None, ge=1)
    resolution_min_height: int | None = Field(default=None, ge=1)
    sort: Literal["date_desc"] = "date_desc"


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


class PublicMarketFilterOption(BaseModel):
    code: str
    label: str


class PublicSortFilterOption(BaseModel):
    value: Literal["date_desc"]
    label: str


class PublicWallpaperFiltersData(BaseModel):
    markets: list[PublicMarketFilterOption]
    sort_options: list[PublicSortFilterOption]


class PublicSiteInfoData(BaseModel):
    site_name: str
    site_description: str
    default_market_code: str
