from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
import logging
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import tarfile
from typing import Any
import uuid

from app.core.logging import bind_trace_id
from app.core.logging import reset_trace_id

logger = logging.getLogger(__name__)

RESTORE_VERIFICATION_DIR_NAME = "restore-verifications"
RESTORE_RECORD_DIR_NAME = "restore-records"
RESTORE_LOG_DIR_NAME = "restore-logs"


class BackupRestoreError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ServiceConfigPaths:
    nginx_config_path: Path
    systemd_service_path: Path
    tmpfiles_config_path: Path

    def to_dict(self) -> dict[str, str]:
        return {
            "nginx_config_path": str(self.nginx_config_path),
            "systemd_service_path": str(self.systemd_service_path),
            "tmpfiles_config_path": str(self.tmpfiles_config_path),
        }


@dataclass(frozen=True, slots=True)
class BackupSourcePaths:
    database_path: Path
    public_dir: Path
    config_dir: Path
    log_dir: Path
    backup_dir: Path
    service_configs: ServiceConfigPaths

    def to_dict(self) -> dict[str, Any]:
        return {
            "database_path": str(self.database_path),
            "public_dir": str(self.public_dir),
            "config_dir": str(self.config_dir),
            "log_dir": str(self.log_dir),
            "backup_dir": str(self.backup_dir),
            "service_configs": self.service_configs.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class RestoreTargetPaths:
    database_path: Path
    public_dir: Path
    config_dir: Path
    log_dir: Path
    backup_dir: Path
    service_configs: ServiceConfigPaths

    def to_dict(self) -> dict[str, Any]:
        return {
            "database_path": str(self.database_path),
            "public_dir": str(self.public_dir),
            "config_dir": str(self.config_dir),
            "log_dir": str(self.log_dir),
            "backup_dir": str(self.backup_dir),
            "service_configs": self.service_configs.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class BackupSummary:
    snapshot_id: str
    snapshot_dir: Path
    manifest_path: Path
    backup_log_path: Path
    started_at_utc: str
    finished_at_utc: str
    database_backup_path: Path
    public_archive_path: Path
    config_archive_path: Path
    logs_archive_path: Path
    service_configs_archive_path: Path

    def to_dict(self) -> dict[str, str]:
        return {
            "snapshot_id": self.snapshot_id,
            "snapshot_dir": str(self.snapshot_dir),
            "manifest_path": str(self.manifest_path),
            "backup_log_path": str(self.backup_log_path),
            "started_at_utc": self.started_at_utc,
            "finished_at_utc": self.finished_at_utc,
            "database_backup_path": str(self.database_backup_path),
            "public_archive_path": str(self.public_archive_path),
            "config_archive_path": str(self.config_archive_path),
            "logs_archive_path": str(self.logs_archive_path),
            "service_configs_archive_path": str(self.service_configs_archive_path),
        }


@dataclass(frozen=True, slots=True)
class RestoreSummary:
    restore_id: str
    snapshot_id: str
    restored_at_utc: str
    restore_log_path: Path
    restore_record_path: Path
    targets: RestoreTargetPaths

    def to_dict(self) -> dict[str, Any]:
        return {
            "restore_id": self.restore_id,
            "snapshot_id": self.snapshot_id,
            "restored_at_utc": self.restored_at_utc,
            "restore_log_path": str(self.restore_log_path),
            "restore_record_path": str(self.restore_record_path),
            "targets": self.targets.to_dict(),
        }


class OperationLogWriter:
    def __init__(self, *, log_path: Path, run_id: str, logger_name: str) -> None:
        self.log_path = log_path
        self.run_id = run_id
        self.logger = logging.getLogger(logger_name)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def write(
        self,
        *,
        level: int,
        event_type: str,
        message: str,
        context: dict[str, str | int | float | bool | None] | None = None,
    ) -> None:
        entry: dict[str, str | int | float | bool | None] = {
            "timestamp_utc": utc_now_text(),
            "level": logging.getLevelName(level),
            "trace_id": self.run_id,
            "event_type": event_type,
            "message": message,
        }
        if context:
            entry.update(context)
        with self.log_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
        self.logger.log(level, "%s event_type=%s", message, event_type)


class BackupManager:
    def create_backup(self, paths: BackupSourcePaths) -> BackupSummary:
        self._validate_backup_sources(paths)
        snapshot_id = build_operation_id(prefix="backup")
        started_at_utc = utc_now_text()
        snapshot_dir = paths.backup_dir / snapshot_id
        artifacts_dir = snapshot_dir / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=False)
        backup_log_path = snapshot_dir / "backup.log"
        log_writer = OperationLogWriter(
            log_path=backup_log_path,
            run_id=snapshot_id,
            logger_name=__name__,
        )
        trace_token = bind_trace_id(snapshot_id)
        try:
            database_backup_path = artifacts_dir / paths.database_path.name
            public_archive_path = artifacts_dir / "public-images.tar.gz"
            config_archive_path = artifacts_dir / "config.tar.gz"
            logs_archive_path = artifacts_dir / "logs.tar.gz"
            service_configs_archive_path = artifacts_dir / "service-configs.tar.gz"

            log_writer.write(
                level=logging.INFO,
                event_type="backup_started",
                message="开始执行备份",
                context={"snapshot_dir": str(snapshot_dir)},
            )

            self._backup_database_consistently(
                source_database_path=paths.database_path,
                destination_path=database_backup_path,
                log_writer=log_writer,
            )
            self._archive_directory(
                source_dir=paths.public_dir,
                destination_path=public_archive_path,
                log_writer=log_writer,
                event_type="backup_public_dir",
            )
            self._archive_directory(
                source_dir=paths.config_dir,
                destination_path=config_archive_path,
                log_writer=log_writer,
                event_type="backup_config_dir",
            )
            self._archive_directory(
                source_dir=paths.log_dir,
                destination_path=logs_archive_path,
                log_writer=log_writer,
                event_type="backup_log_dir",
            )
            self._archive_service_configs(
                service_configs=paths.service_configs,
                destination_path=service_configs_archive_path,
                log_writer=log_writer,
            )

            finished_at_utc = utc_now_text()
            manifest_path = snapshot_dir / "manifest.json"
            manifest = {
                "snapshot_id": snapshot_id,
                "started_at_utc": started_at_utc,
                "finished_at_utc": finished_at_utc,
                "source_paths": paths.to_dict(),
                "artifacts": {
                    "database_backup_path": str(database_backup_path),
                    "public_archive_path": str(public_archive_path),
                    "config_archive_path": str(config_archive_path),
                    "logs_archive_path": str(logs_archive_path),
                    "service_configs_archive_path": str(service_configs_archive_path),
                    "backup_log_path": str(backup_log_path),
                },
            }
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            log_writer.write(
                level=logging.INFO,
                event_type="backup_completed",
                message="备份执行完成",
                context={"manifest_path": str(manifest_path)},
            )
        finally:
            reset_trace_id(trace_token)

        return BackupSummary(
            snapshot_id=snapshot_id,
            snapshot_dir=snapshot_dir,
            manifest_path=manifest_path,
            backup_log_path=backup_log_path,
            started_at_utc=started_at_utc,
            finished_at_utc=finished_at_utc,
            database_backup_path=database_backup_path,
            public_archive_path=public_archive_path,
            config_archive_path=config_archive_path,
            logs_archive_path=logs_archive_path,
            service_configs_archive_path=service_configs_archive_path,
        )

    def restore_backup(
        self,
        *,
        snapshot_dir: Path,
        targets: RestoreTargetPaths,
        force: bool,
    ) -> RestoreSummary:
        manifest = load_backup_manifest(snapshot_dir)
        snapshot_id = str(manifest["snapshot_id"])
        restore_id = build_operation_id(prefix="restore")
        restore_logs_dir = targets.backup_dir / RESTORE_LOG_DIR_NAME
        restore_log_path = restore_logs_dir / f"{restore_id}.log"
        log_writer = OperationLogWriter(
            log_path=restore_log_path,
            run_id=restore_id,
            logger_name=__name__,
        )
        trace_token = bind_trace_id(restore_id)
        try:
            self._prepare_restore_targets(targets=targets, force=force)
            log_writer.write(
                level=logging.INFO,
                event_type="restore_started",
                message="开始执行恢复",
                context={"snapshot_id": snapshot_id},
            )
            artifacts = self._resolve_artifact_paths(snapshot_dir=snapshot_dir, manifest=manifest)

            self._extract_directory_archive(
                archive_path=artifacts["config_archive_path"],
                target_dir=targets.config_dir,
                log_writer=log_writer,
                event_type="restore_config_dir",
            )
            self._restore_database_file(
                source_path=artifacts["database_backup_path"],
                target_path=targets.database_path,
                log_writer=log_writer,
            )
            self._extract_directory_archive(
                archive_path=artifacts["public_archive_path"],
                target_dir=targets.public_dir,
                log_writer=log_writer,
                event_type="restore_public_dir",
            )
            self._extract_directory_archive(
                archive_path=artifacts["logs_archive_path"],
                target_dir=targets.log_dir,
                log_writer=log_writer,
                event_type="restore_log_dir",
            )
            self._restore_service_configs(
                archive_path=artifacts["service_configs_archive_path"],
                targets=targets.service_configs,
                log_writer=log_writer,
            )

            restored_at_utc = utc_now_text()
            restore_records_dir = targets.backup_dir / RESTORE_RECORD_DIR_NAME
            restore_records_dir.mkdir(parents=True, exist_ok=True)
            restore_record_path = restore_records_dir / f"{restore_id}.json"
            restore_record = {
                "restore_id": restore_id,
                "snapshot_id": snapshot_id,
                "restored_at_utc": restored_at_utc,
                "restore_log_path": str(restore_log_path),
                "targets": targets.to_dict(),
            }
            restore_record_path.write_text(
                json.dumps(restore_record, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            log_writer.write(
                level=logging.INFO,
                event_type="restore_completed",
                message="恢复执行完成",
                context={"restore_record_path": str(restore_record_path)},
            )
        finally:
            reset_trace_id(trace_token)

        return RestoreSummary(
            restore_id=restore_id,
            snapshot_id=snapshot_id,
            restored_at_utc=restored_at_utc,
            restore_log_path=restore_log_path,
            restore_record_path=restore_record_path,
            targets=targets,
        )

    def _validate_backup_sources(self, paths: BackupSourcePaths) -> None:
        if not paths.database_path.is_file():
            raise BackupRestoreError(f"数据库文件不存在: {paths.database_path}")
        for directory in (paths.public_dir, paths.config_dir, paths.log_dir):
            if not directory.is_dir():
                raise BackupRestoreError(f"备份目录不存在: {directory}")
        for config_path in (
            paths.service_configs.nginx_config_path,
            paths.service_configs.systemd_service_path,
            paths.service_configs.tmpfiles_config_path,
        ):
            if not config_path.is_file():
                raise BackupRestoreError(f"部署配置文件不存在: {config_path}")
        paths.backup_dir.mkdir(parents=True, exist_ok=True)

    def _backup_database_consistently(
        self,
        *,
        source_database_path: Path,
        destination_path: Path,
        log_writer: OperationLogWriter,
    ) -> None:
        source_connection = sqlite3.connect(source_database_path)
        destination_connection = sqlite3.connect(destination_path)
        try:
            source_connection.backup(destination_connection)
        except sqlite3.Error as exc:
            raise BackupRestoreError(f"SQLite 一致性备份失败: {exc}") from exc
        finally:
            destination_connection.close()
            source_connection.close()
        log_writer.write(
            level=logging.INFO,
            event_type="backup_database",
            message="数据库一致性备份完成",
            context={"database_backup_path": str(destination_path)},
        )

    def _archive_directory(
        self,
        *,
        source_dir: Path,
        destination_path: Path,
        log_writer: OperationLogWriter,
        event_type: str,
    ) -> None:
        with tarfile.open(destination_path, "w:gz") as archive:
            archive.add(source_dir, arcname=".")
        log_writer.write(
            level=logging.INFO,
            event_type=event_type,
            message="目录归档完成",
            context={"source_dir": str(source_dir), "archive_path": str(destination_path)},
        )

    def _archive_service_configs(
        self,
        *,
        service_configs: ServiceConfigPaths,
        destination_path: Path,
        log_writer: OperationLogWriter,
    ) -> None:
        entries = {
            "nginx": service_configs.nginx_config_path,
            "systemd": service_configs.systemd_service_path,
            "tmpfiles": service_configs.tmpfiles_config_path,
        }
        with tarfile.open(destination_path, "w:gz") as archive:
            for prefix, source_path in entries.items():
                archive.add(source_path, arcname=f"{prefix}/{source_path.name}")
        log_writer.write(
            level=logging.INFO,
            event_type="backup_service_configs",
            message="部署配置归档完成",
            context={"archive_path": str(destination_path)},
        )

    def _prepare_restore_targets(self, *, targets: RestoreTargetPaths, force: bool) -> None:
        targets.backup_dir.mkdir(parents=True, exist_ok=True)
        self._prepare_target_directory(path=targets.config_dir, force=force)
        self._prepare_target_directory(path=targets.public_dir, force=force)
        self._prepare_target_directory(path=targets.log_dir, force=force)

        targets.database_path.parent.mkdir(parents=True, exist_ok=True)
        if targets.database_path.exists():
            if not force:
                raise BackupRestoreError(
                    f"目标数据库文件已存在，恢复前请显式传入 --force: {targets.database_path}"
                )
            targets.database_path.unlink()

    def _prepare_target_directory(self, *, path: Path, force: bool) -> None:
        if path.exists():
            if not path.is_dir():
                raise BackupRestoreError(f"目标路径不是目录: {path}")
            if any(path.iterdir()):
                if not force:
                    raise BackupRestoreError(f"目标目录非空，恢复前请显式传入 --force: {path}")
                shutil.rmtree(path)
        path.mkdir(parents=True, exist_ok=True)

    def _resolve_artifact_paths(
        self,
        *,
        snapshot_dir: Path,
        manifest: dict[str, Any],
    ) -> dict[str, Path]:
        artifact_names = (
            "database_backup_path",
            "public_archive_path",
            "config_archive_path",
            "logs_archive_path",
            "service_configs_archive_path",
        )
        resolved: dict[str, Path] = {}
        artifacts = manifest.get("artifacts")
        if not isinstance(artifacts, dict):
            raise BackupRestoreError("备份清单缺少 artifacts 信息")
        for name in artifact_names:
            raw_value = artifacts.get(name)
            if not isinstance(raw_value, str):
                raise BackupRestoreError(f"备份清单缺少 {name}")
            artifact_path = Path(raw_value)
            if not artifact_path.is_absolute():
                artifact_path = snapshot_dir / artifact_path
            if not artifact_path.exists():
                raise BackupRestoreError(f"备份产物不存在: {artifact_path}")
            resolved[name] = artifact_path
        return resolved

    def _extract_directory_archive(
        self,
        *,
        archive_path: Path,
        target_dir: Path,
        log_writer: OperationLogWriter,
        event_type: str,
    ) -> None:
        with tarfile.open(archive_path, "r:gz") as archive:
            safe_members = list(iter_safe_members(archive))
            archive.extractall(target_dir, members=safe_members, filter="data")
        log_writer.write(
            level=logging.INFO,
            event_type=event_type,
            message="目录恢复完成",
            context={"target_dir": str(target_dir), "archive_path": str(archive_path)},
        )

    def _restore_database_file(
        self,
        *,
        source_path: Path,
        target_path: Path,
        log_writer: OperationLogWriter,
    ) -> None:
        shutil.copy2(source_path, target_path)
        log_writer.write(
            level=logging.INFO,
            event_type="restore_database",
            message="数据库恢复完成",
            context={"database_path": str(target_path)},
        )

    def _restore_service_configs(
        self,
        *,
        archive_path: Path,
        targets: ServiceConfigPaths,
        log_writer: OperationLogWriter,
    ) -> None:
        mapping = {
            ("nginx", targets.nginx_config_path.name): targets.nginx_config_path,
            ("systemd", targets.systemd_service_path.name): targets.systemd_service_path,
            ("tmpfiles", targets.tmpfiles_config_path.name): targets.tmpfiles_config_path,
        }
        with tarfile.open(archive_path, "r:gz") as archive:
            for member in iter_safe_members(archive):
                member_path = PurePosixPath(member.name)
                if len(member_path.parts) != 2:
                    continue
                key = (member_path.parts[0], member_path.parts[1])
                destination = mapping.get(key)
                if destination is None:
                    continue
                destination.parent.mkdir(parents=True, exist_ok=True)
                file_obj = archive.extractfile(member)
                if file_obj is None:
                    raise BackupRestoreError(f"无法读取部署配置归档成员: {member.name}")
                destination.write_bytes(file_obj.read())
        log_writer.write(
            level=logging.INFO,
            event_type="restore_service_configs",
            message="部署配置恢复完成",
            context={"archive_path": str(archive_path)},
        )


def build_restore_targets_from_root(snapshot_dir: Path, target_root: Path) -> RestoreTargetPaths:
    manifest = load_backup_manifest(snapshot_dir)
    source_paths = manifest.get("source_paths")
    if not isinstance(source_paths, dict):
        raise BackupRestoreError("备份清单缺少 source_paths 信息")
    service_configs = source_paths.get("service_configs")
    if not isinstance(service_configs, dict):
        raise BackupRestoreError("备份清单缺少 service_configs 信息")

    database_name = Path(expect_manifest_text(source_paths, "database_path")).name
    nginx_name = Path(expect_manifest_text(service_configs, "nginx_config_path")).name
    systemd_name = Path(expect_manifest_text(service_configs, "systemd_service_path")).name
    tmpfiles_name = Path(expect_manifest_text(service_configs, "tmpfiles_config_path")).name

    return RestoreTargetPaths(
        database_path=target_root / "data" / database_name,
        public_dir=target_root / "images" / "public",
        config_dir=target_root / "config",
        log_dir=target_root / "logs",
        backup_dir=target_root / "backups",
        service_configs=ServiceConfigPaths(
            nginx_config_path=target_root / "service" / "nginx" / nginx_name,
            systemd_service_path=target_root / "service" / "systemd" / systemd_name,
            tmpfiles_config_path=target_root / "service" / "tmpfiles" / tmpfiles_name,
        ),
    )


def load_backup_manifest(snapshot_dir: Path) -> dict[str, Any]:
    manifest_path = snapshot_dir / "manifest.json"
    if not manifest_path.is_file():
        raise BackupRestoreError(f"备份清单不存在: {manifest_path}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BackupRestoreError(f"备份清单无法解析: {exc}") from exc
    if not isinstance(manifest, dict):
        raise BackupRestoreError("备份清单格式错误")
    return manifest


def expect_manifest_text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise BackupRestoreError(f"备份清单字段无效: {key}")
    return value


def build_operation_id(*, prefix: str) -> str:
    return f"{prefix}-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"


def utc_now_text() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def iter_safe_members(archive: tarfile.TarFile) -> list[tarfile.TarInfo]:
    members = archive.getmembers()
    safe_members: list[tarfile.TarInfo] = []
    for member in members:
        path = PurePosixPath(member.name)
        if path.is_absolute() or ".." in path.parts:
            raise BackupRestoreError(f"归档中包含不安全路径: {member.name}")
        safe_members.append(member)
    return safe_members
