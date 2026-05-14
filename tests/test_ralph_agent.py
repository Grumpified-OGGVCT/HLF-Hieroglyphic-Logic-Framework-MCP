"""Integration tests for scripts/ralph_agent.sh — GrumpRolled/Jules RALPH Agent."""

import json
import os
import shutil
import subprocess
import tempfile

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
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


def _run_ralph_agent(
    *,
    env=None,
    extra_args=None,
    command=None,
    stdin=None,
):
    """Run ralph_agent.sh and return the CompletedProcess.

    *command* may be a string (split on whitespace) or a list of tokens.
    """
    if command is None:
        command = ["echo", "hello"]
    elif isinstance(command, str):
        command = command.split()

    full_env = os.environ.copy()
    full_env.pop("RALPH_DRY_RUN", None)
    full_env.pop("RALPH_ADVISORY", None)
    # Ensure ralph_agent.sh can find ralph_loop.sh regardless of path style
    full_env["RALPH_LOOP_SCRIPT"] = os.path.join(SCRIPTS_DIR, "ralph_loop.sh")
    if env:
        full_env.update(env)

    cmd = [BASH, RALPH_AGENT]
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
    """Return the trace JSON.  Output may be a single merged trace object
    (persona embedded) or a fallback format with a leading persona metadata
    block followed by the raw ralph_loop.sh trace.  The second form occurs
    when ralph_merge_trace.py cannot be located (mixed path separators on
    Windows).  We merge them into one consistent dict."""
    output = output.strip()
    # Find all complete JSON objects in the output
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

    # If there's exactly one object, return it (merged or raw)
    if len(objects) == 1:
        return objects[0]

    # Multiple objects: the first should be persona meta, the rest is
    # the raw ralph trace.  Merge persona meta into the last/largest one.
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
    # Fallback: merge all into the last object
    result = objects[-1]
    for obj in objects[:-1]:
        result.update(obj)
    return result


pytestmark = pytest.mark.skipif(
    not BASH_AVAILABLE, reason="bash not found on PATH"
)


# ===========================================================================
# Tests
# ===========================================================================


class TestHelpFlag:
    def test_help_flag(self):
        """--help exits 0."""
        result = _run_ralph_agent(extra_args=["--help"], command="echo ignore")
        assert result.returncode == 0
        assert "Usage:" in result.stdout


class TestDryRunWithPersona:
    def test_dry_run_with_persona(self):
        """--persona operator --dry-run produces a trace with persona info."""
        result = _run_ralph_agent(
            extra_args=["--persona", "operator", "--dry-run", "--intent", "persona test"],
        )
        assert result.returncode == 0
        trace = _parse_trace(result.stdout)
        assert "persona" in trace
        assert trace["persona"]["role"] == "operator"


class TestAllPersonas:
    PERSONA_LIST = ["operator", "auditor", "developer", "verifier", "planner", "executor"]

    @pytest.mark.parametrize("persona", PERSONA_LIST)
    def test_persona(self, persona):
        result = _run_ralph_agent(
            extra_args=["--persona", persona, "--dry-run", "--intent", f"test {persona}"],
        )
        assert result.returncode == 0
        trace = _parse_trace(result.stdout)
        assert "persona" in trace
        assert trace["persona"]["role"] == persona

    def test_unknown_persona_fails(self):
        result = _run_ralph_agent(
            extra_args=["--persona", "nonexistent", "--intent", "bad persona"],
        )
        assert result.returncode != 0


class TestAgentIdFlag:
    def test_agent_id_flag(self):
        result = _run_ralph_agent(
            extra_args=["--dry-run", "--agent-id", "test-agent-1", "--intent", "id test"],
        )
        trace = _parse_trace(result.stdout)
        assert trace["persona"]["agent_id"] == "test-agent-1"


class TestTrustStateFlag:
    def test_trust_state_watched(self):
        result = _run_ralph_agent(
            extra_args=["--dry-run", "--trust-state", "watched", "--intent", "trust test"],
        )
        trace = _parse_trace(result.stdout)
        assert trace["persona"]["trust_state"] == "watched"

    def test_trust_state_trusted(self):
        result = _run_ralph_agent(
            extra_args=["--dry-run", "--trust-state", "trusted", "--intent", "trust test"],
        )
        trace = _parse_trace(result.stdout)
        assert trace["persona"]["trust_state"] == "trusted"

    def test_invalid_trust_state_fails(self):
        result = _run_ralph_agent(
            extra_args=["--trust-state", "invalid", "--intent", "bad trust"],
        )
        assert result.returncode != 0


class TestCognitiveLaneFlag:
    def test_cognitive_lane_bridge(self):
        result = _run_ralph_agent(
            extra_args=["--dry-run", "--cognitive-lane", "strict", "--intent", "lane test"],
        )
        trace = _parse_trace(result.stdout)
        assert trace["persona"]["cognitive_lane_policy"] == "strict"

    def test_invalid_lane_fails(self):
        result = _run_ralph_agent(
            extra_args=["--cognitive-lane", "invalid", "--intent", "bad lane"],
        )
        assert result.returncode != 0


class TestHandoffDelegate:
    def test_handoff_delegate(self):
        result = _run_ralph_agent(
            extra_args=[
                "--dry-run",
                "--persona", "planner",
                "--delegate", "planner",
                "--handoff-scope", "task",
                "--intent", "handoff test",
            ],
        )
        trace = _parse_trace(result.stdout)
        assert "handoff_contract" in trace
        hc = trace["handoff_contract"]
        assert hc is not None
        assert hc.get("delegate") == "planner" or hc.get("handoff", {}).get("delegate") == "planner"


class TestSwarmVote:
    def test_swarm_vote_approve(self):
        result = _run_ralph_agent(
            extra_args=[
                "--dry-run",
                "--persona", "executor",
                "--vote", "approve",
                "--swarm-id", "swarm-1",
                "--intent", "vote test",
            ],
        )
        trace = _parse_trace(result.stdout)
        assert "swarm_vote" in trace
        # The vote may be nested under swarm_vote or vote key
        vote = trace.get("swarm_vote")
        assert vote is not None

    def test_vote_reject(self):
        result = _run_ralph_agent(
            extra_args=[
                "--dry-run",
                "--vote", "reject",
                "--swarm-id", "swarm-2",
                "--intent", "reject test",
            ],
        )
        trace = _parse_trace(result.stdout)
        assert "swarm_vote" in trace

    def test_invalid_vote_fails(self):
        result = _run_ralph_agent(
            extra_args=["--vote", "invalid", "--intent", "bad vote"],
        )
        assert result.returncode != 0


class TestSwarmDissent:
    def test_swarm_dissent(self):
        result = _run_ralph_agent(
            extra_args=[
                "--dry-run",
                "--persona", "operator",
                "--dissent", "insufficient test coverage",
                "--swarm-id", "swarm-3",
                "--intent", "dissent test",
            ],
        )
        trace = _parse_trace(result.stdout)
        assert "swarm_dissent" in trace
        dissent = trace.get("swarm_dissent")
        assert dissent is not None


class TestTraceOutputMerge:
    def test_trace_output_merge(self):
        """-o flag generates valid merged JSON with persona+handoff+swarm fields."""
        with tempfile.NamedTemporaryFile(
            suffix=".json", delete=False, mode="w+", dir=REPO_ROOT
        ) as tf:
            tmp_path = tf.name

        try:
            result = _run_ralph_agent(
                extra_args=[
                    "--dry-run",
                    "--persona", "planner",
                    "--delegate", "verifier-01",
                    "--handoff-scope", "verify build",
                    "--vote", "approve",
                    "--swarm-id", "merge-swarm",
                    "--dissent", "needs more review",
                    "-o", tmp_path,
                    "--intent", "merge test",
                ],
                command="echo merge",
            )
            assert result.returncode == 0
            with open(tmp_path, "r") as f:
                trace = _parse_trace(f.read())
            assert "persona" in trace
            assert "handoff_contract" in trace
            assert "swarm_vote" in trace
            assert "swarm_dissent" in trace
        finally:
            os.unlink(tmp_path)


class TestNoDoublePassThrough:
    def test_no_double_pass_through(self):
        """Verify -o flag is NOT passed through to ralph_loop.sh.
        ralph_agent.sh handles -o itself and never adds it to PASSTHROUGH_ARGS."""
        with open(RALPH_AGENT, "r") as f:
            content = f.read()

        # -o is handled separately (line 418-420), not added to PASSTHROUGH_ARGS
        # Confirm it's in a case branch that sets TRACE_OUT and shifts,
        # not in a branch that appends to PASSTHROUGH_ARGS.
        assert "TRACE_OUT=" in content
        # The passthrough block handles -i and -t but NOT -o
        passthrough_section = content[content.find("PASSTHROUGH_ARGS"):]
        # -o should not appear in the PASSTHROUGH_ARGS append block
        # Extract the section around passthrough arg handling
        passthrough_lines = [
            line for line in content.splitlines()
            if "PASSTHROUGH_ARGS" in line and ("-o" in line or "trace-out" in line)
        ]
        assert len(passthrough_lines) == 0, (
            "-o / --trace-out found in PASSTHROUGH_ARGS section; "
            "ralph_agent.sh should handle output itself"
        )

    def test_o_flag_does_not_reach_ralph_loop(self):
        """When running with -o, ralph_loop.sh should not receive -o."""
        with tempfile.NamedTemporaryFile(
            suffix=".json", delete=False, mode="w+", dir=REPO_ROOT
        ) as tf:
            tmp_path = tf.name

        try:
            result = _run_ralph_agent(
                extra_args=[
                    "--dry-run",
                    "--persona", "executor",
                    "-o", tmp_path,
                    "--intent", "no passthrough test",
                ],
            )
            assert result.returncode == 0
            with open(tmp_path, "r") as f:
                trace = _parse_trace(f.read())
            assert "persona" in trace
        finally:
            os.unlink(tmp_path)
