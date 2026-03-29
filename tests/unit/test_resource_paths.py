from datetime import date

from app.services.resource_paths import build_resource_relative_path


def test_build_resource_relative_path_for_original_resource() -> None:
    relative_path = build_resource_relative_path(
        source_type="bing",
        wallpaper_date=date(2026, 3, 24),
        market_code="en-US",
        resource_type="original",
        file_ext="jpg",
        width=3840,
        height=2160,
    )

    assert relative_path == "bing/2026/03/24_en-US_3840x2160.jpg"


def test_build_resource_relative_path_for_variant_resource() -> None:
    relative_path = build_resource_relative_path(
        source_type="bing",
        wallpaper_date=date(2026, 3, 24),
        market_code="en-US",
        resource_type="preview",
        file_ext="jpg",
        width=1600,
        height=900,
    )

    assert relative_path == "bing/2026/03/24_en-US_preview_1600x900.jpg"


def test_build_resource_relative_path_falls_back_to_variant_key_when_resolution_missing() -> None:
    relative_path = build_resource_relative_path(
        source_type="bing",
        wallpaper_date=date(2026, 3, 24),
        market_code="en-US",
        resource_type="download",
        file_ext="jpg",
        width=None,
        height=None,
        variant_key="UHD",
    )

    assert relative_path == "bing/2026/03/24_en-US_download_uhd.jpg"
