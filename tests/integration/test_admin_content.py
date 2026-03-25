from __future__ import annotations

from datetime import UTC
from datetime import datetime
from pathlib import Path

import sqlite3

from fastapi.testclient import TestClient

from tests.integration.test_admin_auth import build_client
from tests.integration.test_admin_auth import prepare_database
from tests.integration.test_admin_auth import seed_admin_user
from tests.integration.test_public_api import seed_wallpaper


def test_admin_wallpaper_list_and_detail_return_management_fields(tmp_path: Path) -> None:
    database_path = prepare_database(tmp_path)
    seed_admin_user(
        database_path=database_path,
        username="admin",
        password="correct-password",
    )
    wallpaper_id = seed_wallpaper(
        database_path=database_path,
        wallpaper_date="2026-03-24",
        market_code="en-US",
        title="Admin Visible",
        content_status="disabled",
        is_public=False,
        resource_status="failed",
        image_status="failed",
        failure_reason="image checksum failed",
    )

    with build_client(tmp_path) as client:
        session_token = login_admin(client)
        list_response = client.get(
            "/api/admin/wallpapers?content_status=disabled&image_status=failed",
            headers={"Authorization": f"Bearer {session_token}"},
        )
        detail_response = client.get(
            f"/api/admin/wallpapers/{wallpaper_id}",
            headers={"Authorization": f"Bearer {session_token}"},
        )

    list_payload = list_response.json()
    detail_payload = detail_response.json()
    assert list_response.status_code == 200
    assert list_payload["pagination"] == {
        "page": 1,
        "page_size": 20,
        "total": 1,
        "total_pages": 1,
    }
    assert list_payload["data"]["items"][0]["title"] == "Admin Visible"
    assert list_payload["data"]["items"][0]["content_status"] == "disabled"
    assert list_payload["data"]["items"][0]["image_status"] == "failed"
    assert list_payload["data"]["items"][0]["failure_reason"] == "image checksum failed"

    assert detail_response.status_code == 200
    assert detail_payload["data"]["source_type"] == "bing"
    assert detail_payload["data"]["resource_status"] == "failed"
    assert detail_payload["data"]["image_status"] == "failed"
    assert detail_payload["data"]["failure_reason"] == "image checksum failed"
    assert detail_payload["data"]["recent_operations"] == []


def test_admin_status_change_updates_public_visibility_and_creates_audit_logs(
    tmp_path: Path,
) -> None:
    database_path = prepare_database(tmp_path)
    seed_admin_user(
        database_path=database_path,
        username="admin",
        password="correct-password",
    )
    wallpaper_id = seed_wallpaper(
        database_path=database_path,
        wallpaper_date="2026-03-24",
        market_code="en-US",
        title="Draft Ready",
        content_status="draft",
        is_public=False,
    )

    with build_client(tmp_path) as client:
        session_token = login_admin(client)
        enable_response = client.post(
            f"/api/admin/wallpapers/{wallpaper_id}/status",
            headers={"Authorization": f"Bearer {session_token}"},
            json={"target_status": "enabled", "operator_reason": "人工审核通过"},
        )
        public_visible_response = client.get(f"/api/public/wallpapers/{wallpaper_id}")
        disable_response = client.post(
            f"/api/admin/wallpapers/{wallpaper_id}/status",
            headers={"Authorization": f"Bearer {session_token}"},
            json={"target_status": "disabled", "operator_reason": "临时下线"},
        )
        public_hidden_response = client.get(f"/api/public/wallpapers/{wallpaper_id}")
        audit_response = client.get(
            f"/api/admin/audit-logs?target_type=wallpaper&target_id={wallpaper_id}",
            headers={"Authorization": f"Bearer {session_token}"},
        )
        detail_response = client.get(
            f"/api/admin/wallpapers/{wallpaper_id}",
            headers={"Authorization": f"Bearer {session_token}"},
        )

    enable_payload = enable_response.json()
    disable_payload = disable_response.json()
    audit_payload = audit_response.json()
    detail_payload = detail_response.json()

    assert enable_response.status_code == 200
    assert enable_payload["data"] == {
        "wallpaper_id": wallpaper_id,
        "previous_status": "draft",
        "target_status": "enabled",
        "is_public": True,
        "deleted_at_utc": None,
    }
    assert public_visible_response.status_code == 200

    assert disable_response.status_code == 200
    assert disable_payload["data"]["previous_status"] == "enabled"
    assert disable_payload["data"]["target_status"] == "disabled"
    assert public_hidden_response.status_code == 404

    assert audit_response.status_code == 200
    assert audit_payload["pagination"]["total"] == 2
    assert audit_payload["data"]["items"][0]["after_state"]["content_status"] == "disabled"
    assert audit_payload["data"]["items"][1]["after_state"]["content_status"] == "enabled"
    assert audit_payload["data"]["items"][0]["trace_id"]

    assert detail_response.status_code == 200
    assert detail_payload["data"]["content_status"] == "disabled"
    assert len(detail_payload["data"]["recent_operations"]) == 2


def test_admin_status_change_rejects_invalid_transitions(tmp_path: Path) -> None:
    database_path = prepare_database(tmp_path)
    seed_admin_user(
        database_path=database_path,
        username="admin",
        password="correct-password",
    )
    failed_wallpaper_id = seed_wallpaper(
        database_path=database_path,
        wallpaper_date="2026-03-24",
        market_code="en-US",
        title="Failed Draft",
        content_status="draft",
        is_public=False,
        resource_status="failed",
        image_status="failed",
        failure_reason="download failed",
    )
    deleted_wallpaper_id = seed_wallpaper(
        database_path=database_path,
        wallpaper_date="2026-03-23",
        market_code="fr-FR",
        title="Deleted Item",
        content_status="deleted",
        is_public=False,
    )

    with build_client(tmp_path) as client:
        session_token = login_admin(client)
        failed_enable_response = client.post(
            f"/api/admin/wallpapers/{failed_wallpaper_id}/status",
            headers={"Authorization": f"Bearer {session_token}"},
            json={"target_status": "enabled", "operator_reason": "尝试重新启用"},
        )
        deleted_enable_response = client.post(
            f"/api/admin/wallpapers/{deleted_wallpaper_id}/status",
            headers={"Authorization": f"Bearer {session_token}"},
            json={"target_status": "enabled", "operator_reason": "误操作恢复"},
        )

    failed_payload = failed_enable_response.json()
    deleted_payload = deleted_enable_response.json()
    assert failed_enable_response.status_code == 409
    assert failed_payload["error_code"] == "CONTENT_INVALID_STATUS_TRANSITION"
    assert failed_payload["message"] == "资源未就绪，不能启用内容"

    assert deleted_enable_response.status_code == 409
    assert deleted_payload["error_code"] == "CONTENT_INVALID_STATUS_TRANSITION"
    assert deleted_payload["message"] == "不允许从 deleted 切换到 enabled"


def test_admin_audit_log_query_supports_time_range_filters(tmp_path: Path) -> None:
    database_path = prepare_database(tmp_path)
    admin_user_id = seed_admin_user(
        database_path=database_path,
        username="admin",
        password="correct-password",
    )
    insert_audit_log(
        database_path=database_path,
        admin_user_id=admin_user_id,
        action_type="wallpaper_status_changed",
        target_type="wallpaper",
        target_id="7",
        created_at_utc="2026-03-24T10:00:00Z",
    )
    insert_audit_log(
        database_path=database_path,
        admin_user_id=admin_user_id,
        action_type="admin_login",
        target_type="admin_session",
        target_id="9",
        created_at_utc="2026-03-24T12:00:00Z",
    )

    with build_client(tmp_path) as client:
        session_token = login_admin(client)
        started_from = "2026-03-24T11:00:00Z"
        started_to = "2026-03-24T13:00:00Z"
        response = client.get(
            f"/api/admin/audit-logs?started_from_utc={started_from}&started_to_utc={started_to}",
            headers={"Authorization": f"Bearer {session_token}"},
        )

    payload = response.json()
    assert response.status_code == 200
    assert payload["pagination"]["total"] == 1
    created_values = [item["created_at_utc"] for item in payload["data"]["items"]]
    assert "2026-03-24T12:00:00Z" in created_values
    assert "2026-03-24T10:00:00Z" not in created_values


def login_admin(client: TestClient) -> str:
    response = client.post(
        "/api/admin/auth/login",
        json={"username": "admin", "password": "correct-password"},
    )
    assert response.status_code == 200
    payload = response.json()
    return str(payload["data"]["session_token"])


def insert_audit_log(
    *,
    database_path: Path,
    admin_user_id: int,
    action_type: str,
    target_type: str,
    target_id: str,
    created_at_utc: str,
) -> None:
    connection = sqlite3.connect(database_path)
    try:
        before_state = "{}"
        after_state = "{}"
        connection.execute(
            """
            INSERT INTO audit_logs (
                admin_user_id,
                action_type,
                target_type,
                target_id,
                before_state_json,
                after_state_json,
                request_source,
                trace_id,
                created_at_utc
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                admin_user_id,
                action_type,
                target_type,
                target_id,
                before_state,
                after_state,
                "pytest",
                build_trace_id(created_at_utc),
                created_at_utc,
            ),
        )
        connection.commit()
    finally:
        connection.close()


def build_trace_id(created_at_utc: str) -> str:
    reference = datetime.fromisoformat(created_at_utc.replace("Z", "+00:00")).astimezone(UTC)
    return f"trace-{reference.strftime('%Y%m%d%H%M%S')}"
