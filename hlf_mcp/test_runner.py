from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from hlf.mcp_metrics import HLFMetrics


DEFAULT_PYTEST_ARGS = ["tests", "-q", "--tb=short"]
DEFAULT_METRICS_DIR = Path.home() / ".sovereign" / "mcp_metrics"
LATEST_SUMMARY_FILE = "pytest_last_run.json"
HISTORY_FILE = "pytest_history.jsonl"


@dataclass(slots=True)
class PytestSuiteSummary:
    command: list[str]
    exit_code: int
    passed: bool
    duration_ms: float
    counts: dict[str, int]
    stdout: str
    stderr: str
    metrics_dir: str


def _extract_counts(output: str) -> dict[str, int]:
    counts = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0, "xfailed": 0, "xpassed": 0}
    patterns = {
        "passed": r"(\d+)\s+passed",
        "failed": r"(\d+)\s+failed",
        "errors": r"(\d+)\s+error[s]?",
        "skipped": r"(\d+)\s+skipped",
        "xfailed": r"(\d+)\s+xfailed",
        "xpassed": r"(\d+)\s+xpassed",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, output, flags=re.IGNORECASE)
        if match:
            counts[key] = int(match.group(1))
    return counts


def _persist_summary(summary: PytestSuiteSummary, metrics_dir: Path) -> None:
    metrics_dir.mkdir(parents=True, exist_ok=True)
    latest_path = metrics_dir / LATEST_SUMMARY_FILE
    history_path = metrics_dir / HISTORY_FILE
    payload = asdict(summary)
    latest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    with history_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")


def run_pytest_suite(
    pytest_args: list[str] | None = None,
    *,
    cwd: Path | None = None,
    metrics_dir: Path | None = None,
) -> PytestSuiteSummary:
    effective_args = list(pytest_args or DEFAULT_PYTEST_ARGS)
    effective_cwd = cwd or Path(__file__).resolve().parent.parent
    effective_metrics_dir = metrics_dir or DEFAULT_METRICS_DIR
    command = [sys.executable, "-m", "pytest", *effective_args]

    started_at = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=str(effective_cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
    combined_output = "\n".join(part for part in [completed.stdout, completed.stderr] if part)
    counts = _extract_counts(combined_output)
    summary = PytestSuiteSummary(
        command=command,
        exit_code=completed.returncode,
        passed=completed.returncode == 0,
        duration_ms=duration_ms,
        counts=counts,
        stdout=completed.stdout,
        stderr=completed.stderr,
        metrics_dir=str(effective_metrics_dir),
    )

    metrics = HLFMetrics(effective_metrics_dir)
    metrics.record_test(
        "pytest_default_suite",
        passed=summary.passed,
        duration_ms=duration_ms,
        error=completed.stderr.strip(),
        details={
            "command": command,
            "exit_code": completed.returncode,
            "counts": counts,
        },
    )
    _persist_summary(summary, effective_metrics_dir)
    return summary


def main(argv: list[str] | None = None) -> int:
    summary = run_pytest_suite(pytest_args=argv or None)
    if summary.stdout:
        print(summary.stdout, end="")
    if summary.stderr:
        print(summary.stderr, file=sys.stderr, end="")
    print(
        f"\n[hlf_mcp.test_runner] passed={summary.passed} exit_code={summary.exit_code} "
        f"duration_ms={summary.duration_ms} metrics_dir={summary.metrics_dir}"
    )
    return summary.exit_code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))