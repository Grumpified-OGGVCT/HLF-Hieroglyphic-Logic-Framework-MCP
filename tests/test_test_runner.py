from __future__ import annotations

from pathlib import Path


def test_run_pytest_suite_records_passing_summary(monkeypatch, tmp_path: Path) -> None:
    from hlf_mcp import test_runner

    recorded: list[dict[str, object]] = []

    class FakeMetrics:
        def __init__(self, metrics_dir: Path) -> None:
            self.metrics_dir = metrics_dir

        def record_test(
            self,
            test_name: str,
            passed: bool,
            duration_ms: float,
            error: str = "",
            details: dict[str, object] | None = None,
        ) -> str:
            recorded.append(
                {
                    "test_name": test_name,
                    "passed": passed,
                    "duration_ms": duration_ms,
                    "error": error,
                    "details": details or {},
                }
            )
            return "test-id"

    class Completed:
        returncode = 0
        stdout = "5 passed in 0.12s\n"
        stderr = ""

    monkeypatch.setattr(test_runner, "HLFMetrics", FakeMetrics)
    monkeypatch.setattr(test_runner.subprocess, "run", lambda *args, **kwargs: Completed())

    summary = test_runner.run_pytest_suite(["tests", "-q"], cwd=tmp_path, metrics_dir=tmp_path)

    assert summary.passed is True
    assert summary.exit_code == 0
    assert summary.counts["passed"] == 5
    assert recorded[0]["test_name"] == "pytest_default_suite"
    assert recorded[0]["passed"] is True
    assert (tmp_path / test_runner.LATEST_SUMMARY_FILE).exists()
    assert (tmp_path / test_runner.HISTORY_FILE).exists()


def test_run_pytest_suite_records_failure_details(monkeypatch, tmp_path: Path) -> None:
    from hlf_mcp import test_runner

    recorded: list[dict[str, object]] = []

    class FakeMetrics:
        def __init__(self, metrics_dir: Path) -> None:
            self.metrics_dir = metrics_dir

        def record_test(
            self,
            test_name: str,
            passed: bool,
            duration_ms: float,
            error: str = "",
            details: dict[str, object] | None = None,
        ) -> str:
            recorded.append(
                {
                    "test_name": test_name,
                    "passed": passed,
                    "duration_ms": duration_ms,
                    "error": error,
                    "details": details or {},
                }
            )
            return "test-id"

    class Completed:
        returncode = 1
        stdout = "2 passed, 1 failed in 0.20s\n"
        stderr = "AssertionError: boom\n"

    monkeypatch.setattr(test_runner, "HLFMetrics", FakeMetrics)
    monkeypatch.setattr(test_runner.subprocess, "run", lambda *args, **kwargs: Completed())

    summary = test_runner.run_pytest_suite(["tests", "-q"], cwd=tmp_path, metrics_dir=tmp_path)

    assert summary.passed is False
    assert summary.counts["passed"] == 2
    assert summary.counts["failed"] == 1
    assert recorded[0]["passed"] is False
    assert recorded[0]["error"] == "AssertionError: boom"
    assert recorded[0]["details"] == {
        "command": [test_runner.sys.executable, "-m", "pytest", "tests", "-q"],
        "exit_code": 1,
        "counts": summary.counts,
    }
