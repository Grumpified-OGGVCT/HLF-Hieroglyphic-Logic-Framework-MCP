from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _api_request(path: str) -> Any:
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
    }
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_code_scanning_alerts(tool_name: str = "CodeQL") -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    page = 1
    encoded_tool = urllib.parse.quote(tool_name)
    while True:
        payload = _api_request(f"code-scanning/alerts?tool_name={encoded_tool}&per_page=100&page={page}")
        if not isinstance(payload, list):
            break
        alerts.extend(item for item in payload if isinstance(item, dict))
        if len(payload) < 100:
            break
        page += 1
    return alerts


def build_code_scanning_summary_payload(alerts: list[dict[str, Any]], *, tool_name: str = "CodeQL") -> dict[str, Any]:
    severity_counts: dict[str, int] = {}
    state_counts: dict[str, int] = {}
    open_alerts = 0

    for alert in alerts:
        state = str(alert.get("state") or "unknown").lower()
        state_counts[state] = state_counts.get(state, 0) + 1
        if state == "open":
            open_alerts += 1

        rule = alert.get("rule") or {}
        severity = str(
            rule.get("security_severity_level")
            or rule.get("severity")
            or alert.get("severity")
            or "unknown"
        ).lower()
        severity_counts[severity] = severity_counts.get(severity, 0) + 1

    total_alerts = len(alerts)
    return {
        "tool": tool_name,
        "collection_state": "summary_collected",
        "alerts_available": total_alerts > 0,
        "codeql_category": "python-security",
        "evidence_refs": ["github-api:code-scanning-alerts"],
        "collected_at": _utc_now(),
        "summary": {
            "total_alerts": total_alerts,
            "open_alerts": open_alerts,
            "closed_alerts": total_alerts - open_alerts,
            "severity_counts": severity_counts,
            "state_counts": state_counts,
        },
    }


def build_fallback_payload(*, reason: str, tool_name: str = "CodeQL") -> dict[str, Any]:
    return {
        "tool": tool_name,
        "collection_state": "metadata_only",
        "alerts_available": False,
        "codeql_category": "python-security",
        "evidence_refs": [f"github-api-unavailable:{reason}"],
        "collected_at": _utc_now(),
        "summary": {
            "total_alerts": None,
            "open_alerts": None,
            "closed_alerts": None,
            "severity_counts": {},
            "state_counts": {},
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch GitHub code scanning summary for weekly artifacts.")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tool-name", default="CodeQL")
    args = parser.parse_args(argv)

    try:
        alerts = fetch_code_scanning_alerts(tool_name=args.tool_name)
        payload = build_code_scanning_summary_payload(alerts, tool_name=args.tool_name)
    except Exception as exc:
        payload = build_fallback_payload(reason=exc.__class__.__name__, tool_name=args.tool_name)

    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "collection_state": payload["collection_state"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())