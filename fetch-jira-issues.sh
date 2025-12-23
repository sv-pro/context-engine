#!/bin/bash

set -euo pipefail

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  cat <<'EOF'
Usage: ./fetch-jira-issues.sh [JQL] [format]

Defaults:
  JQL:     "order by updated desc"
  format:  json | markdown | text  (default: json)

Examples:
  ./fetch-jira-issues.sh
  ./fetch-jira-issues.sh "project = ABC order by updated desc" markdown
  ./fetch-jira-issues.sh "assignee = currentUser()" json > my-issues.json
EOF
  exit 0
fi

source .env

: "${JIRA_EMAIL:?Missing JIRA_EMAIL in .env}"
: "${JIRA_API_TOKEN:?Missing JIRA_API_TOKEN in .env}"
: "${JIRA_BASE_URL:?Missing JIRA_BASE_URL in .env}"

JQL="${1:-order by updated desc}"
FORMAT="${2:-json}"
MAX_RESULTS="${MAX_RESULTS:-50}"

case "${FORMAT}" in
  json|markdown|text) ;;
  *)
    echo "Unsupported format: ${FORMAT}" >&2
    exit 1
    ;;
esac

tmp_file="$(mktemp)"
body_file="$(mktemp)"

python3 - "${JQL}" "${MAX_RESULTS}" > "${body_file}" <<'PY'
import json
import sys

jql = sys.argv[1]
max_results = int(sys.argv[2])

body = {
    "jql": jql,
    "maxResults": max_results,
    "fields": [
        "summary",
        "status",
        "assignee",
        "updated",
        "issuetype",
        "project",
        "priority",
    ],
}

print(json.dumps(body))
PY

curl -sS --user "${JIRA_EMAIL}:${JIRA_API_TOKEN}" \
  --header 'Accept: application/json' \
  --header 'Content-Type: application/json' \
  --url "${JIRA_BASE_URL}/rest/api/3/search/jql" \
  --data @"${body_file}" \
  > "${tmp_file}"

case "${FORMAT}" in
  json)
    cat "${tmp_file}"
    ;;
  markdown|text)
    python3 - "${tmp_file}" "${FORMAT}" <<'PY'
import json
import sys

in_path, fmt = sys.argv[1], sys.argv[2]

with open(in_path, "r", encoding="utf-8") as f:
    data = json.load(f)

issues = data.get("issues", [])

def fmt_assignee(fields):
    assignee = fields.get("assignee")
    if not assignee:
        return "Unassigned"
    return assignee.get("displayName") or "Unassigned"

lines = []
if fmt == "markdown":
    lines.append(f"# Jira issues ({len(issues)})")
    lines.append("")
    for issue in issues:
        fields = issue.get("fields", {})
        lines.append(
            f"- **{issue.get('key')}**: {fields.get('summary','')}"
            f" | {fields.get('status',{}).get('name','')}"
            f" | {fmt_assignee(fields)}"
            f" | {fields.get('updated','')}"
        )
else:
    for issue in issues:
        fields = issue.get("fields", {})
        lines.append(
            f"{issue.get('key')}\t"
            f"{fields.get('summary','')}\t"
            f"{fields.get('status',{}).get('name','')}\t"
            f"{fmt_assignee(fields)}\t"
            f"{fields.get('updated','')}"
        )

sys.stdout.write("\n".join(lines).rstrip() + "\n")
PY
    ;;
esac

rm -f "${tmp_file}" "${body_file}"
