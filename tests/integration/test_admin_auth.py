from __future__ import annotations

from datetime import UTC
from datetime import datetime
import os
from pathlib import Path
import sqlite3

from fastapi.testclient import TestClient

from app.core.config import reset_settings_cache
from app.core.security import hash_password
from app.core.security import verify_password
from app.main import create_app
from app.repositories.migrations import migrate_database
from tests.conftest import clear_bingwall_env


def test_admin_login_returns_session_token_and_persists_hashed_session(tmp_path: Path) -> None:
    database_path = prepare_database(tmp_path)
    seed_admin_user(
        database_path=database_path,
        username="admin",
        password="correct-password",
    )

    with build_client(tmp_path) as client:
        response = client.post(
            "/api/admin/auth/login",
            json={"username": "admin", "password": "correct-password"},
            headers={"User-Agent": "pytest"},
        )

    payload = response.json()
    assert response.status_code == 200
    assert payload["data"]["user"] == {
        "id": 1,
        "username": "admin",
        "role_name": "super_admin",
    }
    assert payload["data"]["session_token"]
    assert payload["data"]["expires_at_utc"].endswith("Z")

    connection = sqlite3.connect(database_path)
    try:
        session_row = connection.execute(
            """
            SELECT session_token_hash, revoked_at_utc, client_ip, user_agent
            FROM admin_sessions
            WHERE admin_user_id = 1
            LIMIT 1;
            """
        ).fetchone()
        audit_actions = connection.execute(
            """
            SELECT action_type
            FROM audit_logs
            ORDER BY id ASC;
            """
        ).fetchall()
        admin_row = connection.execute(
            """
            SELECT password_hash, last_login_at_utc
            FROM admin_users
            WHERE id = 1;
            """
        ).fetchone()
    finally:
        connection.close()

    assert session_row is not None
    assert session_row[0] != payload["data"]["session_token"]
    assert session_row[1] is None
    assert session_row[2]
    assert session_row[3]
    assert admin_row is not None
    assert admin_row[0] != "correct-password"
    assert admin_row[1]
    assert [row[0] for row in audit_actions] == ["admin_login"]


def test_admin_login_rejects_invalid_credentials_without_creating_session(tmp_path: Path) -> None:
    database_path = prepare_database(tmp_path)
    seed_admin_user(
        database_path=database_path,
        username="admin",
        password="correct-password",
    )

    with build_client(tmp_path) as client:
        response = client.post(
            "/api/admin/auth/login",
            json={"username": "admin", "password": "wrong-password"},
        )

    payload = response.json()
    assert response.status_code == 401
    assert payload["error_code"] == "ADMIN_AUTH_INVALID_CREDENTIALS"
    assert payload["message"] == "用户名或密码错误"

    connection = sqlite3.connect(database_path)
    try:
        session_count = connection.execute("SELECT COUNT(*) FROM admin_sessions;").fetchone()
    finally:
        connection.close()

    assert session_count == (0,)


def test_admin_logout_revokes_current_session_and_writes_audit_log(tmp_path: Path) -> None:
    database_path = prepare_database(tmp_path)
    seed_admin_user(
        database_path=database_path,
        username="admin",
        password="correct-password",
    )

    with build_client(tmp_path) as client:
        login_response = client.post(
            "/api/admin/auth/login",
            json={"username": "admin", "password": "correct-password"},
        )
        session_token = login_response.json()["data"]["session_token"]
        logout_response = client.post(
            "/api/admin/auth/logout",
            headers={"Authorization": f"Bearer {session_token}"},
        )

    payload = logout_response.json()
    assert logout_response.status_code == 200
    assert payload["data"] == {"revoked": True}

    connection = sqlite3.connect(database_path)
    try:
        revoked_at = connection.execute(
            """
            SELECT revoked_at_utc
            FROM admin_sessions
            WHERE admin_user_id = 1
            LIMIT 1;
            """
        ).fetchone()
        audit_actions = connection.execute(
            """
            SELECT action_type
            FROM audit_logs
            ORDER BY id ASC;
            """
        ).fetchall()
    finally:
        connection.close()

    assert revoked_at is not None
    assert revoked_at[0]
    assert [row[0] for row in audit_actions] == ["admin_login", "admin_logout"]


def test_admin_logout_rejects_expired_session(tmp_path: Path) -> None:
    database_path = prepare_database(tmp_path)
    seed_admin_user(
        database_path=database_path,
        username="admin",
        password="correct-password",
    )

    with build_client(tmp_path) as client:
        login_response = client.post(
            "/api/admin/auth/login",
            json={"username": "admin", "password": "correct-password"},
        )
        session_token = login_response.json()["data"]["session_token"]

    connection = sqlite3.connect(database_path)
    try:
        connection.execute(
            """
            UPDATE admin_sessions
            SET expires_at_utc = '2000-01-01T00:00:00Z'
            WHERE admin_user_id = 1;
            """
        )
        connection.commit()
    finally:
        connection.close()

    with build_client(tmp_path) as client:
        response = client.post(
            "/api/admin/auth/logout",
            headers={"Authorization": f"Bearer {session_token}"},
        )

    payload = response.json()
    assert response.status_code == 401
    assert payload["error_code"] == "ADMIN_AUTH_SESSION_EXPIRED"
    assert payload["message"] == "会话已过期，请重新登录"


def test_admin_change_password_updates_hash_revokes_sessions_and_requires_relogin(
    tmp_path: Path,
) -> None:
    database_path = prepare_database(tmp_path)
    seed_admin_user(
        database_path=database_path,
        username="admin",
        password="correct-password",
    )

    with build_client(tmp_path) as client:
        first_login_response = client.post(
            "/api/admin/auth/login",
            json={"username": "admin", "password": "correct-password"},
        )
        second_login_response = client.post(
            "/api/admin/auth/login",
            json={"username": "admin", "password": "correct-password"},
        )
        change_password_response = client.post(
            "/api/admin/auth/change-password",
            json={
                "current_password": "correct-password",
                "new_password": "new-password",
                "confirm_new_password": "new-password",
            },
            headers={
                "Authorization": f"Bearer {first_login_response.json()['data']['session_token']}",
            },
        )
        logout_response = client.post(
            "/api/admin/auth/logout",
            headers={
                "Authorization": f"Bearer {second_login_response.json()['data']['session_token']}",
            },
        )
        old_password_login_response = client.post(
            "/api/admin/auth/login",
            json={"username": "admin", "password": "correct-password"},
        )
        new_password_login_response = client.post(
            "/api/admin/auth/login",
            json={"username": "admin", "password": "new-password"},
        )

    payload = change_password_response.json()
    assert change_password_response.status_code == 200
    assert payload["data"] == {"relogin_required": True, "revoked_session_count": 2}

    logout_payload = logout_response.json()
    assert logout_response.status_code == 401
    assert logout_payload["error_code"] == "ADMIN_AUTH_UNAUTHORIZED"

    old_password_payload = old_password_login_response.json()
    assert old_password_login_response.status_code == 401
    assert old_password_payload["error_code"] == "ADMIN_AUTH_INVALID_CREDENTIALS"

    assert new_password_login_response.status_code == 200
    assert new_password_login_response.json()["data"]["session_token"]

    connection = sqlite3.connect(database_path)
    try:
        admin_row = connection.execute(
            """
            SELECT password_hash
            FROM admin_users
            WHERE id = 1;
            """
        ).fetchone()
        session_rows = connection.execute(
            """
            SELECT revoked_at_utc
            FROM admin_sessions
            WHERE admin_user_id = 1
            ORDER BY id ASC;
            """
        ).fetchall()
        audit_actions = connection.execute(
            """
            SELECT action_type
            FROM audit_logs
            ORDER BY id ASC;
            """
        ).fetchall()
    finally:
        connection.close()

    assert admin_row is not None
    assert verify_password("new-password", str(admin_row[0])) is True
    assert all(row[0] for row in session_rows[:2])
    assert "admin_password_changed" in [row[0] for row in audit_actions]


def test_admin_change_password_rejects_invalid_current_password(tmp_path: Path) -> None:
    database_path = prepare_database(tmp_path)
    seed_admin_user(
        database_path=database_path,
        username="admin",
        password="correct-password",
    )

    with build_client(tmp_path) as client:
        login_response = client.post(
            "/api/admin/auth/login",
            json={"username": "admin", "password": "correct-password"},
        )
        change_password_response = client.post(
            "/api/admin/auth/change-password",
            json={
                "current_password": "wrong-password",
                "new_password": "new-password",
                "confirm_new_password": "new-password",
            },
            headers={"Authorization": f"Bearer {login_response.json()['data']['session_token']}"},
        )
        old_password_login_response = client.post(
            "/api/admin/auth/login",
            json={"username": "admin", "password": "correct-password"},
        )

    payload = change_password_response.json()
    assert change_password_response.status_code == 401
    assert payload["error_code"] == "ADMIN_AUTH_INVALID_CURRENT_PASSWORD"
    assert payload["message"] == "当前密码错误"

    assert old_password_login_response.status_code == 200

    connection = sqlite3.connect(database_path)
    try:
        audit_actions = connection.execute(
            """
            SELECT action_type
            FROM audit_logs
            ORDER BY id ASC;
            """
        ).fetchall()
    finally:
        connection.close()

    assert "admin_password_changed" not in [row[0] for row in audit_actions]


def test_admin_change_password_rejects_mismatched_confirmation(tmp_path: Path) -> None:
    database_path = prepare_database(tmp_path)
    seed_admin_user(
        database_path=database_path,
        username="admin",
        password="correct-password",
    )

    with build_client(tmp_path) as client:
        login_response = client.post(
            "/api/admin/auth/login",
            json={"username": "admin", "password": "correct-password"},
        )
        response = client.post(
            "/api/admin/auth/change-password",
            json={
                "current_password": "correct-password",
                "new_password": "new-password",
                "confirm_new_password": "other-password",
            },
            headers={"Authorization": f"Bearer {login_response.json()['data']['session_token']}"},
        )

    payload = response.json()
    assert response.status_code == 422
    assert payload["error_code"] == "ADMIN_AUTH_PASSWORD_CONFIRMATION_MISMATCH"
    assert payload["message"] == "两次输入的新密码不一致"


def test_admin_login_rejects_disabled_account(tmp_path: Path) -> None:
    database_path = prepare_database(tmp_path)
    seed_admin_user(
        database_path=database_path,
        username="disabled-admin",
        password="correct-password",
        status="disabled",
    )

    with build_client(tmp_path) as client:
        response = client.post(
            "/api/admin/auth/login",
            json={"username": "disabled-admin", "password": "correct-password"},
        )

    payload = response.json()
    assert response.status_code == 401
    assert payload["error_code"] == "ADMIN_AUTH_INVALID_CREDENTIALS"


def build_client(tmp_path: Path, *, oss_public_base_url: str | None = None) -> TestClient:
    clear_bingwall_env()
    os.environ["BINGWALL_APP_ENV"] = "test"
    os.environ["BINGWALL_APP_HOST"] = "127.0.0.1"
    os.environ["BINGWALL_APP_PORT"] = "8000"
    os.environ["BINGWALL_APP_BASE_URL"] = "http://127.0.0.1:8000"
    os.environ["BINGWALL_DATABASE_PATH"] = str(tmp_path / "data" / "bingwall.sqlite3")
    os.environ["BINGWALL_STORAGE_TMP_DIR"] = str(tmp_path / "images" / "tmp")
    os.environ["BINGWALL_STORAGE_PUBLIC_DIR"] = str(tmp_path / "images" / "public")
    os.environ["BINGWALL_STORAGE_FAILED_DIR"] = str(tmp_path / "images" / "failed")
    if oss_public_base_url is not None:
        os.environ["BINGWALL_STORAGE_OSS_PUBLIC_BASE_URL"] = oss_public_base_url
    os.environ["BINGWALL_BACKUP_DIR"] = str(tmp_path / "backups")
    os.environ["BINGWALL_SECURITY_SESSION_SECRET"] = "0123456789abcdef0123456789abcdef"
    os.environ["BINGWALL_SECURITY_SESSION_TTL_HOURS"] = "12"
    os.environ["BINGWALL_LOG_LEVEL"] = "INFO"
    reset_settings_cache()
    return TestClient(create_app())


def prepare_database(tmp_path: Path) -> Path:
    database_path = tmp_path / "data" / "bingwall.sqlite3"
    migrate_database(database_path)
    return database_path


def seed_admin_user(
    *,
    database_path: Path,
    username: str,
    password: str,
    status: str = "enabled",
) -> int:
    connection = sqlite3.connect(database_path)
    try:
        now_utc = datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        cursor = connection.execute(
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
            VALUES (?, ?, 'super_admin', ?, NULL, ?, ?);
            """,
            (username, hash_password(password), status, now_utc, now_utc),
        )
        connection.commit()
        lastrowid = cursor.lastrowid
        if lastrowid is None:
            raise RuntimeError("Failed to create admin user test record.")
        return int(lastrowid)
    finally:
        connection.close()
