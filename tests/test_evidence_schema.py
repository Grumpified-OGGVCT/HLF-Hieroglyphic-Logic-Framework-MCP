"""Tests for hlf_mcp.hlf.evidence_schema — canonical EvidenceRecord normalisation."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from hlf_mcp.hlf.evidence_schema import (
    EvidenceRecord,
    check_staleness,
    normalize_hybrid_rag_record,
    normalize_rag_record,
    normalize_server_memory_record,
    supersede_record,
    _sha256,
)


# ═══════════════════════════════════════════════════════════════════════════
# Raw record factories
# ═══════════════════════════════════════════════════════════════════════════

def _server_memory_raw(**overrides) -> dict:
    """Build a realistic server_memory.py decorated recall / store dict."""
    base: dict = {
        "sha256": _sha256("server-memory-test-content"),
        "id": 42,
        "content": "server-memory-test-content",
        "topic": "test-topic",
        "confidence": 0.95,
        "provenance": "agent",
        "entry_kind": "hks_exemplar",
        "artifact_kind": "hks_exemplar",
        "created_at": "2026-01-15T10:30:00+00:00",
        "fresh_until": "2027-01-15T10:30:00+00:00",
        "superseded": False,
        "revoked": False,
        "tombstoned": False,
        "pointer": "<&test-topic-42:SHA256:abcdef1234567890>",
        "pointer_alias": "test-topic-42",
        "evidence": {
            "pointer": "<&test-topic-42:SHA256:abcdef1234567890>",
            "pointer_alias": "test-topic-42",
            "provenance_grade": "evidence-backed",
            "freshness_status": "fresh",
            "superseded": False,
            "revoked": False,
            "tombstoned": False,
        },
        "evaluation": {
            "promotion_eligible": True,
            "requires_local_recheck": False,
            "authority": "test-authority",
        },
        "source_capture": {
            "source_type_classification": "exemplar",
            "source_authority_label": "canonical",
            "source_version": "1.0",
            "freshness_marker": "2026-01-15T10:30:00+00:00",
        },
        "governed_evidence": {
            "source_type": "hks_exemplar",
            "source_authority_label": "canonical",
            "artifact_form": "canonical_knowledge",
            "artifact_kind": "hks_exemplar",
            "fresh_until": "2027-01-15T10:30:00+00:00",
        },
    }
    base.update(overrides)
    return base


def _rag_raw(**overrides) -> dict:
    """Build a realistic rag/memory.py _build_evidence dict."""
    base: dict = {
        "sha256": _sha256("rag-memory-test-content"),
        "content": "rag-memory-test-content",
        "entry_kind": "benchmark_artifact",
        "topic": "benchmark-topic",
        "domain": "performance",
        "solution_kind": "optimization",
        "source_class": "benchmark_artifact",
        "source_type": "build_evidence",
        "source": "ci-pipeline",
        "source_path": "/artifacts/benchmark-42.json",
        "artifact_id": "bench-art-42",
        "workflow_run_url": "https://ci.example.com/runs/42",
        "branch": "main",
        "commit_sha": "abc123def456",
        "collector": "hlf-collector",
        "collector_version": "1.2.3",
        "collected_at": "2026-01-15T10:30:00+00:00",
        "created_at": "2026-01-15T10:30:00+00:00",
        "accessed_at": "2026-01-15T11:00:00+00:00",
        "confidence": 0.88,
        "trust_tier": "trusted",
        "trusted_for_governance": True,
        "fresh_until": "2027-01-15T10:30:00+00:00",
        "freshness_status": "fresh",
        "content_hash_valid": True,
        "current_content_hash": _sha256("rag-memory-test-content"),
        "integrity_status": "ok",
        "revoked": False,
        "tombstoned": False,
        "supersedes": "",
        "superseded": False,
        "state": "active",
        "operator_summary": "Benchmark run passed",
        "operator_identity": {},
        "memory_stratum": "semantic",
        "storage_tier": "hot",
        "salience_score": 0.75,
        "admission_decision": "active",
        "provenance_grade": "evidence-backed",
        "provenance_available": True,
        "source_lineage_present": True,
        "source_lineage_hash": "lineage-hash-123",
        "source_lineage": {},
        "evaluation_id": "eval-42",
        "evaluation_authority": "ci-system",
        "explicit_local_evaluation_present": True,
        "promotion_eligible": True,
        "citation_coverage": 0.9,
        "groundedness": 0.85,
        "source_authority_label": "canonical",
        "source_capture": {},
        "artifact_contract": {},
    }
    base.update(overrides)
    return base


def _hybrid_rag_raw(**overrides) -> dict:
    """Build a realistic hybrid_rag.py search result dict."""
    base: dict = {
        "doc_id": "hybrid-doc-42",
        "text": "Hybrid RAG search result text about benchmark improvements",
        "score": 0.91,
        "bm25_score": 0.85,
        "vector_score": 0.93,
        "metadata": {
            "sha256": _sha256("hybrid-rag-test-content"),
            "entry_kind": "benchmark_artifact",
            "artifact_kind": "benchmark_artifact",
            "topic": "hybrid-topic",
            "confidence": 0.87,
            "created_at": "2026-01-15T10:30:00+00:00",
            "fresh_until": "2027-01-15T10:30:00+00:00",
            "provenance_grade": "evidence-backed",
            "freshness_status": "fresh",
            "superseded": False,
            "revoked": False,
            "tombstoned": False,
            "promotion_eligible": True,
            "source_type": "hybrid_search",
        },
    }
    base.update(overrides)
    return base


# ═══════════════════════════════════════════════════════════════════════════
# Test: normalize_server_memory_record
# ═══════════════════════════════════════════════════════════════════════════


def test_normalize_server_memory_record_produces_valid_evidence_record() -> None:
    """normalize_server_memory_record produces a valid EvidenceRecord with all required fields."""
    raw = _server_memory_raw()
    record = normalize_server_memory_record(raw)

    assert isinstance(record, EvidenceRecord)
    assert record.source == "server_memory"
    assert record.artifact_type == "exemplar"  # hks_exemplar → exemplar
    assert record.content_hash == _sha256("server-memory-test-content")
    assert record.created_at == "2026-01-15T10:30:00+00:00"
    assert record.expires_at == "2027-01-15T10:30:00+00:00"
    assert record.confidence == 0.95
    assert record.is_stale is False
    assert record.is_superseded is False
    assert record.superseded_by is None
    assert len(record.provenance_chain) >= 1
    assert record.provenance_chain[0] == record.evidence_id
    assert isinstance(record.metadata, dict)
    assert record.metadata["topic"] == "test-topic"


# ═══════════════════════════════════════════════════════════════════════════
# Test: normalize_rag_record
# ═══════════════════════════════════════════════════════════════════════════


def test_normalize_rag_record_produces_valid_evidence_record() -> None:
    """normalize_rag_record produces a valid EvidenceRecord with all required fields."""
    raw = _rag_raw()
    record = normalize_rag_record(raw)

    assert isinstance(record, EvidenceRecord)
    assert record.source == "rag"
    assert record.artifact_type == "benchmark"  # benchmark_artifact → benchmark
    assert record.content_hash == _sha256("rag-memory-test-content")
    assert record.created_at == "2026-01-15T10:30:00+00:00"
    assert record.expires_at == "2027-01-15T10:30:00+00:00"
    assert record.confidence == 0.88
    assert record.is_stale is False
    assert record.is_superseded is False
    assert record.superseded_by is None
    assert len(record.provenance_chain) >= 1
    assert isinstance(record.metadata, dict)
    assert record.metadata["domain"] == "performance"
    assert record.metadata["trust_tier"] == "trusted"


# ═══════════════════════════════════════════════════════════════════════════
# Test: normalize_hybrid_rag_record
# ═══════════════════════════════════════════════════════════════════════════


def test_normalize_hybrid_rag_record_produces_valid_evidence_record() -> None:
    """normalize_hybrid_rag_record produces a valid EvidenceRecord with all required fields."""
    raw = _hybrid_rag_raw()
    record = normalize_hybrid_rag_record(raw)

    assert isinstance(record, EvidenceRecord)
    assert record.source == "hybrid_rag"
    assert record.artifact_type == "benchmark"
    assert record.content_hash == _sha256("hybrid-rag-test-content")
    assert record.created_at == "2026-01-15T10:30:00+00:00"
    assert record.expires_at == "2027-01-15T10:30:00+00:00"
    assert record.confidence == 0.87
    assert record.is_stale is False
    assert record.is_superseded is False
    assert record.superseded_by is None
    assert len(record.provenance_chain) >= 1
    assert isinstance(record.metadata, dict)
    assert record.metadata["doc_id"] == "hybrid-doc-42"
    assert record.metadata["score"] == 0.91
    assert record.metadata["bm25_score"] == 0.85
    assert record.metadata["vector_score"] == 0.93


# ═══════════════════════════════════════════════════════════════════════════
# Test: all three normalizers produce records with same canonical shape
# ═══════════════════════════════════════════════════════════════════════════


def test_all_normalizers_produce_same_canonical_shape() -> None:
    """All three normalizers produce EvidenceRecord instances with the same canonical shape."""
    sm = normalize_server_memory_record(_server_memory_raw())
    rag = normalize_rag_record(_rag_raw())
    hr = normalize_hybrid_rag_record(_hybrid_rag_raw())

    for record in (sm, rag, hr):
        assert isinstance(record, EvidenceRecord)
        assert isinstance(record.evidence_id, str)
        assert record.source in {"server_memory", "rag", "hybrid_rag", "hks"}
        assert isinstance(record.artifact_type, str)
        assert isinstance(record.content_hash, str)
        assert isinstance(record.created_at, str)
        # expires_at may be None or str
        assert record.expires_at is None or isinstance(record.expires_at, str)
        assert record.superseded_by is None or isinstance(record.superseded_by, str)
        assert isinstance(record.provenance_chain, list)
        assert isinstance(record.confidence, float)
        assert 0.0 <= record.confidence <= 1.0
        assert isinstance(record.metadata, dict)
        assert isinstance(record.is_stale, bool)
        assert isinstance(record.is_superseded, bool)


# ═══════════════════════════════════════════════════════════════════════════
# Test: check_staleness
# ═══════════════════════════════════════════════════════════════════════════


def test_check_staleness_detects_expired_record() -> None:
    """check_staleness sets is_stale=True when expires_at is in the past."""
    past = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    record = EvidenceRecord(
        evidence_id=str(uuid.uuid4()),
        source="server_memory",
        artifact_type="memory_node",
        content_hash=_sha256("stale-content"),
        created_at="2025-01-01T00:00:00+00:00",
        expires_at=past,
        superseded_by=None,
        provenance_chain=["chain-1"],
        confidence=0.9,
        metadata={},
        is_stale=False,
        is_superseded=False,
    )

    result = check_staleness(record)
    assert result.is_stale is True
    assert result.is_superseded is False  # not superseded, just expired


def test_check_staleness_detects_superseded_record() -> None:
    """check_staleness sets is_stale=True and is_superseded=True when superseded_by is set."""
    record = EvidenceRecord(
        evidence_id=str(uuid.uuid4()),
        source="rag",
        artifact_type="benchmark",
        content_hash=_sha256("superseded-content"),
        created_at="2026-01-01T00:00:00+00:00",
        expires_at="2027-01-01T00:00:00+00:00",  # not expired
        superseded_by="newer-evidence-id",
        provenance_chain=["chain-1"],
        confidence=0.8,
        metadata={},
        is_stale=False,
        is_superseded=False,
    )

    result = check_staleness(record)
    assert result.is_stale is True
    assert result.is_superseded is True


def test_check_staleness_passes_fresh_record() -> None:
    """check_staleness leaves is_stale=False for a fresh, non-superseded record."""
    future = (datetime.now(timezone.utc) + timedelta(days=365)).isoformat()
    record = EvidenceRecord(
        evidence_id=str(uuid.uuid4()),
        source="hybrid_rag",
        artifact_type="exemplar",
        content_hash=_sha256("fresh-content"),
        created_at="2026-01-01T00:00:00+00:00",
        expires_at=future,
        superseded_by=None,
        provenance_chain=["chain-1"],
        confidence=0.95,
        metadata={},
        is_stale=False,
        is_superseded=False,
    )

    result = check_staleness(record)
    assert result.is_stale is False
    assert result.is_superseded is False


# ═══════════════════════════════════════════════════════════════════════════
# Test: supersede_record
# ═══════════════════════════════════════════════════════════════════════════


def test_supersede_record_sets_superseded_by_and_is_stale() -> None:
    """supersede_record sets superseded_by, is_superseded=True, is_stale=True."""
    new_id = str(uuid.uuid4())
    record = EvidenceRecord(
        evidence_id="old-record-1",
        source="rag",
        artifact_type="memory_node",
        content_hash=_sha256("old-content"),
        created_at="2025-01-01T00:00:00+00:00",
        expires_at=None,
        superseded_by=None,
        provenance_chain=["old-record-1"],
        confidence=0.7,
        metadata={},
        is_stale=False,
        is_superseded=False,
    )

    result = supersede_record(record, new_id)
    assert result.superseded_by == new_id
    assert result.is_superseded is True
    assert result.is_stale is True


def test_supersede_record_preserves_provenance_chain() -> None:
    """supersede_record appends the new_id to provenance_chain without losing existing entries."""
    existing_chain = ["old-record-1", "old-record-2"]
    new_id = str(uuid.uuid4())
    record = EvidenceRecord(
        evidence_id="old-record-1",
        source="rag",
        artifact_type="memory_node",
        content_hash=_sha256("chain-test"),
        created_at="2025-01-01T00:00:00+00:00",
        expires_at=None,
        superseded_by=None,
        provenance_chain=list(existing_chain),
        confidence=0.5,
        metadata={},
        is_stale=False,
        is_superseded=False,
    )

    result = supersede_record(record, new_id)

    # Original chain entries preserved
    for entry in existing_chain:
        assert entry in result.provenance_chain
    # New id appended
    assert new_id in result.provenance_chain
    assert result.provenance_chain[-1] == new_id


# ═══════════════════════════════════════════════════════════════════════════
# Test: evidence_id uniqueness
# ═══════════════════════════════════════════════════════════════════════════


def test_evidence_id_is_unique_per_record() -> None:
    """Each normalized record from a different source gets a unique evidence_id."""
    sm = normalize_server_memory_record(_server_memory_raw())
    rag = normalize_rag_record(_rag_raw())
    hr = normalize_hybrid_rag_record(_hybrid_rag_raw())

    ids = {sm.evidence_id, rag.evidence_id, hr.evidence_id}
    assert len(ids) == 3, f"Expected 3 unique evidence_ids, got {len(ids)}"


def test_evidence_id_is_uuid_format() -> None:
    """evidence_id should be a valid UUID string."""
    sm = normalize_server_memory_record(_server_memory_raw())
    # Parse as UUID — should not raise
    parsed = uuid.UUID(sm.evidence_id)
    assert parsed.version == 5  # UUID v5 (deterministic, namespace-based)


# ═══════════════════════════════════════════════════════════════════════════
# Test: content_hash is present
# ═══════════════════════════════════════════════════════════════════════════


def test_content_hash_is_present_in_all_normalizers() -> None:
    """Every normalized record has a non-empty, 64-char hex content_hash."""
    records = [
        normalize_server_memory_record(_server_memory_raw()),
        normalize_rag_record(_rag_raw()),
        normalize_hybrid_rag_record(_hybrid_rag_raw()),
    ]

    for record in records:
        assert record.content_hash, f"{record.source} record has empty content_hash"
        assert len(record.content_hash) == 64, (
            f"{record.source} content_hash length is {len(record.content_hash)}, expected 64"
        )
        # Should be valid hex
        int(record.content_hash, 16)


# ═══════════════════════════════════════════════════════════════════════════
# Edge case tests
# ═══════════════════════════════════════════════════════════════════════════


def test_normalize_server_memory_handles_minimal_dict() -> None:
    """normalize_server_memory_record handles a minimal dict without crashing."""
    minimal: dict = {"content": "minimal content"}
    record = normalize_server_memory_record(minimal)
    assert isinstance(record, EvidenceRecord)
    assert record.source == "server_memory"
    assert record.content_hash == _sha256("minimal content")


def test_normalize_rag_handles_minimal_dict() -> None:
    """normalize_rag_record handles a minimal dict without crashing."""
    minimal: dict = {"sha256": _sha256("minimal rag"), "content": "minimal rag"}
    record = normalize_rag_record(minimal)
    assert isinstance(record, EvidenceRecord)
    assert record.source == "rag"


def test_normalize_hybrid_rag_handles_minimal_dict() -> None:
    """normalize_hybrid_rag_record handles a minimal dict without crashing."""
    minimal: dict = {"doc_id": "doc-1", "text": "minimal hybrid"}
    record = normalize_hybrid_rag_record(minimal)
    assert isinstance(record, EvidenceRecord)
    assert record.source == "hybrid_rag"


def test_confidence_clamped_to_0_1_range() -> None:
    """Confidence values outside [0, 1] are clamped."""
    raw = _rag_raw(confidence=2.5)
    record = normalize_rag_record(raw)
    assert record.confidence == 1.0

    raw2 = _rag_raw(confidence=-0.5)
    record2 = normalize_rag_record(raw2)
    assert record2.confidence == 0.0
