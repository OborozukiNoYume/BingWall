from __future__ import annotations

import sqlite3
from typing import cast

from app.domain.resource_variants import derive_resource_status
from app.domain.resource_variants import RESOURCE_TYPE_ORIGINAL
from app.repositories.collection_repository_models import ResourceCreateInput


class CollectionRepositoryResourceMixin:
    connection: sqlite3.Connection

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

    def find_image_resource_by_source_url_hash_in_scope(
        self,
        *,
        source_url_hash: str,
        source_type: str,
        market_code: str,
    ) -> sqlite3.Row | None:
        row = self.connection.execute(
            """
            SELECT r.*, w.source_type, w.market_code
            FROM image_resources AS r
            INNER JOIN wallpapers AS w ON w.id = r.wallpaper_id
            WHERE r.source_url_hash = ?
              AND w.source_type = ?
              AND w.market_code = ?
            LIMIT 1;
            """,
            (source_url_hash, source_type, market_code),
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

    def list_image_resources_for_wallpaper(self, *, wallpaper_id: int) -> list[sqlite3.Row]:
        rows = self.connection.execute(
            """
            SELECT
                id,
                resource_type,
                variant_key,
                storage_backend,
                relative_path,
                file_size_bytes,
                image_status,
                integrity_check_result
            FROM image_resources
            WHERE wallpaper_id = ?
            ORDER BY id ASC;
            """,
            (wallpaper_id,),
        ).fetchall()
        return list(rows)

    def delete_image_resources_for_wallpaper(self, *, wallpaper_id: int) -> None:
        self.connection.execute(
            """
            DELETE FROM image_resources
            WHERE wallpaper_id = ?;
            """,
            (wallpaper_id,),
        )
        self.connection.commit()

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

    def update_image_resource_relative_path(
        self,
        *,
        resource_id: int,
        relative_path: str,
        filename: str,
        file_ext: str,
        mime_type: str,
        updated_at_utc: str,
    ) -> None:
        self.connection.execute(
            """
            UPDATE image_resources
            SET relative_path = ?,
                filename = ?,
                file_ext = ?,
                mime_type = ?,
                updated_at_utc = ?
            WHERE id = ?;
            """,
            (relative_path, filename, file_ext, mime_type, updated_at_utc, resource_id),
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
