#!/usr/bin/env python3

import argparse
import base64
import json
import os
import sys
import urllib.parse
import urllib.request
import urllib.error


def load_env(path):
    env = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
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
    except FileNotFoundError:
        return env
    return env


def build_headers(auth_type, email, token):
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if auth_type == "bearer":
        headers["Authorization"] = f"Bearer {token}"
    else:
        userpass = f"{email}:{token}".encode("utf-8")
        basic = base64.b64encode(userpass).decode("ascii")
        headers["Authorization"] = f"Basic {basic}"
    return headers


def http_json(method, url, headers, body=None):
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw), resp.headers
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"HTTP {exc.code} for {url}: {raw[:200].strip()}"
        ) from None
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Non-JSON response from {url}: {exc}") from None


def list_projects(base_url, headers):
    start_at = 0
    max_results = 50
    projects = []
    while True:
        url = (
            f"{base_url}/rest/api/3/project/search?"
            + urllib.parse.urlencode({"startAt": start_at, "maxResults": max_results})
        )
        data, resp_headers = http_json("GET", url, headers)
        if resp_headers.get("x-seraph-loginreason") == "AUTHENTICATED_FAILED":
            raise RuntimeError("Authentication failed for Jira API.")
        projects.extend(data.get("values", []))
        if data.get("isLast") is True:
            break
        if not data.get("values"):
            break
        start_at += max_results
    return projects


def fetch_issues(base_url, headers, jql, limit, page_size):
    issues = []
    next_page_token = None
    while len(issues) < limit:
        body = {
            "jql": jql,
            "maxResults": min(page_size, limit - len(issues)),
            "fields": [
                "summary",
                "status",
                "assignee",
                "updated",
                "issuetype",
                "project",
                "priority",
                "description",
            ],
        }
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
        next_page_token = data.get("nextPageToken")
        if not next_page_token:
            break
    return issues


def check_auth(base_url, headers):
    http_json("GET", f"{base_url}/rest/api/3/myself", headers)


def format_issues(issues, fmt):
    if fmt == "json":
        return json.dumps({"count": len(issues), "issues": issues}, indent=2)
    lines = []

    def adf_to_text(node):
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

    def fmt_assignee(fields):
        assignee = fields.get("assignee")
        if not assignee:
            return "Unassigned"
        return assignee.get("displayName") or "Unassigned"

    def fmt_description(fields):
        desc = fields.get("description")
        text = adf_to_text(desc)
        return text.strip()

    if fmt == "markdown":
        lines.append(f"# Jira issues ({len(issues)})")
        lines.append("")
        for issue in issues:
            fields = issue.get("fields", {})
            desc = fmt_description(fields)
            lines.append(
                f"- **{issue.get('key')}**: {fields.get('summary','')}"
                f" | {fields.get('status',{}).get('name','')}"
                f" | {fmt_assignee(fields)}"
                f" | {fields.get('updated','')}"
            )
            if desc:
                for dline in desc.splitlines():
                    lines.append(f"  {dline}")
                lines.append("")
    else:
        for issue in issues:
            fields = issue.get("fields", {})
            desc = fmt_description(fields)
            lines.append(
                f"{issue.get('key')}\t"
                f"{fields.get('summary','')}\t"
                f"{fields.get('status',{}).get('name','')}\t"
                f"{fmt_assignee(fields)}\t"
                f"{fields.get('updated','')}\t"
                f"{desc}"
            )
    return "\n".join(lines).rstrip() + "\n"


def main():
    parser = argparse.ArgumentParser(description="Fetch Jira issues to stdout.")
    parser.add_argument(
        "jql", nargs="?", default="order by updated desc", help="JQL query"
    )
    parser.add_argument(
        "--format",
        choices=["json", "markdown", "text"],
        default="json",
        help="Output format",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Max number of issues to fetch",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=50,
        help="Page size for Jira API",
    )
    parser.add_argument(
        "--list-projects",
        action="store_true",
        help="List project keys and names instead of fetching issues",
    )
    parser.add_argument(
        "--auth",
        choices=["auto", "basic", "bearer"],
        default="auto",
        help="Auth type (default: auto)",
    )
    parser.add_argument(
        "--env-file", default=".env", help="Path to .env (default: .env)"
    )
    args = parser.parse_args()

    file_env = load_env(args.env_file)
    config = dict(os.environ)
    config.update(file_env)

    email = config.get("JIRA_EMAIL", "")
    token = config.get("JIRA_API_TOKEN", "")
    base_url = config.get("JIRA_BASE_URL", "")
    auth_type = config.get("JIRA_AUTH_TYPE", "").strip().lower() or args.auth

    if not token or not base_url:
        print("Missing JIRA_API_TOKEN or JIRA_BASE_URL in .env", file=sys.stderr)
        sys.exit(1)

    if auth_type == "auto":
        auth_type = "basic" if email else "bearer"

    if auth_type == "basic" and not email:
        print("Missing JIRA_EMAIL for basic auth", file=sys.stderr)
        sys.exit(1)

    headers = build_headers(auth_type, email, token)

    try:
        check_auth(base_url, headers)
    except RuntimeError as exc:
        print(
            f"Auth check failed: {exc}\n"
            "Verify JIRA_EMAIL + JIRA_API_TOKEN. If using a PAT bearer token, set "
            "JIRA_AUTH_TYPE=bearer or pass --auth bearer.",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.list_projects:
        projects = list_projects(base_url, headers)
        for p in projects:
            key = p.get("key", "")
            name = p.get("name", "")
            print(f"{key}\t{name}")
        return

    issues = fetch_issues(base_url, headers, args.jql, args.limit, args.page_size)
    try:
        sys.stdout.write(format_issues(issues, args.format))
    except BrokenPipeError:
        sys.exit(0)


if __name__ == "__main__":
    main()
def check_auth(base_url, headers):
    http_json("GET", f"{base_url}/rest/api/3/myself", headers)
