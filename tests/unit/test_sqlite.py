from pathlib import Path
import threading

from app.repositories.sqlite import connect_sqlite


def test_connect_sqlite_allows_request_scope_cross_thread_usage(tmp_path: Path) -> None:
    database_path = tmp_path / "threadsafe.sqlite3"
    connection = connect_sqlite(database_path)
    try:
        connection.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
        connection.execute("INSERT INTO sample (value) VALUES (?)", ("ok",))
        connection.commit()

        errors: list[BaseException] = []
        results: list[str] = []

        def run_query() -> None:
            try:
                row = connection.execute("SELECT value FROM sample WHERE id = 1").fetchone()
                if row is not None:
                    results.append(str(row[0]))
            except BaseException as exc:  # pragma: no cover - used to surface thread errors
                errors.append(exc)

        thread = threading.Thread(target=run_query)
        thread.start()
        thread.join(timeout=5)

        assert not thread.is_alive()
        assert errors == []
        assert results == ["ok"]
    finally:
        connection.close()


def test_connect_sqlite_enables_foreign_keys(tmp_path: Path) -> None:
    database_path = tmp_path / "foreign-keys.sqlite3"
    connection = connect_sqlite(database_path)
    try:
        pragma_row = connection.execute("PRAGMA foreign_keys;").fetchone()
        assert pragma_row is not None
        assert int(pragma_row[0]) == 1
    finally:
        connection.close()
