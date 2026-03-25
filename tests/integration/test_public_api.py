from __future__ import annotations

from datetime import UTC
from datetime import datetime
import os
from pathlib import Path
import sqlite3

from fastapi.testclient import TestClient

from app.core.config import reset_settings_cache
from app.main import create_app
from app.repositories.migrations import migrate_database
from tests.conftest import clear_bingwall_env


def test_public_wallpaper_list_applies_visibility_rules_and_pagination(tmp_path: Path) -> None:
    database_path = prepare_database(tmp_path)
    seed_wallpaper(
        database_path=database_path,
        wallpaper_date="2026-03-24",
        market_code="en-US",
        title="Visible latest",
    )
    seed_wallpaper(
        database_path=database_path,
        wallpaper_date="2026-03-20",
        market_code="fr-FR",
        title="Visible older",
    )
    seed_wallpaper(
        database_path=database_path,
        wallpaper_date="2026-03-25",
        market_code="ja-JP",
        title="Hidden draft",
        content_status="draft",
    )
    seed_wallpaper(
        database_path=database_path,
        wallpaper_date="2026-03-26",
        market_code="de-DE",
        title="Hidden private",
        is_public=False,
    )

    with build_client(tmp_path) as client:
        response = client.get("/api/public/wallpapers?page=1&page_size=1")

    payload = response.json()
    assert response.status_code == 200
    assert response.headers["X-Trace-Id"]
    assert payload["success"] is True
    assert payload["pagination"] == {
        "page": 1,
        "page_size": 1,
        "total": 2,
        "total_pages": 2,
    }
    assert len(payload["data"]["items"]) == 1
    assert payload["data"]["items"][0]["title"] == "Visible latest"
    assert (
        payload["data"]["items"][0]["thumbnail_url"]
        == "/images/bing/2026/03/en-US/visible-latest.jpg"
    )


def test_public_wallpaper_detail_returns_null_download_url_when_not_downloadable(
    tmp_path: Path,
) -> None:
    database_path = prepare_database(tmp_path)
    wallpaper_id = seed_wallpaper(
        database_path=database_path,
        wallpaper_date="2026-03-24",
        market_code="en-US",
        title="Preview only",
        is_downloadable=False,
    )

    with build_client(tmp_path) as client:
        response = client.get(f"/api/public/wallpapers/{wallpaper_id}")

    payload = response.json()
    assert response.status_code == 200
    assert payload["data"]["title"] == "Preview only"
    assert payload["data"]["preview_url"] == "/images/bing/2026/03/en-US/preview-only.jpg"
    assert payload["data"]["download_url"] is None
    assert payload["data"]["is_downloadable"] is False


def test_public_wallpaper_filters_and_site_info_only_return_public_options(tmp_path: Path) -> None:
    database_path = prepare_database(tmp_path)
    seed_wallpaper(
        database_path=database_path,
        wallpaper_date="2026-03-24",
        market_code="en-US",
        title="Visible English",
    )
    seed_wallpaper(
        database_path=database_path,
        wallpaper_date="2026-03-23",
        market_code="fr-FR",
        title="Visible French",
    )
    seed_wallpaper(
        database_path=database_path,
        wallpaper_date="2026-03-22",
        market_code="ja-JP",
        title="Hidden deleted",
        content_status="deleted",
    )

    with build_client(tmp_path) as client:
        filters_response = client.get("/api/public/wallpaper-filters")
        site_info_response = client.get("/api/public/site-info")

    filters_payload = filters_response.json()
    site_info_payload = site_info_response.json()
    assert filters_response.status_code == 200
    assert filters_payload["data"]["markets"] == [
        {"code": "en-US", "label": "English (United States)"},
        {"code": "fr-FR", "label": "Français (France)"},
    ]
    assert filters_payload["data"]["sort_options"] == [{"value": "date_desc", "label": "最新优先"}]
    assert site_info_response.status_code == 200
    assert site_info_payload["data"] == {
        "site_name": "BingWall",
        "site_description": "Bing 壁纸图片服务",
        "default_market_code": "en-US",
    }


def test_public_wallpaper_endpoints_return_uniform_errors_for_invalid_or_hidden_items(
    tmp_path: Path,
) -> None:
    database_path = prepare_database(tmp_path)
    hidden_wallpaper_id = seed_wallpaper(
        database_path=database_path,
        wallpaper_date="2026-03-24",
        market_code="en-US",
        title="Hidden resource",
        publish_end_at_utc="2001-01-01T00:00:00Z",
    )

    with build_client(tmp_path) as client:
        invalid_response = client.get("/api/public/wallpapers?sort=unknown")
        hidden_response = client.get(f"/api/public/wallpapers/{hidden_wallpaper_id}")

    invalid_payload = invalid_response.json()
    hidden_payload = hidden_response.json()
    assert invalid_response.status_code == 422
    assert invalid_payload["success"] is False
    assert invalid_payload["error_code"] == "COMMON_INVALID_ARGUMENT"
    assert invalid_payload["trace_id"]
    assert hidden_response.status_code == 404
    assert hidden_payload == {
        "success": False,
        "message": "壁纸不存在或不可公开访问",
        "error_code": "PUBLIC_WALLPAPER_NOT_FOUND",
        "data": None,
        "trace_id": hidden_payload["trace_id"],
    }


def build_client(tmp_path: Path) -> TestClient:
    clear_bingwall_env()
    os.environ["BINGWALL_APP_ENV"] = "test"
    os.environ["BINGWALL_APP_HOST"] = "127.0.0.1"
    os.environ["BINGWALL_APP_PORT"] = "8000"
    os.environ["BINGWALL_APP_BASE_URL"] = "http://127.0.0.1:8000"
    os.environ["BINGWALL_DATABASE_PATH"] = str(tmp_path / "data" / "bingwall.sqlite3")
    os.environ["BINGWALL_STORAGE_TMP_DIR"] = str(tmp_path / "images" / "tmp")
    os.environ["BINGWALL_STORAGE_PUBLIC_DIR"] = str(tmp_path / "images" / "public")
    os.environ["BINGWALL_STORAGE_FAILED_DIR"] = str(tmp_path / "images" / "failed")
    os.environ["BINGWALL_BACKUP_DIR"] = str(tmp_path / "backups")
    os.environ["BINGWALL_SECURITY_SESSION_SECRET"] = "0123456789abcdef0123456789abcdef"
    os.environ["BINGWALL_SECURITY_SESSION_TTL_HOURS"] = "12"
    os.environ["BINGWALL_LOG_LEVEL"] = "INFO"
    reset_settings_cache()
    return TestClient(create_app())


def prepare_database(tmp_path: Path) -> Path:
    database_path = tmp_path / "data" / "bingwall.sqlite3"
    migrate_database(database_path)
    return database_path


def seed_wallpaper(
    *,
    database_path: Path,
    wallpaper_date: str,
    market_code: str,
    title: str,
    content_status: str = "enabled",
    is_public: bool = True,
    is_downloadable: bool = True,
    resource_status: str = "ready",
    image_status: str = "ready",
    failure_reason: str | None = None,
    publish_start_at_utc: str = "2000-01-01T00:00:00Z",
    publish_end_at_utc: str | None = "2100-01-01T00:00:00Z",
) -> int:
    connection = sqlite3.connect(database_path)
    try:
        now_utc = datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        cursor = connection.execute(
            """
            INSERT INTO wallpapers (
                source_type,
                source_key,
                market_code,
                wallpaper_date,
                title,
                subtitle,
                description,
                copyright_text,
                source_name,
                content_status,
                is_public,
                is_downloadable,
                publish_start_at_utc,
                publish_end_at_utc,
                origin_page_url,
                origin_image_url,
                origin_width,
                origin_height,
                resource_status,
                created_at_utc,
                updated_at_utc
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                "bing",
                f"bing:{market_code}:{wallpaper_date}:{slugify(title)}",
                market_code,
                wallpaper_date,
                title,
                f"{title} subtitle",
                f"{title} description",
                f"{title} copyright",
                "Bing",
                content_status,
                int(is_public),
                int(is_downloadable),
                publish_start_at_utc,
                publish_end_at_utc,
                "https://www.bing.com/example",
                f"https://www.bing.com/{slugify(title)}.jpg",
                1920,
                1080,
                resource_status,
                now_utc,
                now_utc,
            ),
        )
        wallpaper_lastrowid = cursor.lastrowid
        if wallpaper_lastrowid is None:
            raise RuntimeError("Failed to create wallpaper test record.")
        wallpaper_id = int(wallpaper_lastrowid)
        resource_cursor = connection.execute(
            """
            INSERT INTO image_resources (
                wallpaper_id,
                resource_type,
                storage_backend,
                relative_path,
                filename,
                file_ext,
                mime_type,
                file_size_bytes,
                width,
                height,
                source_url,
                source_url_hash,
                content_hash,
                downloaded_at_utc,
                integrity_check_result,
                image_status,
                failure_reason,
                last_processed_at_utc,
                created_at_utc,
                updated_at_utc
            )
            VALUES (?, 'original', 'local', ?, ?, 'jpg', 'image/jpeg', 1024, 1920, 1080, ?, ?, ?, ?, 'passed', ?, ?, ?, ?, ?);
            """,
            (
                wallpaper_id,
                f"bing/2026/03/{market_code}/{slugify(title)}.jpg",
                f"{slugify(title)}.jpg",
                f"https://www.bing.com/{slugify(title)}.jpg",
                f"hash-{slugify(title)}",
                f"content-{slugify(title)}",
                now_utc,
                image_status,
                failure_reason,
                now_utc,
                now_utc,
                now_utc,
            ),
        )
        resource_lastrowid = resource_cursor.lastrowid
        if resource_lastrowid is None:
            raise RuntimeError("Failed to create image resource test record.")
        resource_id = int(resource_lastrowid)
        connection.execute(
            "UPDATE wallpapers SET default_resource_id = ?, updated_at_utc = ? WHERE id = ?;",
            (resource_id, now_utc, wallpaper_id),
        )
        connection.commit()
        return wallpaper_id
    finally:
        connection.close()


def slugify(value: str) -> str:
    return value.lower().replace(" ", "-")
