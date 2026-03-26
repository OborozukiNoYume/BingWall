from pathlib import Path
import sqlite3

from app.repositories.migrations import migrate_database


def test_sqlite_migrations_create_t1_2_schema(tmp_path: Path) -> None:
    database_path = tmp_path / "bingwall.sqlite3"

    applied = migrate_database(database_path)

    assert [migration.version for migration in applied] == [1, 2, 3, 4, 5]

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
        wallpaper_columns = _fetch_table_columns(connection, "wallpapers")
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
        "uq_image_resources_wallpaper_resource_type",
    ]
    assert "created_at_utc" in wallpaper_columns
    assert "updated_at_utc" in wallpaper_columns
    assert "published_at_utc" in wallpaper_columns
    assert any(key[2] == "admin_users" and key[3] == "admin_user_id" for key in audit_foreign_keys)


def test_sqlite_migrations_are_repeatable(tmp_path: Path) -> None:
    database_path = tmp_path / "bingwall.sqlite3"

    first_run = migrate_database(database_path)
    second_run = migrate_database(database_path)

    assert [migration.version for migration in first_run] == [1, 2, 3, 4, 5]
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
    ]


def _fetch_names(connection: sqlite3.Connection, query: str) -> list[str]:
    rows = connection.execute(query).fetchall()
    return [str(row[0]) for row in rows]


def _fetch_table_columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    rows = connection.execute(f"PRAGMA table_info('{table_name}');").fetchall()
    return {str(row[1]) for row in rows}
