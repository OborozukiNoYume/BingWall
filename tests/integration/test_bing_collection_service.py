from pathlib import Path
import sqlite3
from typing import Sequence

from _pytest.monkeypatch import MonkeyPatch

from app.collectors.bing import BingImageDownloadError
from app.domain.collection import BingImageMetadata
from app.domain.collection import CollectedDownloadVariant
from app.domain.collection import DownloadedImage
from app.repositories.collection_repository import CollectionRepository
from app.repositories.file_storage import FileStorage
from app.repositories.migrations import migrate_database
from app.services.bing_collection import BingCollectionService
from tests.support.image_factory import build_test_jpeg_bytes


class FakeBingClient:
    def __init__(
        self,
        *,
        metadata: list[BingImageMetadata],
        downloads: Sequence[DownloadedImage | Exception],
    ) -> None:
        self.metadata = metadata
        self.downloads = list(downloads)
        self.download_calls = 0
        self.requested_urls: list[str] = []

    def fetch_metadata(self, market_code: str, count: int) -> list[BingImageMetadata]:
        return self.metadata[:count]

    def download_image(self, image_url: str) -> DownloadedImage:
        self.requested_urls.append(image_url)
        item = self.downloads[self.download_calls]
        self.download_calls += 1
        if isinstance(item, Exception):
            raise item
        return item


def test_bing_collection_service_persists_successful_collection(tmp_path: Path) -> None:
    service, database_path, storage = build_service(
        tmp_path=tmp_path,
        metadata=[
            make_metadata(
                market_code="en-US",
                wallpaper_date="2026-03-24",
                source_key="bing:en-US:2026-03-24:OHR.Success",
                source_url="https://www.bing.com/th?id=OHR.Success_1920x1080.jpg&pid=hp",
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
    assert wallpapers[0]["content_status"] == "enabled"
    assert wallpapers[0]["is_public"] == 1
    assert wallpapers[0]["subtitle"] == "Test subtitle"
    assert wallpapers[0]["description"] == "Test description"
    assert wallpapers[0]["location_text"] == "Test location"
    assert wallpapers[0]["published_at_utc"] == "2026-03-24T16:00:00Z"
    assert (
        wallpapers[0]["portrait_image_url"]
        == "https://www.bing.com/th?id=OHR.Success_720x1280.jpg&pid=hp"
    )
    assert len(resources) == 4
    assert {str(resource["resource_type"]) for resource in resources} == {
        "original",
        "thumbnail",
        "preview",
        "download",
    }
    assert {str(resource["relative_path"]) for resource in resources} == {
        "bing/2026/03/24_en-US_1920x1080.jpg",
        "bing/2026/03/24_en-US_thumbnail_480x270.jpg",
        "bing/2026/03/24_en-US_preview_1600x900.jpg",
        "bing/2026/03/24_en-US_download_1920x1080.jpg",
    }
    assert all(str(resource["image_status"]) == "ready" for resource in resources)
    original_resource = next(
        resource for resource in resources if str(resource["resource_type"]) == "original"
    )
    assert original_resource["file_size_bytes"] == len(JPEG_BYTES)
    assert len(tasks) == 1
    assert tasks[0]["task_status"] == "succeeded"
    assert len(items) == 1
    assert items[0]["result_status"] == "succeeded"
    public_files = list(storage.public_dir.rglob("*"))
    assert any(path.is_file() for path in public_files)
    assert len([path for path in public_files if path.is_file()]) == 4
    assert all(path.suffix == ".jpg" for path in public_files if path.is_file())
    assert (
        '"portrait_image_url": "https://www.bing.com/th?id=OHR.Success_720x1280.jpg&pid=hp"'
        in str(wallpapers[0]["raw_extra_json"])
    )


def test_bing_collection_service_persists_all_available_bing_download_resolutions(
    tmp_path: Path,
) -> None:
    uhd_url = "https://www.bing.com/th?id=OHR.Success_UHD.jpg&pid=hp"
    hd_url = "https://www.bing.com/th?id=OHR.Success_1920x1080.jpg&pid=hp"
    mobile_url = "https://www.bing.com/th?id=OHR.Success_480x800.jpg&pid=hp"
    service, database_path, _storage = build_service(
        tmp_path=tmp_path,
        metadata=[
            make_metadata(
                market_code="en-US",
                wallpaper_date="2026-03-24",
                source_key="bing:en-US:2026-03-24:OHR.SuccessAll",
                source_url=hd_url,
                download_variants=(
                    CollectedDownloadVariant(
                        variant_key="UHD",
                        source_url=uhd_url,
                        width=3840,
                        height=2160,
                    ),
                    CollectedDownloadVariant(
                        variant_key="1920x1080",
                        source_url=hd_url,
                        width=1920,
                        height=1080,
                    ),
                    CollectedDownloadVariant(
                        variant_key="480x800",
                        source_url=mobile_url,
                        width=480,
                        height=800,
                    ),
                ),
            )
        ],
        downloads=[
            DownloadedImage(
                content=build_test_jpeg_bytes(width=3840, height=2160), mime_type="image/jpeg"
            ),
            DownloadedImage(content=JPEG_BYTES, mime_type="image/jpeg"),
            DownloadedImage(
                content=build_test_jpeg_bytes(width=480, height=800), mime_type="image/jpeg"
            ),
        ],
    )

    fake_client = getattr(service.delegate.adapter, "client")

    try:
        summary = service.collect(
            market_code="en-US", count=1, trigger_type="manual", triggered_by="test"
        )
    finally:
        service.repository.close()

    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        wallpaper = connection.execute("SELECT * FROM wallpapers LIMIT 1;").fetchone()
        download_rows = connection.execute(
            """
            SELECT variant_key, width, height, source_url
            FROM image_resources
            WHERE resource_type = 'download'
            ORDER BY width DESC, height DESC, id ASC;
            """
        ).fetchall()
        stored_download_paths = connection.execute(
            """
            SELECT relative_path
            FROM image_resources
            WHERE resource_type = 'download'
            ORDER BY width DESC, height DESC, id ASC;
            """
        ).fetchall()
    finally:
        connection.close()

    assert summary.task_status == "succeeded"
    assert wallpaper is not None
    assert wallpaper["origin_image_url"] == uhd_url
    assert wallpaper["origin_width"] == 3840
    assert wallpaper["origin_height"] == 2160
    assert fake_client.requested_urls == [uhd_url, hd_url, mobile_url]
    assert [
        (str(row["variant_key"]), int(row["width"]), int(row["height"]), str(row["source_url"]))
        for row in download_rows
    ] == [
        ("UHD", 3840, 2160, uhd_url),
        ("1920x1080", 1920, 1080, hd_url),
        ("480x800", 480, 800, mobile_url),
    ]
    assert [str(row["relative_path"]) for row in stored_download_paths] == [
        "bing/2026/03/24_en-US_download_3840x2160.jpg",
        "bing/2026/03/24_en-US_download_1920x1080.jpg",
        "bing/2026/03/24_en-US_download_480x800.jpg",
    ]


def test_bing_collection_service_skips_missing_download_resolution_without_failing_wallpaper(
    tmp_path: Path,
) -> None:
    missing_url = "https://www.bing.com/th?id=OHR.Success_UHD.jpg&pid=hp"
    hd_url = "https://www.bing.com/th?id=OHR.Success_1920x1080.jpg&pid=hp"
    service, database_path, _storage = build_service(
        tmp_path=tmp_path,
        metadata=[
            make_metadata(
                market_code="en-US",
                wallpaper_date="2026-03-24",
                source_key="bing:en-US:2026-03-24:OHR.SkipMissing",
                source_url=hd_url,
                download_variants=(
                    CollectedDownloadVariant(
                        variant_key="UHD",
                        source_url=missing_url,
                        width=3840,
                        height=2160,
                    ),
                    CollectedDownloadVariant(
                        variant_key="1920x1080",
                        source_url=hd_url,
                        width=1920,
                        height=1080,
                    ),
                ),
            )
        ],
        downloads=[
            BingImageDownloadError(
                "image request failed with HTTP 404: missing",
                status_code=404,
            ),
            DownloadedImage(content=JPEG_BYTES, mime_type="image/jpeg"),
        ],
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
        wallpaper = connection.execute("SELECT * FROM wallpapers LIMIT 1;").fetchone()
        download_count = connection.execute(
            "SELECT COUNT(*) FROM image_resources WHERE resource_type = 'download';"
        ).fetchone()[0]
    finally:
        connection.close()

    assert summary.task_status == "succeeded"
    assert wallpaper is not None
    assert wallpaper["origin_image_url"] == hd_url
    assert download_count == 1


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


def test_bing_collection_service_repairs_existing_wallpaper_without_resources(
    tmp_path: Path,
) -> None:
    service, database_path, storage = build_service(
        tmp_path=tmp_path,
        metadata=[
            make_metadata(
                market_code="en-US",
                wallpaper_date="2026-03-24",
                source_key="bing:en-US:2026-03-24:OHR.Resume",
                source_url="https://www.bing.com/th?id=OHR.Resume_1920x1080.jpg&pid=hp",
            )
        ],
        downloads=[DownloadedImage(content=JPEG_BYTES, mime_type="image/jpeg")],
    )

    connection = sqlite3.connect(database_path)
    try:
        connection.execute(
            """
            INSERT INTO wallpapers (
                source_type,
                source_key,
                market_code,
                wallpaper_date,
                title,
                copyright_text,
                source_name,
                is_public,
                is_downloadable,
                origin_page_url,
                origin_image_url,
                origin_width,
                origin_height,
                resource_status,
                raw_extra_json,
                created_at_utc,
                updated_at_utc
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, 1, ?, ?, ?, ?, 'pending', ?, ?, ?);
            """,
            (
                "bing",
                "bing:en-US:2026-03-24:OHR.Resume",
                "en-US",
                "2026-03-24",
                "Test title",
                "Test copyright",
                "Bing",
                "https://www.bing.com/example",
                "https://www.bing.com/th?id=OHR.Resume_1920x1080.jpg&pid=hp",
                1920,
                1080,
                '{"source_key":"bing:en-US:2026-03-24:OHR.Resume"}',
                "2026-03-24T00:00:00Z",
                "2026-03-24T00:00:00Z",
            ),
        )
        connection.commit()
    finally:
        connection.close()

    try:
        summary = service.collect(
            market_code="en-US", count=1, trigger_type="manual", triggered_by=None
        )
    finally:
        service.repository.close()

    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        wallpaper_count = connection.execute("SELECT COUNT(*) FROM wallpapers;").fetchone()[0]
        wallpaper = connection.execute("SELECT * FROM wallpapers LIMIT 1;").fetchone()
        resource_count = connection.execute("SELECT COUNT(*) FROM image_resources;").fetchone()[0]
        latest_item = connection.execute(
            "SELECT * FROM collection_task_items ORDER BY id ASC LIMIT 1;"
        ).fetchone()
    finally:
        connection.close()

    assert summary.task_status == "succeeded"
    assert summary.success_count == 1
    assert summary.duplicate_count == 0
    assert wallpaper_count == 1
    assert wallpaper is not None
    assert wallpaper["resource_status"] == "ready"
    assert wallpaper["content_status"] == "enabled"
    assert resource_count == 4
    assert latest_item is not None
    assert latest_item["action_name"] == "repair_incomplete_wallpaper"
    assert latest_item["db_write_result"] == "resume_existing_wallpaper_resources"
    public_files = [path for path in storage.public_dir.rglob("*") if path.is_file()]
    assert len(public_files) == 4


def test_bing_collection_service_can_keep_new_wallpaper_in_draft_when_auto_publish_disabled(
    tmp_path: Path,
) -> None:
    service, database_path, _storage = build_service(
        tmp_path=tmp_path,
        metadata=[
            make_metadata(
                market_code="en-US",
                wallpaper_date="2026-03-24",
                source_key="bing:en-US:2026-03-24:OHR.DraftOnly",
                source_url="https://www.bing.com/th?id=OHR.DraftOnly_1920x1080.jpg&pid=hp",
            )
        ],
        downloads=[DownloadedImage(content=JPEG_BYTES, mime_type="image/jpeg")],
        auto_publish_enabled=False,
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
        wallpaper = connection.execute("SELECT * FROM wallpapers LIMIT 1;").fetchone()
    finally:
        connection.close()

    assert summary.task_status == "succeeded"
    assert wallpaper is not None
    assert wallpaper["resource_status"] == "ready"
    assert wallpaper["content_status"] == "draft"
    assert wallpaper["is_public"] == 0


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


def test_bing_collection_service_records_variant_failure_in_task_logs(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    service, database_path, _storage = build_service(
        tmp_path=tmp_path,
        metadata=[
            make_metadata(
                market_code="en-US",
                wallpaper_date="2026-03-24",
                source_key="bing:en-US:2026-03-24:OHR.VariantFailure",
                source_url="https://www.bing.com/th?id=OHR.VariantFailure_1920x1080.jpg",
            )
        ],
        downloads=[DownloadedImage(content=JPEG_BYTES, mime_type="image/jpeg")],
    )
    from PIL import Image

    from app.domain.resource_variants import ResourceType
    from app.services.image_variants import (
        generate_variant_image as original_generate_variant_image,
    )

    def fail_thumbnail(image: Image.Image, *, resource_type: ResourceType) -> object:
        if resource_type == "thumbnail":
            raise RuntimeError("thumbnail encoder unavailable")
        return original_generate_variant_image(image, resource_type=resource_type)

    monkeypatch.setattr("app.services.source_collection.generate_variant_image", fail_thumbnail)

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
        resources = connection.execute(
            "SELECT resource_type, image_status, failure_reason FROM image_resources ORDER BY id ASC;"
        ).fetchall()
        items = connection.execute(
            "SELECT action_name, result_status, failure_reason FROM collection_task_items ORDER BY id ASC;"
        ).fetchall()
    finally:
        connection.close()

    assert summary.task_status == "failed"
    assert wallpaper is not None
    assert wallpaper["resource_status"] == "failed"
    assert {str(resource["resource_type"]) for resource in resources} == {
        "original",
        "thumbnail",
        "preview",
        "download",
    }
    thumbnail_row = next(
        resource for resource in resources if str(resource["resource_type"]) == "thumbnail"
    )
    preview_row = next(
        resource for resource in resources if str(resource["resource_type"]) == "preview"
    )
    assert thumbnail_row["image_status"] == "failed"
    assert "thumbnail generation failed" in str(thumbnail_row["failure_reason"])
    assert preview_row["image_status"] == "failed"
    assert "variant processing aborted" in str(preview_row["failure_reason"])
    assert any(
        item["action_name"] == "generate_variant"
        and item["result_status"] == "failed"
        and "thumbnail generation failed" in str(item["failure_reason"])
        for item in items
    )


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
                source_url="https://www.bing.com/th?id=OHR.Shared_1920x1080.jpg&pid=hp",
            ),
        ],
        downloads=[
            DownloadedImage(content=JPEG_BYTES, mime_type="image/jpeg"),
            DownloadedImage(content=JPEG_BYTES, mime_type="image/jpeg"),
        ],
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

    assert summary.success_count == 2
    assert summary.duplicate_count == 0
    assert wallpaper_count == 2
    assert latest_item["result_status"] == "succeeded"


def test_bing_collection_service_skips_source_url_hash_duplicates_within_same_market(
    tmp_path: Path,
) -> None:
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
                market_code="en-US",
                wallpaper_date="2026-03-25",
                source_key="bing:en-US:2026-03-25:OHR.SharedB",
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


def test_bing_collection_service_repairs_corrupted_ready_resource_files(tmp_path: Path) -> None:
    service, database_path, storage = build_service(
        tmp_path=tmp_path,
        metadata=[
            make_metadata(
                market_code="en-US",
                wallpaper_date="2026-03-24",
                source_key="bing:en-US:2026-03-24:OHR.ResumeCorrupted",
                source_url="https://www.bing.com/th?id=OHR.ResumeCorrupted_1920x1080.jpg&pid=hp",
            )
        ],
        downloads=[
            DownloadedImage(content=JPEG_BYTES, mime_type="image/jpeg"),
            DownloadedImage(
                content=build_test_jpeg_bytes(width=1920, height=1080), mime_type="image/jpeg"
            ),
        ],
    )

    try:
        first_summary = service.collect(
            market_code="en-US", count=1, trigger_type="manual", triggered_by=None
        )
        public_files = [path for path in storage.public_dir.rglob("*") if path.is_file()]
        assert public_files
        corrupted_path = public_files[0]
        corrupted_path.write_bytes(b"x" * corrupted_path.stat().st_size)
        second_summary = service.collect(
            market_code="en-US", count=1, trigger_type="manual", triggered_by=None
        )
    finally:
        service.repository.close()

    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        wallpaper_count = connection.execute("SELECT COUNT(*) FROM wallpapers;").fetchone()[0]
        resource_count = connection.execute("SELECT COUNT(*) FROM image_resources;").fetchone()[0]
        latest_items = connection.execute(
            "SELECT action_name, failure_reason FROM collection_task_items ORDER BY id DESC LIMIT 2;"
        ).fetchall()
    finally:
        connection.close()

    assert first_summary.success_count == 1
    assert second_summary.success_count == 1
    assert second_summary.duplicate_count == 0
    assert wallpaper_count == 1
    assert resource_count == 4
    assert any(str(item["action_name"]) == "repair_incomplete_wallpaper" for item in latest_items)
    assert any("integrity validation" in str(item["failure_reason"]) for item in latest_items)


def build_service(
    *,
    tmp_path: Path,
    metadata: list[BingImageMetadata],
    downloads: list[DownloadedImage | Exception],
    max_download_retries: int = 2,
    auto_publish_enabled: bool = True,
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
        auto_publish_enabled=auto_publish_enabled,
    )
    return service, database_path, storage


def make_metadata(
    *,
    market_code: str,
    wallpaper_date: str,
    source_key: str,
    source_url: str,
    subtitle: str | None = "Test subtitle",
    description: str | None = "Test description",
    location_text: str | None = "Test location",
    published_at_utc: str | None = "2026-03-24T16:00:00Z",
    portrait_image_url: str | None = None,
    download_variants: tuple[CollectedDownloadVariant, ...] = (),
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
        raw_extra_json=json.dumps(
            {
                "source_key": source_key,
                "portrait_image_url": portrait_image_url
                or source_url.replace("_1920x1080", "_720x1280"),
            },
            ensure_ascii=True,
        ),
        subtitle=subtitle,
        description=description,
        location_text=location_text,
        published_at_utc=published_at_utc,
        portrait_image_url=portrait_image_url or source_url.replace("_1920x1080", "_720x1280"),
        download_variants=download_variants,
    )


JPEG_BYTES = build_test_jpeg_bytes()
