from __future__ import annotations

from datetime import date
import json
import os
from pathlib import Path
import sqlite3

from app.core.config import Settings
from app.core.config import load_settings
from app.core.config import reset_settings_cache
from app.repositories.admin_collection_repository import AdminCollectionRepository
from app.services.scheduled_collection import create_scheduled_collection_tasks
from tests.conftest import clear_bingwall_env
from tests.integration.test_admin_auth import prepare_database


def test_create_scheduled_collection_tasks_creates_fixed_date_tasks_for_enabled_sources(
    tmp_path: Path,
) -> None:
    database_path = prepare_database(tmp_path)
    settings = build_scheduled_collection_settings(tmp_path)

    repository = AdminCollectionRepository(str(database_path))
    try:
        results = create_scheduled_collection_tasks(
            repository=repository,
            settings=settings,
            run_date=date(2026, 3, 28),
        )
    finally:
        repository.close()

    assert [result.action for result in results] == ["created", "created"]
    assert [result.source_type for result in results] == ["bing", "nasa_apod"]

    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            """
            SELECT
                task_type,
                source_type,
                trigger_type,
                triggered_by,
                task_status,
                request_snapshot_json
            FROM collection_tasks
            ORDER BY source_type ASC;
            """
        ).fetchall()
    finally:
        connection.close()

    assert len(rows) == 2

    bing_snapshot = json.loads(rows[0]["request_snapshot_json"])
    nasa_snapshot = json.loads(rows[1]["request_snapshot_json"])

    assert rows[0]["task_type"] == "scheduled_collect"
    assert rows[0]["source_type"] == "bing"
    assert rows[0]["trigger_type"] == "cron"
    assert rows[0]["triggered_by"] == "cron"
    assert rows[0]["task_status"] == "queued"
    assert bing_snapshot == {
        "count": 8,
        "date_from": "2026-03-28",
        "date_to": "2026-03-28",
        "force_refresh": False,
        "market_code": "en-US",
        "source_type": "bing",
        "trigger_type": "cron",
    }

    assert rows[1]["task_type"] == "scheduled_collect"
    assert rows[1]["source_type"] == "nasa_apod"
    assert rows[1]["trigger_type"] == "cron"
    assert rows[1]["triggered_by"] == "cron"
    assert rows[1]["task_status"] == "queued"
    assert nasa_snapshot == {
        "count": 1,
        "date_from": "2026-03-28",
        "date_to": "2026-03-28",
        "force_refresh": False,
        "market_code": "global",
        "source_type": "nasa_apod",
        "trigger_type": "cron",
    }


def test_create_scheduled_collection_tasks_skips_existing_same_date_non_failed_task(
    tmp_path: Path,
) -> None:
    database_path = prepare_database(tmp_path)
    settings = build_scheduled_collection_settings(tmp_path, nasa_enabled=False)
    seed_scheduled_task(
        database_path=database_path,
        source_type="bing",
        market_code="en-US",
        scheduled_date="2026-03-28",
        task_status="succeeded",
        count=8,
    )

    repository = AdminCollectionRepository(str(database_path))
    try:
        results = create_scheduled_collection_tasks(
            repository=repository,
            settings=settings,
            run_date=date(2026, 3, 28),
        )
    finally:
        repository.close()

    assert len(results) == 1
    assert results[0].source_type == "bing"
    assert results[0].action == "skipped_existing"
    assert results[0].task_id is None
    assert results[0].reason == "same_date_task_already_exists"

    connection = sqlite3.connect(database_path)
    try:
        task_count = connection.execute(
            "SELECT COUNT(*) FROM collection_tasks WHERE source_type = 'bing';"
        ).fetchone()
    finally:
        connection.close()

    assert task_count == (1,)


def test_create_scheduled_collection_tasks_allows_recreate_after_failed_task(
    tmp_path: Path,
) -> None:
    database_path = prepare_database(tmp_path)
    settings = build_scheduled_collection_settings(tmp_path, nasa_enabled=False)
    seed_scheduled_task(
        database_path=database_path,
        source_type="bing",
        market_code="en-US",
        scheduled_date="2026-03-28",
        task_status="failed",
        count=8,
    )

    repository = AdminCollectionRepository(str(database_path))
    try:
        results = create_scheduled_collection_tasks(
            repository=repository,
            settings=settings,
            run_date=date(2026, 3, 28),
        )
    finally:
        repository.close()

    assert len(results) == 1
    assert results[0].source_type == "bing"
    assert results[0].action == "created"
    assert results[0].task_id is not None

    connection = sqlite3.connect(database_path)
    try:
        task_count = connection.execute(
            "SELECT COUNT(*) FROM collection_tasks WHERE source_type = 'bing';"
        ).fetchone()
        queued_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM collection_tasks
            WHERE source_type = 'bing'
              AND task_status = 'queued';
            """
        ).fetchone()
    finally:
        connection.close()

    assert task_count == (2,)
    assert queued_count == (1,)


def build_scheduled_collection_settings(
    tmp_path: Path,
    *,
    bing_enabled: bool = True,
    nasa_enabled: bool = True,
) -> Settings:
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
    os.environ["BINGWALL_COLLECT_BING_ENABLED"] = str(bing_enabled).lower()
    os.environ["BINGWALL_COLLECT_NASA_APOD_ENABLED"] = str(nasa_enabled).lower()
    os.environ["BINGWALL_SECURITY_SESSION_SECRET"] = "0123456789abcdef0123456789abcdef"
    os.environ["BINGWALL_SECURITY_SESSION_TTL_HOURS"] = "12"
    os.environ["BINGWALL_LOG_LEVEL"] = "INFO"
    reset_settings_cache()
    return load_settings()


def seed_scheduled_task(
    *,
    database_path: Path,
    source_type: str,
    market_code: str,
    scheduled_date: str,
    task_status: str,
    count: int,
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
            VALUES (?, ?, 'cron', 'cron', ?, ?, NULL, NULL, 0, 0, 0, NULL, NULL, ?, ?);
            """,
            (
                "scheduled_collect",
                source_type,
                task_status,
                json.dumps(
                    {
                        "source_type": source_type,
                        "market_code": market_code,
                        "date_from": scheduled_date,
                        "date_to": scheduled_date,
                        "force_refresh": False,
                        "count": count,
                        "trigger_type": "cron",
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                "2026-03-28T03:15:00Z",
                "2026-03-28T03:15:00Z",
            ),
        )
        connection.commit()
    finally:
        connection.close()
