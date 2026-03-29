from __future__ import annotations

import hashlib
from pathlib import Path
import sqlite3

from app.repositories.health_repository import HealthRepository
from app.services.resource_archive import ResourceArchiveService
from tests.integration.test_health_checks import ensure_runtime_dirs
from tests.integration.test_public_api import prepare_database
from tests.integration.test_public_api import seed_wallpaper
from tests.support.image_factory import build_test_jpeg_bytes


def test_resource_archive_rewrites_historical_resources_to_structured_paths(
    tmp_path: Path,
) -> None:
    database_path = prepare_database(tmp_path)
    ensure_runtime_dirs(tmp_path)
    wallpaper_id = seed_wallpaper(
        database_path=database_path,
        wallpaper_date="2026-03-24",
        market_code="en-US",
        title="Archive Migration",
        include_download_resource=True,
    )
    _materialize_ready_resource_files(
        database_path=database_path, public_dir=tmp_path / "images" / "public"
    )

    repository = HealthRepository(database_path)
    service = ResourceArchiveService(
        repository,
        tmp_dir=tmp_path / "images" / "tmp",
        public_dir=tmp_path / "images" / "public",
        failed_dir=tmp_path / "images" / "failed",
    )
    try:
        summary = service.archive_and_cleanup()
    finally:
        repository.close()

    assert summary["archived_resource_count"] == 4
    assert summary["damaged_resource_count"] == 0

    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        resource_rows = connection.execute(
            """
            SELECT resource_type, relative_path
            FROM image_resources
            WHERE wallpaper_id = ?
            ORDER BY id ASC;
            """,
            (wallpaper_id,),
        ).fetchall()
    finally:
        connection.close()

    assert [(str(row["resource_type"]), str(row["relative_path"])) for row in resource_rows] == [
        ("original", "bing/2026/03/24_en-US_1920x1080.jpg"),
        ("thumbnail", "bing/2026/03/24_en-US_thumbnail_480x270.jpg"),
        ("preview", "bing/2026/03/24_en-US_preview_1600x900.jpg"),
        ("download", "bing/2026/03/24_en-US_download_1920x1080.jpg"),
    ]
    for _resource_type, relative_path in resource_rows:
        assert (tmp_path / "images" / "public" / str(relative_path)).is_file()
    assert not (tmp_path / "images" / "public" / "bing" / "2026" / "03" / "en-US").exists()


def test_resource_archive_cleans_tmp_empty_duplicate_and_orphan_files_without_touching_valid_history(
    tmp_path: Path,
) -> None:
    database_path = prepare_database(tmp_path)
    ensure_runtime_dirs(tmp_path)
    seed_wallpaper(
        database_path=database_path,
        wallpaper_date="2026-03-24",
        market_code="en-US",
        title="Archive Cleanup",
        include_download_resource=True,
    )
    _materialize_ready_resource_files(
        database_path=database_path, public_dir=tmp_path / "images" / "public"
    )

    tmp_file = tmp_path / "images" / "tmp" / "leftover.tmp"
    tmp_file.parent.mkdir(parents=True, exist_ok=True)
    tmp_file.write_bytes(b"temporary")

    orphan_empty = tmp_path / "images" / "public" / "orphan-empty.jpg"
    orphan_empty.write_bytes(b"")

    referenced_file = (
        tmp_path / "images" / "public" / "bing" / "2026" / "03" / "en-US" / "archive-cleanup.jpg"
    )
    duplicate_orphan = tmp_path / "images" / "public" / "duplicate-copy.jpg"
    duplicate_orphan.write_bytes(referenced_file.read_bytes())

    unique_orphan = tmp_path / "images" / "public" / "orphan-unique.jpg"
    unique_orphan.write_bytes(build_test_jpeg_bytes(width=800, height=600))

    repository = HealthRepository(database_path)
    service = ResourceArchiveService(
        repository,
        tmp_dir=tmp_path / "images" / "tmp",
        public_dir=tmp_path / "images" / "public",
        failed_dir=tmp_path / "images" / "failed",
    )
    try:
        summary = service.archive_and_cleanup()
    finally:
        repository.close()

    assert summary["tmp_deleted_count"] == 1
    assert int(summary["empty_deleted_count"]) >= 1
    assert int(summary["duplicate_deleted_count"]) >= 1
    assert summary["orphan_quarantined_count"] == 1
    assert not tmp_file.exists()
    assert not orphan_empty.exists()
    assert not duplicate_orphan.exists()
    assert not unique_orphan.exists()
    retained_orphan = tmp_path / "images" / "failed" / "orphaned" / "orphan-unique.jpg"
    assert retained_orphan.is_file()

    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        ready_count = connection.execute(
            """
            SELECT COUNT(*) AS ready_count
            FROM image_resources
            WHERE image_status = 'ready';
            """
        ).fetchone()
    finally:
        connection.close()

    assert ready_count is not None
    assert ready_count["ready_count"] == 4


def test_resource_archive_quarantines_corrupted_ready_resource_and_disables_public_wallpaper(
    tmp_path: Path,
) -> None:
    database_path = prepare_database(tmp_path)
    ensure_runtime_dirs(tmp_path)
    wallpaper_id = seed_wallpaper(
        database_path=database_path,
        wallpaper_date="2026-03-24",
        market_code="en-US",
        title="Corrupted Archive",
        include_download_resource=True,
    )
    _materialize_ready_resource_files(
        database_path=database_path, public_dir=tmp_path / "images" / "public"
    )

    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        original_row = connection.execute(
            """
            SELECT relative_path
            FROM image_resources
            WHERE wallpaper_id = ?
              AND resource_type = 'original'
            LIMIT 1;
            """,
            (wallpaper_id,),
        ).fetchone()
    finally:
        connection.close()
    assert original_row is not None

    corrupted_path = tmp_path / "images" / "public" / str(original_row["relative_path"])
    corrupted_content = b"not-an-image"
    corrupted_path.write_bytes(corrupted_content)
    connection = sqlite3.connect(database_path)
    try:
        connection.execute(
            """
            UPDATE image_resources
            SET file_size_bytes = ?,
                content_hash = ?
            WHERE wallpaper_id = ?
              AND resource_type = 'original';
            """,
            (
                len(corrupted_content),
                hashlib.sha256(corrupted_content).hexdigest(),
                wallpaper_id,
            ),
        )
        connection.commit()
    finally:
        connection.close()

    repository = HealthRepository(database_path)
    service = ResourceArchiveService(
        repository,
        tmp_dir=tmp_path / "images" / "tmp",
        public_dir=tmp_path / "images" / "public",
        failed_dir=tmp_path / "images" / "failed",
    )
    try:
        summary = service.archive_and_cleanup()
    finally:
        repository.close()

    assert summary["damaged_resource_count"] == 1

    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        wallpaper_row = connection.execute(
            """
            SELECT content_status, is_public, resource_status
            FROM wallpapers
            WHERE id = ?;
            """,
            (wallpaper_id,),
        ).fetchone()
        original_status_row = connection.execute(
            """
            SELECT image_status, failure_reason
            FROM image_resources
            WHERE wallpaper_id = ?
              AND resource_type = 'original'
            LIMIT 1;
            """,
            (wallpaper_id,),
        ).fetchone()
    finally:
        connection.close()

    assert wallpaper_row is not None
    assert wallpaper_row["content_status"] == "disabled"
    assert wallpaper_row["is_public"] == 0
    assert wallpaper_row["resource_status"] == "failed"
    assert original_status_row is not None
    assert original_status_row["image_status"] == "failed"
    assert "corrupted image" in str(original_status_row["failure_reason"])
    quarantined_files = list((tmp_path / "images" / "failed" / "invalid").rglob("*"))
    assert any(path.is_file() for path in quarantined_files)


def _materialize_ready_resource_files(*, database_path: Path, public_dir: Path) -> None:
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            """
            SELECT id, relative_path, width, height
            FROM image_resources
            WHERE image_status = 'ready'
            ORDER BY id ASC;
            """
        ).fetchall()
        for row in rows:
            relative_path = str(row["relative_path"])
            width = int(row["width"])
            height = int(row["height"])
            file_path = public_dir / relative_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            content = build_test_jpeg_bytes(width=width, height=height)
            file_path.write_bytes(content)
            connection.execute(
                """
                UPDATE image_resources
                SET file_size_bytes = ?,
                    content_hash = ?,
                    updated_at_utc = updated_at_utc
                WHERE id = ?;
                """,
                (len(content), hashlib.sha256(content).hexdigest(), int(row["id"])),
            )
        connection.commit()
    finally:
        connection.close()
