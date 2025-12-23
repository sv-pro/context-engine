#!/bin/bash

set -euo pipefail

source .env
# JIRA_API_TOKEN, JIRA_EMAIL, JIRA_BASE_URL should be set in .env file

curl -sS --user "${JIRA_EMAIL}:${JIRA_API_TOKEN}" \
  --header 'Accept: application/json' \
  "${JIRA_BASE_URL}/_edge/tenant_info"