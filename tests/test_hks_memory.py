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