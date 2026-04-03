#!/usr/bin/env bash
set -euo pipefail

# Copy this file before use if you do not want to expose credentials in shell history.
# Example:
#   cp scripts/dev/playwright_smoke_with_admin.example.sh /tmp/bingwall-browser-smoke.sh
#   chmod 700 /tmp/bingwall-browser-smoke.sh
#   edit the variables below
#   /tmp/bingwall-browser-smoke.sh

export BINGWALL_BROWSER_BASE_URL="${BINGWALL_BROWSER_BASE_URL:-http://127.0.0.1:30003}"
export BINGWALL_BROWSER_HEADLESS="${BINGWALL_BROWSER_HEADLESS:-true}"

# Fill in a real admin account before running.
export BINGWALL_ADMIN_USERNAME="${BINGWALL_ADMIN_USERNAME:-admin}"
export BINGWALL_ADMIN_PASSWORD="${BINGWALL_ADMIN_PASSWORD:-replace-with-a-real-admin-password}"

node scripts/dev/playwright_smoke.js
