from pathlib import Path
import sqlite3

from app.domain.collection import BingImageMetadata
from app.domain.collection import DownloadedImage
from app.repositories.collection_repository import CollectionRepository
from app.repositories.file_storage import FileStorage
from app.repositories.migrations import migrate_database
from app.services.bing_collection import BingCollectionService


class FakeBingClient:
    def __init__(
        self, *, metadata: list[BingImageMetadata], downloads: list[DownloadedImage]
    ) -> None:
        self.metadata = metadata
        self.downloads = downloads
        self.download_calls = 0

    def fetch_metadata(self, market_code: str, count: int) -> list[BingImageMetadata]:
        return self.metadata[:count]

    def download_image(self, image_url: str) -> DownloadedImage:
        item = self.downloads[self.download_calls]
        self.download_calls += 1
        return item


def test_bing_collection_service_persists_successful_collection(tmp_path: Path) -> None:
    service, database_path, storage = build_service(
        tmp_path=tmp_path,
        metadata=[
            make_metadata(
                market_code="en-US",
                wallpaper_date="2026-03-24",
                source_key="bing:en-US:2026-03-24:OHR.Success",
                source_url="https://www.bing.com/th?id=OHR.Success_1920x1080.jpg",
            )
        ],
        downloads=[DownloadedImage(content=JPEG_BYTES, mime_type="image/jpeg")],
    )

    try:
        summary = service.collect(
            market_code="en-US", count=1, trigger_type="manual", triggered_by="test"
        )
    finally:
        service.repository.close()

    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        wallpapers = connection.execute("SELECT * FROM wallpapers;").fetchall()
        resources = connection.execute("SELECT * FROM image_resources;").fetchall()
        tasks = connection.execute("SELECT * FROM collection_tasks;").fetchall()
        items = connection.execute("SELECT * FROM collection_task_items;").fetchall()
    finally:
        connection.close()

    assert summary.task_status == "succeeded"
    assert summary.success_count == 1
    assert summary.duplicate_count == 0
    assert summary.failure_count == 0
    assert len(wallpapers) == 1
    assert wallpapers[0]["resource_status"] == "ready"
    assert wallpapers[0]["content_status"] == "draft"
    assert len(resources) == 1
    assert resources[0]["image_status"] == "ready"
    assert resources[0]["file_size_bytes"] == len(JPEG_BYTES)
    assert len(tasks) == 1
    assert tasks[0]["task_status"] == "succeeded"
    assert len(items) == 1
    assert items[0]["result_status"] == "succeeded"
    public_files = list(storage.public_dir.rglob("*"))
    assert any(path.is_file() for path in public_files)


def test_bing_collection_service_skips_business_key_duplicates(tmp_path: Path) -> None:
    service, database_path, _storage = build_service(
        tmp_path=tmp_path,
        metadata=[
            make_metadata(
                market_code="en-US",
                wallpaper_date="2026-03-24",
                source_key="bing:en-US:2026-03-24:OHR.Duplicate",
                source_url="https://www.bing.com/th?id=OHR.Duplicate_1920x1080.jpg",
            )
        ],
        downloads=[DownloadedImage(content=JPEG_BYTES, mime_type="image/jpeg")],
    )

    try:
        first_summary = service.collect(
            market_code="en-US", count=1, trigger_type="manual", triggered_by=None
        )
        second_summary = service.collect(
            market_code="en-US", count=1, trigger_type="manual", triggered_by=None
        )
    finally:
        service.repository.close()

    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        wallpaper_count = connection.execute("SELECT COUNT(*) FROM wallpapers;").fetchone()[0]
        latest_task = connection.execute(
            "SELECT * FROM collection_tasks ORDER BY id DESC LIMIT 1;"
        ).fetchone()
        latest_item = connection.execute(
            "SELECT * FROM collection_task_items ORDER BY id DESC LIMIT 1;"
        ).fetchone()
    finally:
        connection.close()

    assert first_summary.success_count == 1
    assert second_summary.task_status == "succeeded"
    assert second_summary.duplicate_count == 1
    assert second_summary.success_count == 0
    assert wallpaper_count == 1
    assert latest_task["duplicate_count"] == 1
    assert latest_item["dedupe_hit_type"] == "business_key"


def test_bing_collection_service_marks_failed_after_retry_exhaustion(tmp_path: Path) -> None:
    service, database_path, storage = build_service(
        tmp_path=tmp_path,
        metadata=[
            make_metadata(
                market_code="en-US",
                wallpaper_date="2026-03-24",
                source_key="bing:en-US:2026-03-24:OHR.Failure",
                source_url="https://www.bing.com/th?id=OHR.Failure_1920x1080.jpg",
            )
        ],
        downloads=[
            DownloadedImage(content=b"", mime_type="image/jpeg"),
            DownloadedImage(content=b"", mime_type="image/jpeg"),
        ],
        max_download_retries=2,
    )

    try:
        summary = service.collect(
            market_code="en-US", count=1, trigger_type="manual", triggered_by=None
        )
    finally:
        service.repository.close()

    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        wallpaper = connection.execute("SELECT * FROM wallpapers LIMIT 1;").fetchone()
        resource = connection.execute("SELECT * FROM image_resources LIMIT 1;").fetchone()
        task = connection.execute("SELECT * FROM collection_tasks LIMIT 1;").fetchone()
        item = connection.execute("SELECT * FROM collection_task_items LIMIT 1;").fetchone()
    finally:
        connection.close()

    assert summary.task_status == "failed"
    assert summary.failure_count == 1
    assert wallpaper["resource_status"] == "failed"
    assert resource["image_status"] == "failed"
    assert "download attempt 2 failed" in resource["failure_reason"]
    assert task["failure_count"] == 1
    assert item["result_status"] == "failed"
    failed_files = [path for path in storage.failed_dir.rglob("*") if path.is_file()]
    assert len(failed_files) == 1


def test_bing_collection_service_skips_source_url_hash_duplicates(tmp_path: Path) -> None:
    duplicated_url = "https://www.bing.com/th?id=OHR.Shared_1920x1080.jpg"
    service, database_path, _storage = build_service(
        tmp_path=tmp_path,
        metadata=[
            make_metadata(
                market_code="en-US",
                wallpaper_date="2026-03-24",
                source_key="bing:en-US:2026-03-24:OHR.SharedA",
                source_url=duplicated_url,
            ),
            make_metadata(
                market_code="fr-FR",
                wallpaper_date="2026-03-25",
                source_key="bing:fr-FR:2026-03-25:OHR.SharedB",
                source_url=duplicated_url,
            ),
        ],
        downloads=[DownloadedImage(content=JPEG_BYTES, mime_type="image/jpeg")],
    )

    try:
        summary = service.collect(
            market_code="en-US", count=2, trigger_type="manual", triggered_by=None
        )
    finally:
        service.repository.close()

    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        wallpaper_count = connection.execute("SELECT COUNT(*) FROM wallpapers;").fetchone()[0]
        latest_item = connection.execute(
            "SELECT * FROM collection_task_items ORDER BY id DESC LIMIT 1;"
        ).fetchone()
    finally:
        connection.close()

    assert summary.success_count == 1
    assert summary.duplicate_count == 1
    assert wallpaper_count == 1
    assert latest_item["dedupe_hit_type"] == "source_url_hash"


def build_service(
    *,
    tmp_path: Path,
    metadata: list[BingImageMetadata],
    downloads: list[DownloadedImage],
    max_download_retries: int = 2,
) -> tuple[BingCollectionService, Path, FileStorage]:
    database_path = tmp_path / "bingwall.sqlite3"
    migrate_database(database_path)
    repository = CollectionRepository(str(database_path))
    storage = FileStorage(
        tmp_dir=tmp_path / "images" / "tmp",
        public_dir=tmp_path / "images" / "public",
        failed_dir=tmp_path / "images" / "failed",
    )
    service = BingCollectionService(
        repository=repository,
        storage=storage,
        bing_client=FakeBingClient(metadata=metadata, downloads=downloads),
        max_download_retries=max_download_retries,
    )
    return service, database_path, storage


def make_metadata(
    *,
    market_code: str,
    wallpaper_date: str,
    source_key: str,
    source_url: str,
) -> BingImageMetadata:
    from datetime import date
    import hashlib
    import json

    return BingImageMetadata(
        market_code=market_code,
        wallpaper_date=date.fromisoformat(wallpaper_date),
        source_key=source_key,
        title="Test title",
        copyright_text="Test copyright",
        origin_page_url="https://www.bing.com/example",
        origin_image_url=source_url,
        source_url_hash=hashlib.sha256(source_url.encode("utf-8")).hexdigest(),
        is_downloadable=True,
        source_name="Bing",
        origin_width=1920,
        origin_height=1080,
        raw_extra_json=json.dumps({"source_key": source_key}, ensure_ascii=True),
    )


JPEG_BYTES = b"\xff\xd8\xff\xdbfake-jpeg-bytes"
