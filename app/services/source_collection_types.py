from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol

from app.domain.collection import CollectedImageMetadata
from app.domain.collection import DownloadedImage
from app.domain.resource_variants import ResourceType
from app.services.image_variants import LoadedImage


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
