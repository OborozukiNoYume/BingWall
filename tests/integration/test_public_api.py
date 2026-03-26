from __future__ import annotations

from datetime import UTC
from datetime import datetime
import os
from pathlib import Path
import sqlite3
import time
from typing import cast

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
        == "/images/bing/2026/03/en-US/visible-latest--thumbnail.jpg"
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
    assert payload["data"]["preview_url"] == "/images/bing/2026/03/en-US/preview-only--preview.jpg"
    assert payload["data"]["download_url"] is None
    assert payload["data"]["is_downloadable"] is False


def test_public_wallpaper_detail_distinguishes_preview_and_download_resources(
    tmp_path: Path,
) -> None:
    database_path = prepare_database(tmp_path)
    wallpaper_id = seed_wallpaper(
        database_path=database_path,
        wallpaper_date="2026-03-24",
        market_code="en-US",
        title="Preview and download",
        include_download_resource=True,
    )

    with build_client(tmp_path) as client:
        response = client.get(f"/api/public/wallpapers/{wallpaper_id}")

    payload = response.json()
    assert response.status_code == 200
    assert payload["data"]["preview_url"] == (
        "/images/bing/2026/03/en-US/preview-and-download--preview.jpg"
    )
    assert payload["data"]["download_url"] == (
        "/images/bing/2026/03/en-US/preview-and-download--download.jpg"
    )


def test_public_api_supports_local_and_oss_resource_urls_in_parallel(tmp_path: Path) -> None:
    database_path = prepare_database(tmp_path)
    seed_wallpaper(
        database_path=database_path,
        wallpaper_date="2026-03-24",
        market_code="en-US",
        title="Local Visible",
    )
    oss_wallpaper_id = seed_wallpaper(
        database_path=database_path,
        wallpaper_date="2026-03-25",
        market_code="en-US",
        title="OSS Visible",
        include_download_resource=True,
        original_storage_backend="oss",
        thumbnail_storage_backend="oss",
        preview_storage_backend="oss",
        download_storage_backend="oss",
    )

    with build_client(tmp_path, oss_public_base_url="https://cdn.example.com/bingwall") as client:
        list_response = client.get("/api/public/wallpapers?page=1&page_size=20")
        detail_response = client.get(f"/api/public/wallpapers/{oss_wallpaper_id}")

    list_payload = list_response.json()
    detail_payload = detail_response.json()

    assert list_response.status_code == 200
    assert [item["title"] for item in list_payload["data"]["items"]] == [
        "OSS Visible",
        "Local Visible",
    ]
    assert list_payload["data"]["items"][0]["thumbnail_url"] == (
        "https://cdn.example.com/bingwall/bing/2026/03/en-US/oss-visible--thumbnail.jpg"
    )
    assert list_payload["data"]["items"][1]["thumbnail_url"] == (
        "/images/bing/2026/03/en-US/local-visible--thumbnail.jpg"
    )

    assert detail_response.status_code == 200
    assert detail_payload["data"]["preview_url"] == (
        "https://cdn.example.com/bingwall/bing/2026/03/en-US/oss-visible--preview.jpg"
    )
    assert detail_payload["data"]["download_url"] == (
        "https://cdn.example.com/bingwall/bing/2026/03/en-US/oss-visible--download.jpg"
    )
    assert str(tmp_path) not in detail_payload["data"]["preview_url"]


def test_public_download_event_records_and_returns_redirect_url(tmp_path: Path) -> None:
    database_path = prepare_database(tmp_path)
    wallpaper_id = seed_wallpaper(
        database_path=database_path,
        wallpaper_date="2026-03-24",
        market_code="en-US",
        title="Download Visible",
        include_download_resource=True,
    )

    with build_client(tmp_path) as client:
        response = client.post(
            "/api/public/download-events",
            json={"wallpaper_id": wallpaper_id, "download_channel": "public_detail"},
            headers={"User-Agent": "pytest-browser"},
        )

    payload = response.json()
    row = get_latest_download_event(database_path)
    assert response.status_code == 200
    assert payload["data"]["redirect_url"] == (
        "/images/bing/2026/03/en-US/download-visible--download.jpg"
    )
    assert payload["data"]["recorded"] is True
    assert payload["data"]["result_status"] == "redirected"
    assert isinstance(payload["data"]["event_id"], int)
    assert row is not None
    assert row["wallpaper_id"] == wallpaper_id
    assert row["request_id"] == payload["trace_id"]
    assert row["download_channel"] == "public_detail"
    assert row["result_status"] == "redirected"
    assert row["redirect_url"] == payload["data"]["redirect_url"]
    assert row["client_ip_hash"] is not None
    assert row["user_agent"] is not None


def test_public_download_event_records_blocked_event_for_non_downloadable_wallpaper(
    tmp_path: Path,
) -> None:
    database_path = prepare_database(tmp_path)
    wallpaper_id = seed_wallpaper(
        database_path=database_path,
        wallpaper_date="2026-03-24",
        market_code="en-US",
        title="Blocked Download",
        is_downloadable=False,
    )

    with build_client(tmp_path) as client:
        response = client.post(
            "/api/public/download-events",
            json={"wallpaper_id": wallpaper_id, "download_channel": "public_detail"},
        )

    payload = response.json()
    row = get_latest_download_event(database_path)
    assert response.status_code == 409
    assert payload["error_code"] == "PUBLIC_DOWNLOAD_NOT_ALLOWED"
    assert row is not None
    assert row["wallpaper_id"] == wallpaper_id
    assert row["result_status"] == "blocked"
    assert row["redirect_url"] is None


def test_public_wallpaper_filters_and_site_info_only_return_public_options(tmp_path: Path) -> None:
    database_path = prepare_database(tmp_path)
    visible_wallpaper_id = seed_wallpaper(
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
    enabled_tag_id = seed_tag(
        database_path=database_path,
        tag_key="theme-forest",
        tag_name="森林",
    )
    disabled_tag_id = seed_tag(
        database_path=database_path,
        tag_key="theme-hidden",
        tag_name="隐藏标签",
        status="disabled",
    )
    bind_wallpaper_tags(
        database_path=database_path,
        wallpaper_id=visible_wallpaper_id,
        tag_ids=[enabled_tag_id, disabled_tag_id],
    )

    with build_client(tmp_path) as client:
        filters_response = client.get("/api/public/wallpaper-filters")
        tags_response = client.get("/api/public/tags")
        site_info_response = client.get("/api/public/site-info")

    filters_payload = filters_response.json()
    tags_payload = tags_response.json()
    site_info_payload = site_info_response.json()
    assert filters_response.status_code == 200
    assert filters_payload["data"]["markets"] == [
        {"code": "en-US", "label": "English (United States)"},
        {"code": "fr-FR", "label": "Français (France)"},
    ]
    assert filters_payload["data"]["tags"] == [
        {
            "id": enabled_tag_id,
            "tag_key": "theme-forest",
            "tag_name": "森林",
            "tag_category": None,
        }
    ]
    assert filters_payload["data"]["sort_options"] == [{"value": "date_desc", "label": "最新优先"}]
    assert tags_response.status_code == 200
    assert tags_payload["data"]["items"] == [
        {
            "id": enabled_tag_id,
            "tag_key": "theme-forest",
            "tag_name": "森林",
            "tag_category": None,
        }
    ]
    assert site_info_response.status_code == 200
    assert site_info_payload["data"] == {
        "site_name": "BingWall",
        "site_description": "Bing 壁纸图片服务",
        "default_market_code": "en-US",
    }


def test_public_wallpaper_list_supports_enabled_tag_filter(tmp_path: Path) -> None:
    database_path = prepare_database(tmp_path)
    sea_wallpaper_id = seed_wallpaper(
        database_path=database_path,
        wallpaper_date="2026-03-24",
        market_code="en-US",
        title="Sea Visible",
    )
    mountain_wallpaper_id = seed_wallpaper(
        database_path=database_path,
        wallpaper_date="2026-03-23",
        market_code="en-US",
        title="Mountain Visible",
    )
    theme_tag_id = seed_tag(
        database_path=database_path,
        tag_key="theme-sea",
        tag_name="海洋",
    )
    location_tag_id = seed_tag(
        database_path=database_path,
        tag_key="location-us",
        tag_name="美国",
    )
    disabled_tag_id = seed_tag(
        database_path=database_path,
        tag_key="theme-disabled",
        tag_name="停用标签",
        status="disabled",
    )
    bind_wallpaper_tags(
        database_path=database_path,
        wallpaper_id=sea_wallpaper_id,
        tag_ids=[theme_tag_id, location_tag_id, disabled_tag_id],
    )
    bind_wallpaper_tags(
        database_path=database_path,
        wallpaper_id=mountain_wallpaper_id,
        tag_ids=[location_tag_id],
    )

    with build_client(tmp_path) as client:
        response = client.get("/api/public/wallpapers?tag_keys=theme-sea,location-us")
        hidden_response = client.get("/api/public/wallpapers?tag_keys=theme-disabled")

    payload = response.json()
    hidden_payload = hidden_response.json()
    assert response.status_code == 200
    assert payload["pagination"]["total"] == 1
    assert payload["data"]["items"][0]["title"] == "Sea Visible"
    assert hidden_response.status_code == 200
    assert hidden_payload["pagination"]["total"] == 0


def test_public_wallpaper_list_supports_keyword_search_across_text_and_enabled_tags(
    tmp_path: Path,
) -> None:
    database_path = prepare_database(tmp_path)
    visible_wallpaper_id = seed_wallpaper(
        database_path=database_path,
        wallpaper_date="2026-03-24",
        market_code="en-US",
        title="Morning Lake",
        subtitle="薄雾清晨",
        description="清晨的湖面与金色山影",
        copyright_text="Morning Lake copyright",
    )
    hidden_wallpaper_id = seed_wallpaper(
        database_path=database_path,
        wallpaper_date="2026-03-23",
        market_code="en-US",
        title="Morning Hidden",
        description="清晨的隐藏内容",
        content_status="disabled",
        is_public=False,
    )
    enabled_tag_id = seed_tag(
        database_path=database_path,
        tag_key="theme-dawn",
        tag_name="晨曦",
    )
    disabled_tag_id = seed_tag(
        database_path=database_path,
        tag_key="theme-secret",
        tag_name="隐藏晨曦",
        status="disabled",
    )
    bind_wallpaper_tags(
        database_path=database_path,
        wallpaper_id=visible_wallpaper_id,
        tag_ids=[enabled_tag_id, disabled_tag_id],
    )
    bind_wallpaper_tags(
        database_path=database_path,
        wallpaper_id=hidden_wallpaper_id,
        tag_ids=[enabled_tag_id],
    )

    with build_client(tmp_path) as client:
        text_response = client.get("/api/public/wallpapers?keyword=金色山影")
        tag_response = client.get("/api/public/wallpapers?keyword=晨曦")
        hidden_tag_response = client.get("/api/public/wallpapers?keyword=隐藏晨曦")

    text_payload = text_response.json()
    tag_payload = tag_response.json()
    hidden_tag_payload = hidden_tag_response.json()

    assert text_response.status_code == 200
    assert text_payload["pagination"]["total"] == 1
    assert text_payload["data"]["items"][0]["title"] == "Morning Lake"

    assert tag_response.status_code == 200
    assert tag_payload["pagination"]["total"] == 1
    assert tag_payload["data"]["items"][0]["title"] == "Morning Lake"

    assert hidden_tag_response.status_code == 200
    assert hidden_tag_payload["pagination"]["total"] == 0


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


def test_public_and_admin_keyword_search_complete_within_one_second_on_representative_samples(
    tmp_path: Path,
) -> None:
    database_path = prepare_database(tmp_path)
    from tests.integration.test_admin_auth import seed_admin_user

    seed_admin_user(
        database_path=database_path,
        username="admin",
        password="correct-password",
    )
    benchmark_tag_id = seed_tag(
        database_path=database_path,
        tag_key="theme-benchmark",
        tag_name="性能样本",
    )
    for index in range(1, 31):
        wallpaper_id = seed_wallpaper(
            database_path=database_path,
            wallpaper_date=f"2026-03-{index:02d}",
            market_code="en-US" if index % 2 == 0 else "fr-FR",
            title=f"Benchmark Sample {index}",
            description=f"Representative search sample {index}",
            content_status="enabled" if index <= 20 else "disabled",
            is_public=index <= 20,
        )
        bind_wallpaper_tags(
            database_path=database_path,
            wallpaper_id=wallpaper_id,
            tag_ids=[benchmark_tag_id],
        )

    with build_client(tmp_path) as client:
        login_response = client.post(
            "/api/admin/auth/login",
            json={"username": "admin", "password": "correct-password"},
        )
        session_token = str(login_response.json()["data"]["session_token"])

        public_started = time.perf_counter()
        public_response = client.get("/api/public/wallpapers?keyword=Benchmark&page=1&page_size=20")
        public_elapsed = time.perf_counter() - public_started

        admin_started = time.perf_counter()
        admin_response = client.get(
            "/api/admin/wallpapers?keyword=Benchmark&page=1&page_size=20",
            headers={"Authorization": f"Bearer {session_token}"},
        )
        admin_elapsed = time.perf_counter() - admin_started

    assert public_response.status_code == 200
    assert public_response.json()["pagination"]["total"] == 20
    assert public_elapsed < 1.0

    assert admin_response.status_code == 200
    assert admin_response.json()["pagination"]["total"] == 30
    assert admin_elapsed < 1.0


def build_client(tmp_path: Path, *, oss_public_base_url: str | None = None) -> TestClient:
    clear_bingwall_env()
    os.environ["BINGWALL_APP_ENV"] = "test"
    os.environ["BINGWALL_APP_HOST"] = "127.0.0.1"
    os.environ["BINGWALL_APP_PORT"] = "8000"
    os.environ["BINGWALL_APP_BASE_URL"] = "http://127.0.0.1:8000"
    os.environ["BINGWALL_DATABASE_PATH"] = str(tmp_path / "data" / "bingwall.sqlite3")
    os.environ["BINGWALL_STORAGE_TMP_DIR"] = str(tmp_path / "images" / "tmp")
    os.environ["BINGWALL_STORAGE_PUBLIC_DIR"] = str(tmp_path / "images" / "public")
    os.environ["BINGWALL_STORAGE_FAILED_DIR"] = str(tmp_path / "images" / "failed")
    if oss_public_base_url is not None:
        os.environ["BINGWALL_STORAGE_OSS_PUBLIC_BASE_URL"] = oss_public_base_url
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
    subtitle: str | None = None,
    description: str | None = None,
    copyright_text: str | None = None,
    content_status: str = "enabled",
    is_public: bool = True,
    is_downloadable: bool = True,
    resource_status: str = "ready",
    image_status: str = "ready",
    failure_reason: str | None = None,
    publish_start_at_utc: str = "2000-01-01T00:00:00Z",
    publish_end_at_utc: str | None = "2100-01-01T00:00:00Z",
    include_download_resource: bool = False,
    original_storage_backend: str = "local",
    thumbnail_storage_backend: str | None = None,
    preview_storage_backend: str | None = None,
    download_storage_backend: str | None = None,
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
                subtitle or f"{title} subtitle",
                description or f"{title} description",
                copyright_text or f"{title} copyright",
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
        slug = slugify(title)
        original_relative_path = f"bing/2026/03/{market_code}/{slug}.jpg"
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
            VALUES (?, 'original', ?, ?, ?, 'jpg', 'image/jpeg', 1024, 1920, 1080, ?, ?, ?, ?, 'passed', ?, ?, ?, ?, ?);
            """,
            (
                wallpaper_id,
                original_storage_backend,
                original_relative_path,
                f"{slug}.jpg",
                f"https://www.bing.com/{slug}.jpg",
                f"hash-{slug}",
                f"content-{slug}",
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
        _seed_variant_resource(
            connection=connection,
            wallpaper_id=wallpaper_id,
            resource_type="thumbnail",
            storage_backend=thumbnail_storage_backend or original_storage_backend,
            relative_path=f"bing/2026/03/{market_code}/{slug}--thumbnail.jpg",
            file_size_bytes=128,
            width=480,
            height=270,
            now_utc=now_utc,
            image_status=image_status,
            failure_reason=failure_reason,
        )
        _seed_variant_resource(
            connection=connection,
            wallpaper_id=wallpaper_id,
            resource_type="preview",
            storage_backend=preview_storage_backend or original_storage_backend,
            relative_path=f"bing/2026/03/{market_code}/{slug}--preview.jpg",
            file_size_bytes=512,
            width=1600,
            height=900,
            now_utc=now_utc,
            image_status=image_status,
            failure_reason=failure_reason,
        )
        if is_downloadable and include_download_resource:
            _seed_variant_resource(
                connection=connection,
                wallpaper_id=wallpaper_id,
                resource_type="download",
                storage_backend=download_storage_backend or original_storage_backend,
                relative_path=f"bing/2026/03/{market_code}/{slug}--download.jpg",
                file_size_bytes=1024,
                width=1920,
                height=1080,
                now_utc=now_utc,
                image_status=image_status,
                failure_reason=failure_reason,
            )
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


def _seed_variant_resource(
    *,
    connection: sqlite3.Connection,
    wallpaper_id: int,
    resource_type: str,
    storage_backend: str,
    relative_path: str,
    file_size_bytes: int,
    width: int,
    height: int,
    now_utc: str,
    image_status: str,
    failure_reason: str | None,
) -> None:
    connection.execute(
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
        VALUES (?, ?, ?, ?, ?, 'jpg', 'image/jpeg', ?, ?, ?, NULL, NULL, ?, ?, 'passed', ?, ?, ?, ?, ?);
        """,
        (
            wallpaper_id,
            resource_type,
            storage_backend,
            relative_path,
            Path(relative_path).name,
            file_size_bytes,
            width,
            height,
            f"content-{resource_type}-{Path(relative_path).stem}",
            now_utc,
            image_status,
            failure_reason,
            now_utc,
            now_utc,
            now_utc,
        ),
    )


def seed_tag(
    *,
    database_path: Path,
    tag_key: str,
    tag_name: str,
    tag_category: str | None = None,
    status: str = "enabled",
    sort_weight: int = 0,
) -> int:
    connection = sqlite3.connect(database_path)
    try:
        now_utc = datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        cursor = connection.execute(
            """
            INSERT INTO tags (
                tag_key,
                tag_name,
                tag_category,
                status,
                sort_weight,
                created_at_utc,
                updated_at_utc
            )
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (tag_key, tag_name, tag_category, status, sort_weight, now_utc, now_utc),
        )
        if cursor.lastrowid is None:
            raise RuntimeError("Failed to create tag test record.")
        connection.commit()
        return int(cursor.lastrowid)
    finally:
        connection.close()


def bind_wallpaper_tags(
    *,
    database_path: Path,
    wallpaper_id: int,
    tag_ids: list[int],
    created_by: str = "pytest",
) -> None:
    connection = sqlite3.connect(database_path)
    try:
        now_utc = datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        for tag_id in tag_ids:
            connection.execute(
                """
                INSERT INTO wallpaper_tags (
                    wallpaper_id,
                    tag_id,
                    created_at_utc,
                    created_by
                )
                VALUES (?, ?, ?, ?);
                """,
                (wallpaper_id, tag_id, now_utc, created_by),
            )
        connection.commit()
    finally:
        connection.close()


def get_latest_download_event(database_path: Path) -> sqlite3.Row | None:
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        row = connection.execute(
            """
            SELECT *
            FROM download_events
            ORDER BY id DESC
            LIMIT 1;
            """
        ).fetchone()
        return cast(sqlite3.Row | None, row)
    finally:
        connection.close()
