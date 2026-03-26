from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import cast

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
            INNER JOIN image_resources AS r ON r.id = w.default_resource_id
            WHERE {filters};
            """,
            parameters,
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
                r.relative_path,
                COALESCE(r.width, w.origin_width) AS width,
                COALESCE(r.height, w.origin_height) AS height
            FROM wallpapers AS w
            INNER JOIN image_resources AS r ON r.id = w.default_resource_id
            WHERE {filters}
            ORDER BY w.wallpaper_date DESC, w.id DESC
            LIMIT ? OFFSET ?;
            """,
            (*parameters, query.page_size, offset),
        ).fetchall()
        return list(items), total

    def get_visible_wallpaper_by_id(
        self, *, wallpaper_id: int, current_time_utc: str
    ) -> sqlite3.Row | None:
        filters, parameters = self._build_visibility_filters(
            query=PublicWallpaperListQuery(),
            current_time_utc=current_time_utc,
        )
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
                r.relative_path,
                COALESCE(r.width, w.origin_width) AS width,
                COALESCE(r.height, w.origin_height) AS height
            FROM wallpapers AS w
            INNER JOIN image_resources AS r ON r.id = w.default_resource_id
            WHERE {filters}
              AND w.id = ?
            LIMIT 1;
            """,
            (*parameters, wallpaper_id),
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
            INNER JOIN image_resources AS r ON r.id = w.default_resource_id
            WHERE {filters}
            ORDER BY w.market_code ASC;
            """,
            parameters,
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
            INNER JOIN image_resources AS r ON r.id = w.default_resource_id
            WHERE {filters}
              AND t.status = 'enabled'
            ORDER BY t.sort_weight DESC, t.tag_name ASC, t.id ASC;
            """,
            parameters,
        ).fetchall()
        return list(rows)

    def _build_visibility_filters(
        self, *, query: PublicWallpaperListQuery, current_time_utc: str
    ) -> tuple[str, tuple[str | int, ...]]:
        clauses = [
            "w.content_status = 'enabled'",
            "w.is_public = 1",
            "w.resource_status = 'ready'",
            "r.image_status = 'ready'",
            "(w.publish_start_at_utc IS NULL OR w.publish_start_at_utc <= ?)",
            "(w.publish_end_at_utc IS NULL OR w.publish_end_at_utc >= ?)",
        ]
        parameters: list[str | int] = [current_time_utc, current_time_utc]
        if query.market_code is not None:
            clauses.append("w.market_code = ?")
            parameters.append(query.market_code)
        if query.resolution_min_width is not None:
            clauses.append("COALESCE(r.width, w.origin_width, 0) >= ?")
            parameters.append(query.resolution_min_width)
        if query.resolution_min_height is not None:
            clauses.append("COALESCE(r.height, w.origin_height, 0) >= ?")
            parameters.append(query.resolution_min_height)
        tag_clauses, tag_parameters = self._build_tag_filter(query=query)
        clauses.extend(tag_clauses)
        parameters.extend(tag_parameters)
        return " AND ".join(clauses), tuple(parameters)

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
