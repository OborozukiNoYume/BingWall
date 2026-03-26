from __future__ import annotations

from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta
from typing import Literal

from pydantic import BaseModel
from pydantic import Field
from pydantic import ValidationInfo
from pydantic import field_validator
from pydantic import model_validator

from app.domain.collection_sources import COLLECTION_SOURCE_MAX_MANUAL_DAYS
from app.domain.collection_sources import CollectionSourceType
from app.domain.collection_sources import normalize_market_code

CollectionTaskStatus = Literal["queued", "running", "succeeded", "partially_failed", "failed"]
CollectionTriggerType = Literal["manual", "admin", "cron"]
CollectionItemResultStatus = Literal["succeeded", "duplicated", "failed"]


class AdminCollectionTaskCreateRequest(BaseModel):
    source_type: CollectionSourceType
    market_code: str = Field(min_length=2, max_length=32)
    date_from: date
    date_to: date
    force_refresh: bool = False

    @field_validator("market_code")
    @classmethod
    def validate_market_code(cls, value: str, info: ValidationInfo) -> str:
        source_type = info.data.get("source_type")
        if source_type is None:
            return value.strip()
        return normalize_market_code(source_type=source_type, market_code=value)

    @model_validator(mode="after")
    def validate_date_range(self) -> AdminCollectionTaskCreateRequest:
        if self.date_to < self.date_from:
            raise ValueError("结束日期不能早于开始日期")

        requested_days = (self.date_to - self.date_from).days + 1
        max_days = COLLECTION_SOURCE_MAX_MANUAL_DAYS[self.source_type]
        source_label = "Bing" if self.source_type == "bing" else "NASA APOD"
        if requested_days > max_days:
            raise ValueError(f"{source_label} 手动采集日期范围不能超过最近 {max_days} 天")

        today_utc = datetime.now(tz=UTC).date()
        earliest_supported = today_utc - timedelta(days=max_days - 1)
        if self.date_to > today_utc:
            raise ValueError("结束日期不能晚于今天")
        if self.date_from < earliest_supported:
            raise ValueError(f"{source_label} 手动采集仅支持最近 {max_days} 天内的日期")
        return self


class AdminCollectionTaskCreateData(BaseModel):
    task_id: int
    task_status: CollectionTaskStatus


class AdminCollectionTaskRetryData(BaseModel):
    task_id: int
    task_status: CollectionTaskStatus
    retry_of_task_id: int


class AdminCollectionTaskListQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    task_status: CollectionTaskStatus | None = None
    trigger_type: CollectionTriggerType | None = None
    source_type: CollectionSourceType | None = None
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


class AdminCollectionTaskSnapshot(BaseModel):
    source_type: CollectionSourceType
    market_code: str
    date_from: str | None = None
    date_to: str | None = None
    force_refresh: bool | None = None
    count: int | None = None
    trigger_type: str | None = None


class AdminCollectionTaskSummary(BaseModel):
    id: int
    task_type: str
    source_type: str
    trigger_type: str
    triggered_by: str | None
    task_status: CollectionTaskStatus
    market_code: str | None
    date_from: str | None
    date_to: str | None
    force_refresh: bool | None
    started_at_utc: str | None
    finished_at_utc: str | None
    success_count: int
    duplicate_count: int
    failure_count: int
    error_summary: str | None
    retry_of_task_id: int | None
    created_at_utc: str
    updated_at_utc: str


class AdminCollectionTaskListData(BaseModel):
    items: list[AdminCollectionTaskSummary]


class AdminCollectionTaskItemSummary(BaseModel):
    id: int
    source_item_key: str | None
    action_name: str
    result_status: CollectionItemResultStatus
    dedupe_hit_type: str | None
    db_write_result: str | None
    file_write_result: str | None
    failure_reason: str | None
    occurred_at_utc: str


class AdminCollectionTaskDetailData(AdminCollectionTaskSummary):
    request_snapshot: AdminCollectionTaskSnapshot
    items: list[AdminCollectionTaskItemSummary]


class AdminCollectionLogListQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    task_id: int | None = Field(default=None, ge=1)
    error_type: str | None = Field(default=None, min_length=1, max_length=100)
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


class AdminCollectionLogSummary(BaseModel):
    id: int
    task_id: int
    task_status: str
    source_type: str
    trigger_type: str
    source_item_key: str | None
    action_name: str
    result_status: CollectionItemResultStatus
    dedupe_hit_type: str | None
    db_write_result: str | None
    file_write_result: str | None
    failure_reason: str | None
    occurred_at_utc: str


class AdminCollectionLogListData(BaseModel):
    items: list[AdminCollectionLogSummary]
