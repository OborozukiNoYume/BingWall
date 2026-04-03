from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC
from datetime import date
from datetime import datetime
import hashlib
import json
import logging
from pathlib import Path
import re
from time import sleep
from typing import Any
from urllib.error import HTTPError
from urllib.parse import parse_qsl
from urllib.parse import parse_qs
from urllib.parse import urlencode
from urllib.parse import urljoin
from urllib.parse import urlparse
from urllib.request import Request
from urllib.request import urlopen

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.domain.collection import BingImageMetadata
from app.domain.collection import CollectionRunSummary
from app.domain.collection import CollectedDownloadVariant
from app.domain.collection import DownloadedImage
from app.repositories.collection_repository import CollectionRepository
from app.repositories.file_storage import FileStorage
from app.services.bing_collection import BingCollectionService
from app.services.source_collection import build_source_relative_path
from app.services.source_collection import task_status_from_counts

logger = logging.getLogger(__name__)

BING_BASE_URL = "https://www.bing.com"
BING_METADATA_PATH = "/HPImageArchive.aspx"
BING_MAX_METADATA_DAYS = 8
IMAGE_ID_PATTERN = re.compile(r"(?:^|[?&])id=([^&]+)")
DIMENSION_PATTERN = re.compile(r"_(\d+)x(\d+)\.(?:jpg|jpeg|png|webp)$", re.IGNORECASE)
UHD_PATTERN = re.compile(r"_UHD\.(?:jpg|jpeg|png|webp)$", re.IGNORECASE)

BING_DOWNLOAD_VARIANT_CANDIDATES: tuple[tuple[str, int | None, int | None], ...] = (
    ("UHD", 3840, 2160),
    ("1920x1200", 1920, 1200),
    ("1920x1080", 1920, 1080),
    ("1366x768", 1366, 768),
    ("720x1280", 720, 1280),
)


class BingImageDownloadError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True, slots=True)
class BingMetadataQuery:
    idx: int
    n: int


class BingClient:
    def __init__(self, *, timeout_seconds: int) -> None:
        self.timeout_seconds = timeout_seconds

    def fetch_metadata(
        self,
        *,
        market_code: str,
        count: int,
        date_from: date | None,
        date_to: date | None,
    ) -> list[BingImageMetadata]:
        metadata_query = resolve_bing_metadata_query(
            count=count,
            date_from=date_from,
            date_to=date_to,
        )
        query = urlencode(
            {"format": "js", "idx": metadata_query.idx, "n": metadata_query.n, "mkt": market_code}
        )
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
        try:
            mime_type, content = read_binary_with_retry(
                request=request,
                timeout_seconds=self.timeout_seconds,
                attempts=2,
            )
        except HTTPError as exc:
            raise BingImageDownloadError(
                f"image request failed with HTTP {exc.code}: {image_url}",
                status_code=exc.code,
            ) from exc
        except RuntimeError as exc:
            raise BingImageDownloadError(str(exc), status_code=None) from exc
        return DownloadedImage(content=content, mime_type=mime_type)

    def _map_image_payload(self, *, market_code: str, payload: dict[str, Any]) -> BingImageMetadata:
        wallpaper_date = parse_bing_date(str(payload["startdate"]))
        origin_image_url = urljoin(BING_BASE_URL, str(payload["url"]))
        download_variants = build_download_variants(
            image_url=origin_image_url,
            urlbase=normalize_optional_text(payload.get("urlbase")),
            is_downloadable=bool(payload.get("wp")),
        )
        source_id = extract_source_id(str(payload.get("urlbase") or payload["url"]))
        source_key = f"bing:{market_code}:{wallpaper_date.isoformat()}:{source_id}"
        primary_variant = download_variants[0] if download_variants else None
        width, height = parse_dimensions_from_url(
            primary_variant.source_url if primary_variant is not None else origin_image_url
        )
        raw_payload = dict(payload)
        raw_payload["requested_market_code"] = market_code
        raw_payload["wallpaper_date"] = wallpaper_date.isoformat()
        raw_payload["published_at_utc"] = parse_bing_fullstartdate(
            normalize_optional_text(payload.get("fullstartdate"))
        )
        raw_payload["hd_image_url"] = (
            primary_variant.source_url if primary_variant else origin_image_url
        )
        raw_payload["portrait_image_url"] = find_portrait_image_url(
            download_variants=download_variants,
            urlbase=normalize_optional_text(payload.get("urlbase")),
            image_url=origin_image_url,
            is_downloadable=bool(payload.get("wp")),
        )
        raw_payload["download_variants"] = [
            {
                "variant_key": variant.variant_key,
                "source_url": variant.source_url,
                "width": variant.width,
                "height": variant.height,
            }
            for variant in download_variants
        ]
        raw_extra_json = json.dumps(raw_payload, ensure_ascii=False, sort_keys=True)
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
            subtitle=extract_bing_subtitle(payload),
            description=extract_bing_description(payload),
            location_text=extract_bing_location_text(payload),
            published_at_utc=parse_bing_fullstartdate(
                normalize_optional_text(payload.get("fullstartdate"))
            ),
            portrait_image_url=find_portrait_image_url(
                download_variants=download_variants,
                urlbase=normalize_optional_text(payload.get("urlbase")),
                image_url=origin_image_url,
                is_downloadable=bool(payload.get("wp")),
            ),
            download_variants=download_variants,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect Bing wallpapers into the BingWall database."
    )
    parser.add_argument("--market")
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--date-from")
    parser.add_argument("--date-to")
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

    if (args.date_from is None) != (args.date_to is None):
        raise RuntimeError("--date-from and --date-to must be provided together.")

    date_from: date | None = None
    date_to: date | None = None
    count = args.count
    if args.date_from is not None and args.date_to is not None:
        date_from = date.fromisoformat(str(args.date_from))
        date_to = date.fromisoformat(str(args.date_to))
        if date_to < date_from:
            raise RuntimeError("--date-to must be greater than or equal to --date-from.")
        count = (date_to - date_from).days + 1

    market_codes = resolve_collect_market_codes(
        requested_market=args.market,
        configured_markets=settings.collect_bing_markets,
    )

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
    market_summaries: list[tuple[str, CollectionRunSummary]] = []
    try:
        for market_code in market_codes:
            market_summaries.append(
                (
                    market_code,
                    service.collect(
                        market_code=market_code,
                        count=count,
                        trigger_type=args.trigger_type,
                        triggered_by=args.triggered_by,
                        date_from=date_from,
                        date_to=date_to,
                    ),
                )
            )
    finally:
        repository.close()

    print(
        json.dumps(
            build_collection_summary_payload(market_summaries=market_summaries),
            ensure_ascii=False,
            sort_keys=True,
        )
    )


def parse_bing_date(value: str) -> date:
    return datetime.strptime(value, "%Y%m%d").date()


def resolve_collect_market_codes(
    *,
    requested_market: str | None,
    configured_markets: tuple[str, ...],
) -> tuple[str, ...]:
    if requested_market is None:
        return configured_markets

    normalized_market = str(requested_market).strip()
    if not normalized_market:
        raise ValueError("--market must not be blank.")
    return (normalized_market,)


def build_collection_summary_payload(
    *,
    market_summaries: list[tuple[str, CollectionRunSummary]],
) -> dict[str, object]:
    if len(market_summaries) == 1:
        market_code, summary = market_summaries[0]
        return {
            "market_code": market_code,
            "task_id": summary.task_id,
            "task_status": summary.task_status,
            "success_count": summary.success_count,
            "duplicate_count": summary.duplicate_count,
            "failure_count": summary.failure_count,
            "error_summary": summary.error_summary,
        }

    success_count = sum(summary.success_count for _market_code, summary in market_summaries)
    duplicate_count = sum(summary.duplicate_count for _market_code, summary in market_summaries)
    failure_count = sum(summary.failure_count for _market_code, summary in market_summaries)
    error_summaries = [
        summary.error_summary
        for _market_code, summary in market_summaries
        if summary.error_summary is not None
    ]
    return {
        "task_ids": [summary.task_id for _market_code, summary in market_summaries],
        "task_status": task_status_from_counts(
            success_count=success_count,
            duplicate_count=duplicate_count,
            failure_count=failure_count,
        ),
        "success_count": success_count,
        "duplicate_count": duplicate_count,
        "failure_count": failure_count,
        "error_summary": "; ".join(error_summaries[:5]) if error_summaries else None,
        "market_count": len(market_summaries),
        "markets": [
            {
                "market_code": market_code,
                "task_id": summary.task_id,
                "task_status": summary.task_status,
                "success_count": summary.success_count,
                "duplicate_count": summary.duplicate_count,
                "failure_count": summary.failure_count,
                "error_summary": summary.error_summary,
            }
            for market_code, summary in market_summaries
        ],
    }


def resolve_bing_metadata_query(
    *,
    count: int,
    date_from: date | None,
    date_to: date | None,
    today_utc: date | None = None,
) -> BingMetadataQuery:
    if not 1 <= count <= BING_MAX_METADATA_DAYS:
        raise ValueError(
            f"Bing metadata count must be between 1 and {BING_MAX_METADATA_DAYS}."
        )

    if date_from is None and date_to is None:
        return BingMetadataQuery(idx=0, n=count)

    if date_from is None or date_to is None:
        raise ValueError("Bing metadata query requires both date_from and date_to.")
    if date_to < date_from:
        raise ValueError("Bing metadata query date_to must not be earlier than date_from.")

    today = today_utc or datetime.now(tz=UTC).date()
    idx = (today - date_to).days
    if idx < 0:
        raise ValueError("Bing metadata query does not support future dates.")

    requested_days = (date_to - date_from).days + 1
    if requested_days > BING_MAX_METADATA_DAYS:
        raise ValueError(
            f"Bing metadata query only supports the most recent {BING_MAX_METADATA_DAYS} days."
        )
    if idx + requested_days > BING_MAX_METADATA_DAYS:
        raise ValueError(
            f"Bing metadata query exceeds the most recent {BING_MAX_METADATA_DAYS}-day window."
        )
    return BingMetadataQuery(idx=idx, n=requested_days)


def parse_bing_fullstartdate(value: str | None) -> str | None:
    if not value:
        return None
    return datetime.strptime(value, "%Y%m%d%H%M").isoformat() + "Z"


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
    parsed_url = urlparse(image_url)
    candidates = [*parse_qs(parsed_url.query).get("id", []), parsed_url.path, image_url]
    for candidate in candidates:
        if UHD_PATTERN.search(candidate):
            return 3840, 2160
        match = DIMENSION_PATTERN.search(candidate)
        if match is not None:
            return int(match.group(1)), int(match.group(2))
    return None, None


def normalize_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def extract_bing_subtitle(payload: dict[str, Any]) -> str | None:
    return first_non_empty_text(
        payload.get("caption"),
        payload.get("bsTitle"),
        payload.get("headline"),
    )


def extract_bing_description(payload: dict[str, Any]) -> str | None:
    return first_non_empty_text(
        payload.get("description"),
        payload.get("desc"),
        payload.get("caption"),
        payload.get("copyrightonly"),
    )


def extract_bing_location_text(payload: dict[str, Any]) -> str | None:
    candidates = (
        normalize_optional_text(payload.get("copyrightonly")),
        normalize_optional_text(payload.get("copyright")),
    )
    for candidate in candidates:
        if not candidate:
            continue
        location_text = candidate.split("(", 1)[0].strip().rstrip(",")
        if location_text:
            return location_text
    return None


def first_non_empty_text(*values: Any) -> str | None:
    for value in values:
        text = normalize_optional_text(value)
        if text:
            return text
    return None


def build_bing_relative_path(item: BingImageMetadata) -> str:
    return build_source_relative_path(
        source_type="bing",
        market_code=item.market_code,
        wallpaper_date=item.wallpaper_date,
        source_key=item.source_key,
        origin_image_url=item.origin_image_url,
    )


def build_download_variants(
    *,
    image_url: str,
    urlbase: str | None,
    is_downloadable: bool,
) -> tuple[CollectedDownloadVariant, ...]:
    if not is_downloadable or not urlbase:
        return ()

    parsed_image_url = urlparse(image_url)
    file_ext = extract_file_ext_from_bing_image_url(image_url)
    passthrough_query = [
        (key, value)
        for key, value in parse_qsl(parsed_image_url.query, keep_blank_values=True)
        if key != "id"
    ]
    original_width, original_height = parse_dimensions_from_url(image_url)
    original_variant_key = (
        "UHD"
        if UHD_PATTERN.search(image_url)
        else f"{original_width}x{original_height}"
        if original_width is not None and original_height is not None
        else None
    )

    variants: list[CollectedDownloadVariant] = []
    seen_variant_keys: set[str] = set()
    for variant_key, width, height in BING_DOWNLOAD_VARIANT_CANDIDATES:
        if variant_key in seen_variant_keys:
            continue
        variants.append(
            CollectedDownloadVariant(
                variant_key=variant_key,
                source_url=build_variant_image_url(
                    urlbase=urlbase,
                    variant_key=variant_key,
                    file_ext=file_ext,
                    passthrough_query=passthrough_query,
                ),
                width=width,
                height=height,
            )
        )
        seen_variant_keys.add(variant_key)

    if original_variant_key is not None and original_variant_key not in seen_variant_keys:
        variants.append(
            CollectedDownloadVariant(
                variant_key=original_variant_key,
                source_url=image_url,
                width=original_width,
                height=original_height,
            )
        )
    return tuple(variants)


def find_portrait_image_url(
    *,
    download_variants: tuple[CollectedDownloadVariant, ...],
    urlbase: str | None,
    image_url: str,
    is_downloadable: bool,
) -> str | None:
    for variant in download_variants:
        if (
            variant.width is not None
            and variant.height is not None
            and variant.height > variant.width
        ):
            return variant.source_url
    if not is_downloadable or not urlbase:
        return None
    file_ext = extract_file_ext_from_bing_image_url(image_url)
    parsed_image_url = urlparse(image_url)
    passthrough_query = [
        (key, value)
        for key, value in parse_qsl(parsed_image_url.query, keep_blank_values=True)
        if key != "id"
    ]
    return build_variant_image_url(
        urlbase=urlbase,
        variant_key="720x1280",
        file_ext=file_ext,
        passthrough_query=passthrough_query,
    )


def build_variant_image_url(
    *,
    urlbase: str,
    variant_key: str,
    file_ext: str,
    passthrough_query: list[tuple[str, str]],
) -> str:
    suffix = f"_UHD.{file_ext}" if variant_key == "UHD" else f"_{variant_key}.{file_ext}"
    candidate = f"{urlbase}{suffix}"
    if passthrough_query:
        candidate = f"{candidate}&{urlencode(passthrough_query)}"
    return urljoin(BING_BASE_URL, candidate)


def extract_file_ext_from_bing_image_url(image_url: str) -> str:
    parsed_url = urlparse(image_url)
    query_id = parse_qs(parsed_url.query).get("id", [])
    for candidate in (*query_id, parsed_url.path):
        suffix = Path(candidate).suffix.lstrip(".").lower()
        if suffix:
            return suffix
    return "jpg"


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
