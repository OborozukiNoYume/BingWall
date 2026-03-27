from __future__ import annotations

from datetime import UTC
from datetime import datetime
import json
import logging
import os
from pathlib import Path
import shutil
import sqlite3
from typing import Literal
from typing import cast

from app.core.config import Settings
from app.repositories.health_repository import HealthRepository
from app.schemas.health import DeepHealthResponse
from app.schemas.health import DirectoryHealthStatus
from app.schemas.health import DiskUsageStatus
from app.schemas.health import HealthDependencyStatus
from app.schemas.health import LatestRestoreVerificationStatus
from app.schemas.health import LatestCollectionTaskStatus
from app.schemas.health import ReadyHealthResponse
from app.schemas.health import ResourceDirectorySummary
from app.schemas.health import ResourceInspectionItem
from app.schemas.health import ResourceInspectionSummary
from app.services.backup_restore import RESTORE_VERIFICATION_DIR_NAME

logger = logging.getLogger(__name__)

DISK_USAGE_THRESHOLD_PERCENT = 85.0
ReadyStatus = Literal["ok", "fail"]
DeepStatus = Literal["ok", "degraded", "fail"]
InspectionAction = Literal["marked_failed", "marked_failed_and_disabled", "skipped"]


class HealthService:
    def __init__(self, settings: Settings, repository: HealthRepository) -> None:
        self.settings = settings
        self.repository = repository

    def build_ready_health(self) -> ReadyHealthResponse:
        timestamp = datetime.now(UTC)
        configuration = self._check_configuration()
        database = self._check_database()
        directories = self._check_directories()
        overall_status: ReadyStatus = "ok"
        if (
            configuration.status == "fail"
            or database.status == "fail"
            or any(directory.status == "fail" for directory in directories)
        ):
            overall_status = "fail"
        return ReadyHealthResponse(
            status=overall_status,
            service="bingwall-api",
            environment=self.settings.app_env,
            timestamp=timestamp,
            configuration=configuration,
            database=database,
            directories=directories,
        )

    def build_deep_health(self) -> DeepHealthResponse:
        ready = self.build_ready_health()
        disk_usage = self._build_disk_usage()
        latest_task = self._build_latest_collection_task()
        resource_directory = self._build_resource_directory_summary()
        latest_restore_verification = self._build_latest_restore_verification()

        overall_status: DeepStatus = "ok"
        if ready.status == "fail" or any(item.status == "fail" for item in disk_usage):
            overall_status = "fail"
        elif latest_task is None or latest_task.task_status in {"failed", "partially_failed"}:
            overall_status = "degraded"

        return DeepHealthResponse(
            status=overall_status,
            service=ready.service,
            environment=ready.environment,
            timestamp=ready.timestamp,
            configuration=ready.configuration,
            database=ready.database,
            directories=ready.directories,
            disk_usage=disk_usage,
            latest_collection_task=latest_task,
            resource_directory=resource_directory,
            latest_restore_verification=latest_restore_verification,
        )

    def _check_configuration(self) -> HealthDependencyStatus:
        required_values = {
            "app_base_url": str(self.settings.app_base_url),
            "database_path": str(self.settings.database_path),
            "storage_tmp_dir": str(self.settings.storage_tmp_dir),
            "storage_public_dir": str(self.settings.storage_public_dir),
            "storage_failed_dir": str(self.settings.storage_failed_dir),
            "backup_dir": str(self.settings.backup_dir),
        }
        missing = [name for name, value in required_values.items() if not value]
        if missing:
            return HealthDependencyStatus(
                status="fail",
                detail=f"缺少必要配置: {', '.join(missing)}",
            )
        return HealthDependencyStatus(status="ok", detail="必要配置已加载")

    def _check_database(self) -> HealthDependencyStatus:
        if not self.settings.database_path.is_file():
            return HealthDependencyStatus(
                status="fail",
                detail=f"数据库文件不存在: {self.settings.database_path}",
            )
        try:
            self.repository.check_database_ready()
        except sqlite3.Error as exc:
            return HealthDependencyStatus(
                status="fail",
                detail=f"数据库不可用: {exc}",
            )
        return HealthDependencyStatus(status="ok", detail="数据库可连接且迁移已应用")

    def _check_directories(self) -> list[DirectoryHealthStatus]:
        directories = [
            ("database_dir", self.settings.database_path.parent),
            ("storage_tmp_dir", self.settings.storage_tmp_dir),
            ("storage_public_dir", self.settings.storage_public_dir),
            ("storage_failed_dir", self.settings.storage_failed_dir),
            ("backup_dir", self.settings.backup_dir),
        ]
        return [self._build_directory_status(name=name, path=path) for name, path in directories]

    def _build_directory_status(self, *, name: str, path: Path) -> DirectoryHealthStatus:
        exists = path.exists()
        readable = exists and path.is_dir() and os_access(path, "read")
        writable = exists and path.is_dir() and os_access(path, "write")
        status: ReadyStatus = "ok" if exists and readable and writable else "fail"
        return DirectoryHealthStatus(
            name=name,
            path=str(path),
            exists=exists,
            readable=readable,
            writable=writable,
            status=status,
        )

    def _build_disk_usage(self) -> list[DiskUsageStatus]:
        targets = [
            ("database_dir", self.settings.database_path.parent),
            ("storage_public_dir", self.settings.storage_public_dir),
            ("backup_dir", self.settings.backup_dir),
        ]
        items: list[DiskUsageStatus] = []
        for name, path in targets:
            if not path.exists():
                items.append(
                    DiskUsageStatus(
                        name=name,
                        path=str(path),
                        total_bytes=0,
                        used_bytes=0,
                        free_bytes=0,
                        used_percent=0.0,
                        threshold_percent=DISK_USAGE_THRESHOLD_PERCENT,
                        status="fail",
                    )
                )
                continue
            usage = shutil.disk_usage(path)
            used_percent = 0.0
            if usage.total > 0:
                used_percent = round((usage.used / usage.total) * 100, 2)
            items.append(
                DiskUsageStatus(
                    name=name,
                    path=str(path),
                    total_bytes=usage.total,
                    used_bytes=usage.used,
                    free_bytes=usage.free,
                    used_percent=used_percent,
                    threshold_percent=DISK_USAGE_THRESHOLD_PERCENT,
                    status="ok" if used_percent < DISK_USAGE_THRESHOLD_PERCENT else "fail",
                )
            )
        return items

    def _build_latest_collection_task(self) -> LatestCollectionTaskStatus | None:
        row = self.repository.get_latest_collection_task()
        if row is None:
            return None
        return LatestCollectionTaskStatus(
            task_id=int(row["id"]),
            task_type=str(row["task_type"]),
            source_type=str(row["source_type"]),
            trigger_type=str(row["trigger_type"]),
            task_status=str(row["task_status"]),
            success_count=int(row["success_count"]),
            duplicate_count=int(row["duplicate_count"]),
            failure_count=int(row["failure_count"]),
            error_summary=_optional_text(row["error_summary"]),
            started_at_utc=_optional_text(row["started_at_utc"]),
            finished_at_utc=_optional_text(row["finished_at_utc"]),
            created_at_utc=str(row["created_at_utc"]),
            updated_at_utc=str(row["updated_at_utc"]),
        )

    def _build_resource_directory_summary(self) -> ResourceDirectorySummary:
        row = self.repository.get_resource_counts()
        return ResourceDirectorySummary(
            path=str(self.settings.storage_public_dir),
            ready_resource_count=int(row["ready_resource_count"] or 0),
            failed_resource_count=int(row["failed_resource_count"] or 0),
            total_resource_count=int(row["total_resource_count"] or 0),
        )

    def _build_latest_restore_verification(self) -> LatestRestoreVerificationStatus | None:
        records_dir = self.settings.backup_dir / RESTORE_VERIFICATION_DIR_NAME
        if not records_dir.is_dir():
            return None

        latest_record: tuple[datetime, LatestRestoreVerificationStatus] | None = None
        for record_path in sorted(records_dir.glob("*.json")):
            try:
                payload = json.loads(record_path.read_text(encoding="utf-8"))
                payload["record_path"] = str(record_path)
                record = LatestRestoreVerificationStatus.model_validate(payload)
                verified_at = datetime.fromisoformat(
                    record.verified_at_utc.replace("Z", "+00:00")
                ).astimezone(UTC)
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                logger.warning("Skip invalid restore verification record path=%s", record_path)
                continue

            if latest_record is None or verified_at > latest_record[0]:
                latest_record = (verified_at, record)

        if latest_record is None:
            return None
        return latest_record[1]


class ResourceInspectionService:
    def __init__(self, repository: HealthRepository, *, public_dir: Path) -> None:
        self.repository = repository
        self.public_dir = public_dir

    def inspect_ready_local_resources(self) -> ResourceInspectionSummary:
        scanned_at_utc = datetime.now(UTC)
        processed_at_utc = scanned_at_utc.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        rows = self.repository.list_ready_local_resources()
        items: list[ResourceInspectionItem] = []
        missing_resource_count = 0
        disabled_wallpaper_count = 0

        for row in rows:
            relative_path = str(row["relative_path"])
            resource_path = self.public_dir / relative_path
            if resource_path.is_file():
                continue

            missing_resource_count += 1
            failure_reason = f"resource inspection missing file: {relative_path}"
            disabled_wallpaper, action = self.repository.mark_resource_missing_and_sync(
                resource_id=int(row["resource_id"]),
                wallpaper_id=int(row["wallpaper_id"]),
                failure_reason=failure_reason,
                processed_at_utc=processed_at_utc,
            )
            if disabled_wallpaper:
                disabled_wallpaper_count += 1
            items.append(
                ResourceInspectionItem(
                    resource_id=int(row["resource_id"]),
                    wallpaper_id=int(row["wallpaper_id"]),
                    relative_path=relative_path,
                    action=cast(InspectionAction, action),
                    failure_reason=failure_reason,
                )
            )

        summary = ResourceInspectionSummary(
            checked_resource_count=len(rows),
            missing_resource_count=missing_resource_count,
            disabled_wallpaper_count=disabled_wallpaper_count,
            scanned_at_utc=scanned_at_utc,
            items=items,
        )
        logger.info(
            "Resource inspection completed checked=%s missing=%s disabled=%s",
            summary.checked_resource_count,
            summary.missing_resource_count,
            summary.disabled_wallpaper_count,
        )
        return summary


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def os_access(path: Path, mode: str) -> bool:
    if mode == "read":
        return os.access(path, os.R_OK)
    if mode == "write":
        return os.access(path, os.W_OK)
    msg = f"Unsupported access mode: {mode}"
    raise ValueError(msg)
