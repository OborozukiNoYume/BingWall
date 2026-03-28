from __future__ import annotations

import json

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.repositories.admin_collection_repository import AdminCollectionRepository
from app.services.scheduled_collection import create_scheduled_collection_tasks


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)

    repository = AdminCollectionRepository(str(settings.database_path))
    try:
        results = create_scheduled_collection_tasks(
            repository=repository,
            settings=settings,
        )
    finally:
        repository.close()

    print(
        json.dumps(
            {
                "created_count": sum(1 for result in results if result.action == "created"),
                "skipped_count": sum(
                    1 for result in results if result.action == "skipped_existing"
                ),
                "items": [
                    {
                        "source_type": result.source_type,
                        "market_code": result.market_code,
                        "date_from": result.date_from,
                        "date_to": result.date_to,
                        "count": result.count,
                        "action": result.action,
                        "task_id": result.task_id,
                        "reason": result.reason,
                    }
                    for result in results
                ],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
