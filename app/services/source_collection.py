from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta
import hashlib
import json
import logging
from pathlib import Path
from typing import Protocol
from typing import cast
from urllib.parse import parse_qs
from urllib.parse import urlparse

from app.domain.collection import CollectedImageMetadata
from app.domain.collection import CollectionRunSummary
from app.domain.collection import DownloadedImage
from app.domain.collection_sources import COLLECTION_SOURCE_MAX_MANUAL_DAYS
from app.domain.collection_sources import CollectionSourceType
from app.domain.resource_variants import RESOURCE_TYPE_DOWNLOAD
from app.domain.resource_variants import RESOURCE_TYPE_ORIGINAL
from app.domain.resource_variants import RESOURCE_TYPE_PREVIEW
from app.domain.resource_variants import RESOURCE_TYPE_THUMBNAIL
from app.domain.resource_variants import ResourceType
from app.repositories.collection_repository import CollectionRepository
from app.repositories.collection_repository import ResourceCreateInput
from app.repositories.collection_repository import TaskItemCreateInput
from app.repositories.collection_repository import WallpaperLocalizationUpsertInput
from app.repositories.collection_repository import WallpaperCreateInput
from app.repositories.file_storage import FileStorage
from app.services.image_variants import LoadedImage
from app.services.image_variants import calculate_variant_dimensions
from app.services.image_variants import generate_variant_image
from app.services.image_variants import load_image_bytes
from app.services.resource_paths import build_resource_relative_path
from app.services.resource_paths import resolve_resource_path_key

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class VariantResourceRecord:
    resource_id: int
    resource_type: ResourceType
    relative_path: str
    variant_key: str = ""


@dataclass(frozen=True, slots=True)
class DownloadedVariantRecord:
    variant_key: str
    source_url: str
    downloaded: DownloadedImage
    loaded_image: LoadedImage


class CollectionSourceAdapter(Protocol):
    source_type: str
    display_name: str

    def fetch_metadata(
        self,
        *,
        market_code: str,
        count: int,
        date_from: date | None,
        date_to: date | None,
    ) -> list[CollectedImageMetadata]: ...

    def download_image(self, image_url: str) -> DownloadedImage: ...

    def is_missing_resource_error(self, exc: Exception) -> bool: ...

    def build_relative_path(self, item: CollectedImageMetadata) -> str: ...


class SourceCollectionService:
    def __init__(
        self,
        *,
        repository: CollectionRepository,
        storage: FileStorage,
        adapter: CollectionSourceAdapter,
        max_download_retries: int,
        auto_publish_enabled: bool = True,
    ) -> None:
        self.repository = repository
        self.storage = storage
        self.adapter = adapter
        self.max_download_retries = max_download_retries
        self.auto_publish_enabled = auto_publish_enabled

    def collect(
        self,
        *,
        market_code: str,
        count: int,
        trigger_type: str,
        triggered_by: str | None,
        date_from: date | None = None,
        date_to: date | None = None,
        latest_available_fallback_days: int | None = None,
    ) -> CollectionRunSummary:
        fallback_days = latest_available_fallback_days
        if fallback_days is None and trigger_type == "cron":
            fallback_days = COLLECTION_SOURCE_MAX_MANUAL_DAYS[
                cast(CollectionSourceType, self.adapter.source_type)
            ]
        started_at_utc = utc_now_isoformat()
        request_snapshot_json = json.dumps(
            {
                "market_code": market_code,
                "count": count,
                "trigger_type": trigger_type,
                "date_from": date_to_isoformat(date_from),
                "date_to": date_to_isoformat(date_to),
            },
            ensure_ascii=True,
            sort_keys=True,
        )
        task_id = self.repository.create_collection_task(
            task_type=task_type_for_trigger(trigger_type),
            source_type=self.adapter.source_type,
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
            latest_available_fallback_days=fallback_days,
        )

    def collect_existing_task(
        self,
        *,
        task_id: int,
        market_code: str,
        count: int,
        date_from: date | None = None,
        date_to: date | None = None,
        latest_available_fallback_days: int | None = None,
    ) -> CollectionRunSummary:
        return self._run_collection(
            task_id=task_id,
            market_code=market_code,
            count=count,
            date_from=date_from,
            date_to=date_to,
            latest_available_fallback_days=latest_available_fallback_days,
        )

    def _run_collection(
        self,
        *,
        task_id: int,
        market_code: str,
        count: int,
        date_from: date | None,
        date_to: date | None,
        latest_available_fallback_days: int | None,
    ) -> CollectionRunSummary:
        self.storage.ensure_directories()

        success_count = 0
        duplicate_count = 0
        failure_count = 0
        failure_reasons: list[str] = []

        try:
            fetch_date_from, fetch_date_to = resolve_fetch_date_window(
                date_from=date_from,
                date_to=date_to,
                latest_available_fallback_days=latest_available_fallback_days,
            )
            fetched_metadata_items = self.adapter.fetch_metadata(
                market_code=market_code,
                count=count,
                date_from=fetch_date_from,
                date_to=fetch_date_to,
            )
            metadata_items, fallback_date = select_metadata_items_for_collection(
                metadata_items=fetched_metadata_items,
                date_from=date_from,
                date_to=date_to,
                latest_available_fallback_days=latest_available_fallback_days,
            )
            if fallback_date is not None and date_from is not None:
                fallback_message = (
                    f"{self.adapter.display_name} 定时采集未命中请求日期 {date_from.isoformat()}，"
                    f"已回退到最近可用日期 {fallback_date.isoformat()}。"
                )
                self.repository.create_task_item(
                    TaskItemCreateInput(
                        task_id=task_id,
                        source_item_key=None,
                        action_name="resolve_date_fallback",
                        result_status="succeeded",
                        dedupe_hit_type=None,
                        db_write_result="used_latest_available_date",
                        file_write_result=None,
                        failure_reason=fallback_message,
                        occurred_at_utc=utc_now_isoformat(),
                    )
                )
                logger.warning(fallback_message)
            if not metadata_items:
                if date_from is not None and date_to is not None:
                    msg = f"{self.adapter.display_name} 上游结果中没有命中请求日期范围的图片。"
                else:
                    msg = (
                        f"{self.adapter.display_name} metadata response did not contain any images."
                    )
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
                    logger.exception(
                        "Failed to collect %s wallpaper %s.",
                        self.adapter.source_type,
                        item.source_key,
                    )
        except Exception as exc:
            failure_count += 1
            failure_reason = str(exc)
            failure_reasons.append(failure_reason)
            self.repository.create_task_item(
                TaskItemCreateInput(
                    task_id=task_id,
                    source_item_key=None,
                    action_name="fetch_metadata",
                    result_status="failed",
                    dedupe_hit_type=None,
                    db_write_result=None,
                    file_write_result=None,
                    failure_reason=failure_reason,
                    occurred_at_utc=utc_now_isoformat(),
                )
            )
            logger.exception(
                "%s metadata collection failed for market %s.",
                self.adapter.display_name,
                market_code,
            )

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

    def _collect_single_item(self, *, task_id: int, item: CollectedImageMetadata) -> str:
        wallpaper_date = item.wallpaper_date.isoformat()
        created_at_utc = utc_now_isoformat()
        wallpaper_input = self._build_wallpaper_create_input(
            item=item,
            wallpaper_date=wallpaper_date,
            created_at_utc=created_at_utc,
        )
        canonical_key = item.canonical_key or item.source_key
        existing_wallpaper = self.repository.find_wallpaper_by_canonical_key(
            source_type=self.adapter.source_type,
            canonical_key=canonical_key,
        )
        if existing_wallpaper is not None:
            existing_wallpaper_id = int(existing_wallpaper["id"])
            existing_localization = self.repository.get_wallpaper_localization(
                wallpaper_id=existing_wallpaper_id,
                market_code=item.market_code,
            )
            self.repository.update_wallpaper_metadata(
                wallpaper_id=existing_wallpaper_id,
                item=wallpaper_input,
                updated_at_utc=created_at_utc,
            )
            self.repository.upsert_wallpaper_localization(
                self._build_wallpaper_localization_input(
                    wallpaper_id=existing_wallpaper_id,
                    item=item,
                    created_at_utc=created_at_utc,
                )
            )
            needs_resume, resume_reason = self._wallpaper_needs_resume(
                wallpaper_id=existing_wallpaper_id
            )
            if not needs_resume:
                self.repository.create_task_item(
                    TaskItemCreateInput(
                        task_id=task_id,
                        source_item_key=item.source_key,
                        action_name=(
                            "attach_localization"
                            if existing_localization is None
                            else "dedupe_check"
                        ),
                        result_status="succeeded" if existing_localization is None else "duplicated",
                        dedupe_hit_type="canonical_key",
                        db_write_result=(
                            "created_wallpaper_localization"
                            if existing_localization is None
                            else "updated_existing_localization"
                        ),
                        file_write_result=None,
                        failure_reason=None,
                        occurred_at_utc=utc_now_isoformat(),
                    )
                )
                return "succeeded" if existing_localization is None else "duplicated"

            self._prepare_wallpaper_resume(
                wallpaper_id=existing_wallpaper_id,
                resume_reason=resume_reason,
            )
            self.repository.create_task_item(
                TaskItemCreateInput(
                    task_id=task_id,
                    source_item_key=item.source_key,
                    action_name="repair_incomplete_wallpaper",
                    result_status="succeeded",
                    dedupe_hit_type=None,
                    db_write_result="resume_existing_wallpaper_resources",
                    file_write_result=None,
                    failure_reason=resume_reason,
                    occurred_at_utc=utc_now_isoformat(),
                )
            )
            wallpaper_id = existing_wallpaper_id
        else:
            existing_resource = self.repository.find_image_resource_by_source_url_hash_in_scope(
                source_url_hash=item.source_url_hash,
                source_type=self.adapter.source_type,
                market_code=item.market_code,
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

            wallpaper_id = self.repository.create_wallpaper(wallpaper_input)
            self.repository.upsert_wallpaper_localization(
                self._build_wallpaper_localization_input(
                    wallpaper_id=wallpaper_id,
                    item=item,
                    created_at_utc=created_at_utc,
                )
            )
        relative_path = self.adapter.build_relative_path(item)
        filename = Path(relative_path).name
        file_ext = Path(relative_path).suffix.lstrip(".").lower() or "jpg"
        resource_id = self.repository.create_image_resource(
            ResourceCreateInput(
                wallpaper_id=wallpaper_id,
                resource_type=RESOURCE_TYPE_ORIGINAL,
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
            original_resource_id=resource_id,
            task_id=task_id,
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

    def _build_wallpaper_create_input(
        self,
        *,
        item: CollectedImageMetadata,
        wallpaper_date: str,
        created_at_utc: str,
    ) -> WallpaperCreateInput:
        return WallpaperCreateInput(
            source_type=self.adapter.source_type,
            source_key=item.source_key,
            canonical_key=item.canonical_key or item.source_key,
            market_code=item.market_code,
            wallpaper_date=wallpaper_date,
            title=item.title,
            subtitle=item.subtitle,
            description=item.description,
            copyright_text=item.copyright_text,
            source_name=item.source_name,
            published_at_utc=item.published_at_utc,
            location_text=item.location_text,
            origin_page_url=item.origin_page_url,
            origin_image_url=item.origin_image_url,
            origin_width=item.origin_width,
            origin_height=item.origin_height,
            is_downloadable=item.is_downloadable,
            portrait_image_url=item.portrait_image_url,
            raw_extra_json=item.raw_extra_json,
            created_at_utc=created_at_utc,
        )

    def _build_wallpaper_localization_input(
        self,
        *,
        wallpaper_id: int,
        item: CollectedImageMetadata,
        created_at_utc: str,
    ) -> WallpaperLocalizationUpsertInput:
        return WallpaperLocalizationUpsertInput(
            wallpaper_id=wallpaper_id,
            market_code=item.market_code,
            source_key=item.source_key,
            title=item.title,
            subtitle=item.subtitle,
            description=item.description,
            copyright_text=item.copyright_text,
            published_at_utc=item.published_at_utc,
            location_text=item.location_text,
            origin_page_url=item.origin_page_url,
            portrait_image_url=item.portrait_image_url,
            raw_extra_json=item.raw_extra_json,
            created_at_utc=created_at_utc,
        )

    def _wallpaper_needs_resume(self, *, wallpaper_id: int) -> tuple[bool, str | None]:
        resource_rows = self.repository.list_image_resources_for_wallpaper(
            wallpaper_id=wallpaper_id
        )
        if not resource_rows:
            return True, "wallpaper exists without any image resources"

        for row in resource_rows:
            if str(row["image_status"]) != "ready":
                return True, f"resource {row['id']} is not ready"
            if str(row["storage_backend"]) != "local":
                continue
            relative_path = str(row["relative_path"])
            file_path = self.storage.public_dir / relative_path
            if not file_path.is_file():
                return True, f"resource file is missing: {relative_path}"
            if row["file_size_bytes"] is not None and file_path.stat().st_size != int(
                row["file_size_bytes"]
            ):
                return True, f"resource file size does not match: {relative_path}"
            try:
                load_image_bytes(file_path.read_bytes(), fallback_mime_type=None)
            except Exception as exc:
                return True, f"resource file failed integrity validation: {relative_path}: {exc}"
        return False, None

    def _prepare_wallpaper_resume(self, *, wallpaper_id: int, resume_reason: str | None) -> None:
        resource_rows = self.repository.list_image_resources_for_wallpaper(
            wallpaper_id=wallpaper_id
        )
        for row in resource_rows:
            if str(row["storage_backend"]) != "local":
                continue
            relative_path = str(row["relative_path"])
            cleanup_path(self.storage.public_dir / relative_path)
            cleanup_path(self.storage.failed_dir / relative_path)
            cleanup_path(self.storage.tmp_dir / relative_path)
        self.repository.delete_image_resources_for_wallpaper(wallpaper_id=wallpaper_id)
        self.repository.reset_wallpaper_for_resource_rebuild(
            wallpaper_id=wallpaper_id,
            updated_at_utc=utc_now_isoformat(),
        )
        if resume_reason:
            logger.warning(
                "Resume collection for %s wallpaper_id=%s because %s",
                self.adapter.source_type,
                wallpaper_id,
                resume_reason,
            )

    def _download_and_store_resource(
        self,
        *,
        wallpaper_id: int,
        original_resource_id: int,
        task_id: int,
        item: CollectedImageMetadata,
        relative_path: str,
    ) -> None:
        try:
            downloaded, loaded_image, actual_source_url, downloaded_variants = (
                self._download_original_image(
                    item=item,
                    relative_path=relative_path,
                )
            )
        except Exception as exc:
            processed_at_utc = utc_now_isoformat()
            self.repository.mark_image_resource_failed(
                resource_id=original_resource_id,
                failure_reason=str(exc),
                processed_at_utc=processed_at_utc,
            )
            self.repository.refresh_wallpaper_resource_status(
                wallpaper_id=wallpaper_id,
                processed_at_utc=processed_at_utc,
            )
            raise
        content_hash = hashlib.sha256(downloaded.content).hexdigest()
        original_file_ext = extract_file_ext_from_source_url(actual_source_url)
        original_mime_type = guess_mime_type(
            file_ext=original_file_ext,
            fallback=loaded_image.mime_type,
        )
        processed_at_utc = utc_now_isoformat()
        canonical_original_relative_path = build_resource_relative_path(
            source_type=self.adapter.source_type,
            wallpaper_date=item.wallpaper_date,
            market_code=item.market_code,
            path_key=resolve_resource_path_key(
                source_type=self.adapter.source_type,
                market_code=item.market_code,
                source_key=item.source_key,
                canonical_key=item.canonical_key,
            ),
            resource_type=RESOURCE_TYPE_ORIGINAL,
            file_ext=original_file_ext,
            width=loaded_image.width,
            height=loaded_image.height,
        )
        self.repository.update_wallpaper_origin_metadata(
            wallpaper_id=wallpaper_id,
            origin_image_url=actual_source_url,
            origin_width=loaded_image.width,
            origin_height=loaded_image.height,
            updated_at_utc=processed_at_utc,
        )
        self.repository.update_image_resource_source(
            resource_id=original_resource_id,
            source_url=actual_source_url,
            source_url_hash=hashlib.sha256(actual_source_url.encode("utf-8")).hexdigest(),
            updated_at_utc=processed_at_utc,
        )
        if canonical_original_relative_path != relative_path:
            self.repository.update_image_resource_relative_path(
                resource_id=original_resource_id,
                relative_path=canonical_original_relative_path,
                filename=Path(canonical_original_relative_path).name,
                file_ext=original_file_ext,
                mime_type=original_mime_type,
                updated_at_utc=processed_at_utc,
            )
            relative_path = canonical_original_relative_path

        original_tmp_path = self.storage.tmp_path_for(relative_path)
        cleanup_path(original_tmp_path)
        try:
            original_tmp_path.write_bytes(downloaded.content)
            self.storage.move_to_public(tmp_path=original_tmp_path, relative_path=relative_path)
            self.repository.mark_image_resource_ready(
                resource_id=original_resource_id,
                file_size_bytes=len(downloaded.content),
                width=loaded_image.width,
                height=loaded_image.height,
                content_hash=content_hash,
                downloaded_at_utc=processed_at_utc,
                integrity_check_result="passed",
                mime_type=original_mime_type,
            )
        except Exception as exc:
            failure_reason = f"original store failed: {exc}"
            if original_tmp_path.exists():
                self.storage.move_to_failed(
                    tmp_path=original_tmp_path,
                    relative_path=relative_path,
                )
            self.repository.mark_image_resource_failed(
                resource_id=original_resource_id,
                failure_reason=failure_reason,
                processed_at_utc=processed_at_utc,
            )
            self.repository.refresh_wallpaper_resource_status(
                wallpaper_id=wallpaper_id,
                processed_at_utc=processed_at_utc,
            )
            raise RuntimeError(failure_reason) from exc

        variant_resources = self._create_non_download_variant_resource_records(
            wallpaper_id=wallpaper_id,
            item=item,
            loaded_image=loaded_image,
        )
        download_resources = self._create_download_resource_records(
            wallpaper_id=wallpaper_id,
            item=item,
            original_relative_path=relative_path,
            original_loaded_image=loaded_image,
            downloaded_variants=downloaded_variants,
        )
        try:
            for resource in variant_resources:
                self._generate_variant_resource(
                    resource=resource,
                    original_image=loaded_image,
                    original_source_key=item.source_key,
                    task_id=task_id,
                    processed_at_utc=processed_at_utc,
                )
            for resource, downloaded_variant in zip(download_resources, downloaded_variants):
                self._store_download_variant_resource(
                    resource=resource,
                    downloaded_variant=downloaded_variant,
                    processed_at_utc=processed_at_utc,
                )
            if item.is_downloadable and not downloaded_variants and download_resources:
                self._copy_original_as_download(
                    resource=download_resources[0],
                    original_relative_path=relative_path,
                    original_content=downloaded.content,
                    original_mime_type=original_mime_type,
                    original_width=loaded_image.width,
                    original_height=loaded_image.height,
                    content_hash=content_hash,
                    processed_at_utc=processed_at_utc,
                )
        except Exception:
            self.repository.mark_pending_image_resources_failed(
                resource_ids=tuple(
                    resource.resource_id for resource in (*variant_resources, *download_resources)
                ),
                failure_reason="variant processing aborted after an earlier failure",
                processed_at_utc=utc_now_isoformat(),
            )
            self.repository.refresh_wallpaper_resource_status(
                wallpaper_id=wallpaper_id,
                processed_at_utc=utc_now_isoformat(),
            )
            raise

        self.repository.refresh_wallpaper_resource_status(
            wallpaper_id=wallpaper_id,
            processed_at_utc=utc_now_isoformat(),
        )
        if self.auto_publish_enabled:
            self.repository.auto_publish_wallpaper_if_ready(
                wallpaper_id=wallpaper_id,
                processed_at_utc=utc_now_isoformat(),
            )

    def _download_original_image(
        self,
        *,
        item: CollectedImageMetadata,
        relative_path: str,
    ) -> tuple[DownloadedImage, LoadedImage, str, list[DownloadedVariantRecord]]:
        downloaded_variants = self._download_available_variants(
            item=item,
            original_relative_path=relative_path,
        )
        if downloaded_variants:
            primary_variant = downloaded_variants[0]
            return (
                primary_variant.downloaded,
                primary_variant.loaded_image,
                primary_variant.source_url,
                downloaded_variants,
            )

        downloaded, loaded_image = self._download_single_image(
            image_url=item.origin_image_url,
            failure_relative_path=relative_path,
            source_key=item.source_key,
        )
        return downloaded, loaded_image, item.origin_image_url, []

    def _download_available_variants(
        self,
        *,
        item: CollectedImageMetadata,
        original_relative_path: str,
    ) -> list[DownloadedVariantRecord]:
        if not item.download_variants:
            return []

        downloaded_variants: list[DownloadedVariantRecord] = []
        for variant in item.download_variants:
            try:
                variant_file_ext = extract_file_ext_from_source_url(variant.source_url)
                failure_relative_path = build_resource_relative_path(
                    source_type=self.adapter.source_type,
                    wallpaper_date=item.wallpaper_date,
                    market_code=item.market_code,
                    path_key=resolve_resource_path_key(
                        source_type=self.adapter.source_type,
                        market_code=item.market_code,
                        source_key=item.source_key,
                        canonical_key=item.canonical_key,
                    ),
                    resource_type=RESOURCE_TYPE_DOWNLOAD,
                    file_ext=variant_file_ext,
                    width=variant.width,
                    height=variant.height,
                    variant_key=variant.variant_key,
                )
                downloaded, loaded_image = self._download_single_image(
                    image_url=variant.source_url,
                    failure_relative_path=failure_relative_path,
                    source_key=item.source_key,
                )
            except Exception as exc:
                if self.adapter.is_missing_resource_error(exc):
                    logger.info(
                        "Download variant unavailable for %s: variant=%s url=%s",
                        item.source_key,
                        variant.variant_key,
                        variant.source_url,
                    )
                    continue
                raise
            downloaded_variants.append(
                DownloadedVariantRecord(
                    variant_key=variant.variant_key,
                    source_url=variant.source_url,
                    downloaded=downloaded,
                    loaded_image=loaded_image,
                )
            )

        if item.is_downloadable and item.download_variants and not downloaded_variants:
            raise RuntimeError("No Bing download variants were available for this wallpaper.")
        return downloaded_variants

    def _download_single_image(
        self,
        *,
        image_url: str,
        failure_relative_path: str,
        source_key: str,
    ) -> tuple[DownloadedImage, LoadedImage]:
        last_error: str | None = None
        for attempt in range(1, self.max_download_retries + 1):
            downloaded: DownloadedImage | None = None
            try:
                downloaded = self.adapter.download_image(image_url)
                loaded_image = load_image_bytes(
                    downloaded.content,
                    fallback_mime_type=downloaded.mime_type,
                )
                return downloaded, loaded_image
            except Exception as exc:
                if downloaded is not None:
                    self._move_failed_original_download(
                        relative_path=failure_relative_path,
                        content=downloaded.content,
                    )
                if self.adapter.is_missing_resource_error(exc):
                    raise
                last_error = f"download attempt {attempt} failed: {exc}"
                logger.warning(
                    "Download attempt %s/%s failed for %s: %s",
                    attempt,
                    self.max_download_retries,
                    source_key,
                    exc,
                )

        if last_error is None:
            last_error = "download failed without a captured error"
        raise RuntimeError(last_error)

    def _move_failed_original_download(self, *, relative_path: str, content: bytes) -> None:
        tmp_path = self.storage.tmp_path_for(relative_path)
        cleanup_path(tmp_path)
        tmp_path.write_bytes(content)
        self.storage.move_to_failed(tmp_path=tmp_path, relative_path=relative_path)

    def _create_non_download_variant_resource_records(
        self,
        *,
        wallpaper_id: int,
        item: CollectedImageMetadata,
        loaded_image: LoadedImage,
    ) -> list[VariantResourceRecord]:
        created_at_utc = utc_now_isoformat()
        thumbnail_preview_ext = default_variant_file_ext(loaded_image=loaded_image)
        resources: list[VariantResourceRecord] = []
        for resource_type in (RESOURCE_TYPE_THUMBNAIL, RESOURCE_TYPE_PREVIEW):
            variant_width, variant_height = calculate_variant_dimensions(
                width=loaded_image.width,
                height=loaded_image.height,
                resource_type=resource_type,
            )
            relative_path = build_resource_relative_path(
                source_type=self.adapter.source_type,
                wallpaper_date=item.wallpaper_date,
                market_code=item.market_code,
                path_key=resolve_resource_path_key(
                    source_type=self.adapter.source_type,
                    market_code=item.market_code,
                    source_key=item.source_key,
                    canonical_key=item.canonical_key,
                ),
                resource_type=resource_type,
                file_ext=thumbnail_preview_ext,
                width=variant_width,
                height=variant_height,
            )
            file_ext = thumbnail_preview_ext
            mime_type = guess_mime_type(file_ext=file_ext, fallback=None)
            resource_id = self.repository.create_image_resource(
                ResourceCreateInput(
                    wallpaper_id=wallpaper_id,
                    resource_type=resource_type,
                    storage_backend="local",
                    relative_path=relative_path,
                    filename=Path(relative_path).name,
                    file_ext=file_ext,
                    mime_type=mime_type,
                    source_url=None,
                    source_url_hash=None,
                    created_at_utc=created_at_utc,
                )
            )
            resources.append(
                VariantResourceRecord(
                    resource_id=resource_id,
                    resource_type=resource_type,
                    relative_path=relative_path,
                )
            )
        return resources

    def _create_download_resource_records(
        self,
        *,
        wallpaper_id: int,
        item: CollectedImageMetadata,
        original_relative_path: str,
        original_loaded_image: LoadedImage,
        downloaded_variants: list[DownloadedVariantRecord],
    ) -> list[VariantResourceRecord]:
        if not item.is_downloadable:
            return []

        created_at_utc = utc_now_isoformat()
        resources: list[VariantResourceRecord] = []
        if downloaded_variants:
            for variant in downloaded_variants:
                file_ext = extract_file_ext_from_source_url(variant.source_url)
                relative_path = build_resource_relative_path(
                    source_type=self.adapter.source_type,
                    wallpaper_date=item.wallpaper_date,
                    market_code=item.market_code,
                    path_key=resolve_resource_path_key(
                        source_type=self.adapter.source_type,
                        market_code=item.market_code,
                        source_key=item.source_key,
                        canonical_key=item.canonical_key,
                    ),
                    resource_type=RESOURCE_TYPE_DOWNLOAD,
                    file_ext=file_ext,
                    width=variant.loaded_image.width,
                    height=variant.loaded_image.height,
                    variant_key=variant.variant_key,
                )
                resource_id = self.repository.create_image_resource(
                    ResourceCreateInput(
                        wallpaper_id=wallpaper_id,
                        resource_type=RESOURCE_TYPE_DOWNLOAD,
                        storage_backend="local",
                        relative_path=relative_path,
                        filename=Path(relative_path).name,
                        file_ext=file_ext,
                        mime_type=guess_mime_type(
                            file_ext=file_ext,
                            fallback=variant.loaded_image.mime_type,
                        ),
                        source_url=variant.source_url,
                        source_url_hash=hashlib.sha256(
                            variant.source_url.encode("utf-8")
                        ).hexdigest(),
                        created_at_utc=created_at_utc,
                        variant_key=variant.variant_key,
                    )
                )
                resources.append(
                    VariantResourceRecord(
                        resource_id=resource_id,
                        resource_type=RESOURCE_TYPE_DOWNLOAD,
                        relative_path=relative_path,
                        variant_key=variant.variant_key,
                    )
                )
            return resources

        relative_path = build_resource_relative_path(
            source_type=self.adapter.source_type,
            wallpaper_date=item.wallpaper_date,
            market_code=item.market_code,
            path_key=resolve_resource_path_key(
                source_type=self.adapter.source_type,
                market_code=item.market_code,
                source_key=item.source_key,
                canonical_key=item.canonical_key,
            ),
            resource_type=RESOURCE_TYPE_DOWNLOAD,
            file_ext=Path(original_relative_path).suffix.lstrip(".").lower() or "jpg",
            width=original_loaded_image.width,
            height=original_loaded_image.height,
        )
        file_ext = Path(relative_path).suffix.lstrip(".").lower() or "jpg"
        resource_id = self.repository.create_image_resource(
            ResourceCreateInput(
                wallpaper_id=wallpaper_id,
                resource_type=RESOURCE_TYPE_DOWNLOAD,
                storage_backend="local",
                relative_path=relative_path,
                filename=Path(relative_path).name,
                file_ext=file_ext,
                mime_type=guess_mime_type(
                    file_ext=file_ext, fallback=original_loaded_image.mime_type
                ),
                source_url=None,
                source_url_hash=None,
                created_at_utc=created_at_utc,
            )
        )
        return [
            VariantResourceRecord(
                resource_id=resource_id,
                resource_type=RESOURCE_TYPE_DOWNLOAD,
                relative_path=relative_path,
            )
        ]

    def _copy_original_as_download(
        self,
        *,
        resource: VariantResourceRecord,
        original_relative_path: str,
        original_content: bytes,
        original_mime_type: str,
        original_width: int,
        original_height: int,
        content_hash: str,
        processed_at_utc: str,
    ) -> None:
        tmp_path = self.storage.tmp_path_for(resource.relative_path)
        cleanup_path(tmp_path)
        try:
            tmp_path.write_bytes(original_content)
            self.storage.move_to_public(tmp_path=tmp_path, relative_path=resource.relative_path)
            self.repository.mark_image_resource_ready(
                resource_id=resource.resource_id,
                file_size_bytes=len(original_content),
                width=original_width,
                height=original_height,
                content_hash=content_hash,
                downloaded_at_utc=processed_at_utc,
                integrity_check_result=f"copied_from:{original_relative_path}",
                mime_type=original_mime_type,
            )
        except Exception as exc:
            failure_reason = f"download resource copy failed: {exc}"
            if tmp_path.exists():
                self.storage.move_to_failed(
                    tmp_path=tmp_path,
                    relative_path=resource.relative_path,
                )
            self.repository.mark_image_resource_failed(
                resource_id=resource.resource_id,
                failure_reason=failure_reason,
                processed_at_utc=processed_at_utc,
            )
            raise RuntimeError(failure_reason) from exc

    def _store_download_variant_resource(
        self,
        *,
        resource: VariantResourceRecord,
        downloaded_variant: DownloadedVariantRecord,
        processed_at_utc: str,
    ) -> None:
        tmp_path = self.storage.tmp_path_for(resource.relative_path)
        cleanup_path(tmp_path)
        try:
            tmp_path.write_bytes(downloaded_variant.downloaded.content)
            self.storage.move_to_public(tmp_path=tmp_path, relative_path=resource.relative_path)
            self.repository.mark_image_resource_ready(
                resource_id=resource.resource_id,
                file_size_bytes=len(downloaded_variant.downloaded.content),
                width=downloaded_variant.loaded_image.width,
                height=downloaded_variant.loaded_image.height,
                content_hash=hashlib.sha256(downloaded_variant.downloaded.content).hexdigest(),
                downloaded_at_utc=processed_at_utc,
                integrity_check_result="passed",
                mime_type=guess_mime_type(
                    file_ext=extract_file_ext_from_source_url(downloaded_variant.source_url),
                    fallback=downloaded_variant.loaded_image.mime_type,
                ),
            )
        except Exception as exc:
            failure_reason = f"download variant {resource.variant_key} store failed: {exc}"
            if tmp_path.exists():
                self.storage.move_to_failed(
                    tmp_path=tmp_path,
                    relative_path=resource.relative_path,
                )
            self.repository.mark_image_resource_failed(
                resource_id=resource.resource_id,
                failure_reason=failure_reason,
                processed_at_utc=processed_at_utc,
            )
            raise RuntimeError(failure_reason) from exc

    def _generate_variant_resource(
        self,
        *,
        resource: VariantResourceRecord,
        original_image: LoadedImage,
        original_source_key: str,
        task_id: int,
        processed_at_utc: str,
    ) -> None:
        tmp_path = self.storage.tmp_path_for(resource.relative_path)
        cleanup_path(tmp_path)
        try:
            variant = generate_variant_image(
                original_image.image,
                resource_type=resource.resource_type,
            )
            tmp_path.write_bytes(variant.content)
            self.storage.move_to_public(tmp_path=tmp_path, relative_path=resource.relative_path)
            self.repository.mark_image_resource_ready(
                resource_id=resource.resource_id,
                file_size_bytes=len(variant.content),
                width=variant.width,
                height=variant.height,
                content_hash=hashlib.sha256(variant.content).hexdigest(),
                downloaded_at_utc=processed_at_utc,
                integrity_check_result="passed",
                mime_type=variant.mime_type,
            )
        except Exception as exc:
            failure_reason = f"{resource.resource_type} generation failed: {exc}"
            if tmp_path.exists():
                self.storage.move_to_failed(
                    tmp_path=tmp_path,
                    relative_path=resource.relative_path,
                )
            self.repository.mark_image_resource_failed(
                resource_id=resource.resource_id,
                failure_reason=failure_reason,
                processed_at_utc=processed_at_utc,
            )
            self.repository.create_task_item(
                TaskItemCreateInput(
                    task_id=task_id,
                    source_item_key=original_source_key,
                    action_name="generate_variant",
                    result_status="failed",
                    dedupe_hit_type=None,
                    db_write_result="variant_resource_failed",
                    file_write_result="failed",
                    failure_reason=failure_reason,
                    occurred_at_utc=utc_now_isoformat(),
                )
            )
            raise RuntimeError(failure_reason) from exc


def build_source_relative_path(
    *,
    source_type: str,
    market_code: str,
    wallpaper_date: date,
    source_key: str,
    canonical_key: str | None,
    origin_image_url: str,
) -> str:
    file_ext = extract_file_ext_from_source_url(origin_image_url)
    return build_resource_relative_path(
        source_type=source_type,
        wallpaper_date=wallpaper_date,
        market_code=market_code,
        path_key=resolve_resource_path_key(
            source_type=source_type,
            market_code=market_code,
            source_key=source_key,
            canonical_key=canonical_key,
        ),
        resource_type=RESOURCE_TYPE_ORIGINAL,
        file_ext=file_ext,
        width=None,
        height=None,
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


def default_variant_file_ext(*, loaded_image: LoadedImage) -> str:
    if "A" in loaded_image.image.getbands() or "transparency" in loaded_image.image.info:
        return "png"
    return "jpg"


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
    metadata_items: list[CollectedImageMetadata],
    date_from: date | None,
    date_to: date | None,
) -> list[CollectedImageMetadata]:
    if date_from is None or date_to is None:
        return metadata_items
    return [item for item in metadata_items if date_from <= item.wallpaper_date <= date_to]


def resolve_fetch_date_window(
    *,
    date_from: date | None,
    date_to: date | None,
    latest_available_fallback_days: int | None,
) -> tuple[date | None, date | None]:
    if not should_use_latest_available_fallback(
        date_from=date_from,
        date_to=date_to,
        latest_available_fallback_days=latest_available_fallback_days,
    ):
        return date_from, date_to
    assert date_from is not None
    assert latest_available_fallback_days is not None
    return date_from - timedelta(days=latest_available_fallback_days - 1), date_to


def select_metadata_items_for_collection(
    *,
    metadata_items: list[CollectedImageMetadata],
    date_from: date | None,
    date_to: date | None,
    latest_available_fallback_days: int | None,
) -> tuple[list[CollectedImageMetadata], date | None]:
    filtered_items = filter_metadata_items(
        metadata_items=metadata_items,
        date_from=date_from,
        date_to=date_to,
    )
    if filtered_items:
        return filtered_items, None
    if not should_use_latest_available_fallback(
        date_from=date_from,
        date_to=date_to,
        latest_available_fallback_days=latest_available_fallback_days,
    ):
        return filtered_items, None
    assert date_from is not None
    fallback_candidates = [item for item in metadata_items if item.wallpaper_date <= date_from]
    if not fallback_candidates:
        return [], None
    fallback_date = max(item.wallpaper_date for item in fallback_candidates)
    return (
        [item for item in fallback_candidates if item.wallpaper_date == fallback_date],
        fallback_date,
    )


def should_use_latest_available_fallback(
    *,
    date_from: date | None,
    date_to: date | None,
    latest_available_fallback_days: int | None,
) -> bool:
    return (
        latest_available_fallback_days is not None
        and latest_available_fallback_days > 1
        and date_from is not None
        and date_to is not None
        and date_from == date_to
    )


def date_to_isoformat(value: date | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()
