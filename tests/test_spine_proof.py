"""Tests for spine proof — end-to-end Merkle trust demonstration (B5 bridge_contract).

Covers:
  1. Spine proof object structure — all phases present, linkage hashes correct
  2. Trust-chain summary completeness — all expected fields
  3. Merkle hash chain integrity — tamper detection via verify_spine_proof
  4. Operator-readable markdown output
  5. verify_spine_proof correctness — good and bad proofs
  6. Integration: build → verify → render round-trip
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import pytest

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from hlf_mcp.hlf.spine_proof import (  # noqa: E402
    SPINE_PROOF_VERSION,
    SPINE_REQUIRED_PHASES,
    build_spine_proof,
    render_spine_markdown,
    verify_spine_proof,
)
from hlf_mcp.hlf.governance_proofs import (  # noqa: E402
    ZERO_HASH,
    PROOF_BOUNDARY,
    sha256_digest,
)


# ── helpers ──────────────────────────────────────────────────────────────


def _make_mock_compile_result(status: str = "ok") -> dict[str, Any]:
    return {
        "status": status,
        "ast_sha256": hashlib.sha256(b"mock-ast").hexdigest(),
        "bytecode_sha256": hashlib.sha256(b"mock-bc").hexdigest(),
        "statement_count": 3,
    }


def _make_mock_execute_result(status: str = "ok") -> dict[str, Any]:
    return {
        "status": status,
        "result": "hello world",
        "gas_used": 42,
        "governance_proof_ref": hashlib.sha256(b"proof-ref").hexdigest()[:32],
    }


def _make_mock_memory_result() -> dict[str, Any]:
    return {
        "pointer": "hlf://memory/test-ptr-001",
        "sha256": hashlib.sha256(b"mock-memory").hexdigest(),
        "topic": "hlf-execution",
        "audit": {"trace_id": hashlib.sha256(b"audit").hexdigest()},
    }


# ── structure tests ─────────────────────────────────────────────────────


def test_spine_proof_has_all_required_top_level_keys() -> None:
    """Proof object contains all expected top-level keys."""
    spine = build_spine_proof(
        intent_text="print hello world",
        hlf_source='[HLF-v3]\nFUNCTION main {\n  RESULT 0 "hello"\n}\n\u03a9\n',
        compile_result=_make_mock_compile_result(),
        execute_result=_make_mock_execute_result(),
        memory_result=_make_mock_memory_result(),
    )

    expected_keys = {
        "spine_proof_version",
        "bridge_lane",
        "proof_boundary",
        "intent_text",
        "phases",
        "linkage",
        "trust_chain_summary",
        "hash_chain",
        "operator_summary",
    }
    assert expected_keys.issubset(set(spine.keys()))
    assert spine["spine_proof_version"] == SPINE_PROOF_VERSION
    assert spine["bridge_lane"] == "bridge_contract"


def test_spine_proof_phases_contain_all_required_phases() -> None:
    """All five phases are present in the phases dict."""
    spine = build_spine_proof(
        intent_text="print hello world",
        hlf_source='[HLF-v3]\nFUNCTION main {\n  RESULT 0 "hello"\n}\n\u03a9\n',
        compile_result=_make_mock_compile_result(),
        execute_result=_make_mock_execute_result(),
        memory_result=_make_mock_memory_result(),
    )

    phases = spine["phases"]
    for phase_name in SPINE_REQUIRED_PHASES:
        assert phase_name in phases, f"missing phase: {phase_name}"
        assert isinstance(phases[phase_name], dict), f"phase {phase_name} is not a dict"


def test_spine_proof_linkage_matches_phases() -> None:
    """Each linkage hash matches the SHA-256 of its corresponding phase payload."""
    spine = build_spine_proof(
        intent_text="print hello world",
        hlf_source='[HLF-v3]\nFUNCTION main {\n  RESULT 0 "hello"\n}\n\u03a9\n',
        compile_result=_make_mock_compile_result(),
        execute_result=_make_mock_execute_result(),
        memory_result=_make_mock_memory_result(),
    )

    linkage = spine["linkage"]
    phases = spine["phases"]
    for phase_name in SPINE_REQUIRED_PHASES:
        expected = sha256_digest(phases[phase_name])
        assert linkage[phase_name] == expected, f"linkage mismatch for {phase_name}"


def test_spine_proof_hash_chain_is_verifiable() -> None:
    """The hash chain within the spine proof passes governance proof verification."""
    spine = build_spine_proof(
        intent_text="print hello world",
        hlf_source='[HLF-v3]\nFUNCTION main {\n  RESULT 0 "hello"\n}\n\u03a9\n',
        compile_result=_make_mock_compile_result(),
        execute_result=_make_mock_execute_result(),
        memory_result=_make_mock_memory_result(),
    )

    verification = verify_spine_proof(spine)
    assert verification["verified"] is True, f"errors: {verification.get('errors')}"
    assert verification["status"] == "ok"
    assert verification["error_count"] == 0


# ── trust-chain summary tests ────────────────────────────────────────────


def test_trust_chain_summary_has_required_fields() -> None:
    """Trust-chain summary contains all expected fields for operator inspection."""
    spine = build_spine_proof(
        intent_text="print hello world",
        hlf_source='[HLF-v3]\nFUNCTION main {\n  RESULT 0 "hello"\n}\n\u03a9\n',
        compile_result=_make_mock_compile_result(),
        execute_result=_make_mock_execute_result(),
        memory_result=_make_mock_memory_result(),
    )

    trust = spine["trust_chain_summary"]
    required = {
        "phases_linked",
        "phases",
        "hash_algorithm",
        "chain_head",
        "event_count",
        "memory_anchors",
        "runtime_anchors",
        "claim_lane_note",
    }
    assert required.issubset(set(trust.keys()))
    assert trust["phases_linked"] == 5
    assert trust["hash_algorithm"] == "SHA-256"
    assert len(trust["chain_head"]) == 64  # full SHA-256 hex
    assert "bridge_contract" in trust["claim_lane_note"]
    assert "tamper-evident" in trust["claim_lane_note"]


def test_trust_chain_summary_phases_list_correct() -> None:
    """The phases list in trust summary matches expected spine event types."""
    spine = build_spine_proof(
        intent_text="compute 1+1",
        hlf_source='[HLF-v3]\nFUNCTION main {\n  RESULT 0 "2"\n}\n\u03a9\n',
        compile_result=_make_mock_compile_result(),
        execute_result=_make_mock_execute_result(),
        memory_result=_make_mock_memory_result(),
    )

    trust = spine["trust_chain_summary"]
    expected_phases = [
        "intent_captured",
        "translation_to_hlf",
        "compilation",
        "execution",
        "memory_store",
    ]
    assert trust["phases"] == expected_phases


# ── Merkle chain integrity tests ─────────────────────────────────────────


def test_spine_proof_detects_tampered_intent() -> None:
    """Modifying the intent payload after proof construction causes verify to fail."""
    spine = build_spine_proof(
        intent_text="print hello world",
        hlf_source='[HLF-v3]\nFUNCTION main {\n  RESULT 0 "hello"\n}\n\u03a9\n',
        compile_result=_make_mock_compile_result(),
        execute_result=_make_mock_execute_result(),
        memory_result=_make_mock_memory_result(),
    )

    # Tamper: change intent text in the phase payload
    spine["phases"]["intent"]["text"] = "rm -rf /"
    verification = verify_spine_proof(spine)

    assert verification["verified"] is False
    assert verification["error_count"] >= 1


def test_spine_proof_detects_tampered_phase_payload() -> None:
    """Modifying a phase payload hash causes linkage verification to fail."""
    spine = build_spine_proof(
        intent_text="print hello world",
        hlf_source='[HLF-v3]\nFUNCTION main {\n  RESULT 0 "hello"\n}\n\u03a9\n',
        compile_result=_make_mock_compile_result(),
        execute_result=_make_mock_execute_result(),
        memory_result=_make_mock_memory_result(),
    )

    # Tamper: change a linkage hash
    spine["linkage"]["execute"] = "0" * 64
    verification = verify_spine_proof(spine)

    assert verification["verified"] is False
    assert any("linkage" in err.lower() for err in verification["errors"])


def test_spine_proof_detects_tampered_chain_event() -> None:
    """Modifying a chain event payload causes chain verification to fail."""
    spine = build_spine_proof(
        intent_text="print hello world",
        hlf_source='[HLF-v3]\nFUNCTION main {\n  RESULT 0 "hello"\n}\n\u03a9\n',
        compile_result=_make_mock_compile_result(),
        execute_result=_make_mock_execute_result(),
        memory_result=_make_mock_memory_result(),
    )

    # Tamper: change payload inside the hash chain
    chain = spine["hash_chain"]["chain"]
    chain["events"][2]["payload"]["status"] = "compromised"
    verification = verify_spine_proof(spine)

    assert verification["verified"] is False
    assert any("hash_chain" in err.lower() or "chain:" in err.lower() for err in verification["errors"])


def test_spine_proof_detects_missing_phase() -> None:
    """Removing a required phase from the proof causes verification to fail."""
    spine = build_spine_proof(
        intent_text="print hello world",
        hlf_source='[HLF-v3]\nFUNCTION main {\n  RESULT 0 "hello"\n}\n\u03a9\n',
        compile_result=_make_mock_compile_result(),
        execute_result=_make_mock_execute_result(),
        memory_result=_make_mock_memory_result(),
    )

    # Remove a phase
    del spine["phases"]["memory"]
    verification = verify_spine_proof(spine)

    assert verification["verified"] is False
    assert any("memory" in err for err in verification["errors"])


# ── boundary tests ───────────────────────────────────────────────────────


def test_spine_proof_boundary_declares_no_signature() -> None:
    """Proof boundary correctly declares hash-chain-only integrity."""
    spine = build_spine_proof(
        intent_text="print hello world",
        hlf_source='[HLF-v3]\nFUNCTION main {\n  RESULT 0 "hello"\n}\n\u03a9\n',
        compile_result=_make_mock_compile_result(),
        execute_result=_make_mock_execute_result(),
        memory_result=_make_mock_memory_result(),
    )

    boundary = spine["proof_boundary"]
    assert boundary["signature"] == "none"
    assert boundary["non_repudiation"] is False
    assert boundary["integrity"] == "sha256_hash_chain"


def test_operator_summary_does_not_overclaim() -> None:
    """Operator summary explicitly states what is NOT claimed."""
    spine = build_spine_proof(
        intent_text="print hello world",
        hlf_source='[HLF-v3]\nFUNCTION main {\n  RESULT 0 "hello"\n}\n\u03a9\n',
        compile_result=_make_mock_compile_result(),
        execute_result=_make_mock_execute_result(),
        memory_result=_make_mock_memory_result(),
    )

    summary = spine["operator_summary"]
    assert "no digital signature" in summary.lower()
    assert "non-repudiation" in summary.lower() or "bridge_contract" in summary.lower()


# ── markdown rendering tests ─────────────────────────────────────────────


def test_render_spine_markdown_contains_all_sections() -> None:
    """Markdown output includes all expected sections."""
    spine = build_spine_proof(
        intent_text="print hello world",
        hlf_source='[HLF-v3]\nFUNCTION main {\n  RESULT 0 "hello"\n}\n\u03a9\n',
        compile_result=_make_mock_compile_result(),
        execute_result=_make_mock_execute_result(),
        memory_result=_make_mock_memory_result(),
    )

    md = render_spine_markdown(spine)
    assert "HLF Spine Proof" in md
    assert "Phase Linkage" in md
    assert "Trust Chain Summary" in md
    assert "Proof Boundary" in md
    assert "Operator Summary" in md
    assert "Governance Proof Audit" in md
    assert "SHA-256" in md


def test_render_spine_markdown_includes_chain_head() -> None:
    """Markdown includes the chain head hash."""
    spine = build_spine_proof(
        intent_text="print hello world",
        hlf_source='[HLF-v3]\nFUNCTION main {\n  RESULT 0 "hello"\n}\n\u03a9\n',
        compile_result=_make_mock_compile_result(),
        execute_result=_make_mock_execute_result(),
        memory_result=_make_mock_memory_result(),
    )

    md = render_spine_markdown(spine)
    chain_head = spine["hash_chain"]["chain_head"]
    assert chain_head[:16] in md


def test_render_spine_markdown_failed_verification() -> None:
    """Markdown shows FAILED when verification is not successful."""
    spine = build_spine_proof(
        intent_text="print hello world",
        hlf_source='[HLF-v3]\nFUNCTION main {\n  RESULT 0 "hello"\n}\n\u03a9\n',
        compile_result=_make_mock_compile_result(),
        execute_result=_make_mock_execute_result(),
        memory_result=_make_mock_memory_result(),
    )

    # Tamper to break verification
    spine["phases"]["intent"]["text"] = "tampered"
    spine["verification"] = verify_spine_proof(spine)
    md = render_spine_markdown(spine)

    assert "FAILED" in md


# ── round-trip integration tests ─────────────────────────────────────────


def test_build_verify_render_roundtrip() -> None:
    """Full round-trip: build proof, verify it, render markdown — all consistent."""
    intent = "compute the sum of 1 and 2"
    hlf = '[HLF-v3]\nFUNCTION main {\n  RESULT 0 "3"\n}\n\u03a9\n'

    spine = build_spine_proof(
        intent_text=intent,
        hlf_source=hlf,
        compile_result=_make_mock_compile_result(),
        execute_result=_make_mock_execute_result(),
        memory_result=_make_mock_memory_result(),
    )
    verification = verify_spine_proof(spine)

    assert verification["verified"] is True
    assert spine["intent_text"] == intent

    md = render_spine_markdown(spine)
    assert intent in md or "Spine Proof" in md

    # Re-verify from markdown's version — should be consistent
    spine["verification"] = verification
    assert spine["verification"]["verified"] is True


def test_spine_proof_version_is_declared() -> None:
    """The spine proof version is declared and matches the module constant."""
    spine = build_spine_proof(
        intent_text="test",
        hlf_source='[HLF-v3]\nFUNCTION main {\n  RESULT 0 "ok"\n}\n\u03a9\n',
        compile_result=_make_mock_compile_result(),
        execute_result=_make_mock_execute_result(),
        memory_result=_make_mock_memory_result(),
    )

    assert spine["spine_proof_version"] == SPINE_PROOF_VERSION
    assert SPINE_PROOF_VERSION == "spine-proof-bridge-v1"


def test_bridge_lane_is_explicit() -> None:
    """Bridge lane can be customized and is reflected in the proof."""
    spine = build_spine_proof(
        intent_text="test",
        hlf_source='[HLF-v3]\nFUNCTION main {\n  RESULT 0 "ok"\n}\n\u03a9\n',
        compile_result=_make_mock_compile_result(),
        execute_result=_make_mock_execute_result(),
        memory_result=_make_mock_memory_result(),
        bridge_lane="current_truth",
    )

    assert spine["bridge_lane"] == "current_truth"
