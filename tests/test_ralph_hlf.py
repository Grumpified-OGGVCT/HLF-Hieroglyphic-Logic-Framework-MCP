"""Integration tests for scripts/ralph_hlf.sh — HLF-aware RALPH harness."""

import json
import os
import shutil
import subprocess

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
RALPH_HLF = os.path.join(SCRIPTS_DIR, "ralph_hlf.sh")
RALPH_LOOP = os.path.join(SCRIPTS_DIR, "ralph_loop.sh")

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _find_bash():
    """Find a usable bash. Prefer Git Bash over WSL bash, which doesn't
    understand Windows-style paths."""
    for candidate in (
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files\Git\usr\bin\bash.exe",
    ):
        if os.path.isfile(candidate):
            return candidate
    found = shutil.which("bash")
    if found:
        return found
    return "bash"


BASH = _find_bash()
BASH_AVAILABLE = os.path.isfile(BASH) or shutil.which("bash") is not None


def _run_ralph_hlf(
    *,
    env=None,
    extra_args=None,
    command=None,
    stdin=None,
):
    """Run ralph_hlf.sh and return the CompletedProcess.

    *command* may be a string (split on whitespace) or a list of tokens.
    """
    if command is None:
        command = ["echo", "hello"]
    elif isinstance(command, str):
        command = command.split()

    full_env = os.environ.copy()
    full_env.pop("RALPH_DRY_RUN", None)
    full_env.pop("HLF_DEBUG", None)
    if env:
        full_env.update(env)

    cmd = [BASH, RALPH_HLF]
    if extra_args:
        cmd.extend(extra_args)
    cmd.extend(["--"] + command)

    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=full_env,
        cwd=str(REPO_ROOT),
        input=stdin,
    )


def _parse_trace(output: str):
    """Return the last JSON object from stdout."""
    return json.loads(output.strip())


pytestmark = pytest.mark.skipif(
    not BASH_AVAILABLE, reason="bash not found on PATH"
)


# ===========================================================================
# Tests
# ===========================================================================


class TestHelpFlag:
    def test_help_flag(self):
        """--help exits 0 and prints usage."""
        result = _run_ralph_hlf(extra_args=["--help"], command="echo ignore")
        assert result.returncode == 0
        assert "Usage:" in result.stdout
        assert "hearth" in result.stdout.lower()


class TestDryRunCompilesHLF:
    def test_dry_run_compiles_hlf(self):
        """RALPH_DRY_RUN=1 produces a trace that includes HLF compilation
        attempt information (the 'hlf' block with compile_ok field)."""
        # Even when the full HLF MCP stack isn't running, the trace should
        # contain the HLF block that records whether compilation succeeded.
        result = _run_ralph_hlf(
            env={"RALPH_DRY_RUN": "true"},
            extra_args=["--intent", "say hello world"],
        )
        assert result.returncode == 0
        trace = _parse_trace(result.stdout)
        assert trace.get("ralph_flavor") == "hlf"
        assert "hlf" in trace
        # compile_ok may be false (if hlf_mcp isn't importable) but the
        # block must exist
        assert "compile_ok" in trace["hlf"]

    def test_dry_run_trace_is_valid_json(self):
        """Dry-run trace is always valid JSON."""
        result = _run_ralph_hlf(
            env={"RALPH_DRY_RUN": "true"},
            extra_args=["--intent", "json validation test"],
        )
        assert result.returncode == 0
        trace = _parse_trace(result.stdout)
        assert "trace_id" in trace
        assert "phases" in trace


class TestTierFlag:
    def test_tier_flag_hearth(self):
        result = _run_ralph_hlf(
            env={"RALPH_DRY_RUN": "true"},
            extra_args=["--intent", "tier test", "--tier", "hearth"],
        )
        trace = _parse_trace(result.stdout)
        assert trace["hlf"]["tier"] == "hearth"

    def test_tier_flag_forge(self):
        result = _run_ralph_hlf(
            env={"RALPH_DRY_RUN": "true"},
            extra_args=["--intent", "tier test", "--tier", "forge"],
        )
        trace = _parse_trace(result.stdout)
        assert trace["hlf"]["tier"] == "forge"

    def test_tier_flag_anvil(self):
        result = _run_ralph_hlf(
            env={"RALPH_DRY_RUN": "true"},
            extra_args=["--intent", "tier test", "--tier", "anvil"],
        )
        trace = _parse_trace(result.stdout)
        assert trace["hlf"]["tier"] == "anvil"

    def test_invalid_tier_rejected(self):
        result = _run_ralph_hlf(
            extra_args=["--intent", "bad tier", "--tier", "invalid"],
        )
        assert result.returncode != 0


class TestGasLimitFlag:
    def test_gas_limit_flag(self):
        result = _run_ralph_hlf(
            env={"RALPH_DRY_RUN": "true"},
            extra_args=["--intent", "gas test", "--gas-limit", "100"],
        )
        trace = _parse_trace(result.stdout)
        assert trace["hlf"]["gas_limit"] == 100


class TestHLFDebugFlag:
    def test_hlf_debug_flag(self):
        """--hlf-debug is parsed without error."""
        result = _run_ralph_hlf(
            env={"RALPH_DRY_RUN": "true"},
            extra_args=[
                "--intent", "debug test",
                "--hlf-debug",
            ],
        )
        assert result.returncode == 0
        trace = _parse_trace(result.stdout)
        assert "trace_id" in trace


class TestSourceIncludesRalphLoop:
    def test_sources_ralph_loop(self):
        """Verify ralph_hlf.sh sources ralph_loop.sh with
        RALPH_SOURCE_ONLY=true rather than duplicating logic."""
        with open(RALPH_HLF, "r") as f:
            content = f.read()

        assert "RALPH_SOURCE_ONLY=true" in content
        # Must source ralph_loop.sh
        assert "source" in content
        assert "ralph_loop.sh" in content
        # Should reference _now, _sha, _phase from the sourced file
        assert "_now" in content
        assert "_phase" in content

    def test_does_not_duplicate_ralph_loop_helpers(self):
        """ralph_hlf.sh should not redefine helpers that come from
        ralph_loop.sh (like the _phase function body)."""
        with open(RALPH_HLF, "r") as f:
            content = f.read()

        # ralph_loop.sh defines these functions.  ralph_hlf.sh should
        # NOT redefine them (it sources them instead).
        # Check that _phase isn't redefined with a function body in hlf.
        import re

        phase_defs = re.findall(r"^_phase\(\)\s*\{", content, re.MULTILINE)
        assert len(phase_defs) == 0, (
            "ralph_hlf.sh redefines _phase(); should source it from ralph_loop.sh"
        )

        now_defs = re.findall(r"^_now\(\)\s*\{", content, re.MULTILINE)
        assert len(now_defs) == 0, (
            "ralph_hlf.sh redefines _now(); should source it from ralph_loop.sh"
        )


class TestFallbackToDirect:
    def test_fallback_to_direct(self):
        """When HLF compile/translate fails (no hlf_mcp server), the trace
        shows that the plan fell back to direct execution
        (compile_ok=false and selected_index=0 or dry_run)."""
        result = _run_ralph_hlf(
            env={"RALPH_DRY_RUN": "true"},
            extra_args=["--intent", "this will likely not compile to hlf"],
        )
        assert result.returncode == 0
        trace = _parse_trace(result.stdout)
        # When HLF compilation isn't available, compile_ok should be false
        assert trace["hlf"]["compile_ok"] is False
        # The trace should still complete successfully (fallback worked)
        assert trace["phases"]["handle"]["exit_code"] == 0
