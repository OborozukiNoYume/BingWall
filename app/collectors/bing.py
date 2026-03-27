from __future__ import annotations

import argparse
from datetime import datetime
from datetime import date
import hashlib
import json
import logging
from pathlib import Path
import re
from time import sleep
from typing import Any
from urllib.parse import parse_qs
from urllib.parse import urlencode
from urllib.parse import urljoin
from urllib.parse import urlparse
from urllib.request import Request
from urllib.request import urlopen

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.domain.collection import BingImageMetadata
from app.domain.collection import DownloadedImage
from app.repositories.collection_repository import CollectionRepository
from app.repositories.file_storage import FileStorage
from app.services.bing_collection import BingCollectionService
from app.services.source_collection import build_source_relative_path

logger = logging.getLogger(__name__)

BING_BASE_URL = "https://www.bing.com"
BING_METADATA_PATH = "/HPImageArchive.aspx"
IMAGE_ID_PATTERN = re.compile(r"(?:^|[?&])id=([^&]+)")
DIMENSION_PATTERN = re.compile(r"_(\d+)x(\d+)\.(?:jpg|jpeg|png|webp)$", re.IGNORECASE)


class BingClient:
    def __init__(self, *, timeout_seconds: int) -> None:
        self.timeout_seconds = timeout_seconds

    def fetch_metadata(self, market_code: str, count: int) -> list[BingImageMetadata]:
        query = urlencode({"format": "js", "idx": 0, "n": count, "mkt": market_code})
        request = Request(
            url=f"{BING_BASE_URL}{BING_METADATA_PATH}?{query}",
            headers={"User-Agent": "BingWall/0.1"},
        )
        payload = read_json_with_retry(
            request=request,
            timeout_seconds=self.timeout_seconds,
            attempts=2,
        )

        images = payload.get("images")
        if not isinstance(images, list):
            msg = "Bing metadata response does not contain an images list."
            raise ValueError(msg)
        return [self._map_image_payload(market_code=market_code, payload=item) for item in images]

    def download_image(self, image_url: str) -> DownloadedImage:
        request = Request(url=image_url, headers={"User-Agent": "BingWall/0.1"})
        mime_type, content = read_binary_with_retry(
            request=request,
            timeout_seconds=self.timeout_seconds,
            attempts=2,
        )
        return DownloadedImage(content=content, mime_type=mime_type)

    def _map_image_payload(self, *, market_code: str, payload: dict[str, Any]) -> BingImageMetadata:
        wallpaper_date = parse_bing_date(str(payload["startdate"]))
        origin_image_url = urljoin(BING_BASE_URL, str(payload["url"]))
        source_id = extract_source_id(str(payload.get("urlbase") or payload["url"]))
        source_key = f"bing:{market_code}:{wallpaper_date.isoformat()}:{source_id}"
        width, height = parse_dimensions_from_url(origin_image_url)
        raw_extra_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return BingImageMetadata(
            market_code=market_code,
            wallpaper_date=wallpaper_date,
            source_key=source_key,
            title=normalize_optional_text(payload.get("title")),
            copyright_text=normalize_optional_text(payload.get("copyright")),
            origin_page_url=normalize_optional_text(payload.get("copyrightlink")),
            origin_image_url=origin_image_url,
            source_url_hash=hashlib.sha256(origin_image_url.encode("utf-8")).hexdigest(),
            is_downloadable=bool(payload.get("wp")),
            source_name="Bing",
            origin_width=width,
            origin_height=height,
            raw_extra_json=raw_extra_json,
        )


def parse_args() -> argparse.Namespace:
    settings = get_settings()
    parser = argparse.ArgumentParser(
        description="Collect Bing wallpapers into the BingWall database."
    )
    parser.add_argument("--market", default=settings.collect_bing_default_market)
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--trigger-type", default="manual", choices=["manual", "cron"])
    parser.add_argument("--triggered-by")
    return parser.parse_args()


def main() -> None:
    settings = get_settings()
    if not settings.collect_bing_enabled:
        msg = "Bing collection is disabled by configuration."
        raise RuntimeError(msg)

    args = parse_args()
    configure_logging(settings.log_level)

    repository = CollectionRepository(str(settings.database_path))
    storage = FileStorage(
        tmp_dir=settings.storage_tmp_dir,
        public_dir=settings.storage_public_dir,
        failed_dir=settings.storage_failed_dir,
    )
    service = BingCollectionService(
        repository=repository,
        storage=storage,
        bing_client=BingClient(timeout_seconds=settings.collect_bing_timeout_seconds),
        max_download_retries=settings.collect_bing_max_download_retries,
        auto_publish_enabled=settings.collect_auto_publish_enabled,
    )
    try:
        summary = service.collect(
            market_code=args.market,
            count=args.count,
            trigger_type=args.trigger_type,
            triggered_by=args.triggered_by,
        )
    finally:
        repository.close()

    print(
        json.dumps(
            {
                "task_id": summary.task_id,
                "task_status": summary.task_status,
                "success_count": summary.success_count,
                "duplicate_count": summary.duplicate_count,
                "failure_count": summary.failure_count,
                "error_summary": summary.error_summary,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


def parse_bing_date(value: str) -> date:
    return datetime.strptime(value, "%Y%m%d").date()


def extract_source_id(value: str) -> str:
    query_value = value
    if value.startswith("/"):
        query_value = value.partition("?")[2]
    parsed = parse_qs(query_value)
    if "id" in parsed and parsed["id"]:
        return parsed["id"][0]

    match = IMAGE_ID_PATTERN.search(value)
    if match is not None:
        return match.group(1)

    parsed_url = urlparse(value)
    if parsed_url.path:
        return Path(parsed_url.path).stem

    msg = f"Could not extract Bing source id from value: {value}"
    raise ValueError(msg)


def parse_dimensions_from_url(image_url: str) -> tuple[int | None, int | None]:
    match = DIMENSION_PATTERN.search(image_url)
    if match is None:
        return None, None
    return int(match.group(1)), int(match.group(2))


def normalize_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def build_bing_relative_path(item: BingImageMetadata) -> str:
    return build_source_relative_path(
        source_type="bing",
        market_code=item.market_code,
        wallpaper_date=item.wallpaper_date,
        source_key=item.source_key,
        origin_image_url=item.origin_image_url,
    )


def read_json_with_retry(
    *,
    request: Request,
    timeout_seconds: int,
    attempts: int,
) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("metadata response must be a JSON object")
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


if __name__ == "__main__":
    main()
