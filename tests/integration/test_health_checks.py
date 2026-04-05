from __future__ import annotations

import json
import os
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from pathlib import Path
import sqlite3
from typing import cast

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import reset_settings_cache
from app.main import create_app
from app.repositories.health_repository import HealthRepository
from app.services.health import ResourceInspectionService
from tests.integration.test_admin_collection import seed_collection_task
from tests.integration.test_public_api import build_client
from tests.integration.test_public_api import prepare_database
from tests.integration.test_public_api import seed_wallpaper
from tests.conftest import clear_bingwall_env


def test_ready_health_reports_database_and_directory_status(tmp_path: Path) -> None:
    prepare_database(tmp_path)
    ensure_runtime_dirs(tmp_path)

    with build_client(tmp_path) as client:
        response = client.get("/api/health/ready")

    payload = response.json()
    assert response.status_code == 200
    assert payload["status"] == "ok"
    assert payload["database"]["status"] == "ok"
    assert payload["configuration"]["status"] == "ok"
    assert {item["name"] for item in payload["directories"]} == {
        "database_dir",
        "storage_tmp_dir",
        "storage_public_dir",
        "storage_failed_dir",
        "backup_dir",
    }
    assert all(item["status"] == "ok" for item in payload["directories"])


def test_ready_health_returns_503_when_required_directory_is_missing(tmp_path: Path) -> None:
    prepare_database(tmp_path)
    ensure_runtime_dirs(tmp_path, include_public_dir=False)

    with build_client(tmp_path) as client:
        response = client.get("/api/health/ready")

    payload = response.json()
    assert response.status_code == 503
    assert payload["status"] == "fail"
    public_dir = next(
        item for item in payload["directories"] if item["name"] == "storage_public_dir"
    )
    assert public_dir["exists"] is False
    assert public_dir["status"] == "fail"


def test_deep_health_returns_latest_collection_task_and_disk_summary(tmp_path: Path) -> None:
    database_path = prepare_database(tmp_path)
    ensure_runtime_dirs(tmp_path)
    seed_collection_task(
        database_path=database_path,
        request_snapshot={
            "source_type": "bing",
            "market_code": "en-US",
            "date_from": "2026-03-24",
            "date_to": "2026-03-24",
            "force_refresh": False,
        },
        task_status="succeeded",
        error_summary=None,
    )

    with build_client(tmp_path) as client:
        response = client.get("/api/health/deep")

    payload = response.json()
    assert response.status_code == 200
    assert payload["status"] == "ok"
    assert payload["latest_collection_task"]["task_status"] == "succeeded"
    assert {item["name"] for item in payload["disk_usage"]} == {
        "database_dir",
        "storage_public_dir",
        "backup_dir",
    }
    assert payload["resource_directory"]["path"].endswith("/images/public")


def test_operations_metrics_returns_collection_backup_and_http_5xx_summary(tmp_path: Path) -> None:
    database_path = prepare_database(tmp_path)
    ensure_runtime_dirs(tmp_path)
    now = datetime.now(tz=UTC).replace(microsecond=0)
    first_finished_at_utc = (now - timedelta(hours=2)).isoformat().replace("+00:00", "Z")
    second_finished_at_utc = (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    http_5xx_occurred_at_utc = (now - timedelta(minutes=30)).isoformat().replace("+00:00", "Z")
    snapshot_id = f"backup-{now.strftime('%Y%m%dT%H%M%SZ')}-abcd1234"
    seed_metrics_collection_task(
        database_path=database_path,
        task_status="succeeded",
        success_count=3,
        duplicate_count=1,
        failure_count=0,
        finished_at_utc=first_finished_at_utc,
    )
    seed_metrics_collection_task(
        database_path=database_path,
        task_status="partially_failed",
        success_count=2,
        duplicate_count=0,
        failure_count=1,
        finished_at_utc=second_finished_at_utc,
    )
    create_backup_manifest(
        tmp_path=tmp_path,
        snapshot_id=snapshot_id,
        finished_at_utc=second_finished_at_utc,
    )

    repository = HealthRepository(database_path)
    try:
        repository.record_http_5xx_event(
            method="GET",
            path="/api/public/site-info",
            status_code=503,
            trace_id="trace-metrics-1",
            error_type=None,
            occurred_at_utc=http_5xx_occurred_at_utc,
        )
    finally:
        repository.close()

    with build_client(tmp_path) as client:
        response = client.get("/api/health/metrics")

    payload = response.json()
    assert response.status_code == 200
    assert payload["service"] == "bingwall-api"
    assert payload["collection"]["window_days"] == 7
    assert payload["collection"]["completed_task_count"] == 2
    assert payload["collection"]["succeeded_task_count"] == 1
    assert payload["collection"]["partially_failed_task_count"] == 1
    assert payload["collection"]["failed_task_count"] == 0
    assert payload["collection"]["successful_item_count"] == 5
    assert payload["collection"]["duplicate_item_count"] == 1
    assert payload["collection"]["failed_item_count"] == 1
    assert payload["collection"]["success_rate_percent"] == 85.71
    assert payload["latest_backup"]["snapshot_id"] == snapshot_id
    assert payload["latest_backup"]["manifest_path"].endswith("/manifest.json")
    assert payload["http_5xx"]["window_hours"] == 24
    assert payload["http_5xx"]["count"] == 1
    assert payload["http_5xx"]["latest_event"]["path"] == "/api/public/site-info"
    assert payload["http_5xx"]["latest_event"]["status_code"] == 503


def test_unhandled_500_request_is_recorded_by_metrics_endpoint(tmp_path: Path) -> None:
    prepare_database(tmp_path)
    ensure_runtime_dirs(tmp_path)

    client = build_server_error_client(tmp_path)
    app = cast(FastAPI, client.app)

    def boom() -> None:
        raise RuntimeError("boom")

    app.add_api_route("/__test__/boom", boom, methods=["GET"])

    with client:
        error_response = client.get("/__test__/boom")
        metrics_response = client.get("/api/health/metrics")

    metrics_payload = metrics_response.json()
    assert error_response.status_code == 500
    assert metrics_response.status_code == 200
    assert metrics_payload["http_5xx"]["count"] == 1
    assert metrics_payload["http_5xx"]["latest_event"]["path"] == "/__test__/boom"
    assert metrics_payload["http_5xx"]["latest_event"]["status_code"] == 500
    assert metrics_payload["http_5xx"]["latest_event"]["error_type"] == "RuntimeError"


def test_resource_inspection_marks_missing_resource_failed_and_hides_public_wallpaper(
    tmp_path: Path,
) -> None:
    database_path = prepare_database(tmp_path)
    ensure_runtime_dirs(tmp_path)
    wallpaper_id = seed_wallpaper(
        database_path=database_path,
        wallpaper_date="2026-03-24",
        market_code="en-US",
        title="Missing file wallpaper",
    )

    with build_client(tmp_path) as client:
        before_response = client.get(f"/api/public/wallpapers/{wallpaper_id}")

    assert before_response.status_code == 200

    repository = HealthRepository(database_path)
    service = ResourceInspectionService(
        repository,
        public_dir=tmp_path / "images" / "public",
    )
    try:
        summary = service.inspect_ready_local_resources()
    finally:
        repository.close()

    assert summary.checked_resource_count == 3
    assert summary.missing_resource_count == 3
    assert summary.disabled_wallpaper_count == 1
    assert summary.items[0].action == "marked_failed_and_disabled"

    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        wallpaper_row = connection.execute(
            """
            SELECT content_status, is_public, resource_status
            FROM wallpapers
            WHERE id = ?;
            """,
            (wallpaper_id,),
        ).fetchone()
        resource_row = connection.execute(
            """
            SELECT COUNT(*) AS total_count
            FROM image_resources
            WHERE wallpaper_id = ?;
            """,
            (wallpaper_id,),
        ).fetchone()
        failed_count_row = connection.execute(
            """
            SELECT COUNT(*) AS failed_count
            FROM image_resources
            WHERE wallpaper_id = ?
              AND image_status = 'failed';
            """,
            (wallpaper_id,),
        ).fetchone()
    finally:
        connection.close()

    assert wallpaper_row is not None
    assert wallpaper_row["content_status"] == "disabled"
    assert wallpaper_row["is_public"] == 0
    assert wallpaper_row["resource_status"] == "failed"
    assert resource_row is not None
    assert resource_row["total_count"] == 3
    assert failed_count_row is not None
    assert failed_count_row["failed_count"] == 3

    with build_client(tmp_path) as client:
        after_response = client.get(f"/api/public/wallpapers/{wallpaper_id}")

    assert after_response.status_code == 404


def ensure_runtime_dirs(tmp_path: Path, *, include_public_dir: bool = True) -> None:
    (tmp_path / "images" / "tmp").mkdir(parents=True, exist_ok=True)
    (tmp_path / "images" / "failed").mkdir(parents=True, exist_ok=True)
    (tmp_path / "backups").mkdir(parents=True, exist_ok=True)
    if include_public_dir:
        (tmp_path / "images" / "public").mkdir(parents=True, exist_ok=True)


def seed_metrics_collection_task(
    *,
    database_path: Path,
    task_status: str,
    success_count: int,
    duplicate_count: int,
    failure_count: int,
    finished_at_utc: str,
) -> None:
    connection = sqlite3.connect(database_path)
    try:
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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?);
            """,
            (
                "scheduled_collect",
                "bing",
                "cron",
                "cron",
                task_status,
                json.dumps(
                    {
                        "source_type": "bing",
                        "market_code": "en-US",
                        "date_from": "2026-04-05",
                        "date_to": "2026-04-05",
                        "force_refresh": False,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                "2026-04-05T00:50:00Z",
                finished_at_utc,
                success_count,
                duplicate_count,
                failure_count,
                None if failure_count == 0 else "partial failure",
                finished_at_utc,
                finished_at_utc,
            ),
        )
        connection.commit()
    finally:
        connection.close()


def create_backup_manifest(*, tmp_path: Path, snapshot_id: str, finished_at_utc: str) -> None:
    snapshot_dir = tmp_path / "backups" / snapshot_id
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = snapshot_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "snapshot_id": snapshot_id,
                "started_at_utc": "2026-04-05T01:50:00Z",
                "finished_at_utc": finished_at_utc,
                "source_paths": {},
                "artifacts": {},
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def build_server_error_client(tmp_path: Path) -> TestClient:
    clear_bingwall_env()
    os.environ["BINGWALL_APP_ENV"] = "test"
    os.environ["BINGWALL_APP_HOST"] = "127.0.0.1"
    os.environ["BINGWALL_APP_PORT"] = "8000"
    os.environ["BINGWALL_APP_BASE_URL"] = "http://127.0.0.1:8000"
    os.environ["BINGWALL_DATABASE_PATH"] = str(tmp_path / "data" / "bingwall.sqlite3")
    os.environ["BINGWALL_STORAGE_TMP_DIR"] = str(tmp_path / "images" / "tmp")
    os.environ["BINGWALL_STORAGE_PUBLIC_DIR"] = str(tmp_path / "images" / "public")
    os.environ["BINGWALL_STORAGE_FAILED_DIR"] = str(tmp_path / "images" / "failed")
    os.environ["BINGWALL_BACKUP_DIR"] = str(tmp_path / "backups")
    os.environ["BINGWALL_SECURITY_SESSION_SECRET"] = "0123456789abcdef0123456789abcdef"
    os.environ["BINGWALL_SECURITY_SESSION_TTL_HOURS"] = "12"
    os.environ["BINGWALL_LOG_LEVEL"] = "INFO"
    reset_settings_cache()
    return TestClient(create_app(), raise_server_exceptions=False)
