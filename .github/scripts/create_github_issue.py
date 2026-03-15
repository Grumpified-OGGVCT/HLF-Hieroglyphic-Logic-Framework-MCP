"""
create_github_issue.py — Create or update a GitHub issue from a workflow.

Uses the GitHub REST API with GITHUB_TOKEN authentication.
Checks for an existing open issue with the same title first to avoid duplicates.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from typing import Any


def _gh_api(method: str, path: str, payload: dict | None = None) -> dict[str, Any]:
    token = os.environ.get("GITHUB_TOKEN", "")
    repo  = os.environ.get("GITHUB_REPOSITORY", "")
    if not token:
        raise RuntimeError("GITHUB_TOKEN not set")
    if not repo:
        raise RuntimeError("GITHUB_REPOSITORY not set")

    url = f"https://api.github.com/repos/{repo}/{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
    }
    body = json.dumps(payload).encode("utf-8") if payload else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API {method} {url} → {exc.code}: {body_text[:500]}") from exc


def find_existing_issue(title: str, label: str) -> int | None:
    """Return issue number if an open issue with this exact title + label exists."""
    result = _gh_api("GET", f"issues?state=open&labels={label}&per_page=50")
    if isinstance(result, list):
        for issue in result:
            if issue.get("title") == title:
                return issue["number"]
    return None


def create_or_update_issue(
    title: str,
    body: str,
    labels: list[str],
    assignees: list[str] | None = None,
) -> dict[str, Any]:
    """Create a new issue, or update the body of an existing open issue."""
    label = labels[0] if labels else ""
    existing = find_existing_issue(title, label)
    if existing:
        print(f"[create_github_issue] Updating existing issue #{existing}", file=sys.stderr)
        return _gh_api("PATCH", f"issues/{existing}", {"body": body, "labels": labels})
    else:
        payload: dict[str, Any] = {"title": title, "body": body, "labels": labels}
        if assignees:
            payload["assignees"] = assignees
        result = _gh_api("POST", "issues", payload)
        print(f"[create_github_issue] Created issue #{result.get('number')}: {title}", file=sys.stderr)
        return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", required=True)
    parser.add_argument("--body", required=True, help="Issue body text or @file.md to read from file")
    parser.add_argument("--labels", default="", help="Comma-separated label names")
    parser.add_argument("--assignees", default="", help="Comma-separated GitHub usernames")
    args = parser.parse_args()

    body = args.body
    if body.startswith("@"):
        with open(body[1:], encoding="utf-8") as f:
            body = f.read()

    labels = [l.strip() for l in args.labels.split(",") if l.strip()]
    assignees = [a.strip() for a in args.assignees.split(",") if a.strip()]

    result = create_or_update_issue(
        title=args.title,
        body=body,
        labels=labels,
        assignees=assignees or None,
    )
    print(json.dumps({"issue_number": result.get("number"), "url": result.get("html_url")}, indent=2))


if __name__ == "__main__":
    main()
