from __future__ import annotations

import json
import logging
import sys

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.repositories.health_repository import HealthRepository
from app.services.health import ResourceInspectionService


def main() -> int:
    settings = get_settings()
    configure_logging(settings.log_level)

    repository = HealthRepository(settings.database_path)
    service = ResourceInspectionService(
        repository,
        public_dir=settings.storage_public_dir,
    )
    try:
        summary = service.inspect_ready_local_resources()
    finally:
        repository.close()

    logging.getLogger(__name__).info(
        "Resource inspection summary checked=%s missing=%s disabled=%s",
        summary.checked_resource_count,
        summary.missing_resource_count,
        summary.disabled_wallpaper_count,
    )
    print(json.dumps(summary.model_dump(mode="json"), ensure_ascii=False, sort_keys=True))
    if summary.missing_resource_count > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
