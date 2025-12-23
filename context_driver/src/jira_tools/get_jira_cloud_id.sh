#!/bin/bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "${ROOT_DIR}"

if [ ! -f ".env" ]; then
  echo "Missing .env in ${ROOT_DIR}" >&2
  exit 1
fi

source .env

curl -sS --user "${JIRA_EMAIL}:${JIRA_API_TOKEN}" \
  --header 'Accept: application/json' \
  "${JIRA_BASE_URL}/_edge/tenant_info"
