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
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


def _gh_api(method: str, path: str, payload: dict | None = None) -> dict[str, Any]:
    token = os.environ.get("GITHUB_TOKEN", "")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
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
    label_query = urllib.parse.quote(label)
    result = _gh_api("GET", f"issues?state=open&labels={label_query}&per_page=50")
    if isinstance(result, list):
        for issue in result:
            if issue.get("title") == title:
                return issue["number"]
    return None


def list_open_pull_requests() -> list[dict[str, Any]]:
    result = _gh_api("GET", "pulls?state=open&per_page=100")
    return result if isinstance(result, list) else []


def find_conflicting_pull_request(
    *,
    head_branches: list[str] | None = None,
    base_branches: list[str] | None = None,
    labels: list[str] | None = None,
    title_substrings: list[str] | None = None,
) -> dict[str, Any] | None:
    wanted_head = {value for value in (head_branches or []) if value}
    wanted_base = {value for value in (base_branches or []) if value}
    wanted_labels = {value for value in (labels or []) if value}
    wanted_substrings = [value.lower() for value in (title_substrings or []) if value]

    for pr in list_open_pull_requests():
        reasons: list[str] = []
        head_ref = str(pr.get("head", {}).get("ref", ""))
        base_ref = str(pr.get("base", {}).get("ref", ""))
        pr_labels = {str(label.get("name", "")) for label in pr.get("labels", [])}
        searchable = "\n".join(
            [
                str(pr.get("title", "")),
                str(pr.get("body", "")),
            ]
        ).lower()

        if wanted_head and head_ref in wanted_head:
            reasons.append(f"head={head_ref}")
        if wanted_base and base_ref in wanted_base:
            reasons.append(f"base={base_ref}")
        if wanted_labels and pr_labels.intersection(wanted_labels):
            reasons.append(f"labels={','.join(sorted(pr_labels.intersection(wanted_labels)))}")
        matched_substrings = [needle for needle in wanted_substrings if needle in searchable]
        if matched_substrings:
            reasons.append(f"title/body~{','.join(matched_substrings)}")

        if reasons:
            pr["_conflict_reasons"] = reasons
            return pr
    return None


def create_or_update_issue(
    title: str,
    body: str,
    labels: list[str],
    assignees: list[str] | None = None,
    conflict_head_branches: list[str] | None = None,
    conflict_base_branches: list[str] | None = None,
    conflict_labels: list[str] | None = None,
    conflict_title_substrings: list[str] | None = None,
) -> dict[str, Any]:
    """Create a new issue, or update the body of an existing open issue."""
    conflict = find_conflicting_pull_request(
        head_branches=conflict_head_branches,
        base_branches=conflict_base_branches,
        labels=conflict_labels,
        title_substrings=conflict_title_substrings,
    )
    if conflict:
        print(
            f"[create_github_issue] Skipping due to conflicting PR #{conflict.get('number')} "
            f"({', '.join(conflict.get('_conflict_reasons', []))})",
            file=sys.stderr,
        )
        return {
            "skipped": True,
            "reason": "conflicting_open_pr",
            "conflicting_pr_number": conflict.get("number"),
            "conflicting_pr_url": conflict.get("html_url"),
            "conflicting_pr_title": conflict.get("title"),
        }

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
        print(
            f"[create_github_issue] Created issue #{result.get('number')}: {title}", file=sys.stderr
        )
        return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", required=True)
    parser.add_argument(
        "--body", required=True, help="Issue body text or @file.md to read from file"
    )
    parser.add_argument("--labels", default="", help="Comma-separated label names")
    parser.add_argument("--assignees", default="", help="Comma-separated GitHub usernames")
    parser.add_argument(
        "--conflict-head-branches",
        default="",
        help="Comma-separated PR head branches that should block issue creation",
    )
    parser.add_argument(
        "--conflict-base-branches",
        default="",
        help="Comma-separated PR base branches that should block issue creation",
    )
    parser.add_argument(
        "--conflict-labels",
        default="",
        help="Comma-separated PR labels that should block issue creation",
    )
    parser.add_argument(
        "--conflict-title-substrings",
        default="",
        help="Comma-separated lowercase/phrase substrings in PR title/body that should block issue creation",
    )
    args = parser.parse_args()

    body = args.body
    if body.startswith("@"):
        with open(body[1:], encoding="utf-8") as f:
            body = f.read()

    labels = [label.strip() for label in args.labels.split(",") if label.strip()]
    assignees = [a.strip() for a in args.assignees.split(",") if a.strip()]
    conflict_head_branches = [
        value.strip() for value in args.conflict_head_branches.split(",") if value.strip()
    ]
    conflict_base_branches = [
        value.strip() for value in args.conflict_base_branches.split(",") if value.strip()
    ]
    conflict_labels = [value.strip() for value in args.conflict_labels.split(",") if value.strip()]
    conflict_title_substrings = [
        value.strip() for value in args.conflict_title_substrings.split(",") if value.strip()
    ]

    result = create_or_update_issue(
        title=args.title,
        body=body,
        labels=labels,
        assignees=assignees or None,
        conflict_head_branches=conflict_head_branches or None,
        conflict_base_branches=conflict_base_branches or None,
        conflict_labels=conflict_labels or None,
        conflict_title_substrings=conflict_title_substrings or None,
    )
    print(
        json.dumps(
            {
                "issue_number": result.get("number"),
                "url": result.get("html_url"),
                "skipped": result.get("skipped", False),
                "reason": result.get("reason"),
                "conflicting_pr_number": result.get("conflicting_pr_number"),
                "conflicting_pr_url": result.get("conflicting_pr_url"),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
