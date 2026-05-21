"""
Tests for Hybrid RAG Pipeline + Integrations.

Coverage:
- BM25 keyword search
- Vector/semantic search
- Hybrid search fusion
- Deduplication across BM25+vector
- Cross-encoder reranking
- Index management (add, remove, clear)
- Thread safety
- Integration stubs (Janus, ChronosGraph, BrowserOS, LOLLMS, MSTY, AnythingLLM)
- Edge cases (empty index, empty query, duplicate docs, large texts)
"""

from __future__ import annotations

import json
import threading
import time
from typing import Any

import pytest

from hlf_mcp.hlf.hybrid_rag import (
    HybridRAG,
    _SimpleBM25,
    _InMemoryVectorStore,
    _CrossEncoderReranker,
    _bag_of_words_embedding,
    _cosine_sim,
    _tokenize,
    create_hybrid_rag,
    get_hybrid_rag,
)
from hlf_mcp.hlf.rag_integrations import (
    AnythingLLMImport,
    BaseIntegration,
    BrowserOSGuidesIntegration,
    ChronosGraphIntegration,
    EvidenceContract,
    JanusIntegration,
    LOLLMSImport,
    MSTYImport,
    create_all_integrations,
)


# ─────────────────────────────────────────────────────────────────── #
# Fixtures
# ─────────────────────────────────────────────────────────────────── #

@pytest.fixture
def rag():
    """Fresh in-memory HybridRAG instance (no Chroma)."""
    HybridRAG.reset_instance()
    rag = HybridRAG(use_chroma=False, embedding_dim=128)
    return rag


@pytest.fixture
def populated_rag(rag):
    """RAG with 10 test documents."""
    docs = [
        ("HLF is a deterministic orchestration protocol for multi-agent systems.", {"topic": "hlf", "year": 2025}),
        ("The Heptapod Protocol enables time-aware knowledge representation.", {"topic": "heptapod", "year": 2024}),
        ("BM25 is a probabilistic retrieval function based on term frequency.", {"topic": "ir", "year": 2023}),
        ("Vector search uses embedding similarity for semantic retrieval.", {"topic": "ir", "year": 2022}),
        ("ChromaDB is an open-source vector database for AI applications.", {"topic": "tools", "year": 2024}),
        ("HLF's MCP server provides tool dispatch and governance enforcement.", {"topic": "hlf", "year": 2025}),
        ("RAG combines retrieval with generation for grounded answers.", {"topic": "ir", "year": 2023}),
        ("BrowserOS is a browser-based operating system with MCP integration.", {"topic": "tools", "year": 2025}),
        ("Janus provides a semantic knowledge graph for RAG ingestion.", {"topic": "tools", "year": 2024}),
        ("ChronosGraph processes video content into text transcriptions.", {"topic": "tools", "year": 2025}),
    ]
    for i, (text, meta) in enumerate(docs):
        rag.add_document(doc_id=f"doc_{i}", text=text, metadata=meta)
    return rag


# ─────────────────────────────────────────────────────────────────── #
# 1. BM25 Search Tests
# ─────────────────────────────────────────────────────────────────── #

def test_bm25_search_returns_results(populated_rag):
    """BM25 search returns ranked documents."""
    results = populated_rag.bm25_search("HLF protocol")
    assert len(results) > 0
    assert results[0]["score"] > 0
    # Top result should mention HLF
    assert "HLF" in results[0]["text"] or "hlf" in results[0]["text"].lower()


def test_bm25_search_empty_query(populated_rag):
    """BM25 search with empty query returns empty list."""
    results = populated_rag.bm25_search("")
    assert results == []


def test_bm25_search_empty_index(rag):
    """BM25 search on empty index returns empty list."""
    results = rag.bm25_search("anything")
    assert results == []


# ─────────────────────────────────────────────────────────────────── #
# 2. Vector Search Tests
# ─────────────────────────────────────────────────────────────────── #

def test_vector_search_returns_results(populated_rag):
    """Vector search returns semantically similar documents."""
    results = populated_rag.vector_search("deterministic multi-agent orchestration")
    assert len(results) > 0
    assert results[0]["score"] > 0


def test_vector_search_empty_query(populated_rag):
    """Vector search with empty query returns empty or low-score results."""
    results = populated_rag.vector_search("")
    # Should return no results or results with zero score
    assert len(results) == 0 or all(r["score"] == 0.0 for r in results)


def test_vector_search_empty_index(rag):
    """Vector search on empty index returns empty list."""
    results = rag.vector_search("anything")
    assert results == []


# ─────────────────────────────────────────────────────────────────── #
# 3. Hybrid Search Tests
# ─────────────────────────────────────────────────────────────────── #

def test_hybrid_search_returns_results(populated_rag):
    """Hybrid search combines BM25+vector and returns results."""
    results = populated_rag.search("HLF deterministic protocol", k=5)
    assert len(results) > 0
    assert len(results) <= 5
    for r in results:
        assert "doc_id" in r
        assert "text" in r
        assert "score" in r
        assert "bm25_score" in r
        assert "vector_score" in r
        assert "metadata" in r


def test_hybrid_search_dedup(populated_rag):
    """Hybrid search returns unique document IDs (deduplication works)."""
    results = populated_rag.search("knowledge representation", k=10)
    doc_ids = [r["doc_id"] for r in results]
    assert len(doc_ids) == len(set(doc_ids)), f"Duplicate doc_ids found: {doc_ids}"


def test_hybrid_search_k_truncation(populated_rag):
    """Hybrid search respects k parameter."""
    for k in [1, 3, 5]:
        results = populated_rag.search("HLF", k=k)
        assert len(results) <= k


def test_hybrid_search_no_rerank(populated_rag):
    """Hybrid search works without reranking."""
    results = populated_rag.search("protocol", k=5, rerank=False)
    assert len(results) > 0


def test_hybrid_search_empty_index(rag):
    """Hybrid search on empty index returns empty list."""
    results = rag.search("anything")
    assert results == []


# ─────────────────────────────────────────────────────────────────── #
# 4. Cross-Encoder Reranker Tests
# ─────────────────────────────────────────────────────────────────── #

def test_reranker_scores(populated_rag):
    """Cross-encoder reranker reorders results."""
    # Get results with and without reranking
    results_reranked = populated_rag.search("multi-agent orchestration", k=5, rerank=True)
    results_unranked = populated_rag.search("multi-agent orchestration", k=5, rerank=False)

    # Both should return results
    assert len(results_reranked) > 0
    assert len(results_unranked) > 0

    # Scores should differ when reranking is applied
    if len(results_reranked) == len(results_unranked):
        reranked_scores = [r["score"] for r in results_reranked]
        unranked_scores = [r["score"] for r in results_unranked]
        assert reranked_scores != unranked_scores, "Reranking should modify scores"


def test_reranker_exact_match_bonus():
    """Reranker gives higher score to exact phrase matches."""
    reranker = _CrossEncoderReranker()
    score_exact = reranker.score("HLF protocol", "The HLF protocol is used for agent orchestration.")
    score_loose = reranker.score("HLF protocol", "Something completely unrelated to any system.")
    assert score_exact > score_loose


def test_reranker_empty_inputs():
    """Reranker handles empty inputs gracefully."""
    reranker = _CrossEncoderReranker()
    assert reranker.score("", "text") == 0.0
    assert reranker.score("query", "") == 0.0
    assert reranker.score("", "") == 0.0


# ─────────────────────────────────────────────────────────────────── #
# 5. Index Management Tests
# ─────────────────────────────────────────────────────────────────── #

def test_add_document(rag):
    """Adding a document returns a doc_id and increments count."""
    doc_id = rag.add_document(text="Test document content")
    assert doc_id is not None
    assert rag.count() == 1


def test_add_document_with_custom_id(rag):
    """Adding a document with custom ID works."""
    rag.add_document(doc_id="my_id", text="Custom ID document")
    assert rag.count() == 1
    results = rag.search("Custom ID")
    assert results[0]["doc_id"] == "my_id"


def test_remove_document(populated_rag):
    """Removing a document decreases count."""
    initial = populated_rag.count()
    result = populated_rag.remove_document("doc_0")
    assert result is True
    assert populated_rag.count() == initial - 1


def test_remove_nonexistent_document(populated_rag):
    """Removing a non-existent document returns False."""
    result = populated_rag.remove_document("nonexistent_id")
    assert result is False


def test_clear_index(populated_rag):
    """Clearing the index removes all documents."""
    assert populated_rag.count() > 0
    populated_rag.clear_index()
    assert populated_rag.count() == 0
    results = populated_rag.search("HLF")
    assert results == []


def test_get_stats(populated_rag):
    """Stats return accurate index information."""
    stats = populated_rag.get_stats()
    assert stats["document_count"] == populated_rag.count()
    assert stats["total_characters"] > 0
    assert "embedding_dim" in stats


# ─────────────────────────────────────────────────────────────────── #
# 6. Thread Safety Tests
# ─────────────────────────────────────────────────────────────────── #

def test_concurrent_add_documents(rag):
    """Concurrent document additions don't corrupt the index."""
    errors = []
    count_per_thread = 50

    def add_batch(prefix, start_idx):
        try:
            for i in range(count_per_thread):
                rag.add_document(
                    doc_id=f"{prefix}_{start_idx + i}",
                    text=f"Thread {prefix} document {i} about RAG systems.",
                )
        except Exception as e:
            errors.append(str(e))

    threads = []
    for t in range(4):
        t = threading.Thread(target=add_batch, args=(f"t{t}", t * count_per_thread))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    assert len(errors) == 0, f"Errors during concurrent add: {errors}"
    assert rag.count() == 4 * count_per_thread


def test_concurrent_search(populated_rag):
    """Concurrent searches don't raise errors."""
    errors = []

    def search_batch():
        try:
            for _ in range(20):
                populated_rag.search("HLF protocol", k=3)
                populated_rag.bm25_search("deterministic")
                populated_rag.vector_search("semantic retrieval")
        except Exception as e:
            errors.append(str(e))

    threads = [threading.Thread(target=search_batch) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"Errors during concurrent search: {errors}"


# ─────────────────────────────────────────────────────────────────── #
# 7. Integration Stubs Tests
# ─────────────────────────────────────────────────────────────────── #

def test_evidence_contract_roundtrip():
    """EvidenceContract to_dict/from_dict roundtrip."""
    ec = EvidenceContract(
        source="test://source",
        source_type="test",
        content_hash="abc123",
        metadata={"key": "value"},
        rag_doc_ids=["d1", "d2"],
    )
    d = ec.to_dict()
    ec2 = EvidenceContract.from_dict(d)
    assert ec2.source == ec.source
    assert ec2.source_type == ec.source_type
    assert ec2.content_hash == ec.content_hash
    assert ec2.rag_doc_ids == ec.rag_doc_ids
    assert ec2.metadata["key"] == "value"


def test_create_all_integrations(rag):
    """create_all_integrations returns all 6 integrations."""
    integrations = create_all_integrations(rag=rag)
    assert len(integrations) == 6
    assert "janus" in integrations
    assert "chronos_graph" in integrations
    assert "browseros_guides" in integrations
    assert "lollms" in integrations
    assert "msty" in integrations
    assert "anythingllm" in integrations
    for name, integration in integrations.items():
        assert isinstance(integration, BaseIntegration)


def test_janus_integration_stub(rag):
    """JanusIntegration crawl/query/archive work (simulated)."""
    ji = JanusIntegration(rag=rag)
    # Crawl
    evidence = ji.crawl("http://example.com/page", depth=1)
    assert isinstance(evidence, EvidenceContract)
    assert evidence.source_type == "janus"
    assert len(evidence.rag_doc_ids) > 0

    # Query
    result = ji.query("example")
    assert isinstance(result, dict)
    assert "query" in result
    assert "results" in result

    # Archive
    evidence2 = ji.archive("resource-123")
    assert isinstance(evidence2, EvidenceContract)
    assert evidence2.source_type == "janus"


def test_chronos_integration_stub(rag):
    """ChronosGraphIntegration transcribe/ingest work (simulated)."""
    ci = ChronosGraphIntegration(rag=rag)
    # Transcribe
    result = ci.transcribe("/tmp/test_video.mp4", language="en")
    assert isinstance(result, dict)
    assert "transcription" in result
    assert len(result["transcription"]) > 0
    assert result["language"] == "en"

    # Ingest (string)
    evidence = ci.ingest("Sample transcription text")
    assert isinstance(evidence, EvidenceContract)
    assert evidence.source_type == "chronos_graph"

    # Ingest (dict)
    evidence2 = ci.ingest({"transcription": "Dict transcription", "video_path": "/tmp/v.mp4"})
    assert isinstance(evidence2, EvidenceContract)


def test_browseros_integration_stub(rag):
    """BrowserOSGuidesIntegration extract/compile work (simulated)."""
    bi = BrowserOSGuidesIntegration(rag=rag)
    # Extract
    result = bi.extract("http://example.com/guide")
    assert isinstance(result, dict)
    assert "sections" in result
    assert len(result["sections"]) > 0
    assert "title" in result["sections"][0]

    # Compile
    evidence = bi.compile("guide-123")
    assert isinstance(evidence, EvidenceContract)
    assert evidence.source_type == "browseros_guides"
    assert len(evidence.rag_doc_ids) > 0


def test_lollms_import_stub(rag):
    """LOLLMSImport import_datastore works (simulated)."""
    li = LOLLMSImport(rag=rag)
    evidence = li.import_datastore("datastore-abc")
    assert isinstance(evidence, EvidenceContract)
    assert evidence.source_type == "lollms_datastore"
    assert len(evidence.rag_doc_ids) > 0


def test_msty_import_stub(rag):
    """MSTYImport import_knowledge_stack works (simulated)."""
    mi = MSTYImport(rag=rag)
    evidence = mi.import_knowledge_stack("stack-xyz")
    assert isinstance(evidence, EvidenceContract)
    assert evidence.source_type == "msty_knowledge_stack"
    assert len(evidence.rag_doc_ids) > 0


def test_anythingllm_import_stub(rag):
    """AnythingLLMImport import_workspace works (simulated)."""
    ai = AnythingLLMImport(rag=rag)
    evidence = ai.import_workspace("workspace-alpha")
    assert isinstance(evidence, EvidenceContract)
    assert evidence.source_type == "anythingllm_workspace"
    assert len(evidence.rag_doc_ids) > 0


# ─────────────────────────────────────────────────────────────────── #
# 8. Edge Cases
# ─────────────────────────────────────────────────────────────────── #

def test_add_duplicate_doc_id(rag):
    """Adding a document with an existing doc_id overwrites it."""
    rag.add_document(doc_id="dup", text="First version")
    rag.add_document(doc_id="dup", text="Second version overwritten")
    assert rag.count() == 1
    results = rag.search("Second version")
    assert len(results) == 1
    assert "overwritten" in results[0]["text"]


def test_large_text_document(rag):
    """Large text documents are handled correctly."""
    large_text = "HLF protocol " * 1000  # ~14K chars
    doc_id = rag.add_document(text=large_text)
    assert doc_id is not None
    assert rag.count() == 1
    results = rag.search("HLF", k=3)
    assert len(results) > 0


def test_special_characters_in_text(rag):
    """Documents with special characters are handled."""
    text = "Query with JSON: {\"key\": [1, 2, 3]} and symbols: @#$%^&*()"
    rag.add_document(text=text)
    results = rag.search("JSON key")
    assert len(results) > 0


def test_very_short_document(rag):
    """Very short (single-token) documents are indexed."""
    rag.add_document(text="HLF")
    results = rag.search("HLF")
    assert len(results) == 1


def test_add_and_search_unicode(rag):
    """Unicode documents are properly indexed."""
    text = "Héllö Wörld — em dash and unicode: α β γ δ ε"
    rag.add_document(text=text)
    results = rag.search("Héllö")
    assert len(results) > 0


# ─────────────────────────────────────────────────────────────────── #
# 9. Convenience Functions
# ─────────────────────────────────────────────────────────────────── #

def test_create_hybrid_rag():
    """create_hybrid_rag returns a new HybridRAG instance."""
    HybridRAG.reset_instance()
    r1 = create_hybrid_rag(use_chroma=False)
    r2 = create_hybrid_rag(use_chroma=False)
    assert isinstance(r1, HybridRAG)
    assert isinstance(r2, HybridRAG)
    # These are separate instances, not singletons
    r1.add_document(text="doc in r1")
    assert r1.count() == 1
    assert r2.count() == 0
    HybridRAG.reset_instance()


def test_get_hybrid_rag_singleton():
    """get_hybrid_rag returns the singleton instance."""
    HybridRAG.reset_instance()
    r1 = get_hybrid_rag(use_chroma=False)
    r2 = get_hybrid_rag()
    assert r1 is r2
    HybridRAG.reset_instance()


def test_search_results_include_both_scores(populated_rag):
    """Hybrid search results include both BM25 and vector scores."""
    results = populated_rag.search("semantic retrieval", k=5)
    for r in results:
        assert "bm25_score" in r
        assert "vector_score" in r
        assert isinstance(r["bm25_score"], (int, float))
        assert isinstance(r["vector_score"], (int, float))


def test_large_k_returns_all_docs(populated_rag):
    """Search with k > document count returns all documents."""
    results = populated_rag.search("HLF", k=100)
    assert len(results) == populated_rag.count()


def test_add_remove_add_cycle(populated_rag):
    """Add, remove, re-add same doc_id works correctly."""
    doc_id = "doc_0"
    text_before = populated_rag.search("deterministic")[0]["text"]
    populated_rag.remove_document(doc_id)
    # Re-add with different text
    populated_rag.add_document(doc_id=doc_id, text="Completely new text about quantum computing.")
    results = populated_rag.search("quantum")
    assert len(results) > 0
    assert results[0]["doc_id"] == doc_id
    assert "quantum" in results[0]["text"]


# ─────────────────────────────────────────────────────────────────── #
# 10. Utility Function Tests
# ─────────────────────────────────────────────────────────────────── #

def test_tokenize():
    """_tokenize splits text into lowercase alphanumeric tokens."""
    tokens = _tokenize("Hello World! This is a test.")
    assert "hello" in tokens
    assert "world" in tokens
    assert "test" in tokens
    # Punctuation filtered out
    assert "!" not in tokens
    # Short tokens filtered out
    assert not any(len(t) < 2 for t in tokens)


def test_cosine_sim():
    """_cosine_sim computes cosine similarity correctly."""
    a = [1.0, 0.0, 0.0]
    b = [1.0, 0.0, 0.0]
    assert _cosine_sim(a, b) == pytest.approx(1.0)

    a = [1.0, 0.0, 0.0]
    b = [0.0, 1.0, 0.0]
    assert _cosine_sim(a, b) == pytest.approx(0.0)

    assert _cosine_sim([], [1.0]) == 0.0
    assert _cosine_sim([1.0], []) == 0.0


def test_bag_of_words_embedding():
    """_bag_of_words_embedding produces fixed-dimension vectors."""
    emb = _bag_of_words_embedding("test document", dim=128)
    assert len(emb) == 128
    assert any(v != 0.0 for v in emb)  # Not all zeros

    emb2 = _bag_of_words_embedding("test document", dim=128)
    assert emb == emb2  # Deterministic

    emb_empty = _bag_of_words_embedding("", dim=128)
    assert emb_empty == [0.0] * 128


def test_similar_texts_higher_similarity():
    """Similar texts produce embeddings with higher cosine similarity."""
    emb_a = _bag_of_words_embedding("HLF deterministic orchestration protocol", dim=128)
    emb_b = _bag_of_words_embedding("HLF deterministic multi-agent protocol", dim=128)
    emb_c = _bag_of_words_embedding("Chocolate cake recipe with vanilla frosting", dim=128)

    sim_ab = _cosine_sim(emb_a, emb_b)
    sim_ac = _cosine_sim(emb_a, emb_c)
    assert sim_ab > sim_ac, f"Expected sim_ab ({sim_ab}) > sim_ac ({sim_ac})"


# ─────────────────────────────────────────────────────────────────── #
# 11. Simple BM25 Fallback Tests
# ─────────────────────────────────────────────────────────────────── #

def test_simple_bm25_index_and_search():
    """_SimpleBM25 fallback works correctly."""
    bm25 = _SimpleBM25()
    bm25.index("d1", "HLF deterministic protocol for agents")
    bm25.index("d2", "Chocolate cake recipe step by step")
    bm25.index("d3", "HLF agent orchestration and protocol")

    results = bm25.search("HLF protocol", k=2)
    assert len(results) == 2
    assert results[0][0] == "d1" or results[0][0] == "d3"
    assert results[0][1] >= results[1][1]  # Scores are non-ascending


def test_simple_bm25_remove_and_clear():
    """_SimpleBM25 remove and clear operations work."""
    bm25 = _SimpleBM25()
    bm25.index("d1", "document one")
    bm25.index("d2", "document two")

    assert bm25.remove("d1") is True
    assert bm25.remove("d1") is False  # Already removed
    results = bm25.search("document", k=2)
    assert len(results) == 1
    assert results[0][0] == "d2"

    bm25.clear()
    assert bm25.search("document") == []


# ─────────────────────────────────────────────────────────────────── #
# 12. In-Memory Vector Store Tests
# ─────────────────────────────────────────────────────────────────── #

def test_inmemory_vector_store():
    """_InMemoryVectorStore CRUD operations work."""
    vs = _InMemoryVectorStore()
    vs.add("v1", "text one", [1.0, 0.0, 0.0], {"topic": "a"})
    vs.add("v2", "text two", [0.0, 1.0, 0.0], {"topic": "b"})
    vs.add("v3", "text three", [1.0, 0.1, 0.0], {"topic": "a"})

    assert vs.count() == 3

    results = vs.search([1.0, 0.0, 0.0], k=2)
    assert len(results) == 2
    # v1 should be top match (exact match)
    assert results[0][0] == "v1"

    assert vs.remove("v1") is True
    assert vs.count() == 2

    vs.clear()
    assert vs.count() == 0


# ─────────────────────────────────────────────────────────────────── #
# 13. Integration feeds into RAG
# ─────────────────────────────────────────────────────────────────── #

def test_integration_data_feeds_into_rag(rag):
    """Integration stubs actually feed data into the RAG index."""
    initial_count = rag.count()

    # Janus crawl
    ji = JanusIntegration(rag=rag)
    ji.crawl("http://example.com")

    # ChronosGraph ingest
    ci = ChronosGraphIntegration(rag=rag)
    ci.ingest("Sample transcription from ChronosGraph")

    # BrowserOS compile
    bi = BrowserOSGuidesIntegration(rag=rag)
    bi.compile("test-guide")

    # LOLLMS import
    li = LOLLMSImport(rag=rag)
    li.import_datastore("test-ds")

    # MSTY import
    mi = MSTYImport(rag=rag)
    mi.import_knowledge_stack("test-stack")

    # AnythingLLM import
    ai = AnythingLLMImport(rag=rag)
    ai.import_workspace("test-ws")

    # All integrations should have fed data into RAG
    assert rag.count() > initial_count
