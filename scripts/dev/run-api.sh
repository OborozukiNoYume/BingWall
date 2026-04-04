#!/usr/bin/env bash
set -euo pipefail

UV_BIN="${UV_BIN:-uv}"

exec "${UV_BIN}" run python -c 'from app.core.config import get_settings; import uvicorn; settings = get_settings(); uvicorn.run("app.main:create_app", factory=True, host=settings.app_host, port=settings.app_port)'
