from pathlib import Path

import pytest

from hlf_mcp.hlf.hlfsh import HELP_TEXT, HLFShell
from hlf_mcp.hlf.hlftest import (
    HLFTestReport,
    HLFTestResult,
    HLFTestRunner,
    _cli_main,
    assert_compiles,
    assert_gas_under,
)


def _program(body: str) -> str:
    return f"[HLF-v3]\n{body}\nΩ\n"


class TestHLFTestHarness:
    def test_result_passed_property(self) -> None:
        result = HLFTestResult(source="test.hlf", compiles=True, lint_warnings=[])
        assert result.passed is True

    def test_report_counts(self) -> None:
        report = HLFTestReport(
            results=[
                HLFTestResult(source="a", compiles=True),
                HLFTestResult(source="b", compiles=False),
                HLFTestResult(source="c", compiles=True, lint_warnings=["warn"]),
            ]
        )
        assert report.total == 3
        assert report.passed == 1
        assert report.failed == 2
        assert report.compile_errors == 1

    def test_runner_accepts_bare_snippet(self) -> None:
        runner = HLFTestRunner()
        result = runner.test_source('SET name = "world"', name="snippet")
        assert result.compiles is True
        assert result.gas_used > 0

    def test_runner_reports_compile_failure(self) -> None:
        runner = HLFTestRunner()
        result = runner.test_source("not valid hlf")
        assert result.compiles is False
        assert result.compile_error != ""

    def test_runner_directory(self, tmp_path: Path) -> None:
        for name in ["a", "b"]:
            (tmp_path / f"{name}.hlf").write_text(_program("SET value = 1"), encoding="utf-8")
        report = HLFTestRunner().test_directory(tmp_path)
        assert report.total == 2
        assert report.total_gas > 0

    def test_assert_helpers(self) -> None:
        result = assert_compiles("SET port = 8080")
        assert result.compiles is True
        with pytest.raises(AssertionError, match="exceeds limit"):
            assert_gas_under("SET x = 1", limit=0)

    def test_cli_entry(self, tmp_path: Path) -> None:
        hlf_file = tmp_path / "ok.hlf"
        hlf_file.write_text(_program("SET ok = true"), encoding="utf-8")
        assert _cli_main([str(hlf_file)]) == 0


@pytest.fixture
def shell() -> HLFShell:
    return HLFShell(gas_limit=100)


class TestHLFShell:
    def test_help_command(self, shell: HLFShell) -> None:
        assert shell.handle_command(":help") == HELP_TEXT

    def test_eval_bare_set_persists_env(self, shell: HLFShell) -> None:
        output = shell.eval('SET name = "world"')
        assert "name = world" in output
        assert shell.env["name"] == "world"

    def test_gas_and_reset_commands(self, shell: HLFShell) -> None:
        shell.eval("SET count = 1")
        gas = shell.handle_command(":gas")
        assert gas is not None and "Gas used" in gas
        reset = shell.handle_command(":reset")
        assert reset is not None and "reset" in reset.lower()
        assert shell.gas_used == 0
        assert shell.env == {}

    def test_ast_and_lint_commands(self, shell: HLFShell) -> None:
        shell.eval('SET name = "world"')
        ast_text = shell.handle_command(":ast")
        lint_text = shell.handle_command(":lint")
        assert ast_text is not None and '"kind": "program"' in ast_text
        assert lint_text is not None

    def test_load_and_quit(self, shell: HLFShell, tmp_path: Path) -> None:
        hlf_file = tmp_path / "loadable.hlf"
        hlf_file.write_text(_program("SET loaded = true"), encoding="utf-8")
        loaded = shell.handle_command(f":load {hlf_file}")
        assert loaded is not None and "loaded = true" in loaded
        with pytest.raises(SystemExit):
            shell.handle_command(":quit")
