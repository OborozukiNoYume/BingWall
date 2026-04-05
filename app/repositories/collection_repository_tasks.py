from __future__ import annotations

import sqlite3
from typing import cast

from app.repositories.collection_repository_models import TaskItemCreateInput


class CollectionRepositoryTaskMixin:
    connection: sqlite3.Connection

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
