from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import cast

from app.domain.resource_variants import PUBLIC_DETAIL_DOWNLOAD_RESOURCE_TYPE
from app.domain.resource_variants import PUBLIC_DETAIL_PREVIEW_RESOURCE_TYPE
from app.domain.resource_variants import PUBLIC_LIST_RESOURCE_TYPE
from app.domain.resource_variants import RESOURCE_TYPE_ORIGINAL
from app.repositories.sqlite import connect_sqlite
from app.schemas.public import PublicWallpaperListQuery


class PublicRepository:
    def __init__(self, database_path: str | Path) -> None:
        self.connection = connect_sqlite(Path(database_path))
        self.connection.row_factory = sqlite3.Row

    def close(self) -> None:
        self.connection.close()

    def list_visible_wallpapers(
        self, *, query: PublicWallpaperListQuery, current_time_utc: str
    ) -> tuple[list[sqlite3.Row], int]:
        filters, parameters = self._build_visibility_filters(
            query=query,
            current_time_utc=current_time_utc,
        )
        count_row = self.connection.execute(
            f"""
            SELECT COUNT(*)
            FROM wallpapers AS w
            INNER JOIN image_resources AS original_resource
                ON original_resource.wallpaper_id = w.id
               AND original_resource.resource_type = ?
               AND original_resource.image_status = 'ready'
            LEFT JOIN image_resources AS thumbnail_resource
                ON thumbnail_resource.wallpaper_id = w.id
               AND thumbnail_resource.resource_type = ?
               AND thumbnail_resource.image_status = 'ready'
            WHERE {filters};
            """,
            (
                RESOURCE_TYPE_ORIGINAL,
                PUBLIC_LIST_RESOURCE_TYPE,
                *parameters,
            ),
        ).fetchone()
        total = int(count_row[0]) if count_row is not None else 0
        offset = (query.page - 1) * query.page_size
        items = self.connection.execute(
            f"""
            SELECT
                w.id,
                w.title,
                w.subtitle,
                w.copyright_text,
                w.source_name,
                w.market_code,
                w.wallpaper_date,
                COALESCE(thumbnail_resource.relative_path, original_resource.relative_path)
                    AS relative_path,
                COALESCE(thumbnail_resource.storage_backend, original_resource.storage_backend)
                    AS storage_backend,
                COALESCE(original_resource.width, w.origin_width) AS width,
                COALESCE(original_resource.height, w.origin_height) AS height
            FROM wallpapers AS w
            INNER JOIN image_resources AS original_resource
                ON original_resource.wallpaper_id = w.id
               AND original_resource.resource_type = ?
               AND original_resource.image_status = 'ready'
            LEFT JOIN image_resources AS thumbnail_resource
                ON thumbnail_resource.wallpaper_id = w.id
               AND thumbnail_resource.resource_type = ?
               AND thumbnail_resource.image_status = 'ready'
            WHERE {filters}
            ORDER BY w.wallpaper_date DESC, w.id DESC
            LIMIT ? OFFSET ?;
            """,
            (
                RESOURCE_TYPE_ORIGINAL,
                PUBLIC_LIST_RESOURCE_TYPE,
                *parameters,
                query.page_size,
                offset,
            ),
        ).fetchall()
        return list(items), total

    def get_visible_wallpaper_by_id(
        self, *, wallpaper_id: int, current_time_utc: str
    ) -> sqlite3.Row | None:
        return self._get_visible_wallpaper_detail(
            current_time_utc=current_time_utc,
            extra_clauses=["w.id = ?"],
            extra_parameters=(wallpaper_id,),
            order_by="w.id DESC",
        )

    def get_visible_wallpaper_for_today(
        self,
        *,
        current_time_utc: str,
        current_date: str,
        default_market_code: str,
    ) -> sqlite3.Row | None:
        return self._get_visible_wallpaper_detail(
            current_time_utc=current_time_utc,
            extra_clauses=["w.wallpaper_date = ?"],
            extra_parameters=(current_date, default_market_code),
            order_by="CASE WHEN w.market_code = ? THEN 0 ELSE 1 END ASC, w.id DESC",
        )

    def get_random_visible_wallpaper(self, *, current_time_utc: str) -> sqlite3.Row | None:
        return self._get_visible_wallpaper_detail(
            current_time_utc=current_time_utc,
            extra_clauses=[],
            extra_parameters=(),
            order_by="RANDOM()",
        )

    def _get_visible_wallpaper_detail(
        self,
        *,
        current_time_utc: str,
        extra_clauses: list[str],
        extra_parameters: tuple[str | int, ...],
        order_by: str,
    ) -> sqlite3.Row | None:
        filters, parameters = self._build_visibility_filters(
            query=PublicWallpaperListQuery(),
            current_time_utc=current_time_utc,
        )
        if extra_clauses:
            filters = f"{filters} AND {' AND '.join(extra_clauses)}"
        row = self.connection.execute(
            f"""
            SELECT
                w.id,
                w.title,
                w.subtitle,
                w.description,
                w.copyright_text,
                w.market_code,
                w.wallpaper_date,
                w.is_downloadable,
                w.source_name,
                COALESCE(preview_resource.relative_path, original_resource.relative_path)
                    AS preview_relative_path,
                COALESCE(preview_resource.storage_backend, original_resource.storage_backend)
                    AS preview_storage_backend,
                COALESCE(download_resource.relative_path, original_resource.relative_path)
                    AS download_relative_path,
                COALESCE(download_resource.storage_backend, original_resource.storage_backend)
                    AS download_storage_backend,
                COALESCE(download_resource.width, original_resource.width, w.origin_width) AS width,
                COALESCE(download_resource.height, original_resource.height, w.origin_height)
                    AS height
            FROM wallpapers AS w
            INNER JOIN image_resources AS original_resource
                ON original_resource.wallpaper_id = w.id
               AND original_resource.resource_type = ?
               AND original_resource.image_status = 'ready'
            LEFT JOIN image_resources AS preview_resource
                ON preview_resource.wallpaper_id = w.id
               AND preview_resource.resource_type = ?
               AND preview_resource.image_status = 'ready'
            LEFT JOIN image_resources AS download_resource
                ON download_resource.wallpaper_id = w.id
               AND download_resource.resource_type = ?
               AND download_resource.image_status = 'ready'
            WHERE {filters}
            ORDER BY {order_by}
            LIMIT 1;
            """,
            (
                RESOURCE_TYPE_ORIGINAL,
                PUBLIC_DETAIL_PREVIEW_RESOURCE_TYPE,
                PUBLIC_DETAIL_DOWNLOAD_RESOURCE_TYPE,
                *parameters,
                *extra_parameters,
            ),
        ).fetchone()
        return cast(sqlite3.Row | None, row)

    def list_visible_market_codes(self, *, current_time_utc: str) -> list[str]:
        filters, parameters = self._build_visibility_filters(
            query=PublicWallpaperListQuery(),
            current_time_utc=current_time_utc,
        )
        rows = self.connection.execute(
            f"""
            SELECT DISTINCT w.market_code
            FROM wallpapers AS w
            INNER JOIN image_resources AS original_resource
                ON original_resource.wallpaper_id = w.id
               AND original_resource.resource_type = ?
               AND original_resource.image_status = 'ready'
            WHERE {filters}
            ORDER BY w.market_code ASC;
            """,
            (RESOURCE_TYPE_ORIGINAL, *parameters),
        ).fetchall()
        return [str(row["market_code"]) for row in rows]

    def list_visible_tags(self, *, current_time_utc: str) -> list[sqlite3.Row]:
        filters, parameters = self._build_visibility_filters(
            query=PublicWallpaperListQuery(),
            current_time_utc=current_time_utc,
        )
        rows = self.connection.execute(
            f"""
            SELECT DISTINCT
                t.id,
                t.tag_key,
                t.tag_name,
                t.tag_category,
                t.sort_weight
            FROM tags AS t
            INNER JOIN wallpaper_tags AS wt ON wt.tag_id = t.id
            INNER JOIN wallpapers AS w ON w.id = wt.wallpaper_id
            INNER JOIN image_resources AS original_resource
                ON original_resource.wallpaper_id = w.id
               AND original_resource.resource_type = ?
               AND original_resource.image_status = 'ready'
            WHERE {filters}
              AND t.status = 'enabled'
            ORDER BY t.sort_weight DESC, t.tag_name ASC, t.id ASC;
            """,
            (RESOURCE_TYPE_ORIGINAL, *parameters),
        ).fetchall()
        return list(rows)

    def _build_visibility_filters(
        self, *, query: PublicWallpaperListQuery, current_time_utc: str
    ) -> tuple[str, tuple[str | int, ...]]:
        clauses = [
            "w.content_status = 'enabled'",
            "w.is_public = 1",
            "w.resource_status = 'ready'",
            "(w.publish_start_at_utc IS NULL OR w.publish_start_at_utc <= ?)",
            "(w.publish_end_at_utc IS NULL OR w.publish_end_at_utc >= ?)",
        ]
        parameters: list[str | int] = [current_time_utc, current_time_utc]
        if query.market_code is not None:
            clauses.append("w.market_code = ?")
            parameters.append(query.market_code)
        if query.resolution_min_width is not None:
            clauses.append("COALESCE(original_resource.width, w.origin_width, 0) >= ?")
            parameters.append(query.resolution_min_width)
        if query.resolution_min_height is not None:
            clauses.append("COALESCE(original_resource.height, w.origin_height, 0) >= ?")
            parameters.append(query.resolution_min_height)
        keyword_clauses, keyword_parameters = self._build_keyword_filter(query=query)
        clauses.extend(keyword_clauses)
        parameters.extend(keyword_parameters)
        tag_clauses, tag_parameters = self._build_tag_filter(query=query)
        clauses.extend(tag_clauses)
        parameters.extend(tag_parameters)
        return " AND ".join(clauses), tuple(parameters)

    def _build_keyword_filter(
        self, *, query: PublicWallpaperListQuery
    ) -> tuple[list[str], list[str]]:
        if query.keyword is None:
            return [], []
        keyword = _build_like_pattern(query.keyword)
        clauses = [
            """
            (
                w.title LIKE ? ESCAPE '\\' COLLATE NOCASE
                OR w.subtitle LIKE ? ESCAPE '\\' COLLATE NOCASE
                OR w.description LIKE ? ESCAPE '\\' COLLATE NOCASE
                OR w.copyright_text LIKE ? ESCAPE '\\' COLLATE NOCASE
                OR EXISTS (
                    SELECT 1
                    FROM wallpaper_tags AS wt_search
                    INNER JOIN tags AS t_search ON t_search.id = wt_search.tag_id
                    WHERE wt_search.wallpaper_id = w.id
                      AND t_search.status = 'enabled'
                      AND (
                          t_search.tag_key LIKE ? ESCAPE '\\' COLLATE NOCASE
                          OR t_search.tag_name LIKE ? ESCAPE '\\' COLLATE NOCASE
                      )
                )
            )
            """
        ]
        return clauses, [keyword, keyword, keyword, keyword, keyword, keyword]

    def _build_tag_filter(self, *, query: PublicWallpaperListQuery) -> tuple[list[str], list[str]]:
        tag_keys = _parse_tag_keys(query.tag_keys)
        if not tag_keys:
            return [], []

        clauses: list[str] = []
        parameters: list[str] = []
        for index, tag_key in enumerate(tag_keys):
            clauses.append(
                f"""
                EXISTS (
                    SELECT 1
                    FROM wallpaper_tags AS wt_{index}
                    INNER JOIN tags AS t_{index} ON t_{index}.id = wt_{index}.tag_id
                    WHERE wt_{index}.wallpaper_id = w.id
                      AND t_{index}.status = 'enabled'
                      AND t_{index}.tag_key = ?
                )
                """
            )
            parameters.append(tag_key)
        return clauses, parameters


def _parse_tag_keys(raw_value: str | None) -> list[str]:
    if raw_value is None:
        return []
    parts = [item.strip() for item in raw_value.split(",") if item.strip()]
    return list(dict.fromkeys(parts))


def _build_like_pattern(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"
