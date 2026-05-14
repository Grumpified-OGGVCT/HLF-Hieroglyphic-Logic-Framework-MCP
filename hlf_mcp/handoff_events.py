from __future__ import annotations

import hashlib
import json
import time
from typing import Any

HANDOFF_EVENT_TYPES = {"delegate", "vote", "dissent", "progress", "complete"}
LIFECYCLE_PHASES = {"specify", "plan", "execute", "verify", "merge"}
HANDOFF_CONTRACT_TEMPLATES = {"delegation", "dissent", "vote", "review_board"}
PERSONA_ROLES = {
    "planner", "executor", "verifier", "scribe", "operator",
    "strategist", "steward", "sentinel", "herald", "chronicler",
    "cove", "consolidator",
}

HANDOFF_EVENT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "hlf-handoff-event-v1",
    "title": "HLF Handoff Event Primitive",
    "description": (
        "Conformant JSON event where Agent A hands scope S to Agent B with constraints C, "
        "delegation gas/time bounds, payload hash, and linear lineage hash."
    ),
    "type": "object",
    "required": [
        "schema",
        "$type",
        "event_type",
        "parent_event_hash",
        "event_hash",
        "payload_hash",
        "lineage_hash",
        "delegator",
        "delegate",
        "scope",
        "constraints",
        "delegation_gas_ceiling",
        "proof_boundary",
        "source_persona",
        "target_persona",
    ],
    "properties": {
        "schema": {"const": "hlf-handoff-event-v1"},
        "$type": {"const": "hlf://schema/handoff_event"},
        "event_type": {"enum": sorted(HANDOFF_EVENT_TYPES)},
        "lifecycle_phase": {"enum": sorted(LIFECYCLE_PHASES)},
        "parent_event_hash": {"type": "string"},
        "event_hash": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        "payload_hash": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        "lineage_hash": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        "delegator": {"type": "string", "minLength": 1},
        "delegate": {"type": "string", "minLength": 1},
        "scope": {"oneOf": [{"type": "string", "minLength": 1}, {"type": "object"}]},
        "constraints": {"oneOf": [{"type": "object"}, {"type": "array"}]},
        "delegation_gas_ceiling": {"type": ["integer", "null"]},
        "deadline": {"type": "string"},
        "epoch": {"type": "string"},
        "claim_lane": {"type": "string"},
        "proof_boundary": {
            "type": "object",
            "properties": {
                "attestable_disagreement": {"type": "boolean"},
                "bft_consensus": {"const": False},
                "grammar_extension": {"const": False},
                "framework_or_dsl": {"const": False},
            },
        },
        "vm_gas_limit": {"type": ["integer", "null"]},
        "gas_bounds": {
            "type": "object",
            "properties": {
                "delegation_gas_ceiling": {"type": ["integer", "null"]},
                "vm_gas_limit": {"type": ["integer", "null"]},
                "separate_delegation_gas_from_vm_gas": {"const": True},
            },
        },
        "external_agent_conformance": {
            "type": "object",
            "properties": {
                "schema": {"const": "hlf-handoff-event-v1"},
                "$type": {"const": "hlf://schema/handoff_event"},
                "json_conformant": {"const": True},
                "hlf_native": {"type": "boolean"},
            },
        },
        "route_trace_ref": {"oneOf": [{"type": "string"}, {"type": "object"}]},
        "orchestration_ref": {"oneOf": [{"type": "string"}, {"type": "object"}]},
        "semantic_drift": {"type": "object"},
        "source_persona": {"type": "string", "minLength": 1},
        "target_persona": {"type": "string", "minLength": 1},
    },
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def sha256_hex(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def get_handoff_event_schema() -> dict[str, Any]:
    return dict(HANDOFF_EVENT_SCHEMA)


def get_handoff_contract_templates() -> dict[str, Any]:
    return {
        "$type": "hlf://schema/handoff_contract_templates",
        "schema": "hlf-handoff-contract-templates-v1",
        "claim_lane": "current-true",
        "proof_boundary": {
            "framework_or_dsl": False,
            "grammar_extension": False,
            "description": (
                "Templates are JSON contract compositions over handoff_event-v1. "
                "They do not create a swarm DSL and do not require HLF compilation."
            ),
        },
        "templates": {
            "delegation": {
                "description": "Delegator assigns bounded scope to delegate, then receives progress/complete events.",
                "event_sequence": ["delegate", "progress", "complete"],
                "required_payload_fields": ["intent"],
            },
            "vote": {
                "description": "Reviewers emit attestable vote events over a delegated scope.",
                "event_sequence": ["delegate", "vote"],
                "required_payload_fields": ["vote", "rationale"],
            },
            "dissent": {
                "description": "Reviewer emits an attestable dissent event without claiming BFT consensus.",
                "event_sequence": ["delegate", "dissent"],
                "required_payload_fields": ["dissent", "rationale"],
            },
            "review_board": {
                "description": "Multiple JSON vote and dissent events compose into an inspectable review-board packet.",
                "event_sequence": ["delegate", "vote", "vote", "dissent", "complete"],
                "required_payload_fields": ["review_board_id", "rationale"],
            },
        },
    }


def build_handoff_contract_template(
    *,
    template: str,
    scope: str,
    participants: list[str] | None = None,
    lifecycle_phase: str = "verify",
) -> dict[str, Any]:
    normalized_template = str(template or "").strip().lower()
    templates = get_handoff_contract_templates()["templates"]
    if normalized_template not in templates:
        return {
            "status": "error",
            "error": "unsupported_handoff_contract_template",
            "supported_templates": sorted(HANDOFF_CONTRACT_TEMPLATES),
        }
    normalized_phase = normalize_lifecycle_phase(lifecycle_phase)
    return {
        "status": "ok",
        "$type": "hlf://schema/handoff_contract_template",
        "schema": "hlf-handoff-contract-template-v1",
        "template": normalized_template,
        "scope": str(scope or ""),
        "participants": [str(item) for item in (participants or []) if str(item)],
        "lifecycle_phase": normalized_phase,
        "contract": templates[normalized_template],
        "event_contract": {
            "event_schema": "hlf-handoff-event-v1",
            "$type": "hlf://schema/handoff_event",
            "event_sequence": list(templates[normalized_template]["event_sequence"]),
            "payload_form": "open_json",
            "non_hlf_participation": True,
            "requires_hlf_compilation": False,
        },
        "proof_boundary": get_handoff_contract_templates()["proof_boundary"],
    }


def normalize_lifecycle_phase(value: str) -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in LIFECYCLE_PHASES else "execute"


def evaluate_semantic_drift(
    *,
    original_intent: str,
    delegate_result: str,
    threshold: float = 0.55,
) -> dict[str, Any]:
    """Deterministic lexical drift check for cross-agent delegation/result closure.

    This is intentionally a bounded proof slice: it catches obvious scope/target
    drift without claiming full semantic verification or model-based entailment.
    """
    original_tokens = _intent_tokens(original_intent)
    result_tokens = _intent_tokens(delegate_result)
    overlap = original_tokens & result_tokens
    union = original_tokens | result_tokens
    similarity = round(len(overlap) / len(union), 4) if union else 1.0
    missing_tokens = sorted(original_tokens - result_tokens)
    introduced_tokens = sorted(result_tokens - original_tokens)
    drift_flags: list[str] = []
    if similarity < threshold:
        drift_flags.append("low_token_overlap")
    if missing_tokens:
        drift_flags.append("intent_terms_missing_from_delegate_result")
    if any(token in introduced_tokens for token in {"delete", "destructive", "publish", "deploy"}):
        drift_flags.append("potential_scope_expansion")
    return {
        "$type": "hlf://schema/handoff_semantic_drift",
        "schema": "hlf-handoff-semantic-drift-v1",
        "original_intent_hash": sha256_hex(str(original_intent or "")),
        "delegate_result_hash": sha256_hex(str(delegate_result or "")),
        "similarity_score": similarity,
        "threshold": float(threshold),
        "drift_detected": bool(drift_flags),
        "drift_flags": drift_flags,
        "missing_intent_terms": missing_tokens,
        "introduced_result_terms": introduced_tokens,
        "claim_lane": "current-true",
        "proof_boundary": {
            "bounded_lexical_check": True,
            "full_semantic_entailment": False,
            "requires_hlf_compilation": False,
        },
    }


def _intent_tokens(value: str) -> set[str]:
    normalized = "".join(ch.lower() if ch.isalnum() else " " for ch in str(value or ""))
    stop = {
        "a",
        "an",
        "and",
        "or",
        "the",
        "to",
        "for",
        "of",
        "in",
        "with",
        "is",
        "was",
        "be",
        "by",
        "on",
        "as",
        "this",
        "that",
    }
    return {token for token in normalized.split() if len(token) > 2 and token not in stop}


def coerce_json_payload(payload: Any = None, payload_json: str = "") -> tuple[Any, dict[str, Any]]:
    if payload_json and payload not in (None, {}, []):
        return payload, {"accepted": True, "source": "payload", "payload_json_ignored": True}
    if payload_json:
        try:
            decoded = json.loads(payload_json)
        except json.JSONDecodeError as exc:
            return None, {
                "accepted": False,
                "source": "payload_json",
                "error": "invalid_json",
                "message": str(exc),
            }
        return decoded, {"accepted": True, "source": "payload_json"}
    if payload is None:
        payload = {}
    return payload, {"accepted": True, "source": "payload"}


def normalize_handoff_event(
    *,
    delegator: str,
    delegate: str,
    scope: str | dict[str, Any],
    constraints: dict[str, Any] | list[Any] | None = None,
    delegation_gas_ceiling: int | None = None,
    deadline: str = "",
    epoch: str = "",
    event_type: str = "delegate",
    claim_lane: str = "",
    proof_boundary: dict[str, Any] | None = None,
    payload: Any = None,
    payload_json: str = "",
    parent_event_hash: str = "",
    parent_lineage_hash: str = "",
    vm_gas_limit: int | None = None,
    source_agent_kind: str = "hlf",
    lifecycle_phase: str = "execute",
    route_trace_ref: str | dict[str, Any] | None = None,
    orchestration_ref: str | dict[str, Any] | None = None,
    semantic_drift: dict[str, Any] | None = None,
    source_persona: str = "",
    target_persona: str = "",
    timestamp: float | None = None,
) -> dict[str, Any]:
    normalized_type = str(event_type or "").strip().lower()
    if normalized_type not in HANDOFF_EVENT_TYPES:
        return {
            "status": "error",
            "error": "unsupported_handoff_event_type",
            "supported_event_types": sorted(HANDOFF_EVENT_TYPES),
            "event_type": event_type,
        }

    normalized_delegator = str(delegator or "").strip()
    normalized_delegate = str(delegate or "").strip()
    if not normalized_delegator or not normalized_delegate:
        return {
            "status": "error",
            "error": "delegator_and_delegate_required",
            "message": "Handoff events require both delegator and delegate.",
        }

    normalized_scope: str | dict[str, Any]
    if isinstance(scope, dict):
        normalized_scope = dict(scope)
        scope_present = bool(normalized_scope)
    else:
        normalized_scope = str(scope or "").strip()
        scope_present = bool(normalized_scope)
    if not scope_present:
        return {
            "status": "error",
            "error": "scope_required",
            "message": "Handoff events require a non-empty scope.",
        }

    normalized_constraints: dict[str, Any] | list[Any]
    if isinstance(constraints, dict):
        normalized_constraints = dict(constraints)
    elif isinstance(constraints, list):
        normalized_constraints = list(constraints)
    else:
        normalized_constraints = {}

    decoded_payload, payload_acceptance = coerce_json_payload(payload, payload_json)
    if payload_acceptance.get("accepted") is not True:
        return {"status": "error", **payload_acceptance}

    now = time.time() if timestamp is None else float(timestamp)
    payload_hash = sha256_hex(decoded_payload)
    normalized_parent_event_hash = str(parent_event_hash or "").strip()
    normalized_parent_lineage_hash = str(parent_lineage_hash or "").strip()
    normalized_source_agent_kind = str(source_agent_kind or "hlf").strip().lower()
    normalized_source_persona = str(source_persona or "").strip().lower()
    normalized_target_persona = str(target_persona or "").strip().lower()
    external_agent_conformance = {
        "schema": "hlf-handoff-event-v1",
        "$type": "hlf://schema/handoff_event",
        "json_conformant": True,
        "hlf_native": normalized_source_agent_kind == "hlf",
        "source_agent_kind": normalized_source_agent_kind,
        "payload_acceptance": payload_acceptance,
    }
    proof_boundary_record = {
        **(dict(proof_boundary or {}) if isinstance(proof_boundary, dict) else {}),
        "boundary_type": "handoff_event",
        "attestable_disagreement": normalized_type in {"vote", "dissent"},
        "bft_consensus": False,
        "grammar_extension": False,
        "framework_or_dsl": False,
    }
    gas_bounds = {
        "delegation_gas_ceiling": delegation_gas_ceiling,
        "vm_gas_limit": vm_gas_limit,
        "separate_delegation_gas_from_vm_gas": True,
    }
    event_body = {
        "schema": "hlf-handoff-event-v1",
        "$type": "hlf://schema/handoff_event",
        "event_type": normalized_type,
        "lifecycle_phase": normalize_lifecycle_phase(lifecycle_phase),
        "parent_event_hash": normalized_parent_event_hash,
        "delegator": normalized_delegator,
        "delegate": normalized_delegate,
        "scope": normalized_scope,
        "constraints": normalized_constraints,
        "delegation_gas_ceiling": delegation_gas_ceiling,
        "deadline": str(deadline or ""),
        "epoch": str(epoch or ""),
        "payload_hash": payload_hash,
        "claim_lane": str(claim_lane or ""),
        "proof_boundary": proof_boundary_record,
        "vm_gas_limit": vm_gas_limit,
        "gas_bounds": gas_bounds,
        "external_agent_conformance": external_agent_conformance,
        "route_trace_ref": route_trace_ref or "",
        "orchestration_ref": orchestration_ref or "",
        "semantic_drift": dict(semantic_drift or {}),
        "source_persona": normalized_source_persona,
        "target_persona": normalized_target_persona,
        "timestamp": now,
    }
    event_hash = sha256_hex(event_body)
    lineage_hash = sha256_hex(
        {
            "linear_handoff_chain_v1": True,
            "parent_lineage_hash": normalized_parent_lineage_hash,
            "event_hash": event_hash,
        }
    )
    return {
        "status": "ok",
        **event_body,
        "payload": decoded_payload,
        "event_hash": event_hash,
        "lineage_hash": lineage_hash,
        "lineage_model": {
            "current": "linear_handoff_chain_v1",
            "upgrade_path": (
                "Merkle upgrade path: keep event_hash as leaf hash, group sibling event leaves "
                "by epoch or scope, and publish a Merkle root while retaining parent_event_hash "
                "for backwards-compatible linear verification."
            ),
        },
    }


def persona_lineage_entry(
    *,
    persona_role: str,
    event_hash: str,
    lifecycle_phase: str,
) -> dict[str, Any]:
    """Produce a bounded persona-lineage entry for audit/handoff tracing."""
    return {
        "persona_role": str(persona_role or "").strip().lower(),
        "event_hash": str(event_hash or ""),
        "lifecycle_phase": str(lifecycle_phase or ""),
        "claim_lane": "bridge-true",
        "proof_boundary": {
            "persona_lineage_tracking": True,
            "runtime_enforcement": False,
            "requires_hlf_compilation": False,
        },
    }




def _scan_handoff_chain_freshness(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Scan handoff chain events for stale/superseded/revoked evidence references.

    Returns a structured verdict that surfaces freshness issues across the
    handoff lifecycle chain.  This is the B4 lifecycle freshness gate for
    handoff resolution.
    """
    stale_entries: list[dict[str, Any]] = []
    superseded_entries: list[dict[str, Any]] = []
    revoked_entries: list[dict[str, Any]] = []
    fresh_count = 0
    total_checked = 0

    for event in events:
        if not isinstance(event, dict):
            continue
        event_hash = str(event.get("event_hash", ""))[:12]
        # Check payload for embedded evidence
        payload = event.get("payload")
        if isinstance(payload, dict):
            for key in ("evidence", "memory_evidence", "hks_evidence", "proof_surface"):
                ev = payload.get(key)
                if isinstance(ev, dict):
                    total_checked += 1
                    freshness = str(ev.get("freshness_status") or "unknown")
                    superseded = bool(ev.get("superseded"))
                    revoked = bool(ev.get("revoked"))
                    tombstoned = bool(ev.get("tombstoned"))
                    entry = {
                        "event_hash": event_hash,
                        "scope": str(event.get("scope", ""))[:60],
                        "source_key": key,
                        "sha256": str(ev.get("sha256", ev.get("bundle_sha256", ""))),
                        "freshness_status": freshness,
                        "superseded": superseded,
                        "revoked": revoked,
                        "tombstoned": tombstoned,
                    }
                    if revoked or tombstoned:
                        revoked_entries.append(entry)
                    elif superseded:
                        superseded_entries.append(entry)
                    elif freshness == "stale":
                        stale_entries.append(entry)
                    else:
                        fresh_count += 1
                elif isinstance(ev, list):
                    for i, item in enumerate(ev):
                        if isinstance(item, dict):
                            total_checked += 1
                            freshness = str(item.get("freshness_status") or "unknown")
                            superseded = bool(item.get("superseded"))
                            revoked = bool(item.get("revoked"))
                            tombstoned = bool(item.get("tombstoned"))
                            entry = {
                                "event_hash": event_hash,
                                "scope": str(event.get("scope", ""))[:60],
                                "source_key": f"{key}[{i}]",
                                "sha256": str(item.get("sha256", item.get("bundle_sha256", ""))),
                                "freshness_status": freshness,
                                "superseded": superseded,
                                "revoked": revoked,
                                "tombstoned": tombstoned,
                            }
                            if revoked or tombstoned:
                                revoked_entries.append(entry)
                            elif superseded:
                                superseded_entries.append(entry)
                            elif freshness == "stale":
                                stale_entries.append(entry)
                            else:
                                fresh_count += 1

    all_fresh = len(stale_entries) == 0 and len(superseded_entries) == 0 and len(revoked_entries) == 0
    return {
        "all_fresh": all_fresh,
        "total_checked": total_checked,
        "fresh_count": fresh_count,
        "stale_count": len(stale_entries),
        "superseded_count": len(superseded_entries),
        "revoked_count": len(revoked_entries),
        "stale_entries": stale_entries,
        "superseded_entries": superseded_entries,
        "revoked_entries": revoked_entries,
    }


def verify_handoff_chain(events: list[dict[str, Any]]) -> dict[str, Any]:
    continuity_errors: list[dict[str, Any]] = []
    type_counts = {event_type: 0 for event_type in sorted(HANDOFF_EVENT_TYPES)}
    phase_counts = {phase: 0 for phase in sorted(LIFECYCLE_PHASES)}
    persona_transitions: list[dict[str, Any]] = []
    previous_event_hash = ""
    previous_lineage_hash = ""
    for index, event in enumerate(events):
        event_type = str(event.get("event_type") or "")
        if event_type in type_counts:
            type_counts[event_type] += 1
        lifecycle_phase = str(event.get("lifecycle_phase") or "")
        if lifecycle_phase in phase_counts:
            phase_counts[lifecycle_phase] += 1
        source_persona = str(event.get("source_persona") or "")
        target_persona = str(event.get("target_persona") or "")
        if source_persona or target_persona:
            persona_transitions.append(persona_lineage_entry(
                persona_role=target_persona or source_persona,
                event_hash=str(event.get("event_hash") or ""),
                lifecycle_phase=lifecycle_phase,
            ))
        parent_hash = str(event.get("parent_event_hash") or "")
        if index == 0:
            if parent_hash:
                continuity_errors.append(
                    {
                        "index": index,
                        "event_hash": event.get("event_hash"),
                        "error": "first_event_has_parent_event_hash",
                    }
                )
        elif parent_hash != previous_event_hash:
            continuity_errors.append(
                {
                    "index": index,
                    "event_hash": event.get("event_hash"),
                    "error": "parent_event_hash_mismatch",
                    "expected_parent_event_hash": previous_event_hash,
                    "actual_parent_event_hash": parent_hash,
                }
            )
        recomputed_lineage_hash = sha256_hex(
            {
                "linear_handoff_chain_v1": True,
                "parent_lineage_hash": previous_lineage_hash if index else "",
                "event_hash": event.get("event_hash"),
            }
        )
        if event.get("lineage_hash") != recomputed_lineage_hash:
            continuity_errors.append(
                {
                    "index": index,
                    "event_hash": event.get("event_hash"),
                    "error": "lineage_hash_mismatch",
                    "expected_lineage_hash": recomputed_lineage_hash,
                    "actual_lineage_hash": event.get("lineage_hash"),
                }
            )
        previous_event_hash = str(event.get("event_hash") or "")
        previous_lineage_hash = str(event.get("lineage_hash") or "")

    return {
        "status": "ok" if not continuity_errors else "warning",
        "verified": not continuity_errors,
        "event_count": len(events),
        "head_event_hash": previous_event_hash,
        "head_lineage_hash": previous_lineage_hash,
        "continuity_errors": continuity_errors,
        "event_type_counts": type_counts,
        "lifecycle_phase_counts": phase_counts,
        "persona_transitions": persona_transitions,
        "semantic_drift_events": sum(
            1
            for event in events
            if isinstance(event.get("semantic_drift"), dict)
            and event.get("semantic_drift", {}).get("drift_detected") is True
        ),
        "attestable_disagreement_events": type_counts["vote"] + type_counts["dissent"],
        "bft_consensus": False,
        "lineage_model": "linear_handoff_chain_v1",
        "merkle_upgrade_path": (
            "Use each event_hash as a Merkle leaf, bind leaf order to parent_event_hash continuity, "
            "and publish epoch/scope roots without changing the conformant JSON event schema."
        ),
        # ── B4: Memory freshness scan across handoff chain ──
        "memory_freshness": _scan_handoff_chain_freshness(events),
    }
