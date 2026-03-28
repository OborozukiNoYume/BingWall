from __future__ import annotations

from typing import Literal

ResourceType = Literal["original", "thumbnail", "preview", "download"]
ResourceStatus = Literal["pending", "ready", "failed"]

RESOURCE_TYPE_ORIGINAL: ResourceType = "original"
RESOURCE_TYPE_THUMBNAIL: ResourceType = "thumbnail"
RESOURCE_TYPE_PREVIEW: ResourceType = "preview"
RESOURCE_TYPE_DOWNLOAD: ResourceType = "download"

PUBLIC_LIST_RESOURCE_TYPE: ResourceType = RESOURCE_TYPE_THUMBNAIL
PUBLIC_DETAIL_PREVIEW_RESOURCE_TYPE: ResourceType = RESOURCE_TYPE_PREVIEW
PUBLIC_DETAIL_DOWNLOAD_RESOURCE_TYPE: ResourceType = RESOURCE_TYPE_DOWNLOAD

REQUIRED_READY_RESOURCE_TYPES: tuple[ResourceType, ...] = (
    RESOURCE_TYPE_ORIGINAL,
    RESOURCE_TYPE_THUMBNAIL,
    RESOURCE_TYPE_PREVIEW,
)


def expected_resource_types(*, is_downloadable: bool) -> tuple[ResourceType, ...]:
    if is_downloadable:
        return (*REQUIRED_READY_RESOURCE_TYPES, RESOURCE_TYPE_DOWNLOAD)
    return REQUIRED_READY_RESOURCE_TYPES


def derive_resource_status(
    *,
    resources: list[tuple[str, str]],
    is_downloadable: bool,
) -> ResourceStatus:
    ready_types = {
        resource_type
        for resource_type, image_status in resources
        if image_status == "ready"
    }
    failed_types = {
        resource_type
        for resource_type, image_status in resources
        if image_status == "failed"
    }
    has_download_rows = any(resource_type == RESOURCE_TYPE_DOWNLOAD for resource_type, _ in resources)
    has_ready_download = RESOURCE_TYPE_DOWNLOAD in ready_types or (
        is_downloadable and not has_download_rows and RESOURCE_TYPE_ORIGINAL in ready_types
    )
    has_failed_download = has_download_rows and RESOURCE_TYPE_DOWNLOAD in failed_types

    if REQUIRED_READY_RESOURCE_TYPES and not set(REQUIRED_READY_RESOURCE_TYPES).issubset(ready_types):
        if set(REQUIRED_READY_RESOURCE_TYPES).intersection(failed_types):
            return "failed"
        if is_downloadable and has_failed_download:
            return "failed"
        return "pending"

    if is_downloadable and not has_ready_download:
        return "failed" if has_failed_download else "pending"

    return "ready"
