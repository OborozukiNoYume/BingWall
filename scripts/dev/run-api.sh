#!/usr/bin/env bash
set -euo pipefail

UV_BIN="${UV_BIN:-uv}"

exec "${UV_BIN}" run python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
