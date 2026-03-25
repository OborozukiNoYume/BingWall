from __future__ import annotations

import argparse
import json

from app.collectors.bing import BingClient
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.repositories.collection_repository import CollectionRepository
from app.repositories.file_storage import FileStorage
from app.services.admin_collection import ManualCollectionTaskConsumer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Consume queued manual collection tasks for BingWall."
    )
    parser.add_argument("--max-tasks", type=int, default=1)
    return parser.parse_args()


def main() -> None:
    settings = get_settings()
    if not settings.collect_bing_enabled:
        raise RuntimeError("Bing collection is disabled by configuration.")

    args = parse_args()
    configure_logging(settings.log_level)

    repository = CollectionRepository(str(settings.database_path))
    storage = FileStorage(
        tmp_dir=settings.storage_tmp_dir,
        public_dir=settings.storage_public_dir,
        failed_dir=settings.storage_failed_dir,
    )
    consumer = ManualCollectionTaskConsumer(
        repository=repository,
        storage=storage,
        bing_client=BingClient(timeout_seconds=settings.collect_bing_timeout_seconds),
        max_download_retries=settings.collect_bing_max_download_retries,
    )

    consumed: list[dict[str, object]] = []
    try:
        for _ in range(max(args.max_tasks, 1)):
            summary = consumer.consume_next_queued_task()
            if summary is None:
                break
            consumed.append({
                "task_id": summary.task_id,
                "task_status": summary.task_status,
                "success_count": summary.success_count,
                "duplicate_count": summary.duplicate_count,
                "failure_count": summary.failure_count,
                "error_summary": summary.error_summary,
            })
    finally:
        repository.close()

    print(
        json.dumps(
            {
                "processed_count": len(consumed),
                "items": consumed,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
