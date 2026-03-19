from __future__ import annotations

import uuid

from hlf_mcp import server
from hlf_mcp.rag.memory import HKSProvenance, HKSTestEvidence, HKSValidatedExemplar, RAGMemory


def test_rag_memory_store_exemplar_and_filter_by_domain() -> None:
    memory = RAGMemory()
    unique = uuid.uuid4().hex
    exemplar = HKSValidatedExemplar(
        problem=f"How to fix flaky retries {unique}",
        validated_solution="Bound retries, backoff, and assert final state.",
        domain="ai-engineering",
        solution_kind="repair-pattern",
        provenance=HKSProvenance(
            source_type="test",
            source="tests.test_hks_memory",
            collector="pytest",
            collected_at="2026-03-18T00:00:00+00:00",
        ),
        tests=[HKSTestEvidence(name="pytest", passed=True, exit_code=0, counts={"passed": 1})],
        tags=["retry", unique],
    )

    stored = memory.store_exemplar(exemplar)
    recalled = memory.query(unique, entry_kind="hks_exemplar", domain="ai-engineering")
    filtered_out = memory.query(unique, entry_kind="hks_exemplar", domain="general-coding")

    assert stored["stored"] is True
    assert recalled["count"] == 1
    assert recalled["results"][0]["domain"] == "ai-engineering"
    assert recalled["results"][0]["metadata"]["solution_kind"] == "repair-pattern"
    assert filtered_out["count"] == 0


def test_server_hks_capture_and_recall_round_trip() -> None:
    unique = uuid.uuid4().hex

    stored = server.hlf_hks_capture(
        problem=f"How to stabilize a compiler test {unique}",
        validated_solution="Use unique IDs and assert deterministic output.",
        domain="general-coding",
        solution_kind="test-pattern",
        tags=[unique],
        tests=[{"name": "pytest", "passed": True, "exit_code": 0, "counts": {"passed": 1}}],
    )
    recalled = server.hlf_hks_recall(unique, domain="general-coding", solution_kind="test-pattern")

    assert stored["stored"] is True
    assert stored["audit"]["event"] == "hlf_hks_capture"
    assert recalled["count"] >= 1
    assert any(result["entry_kind"] == "hks_exemplar" for result in recalled["results"])


def test_rag_memory_query_filters_superseded_entries_by_default() -> None:
    memory = RAGMemory()
    unique = uuid.uuid4().hex

    original = memory.store(
        f"repair pattern {unique}",
        topic="hlf_validated_exemplars",
        provenance="unit-test",
        entry_kind="hks_exemplar",
        domain="general-coding",
        solution_kind="repair-pattern",
        metadata={
            "governed_evidence": {
                "source_class": "hks_exemplar",
                "source_type": "test",
                "source": "tests.test_hks_memory",
                "collected_at": "2026-03-19T00:00:00+00:00",
            }
        },
    )
    replacement = memory.store(
        f"repair pattern {unique} replacement",
        topic="hlf_validated_exemplars",
        provenance="unit-test",
        entry_kind="hks_exemplar",
        domain="general-coding",
        solution_kind="repair-pattern",
        supersedes_sha256=str(original["sha256"]),
        metadata={
            "governed_evidence": {
                "source_class": "hks_exemplar",
                "source_type": "test",
                "source": "tests.test_hks_memory",
                "collected_at": "2026-03-19T00:00:01+00:00",
            }
        },
    )

    active = memory.query(unique, entry_kind="hks_exemplar", domain="general-coding")
    full_history = memory.query(
        unique,
        entry_kind="hks_exemplar",
        domain="general-coding",
        include_superseded=True,
    )

    assert replacement["stored"] is True
    assert active["count"] == 1
    assert active["results"][0]["sha256"] == replacement["sha256"]
    assert full_history["count"] == 2
    superseded = next(result for result in full_history["results"] if result["sha256"] == original["sha256"])
    assert superseded["evidence"]["superseded"] is True
    assert superseded["governance_status"] == "superseded"


def test_rag_memory_query_filters_stale_and_requires_evidence_backed_provenance() -> None:
    memory = RAGMemory()
    unique = uuid.uuid4().hex

    memory.store(
        f"plain fact {unique}",
        topic="general",
        provenance="agent",
    )
    memory.store(
        f"stale governed fact {unique}",
        topic="general",
        provenance="unit-test",
        metadata={
            "governed_evidence": {
                "source_class": "fact",
                "source_type": "test",
                "source": "tests.test_hks_memory",
                "source_path": f"artifact:{unique}",
                "collected_at": "2026-03-19T00:00:00+00:00",
                "fresh_until": "2000-01-01T00:00:00+00:00",
            }
        },
    )
    memory.store(
        f"fresh governed fact {unique}",
        topic="general",
        provenance="unit-test",
        metadata={
            "governed_evidence": {
                "source_class": "fact",
                "source_type": "test",
                "source": "tests.test_hks_memory",
                "source_path": f"artifact:{unique}:fresh",
                "collected_at": "2026-03-19T00:00:00+00:00",
                "fresh_until": "2999-01-01T00:00:00+00:00",
            }
        },
    )

    default_results = memory.query(unique)
    stale_results = memory.query(unique, include_stale=True)
    provenance_results = memory.query(unique, require_provenance=True)

    assert default_results["count"] == 2
    assert all(result["evidence"]["freshness_status"] == "fresh" for result in default_results["results"])
    assert stale_results["count"] == 3
    assert any(result["evidence"]["freshness_status"] == "stale" for result in stale_results["results"])
    assert provenance_results["count"] == 1
    assert provenance_results["results"][0]["evidence"]["provenance_grade"] == "evidence-backed"


def test_recorded_benchmark_artifact_exposes_memory_evidence() -> None:
    artifact = server.hlf_record_benchmark_artifact(
        profile_name=f"benchmark-{uuid.uuid4().hex[:8]}",
        benchmark_scores={"routing_quality": 0.91},
        topic="memory-evidence-roundtrip",
        details={"suite": "memory-governance"},
    )

    assert artifact["status"] == "ok"
    assert artifact["artifact"]["memory_ref"]["sha256"]
    assert artifact["artifact"]["memory_evidence"]["source_class"] == "benchmark_artifact"
    assert artifact["artifact"]["memory_evidence"]["provenance_grade"] == "evidence-backed"