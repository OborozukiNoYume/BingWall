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
