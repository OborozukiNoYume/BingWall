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


class CollectionMetricsSummary(BaseModel):
    window_days: int
    completed_task_count: int
    succeeded_task_count: int
    partially_failed_task_count: int
    failed_task_count: int
    successful_item_count: int
    duplicate_item_count: int
    failed_item_count: int
    success_rate_percent: float | None
    latest_finished_at_utc: str | None


class ResourceDirectorySummary(BaseModel):
    path: str
    ready_resource_count: int
    failed_resource_count: int
    total_resource_count: int


class LatestBackupSnapshotStatus(BaseModel):
    snapshot_id: str
    finished_at_utc: str
    snapshot_dir: str
    manifest_path: str
    age_hours: float


class LatestRestoreVerificationStatus(BaseModel):
    verification_id: str
    snapshot_id: str
    status: Literal["passed", "failed"]
    verified_at_utc: str
    deep_health_status: Literal["ok", "degraded", "fail"]
    public_home_status_code: int
    public_api_status_code: int
    admin_api_status_code: int
    resource_inspection_missing_count: int
    record_path: str


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
    latest_restore_verification: LatestRestoreVerificationStatus | None


class Http5xxLatestEventStatus(BaseModel):
    method: str
    path: str
    status_code: int
    trace_id: str
    error_type: str | None
    occurred_at_utc: str


class Http5xxMetricsSummary(BaseModel):
    window_hours: int
    count: int
    latest_event: Http5xxLatestEventStatus | None


class OperationsMetricsResponse(BaseModel):
    service: str
    environment: Literal["development", "test", "production"]
    timestamp: datetime
    collection: CollectionMetricsSummary
    latest_backup: LatestBackupSnapshotStatus | None
    http_5xx: Http5xxMetricsSummary


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
