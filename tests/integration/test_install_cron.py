from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import subprocess
import sys


def test_install_cron_script_renders_expected_template(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    app_dir = tmp_path / "app"
    venv_python = app_dir / ".venv" / "bin" / "python"
    log_dir = tmp_path / "logs"
    env_file = tmp_path / "bingwall.env"
    output_path = tmp_path / "rendered-cron.txt"

    app_dir.mkdir(parents=True, exist_ok=True)
    venv_python.parent.mkdir(parents=True, exist_ok=True)
    venv_python.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    venv_python.chmod(
        venv_python.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    )
    log_dir.mkdir(parents=True, exist_ok=True)
    env_file.write_text("BINGWALL_LOG_LEVEL=INFO\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts" / "install_cron.py"),
            "--app-dir",
            str(app_dir),
            "--venv-python",
            str(venv_python),
            "--log-dir",
            str(log_dir),
            "--env-file",
            str(env_file),
            "--output",
            str(output_path),
        ],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    rendered = output_path.read_text(encoding="utf-8")

    assert payload["installed"] is False
    assert payload["entry_count"] == 5
    assert payload["output_path"] == str(output_path)
    assert "CRON_TZ=UTC" in rendered
    assert str(app_dir) in rendered
    assert str(venv_python) in rendered
    assert str(log_dir) in rendered
    assert str(env_file) in rendered
    assert "scripts/run_backup.py" in rendered


def test_install_cron_script_installs_with_fake_crontab(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    state_dir = tmp_path / "fake-crontab-state"
    app_dir = tmp_path / "app"
    venv_python = app_dir / ".venv" / "bin" / "python"
    log_dir = tmp_path / "logs"
    env_file = tmp_path / "bingwall.env"
    fake_crontab = tmp_path / "fake-crontab.py"

    state_dir.mkdir(parents=True, exist_ok=True)
    app_dir.mkdir(parents=True, exist_ok=True)
    venv_python.parent.mkdir(parents=True, exist_ok=True)
    venv_python.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    venv_python.chmod(
        venv_python.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    )
    log_dir.mkdir(parents=True, exist_ok=True)
    env_file.write_text("BINGWALL_LOG_LEVEL=INFO\n", encoding="utf-8")
    (state_dir / "installed.txt").write_text("MAILTO=\"\"\n0 1 * * * echo old\n", encoding="utf-8")

    fake_crontab.write_text(
        """
#!/usr/bin/env python3
from pathlib import Path
import os
import sys

state_dir = Path(os.environ["FAKE_CRONTAB_STATE_DIR"])
installed_path = state_dir / "installed.txt"

if len(sys.argv) == 2 and sys.argv[1] == "-l":
    if installed_path.exists():
        sys.stdout.write(installed_path.read_text(encoding="utf-8"))
        sys.exit(0)
    sys.stderr.write("no crontab for bingwall\\n")
    sys.exit(1)

if len(sys.argv) == 2:
    source_path = Path(sys.argv[1])
    installed_path.write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")
    sys.exit(0)

sys.stderr.write("unsupported fake crontab invocation\\n")
sys.exit(2)
""".lstrip(),
        encoding="utf-8",
    )
    fake_crontab.chmod(
        fake_crontab.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    )

    result = subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts" / "install_cron.py"),
            "--install",
            "--app-dir",
            str(app_dir),
            "--venv-python",
            str(venv_python),
            "--log-dir",
            str(log_dir),
            "--env-file",
            str(env_file),
            "--crontab-bin",
            str(fake_crontab),
        ],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, "FAKE_CRONTAB_STATE_DIR": str(state_dir)},
    )

    payload = json.loads(result.stdout)
    installed_cron = (state_dir / "installed.txt").read_text(encoding="utf-8")

    assert payload["installed"] is True
    assert payload["backup_path"] is not None
    assert Path(payload["backup_path"]).read_text(encoding="utf-8") == "MAILTO=\"\"\n0 1 * * * echo old\n"
    assert "scripts/create_scheduled_collection_tasks.py" in installed_cron
    assert "scripts/run_resource_inspection.py" in installed_cron
    assert "scripts/run_wallpaper_archive.py" in installed_cron
    assert "scripts/run_backup.py" in installed_cron


def test_install_cron_script_rejects_relative_paths(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    output_path = tmp_path / "rendered-cron.txt"

    result = subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts" / "install_cron.py"),
            "--app-dir",
            "relative-app",
            "--output",
            str(output_path),
        ],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "absolute path" in result.stderr
