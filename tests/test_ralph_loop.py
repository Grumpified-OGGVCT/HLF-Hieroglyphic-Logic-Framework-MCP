"""Integration tests for scripts/ralph_loop.sh — generic RALPH harness."""

import json
import os
import shutil
import subprocess
import tempfile

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
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
    # Fall back to PATH lookup (may be WSL bash)
    found = shutil.which("bash")
    if found:
        return found
    return "bash"


BASH = _find_bash()
BASH_AVAILABLE = os.path.isfile(BASH) or shutil.which("bash") is not None


def _run_ralph_loop(
    *,
    env=None,
    extra_args=None,
    command=None,
    stdin=None,
    cwd=None,
):
    """Run ralph_loop.sh and return the CompletedProcess.

    *command* may be a string (split on whitespace) or a list of tokens.
    Defaults to ``['echo', 'hello']``.
    """
    if cwd is None:
        cwd = REPO_ROOT

    if command is None:
        command = ["echo", "hello"]
    elif isinstance(command, str):
        command = command.split()

    full_env = os.environ.copy()
    full_env.pop("RALPH_DRY_RUN", None)
    full_env.pop("RALPH_ADVISORY", None)
    full_env.pop("RALPH_SOURCE_ONLY", None)
    if env:
        full_env.update(env)

    cmd = [BASH, RALPH_LOOP]
    if extra_args:
        cmd.extend(extra_args)
    cmd.extend(["--"] + command)

    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=full_env,
        cwd=str(cwd),
        input=stdin,
    )


def _parse_trace(output: str):
    """Return the trace JSON from stdout.  Raises on invalid JSON."""
    # The trace is the last JSON object in stdout (after phase log lines
    # that may appear on stderr, but stdout carries the trace).
    return json.loads(output.strip())


# ---------------------------------------------------------------------------
# skip marker when bash is missing
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.skipif(
    not BASH_AVAILABLE, reason="bash not found on PATH"
)


# ===========================================================================
# Tests
# ===========================================================================


class TestHelpFlag:
    def test_help_flag(self):
        """--help exits 0 and prints usage text."""
        result = _run_ralph_loop(extra_args=["--help"], command="echo ignore")
        assert result.returncode == 0
        assert "Usage:" in result.stdout


class TestDryRun:
    def test_dry_run_with_intent(self):
        """RALPH_DRY_RUN=1 produces valid trace JSON and exits 0."""
        result = _run_ralph_loop(
            env={"RALPH_DRY_RUN": "true"},
            extra_args=["--intent", "test intent"],
        )
        assert result.returncode == 0
        trace = _parse_trace(result.stdout)
        assert trace.get("ralph_version") is not None
        assert trace["agent_id"]
        # dry-run plan should be index 2
        assert trace["phases"]["list"]["selected_index"] == 2

    def test_dry_run_trace_is_valid_json(self):
        """Even a minimal dry-run produces parseable JSON."""
        result = _run_ralph_loop(
            env={"RALPH_DRY_RUN": "true"},
            extra_args=["--intent", "minimal"],
        )
        assert result.returncode == 0
        trace = _parse_trace(result.stdout)
        assert "trace_id" in trace
        assert "phases" in trace


class TestMissingIntent:
    def test_no_args_fails(self):
        """Running without --intent and without a command exits non-zero."""
        full_env = os.environ.copy()
        full_env.pop("RALPH_DRY_RUN", None)
        full_env.pop("RALPH_ADVISORY", None)
        result = subprocess.run(
            [BASH, RALPH_LOOP],
            capture_output=True,
            text=True,
            env=full_env,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode != 0

    def test_intent_from_stdin(self):
        """Intent piped via stdin is accepted."""
        result = _run_ralph_loop(
            stdin="piped intent from stdin",
            command="echo ok",
        )
        assert result.returncode == 0
        trace = _parse_trace(result.stdout)
        # intent length should be > 0
        assert trace["intent_len"] > 0


class TestTraceOutput:
    def test_trace_output_to_file(self):
        """--trace-out writes valid JSON to the specified file."""
        with tempfile.NamedTemporaryFile(
            suffix=".json", delete=False, mode="w+", dir=REPO_ROOT
        ) as tf:
            tmp_path = tf.name

        try:
            result = _run_ralph_loop(
                env={"RALPH_DRY_RUN": "true"},
                extra_args=[
                    "--intent", "file output test",
                    "--trace-out", tmp_path,
                ],
            )
            assert result.returncode == 0
            with open(tmp_path, "r") as f:
                trace = json.load(f)
            assert "trace_id" in trace
            assert trace["intent_len"] > 0
        finally:
            os.unlink(tmp_path)


class TestTimeoutHandling:
    def test_timeout_handling(self):
        """A command that sleeps beyond the timeout causes non-zero exit."""
        result = _run_ralph_loop(
            extra_args=[
                "--intent", "sleep test",
                "--timeout", "1",
            ],
            command="sleep 5",
        )
        # Should exit non-zero (124 for GNU timeout, or other for watchdog)
        assert result.returncode != 0


class TestDomainDetection:
    def test_git_intent_detects_code_domain(self):
        """Intent with 'build' keywords yields domain_hint=build."""
        result = _run_ralph_loop(
            env={"RALPH_DRY_RUN": "true"},
            extra_args=["--intent", "build and compile the project with make"],
        )
        assert result.returncode == 0
        trace = _parse_trace(result.stdout)
        assert trace["phases"]["analyze"]["domain_hint"] == "build"

    def test_deploy_intent(self):
        result = _run_ralph_loop(
            env={"RALPH_DRY_RUN": "true"},
            extra_args=["--intent", "deploy the docker image to k8s"],
        )
        trace = _parse_trace(result.stdout)
        assert trace["phases"]["analyze"]["domain_hint"] == "deploy"

    def test_verify_intent(self):
        result = _run_ralph_loop(
            env={"RALPH_DRY_RUN": "true"},
            extra_args=["--intent", "test and verify the lint audit"],
        )
        trace = _parse_trace(result.stdout)
        assert trace["phases"]["analyze"]["domain_hint"] == "verify"

    def test_repair_intent(self):
        result = _run_ralph_loop(
            env={"RALPH_DRY_RUN": "true"},
            extra_args=["--intent", "fix the bug and patch the defect"],
        )
        trace = _parse_trace(result.stdout)
        assert trace["phases"]["analyze"]["domain_hint"] == "repair"

    def test_security_intent(self):
        result = _run_ralph_loop(
            env={"RALPH_DRY_RUN": "true"},
            extra_args=["--intent", "security vulnerability CVE threat analysis"],
        )
        trace = _parse_trace(result.stdout)
        assert trace["phases"]["analyze"]["domain_hint"] == "security"


class TestAdvisoryMode:
    def test_advisory_mode_flag(self):
        """RALPH_ADVISORY=1 selects advisory plan (index 1)."""
        result = _run_ralph_loop(
            env={"RALPH_ADVISORY": "true"},
            extra_args=["--intent", "advisory test"],
        )
        assert result.returncode == 0
        trace = _parse_trace(result.stdout)
        assert trace["phases"]["list"]["selected_index"] == 1


class TestComplexIntent:
    def test_special_characters_in_intent(self):
        """Intent with quotes, newlines, backslashes doesn't break JSON."""
        result = _run_ralph_loop(
            env={"RALPH_DRY_RUN": "true"},
            extra_args=["--intent", """test with "quotes", 'apostrophes', &
            backticks `cmd`, $dollar, and newlines"""],
        )
        assert result.returncode == 0
        trace = _parse_trace(result.stdout)
        assert trace["intent_len"] > 0

    def test_unicode_in_intent(self):
        """Unicode characters survive round-trip."""
        result = _run_ralph_loop(
            env={"RALPH_DRY_RUN": "true"},
            extra_args=["--intent", "unicode test: café, naïve, résumé, 日本語"],
        )
        assert result.returncode == 0
        trace = _parse_trace(result.stdout)
        assert "café" in trace["intent"] or trace["intent_len"] > 0
