from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class LiveHealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    environment: Literal["development", "test", "production"]
    timestamp: datetime


class HealthDependencyStatus(BaseModel):
    status: Literal["ok", "fail"]
    detail: str


class DirectoryHealthStatus(BaseModel):
    name: str
    path: str
    exists: bool
    readable: bool
    writable: bool
    status: Literal["ok", "fail"]


class ReadyHealthResponse(BaseModel):
    status: Literal["ok", "fail"]
    service: str
    environment: Literal["development", "test", "production"]
    timestamp: datetime
    configuration: HealthDependencyStatus
    database: HealthDependencyStatus
    directories: list[DirectoryHealthStatus]


class DiskUsageStatus(BaseModel):
    name: str
    path: str
    total_bytes: int
    used_bytes: int
    free_bytes: int
    used_percent: float
    threshold_percent: float
    status: Literal["ok", "fail"]


class LatestCollectionTaskStatus(BaseModel):
    task_id: int
    task_type: str
    source_type: str
    trigger_type: str
    task_status: str
    success_count: int
    duplicate_count: int
    failure_count: int
    error_summary: str | None
    started_at_utc: str | None
    finished_at_utc: str | None
    created_at_utc: str
    updated_at_utc: str


class ResourceDirectorySummary(BaseModel):
    path: str
    ready_resource_count: int
    failed_resource_count: int
    total_resource_count: int


class DeepHealthResponse(BaseModel):
    status: Literal["ok", "degraded", "fail"]
    service: str
    environment: Literal["development", "test", "production"]
    timestamp: datetime
    configuration: HealthDependencyStatus
    database: HealthDependencyStatus
    directories: list[DirectoryHealthStatus]
    disk_usage: list[DiskUsageStatus]
    latest_collection_task: LatestCollectionTaskStatus | None
    resource_directory: ResourceDirectorySummary


class ResourceInspectionItem(BaseModel):
    resource_id: int
    wallpaper_id: int
    relative_path: str
    action: Literal["marked_failed", "marked_failed_and_disabled", "skipped"]
    failure_reason: str | None


class ResourceInspectionSummary(BaseModel):
    checked_resource_count: int
    missing_resource_count: int
    disabled_wallpaper_count: int
    scanned_at_utc: datetime
    items: list[ResourceInspectionItem]
