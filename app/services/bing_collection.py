from __future__ import annotations

from datetime import date
from typing import Protocol

from app.domain.collection import BingImageMetadata
from app.domain.collection import CollectionRunSummary
from app.domain.collection import DownloadedImage
from app.repositories.collection_repository import CollectionRepository
from app.repositories.file_storage import FileStorage
from app.services.source_collection import SourceCollectionService


class BingClientProtocol(Protocol):
    def fetch_metadata(
        self,
        *,
        market_code: str,
        count: int,
        date_from: date | None,
        date_to: date | None,
    ) -> list[BingImageMetadata]: ...

    def download_image(self, image_url: str) -> DownloadedImage: ...


class BingSourceAdapter:
    source_type = "bing"
    display_name = "Bing"

    def __init__(self, *, client: BingClientProtocol) -> None:
        self.client = client

    def fetch_metadata(
        self,
        *,
        market_code: str,
        count: int,
        date_from: date | None,
        date_to: date | None,
    ) -> list[BingImageMetadata]:
        return self.client.fetch_metadata(
            market_code=market_code,
            count=count,
            date_from=date_from,
            date_to=date_to,
        )

    def download_image(self, image_url: str) -> DownloadedImage:
        return self.client.download_image(image_url)

    def is_missing_resource_error(self, exc: Exception) -> bool:
        from app.collectors.bing import BingImageDownloadError

        return isinstance(exc, BingImageDownloadError) and exc.status_code == 404

    def build_relative_path(self, item: BingImageMetadata) -> str:
        from app.collectors.bing import build_bing_relative_path

        return build_bing_relative_path(item)


class BingCollectionService:
    def __init__(
        self,
        *,
        repository: CollectionRepository,
        storage: FileStorage,
        bing_client: BingClientProtocol,
        max_download_retries: int,
        auto_publish_enabled: bool = True,
    ) -> None:
        self.repository = repository
        self.delegate = SourceCollectionService(
            repository=repository,
            storage=storage,
            adapter=BingSourceAdapter(client=bing_client),
            max_download_retries=max_download_retries,
            auto_publish_enabled=auto_publish_enabled,
        )

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
        return self.delegate.collect(
            market_code=market_code,
            count=count,
            trigger_type=trigger_type,
            triggered_by=triggered_by,
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
        return self.delegate.collect_existing_task(
            task_id=task_id,
            market_code=market_code,
            count=count,
            date_from=date_from,
            date_to=date_to,
        )
