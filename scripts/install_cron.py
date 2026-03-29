#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE_PATH = REPO_ROOT / "deploy" / "cron" / "bingwall-cron"
DEFAULT_APP_DIR = Path("/opt/bingwall/app")
DEFAULT_LOG_DIR = Path("/var/log/bingwall")
DEFAULT_ENV_FILE = Path("/etc/bingwall/bingwall.env")
PLACEHOLDER_APP_DIR = "__BINGWALL_APP_DIR__"
PLACEHOLDER_UV_BIN = "__BINGWALL_UV_BIN__"
PLACEHOLDER_LOG_DIR = "__BINGWALL_LOG_DIR__"
PLACEHOLDER_ENV_FILE = "__BINGWALL_ENV_FILE__"


class CronInstallError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class RenderContext:
    template_path: Path
    app_dir: Path
    uv_bin: Path
    log_dir: Path
    env_file: Path
    output_path: Path | None
    install: bool
    crontab_bin: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render and optionally install the BingWall cron template."
    )
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE_PATH)
    parser.add_argument("--app-dir", type=Path, default=DEFAULT_APP_DIR)
    parser.add_argument(
        "--uv-bin",
        default="uv",
        help="The uv executable or absolute path used in the rendered cron entries.",
    )
    parser.add_argument("--log-dir", type=Path, default=DEFAULT_LOG_DIR)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--install",
        action="store_true",
        help="Install the rendered cron file into the current user's crontab.",
    )
    parser.add_argument(
        "--crontab-bin",
        default="crontab",
        help="The crontab executable or absolute path used for installation.",
    )
    return parser.parse_args()


def main() -> int:
    try:
        args = parse_args()
        context = build_context(args)
        rendered_cron = render_cron_template(context)
        entry_count = validate_rendered_cron(rendered_cron)
        written_path = write_output_if_requested(rendered_cron, context.output_path)

        backup_path: Path | None = None
        if context.install:
            crontab_executable = resolve_executable(context.crontab_bin)
            backup_path = backup_existing_crontab(crontab_executable, context.log_dir)
            install_crontab(crontab_executable, rendered_cron, written_path)
            verify_installed_crontab(crontab_executable, rendered_cron)

        print(
            json.dumps(
                {
                    "app_dir": str(context.app_dir),
                    "backup_path": None if backup_path is None else str(backup_path),
                    "entry_count": entry_count,
                    "env_file": str(context.env_file),
                    "installed": context.install,
                    "log_dir": str(context.log_dir),
                    "output_path": None if written_path is None else str(written_path),
                    "template_path": str(context.template_path),
                    "uv_bin": str(context.uv_bin),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    except CronInstallError as exc:
        print(str(exc), file=sys.stderr)
        return 1


def build_context(args: argparse.Namespace) -> RenderContext:
    validate_cli_path("template", args.template)
    validate_cli_path("app_dir", args.app_dir)
    validate_cli_path("log_dir", args.log_dir)
    validate_cli_path("env_file", args.env_file)
    if args.output:
        validate_cli_path("output_path", args.output)

    app_dir = resolve_path(args.app_dir)
    uv_bin = resolve_executable(args.uv_bin)
    log_dir = resolve_path(args.log_dir)
    env_file = resolve_path(args.env_file)
    output_path = resolve_path(args.output) if args.output else None
    template_path = resolve_path(args.template)

    validate_template_path(template_path)
    validate_safe_path("app_dir", app_dir)
    validate_safe_path("uv_bin", uv_bin)
    validate_safe_path("log_dir", log_dir)
    validate_safe_path("env_file", env_file)
    if output_path is not None:
        validate_safe_path("output_path", output_path)

    if args.install:
        validate_runtime_path("app_dir", app_dir, path_type="dir")
        validate_runtime_path("log_dir", log_dir, path_type="dir")
        validate_runtime_path("env_file", env_file, path_type="file")
        validate_runtime_path("uv_bin", uv_bin, path_type="file", executable=True)

    return RenderContext(
        template_path=template_path,
        app_dir=app_dir,
        uv_bin=uv_bin,
        log_dir=log_dir,
        env_file=env_file,
        output_path=output_path,
        install=args.install,
        crontab_bin=str(args.crontab_bin),
    )


def resolve_path(path_like: Path) -> Path:
    return path_like.expanduser().resolve(strict=False)


def validate_template_path(template_path: Path) -> None:
    if not template_path.is_file():
        raise CronInstallError(f"Cron template does not exist: {template_path}")


def validate_cli_path(name: str, path: Path) -> None:
    raw_path = str(path)
    if raw_path.startswith("~"):
        return
    if not path.is_absolute():
        raise CronInstallError(f"{name} must be an absolute path: {path}")


def validate_safe_path(name: str, path: Path) -> None:
    if not path.is_absolute():
        raise CronInstallError(f"{name} must be an absolute path: {path}")
    if any(character.isspace() for character in str(path)):
        raise CronInstallError(f"{name} must not contain whitespace: {path}")


def validate_runtime_path(
    name: str,
    path: Path,
    *,
    path_type: str,
    executable: bool = False,
) -> None:
    if path_type == "dir" and not path.is_dir():
        raise CronInstallError(f"{name} directory does not exist: {path}")
    if path_type == "file" and not path.is_file():
        raise CronInstallError(f"{name} file does not exist: {path}")
    if executable and not os.access(path, os.X_OK):
        raise CronInstallError(f"{name} is not executable: {path}")


def render_cron_template(context: RenderContext) -> str:
    rendered = context.template_path.read_text(encoding="utf-8")
    rendered = rendered.replace(PLACEHOLDER_APP_DIR, str(context.app_dir))
    rendered = rendered.replace(PLACEHOLDER_UV_BIN, str(context.uv_bin))
    rendered = rendered.replace(PLACEHOLDER_LOG_DIR, str(context.log_dir))
    rendered = rendered.replace(PLACEHOLDER_ENV_FILE, str(context.env_file))

    if any(
        placeholder in rendered
        for placeholder in (
            PLACEHOLDER_APP_DIR,
            PLACEHOLDER_UV_BIN,
            PLACEHOLDER_LOG_DIR,
            PLACEHOLDER_ENV_FILE,
        )
    ):
        raise CronInstallError("Cron template still contains unresolved placeholders.")
    return rendered


def validate_rendered_cron(rendered_cron: str) -> int:
    entry_count = 0
    for line_number, raw_line in enumerate(rendered_cron.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if is_environment_assignment(line):
            continue

        columns = line.split()
        if len(columns) < 6:
            raise CronInstallError(
                f"Invalid cron entry at line {line_number}: expected at least 6 columns."
            )
        entry_count += 1

    if entry_count == 0:
        raise CronInstallError("Cron template does not contain any runnable entries.")
    return entry_count


def is_environment_assignment(line: str) -> bool:
    if "=" not in line:
        return False
    key, _, value = line.partition("=")
    if not key or not value:
        return False
    return " " not in key and "\t" not in key


def write_output_if_requested(rendered_cron: str, output_path: Path | None) -> Path | None:
    if output_path is None:
        return None

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered_cron, encoding="utf-8")
    return output_path


def resolve_executable(command: str) -> Path:
    if not command:
        raise CronInstallError("crontab executable must not be empty.")

    if "/" in command:
        executable = Path(command).expanduser().resolve(strict=False)
        validate_safe_path("crontab_bin", executable)
        validate_runtime_path("crontab_bin", executable, path_type="file", executable=True)
        return executable

    resolved = shutil.which(command)
    if resolved is None:
        raise CronInstallError(f"crontab executable is not available: {command}")
    return Path(resolved)


def backup_existing_crontab(crontab_executable: Path, log_dir: Path) -> Path | None:
    result = subprocess.run(
        [str(crontab_executable), "-l"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        backup_path = log_dir / f"crontab.backup.{utc_timestamp()}.txt"
        backup_path.write_text(result.stdout, encoding="utf-8")
        return backup_path

    stderr_text = (result.stderr or result.stdout).strip().lower()
    if result.returncode == 1 and "no crontab for" in stderr_text:
        return None

    raise CronInstallError(
        f"Failed to read current crontab. exit_code={result.returncode}, stderr={result.stderr.strip()}"
    )


def install_crontab(
    crontab_executable: Path,
    rendered_cron: str,
    output_path: Path | None,
) -> None:
    temp_path: Path | None = None
    install_path = output_path
    if install_path is None:
        with tempfile.NamedTemporaryFile(
            prefix="bingwall-cron-",
            suffix=".tmp",
            delete=False,
            mode="w",
            encoding="utf-8",
        ) as handle:
            handle.write(rendered_cron)
            temp_path = Path(handle.name)
            install_path = temp_path

    try:
        result = subprocess.run(
            [str(crontab_executable), str(install_path)],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise CronInstallError(
                f"Failed to install crontab. exit_code={result.returncode}, stderr={result.stderr.strip()}"
            )
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def verify_installed_crontab(crontab_executable: Path, rendered_cron: str) -> None:
    result = subprocess.run(
        [str(crontab_executable), "-l"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise CronInstallError(
            f"Failed to verify installed crontab. exit_code={result.returncode}, stderr={result.stderr.strip()}"
        )

    if normalize_crontab_text(result.stdout) != normalize_crontab_text(rendered_cron):
        raise CronInstallError("Installed crontab does not match the rendered BingWall template.")


def normalize_crontab_text(text: str) -> str:
    normalized_lines = [line.rstrip() for line in text.splitlines()]
    return "\n".join(normalized_lines).strip()


def utc_timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


if __name__ == "__main__":
    sys.exit(main())
