from __future__ import annotations

import argparse
from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta
import hashlib
import json
from time import sleep
from typing import Any
from typing import Protocol
from urllib.parse import urlencode
from urllib.request import Request
from urllib.request import urlopen

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.domain.collection import CollectedImageMetadata
from app.domain.collection import CollectionRunSummary
from app.domain.collection import DownloadedImage
from app.repositories.collection_repository import CollectionRepository
from app.repositories.file_storage import FileStorage
from app.services.source_collection import SourceCollectionService
from app.services.source_collection import build_source_relative_path

NASA_APOD_BASE_URL = "https://api.nasa.gov/planetary/apod"


class NasaApodClient:
    def __init__(self, *, api_key: str, timeout_seconds: int) -> None:
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def fetch_metadata(
        self,
        *,
        market_code: str,
        count: int,
        date_from: date | None,
        date_to: date | None,
    ) -> list[CollectedImageMetadata]:
        del market_code
        start_date, end_date = resolve_date_window(
            count=count, date_from=date_from, date_to=date_to
        )
        query = urlencode({
            "api_key": self.api_key,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        })
        request = Request(
            url=f"{NASA_APOD_BASE_URL}?{query}",
            headers={"User-Agent": "BingWall/0.1"},
        )
        payload = read_json_with_retry(
            request=request,
            timeout_seconds=self.timeout_seconds,
            attempts=2,
        )
        items = payload if isinstance(payload, list) else [payload]
        metadata: list[CollectedImageMetadata] = []
        for item in items:
            if str(item.get("media_type")) != "image":
                continue
            metadata.append(self._map_item_payload(item))
        metadata.sort(key=lambda item: item.wallpaper_date, reverse=True)
        return metadata[:count]

    def download_image(self, image_url: str) -> DownloadedImage:
        request = Request(url=image_url, headers={"User-Agent": "BingWall/0.1"})
        mime_type, content = read_binary_with_retry(
            request=request,
            timeout_seconds=self.timeout_seconds,
            attempts=2,
        )
        return DownloadedImage(content=content, mime_type=mime_type)

    def _map_item_payload(self, payload: dict[str, Any]) -> CollectedImageMetadata:
        wallpaper_date = date.fromisoformat(str(payload["date"]))
        origin_image_url = str(payload.get("hdurl") or payload["url"])
        title = normalize_optional_text(payload.get("title"))
        source_slug = slugify(title or wallpaper_date.isoformat())
        source_key = f"nasa_apod:global:{wallpaper_date.isoformat()}:{source_slug}"
        raw_extra_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return CollectedImageMetadata(
            market_code="global",
            wallpaper_date=wallpaper_date,
            source_key=source_key,
            title=title,
            copyright_text=normalize_optional_text(payload.get("copyright")),
            origin_page_url=None,
            origin_image_url=origin_image_url,
            source_url_hash=hashlib.sha256(origin_image_url.encode("utf-8")).hexdigest(),
            is_downloadable=True,
            source_name="NASA APOD",
            origin_width=None,
            origin_height=None,
            raw_extra_json=raw_extra_json,
        )


class NasaApodSourceAdapter:
    source_type = "nasa_apod"
    display_name = "NASA APOD"

    def __init__(self, *, client: NasaApodClientProtocol) -> None:
        self.client = client

    def fetch_metadata(
        self,
        *,
        market_code: str,
        count: int,
        date_from: date | None,
        date_to: date | None,
    ) -> list[CollectedImageMetadata]:
        return self.client.fetch_metadata(
            market_code=market_code,
            count=count,
            date_from=date_from,
            date_to=date_to,
        )

    def download_image(self, image_url: str) -> DownloadedImage:
        return self.client.download_image(image_url)

    def build_relative_path(self, item: CollectedImageMetadata) -> str:
        return build_source_relative_path(
            source_type=self.source_type,
            market_code=item.market_code,
            wallpaper_date=item.wallpaper_date,
            source_key=item.source_key,
            origin_image_url=item.origin_image_url,
        )


class NasaApodClientProtocol(Protocol):
    def fetch_metadata(
        self,
        *,
        market_code: str,
        count: int,
        date_from: date | None,
        date_to: date | None,
    ) -> list[CollectedImageMetadata]: ...

    def download_image(self, image_url: str) -> DownloadedImage: ...


def parse_args() -> argparse.Namespace:
    settings = get_settings()
    today_utc = datetime.now(tz=UTC).date()
    parser = argparse.ArgumentParser(
        description="Collect NASA APOD images into the BingWall database."
    )
    parser.add_argument("--market", default=settings.collect_nasa_apod_default_market)
    parser.add_argument("--date-from", default=today_utc.isoformat())
    parser.add_argument("--date-to", default=today_utc.isoformat())
    parser.add_argument("--trigger-type", default="manual", choices=["manual", "cron"])
    parser.add_argument("--triggered-by")
    return parser.parse_args()


def main() -> None:
    settings = get_settings()
    if not settings.collect_nasa_apod_enabled:
        raise RuntimeError("NASA APOD collection is disabled by configuration.")

    args = parse_args()
    configure_logging(settings.log_level)

    date_from = date.fromisoformat(str(args.date_from))
    date_to = date.fromisoformat(str(args.date_to))
    count = max((date_to - date_from).days + 1, 1)
    repository = CollectionRepository(str(settings.database_path))
    storage = FileStorage(
        tmp_dir=settings.storage_tmp_dir,
        public_dir=settings.storage_public_dir,
        failed_dir=settings.storage_failed_dir,
    )
    service = SourceCollectionService(
        repository=repository,
        storage=storage,
        adapter=NasaApodSourceAdapter(
            client=NasaApodClient(
                api_key=settings.collect_nasa_apod_api_key.get_secret_value(),
                timeout_seconds=settings.collect_nasa_apod_timeout_seconds,
            )
        ),
        max_download_retries=settings.collect_nasa_apod_max_download_retries,
        auto_publish_enabled=settings.collect_auto_publish_enabled,
    )
    try:
        summary = service.collect(
            market_code=str(args.market),
            count=count,
            trigger_type=str(args.trigger_type),
            triggered_by=args.triggered_by,
            date_from=date_from,
            date_to=date_to,
        )
    finally:
        repository.close()

    print(json.dumps(build_summary_payload(summary), ensure_ascii=False, sort_keys=True))


def resolve_date_window(
    *,
    count: int,
    date_from: date | None,
    date_to: date | None,
) -> tuple[date, date]:
    if date_from is not None and date_to is not None:
        return date_from, date_to
    end_date = datetime.now(tz=UTC).date()
    start_date = end_date - timedelta(days=max(count - 1, 0))
    return start_date, end_date


def normalize_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def slugify(value: str) -> str:
    normalized = [character.lower() if character.isalnum() else "-" for character in value.strip()]
    slug = "".join(normalized).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "apod"


def read_json_with_retry(
    *,
    request: Request,
    timeout_seconds: int,
    attempts: int,
) -> dict[str, Any] | list[dict[str, Any]]:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if not isinstance(payload, dict | list):
                raise ValueError("metadata response must be a JSON object or list")
            return payload
        except Exception as exc:
            last_error = exc
            if attempt >= attempts:
                break
            sleep(0.5 * attempt)
    if last_error is None:
        raise RuntimeError("metadata request failed without a captured error")
    raise RuntimeError(
        f"metadata request failed after {attempts} attempts: {last_error}"
    ) from last_error


def read_binary_with_retry(
    *,
    request: Request,
    timeout_seconds: int,
    attempts: int,
) -> tuple[str | None, bytes]:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                return response.headers.get_content_type(), response.read()
        except Exception as exc:
            last_error = exc
            if attempt >= attempts:
                break
            sleep(0.5 * attempt)
    if last_error is None:
        raise RuntimeError("binary request failed without a captured error")
    raise RuntimeError(
        f"binary request failed after {attempts} attempts: {last_error}"
    ) from last_error


def build_summary_payload(summary: CollectionRunSummary) -> dict[str, object]:
    return {
        "task_id": summary.task_id,
        "task_status": summary.task_status,
        "success_count": summary.success_count,
        "duplicate_count": summary.duplicate_count,
        "failure_count": summary.failure_count,
        "error_summary": summary.error_summary,
    }


if __name__ == "__main__":
    main()
