from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AppEnvironment = Literal["development", "test", "production"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

SETTINGS_MODEL_CONFIG = SettingsConfigDict(
    env_prefix="BINGWALL_",
    env_file=".env",
    env_file_encoding="utf-8",
    extra="ignore",
)


class Settings(BaseSettings):
    model_config = SETTINGS_MODEL_CONFIG

    app_env: AppEnvironment = "development"
    app_host: str
    app_port: int = Field(ge=1, le=65535)
    app_base_url: AnyHttpUrl
    site_name: str = Field(default="BingWall", min_length=1, max_length=100)
    site_description: str = Field(default="Bing 壁纸图片服务", min_length=1, max_length=200)
    database_path: Path
    storage_tmp_dir: Path
    storage_public_dir: Path
    storage_failed_dir: Path
    storage_oss_public_base_url: AnyHttpUrl | None = None
    backup_dir: Path
    collect_bing_enabled: bool = True
    collect_bing_default_market: str = Field(default="en-US", min_length=2)
    collect_bing_timeout_seconds: int = Field(default=10, gt=0, le=120)
    collect_bing_max_download_retries: int = Field(default=3, ge=1, le=10)
    collect_nasa_apod_enabled: bool = True
    collect_nasa_apod_default_market: str = Field(default="global", min_length=2)
    collect_nasa_apod_api_key: SecretStr = Field(default=SecretStr("DEMO_KEY"))
    collect_nasa_apod_timeout_seconds: int = Field(default=10, gt=0, le=120)
    collect_nasa_apod_max_download_retries: int = Field(default=3, ge=1, le=10)
    security_session_secret: SecretStr
    security_session_ttl_hours: int = Field(gt=0, le=24)
    log_level: LogLevel = "INFO"

    @field_validator("security_session_secret")
    @classmethod
    def validate_session_secret(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 32:
            msg = "BINGWALL_SECURITY_SESSION_SECRET must be at least 32 characters long."
            raise ValueError(msg)
        return value


class BootstrapAdminSettings(BaseSettings):
    model_config = SETTINGS_MODEL_CONFIG

    security_bootstrap_admin_username: str | None = Field(default=None, max_length=100)
    security_bootstrap_admin_password: SecretStr | None = None

    @field_validator("security_bootstrap_admin_username")
    @classmethod
    def validate_bootstrap_admin_username(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            msg = "BINGWALL_SECURITY_BOOTSTRAP_ADMIN_USERNAME must not be blank."
            raise ValueError(msg)
        return normalized

    @field_validator("security_bootstrap_admin_password")
    @classmethod
    def validate_bootstrap_admin_password(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None:
            return None
        normalized = value.get_secret_value().strip()
        if not normalized:
            msg = "BINGWALL_SECURITY_BOOTSTRAP_ADMIN_PASSWORD must not be blank."
            raise ValueError(msg)
        if len(normalized) < 12:
            msg = "BINGWALL_SECURITY_BOOTSTRAP_ADMIN_PASSWORD must be at least 12 characters long."
            raise ValueError(msg)
        return SecretStr(normalized)

    @model_validator(mode="after")
    def validate_bootstrap_admin_pair(self) -> "BootstrapAdminSettings":
        has_username = self.security_bootstrap_admin_username is not None
        has_password = self.security_bootstrap_admin_password is not None
        if has_username != has_password:
            msg = (
                "BINGWALL_SECURITY_BOOTSTRAP_ADMIN_USERNAME and "
                "BINGWALL_SECURITY_BOOTSTRAP_ADMIN_PASSWORD must be provided together."
            )
            raise ValueError(msg)
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()


def load_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


def load_bootstrap_admin_settings() -> BootstrapAdminSettings:
    return BootstrapAdminSettings()


def reset_settings_cache() -> None:
    get_settings.cache_clear()
