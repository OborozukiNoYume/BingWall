import os

from fastapi.testclient import TestClient

from app.core.config import reset_settings_cache
from app.main import create_app
from tests.conftest import clear_bingwall_env


def set_valid_env() -> None:
    os.environ["BINGWALL_APP_ENV"] = "test"
    os.environ["BINGWALL_APP_HOST"] = "127.0.0.1"
    os.environ["BINGWALL_APP_PORT"] = "8000"
    os.environ["BINGWALL_APP_BASE_URL"] = "http://127.0.0.1:8000"
    os.environ["BINGWALL_DATABASE_PATH"] = "./var/data/bingwall.sqlite3"
    os.environ["BINGWALL_STORAGE_TMP_DIR"] = "./var/images/tmp"
    os.environ["BINGWALL_STORAGE_PUBLIC_DIR"] = "./var/images/public"
    os.environ["BINGWALL_STORAGE_FAILED_DIR"] = "./var/images/failed"
    os.environ["BINGWALL_BACKUP_DIR"] = "./var/backups"
    os.environ["BINGWALL_SECURITY_SESSION_SECRET"] = "0123456789abcdef0123456789abcdef"
    os.environ["BINGWALL_SECURITY_SESSION_TTL_HOURS"] = "12"
    os.environ["BINGWALL_LOG_LEVEL"] = "INFO"


def test_live_health_endpoint_returns_ok() -> None:
    clear_bingwall_env()
    set_valid_env()
    reset_settings_cache()

    client = TestClient(create_app())
    response = client.get("/api/health/live")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.headers["X-Trace-Id"]

    clear_bingwall_env()
