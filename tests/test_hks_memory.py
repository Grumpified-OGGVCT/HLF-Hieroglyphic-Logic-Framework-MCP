from __future__ import annotations

import uuid
from pathlib import Path

import pytest

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
        evaluation={
            "authority": "local_hks",
            "groundedness": 1.0,
            "citation_coverage": 1.0,
            "freshness_verdict": "fresh",
            "provenance_verdict": "evidence-backed",
            "promotion_eligible": True,
            "operator_summary": "Local HKS validated this retry repair exemplar.",
        },
    )

    stored = memory.store_exemplar(exemplar)
    recalled = memory.query(unique, entry_kind="hks_exemplar", domain="ai-engineering")
    filtered_out = memory.query(unique, entry_kind="hks_exemplar", domain="general-coding")

    assert stored["stored"] is True
    assert stored["evaluation"]["authority"] == "local_hks"
    assert stored["evaluation"]["explicit_local_evaluation_present"] is True
    assert stored["evaluation"]["promotion_eligible"] is True
    assert stored["memory_stratum"] == "semantic"
    assert stored["storage_tier"] == "warm"
    assert recalled["count"] == 1
    assert recalled["results"][0]["domain"] == "ai-engineering"
    assert recalled["results"][0]["metadata"]["solution_kind"] == "repair-pattern"
    assert recalled["results"][0]["evaluation"]["authority"] == "local_hks"
    assert recalled["results"][0]["evaluation"]["explicit_local_evaluation_present"] is True
    assert recalled["results"][0]["evaluation"]["promotion_eligible"] is True
    assert recalled["results"][0]["memory_stratum"] == "semantic"
    assert recalled["results"][0]["evidence"]["memory_stratum"] == "semantic"
    assert recalled["results"][0]["metadata"]["evaluation"]["evaluation_id"]
    assert filtered_out["count"] == 0


def test_rag_memory_exposes_explicit_memory_strata_and_storage_tiers() -> None:
    memory = RAGMemory()
    unique = uuid.uuid4().hex

    working = memory.store(
        f"working note {unique}",
        topic="general",
        provenance="agent",
    )
    provenance_record = memory.store(
        f"artifact-backed fact {unique}",
        topic="weekly-evidence",
        provenance="unit-test",
        metadata={
            "governed_evidence": {
                "source_class": "fact",
                "source_type": "test",
                "source": "tests.test_hks_memory",
                "source_path": f"artifact:{unique}",
                "collected_at": "2026-03-23T00:00:00+00:00",
            }
        },
    )
    semantic = memory.store_exemplar(
        HKSValidatedExemplar(
            problem=f"Semantic exemplar {unique}",
            validated_solution="Store the reusable fix as a governed exemplar.",
            domain="general-coding",
            solution_kind="repair-pattern",
            provenance=HKSProvenance(
                source_type="test",
                source="tests.test_hks_memory",
                collector="pytest",
                collected_at="2026-03-23T00:00:00+00:00",
            ),
            evaluation={
                "authority": "local_hks",
                "promotion_eligible": True,
            },
        )
    )

    all_facts = memory.query_facts(include_stale=True, include_superseded=True, include_revoked=True)
    by_sha = {fact["sha256"]: fact for fact in all_facts}
    stats = memory.stats()

    assert working["memory_stratum"] == "working"
    assert working["storage_tier"] == "hot"
    assert working["evaluation"]["explicit_local_evaluation_present"] is False
    assert working["evaluation"]["promotion_eligible"] is False
    assert provenance_record["memory_stratum"] == "provenance"
    assert provenance_record["storage_tier"] == "warm"
    assert provenance_record["evaluation"]["explicit_local_evaluation_present"] is False
    assert provenance_record["evaluation"]["promotion_eligible"] is False
    assert semantic["memory_stratum"] == "semantic"
    assert semantic["storage_tier"] == "warm"
    assert semantic["evaluation"]["explicit_local_evaluation_present"] is True
    assert by_sha[working["sha256"]]["memory_stratum"] == "working"
    assert by_sha[provenance_record["sha256"]]["memory_stratum"] == "provenance"
    assert by_sha[semantic["sha256"]]["memory_stratum"] == "semantic"
    assert stats["memory_strata"]["working"] >= 1
    assert stats["memory_strata"]["provenance"] >= 1
    assert stats["memory_strata"]["semantic"] >= 1
    assert stats["storage_tiers"]["hot"] >= 1
    assert stats["storage_tiers"]["warm"] >= 2


def test_rag_memory_query_exposes_retrieval_contract_and_graph_context() -> None:
    memory = RAGMemory()
    unique = uuid.uuid4().hex

    memory.store(
        f"repair pattern bridge {unique}",
        topic="hlf_validated_exemplars",
        provenance="tests.test_hks_memory",
        tags=["repair", unique],
        entry_kind="hks_exemplar",
        domain="general-coding",
        solution_kind="repair-pattern",
        metadata={
            "governed_evidence": {
                "source_class": "hks_exemplar",
                "source_type": "test",
                "source": "tests.test_hks_memory",
                "source_path": f"artifact:{unique}",
                "collected_at": "2026-03-23T00:00:00+00:00",
            }
        },
    )

    recalled = memory.query(
        f"repair pattern {unique}",
        entry_kind="hks_exemplar",
        domain="general-coding",
        solution_kind="repair-pattern",
    )

    assert recalled["retrieval_contract"]["query_mode"] == "hybrid-governed-recall"
    assert recalled["retrieval_contract"]["semantic_mode"] == "sparse-vector+graph-boosted-ranking"
    assert "semantic" in recalled["retrieval_contract"]["active_paths"]
    assert "metadata-filtered" in recalled["retrieval_contract"]["active_paths"]
    assert recalled["retrieval_contract"]["path_counts"]["graph-linked"] >= 1
    assert recalled["retrieval_contract"]["path_status"]["dense-semantic"]["status"] == "unavailable"
    assert recalled["retrieval_contract"]["path_status"]["semantic"]["mode"] == "sparse-vector"
    assert recalled["retrieval_contract"]["path_status"]["graph-linked"]["source"] == "persisted-hks-node-graph"
    assert recalled["retrieval_contract"]["graph_traversal_totals"]["matched_entity_total"] >= 1
    assert recalled["retrieval_contract"]["purpose"] == "default"
    assert recalled["governed_hks_contract"]["admitted"] is True
    assert recalled["governed_hks_contract"]["reference_allowed"] is True
    result = recalled["results"][0]
    assert result["retrieval_contract"]["primary_path"] in {"semantic", "graph-linked", "lexical"}
    assert "lexical" in result["retrieval_contract"]["applied_paths"]
    assert result["retrieval_contract"]["graph_score"] > 0.0
    assert result["retrieval_contract"]["rank_score"] > 0.0
    assert result["retrieval_contract"]["path_status"]["graph-linked"]["status"] == "active"
    assert result["retrieval_contract"]["path_status"]["graph-linked"]["source"] == "persisted-hks-node-graph"
    assert result["retrieval_contract"]["graph_traversal_summary"]["matched_entity_count"] >= 1
    assert result["graph_context"]["graph_linked"] is True
    assert result["graph_context"]["link_count"] >= 1
    assert result["graph_context"]["graph_source"] == "persisted-hks-node-graph"
    assert len(result["graph_context"]["attached_node_ids"]) >= 1
    assert any(entity["kind"] == "domain" for entity in result["graph_context"]["entities"])


def test_rag_memory_store_materializes_first_class_graph_nodes() -> None:
    memory = RAGMemory()
    unique = uuid.uuid4().hex

    stored = memory.store(
        f"translation repair graph {unique}",
        topic="hlf_repairs",
        confidence=1.0,
        provenance="tests.test_hks_memory",
        tags=["repair", "translation", unique],
        entry_kind="hks_exemplar",
        domain="hlf-specific",
        solution_kind="repair-pattern",
        metadata={
            "graph_context": {
                "entities": [
                    {"kind": "contract", "value": "translation-repair"},
                    {"kind": "repair_procedure", "value": "low_fidelity"},
                ],
                "links": [
                    {
                        "source": "contract:translation-repair",
                        "relation": "repairs",
                        "target": "repair_procedure:low_fidelity",
                    }
                ],
            },
            "governed_evidence": {
                "source_class": "hks_exemplar",
                "source_type": "test",
                "source": "tests.test_hks_memory",
                "source_path": f"artifact:{unique}",
                "collected_at": "2026-03-23T00:00:00+00:00",
            },
        },
    )

    graph_nodes = memory.query_facts(
        entry_kind="hks_graph_node",
        include_stale=True,
        include_superseded=True,
        include_revoked=True,
        include_archive=True,
    )

    contract_node = next(
        node
        for node in graph_nodes
        if (node.get("metadata") or {}).get("graph_node", {}).get("node_id") == "contract:translation-repair"
    )
    assert contract_node["graph_context"]["graph_source"] == "metadata-derived"
    assert contract_node["metadata"]["graph_node"]["attached_fact_sha256s"][0] == stored["sha256"]
    assert any(
        relation["target"] == "repair_procedure:low_fidelity"
        for relation in contract_node["metadata"]["graph_node"]["relations"]
    )
    recalled = memory.query(unique, top_k=3, topic="hlf_repairs", purpose="repair_pattern_recall")
    assert recalled["governed_hks_contract"]["graph_posture"]["source"] == "persisted-hks-node-graph"


def test_rag_memory_store_exemplar_blocks_external_comparator_promotion() -> None:
    memory = RAGMemory()
    exemplar = HKSValidatedExemplar(
        problem=f"How to promote comparator-only result {uuid.uuid4().hex}",
        validated_solution="Do not promote comparator-only output.",
        domain="general-coding",
        solution_kind="repair-pattern",
        provenance=HKSProvenance(
            source_type="test",
            source="tests.test_hks_memory",
            collector="pytest",
            collected_at="2026-03-23T00:00:00+00:00",
        ),
        evaluation={
            "authority": "external_comparator",
            "promotion_eligible": True,
            "operator_summary": "Comparator found a similar pattern.",
        },
    )

    with pytest.raises(ValueError, match="local_hks evaluation authority"):
        memory.store_exemplar(exemplar)


def test_rag_memory_store_exemplar_blocks_missing_explicit_local_evaluation() -> None:
    memory = RAGMemory()
    exemplar = HKSValidatedExemplar(
        problem=f"How to promote result without explicit evaluation {uuid.uuid4().hex}",
        validated_solution="Require the capture path to materialize the local evaluation contract first.",
        domain="general-coding",
        solution_kind="repair-pattern",
        provenance=HKSProvenance(
            source_type="test",
            source="tests.test_hks_memory",
            collector="pytest",
            collected_at="2026-03-23T00:00:00+00:00",
        ),
    )

    with pytest.raises(ValueError, match="explicit local_hks evaluation contract"):
        memory.store_exemplar(exemplar)


def test_rag_memory_store_exemplar_blocks_non_promotable_local_evaluation() -> None:
    memory = RAGMemory()
    exemplar = HKSValidatedExemplar(
        problem=f"How to promote non-promotable local result {uuid.uuid4().hex}",
        validated_solution="Keep blocked until local evaluation clears it.",
        domain="general-coding",
        solution_kind="repair-pattern",
        provenance=HKSProvenance(
            source_type="test",
            source="tests.test_hks_memory",
            collector="pytest",
            collected_at="2026-03-23T00:00:00+00:00",
        ),
        evaluation={
            "authority": "local_hks",
            "promotion_eligible": False,
            "operator_summary": "Local evaluation blocked promotion.",
        },
    )

    with pytest.raises(ValueError, match="promotion eligible"):
        memory.store_exemplar(exemplar)


def test_rag_memory_non_exemplar_write_does_not_infer_promotion_from_partial_local_evaluation() -> None:
    memory = RAGMemory()
    unique = uuid.uuid4().hex

    stored = memory.store(
        f"partial local evaluation fact {unique}",
        topic="general",
        confidence=1.0,
        provenance="tests.test_hks_memory",
        metadata={
            "evaluation": {
                "authority": "local_hks",
                "groundedness": 0.9,
                "citation_coverage": 1.0,
                "operator_summary": "Partial local evaluation exists but did not explicitly approve promotion.",
            },
            "governed_evidence": {
                "source_class": "fact",
                "source_type": "test",
                "source": "tests.test_hks_memory",
                "source_path": f"artifact:{unique}",
                "collected_at": "2026-03-23T00:00:00+00:00",
            },
        },
    )

    assert stored["evaluation"]["authority"] == "local_hks"
    assert stored["evaluation"]["explicit_local_evaluation_present"] is True
    assert stored["evaluation"]["promotion_eligible"] is False


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
    assert recalled["status"] == "ok"
    assert recalled["operator_summary"]
    assert recalled["governance_event"]["event"]["action"] == "recall_hks_exemplar"
    assert recalled["evidence_summary"]["evidence_backed_count"] >= 1
    assert recalled["count"] >= 1
    assert any(result["entry_kind"] == "hks_exemplar" for result in recalled["results"])
    assert any(result["pointer"].startswith("&hlf_validated_exemplars-") for result in recalled["results"])
    recalled_eval = next(result["evaluation"] for result in recalled["results"] if result["entry_kind"] == "hks_exemplar")
    assert recalled_eval["authority"] == "local_hks"
    assert recalled_eval["promotion_eligible"] is True


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
    superseded = next(
        result for result in full_history["results"] if result["sha256"] == original["sha256"]
    )
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
    stale_results = memory.query(unique, include_stale=True, include_archive=True)
    provenance_results = memory.query(unique, require_provenance=True)

    assert default_results["count"] == 2
    assert all(
        result["evidence"]["freshness_status"] == "fresh" for result in default_results["results"]
    )
    assert stale_results["count"] == 3
    assert any(
        result["evidence"]["freshness_status"] == "stale" for result in stale_results["results"]
    )
    archived = next(
        result for result in stale_results["results"] if result["content"] == f"stale governed fact {unique}"
    )
    assert archived["memory_stratum"] == "archive"
    assert archived["storage_tier"] == "cold"
    assert archived["evidence"]["admission_decision"] == "archive"
    assert provenance_results["count"] == 1
    assert provenance_results["results"][0]["evidence"]["provenance_grade"] == "evidence-backed"


def test_rag_memory_default_query_hides_archived_records_unless_requested() -> None:
    memory = RAGMemory()
    unique = uuid.uuid4().hex

    memory.store(
        f"fresh active fact {unique}",
        topic="general",
        provenance="unit-test",
        metadata={
            "governed_evidence": {
                "source_class": "fact",
                "source_type": "test",
                "source": "tests.test_hks_memory",
                "source_path": f"artifact:{unique}:active",
                "collected_at": "2026-03-23T00:00:00+00:00",
                "fresh_until": "2999-01-01T00:00:00+00:00",
            },
            "evaluation": {
                "authority": "local_hks",
                "groundedness": 0.95,
                "citation_coverage": 1.0,
            },
        },
    )
    archived = memory.store(
        f"low salience fact {unique}",
        topic="general",
        confidence=0.1,
        provenance="unit-test",
        metadata={
            "governed_evidence": {
                "source_class": "fact",
                "source_type": "test",
                "source": "tests.test_hks_memory",
                "source_path": f"artifact:{unique}:archived",
                "collected_at": "2026-03-23T00:00:00+00:00",
                "fresh_until": "2999-01-01T00:00:00+00:00",
            },
            "evaluation": {
                "authority": "local_hks",
                "groundedness": 0.05,
                "citation_coverage": 0.0,
            },
        },
    )

    default_results = memory.query(unique, include_archive=False)
    archive_results = memory.query(unique, include_archive=True)

    assert archived["memory_stratum"] == "archive"
    assert archived["storage_tier"] == "cold"
    assert all(result["sha256"] != archived["sha256"] for result in default_results["results"])
    assert any(result["sha256"] == archived["sha256"] for result in archive_results["results"])


def test_weekly_artifact_memory_record_routes_unverified_artifact_to_archive() -> None:
    from hlf_mcp.weekly_artifacts import build_weekly_artifact_memory_record

    artifact = {
        "artifact_id": f"artifact-{uuid.uuid4().hex[:8]}",
        "artifact_status": "advisory",
        "source": "weekly-test",
        "generated_at": "2026-03-23T00:00:00Z",
        "verification": {"verified": False},
        "latest_suite_summary": {"passed": False},
        "provenance": {
            "source": "weekly-test",
            "collector": "pytest",
            "collected_at": "2026-03-23T00:00:00Z",
        },
    }

    record = build_weekly_artifact_memory_record(artifact)

    assert record is not None
    assert record["metadata"]["memory_stratum"] == "archive"
    assert record["metadata"]["storage_tier"] == "cold"
    assert record["metadata"]["governed_evidence"]["memory_stratum"] == "archive"
    assert record["metadata"]["artifact_contract"]["artifact_form"] == "raw_intake"
    assert record["metadata"]["source_capture"]["source_authority_label"] == "advisory"


def test_rag_memory_store_materializes_source_capture_and_artifact_contract() -> None:
    memory = RAGMemory()
    unique = uuid.uuid4().hex

    result = memory.store(
        f"structured capture {unique}",
        topic="hks_source_capture_contract",
        confidence=0.88,
        provenance="tests.test_hks_memory",
        metadata={
            "artifact_form": "raw_intake",
            "artifact_kind": "answer_span",
            "source_authority_label": "advisory",
            "source_capture": {
                "extraction_fidelity_score": 0.82,
                "code_block_recall_score": 0.75,
                "structure_fidelity_score": 0.91,
                "citation_recoverability_score": 0.79,
                "source_type_classification": "docs_site",
                "source_authority_label": "advisory",
                "source_version": "v2026.03",
                "freshness_marker": "2026-03-23T00:00:00+00:00",
            },
            "governed_evidence": {
                "source_class": "fact",
                "source_type": "docs_site",
                "source": "tests.test_hks_memory",
                "source_path": f"artifact:{unique}",
                "collected_at": "2026-03-23T00:00:00+00:00",
            },
        },
    )

    assert result["source_capture"]["extraction_fidelity_score"] == 0.82
    assert result["source_capture"]["source_type_classification"] == "docs_site"
    assert result["artifact_contract"]["artifact_form"] == "raw_intake"
    assert result["artifact_contract"]["artifact_kind"] == "answer_span"
    assert result["evidence"]["source_authority_label"] == "advisory"
    assert result["evidence"]["artifact_form"] == "raw_intake"
    assert result["evidence"]["artifact_contract"]["artifact_kind"] == "answer_span"


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


def test_benchmark_artifact_materializes_prompt_code_and_upgrade_graph_nodes() -> None:
    unique = uuid.uuid4().hex[:8]

    recorded = server.hlf_record_benchmark_artifact(
        profile_name=f"benchmark-{unique}",
        benchmark_scores={"routing_quality": 0.91, "verifier_accuracy": 0.88},
        topic=f"benchmark-graph-{unique}",
        domains=["general-coding"],
        languages=["en"],
        details={
            "prompt_name": f"repair-prompt-{unique}",
            "code_pattern": f"governed-loop-{unique}",
            "upgrade_candidate": f"upgrade-path-{unique}",
        },
    )

    assert recorded["status"] == "ok"

    graph_nodes = server.memory_store.query_facts(
        entry_kind="hks_graph_node",
        include_stale=True,
        include_superseded=True,
        include_revoked=True,
        include_archive=True,
    )
    node_ids = {
        (node.get("metadata") or {}).get("graph_node", {}).get("node_id"): node
        for node in graph_nodes
    }

    assert f"prompt_asset:repair-prompt-{unique}" in node_ids
    assert f"code_pattern:governed-loop-{unique}" in node_ids
    assert f"upgrade_opportunity:upgrade-path-{unique}" in node_ids

    recalled = server.memory_store.query(
        unique,
        top_k=5,
        topic="hlf_benchmark_artifacts",
        purpose="verifier_evidence",
    )

    assert recalled["governed_hks_contract"]["admitted"] is True
    assert recalled["governed_hks_contract"]["graph_posture"]["source"] == "persisted-hks-node-graph"
    assert any(result["entry_kind"] == "benchmark_artifact" for result in recalled["results"])


def test_rag_memory_resolve_pointer_blocks_basic_fact_for_routing_evidence() -> None:
    memory = RAGMemory()
    stored = memory.store("ungoverned routing hint", topic="routing-hints", provenance="agent")
    pointer = f"&routing-hints-{stored['id']}:SHA256:{stored['sha256']}"

    outcome = memory.resolve_pointer(pointer, purpose="routing_evidence")

    assert outcome["status"] == "blocked"
    assert outcome["admitted"] is False
    assert "evidence_backed_provenance_required" in outcome["reasons"]
    assert outcome["provenance_grade"] == "basic"


def test_rag_memory_query_rejects_basic_fact_for_routing_evidence() -> None:
    memory = RAGMemory()
    unique = uuid.uuid4().hex
    memory.store(
        f"ungoverned routing evidence {unique}",
        topic="routing-evidence-rejection",
        provenance="tests.test_hks_memory",
    )

    result = memory.query(
        unique,
        top_k=3,
        topic="routing-evidence-rejection",
        purpose="routing_evidence",
    )

    assert result["count"] == 0
    assert result["retrieval_contract"]["purpose"] == "routing_evidence"
    assert result["retrieval_contract"]["admitted_result_count"] == 0
    assert result["retrieval_contract"]["rejected_result_count"] >= 1


def test_rag_memory_query_rejects_unlinked_benchmark_for_verifier_evidence() -> None:
    memory = RAGMemory()
    unique = uuid.uuid4().hex
    memory.store(
        f"verifier benchmark payload {unique}",
        topic="hlf_benchmark_artifacts",
        confidence=1.0,
        provenance="tests.test_hks_memory",
        entry_kind="benchmark_artifact",
        metadata={
            "artifact_id": unique,
            "governed_evidence": {
                "source_class": "benchmark_artifact",
                "source_type": "benchmark_artifact",
                "source": "tests.test_hks_memory",
                "source_path": f"artifact:{unique}",
                "artifact_id": unique,
                "collector": "tests.test_hks_memory",
                "collected_at": "2026-03-23T00:00:00+00:00",
                "trust_tier": "validated",
            },
        },
    )

    result = memory.query(
        f"verifier benchmark payload {unique}",
        top_k=3,
        topic="hlf_benchmark_artifacts",
        purpose="verifier_evidence",
    )

    assert result["count"] == 0
    assert result["retrieval_contract"]["purpose"] == "verifier_evidence"
    assert result["retrieval_contract"]["admitted_result_count"] == 0
    assert result["retrieval_contract"]["rejected_result_count"] >= 1


def test_rag_memory_query_skips_low_signal_translation_memory_request() -> None:
    memory = RAGMemory()

    result = memory.query(
        "x",
        top_k=3,
        topic="hlf_translation_contracts",
        purpose="translation_memory",
    )

    assert result["count"] == 0
    assert result["retrieval_contract"]["invocation_gate"]["decision"] == "skip"
    assert result["retrieval_contract"]["invocation_gate"]["retrieval_invoked"] is False
    assert result["governed_hks_contract"]["admitted"] is False


def test_rag_memory_query_invokes_translation_memory_for_chinese_signal() -> None:
    memory = RAGMemory()

    result = memory.query(
        "你好世界",
        top_k=3,
        topic="hlf_translation_contracts",
        purpose="translation_memory",
    )

    assert result["retrieval_contract"]["invocation_gate"]["decision"] == "invoke"
    assert result["retrieval_contract"]["invocation_gate"]["retrieval_invoked"] is True


def test_rag_memory_query_escalates_low_signal_verifier_request() -> None:
    memory = RAGMemory()

    result = memory.query(
        "?",
        top_k=3,
        topic="hlf_benchmark_artifacts",
        purpose="verifier_evidence",
    )

    assert result["count"] == 0
    assert result["retrieval_contract"]["invocation_gate"]["decision"] == "escalate"
    assert result["retrieval_contract"]["invocation_gate"]["review_required"] is True
    assert result["retrieval_contract"]["invocation_gate"]["retrieval_invoked"] is False


def test_server_memory_resolve_allows_hks_exemplar_for_execution_and_emits_event() -> None:
    unique = uuid.uuid4().hex
    stored = server.hlf_hks_capture(
        problem=f"How to resolve governed exemplar {unique}",
        validated_solution="Use the validated exemplar contract.",
        domain="hlf-specific",
        solution_kind="repair-pattern",
        tags=[unique],
        tests=[{"name": "pytest", "passed": True, "exit_code": 0, "counts": {"passed": 1}}],
        source="tests.test_hks_memory",
        artifact_path=f"artifact:{unique}",
    )
    pointer = f"&hlf_validated_exemplars-{stored['id']}:SHA256:{stored['sha256']}"

    outcome = server.hlf_memory_resolve(pointer, purpose="execution")

    assert outcome["status"] == "ok"
    assert outcome["admitted"] is True
    assert outcome["provenance_grade"] == "evidence-backed"
    assert outcome["governance_event"]["event"]["kind"] == "pointer_resolution"
    assert outcome["resolution"]["fact"]["entry_kind"] == "hks_exemplar"


def test_governed_recall_syncs_verified_weekly_artifacts_into_memory(
    monkeypatch, tmp_path: Path
) -> None:
    from hlf_mcp import weekly_artifacts

    unique = uuid.uuid4().hex
    metrics_dir = tmp_path / "metrics"
    monkeypatch.setattr(
        weekly_artifacts,
        "collect_git_context",
        lambda repo_root: {
            "branch": "integrate-sovereign",
            "commit_sha": f"sha-{unique}",
            "commit_short_sha": unique[:8],
            "status_porcelain": [],
        },
    )
    monkeypatch.setattr(
        weekly_artifacts,
        "collect_governance_manifest_snapshot",
        lambda repo_root: {
            "manifest_present": True,
            "manifest_sha256": f"manifest-{unique}",
            "drift": [],
            "entry_count": 4,
        },
    )
    monkeypatch.setattr(
        weekly_artifacts,
        "collect_server_surface",
        lambda: {
            "registered_tool_count": 35,
            "registered_resource_count": 9,
            "exported_callable_count": 35,
        },
    )

    artifact = weekly_artifacts.build_weekly_artifact(
        repo_root=tmp_path,
        metrics_dir=metrics_dir,
        source=f"weekly-{unique}",
        workflow_run_url=f"https://example.test/run/{unique}",
        latest_suite_summary={"passed": True, "counts": {"passed": 1}, "exit_code": 0},
    )
    weekly_artifacts.persist_weekly_artifact(artifact, metrics_dir)

    recalled = server.hlf_governed_recall(unique, metrics_dir=str(metrics_dir), top_k=5)

    assert recalled["status"] == "ok"
    assert recalled["weekly_sync"]["count"] >= 1
    assert recalled["recall_summary"]["archive_visibility"] == "filtered_by_default"
    assert recalled["recall_summary"]["active_result_count"] >= 1
    assert "active" in recalled["recall_summary"]["admission_decision_counts"]
    assert "semantic" in recalled["recall_summary"]["retrieval_path_counts"]
    assert recalled["retrieval_contract"]["query_mode"] == "hybrid-governed-recall"
    assert any(result["entry_kind"] == "weekly_artifact" for result in recalled["results"])
    weekly_result = next(result for result in recalled["results"] if result["entry_kind"] == "weekly_artifact")
    assert weekly_result["metadata"]["artifact_id"] == artifact["artifact_id"]
    assert weekly_result["evaluation"]["authority"] == "local_hks"
    assert weekly_result["evaluation"]["promotion_eligible"] is True
    assert weekly_result["graph_context"]["graph_linked"] is True


def test_weekly_artifact_memory_record_materializes_first_class_graph_nodes() -> None:
    from hlf_mcp.weekly_artifacts import build_weekly_artifact_memory_record

    memory = RAGMemory()
    unique = uuid.uuid4().hex[:8]
    artifact = {
        "artifact_id": f"weekly-{unique}",
        "artifact_status": "promoted",
        "source": f"weekly-{unique}",
        "generated_at": "2026-03-24T00:00:00Z",
        "verification": {"verified": True},
        "latest_suite_summary": {"passed": True},
        "provenance": {
            "source": f"weekly-{unique}",
            "collector": "pytest",
            "collected_at": "2026-03-24T00:00:00Z",
            "branch": "integrate-sovereign",
            "commit_sha": f"commit-{unique}",
        },
    }

    record = build_weekly_artifact_memory_record(artifact)
    assert record is not None

    stored = memory.store(
        record["content"],
        topic=record["topic"],
        confidence=record["confidence"],
        provenance=record["provenance"],
        tags=record["tags"],
        entry_kind=record["entry_kind"],
        metadata=record["metadata"],
    )

    graph_nodes = memory.query_facts(
        entry_kind="hks_graph_node",
        include_stale=True,
        include_superseded=True,
        include_revoked=True,
        include_archive=True,
    )
    node_ids = {
        (node.get("metadata") or {}).get("graph_node", {}).get("node_id"): node
        for node in graph_nodes
    }

    assert stored["memory_stratum"] == "provenance"
    assert f"weekly_artifact:weekly-{unique}" in node_ids
    assert "artifact_status:promoted" in node_ids

    recalled = memory.query(
        unique,
        top_k=3,
        topic="hlf_weekly_artifacts",
        purpose="routing_evidence",
    )

    assert recalled["governed_hks_contract"]["admitted"] is True
    assert recalled["governed_hks_contract"]["graph_posture"]["source"] == "persisted-hks-node-graph"
    assert recalled["results"][0]["entry_kind"] == "weekly_artifact"


def test_hlf_memory_stats_exposes_archive_admission_bridge_summary() -> None:
    unique = uuid.uuid4().hex

    server.memory_store.store(
        f"active stats fact {unique}",
        topic="hlf_memory_stats_bridge",
        confidence=1.0,
        provenance="tests.test_hks_memory",
        metadata={
            "memory_stratum": "semantic",
            "storage_tier": "warm",
            "governed_evidence": {
                "source_class": "fact",
                "source_type": "test",
                "source": "tests.test_hks_memory",
                "source_path": f"artifact:{unique}:active",
                "fresh_until": "2999-01-01T00:00:00+00:00",
            },
        },
    )
    server.memory_store.store(
        f"archived stats fact {unique}",
        topic="hlf_memory_stats_bridge",
        confidence=1.0,
        provenance="tests.test_hks_memory",
        metadata={
            "memory_stratum": "archive",
            "storage_tier": "cold",
            "governed_evidence": {
                "source_class": "fact",
                "source_type": "test",
                "source": "tests.test_hks_memory",
                "source_path": f"artifact:{unique}:archive",
                "fresh_until": "2000-01-01T00:00:00+00:00",
                "admission_decision": "archive",
            },
        },
    )

    stats = server.hlf_memory_stats()

    assert stats["claim_lane"] == "bridge-true"
    assert stats["archive_admission"]["archive_visibility_default"] == "filtered"
    assert stats["archive_admission"]["admission_model"] == "salience_and_governance_gated"
    assert stats["archive_admission"]["active_facts"] >= 1
    assert stats["archive_admission"]["archive_facts"] >= 1
    assert "raw_intake" in stats["artifact_forms"]
    assert "advisory" in stats["source_authority_labels"]
    assert "Archive-tier facts stay hidden from default governed recall" in stats["operator_summary"]


def test_hks_external_compare_returns_quarantined_bridge_contract() -> None:
    unique = f"external-compare-{uuid.uuid4().hex}"
    server.hlf_hks_capture(
        problem=unique,
        validated_solution="Keep local HKS as the admission authority.",
        domain="general-coding",
        tests=[{"name": "compare-guard", "passed": True, "exit_code": 0, "counts": {"passed": 1}}],
        summary="External comparator quarantine coverage",
    )

    result = server.hlf_hks_external_compare(
        unique,
        comparator_name="bounded-exa",
        comparator_results=[
            {
                "title": "Comparator candidate",
                "snippet": "Advisory similar fix.",
                "url": "https://example.test/comparator",
                "score": 0.91,
            }
        ],
        enabled=True,
    )

    assert result["status"] == "ok"
    assert result["lane"] == "bridge"
    assert result["requires_local_recheck"] is True
    assert result["admission_authority"] == "local_hks_only"
    assert result["comparator_results"][0]["authority"] == "external_comparator"
