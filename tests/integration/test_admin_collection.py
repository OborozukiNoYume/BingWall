from __future__ import annotations

import json
from pathlib import Path
import sqlite3

from app.domain.collection import BingImageMetadata
from app.domain.collection import DownloadedImage
from tests.integration.test_admin_auth import build_client
from tests.integration.test_admin_auth import prepare_database
from tests.integration.test_admin_auth import seed_admin_user
from tests.integration.test_admin_content import login_admin
from tests.integration.test_bing_collection_service import FakeBingClient
from tests.integration.test_bing_collection_service import JPEG_BYTES
from tests.integration.test_bing_collection_service import make_metadata


def test_admin_collection_task_create_and_list_detail(tmp_path: Path) -> None:
    database_path = prepare_database(tmp_path)
    seed_admin_user(
        database_path=database_path,
        username="admin",
        password="correct-password",
    )

    with build_client(tmp_path) as client:
        session_token = login_admin(client)
        create_response = client.post(
            "/api/admin/collection-tasks",
            headers={"Authorization": f"Bearer {session_token}"},
            json={
                "source_type": "bing",
                "market_code": "en-US",
                "date_from": "2026-03-23",
                "date_to": "2026-03-24",
                "force_refresh": False,
            },
        )
        task_id = create_response.json()["data"]["task_id"]
        list_response = client.get(
            "/api/admin/collection-tasks?task_status=queued",
            headers={"Authorization": f"Bearer {session_token}"},
        )
        detail_response = client.get(
            f"/api/admin/collection-tasks/{task_id}",
            headers={"Authorization": f"Bearer {session_token}"},
        )

    create_payload = create_response.json()
    list_payload = list_response.json()
    detail_payload = detail_response.json()

    assert create_response.status_code == 200
    assert create_payload["data"]["task_status"] == "queued"
    assert list_response.status_code == 200
    assert list_payload["pagination"]["total"] == 1
    assert list_payload["data"]["items"][0]["market_code"] == "en-US"
    assert list_payload["data"]["items"][0]["date_from"] == "2026-03-23"
    assert list_payload["data"]["items"][0]["date_to"] == "2026-03-24"
    assert detail_response.status_code == 200
    assert detail_payload["data"]["request_snapshot"] == {
        "source_type": "bing",
        "market_code": "en-US",
        "date_from": "2026-03-23",
        "date_to": "2026-03-24",
        "force_refresh": False,
        "count": None,
        "trigger_type": None,
    }
    assert detail_payload["data"]["items"] == []

    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        task_row = connection.execute(
            """
            SELECT task_status, trigger_type, triggered_by, request_snapshot_json
            FROM collection_tasks
            WHERE id = ?;
            """,
            (task_id,),
        ).fetchone()
        audit_row = connection.execute(
            """
            SELECT action_type, target_type, target_id
            FROM audit_logs
            WHERE target_id = ?
            ORDER BY id DESC
            LIMIT 1;
            """,
            (str(task_id),),
        ).fetchone()
    finally:
        connection.close()

    assert task_row is not None
    assert task_row["task_status"] == "queued"
    assert task_row["trigger_type"] == "admin"
    assert task_row["triggered_by"] == "admin"
    assert json.loads(task_row["request_snapshot_json"])["market_code"] == "en-US"
    assert audit_row is not None
    assert audit_row["action_type"] == "collection_task_created"
    assert audit_row["target_type"] == "collection_task"
    assert audit_row["target_id"] == str(task_id)


def test_manual_collection_consumer_updates_task_detail_and_logs(tmp_path: Path) -> None:
    database_path = prepare_database(tmp_path)
    seed_admin_user(
        database_path=database_path,
        username="admin",
        password="correct-password",
    )

    with build_client(tmp_path) as client:
        session_token = login_admin(client)
        create_response = client.post(
            "/api/admin/collection-tasks",
            headers={"Authorization": f"Bearer {session_token}"},
            json={
                "source_type": "bing",
                "market_code": "en-US",
                "date_from": "2026-03-23",
                "date_to": "2026-03-24",
                "force_refresh": False,
            },
        )
        task_id = create_response.json()["data"]["task_id"]

    run_manual_consumer(
        tmp_path=tmp_path,
        metadata=[
            make_metadata(
                market_code="en-US",
                wallpaper_date="2026-03-24",
                source_key="bing:en-US:2026-03-24:OHR.Today",
                source_url="https://www.bing.com/th?id=OHR.Today_1920x1080.jpg",
            ),
            make_metadata(
                market_code="en-US",
                wallpaper_date="2026-03-23",
                source_key="bing:en-US:2026-03-23:OHR.Yesterday",
                source_url="https://www.bing.com/th?id=OHR.Yesterday_1920x1080.jpg",
            ),
        ],
    )

    with build_client(tmp_path) as client:
        session_token = login_admin(client)
        detail_response = client.get(
            f"/api/admin/collection-tasks/{task_id}",
            headers={"Authorization": f"Bearer {session_token}"},
        )
        logs_response = client.get(
            f"/api/admin/logs?task_id={task_id}",
            headers={"Authorization": f"Bearer {session_token}"},
        )

    detail_payload = detail_response.json()
    logs_payload = logs_response.json()

    assert detail_response.status_code == 200
    assert detail_payload["data"]["task_status"] == "succeeded"
    assert detail_payload["data"]["success_count"] == 2
    assert detail_payload["data"]["duplicate_count"] == 0
    assert detail_payload["data"]["failure_count"] == 0
    assert len(detail_payload["data"]["items"]) == 2
    assert {item["result_status"] for item in detail_payload["data"]["items"]} == {"succeeded"}

    assert logs_response.status_code == 200
    assert logs_payload["pagination"]["total"] == 2
    assert logs_payload["data"]["items"][0]["task_id"] == task_id
    assert logs_payload["data"]["items"][0]["task_status"] == "succeeded"


def test_admin_collection_retry_and_logs_query(tmp_path: Path) -> None:
    database_path = prepare_database(tmp_path)
    seed_admin_user(
        database_path=database_path,
        username="admin",
        password="correct-password",
    )
    original_task_id = seed_collection_task(
        database_path=database_path,
        request_snapshot={
            "source_type": "bing",
            "market_code": "en-US",
            "date_from": "2026-03-24",
            "date_to": "2026-03-24",
            "force_refresh": False,
        },
        task_status="failed",
        error_summary="download attempt 2 failed: downloaded image is empty",
    )
    seed_collection_task_item(
        database_path=database_path,
        task_id=original_task_id,
        result_status="failed",
        failure_reason="download attempt 2 failed: downloaded image is empty",
    )

    with build_client(tmp_path) as client:
        session_token = login_admin(client)
        logs_response = client.get(
            f"/api/admin/logs?task_id={original_task_id}&error_type=failed",
            headers={"Authorization": f"Bearer {session_token}"},
        )
        retry_response = client.post(
            f"/api/admin/collection-tasks/{original_task_id}/retry",
            headers={"Authorization": f"Bearer {session_token}"},
        )

    logs_payload = logs_response.json()
    retry_payload = retry_response.json()

    assert logs_response.status_code == 200
    assert logs_payload["pagination"]["total"] == 1
    assert logs_payload["data"]["items"][0]["failure_reason"] == (
        "download attempt 2 failed: downloaded image is empty"
    )

    assert retry_response.status_code == 200
    assert retry_payload["data"]["task_status"] == "queued"
    assert retry_payload["data"]["retry_of_task_id"] == original_task_id

    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        retried_row = connection.execute(
            """
            SELECT retry_of_task_id, task_status
            FROM collection_tasks
            WHERE id = ?;
            """,
            (retry_payload["data"]["task_id"],),
        ).fetchone()
        audit_row = connection.execute(
            """
            SELECT action_type, target_type
            FROM audit_logs
            WHERE target_id = ?
            ORDER BY id DESC
            LIMIT 1;
            """,
            (str(retry_payload["data"]["task_id"]),),
        ).fetchone()
    finally:
        connection.close()

    assert retried_row is not None
    assert retried_row["retry_of_task_id"] == original_task_id
    assert retried_row["task_status"] == "queued"
    assert audit_row is not None
    assert audit_row["action_type"] == "collection_task_retried"
    assert audit_row["target_type"] == "collection_task"


def test_admin_collection_task_create_rejects_out_of_window_date_range(tmp_path: Path) -> None:
    database_path = prepare_database(tmp_path)
    seed_admin_user(
        database_path=database_path,
        username="admin",
        password="correct-password",
    )

    with build_client(tmp_path) as client:
        session_token = login_admin(client)
        response = client.post(
            "/api/admin/collection-tasks",
            headers={"Authorization": f"Bearer {session_token}"},
            json={
                "source_type": "bing",
                "market_code": "en-US",
                "date_from": "2026-03-10",
                "date_to": "2026-03-24",
                "force_refresh": False,
            },
        )

    payload = response.json()
    assert response.status_code == 422
    assert payload["error_code"] == "COMMON_INVALID_ARGUMENT"
    assert "最近 8 天" in payload["message"]


def run_manual_consumer(*, tmp_path: Path, metadata: list[BingImageMetadata]) -> None:
    from app.repositories.collection_repository import CollectionRepository
    from app.repositories.file_storage import FileStorage
    from app.services.admin_collection import ManualCollectionTaskConsumer

    repository = CollectionRepository(str(tmp_path / "data" / "bingwall.sqlite3"))
    storage = FileStorage(
        tmp_dir=tmp_path / "images" / "tmp",
        public_dir=tmp_path / "images" / "public",
        failed_dir=tmp_path / "images" / "failed",
    )
    consumer = ManualCollectionTaskConsumer(
        repository=repository,
        storage=storage,
        bing_client=FakeBingClient(
            metadata=list(metadata),
            downloads=[
                DownloadedImage(content=JPEG_BYTES, mime_type="image/jpeg"),
                DownloadedImage(content=JPEG_BYTES, mime_type="image/jpeg"),
            ],
        ),
        max_download_retries=2,
    )
    try:
        summary = consumer.consume_next_queued_task()
    finally:
        repository.close()

    assert summary is not None
    assert summary.task_status == "succeeded"


def seed_collection_task(
    *,
    database_path: Path,
    request_snapshot: dict[str, object],
    task_status: str,
    error_summary: str | None,
) -> int:
    connection = sqlite3.connect(database_path)
    try:
        cursor = connection.execute(
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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 1, ?, NULL, ?, ?);
            """,
            (
                "manual_collect",
                "bing",
                "admin",
                "admin",
                task_status,
                json.dumps(request_snapshot, ensure_ascii=False, sort_keys=True),
                "2026-03-24T10:00:00Z",
                "2026-03-24T10:01:00Z",
                error_summary,
                "2026-03-24T09:59:00Z",
                "2026-03-24T10:01:00Z",
            ),
        )
        connection.commit()
        assert cursor.lastrowid is not None
        return int(cursor.lastrowid)
    finally:
        connection.close()


def seed_collection_task_item(
    *,
    database_path: Path,
    task_id: int,
    result_status: str,
    failure_reason: str | None,
) -> None:
    connection = sqlite3.connect(database_path)
    try:
        connection.execute(
            """
            INSERT INTO collection_task_items (
                task_id,
                source_item_key,
                action_name,
                result_status,
                dedupe_hit_type,
                db_write_result,
                file_write_result,
                failure_reason,
                occurred_at_utc
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                task_id,
                "bing:en-US:2026-03-24:OHR.Failure",
                "collect_candidate",
                result_status,
                None,
                "wallpaper_and_resource_created",
                "failed",
                failure_reason,
                "2026-03-24T10:00:30Z",
            ),
        )
        connection.commit()
    finally:
        connection.close()
