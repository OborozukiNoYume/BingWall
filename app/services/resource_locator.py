from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from urllib.parse import quote

from app.core.config import Settings

LOCAL_STORAGE_BACKEND = "local"
OSS_STORAGE_BACKEND = "oss"
SUPPORTED_STORAGE_BACKENDS = frozenset({LOCAL_STORAGE_BACKEND, OSS_STORAGE_BACKEND})


@dataclass(frozen=True)
class ResourceLocator:
    local_url_prefix: str = "/images"
    oss_public_base_url: str | None = None

    @classmethod
    def from_settings(cls, settings: Settings) -> ResourceLocator:
        oss_public_base_url = settings.storage_oss_public_base_url
        return cls(
            oss_public_base_url=(
                str(oss_public_base_url).rstrip("/") if oss_public_base_url is not None else None
            )
        )

    def build_url(self, *, storage_backend: str | None, relative_path: str | None) -> str | None:
        if relative_path is None:
            return None
        return self.build_required_url(
            storage_backend=storage_backend,
            relative_path=relative_path,
        )

    def build_required_url(self, *, storage_backend: str | None, relative_path: str) -> str:
        normalized_relative_path = normalize_relative_path(relative_path)
        backend = normalize_storage_backend(storage_backend)
        encoded_relative_path = quote(normalized_relative_path, safe="/-_.~")

        if backend == LOCAL_STORAGE_BACKEND:
            return f"{self.local_url_prefix.rstrip('/')}/{encoded_relative_path}"
        if self.oss_public_base_url is None:
            msg = "OSS public base URL is not configured."
            raise ValueError(msg)
        return f"{self.oss_public_base_url}/{encoded_relative_path}"


def normalize_storage_backend(storage_backend: str | None) -> str:
    normalized = (storage_backend or LOCAL_STORAGE_BACKEND).strip().lower()
    if normalized not in SUPPORTED_STORAGE_BACKENDS:
        msg = f"Unsupported storage backend: {storage_backend!r}"
        raise ValueError(msg)
    return normalized


def normalize_relative_path(relative_path: str) -> str:
    candidate = relative_path.strip().replace("\\", "/")
    if not candidate:
        raise ValueError("Resource relative path must not be empty.")

    path = PurePosixPath(candidate)
    if path.is_absolute():
        raise ValueError("Resource relative path must not be absolute.")

    normalized_parts = [part for part in path.parts if part not in {"", "."}]
    if not normalized_parts or any(part == ".." for part in normalized_parts):
        raise ValueError("Resource relative path must stay within the storage root.")

    return "/".join(normalized_parts)
