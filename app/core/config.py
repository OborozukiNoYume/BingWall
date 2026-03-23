from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AppEnvironment = Literal["development", "test", "production"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BINGWALL_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: AppEnvironment = "development"
    app_host: str
    app_port: int = Field(ge=1, le=65535)
    app_base_url: AnyHttpUrl
    database_path: Path
    storage_tmp_dir: Path
    storage_public_dir: Path
    storage_failed_dir: Path
    backup_dir: Path
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


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()


def load_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


def reset_settings_cache() -> None:
    get_settings.cache_clear()
