from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from pathlib import Path
import sqlite3

from app.repositories.sqlite import connect_sqlite

MIGRATIONS_DIR = Path(__file__).resolve().parent / "versions"


@dataclass(frozen=True, slots=True)
class MigrationScript:
    version: int
    name: str
    path: Path


def discover_migration_scripts() -> list[MigrationScript]:
    scripts: list[MigrationScript] = []
    for path in sorted(MIGRATIONS_DIR.glob("V*.sql")):
        prefix, separator, name = path.stem.partition("__")
        if separator != "__" or not prefix.startswith("V"):
            msg = f"Invalid migration filename: {path.name}"
            raise ValueError(msg)
        version = int(prefix[1:])
        scripts.append(MigrationScript(version=version, name=name, path=path))

    versions = [script.version for script in scripts]
    if len(versions) != len(set(versions)):
        msg = "Duplicate migration versions discovered."
        raise ValueError(msg)

    return scripts


def migrate_database(database_path: Path) -> list[MigrationScript]:
    applied_migrations: list[MigrationScript] = []
    connection = connect_sqlite(database_path)

    try:
        _ensure_schema_migrations_table(connection)
        applied_versions = _get_applied_versions(connection)

        for migration in discover_migration_scripts():
            if migration.version in applied_versions:
                continue

            with connection:
                connection.executescript(migration.path.read_text(encoding="utf-8"))
                connection.execute(
                    """
                    INSERT INTO schema_migrations (version, name, applied_at_utc)
                    VALUES (?, ?, ?);
                    """,
                    (migration.version, migration.name, _utc_now_isoformat()),
                )
            applied_migrations.append(migration)

        return applied_migrations
    finally:
        connection.close()


def _ensure_schema_migrations_table(connection: sqlite3.Connection) -> None:
    with connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at_utc TEXT NOT NULL
            );
            """
        )


def _get_applied_versions(connection: sqlite3.Connection) -> set[int]:
    rows = connection.execute("SELECT version FROM schema_migrations;").fetchall()
    return {int(row[0]) for row in rows}


def _utc_now_isoformat() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
