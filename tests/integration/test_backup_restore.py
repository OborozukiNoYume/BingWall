from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


def test_t2_5_backup_restore_rehearsal_script_completes_successfully() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, str(repo_root / "scripts" / "verify_t2_5.py")],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert payload["deep_health_status"] == "ok"
    assert Path(payload["verification_record_path"]).is_file()
