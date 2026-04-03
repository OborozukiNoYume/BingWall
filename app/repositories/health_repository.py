from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import cast

from app.domain.resource_variants import derive_resource_status
from app.domain.resource_variants import RESOURCE_TYPE_ORIGINAL
from app.repositories.sqlite import connect_sqlite


class HealthRepository:
    def __init__(self, database_path: str | Path) -> None:
        self.connection = connect_sqlite(Path(database_path))
        self.connection.row_factory = sqlite3.Row

    def close(self) -> None:
        self.connection.close()

    def check_database_ready(self) -> None:
        self.connection.execute(
            """
            SELECT version
            FROM schema_migrations
            ORDER BY version DESC
            LIMIT 1;
            """
        ).fetchone()

    def get_latest_collection_task(self) -> sqlite3.Row | None:
        row = self.connection.execute(
            """
            SELECT
                id,
                task_type,
                source_type,
                trigger_type,
                task_status,
                success_count,
                duplicate_count,
                failure_count,
                error_summary,
                started_at_utc,
                finished_at_utc,
                created_at_utc,
                updated_at_utc
            FROM collection_tasks
            ORDER BY created_at_utc DESC, id DESC
            LIMIT 1;
            """
        ).fetchone()
        return cast(sqlite3.Row | None, row)

    def get_resource_counts(self) -> sqlite3.Row:
        row = self.connection.execute(
            """
            SELECT
                COUNT(*) AS total_resource_count,
                SUM(CASE WHEN image_status = 'ready' THEN 1 ELSE 0 END) AS ready_resource_count,
                SUM(CASE WHEN image_status = 'failed' THEN 1 ELSE 0 END) AS failed_resource_count
            FROM image_resources
            WHERE storage_backend = 'local';
            """
        ).fetchone()
        if row is None:
            msg = "Failed to query resource counts."
            raise RuntimeError(msg)
        return cast(sqlite3.Row, row)

    def list_ready_local_resources(self) -> list[sqlite3.Row]:
        rows = self.connection.execute(
            """
            SELECT
                r.id AS resource_id,
                r.wallpaper_id,
                r.relative_path,
                w.content_status
            FROM image_resources AS r
            INNER JOIN wallpapers AS w ON w.id = r.wallpaper_id
            WHERE r.storage_backend = 'local'
              AND r.image_status = 'ready'
            ORDER BY r.id ASC;
            """
        ).fetchall()
        return list(rows)

    def list_ready_local_resources_with_hashes(self) -> list[sqlite3.Row]:
        rows = self.connection.execute(
            """
            SELECT
                id AS resource_id,
                relative_path,
                content_hash
            FROM image_resources
            WHERE storage_backend = 'local'
              AND image_status = 'ready'
            ORDER BY id ASC;
            """
        ).fetchall()
        return list(rows)

    def list_local_resources_for_archive(self) -> list[sqlite3.Row]:
        rows = self.connection.execute(
            """
            SELECT
                r.id AS resource_id,
                r.wallpaper_id,
                r.resource_type,
                r.variant_key,
                r.relative_path,
                r.file_ext,
                r.file_size_bytes,
                r.width,
                r.height,
                r.image_status,
                w.source_type,
                w.source_key,
                w.canonical_key,
                w.market_code,
                w.wallpaper_date
            FROM image_resources AS r
            INNER JOIN wallpapers AS w ON w.id = r.wallpaper_id
            WHERE r.storage_backend = 'local'
            ORDER BY r.id ASC;
            """
        ).fetchall()
        return list(rows)

    def update_image_resource_relative_path(
        self,
        *,
        resource_id: int,
        relative_path: str,
        filename: str,
        file_ext: str,
        updated_at_utc: str,
    ) -> None:
        self.connection.execute(
            """
            UPDATE image_resources
            SET relative_path = ?,
                filename = ?,
                file_ext = ?,
                updated_at_utc = ?
            WHERE id = ?;
            """,
            (relative_path, filename, file_ext, updated_at_utc, resource_id),
        )
        self.connection.commit()

    def mark_resource_missing_and_sync(
        self,
        *,
        resource_id: int,
        wallpaper_id: int,
        failure_reason: str,
        processed_at_utc: str,
    ) -> tuple[bool, str]:
        disabled_wallpaper = False
        action = "marked_failed"
        with self.connection:
            self.connection.execute(
                """
                UPDATE image_resources
                SET image_status = 'failed',
                    failure_reason = ?,
                    integrity_check_result = 'failed',
                    last_processed_at_utc = ?,
                    updated_at_utc = ?
                WHERE id = ?
                  AND image_status = 'ready';
                """,
                (failure_reason, processed_at_utc, processed_at_utc, resource_id),
            )
            resource_rows = self.connection.execute(
                """
                SELECT id, resource_type, image_status
                FROM image_resources
                WHERE wallpaper_id = ?
                ORDER BY id ASC;
                """,
                (wallpaper_id,),
            ).fetchall()
            wallpaper_row = self.connection.execute(
                """
                SELECT content_status, is_downloadable
                FROM wallpapers
                WHERE id = ?
                LIMIT 1;
                """,
                (wallpaper_id,),
            ).fetchone()
            if wallpaper_row is None:
                msg = f"Wallpaper {wallpaper_id} not found while syncing missing resource."
                raise RuntimeError(msg)

            resource_status = derive_resource_status(
                resources=[
                    (str(row["resource_type"]), str(row["image_status"])) for row in resource_rows
                ],
                is_downloadable=bool(wallpaper_row["is_downloadable"]),
            )

            default_resource_id: int | None = None
            for row in resource_rows:
                if (
                    str(row["resource_type"]) == RESOURCE_TYPE_ORIGINAL
                    and str(row["image_status"]) == "ready"
                ):
                    default_resource_id = int(row["id"])
                    break
            if default_resource_id is None:
                for row in resource_rows:
                    if str(row["image_status"]) == "ready":
                        default_resource_id = int(row["id"])
                        break

            next_content_status = str(wallpaper_row["content_status"])
            next_is_public = 1 if next_content_status == "enabled" else 0
            if next_content_status == "enabled" and resource_status != "ready":
                next_content_status = "disabled"
                next_is_public = 0
                disabled_wallpaper = True
                action = "marked_failed_and_disabled"
            self.connection.execute(
                """
                UPDATE wallpapers
                SET resource_status = ?,
                    default_resource_id = ?,
                    content_status = ?,
                    is_public = ?,
                    updated_at_utc = ?
                WHERE id = ?;
                """,
                (
                    resource_status,
                    default_resource_id,
                    next_content_status,
                    next_is_public,
                    processed_at_utc,
                    wallpaper_id,
                ),
            )
        return disabled_wallpaper, action

    def mark_resource_failed_and_sync(
        self,
        *,
        resource_id: int,
        wallpaper_id: int,
        failure_reason: str,
        processed_at_utc: str,
    ) -> tuple[bool, str]:
        return self.mark_resource_missing_and_sync(
            resource_id=resource_id,
            wallpaper_id=wallpaper_id,
            failure_reason=failure_reason,
            processed_at_utc=processed_at_utc,
        )
