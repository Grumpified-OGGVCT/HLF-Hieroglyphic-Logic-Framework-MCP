"""
Spine Proof — end-to-end Merkle trust demonstration across the HLF pipeline.

Bridge contract (B5): builds demonstrable trust proof across
intent → compile → execute → memory-store without overstating completion.

Uses the existing governance_proofs primitives for hash-chain construction.
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from hlf_mcp.hlf.governance_proofs import (
    PROOF_BOUNDARY,
    ZERO_HASH,
    build_anchor,
    build_event_chain,
    build_governance_proof,
    freeze_payload,
    render_proof_markdown,
    sha256_digest,
    summarize_memory_anchor_trust,
    verify_event_chain,
    verify_governance_proof,
)

SPINE_PROOF_VERSION = "spine-proof-bridge-v1"

# ── spine event types ──────────────────────────────────────────────────────

SPINE_EVENT_KINDS = frozenset(
    {
        "intent_captured",
        "translation_to_hlf",
        "compilation",
        "execution",
        "memory_store",
    }
)

SPINE_REQUIRED_PHASES = ("intent", "translate", "compile", "execute", "memory")


# ── public API ─────────────────────────────────────────────────────────────


def build_spine_proof(
    *,
    intent_text: str,
    hlf_source: str,
    compile_result: dict[str, Any],
    execute_result: dict[str, Any],
    memory_result: dict[str, Any],
    bridge_lane: str = "bridge_contract",
) -> dict[str, Any]:
    """Build an end-to-end spine proof across the full HLF lifecycle.

    Args:
        intent_text: Original natural-language intent.
        hlf_source: HLF source produced by translation.
        compile_result: Result dict from hlf_compile.
        execute_result: Result dict from hlf_code_execute or hlf_run.
        memory_result: Result dict from hlf_memory_store.
        bridge_lane: Claim lane for the proof (default bridge_contract).

    Returns:
        A spine proof object suitable for operator inspection and verification.
    """
    intent_payload = freeze_payload({"text": intent_text, "timestamp_utc": _utc_now()})
    translate_payload = freeze_payload(
        {
            "hlf_source": hlf_source,
            "source_sha256": _source_sha256(hlf_source),
            "statement_count": _count_hlf_statements(hlf_source),
        }
    )
    compile_payload = freeze_payload(
        {
            "status": compile_result.get("status"),
            "ast_sha256": compile_result.get("ast_sha256"),
            "bytecode_sha256": compile_result.get("bytecode_sha256"),
            "statement_count": compile_result.get("statement_count", 0),
        }
    )
    execute_payload = freeze_payload(
        {
            "status": execute_result.get("status"),
            "result": execute_result.get("result"),
            "gas_used": execute_result.get("gas_used"),
            "governance_proof_ref": execute_result.get("governance_proof_ref"),
        }
    )
    memory_payload = freeze_payload(
        {
            "pointer": memory_result.get("pointer"),
            "sha256": memory_result.get("sha256"),
            "topic": memory_result.get("topic", "hlf-execution"),
            "audit_trace_id": memory_result.get("audit", {}).get("trace_id"),
        }
    )

    events = [
        {"event_type": "intent_captured", "payload": intent_payload},
        {"event_type": "translation_to_hlf", "payload": translate_payload},
        {"event_type": "compilation", "payload": compile_payload},
        {"event_type": "execution", "payload": execute_payload},
        {"event_type": "memory_store", "payload": memory_payload},
    ]

    proof = build_governance_proof(
        artifact_kind="hlf_spine_proof",
        artifact_id=sha256_digest({"intent": intent_text})[:32],
        events=events,
        memory_anchors=[
            build_anchor(
                "memory_ref",
                f"hlf_execution_{memory_result.get('pointer', 'unknown')}",
                memory_payload,
            )
        ],
        runtime_anchors=[
            build_anchor("compile_output", "hlf_compile", compile_payload),
            build_anchor("execute_output", "hlf_code_execute", execute_payload),
        ],
        replay_scope={
            "intent_sha256": sha256_digest(intent_payload),
            "hlf_source_sha256": translate_payload["source_sha256"],
            "compile_sha256": sha256_digest(compile_payload),
            "execute_sha256": sha256_digest(execute_payload),
            "memory_sha256": sha256_digest(memory_payload),
        },
    )

    trust_summary = _build_trust_summary(events, proof)

    spine: dict[str, Any] = {
        "spine_proof_version": SPINE_PROOF_VERSION,
        "bridge_lane": bridge_lane,
        "proof_boundary": dict(PROOF_BOUNDARY),
        "intent_text": intent_text,
        "phases": {
            "intent": intent_payload,
            "translate": translate_payload,
            "compile": compile_payload,
            "execute": execute_payload,
            "memory": memory_payload,
        },
        "linkage": {
            "intent": sha256_digest(intent_payload),
            "translate": sha256_digest(translate_payload),
            "compile": sha256_digest(compile_payload),
            "execute": sha256_digest(execute_payload),
            "memory": sha256_digest(memory_payload),
        },
        "trust_chain_summary": trust_summary,
        "hash_chain": proof,
        "operator_summary": (
            "Spine proof linking intent → HLF translation → compilation → execution → "
            "memory store through a SHA-256 hash chain. "
            "This is bridge_contract evidence; no digital signature or non-repudiation is claimed."
        ),
    }
    spine["verification"] = verify_spine_proof(spine)
    return spine


def verify_spine_proof(spine: dict[str, Any]) -> dict[str, Any]:
    """Verify a spine proof object's hash chain and structural integrity.

    Returns a verification report with status, errors, and trust assessment.
    """
    errors: list[str] = []

    # version check
    if spine.get("spine_proof_version") != SPINE_PROOF_VERSION:
        errors.append(f"spine_proof_version mismatch: {spine.get('spine_proof_version')}")

    # boundary check
    boundary = spine.get("proof_boundary", {})
    if isinstance(boundary, dict) and boundary.get("signature") != "none":
        errors.append("proof_boundary signature must be 'none'")

    # phase completeness
    phases = spine.get("phases", {})
    if not isinstance(phases, dict):
        errors.append("phases must be a dict")
    else:
        for phase_name in SPINE_REQUIRED_PHASES:
            if phase_name not in phases:
                errors.append(f"missing phase: {phase_name}")

    # linkage integrity
    linkage = spine.get("linkage", {})
    if isinstance(linkage, dict) and isinstance(phases, dict):
        for phase_name in SPINE_REQUIRED_PHASES:
            if phase_name in phases and phase_name in linkage:
                expected_hash = sha256_digest(phases[phase_name])
                if linkage[phase_name] != expected_hash:
                    errors.append(f"linkage hash mismatch for {phase_name}")

    # hash chain verification
    hash_chain = spine.get("hash_chain", {})
    if isinstance(hash_chain, dict):
        gov_verification = verify_governance_proof(hash_chain)
        if not gov_verification.get("verified"):
            errors.append("hash_chain verification failed")
            for chain_err in gov_verification.get("chain", {}).get("errors", []):
                errors.append(f"chain: {chain_err}")
            for anchor_err in gov_verification.get("anchor_errors", []):
                errors.append(f"anchor: {anchor_err}")
    else:
        errors.append("hash_chain missing or invalid")

    # event count check
    events = _get_chain_events(spine)
    if len(events) != len(SPINE_REQUIRED_PHASES):
        errors.append(
            f"event count mismatch: expected {len(SPINE_REQUIRED_PHASES)}, got {len(events)}"
        )

    verified = len(errors) == 0
    return {
        "status": "ok" if verified else "error",
        "verified": verified,
        "error_count": len(errors),
        "errors": errors,
        "phases_present": (
            [p for p in SPINE_REQUIRED_PHASES if p in phases] if isinstance(phases, dict) else []
        ),
        "boundary": dict(PROOF_BOUNDARY),
        "operator_summary": (
            "Spine proof hash chain and phase linkage verified successfully."
            if verified
            else f"Spine proof verification failed with {len(errors)} error(s)."
        ),
    }


def render_spine_markdown(spine: dict[str, Any]) -> str:
    """Render a spine proof as operator-readable markdown."""
    verification = spine.get("verification", verify_spine_proof(spine))
    linkage = spine.get("linkage", {})
    phases = spine.get("phases", {})
    trust = spine.get("trust_chain_summary", {})

    lines = [
        "# HLF Spine Proof — End-to-End Merkle Trust Demonstration",
        "",
        f"**Version:** `{spine.get('spine_proof_version', 'unknown')}`",
        f"**Lane:** `{spine.get('bridge_lane', 'bridge_contract')}`",
        f"**Verification:** {'✅ VERIFIED' if verification.get('verified') else '❌ FAILED'}",
        "",
        "## 🔗 Phase Linkage (SHA-256)",
        "",
    ]
    phase_labels = {
        "intent": "🎯 Intent Captured",
        "translate": "📝 Translation → HLF",
        "compile": "⚙️ Compilation → AST",
        "execute": "▶️ Execution → VM",
        "memory": "💾 Memory Store → Evidence",
    }
    for phase_name in SPINE_REQUIRED_PHASES:
        label = phase_labels.get(phase_name, phase_name)
        link_hash = linkage.get(phase_name, "missing")
        present = "✅" if phase_name in (phases or {}) else "❌"
        lines.append(f"- {present} **{label}**  ")
        lines.append(f"  `{link_hash[:32]}…`")

    lines.extend(
        [
            "",
            "## 🧱 Trust Chain Summary",
            "",
        ]
    )
    if trust:
        for key in ("phases_linked", "chain_head", "event_count", "memory_anchors", "runtime_anchors"):
            if key in trust:
                lines.append(f"- **{key.replace('_', ' ').title()}:** {trust[key]}")
        if trust.get("hash_algorithm"):
            lines.append(f"- **Hash Algorithm:** {trust['hash_algorithm']}")
        if trust.get("claim_lane_note"):
            lines.append(f"- **Claim Note:** {trust['claim_lane_note']}")
    else:
        lines.append("_(trust summary not available)_")

    lines.extend(
        [
            "",
            "## 📋 Proof Boundary",
            "",
            f"- **Integrity:** {spine.get('proof_boundary', {}).get('integrity', 'sha256_hash_chain')}",
            f"- **Signature:** {spine.get('proof_boundary', {}).get('signature', 'none')}",
            f"- **Non-repudiation:** {spine.get('proof_boundary', {}).get('non_repudiation', False)}",
            "",
            "## 📝 Operator Summary",
            "",
            spine.get("operator_summary", "No summary available."),
            "",
        ]
    )

    # add the governance proof audit
    hash_chain = spine.get("hash_chain", {})
    if hash_chain:
        lines.append("## 🔐 Governance Proof Audit")
        lines.append("")
        lines.append(render_proof_markdown(hash_chain))

    return "\n".join(lines) + "\n"


# ── helpers ────────────────────────────────────────────────────────────────


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _source_sha256(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _count_hlf_statements(source: str) -> int:
    """Count non-empty, non-comment lines in HLF source."""
    count = 0
    for line in source.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and stripped not in ("Ω",):
            count += 1
    return count


def _get_chain_events(spine: dict[str, Any]) -> list[dict[str, Any]]:
    chain = spine.get("hash_chain", {}).get("chain", {})
    events = chain.get("events") if isinstance(chain, dict) else []
    return events


def _build_trust_summary(
    events: list[dict[str, Any]], proof: dict[str, Any]
) -> dict[str, Any]:
    """Build a human-readable trust-chain summary."""
    return {
        "phases_linked": len(events),
        "phases": [e.get("event_type", "unknown") for e in events],
        "hash_algorithm": "SHA-256",
        "chain_head": proof.get("chain_head", "unknown"),
        "event_count": len(events),
        "memory_anchors": proof.get("anchor_summary", {}).get("memory_anchor_count", 0),
        "runtime_anchors": proof.get("anchor_summary", {}).get("runtime_anchor_count", 0),
        "claim_lane_note": "bridge_contract — tamper-evident hash chain; no cryptographic signature claimed",
    }
