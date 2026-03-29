#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import argparse
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from typing import TypedDict


REPO_ROOT = Path(__file__).resolve().parents[1]
NGINX_IMAGE = "nginx:1.27-alpine"
APP_PORT = 8000
DEFAULT_NGINX_PORT = 18080
HTTP_TIMEOUT_SECONDS = 5
HTTP_WAIT_SECONDS = 30
RELATIVE_IMAGE_PATH = Path("bing/2026/03/en-US/t1-6-smoke.jpg")
JPEG_BYTES = b"\xff\xd8\xff\xdbt1-6-smoke-jpeg"


class VerificationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class VerificationPaths:
    workspace: Path
    database_path: Path
    public_dir: Path
    log_dir: Path
    nginx_config_path: Path


class HttpResponse(TypedDict):
    status: int
    headers: dict[str, str]
    body: bytes


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify BingWall T1.6 deployment acceptance in a rootless local environment."
    )
    parser.add_argument(
        "--nginx-port",
        type=int,
        default=DEFAULT_NGINX_PORT,
        help="Temporary local port used by the Dockerized nginx proxy.",
    )
    parser.add_argument(
        "--keep-workspace",
        action="store_true",
        help="Keep the generated temporary workspace for debugging.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_prerequisites()

    paths = prepare_workspace(listen_port=args.nginx_port)
    unit_name = f"bingwall-t1-6-{uuid.uuid4().hex[:8]}"
    container_name = f"bingwall-nginx-{uuid.uuid4().hex[:8]}"

    try:
        verify_systemd_unit_file(paths=paths)
        verify_tmpfiles_template()
        wallpaper_id = seed_sample_wallpaper(paths)
        start_uvicorn_under_systemd(paths=paths, unit_name=unit_name)
        verify_systemd_restart(unit_name=unit_name)
        verify_nginx_proxy(
            paths=paths,
            container_name=container_name,
            wallpaper_id=wallpaper_id,
            listen_port=args.nginx_port,
            unit_name=unit_name,
        )
        print_summary(paths=paths, listen_port=args.nginx_port)
        return 0
    except VerificationError as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        if args.keep_workspace:
            print(f"[INFO] Workspace kept at: {paths.workspace}", file=sys.stderr)
        return 1
    finally:
        stop_systemd_unit(unit_name)
        stop_nginx_container(container_name)
        if not args.keep_workspace:
            shutil.rmtree(paths.workspace, ignore_errors=True)


def ensure_prerequisites() -> None:
    if shutil.which("uv") is None:
        raise VerificationError("Required command is not available: uv")
    if not (REPO_ROOT / ".venv").exists():
        raise VerificationError(
            f"Python virtual environment is missing: {REPO_ROOT / '.venv'}. Run `make setup` first."
        )

    for command in ("docker", "systemd-analyze", "systemd-run", "systemctl", "journalctl"):
        if shutil.which(command) is None:
            raise VerificationError(f"Required command is not available: {command}")

    if shutil.which("systemd-tmpfiles") is None:
        raise VerificationError("Required command is not available: systemd-tmpfiles")


def prepare_workspace(*, listen_port: int) -> VerificationPaths:
    workspace = Path(tempfile.mkdtemp(prefix="bingwall-t1-6-"))
    runtime_root = workspace / "runtime"
    public_dir = runtime_root / "images" / "public"
    database_path = runtime_root / "data" / "bingwall.sqlite3"
    log_dir = runtime_root / "logs"

    public_dir.mkdir(parents=True, exist_ok=True)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    nginx_config_path = workspace / "bingwall.nginx.conf"
    nginx_template = (REPO_ROOT / "deploy/nginx/bingwall.conf").read_text(encoding="utf-8")
    nginx_template = nginx_template.replace("listen 80;", f"listen {listen_port};", 1)
    nginx_template = nginx_template.replace("listen [::]:80;", f"listen [::]:{listen_port};", 1)
    nginx_config_path.write_text(nginx_template, encoding="utf-8")

    return VerificationPaths(
        workspace=workspace,
        database_path=database_path,
        public_dir=public_dir,
        log_dir=log_dir,
        nginx_config_path=nginx_config_path,
    )


def verify_systemd_unit_file(*, paths: VerificationPaths) -> None:
    service_path = REPO_ROOT / "deploy/systemd/bingwall-api.service"
    local_verify_env = paths.workspace / "local-verify.env"
    local_verify_env.write_text("", encoding="utf-8")
    local_service_path = paths.workspace / "bingwall-api.local-verify.service"
    service_text = service_path.read_text(encoding="utf-8")
    service_text = service_text.replace("/opt/bingwall/app", str(REPO_ROOT))
    service_text = service_text.replace("/etc/bingwall/bingwall.env", str(local_verify_env))
    local_service_path.write_text(service_text, encoding="utf-8")
    run_command(
        ["systemd-analyze", "verify", str(local_service_path)],
        description="systemd-analyze verify",
    )
    run_command(
        ["systemd-analyze", "security", "--offline=yes", str(service_path)],
        description="systemd-analyze security",
    )


def verify_tmpfiles_template() -> None:
    tmp_root = Path(tempfile.mkdtemp(prefix="bingwall-tmpfiles-"))
    try:
        template_path = REPO_ROOT / "deploy/systemd/bingwall.tmpfiles.conf"
        result = run_command(
            [
                "systemd-tmpfiles",
                "--create",
                "--graceful",
                f"--root={tmp_root}",
                str(template_path),
            ],
            description="systemd-tmpfiles create",
        )
        if "Changing mode 02750 to 0750 because of changed ownership." in result.stderr:
            print(
                "[INFO] Rootless tmpfiles validation cannot keep the setgid bit without real owner changes."
            )

        expected_dirs = (
            tmp_root / "var/lib/bingwall/data",
            tmp_root / "var/lib/bingwall/images/tmp",
            tmp_root / "var/lib/bingwall/images/failed",
            tmp_root / "var/lib/bingwall/images/public",
            tmp_root / "var/log/bingwall",
            tmp_root / "var/backups/bingwall",
            tmp_root / "etc/bingwall",
        )
        for directory in expected_dirs:
            if not directory.is_dir():
                raise VerificationError(f"tmpfiles did not create expected directory: {directory}")
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)


def seed_sample_wallpaper(paths: VerificationPaths) -> int:
    sys.path.insert(0, str(REPO_ROOT))
    from app.repositories.migrations import migrate_database

    migrate_database(paths.database_path)

    image_path = paths.public_dir / RELATIVE_IMAGE_PATH
    image_path.parent.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(JPEG_BYTES)

    connection = sqlite3.connect(paths.database_path)
    try:
        now_utc = utc_now_isoformat()
        cursor = connection.execute(
            """
            INSERT INTO wallpapers (
                source_type,
                source_key,
                market_code,
                wallpaper_date,
                title,
                subtitle,
                description,
                copyright_text,
                source_name,
                content_status,
                is_public,
                is_downloadable,
                publish_start_at_utc,
                publish_end_at_utc,
                origin_page_url,
                origin_image_url,
                origin_width,
                origin_height,
                resource_status,
                created_at_utc,
                updated_at_utc
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ready', ?, ?);
            """,
            (
                "bing",
                "bing:en-US:2026-03-25:t1-6-smoke",
                "en-US",
                "2026-03-25",
                "T1.6 Smoke",
                "T1.6 Smoke subtitle",
                "T1.6 Smoke description",
                "T1.6 Smoke copyright",
                "Bing",
                "enabled",
                1,
                1,
                "2000-01-01T00:00:00Z",
                "2100-01-01T00:00:00Z",
                "https://www.bing.com/example",
                "https://www.bing.com/t1-6-smoke.jpg",
                1920,
                1080,
                now_utc,
                now_utc,
            ),
        )
        wallpaper_lastrowid = cursor.lastrowid
        if wallpaper_lastrowid is None:
            raise VerificationError("Failed to create sample wallpaper.")
        wallpaper_id = int(wallpaper_lastrowid)
        resource_cursor = connection.execute(
            """
            INSERT INTO image_resources (
                wallpaper_id,
                resource_type,
                storage_backend,
                relative_path,
                filename,
                file_ext,
                mime_type,
                file_size_bytes,
                width,
                height,
                source_url,
                source_url_hash,
                content_hash,
                downloaded_at_utc,
                integrity_check_result,
                image_status,
                last_processed_at_utc,
                created_at_utc,
                updated_at_utc
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ready', ?, ?, ?);
            """,
            (
                wallpaper_id,
                "original",
                "local",
                str(RELATIVE_IMAGE_PATH).replace("\\", "/"),
                RELATIVE_IMAGE_PATH.name,
                ".jpg",
                "image/jpeg",
                len(JPEG_BYTES),
                1920,
                1080,
                "https://www.bing.com/t1-6-smoke.jpg",
                "t1-6-source-hash",
                "t1-6-content-hash",
                now_utc,
                "passed",
                now_utc,
                now_utc,
                now_utc,
            ),
        )
        resource_lastrowid = resource_cursor.lastrowid
        if resource_lastrowid is None:
            raise VerificationError("Failed to create sample image resource.")
        connection.execute(
            "UPDATE wallpapers SET default_resource_id = ? WHERE id = ?;",
            (int(resource_lastrowid), wallpaper_id),
        )
        connection.commit()
        return wallpaper_id
    finally:
        connection.close()


def start_uvicorn_under_systemd(*, paths: VerificationPaths, unit_name: str) -> None:
    env_vars = build_runtime_env(paths)
    uv_executable = shutil.which("uv")
    if uv_executable is None:
        raise VerificationError("Required command is not available: uv")
    command = [
        "systemd-run",
        "--user",
        "--unit",
        unit_name,
        "--collect",
        f"--property=WorkingDirectory={REPO_ROOT}",
        "--property=Restart=on-failure",
        "--property=RestartSec=1",
        "--property=Type=simple",
    ]
    for key, value in env_vars.items():
        command.append(f"--setenv={key}={value}")
    command.extend([
        uv_executable,
        "run",
        "--directory",
        str(REPO_ROOT),
        "--no-sync",
        "python",
        "-m",
        "uvicorn",
        "app.main:create_app",
        "--factory",
        "--host",
        "127.0.0.1",
        "--port",
        str(APP_PORT),
    ])
    run_command(command, description="systemd-run uvicorn")
    wait_for_url(f"http://127.0.0.1:{APP_PORT}/api/health/live", expected_status=200)


def verify_systemd_restart(*, unit_name: str) -> None:
    run_command(
        ["systemctl", "--user", "restart", unit_name],
        description="systemctl --user restart",
    )
    wait_for_url(f"http://127.0.0.1:{APP_PORT}/api/health/live", expected_status=200)


def verify_nginx_proxy(
    *,
    paths: VerificationPaths,
    container_name: str,
    wallpaper_id: int,
    listen_port: int,
    unit_name: str,
) -> None:
    verify_nginx_config(paths=paths)
    start_nginx_container(paths=paths, container_name=container_name)
    wait_for_url(f"http://127.0.0.1:{listen_port}/api/health/live", expected_status=200)

    health_response = fetch(f"http://127.0.0.1:{listen_port}/api/health/live")
    site_info_response = fetch(f"http://127.0.0.1:{listen_port}/api/public/site-info")
    page_response = fetch(f"http://127.0.0.1:{listen_port}/")
    asset_response = fetch(f"http://127.0.0.1:{listen_port}/assets/site.js")
    detail_response = fetch(f"http://127.0.0.1:{listen_port}/api/public/wallpapers/{wallpaper_id}")
    image_response = fetch(
        f"http://127.0.0.1:{listen_port}/images/{RELATIVE_IMAGE_PATH.as_posix()}"
    )

    if health_response["status"] != 200:
        raise VerificationError("nginx proxy health check did not return HTTP 200.")
    if json.loads(site_info_response["body"].decode("utf-8"))["data"]["site_name"] != "BingWall":
        raise VerificationError("nginx proxy site info response is invalid.")
    if b'data-page="home"' not in page_response["body"]:
        raise VerificationError("nginx proxy did not return the public home page.")
    if b'fetchEnvelope("/api/public/site-info")' not in asset_response["body"]:
        raise VerificationError("nginx did not serve the expected public asset.")
    if json.loads(detail_response["body"].decode("utf-8"))["data"]["id"] != wallpaper_id:
        raise VerificationError("nginx proxy wallpaper detail response is invalid.")
    if image_response["body"] != JPEG_BYTES:
        raise VerificationError("nginx did not serve the seeded public image bytes.")
    if not health_response["headers"].get("x-trace-id"):
        raise VerificationError("Proxied response did not return X-Trace-Id.")

    wait_for_log_line(paths.log_dir / "nginx.access.log", "/api/health/live")
    journal_output = run_command(
        ["journalctl", "--user", "-u", unit_name, "-n", "100", "--no-pager"],
        description="journalctl --user",
    ).stdout
    if "Application configured for 127.0.0.1:8000." not in journal_output:
        raise VerificationError("Application startup log was not found in the user journal.")
    if "Request completed method=GET path=/api/health/live status_code=200" not in journal_output:
        raise VerificationError("Application access log was not found in the user journal.")


def verify_nginx_config(*, paths: VerificationPaths) -> None:
    mounts = build_nginx_mounts(paths)
    command = [
        "docker",
        "run",
        "--rm",
        "--network",
        "host",
        *mounts,
        NGINX_IMAGE,
        "nginx",
        "-t",
    ]
    run_command(command, description="dockerized nginx -t")


def start_nginx_container(*, paths: VerificationPaths, container_name: str) -> None:
    mounts = build_nginx_mounts(paths)
    command = [
        "docker",
        "run",
        "--detach",
        "--rm",
        "--name",
        container_name,
        "--network",
        "host",
        *mounts,
        NGINX_IMAGE,
    ]
    run_command(command, description="dockerized nginx start")


def build_nginx_mounts(paths: VerificationPaths) -> list[str]:
    return [
        "--volume",
        f"{paths.nginx_config_path}:/etc/nginx/conf.d/default.conf:ro",
        "--volume",
        f"{REPO_ROOT / 'web/public/assets'}:/opt/bingwall/app/web/public/assets:ro",
        "--volume",
        f"{paths.public_dir}:/var/lib/bingwall/images/public:ro",
        "--volume",
        f"{paths.log_dir}:/var/log/bingwall",
    ]


def build_runtime_env(paths: VerificationPaths) -> dict[str, str]:
    return {
        "BINGWALL_APP_ENV": "production",
        "BINGWALL_APP_HOST": "127.0.0.1",
        "BINGWALL_APP_PORT": str(APP_PORT),
        "BINGWALL_APP_BASE_URL": "http://127.0.0.1",
        "BINGWALL_SITE_NAME": "BingWall",
        "BINGWALL_SITE_DESCRIPTION": "Bing wallpaper service",
        "BINGWALL_DATABASE_PATH": str(paths.database_path),
        "BINGWALL_STORAGE_TMP_DIR": str(paths.workspace / "runtime/images/tmp"),
        "BINGWALL_STORAGE_PUBLIC_DIR": str(paths.public_dir),
        "BINGWALL_STORAGE_FAILED_DIR": str(paths.workspace / "runtime/images/failed"),
        "BINGWALL_BACKUP_DIR": str(paths.workspace / "runtime/backups"),
        "BINGWALL_COLLECT_BING_ENABLED": "true",
        "BINGWALL_COLLECT_BING_DEFAULT_MARKET": "en-US",
        "BINGWALL_COLLECT_BING_TIMEOUT_SECONDS": "10",
        "BINGWALL_COLLECT_BING_MAX_DOWNLOAD_RETRIES": "3",
        "BINGWALL_SECURITY_SESSION_SECRET": "0123456789abcdef0123456789abcdef",
        "BINGWALL_SECURITY_SESSION_TTL_HOURS": "12",
        "BINGWALL_LOG_LEVEL": "INFO",
    }


def wait_for_url(url: str, *, expected_status: int) -> None:
    deadline = time.monotonic() + HTTP_WAIT_SECONDS
    while time.monotonic() < deadline:
        try:
            response = fetch(url)
        except VerificationError:
            time.sleep(1)
            continue
        if response["status"] == expected_status:
            return
        time.sleep(1)
    raise VerificationError(f"Timed out waiting for {url} to return HTTP {expected_status}.")


def fetch(url: str) -> HttpResponse:
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            return {
                "status": response.getcode(),
                "headers": {key.lower(): value for key, value in response.headers.items()},
                "body": response.read(),
            }
    except urllib.error.URLError as exc:
        raise VerificationError(f"HTTP request failed for {url}: {exc}") from exc


def wait_for_log_line(log_path: Path, expected_fragment: str) -> None:
    deadline = time.monotonic() + HTTP_WAIT_SECONDS
    while time.monotonic() < deadline:
        if log_path.exists():
            content = log_path.read_text(encoding="utf-8")
            if expected_fragment in content:
                return
        time.sleep(1)
    raise VerificationError(f"Expected nginx access log fragment not found: {expected_fragment}")


def stop_systemd_unit(unit_name: str) -> None:
    run_command(
        ["systemctl", "--user", "stop", unit_name],
        description="systemctl --user stop",
        check=False,
    )


def stop_nginx_container(container_name: str) -> None:
    run_command(
        ["docker", "rm", "--force", container_name],
        description="docker rm --force",
        check=False,
    )


def run_command(
    command: list[str],
    *,
    description: str,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.stdout.strip():
        print(f"[INFO] {description} stdout:\n{result.stdout.strip()}")
    if result.stderr.strip():
        print(f"[INFO] {description} stderr:\n{result.stderr.strip()}")
    if check and result.returncode != 0:
        raise VerificationError(
            f"{description} failed with exit code {result.returncode}: {' '.join(command)}"
        )
    return result


def utc_now_isoformat() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def print_summary(*, paths: VerificationPaths, listen_port: int) -> None:
    print("[OK] T1.6 verification passed.")
    print(f"[OK] Temporary nginx endpoint: http://127.0.0.1:{listen_port}")
    print(f"[OK] Sample database: {paths.database_path}")
    print(f"[OK] Sample image: {paths.public_dir / RELATIVE_IMAGE_PATH}")


if __name__ == "__main__":
    sys.exit(main())
