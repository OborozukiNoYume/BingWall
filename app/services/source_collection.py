from __future__ import annotations

from datetime import date
import json
import logging
from pathlib import Path
from typing import cast

from app.domain.collection import CollectedImageMetadata
from app.domain.collection import CollectionRunSummary
from app.domain.collection_sources import COLLECTION_SOURCE_MAX_MANUAL_DAYS
from app.domain.collection_sources import CollectionSourceType
from app.domain.resource_variants import RESOURCE_TYPE_ORIGINAL
from app.repositories.collection_repository import CollectionRepository
from app.repositories.collection_repository import ResourceCreateInput
from app.repositories.collection_repository import TaskItemCreateInput
from app.repositories.collection_repository import WallpaperCreateInput
from app.repositories.collection_repository import WallpaperLocalizationUpsertInput
from app.repositories.file_storage import FileStorage
from app.services.image_variants import generate_variant_image
from app.services.source_collection_resource_pipeline import SourceCollectionResourcePipelineMixin
from app.services.source_collection_types import CollectionSourceAdapter
from app.services.source_collection_types import DownloadedVariantRecord
from app.services.source_collection_types import VariantResourceRecord
from app.services.source_collection_utils import build_source_relative_path
from app.services.source_collection_utils import cleanup_path
from app.services.source_collection_utils import date_to_isoformat
from app.services.source_collection_utils import default_variant_file_ext
from app.services.source_collection_utils import extract_file_ext_from_source_url
from app.services.source_collection_utils import filter_metadata_items
from app.services.source_collection_utils import guess_mime_type
from app.services.source_collection_utils import resolve_fetch_date_window
from app.services.source_collection_utils import select_metadata_items_for_collection
from app.services.source_collection_utils import should_use_latest_available_fallback
from app.services.source_collection_utils import task_status_from_counts
from app.services.source_collection_utils import task_type_for_trigger
from app.services.source_collection_utils import utc_now_isoformat

logger = logging.getLogger(__name__)


class SourceCollectionService(SourceCollectionResourcePipelineMixin):
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

        from app.services.image_variants import load_image_bytes

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


__all__ = [
    "CollectionSourceAdapter",
    "DownloadedVariantRecord",
    "SourceCollectionService",
    "VariantResourceRecord",
    "build_source_relative_path",
    "cleanup_path",
    "date_to_isoformat",
    "default_variant_file_ext",
    "extract_file_ext_from_source_url",
    "filter_metadata_items",
    "generate_variant_image",
    "guess_mime_type",
    "resolve_fetch_date_window",
    "select_metadata_items_for_collection",
    "should_use_latest_available_fallback",
    "task_status_from_counts",
    "task_type_for_trigger",
    "utc_now_isoformat",
]
