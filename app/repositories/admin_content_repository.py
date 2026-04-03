from __future__ import annotations

from datetime import UTC
from datetime import datetime
from pathlib import Path
import sqlite3
from typing import cast

from app.repositories.sqlite import connect_sqlite
from app.schemas.admin_content import AdminTagListQuery
from app.schemas.admin_content import AdminAuditLogListQuery
from app.schemas.admin_content import AdminWallpaperListQuery


class AdminContentRepository:
    def __init__(self, database_path: str | Path) -> None:
        self.connection = connect_sqlite(Path(database_path))
        self.connection.row_factory = sqlite3.Row

    def close(self) -> None:
        self.connection.close()

    def list_wallpapers(self, *, query: AdminWallpaperListQuery) -> tuple[list[sqlite3.Row], int]:
        filters, parameters = self._build_wallpaper_filters(query=query)
        count_row = self.connection.execute(
            f"""
            SELECT COUNT(*)
            FROM wallpapers AS w
            LEFT JOIN image_resources AS r ON r.id = w.default_resource_id
            WHERE {filters};
            """,
            parameters,
        ).fetchone()
        total = int(count_row[0]) if count_row is not None else 0
        offset = (query.page - 1) * query.page_size
        rows = self.connection.execute(
            f"""
            SELECT
                w.id,
                w.title,
                w.copyright_text,
                w.source_key,
                w.market_code,
                w.wallpaper_date,
                w.source_type,
                w.source_name,
                w.content_status,
                w.resource_status,
                w.is_public,
                w.is_downloadable,
                w.created_at_utc,
                w.updated_at_utc,
                r.image_status,
                r.relative_path,
                r.storage_backend,
                COALESCE(r.width, w.origin_width) AS width,
                COALESCE(r.height, w.origin_height) AS height,
                r.failure_reason
            FROM wallpapers AS w
            LEFT JOIN image_resources AS r ON r.id = w.default_resource_id
            WHERE {filters}
            ORDER BY w.created_at_utc DESC, w.id DESC
            LIMIT ? OFFSET ?;
            """,
            (*parameters, query.page_size, offset),
        ).fetchall()
        return list(rows), total

    def get_wallpaper_detail(self, *, wallpaper_id: int) -> sqlite3.Row | None:
        row = self.connection.execute(
            """
            SELECT
                w.id,
                w.title,
                w.subtitle,
                w.description,
                w.location_text,
                w.copyright_text,
                w.source_type,
                w.source_name,
                w.source_key,
                w.canonical_key,
                w.market_code,
                w.wallpaper_date,
                w.published_at_utc,
                w.publish_start_at_utc,
                w.publish_end_at_utc,
                w.origin_page_url,
                w.origin_image_url,
                w.origin_width,
                w.origin_height,
                w.content_status,
                w.resource_status,
                w.is_public,
                w.is_downloadable,
                w.deleted_at_utc,
                w.created_at_utc,
                w.updated_at_utc,
                r.relative_path,
                r.resource_type,
                r.storage_backend,
                r.mime_type,
                r.file_size_bytes,
                COALESCE(r.width, w.origin_width) AS width,
                COALESCE(r.height, w.origin_height) AS height,
                r.image_status,
                r.failure_reason
            FROM wallpapers AS w
            LEFT JOIN image_resources AS r ON r.id = w.default_resource_id
            WHERE w.id = ?
            LIMIT 1;
            """,
            (wallpaper_id,),
        ).fetchone()
        return cast(sqlite3.Row | None, row)

    def list_wallpaper_localizations(self, *, wallpaper_id: int) -> list[sqlite3.Row]:
        rows = self.connection.execute(
            """
            SELECT
                market_code,
                source_key,
                title,
                subtitle,
                description,
                copyright_text,
                published_at_utc,
                location_text,
                origin_page_url,
                portrait_image_url,
                updated_at_utc
            FROM wallpaper_localizations
            WHERE wallpaper_id = ?
            ORDER BY market_code ASC, id ASC;
            """,
            (wallpaper_id,),
        ).fetchall()
        return list(rows)

    def get_wallpaper_for_tag_binding(self, *, wallpaper_id: int) -> sqlite3.Row | None:
        row = self.connection.execute(
            """
            SELECT
                id,
                title,
                content_status
            FROM wallpapers
            WHERE id = ?
            LIMIT 1;
            """,
            (wallpaper_id,),
        ).fetchone()
        return cast(sqlite3.Row | None, row)

    def get_wallpaper_for_status_change(self, *, wallpaper_id: int) -> sqlite3.Row | None:
        row = self.connection.execute(
            """
            SELECT
                w.id,
                w.title,
                w.content_status,
                w.resource_status,
                w.is_public,
                w.is_downloadable,
                w.deleted_at_utc,
                r.image_status
            FROM wallpapers AS w
            LEFT JOIN image_resources AS r ON r.id = w.default_resource_id
            WHERE w.id = ?
            LIMIT 1;
            """,
            (wallpaper_id,),
        ).fetchone()
        return cast(sqlite3.Row | None, row)

    def update_wallpaper_status(
        self,
        *,
        wallpaper_id: int,
        content_status: str,
        is_public: bool,
        deleted_at_utc: str | None,
        updated_at_utc: str,
    ) -> None:
        with self.connection:
            self.connection.execute(
                """
                UPDATE wallpapers
                SET content_status = ?,
                    is_public = ?,
                    deleted_at_utc = ?,
                    updated_at_utc = ?
                WHERE id = ?;
                """,
                (content_status, int(is_public), deleted_at_utc, updated_at_utc, wallpaper_id),
            )

    def insert_audit_log(
        self,
        *,
        admin_user_id: int,
        action_type: str,
        target_type: str,
        target_id: str,
        before_state_json: str | None,
        after_state_json: str | None,
        request_source: str | None,
        trace_id: str,
        created_at_utc: str,
    ) -> None:
        with self.connection:
            self.connection.execute(
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
                    before_state_json,
                    after_state_json,
                    request_source,
                    trace_id,
                    created_at_utc,
                ),
            )

    def list_audit_logs(self, *, query: AdminAuditLogListQuery) -> tuple[list[sqlite3.Row], int]:
        filters, parameters = self._build_audit_log_filters(query=query)
        count_row = self.connection.execute(
            f"""
            SELECT COUNT(*)
            FROM audit_logs AS a
            INNER JOIN admin_users AS u ON u.id = a.admin_user_id
            WHERE {filters};
            """,
            parameters,
        ).fetchone()
        total = int(count_row[0]) if count_row is not None else 0
        offset = (query.page - 1) * query.page_size
        rows = self.connection.execute(
            f"""
            SELECT
                a.id,
                a.admin_user_id,
                u.username AS admin_username,
                a.action_type,
                a.target_type,
                a.target_id,
                a.before_state_json,
                a.after_state_json,
                a.request_source,
                a.trace_id,
                a.created_at_utc
            FROM audit_logs AS a
            INNER JOIN admin_users AS u ON u.id = a.admin_user_id
            WHERE {filters}
            ORDER BY a.created_at_utc DESC, a.id DESC
            LIMIT ? OFFSET ?;
            """,
            (*parameters, query.page_size, offset),
        ).fetchall()
        return list(rows), total

    def list_recent_audit_logs_for_target(
        self,
        *,
        target_type: str,
        target_id: str,
        limit: int,
    ) -> list[sqlite3.Row]:
        rows = self.connection.execute(
            """
            SELECT
                a.id,
                a.admin_user_id,
                u.username AS admin_username,
                a.action_type,
                a.target_type,
                a.target_id,
                a.before_state_json,
                a.after_state_json,
                a.request_source,
                a.trace_id,
                a.created_at_utc
            FROM audit_logs AS a
            INNER JOIN admin_users AS u ON u.id = a.admin_user_id
            WHERE a.target_type = ?
              AND a.target_id = ?
            ORDER BY a.created_at_utc DESC, a.id DESC
            LIMIT ?;
            """,
            (target_type, target_id, limit),
        ).fetchall()
        return list(rows)

    def list_tags(self, *, query: AdminTagListQuery) -> list[sqlite3.Row]:
        filters, parameters = self._build_tag_filters(query=query)
        rows = self.connection.execute(
            f"""
            SELECT
                t.id,
                t.tag_key,
                t.tag_name,
                t.tag_category,
                t.status,
                t.sort_weight,
                t.created_at_utc,
                t.updated_at_utc,
                COUNT(wt.wallpaper_id) AS wallpaper_count
            FROM tags AS t
            LEFT JOIN wallpaper_tags AS wt ON wt.tag_id = t.id
            WHERE {filters}
            GROUP BY
                t.id,
                t.tag_key,
                t.tag_name,
                t.tag_category,
                t.status,
                t.sort_weight,
                t.created_at_utc,
                t.updated_at_utc
            ORDER BY t.sort_weight DESC, t.tag_name ASC, t.id ASC;
            """,
            parameters,
        ).fetchall()
        return list(rows)

    def get_tag_by_id(self, *, tag_id: int) -> sqlite3.Row | None:
        row = self.connection.execute(
            """
            SELECT
                t.id,
                t.tag_key,
                t.tag_name,
                t.tag_category,
                t.status,
                t.sort_weight,
                t.created_at_utc,
                t.updated_at_utc,
                COUNT(wt.wallpaper_id) AS wallpaper_count
            FROM tags AS t
            LEFT JOIN wallpaper_tags AS wt ON wt.tag_id = t.id
            WHERE t.id = ?
            GROUP BY
                t.id,
                t.tag_key,
                t.tag_name,
                t.tag_category,
                t.status,
                t.sort_weight,
                t.created_at_utc,
                t.updated_at_utc
            LIMIT 1;
            """,
            (tag_id,),
        ).fetchone()
        return cast(sqlite3.Row | None, row)

    def get_tag_by_key(self, *, tag_key: str) -> sqlite3.Row | None:
        row = self.connection.execute(
            """
            SELECT
                t.id,
                t.tag_key,
                t.tag_name,
                t.tag_category,
                t.status,
                t.sort_weight,
                t.created_at_utc,
                t.updated_at_utc,
                COUNT(wt.wallpaper_id) AS wallpaper_count
            FROM tags AS t
            LEFT JOIN wallpaper_tags AS wt ON wt.tag_id = t.id
            WHERE t.tag_key = ?
            GROUP BY
                t.id,
                t.tag_key,
                t.tag_name,
                t.tag_category,
                t.status,
                t.sort_weight,
                t.created_at_utc,
                t.updated_at_utc
            LIMIT 1;
            """,
            (tag_key,),
        ).fetchone()
        return cast(sqlite3.Row | None, row)

    def create_tag(
        self,
        *,
        tag_key: str,
        tag_name: str,
        tag_category: str | None,
        status: str,
        sort_weight: int,
        created_at_utc: str,
        updated_at_utc: str,
    ) -> int:
        with self.connection:
            cursor = self.connection.execute(
                """
                INSERT INTO tags (
                    tag_key,
                    tag_name,
                    tag_category,
                    status,
                    sort_weight,
                    created_at_utc,
                    updated_at_utc
                )
                VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    tag_key,
                    tag_name,
                    tag_category,
                    status,
                    sort_weight,
                    created_at_utc,
                    updated_at_utc,
                ),
            )
        if cursor.lastrowid is None:
            raise RuntimeError("Failed to create tag.")
        return int(cursor.lastrowid)

    def update_tag(
        self,
        *,
        tag_id: int,
        tag_key: str,
        tag_name: str,
        tag_category: str | None,
        status: str,
        sort_weight: int,
        updated_at_utc: str,
    ) -> None:
        with self.connection:
            self.connection.execute(
                """
                UPDATE tags
                SET tag_key = ?,
                    tag_name = ?,
                    tag_category = ?,
                    status = ?,
                    sort_weight = ?,
                    updated_at_utc = ?
                WHERE id = ?;
                """,
                (
                    tag_key,
                    tag_name,
                    tag_category,
                    status,
                    sort_weight,
                    updated_at_utc,
                    tag_id,
                ),
            )

    def list_wallpaper_tags(self, *, wallpaper_id: int) -> list[sqlite3.Row]:
        rows = self.connection.execute(
            """
            SELECT
                t.id,
                t.tag_key,
                t.tag_name,
                t.tag_category,
                t.status,
                t.sort_weight
            FROM wallpaper_tags AS wt
            INNER JOIN tags AS t ON t.id = wt.tag_id
            WHERE wt.wallpaper_id = ?
            ORDER BY t.sort_weight DESC, t.tag_name ASC, t.id ASC;
            """,
            (wallpaper_id,),
        ).fetchall()
        return list(rows)

    def list_tags_by_ids(self, *, tag_ids: list[int]) -> list[sqlite3.Row]:
        if not tag_ids:
            return []
        placeholders = ", ".join("?" for _ in tag_ids)
        rows = self.connection.execute(
            f"""
            SELECT
                t.id,
                t.tag_key,
                t.tag_name,
                t.tag_category,
                t.status,
                t.sort_weight
            FROM tags AS t
            WHERE t.id IN ({placeholders})
            ORDER BY t.sort_weight DESC, t.tag_name ASC, t.id ASC;
            """,
            tuple(tag_ids),
        ).fetchall()
        return list(rows)

    def replace_wallpaper_tags(
        self,
        *,
        wallpaper_id: int,
        tag_ids: list[int],
        created_at_utc: str,
        created_by: str,
    ) -> None:
        with self.connection:
            self.connection.execute(
                "DELETE FROM wallpaper_tags WHERE wallpaper_id = ?;",
                (wallpaper_id,),
            )
            for tag_id in tag_ids:
                self.connection.execute(
                    """
                    INSERT INTO wallpaper_tags (
                        wallpaper_id,
                        tag_id,
                        created_at_utc,
                        created_by
                    )
                    VALUES (?, ?, ?, ?);
                    """,
                    (wallpaper_id, tag_id, created_at_utc, created_by),
                )

    def _build_wallpaper_filters(
        self, *, query: AdminWallpaperListQuery
    ) -> tuple[str, tuple[str | int, ...]]:
        clauses = ["1 = 1"]
        parameters: list[str | int] = []
        if query.content_status is not None:
            clauses.append("w.content_status = ?")
            parameters.append(query.content_status)
        if query.image_status is not None:
            clauses.append("r.image_status = ?")
            parameters.append(query.image_status)
        if query.market_code is not None:
            clauses.append(
                """
                (
                    w.market_code = ?
                    OR EXISTS (
                        SELECT 1
                        FROM wallpaper_localizations AS wl_market
                        WHERE wl_market.wallpaper_id = w.id
                          AND wl_market.market_code = ?
                    )
                )
                """
            )
            parameters.extend([query.market_code, query.market_code])
        if query.keyword is not None:
            keyword = build_like_pattern(query.keyword)
            clauses.append(
                """
                (
                    w.title LIKE ? ESCAPE '\\' COLLATE NOCASE
                    OR w.subtitle LIKE ? ESCAPE '\\' COLLATE NOCASE
                    OR w.description LIKE ? ESCAPE '\\' COLLATE NOCASE
                    OR w.copyright_text LIKE ? ESCAPE '\\' COLLATE NOCASE
                    OR EXISTS (
                        SELECT 1
                        FROM wallpaper_localizations AS wl_search
                        WHERE wl_search.wallpaper_id = w.id
                          AND (
                              wl_search.title LIKE ? ESCAPE '\\' COLLATE NOCASE
                              OR wl_search.subtitle LIKE ? ESCAPE '\\' COLLATE NOCASE
                              OR wl_search.description LIKE ? ESCAPE '\\' COLLATE NOCASE
                              OR wl_search.copyright_text LIKE ? ESCAPE '\\' COLLATE NOCASE
                          )
                    )
                    OR EXISTS (
                        SELECT 1
                        FROM wallpaper_tags AS wt_search
                        INNER JOIN tags AS t_search ON t_search.id = wt_search.tag_id
                        WHERE wt_search.wallpaper_id = w.id
                          AND (
                              t_search.tag_key LIKE ? ESCAPE '\\' COLLATE NOCASE
                              OR t_search.tag_name LIKE ? ESCAPE '\\' COLLATE NOCASE
                          )
                    )
                )
                """
            )
            parameters.extend(
                [
                    keyword,
                    keyword,
                    keyword,
                    keyword,
                    keyword,
                    keyword,
                    keyword,
                    keyword,
                    keyword,
                    keyword,
                ]
            )
        if query.created_from_utc is not None:
            clauses.append("w.created_at_utc >= ?")
            parameters.append(datetime_to_utc_string(query.created_from_utc))
        if query.created_to_utc is not None:
            clauses.append("w.created_at_utc <= ?")
            parameters.append(datetime_to_utc_string(query.created_to_utc))
        return " AND ".join(clauses), tuple(parameters)

    def _build_audit_log_filters(
        self, *, query: AdminAuditLogListQuery
    ) -> tuple[str, tuple[str | int, ...]]:
        clauses = ["1 = 1"]
        parameters: list[str | int] = []
        if query.admin_user_id is not None:
            clauses.append("a.admin_user_id = ?")
            parameters.append(query.admin_user_id)
        if query.target_type is not None:
            clauses.append("a.target_type = ?")
            parameters.append(query.target_type)
        if query.target_id is not None:
            clauses.append("a.target_id = ?")
            parameters.append(query.target_id)
        if query.started_from_utc is not None:
            clauses.append("a.created_at_utc >= ?")
            parameters.append(datetime_to_utc_string(query.started_from_utc))
        if query.started_to_utc is not None:
            clauses.append("a.created_at_utc <= ?")
            parameters.append(datetime_to_utc_string(query.started_to_utc))
        return " AND ".join(clauses), tuple(parameters)

    def _build_tag_filters(self, *, query: AdminTagListQuery) -> tuple[str, tuple[str, ...]]:
        clauses = ["1 = 1"]
        parameters: list[str] = []
        if query.status is not None:
            clauses.append("t.status = ?")
            parameters.append(query.status)
        if query.tag_category is not None:
            clauses.append("t.tag_category = ?")
            parameters.append(query.tag_category)
        return " AND ".join(clauses), tuple(parameters)


def datetime_to_utc_string(value: datetime) -> str:
    normalized = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return normalized.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_like_pattern(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"
