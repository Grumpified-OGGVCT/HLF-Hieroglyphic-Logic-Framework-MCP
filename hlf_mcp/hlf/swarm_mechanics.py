from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from hlf_mcp.hlf.governance_proofs import (
    build_anchor,
    build_governance_proof,
    governance_body,
    sha256_digest,
)

SWARM_ARTIFACT_KIND = "hlf_swarm_mechanics"
SWARM_CONTRACT_VERSION = "1.0"


def build_swarm_mechanics_artifact(
    *,
    source: str,
    ast: dict[str, Any],
    validation: dict[str, Any],
    compile_result: dict[str, Any],
    handoff: dict[str, Any] | None = None,
    votes: list[dict[str, Any]] | None = None,
    dissent: list[dict[str, Any]] | None = None,
    progress_events: list[dict[str, Any]] | None = None,
    quorum: str = "strict",
) -> dict[str, Any]:
    """Materialize bounded local swarm mechanics as inspectable HLF-derived artifacts."""
    normalized_quorum = _normalize_quorum(quorum)
    statements = ast.get("statements") if isinstance(ast.get("statements"), list) else []
    source_sha256 = hashlib.sha256(source.encode("utf-8")).hexdigest()
    ast_sha256 = str(ast.get("sha256") or "")
    swarm_id = hashlib.sha256(
        f"{source_sha256}:{ast_sha256}:{SWARM_CONTRACT_VERSION}".encode()
    ).hexdigest()[:16]

    extracted_delegations = _extract_delegations(statements, swarm_id=swarm_id)
    extracted_votes = _extract_votes(statements, quorum=normalized_quorum)
    normalized_votes = extracted_votes + [
        _normalize_vote(item, index=len(extracted_votes) + index, quorum=normalized_quorum)
        for index, item in enumerate(votes or [])
        if isinstance(item, dict)
    ]
    dissent_records = _extract_dissent(statements) + [
        _normalize_dissent(item, index=index)
        for index, item in enumerate(dissent or [])
        if isinstance(item, dict)
    ]
    dissent_records.extend(_dissent_from_votes(normalized_votes))
    progress = _extract_progress(statements) + [
        _normalize_progress(item, index=index)
        for index, item in enumerate(progress_events or [])
        if isinstance(item, dict)
    ]

    generated_progress = _generated_progress_events(
        swarm_id=swarm_id,
        delegations=extracted_delegations,
        votes=normalized_votes,
        dissent=dissent_records,
    )
    progress = _dedupe_dicts(progress + generated_progress, key_fields=("event_id", "kind", "phase"))
    consensus = _build_consensus(normalized_votes, dissent_records, quorum=normalized_quorum)
    lineage = _build_lineage(
        source_sha256=source_sha256,
        ast_sha256=ast_sha256,
        compile_result=compile_result,
        handoff=handoff,
        delegations=extracted_delegations,
        votes=normalized_votes,
        dissent=dissent_records,
        progress=progress,
    )
    materialized_source = materialize_swarm_hlf(
        source,
        swarm_id=swarm_id,
        delegations=extracted_delegations,
        votes=normalized_votes,
        dissent=dissent_records,
        progress=progress,
        lineage=lineage,
        quorum=normalized_quorum,
    )

    artifact = {
        "artifact_kind": SWARM_ARTIFACT_KIND,
        "contract_version": SWARM_CONTRACT_VERSION,
        "swarm_id": swarm_id,
        "operator_summary": (
            "Bounded local swarm mechanics were materialized as HLF delegation, vote, "
            "dissent, lineage, and progress artifacts. No distributed A2A transport is claimed."
        ),
        "boundary": {
            "mode": "local_bounded_swarm",
            "distributed_a2a": False,
            "claim": "local HLF artifact coordination only",
        },
        "source": {
            "raw_hlf_source": source,
            "materialized_hlf_source": materialized_source,
            "source_sha256": source_sha256,
            "ast_sha256": ast_sha256,
            "validation": dict(validation),
        },
        "delegations": extracted_delegations,
        "votes": normalized_votes,
        "consensus": consensus,
        "dissent": dissent_records,
        "trace_lineage": lineage,
        "progress_events": progress,
        "handoff": _summarize_handoff(handoff),
    }
    artifact["governance_proof"] = build_governance_proof(
        artifact_kind=SWARM_ARTIFACT_KIND,
        artifact_id=swarm_id,
        events=[
            {"event_type": "source", "payload": artifact["source"]},
            {"event_type": "delegations", "payload": extracted_delegations},
            {"event_type": "votes", "payload": normalized_votes},
            {"event_type": "consensus", "payload": consensus},
            {"event_type": "dissent", "payload": dissent_records},
            {"event_type": "progress", "payload": progress},
            {"event_type": "trace_lineage", "payload": lineage},
            {"event_type": "handoff", "payload": artifact["handoff"]},
        ],
        memory_anchors=[build_anchor("memory", "swarm.source", artifact["source"])],
        runtime_anchors=[build_anchor("runtime", "swarm.trace_lineage", lineage)],
        replay_scope={
            "artifact_body_hash": sha256_digest(governance_body(artifact)),
            "source_sha256": source_sha256,
            "ast_sha256": ast_sha256,
            "quorum": normalized_quorum,
            "contract_version": SWARM_CONTRACT_VERSION,
        },
    )
    return artifact


def materialize_swarm_hlf(
    source: str,
    *,
    swarm_id: str,
    delegations: list[dict[str, Any]],
    votes: list[dict[str, Any]],
    dissent: list[dict[str, Any]],
    progress: list[dict[str, Any]],
    lineage: dict[str, Any],
    quorum: str,
) -> str:
    lines = [line.rstrip() for line in source.splitlines() if line.strip()]
    if lines and lines[-1].strip() == "Ω":
        lines = lines[:-1]
    tags = {_tag_from_line(line) for line in lines}

    if "TRACE" not in tags:
        lines.append(
            f'∇ [TRACE] swarm_id="{swarm_id}" source_sha256="{lineage["source_sha256"]}" '
            f'ast_sha256="{lineage["ast_sha256"]}"'
        )
    if not any(_tag_from_line(line) == "DELEGATE" for line in lines):
        for delegation in delegations:
            lines.append(
                '⌘ [DELEGATE] agent="{agent}" goal="{goal}" task_id="{task_id}"'.format(
                    agent=_escape_hlf_string(str(delegation.get("agent") or "local-agent")),
                    goal=_escape_hlf_string(str(delegation.get("goal") or "coordinate")),
                    task_id=_escape_hlf_string(str(delegation.get("task_id") or "")),
                )
            )
    if not any(_tag_from_line(line) in {"VOTE", "CONSENSUS"} for line in lines):
        for vote in votes:
            lines.append(
                '⨝ [VOTE] voter="{voter}" decision="{decision}" quorum="{quorum}"'.format(
                    voter=_escape_hlf_string(str(vote.get("voter") or "local-voter")),
                    decision=_escape_hlf_string(str(vote.get("decision") or "approve")),
                    quorum=_escape_hlf_string(quorum),
                )
            )
    if dissent and not any(_tag_from_line(line) in {"DISSENT", "VETO"} for line in lines):
        for item in dissent:
            lines.append(
                'Ж [DISSENT] agent="{agent}" reason="{reason}" severity="{severity}"'.format(
                    agent=_escape_hlf_string(str(item.get("agent") or "local-witness")),
                    reason=_escape_hlf_string(str(item.get("reason") or "unspecified")),
                    severity=_escape_hlf_string(str(item.get("severity") or "warning")),
                )
            )
    if not any(_tag_from_line(line) == "PROGRESS" for line in lines):
        for event in progress[:10]:
            lines.append(
                '∇ [PROGRESS] event_id="{event_id}" phase="{phase}" status="{status}"'.format(
                    event_id=_escape_hlf_string(str(event.get("event_id") or "")),
                    phase=_escape_hlf_string(str(event.get("phase") or event.get("kind") or "")),
                    status=_escape_hlf_string(str(event.get("status") or "observed")),
                )
            )
    lines.append("Ω")
    return "\n".join(lines) + "\n"


def _extract_delegations(statements: list[Any], *, swarm_id: str) -> list[dict[str, Any]]:
    delegations: list[dict[str, Any]] = []
    for index, stmt in enumerate(statements):
        if not isinstance(stmt, dict) or stmt.get("tag") not in {"DELEGATE", "ROUTE"}:
            continue
        args = _args_to_dict(stmt.get("arguments", []))
        agent = str(args.get("agent") or args.get("to") or args.get("role") or "local-agent")
        goal = str(args.get("goal") or args.get("task") or args.get("strategy") or "coordinate")
        task_seed = f"{swarm_id}:{index}:{agent}:{goal}"
        delegations.append(
            {
                "delegation_id": hashlib.sha256(task_seed.encode("utf-8")).hexdigest()[:16],
                "task_id": str(args.get("task_id") or hashlib.sha256(task_seed.encode()).hexdigest()[:12]),
                "agent": agent,
                "goal": goal,
                "role": str(args.get("role") or ""),
                "source_tag": str(stmt.get("tag") or ""),
                "statement_index": index,
                "handoff_required": True,
                "wire_format": "raw_hlf_source",
            }
        )
    if not delegations:
        task_seed = f"{swarm_id}:local:coordinator"
        delegations.append(
            {
                "delegation_id": hashlib.sha256(task_seed.encode("utf-8")).hexdigest()[:16],
                "task_id": hashlib.sha256(task_seed.encode("utf-8")).hexdigest()[:12],
                "agent": "local-coordinator",
                "goal": "coordinate bounded local swarm mechanics",
                "role": "coordinator",
                "source_tag": "DERIVED",
                "statement_index": -1,
                "handoff_required": True,
                "wire_format": "raw_hlf_source",
            }
        )
    return delegations


def _extract_votes(statements: list[Any], *, quorum: str) -> list[dict[str, Any]]:
    votes: list[dict[str, Any]] = []
    for index, stmt in enumerate(statements):
        if not isinstance(stmt, dict) or stmt.get("tag") not in {"VOTE", "CONSENSUS"}:
            continue
        args = _args_to_dict(stmt.get("arguments", []))
        votes.append(_normalize_vote(args, index=index, quorum=quorum))
    return votes


def _extract_dissent(statements: list[Any]) -> list[dict[str, Any]]:
    dissent: list[dict[str, Any]] = []
    for index, stmt in enumerate(statements):
        if not isinstance(stmt, dict):
            continue
        args = _args_to_dict(stmt.get("arguments", []))
        tag = str(stmt.get("tag") or "")
        dissent_state = str(args.get("dissent_state") or args.get("dissent") or "none")
        if tag not in {"DISSENT", "VETO"} and dissent_state in {"", "none", "false"}:
            continue
        dissent.append(_normalize_dissent(args | {"source_tag": tag}, index=index))
    return dissent


def _extract_progress(statements: list[Any]) -> list[dict[str, Any]]:
    progress: list[dict[str, Any]] = []
    for index, stmt in enumerate(statements):
        if not isinstance(stmt, dict) or stmt.get("tag") not in {"PROGRESS", "EVENT"}:
            continue
        progress.append(_normalize_progress(_args_to_dict(stmt.get("arguments", [])), index=index))
    return progress


def _normalize_vote(item: dict[str, Any], *, index: int, quorum: str) -> dict[str, Any]:
    decision = str(item.get("decision") or item.get("vote") or item.get("choice") or "approve").lower()
    if decision in {"yes", "pass", "passed", "allow", "allowed"}:
        decision = "approve"
    if decision in {"no", "fail", "failed", "deny", "denied", "reject"}:
        decision = "reject"
    return {
        "vote_id": str(item.get("vote_id") or f"vote-{index + 1:03d}"),
        "voter": str(item.get("voter") or item.get("agent") or "local-voter"),
        "decision": decision,
        "weight": float(item.get("weight") or 1.0),
        "quorum": str(item.get("quorum") or quorum),
        "reason": str(item.get("reason") or ""),
    }


def _normalize_dissent(item: dict[str, Any], *, index: int) -> dict[str, Any]:
    return {
        "dissent_id": str(item.get("dissent_id") or f"dissent-{index + 1:03d}"),
        "agent": str(item.get("agent") or item.get("voter") or "local-witness"),
        "reason": str(item.get("reason") or item.get("dissent_state") or "unspecified"),
        "severity": str(item.get("severity") or "warning"),
        "source_tag": str(item.get("source_tag") or "DISSENT"),
    }


def _normalize_progress(item: dict[str, Any], *, index: int) -> dict[str, Any]:
    return {
        "event_id": str(item.get("event_id") or f"progress-{index + 1:03d}"),
        "kind": str(item.get("kind") or "progress"),
        "phase": str(item.get("phase") or item.get("status") or "observed"),
        "status": str(item.get("status") or "observed"),
        "agent": str(item.get("agent") or ""),
        "message": str(item.get("message") or ""),
        "timestamp_ns": int(item.get("timestamp_ns") or time.time_ns()),
    }


def _dissent_from_votes(votes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index, vote in enumerate(votes):
        if str(vote.get("decision")) not in {"reject", "veto", "block"}:
            continue
        records.append(
            {
                "dissent_id": f"vote-dissent-{index + 1:03d}",
                "agent": str(vote.get("voter") or "local-voter"),
                "reason": str(vote.get("reason") or f"vote decision {vote.get('decision')}"),
                "severity": "critical" if vote.get("decision") in {"veto", "block"} else "warning",
                "source_tag": "VOTE",
            }
        )
    return records


def _generated_progress_events(
    *,
    swarm_id: str,
    delegations: list[dict[str, Any]],
    votes: list[dict[str, Any]],
    dissent: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    now = time.time_ns()
    events = [
        {
            "event_id": f"{swarm_id}-start",
            "kind": "progress",
            "phase": "start",
            "status": "started",
            "agent": "local-coordinator",
            "message": "Local bounded swarm artifact assembly started.",
            "timestamp_ns": now,
        }
    ]
    for delegation in delegations:
        events.append(
            {
                "event_id": f"{delegation['delegation_id']}-delegated",
                "kind": "delegation",
                "phase": "delegate",
                "status": "recorded",
                "agent": str(delegation.get("agent") or ""),
                "message": str(delegation.get("goal") or ""),
                "timestamp_ns": now + len(events),
            }
        )
    if votes:
        events.append(
            {
                "event_id": f"{swarm_id}-vote",
                "kind": "vote",
                "phase": "consensus",
                "status": "recorded",
                "agent": "local-coordinator",
                "message": f"Recorded {len(votes)} vote(s).",
                "timestamp_ns": now + len(events),
            }
        )
    if dissent:
        events.append(
            {
                "event_id": f"{swarm_id}-dissent",
                "kind": "dissent",
                "phase": "review",
                "status": "requires_review",
                "agent": "local-coordinator",
                "message": f"Recorded {len(dissent)} dissent artifact(s).",
                "timestamp_ns": now + len(events),
            }
        )
    events.append(
        {
            "event_id": f"{swarm_id}-complete",
            "kind": "progress",
            "phase": "complete",
            "status": "completed",
            "agent": "local-coordinator",
            "message": "Local bounded swarm artifact assembly completed.",
            "timestamp_ns": now + len(events),
        }
    )
    return events


def _build_consensus(
    votes: list[dict[str, Any]],
    dissent: list[dict[str, Any]],
    *,
    quorum: str,
) -> dict[str, Any]:
    approvals = [vote for vote in votes if vote.get("decision") == "approve"]
    rejections = [vote for vote in votes if vote.get("decision") in {"reject", "veto", "block"}]
    total_weight = round(sum(float(vote.get("weight") or 0.0) for vote in votes), 3)
    approval_weight = round(sum(float(vote.get("weight") or 0.0) for vote in approvals), 3)
    if quorum == "strict":
        reached = bool(votes) and not rejections and not dissent
    elif quorum == "majority":
        reached = bool(votes) and approval_weight > (total_weight / 2) and not dissent
    else:
        reached = bool(approvals) and not any(item.get("severity") == "critical" for item in dissent)
    return {
        "quorum": quorum,
        "vote_count": len(votes),
        "approval_count": len(approvals),
        "rejection_count": len(rejections),
        "dissent_count": len(dissent),
        "approval_weight": approval_weight,
        "total_weight": total_weight,
        "reached": reached,
        "state": "accepted" if reached else "review_required",
    }


def _build_lineage(
    *,
    source_sha256: str,
    ast_sha256: str,
    compile_result: dict[str, Any],
    handoff: dict[str, Any] | None,
    delegations: list[dict[str, Any]],
    votes: list[dict[str, Any]],
    dissent: list[dict[str, Any]],
    progress: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "source_sha256": source_sha256,
        "ast_sha256": ast_sha256,
        "compile": {
            "version": compile_result.get("version"),
            "node_count": compile_result.get("node_count", 0),
            "gas_estimate": compile_result.get("gas_estimate", 0),
        },
        "handoff": _summarize_handoff(handoff),
        "artifact_counts": {
            "delegations": len(delegations),
            "votes": len(votes),
            "dissent": len(dissent),
            "progress_events": len(progress),
        },
        "trace": [
            {"kind": "delegation", "id": item.get("delegation_id")}
            for item in delegations
        ]
        + [{"kind": "vote", "id": item.get("vote_id")} for item in votes]
        + [{"kind": "dissent", "id": item.get("dissent_id")} for item in dissent]
        + [{"kind": "progress", "id": item.get("event_id")} for item in progress],
    }


def _summarize_handoff(handoff: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(handoff, dict):
        return {
            "present": False,
            "compatible": True,
            "required_wire_format": "raw_hlf_source",
        }
    return {
        "present": True,
        "compatible": handoff.get("wire_format") == "raw_hlf_source"
        and bool(handoff.get("raw_hlf_source")),
        "artifact_kind": handoff.get("artifact_kind"),
        "handoff_mode": handoff.get("handoff_mode"),
        "wire_format": handoff.get("wire_format"),
        "ast_sha256": handoff.get("ast_sha256"),
    }


def _args_to_dict(arguments: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    if not isinstance(arguments, list):
        return result
    positional_index = 0
    for arg in arguments:
        if not isinstance(arg, dict):
            continue
        value = _value_from_arg(arg)
        name = str(arg.get("name") or "")
        if name:
            result[name] = value
        else:
            result[f"arg{positional_index}"] = value
            positional_index += 1
    return result


def _value_from_arg(arg: dict[str, Any]) -> Any:
    value = arg.get("value")
    if isinstance(value, dict) and "value" in value:
        return value.get("value")
    if value is not None:
        return value
    if "path" in arg:
        return arg.get("path")
    return ""


def _tag_from_line(line: str) -> str:
    start = line.find("[")
    end = line.find("]", start + 1)
    if start == -1 or end == -1:
        return ""
    return line[start + 1 : end].strip().upper()


def _normalize_quorum(quorum: str) -> str:
    normalized = str(quorum or "strict").strip().lower()
    return normalized if normalized in {"strict", "majority", "advisory"} else "strict"


def _dedupe_dicts(items: list[dict[str, Any]], *, key_fields: tuple[str, ...]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for item in items:
        key = json.dumps({field: item.get(field) for field in key_fields}, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _escape_hlf_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
