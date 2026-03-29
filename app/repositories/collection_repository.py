from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3
from typing import cast
from typing import Any

from app.domain.resource_variants import derive_resource_status
from app.domain.resource_variants import RESOURCE_TYPE_ORIGINAL
from app.repositories.sqlite import connect_sqlite


@dataclass(frozen=True, slots=True)
class WallpaperCreateInput:
    source_type: str
    source_key: str
    market_code: str
    wallpaper_date: str
    title: str | None
    copyright_text: str | None
    source_name: str
    origin_page_url: str | None
    origin_image_url: str
    origin_width: int | None
    origin_height: int | None
    is_downloadable: bool
    raw_extra_json: str
    created_at_utc: str


@dataclass(frozen=True, slots=True)
class ResourceCreateInput:
    wallpaper_id: int
    resource_type: str
    storage_backend: str
    relative_path: str
    filename: str
    file_ext: str
    mime_type: str
    source_url: str | None
    source_url_hash: str | None
    created_at_utc: str
    variant_key: str = ""


@dataclass(frozen=True, slots=True)
class TaskItemCreateInput:
    task_id: int
    source_item_key: str | None
    action_name: str
    result_status: str
    dedupe_hit_type: str | None
    db_write_result: str | None
    file_write_result: str | None
    failure_reason: str | None
    occurred_at_utc: str


class CollectionRepository:
    def __init__(self, database_path: str | Path) -> None:
        self.connection = connect_sqlite(Path(database_path))
        self.connection.row_factory = sqlite3.Row

    def close(self) -> None:
        self.connection.close()

    def create_collection_task(
        self,
        *,
        task_type: str,
        source_type: str,
        trigger_type: str,
        triggered_by: str | None,
        request_snapshot_json: str,
        created_at_utc: str,
    ) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO collection_tasks (
                task_type,
                source_type,
                trigger_type,
                triggered_by,
                task_status,
                request_snapshot_json,
                started_at_utc,
                success_count,
                duplicate_count,
                failure_count,
                created_at_utc,
                updated_at_utc
            )
            VALUES (?, ?, ?, ?, 'running', ?, ?, 0, 0, 0, ?, ?);
            """,
            (
                task_type,
                source_type,
                trigger_type,
                triggered_by,
                request_snapshot_json,
                created_at_utc,
                created_at_utc,
                created_at_utc,
            ),
        )
        self.connection.commit()
        lastrowid = cursor.lastrowid
        if lastrowid is None:
            msg = "Failed to create collection task."
            raise RuntimeError(msg)
        return int(lastrowid)

    def claim_next_queued_task(
        self,
        *,
        source_type: str,
        claimed_at_utc: str,
    ) -> sqlite3.Row | None:
        self.connection.execute("BEGIN IMMEDIATE;")
        try:
            running_row = self.connection.execute(
                """
                SELECT id
                FROM collection_tasks
                WHERE source_type = ?
                  AND task_status = 'running'
                ORDER BY started_at_utc ASC, id ASC
                LIMIT 1;
                """,
                (source_type,),
            ).fetchone()
            if running_row is not None:
                self.connection.commit()
                return None

            queued_row = self.connection.execute(
                """
                SELECT *
                FROM collection_tasks
                WHERE source_type = ?
                  AND task_status = 'queued'
                ORDER BY created_at_utc ASC, id ASC
                LIMIT 1;
                """,
                (source_type,),
            ).fetchone()
            if queued_row is None:
                self.connection.commit()
                return None

            updated = self.connection.execute(
                """
                UPDATE collection_tasks
                SET task_status = 'running',
                    started_at_utc = ?,
                    updated_at_utc = ?
                WHERE id = ?
                  AND task_status = 'queued';
                """,
                (claimed_at_utc, claimed_at_utc, int(queued_row["id"])),
            )
            if updated.rowcount != 1:
                self.connection.commit()
                return None

            claimed_row = self.connection.execute(
                """
                SELECT *
                FROM collection_tasks
                WHERE id = ?
                LIMIT 1;
                """,
                (int(queued_row["id"]),),
            ).fetchone()
            self.connection.commit()
            return cast(sqlite3.Row | None, claimed_row)
        except Exception:
            self.connection.rollback()
            raise

    def claim_next_queued_task_for_sources(
        self,
        *,
        source_types: tuple[str, ...],
        claimed_at_utc: str,
    ) -> sqlite3.Row | None:
        if not source_types:
            return None
        placeholders = ", ".join("?" for _ in source_types)
        self.connection.execute("BEGIN IMMEDIATE;")
        try:
            running_row = self.connection.execute(
                f"""
                SELECT id
                FROM collection_tasks
                WHERE source_type IN ({placeholders})
                  AND task_status = 'running'
                ORDER BY started_at_utc ASC, id ASC
                LIMIT 1;
                """,
                source_types,
            ).fetchone()
            if running_row is not None:
                self.connection.commit()
                return None

            queued_row = self.connection.execute(
                f"""
                SELECT *
                FROM collection_tasks
                WHERE source_type IN ({placeholders})
                  AND task_status = 'queued'
                ORDER BY created_at_utc ASC, id ASC
                LIMIT 1;
                """,
                source_types,
            ).fetchone()
            if queued_row is None:
                self.connection.commit()
                return None

            updated = self.connection.execute(
                """
                UPDATE collection_tasks
                SET task_status = 'running',
                    started_at_utc = ?,
                    updated_at_utc = ?
                WHERE id = ?
                  AND task_status = 'queued';
                """,
                (claimed_at_utc, claimed_at_utc, int(queued_row["id"])),
            )
            if updated.rowcount != 1:
                self.connection.commit()
                return None

            claimed_row = self.connection.execute(
                """
                SELECT *
                FROM collection_tasks
                WHERE id = ?
                LIMIT 1;
                """,
                (int(queued_row["id"]),),
            ).fetchone()
            self.connection.commit()
            return cast(sqlite3.Row | None, claimed_row)
        except Exception:
            self.connection.rollback()
            raise

    def claim_task_by_id(
        self,
        *,
        task_id: int,
        claimed_at_utc: str,
    ) -> sqlite3.Row | None:
        self.connection.execute("BEGIN IMMEDIATE;")
        try:
            task_row = self.connection.execute(
                """
                SELECT *
                FROM collection_tasks
                WHERE id = ?
                LIMIT 1;
                """,
                (task_id,),
            ).fetchone()
            if task_row is None:
                self.connection.commit()
                return None

            running_row = self.connection.execute(
                """
                SELECT id
                FROM collection_tasks
                WHERE source_type = ?
                  AND task_status = 'running'
                  AND id != ?
                ORDER BY started_at_utc ASC, id ASC
                LIMIT 1;
                """,
                (str(task_row["source_type"]), task_id),
            ).fetchone()
            if running_row is not None:
                self.connection.commit()
                return None

            updated = self.connection.execute(
                """
                UPDATE collection_tasks
                SET task_status = 'running',
                    started_at_utc = ?,
                    updated_at_utc = ?
                WHERE id = ?
                  AND task_status = 'queued';
                """,
                (claimed_at_utc, claimed_at_utc, task_id),
            )
            if updated.rowcount != 1:
                self.connection.commit()
                return None

            claimed_row = self.connection.execute(
                """
                SELECT *
                FROM collection_tasks
                WHERE id = ?
                LIMIT 1;
                """,
                (task_id,),
            ).fetchone()
            self.connection.commit()
            return cast(sqlite3.Row | None, claimed_row)
        except Exception:
            self.connection.rollback()
            raise

    def finish_collection_task(
        self,
        *,
        task_id: int,
        task_status: str,
        success_count: int,
        duplicate_count: int,
        failure_count: int,
        error_summary: str | None,
        finished_at_utc: str,
    ) -> None:
        self.connection.execute(
            """
            UPDATE collection_tasks
            SET task_status = ?,
                finished_at_utc = ?,
                success_count = ?,
                duplicate_count = ?,
                failure_count = ?,
                error_summary = ?,
                updated_at_utc = ?
            WHERE id = ?;
            """,
            (
                task_status,
                finished_at_utc,
                success_count,
                duplicate_count,
                failure_count,
                error_summary,
                finished_at_utc,
                task_id,
            ),
        )
        self.connection.commit()

    def get_collection_task(self, *, task_id: int) -> sqlite3.Row | None:
        row = self.connection.execute(
            """
            SELECT *
            FROM collection_tasks
            WHERE id = ?
            LIMIT 1;
            """,
            (task_id,),
        ).fetchone()
        return cast(sqlite3.Row | None, row)

    def create_task_item(self, item: TaskItemCreateInput) -> None:
        self.connection.execute(
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
                item.task_id,
                item.source_item_key,
                item.action_name,
                item.result_status,
                item.dedupe_hit_type,
                item.db_write_result,
                item.file_write_result,
                item.failure_reason,
                item.occurred_at_utc,
            ),
        )
        self.connection.commit()

    def find_wallpaper_by_business_key(
        self,
        *,
        source_type: str,
        wallpaper_date: str,
        market_code: str,
    ) -> sqlite3.Row | None:
        row = self.connection.execute(
            """
            SELECT *
            FROM wallpapers
            WHERE source_type = ?
              AND wallpaper_date = ?
              AND market_code = ?;
            """,
            (source_type, wallpaper_date, market_code),
        ).fetchone()
        return cast(sqlite3.Row | None, row)

    def find_image_resource_by_source_url_hash(self, source_url_hash: str) -> sqlite3.Row | None:
        row = self.connection.execute(
            """
            SELECT *
            FROM image_resources
            WHERE source_url_hash = ?
            LIMIT 1;
            """,
            (source_url_hash,),
        ).fetchone()
        return cast(sqlite3.Row | None, row)

    def wallpaper_has_image_resources(self, *, wallpaper_id: int) -> bool:
        row = self.connection.execute(
            """
            SELECT 1
            FROM image_resources
            WHERE wallpaper_id = ?
            LIMIT 1;
            """,
            (wallpaper_id,),
        ).fetchone()
        return row is not None

    def create_wallpaper(self, item: WallpaperCreateInput) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO wallpapers (
                source_type,
                source_key,
                market_code,
                wallpaper_date,
                title,
                copyright_text,
                source_name,
                is_public,
                is_downloadable,
                origin_page_url,
                origin_image_url,
                origin_width,
                origin_height,
                resource_status,
                raw_extra_json,
                created_at_utc,
                updated_at_utc
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, 'pending', ?, ?, ?);
            """,
            (
                item.source_type,
                item.source_key,
                item.market_code,
                item.wallpaper_date,
                item.title,
                item.copyright_text,
                item.source_name,
                int(item.is_downloadable),
                item.origin_page_url,
                item.origin_image_url,
                item.origin_width,
                item.origin_height,
                item.raw_extra_json,
                item.created_at_utc,
                item.created_at_utc,
            ),
        )
        self.connection.commit()
        lastrowid = cursor.lastrowid
        if lastrowid is None:
            msg = "Failed to create wallpaper."
            raise RuntimeError(msg)
        return int(lastrowid)

    def create_image_resource(self, item: ResourceCreateInput) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO image_resources (
                wallpaper_id,
                resource_type,
                variant_key,
                storage_backend,
                relative_path,
                filename,
                file_ext,
                mime_type,
                source_url,
                source_url_hash,
                image_status,
                created_at_utc,
                updated_at_utc
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?);
            """,
            (
                item.wallpaper_id,
                item.resource_type,
                item.variant_key,
                item.storage_backend,
                item.relative_path,
                item.filename,
                item.file_ext,
                item.mime_type,
                item.source_url,
                item.source_url_hash,
                item.created_at_utc,
                item.created_at_utc,
            ),
        )
        self.connection.commit()
        lastrowid = cursor.lastrowid
        if lastrowid is None:
            msg = "Failed to create image resource."
            raise RuntimeError(msg)
        return int(lastrowid)

    def update_wallpaper_origin_metadata(
        self,
        *,
        wallpaper_id: int,
        origin_image_url: str,
        origin_width: int | None,
        origin_height: int | None,
        updated_at_utc: str,
    ) -> None:
        self.connection.execute(
            """
            UPDATE wallpapers
            SET origin_image_url = ?,
                origin_width = ?,
                origin_height = ?,
                updated_at_utc = ?
            WHERE id = ?;
            """,
            (origin_image_url, origin_width, origin_height, updated_at_utc, wallpaper_id),
        )
        self.connection.commit()

    def update_image_resource_source(
        self,
        *,
        resource_id: int,
        source_url: str | None,
        source_url_hash: str | None,
        updated_at_utc: str,
    ) -> None:
        self.connection.execute(
            """
            UPDATE image_resources
            SET source_url = ?,
                source_url_hash = ?,
                updated_at_utc = ?
            WHERE id = ?;
            """,
            (source_url, source_url_hash, updated_at_utc, resource_id),
        )
        self.connection.commit()

    def mark_image_resource_ready(
        self,
        *,
        resource_id: int,
        file_size_bytes: int,
        width: int | None,
        height: int | None,
        content_hash: str,
        downloaded_at_utc: str,
        integrity_check_result: str,
        mime_type: str,
    ) -> None:
        self.connection.execute(
            """
            UPDATE image_resources
            SET file_size_bytes = ?,
                width = ?,
                height = ?,
                content_hash = ?,
                downloaded_at_utc = ?,
                integrity_check_result = ?,
                image_status = 'ready',
                failure_reason = NULL,
                last_processed_at_utc = ?,
                mime_type = ?,
                updated_at_utc = ?
            WHERE id = ?;
            """,
            (
                file_size_bytes,
                width,
                height,
                content_hash,
                downloaded_at_utc,
                integrity_check_result,
                downloaded_at_utc,
                mime_type,
                downloaded_at_utc,
                resource_id,
            ),
        )
        self.connection.commit()

    def mark_image_resource_failed(
        self,
        *,
        resource_id: int,
        failure_reason: str,
        processed_at_utc: str,
    ) -> None:
        self.connection.execute(
            """
            UPDATE image_resources
            SET image_status = 'failed',
                failure_reason = ?,
                integrity_check_result = 'failed',
                last_processed_at_utc = ?,
                updated_at_utc = ?
            WHERE id = ?;
            """,
            (failure_reason, processed_at_utc, processed_at_utc, resource_id),
        )
        self.connection.commit()

    def mark_pending_image_resources_failed(
        self,
        *,
        resource_ids: tuple[int, ...],
        failure_reason: str,
        processed_at_utc: str,
    ) -> None:
        if not resource_ids:
            return
        placeholders = ", ".join("?" for _ in resource_ids)
        self.connection.execute(
            f"""
            UPDATE image_resources
            SET image_status = 'failed',
                failure_reason = ?,
                integrity_check_result = 'failed',
                last_processed_at_utc = ?,
                updated_at_utc = ?
            WHERE id IN ({placeholders})
              AND image_status = 'pending';
            """,
            (failure_reason, processed_at_utc, processed_at_utc, *resource_ids),
        )
        self.connection.commit()

    def refresh_wallpaper_resource_status(
        self, *, wallpaper_id: int, processed_at_utc: str
    ) -> None:
        wallpaper_row = self.connection.execute(
            """
            SELECT is_downloadable
            FROM wallpapers
            WHERE id = ?
            LIMIT 1;
            """,
            (wallpaper_id,),
        ).fetchone()
        if wallpaper_row is None:
            raise RuntimeError(f"Wallpaper {wallpaper_id} not found.")

        resource_rows = self.connection.execute(
            """
            SELECT id, resource_type, image_status
            FROM image_resources
            WHERE wallpaper_id = ?
            ORDER BY id ASC;
            """,
            (wallpaper_id,),
        ).fetchall()
        resource_status = derive_resource_status(
            resources=[
                (str(row["resource_type"]), str(row["image_status"]))
                for row in resource_rows
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

        self.connection.execute(
            """
            UPDATE wallpapers
            SET resource_status = ?,
                default_resource_id = ?,
                updated_at_utc = ?
            WHERE id = ?;
            """,
            (resource_status, default_resource_id, processed_at_utc, wallpaper_id),
        )
        self.connection.commit()

    def auto_publish_wallpaper_if_ready(self, *, wallpaper_id: int, processed_at_utc: str) -> None:
        self.connection.execute(
            """
            UPDATE wallpapers
            SET content_status = 'enabled',
                is_public = 1,
                updated_at_utc = ?
            WHERE id = ?
              AND content_status = 'draft'
              AND resource_status = 'ready';
            """,
            (processed_at_utc, wallpaper_id),
        )
        self.connection.commit()

    def fetch_one(self, query: str, parameters: tuple[Any, ...] = ()) -> sqlite3.Row | None:
        row = self.connection.execute(query, parameters).fetchone()
        return cast(sqlite3.Row | None, row)

    def fetch_all(self, query: str, parameters: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        return list(self.connection.execute(query, parameters).fetchall())
