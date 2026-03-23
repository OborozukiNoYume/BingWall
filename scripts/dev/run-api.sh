#!/usr/bin/env bash
set -euo pipefail

VENV_DIR="${VENV_DIR:-.venv}"

"${VENV_DIR}/bin/python" -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
