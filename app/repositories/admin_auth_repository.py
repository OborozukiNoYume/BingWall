from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import Any
from typing import cast

from app.repositories.sqlite import connect_sqlite


class AdminAuthRepository:
    def __init__(self, database_path: str | Path) -> None:
        self.connection = connect_sqlite(Path(database_path))
        self.connection.row_factory = sqlite3.Row

    def close(self) -> None:
        self.connection.close()

    def get_admin_user_by_username(self, *, username: str) -> sqlite3.Row | None:
        row = self.connection.execute(
            """
            SELECT id, username, password_hash, role_name, status
            FROM admin_users
            WHERE username = ?
            LIMIT 1;
            """,
            (username,),
        ).fetchone()
        return cast(sqlite3.Row | None, row)

    def create_session(
        self,
        *,
        admin_user_id: int,
        session_token_hash: str,
        session_version: int,
        issued_at_utc: str,
        expires_at_utc: str,
        client_ip: str | None,
        user_agent: str | None,
    ) -> int:
        with self.connection:
            cursor = self.connection.execute(
                """
                INSERT INTO admin_sessions (
                    admin_user_id,
                    session_token_hash,
                    session_version,
                    issued_at_utc,
                    expires_at_utc,
                    revoked_at_utc,
                    last_seen_at_utc,
                    client_ip,
                    user_agent,
                    created_at_utc,
                    updated_at_utc
                )
                VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?);
                """,
                (
                    admin_user_id,
                    session_token_hash,
                    session_version,
                    issued_at_utc,
                    expires_at_utc,
                    issued_at_utc,
                    client_ip,
                    user_agent,
                    issued_at_utc,
                    issued_at_utc,
                ),
            )
        session_id = cursor.lastrowid
        if session_id is None:
            raise RuntimeError("Failed to create admin session.")
        return int(session_id)

    def update_admin_last_login(self, *, admin_user_id: int, logged_in_at_utc: str) -> None:
        with self.connection:
            self.connection.execute(
                """
                UPDATE admin_users
                SET last_login_at_utc = ?, updated_at_utc = ?
                WHERE id = ?;
                """,
                (logged_in_at_utc, logged_in_at_utc, admin_user_id),
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

    def get_session_with_user(self, *, session_token_hash: str) -> sqlite3.Row | None:
        row = self.connection.execute(
            """
            SELECT
                s.id AS session_id,
                s.admin_user_id,
                s.session_version,
                s.issued_at_utc,
                s.expires_at_utc,
                s.revoked_at_utc,
                s.last_seen_at_utc,
                u.username,
                u.role_name,
                u.status
            FROM admin_sessions AS s
            INNER JOIN admin_users AS u ON u.id = s.admin_user_id
            WHERE s.session_token_hash = ?
            LIMIT 1;
            """,
            (session_token_hash,),
        ).fetchone()
        return cast(sqlite3.Row | None, row)

    def touch_session(self, *, session_id: int, seen_at_utc: str) -> None:
        with self.connection:
            self.connection.execute(
                """
                UPDATE admin_sessions
                SET last_seen_at_utc = ?, updated_at_utc = ?
                WHERE id = ?;
                """,
                (seen_at_utc, seen_at_utc, session_id),
            )

    def revoke_session(self, *, session_id: int, revoked_at_utc: str) -> None:
        with self.connection:
            self.connection.execute(
                """
                UPDATE admin_sessions
                SET revoked_at_utc = ?, updated_at_utc = ?
                WHERE id = ?
                  AND revoked_at_utc IS NULL;
                """,
                (revoked_at_utc, revoked_at_utc, session_id),
            )

    def fetch_value(self, query: str, parameters: tuple[Any, ...] = ()) -> Any:
        row = self.connection.execute(query, parameters).fetchone()
        if row is None:
            return None
        return row[0]
