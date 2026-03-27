from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from pydantic import ValidationError

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.services.backup_restore import BackupManager
from app.services.backup_restore import BackupSourcePaths
from app.services.backup_restore import ServiceConfigPaths

DEFAULT_DATABASE_PATH = Path("/var/lib/bingwall/data/bingwall.sqlite3")
DEFAULT_PUBLIC_DIR = Path("/var/lib/bingwall/images/public")
DEFAULT_CONFIG_DIR = Path("/etc/bingwall")
DEFAULT_LOG_DIR = Path("/var/log/bingwall")
DEFAULT_BACKUP_DIR = Path("/var/backups/bingwall")
DEFAULT_NGINX_CONFIG_PATH = Path("/etc/nginx/sites-available/bingwall.conf")
DEFAULT_SYSTEMD_SERVICE_PATH = Path("/etc/systemd/system/bingwall-api.service")
DEFAULT_TMPFILES_CONFIG_PATH = Path("/etc/tmpfiles.d/bingwall.conf")


def main() -> int:
    defaults = build_defaults()
    parser = argparse.ArgumentParser(description="Create a BingWall backup snapshot.")
    parser.add_argument("--database-path", type=Path, default=defaults.database_path)
    parser.add_argument("--public-dir", type=Path, default=defaults.public_dir)
    parser.add_argument("--config-dir", type=Path, default=defaults.config_dir)
    parser.add_argument("--log-dir", type=Path, default=defaults.log_dir)
    parser.add_argument("--backup-dir", type=Path, default=defaults.backup_dir)
    parser.add_argument(
        "--nginx-config-path",
        type=Path,
        default=defaults.service_configs.nginx_config_path,
    )
    parser.add_argument(
        "--systemd-service-path",
        type=Path,
        default=defaults.service_configs.systemd_service_path,
    )
    parser.add_argument(
        "--tmpfiles-config-path",
        type=Path,
        default=defaults.service_configs.tmpfiles_config_path,
    )
    parser.add_argument("--log-level", default=defaults.log_level)
    args = parser.parse_args()

    configure_logging(args.log_level)
    manager = BackupManager()
    summary = manager.create_backup(
        BackupSourcePaths(
            database_path=args.database_path,
            public_dir=args.public_dir,
            config_dir=args.config_dir,
            log_dir=args.log_dir,
            backup_dir=args.backup_dir,
            service_configs=ServiceConfigPaths(
                nginx_config_path=args.nginx_config_path,
                systemd_service_path=args.systemd_service_path,
                tmpfiles_config_path=args.tmpfiles_config_path,
            ),
        )
    )
    print(json.dumps(summary.to_dict(), ensure_ascii=False, sort_keys=True))
    return 0


def build_defaults() -> BackupDefaults:
    try:
        settings = get_settings()
    except ValidationError:
        return BackupDefaults(
            database_path=DEFAULT_DATABASE_PATH,
            public_dir=DEFAULT_PUBLIC_DIR,
            config_dir=DEFAULT_CONFIG_DIR,
            log_dir=DEFAULT_LOG_DIR,
            backup_dir=DEFAULT_BACKUP_DIR,
            log_level="INFO",
            service_configs=ServiceConfigPaths(
                nginx_config_path=DEFAULT_NGINX_CONFIG_PATH,
                systemd_service_path=DEFAULT_SYSTEMD_SERVICE_PATH,
                tmpfiles_config_path=DEFAULT_TMPFILES_CONFIG_PATH,
            ),
        )

    return BackupDefaults(
        database_path=settings.database_path,
        public_dir=settings.storage_public_dir,
        config_dir=DEFAULT_CONFIG_DIR,
        log_dir=DEFAULT_LOG_DIR,
        backup_dir=settings.backup_dir,
        log_level=settings.log_level,
        service_configs=ServiceConfigPaths(
            nginx_config_path=DEFAULT_NGINX_CONFIG_PATH,
            systemd_service_path=DEFAULT_SYSTEMD_SERVICE_PATH,
            tmpfiles_config_path=DEFAULT_TMPFILES_CONFIG_PATH,
        ),
    )


class BackupDefaults:
    def __init__(
        self,
        *,
        database_path: Path,
        public_dir: Path,
        config_dir: Path,
        log_dir: Path,
        backup_dir: Path,
        log_level: str,
        service_configs: ServiceConfigPaths,
    ) -> None:
        self.database_path = database_path
        self.public_dir = public_dir
        self.config_dir = config_dir
        self.log_dir = log_dir
        self.backup_dir = backup_dir
        self.log_level = log_level
        self.service_configs = service_configs


if __name__ == "__main__":
    sys.exit(main())
