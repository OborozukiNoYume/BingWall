#!/usr/bin/env bash

set -euo pipefail

if [[ -z "${GITHUB_TOKEN:-}" ]]; then
  echo "GITHUB_TOKEN is required" >&2
  exit 1
fi

OWNER="${GITHUB_OWNER:-OborozukiNoYume}"
REPO="${GITHUB_REPO:-BingWall}"
API_URL="https://api.github.com/repos/${OWNER}/${REPO}/branches/main/protection"

curl \
  --fail \
  --silent \
  --show-error \
  -X PUT \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  "${API_URL}" \
  -d @- <<'EOF'
{
  "required_status_checks": {
    "strict": true,
    "contexts": [
      "verify"
    ]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": false,
    "required_approving_review_count": 1,
    "require_last_push_approval": false
  },
  "restrictions": null,
  "required_conversation_resolution": true,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "block_creations": false,
  "lock_branch": false,
  "allow_fork_syncing": false
}
EOF

echo "main branch protection applied for ${OWNER}/${REPO}"
