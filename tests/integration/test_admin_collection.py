from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from typing import Any

from app.collectors.nasa_apod import NasaApodSourceAdapter
from app.domain.collection import CollectedImageMetadata
from app.domain.collection import BingImageMetadata
from app.domain.collection import DownloadedImage
from app.services.bing_collection import BingSourceAdapter
from tests.integration.test_admin_auth import build_client
from tests.integration.test_admin_auth import prepare_database
from tests.integration.test_admin_auth import seed_admin_user
from tests.integration.test_admin_content import login_admin
from tests.integration.test_bing_collection_service import FakeBingClient
from tests.integration.test_bing_collection_service import JPEG_BYTES
from tests.integration.test_bing_collection_service import make_metadata
from app.services.source_collection import SourceCollectionService


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


def test_admin_collection_task_can_be_consumed_manually(tmp_path: Path, monkeypatch: Any) -> None:
    database_path = prepare_database(tmp_path)
    seed_admin_user(
        database_path=database_path,
        username="admin",
        password="correct-password",
    )

    metadata = [
        make_metadata(
            market_code="en-US",
            wallpaper_date="2026-03-24",
            source_key="bing:en-US:2026-03-24:OHR.Today",
            source_url="https://www.bing.com/th?id=OHR.Today_1920x1080.jpg",
        )
    ]

    def fake_fetch_metadata(self: object, market_code: str, count: int) -> list[BingImageMetadata]:
        del self, market_code, count
        return list(metadata)

    def fake_download_image(self: object, image_url: str) -> DownloadedImage:
        del self, image_url
        return DownloadedImage(content=JPEG_BYTES, mime_type="image/jpeg")

    monkeypatch.setattr("app.collectors.bing.BingClient.fetch_metadata", fake_fetch_metadata)
    monkeypatch.setattr("app.collectors.bing.BingClient.download_image", fake_download_image)

    with build_client(tmp_path) as client:
        session_token = login_admin(client)
        create_response = client.post(
            "/api/admin/collection-tasks",
            headers={"Authorization": f"Bearer {session_token}"},
            json={
                "source_type": "bing",
                "market_code": "en-US",
                "date_from": "2026-03-24",
                "date_to": "2026-03-24",
                "force_refresh": False,
            },
        )
        task_id = create_response.json()["data"]["task_id"]
        consume_response = client.post(
            f"/api/admin/collection-tasks/{task_id}/consume",
            headers={"Authorization": f"Bearer {session_token}"},
        )
        detail_response = client.get(
            f"/api/admin/collection-tasks/{task_id}",
            headers={"Authorization": f"Bearer {session_token}"},
        )

    consume_payload = consume_response.json()
    detail_payload = detail_response.json()

    assert create_response.status_code == 200
    assert consume_response.status_code == 200
    assert consume_payload["data"]["task_id"] == task_id
    assert consume_payload["data"]["task_status"] == "succeeded"
    assert consume_payload["data"]["success_count"] == 1
    assert consume_payload["data"]["duplicate_count"] == 0
    assert consume_payload["data"]["failure_count"] == 0
    assert detail_response.status_code == 200
    assert detail_payload["data"]["task_status"] == "succeeded"
    assert detail_payload["data"]["started_at_utc"] is not None
    assert len(detail_payload["data"]["items"]) == 1

    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        audit_row = connection.execute(
            """
            SELECT action_type, target_type, target_id
            FROM audit_logs
            WHERE action_type = 'collection_task_consumed'
              AND target_id = ?
            ORDER BY id DESC
            LIMIT 1;
            """,
            (str(task_id),),
        ).fetchone()
    finally:
        connection.close()

    assert audit_row is not None
    assert audit_row["target_type"] == "collection_task"
    assert audit_row["target_id"] == str(task_id)


def test_admin_collection_task_manual_consume_rejects_non_queued_status(tmp_path: Path) -> None:
    database_path = prepare_database(tmp_path)
    seed_admin_user(
        database_path=database_path,
        username="admin",
        password="correct-password",
    )
    task_id = seed_collection_task(
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
        session_token = login_admin(client)
        response = client.post(
            f"/api/admin/collection-tasks/{task_id}/consume",
            headers={"Authorization": f"Bearer {session_token}"},
        )

    payload = response.json()
    assert response.status_code == 409
    assert payload["error_code"] == "COLLECT_TASK_CONSUME_NOT_ALLOWED"
    assert payload["message"] == "只有 queued 状态的任务允许手动触发执行"


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
        source_type="bing",
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


def test_manual_collection_consumer_supports_nasa_apod_tasks(tmp_path: Path) -> None:
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
                "source_type": "nasa_apod",
                "market_code": "global",
                "date_from": "2026-03-24",
                "date_to": "2026-03-24",
                "force_refresh": False,
            },
        )
        task_id = create_response.json()["data"]["task_id"]

    run_manual_consumer(
        tmp_path=tmp_path,
        source_type="nasa_apod",
        metadata=[
            make_nasa_metadata(
                wallpaper_date="2026-03-24",
                source_key="nasa_apod:global:2026-03-24:moonrise",
                source_url="https://apod.nasa.gov/apod/image/2603/moonrise.jpg",
            )
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

    assert create_response.status_code == 200
    assert detail_response.status_code == 200
    assert detail_payload["data"]["source_type"] == "nasa_apod"
    assert detail_payload["data"]["market_code"] == "global"
    assert detail_payload["data"]["task_status"] == "succeeded"
    assert detail_payload["data"]["success_count"] == 1
    assert logs_response.status_code == 200
    assert logs_payload["pagination"]["total"] == 1
    assert logs_payload["data"]["items"][0]["source_type"] == "nasa_apod"
    assert logs_payload["data"]["items"][0]["result_status"] == "succeeded"


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


def run_manual_consumer(
    *,
    tmp_path: Path,
    source_type: str,
    metadata: list[BingImageMetadata | CollectedImageMetadata],
) -> None:
    from app.repositories.collection_repository import CollectionRepository
    from app.repositories.file_storage import FileStorage
    from app.services.admin_collection import ManualCollectionTaskConsumer

    repository = CollectionRepository(str(tmp_path / "data" / "bingwall.sqlite3"))
    storage = FileStorage(
        tmp_dir=tmp_path / "images" / "tmp",
        public_dir=tmp_path / "images" / "public",
        failed_dir=tmp_path / "images" / "failed",
    )
    downloads = [
        DownloadedImage(content=JPEG_BYTES, mime_type="image/jpeg"),
        DownloadedImage(content=JPEG_BYTES, mime_type="image/jpeg"),
    ]
    services: dict[str, SourceCollectionService] = {}
    if source_type == "bing":
        services["bing"] = SourceCollectionService(
            repository=repository,
            storage=storage,
            adapter=BingSourceAdapter(
                client=FakeBingClient(metadata=list(metadata), downloads=downloads)
            ),
            max_download_retries=2,
            auto_publish_enabled=True,
        )
    if source_type == "nasa_apod":
        services["nasa_apod"] = SourceCollectionService(
            repository=repository,
            storage=storage,
            adapter=NasaApodSourceAdapter(
                client=FakeNasaApodClient(metadata=list(metadata), downloads=downloads)
            ),
            max_download_retries=2,
            auto_publish_enabled=True,
        )
    consumer = ManualCollectionTaskConsumer(
        repository=repository,
        services=services,
        supported_source_types=(source_type,),
    )
    try:
        summary = consumer.consume_next_queued_task()
    finally:
        repository.close()

    assert summary is not None
    assert summary.task_status == "succeeded"


class FakeNasaApodClient:
    def __init__(
        self,
        *,
        metadata: list[BingImageMetadata | CollectedImageMetadata],
        downloads: list[DownloadedImage],
    ) -> None:
        self.metadata = metadata
        self.downloads = downloads
        self.download_calls = 0

    def fetch_metadata(
        self,
        *,
        market_code: str,
        count: int,
        date_from: object,
        date_to: object,
    ) -> list[CollectedImageMetadata]:
        del market_code
        del date_from
        del date_to
        return [item for item in self.metadata[:count] if isinstance(item, CollectedImageMetadata)]

    def download_image(self, image_url: str) -> DownloadedImage:
        del image_url
        item = self.downloads[self.download_calls]
        self.download_calls += 1
        return item


def make_nasa_metadata(
    *,
    wallpaper_date: str,
    source_key: str,
    source_url: str,
) -> CollectedImageMetadata:
    from datetime import date
    import hashlib
    import json

    return CollectedImageMetadata(
        market_code="global",
        wallpaper_date=date.fromisoformat(wallpaper_date),
        source_key=source_key,
        title="Moonrise",
        copyright_text="NASA",
        origin_page_url=None,
        origin_image_url=source_url,
        source_url_hash=hashlib.sha256(source_url.encode("utf-8")).hexdigest(),
        is_downloadable=True,
        source_name="NASA APOD",
        origin_width=None,
        origin_height=None,
        raw_extra_json=json.dumps({"source_key": source_key}, ensure_ascii=True),
    )


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
