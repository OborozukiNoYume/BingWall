from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from app.domain.collection import CollectedImageMetadata
from app.domain.collection import DownloadedImage
from app.domain.resource_variants import RESOURCE_TYPE_DOWNLOAD
from app.domain.resource_variants import RESOURCE_TYPE_ORIGINAL
from app.domain.resource_variants import RESOURCE_TYPE_PREVIEW
from app.domain.resource_variants import RESOURCE_TYPE_THUMBNAIL
from app.repositories.collection_repository import CollectionRepository
from app.repositories.collection_repository import ResourceCreateInput
from app.repositories.collection_repository import TaskItemCreateInput
from app.repositories.file_storage import FileStorage
from app.services.image_variants import LoadedImage
from app.services.image_variants import calculate_variant_dimensions
from app.services.image_variants import load_image_bytes
from app.services.resource_paths import build_resource_relative_path
from app.services.resource_paths import resolve_resource_path_key
from app.services.source_collection_types import CollectionSourceAdapter
from app.services.source_collection_types import DownloadedVariantRecord
from app.services.source_collection_types import VariantResourceRecord
from app.services.source_collection_utils import cleanup_path
from app.services.source_collection_utils import default_variant_file_ext
from app.services.source_collection_utils import extract_file_ext_from_source_url
from app.services.source_collection_utils import guess_mime_type
from app.services.source_collection_utils import utc_now_isoformat

logger = logging.getLogger(__name__)


class SourceCollectionResourcePipelineMixin:
    repository: CollectionRepository
    storage: FileStorage
    adapter: CollectionSourceAdapter
    max_download_retries: int
    auto_publish_enabled: bool

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
            from app.services import source_collection as source_collection_module

            variant = source_collection_module.generate_variant_image(
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
