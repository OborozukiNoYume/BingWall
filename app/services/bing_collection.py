from __future__ import annotations

from datetime import UTC
from datetime import date
from datetime import datetime
import hashlib
import json
import logging
from pathlib import Path
import re
from typing import Protocol
from urllib.parse import parse_qs
from urllib.parse import urlparse

from app.domain.collection import BingImageMetadata
from app.domain.collection import CollectionRunSummary
from app.domain.collection import DownloadedImage
from app.repositories.collection_repository import CollectionRepository
from app.repositories.collection_repository import ResourceCreateInput
from app.repositories.collection_repository import TaskItemCreateInput
from app.repositories.collection_repository import WallpaperCreateInput
from app.repositories.file_storage import FileStorage

logger = logging.getLogger(__name__)

IMAGE_DIMENSION_PATTERN = re.compile(r"_(\d+)x(\d+)\.(?:jpg|jpeg|png|webp)$", re.IGNORECASE)
SAFE_PATH_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")


class BingClientProtocol(Protocol):
    def fetch_metadata(self, market_code: str, count: int) -> list[BingImageMetadata]: ...

    def download_image(self, image_url: str) -> DownloadedImage: ...


class BingCollectionService:
    def __init__(
        self,
        *,
        repository: CollectionRepository,
        storage: FileStorage,
        bing_client: BingClientProtocol,
        max_download_retries: int,
    ) -> None:
        self.repository = repository
        self.storage = storage
        self.bing_client = bing_client
        self.max_download_retries = max_download_retries

    def collect(
        self,
        *,
        market_code: str,
        count: int,
        trigger_type: str,
        triggered_by: str | None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> CollectionRunSummary:
        started_at_utc = utc_now_isoformat()
        request_snapshot_json = json.dumps(
            {
                "market_code": market_code,
                "count": count,
                "trigger_type": trigger_type,
            },
            ensure_ascii=True,
            sort_keys=True,
        )
        task_id = self.repository.create_collection_task(
            task_type=task_type_for_trigger(trigger_type),
            source_type="bing",
            trigger_type=trigger_type,
            triggered_by=triggered_by,
            request_snapshot_json=request_snapshot_json,
            created_at_utc=started_at_utc,
        )
        return self._run_collection(
            task_id=task_id,
            market_code=market_code,
            count=count,
            date_from=date_from,
            date_to=date_to,
        )

    def collect_existing_task(
        self,
        *,
        task_id: int,
        market_code: str,
        count: int,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> CollectionRunSummary:
        return self._run_collection(
            task_id=task_id,
            market_code=market_code,
            count=count,
            date_from=date_from,
            date_to=date_to,
        )

    def _run_collection(
        self,
        *,
        task_id: int,
        market_code: str,
        count: int,
        date_from: date | None,
        date_to: date | None,
    ) -> CollectionRunSummary:
        self.storage.ensure_directories()

        success_count = 0
        duplicate_count = 0
        failure_count = 0
        failure_reasons: list[str] = []

        try:
            metadata_items = self.bing_client.fetch_metadata(market_code, count)
            metadata_items = filter_metadata_items(
                metadata_items=metadata_items,
                date_from=date_from,
                date_to=date_to,
            )
            if not metadata_items:
                if date_from is not None and date_to is not None:
                    msg = "Bing 上游结果中没有命中请求日期范围的图片。"
                else:
                    msg = "Bing metadata response did not contain any images."
                raise RuntimeError(msg)

            for item in metadata_items:
                try:
                    outcome = self._collect_single_item(task_id=task_id, item=item)
                    if outcome == "succeeded":
                        success_count += 1
                    else:
                        duplicate_count += 1
                except Exception as exc:
                    failure_count += 1
                    failure_reason = str(exc)
                    failure_reasons.append(failure_reason)
                    self.repository.create_task_item(
                        TaskItemCreateInput(
                            task_id=task_id,
                            source_item_key=item.source_key,
                            action_name="collect_candidate",
                            result_status="failed",
                            dedupe_hit_type=None,
                            db_write_result="wallpaper_and_resource_created",
                            file_write_result="failed",
                            failure_reason=failure_reason,
                            occurred_at_utc=utc_now_isoformat(),
                        )
                    )
                    logger.exception("Failed to collect Bing wallpaper %s.", item.source_key)
        except Exception as exc:
            failure_count += 1
            failure_reasons.append(str(exc))
            logger.exception("Bing metadata collection failed for market %s.", market_code)

        task_status = task_status_from_counts(
            success_count=success_count,
            duplicate_count=duplicate_count,
            failure_count=failure_count,
        )
        error_summary = "; ".join(failure_reasons[:5]) if failure_reasons else None
        finished_at_utc = utc_now_isoformat()
        self.repository.finish_collection_task(
            task_id=task_id,
            task_status=task_status,
            success_count=success_count,
            duplicate_count=duplicate_count,
            failure_count=failure_count,
            error_summary=error_summary,
            finished_at_utc=finished_at_utc,
        )
        return CollectionRunSummary(
            task_id=task_id,
            task_status=task_status,
            success_count=success_count,
            duplicate_count=duplicate_count,
            failure_count=failure_count,
            error_summary=error_summary,
        )

    def _collect_single_item(self, *, task_id: int, item: BingImageMetadata) -> str:
        wallpaper_date = item.wallpaper_date.isoformat()
        existing_wallpaper = self.repository.find_wallpaper_by_business_key(
            source_type="bing",
            wallpaper_date=wallpaper_date,
            market_code=item.market_code,
        )
        if existing_wallpaper is not None:
            self.repository.create_task_item(
                TaskItemCreateInput(
                    task_id=task_id,
                    source_item_key=item.source_key,
                    action_name="dedupe_check",
                    result_status="duplicated",
                    dedupe_hit_type="business_key",
                    db_write_result="skipped_existing_wallpaper",
                    file_write_result=None,
                    failure_reason=None,
                    occurred_at_utc=utc_now_isoformat(),
                )
            )
            return "duplicated"

        existing_resource = self.repository.find_image_resource_by_source_url_hash(
            item.source_url_hash
        )
        if existing_resource is not None:
            self.repository.create_task_item(
                TaskItemCreateInput(
                    task_id=task_id,
                    source_item_key=item.source_key,
                    action_name="dedupe_check",
                    result_status="duplicated",
                    dedupe_hit_type="source_url_hash",
                    db_write_result="skipped_existing_resource",
                    file_write_result=None,
                    failure_reason=None,
                    occurred_at_utc=utc_now_isoformat(),
                )
            )
            return "duplicated"

        created_at_utc = utc_now_isoformat()
        wallpaper_id = self.repository.create_wallpaper(
            WallpaperCreateInput(
                source_type="bing",
                source_key=item.source_key,
                market_code=item.market_code,
                wallpaper_date=wallpaper_date,
                title=item.title,
                copyright_text=item.copyright_text,
                source_name=item.source_name,
                origin_page_url=item.origin_page_url,
                origin_image_url=item.origin_image_url,
                origin_width=item.origin_width,
                origin_height=item.origin_height,
                is_downloadable=item.is_downloadable,
                raw_extra_json=item.raw_extra_json,
                created_at_utc=created_at_utc,
            )
        )
        relative_path = build_relative_path(item=item)
        filename = Path(relative_path).name
        file_ext = Path(relative_path).suffix.lstrip(".").lower() or "jpg"
        resource_id = self.repository.create_image_resource(
            ResourceCreateInput(
                wallpaper_id=wallpaper_id,
                resource_type="original",
                storage_backend="local",
                relative_path=relative_path,
                filename=filename,
                file_ext=file_ext,
                mime_type=guess_mime_type(file_ext=file_ext, fallback=None),
                source_url=item.origin_image_url,
                source_url_hash=item.source_url_hash,
                created_at_utc=created_at_utc,
            )
        )

        self._download_and_store_resource(
            wallpaper_id=wallpaper_id,
            resource_id=resource_id,
            item=item,
            relative_path=relative_path,
        )
        self.repository.create_task_item(
            TaskItemCreateInput(
                task_id=task_id,
                source_item_key=item.source_key,
                action_name="collect_candidate",
                result_status="succeeded",
                dedupe_hit_type=None,
                db_write_result="wallpaper_and_resource_created",
                file_write_result="stored_in_public",
                failure_reason=None,
                occurred_at_utc=utc_now_isoformat(),
            )
        )
        return "succeeded"

    def _download_and_store_resource(
        self,
        *,
        wallpaper_id: int,
        resource_id: int,
        item: BingImageMetadata,
        relative_path: str,
    ) -> None:
        last_error: str | None = None
        for attempt in range(1, self.max_download_retries + 1):
            tmp_path = self.storage.tmp_path_for(relative_path)
            cleanup_path(tmp_path)
            try:
                downloaded = self.bing_client.download_image(item.origin_image_url)
                tmp_path.write_bytes(downloaded.content)
                validate_downloaded_image(downloaded.content)
                content_hash = hashlib.sha256(downloaded.content).hexdigest()
                mime_type = guess_mime_type(
                    file_ext=Path(relative_path).suffix.lstrip(".").lower(),
                    fallback=downloaded.mime_type,
                )
                self.storage.move_to_public(tmp_path=tmp_path, relative_path=relative_path)
                processed_at_utc = utc_now_isoformat()
                self.repository.mark_image_resource_ready(
                    resource_id=resource_id,
                    file_size_bytes=len(downloaded.content),
                    width=item.origin_width,
                    height=item.origin_height,
                    content_hash=content_hash,
                    downloaded_at_utc=processed_at_utc,
                    integrity_check_result="passed",
                    mime_type=mime_type,
                )
                self.repository.refresh_wallpaper_resource_status(
                    wallpaper_id=wallpaper_id,
                    processed_at_utc=processed_at_utc,
                )
                return
            except Exception as exc:
                last_error = f"download attempt {attempt} failed: {exc}"
                if tmp_path.exists():
                    self.storage.move_to_failed(tmp_path=tmp_path, relative_path=relative_path)
                logger.warning(
                    "Download attempt %s/%s failed for %s: %s",
                    attempt,
                    self.max_download_retries,
                    item.source_key,
                    exc,
                )

        if last_error is None:
            last_error = "download failed without a captured error"
        processed_at_utc = utc_now_isoformat()
        self.repository.mark_image_resource_failed(
            resource_id=resource_id,
            failure_reason=last_error,
            processed_at_utc=processed_at_utc,
        )
        self.repository.refresh_wallpaper_resource_status(
            wallpaper_id=wallpaper_id,
            processed_at_utc=processed_at_utc,
        )
        raise RuntimeError(last_error)


def build_relative_path(*, item: BingImageMetadata) -> str:
    safe_source_key = SAFE_PATH_PATTERN.sub("-", item.source_key.replace(":", "-")).strip("-")
    file_ext = extract_file_ext_from_source_url(item.origin_image_url)
    return (
        f"bing/{item.wallpaper_date.year:04d}/{item.wallpaper_date.month:02d}/"
        f"{item.market_code}/{safe_source_key}.{file_ext}"
    )


def cleanup_path(path: Path) -> None:
    if path.exists():
        path.unlink()


def guess_mime_type(*, file_ext: str, fallback: str | None) -> str:
    if fallback and fallback.startswith("image/"):
        return fallback
    return {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
    }.get(file_ext.lower(), "application/octet-stream")


def extract_file_ext_from_source_url(source_url: str) -> str:
    parsed_url = urlparse(source_url)
    query_id = parse_qs(parsed_url.query).get("id", [])
    candidates = [*query_id, parsed_url.path]
    for candidate in candidates:
        suffix = Path(candidate).suffix.lstrip(".").lower()
        if suffix:
            return suffix
    return "jpg"


def validate_downloaded_image(content: bytes) -> None:
    if not content:
        msg = "downloaded image is empty"
        raise ValueError(msg)
    if content.startswith(b"\xff\xd8\xff"):
        return
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return
    msg = "downloaded file does not have a supported image signature"
    raise ValueError(msg)


def task_type_for_trigger(trigger_type: str) -> str:
    if trigger_type == "cron":
        return "scheduled_collect"
    return "manual_collect"


def task_status_from_counts(*, success_count: int, duplicate_count: int, failure_count: int) -> str:
    if failure_count == 0:
        return "succeeded"
    if success_count > 0 or duplicate_count > 0:
        return "partially_failed"
    return "failed"


def utc_now_isoformat() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def filter_metadata_items(
    *,
    metadata_items: list[BingImageMetadata],
    date_from: date | None,
    date_to: date | None,
) -> list[BingImageMetadata]:
    if date_from is None or date_to is None:
        return metadata_items
    return [item for item in metadata_items if date_from <= item.wallpaper_date <= date_to]
