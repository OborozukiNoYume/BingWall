from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from app.core.logging import configure_logging
from app.services.backup_restore import BackupManager
from app.services.backup_restore import RestoreTargetPaths
from app.services.backup_restore import ServiceConfigPaths
from app.services.backup_restore import build_restore_targets_from_root

DEFAULT_DATABASE_PATH = Path("/var/lib/bingwall/data/bingwall.sqlite3")
DEFAULT_PUBLIC_DIR = Path("/var/lib/bingwall/images/public")
DEFAULT_CONFIG_DIR = Path("/etc/bingwall")
DEFAULT_LOG_DIR = Path("/var/log/bingwall")
DEFAULT_BACKUP_DIR = Path("/var/backups/bingwall")
DEFAULT_NGINX_CONFIG_PATH = Path("/etc/nginx/sites-available/bingwall.conf")
DEFAULT_SYSTEMD_SERVICE_PATH = Path("/etc/systemd/system/bingwall-api.service")
DEFAULT_TMPFILES_CONFIG_PATH = Path("/etc/tmpfiles.d/bingwall.conf")


def main() -> int:
    parser = argparse.ArgumentParser(description="Restore a BingWall backup snapshot.")
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--target-root", type=Path)
    parser.add_argument("--database-path", type=Path, default=DEFAULT_DATABASE_PATH)
    parser.add_argument("--public-dir", type=Path, default=DEFAULT_PUBLIC_DIR)
    parser.add_argument("--config-dir", type=Path, default=DEFAULT_CONFIG_DIR)
    parser.add_argument("--log-dir", type=Path, default=DEFAULT_LOG_DIR)
    parser.add_argument("--backup-dir", type=Path, default=DEFAULT_BACKUP_DIR)
    parser.add_argument("--nginx-config-path", type=Path, default=DEFAULT_NGINX_CONFIG_PATH)
    parser.add_argument(
        "--systemd-service-path",
        type=Path,
        default=DEFAULT_SYSTEMD_SERVICE_PATH,
    )
    parser.add_argument("--tmpfiles-config-path", type=Path, default=DEFAULT_TMPFILES_CONFIG_PATH)
    parser.add_argument("--log-level", default="INFO")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    configure_logging(args.log_level)
    if args.target_root is not None:
        targets = build_restore_targets_from_root(args.snapshot, args.target_root)
    else:
        targets = RestoreTargetPaths(
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

    manager = BackupManager()
    summary = manager.restore_backup(
        snapshot_dir=args.snapshot,
        targets=targets,
        force=args.force,
    )
    print(json.dumps(summary.to_dict(), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
