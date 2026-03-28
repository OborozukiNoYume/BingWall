from __future__ import annotations

from datetime import UTC
from datetime import datetime
from pathlib import Path
import sqlite3
from typing import cast

from app.repositories.sqlite import connect_sqlite
from app.schemas.admin_collection import AdminCollectionLogListQuery
from app.schemas.admin_collection import AdminCollectionTaskListQuery


class AdminCollectionRepository:
    def __init__(self, database_path: str | Path) -> None:
        self.connection = connect_sqlite(Path(database_path))
        self.connection.row_factory = sqlite3.Row

    def close(self) -> None:
        self.connection.close()

    def create_queued_task(
        self,
        *,
        task_type: str,
        source_type: str,
        trigger_type: str,
        triggered_by: str | None,
        request_snapshot_json: str,
        retry_of_task_id: int | None,
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
                finished_at_utc,
                success_count,
                duplicate_count,
                failure_count,
                error_summary,
                retry_of_task_id,
                created_at_utc,
                updated_at_utc
            )
            VALUES (?, ?, ?, ?, 'queued', ?, NULL, NULL, 0, 0, 0, NULL, ?, ?, ?);
            """,
            (
                task_type,
                source_type,
                trigger_type,
                triggered_by,
                request_snapshot_json,
                retry_of_task_id,
                created_at_utc,
                created_at_utc,
            ),
        )
        self.connection.commit()
        lastrowid = cursor.lastrowid
        if lastrowid is None:
            raise RuntimeError("Failed to create queued collection task.")
        return int(lastrowid)

    def get_task(self, *, task_id: int) -> sqlite3.Row | None:
        row = self.connection.execute(
            """
            SELECT
                id,
                task_type,
                source_type,
                trigger_type,
                triggered_by,
                task_status,
                request_snapshot_json,
                started_at_utc,
                finished_at_utc,
                success_count,
                duplicate_count,
                failure_count,
                error_summary,
                retry_of_task_id,
                created_at_utc,
                updated_at_utc
            FROM collection_tasks
            WHERE id = ?
            LIMIT 1;
            """,
            (task_id,),
        ).fetchone()
        return cast(sqlite3.Row | None, row)

    def list_tasks(self, *, query: AdminCollectionTaskListQuery) -> tuple[list[sqlite3.Row], int]:
        filters, parameters = self._build_task_filters(query=query)
        count_row = self.connection.execute(
            f"""
            SELECT COUNT(*)
            FROM collection_tasks
            WHERE {filters};
            """,
            parameters,
        ).fetchone()
        total = int(count_row[0]) if count_row is not None else 0
        offset = (query.page - 1) * query.page_size
        rows = self.connection.execute(
            f"""
            SELECT
                id,
                task_type,
                source_type,
                trigger_type,
                triggered_by,
                task_status,
                request_snapshot_json,
                started_at_utc,
                finished_at_utc,
                success_count,
                duplicate_count,
                failure_count,
                error_summary,
                retry_of_task_id,
                created_at_utc,
                updated_at_utc
            FROM collection_tasks
            WHERE {filters}
            ORDER BY created_at_utc DESC, id DESC
            LIMIT ? OFFSET ?;
            """,
            (*parameters, query.page_size, offset),
        ).fetchall()
        return list(rows), total

    def list_task_items(self, *, task_id: int, limit: int = 200) -> list[sqlite3.Row]:
        rows = self.connection.execute(
            """
            SELECT
                id,
                source_item_key,
                action_name,
                result_status,
                dedupe_hit_type,
                db_write_result,
                file_write_result,
                failure_reason,
                occurred_at_utc
            FROM collection_task_items
            WHERE task_id = ?
            ORDER BY occurred_at_utc DESC, id DESC
            LIMIT ?;
            """,
            (task_id, limit),
        ).fetchall()
        return list(rows)

    def list_recent_tasks_for_source(
        self,
        *,
        source_type: str,
        trigger_type: str,
        limit: int = 20,
    ) -> list[sqlite3.Row]:
        rows = self.connection.execute(
            """
            SELECT
                id,
                task_type,
                source_type,
                trigger_type,
                task_status,
                request_snapshot_json,
                created_at_utc
            FROM collection_tasks
            WHERE source_type = ?
              AND trigger_type = ?
            ORDER BY created_at_utc DESC, id DESC
            LIMIT ?;
            """,
            (source_type, trigger_type, limit),
        ).fetchall()
        return list(rows)

    def list_logs(self, *, query: AdminCollectionLogListQuery) -> tuple[list[sqlite3.Row], int]:
        filters, parameters = self._build_log_filters(query=query)
        count_row = self.connection.execute(
            f"""
            SELECT COUNT(*)
            FROM collection_task_items AS i
            INNER JOIN collection_tasks AS t ON t.id = i.task_id
            WHERE {filters};
            """,
            parameters,
        ).fetchone()
        total = int(count_row[0]) if count_row is not None else 0
        offset = (query.page - 1) * query.page_size
        rows = self.connection.execute(
            f"""
            SELECT
                i.id,
                i.task_id,
                i.source_item_key,
                i.action_name,
                i.result_status,
                i.dedupe_hit_type,
                i.db_write_result,
                i.file_write_result,
                i.failure_reason,
                i.occurred_at_utc,
                t.task_status,
                t.source_type,
                t.trigger_type
            FROM collection_task_items AS i
            INNER JOIN collection_tasks AS t ON t.id = i.task_id
            WHERE {filters}
            ORDER BY i.occurred_at_utc DESC, i.id DESC
            LIMIT ? OFFSET ?;
            """,
            (*parameters, query.page_size, offset),
        ).fetchall()
        return list(rows), total

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

    def _build_task_filters(
        self, *, query: AdminCollectionTaskListQuery
    ) -> tuple[str, tuple[str, ...]]:
        clauses = ["1 = 1"]
        parameters: list[str] = []
        if query.task_status is not None:
            clauses.append("task_status = ?")
            parameters.append(query.task_status)
        if query.trigger_type is not None:
            clauses.append("trigger_type = ?")
            parameters.append(query.trigger_type)
        if query.source_type is not None:
            clauses.append("source_type = ?")
            parameters.append(query.source_type)
        if query.created_from_utc is not None:
            clauses.append("created_at_utc >= ?")
            parameters.append(datetime_to_utc_string(query.created_from_utc))
        if query.created_to_utc is not None:
            clauses.append("created_at_utc <= ?")
            parameters.append(datetime_to_utc_string(query.created_to_utc))
        return " AND ".join(clauses), tuple(parameters)

    def _build_log_filters(
        self, *, query: AdminCollectionLogListQuery
    ) -> tuple[str, tuple[str | int, ...]]:
        clauses = ["1 = 1"]
        parameters: list[str | int] = []
        if query.task_id is not None:
            clauses.append("i.task_id = ?")
            parameters.append(query.task_id)
        if query.error_type is not None:
            clauses.append(
                "("
                "i.result_status = ? OR "
                "i.action_name = ? OR "
                "COALESCE(i.dedupe_hit_type, '') = ? OR "
                "COALESCE(i.db_write_result, '') = ? OR "
                "COALESCE(i.file_write_result, '') = ?"
                ")"
            )
            parameters.extend([query.error_type] * 5)
        if query.started_from_utc is not None:
            clauses.append("i.occurred_at_utc >= ?")
            parameters.append(datetime_to_utc_string(query.started_from_utc))
        if query.started_to_utc is not None:
            clauses.append("i.occurred_at_utc <= ?")
            parameters.append(datetime_to_utc_string(query.started_to_utc))
        return " AND ".join(clauses), tuple(parameters)


def datetime_to_utc_string(value: datetime) -> str:
    normalized = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return normalized.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
