#!/usr/bin/env python3
"""
Fetch Jira issues and write each as a Markdown file.
"""

import argparse
import base64
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, Iterable, List, Optional


DEFAULT_FIELDS = [
    "summary",
    "status",
    "assignee",
    "updated",
    "issuetype",
    "project",
    "priority",
    "description",
]


def load_env(path: Path) -> Dict[str, str]:
    env: Dict[str, str] = {}
    if not path.exists():
        return env
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip()
        if (val.startswith('"') and val.endswith('"')) or (
            val.startswith("'") and val.endswith("'")
        ):
            val = val[1:-1]
        env[key] = val
    return env


def build_headers(email: str, token: str) -> Dict[str, str]:
    userpass = f"{email}:{token}".encode("utf-8")
    basic = base64.b64encode(userpass).decode("ascii")
    return {
        "Authorization": f"Basic {basic}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def http_json(method: str, url: str, headers: Dict[str, str], body: Optional[dict] = None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw), resp.headers
    except urllib.error.HTTPError as exc:  # type: ignore[unreachable]
        raw = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} for {url}: {raw}") from None
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Non-JSON response from {url}: {exc}") from None


def check_auth(base_url: str, headers: Dict[str, str]) -> None:
    http_json("GET", f"{base_url}/rest/api/3/myself", headers)


def fetch_issues(
    base_url: str,
    headers: Dict[str, str],
    jql: str,
    fields: Iterable[str],
    page_size: int = 100,
    limit: Optional[int] = None,
) -> List[dict]:
    issues: List[dict] = []
    next_page_token: Optional[str] = None
    fields_list = list(fields)
    while True:
        remaining = limit - len(issues) if limit is not None else page_size
        page_limit = min(page_size, remaining) if limit is not None else page_size
        body = {"jql": jql, "maxResults": page_limit, "fields": fields_list}
        if next_page_token:
            body["nextPageToken"] = next_page_token
        data, resp_headers = http_json(
            "POST", f"{base_url}/rest/api/3/search/jql", headers, body
        )
        if resp_headers.get("x-seraph-loginreason") == "AUTHENTICATED_FAILED":
            raise RuntimeError("Authentication failed for Jira API.")
        batch = data.get("issues", [])
        issues.extend(batch)
        if data.get("isLast") or not batch:
            break
        if limit is not None and len(issues) >= limit:
            break
        next_page_token = data.get("nextPageToken")
        if not next_page_token:
            break
    if limit is not None:
        return issues[:limit]
    return issues


def adf_to_text(node) -> str:
    # Minimal ADF to text renderer; keeps paragraphs, lists, and code blocks readable.
    if not node:
        return ""
    if isinstance(node, list):
        parts = [adf_to_text(n) for n in node]
        return "\n".join(p for p in parts if p)
    if not isinstance(node, dict):
        return ""
    node_type = node.get("type")
    content = node.get("content", [])
    if node_type == "text":
        return node.get("text", "")
    if node_type in {"paragraph", "heading"}:
        return "".join(adf_to_text(c) for c in content)
    if node_type == "hardBreak":
        return "\n"
    if node_type in {"bulletList", "orderedList"}:
        parts = []
        for item in content or []:
            item_text = adf_to_text(item)
            if item_text:
                for idx, line in enumerate(item_text.splitlines()):
                    prefix = "- " if idx == 0 else "  "
                    parts.append(prefix + line)
        return "\n".join(parts)
    if node_type == "listItem":
        return "\n".join(adf_to_text(c) for c in content)
    if node_type == "codeBlock":
        inner = "".join(adf_to_text(c) for c in content)
        return inner
    return "\n".join(adf_to_text(c) for c in content)


def issue_to_markdown(issue: dict) -> str:
    fields = issue.get("fields", {})
    summary = fields.get("summary", "")
    status = fields.get("status", {}).get("name", "")
    assignee = fields.get("assignee", {}) or {}
    assignee_name = assignee.get("displayName") or "Unassigned"
    updated = fields.get("updated", "")
    issuetype = fields.get("issuetype", {}).get("name", "")
    priority = fields.get("priority", {}).get("name", "")
    project = fields.get("project", {}).get("key") or ""
    description = adf_to_text(fields.get("description", {})).strip()

    lines = [
        f"# {issue.get('key', '')} {summary}".strip(),
        "",
        f"- Status: {status}",
        f"- Assignee: {assignee_name}",
        f"- Updated: {updated}",
        f"- Type: {issuetype}",
        f"- Priority: {priority}",
        f"- Project: {project}",
    ]
    if description:
        lines.extend(["", "## Description", description])
    return "\n".join(lines).rstrip() + "\n"


def write_issue_files(issues: List[dict], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for issue in issues:
        key = issue.get("key") or issue.get("id")
        if not key:
            continue
        filename = f"{key}.md"
        path = output_dir / filename
        path.write_text(issue_to_markdown(issue), encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Fetch Jira issues and write Markdown files.")
    parser.add_argument(
        "--project",
        default="CDDOS",
        help="Project key (default: CDDOS)",
    )
    parser.add_argument(
        "--jql",
        default=None,
        help="Optional full JQL. If omitted, uses 'project = <project> order by updated desc'.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of issues to fetch (default: all available).",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=100,
        help="Page size per request (default: 100).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("volumes/brain/jira"),
        help="Directory to write Markdown files (default: volumes/brain/jira).",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(".env"),
        help="Path to .env file containing JIRA_EMAIL, JIRA_API_TOKEN, JIRA_BASE_URL.",
    )
    args = parser.parse_args(argv)

    file_env = load_env(args.env_file)
    env = {**os.environ, **file_env}
    email = env.get("JIRA_EMAIL", "")
    token = env.get("JIRA_API_TOKEN", "")
    base_url = env.get("JIRA_BASE_URL", "")

    if not email or not token or not base_url:
        raise SystemExit("Missing JIRA_EMAIL, JIRA_API_TOKEN, or JIRA_BASE_URL.")

    headers = build_headers(email, token)
    check_auth(base_url, headers)

    jql = args.jql or f"project = {args.project} order by updated desc"
    issues = fetch_issues(
        base_url=base_url,
        headers=headers,
        jql=jql,
        fields=DEFAULT_FIELDS,
        page_size=args.page_size,
        limit=args.limit,
    )
    write_issue_files(issues, args.output)
    print(f"Wrote {len(issues)} issues to {args.output}")


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(0)
