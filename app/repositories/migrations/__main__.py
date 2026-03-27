import argparse
from pathlib import Path

from app.core.config import get_settings
from app.core.config import load_bootstrap_admin_settings
from app.repositories.migrations.runner import migrate_database
from app.services.admin_bootstrap import ensure_bootstrap_admin_user


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply BingWall SQLite migrations.")
    parser.add_argument(
        "--database-path",
        type=Path,
        help="Optional SQLite database path. Defaults to BINGWALL_DATABASE_PATH from settings.",
    )
    return parser.parse_args()


def resolve_database_path(database_path: Path | None) -> Path:
    if database_path is not None:
        return database_path
    return get_settings().database_path


def main() -> None:
    args = parse_args()
    database_path = resolve_database_path(args.database_path)
    applied_migrations = migrate_database(database_path)
    bootstrap_settings = load_bootstrap_admin_settings()
    bootstrap_admin_created = ensure_bootstrap_admin_user(
        database_path=database_path,
        username=bootstrap_settings.security_bootstrap_admin_username,
        password=(
            bootstrap_settings.security_bootstrap_admin_password.get_secret_value()
            if bootstrap_settings.security_bootstrap_admin_password is not None
            else None
        ),
    )

    if applied_migrations:
        for migration in applied_migrations:
            print(
                f"Applied migration V{migration.version:04d} ({migration.name}) to {database_path}."
            )
    else:
        print(f"No pending migrations for {database_path}.")

    if bootstrap_admin_created:
        print(f"Bootstrapped enabled admin user to {database_path}.")


if __name__ == "__main__":
    main()
