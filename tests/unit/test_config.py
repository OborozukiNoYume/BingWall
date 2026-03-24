import os

import pytest
from pydantic import ValidationError

from app.core.config import load_settings, reset_settings_cache
from tests.conftest import clear_bingwall_env


def set_valid_env() -> None:
    os.environ["BINGWALL_APP_ENV"] = "development"
    os.environ["BINGWALL_APP_HOST"] = "127.0.0.1"
    os.environ["BINGWALL_APP_PORT"] = "8000"
    os.environ["BINGWALL_APP_BASE_URL"] = "http://127.0.0.1:8000"
    os.environ["BINGWALL_DATABASE_PATH"] = "./var/data/bingwall.sqlite3"
    os.environ["BINGWALL_STORAGE_TMP_DIR"] = "./var/images/tmp"
    os.environ["BINGWALL_STORAGE_PUBLIC_DIR"] = "./var/images/public"
    os.environ["BINGWALL_STORAGE_FAILED_DIR"] = "./var/images/failed"
    os.environ["BINGWALL_BACKUP_DIR"] = "./var/backups"
    os.environ["BINGWALL_COLLECT_BING_ENABLED"] = "true"
    os.environ["BINGWALL_COLLECT_BING_DEFAULT_MARKET"] = "en-US"
    os.environ["BINGWALL_COLLECT_BING_TIMEOUT_SECONDS"] = "10"
    os.environ["BINGWALL_COLLECT_BING_MAX_DOWNLOAD_RETRIES"] = "3"
    os.environ["BINGWALL_SECURITY_SESSION_SECRET"] = "0123456789abcdef0123456789abcdef"
    os.environ["BINGWALL_SECURITY_SESSION_TTL_HOURS"] = "12"
    os.environ["BINGWALL_LOG_LEVEL"] = "INFO"


def test_settings_require_key_configuration() -> None:
    clear_bingwall_env()
    reset_settings_cache()

    with pytest.raises(ValidationError):
        load_settings()


def test_settings_validate_session_secret_length() -> None:
    clear_bingwall_env()
    set_valid_env()
    os.environ["BINGWALL_SECURITY_SESSION_SECRET"] = "too-short"
    reset_settings_cache()

    with pytest.raises(ValidationError):
        load_settings()


def test_settings_load_valid_configuration() -> None:
    clear_bingwall_env()
    set_valid_env()
    reset_settings_cache()

    settings = load_settings()

    assert settings.app_host == "127.0.0.1"
    assert settings.app_port == 8000
    assert settings.collect_bing_default_market == "en-US"
    assert settings.collect_bing_max_download_retries == 3
    assert settings.security_session_ttl_hours == 12

    clear_bingwall_env()
