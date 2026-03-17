#!/usr/bin/env python3
"""
HLF Fork Monitor — scan GitHub forks for ethics compliance and open advisory issues.

This script uses the GitHub REST API to find forks of the HLF repository,
spot-checks the presence of core governance files via the Contents API, and
optionally creates a GitHub issue on non-compliant forks to notify maintainers.

Design principles (same as the rest of HLF):
  • WARN-FIRST   — issues are advisory notices, not bans or takedowns.
  • TRANSPARENT  — the issue body explains exactly what was checked and why.
  • HUMAN-FIRST  — no automated action is taken beyond creating an issue;
                   a human decides what to do next.
  • NON-INVASIVE — the script is read-only unless --create-issues is passed
                   explicitly.  It never modifies fork repositories directly.

Usage::

    # Dry run — just list compliance status
    python scripts/monitor_forks.py --repo Grumpified-OGGVCT/HLF-Hieroglyphic-Logic-Framework-MCP

    # Create advisory issues on non-compliant forks (requires GITHUB_TOKEN)
    python scripts/monitor_forks.py \\
        --repo Grumpified-OGGVCT/HLF-Hieroglyphic-Logic-Framework-MCP \\
        --create-issues \\
        --token $GITHUB_TOKEN

    # Output as JSON for CI consumption
    python scripts/monitor_forks.py --repo owner/repo --json

Environment:
    GITHUB_TOKEN — optional GitHub personal access token for authenticated
                   requests (higher rate limits, ability to create issues).

People are the priority.  AI is the tool.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

# ── Constants ────────────────────────────────────────────────────────────────

GITHUB_API = "https://api.github.com"
USER_AGENT = "HLF-Fork-Monitor/1.0 (github.com/Grumpified-OGGVCT/HLF-Hieroglyphic-Logic-Framework-MCP)"

# Files to spot-check via the GitHub contents API (raw presence check)
SPOT_CHECK_FILES = [
    "HLF_ETHICAL_GOVERNOR.md",
    "governance/align_rules.json",
    "hlf_mcp/hlf/ethics/governor.py",
    "hlf_mcp/hlf/capsules.py",
]

ADVISORY_ISSUE_TITLE = "⚠ HLF Ethics Compliance Advisory"

ADVISORY_ISSUE_BODY_TEMPLATE = """\
## HLF Ethics Compliance Advisory

Hi! This is an automated, non-invasive advisory from the upstream \
[HLF-Hieroglyphic-Logic-Framework-MCP](https://github.com/{upstream_repo}) project.

Our fork monitor noticed that the following governance files are missing or \
may have been removed from this fork:

{missing_files}

### Why does this matter?

These files are part of the HLF ethical governance layer that protects your \
users from prompt injection, credential exposure, path traversal, and similar \
threats.  Without them, your fork may expose users to risks that the upstream \
project guards against.

### What to do

You have complete freedom to extend or adapt HLF however you like — this is \
**not** a takedown request or a threat.  We're just letting you know so you \
can make an informed decision.

Options:
1. **Restore the missing files** from upstream:
   ```bash
   git remote add upstream https://github.com/{upstream_repo}.git
   git fetch upstream
   git checkout upstream/main -- {restore_paths}
   ```
2. **Implement equivalent protections** in your own way (totally fine!).
3. **Ignore this notice** if you've intentionally removed these files and \
   understand the implications.

### Verify compliance locally

```bash
python scripts/fork_compliance_check.py --path .
```

This notice was generated automatically and does not represent legal action. \
Questions? Open an issue on the [upstream repository](https://github.com/{upstream_repo}).

*People are the priority.  AI is the tool.*
"""

# ── Data types ────────────────────────────────────────────────────────────────

@dataclass
class ForkStatus:
    full_name: str
    html_url: str
    owner: str
    repo: str
    missing_files: list[str] = field(default_factory=list)
    compliant: bool = True
    issue_created: bool = False
    issue_url: str = ""
    error: str = ""


@dataclass
class MonitorReport:
    upstream_repo: str
    total_forks: int
    compliant: list[ForkStatus] = field(default_factory=list)
    non_compliant: list[ForkStatus] = field(default_factory=list)
    errored: list[ForkStatus] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        def _fs(s: ForkStatus) -> dict[str, Any]:
            return {
                "full_name":      s.full_name,
                "html_url":       s.html_url,
                "compliant":      s.compliant,
                "missing_files":  s.missing_files,
                "issue_created":  s.issue_created,
                "issue_url":      s.issue_url,
                "error":          s.error,
            }
        return {
            "upstream_repo": self.upstream_repo,
            "total_forks":   self.total_forks,
            "compliant":     [_fs(s) for s in self.compliant],
            "non_compliant": [_fs(s) for s in self.non_compliant],
            "errored":       [_fs(s) for s in self.errored],
            "summary": {
                "compliant":     len(self.compliant),
                "non_compliant": len(self.non_compliant),
                "errored":       len(self.errored),
            },
        }


# ── GitHub API helpers ────────────────────────────────────────────────────────

def _api_request(
    path: str,
    token: str | None = None,
    method: str = "GET",
    body: dict[str, Any] | None = None,
) -> Any:
    """
    Make a GitHub API request.  Returns parsed JSON or raises urllib.error.HTTPError.
    """
    url = f"{GITHUB_API}{path}"
    headers = {
        "Accept":     "application/vnd.github+json",
        "User-Agent": USER_AGENT,
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    data = json.dumps(body).encode() if body else None
    req  = urllib.request.Request(url, data=data, headers=headers, method=method)

    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def _file_exists_in_fork(owner: str, repo: str, path: str, token: str | None) -> bool:
    """Check if a file exists in a GitHub repo via the contents API."""
    try:
        _api_request(f"/repos/{owner}/{repo}/contents/{path}", token=token)
        return True
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return False
        raise


def _get_forks(upstream_owner: str, upstream_repo: str, token: str | None) -> list[dict[str, Any]]:
    """Return all forks (paginated)."""
    forks: list[dict[str, Any]] = []
    page = 1
    while True:
        batch = _api_request(
            f"/repos/{upstream_owner}/{upstream_repo}/forks?per_page=100&page={page}",
            token=token,
        )
        if not batch:
            break
        forks.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return forks


def _create_advisory_issue(
    owner: str,
    repo: str,
    missing_files: list[str],
    upstream_repo: str,
    token: str,
) -> str:
    """Create an advisory issue on a non-compliant fork.  Returns the issue URL."""
    missing_md  = "\n".join(f"- `{f}`" for f in missing_files)
    restore_str = " ".join(missing_files)
    body = ADVISORY_ISSUE_BODY_TEMPLATE.format(
        upstream_repo  = upstream_repo,
        missing_files  = missing_md,
        restore_paths  = restore_str,
    )
    result = _api_request(
        f"/repos/{owner}/{repo}/issues",
        token   = token,
        method  = "POST",
        body    = {"title": ADVISORY_ISSUE_TITLE, "body": body},
    )
    return result.get("html_url", "")


# ── Monitor ───────────────────────────────────────────────────────────────────

def monitor(
    upstream_repo: str,
    token: str | None = None,
    create_issues: bool = False,
    rate_limit_delay: float = 0.5,
) -> MonitorReport:
    """
    Scan all forks of the upstream repo and check for ethics compliance.

    Args:
        upstream_repo:   "owner/repo" string.
        token:           GitHub PAT (optional but needed for create_issues).
        create_issues:   If True, open advisory issues on non-compliant forks.
        rate_limit_delay: Seconds to sleep between API calls (be polite).

    Returns:
        MonitorReport
    """
    parts = upstream_repo.split("/", 1)
    if len(parts) != 2:
        raise ValueError(f"upstream_repo must be 'owner/repo', got: '{upstream_repo}'")
    upstream_owner, upstream_repo_name = parts

    forks = _get_forks(upstream_owner, upstream_repo_name, token)
    report = MonitorReport(upstream_repo=upstream_repo, total_forks=len(forks))

    for fork in forks:
        owner = fork["owner"]["login"]
        repo  = fork["name"]
        status = ForkStatus(
            full_name = fork["full_name"],
            html_url  = fork["html_url"],
            owner     = owner,
            repo      = repo,
        )

        try:
            missing: list[str] = []
            for file_path in SPOT_CHECK_FILES:
                time.sleep(rate_limit_delay)
                if not _file_exists_in_fork(owner, repo, file_path, token):
                    missing.append(file_path)

            status.missing_files = missing
            status.compliant     = len(missing) == 0

            if not status.compliant and create_issues and token:
                time.sleep(rate_limit_delay)
                try:
                    issue_url = _create_advisory_issue(
                        owner, repo, missing, upstream_repo, token
                    )
                    status.issue_created = True
                    status.issue_url     = issue_url
                except Exception as exc:  # noqa: BLE001
                    status.error = f"Could not create issue: {exc}"

            if status.compliant:
                report.compliant.append(status)
            else:
                report.non_compliant.append(status)

        except Exception as exc:  # noqa: BLE001
            status.error = str(exc)
            report.errored.append(status)

    return report


# ── CLI ────────────────────────────────────────────────────────────────────────

def _print_report(report: MonitorReport) -> None:
    width = 70
    print("=" * width)
    print("  HLF Fork Monitor Report")
    print(f"  Upstream: {report.upstream_repo}")
    print(f"  Total forks scanned: {report.total_forks}")
    print("=" * width)

    if report.non_compliant:
        print(f"\n⚠  NON-COMPLIANT FORKS ({len(report.non_compliant)})")
        for s in report.non_compliant:
            print(f"\n  {s.html_url}")
            for f in s.missing_files:
                print(f"    ✗ missing: {f}")
            if s.issue_created:
                print(f"    → Advisory issue created: {s.issue_url}")
            if s.error:
                print(f"    ! Error: {s.error}")

    if report.compliant:
        print(f"\n✓  COMPLIANT FORKS ({len(report.compliant)})")
        for s in report.compliant:
            print(f"  ✓ {s.html_url}")

    if report.errored:
        print(f"\n!  ERRORS ({len(report.errored)})")
        for s in report.errored:
            print(f"  ! {s.full_name}: {s.error}")

    print()
    print("-" * width)
    print(
        f"  Summary — compliant: {len(report.compliant)}  "
        f"non-compliant: {len(report.non_compliant)}  "
        f"errors: {len(report.errored)}"
    )
    print("=" * width)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="HLF Fork Monitor — non-invasive ethics compliance scanner.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--repo",
        required=True,
        help="Upstream repo in 'owner/repo' format.",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("GITHUB_TOKEN"),
        help="GitHub PAT (default: $GITHUB_TOKEN).",
    )
    parser.add_argument(
        "--create-issues",
        action="store_true",
        help="Create advisory issues on non-compliant forks (requires --token).",
    )
    parser.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Output as JSON.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Seconds between API calls (default: 0.5).",
    )
    args = parser.parse_args()

    if args.create_issues and not args.token:
        print("ERROR: --create-issues requires --token or $GITHUB_TOKEN.", file=sys.stderr)
        sys.exit(2)

    try:
        report = monitor(
            upstream_repo  = args.repo,
            token          = args.token,
            create_issues  = args.create_issues,
            rate_limit_delay = args.delay,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.as_json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        _print_report(report)

    sys.exit(0 if not report.non_compliant else 1)


if __name__ == "__main__":
    main()
