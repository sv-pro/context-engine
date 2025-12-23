import argparse
import os
import sys

import requests


DEFAULT_URL = os.environ.get("CONTEXT_DRIVER_BASE_URL", "http://localhost:8000")
DEFAULT_STRATEGY = os.environ.get("SEARCH_STRATEGY", "super_hybrid")


def parse_args():
    parser = argparse.ArgumentParser(description="Context Driver CLI")
    parser.add_argument("command", nargs="?", default="/context", help="Command like /context")
    parser.add_argument("query", nargs="*", help="Query text (or pipe via stdin)")
    parser.add_argument("--url", default=DEFAULT_URL, help="Context Driver base URL")
    parser.add_argument("--strategy", default=DEFAULT_STRATEGY, help="Search strategy")
    parser.add_argument("--limit", type=int, default=5, help="Number of sources to fetch")
    parser.add_argument("--show-system-prompt", action="store_true", help="Include system prompt output")
    parser.add_argument("--json", action="store_true", help="Print raw JSON response")
    parser.add_argument("--timeout", type=float, default=30, help="Request timeout in seconds")
    return parser.parse_args()


def read_query(args):
    if args.query:
        return " ".join(args.query).strip()
    if sys.stdin.isatty():
        return ""
    return sys.stdin.read().strip()


def request_context(args, query):
    url = args.url.rstrip("/")
    payload = {
        "query": query,
        "limit": args.limit,
        "strategy": args.strategy,
    }
    if args.show_system_prompt:
        payload["include_system_prompt"] = True

    return requests.post(f"{url}/v1/context", json=payload, timeout=args.timeout)


def print_context(data, show_system_prompt):
    print(f"Query: {data.get('query', '')}")
    print(f"Strategy: {data.get('strategy', '')}")
    print(f"Limit: {data.get('limit', '')}")
    sources = data.get("sources", [])
    print(f"Sources: {len(sources)}")
    print("")
    print("--- Context ---")
    print(data.get("context_text") or "[No context available]")

    if sources:
        print("")
        print("--- Sources ---")
        for src in sources:
            section = src.get("section")
            section_display = f" > {section}" if section else ""
            similarity = src.get("similarity")
            if isinstance(similarity, (int, float)):
                similarity_display = f" similarity={similarity:.4f}"
            else:
                similarity_display = ""
            print(
                f"[{src.get('source_num')}] "
                f"{src.get('title')}{section_display} "
                f"({src.get('file_path')}){similarity_display}"
            )

    if show_system_prompt and "system_prompt" in data:
        print("")
        print("--- System Prompt ---")
        print(data.get("system_prompt") or "")


def main():
    args = parse_args()
    command = (args.command or "").strip()
    if command.startswith("/"):
        command = command[1:]

    if command != "context":
        sys.stderr.write("Unsupported command. Use /context.\n")
        return 2

    query = read_query(args)
    if not query:
        sys.stderr.write("Query is required. Pass it as arguments or via stdin.\n")
        return 2

    try:
        response = request_context(args, query)
    except requests.RequestException as exc:
        sys.stderr.write(f"Request failed: {exc}\n")
        return 1

    if args.json:
        sys.stdout.write(response.text)
        if not response.text.endswith("\n"):
            sys.stdout.write("\n")
        return 0 if response.ok else 1

    if response.status_code != 200:
        sys.stderr.write(f"Error: HTTP {response.status_code}\n{response.text}\n")
        return 1

    data = response.json()
    print_context(data, args.show_system_prompt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
