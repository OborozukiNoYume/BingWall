import pytest

from app.services.resource_locator import ResourceLocator


def test_resource_locator_builds_local_and_oss_urls() -> None:
    locator = ResourceLocator(oss_public_base_url="https://cdn.example.com/bingwall")

    local_url = locator.build_url(
        storage_backend="local",
        relative_path="bing/2026/03/24_en-US_preview_1600x900.jpg",
    )
    oss_url = locator.build_url(
        storage_backend="oss",
        relative_path="bing/2026/03/24_en-US_preview_1600x900.jpg",
    )

    assert local_url == "/images/bing/2026/03/24_en-US_preview_1600x900.jpg"
    assert oss_url == "https://cdn.example.com/bingwall/bing/2026/03/24_en-US_preview_1600x900.jpg"


def test_resource_locator_rejects_path_traversal() -> None:
    locator = ResourceLocator(oss_public_base_url="https://cdn.example.com/bingwall")

    with pytest.raises(ValueError):
        locator.build_url(storage_backend="local", relative_path="../secrets.txt")


def test_resource_locator_requires_oss_base_url_for_oss_resources() -> None:
    locator = ResourceLocator()

    with pytest.raises(ValueError):
        locator.build_url(
            storage_backend="oss",
            relative_path="bing/2026/03/24_en-US_preview_1600x900.jpg",
        )
