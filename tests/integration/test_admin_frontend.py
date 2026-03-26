from __future__ import annotations

from pathlib import Path

from tests.integration.test_admin_auth import build_client
from tests.integration.test_admin_auth import prepare_database
from tests.integration.test_admin_auth import seed_admin_user
from tests.integration.test_public_api import seed_wallpaper


def test_admin_frontend_shell_routes_return_html_pages(tmp_path: Path) -> None:
    database_path = prepare_database(tmp_path)
    seed_admin_user(
        database_path=database_path,
        username="admin",
        password="correct-password",
    )
    wallpaper_id = seed_wallpaper(
        database_path=database_path,
        wallpaper_date="2026-03-24",
        market_code="en-US",
        title="Admin Frontend",
    )

    with build_client(tmp_path) as client:
        login_response = client.get("/admin/login")
        list_response = client.get("/admin/wallpapers?page=2&content_status=draft")
        detail_response = client.get(f"/admin/wallpapers/{wallpaper_id}")
        tags_response = client.get("/admin/tags?status=enabled")
        task_list_response = client.get("/admin/tasks?page=1&task_status=queued")
        task_detail_response = client.get("/admin/tasks/7")
        download_stats_response = client.get("/admin/download-stats?days=30&top_limit=10")
        logs_response = client.get("/admin/logs?task_id=7&error_type=failed")
        audit_response = client.get("/admin/audit-logs?target_type=wallpaper&target_id=1")

    assert login_response.status_code == 200
    assert "text/html" in login_response.headers["content-type"]
    assert 'data-page="admin-login"' in login_response.text
    assert 'src="/admin-assets/admin.js"' in login_response.text

    assert list_response.status_code == 200
    assert 'data-page="admin-wallpapers"' in list_response.text
    assert "内容管理" in list_response.text

    assert detail_response.status_code == 200
    assert 'data-page="admin-detail"' in detail_response.text
    assert f'data-wallpaper-id="{wallpaper_id}"' in detail_response.text

    assert tags_response.status_code == 200
    assert 'data-page="admin-tags"' in tags_response.text
    assert "标签管理" in tags_response.text

    assert task_list_response.status_code == 200
    assert 'data-page="admin-tasks"' in task_list_response.text
    assert "采集任务" in task_list_response.text

    assert task_detail_response.status_code == 200
    assert 'data-page="admin-task-detail"' in task_detail_response.text
    assert 'data-task-id="7"' in task_detail_response.text

    assert download_stats_response.status_code == 200
    assert 'data-page="admin-download-stats"' in download_stats_response.text
    assert "下载统计" in download_stats_response.text

    assert logs_response.status_code == 200
    assert 'data-page="admin-logs"' in logs_response.text
    assert "结构化日志" in logs_response.text

    assert audit_response.status_code == 200
    assert 'data-page="admin-audit"' in audit_response.text
    assert "审计记录" in audit_response.text


def test_admin_frontend_assets_only_reference_admin_api_contract(tmp_path: Path) -> None:
    prepare_database(tmp_path)

    with build_client(tmp_path) as client:
        js_response = client.get("/admin-assets/admin.js")
        css_response = client.get("/admin-assets/admin.css")

    assert js_response.status_code == 200
    assert "/api/admin/auth/login" in js_response.text
    assert "/api/admin/auth/logout" in js_response.text
    assert "/api/admin/wallpapers" in js_response.text
    assert "/api/admin/wallpapers/" in js_response.text
    assert "/api/admin/tags" in js_response.text
    assert "/api/admin/collection-tasks" in js_response.text
    assert "/api/admin/download-stats" in js_response.text
    assert "/api/admin/logs" in js_response.text
    assert "/api/admin/audit-logs" in js_response.text
    assert "逻辑删除" in js_response.text
    assert "标签管理" in js_response.text
    assert "下载统计" in js_response.text
    assert "sqlite" not in js_response.text.lower()

    assert css_response.status_code == 200
    assert ".admin-shell" in css_response.text
    assert ".detail-grid" in css_response.text
    assert ".stats-grid" in css_response.text
    assert ".tag-chip-grid" in css_response.text
