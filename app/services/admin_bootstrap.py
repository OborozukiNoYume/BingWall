from __future__ import annotations

from datetime import UTC
from datetime import datetime
import logging
from pathlib import Path

from app.core.security import hash_password
from app.repositories.sqlite import connect_sqlite

logger = logging.getLogger(__name__)


def ensure_bootstrap_admin_user(
    *,
    database_path: Path,
    username: str | None,
    password: str | None,
) -> bool:
    normalized_username = _normalize_optional_value(username)
    normalized_password = _normalize_optional_value(password)
    if normalized_username is None or normalized_password is None:
        return False

    connection = connect_sqlite(database_path)
    try:
        row = connection.execute("SELECT COUNT(*) FROM admin_users;").fetchone()
        existing_admin_count = 0 if row is None else int(row[0])
        if existing_admin_count > 0:
            logger.info(
                "Bootstrap admin creation skipped because admin_users is not empty: count=%s",
                existing_admin_count,
            )
            return False

        now_utc = _utc_now_isoformat()
        with connection:
            connection.execute(
                """
                INSERT INTO admin_users (
                    username,
                    password_hash,
                    role_name,
                    status,
                    last_login_at_utc,
                    created_at_utc,
                    updated_at_utc
                )
                VALUES (?, ?, 'super_admin', 'enabled', NULL, ?, ?);
                """,
                (
                    normalized_username,
                    hash_password(normalized_password),
                    now_utc,
                    now_utc,
                ),
            )
        logger.info("Bootstrap admin user created: username=%s", normalized_username)
        return True
    finally:
        connection.close()


def _normalize_optional_value(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    return normalized


def _utc_now_isoformat() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
