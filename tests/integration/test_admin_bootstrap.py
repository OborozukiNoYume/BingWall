from __future__ import annotations

from pathlib import Path
import sqlite3

from app.services.admin_bootstrap import ensure_bootstrap_admin_user
from tests.integration.test_admin_auth import prepare_database, seed_admin_user


def test_bootstrap_admin_user_creates_enabled_super_admin_when_database_is_empty(
    tmp_path: Path,
) -> None:
    database_path = prepare_database(tmp_path)

    created = ensure_bootstrap_admin_user(
        database_path=database_path,
        username="admin",
        password="strong-admin-password",
    )

    assert created is True

    connection = sqlite3.connect(database_path)
    try:
        row = connection.execute(
            """
            SELECT username, role_name, status, password_hash
            FROM admin_users
            LIMIT 1;
            """
        ).fetchone()
    finally:
        connection.close()

    assert row is not None
    assert row[0] == "admin"
    assert row[1] == "super_admin"
    assert row[2] == "enabled"
    assert row[3] != "strong-admin-password"


def test_bootstrap_admin_user_is_repeatable_without_creating_duplicates(tmp_path: Path) -> None:
    database_path = prepare_database(tmp_path)

    first_created = ensure_bootstrap_admin_user(
        database_path=database_path,
        username="admin",
        password="strong-admin-password",
    )
    second_created = ensure_bootstrap_admin_user(
        database_path=database_path,
        username="admin",
        password="strong-admin-password",
    )

    connection = sqlite3.connect(database_path)
    try:
        admin_count = connection.execute("SELECT COUNT(*) FROM admin_users;").fetchone()
    finally:
        connection.close()

    assert first_created is True
    assert second_created is False
    assert admin_count == (1,)


def test_bootstrap_admin_user_does_not_override_existing_admins(tmp_path: Path) -> None:
    database_path = prepare_database(tmp_path)
    seed_admin_user(
        database_path=database_path,
        username="existing-admin",
        password="already-present-password",
    )

    created = ensure_bootstrap_admin_user(
        database_path=database_path,
        username="admin",
        password="strong-admin-password",
    )

    connection = sqlite3.connect(database_path)
    try:
        usernames = connection.execute(
            """
            SELECT username
            FROM admin_users
            ORDER BY id ASC;
            """
        ).fetchall()
    finally:
        connection.close()

    assert created is False
    assert usernames == [("existing-admin",)]
