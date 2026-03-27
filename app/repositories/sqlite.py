from pathlib import Path
import sqlite3


def connect_sqlite(database_path: Path) -> sqlite3.Connection:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    # FastAPI may create the repository in one worker thread and execute the
    # actual sync endpoint logic in another thread within the same request.
    connection = sqlite3.connect(database_path, check_same_thread=False)
    connection.execute("PRAGMA foreign_keys = ON;")
    return connection
