import json
import os

# SwarmGlass: swarm tools require DSL — gate behind EXP=1
os.environ["SWARMGLASS_HLF_ENABLED"] = "1"

from hlf_mcp import server
from hlf_mcp.hlf.compiler import HLFCompiler
from hlf_mcp.hlf.swarm_mechanics import build_swarm_mechanics_artifact

SWARM_HLF = """\
[HLF-v3]
⌘ [DELEGATE] agent="scribe" goal="summarize"
⨝ [VOTE] voter="planner" decision="approve"
Ж [DISSENT] agent="reviewer" reason="needs citations" severity="warning"
∇ [PROGRESS] event_id="evt-1" phase="plan" status="started"
Ω
"""


def test_swarm_mechanics_materializes_first_class_hlf_artifacts() -> None:
    compiler = HLFCompiler()
    validation = compiler.validate(SWARM_HLF)
    compile_result = compiler.compile(SWARM_HLF)

    artifact = build_swarm_mechanics_artifact(
        source=SWARM_HLF,
        ast=compile_result["ast"],
        validation=validation,
        compile_result=compile_result,
        votes=[{"voter": "verifier", "decision": "approve"}],
        quorum="strict",
    )

    assert artifact["artifact_kind"] == "hlf_swarm_mechanics"
    assert artifact["boundary"]["distributed_a2a"] is False
    assert artifact["delegations"][0]["agent"] == "scribe"
    assert len(artifact["votes"]) == 2
    assert artifact["dissent"][0]["agent"] == "reviewer"
    assert artifact["trace_lineage"]["artifact_counts"]["progress_events"] >= 3
    assert "[TRACE]" in artifact["source"]["materialized_hlf_source"]
    assert compiler.validate(artifact["source"]["materialized_hlf_source"])["valid"] is True


def test_hlf_swarm_mechanics_tool_accepts_raw_hlf_handoff_and_persists_resource() -> None:
    handoff = {
        "artifact_kind": "raw_hlf_subagent_handoff",
        "handoff_mode": "swarm",
        "wire_format": "raw_hlf_source",
        "raw_hlf_source": SWARM_HLF,
    }

    result = server.hlf_swarm_mechanics(handoff=handoff, persist=True)

    assert result["status"] == "ok"
    artifact = result["swarm_mechanics"]
    assert artifact["handoff"]["compatible"] is True
    assert artifact["boundary"]["mode"] == "local_bounded_swarm"
    assert artifact["source"]["validation"]["valid"] is True
    assert artifact["governance_event_ref"]["kind"] == "validated_solution_capture"

    resource = json.loads(server.REGISTERED_RESOURCES["hlf://status/swarm_mechanics"]())
    assert resource["status"] == "ok"
    assert resource["swarm_mechanics"]["swarm_id"] == artifact["swarm_id"]
    assert "hlf://reports/swarm_mechanics" in server.REGISTERED_RESOURCES


def test_swarm_handoff_declares_local_boundary_and_mechanics_compatibility() -> None:
    result = server.hlf_do("Delegate a summary to a scribe and require review.", dry_run=True, handoff_mode="swarm")

    handoff = result["subagent_handoff"]
    assert handoff["wire_format"] == "raw_hlf_source"
    assert handoff["swarm_mechanics"]["compatible"] is True
    assert handoff["swarm_mechanics"]["distributed_a2a"] is False
    assert handoff["swarm_mechanics"]["tool"] == "hlf_swarm_mechanics"
