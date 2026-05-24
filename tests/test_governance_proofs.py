from __future__ import annotations

import json
import os
import pytest

# hlf_swarm_mechanics and hlf_governance_proof_verify are registered
# via register_core_tools(), which is gated behind SWARMGLASS_EXPERIMENTAL=1.
# Set the env var before importing server so the tools are available.
os.environ["SWARMGLASS_EXPERIMENTAL"] = "1"

from hlf_mcp import server
from hlf_mcp.hlf.audit_chain import AuditChain
from hlf_mcp.hlf.code_execution import execute_code_bearing_hlf
from hlf_mcp.hlf.governance_proofs import (
    build_anchor,
    build_event_chain,
    build_governance_proof,
    verify_event_chain,
    verify_governance_proof,
)


def test_event_chain_verifies_and_detects_tamper() -> None:
    chain = build_event_chain(
        [
            {"event_type": "compile", "payload": {"ast_sha256": "abc"}},
            {"event_type": "runtime", "payload": {"status": "ok"}},
        ],
        chain_id="chain-1",
    )

    assert verify_event_chain(chain)["verified"] is True

    chain["events"][1]["payload"]["status"] = "tampered"
    report = verify_event_chain(chain)
    assert report["verified"] is False
    assert report["error_count"] >= 1


def test_audit_chain_integrity_report_states_hash_only_boundary(tmp_path) -> None:
    audit = AuditChain(
        log_path=str(tmp_path / "audit.jsonl"),
        last_hash_path=str(tmp_path / "last_hash.txt"),
    )
    first = audit.log("compile", {"status": "ok"})
    second = audit.log("runtime", {"status": "ok"})

    report = audit.verify_integrity(limit=10)

    assert report["verified"] is True
    assert report["checked"] == 2
    assert second["parent_trace_hash"] == first["trace_id"]
    assert report["boundary"]["signature"] == "none"
    assert "hash-chain integrity only" in audit.human_report(limit=2)


def test_code_execute_result_has_first_class_governance_proof() -> None:
    source = "[HLF-v3]\nFUNCTION main {\n  RESULT 0 \"proof-ok\"\n}\nΩ\n"

    result = execute_code_bearing_hlf(source, entrypoint="main")
    proof = result["governance_proof"]
    report = verify_governance_proof(proof)

    assert result["status"] in ("ok", "verification_blocked")
    assert report["verified"] is True
    assert proof["boundary"]["signature"] == "none"
    assert result["result_artifact"]["governance_proof_ref"] == proof["chain_head"]


def test_governance_proof_summarizes_memory_anchor_trust_without_overclaiming() -> None:
    proof = build_governance_proof(
        artifact_kind="test",
        artifact_id="memory-trust",
        events=[{"event_type": "decision", "payload": {"status": "accepted"}}],
        memory_anchors=[
            build_anchor(
                "memory",
                "unit-test",
                {
                    "evidence": {
                        "state": "active",
                        "trusted_for_governance": True,
                        "source_lineage_present": True,
                        "content_hash_valid": True,
                        "source_authority_label": "canonical",
                    }
                },
            )
        ],
    )
    report = verify_governance_proof(proof)

    assert proof["anchor_summary"]["memory_trust"]["trusted_for_governance_count"] == 1
    assert report["memory_trust"]["source_lineage_present_count"] == 1
    assert "not a signature" in proof["anchor_summary"]["memory_trust"]["claim_lane"]


def test_swarm_mechanics_resource_reports_proof_verification() -> None:
    source = (
        "[HLF-v3]\n"
        "⌘ [DELEGATE] agent=\"scribe\" goal=\"summarize\"\n"
        "⨝ [VOTE] voter=\"planner\" decision=\"approve\"\n"
        "Ω\n"
    )

    result = server.hlf_swarm_mechanics(source=source, persist=True)
    artifact = result["swarm_mechanics"]
    status = json.loads(server.REGISTERED_RESOURCES["hlf://status/swarm_mechanics"]())
    tool_report = server.hlf_governance_proof_verify(artifact["governance_proof"], include_report=True)

    assert verify_governance_proof(artifact["governance_proof"])["verified"] is True
    assert status["governance_proof_verification"]["verified"] is True
    assert "no digital signature" in artifact["governance_proof"]["operator_summary"]
    assert "Governance Proof Audit" in tool_report["human_report"]
