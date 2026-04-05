from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import Any
from typing import cast

from app.repositories.collection_repository_models import ResourceCreateInput
from app.repositories.collection_repository_models import TaskItemCreateInput
from app.repositories.collection_repository_models import WallpaperCreateInput
from app.repositories.collection_repository_models import WallpaperLocalizationUpsertInput
from app.repositories.collection_repository_resources import CollectionRepositoryResourceMixin
from app.repositories.collection_repository_tasks import CollectionRepositoryTaskMixin
from app.repositories.collection_repository_wallpapers import CollectionRepositoryWallpaperMixin
from app.repositories.sqlite import connect_sqlite


class CollectionRepository(
    CollectionRepositoryTaskMixin,
    CollectionRepositoryWallpaperMixin,
    CollectionRepositoryResourceMixin,
):
    def __init__(self, database_path: str | Path) -> None:
        self.connection = connect_sqlite(Path(database_path))
        self.connection.row_factory = sqlite3.Row

    def close(self) -> None:
        self.connection.close()

    def fetch_one(self, query: str, parameters: tuple[Any, ...] = ()) -> sqlite3.Row | None:
        row = self.connection.execute(query, parameters).fetchone()
        return cast(sqlite3.Row | None, row)

    def fetch_all(self, query: str, parameters: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        return list(self.connection.execute(query, parameters).fetchall())


__all__ = [
    "CollectionRepository",
    "ResourceCreateInput",
    "TaskItemCreateInput",
    "WallpaperCreateInput",
    "WallpaperLocalizationUpsertInput",
]
