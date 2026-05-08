from __future__ import annotations

import hashlib
import json
from typing import Any

ZERO_HASH = "0" * 64
PROOF_VERSION = "hash-chain-v1"
PROOF_BOUNDARY = {
    "integrity": "sha256_hash_chain",
    "cryptographic_claim": "tamper-evident content hashing only",
    "signature": "none",
    "non_repudiation": False,
    "confidentiality": False,
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def sha256_digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def freeze_payload(value: Any) -> Any:
    return json.loads(canonical_json(value))


def governance_body(value: dict[str, Any]) -> dict[str, Any]:
    excluded = {"governance_proof", "governance_proofs"}
    return {key: item for key, item in value.items() if key not in excluded}


def build_event_chain(
    events: list[dict[str, Any]],
    *,
    chain_id: str,
    initial_hash: str = ZERO_HASH,
) -> dict[str, Any]:
    prev_hash = initial_hash
    entries: list[dict[str, Any]] = []
    for index, event in enumerate(events):
        event_type = str(event.get("event_type") or event.get("kind") or f"event_{index}")
        payload = freeze_payload(event.get("payload", event))
        payload_hash = sha256_digest(payload)
        event_hash = sha256_digest(
            {
                "chain_id": chain_id,
                "index": index,
                "event_type": event_type,
                "payload_hash": payload_hash,
                "prev_hash": prev_hash,
            }
        )
        entries.append(
            {
                "index": index,
                "event_type": event_type,
                "payload": payload,
                "payload_hash": payload_hash,
                "prev_hash": prev_hash,
                "event_hash": event_hash,
            }
        )
        prev_hash = event_hash
    return {
        "chain_id": chain_id,
        "algorithm": "sha256",
        "initial_hash": initial_hash,
        "head_hash": prev_hash,
        "event_count": len(entries),
        "events": entries,
    }


def verify_event_chain(chain: dict[str, Any]) -> dict[str, Any]:
    chain_id = str(chain.get("chain_id") or "")
    prev_hash = str(chain.get("initial_hash") or ZERO_HASH)
    errors: list[str] = []
    events = chain.get("events") if isinstance(chain.get("events"), list) else []
    for expected_index, entry in enumerate(events):
        if not isinstance(entry, dict):
            errors.append(f"entry {expected_index} is not an object")
            continue
        if int(entry.get("index", -1)) != expected_index:
            errors.append(f"entry {expected_index} index mismatch")
        if str(entry.get("prev_hash") or "") != prev_hash:
            errors.append(f"entry {expected_index} prev_hash mismatch")
        payload_hash = sha256_digest(entry.get("payload"))
        if payload_hash != str(entry.get("payload_hash") or ""):
            errors.append(f"entry {expected_index} payload_hash mismatch")
        event_type = str(entry.get("event_type") or f"event_{expected_index}")
        event_hash = sha256_digest(
            {
                "chain_id": chain_id,
                "index": expected_index,
                "event_type": event_type,
                "payload_hash": payload_hash,
                "prev_hash": prev_hash,
            }
        )
        if event_hash != str(entry.get("event_hash") or ""):
            errors.append(f"entry {expected_index} event_hash mismatch")
        prev_hash = str(entry.get("event_hash") or "")
    if prev_hash != str(chain.get("head_hash") or ""):
        errors.append("head_hash mismatch")
    declared_count = int(chain.get("event_count") or 0)
    if declared_count != len(events):
        errors.append("event_count mismatch")
    return {
        "status": "ok" if not errors else "error",
        "verified": not errors,
        "error_count": len(errors),
        "errors": errors,
        "chain_id": chain_id,
        "head_hash": chain.get("head_hash"),
        "event_count": len(events),
        "boundary": dict(PROOF_BOUNDARY),
    }


def build_anchor(anchor_type: str, source: str, payload: Any) -> dict[str, Any]:
    frozen = freeze_payload(payload)
    return {
        "anchor_type": anchor_type,
        "source": source,
        "payload_hash": sha256_digest(frozen),
        "payload": frozen,
    }


def summarize_memory_anchor_trust(memory_anchors: list[dict[str, Any]]) -> dict[str, Any]:
    statuses: dict[str, int] = {}
    trusted_count = 0
    lineage_count = 0
    integrity_count = 0
    advisory_count = 0
    for anchor in memory_anchors:
        payload = anchor.get("payload") if isinstance(anchor, dict) else {}
        evidence = payload.get("evidence") if isinstance(payload, dict) and isinstance(payload.get("evidence"), dict) else payload
        if not isinstance(evidence, dict):
            evidence = {}
        status = str(evidence.get("state") or evidence.get("governance_status") or "unknown")
        statuses[status] = statuses.get(status, 0) + 1
        if bool(evidence.get("trusted_for_governance", False)):
            trusted_count += 1
        if bool(evidence.get("source_lineage_present", False)):
            lineage_count += 1
        if evidence.get("content_hash_valid") is not False:
            integrity_count += 1
        if str(evidence.get("source_authority_label") or "").lower() == "advisory":
            advisory_count += 1
    return {
        "anchor_count": len(memory_anchors),
        "trusted_for_governance_count": trusted_count,
        "source_lineage_present_count": lineage_count,
        "content_hash_valid_count": integrity_count,
        "advisory_authority_count": advisory_count,
        "status_counts": dict(sorted(statuses.items())),
        "claim_lane": "advisory fields are reported as advisory; this is not a signature or non-repudiation proof",
    }


def build_governance_proof(
    *,
    artifact_kind: str,
    artifact_id: str,
    events: list[dict[str, Any]],
    memory_anchors: list[dict[str, Any]] | None = None,
    runtime_anchors: list[dict[str, Any]] | None = None,
    replay_scope: dict[str, Any] | None = None,
) -> dict[str, Any]:
    chain_id = sha256_digest({"artifact_kind": artifact_kind, "artifact_id": artifact_id})[:32]
    chain = build_event_chain(events, chain_id=chain_id)
    memory = memory_anchors or []
    runtime = runtime_anchors or []
    replay = replay_scope or {}
    return {
        "proof_version": PROOF_VERSION,
        "artifact_kind": artifact_kind,
        "artifact_id": artifact_id,
        "boundary": dict(PROOF_BOUNDARY),
        "chain": chain,
        "chain_head": chain["head_hash"],
        "memory_anchors": memory,
        "runtime_anchors": runtime,
        "anchor_summary": {
            "memory_anchor_count": len(memory),
            "runtime_anchor_count": len(runtime),
            "memory_trust": summarize_memory_anchor_trust(memory),
        },
        "deterministic_replay": {
            "mode": "canonical_json_equivalence",
            "scope": replay,
            "scope_hash": sha256_digest(replay),
        },
        "operator_summary": (
            "SHA-256 hash-chain integrity proof with memory/runtime anchors; "
            "no digital signature, non-repudiation, or confidentiality is claimed."
        ),
    }


def verify_governance_proof(proof: dict[str, Any]) -> dict[str, Any]:
    chain = proof.get("chain") if isinstance(proof.get("chain"), dict) else {}
    chain_report = verify_event_chain(chain)
    anchor_errors: list[str] = []
    for section in ("memory_anchors", "runtime_anchors"):
        anchors = proof.get(section) if isinstance(proof.get(section), list) else []
        for index, anchor in enumerate(anchors):
            if not isinstance(anchor, dict):
                anchor_errors.append(f"{section}[{index}] is not an object")
                continue
            payload_hash = sha256_digest(anchor.get("payload"))
            if payload_hash != str(anchor.get("payload_hash") or ""):
                anchor_errors.append(f"{section}[{index}] payload_hash mismatch")
    replay = proof.get("deterministic_replay") if isinstance(proof.get("deterministic_replay"), dict) else {}
    scope_hash = sha256_digest(replay.get("scope") if isinstance(replay, dict) else {})
    if scope_hash != str(replay.get("scope_hash") or ""):
        anchor_errors.append("deterministic_replay scope_hash mismatch")
    verified = bool(chain_report.get("verified")) and not anchor_errors
    memory_anchors = proof.get("memory_anchors") if isinstance(proof.get("memory_anchors"), list) else []
    return {
        "status": "ok" if verified else "error",
        "verified": verified,
        "chain": chain_report,
        "anchor_errors": anchor_errors,
        "memory_trust": summarize_memory_anchor_trust(memory_anchors),
        "boundary": dict(PROOF_BOUNDARY),
        "operator_summary": (
            "Proof verifies SHA-256 hash-chain and anchor payload hashes only."
            if verified
            else "Proof verification failed; see chain and anchor errors."
        ),
    }


def render_proof_markdown(proof: dict[str, Any]) -> str:
    report = verify_governance_proof(proof)
    boundary = proof.get("boundary") if isinstance(proof.get("boundary"), dict) else PROOF_BOUNDARY
    lines = [
        "# Governance Proof Audit",
        "",
        f"- Artifact: {proof.get('artifact_kind')} / {proof.get('artifact_id')}",
        f"- Verification: {report.get('status')}",
        f"- Chain head: {proof.get('chain_head')}",
        f"- Events: {(proof.get('chain') or {}).get('event_count')}",
        f"- Memory anchors: {len(proof.get('memory_anchors') or [])}",
        f"- Runtime anchors: {len(proof.get('runtime_anchors') or [])}",
        f"- Boundary: {boundary.get('cryptographic_claim')}; signature={boundary.get('signature')}",
        "",
        str(report.get("operator_summary") or ""),
    ]
    return "\n".join(lines) + "\n"


__all__ = [
    "PROOF_BOUNDARY",
    "PROOF_VERSION",
    "ZERO_HASH",
    "build_anchor",
    "build_event_chain",
    "build_governance_proof",
    "canonical_json",
    "freeze_payload",
    "governance_body",
    "render_proof_markdown",
    "sha256_digest",
    "summarize_memory_anchor_trust",
    "verify_event_chain",
    "verify_governance_proof",
]
