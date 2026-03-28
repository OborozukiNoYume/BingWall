from app.collectors.bing import build_download_variants


def test_build_download_variants_uses_exact_15_official_bing_resolutions() -> None:
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
        ("1280x768", 1280, 768),
        ("1280x720", 1280, 720),
        ("1024x768", 1024, 768),
        ("800x600", 800, 600),
        ("800x480", 800, 480),
        ("720x1280", 720, 1280),
        ("768x1280", 768, 1280),
        ("640x480", 640, 480),
        ("480x800", 480, 800),
        ("400x240", 400, 240),
        ("240x320", 240, 320),
    ]
