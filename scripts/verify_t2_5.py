#!/usr/bin/env python3
from __future__ import annotations

from datetime import UTC, datetime
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
from typing import Literal, cast

from fastapi.testclient import TestClient

from app.core.config import reset_settings_cache
from app.core.security import hash_password
from app.main import create_app
from app.repositories.health_repository import HealthRepository
from app.repositories.migrations import migrate_database
from app.services.backup_restore import RESTORE_VERIFICATION_DIR_NAME
from app.services.backup_restore import build_operation_id
from app.services.health import ResourceInspectionService
from app.schemas.health import LatestRestoreVerificationStatus

REPO_ROOT = Path(__file__).resolve().parents[1]
JPEG_BYTES = b"\xff\xd8\xff\xdbt2-5-restore-smoke-jpeg"
ENV_KEYS = (
    "BINGWALL_APP_ENV",
    "BINGWALL_APP_HOST",
    "BINGWALL_APP_PORT",
    "BINGWALL_APP_BASE_URL",
    "BINGWALL_SITE_NAME",
    "BINGWALL_SITE_DESCRIPTION",
    "BINGWALL_DATABASE_PATH",
    "BINGWALL_STORAGE_TMP_DIR",
    "BINGWALL_STORAGE_PUBLIC_DIR",
    "BINGWALL_STORAGE_FAILED_DIR",
    "BINGWALL_BACKUP_DIR",
    "BINGWALL_COLLECT_BING_ENABLED",
    "BINGWALL_COLLECT_BING_DEFAULT_MARKET",
    "BINGWALL_COLLECT_BING_TIMEOUT_SECONDS",
    "BINGWALL_COLLECT_BING_MAX_DOWNLOAD_RETRIES",
    "BINGWALL_SECURITY_SESSION_SECRET",
    "BINGWALL_SECURITY_SESSION_TTL_HOURS",
    "BINGWALL_LOG_LEVEL",
)


def main() -> int:
    workspace = Path(tempfile.mkdtemp(prefix="bingwall-t2-5-"))
    source_root = workspace / "source-runtime"
    restored_root = workspace / "restored-runtime"

    prepare_source_runtime(source_root)
    backup_summary = run_json_command([
        sys.executable,
        str(REPO_ROOT / "scripts" / "run_backup.py"),
        "--database-path",
        str(source_root / "data" / "bingwall.sqlite3"),
        "--public-dir",
        str(source_root / "images" / "public"),
        "--config-dir",
        str(source_root / "config"),
        "--log-dir",
        str(source_root / "logs"),
        "--backup-dir",
        str(source_root / "backups"),
        "--nginx-config-path",
        str(source_root / "service" / "nginx" / "bingwall.conf"),
        "--systemd-service-path",
        str(source_root / "service" / "systemd" / "bingwall-api.service"),
        "--tmpfiles-config-path",
        str(source_root / "service" / "tmpfiles" / "bingwall.conf"),
    ])
    restore_summary = run_json_command([
        sys.executable,
        str(REPO_ROOT / "scripts" / "run_restore.py"),
        "--snapshot",
        str(backup_summary["snapshot_dir"]),
        "--target-root",
        str(restored_root),
        "--force",
    ])

    (restored_root / "images" / "tmp").mkdir(parents=True, exist_ok=True)
    (restored_root / "images" / "failed").mkdir(parents=True, exist_ok=True)

    with build_client(restored_root) as client:
        public_home_response = client.get("/")
        public_api_response = client.get("/api/public/site-info")
        login_response = client.post(
            "/api/admin/auth/login",
            json={"username": "admin", "password": "correct-password"},
        )
        session_token = login_response.json()["data"]["session_token"]
        admin_api_response = client.get(
            "/api/admin/wallpapers",
            headers={"Authorization": f"Bearer {session_token}"},
        )
        deep_health_before_record = client.get("/api/health/deep")

    inspection_summary = run_resource_inspection(restored_root)
    verification_record_path = write_restore_verification_record(
        restored_root=restored_root,
        snapshot_id=str(restore_summary["snapshot_id"]),
        public_home_status_code=public_home_response.status_code,
        public_api_status_code=public_api_response.status_code,
        admin_api_status_code=admin_api_response.status_code,
        deep_health_status=str(deep_health_before_record.json()["status"]),
        resource_inspection_missing_count=cast(int, inspection_summary["missing_resource_count"]),
    )

    with build_client(restored_root) as client:
        deep_health_after_record = client.get("/api/health/deep")

    payload = deep_health_after_record.json()
    assert payload["status"] == "ok"
    assert payload["latest_restore_verification"]["record_path"] == str(verification_record_path)
    assert payload["latest_restore_verification"]["status"] == "passed"
    assert public_home_response.status_code == 200
    assert public_api_response.status_code == 200
    assert admin_api_response.status_code == 200
    assert inspection_summary["missing_resource_count"] == 0

    print(
        json.dumps(
            {
                "workspace": str(workspace),
                "backup_summary": backup_summary,
                "restore_summary": restore_summary,
                "verification_record_path": str(verification_record_path),
                "deep_health_status": payload["status"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


def prepare_source_runtime(root: Path) -> None:
    database_path = root / "data" / "bingwall.sqlite3"
    public_dir = root / "images" / "public"
    config_dir = root / "config"
    log_dir = root / "logs"
    backup_dir = root / "backups"
    nginx_dir = root / "service" / "nginx"
    systemd_dir = root / "service" / "systemd"
    tmpfiles_dir = root / "service" / "tmpfiles"

    public_dir.mkdir(parents=True, exist_ok=True)
    config_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    backup_dir.mkdir(parents=True, exist_ok=True)
    nginx_dir.mkdir(parents=True, exist_ok=True)
    systemd_dir.mkdir(parents=True, exist_ok=True)
    tmpfiles_dir.mkdir(parents=True, exist_ok=True)
    migrate_database(database_path)

    relative_path = Path("bing/2026/03/en-US/t2-5-restore.jpg")
    image_path = public_dir / relative_path
    image_path.parent.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(JPEG_BYTES)

    now_utc = utc_now_text()
    connection = sqlite3.connect(database_path)
    try:
        cursor = connection.execute(
            """
            INSERT INTO wallpapers (
                source_type,
                source_key,
                market_code,
                wallpaper_date,
                title,
                subtitle,
                description,
                copyright_text,
                source_name,
                content_status,
                is_public,
                is_downloadable,
                publish_start_at_utc,
                publish_end_at_utc,
                origin_page_url,
                origin_image_url,
                origin_width,
                origin_height,
                resource_status,
                created_at_utc,
                updated_at_utc
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                "bing",
                "bing:en-US:2026-03-25:t2-5-restore",
                "en-US",
                "2026-03-25",
                "T2.5 Restore",
                "T2.5 Restore subtitle",
                "T2.5 Restore description",
                "T2.5 Restore copyright",
                "Bing",
                "enabled",
                1,
                1,
                "2000-01-01T00:00:00Z",
                "2100-01-01T00:00:00Z",
                "https://www.bing.com/example",
                "https://www.bing.com/t2-5-restore.jpg",
                1920,
                1080,
                "ready",
                now_utc,
                now_utc,
            ),
        )
        assert cursor.lastrowid is not None
        wallpaper_id = int(cursor.lastrowid)
        connection.execute(
            """
            INSERT INTO image_resources (
                wallpaper_id,
                resource_type,
                storage_backend,
                relative_path,
                filename,
                file_ext,
                mime_type,
                file_size_bytes,
                width,
                height,
                source_url,
                source_url_hash,
                content_hash,
                downloaded_at_utc,
                image_status,
                integrity_check_result,
                failure_reason,
                last_processed_at_utc,
                created_at_utc,
                updated_at_utc
            )
            VALUES (?, 'original', 'local', ?, ?, 'jpg', 'image/jpeg', ?, 1920, 1080, ?, ?, ?, ?, 'ready', 'passed', NULL, ?, ?, ?);
            """,
            (
                wallpaper_id,
                str(relative_path),
                "t2-5-restore.jpg",
                len(JPEG_BYTES),
                "https://www.bing.com/t2-5-restore.jpg",
                "hash-t2-5-restore",
                "content-t2-5-restore",
                now_utc,
                now_utc,
                now_utc,
                now_utc,
            ),
        )
        connection.execute(
            """
            UPDATE wallpapers
            SET default_resource_id = (
                SELECT id
                FROM image_resources
                WHERE wallpaper_id = ?
                ORDER BY id ASC
                LIMIT 1
            )
            WHERE id = ?;
            """,
            (wallpaper_id, wallpaper_id),
        )
        connection.execute(
            """
            INSERT INTO admin_users (
                username,
                password_hash,
                role_name,
                status,
                last_login_at_utc,
                created_at_utc,
                updated_at_utc
            )
            VALUES (?, ?, 'super_admin', 'enabled', NULL, ?, ?);
            """,
            ("admin", hash_password("correct-password"), now_utc, now_utc),
        )
        connection.execute(
            """
            INSERT INTO collection_tasks (
                task_type,
                source_type,
                trigger_type,
                triggered_by,
                task_status,
                request_snapshot_json,
                started_at_utc,
                finished_at_utc,
                success_count,
                duplicate_count,
                failure_count,
                error_summary,
                retry_of_task_id,
                created_at_utc,
                updated_at_utc
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?);
            """,
            (
                "manual_collect",
                "bing",
                "admin",
                "admin",
                "succeeded",
                json.dumps(
                    {
                        "source_type": "bing",
                        "market_code": "en-US",
                        "date_from": "2026-03-25",
                        "date_to": "2026-03-25",
                        "force_refresh": False,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                "2026-03-25T10:00:00Z",
                "2026-03-25T10:01:00Z",
                1,
                0,
                0,
                "2026-03-25T09:59:00Z",
                "2026-03-25T10:01:00Z",
            ),
        )
        connection.commit()
    finally:
        connection.close()

    (config_dir / "bingwall.env").write_text(
        "\n".join((
            "BINGWALL_APP_ENV=production",
            "BINGWALL_APP_HOST=127.0.0.1",
            "BINGWALL_APP_PORT=8000",
            "BINGWALL_APP_BASE_URL=http://127.0.0.1:8000",
            f"BINGWALL_DATABASE_PATH={database_path}",
            f"BINGWALL_STORAGE_TMP_DIR={root / 'images' / 'tmp'}",
            f"BINGWALL_STORAGE_PUBLIC_DIR={public_dir}",
            f"BINGWALL_STORAGE_FAILED_DIR={root / 'images' / 'failed'}",
            f"BINGWALL_BACKUP_DIR={backup_dir}",
            "BINGWALL_SECURITY_SESSION_SECRET=0123456789abcdef0123456789abcdef",
            "BINGWALL_SECURITY_SESSION_TTL_HOURS=12",
            "BINGWALL_LOG_LEVEL=INFO",
        ))
        + "\n",
        encoding="utf-8",
    )
    (config_dir / "deploy-note.txt").write_text("t2.5 restore rehearsal\n", encoding="utf-8")
    (log_dir / "app.log").write_text("2026-03-25T10:00:00Z INFO app startup\n", encoding="utf-8")
    (nginx_dir / "bingwall.conf").write_text("server { listen 80; }\n", encoding="utf-8")
    (systemd_dir / "bingwall-api.service").write_text(
        "[Service]\nExecStart=/bin/true\n", encoding="utf-8"
    )
    (tmpfiles_dir / "bingwall.conf").write_text(
        "d /var/lib/bingwall 0750 root root -\n", encoding="utf-8"
    )


def build_client(root: Path) -> TestClient:
    clear_bingwall_env()
    os.environ["BINGWALL_APP_ENV"] = "test"
    os.environ["BINGWALL_APP_HOST"] = "127.0.0.1"
    os.environ["BINGWALL_APP_PORT"] = "8000"
    os.environ["BINGWALL_APP_BASE_URL"] = "http://127.0.0.1:8000"
    os.environ["BINGWALL_SITE_NAME"] = "BingWall"
    os.environ["BINGWALL_SITE_DESCRIPTION"] = "Bing 壁纸图片服务"
    os.environ["BINGWALL_DATABASE_PATH"] = str(root / "data" / "bingwall.sqlite3")
    os.environ["BINGWALL_STORAGE_TMP_DIR"] = str(root / "images" / "tmp")
    os.environ["BINGWALL_STORAGE_PUBLIC_DIR"] = str(root / "images" / "public")
    os.environ["BINGWALL_STORAGE_FAILED_DIR"] = str(root / "images" / "failed")
    os.environ["BINGWALL_BACKUP_DIR"] = str(root / "backups")
    os.environ["BINGWALL_SECURITY_SESSION_SECRET"] = "0123456789abcdef0123456789abcdef"
    os.environ["BINGWALL_SECURITY_SESSION_TTL_HOURS"] = "12"
    os.environ["BINGWALL_LOG_LEVEL"] = "INFO"
    reset_settings_cache()
    return TestClient(create_app())


def clear_bingwall_env() -> None:
    for key in ENV_KEYS:
        os.environ.pop(key, None)
    reset_settings_cache()


def run_json_command(command: list[str]) -> dict[str, object]:
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return cast(dict[str, object], json.loads(result.stdout))


def run_resource_inspection(root: Path) -> dict[str, object]:
    repository = HealthRepository(root / "data" / "bingwall.sqlite3")
    service = ResourceInspectionService(repository, public_dir=root / "images" / "public")
    try:
        summary = service.inspect_ready_local_resources()
    finally:
        repository.close()
    return summary.model_dump(mode="json")


def write_restore_verification_record(
    *,
    restored_root: Path,
    snapshot_id: str,
    public_home_status_code: int,
    public_api_status_code: int,
    admin_api_status_code: int,
    deep_health_status: str,
    resource_inspection_missing_count: int,
) -> Path:
    verification_dir = restored_root / "backups" / RESTORE_VERIFICATION_DIR_NAME
    verification_dir.mkdir(parents=True, exist_ok=True)
    verification_id = build_operation_id(prefix="verification")
    record_path = verification_dir / f"{verification_id}.json"
    payload = LatestRestoreVerificationStatus(
        verification_id=verification_id,
        snapshot_id=snapshot_id,
        status="passed",
        verified_at_utc=utc_now_text(),
        deep_health_status=cast(Literal["ok", "degraded", "fail"], deep_health_status),
        public_home_status_code=public_home_status_code,
        public_api_status_code=public_api_status_code,
        admin_api_status_code=admin_api_status_code,
        resource_inspection_missing_count=resource_inspection_missing_count,
        record_path=str(record_path),
    )
    record_path.write_text(
        json.dumps(payload.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return record_path


def utc_now_text() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    sys.exit(main())
