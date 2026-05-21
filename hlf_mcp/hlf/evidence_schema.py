"""
Evidence Schema Normalization — canonical EvidenceRecord across all memory sources.

Normalizes evidence records from three heterogeneous sources into a single
canonical schema:

  - server_memory.py  (MCP tool output / decorated recall dicts)
  - rag/memory.py     (_build_evidence dicts)
  - hybrid_rag.py     (search result dicts)

Also provides staleness checking and record supersession.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

# ---------------------------------------------------------------------------
# Canonical Evidence Record
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class EvidenceRecord:
    """Canonical evidence record normalised from any memory source.

    All normalizer functions MUST produce this shape so downstream
    consumers (governance, dream cycle, audit) operate on a single
    schema regardless of provenance.
    """

    evidence_id: str  # UUID
    source: str  # "server_memory" | "rag" | "hybrid_rag" | "hks"
    artifact_type: str  # "benchmark" | "exemplar" | "route_trace" | "proof" | "memory_node"
    content_hash: str  # SHA-256 hex digest
    created_at: str  # ISO-8601 timestamp
    expires_at: str | None  # None = no expiry
    superseded_by: str | None  # evidence_id of replacement record
    provenance_chain: list[str]  # ordered list of evidence_ids leading to this record
    confidence: float  # 0.0 – 1.0
    metadata: dict[str, Any]  # source-specific enrichment
    is_stale: bool  # True if superseded or expired
    is_superseded: bool  # True if superseded_by is set

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "source": self.source,
            "artifact_type": self.artifact_type,
            "content_hash": self.content_hash,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "superseded_by": self.superseded_by,
            "provenance_chain": list(self.provenance_chain),
            "confidence": self.confidence,
            "metadata": dict(self.metadata),
            "is_stale": self.is_stale,
            "is_superseded": self.is_superseded,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_HKS_UUID_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # DNS namespace


def _deterministic_uuid(seed: str) -> str:
    """Generate a deterministic UUID v5 from a seed string."""
    return str(uuid.uuid5(_HKS_UUID_NAMESPACE, seed))


def _sha256(content: str) -> str:
    """SHA-256 hex digest of a string."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _now_iso() -> str:
    """Current UTC timestamp in ISO-8601."""
    return datetime.now(timezone.utc).isoformat()


def _coerce_float(val: Any, default: float = 0.0) -> float:
    """Safely coerce a value to float."""
    if val is None:
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _coerce_bool(val: Any) -> bool:
    """Safely coerce a value to bool."""
    if val is None:
        return False
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(val)
    if isinstance(val, str):
        return val.strip().lower() in {"true", "1", "yes", "y"}
    return bool(val)


def _is_past(iso_string: str | None) -> bool:
    """Return True if the ISO-8601 timestamp is in the past."""
    if iso_string is None:
        return False
    try:
        ts = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
        return ts < datetime.now(timezone.utc)
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# Artifact type mapping
# ---------------------------------------------------------------------------

# Maps entry_kind / artifact_kind values onto canonical artifact_type labels.
_ARTIFACT_TYPE_MAP: dict[str, str] = {
    "benchmark_artifact": "benchmark",
    "benchmark": "benchmark",
    "hks_exemplar": "exemplar",
    "exemplar": "exemplar",
    "governed_route": "route_trace",
    "route_trace": "route_trace",
    "governance_proof": "proof",
    "proof": "proof",
    "memory_node": "memory_node",
    "weekly_artifact": "benchmark",
    "fact": "memory_node",
    "evidence": "memory_node",
    "dream_finding": "memory_node",
    "dream_cycle": "memory_node",
    "governed_recall": "memory_node",
    "internal_workflow": "memory_node",
    "execution_admission": "memory_node",
    "witness_observation": "memory_node",
    "media_evidence": "memory_node",
    "translation_contract": "memory_node",
    "symbolic_surface": "memory_node",
}


def _map_artifact_type(kind: str | None) -> str:
    """Map an entry_kind / artifact_kind to canonical artifact_type."""
    if not kind:
        return "memory_node"
    return _ARTIFACT_TYPE_MAP.get(str(kind).strip().lower(), "memory_node")


# ---------------------------------------------------------------------------
# Normalizers
# ---------------------------------------------------------------------------


def normalize_server_memory_record(raw: dict[str, Any]) -> EvidenceRecord:
    """Normalize a server_memory.py output dict into a canonical EvidenceRecord.

    Handles the decorated recall dict from ``_decorate_recalled_facts`` and the
    store result dict from ``hlf_memory_store``.
    """
    # ── content hash ──────────────────────────────────────────────────
    content_hash = str(raw.get("sha256") or raw.get("content_hash") or "")
    if not content_hash and raw.get("content"):
        content_hash = _sha256(str(raw["content"]))
    if not content_hash and raw.get("pointer"):
        # pointer format: <&alias:SHA256:digest>
        pointer = str(raw["pointer"])
        parts = pointer.split(":")
        if len(parts) >= 3:
            content_hash = parts[2].rstrip(">")

    # ── evidence_id ───────────────────────────────────────────────────
    raw_id = raw.get("evidence_id") or raw.get("id")
    evidence_id = ""
    if raw_id is not None:
        raw_id_str = str(raw_id)
        # Only accept as evidence_id if it looks like a UUID.
        try:
            uuid.UUID(raw_id_str)
            evidence_id = raw_id_str
        except (ValueError, AttributeError):
            pass
    if not evidence_id:
        evidence_id = _deterministic_uuid(f"server_memory:{content_hash}" if content_hash else f"server_memory:{_now_iso()}")

    # ── metadata sub-blocks ───────────────────────────────────────────
    evidence_block = raw.get("evidence") if isinstance(raw.get("evidence"), dict) else {}
    evaluation_block = raw.get("evaluation") if isinstance(raw.get("evaluation"), dict) else {}
    governed_block = raw.get("governed_evidence") if isinstance(raw.get("governed_evidence"), dict) else {}
    source_capture = raw.get("source_capture") if isinstance(raw.get("source_capture"), dict) else {}
    pointer_entry = raw.get("pointer_entry") if isinstance(raw.get("pointer_entry"), dict) else {}

    # ── artifact_type ─────────────────────────────────────────────────
    artifact_kind = str(
        raw.get("artifact_kind")
        or governed_block.get("artifact_kind")
        or raw.get("entry_kind")
        or "memory_node"
    )
    artifact_type = _map_artifact_type(artifact_kind)

    # ── created_at ────────────────────────────────────────────────────
    created_at = str(
        raw.get("created_at")
        or source_capture.get("freshness_marker")
        or _now_iso()
    )

    # ── expires_at ────────────────────────────────────────────────────
    expires_at = raw.get("fresh_until") or governed_block.get("fresh_until") or None
    if expires_at is not None:
        expires_at = str(expires_at)

    # ── superseded / stale ────────────────────────────────────────────
    superseded_by: str | None = None
    supersedes = raw.get("supersedes") or evidence_block.get("supersedes") or ""
    if supersedes:
        superseded_by = _deterministic_uuid(f"server_memory:{supersedes}")

    is_superseded = _coerce_bool(
        raw.get("superseded") or evidence_block.get("superseded")
    )
    if is_superseded and not superseded_by:
        superseded_by = evidence_block.get("superseded_by") or "unknown"

    is_stale = (
        is_superseded
        or _coerce_bool(raw.get("revoked") or evidence_block.get("revoked"))
        or _coerce_bool(raw.get("tombstoned") or evidence_block.get("tombstoned"))
        or (evidence_block.get("freshness_status") == "stale")
        or _is_past(expires_at)
    )

    # ── provenance_chain ──────────────────────────────────────────────
    provenance_chain: list[str] = list(
        raw.get("provenance_chain") or [evidence_id]
    )

    # ── confidence ────────────────────────────────────────────────────
    confidence = _coerce_float(
        raw.get("confidence") or governed_block.get("confidence") or 1.0
    )
    confidence = max(0.0, min(1.0, confidence))

    # ── metadata ──────────────────────────────────────────────────────
    metadata: dict[str, Any] = {
        "topic": raw.get("topic", ""),
        "provenance": raw.get("provenance", "agent"),
        "entry_kind": artifact_kind,
        "pointer": raw.get("pointer"),
        "pointer_alias": pointer_entry.get("alias") or raw.get("pointer_alias"),
        "evidence_block": evidence_block,
        "evaluation_block": evaluation_block,
        "governed_evidence": governed_block,
        "source_capture": source_capture,
        "promotion_eligible": evaluation_block.get("promotion_eligible", False),
        "freshness_status": evidence_block.get("freshness_status", "fresh"),
        "provenance_grade": evidence_block.get("provenance_grade", "basic"),
        "revoked": _coerce_bool(raw.get("revoked") or evidence_block.get("revoked")),
        "tombstoned": _coerce_bool(raw.get("tombstoned") or evidence_block.get("tombstoned")),
    }

    return EvidenceRecord(
        evidence_id=evidence_id,
        source="server_memory",
        artifact_type=artifact_type,
        content_hash=content_hash,
        created_at=created_at,
        expires_at=expires_at,
        superseded_by=superseded_by,
        provenance_chain=provenance_chain,
        confidence=confidence,
        metadata=metadata,
        is_stale=is_stale,
        is_superseded=is_superseded,
    )


def normalize_rag_record(raw: dict[str, Any]) -> EvidenceRecord:
    """Normalize a rag/memory.py ``_build_evidence`` dict into a canonical EvidenceRecord."""
    # ── content hash ──────────────────────────────────────────────────
    content_hash = str(raw.get("sha256") or raw.get("content_hash") or raw.get("current_content_hash") or "")
    if not content_hash and raw.get("content"):
        content_hash = _sha256(str(raw["content"]))

    # ── evidence_id ───────────────────────────────────────────────────
    evidence_id = str(raw.get("evidence_id") or raw.get("artifact_id") or "")
    if not evidence_id:
        evidence_id = _deterministic_uuid(f"rag:{content_hash}" if content_hash else f"rag:{_now_iso()}")

    # ── artifact_type ─────────────────────────────────────────────────
    entry_kind = str(raw.get("entry_kind") or raw.get("source_class") or "")
    artifact_type = _map_artifact_type(entry_kind)

    # ── created_at ────────────────────────────────────────────────────
    created_at = str(
        raw.get("created_at")
        or raw.get("collected_at")
        or _now_iso()
    )

    # ── expires_at ────────────────────────────────────────────────────
    expires_at = raw.get("fresh_until") or None
    if expires_at is not None:
        expires_at = str(expires_at)

    # ── superseded / stale ────────────────────────────────────────────
    supersedes_raw = raw.get("supersedes") or ""
    superseded_by: str | None = None
    if supersedes_raw:
        superseded_by = _deterministic_uuid(f"rag:{supersedes_raw}")

    is_superseded = _coerce_bool(raw.get("superseded"))
    if is_superseded and not superseded_by:
        superseded_by = raw.get("superseded_by") or "unknown"

    state = str(raw.get("state") or "active").lower()
    is_stale = (
        is_superseded
        or state in {"stale", "superseded", "revoked", "tombstoned", "tampered"}
        or _coerce_bool(raw.get("revoked"))
        or _coerce_bool(raw.get("tombstoned"))
        or str(raw.get("freshness_status") or "") == "stale"
        or _is_past(expires_at)
        or not _coerce_bool(raw.get("content_hash_valid", True))
    )

    # ── provenance_chain ──────────────────────────────────────────────
    provenance_chain: list[str] = list(
        raw.get("provenance_chain") or [evidence_id]
    )

    # ── confidence ────────────────────────────────────────────────────
    confidence = _coerce_float(raw.get("confidence"), 1.0)
    confidence = max(0.0, min(1.0, confidence))

    # ── metadata ──────────────────────────────────────────────────────
    metadata: dict[str, Any] = {
        "topic": raw.get("topic", ""),
        "domain": raw.get("domain", ""),
        "solution_kind": raw.get("solution_kind", ""),
        "entry_kind": entry_kind,
        "source_type": raw.get("source_type", ""),
        "source": raw.get("source", ""),
        "source_path": raw.get("source_path", ""),
        "artifact_id": raw.get("artifact_id", ""),
        "workflow_run_url": raw.get("workflow_run_url", ""),
        "branch": raw.get("branch", ""),
        "commit_sha": raw.get("commit_sha", ""),
        "collector": raw.get("collector", ""),
        "collector_version": raw.get("collector_version", ""),
        "collected_at": raw.get("collected_at", ""),
        "trust_tier": raw.get("trust_tier", "local"),
        "trusted_for_governance": raw.get("trusted_for_governance", False),
        "freshness_status": raw.get("freshness_status", "fresh"),
        "content_hash_valid": raw.get("content_hash_valid", True),
        "integrity_status": raw.get("integrity_status", "ok"),
        "revoked": _coerce_bool(raw.get("revoked")),
        "tombstoned": _coerce_bool(raw.get("tombstoned")),
        "state": state,
        "operator_summary": raw.get("operator_summary", ""),
        "operator_identity": raw.get("operator_identity", {}),
        "memory_stratum": raw.get("memory_stratum", "working"),
        "storage_tier": raw.get("storage_tier", "warm"),
        "salience_score": _coerce_float(raw.get("salience_score")),
        "admission_decision": raw.get("admission_decision", "active"),
        "provenance_grade": raw.get("provenance_grade", "basic"),
        "provenance_available": raw.get("provenance_available", False),
        "source_lineage_present": raw.get("source_lineage_present", False),
        "source_lineage_hash": raw.get("source_lineage_hash", ""),
        "source_lineage": raw.get("source_lineage", {}),
        "evaluation_id": raw.get("evaluation_id", ""),
        "evaluation_authority": raw.get("evaluation_authority", ""),
        "explicit_local_evaluation_present": raw.get("explicit_local_evaluation_present", False),
        "promotion_eligible": raw.get("promotion_eligible", False),
        "citation_coverage": raw.get("citation_coverage"),
        "groundedness": raw.get("groundedness"),
        "source_authority_label": raw.get("source_authority_label", "advisory"),
        "source_capture": raw.get("source_capture", {}),
        "artifact_contract": raw.get("artifact_contract", {}),
    }

    return EvidenceRecord(
        evidence_id=evidence_id,
        source="rag",
        artifact_type=artifact_type,
        content_hash=content_hash,
        created_at=created_at,
        expires_at=expires_at,
        superseded_by=superseded_by,
        provenance_chain=provenance_chain,
        confidence=confidence,
        metadata=metadata,
        is_stale=is_stale,
        is_superseded=is_superseded,
    )


def normalize_hybrid_rag_record(raw: dict[str, Any]) -> EvidenceRecord:
    """Normalize a hybrid_rag.py search result dict into a canonical EvidenceRecord."""
    # ── doc_id → evidence parts ───────────────────────────────────────
    doc_id = str(raw.get("doc_id") or "")
    inner_meta = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}

    # ── content hash ──────────────────────────────────────────────────
    # Hybrid RAG results may embed sha256 in doc_id or inner metadata.
    content_hash = str(
        inner_meta.get("sha256")
        or inner_meta.get("content_hash")
        or raw.get("sha256")
        or raw.get("content_hash")
        or ""
    )
    text = str(raw.get("text") or "")
    if not content_hash and text:
        content_hash = _sha256(text)
    if not content_hash and doc_id:
        content_hash = _sha256(doc_id)

    # ── evidence_id ───────────────────────────────────────────────────
    evidence_id = str(
        inner_meta.get("evidence_id")
        or inner_meta.get("artifact_id")
        or raw.get("evidence_id")
        or ""
    )
    if not evidence_id:
        evidence_id = _deterministic_uuid(f"hybrid_rag:{content_hash}" if content_hash else f"hybrid_rag:{doc_id}")

    # ── artifact_type ─────────────────────────────────────────────────
    artifact_type = _map_artifact_type(
        inner_meta.get("entry_kind")
        or inner_meta.get("artifact_kind")
        or inner_meta.get("source_class")
    )

    # ── created_at ────────────────────────────────────────────────────
    created_at = str(
        inner_meta.get("created_at")
        or inner_meta.get("collected_at")
        or raw.get("created_at")
        or _now_iso()
    )

    # ── expires_at ────────────────────────────────────────────────────
    expires_at = (
        inner_meta.get("fresh_until")
        or inner_meta.get("expires_at")
        or raw.get("fresh_until")
    )

    # ── superseded / stale ────────────────────────────────────────────
    superseded_by: str | None = None
    supersedes_raw = inner_meta.get("supersedes") or raw.get("supersedes") or ""
    if supersedes_raw:
        superseded_by = _deterministic_uuid(f"hybrid_rag:{supersedes_raw}")

    is_superseded = _coerce_bool(
        inner_meta.get("superseded") or raw.get("superseded")
    )
    if is_superseded and not superseded_by:
        superseded_by = inner_meta.get("superseded_by") or "unknown"

    is_stale = (
        is_superseded
        or _coerce_bool(inner_meta.get("revoked") or raw.get("revoked"))
        or _coerce_bool(inner_meta.get("tombstoned") or raw.get("tombstoned"))
        or str(inner_meta.get("freshness_status") or "") == "stale"
        or _is_past(expires_at)
    )

    # ── provenance_chain ──────────────────────────────────────────────
    provenance_chain: list[str] = list(
        inner_meta.get("provenance_chain")
        or raw.get("provenance_chain")
        or [evidence_id]
    )

    # ── confidence ────────────────────────────────────────────────────
    confidence = _coerce_float(
        inner_meta.get("confidence") or raw.get("score") or raw.get("confidence") or 0.5
    )
    confidence = max(0.0, min(1.0, confidence))

    # ── metadata ──────────────────────────────────────────────────────
    metadata: dict[str, Any] = {
        "doc_id": doc_id,
        "text": text,
        "score": raw.get("score"),
        "bm25_score": raw.get("bm25_score"),
        "vector_score": raw.get("vector_score"),
        "inner_metadata": inner_meta,
        "source_type": inner_meta.get("source_type") or raw.get("source_type", ""),
        "topic": inner_meta.get("topic") or raw.get("topic", ""),
        "entry_kind": inner_meta.get("entry_kind") or raw.get("entry_kind", ""),
        "promotion_eligible": inner_meta.get("promotion_eligible", False),
        "provenance_grade": inner_meta.get("provenance_grade", "basic"),
        "freshness_status": inner_meta.get("freshness_status", "fresh"),
    }

    return EvidenceRecord(
        evidence_id=evidence_id,
        source="hybrid_rag",
        artifact_type=artifact_type,
        content_hash=content_hash,
        created_at=created_at,
        expires_at=expires_at,
        superseded_by=superseded_by,
        provenance_chain=provenance_chain,
        confidence=confidence,
        metadata=metadata,
        is_stale=is_stale,
        is_superseded=is_superseded,
    )


# ---------------------------------------------------------------------------
# Staleness & supersession
# ---------------------------------------------------------------------------


def check_staleness(record: EvidenceRecord) -> EvidenceRecord:
    """Evaluate and update staleness flags on a canonical EvidenceRecord.

    Sets ``is_stale`` to True if:
      - ``expires_at`` is in the past, or
      - ``superseded_by`` is set (non-None).

    Returns the same record instance (mutated in place for convenience).
    """
    expired = _is_past(record.expires_at)
    superseded = record.superseded_by is not None and record.superseded_by != ""

    record.is_superseded = superseded
    record.is_stale = expired or superseded
    return record


def supersede_record(old: EvidenceRecord, new_id: str) -> EvidenceRecord:
    """Mark *old* as superseded by *new_id* and return the updated record.

    Appends *new_id* to the provenance chain so downstream consumers can
    trace the full lineage.

    Returns the mutated *old* record.
    """
    old.superseded_by = new_id
    old.is_superseded = True
    old.is_stale = True
    if new_id not in old.provenance_chain:
        old.provenance_chain.append(new_id)
    return old
