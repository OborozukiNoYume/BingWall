from __future__ import annotations

import json
import logging
import sys

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.repositories.health_repository import HealthRepository
from app.services.resource_archive import ResourceArchiveService


def main() -> int:
    settings = get_settings()
    configure_logging(settings.log_level)

    repository = HealthRepository(settings.database_path)
    service = ResourceArchiveService(
        repository,
        tmp_dir=settings.storage_tmp_dir,
        public_dir=settings.storage_public_dir,
        failed_dir=settings.storage_failed_dir,
    )
    try:
        summary = service.archive_and_cleanup()
    finally:
        repository.close()

    logging.getLogger(__name__).info(
        "Wallpaper archive summary archived=%s damaged=%s tmp_deleted=%s orphan_quarantined=%s",
        summary["archived_resource_count"],
        summary["damaged_resource_count"],
        summary["tmp_deleted_count"],
        summary["orphan_quarantined_count"],
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    if int(summary["damaged_resource_count"]) > 0 or int(summary["skipped_conflict_count"]) > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
