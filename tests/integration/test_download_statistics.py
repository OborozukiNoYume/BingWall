from __future__ import annotations

from datetime import UTC
from datetime import datetime
from datetime import timedelta
from pathlib import Path
import sqlite3

from tests.integration.test_admin_auth import build_client
from tests.integration.test_admin_auth import prepare_database
from tests.integration.test_admin_auth import seed_admin_user
from tests.integration.test_admin_content import login_admin
from tests.integration.test_public_api import seed_wallpaper


def test_admin_download_stats_returns_summary_top_content_and_trends(tmp_path: Path) -> None:
    database_path = prepare_database(tmp_path)
    seed_admin_user(
        database_path=database_path,
        username="admin",
        password="correct-password",
    )
    first_wallpaper_id = seed_wallpaper(
        database_path=database_path,
        wallpaper_date="2026-03-24",
        market_code="en-US",
        title="Popular Download",
        include_download_resource=True,
    )
    second_wallpaper_id = seed_wallpaper(
        database_path=database_path,
        wallpaper_date="2026-03-23",
        market_code="fr-FR",
        title="Less Popular Download",
        include_download_resource=True,
    )
    insert_download_event(
        database_path=database_path,
        wallpaper_id=first_wallpaper_id,
        result_status="redirected",
        occurred_at_utc=utc_days_ago(days=0, hour=10),
    )
    insert_download_event(
        database_path=database_path,
        wallpaper_id=first_wallpaper_id,
        result_status="redirected",
        occurred_at_utc=utc_days_ago(days=1, hour=11),
    )
    insert_download_event(
        database_path=database_path,
        wallpaper_id=second_wallpaper_id,
        result_status="blocked",
        occurred_at_utc=utc_days_ago(days=1, hour=12),
    )
    insert_download_event(
        database_path=database_path,
        wallpaper_id=second_wallpaper_id,
        result_status="degraded",
        occurred_at_utc=utc_days_ago(days=2, hour=13),
    )

    with build_client(tmp_path) as client:
        session_token = login_admin(client)
        response = client.get(
            "/api/admin/download-stats?days=7&top_limit=2",
            headers={"Authorization": f"Bearer {session_token}"},
        )

    payload = response.json()
    summary = payload["data"]["summary"]
    top_wallpapers = payload["data"]["top_wallpapers"]
    daily_trends = payload["data"]["daily_trends"]

    assert response.status_code == 200
    assert summary["total_events"] == 4
    assert summary["redirected_events"] == 2
    assert summary["blocked_events"] == 1
    assert summary["degraded_events"] == 1
    assert summary["unique_wallpapers"] == 2
    assert summary["unique_markets"] == 2
    assert summary["latest_occurred_at_utc"] == utc_days_ago(days=0, hour=10)

    assert [item["title"] for item in top_wallpapers] == ["Popular Download"]
    assert top_wallpapers[0]["download_count"] == 2

    trend_by_date = {item["trend_date"]: item for item in daily_trends}
    assert len(daily_trends) == 7
    assert trend_by_date[utc_days_ago(days=0, hour=10)[:10]]["redirected_events"] == 1
    assert trend_by_date[utc_days_ago(days=1, hour=11)[:10]]["total_events"] == 2
    assert trend_by_date[utc_days_ago(days=2, hour=13)[:10]]["degraded_events"] == 1


def insert_download_event(
    *,
    database_path: Path,
    wallpaper_id: int,
    result_status: str,
    occurred_at_utc: str,
) -> None:
    connection = sqlite3.connect(database_path)
    try:
        resource_id = connection.execute(
            """
            SELECT id
            FROM image_resources
            WHERE wallpaper_id = ?
              AND resource_type = 'download'
            LIMIT 1;
            """,
            (wallpaper_id,),
        ).fetchone()[0]
        market_code = connection.execute(
            "SELECT market_code FROM wallpapers WHERE id = ? LIMIT 1;",
            (wallpaper_id,),
        ).fetchone()[0]
        connection.execute(
            """
            INSERT INTO download_events (
                wallpaper_id,
                resource_id,
                request_id,
                market_code,
                download_channel,
                client_ip_hash,
                user_agent,
                result_status,
                redirect_url,
                occurred_at_utc,
                created_at_utc
            )
            VALUES (?, ?, ?, ?, 'public_detail', 'iphash', 'uahash', ?, ?, ?, ?);
            """,
            (
                wallpaper_id,
                resource_id,
                f"trace-{wallpaper_id}-{result_status}",
                market_code,
                result_status,
                None if result_status == "blocked" else f"/images/test/{wallpaper_id}.jpg",
                occurred_at_utc,
                occurred_at_utc,
            ),
        )
        connection.commit()
    finally:
        connection.close()


def utc_days_ago(*, days: int, hour: int) -> str:
    moment = datetime.now(tz=UTC).replace(hour=hour, minute=0, second=0, microsecond=0)
    return (moment - timedelta(days=days)).isoformat().replace("+00:00", "Z")
