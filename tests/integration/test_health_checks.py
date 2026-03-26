from __future__ import annotations

from pathlib import Path
import sqlite3

from app.repositories.health_repository import HealthRepository
from app.services.health import ResourceInspectionService
from tests.integration.test_admin_collection import seed_collection_task
from tests.integration.test_public_api import build_client
from tests.integration.test_public_api import prepare_database
from tests.integration.test_public_api import seed_wallpaper


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
