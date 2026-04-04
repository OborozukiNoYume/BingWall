#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

export BINGWALL_VERIFY_DEPLOY_APP_HOST="${BINGWALL_VERIFY_DEPLOY_APP_HOST:-127.0.0.1}"
export BINGWALL_VERIFY_DEPLOY_APP_PORT="${BINGWALL_VERIFY_DEPLOY_APP_PORT:-28000}"
export BINGWALL_VERIFY_DEPLOY_NGINX_PORT="${BINGWALL_VERIFY_DEPLOY_NGINX_PORT:-28080}"

if [[ -z "${XDG_RUNTIME_DIR:-}" && -d "/run/user/$(id -u)" ]]; then
  export XDG_RUNTIME_DIR="/run/user/$(id -u)"
fi

if [[ -n "${XDG_RUNTIME_DIR:-}" && -z "${DBUS_SESSION_BUS_ADDRESS:-}" && -S "${XDG_RUNTIME_DIR}/bus" ]]; then
  export DBUS_SESSION_BUS_ADDRESS="unix:path=${XDG_RUNTIME_DIR}/bus"
fi

for command in uv docker systemd-analyze systemd-run systemctl journalctl systemd-tmpfiles; do
  if ! command -v "${command}" >/dev/null 2>&1; then
    echo "[verify-deploy-workflow] missing required command: ${command}" >&2
    exit 1
  fi
done

if ! systemctl --user is-system-running >/dev/null 2>&1; then
  cat >&2 <<'EOF'
[verify-deploy-workflow] systemd --user is not reachable for the current runner account.
Expected a Linux self-hosted runner with:
  - an active user manager (`systemctl --user is-system-running`)
  - Docker access
  - XDG_RUNTIME_DIR / DBUS_SESSION_BUS_ADDRESS pointing at the runner user's bus

If the runner is launched as a service, ensure the runner account has a persistent user session,
for example by enabling linger and exporting:
  XDG_RUNTIME_DIR=/run/user/<uid>
  DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/<uid>/bus
EOF
  exit 1
fi

cd "${REPO_ROOT}"
exec make verify-deploy
