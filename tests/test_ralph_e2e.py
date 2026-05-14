"""End-to-end integration tests for the RALPH cognitive loop pipeline."""

import json
import os
import shutil
import subprocess
import tempfile

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
RALPH_LOOP = os.path.join(SCRIPTS_DIR, "ralph_loop.sh")
RALPH_HLF = os.path.join(SCRIPTS_DIR, "ralph_hlf.sh")
RALPH_AGENT = os.path.join(SCRIPTS_DIR, "ralph_agent.sh")

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

REQUIRED_PHASES = {"receive", "analyze", "list", "plan", "handle"}


def _parse_trace(output: str):
    """Return the trace JSON.  Output may be a single merged trace object or
    a fallback format with a leading persona metadata block followed by the
    raw ralph_loop.sh trace.  We merge them into one consistent dict."""
    output = output.strip()
    decoder = json.JSONDecoder()
    idx = 0
    objects = []
    while idx < len(output):
        try:
            obj, end = decoder.raw_decode(output[idx:])
            objects.append(obj)
            idx += end
        except json.JSONDecodeError:
            idx += 1

    if not objects:
        raise json.JSONDecodeError("No JSON found in output", output, 0)

    if len(objects) == 1:
        return objects[0]

    # Multiple objects: merge persona meta into the trace
    persona_meta = None
    trace = None
    for obj in objects:
        if "persona" in obj and "ralph_version" not in obj:
            persona_meta = obj
        elif "ralph_version" in obj:
            trace = obj

    if persona_meta and trace:
        trace.update(persona_meta)
        return trace
    if trace:
        return trace
    result = objects[-1]
    for obj in objects[:-1]:
        result.update(obj)
    return result


def _validate_trace(trace):
    """Common validations for any trace object."""
    assert isinstance(trace, dict)
    assert "trace_id" in trace
    assert "phases" in trace
    phases = trace["phases"]
    for phase in REQUIRED_PHASES:
        assert phase in phases, f"Missing required phase: {phase}"
    # All phase blocks must be dicts with 'status' or similar
    for name, block in phases.items():
        assert isinstance(block, dict), f"Phase '{name}' is not a dict"


pytestmark = pytest.mark.skipif(
    not BASH_AVAILABLE, reason="bash not found on PATH"
)


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture
def temp_dir():
    """Create a temporary directory that's cleaned up after test."""
    with tempfile.TemporaryDirectory(dir=REPO_ROOT) as td:
        yield td


# ===========================================================================
# Tests
# ===========================================================================


class TestFullPipelineDry:
    def test_full_pipeline_dry(self, temp_dir):
        """Dry-run with agent persona + handoff + swarm produces complete trace."""
        trace_path = os.path.join(temp_dir, "e2e_trace.json")

        cmd = [
            BASH,
            RALPH_AGENT,
            "--dry-run",
            "--persona", "planner",
            "--agent-id", "e2e-agent",
            "--trust-state", "approved",
            "--cognitive-lane", "balanced",
            "--delegate", "executor-01",
            "--handoff-scope", "execute build pipeline",
            "--vote", "approve",
            "--swarm-id", "e2e-swarm",
            "--dissent", "add more tests before merge",
            "-o", trace_path,
            "--intent", "end-to-end pipeline test",
            "--",
            "echo", "pipeline output",
        ]

        full_env = os.environ.copy()
        full_env.pop("RALPH_DRY_RUN", None)
        full_env["RALPH_LOOP_SCRIPT"] = os.path.join(SCRIPTS_DIR, "ralph_loop.sh")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=full_env,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0

        with open(trace_path, "r") as f:
            trace = _parse_trace(f.read())

        _validate_trace(trace)
        assert trace.get("persona", {}).get("role") == "planner"
        assert trace.get("persona", {}).get("agent_id") == "e2e-agent"
        assert "handoff_contract" in trace
        assert "swarm_vote" in trace
        assert "swarm_dissent" in trace


class TestRealExecutionSimple:
    def test_real_execution_echo(self):
        """Actual execution of 'echo hello' via RALPH loop succeeds."""
        full_env = os.environ.copy()
        full_env.pop("RALPH_DRY_RUN", None)
        full_env.pop("RALPH_ADVISORY", None)

        result = subprocess.run(
            [BASH, RALPH_LOOP, "--intent", "echo hello world", "--", "echo", "hello world"],
            capture_output=True,
            text=True,
            env=full_env,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0
        trace = _parse_trace(result.stdout)
        _validate_trace(trace)
        assert trace["phases"]["handle"]["exit_code"] == 0

    def test_real_execution_true(self):
        """Actual execution of 'true' via RALPH loop succeeds."""
        full_env = os.environ.copy()
        full_env.pop("RALPH_DRY_RUN", None)

        result = subprocess.run(
            [BASH, RALPH_LOOP, "--intent", "run true", "--", "true"],
            capture_output=True,
            text=True,
            env=full_env,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0
        trace = _parse_trace(result.stdout)
        _validate_trace(trace)

    def test_real_execution_echo_via_agent(self):
        """Actual execution of 'echo' through ralph_agent.sh succeeds."""
        full_env = os.environ.copy()
        full_env.pop("RALPH_DRY_RUN", None)
        full_env["RALPH_LOOP_SCRIPT"] = os.path.join(SCRIPTS_DIR, "ralph_loop.sh")

        result = subprocess.run(
            [
                BASH, RALPH_AGENT,
                "--persona", "executor",
                "--intent", "say hello",
                "--", "echo", "hello from agent",
            ],
            capture_output=True,
            text=True,
            env=full_env,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0
        trace = _parse_trace(result.stdout)
        _validate_trace(trace)


class TestTraceIsValidJSON:
    def test_loop_trace_is_valid_json(self):
        """ralph_loop.sh dry-run trace parses as valid JSON."""
        full_env = os.environ.copy()
        full_env["RALPH_DRY_RUN"] = "true"
        result = subprocess.run(
            [BASH, RALPH_LOOP, "--intent", "valid json test", "--", "echo", "ok"],
            capture_output=True,
            text=True,
            env=full_env,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0
        trace = _parse_trace(result.stdout)
        _validate_trace(trace)

    def test_hlf_trace_is_valid_json(self):
        """ralph_hlf.sh dry-run trace parses as valid JSON."""
        full_env = os.environ.copy()
        full_env["RALPH_DRY_RUN"] = "true"
        result = subprocess.run(
            [BASH, RALPH_HLF, "--intent", "valid json hlf", "--", "echo", "ok"],
            capture_output=True,
            text=True,
            env=full_env,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0
        trace = _parse_trace(result.stdout)
        _validate_trace(trace)

    def test_agent_trace_is_valid_json(self):
        """ralph_agent.sh dry-run trace parses as valid JSON."""
        full_env = os.environ.copy()
        full_env["RALPH_LOOP_SCRIPT"] = os.path.join(SCRIPTS_DIR, "ralph_loop.sh")
        result = subprocess.run(
            [
                BASH, RALPH_AGENT,
                "--dry-run",
                "--persona", "executor",
                "--intent", "valid json agent",
                "--", "echo", "ok",
            ],
            capture_output=True,
            text=True,
            env=full_env,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0
        trace = _parse_trace(result.stdout)
        _validate_trace(trace)


class TestTraceHasRequiredPhases:
    def test_loop_has_all_phases(self):
        full_env = os.environ.copy()
        full_env["RALPH_DRY_RUN"] = "true"
        result = subprocess.run(
            [BASH, RALPH_LOOP, "--intent", "phases test", "--", "echo", "ok"],
            capture_output=True,
            text=True,
            env=full_env,
            cwd=str(REPO_ROOT),
        )
        trace = _parse_trace(result.stdout)
        for phase in REQUIRED_PHASES:
            assert phase in trace["phases"], f"Missing phase: {phase}"

    def test_hlf_has_all_phases(self):
        full_env = os.environ.copy()
        full_env["RALPH_DRY_RUN"] = "true"
        result = subprocess.run(
            [BASH, RALPH_HLF, "--intent", "phases hlf test", "--", "echo", "ok"],
            capture_output=True,
            text=True,
            env=full_env,
            cwd=str(REPO_ROOT),
        )
        trace = _parse_trace(result.stdout)
        for phase in REQUIRED_PHASES:
            assert phase in trace["phases"], f"Missing phase: {phase}"

    def test_agent_has_all_phases(self):
        full_env = os.environ.copy()
        full_env["RALPH_LOOP_SCRIPT"] = os.path.join(SCRIPTS_DIR, "ralph_loop.sh")
        result = subprocess.run(
            [
                BASH, RALPH_AGENT,
                "--dry-run",
                "--persona", "developer",
                "--intent", "phases agent test",
                "--", "echo", "ok",
            ],
            capture_output=True,
            text=True,
            env=full_env,
            cwd=str(REPO_ROOT),
        )
        trace = _parse_trace(result.stdout)
        for phase in REQUIRED_PHASES:
            assert phase in trace["phases"], f"Missing phase: {phase}"


class TestHLFE2E:
    def test_hlf_full_dry_pipeline(self, temp_dir):
        """ralph_hlf.sh dry-run with tier and gas-limit produces a complete
        trace with HLF metadata."""
        trace_path = os.path.join(temp_dir, "hlf_e2e.json")

        full_env = os.environ.copy()
        full_env["RALPH_DRY_RUN"] = "true"

        result = subprocess.run(
            [
                BASH, RALPH_HLF,
                "--intent", "build and verify the project",
                "--tier", "forge",
                "--gas-limit", "500",
                "--trace-out", trace_path,
                "--", "echo", "hlf pipeline",
            ],
            capture_output=True,
            text=True,
            env=full_env,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0

        with open(trace_path, "r") as f:
            trace = _parse_trace(f.read())

        _validate_trace(trace)
        assert trace["ralph_flavor"] == "hlf"
        assert trace["hlf"]["tier"] == "forge"
        assert trace["hlf"]["gas_limit"] == 500
        # domain hint from "build and verify" → should be "build" (first match)
        assert trace["phases"]["analyze"]["domain_hint"] in ("build", "verify")
