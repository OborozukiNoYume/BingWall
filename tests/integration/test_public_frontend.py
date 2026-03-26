from __future__ import annotations

from pathlib import Path

from tests.integration.test_public_api import build_client
from tests.integration.test_public_api import prepare_database
from tests.integration.test_public_api import seed_wallpaper

JPEG_BYTES = b"\xff\xd8\xff\xdbfrontend-jpeg"


def test_public_frontend_shell_routes_return_html_pages(tmp_path: Path) -> None:
    database_path = prepare_database(tmp_path)
    wallpaper_id = seed_wallpaper(
        database_path=database_path,
        wallpaper_date="2026-03-24",
        market_code="en-US",
        title="Frontend shell",
    )

    with build_client(tmp_path) as client:
        home_response = client.get("/")
        list_response = client.get("/wallpapers?page=2&market_code=en-US")
        detail_response = client.get(f"/wallpapers/{wallpaper_id}")

    assert home_response.status_code == 200
    assert "text/html" in home_response.headers["content-type"]
    assert 'data-page="home"' in home_response.text
    assert 'src="/assets/site.js"' in home_response.text

    assert list_response.status_code == 200
    assert 'data-page="list"' in list_response.text
    assert "公开壁纸列表" in list_response.text

    assert detail_response.status_code == 200
    assert 'data-page="detail"' in detail_response.text
    assert f'data-wallpaper-id="{wallpaper_id}"' in detail_response.text


def test_public_frontend_assets_only_reference_public_api_contract(tmp_path: Path) -> None:
    prepare_database(tmp_path)

    with build_client(tmp_path) as client:
        asset_response = client.get("/assets/site.js")
        css_response = client.get("/assets/site.css")

    assert asset_response.status_code == 200
    assert 'fetchEnvelope("/api/public/site-info")' in asset_response.text
    assert "/api/public/wallpaper-filters" in asset_response.text
    assert "/api/public/wallpapers?page=1&page_size=6&sort=date_desc" in asset_response.text
    assert "tag_keys" in asset_response.text
    assert "内容不存在" in asset_response.text
    assert "服务繁忙" in asset_response.text
    assert "sqlite" not in asset_response.text.lower()

    assert css_response.status_code == 200
    assert ".card-grid" in css_response.text
    assert ".detail-layout" in css_response.text
    assert ".tag-filter-grid" in css_response.text


def test_public_frontend_can_serve_public_images_from_storage_directory(tmp_path: Path) -> None:
    database_path = prepare_database(tmp_path)
    seed_wallpaper(
        database_path=database_path,
        wallpaper_date="2026-03-24",
        market_code="en-US",
        title="Frontend image",
    )

    image_path = (
        tmp_path / "images" / "public" / "bing" / "2026" / "03" / "en-US" / "frontend-image.jpg"
    )
    image_path.parent.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(JPEG_BYTES)

    with build_client(tmp_path) as client:
        response = client.get("/images/bing/2026/03/en-US/frontend-image.jpg")

    assert response.status_code == 200
    assert response.content == JPEG_BYTES
