from __future__ import annotations

from datetime import datetime
from typing import Any
from typing import Literal

from pydantic import BaseModel
from pydantic import Field
from pydantic import ValidationInfo
from pydantic import field_validator

ContentStatus = Literal["draft", "enabled", "disabled", "deleted"]
ImageStatus = Literal["pending", "ready", "failed"]
AdminTargetType = Literal["wallpaper", "admin_session"]


class AdminWallpaperListQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    content_status: ContentStatus | None = None
    image_status: ImageStatus | None = None
    market_code: str | None = Field(default=None, min_length=2, max_length=32)
    created_from_utc: datetime | None = None
    created_to_utc: datetime | None = None

    @field_validator("created_to_utc")
    @classmethod
    def validate_created_range(
        cls, value: datetime | None, info: ValidationInfo
    ) -> datetime | None:
        created_from_utc = info.data.get("created_from_utc")
        if value is not None and created_from_utc is not None and value < created_from_utc:
            raise ValueError("must be greater than or equal to created_from_utc")
        return value


class AdminWallpaperSummary(BaseModel):
    id: int
    title: str
    market_code: str
    wallpaper_date: str
    source_type: str
    source_name: str
    content_status: ContentStatus
    resource_status: str
    image_status: ImageStatus | None
    is_public: bool
    is_downloadable: bool
    preview_url: str | None
    width: int | None
    height: int | None
    failure_reason: str | None
    created_at_utc: str
    updated_at_utc: str


class AdminWallpaperListData(BaseModel):
    items: list[AdminWallpaperSummary]


class AdminAuditLogSummary(BaseModel):
    id: int
    admin_user_id: int
    admin_username: str
    action_type: str
    target_type: str
    target_id: str
    before_state: dict[str, Any] | None
    after_state: dict[str, Any] | None
    request_source: str | None
    trace_id: str
    created_at_utc: str


class AdminWallpaperDetailData(BaseModel):
    id: int
    title: str
    subtitle: str | None
    description: str | None
    location_text: str | None
    copyright_text: str | None
    source_type: str
    source_name: str
    source_key: str
    market_code: str
    wallpaper_date: str
    published_at_utc: str | None
    publish_start_at_utc: str | None
    publish_end_at_utc: str | None
    origin_page_url: str | None
    origin_image_url: str | None
    origin_width: int | None
    origin_height: int | None
    resource_relative_path: str | None
    preview_url: str | None
    resource_type: str | None
    storage_backend: str | None
    mime_type: str | None
    file_size_bytes: int | None
    width: int | None
    height: int | None
    content_status: ContentStatus
    resource_status: str
    image_status: ImageStatus | None
    is_public: bool
    is_downloadable: bool
    failure_reason: str | None
    deleted_at_utc: str | None
    created_at_utc: str
    updated_at_utc: str
    recent_operations: list[AdminAuditLogSummary]


class AdminWallpaperStatusUpdateRequest(BaseModel):
    target_status: Literal["enabled", "disabled", "deleted"]
    operator_reason: str = Field(min_length=1, max_length=200)


class AdminWallpaperStatusUpdateData(BaseModel):
    wallpaper_id: int
    previous_status: ContentStatus
    target_status: ContentStatus
    is_public: bool
    deleted_at_utc: str | None


class AdminAuditLogListQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    admin_user_id: int | None = Field(default=None, ge=1)
    target_type: AdminTargetType | None = None
    target_id: str | None = Field(default=None, min_length=1, max_length=100)
    started_from_utc: datetime | None = None
    started_to_utc: datetime | None = None

    @field_validator("started_to_utc")
    @classmethod
    def validate_started_range(
        cls, value: datetime | None, info: ValidationInfo
    ) -> datetime | None:
        started_from_utc = info.data.get("started_from_utc")
        if value is not None and started_from_utc is not None and value < started_from_utc:
            raise ValueError("must be greater than or equal to started_from_utc")
        return value


class AdminAuditLogListData(BaseModel):
    items: list[AdminAuditLogSummary]
