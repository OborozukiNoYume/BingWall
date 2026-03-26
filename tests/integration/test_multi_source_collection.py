from __future__ import annotations

from pathlib import Path
import sqlite3

from app.collectors.nasa_apod import NasaApodSourceAdapter
from app.domain.collection import CollectedImageMetadata
from app.domain.collection import DownloadedImage
from app.repositories.collection_repository import CollectionRepository
from app.repositories.file_storage import FileStorage
from app.repositories.migrations import migrate_database
from app.services.source_collection import SourceCollectionService
from tests.support.image_factory import build_test_jpeg_bytes

JPEG_BYTES = build_test_jpeg_bytes()


class FakeNasaApodClient:
    def __init__(
        self,
        *,
        metadata: list[CollectedImageMetadata],
        downloads: list[DownloadedImage],
    ) -> None:
        self.metadata = metadata
        self.downloads = downloads
        self.download_calls = 0

    def fetch_metadata(
        self,
        *,
        market_code: str,
        count: int,
        date_from: object,
        date_to: object,
    ) -> list[CollectedImageMetadata]:
        del market_code
        del date_from
        del date_to
        return self.metadata[:count]

    def download_image(self, image_url: str) -> DownloadedImage:
        del image_url
        item = self.downloads[self.download_calls]
        self.download_calls += 1
        return item


def test_nasa_apod_collection_persists_source_specific_records(tmp_path: Path) -> None:
    database_path = tmp_path / "bingwall.sqlite3"
    migrate_database(database_path)
    repository = CollectionRepository(str(database_path))
    storage = FileStorage(
        tmp_dir=tmp_path / "images" / "tmp",
        public_dir=tmp_path / "images" / "public",
        failed_dir=tmp_path / "images" / "failed",
    )
    service = SourceCollectionService(
        repository=repository,
        storage=storage,
        adapter=NasaApodSourceAdapter(
            client=FakeNasaApodClient(
                metadata=[
                    make_nasa_metadata(
                        wallpaper_date="2026-03-24",
                        source_key="nasa_apod:global:2026-03-24:moonrise",
                        source_url="https://apod.nasa.gov/apod/image/2603/moonrise.jpg",
                    )
                ],
                downloads=[DownloadedImage(content=JPEG_BYTES, mime_type="image/jpeg")],
            )
        ),
        max_download_retries=2,
    )

    try:
        summary = service.collect(
            market_code="global",
            count=1,
            trigger_type="manual",
            triggered_by="pytest",
        )
    finally:
        repository.close()

    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        wallpaper = connection.execute("SELECT * FROM wallpapers LIMIT 1;").fetchone()
        resources = connection.execute("SELECT * FROM image_resources ORDER BY id ASC;").fetchall()
        task = connection.execute("SELECT * FROM collection_tasks LIMIT 1;").fetchone()
        item = connection.execute("SELECT * FROM collection_task_items LIMIT 1;").fetchone()
    finally:
        connection.close()

    assert summary.task_status == "succeeded"
    assert summary.success_count == 1
    assert wallpaper is not None
    assert wallpaper["source_type"] == "nasa_apod"
    assert wallpaper["market_code"] == "global"
    assert wallpaper["source_name"] == "NASA APOD"
    assert len(resources) == 4
    assert all(str(resource["relative_path"]).startswith("nasa_apod/") for resource in resources)
    assert all(resource["image_status"] == "ready" for resource in resources)
    assert task is not None
    assert task["source_type"] == "nasa_apod"
    assert item is not None
    assert item["action_name"] == "collect_candidate"
    assert item["result_status"] == "succeeded"


def make_nasa_metadata(
    *,
    wallpaper_date: str,
    source_key: str,
    source_url: str,
) -> CollectedImageMetadata:
    from datetime import date
    import hashlib
    import json

    return CollectedImageMetadata(
        market_code="global",
        wallpaper_date=date.fromisoformat(wallpaper_date),
        source_key=source_key,
        title="Moonrise",
        copyright_text="NASA",
        origin_page_url=None,
        origin_image_url=source_url,
        source_url_hash=hashlib.sha256(source_url.encode("utf-8")).hexdigest(),
        is_downloadable=True,
        source_name="NASA APOD",
        origin_width=None,
        origin_height=None,
        raw_extra_json=json.dumps({"source_key": source_key}, ensure_ascii=True),
    )
