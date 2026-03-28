from app.collectors.bing import build_download_variants


def test_build_download_variants_uses_exact_5_allowed_bing_resolutions() -> None:
    variants = build_download_variants(
        image_url="https://www.bing.com/th?id=OHR.Example_1920x1080.jpg&pid=hp",
        urlbase="/th?id=OHR.Example",
        is_downloadable=True,
    )

    assert [(item.variant_key, item.width, item.height) for item in variants] == [
        ("UHD", 3840, 2160),
        ("1920x1200", 1920, 1200),
        ("1920x1080", 1920, 1080),
        ("1366x768", 1366, 768),
        ("720x1280", 720, 1280),
    ]
