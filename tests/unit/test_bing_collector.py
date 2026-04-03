from datetime import date

import pytest

from app.collectors.bing import build_download_variants
from app.collectors.bing import build_collection_summary_payload
from app.collectors.bing import resolve_collect_market_codes
from app.collectors.bing import resolve_bing_metadata_query
from app.domain.collection import CollectionRunSummary


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


def test_resolve_bing_metadata_query_defaults_to_today_window() -> None:
    query = resolve_bing_metadata_query(
        count=5,
        date_from=None,
        date_to=None,
        today_utc=date(2026, 4, 3),
    )

    assert query.idx == 0
    assert query.n == 5


def test_resolve_bing_metadata_query_maps_single_past_date_to_idx() -> None:
    query = resolve_bing_metadata_query(
        count=1,
        date_from=date(2026, 4, 1),
        date_to=date(2026, 4, 1),
        today_utc=date(2026, 4, 3),
    )

    assert query.idx == 2
    assert query.n == 1


def test_resolve_bing_metadata_query_maps_date_range_to_idx_and_n() -> None:
    query = resolve_bing_metadata_query(
        count=3,
        date_from=date(2026, 4, 1),
        date_to=date(2026, 4, 3),
        today_utc=date(2026, 4, 3),
    )

    assert query.idx == 0
    assert query.n == 3


def test_resolve_bing_metadata_query_rejects_out_of_window_request() -> None:
    with pytest.raises(ValueError, match="most recent 8-day window"):
        resolve_bing_metadata_query(
            count=1,
            date_from=date(2026, 3, 26),
            date_to=date(2026, 3, 26),
            today_utc=date(2026, 4, 3),
        )


def test_resolve_collect_market_codes_defaults_to_configured_markets() -> None:
    markets = resolve_collect_market_codes(
        requested_market=None,
        configured_markets=(
            "zh-CN",
            "en-US",
            "ja-JP",
            "en-GB",
            "de-DE",
            "fr-FR",
            "en-CA",
            "en-AU",
        ),
    )

    assert markets == (
        "zh-CN",
        "en-US",
        "ja-JP",
        "en-GB",
        "de-DE",
        "fr-FR",
        "en-CA",
        "en-AU",
    )


def test_resolve_collect_market_codes_prefers_explicit_market() -> None:
    markets = resolve_collect_market_codes(
        requested_market="en-US",
        configured_markets=("zh-CN", "en-US"),
    )

    assert markets == ("en-US",)


def test_build_collection_summary_payload_aggregates_multiple_markets() -> None:
    payload = build_collection_summary_payload(
        market_summaries=[
            (
                "zh-CN",
                CollectionRunSummary(
                    task_id=1,
                    task_status="succeeded",
                    success_count=1,
                    duplicate_count=0,
                    failure_count=0,
                    error_summary=None,
                ),
            ),
            (
                "en-US",
                CollectionRunSummary(
                    task_id=2,
                    task_status="failed",
                    success_count=0,
                    duplicate_count=0,
                    failure_count=1,
                    error_summary="network error",
                ),
            ),
        ]
    )

    assert payload["market_count"] == 2
    assert payload["task_ids"] == [1, 2]
    assert payload["task_status"] == "partially_failed"
    assert payload["success_count"] == 1
    assert payload["failure_count"] == 1
    assert payload["error_summary"] == "network error"
