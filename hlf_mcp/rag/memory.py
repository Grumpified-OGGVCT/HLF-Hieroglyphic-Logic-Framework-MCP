"""
Infinite RAG Memory — SQLite-backed fact store with vector similarity.

Tiers:
  Hot  (in-process dict): active context, sub-ms access
  Warm (SQLite WAL):       persistent embeddings, ~5ms
  Cold (not implemented in this layer): long-term archive

Features:
  - SHA-256 dedup: prevents duplicate storage
  - Vector Race Protection: cosine similarity >0.98 blocks duplicates
  - 30-day decay: low-relevance facts pruned automatically
  - Merkle provenance chain per topic
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import re
import sqlite3
import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from hlf_mcp.hlf.memory_node import build_pointer_ref, parse_pointer_ref, verify_pointer_ref

logger = logging.getLogger(__name__)

# ── Simple vector embedding (bag-of-words TF-IDF approximation) ───────────────
# Used when a proper ML embedding model is unavailable.


def _tokenize(text: str) -> list[str]:
    return [
        token.lower()
        for token in re.findall(r"[\u3400-\u9fff]|[\u0600-\u06ff]+|[A-Za-zÀ-ÖØ-öø-ÿ0-9]+", text)
    ]


def _bow_vector(text: str, vocab: dict[str, int] | None = None) -> dict[str, float]:
    """Build a term-frequency vector from text."""
    tokens = _tokenize(text)
    tf: dict[str, float] = {}
    for t in tokens:
        tf[t] = tf.get(t, 0) + 1
    if tokens:
        max_tf = max(tf.values())
        tf = {k: v / max_tf for k, v in tf.items()}
    return tf


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    """Cosine similarity between two sparse TF vectors."""
    keys = set(a) & set(b)
    if not keys:
        return 0.0
    dot = sum(a[k] * b[k] for k in keys)
    mag_a = math.sqrt(sum(v * v for v in a.values()))
    mag_b = math.sqrt(sum(v * v for v in b.values()))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


# ── Database schema ───────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS fact_store (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    sha256      TEXT    NOT NULL UNIQUE,
    content     TEXT    NOT NULL,
    topic       TEXT    NOT NULL DEFAULT '',
    confidence  REAL    NOT NULL DEFAULT 1.0,
    provenance  TEXT    NOT NULL DEFAULT 'agent',
    tags        TEXT    NOT NULL DEFAULT '[]',
    vector_json TEXT    NOT NULL DEFAULT '{}',
    created_at  REAL    NOT NULL,
    accessed_at REAL    NOT NULL,
    access_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS rolling_context (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    topic       TEXT    NOT NULL,
    summary     TEXT    NOT NULL,
    updated_at  REAL    NOT NULL
);

CREATE TABLE IF NOT EXISTS merkle_chain (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    topic       TEXT    NOT NULL,
    prev_hash   TEXT    NOT NULL DEFAULT '',
    entry_hash  TEXT    NOT NULL,
    created_at  REAL    NOT NULL
);

PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
"""

_DECAY_DAYS = 30
_DEDUP_THRESHOLD = 0.98
_ARCHIVE_SALIENCE_THRESHOLD = 0.45
HKS_DOMAINS = {
    "general-coding",
    "ai-engineering",
    "hlf-specific",
    "devops",
    "security",
    "data-engineering",
    "frontend",
    "backend",
    "infrastructure",
}
HKS_MEMORY_STRATA = {"working", "episodic", "semantic", "provenance", "archive"}
HKS_STORAGE_TIERS = {"hot", "warm", "cold"}
HKS_ARTIFACT_FORMS = {"raw_intake", "canonical_knowledge"}
HKS_SOURCE_AUTHORITY_LABELS = {"advisory", "canonical"}

_SEMANTIC_ENTRY_KINDS = {"hks_exemplar"}
_EPISODIC_ENTRY_KINDS = {
    "governed_recall",
    "internal_workflow",
    "governed_route",
    "execution_admission",
    "witness_observation",
    "dream_finding",
    "dream_cycle",
}
_PROVENANCE_ENTRY_KINDS = {
    "weekly_artifact",
    "benchmark_artifact",
    "media_evidence",
    "translation_contract",
    "symbolic_surface",
}
_GRAPH_NODE_ENTRY_KIND = "hks_graph_node"

_RETRIEVAL_PURPOSE_POLICIES: dict[str, dict[str, Any]] = {
    "default": {
        "require_provenance": False,
        "require_active": False,
        "require_graph_linked": False,
        "min_graph_score": 0.0,
        "min_rank_score": 0.0,
        "allowed_entry_kinds": set(),
    },
    "translation_memory": {
        "require_provenance": True,
        "require_active": True,
        "require_graph_linked": False,
        "min_graph_score": 0.05,
        "min_rank_score": 0.12,
        "allowed_entry_kinds": {"hks_exemplar"},
    },
    "repair_pattern_recall": {
        "require_provenance": True,
        "require_active": True,
        "require_graph_linked": False,
        "min_graph_score": 0.05,
        "min_rank_score": 0.12,
        "allowed_entry_kinds": {"hks_exemplar"},
    },
    "routing_evidence": {
        "require_provenance": True,
        "require_active": True,
        "require_graph_linked": True,
        "min_graph_score": 0.1,
        "min_rank_score": 0.35,
        "allowed_entry_kinds": {"hks_exemplar", "weekly_artifact"},
    },
    "verifier_evidence": {
        "require_provenance": True,
        "require_active": True,
        "require_graph_linked": True,
        "min_graph_score": 0.1,
        "min_rank_score": 0.3,
        "allowed_entry_kinds": {"hks_exemplar", "weekly_artifact", "benchmark_artifact"},
    },
    "execution_admission": {
        "require_provenance": True,
        "require_active": True,
        "require_graph_linked": True,
        "min_graph_score": 0.1,
        "min_rank_score": 0.3,
        "allowed_entry_kinds": {
            "hks_exemplar",
            "weekly_artifact",
            "benchmark_artifact",
            "translation_contract",
        },
    },
}

_POINTER_PURPOSE_POLICIES: dict[str, dict[str, bool]] = {
    "execution": {"require_provenance": False, "allow_stale": False, "allow_superseded": False},
    "memory_read": {"require_provenance": False, "allow_stale": False, "allow_superseded": False},
    "routing_evidence": {
        "require_provenance": True,
        "allow_stale": False,
        "allow_superseded": False,
    },
    "verifier_evidence": {
        "require_provenance": True,
        "allow_stale": False,
        "allow_superseded": False,
    },
    "operator_review": {"require_provenance": False, "allow_stale": True, "allow_superseded": True},
}


def _timestamp_to_iso8601(value: float | int | None) -> str | None:
    if value is None:
        return None
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(float(value)))


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False


def _coerce_float(value: Any, default: float) -> float:
    try:
        if value in (None, ""):
            raise ValueError
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _parse_fresh_until(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            return None
        try:
            if normalized.endswith("Z"):
                normalized = normalized[:-1] + "+00:00"
            return time.mktime(time.strptime(normalized[:19], "%Y-%m-%dT%H:%M:%S"))
        except ValueError:
            try:
                return float(normalized)
            except ValueError:
                return None
    return None


def _normalize_memory_stratum(
    value: Any,
    *,
    entry_kind: str,
    topic: str,
    metadata: dict[str, Any],
) -> str:
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in HKS_MEMORY_STRATA:
            return normalized

    governed_evidence = (
        metadata.get("governed_evidence") if isinstance(metadata.get("governed_evidence"), dict) else {}
    )
    for candidate in (
        metadata.get("memory_stratum"),
        metadata.get("memory_layer"),
        governed_evidence.get("memory_stratum"),
        governed_evidence.get("memory_layer"),
    ):
        if isinstance(candidate, str):
            normalized = candidate.strip().lower()
            if normalized in HKS_MEMORY_STRATA:
                return normalized

    normalized_entry_kind = str(entry_kind or "fact").strip().lower()
    normalized_topic = str(topic or "").strip().lower()

    if normalized_entry_kind == _GRAPH_NODE_ENTRY_KIND:
        return "semantic"
    if normalized_entry_kind in _SEMANTIC_ENTRY_KINDS or normalized_topic.startswith("hlf_validated_exemplars"):
        return "semantic"
    if "translation_contract" in normalized_topic:
        return "semantic"
    if normalized_entry_kind in _EPISODIC_ENTRY_KINDS:
        return "episodic"
    if any(token in normalized_topic for token in ("governed_recall", "workflow", "route", "admission", "dream", "witness")):
        return "episodic"
    if normalized_entry_kind in _PROVENANCE_ENTRY_KINDS:
        return "provenance"
    if any(
        [
            governed_evidence.get("source_path"),
            governed_evidence.get("artifact_id"),
            governed_evidence.get("workflow_run_url"),
            governed_evidence.get("commit_sha"),
        ]
    ):
        return "provenance"
    return "working"


def _normalize_storage_tier(value: Any, *, memory_stratum: str) -> str:
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in HKS_STORAGE_TIERS:
            return normalized

    if memory_stratum == "archive":
        return "cold"
    if memory_stratum == "working":
        return "hot"
    return "warm"


def _has_explicit_memory_contract(metadata: dict[str, Any], governed_evidence: dict[str, Any]) -> bool:
    candidates = (
        metadata.get("memory_stratum"),
        metadata.get("memory_layer"),
        metadata.get("storage_tier"),
        metadata.get("artifact_form"),
        metadata.get("source_authority_label"),
        governed_evidence.get("memory_stratum"),
        governed_evidence.get("memory_layer"),
        governed_evidence.get("storage_tier"),
        governed_evidence.get("artifact_form"),
        governed_evidence.get("source_authority_label"),
    )
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip().lower() in (
            HKS_MEMORY_STRATA | HKS_STORAGE_TIERS | HKS_ARTIFACT_FORMS | HKS_SOURCE_AUTHORITY_LABELS
        ):
            return True
    return False


def _score_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return round(max(0.0, min(float(value), 1.0)), 4)
    except (TypeError, ValueError):
        return None


def _build_source_capture_view(
    metadata: dict[str, Any],
    *,
    governed_evidence: dict[str, Any],
    evaluation: dict[str, Any],
    entry_kind: str,
) -> dict[str, Any]:
    source_capture = metadata.get("source_capture") if isinstance(metadata.get("source_capture"), dict) else {}
    source_type_classification = str(
        source_capture.get("source_type_classification")
        or governed_evidence.get("source_type_classification")
        or governed_evidence.get("source_type")
        or entry_kind
    ).strip() or entry_kind
    source_authority_label = str(
        source_capture.get("source_authority_label")
        or metadata.get("source_authority_label")
        or governed_evidence.get("source_authority_label")
        or (
            "canonical"
            if bool(evaluation.get("promotion_eligible", False)) and evaluation.get("authority") == "local_hks"
            else "advisory"
        )
    ).strip().lower() or "advisory"
    if source_authority_label not in HKS_SOURCE_AUTHORITY_LABELS:
        source_authority_label = "advisory"

    source_version = str(
        source_capture.get("source_version")
        or metadata.get("source_version")
        or governed_evidence.get("source_version")
        or governed_evidence.get("commit_sha")
        or ""
    )
    freshness_marker = str(
        source_capture.get("freshness_marker")
        or metadata.get("fresh_until")
        or governed_evidence.get("fresh_until")
        or evaluation.get("freshness_verdict")
        or ""
    )

    return {
        "extraction_fidelity_score": _score_or_none(
            source_capture.get("extraction_fidelity_score")
            or metadata.get("extraction_fidelity_score")
            or governed_evidence.get("extraction_fidelity_score")
        ),
        "code_block_recall_score": _score_or_none(
            source_capture.get("code_block_recall_score")
            or metadata.get("code_block_recall_score")
            or governed_evidence.get("code_block_recall_score")
        ),
        "structure_fidelity_score": _score_or_none(
            source_capture.get("structure_fidelity_score")
            or metadata.get("structure_fidelity_score")
            or governed_evidence.get("structure_fidelity_score")
        ),
        "citation_recoverability_score": _score_or_none(
            source_capture.get("citation_recoverability_score")
            or metadata.get("citation_recoverability_score")
            or governed_evidence.get("citation_recoverability_score")
        ),
        "source_type_classification": source_type_classification,
        "source_authority_label": source_authority_label,
        "source_version": source_version,
        "freshness_marker": freshness_marker,
    }


def _build_artifact_contract_view(
    metadata: dict[str, Any],
    *,
    governed_evidence: dict[str, Any],
    evaluation: dict[str, Any],
    entry_kind: str,
    topic: str,
) -> dict[str, Any]:
    artifact_contract = (
        metadata.get("artifact_contract") if isinstance(metadata.get("artifact_contract"), dict) else {}
    )
    artifact_kind = str(
        artifact_contract.get("artifact_kind")
        or metadata.get("artifact_kind")
        or governed_evidence.get("artifact_kind")
        or entry_kind
    ).strip() or entry_kind

    requested_form = str(
        artifact_contract.get("artifact_form")
        or metadata.get("artifact_form")
        or governed_evidence.get("artifact_form")
        or ""
    ).strip().lower()
    if requested_form in HKS_ARTIFACT_FORMS:
        artifact_form = requested_form
    elif entry_kind == "hks_exemplar" or (
        evaluation.get("authority") == "local_hks"
        and bool(evaluation.get("promotion_eligible", False))
    ):
        artifact_form = "canonical_knowledge"
    elif str(topic or "").strip().lower().startswith("hlf_validated_exemplars"):
        artifact_form = "canonical_knowledge"
    else:
        artifact_form = "raw_intake"

    canonicalized = artifact_contract.get("canonicalized")
    if canonicalized is None:
        canonicalized = artifact_form == "canonical_knowledge"

    return {
        "artifact_form": artifact_form,
        "artifact_kind": artifact_kind,
        "canonicalized": bool(canonicalized),
    }


def _compute_salience_score(
    *,
    confidence: float,
    groundedness: float,
    citation_coverage: float,
    freshness_verdict: str,
    provenance_backed: bool,
    entry_kind: str,
    promotion_eligible: bool,
    revoked: bool,
    tombstoned: bool,
) -> float:
    if revoked or tombstoned:
        return 0.0

    freshness_score = 1.0 if freshness_verdict == "fresh" else 0.0
    provenance_score = 1.0 if provenance_backed else 0.25
    semantic_bonus = 0.1 if entry_kind == "hks_exemplar" else 0.0
    promotion_bonus = 0.1 if promotion_eligible else 0.0

    score = (
        float(confidence) * 0.25
        + float(groundedness) * 0.25
        + float(citation_coverage) * 0.2
        + freshness_score * 0.15
        + provenance_score * 0.15
        + semantic_bonus
        + promotion_bonus
    )
    return round(max(0.0, min(score, 1.0)), 4)


def _build_evaluation_view(
    metadata: dict[str, Any],
    *,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    evaluation = metadata.get("evaluation") if isinstance(metadata.get("evaluation"), dict) else {}
    if not evaluation:
        return {}

    materialized = dict(evaluation)
    authority = str(materialized.get("authority") or "local_hks").strip() or "local_hks"
    materialized["authority"] = authority

    if evidence is not None:
        materialized["freshness_verdict"] = str(
            evidence.get("freshness_status") or materialized.get("freshness_verdict") or "fresh"
        )
        materialized["provenance_verdict"] = str(
            evidence.get("provenance_grade") or materialized.get("provenance_verdict") or "basic"
        )

        if authority != "local_hks":
            materialized["promotion_eligible"] = False
            materialized["promotion_blocked"] = True
            materialized["requires_local_recheck"] = True
            materialized["lane"] = str(materialized.get("lane") or "bridge")
        else:
            promotion_allowed = bool(materialized.get("promotion_eligible"))
            promotion_allowed = (
                promotion_allowed
                and materialized["freshness_verdict"] != "stale"
                and materialized["provenance_verdict"] == "evidence-backed"
                and not bool(evidence.get("revoked"))
                and not bool(evidence.get("tombstoned"))
            )
            materialized["promotion_eligible"] = promotion_allowed
            materialized["promotion_blocked"] = not promotion_allowed
            materialized["requires_local_recheck"] = False
            materialized["lane"] = str(materialized.get("lane") or "current_truth")

    return materialized


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _collect_string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        normalized = value.strip()
        return [normalized] if normalized else []
    if not isinstance(value, list):
        return []
    collected: list[str] = []
    for item in value:
        normalized = str(item or "").strip()
        if normalized:
            collected.append(normalized)
    return _dedupe_preserve_order(collected)


def _infer_asset_graph_elements(
    *,
    topic: str,
    entry_kind: str,
    metadata: dict[str, Any],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    entities: list[dict[str, str]] = []
    links: list[dict[str, str]] = []
    details = metadata.get("details") if isinstance(metadata.get("details"), dict) else {}
    result_payload = metadata.get("result") if isinstance(metadata.get("result"), dict) else {}
    benchmark_scores = (
        metadata.get("benchmark_scores") if isinstance(metadata.get("benchmark_scores"), dict) else {}
    )
    artifact_contract = (
        metadata.get("artifact_contract") if isinstance(metadata.get("artifact_contract"), dict) else {}
    )

    def add_entity(kind: str, value: Any) -> None:
        normalized = str(value or "").strip()
        if not normalized:
            return
        entities.append({"kind": kind, "value": normalized})

    def add_link(source: str, relation: str, target: str) -> None:
        normalized_source = str(source or "").strip()
        normalized_target = str(target or "").strip()
        normalized_relation = str(relation or "related_to").strip() or "related_to"
        if not normalized_source or not normalized_target:
            return
        links.append(
            {
                "source": normalized_source,
                "relation": normalized_relation,
                "target": normalized_target,
            }
        )

    for prompt_name in _collect_string_list(
        details.get("prompt_name")
        or details.get("prompt_asset")
        or result_payload.get("prompt_name")
        or result_payload.get("prompt_asset")
    ):
        add_entity("prompt_asset", prompt_name)
        add_link(f"topic:{topic}", "materializes_prompt", f"prompt_asset:{prompt_name}")

    for code_pattern in _collect_string_list(
        details.get("code_pattern")
        or details.get("code_patterns")
        or result_payload.get("code_pattern")
        or result_payload.get("code_patterns")
    ):
        add_entity("code_pattern", code_pattern)
        add_link(f"topic:{topic}", "materializes_code_pattern", f"code_pattern:{code_pattern}")

    for upgrade in _collect_string_list(
        details.get("upgrade_candidate")
        or details.get("upgrade_candidates")
        or details.get("recommended_upgrade")
        or result_payload.get("upgrade_candidate")
        or result_payload.get("recommended_upgrade")
    ):
        add_entity("upgrade_opportunity", upgrade)
        add_link(f"topic:{topic}", "materializes_upgrade", f"upgrade_opportunity:{upgrade}")

    for metric in sorted(str(name) for name in benchmark_scores.keys() if str(name))[:8]:
        add_entity("benchmark_metric", metric)
        add_link(f"topic:{topic}", "measured_by", f"benchmark_metric:{metric}")

    return entities, links


def _build_graph_context(
    *,
    topic: str,
    domain: str,
    solution_kind: str,
    tags: list[str],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    explicit = metadata.get("graph_context") if isinstance(metadata.get("graph_context"), dict) else {}
    entities: list[dict[str, str]] = []
    links: list[dict[str, str]] = []
    seen_entities: set[tuple[str, str]] = set()
    seen_links: set[tuple[str, str, str]] = set()

    def add_entity(kind: str, value: Any) -> None:
        normalized = str(value or "").strip()
        if not normalized:
            return
        key = (kind, normalized)
        if key in seen_entities:
            return
        seen_entities.add(key)
        entities.append({"kind": kind, "value": normalized, "node_id": f"{kind}:{normalized}"})

    def add_link(source_kind: str, source_value: Any, relation: str, target_kind: str, target_value: Any) -> None:
        source = str(source_value or "").strip()
        target = str(target_value or "").strip()
        if not source or not target:
            return
        key = (f"{source_kind}:{source}", relation, f"{target_kind}:{target}")
        if key in seen_links:
            return
        seen_links.add(key)
        links.append({"source": key[0], "relation": relation, "target": key[2]})

    add_entity("topic", topic)
    add_entity("domain", domain)
    add_entity("solution_kind", solution_kind)
    for tag in tags[:8]:
        add_entity("tag", tag)

    for item in explicit.get("entities") or []:
        if not isinstance(item, dict):
            continue
        add_entity(str(item.get("kind") or "entity"), item.get("value"))

    add_link("topic", topic, "scoped_to", "domain", domain)
    add_link("topic", topic, "uses_solution_kind", "solution_kind", solution_kind)
    for tag in tags[:8]:
        add_link("topic", topic, "tagged_with", "tag", tag)

    inferred_entities, inferred_links = _infer_asset_graph_elements(
        topic=topic,
        entry_kind=str(metadata.get("entry_kind") or metadata.get("governed_evidence", {}).get("source_class") or ""),
        metadata=metadata,
    )
    for item in inferred_entities:
        if isinstance(item, dict):
            add_entity(str(item.get("kind") or "entity"), item.get("value"))
    for item in inferred_links:
        if not isinstance(item, dict):
            continue
        source = str(item.get("source") or "").strip()
        relation = str(item.get("relation") or "related_to").strip() or "related_to"
        target = str(item.get("target") or "").strip()
        if not source or not target:
            continue
        key = (source, relation, target)
        if key in seen_links:
            continue
        seen_links.add(key)
        links.append({"source": source, "relation": relation, "target": target})

    for item in explicit.get("links") or []:
        if not isinstance(item, dict):
            continue
        source = str(item.get("source") or "").strip()
        relation = str(item.get("relation") or "related_to").strip()
        target = str(item.get("target") or "").strip()
        if not source or not target:
            continue
        key = (source, relation, target)
        if key in seen_links:
            continue
        seen_links.add(key)
        links.append({"source": source, "relation": relation, "target": target})

    return {
        "graph_linked": bool(links),
        "entity_count": len(entities),
        "link_count": len(links),
        "entities": entities,
        "links": links,
    }


def _build_result_retrieval_contract(
    *,
    query_text: str,
    content: str,
    topic: str,
    domain: str,
    solution_kind: str,
    tags: list[str],
    similarity: float,
    metadata_filters: dict[str, str],
    graph_context: dict[str, Any],
    graph_score: float,
    graph_traversal: dict[str, Any],
    lexical_score: float,
    rank_score: float,
    purpose: str,
    purpose_policy: dict[str, Any],
    admitted_for_purpose: bool,
    rejection_reasons: list[str],
) -> dict[str, Any]:
    query_terms = set(_tokenize(query_text))
    searchable_terms = set(
        _tokenize(
            " ".join(
                part
                for part in [content, topic, domain, solution_kind, " ".join(tags)]
                if part
            )
        )
    )
    lexical_overlap_terms = _dedupe_preserve_order(
        [term for term in _tokenize(query_text) if term in searchable_terms]
    )[:8]
    applied_paths = ["semantic"]
    if lexical_overlap_terms:
        applied_paths.append("lexical")
    if metadata_filters:
        applied_paths.append("metadata-filtered")
    if bool(graph_context.get("graph_linked")):
        applied_paths.append("graph-linked")

    path_scores = {
        "semantic": round(similarity, 4),
        "lexical": round(lexical_score, 4),
        "graph-linked": round(graph_score, 4),
    }
    primary_path = max(path_scores, key=path_scores.get)
    graph_traversal_summary = {
        "matched_entity_count": len(graph_traversal.get("matched_entities") or []),
        "traversed_link_count": len(graph_traversal.get("traversed_links") or []),
        "reachable_node_count": int(graph_traversal.get("reachable_node_count") or 0),
    }
    path_status = {
        "semantic": {
            "status": "active",
            "mode": "sparse-vector",
            "score": round(similarity, 4),
        },
        "dense-semantic": {
            "status": "unavailable",
            "mode": "not-configured",
            "reason": "local runtime uses a sparse embedding proxy instead of a dense semantic index",
        },
        "lexical": {
            "status": "active" if lexical_overlap_terms else "inactive",
            "score": round(lexical_score, 4),
            "overlap_terms": lexical_overlap_terms,
        },
        "metadata-filtered": {
            "status": "active" if metadata_filters else "inactive",
            "filter_dimensions": sorted(metadata_filters.keys()),
        },
        "graph-linked": {
            "status": "active" if bool(graph_context.get("graph_linked")) else "inactive",
            "score": round(graph_score, 4),
            "source": str(graph_context.get("graph_source") or "metadata-derived"),
            "link_count": int(graph_context.get("link_count") or 0),
            "attached_node_count": len(graph_context.get("attached_node_ids") or []),
            "matched_entity_count": graph_traversal_summary["matched_entity_count"],
            "traversed_link_count": graph_traversal_summary["traversed_link_count"],
            "reachable_node_count": graph_traversal_summary["reachable_node_count"],
        },
    }

    return {
        "contract_version": "hks-retrieval-v1",
        "primary_path": primary_path,
        "semantic_mode": "sparse-vector+graph-boosted-ranking",
        "applied_paths": applied_paths,
        "metadata_filters": metadata_filters,
        "lexical_overlap_terms": lexical_overlap_terms,
        "query_term_count": len(query_terms),
        "graph_link_count": int(graph_context.get("link_count") or 0),
        "graph_linked": bool(graph_context.get("graph_linked")),
        "graph_source": str(graph_context.get("graph_source") or "metadata-derived"),
        "similarity": round(similarity, 4),
        "lexical_score": round(lexical_score, 4),
        "graph_score": round(graph_score, 4),
        "rank_score": round(rank_score, 4),
        "graph_traversal": graph_traversal,
        "graph_traversal_summary": graph_traversal_summary,
        "path_status": path_status,
        "purpose": purpose,
        "purpose_policy": purpose_policy,
        "admitted_for_purpose": admitted_for_purpose,
        "rejection_reasons": rejection_reasons,
    }


def _build_query_retrieval_contract(
    *,
    results: list[dict[str, Any]],
    metadata_filters: dict[str, str],
    purpose: str,
    purpose_policy: dict[str, Any],
    rejected_count: int,
    invocation_gate: dict[str, Any],
) -> dict[str, Any]:
    path_counts: dict[str, int] = {}
    graph_linked_result_count = 0
    admitted_count = 0
    matched_entity_total = 0
    traversed_link_total = 0
    reachable_node_max = 0
    for item in results:
        if not isinstance(item, dict):
            continue
        retrieval = item.get("retrieval_contract") if isinstance(item.get("retrieval_contract"), dict) else {}
        for path in retrieval.get("applied_paths") or []:
            normalized = str(path or "").strip()
            if not normalized:
                continue
            path_counts[normalized] = path_counts.get(normalized, 0) + 1
        if bool(retrieval.get("graph_linked")):
            graph_linked_result_count += 1
        if bool(retrieval.get("admitted_for_purpose")):
            admitted_count += 1
        graph_summary = (
            retrieval.get("graph_traversal_summary")
            if isinstance(retrieval.get("graph_traversal_summary"), dict)
            else {}
        )
        matched_entity_total += int(graph_summary.get("matched_entity_count") or 0)
        traversed_link_total += int(graph_summary.get("traversed_link_count") or 0)
        reachable_node_max = max(reachable_node_max, int(graph_summary.get("reachable_node_count") or 0))

    path_status = {
        "semantic": {
            "status": "active" if path_counts.get("semantic") else "available",
            "mode": "sparse-vector",
            "result_count": path_counts.get("semantic", 0),
        },
        "dense-semantic": {
            "status": "unavailable",
            "mode": "not-configured",
            "reason": "local runtime uses a sparse embedding proxy instead of a dense semantic index",
        },
        "lexical": {
            "status": "active" if path_counts.get("lexical") else "available",
            "result_count": path_counts.get("lexical", 0),
        },
        "metadata-filtered": {
            "status": "active" if metadata_filters else "inactive",
            "result_count": path_counts.get("metadata-filtered", 0),
            "filter_dimensions": sorted(metadata_filters.keys()),
        },
        "graph-linked": {
            "status": "active" if graph_linked_result_count else "available",
            "result_count": path_counts.get("graph-linked", 0),
            "source": next(
                (
                    str(((item.get("retrieval_contract") or {}).get("path_status") or {}).get("graph-linked", {}).get("source") or "")
                    for item in results
                    if isinstance(item, dict)
                    and isinstance(item.get("retrieval_contract"), dict)
                    and isinstance(((item.get("retrieval_contract") or {}).get("path_status") or {}).get("graph-linked"), dict)
                    and str((((item.get("retrieval_contract") or {}).get("path_status") or {}).get("graph-linked", {})).get("source") or "")
                ),
                "metadata-derived",
            ),
            "matched_entity_total": matched_entity_total,
            "traversed_link_total": traversed_link_total,
            "reachable_node_max": reachable_node_max,
        },
    }

    return {
        "contract_version": "hks-retrieval-v1",
        "query_mode": "hybrid-governed-recall",
        "semantic_mode": "sparse-vector+graph-boosted-ranking",
        "metadata_filters": metadata_filters,
        "purpose": purpose,
        "purpose_policy": purpose_policy,
        "invocation_gate": invocation_gate,
        "active_paths": sorted(path_counts.keys()),
        "path_counts": dict(sorted(path_counts.items())),
        "path_status": path_status,
        "graph_linked_result_count": graph_linked_result_count,
        "graph_traversal_totals": {
            "matched_entity_total": matched_entity_total,
            "traversed_link_total": traversed_link_total,
            "reachable_node_max": reachable_node_max,
        },
        "admitted_result_count": admitted_count,
        "rejected_result_count": rejected_count,
    }


def _build_governed_hks_contract(
    *,
    query_text: str,
    results: list[dict[str, Any]],
    purpose: str,
    purpose_policy: dict[str, Any],
    retrieval_contract: dict[str, Any],
) -> dict[str, Any]:
    evidence_refs: list[dict[str, Any]] = []
    for item in results[:5]:
        if not isinstance(item, dict):
            continue
        evidence = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
        retrieval = (
            item.get("retrieval_contract") if isinstance(item.get("retrieval_contract"), dict) else {}
        )
        graph_context = item.get("graph_context") if isinstance(item.get("graph_context"), dict) else {}
        pointer = build_pointer_ref(
            f"{item.get('topic') or 'general'}-{item.get('id') or 'entry'}",
            str(item.get("sha256") or ""),
        )
        evidence_refs.append(
            {
                "fact_id": item.get("id"),
                "pointer": pointer,
                "sha256": item.get("sha256"),
                "entry_kind": item.get("entry_kind"),
                "topic": item.get("topic"),
                "domain": item.get("domain"),
                "solution_kind": item.get("solution_kind"),
                "rank_score": retrieval.get("rank_score"),
                "graph_score": retrieval.get("graph_score"),
                "primary_path": retrieval.get("primary_path"),
                "graph_source": retrieval.get("graph_source") or graph_context.get("graph_source"),
                "graph_node_ids": list(graph_context.get("attached_node_ids") or []),
                "trust_tier": evidence.get("trust_tier"),
                "freshness_status": evidence.get("freshness_status"),
                "provenance_grade": evidence.get("provenance_grade"),
                "source_authority_label": evidence.get("source_authority_label"),
                "promotion_eligible": evidence.get("promotion_eligible"),
            }
        )

    graph_status = (
        retrieval_contract.get("path_status", {}).get("graph-linked")
        if isinstance(retrieval_contract.get("path_status"), dict)
        else {}
    )
    reference_allowed = bool(evidence_refs)
    primary_evidence = evidence_refs[0] if evidence_refs else None
    allowed_entry_kinds = sorted(purpose_policy.get("allowed_entry_kinds") or [])
    return {
        "contract_version": "governed-hks-evidence-v1",
        "purpose": purpose,
        "query": query_text,
        "admitted": reference_allowed,
        "reference_allowed": reference_allowed,
        "evidence_count": len(evidence_refs),
        "policy_requirements": {
            "require_provenance": bool(purpose_policy.get("require_provenance", False)),
            "require_active": bool(purpose_policy.get("require_active", False)),
            "require_graph_linked": bool(purpose_policy.get("require_graph_linked", False)),
            "min_graph_score": float(purpose_policy.get("min_graph_score") or 0.0),
            "min_rank_score": float(purpose_policy.get("min_rank_score") or 0.0),
            "allowed_entry_kinds": allowed_entry_kinds,
        },
        "graph_posture": {
            "source": str(graph_status.get("source") or "metadata-derived"),
            "matched_entity_total": int((retrieval_contract.get("graph_traversal_totals") or {}).get("matched_entity_total") or 0),
            "traversed_link_total": int((retrieval_contract.get("graph_traversal_totals") or {}).get("traversed_link_total") or 0),
            "reachable_node_max": int((retrieval_contract.get("graph_traversal_totals") or {}).get("reachable_node_max") or 0),
            "result_count": int(graph_status.get("result_count") or 0),
        },
        "primary_evidence": primary_evidence,
        "evidence_refs": evidence_refs,
        "operator_summary": (
            f"Governed HKS contract {'admitted' if reference_allowed else 'withheld'} {len(evidence_refs)} evidence reference(s) "
            f"for purpose '{purpose}' under graph source '{graph_status.get('source') or 'metadata-derived'}'."
        ),
    }


def _build_query_graph_context(
    *,
    query_text: str,
    metadata_filters: dict[str, str],
) -> dict[str, Any]:
    seed_values = _dedupe_preserve_order(
        [*metadata_filters.values(), *_tokenize(query_text)]
    )
    return {
        "seed_values": seed_values,
        "seed_lookup": {value.casefold() for value in seed_values},
    }


def _score_graph_relevance(
    *,
    query_graph_context: dict[str, Any],
    graph_context: dict[str, Any],
) -> dict[str, Any]:
    seed_lookup = query_graph_context.get("seed_lookup") if isinstance(query_graph_context.get("seed_lookup"), set) else set()
    entities = graph_context.get("entities") if isinstance(graph_context.get("entities"), list) else []
    links = graph_context.get("links") if isinstance(graph_context.get("links"), list) else []
    matched_entities: list[dict[str, str]] = []
    matched_nodes: set[str] = set()
    adjacency: dict[str, list[dict[str, str]]] = {}

    for entity in entities:
        if not isinstance(entity, dict):
            continue
        value = str(entity.get("value") or "").strip()
        node_id = str(entity.get("node_id") or "").strip()
        if not value or not node_id:
            continue
        entity_tokens = {token.casefold() for token in _tokenize(value)} | {value.casefold()}
        if seed_lookup & entity_tokens:
            matched_nodes.add(node_id)
            matched_entities.append({
                "kind": str(entity.get("kind") or "entity"),
                "value": value,
                "node_id": node_id,
            })

    for link in links:
        if not isinstance(link, dict):
            continue
        source = str(link.get("source") or "").strip()
        target = str(link.get("target") or "").strip()
        relation = str(link.get("relation") or "related_to").strip()
        if not source or not target:
            continue
        adjacency.setdefault(source, []).append({"source": source, "target": target, "relation": relation})
        adjacency.setdefault(target, []).append({"source": target, "target": source, "relation": relation})

    visited_nodes = set(matched_nodes)
    traversed_links: list[dict[str, str]] = []
    frontier = list(matched_nodes)
    while frontier:
        node_id = frontier.pop(0)
        for link in adjacency.get(node_id, []):
            traversed_links.append({
                "source": str(link.get("source") or ""),
                "target": str(link.get("target") or ""),
                "relation": str(link.get("relation") or "related_to"),
            })
            target = str(link.get("target") or "").strip()
            if target and target not in visited_nodes:
                visited_nodes.add(target)
                frontier.append(target)

    entity_denominator = max(len([item for item in entities if isinstance(item, dict)]), 1)
    link_denominator = max(len([item for item in links if isinstance(item, dict)]), 1)
    entity_score = len(matched_entities) / entity_denominator
    traversal_score = min(len(traversed_links), link_denominator) / link_denominator
    graph_score = round(min(1.0, entity_score * 0.7 + traversal_score * 0.3), 4)

    return {
        "graph_score": graph_score,
        "matched_entities": matched_entities[:8],
        "traversed_links": traversed_links[:8],
        "reachable_node_count": len(visited_nodes),
        "seed_values": list(query_graph_context.get("seed_values") or []),
    }


def _resolve_query_policy(
    *,
    purpose: str | None,
    require_provenance: bool,
) -> tuple[str, dict[str, Any]]:
    normalized_purpose = str(purpose or "default").strip().lower() or "default"
    base_policy = dict(_RETRIEVAL_PURPOSE_POLICIES.get(normalized_purpose) or _RETRIEVAL_PURPOSE_POLICIES["default"])
    base_policy["require_provenance"] = bool(base_policy.get("require_provenance", False) or require_provenance)
    base_policy["allowed_entry_kinds"] = set(base_policy.get("allowed_entry_kinds") or set())
    return normalized_purpose, base_policy


def _is_invocation_signal_term(term: str) -> bool:
    normalized = str(term or "").strip()
    if not normalized or normalized.isdigit():
        return False
    if len(normalized) >= 3:
        return True
    return bool(re.search(r"[\u3400-\u9fff\u0600-\u06ff]", normalized))


def _build_invocation_gate(
    *,
    query_text: str,
    metadata_filters: dict[str, str],
    purpose: str,
) -> dict[str, Any]:
    raw_terms = _tokenize(query_text)
    signal_terms = [term for term in raw_terms if _is_invocation_signal_term(term)]
    metadata_dimensions = sorted(
        key for key, value in metadata_filters.items() if str(value or "").strip()
    )
    substantive_metadata_dimensions = [
        key for key in metadata_dimensions if key != "topic"
    ]
    signal_score = round(
        min(1.0, len(signal_terms) * 0.22 + len(substantive_metadata_dimensions) * 0.18),
        4,
    )
    high_stakes = purpose in {"routing_evidence", "verifier_evidence", "execution_admission"}
    if signal_terms or substantive_metadata_dimensions:
        decision = "invoke"
        reason = "query_signal_sufficient"
    elif high_stakes:
        decision = "escalate"
        reason = "underspecified_high_stakes_query"
    else:
        decision = "skip"
        reason = "underspecified_low_signal_query"
    return {
        "decision": decision,
        "reason": reason,
        "purpose": purpose,
        "query_signal_score": signal_score,
        "signal_term_count": len(signal_terms),
        "signal_terms": signal_terms[:8],
        "metadata_dimension_count": len(substantive_metadata_dimensions),
        "metadata_dimensions": metadata_dimensions,
        "substantive_metadata_dimensions": substantive_metadata_dimensions,
        "high_stakes": high_stakes,
        "retrieval_invoked": decision == "invoke",
        "review_required": decision == "escalate",
    }


def _apply_query_policy(
    *,
    fact: dict[str, Any],
    purpose: str,
    purpose_policy: dict[str, Any],
) -> tuple[bool, list[str]]:
    if purpose == "default":
        return True, []
    reasons: list[str] = []
    evidence = fact.get("evidence") if isinstance(fact.get("evidence"), dict) else {}
    retrieval = fact.get("retrieval_contract") if isinstance(fact.get("retrieval_contract"), dict) else {}
    if purpose_policy.get("require_provenance") and evidence.get("provenance_grade") != "evidence-backed":
        reasons.append("provenance_required")
    if purpose_policy.get("require_active") and str(evidence.get("state") or fact.get("governance_status") or "") != "active":
        reasons.append("active_state_required")
    if purpose_policy.get("require_graph_linked") and not bool(retrieval.get("graph_linked")):
        reasons.append("graph_link_required")
    if float(retrieval.get("graph_score") or 0.0) < float(purpose_policy.get("min_graph_score") or 0.0):
        reasons.append("graph_score_below_threshold")
    if float(retrieval.get("rank_score") or 0.0) < float(purpose_policy.get("min_rank_score") or 0.0):
        reasons.append("rank_score_below_threshold")
    allowed_entry_kinds = purpose_policy.get("allowed_entry_kinds") if isinstance(purpose_policy.get("allowed_entry_kinds"), set) else set()
    if allowed_entry_kinds and str(fact.get("entry_kind") or "") not in allowed_entry_kinds:
        reasons.append("entry_kind_not_allowed")
    return len(reasons) == 0, reasons


@dataclass(slots=True)
class HKSTestEvidence:
    name: str
    passed: bool
    exit_code: int | None = None
    counts: dict[str, int] | None = None
    details: dict[str, Any] | None = None


@dataclass(slots=True)
class HKSProvenance:
    source_type: str
    source: str
    collector: str
    collected_at: str
    workflow_run_url: str | None = None
    branch: str | None = None
    commit_sha: str | None = None
    artifact_path: str | None = None
    confidence: float | None = None


@dataclass(slots=True)
class HKSValidatedExemplar:
    problem: str
    validated_solution: str
    domain: str
    solution_kind: str
    provenance: HKSProvenance
    tests: list[HKSTestEvidence] = field(default_factory=list)
    supersedes: str | None = None
    topic: str = "hlf_validated_exemplars"
    tags: list[str] = field(default_factory=list)
    summary: str = ""
    confidence: float = 1.0
    evaluation: dict[str, Any] | None = None
    graph_context: dict[str, Any] | None = None
    schema_version: str = "1.0"
    status: str = "validated"

    def __post_init__(self) -> None:
        if self.domain not in HKS_DOMAINS:
            raise ValueError(f"Unsupported HKS domain: {self.domain}")

    def to_content(self) -> str:
        parts = [
            self.problem,
            self.validated_solution,
            self.summary,
            self.domain,
            self.solution_kind,
        ]
        if self.tags:
            parts.append(" ".join(self.tags))
        return "\n".join(part for part in parts if part)

    def to_metadata(self) -> dict[str, Any]:
        return asdict(self)


class RAGMemory:
    """Infinite RAG memory with hot/warm tiering."""

    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = db_path or os.environ.get("HLF_MEMORY_DB", ":memory:")
        self._lock = threading.Lock()
        # Hot tier: topic → list of recent entries
        self._hot: dict[str, list[dict[str, Any]]] = {}
        # Persistent shared connection for `:memory:` databases (each new
        # sqlite3.connect(":memory:") would open a *distinct* empty database).
        # For file-backed paths we still share the connection for simplicity
        # and to avoid WAL conflicts between competing connections.
        self._conn: sqlite3.Connection = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        self._conn.executescript(_SCHEMA)
        self._ensure_column("fact_store", "entry_kind", "TEXT NOT NULL DEFAULT 'fact'")
        self._ensure_column("fact_store", "domain", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("fact_store", "solution_kind", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("fact_store", "supersedes_sha256", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("fact_store", "metadata_json", "TEXT NOT NULL DEFAULT '{}' ")
        # Fix 4: promote evidence fields to typed columns for SQL-level filtering
        self._ensure_column("fact_store", "memory_stratum", "TEXT NOT NULL DEFAULT 'working'")
        self._ensure_column("fact_store", "storage_tier", "TEXT NOT NULL DEFAULT 'warm'")
        self._ensure_column("fact_store", "revoked", "INTEGER NOT NULL DEFAULT 0")
        self._ensure_column("fact_store", "tombstoned", "INTEGER NOT NULL DEFAULT 0")
        self._ensure_column("fact_store", "provenance_grade", "TEXT NOT NULL DEFAULT 'basic'")
        self._ensure_column("fact_store", "salience_score", "REAL NOT NULL DEFAULT 0.0")
        self._ensure_column("fact_store", "artifact_form", "TEXT NOT NULL DEFAULT 'raw_intake'")
        self._ensure_column("fact_store", "source_authority_label", "TEXT NOT NULL DEFAULT 'advisory'")
        self._ensure_column("fact_store", "source_type", "TEXT NOT NULL DEFAULT ''")
        self._backfill_evidence_columns()

    def _ensure_column(self, table: str, column: str, ddl: str) -> None:
        existing = {
            row["name"] for row in self._conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if column not in existing:
            self._conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

    def _backfill_evidence_columns(self) -> None:
        """One-time backfill: derive evidence columns from metadata_json for pre-existing rows."""
        rows = self._conn.execute(
            "SELECT id, metadata_json FROM fact_store "
            "WHERE memory_stratum = 'working' AND salience_score = 0.0 AND metadata_json != '{}'"
        ).fetchall()
        if not rows:
            return
        for row in rows:
            meta = json.loads(row["metadata_json"] or "{}")
            governed = meta.get("governed_evidence") if isinstance(meta.get("governed_evidence"), dict) else {}
            stratum = str(governed.get("memory_stratum") or meta.get("memory_stratum") or "working")
            tier = str(governed.get("storage_tier") or meta.get("storage_tier") or "warm")
            revoked = 1 if _coerce_bool(governed.get("revoked") or meta.get("revoked")) else 0
            tombstoned = 1 if _coerce_bool(governed.get("tombstoned") or meta.get("tombstoned")) else 0
            grade = str(governed.get("provenance_grade") or meta.get("provenance_grade") or "basic")
            salience = float(governed.get("salience_score") or meta.get("salience_score") or 0.0)
            art_form = str(governed.get("artifact_form") or meta.get("artifact_form") or "raw_intake")
            auth_label = str(governed.get("source_authority_label") or meta.get("source_authority_label") or "advisory")
            src_type = str(governed.get("source_type") or meta.get("source_type") or "")
            self._conn.execute(
                "UPDATE fact_store SET memory_stratum=?, storage_tier=?, revoked=?, tombstoned=?, "
                "provenance_grade=?, salience_score=?, artifact_form=?, source_authority_label=?, "
                "source_type=? WHERE id=?",
                (stratum, tier, revoked, tombstoned, grade, salience, art_form, auth_label, src_type, row["id"]),
            )
        self._conn.commit()

    def _connect(self) -> sqlite3.Connection:
        return self._conn

    def _normalize_metadata(
        self,
        *,
        metadata: dict[str, Any] | None,
        topic: str,
        confidence: float,
        provenance: str,
        entry_kind: str,
        domain: str,
        solution_kind: str,
        supersedes_sha256: str,
        created_at: float,
    ) -> dict[str, Any]:
        normalized = dict(metadata or {})
        provenance_payload = normalized.get("provenance")
        if not isinstance(provenance_payload, dict):
            provenance_payload = {}
        governed_evidence = normalized.get("governed_evidence")
        if not isinstance(governed_evidence, dict):
            governed_evidence = {}

        source_path = (
            governed_evidence.get("source_path")
            or normalized.get("artifact_path")
            or normalized.get("source_path")
            or provenance_payload.get("artifact_path")
        )
        artifact_id = governed_evidence.get("artifact_id") or normalized.get("artifact_id")
        collector = (
            governed_evidence.get("collector") or provenance_payload.get("collector") or provenance
        )
        collected_at = (
            governed_evidence.get("collected_at")
            or provenance_payload.get("collected_at")
            or _timestamp_to_iso8601(created_at)
        )
        governed_evidence.update(
            {
                "source_class": governed_evidence.get("source_class") or entry_kind,
                "source_type": governed_evidence.get("source_type")
                or provenance_payload.get("source_type")
                or entry_kind,
                "source": governed_evidence.get("source")
                or provenance_payload.get("source")
                or normalized.get("source")
                or provenance,
                "source_path": source_path,
                "artifact_id": artifact_id,
                "workflow_run_url": governed_evidence.get("workflow_run_url")
                or provenance_payload.get("workflow_run_url"),
                "branch": governed_evidence.get("branch") or provenance_payload.get("branch"),
                "commit_sha": governed_evidence.get("commit_sha")
                or provenance_payload.get("commit_sha"),
                "collector": collector,
                "collector_version": governed_evidence.get("collector_version")
                or normalized.get("collector_version"),
                "collected_at": collected_at,
                "confidence": float(
                    governed_evidence.get("confidence")
                    or provenance_payload.get("confidence")
                    or confidence
                ),
                "fresh_until": governed_evidence.get("fresh_until")
                or normalized.get("fresh_until"),
                "trust_tier": governed_evidence.get("trust_tier")
                or normalized.get("trust_tier")
                or "local",
                "operator_summary": governed_evidence.get("operator_summary")
                or normalized.get("operator_summary")
                or normalized.get("summary")
                or "",
                "revoked": _coerce_bool(
                    governed_evidence.get("revoked") or normalized.get("revoked")
                ),
                "tombstoned": _coerce_bool(
                    governed_evidence.get("tombstoned") or normalized.get("tombstoned")
                ),
                "supersedes": governed_evidence.get("supersedes") or supersedes_sha256,
                "topic": topic,
                "domain": domain,
                "solution_kind": solution_kind,
            }
        )
        explicit_memory_contract = _has_explicit_memory_contract(normalized, governed_evidence)
        memory_stratum = _normalize_memory_stratum(
            normalized.get("memory_stratum"),
            entry_kind=entry_kind,
            topic=topic,
            metadata=normalized,
        )
        storage_tier = _normalize_storage_tier(
            normalized.get("storage_tier") or governed_evidence.get("storage_tier"),
            memory_stratum=memory_stratum,
        )
        governed_evidence["memory_stratum"] = memory_stratum
        governed_evidence["storage_tier"] = storage_tier
        normalized["memory_stratum"] = memory_stratum
        normalized["storage_tier"] = storage_tier
        normalized["tiering_contract"] = {
            "memory_stratum": memory_stratum,
            "storage_tier": storage_tier,
            "architecture_version": "hks-tiering-v1",
        }
        normalized["governed_evidence"] = governed_evidence

        evaluation = normalized.get("evaluation")
        if not isinstance(evaluation, dict):
            evaluation = {}
        has_explicit_evaluation = bool(evaluation)

        provenance_backed = bool(provenance_payload) or any(
            [
                source_path,
                artifact_id,
                governed_evidence.get("workflow_run_url"),
                governed_evidence.get("branch"),
                governed_evidence.get("commit_sha"),
            ]
        )
        fresh_until_ts = _parse_fresh_until(
            governed_evidence.get("fresh_until") or normalized.get("fresh_until")
        )
        freshness_verdict = "stale" if fresh_until_ts is not None and fresh_until_ts < created_at else "fresh"
        provenance_verdict = "evidence-backed" if provenance_backed else "basic"
        authority = str(evaluation.get("authority") or "local_hks").strip() or "local_hks"
        evaluation_id = str(
            evaluation.get("evaluation_id")
            or f"eval-{hashlib.sha256(f'{topic}|{entry_kind}|{authority}|{created_at}|{governed_evidence.get("source") or provenance}'.encode()).hexdigest()[:12]}"
        )
        citation_coverage = _coerce_float(
            evaluation.get("citation_coverage"), 1.0 if provenance_backed else 0.0
        )
        groundedness = _coerce_float(evaluation.get("groundedness"), confidence)

        requested_promotion = evaluation.get("promotion_eligible")
        revoked = _coerce_bool(governed_evidence.get("revoked") or normalized.get("revoked"))
        tombstoned = _coerce_bool(
            governed_evidence.get("tombstoned") or normalized.get("tombstoned")
        )
        if authority != "local_hks":
            promotion_eligible = False
            promotion_blocked = True
            requires_local_recheck = True
            lane = "bridge"
        else:
            promotion_eligible = (
                has_explicit_evaluation
                and _coerce_bool(requested_promotion)
                and freshness_verdict == "fresh"
                and provenance_backed
            )
            promotion_blocked = not promotion_eligible
            requires_local_recheck = False
            lane = "current_truth"

        salience_score = _compute_salience_score(
            confidence=confidence,
            groundedness=groundedness,
            citation_coverage=citation_coverage,
            freshness_verdict=freshness_verdict,
            provenance_backed=provenance_backed,
            entry_kind=entry_kind,
            promotion_eligible=promotion_eligible,
            revoked=revoked,
            tombstoned=tombstoned,
        )
        if not explicit_memory_contract:
            if revoked or tombstoned or freshness_verdict == "stale" or salience_score < _ARCHIVE_SALIENCE_THRESHOLD:
                memory_stratum = "archive"
                storage_tier = "cold"
            elif memory_stratum == "working" and provenance_backed:
                memory_stratum = "provenance"
                storage_tier = "warm"

        admission_decision = "archive" if memory_stratum == "archive" else "active"
        governed_evidence["memory_stratum"] = memory_stratum
        governed_evidence["storage_tier"] = storage_tier
        governed_evidence["salience_score"] = salience_score
        governed_evidence["admission_decision"] = admission_decision
        normalized["memory_stratum"] = memory_stratum
        normalized["storage_tier"] = storage_tier
        normalized["salience_score"] = salience_score
        normalized["admission_decision"] = admission_decision
        normalized["tiering_contract"] = {
            "memory_stratum": memory_stratum,
            "storage_tier": storage_tier,
            "architecture_version": "hks-tiering-v1",
            "salience_score": salience_score,
            "admission_decision": admission_decision,
        }

        explicit_local_evaluation_present = has_explicit_evaluation and authority == "local_hks"

        normalized["evaluation"] = {
            "evaluation_id": evaluation_id,
            "authority": authority,
            "explicit_local_evaluation_present": explicit_local_evaluation_present,
            "groundedness": groundedness,
            "citation_coverage": citation_coverage,
            "freshness_verdict": str(evaluation.get("freshness_verdict") or freshness_verdict),
            "provenance_verdict": str(
                evaluation.get("provenance_verdict") or provenance_verdict
            ),
            "promotion_eligible": promotion_eligible,
            "promotion_blocked": promotion_blocked,
            "requires_local_recheck": requires_local_recheck,
            "lane": str(evaluation.get("lane") or lane),
            "salience_score": salience_score,
            "admission_decision": admission_decision,
            "operator_summary": str(
                evaluation.get("operator_summary")
                or governed_evidence.get("operator_summary")
                or normalized.get("operator_summary")
                or normalized.get("summary")
                or ""
            ),
        }
        source_capture = _build_source_capture_view(
            normalized,
            governed_evidence=governed_evidence,
            evaluation=normalized["evaluation"],
            entry_kind=entry_kind,
        )
        artifact_contract = _build_artifact_contract_view(
            normalized,
            governed_evidence=governed_evidence,
            evaluation=normalized["evaluation"],
            entry_kind=entry_kind,
            topic=topic,
        )
        normalized["source_capture"] = source_capture
        normalized["artifact_contract"] = artifact_contract
        normalized["artifact_form"] = artifact_contract["artifact_form"]
        normalized["artifact_kind"] = artifact_contract["artifact_kind"]
        normalized["source_authority_label"] = source_capture["source_authority_label"]
        governed_evidence["artifact_form"] = artifact_contract["artifact_form"]
        governed_evidence["artifact_kind"] = artifact_contract["artifact_kind"]
        governed_evidence["source_authority_label"] = source_capture["source_authority_label"]
        if source_capture["source_type_classification"]:
            governed_evidence["source_type_classification"] = source_capture["source_type_classification"]
        for metric_key in (
            "extraction_fidelity_score",
            "code_block_recall_score",
            "structure_fidelity_score",
            "citation_recoverability_score",
            "source_version",
            "freshness_marker",
        ):
            if source_capture.get(metric_key) is not None and source_capture.get(metric_key) != "":
                governed_evidence[metric_key] = source_capture.get(metric_key)
        return normalized

    def _superseded_hashes(self, conn: sqlite3.Connection) -> set[str]:
        rows = conn.execute(
            "SELECT DISTINCT supersedes_sha256 FROM fact_store WHERE supersedes_sha256 != ''"
        ).fetchall()
        return {
            str(row["supersedes_sha256"]).strip().lower()
            for row in rows
            if row["supersedes_sha256"]
        }

    def _build_evidence(
        self,
        *,
        row: sqlite3.Row,
        metadata: dict[str, Any],
        superseded_hashes: set[str],
        now: float,
    ) -> dict[str, Any]:
        governed = (
            metadata.get("governed_evidence")
            if isinstance(metadata.get("governed_evidence"), dict)
            else {}
        )
        provenance_payload = (
            metadata.get("provenance") if isinstance(metadata.get("provenance"), dict) else {}
        )

        collector = (
            governed.get("collector") or provenance_payload.get("collector") or row["provenance"]
        )
        collected_at = (
            governed.get("collected_at")
            or provenance_payload.get("collected_at")
            or _timestamp_to_iso8601(row["created_at"])
        )
        source = (
            governed.get("source")
            or provenance_payload.get("source")
            or metadata.get("source")
            or row["provenance"]
        )
        source_type = (
            governed.get("source_type")
            or provenance_payload.get("source_type")
            or row["entry_kind"]
        )
        source_path = (
            governed.get("source_path")
            or metadata.get("artifact_path")
            or provenance_payload.get("artifact_path")
            or metadata.get("source_path")
        )
        artifact_id = governed.get("artifact_id") or metadata.get("artifact_id")
        workflow_run_url = governed.get("workflow_run_url") or provenance_payload.get(
            "workflow_run_url"
        )
        branch = governed.get("branch") or provenance_payload.get("branch")
        commit_sha = governed.get("commit_sha") or provenance_payload.get("commit_sha")
        operator_summary = (
            governed.get("operator_summary")
            or metadata.get("operator_summary")
            or metadata.get("summary")
            or ""
        )
        operator_identity = {
            "operator_id": str(governed.get("operator_id") or metadata.get("operator_id") or ""),
            "operator_display_name": str(
                governed.get("operator_display_name") or metadata.get("operator_display_name") or ""
            ),
            "operator_channel": str(
                governed.get("operator_channel") or metadata.get("operator_channel") or ""
            ),
        }
        collector_version = governed.get("collector_version") or metadata.get("collector_version")
        trust_tier = governed.get("trust_tier") or metadata.get("trust_tier") or "local"
        fresh_until = governed.get("fresh_until") or metadata.get("fresh_until")
        fresh_until_ts = _parse_fresh_until(fresh_until)
        freshness_status = (
            "stale" if fresh_until_ts is not None and fresh_until_ts < now else "fresh"
        )
        revoked = _coerce_bool(governed.get("revoked") or metadata.get("revoked"))
        tombstoned = _coerce_bool(governed.get("tombstoned") or metadata.get("tombstoned"))
        superseded = str(row["sha256"]).lower() in superseded_hashes
        provenance_backed = bool(provenance_payload) or any(
            [
                source_path,
                artifact_id,
                workflow_run_url,
                branch,
                commit_sha,
            ]
        )
        if tombstoned:
            state = "tombstoned"
        elif revoked:
            state = "revoked"
        elif superseded:
            state = "superseded"
        elif freshness_status == "stale":
            state = "stale"
        else:
            state = "active"

        evaluation = _build_evaluation_view(metadata, evidence={
            "freshness_status": freshness_status,
            "provenance_grade": "evidence-backed" if provenance_backed else "basic",
            "revoked": revoked,
            "tombstoned": tombstoned,
        })

        return {
            "sha256": row["sha256"],
            "entry_kind": row["entry_kind"],
            "topic": row["topic"],
            "domain": row["domain"],
            "solution_kind": row["solution_kind"],
            "source_class": governed.get("source_class") or row["entry_kind"],
            "source_type": source_type,
            "source": source,
            "source_path": source_path,
            "artifact_id": artifact_id,
            "workflow_run_url": workflow_run_url,
            "branch": branch,
            "commit_sha": commit_sha,
            "collector": collector,
            "collector_version": collector_version,
            "collected_at": collected_at,
            "created_at": _timestamp_to_iso8601(row["created_at"]),
            "accessed_at": _timestamp_to_iso8601(row["accessed_at"]),
            "confidence": float(
                governed.get("confidence")
                or provenance_payload.get("confidence")
                or row["confidence"]
            ),
            "trust_tier": trust_tier,
            "fresh_until": fresh_until,
            "freshness_status": freshness_status,
            "revoked": revoked,
            "tombstoned": tombstoned,
            "supersedes": governed.get("supersedes") or row["supersedes_sha256"],
            "superseded": superseded,
            "state": state,
            "operator_summary": operator_summary,
            "memory_stratum": governed.get("memory_stratum") or metadata.get("memory_stratum") or "working",
            "storage_tier": governed.get("storage_tier") or metadata.get("storage_tier") or "warm",
            "salience_score": governed.get("salience_score") or metadata.get("salience_score") or evaluation.get("salience_score") or 0.0,
            "admission_decision": governed.get("admission_decision") or metadata.get("admission_decision") or evaluation.get("admission_decision") or "active",
            "operator_identity": operator_identity,
            "provenance_grade": "evidence-backed" if provenance_backed else "basic",
            "provenance_available": bool(collector and collected_at),
            "evaluation_id": evaluation.get("evaluation_id"),
            "evaluation_authority": evaluation.get("authority"),
            "explicit_local_evaluation_present": evaluation.get(
                "explicit_local_evaluation_present", False
            ),
            "promotion_eligible": evaluation.get("promotion_eligible", False),
            "citation_coverage": evaluation.get("citation_coverage"),
            "groundedness": evaluation.get("groundedness"),
            "source_capture": dict(metadata.get("source_capture") or {}),
            "artifact_contract": dict(metadata.get("artifact_contract") or {}),
        }

    def _row_to_fact(
        self,
        *,
        row: sqlite3.Row,
        metadata: dict[str, Any],
        evidence: dict[str, Any],
        similarity: float | None = None,
        query_text: str | None = None,
        metadata_filters: dict[str, str] | None = None,
        purpose: str = "default",
        purpose_policy: dict[str, Any] | None = None,
        query_graph_context: dict[str, Any] | None = None,
        graph_substrate: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        evaluation = _build_evaluation_view(metadata, evidence=evidence)
        tags = json.loads(row["tags"] or "[]")
        graph_context = _build_graph_context(
            topic=str(row["topic"] or ""),
            domain=str(row["domain"] or ""),
            solution_kind=str(row["solution_kind"] or ""),
            tags=[str(tag) for tag in tags if str(tag)],
            metadata=metadata,
        )
        graph_context = self._augment_graph_context(
            graph_context=graph_context,
            fact_sha256=str(row["sha256"] or ""),
            graph_substrate=graph_substrate,
        )
        result = {
            "id": row["id"],
            "sha256": row["sha256"],
            "content": row["content"],
            "topic": row["topic"],
            "confidence": row["confidence"],
            "provenance": row["provenance"],
            "tags": tags,
            "created_at": row["created_at"],
            "entry_kind": row["entry_kind"],
            "domain": row["domain"],
            "solution_kind": row["solution_kind"],
            "supersedes_sha256": row["supersedes_sha256"],
            "metadata": metadata,
            "evaluation": evaluation,
            "evidence": evidence,
            "governance_status": evidence["state"],
            "memory_stratum": evidence.get("memory_stratum") or metadata.get("memory_stratum") or "working",
            "storage_tier": evidence.get("storage_tier") or metadata.get("storage_tier") or "warm",
            "graph_context": graph_context,
            "source_capture": dict(metadata.get("source_capture") or {}),
            "artifact_contract": dict(metadata.get("artifact_contract") or {}),
        }
        if similarity is not None:
            result["similarity"] = round(similarity, 4)
        if query_text is not None and similarity is not None:
            lexical_overlap = set(_tokenize(query_text)) & set(_tokenize(str(row["content"] or "")))
            lexical_score = (
                len(lexical_overlap) / max(len(set(_tokenize(query_text))), 1)
                if query_text.strip()
                else 0.0
            )
            graph_relevance = _score_graph_relevance(
                query_graph_context=query_graph_context or _build_query_graph_context(
                    query_text=query_text,
                    metadata_filters=dict(metadata_filters or {}),
                ),
                graph_context=graph_context,
            )
            graph_score = float(graph_relevance.get("graph_score") or 0.0)
            rank_score = round(min(1.0, similarity * 0.55 + lexical_score * 0.2 + graph_score * 0.25), 4)
            result["retrieval_contract"] = _build_result_retrieval_contract(
                query_text=query_text,
                content=str(row["content"] or ""),
                topic=str(row["topic"] or ""),
                domain=str(row["domain"] or ""),
                solution_kind=str(row["solution_kind"] or ""),
                tags=[str(tag) for tag in tags if str(tag)],
                similarity=similarity,
                metadata_filters=dict(metadata_filters or {}),
                graph_context=graph_context,
                graph_score=graph_score,
                graph_traversal={
                    "seed_values": graph_relevance.get("seed_values") or [],
                    "matched_entities": graph_relevance.get("matched_entities") or [],
                    "traversed_links": graph_relevance.get("traversed_links") or [],
                    "reachable_node_count": int(graph_relevance.get("reachable_node_count") or 0),
                },
                lexical_score=lexical_score,
                rank_score=rank_score,
                purpose=purpose,
                purpose_policy={
                    **(purpose_policy or {}),
                    "allowed_entry_kinds": sorted((purpose_policy or {}).get("allowed_entry_kinds") or []),
                },
                admitted_for_purpose=False,
                rejection_reasons=[],
            )
        return result

    def _materialize_graph_nodes(
        self,
        conn: sqlite3.Connection,
        *,
        fact_id: int,
        fact_sha256: str,
        topic: str,
        entry_kind: str,
        domain: str,
        solution_kind: str,
        tags: list[str],
        metadata: dict[str, Any],
        provenance: str,
        created_at: float,
    ) -> None:
        if entry_kind == _GRAPH_NODE_ENTRY_KIND:
            return
        graph_context = _build_graph_context(
            topic=topic,
            domain=domain,
            solution_kind=solution_kind,
            tags=tags,
            metadata=metadata,
        )
        entities = graph_context.get("entities") if isinstance(graph_context.get("entities"), list) else []
        links = graph_context.get("links") if isinstance(graph_context.get("links"), list) else []
        if not entities or not links:
            return

        relation_map: dict[str, list[dict[str, str]]] = {}
        for link in links:
            if not isinstance(link, dict):
                continue
            source = str(link.get("source") or "").strip()
            target = str(link.get("target") or "").strip()
            relation = str(link.get("relation") or "related_to").strip() or "related_to"
            if not source or not target:
                continue
            relation_map.setdefault(source, []).append({"relation": relation, "target": target})
            relation_map.setdefault(target, []).append({"relation": relation, "target": source})

        source_governed = (
            metadata.get("governed_evidence") if isinstance(metadata.get("governed_evidence"), dict) else {}
        )
        source_evaluation = (
            metadata.get("evaluation") if isinstance(metadata.get("evaluation"), dict) else {}
        )
        source_authority_label = str(
            source_governed.get("source_authority_label")
            or metadata.get("source_authority_label")
            or "advisory"
        ).strip().lower() or "advisory"
        artifact_form = "canonical_knowledge" if bool(source_evaluation.get("promotion_eligible")) else "raw_intake"

        for entity in entities:
            if not isinstance(entity, dict):
                continue
            node_id = str(entity.get("node_id") or "").strip()
            node_kind = str(entity.get("kind") or "entity").strip() or "entity"
            node_value = str(entity.get("value") or "").strip()
            if not node_id or not node_value:
                continue
            node_relations = relation_map.get(node_id, [])
            graph_node_payload = {
                "node_id": node_id,
                "kind": node_kind,
                "value": node_value,
                "attached_fact_sha256s": [fact_sha256],
                "attached_fact_ids": [fact_id],
                "topics": [topic] if topic else [],
                "domains": [domain] if domain else [],
                "solution_kinds": [solution_kind] if solution_kind else [],
                "entry_kinds": [entry_kind] if entry_kind else [],
                "tags": list(tags[:8]),
                "relations": node_relations[:12],
            }
            node_metadata = {
                "graph_node": graph_node_payload,
                "graph_context": {
                    "entities": [{"kind": node_kind, "value": node_value, "node_id": node_id}],
                    "links": [
                        {"source": node_id, "relation": item["relation"], "target": item["target"]}
                        for item in node_relations[:12]
                    ],
                },
                "memory_stratum": "semantic",
                "storage_tier": "warm",
                "artifact_kind": "graph_node",
                "artifact_form": artifact_form,
                "source_authority_label": source_authority_label,
                "governed_evidence": {
                    "source_class": _GRAPH_NODE_ENTRY_KIND,
                    "source_type": "graph_node",
                    "source": source_governed.get("source") or provenance,
                    "source_path": f"graph-node:{node_id}",
                    "artifact_id": f"graph-node:{node_id}",
                    "collector": "hks_graph_materializer",
                    "collected_at": source_governed.get("collected_at") or _timestamp_to_iso8601(created_at),
                    "confidence": 1.0,
                    "trust_tier": source_governed.get("trust_tier") or "local",
                    "fresh_until": source_governed.get("fresh_until"),
                    "source_authority_label": source_authority_label,
                    "operator_summary": f"First-class HKS graph node '{node_id}' links governed semantic evidence across attached facts.",
                },
            }
            if source_evaluation:
                node_metadata["evaluation"] = {
                    "authority": str(source_evaluation.get("authority") or "local_hks"),
                    "groundedness": _coerce_float(source_evaluation.get("groundedness"), 1.0),
                    "citation_coverage": _coerce_float(source_evaluation.get("citation_coverage"), 1.0),
                    "freshness_verdict": str(source_evaluation.get("freshness_verdict") or "fresh"),
                    "provenance_verdict": str(source_evaluation.get("provenance_verdict") or "basic"),
                    "promotion_eligible": bool(source_evaluation.get("promotion_eligible", False)),
                    "promotion_blocked": bool(source_evaluation.get("promotion_blocked", not bool(source_evaluation.get("promotion_eligible", False)))),
                    "requires_local_recheck": bool(source_evaluation.get("requires_local_recheck", False)),
                    "lane": str(source_evaluation.get("lane") or "bridge"),
                    "operator_summary": f"Graph node '{node_id}' inherits the promotion posture of its attached governed evidence.",
                }
            self._upsert_graph_node(
                conn,
                node_id=node_id,
                node_kind=node_kind,
                node_value=node_value,
                tags=tags,
                domain=domain,
                metadata=node_metadata,
                created_at=created_at,
            )

    def _upsert_graph_node(
        self,
        conn: sqlite3.Connection,
        *,
        node_id: str,
        node_kind: str,
        node_value: str,
        tags: list[str],
        domain: str,
        metadata: dict[str, Any],
        created_at: float,
    ) -> None:
        node_content = f"{node_kind} {node_value}"
        node_sha256 = hashlib.sha256(node_content.encode()).hexdigest()
        row = conn.execute(
            "SELECT id, created_at, provenance, tags, metadata_json FROM fact_store WHERE sha256 = ?",
            (node_sha256,),
        ).fetchone()

        if row is not None:
            existing_metadata = json.loads(row["metadata_json"] or "{}")
            existing_graph_node = (
                existing_metadata.get("graph_node") if isinstance(existing_metadata.get("graph_node"), dict) else {}
            )
            incoming_graph_node = (
                metadata.get("graph_node") if isinstance(metadata.get("graph_node"), dict) else {}
            )
            merged_relations: list[dict[str, str]] = []
            seen_relations: set[tuple[str, str]] = set()
            for relation in [*existing_graph_node.get("relations", []), *incoming_graph_node.get("relations", [])]:
                if not isinstance(relation, dict):
                    continue
                relation_name = str(relation.get("relation") or "related_to").strip() or "related_to"
                target = str(relation.get("target") or "").strip()
                if not target:
                    continue
                key = (relation_name, target)
                if key in seen_relations:
                    continue
                seen_relations.add(key)
                merged_relations.append({"relation": relation_name, "target": target})
            merged_graph_node = {
                "node_id": node_id,
                "kind": node_kind,
                "value": node_value,
                "attached_fact_sha256s": _dedupe_preserve_order(
                    [
                        *[str(item) for item in existing_graph_node.get("attached_fact_sha256s", [])],
                        *[str(item) for item in incoming_graph_node.get("attached_fact_sha256s", [])],
                    ]
                ),
                "attached_fact_ids": [
                    int(item)
                    for item in _dedupe_preserve_order(
                        [
                            *[str(item) for item in existing_graph_node.get("attached_fact_ids", [])],
                            *[str(item) for item in incoming_graph_node.get("attached_fact_ids", [])],
                        ]
                    )
                    if str(item).isdigit()
                ],
                "topics": _dedupe_preserve_order(
                    [
                        *[str(item) for item in existing_graph_node.get("topics", [])],
                        *[str(item) for item in incoming_graph_node.get("topics", [])],
                    ]
                ),
                "domains": _dedupe_preserve_order(
                    [
                        *[str(item) for item in existing_graph_node.get("domains", [])],
                        *[str(item) for item in incoming_graph_node.get("domains", [])],
                    ]
                ),
                "solution_kinds": _dedupe_preserve_order(
                    [
                        *[str(item) for item in existing_graph_node.get("solution_kinds", [])],
                        *[str(item) for item in incoming_graph_node.get("solution_kinds", [])],
                    ]
                ),
                "entry_kinds": _dedupe_preserve_order(
                    [
                        *[str(item) for item in existing_graph_node.get("entry_kinds", [])],
                        *[str(item) for item in incoming_graph_node.get("entry_kinds", [])],
                    ]
                ),
                "tags": _dedupe_preserve_order(
                    [
                        *[str(item) for item in existing_graph_node.get("tags", [])],
                        *[str(item) for item in incoming_graph_node.get("tags", [])],
                    ]
                )[:12],
                "relations": merged_relations[:24],
            }
            merged_metadata = {**existing_metadata, **metadata, "graph_node": merged_graph_node}
            merged_metadata["graph_context"] = {
                "entities": [{"kind": node_kind, "value": node_value, "node_id": node_id}],
                "links": [
                    {"source": node_id, "relation": item["relation"], "target": item["target"]}
                    for item in merged_relations[:24]
                ],
            }
            normalized_metadata = self._normalize_metadata(
                metadata=merged_metadata,
                topic="hlf_graph_nodes",
                confidence=1.0,
                provenance=str(row["provenance"] or "hks_graph_materializer"),
                entry_kind=_GRAPH_NODE_ENTRY_KIND,
                domain=domain,
                solution_kind="graph-node",
                supersedes_sha256="",
                created_at=float(row["created_at"]),
            )
            merged_tags = _dedupe_preserve_order(
                [
                    *json.loads(row["tags"] or "[]"),
                    *tags,
                    "hks",
                    "graph",
                    node_kind,
                ]
            )[:16]
            conn.execute(
                "UPDATE fact_store SET tags = ?, metadata_json = ?, accessed_at = ? WHERE id = ?",
                (
                    json.dumps(merged_tags),
                    json.dumps(normalized_metadata, ensure_ascii=False, sort_keys=True),
                    time.time(),
                    row["id"],
                ),
            )
            return

        normalized_metadata = self._normalize_metadata(
            metadata=metadata,
            topic="hlf_graph_nodes",
            confidence=1.0,
            provenance="hks_graph_materializer",
            entry_kind=_GRAPH_NODE_ENTRY_KIND,
            domain=domain,
            solution_kind="graph-node",
            supersedes_sha256="",
            created_at=created_at,
        )
        vec = _bow_vector(node_content)
        cursor = conn.execute(
            """
            INSERT INTO fact_store
                (
                    sha256, content, topic, confidence, provenance, tags, vector_json,
                    created_at, accessed_at, entry_kind, domain, solution_kind,
                    supersedes_sha256, metadata_json
                )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                node_sha256,
                node_content,
                "hlf_graph_nodes",
                1.0,
                "hks_graph_materializer",
                json.dumps(_dedupe_preserve_order([*tags, "hks", "graph", node_kind])[:16]),
                json.dumps(vec),
                created_at,
                created_at,
                _GRAPH_NODE_ENTRY_KIND,
                domain,
                "graph-node",
                "",
                json.dumps(normalized_metadata, ensure_ascii=False, sort_keys=True),
            ),
        )
        self._append_merkle(conn, "hlf_graph_nodes", node_sha256)
        if "hlf_graph_nodes" not in self._hot:
            self._hot["hlf_graph_nodes"] = []
        self._hot["hlf_graph_nodes"].append(
            {
                "id": cursor.lastrowid,
                "content": node_content,
                "topic": "hlf_graph_nodes",
                "confidence": 1.0,
                "vector": vec,
            }
        )

    def _load_graph_substrate(
        self,
        conn: sqlite3.Connection,
        *,
        now: float,
        superseded_hashes: set[str],
    ) -> dict[str, Any]:
        rows = conn.execute(
            "SELECT id, sha256, content, topic, confidence, provenance, tags, created_at, accessed_at, entry_kind, domain, solution_kind, supersedes_sha256, metadata_json FROM fact_store WHERE entry_kind = ?",
            (_GRAPH_NODE_ENTRY_KIND,),
        ).fetchall()
        node_index: dict[str, dict[str, Any]] = {}
        attached_fact_index: dict[str, set[str]] = {}
        relation_count = 0
        for row in rows:
            metadata = json.loads(row["metadata_json"] or "{}")
            evidence = self._build_evidence(
                row=row,
                metadata=metadata,
                superseded_hashes=superseded_hashes,
                now=now,
            )
            if evidence.get("state") != "active":
                continue
            graph_node = metadata.get("graph_node") if isinstance(metadata.get("graph_node"), dict) else {}
            node_id = str(graph_node.get("node_id") or "").strip()
            if not node_id:
                continue
            attached_fact_sha256s = [
                str(item).strip().lower()
                for item in graph_node.get("attached_fact_sha256s", [])
                if str(item).strip()
            ]
            relations = [
                {
                    "relation": str(item.get("relation") or "related_to").strip() or "related_to",
                    "target": str(item.get("target") or "").strip(),
                }
                for item in graph_node.get("relations", [])
                if isinstance(item, dict) and str(item.get("target") or "").strip()
            ]
            relation_count += len(relations)
            node_index[node_id] = {
                "node_id": node_id,
                "kind": str(graph_node.get("kind") or "entity").strip() or "entity",
                "value": str(graph_node.get("value") or row["content"] or "").strip(),
                "relations": relations,
                "attached_fact_sha256s": attached_fact_sha256s,
            }
            for fact_sha256 in attached_fact_sha256s:
                attached_fact_index.setdefault(fact_sha256, set()).add(node_id)
        return {
            "node_index": node_index,
            "attached_fact_index": attached_fact_index,
            "node_count": len(node_index),
            "relation_count": relation_count,
            "source": "persisted-hks-node-graph" if node_index else "metadata-derived",
        }

    def _augment_graph_context(
        self,
        *,
        graph_context: dict[str, Any],
        fact_sha256: str,
        graph_substrate: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not isinstance(graph_context, dict):
            graph_context = {}
        substrate = graph_substrate if isinstance(graph_substrate, dict) else {}
        node_index = substrate.get("node_index") if isinstance(substrate.get("node_index"), dict) else {}
        attached_fact_index = (
            substrate.get("attached_fact_index") if isinstance(substrate.get("attached_fact_index"), dict) else {}
        )
        attached_node_ids = set(
            attached_fact_index.get(str(fact_sha256 or "").strip().lower(), set())
        )
        for entity in graph_context.get("entities") or []:
            if not isinstance(entity, dict):
                continue
            node_id = str(entity.get("node_id") or "").strip()
            if node_id and node_id in node_index:
                attached_node_ids.add(node_id)

        entities: list[dict[str, str]] = []
        links: list[dict[str, str]] = []
        seen_entities: set[str] = set()
        seen_links: set[tuple[str, str, str]] = set()

        def add_entity(item: dict[str, Any]) -> None:
            node_id = str(item.get("node_id") or "").strip()
            if not node_id or node_id in seen_entities:
                return
            seen_entities.add(node_id)
            entities.append(
                {
                    "kind": str(item.get("kind") or "entity").strip() or "entity",
                    "value": str(item.get("value") or "").strip(),
                    "node_id": node_id,
                }
            )

        def add_link(source: str, relation: str, target: str) -> None:
            normalized_source = str(source or "").strip()
            normalized_target = str(target or "").strip()
            normalized_relation = str(relation or "related_to").strip() or "related_to"
            if not normalized_source or not normalized_target:
                return
            key = (normalized_source, normalized_relation, normalized_target)
            if key in seen_links:
                return
            seen_links.add(key)
            links.append(
                {
                    "source": normalized_source,
                    "relation": normalized_relation,
                    "target": normalized_target,
                }
            )

        for entity in graph_context.get("entities") or []:
            if isinstance(entity, dict):
                add_entity(entity)
        for link in graph_context.get("links") or []:
            if isinstance(link, dict):
                add_link(link.get("source", ""), link.get("relation", "related_to"), link.get("target", ""))

        frontier = list(attached_node_ids)
        visited: set[str] = set()
        while frontier and len(visited) < 24:
            node_id = frontier.pop(0)
            if node_id in visited:
                continue
            visited.add(node_id)
            node = node_index.get(node_id)
            if not isinstance(node, dict):
                continue
            add_entity(node)
            for relation in node.get("relations") or []:
                if not isinstance(relation, dict):
                    continue
                target = str(relation.get("target") or "").strip()
                add_link(node_id, relation.get("relation", "related_to"), target)
                target_node = node_index.get(target)
                if isinstance(target_node, dict):
                    add_entity(target_node)
                    if target not in visited:
                        frontier.append(target)

        return {
            "graph_linked": bool(links),
            "entity_count": len(entities),
            "link_count": len(links),
            "entities": entities[:16],
            "links": links[:24],
            "graph_source": str(substrate.get("source") or "metadata-derived"),
            "attached_node_ids": sorted(attached_node_ids)[:16],
            "persisted_node_count": int(substrate.get("node_count") or 0),
            "persisted_relation_count": int(substrate.get("relation_count") or 0),
        }

    def _include_fact(
        self,
        *,
        evidence: dict[str, Any],
        include_stale: bool,
        include_superseded: bool,
        include_revoked: bool,
        require_provenance: bool,
        include_archive: bool,
    ) -> bool:
        if not include_revoked and (evidence["revoked"] or evidence["tombstoned"]):
            return False
        if not include_stale and evidence["freshness_status"] == "stale":
            return False
        if not include_archive and evidence.get("memory_stratum") == "archive":
            return False
        if not include_superseded and evidence["superseded"]:
            return False
        if require_provenance and evidence["provenance_grade"] != "evidence-backed":
            return False
        return True

    # ── Store ─────────────────────────────────────────────────────────────────

    def store(
        self,
        content: str,
        topic: str = "general",
        confidence: float = 1.0,
        provenance: str = "agent",
        tags: list[str] | None = None,
        *,
        entry_kind: str = "fact",
        domain: str | None = None,
        solution_kind: str | None = None,
        supersedes_sha256: str | None = None,
        metadata: dict[str, Any] | None = None,
        strict: bool = False,
    ) -> dict[str, Any]:
        """Store a fact. Returns {id, sha256, stored, duplicate_reason}.

        When ``strict=True``, basic evidence provenance is enforced:
        - content must be non-empty
        - confidence must be in [0.0, 1.0]
        - provenance must be an explicit declared value
        - metadata should contain governed_evidence when making evidence claims
        """
        # ── Write-path evidence validation ────────────────────────────────
        if not content or not content.strip():
            return {"stored": False, "error": "empty_content", "sha256": ""}

        if not 0.0 <= confidence <= 1.0:
            return {"stored": False, "error": "confidence_out_of_range", "sha256": ""}

        if strict:
            _VALID_PROVENANCE = {
                "agent", "operator", "system", "user", "pipeline",
                "extraction", "governed_recall", "hks_capture",
            }
            if provenance not in _VALID_PROVENANCE:
                return {
                    "stored": False,
                    "error": f"strict: provenance '{provenance}' not in {sorted(_VALID_PROVENANCE)}",
                    "sha256": "",
                }
            meta = metadata or {}
            governed = meta.get("governed_evidence") or {}
            if entry_kind in ("evidence", "hks_exemplar") and not governed.get("source_type"):
                return {
                    "stored": False,
                    "error": "strict: evidence/hks entries require governed_evidence.source_type",
                    "sha256": "",
                }
        normalized_domain = self._normalize_domain(domain)
        sha256 = hashlib.sha256(content.encode()).hexdigest()
        tags_json = json.dumps(tags or [])
        vec = _bow_vector(content)
        vec_json = json.dumps(vec)
        metadata_json = json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True)
        now = time.time()
        normalized_metadata = self._normalize_metadata(
            metadata=metadata,
            topic=topic,
            confidence=confidence,
            provenance=provenance,
            entry_kind=entry_kind,
            domain=normalized_domain,
            solution_kind=solution_kind or "",
            supersedes_sha256=supersedes_sha256 or "",
            created_at=now,
        )
        metadata_json = json.dumps(normalized_metadata, ensure_ascii=False, sort_keys=True)

        # Extract typed evidence columns from enriched metadata
        _ge = normalized_metadata.get("governed_evidence") or {}
        col_memory_stratum = str(_ge.get("memory_stratum") or normalized_metadata.get("memory_stratum") or "working")
        col_storage_tier = str(_ge.get("storage_tier") or normalized_metadata.get("storage_tier") or "warm")
        col_revoked = 1 if _coerce_bool(_ge.get("revoked")) else 0
        col_tombstoned = 1 if _coerce_bool(_ge.get("tombstoned")) else 0
        col_provenance_grade = "evidence-backed" if (
            bool(normalized_metadata.get("provenance"))
            or any([
                _ge.get("source_path"),
                _ge.get("artifact_id"),
                _ge.get("workflow_run_url"),
                _ge.get("branch"),
                _ge.get("commit_sha"),
            ])
        ) else "basic"
        col_salience_score = float(_ge.get("salience_score") or normalized_metadata.get("salience_score") or 0.0)
        col_artifact_form = str(_ge.get("artifact_form") or normalized_metadata.get("artifact_form") or "raw_intake")
        col_source_authority_label = str(_ge.get("source_authority_label") or normalized_metadata.get("source_authority_label") or "advisory")
        col_source_type = str(_ge.get("source_type") or normalized_metadata.get("source_type") or "")

        with self._lock, self._connect() as conn:
            # SHA-256 exact dedup
            existing = conn.execute(
                "SELECT id FROM fact_store WHERE sha256 = ?", (sha256,)
            ).fetchone()
            if existing:
                return {
                    "id": existing["id"],
                    "sha256": sha256,
                    "stored": False,
                    "duplicate_reason": "sha256_exact_match",
                }

            # Vector race protection: check cosine similarity > 0.98
            recent = conn.execute(
                "SELECT id, sha256, vector_json FROM fact_store "
                "WHERE topic = ? ORDER BY created_at DESC LIMIT 100",
                (topic,),
            ).fetchall()
            for row in recent:
                existing_vec = json.loads(row["vector_json"] or "{}")
                sim = _cosine(vec, existing_vec)
                if sim >= _DEDUP_THRESHOLD:
                    return {
                        "id": row["id"],
                        "sha256": sha256,
                        "stored": False,
                        "duplicate_reason": f"vector_similarity_{sim:.3f}",
                    }

            # Insert
            cursor = conn.execute(
                """
                INSERT INTO fact_store
                    (
                        sha256, content, topic, confidence, provenance, tags, vector_json,
                        created_at, accessed_at, entry_kind, domain, solution_kind,
                        supersedes_sha256, metadata_json,
                        memory_stratum, storage_tier, revoked, tombstoned,
                        provenance_grade, salience_score,
                        artifact_form, source_authority_label, source_type
                    )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sha256,
                    content,
                    topic,
                    confidence,
                    provenance,
                    tags_json,
                    vec_json,
                    now,
                    now,
                    entry_kind,
                    normalized_domain,
                    solution_kind or "",
                    supersedes_sha256 or "",
                    metadata_json,
                    col_memory_stratum,
                    col_storage_tier,
                    col_revoked,
                    col_tombstoned,
                    col_provenance_grade,
                    col_salience_score,
                    col_artifact_form,
                    col_source_authority_label,
                    col_source_type,
                ),
            )
            row_id = cursor.lastrowid

            # Update Merkle chain
            self._append_merkle(conn, topic, sha256)

            # Update hot tier
            if topic not in self._hot:
                self._hot[topic] = []
            self._hot[topic].append(
                {
                    "id": row_id,
                    "content": content,
                    "topic": topic,
                    "confidence": confidence,
                    "vector": vec,
                }
            )
            self._materialize_graph_nodes(
                conn,
                fact_id=int(row_id),
                fact_sha256=sha256,
                topic=topic,
                entry_kind=entry_kind,
                domain=normalized_domain,
                solution_kind=solution_kind or "",
                tags=list(tags or []),
                metadata=normalized_metadata,
                provenance=provenance,
                created_at=now,
            )

        return {
            "evaluation": _build_evaluation_view(normalized_metadata, evidence={
                "freshness_status": "fresh",
                "provenance_grade": "evidence-backed"
                if bool(normalized_metadata.get("provenance"))
                or any(
                    [
                        normalized_metadata["governed_evidence"].get("source_path"),
                        normalized_metadata["governed_evidence"].get("artifact_id"),
                        normalized_metadata["governed_evidence"].get("workflow_run_url"),
                        normalized_metadata["governed_evidence"].get("branch"),
                        normalized_metadata["governed_evidence"].get("commit_sha"),
                    ]
                )
                else "basic",
                "revoked": normalized_metadata["governed_evidence"].get("revoked", False),
                "tombstoned": normalized_metadata["governed_evidence"].get("tombstoned", False),
            }),
            "id": row_id,
            "sha256": sha256,
            "stored": True,
            "duplicate_reason": None,
            "entry_kind": entry_kind,
            "domain": normalized_domain,
            "solution_kind": solution_kind or "",
            "supersedes_sha256": supersedes_sha256 or "",
            "metadata": normalized_metadata,
            "source_capture": dict(normalized_metadata.get("source_capture") or {}),
            "artifact_contract": dict(normalized_metadata.get("artifact_contract") or {}),
            "memory_stratum": normalized_metadata.get("memory_stratum") or "working",
            "storage_tier": normalized_metadata.get("storage_tier") or "warm",
            "evidence": {
                "sha256": sha256,
                "entry_kind": entry_kind,
                "topic": topic,
                "domain": normalized_domain,
                "solution_kind": solution_kind or "",
                "source_class": normalized_metadata["governed_evidence"].get("source_class")
                or entry_kind,
                "source_type": normalized_metadata["governed_evidence"].get("source_type")
                or entry_kind,
                "source": normalized_metadata["governed_evidence"].get("source") or provenance,
                "source_path": normalized_metadata["governed_evidence"].get("source_path"),
                "artifact_id": normalized_metadata["governed_evidence"].get("artifact_id"),
                "workflow_run_url": normalized_metadata["governed_evidence"].get(
                    "workflow_run_url"
                ),
                "branch": normalized_metadata["governed_evidence"].get("branch"),
                "commit_sha": normalized_metadata["governed_evidence"].get("commit_sha"),
                "collector": normalized_metadata["governed_evidence"].get("collector")
                or provenance,
                "collector_version": normalized_metadata["governed_evidence"].get(
                    "collector_version"
                ),
                "collected_at": normalized_metadata["governed_evidence"].get("collected_at")
                or _timestamp_to_iso8601(now),
                "created_at": _timestamp_to_iso8601(now),
                "accessed_at": _timestamp_to_iso8601(now),
                "confidence": normalized_metadata["governed_evidence"].get(
                    "confidence", confidence
                ),
                "trust_tier": normalized_metadata["governed_evidence"].get("trust_tier", "local"),
                "fresh_until": normalized_metadata["governed_evidence"].get("fresh_until"),
                "freshness_status": "fresh",
                "revoked": normalized_metadata["governed_evidence"].get("revoked", False),
                "tombstoned": normalized_metadata["governed_evidence"].get("tombstoned", False),
                "supersedes": normalized_metadata["governed_evidence"].get("supersedes")
                or supersedes_sha256
                or "",
                "superseded": False,
                "state": "active",
                "operator_summary": normalized_metadata["governed_evidence"].get("operator_summary")
                or "",
                "memory_stratum": normalized_metadata.get("memory_stratum") or "working",
                "storage_tier": normalized_metadata.get("storage_tier") or "warm",
                "provenance_grade": "evidence-backed"
                if bool(normalized_metadata.get("provenance"))
                or any(
                    [
                        normalized_metadata["governed_evidence"].get("source_path"),
                        normalized_metadata["governed_evidence"].get("artifact_id"),
                        normalized_metadata["governed_evidence"].get("workflow_run_url"),
                        normalized_metadata["governed_evidence"].get("branch"),
                        normalized_metadata["governed_evidence"].get("commit_sha"),
                    ]
                )
                else "basic",
                "provenance_available": True,
                "evaluation_id": normalized_metadata["evaluation"].get("evaluation_id"),
                "evaluation_authority": normalized_metadata["evaluation"].get("authority"),
                "source_authority_label": normalized_metadata.get("source_authority_label") or "advisory",
                "artifact_form": normalized_metadata.get("artifact_form") or "raw_intake",
                "artifact_kind": normalized_metadata.get("artifact_kind") or entry_kind,
                "promotion_eligible": normalized_metadata["evaluation"].get(
                    "promotion_eligible", False
                ),
                "citation_coverage": normalized_metadata["evaluation"].get("citation_coverage"),
                "groundedness": normalized_metadata["evaluation"].get("groundedness"),
                "source_capture": dict(normalized_metadata.get("source_capture") or {}),
                "artifact_contract": dict(normalized_metadata.get("artifact_contract") or {}),
            },
        }

    def govern_fact(
        self,
        *,
        action: str,
        fact_id: int | None = None,
        sha256: str | None = None,
        operator_summary: str = "",
        governed_by: str = "operator",
        reason: str = "",
        operator_id: str = "",
        operator_display_name: str = "",
        operator_channel: str = "",
    ) -> dict[str, Any] | None:
        normalized_action = str(action or "").strip().lower()
        if normalized_action not in {"revoke", "tombstone", "reinstate"}:
            raise ValueError(f"unsupported governance action: {action!r}")
        if fact_id is None and not sha256:
            raise ValueError("fact_id or sha256 is required")

        with self._lock, self._connect() as conn:
            if fact_id is not None:
                row = conn.execute(
                    "SELECT id, sha256, content, topic, confidence, provenance, tags, "
                    "created_at, accessed_at, entry_kind, domain, solution_kind, "
                    "supersedes_sha256, metadata_json FROM fact_store WHERE id = ?",
                    (fact_id,),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT id, sha256, content, topic, confidence, provenance, tags, "
                    "created_at, accessed_at, entry_kind, domain, solution_kind, "
                    "supersedes_sha256, metadata_json FROM fact_store WHERE sha256 = ?",
                    (str(sha256).strip().lower(),),
                ).fetchone()

            if row is None:
                return None

            metadata = json.loads(row["metadata_json"] or "{}")
            governed_evidence = metadata.get("governed_evidence")
            if not isinstance(governed_evidence, dict):
                governed_evidence = {}
            if normalized_action == "revoke":
                governed_evidence["revoked"] = True
                governed_evidence["tombstoned"] = False
            elif normalized_action == "tombstone":
                governed_evidence["revoked"] = False
                governed_evidence["tombstoned"] = True
            else:
                governed_evidence["revoked"] = False
                governed_evidence["tombstoned"] = False

            if operator_summary:
                governed_evidence["operator_summary"] = operator_summary
            metadata["governed_evidence"] = governed_evidence
            metadata["governance_action"] = normalized_action
            metadata["governed_by"] = governed_by
            metadata["governed_reason"] = reason
            metadata["operator_id"] = str(operator_id or "")
            metadata["operator_display_name"] = str(operator_display_name or "")
            metadata["operator_channel"] = str(operator_channel or "")
            metadata["governed_at"] = _timestamp_to_iso8601(time.time())

            normalized_metadata = self._normalize_metadata(
                metadata=metadata,
                topic=str(row["topic"] or ""),
                confidence=float(row["confidence"]),
                provenance=str(row["provenance"] or "agent"),
                entry_kind=str(row["entry_kind"] or "fact"),
                domain=str(row["domain"] or ""),
                solution_kind=str(row["solution_kind"] or ""),
                supersedes_sha256=str(row["supersedes_sha256"] or ""),
                created_at=float(row["created_at"]),
            )
            now = time.time()
            # Fix 4: also update typed evidence columns so SQL filters
            # reflect governance actions immediately
            ge = normalized_metadata.get("governed_evidence") or {}
            col_revoked = 1 if _coerce_bool(ge.get("revoked")) else 0
            col_tombstoned = 1 if _coerce_bool(ge.get("tombstoned")) else 0
            col_provenance_grade = str(ge.get("provenance_grade") or "basic")
            conn.execute(
                "UPDATE fact_store SET metadata_json = ?, accessed_at = ?, "
                "revoked = ?, tombstoned = ?, provenance_grade = ? WHERE id = ?",
                (
                    json.dumps(normalized_metadata, ensure_ascii=False, sort_keys=True),
                    now,
                    col_revoked,
                    col_tombstoned,
                    col_provenance_grade,
                    row["id"],
                ),
            )
            superseded_hashes = self._superseded_hashes(conn)

        evidence = self._build_evidence(
            row=row,
            metadata=normalized_metadata,
            superseded_hashes=superseded_hashes,
            now=now,
        )
        return self._row_to_fact(row=row, metadata=normalized_metadata, evidence=evidence)

    def store_exemplar(self, exemplar: HKSValidatedExemplar) -> dict[str, Any]:
        if not isinstance(exemplar.evaluation, dict) or not exemplar.evaluation:
            raise ValueError("hks exemplar promotion requires an explicit local_hks evaluation contract")
        metadata = exemplar.to_metadata()
        normalized_metadata = self._normalize_metadata(
            metadata=metadata,
            topic=exemplar.topic,
            confidence=exemplar.confidence,
            provenance=exemplar.provenance.collector,
            entry_kind="hks_exemplar",
            domain=exemplar.domain,
            solution_kind=exemplar.solution_kind,
            supersedes_sha256=exemplar.supersedes or "",
            created_at=time.time(),
        )
        evaluation = normalized_metadata.get("evaluation") if isinstance(normalized_metadata.get("evaluation"), dict) else {}
        if str(evaluation.get("authority") or "") != "local_hks":
            raise ValueError("hks exemplar promotion requires local_hks evaluation authority")
        if not _coerce_bool(evaluation.get("promotion_eligible")):
            raise ValueError("hks exemplar promotion requires a local evaluation marked promotion eligible")
        tags = sorted(set([*exemplar.tags, "hks", exemplar.domain, exemplar.solution_kind]))
        return self.store(
            exemplar.to_content(),
            topic=exemplar.topic,
            confidence=exemplar.confidence,
            provenance=exemplar.provenance.collector,
            tags=tags,
            entry_kind="hks_exemplar",
            domain=exemplar.domain,
            solution_kind=exemplar.solution_kind,
            supersedes_sha256=exemplar.supersedes,
            metadata=normalized_metadata,
        )

    def resolve_pointer(
        self,
        pointer: str,
        *,
        purpose: str = "execution",
        registry_entry: dict[str, Any] | None = None,
        trust_mode: str = "enforce",
        include_stale: bool = False,
        include_superseded: bool = False,
        include_revoked: bool = False,
        require_provenance: bool = False,
        include_archive: bool = False,
    ) -> dict[str, Any]:
        parsed = parse_pointer_ref(pointer)
        if parsed is None:
            return {
                "status": "not_pointer",
                "admitted": True,
                "pointer": str(pointer or ""),
                "purpose": purpose,
                "trust_mode": trust_mode,
            }

        normalized_purpose = str(purpose or "execution").strip().lower() or "execution"
        policy = dict(
            _POINTER_PURPOSE_POLICIES.get(
                normalized_purpose,
                _POINTER_PURPOSE_POLICIES["execution"],
            )
        )
        policy["require_provenance"] = bool(require_provenance or policy["require_provenance"])
        policy["allow_stale"] = bool(include_stale or policy["allow_stale"])
        policy["allow_superseded"] = bool(include_superseded or policy["allow_superseded"])
        policy["allow_revoked"] = bool(include_revoked)

        fact_match: dict[str, Any] | None = None
        if registry_entry is None:
            for fact in self.query_facts(
                include_stale=True,
                include_superseded=True,
                include_revoked=True,
            ):
                if str(fact.get("sha256") or "").lower() == parsed["digest"]:
                    fact_match = fact
                    break

        effective_entry = dict(registry_entry or {})
        if fact_match is not None:
            evidence = dict(fact_match.get("evidence") or {})
            effective_entry.update(
                {
                    "pointer": build_pointer_ref(
                        f"{fact_match.get('topic') or 'general'}-{fact_match.get('id') or 'entry'}",
                        str(fact_match.get("sha256") or ""),
                    ),
                    "alias": parsed["alias"],
                    "content_hash": fact_match.get("sha256"),
                    "content": fact_match.get("content"),
                    "trust_tier": evidence.get("trust_tier", "local"),
                    "fresh_until": evidence.get("fresh_until"),
                    "revoked": evidence.get("revoked", False),
                    "tombstoned": evidence.get("tombstoned", False),
                    "metadata": dict(fact_match.get("metadata") or {}),
                }
            )

        verification = verify_pointer_ref(pointer, registry_entry=effective_entry or None)
        if verification["status"] == "not_pointer":
            return {
                "status": "not_pointer",
                "admitted": True,
                "pointer": str(pointer or ""),
                "purpose": normalized_purpose,
                "trust_mode": trust_mode,
            }

        admission_reasons: list[str] = []
        admitted = verification["status"] == "ok"
        evidence: dict[str, Any] = {}
        governance_status = str(verification.get("governance_status") or "unknown")
        freshness_status = str(verification.get("freshness_status") or "unknown")
        if fact_match is not None:
            evidence = dict(fact_match.get("evidence") or {})
            governance_status = str(evidence.get("state") or governance_status)
            freshness_status = str(evidence.get("freshness_status") or freshness_status)

        if verification["status"] != "ok":
            admission_reasons.append(
                str(verification.get("reason") or verification["status"])
            )
        elif fact_match is None and not effective_entry:
            admitted = False
            admission_reasons.append("pointer_not_resolved_to_memory")

        if admitted and fact_match is not None:
            if not policy["allow_revoked"] and evidence.get("revoked"):
                admitted = False
                admission_reasons.append("pointer_revoked")
            if not policy["allow_revoked"] and evidence.get("tombstoned"):
                admitted = False
                admission_reasons.append("pointer_tombstoned")
            if not policy["allow_stale"] and freshness_status == "stale":
                admitted = False
                admission_reasons.append("pointer_stale_for_purpose")
            if not policy["allow_superseded"] and evidence.get("superseded"):
                admitted = False
                admission_reasons.append("pointer_superseded_for_purpose")
            if policy["require_provenance"] and evidence.get("provenance_grade") != "evidence-backed":
                admitted = False
                admission_reasons.append("evidence_backed_provenance_required")

        if admitted:
            status = "ok"
        elif verification["status"] != "ok":
            status = str(verification["status"])
        else:
            status = "blocked"

        return {
            "status": status,
            "admitted": admitted,
            "pointer": pointer,
            "purpose": normalized_purpose,
            "trust_mode": trust_mode,
            "resolution": {
                "verification": verification,
                "fact": {
                    "id": fact_match.get("id"),
                    "sha256": fact_match.get("sha256"),
                    "topic": fact_match.get("topic"),
                    "entry_kind": fact_match.get("entry_kind"),
                    "domain": fact_match.get("domain"),
                    "solution_kind": fact_match.get("solution_kind"),
                }
                if fact_match is not None
                else None,
                "policy": {
                    "require_provenance": policy["require_provenance"],
                    "allow_stale": policy["allow_stale"],
                    "allow_superseded": policy["allow_superseded"],
                    "allow_revoked": policy["allow_revoked"],
                },
            },
            "trust_tier": verification.get("trust_tier")
            or evidence.get("trust_tier")
            or "unknown",
            "governance_status": governance_status,
            "freshness_status": freshness_status,
            "provenance_grade": evidence.get("provenance_grade", "basic"),
            "operator_summary": evidence.get("operator_summary", ""),
            "evidence": evidence,
            "resolved_value": verification.get("resolved_value"),
            "reason": ", ".join(admission_reasons),
            "reasons": admission_reasons,
        }

    # ── Query ─────────────────────────────────────────────────────────────────

    def query(
        self,
        query_text: str,
        top_k: int = 5,
        topic: str | None = None,
        min_confidence: float = 0.0,
        *,
        entry_kind: str | None = None,
        domain: str | None = None,
        solution_kind: str | None = None,
        include_stale: bool = False,
        include_superseded: bool = False,
        include_revoked: bool = False,
        require_provenance: bool = False,
        include_archive: bool = False,
        purpose: str | None = None,
    ) -> dict[str, Any]:
        """Query memory by semantic similarity."""
        query_vec = _bow_vector(query_text)
        now = time.time()
        decay_cutoff = now - (_DECAY_DAYS * 86400)
        normalized_domain = self._normalize_domain(domain)
        normalized_purpose, purpose_policy = _resolve_query_policy(
            purpose=purpose,
            require_provenance=require_provenance,
        )
        metadata_filters = {
            key: value
            for key, value in {
                "topic": topic or "",
                "entry_kind": entry_kind or "",
                "domain": normalized_domain,
                "solution_kind": solution_kind or "",
            }.items()
            if value
        }
        query_graph_context = _build_query_graph_context(
            query_text=query_text,
            metadata_filters=metadata_filters,
        )
        invocation_gate = _build_invocation_gate(
            query_text=query_text,
            metadata_filters=metadata_filters,
            purpose=normalized_purpose,
        )

        if not invocation_gate.get("retrieval_invoked", False):
            retrieval_contract = _build_query_retrieval_contract(
                results=[],
                metadata_filters=metadata_filters,
                purpose=normalized_purpose,
                purpose_policy={
                    **purpose_policy,
                    "allowed_entry_kinds": sorted(purpose_policy.get("allowed_entry_kinds") or []),
                },
                rejected_count=0,
                invocation_gate=invocation_gate,
            )
            governed_hks_contract = _build_governed_hks_contract(
                query_text=query_text,
                results=[],
                purpose=normalized_purpose,
                purpose_policy={
                    **purpose_policy,
                    "allowed_entry_kinds": sorted(purpose_policy.get("allowed_entry_kinds") or []),
                },
                retrieval_contract=retrieval_contract,
            )

            return {
                "results": [],
                "count": 0,
                "query": query_text,
                "entry_kind": entry_kind,
                "domain": normalized_domain,
                "solution_kind": solution_kind,
                "include_stale": include_stale,
                "include_superseded": include_superseded,
                "include_revoked": include_revoked,
                "require_provenance": require_provenance,
                "include_archive": include_archive,
                "purpose": normalized_purpose,
                "retrieval_contract": retrieval_contract,
                "governed_hks_contract": governed_hks_contract,
            }

        with self._connect() as conn:
            sql = """
                SELECT id, content, topic, confidence, provenance, tags,
                      sha256, vector_json, created_at, accessed_at, entry_kind,
                       domain, solution_kind, supersedes_sha256, metadata_json
                FROM fact_store
                WHERE confidence >= ?
                  AND created_at >= ?
            """
            params: list[Any] = [min_confidence, decay_cutoff]
            if topic:
                sql += " AND topic = ?"
                params.append(topic)
            if entry_kind:
                sql += " AND entry_kind = ?"
                params.append(entry_kind)
            if normalized_domain:
                sql += " AND domain = ?"
                params.append(normalized_domain)
            if solution_kind:
                sql += " AND solution_kind = ?"
                params.append(solution_kind)
            # Fix 4: push evidence governance filters into SQL
            if not include_revoked:
                sql += " AND revoked = 0 AND tombstoned = 0"
            if not include_archive:
                sql += " AND memory_stratum != 'archive'"
            if require_provenance:
                sql += " AND provenance_grade = 'evidence-backed'"
            sql += " ORDER BY salience_score DESC, confidence DESC, accessed_at DESC LIMIT 500"

            superseded_hashes = self._superseded_hashes(conn)
            rows = conn.execute(sql, params).fetchall()
            graph_substrate = self._load_graph_substrate(
                conn,
                now=now,
                superseded_hashes=superseded_hashes,
            )

        # Score by cosine similarity
        scored: list[dict[str, Any]] = []
        rejected_count = 0
        for row in rows:
            if not entry_kind and str(row["entry_kind"] or "") == _GRAPH_NODE_ENTRY_KIND:
                continue
            vec = json.loads(row["vector_json"] or "{}")
            sim = _cosine(query_vec, vec)
            metadata = json.loads(row["metadata_json"] or "{}")
            evidence = self._build_evidence(
                row=row,
                metadata=metadata,
                superseded_hashes=superseded_hashes,
                now=now,
            )
            if not self._include_fact(
                evidence=evidence,
                include_stale=include_stale,
                include_superseded=include_superseded,
                include_revoked=include_revoked,
                require_provenance=require_provenance,
                include_archive=include_archive,
            ):
                continue
            fact = self._row_to_fact(
                row=row,
                metadata=metadata,
                evidence=evidence,
                similarity=sim,
                query_text=query_text,
                metadata_filters=metadata_filters,
                purpose=normalized_purpose,
                purpose_policy=purpose_policy,
                query_graph_context=query_graph_context,
                graph_substrate=graph_substrate,
            )
            admitted_for_purpose, rejection_reasons = _apply_query_policy(
                fact=fact,
                purpose=normalized_purpose,
                purpose_policy=purpose_policy,
            )
            retrieval = fact.get("retrieval_contract") if isinstance(fact.get("retrieval_contract"), dict) else None
            if retrieval is not None:
                retrieval["admitted_for_purpose"] = admitted_for_purpose
                retrieval["rejection_reasons"] = rejection_reasons
            if not admitted_for_purpose:
                rejected_count += 1
                continue
            scored.append(fact)

        scored.sort(
            key=lambda item: (
                float((item.get("retrieval_contract") or {}).get("rank_score") or 0.0),
                float(item.get("similarity") or 0.0),
            ),
            reverse=True,
        )
        results = scored[:top_k]
        retrieval_contract = _build_query_retrieval_contract(
            results=results,
            metadata_filters=metadata_filters,
            purpose=normalized_purpose,
            purpose_policy={
                **purpose_policy,
                "allowed_entry_kinds": sorted(purpose_policy.get("allowed_entry_kinds") or []),
            },
            rejected_count=rejected_count,
            invocation_gate=invocation_gate,
        )
        governed_hks_contract = _build_governed_hks_contract(
            query_text=query_text,
            results=results,
            purpose=normalized_purpose,
            purpose_policy={
                **purpose_policy,
                "allowed_entry_kinds": sorted(purpose_policy.get("allowed_entry_kinds") or []),
            },
            retrieval_contract=retrieval_contract,
        )

        # Update access stats
        if results:
            ids = [r["id"] for r in results]
            with self._connect() as conn:
                conn.executemany(
                    "UPDATE fact_store SET accessed_at=?, access_count=access_count+1 WHERE id=?",
                    [(now, rid) for rid in ids],
                )

        return {
            "results": results,
            "count": len(results),
            "query": query_text,
            "entry_kind": entry_kind,
            "domain": normalized_domain,
            "solution_kind": solution_kind,
            "include_stale": include_stale,
            "include_superseded": include_superseded,
            "include_revoked": include_revoked,
            "require_provenance": require_provenance,
            "include_archive": include_archive,
            "purpose": normalized_purpose,
            "retrieval_contract": retrieval_contract,
            "governed_hks_contract": governed_hks_contract,
        }

    def query_facts(
        self,
        *,
        entry_kind: str | None = None,
        topic: str | None = None,
        domain: str | None = None,
        solution_kind: str | None = None,
        profile: str | None = None,
        model: str | None = None,
        include_stale: bool = False,
        include_superseded: bool = False,
        include_revoked: bool = False,
        require_provenance: bool = False,
        include_archive: bool = False,
    ) -> list[dict[str, Any]]:
        normalized_domain = self._normalize_domain(domain)
        with self._connect() as conn:
            sql = (
                "SELECT id, sha256, content, topic, confidence, provenance, tags, "
                "created_at, accessed_at, entry_kind, domain, solution_kind, "
                "supersedes_sha256, metadata_json FROM fact_store WHERE 1=1"
            )
            params: list[Any] = []
            if entry_kind:
                sql += " AND entry_kind = ?"
                params.append(entry_kind)
            if topic:
                sql += " AND topic = ?"
                params.append(topic)
            if normalized_domain:
                sql += " AND domain = ?"
                params.append(normalized_domain)
            if solution_kind:
                sql += " AND solution_kind = ?"
                params.append(solution_kind)
            sql += " ORDER BY created_at DESC"
            superseded_hashes = self._superseded_hashes(conn)
            rows = conn.execute(sql, params).fetchall()

        now = time.time()
        results: list[dict[str, Any]] = []
        for row in rows:
            metadata = json.loads(row["metadata_json"] or "{}")
            if profile and str(metadata.get("profile_name") or "") != profile:
                continue
            if model and str(metadata.get("model") or metadata.get("model_name") or "") != model:
                continue
            evidence = self._build_evidence(
                row=row,
                metadata=metadata,
                superseded_hashes=superseded_hashes,
                now=now,
            )
            if not self._include_fact(
                evidence=evidence,
                include_stale=include_stale,
                include_superseded=include_superseded,
                include_revoked=include_revoked,
                require_provenance=require_provenance,
                include_archive=include_archive,
            ):
                continue
            results.append(self._row_to_fact(row=row, metadata=metadata, evidence=evidence))
        return results

    def all_facts(self) -> list[dict[str, Any]]:
        return self.query_facts(
            include_stale=True,
            include_superseded=True,
            include_revoked=True,
            include_archive=True,
        )

    # ── Merkle chain ──────────────────────────────────────────────────────────

    def _append_merkle(self, conn: sqlite3.Connection, topic: str, entry_hash: str) -> None:
        last = conn.execute(
            "SELECT entry_hash FROM merkle_chain WHERE topic=? ORDER BY id DESC LIMIT 1",
            (topic,),
        ).fetchone()
        prev_hash = last["entry_hash"] if last else ""
        chain_hash = hashlib.sha256(f"{prev_hash}{entry_hash}".encode()).hexdigest()
        conn.execute(
            "INSERT INTO merkle_chain (topic, prev_hash, entry_hash, created_at) VALUES (?,?,?,?)",
            (topic, prev_hash, chain_hash, time.time()),
        )

    # ── Stats ─────────────────────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """Return memory store statistics."""
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) AS n FROM fact_store").fetchone()["n"]
            exemplar_count = conn.execute(
                "SELECT COUNT(*) AS n FROM fact_store WHERE entry_kind = 'hks_exemplar'"
            ).fetchone()["n"]
            topics = conn.execute(
                "SELECT topic, COUNT(*) AS n FROM fact_store GROUP BY topic ORDER BY n DESC LIMIT 10"
            ).fetchall()
            domains = conn.execute(
                "SELECT domain, COUNT(*) AS n FROM fact_store WHERE domain != '' GROUP BY domain ORDER BY n DESC"
            ).fetchall()
            chain_depth = conn.execute("SELECT COUNT(*) AS n FROM merkle_chain").fetchone()["n"]
            metadata_rows = conn.execute("SELECT metadata_json FROM fact_store").fetchall()

        memory_strata = {stratum: 0 for stratum in sorted(HKS_MEMORY_STRATA)}
        storage_tiers = {tier: 0 for tier in sorted(HKS_STORAGE_TIERS)}
        artifact_forms = {artifact_form: 0 for artifact_form in sorted(HKS_ARTIFACT_FORMS)}
        source_authority_labels = {label: 0 for label in sorted(HKS_SOURCE_AUTHORITY_LABELS)}
        source_type_classifications: dict[str, int] = {}
        scored_capture_count = 0
        extraction_fidelity_total = 0.0
        for row in metadata_rows:
            metadata = json.loads(row["metadata_json"] or "{}")
            memory_stratum = str(metadata.get("memory_stratum") or "working")
            storage_tier = str(metadata.get("storage_tier") or "warm")
            artifact_form = str(metadata.get("artifact_form") or "raw_intake")
            source_authority_label = str(metadata.get("source_authority_label") or "advisory")
            source_capture = metadata.get("source_capture") if isinstance(metadata.get("source_capture"), dict) else {}
            source_type_classification = str(source_capture.get("source_type_classification") or "").strip()
            extraction_fidelity_score = _score_or_none(source_capture.get("extraction_fidelity_score"))
            if memory_stratum in memory_strata:
                memory_strata[memory_stratum] += 1
            if storage_tier in storage_tiers:
                storage_tiers[storage_tier] += 1
            if artifact_form in artifact_forms:
                artifact_forms[artifact_form] += 1
            if source_authority_label in source_authority_labels:
                source_authority_labels[source_authority_label] += 1
            if source_type_classification:
                source_type_classifications[source_type_classification] = (
                    source_type_classifications.get(source_type_classification, 0) + 1
                )
            if extraction_fidelity_score is not None:
                scored_capture_count += 1
                extraction_fidelity_total += extraction_fidelity_score

        return {
            "total_facts": total,
            "hks_exemplars": exemplar_count,
            "merkle_chain_depth": chain_depth,
            "hot_tier_topics": len(self._hot),
            "memory_strata": memory_strata,
            "storage_tiers": storage_tiers,
            "artifact_forms": artifact_forms,
            "source_authority_labels": source_authority_labels,
            "source_type_classifications": source_type_classifications,
            "average_extraction_fidelity_score": round(
                extraction_fidelity_total / scored_capture_count, 4
            )
            if scored_capture_count
            else None,
            "top_topics": [{"topic": r["topic"], "count": r["n"]} for r in topics],
            "domains": [{"domain": r["domain"], "count": r["n"]} for r in domains],
            "db_path": self._db_path,
        }

    # ── Decay pruning ─────────────────────────────────────────────────────────

    def prune_decay(self) -> int:
        """Prune facts older than DECAY_DAYS with low confidence."""
        cutoff = time.time() - (_DECAY_DAYS * 86400)
        with self._connect() as conn:
            result = conn.execute(
                "DELETE FROM fact_store WHERE created_at < ? AND confidence < 0.5",
                (cutoff,),
            )
            return result.rowcount

    def _normalize_domain(self, domain: str | None) -> str:
        if domain is None:
            return ""
        if domain not in HKS_DOMAINS:
            logger.warning("Unknown HKS domain %r — accepting but flagging", domain)
        return domain
