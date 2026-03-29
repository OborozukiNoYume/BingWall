from pathlib import Path
import sqlite3

import pytest

from app.repositories.migrations import discover_migration_scripts
from app.repositories.migrations import migrate_database
from app.repositories.sqlite import connect_sqlite


def test_sqlite_migrations_create_t1_2_schema(tmp_path: Path) -> None:
    database_path = tmp_path / "bingwall.sqlite3"

    applied = migrate_database(database_path)

    assert [migration.version for migration in applied] == [1, 2, 3, 4, 5, 6, 7, 8]

    connection = sqlite3.connect(database_path)
    try:
        tables = _fetch_names(
            connection,
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name;
            """,
        )
        indexes = _fetch_names(
            connection,
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'index'
              AND name NOT LIKE 'sqlite_autoindex%'
            ORDER BY name;
            """,
        )
        triggers = _fetch_names(
            connection,
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'trigger'
            ORDER BY name;
            """,
        )
        wallpaper_columns = _fetch_table_columns(connection, "wallpapers")
        image_resource_columns = _fetch_table_columns(connection, "image_resources")
        audit_foreign_keys = connection.execute("PRAGMA foreign_key_list('audit_logs');").fetchall()
    finally:
        connection.close()

    assert tables == [
        "admin_sessions",
        "admin_users",
        "audit_logs",
        "collection_task_items",
        "collection_tasks",
        "download_events",
        "image_resources",
        "schema_migrations",
        "tags",
        "wallpaper_tags",
        "wallpapers",
    ]
    assert indexes == [
        "idx_admin_sessions_token_hash",
        "idx_admin_sessions_user_expires",
        "idx_collection_task_items_result_status",
        "idx_collection_task_items_task_occurred",
        "idx_collection_tasks_status_created",
        "idx_collection_tasks_trigger_created",
        "idx_download_events_market_occurred",
        "idx_download_events_resource_occurred",
        "idx_download_events_result_occurred",
        "idx_download_events_wallpaper_occurred",
        "idx_image_resources_content_hash",
        "idx_image_resources_source_url_hash",
        "idx_image_resources_status_processed",
        "idx_image_resources_wallpaper_resource_type",
        "idx_tags_status_sort",
        "idx_wallpaper_tags_tag_wallpaper",
        "idx_wallpapers_created_at_utc",
        "idx_wallpapers_market_date",
        "idx_wallpapers_public_listing",
        "uq_image_resources_wallpaper_resource_variant",
    ]
    assert triggers == [
        "tr_admin_users_status_insert",
        "tr_admin_users_status_update",
    ]
    assert "created_at_utc" in wallpaper_columns
    assert "updated_at_utc" in wallpaper_columns
    assert "published_at_utc" in wallpaper_columns
    assert "portrait_image_url" in wallpaper_columns
    assert "variant_key" in image_resource_columns
    assert any(key[2] == "admin_users" and key[3] == "admin_user_id" for key in audit_foreign_keys)


def test_sqlite_migrations_are_repeatable(tmp_path: Path) -> None:
    database_path = tmp_path / "bingwall.sqlite3"

    first_run = migrate_database(database_path)
    second_run = migrate_database(database_path)

    assert [migration.version for migration in first_run] == [1, 2, 3, 4, 5, 6, 7, 8]
    assert second_run == []

    connection = sqlite3.connect(database_path)
    try:
        schema_migrations_rows = connection.execute(
            """
            SELECT version, name
            FROM schema_migrations
            ORDER BY version;
            """
        ).fetchall()
    finally:
        connection.close()

    assert schema_migrations_rows == [
        (1, "baseline"),
        (2, "admin_sessions"),
        (3, "tags"),
        (4, "image_resource_variants"),
        (5, "download_events"),
        (6, "admin_user_status_constraint"),
        (7, "image_resource_download_resolution_variants"),
        (8, "wallpapers_bing_portrait_image_url"),
    ]


def test_admin_user_status_constraint_migration_cleans_legacy_values_and_blocks_invalid_writes(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "bingwall.sqlite3"
    _apply_migrations_through_version(database_path=database_path, target_version=5)

    connection = sqlite3.connect(database_path)
    try:
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
            VALUES
                ('legacy-active', 'hash-1', 'super_admin', 'active', NULL, '2026-03-27T00:00:00Z', '2026-03-27T00:00:00Z'),
                ('legacy-disabled', 'hash-2', 'super_admin', ' DISABLED ', NULL, '2026-03-27T00:00:00Z', '2026-03-27T00:00:00Z'),
                ('legacy-unknown', 'hash-3', 'super_admin', 'pending', NULL, '2026-03-27T00:00:00Z', '2026-03-27T00:00:00Z');
            """
        )
        connection.commit()
    finally:
        connection.close()

    applied = migrate_database(database_path)
    assert [migration.version for migration in applied] == [6, 7, 8]

    connection = sqlite3.connect(database_path)
    try:
        rows = connection.execute(
            """
            SELECT username, status
            FROM admin_users
            ORDER BY username ASC;
            """
        ).fetchall()

        with pytest.raises(sqlite3.IntegrityError):
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
                VALUES (
                    'legacy-invalid-after-migration',
                    'hash-4',
                    'super_admin',
                    'active',
                    NULL,
                    '2026-03-27T00:00:00Z',
                    '2026-03-27T00:00:00Z'
                );
                """
            )

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE admin_users SET status = 'pending' WHERE username = 'legacy-active';"
            )
    finally:
        connection.close()

    assert rows == [
        ("legacy-active", "enabled"),
        ("legacy-disabled", "disabled"),
        ("legacy-unknown", "disabled"),
    ]


def _fetch_names(connection: sqlite3.Connection, query: str) -> list[str]:
    rows = connection.execute(query).fetchall()
    return [str(row[0]) for row in rows]


def _fetch_table_columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    rows = connection.execute(f"PRAGMA table_info('{table_name}');").fetchall()
    return {str(row[1]) for row in rows}


def _apply_migrations_through_version(*, database_path: Path, target_version: int) -> None:
    connection = connect_sqlite(database_path)
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at_utc TEXT NOT NULL
            );
            """
        )
        for migration in discover_migration_scripts():
            if migration.version > target_version:
                break
            with connection:
                connection.executescript(migration.path.read_text(encoding="utf-8"))
                connection.execute(
                    """
                    INSERT INTO schema_migrations (version, name, applied_at_utc)
                    VALUES (?, ?, ?);
                    """,
                    (migration.version, migration.name, "2026-03-27T00:00:00Z"),
                )
    finally:
        connection.close()
