"""
Hybrid RAG Pipeline — BM25 + Vector + Cross-Encoder Reranker.

Phase 2 of UNIFIED_ECOSYSTEM_ROADMAP.md: Build Hybrid RAG pipeline.
Integrates keyword search (BM25), vector semantic search, and cross-encoder
reranking into a unified retrieval interface.

Sources:
  - Janus (conversation history)
  - ChronosGraph (temporal knowledge graph)
  - BrowserOS_Guides (documentation)
  - HKS exemplars (validated knowledge)

Architecture:
    Query → BM25 keyword search → Vector semantic search
           → Reciprocal Rank Fusion → Cross-encoder reranker
           → Final ranked results
"""

from __future__ import annotations

import logging
import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ─── Result Types ────────────────────────────────────────────────────────────


@dataclass
class SearchResult:
    """A single search result from any retrieval method."""

    doc_id: str
    text: str
    score: float = 0.0
    source: str = "unknown"          # janus, chronos, browseros, hks
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "text": self.text[:500],
            "score": round(self.score, 4),
            "source": self.source,
        }


@dataclass
class HybridSearchResult:
    """Aggregated hybrid search result with provenance."""

    results: list[SearchResult]
    query: str
    fusion_method: str = "rrf"        # reciprocal rank fusion
    reranker_applied: bool = False
    elapsed_ms: float = 0.0
    source_breakdown: dict[str, int] = field(default_factory=dict)

    def top_k(self, k: int = 5) -> list[SearchResult]:
        return self.results[:k]

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "total_results": len(self.results),
            "top_results": [r.to_dict() for r in self.results[:10]],
            "fusion": self.fusion_method,
            "reranked": self.reranker_applied,
            "sources": self.source_breakdown,
            "elapsed_ms": round(self.elapsed_ms, 1),
        }


# ─── BM25 Implementation ─────────────────────────────────────────────────────


class BM25Index:
    """Minimal BM25 keyword index with TF-IDF scoring.

    Uses Okapi BM25 formula:
        score(D, Q) = Σ IDF(qi) * (f(qi, D) * (k1 + 1)) / (f(qi, D) + k1 * (1 - b + b * |D|/avgdl))

    No external dependencies — pure Python implementation.
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self._docs: dict[str, str] = {}                  # doc_id → text
        self._doc_freqs: dict[str, int] = {}             # term → document frequency
        self._term_freqs: dict[str, dict[str, int]] = {} # doc_id → {term → count}
        self._avgdl: float = 0.0

    @property
    def doc_count(self) -> int:
        return len(self._docs)

    def index(self, doc_id: str, text: str) -> None:
        """Index a single document."""
        tokens = self._tokenize(text)
        self._docs[doc_id] = text
        self._term_freqs[doc_id] = {}

        seen_terms: set[str] = set()
        for token in tokens:
            self._term_freqs[doc_id][token] = self._term_freqs[doc_id].get(token, 0) + 1
            if token not in seen_terms:
                self._doc_freqs[token] = self._doc_freqs.get(token, 0) + 1
                seen_terms.add(token)

        # Recompute average doc length
        total_len = sum(len(self._tokenize(d)) for d in self._docs.values())
        self._avgdl = total_len / max(1, self.doc_count)

    def remove(self, doc_id: str) -> None:
        """Remove a document from the index."""
        if doc_id not in self._docs:
            return
        tokens = set(self._tokenize(self._docs[doc_id]))
        for token in tokens:
            self._doc_freqs[token] = max(0, self._doc_freqs.get(token, 1) - 1)
        self._docs.pop(doc_id, None)
        self._term_freqs.pop(doc_id, None)

    def search(self, query: str, top_k: int = 10) -> list[SearchResult]:
        """Search the BM25 index and return ranked results."""
        if not self._docs:
            return []

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        N = self.doc_count
        scores: dict[str, float] = {}

        for doc_id, doc_text in self._docs.items():
            doc_tfs = self._term_freqs.get(doc_id, {})
            doc_len = len(self._tokenize(doc_text))
            score = 0.0

            for qt in query_tokens:
                tf = doc_tfs.get(qt, 0)
                if tf == 0:
                    continue
                df = self._doc_freqs.get(qt, 0)
                idf = math.log((N - df + 0.5) / (df + 0.5) + 1.0)
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / max(1.0, self._avgdl))
                score += idf * numerator / denominator

            if score > 0:
                scores[doc_id] = score

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [
            SearchResult(
                doc_id=did,
                text=self._docs[did],
                score=score,
                source="bm25",
            )
            for did, score in ranked[:top_k]
        ]

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Simple lowercase tokenization."""
        return text.lower().replace(".", " ").replace(",", " ").replace(":", " ").split()


# ─── Reciprocal Rank Fusion ──────────────────────────────────────────────────


def reciprocal_rank_fusion(
    result_lists: list[list[SearchResult]],
    k: int = 60,
) -> list[SearchResult]:
    """Fuse multiple ranked result lists using Reciprocal Rank Fusion.

    RRF score = Σ 1 / (k + rank_i)
    where rank_i is the position (1-indexed) in each result list.
    """
    fused: dict[str, tuple[float, SearchResult]] = {}

    for results in result_lists:
        for rank, result in enumerate(results, start=1):
            rrf_score = 1.0 / (k + rank)
            if result.doc_id in fused:
                prev_score, prev_result = fused[result.doc_id]
                fused[result.doc_id] = (prev_score + rrf_score, prev_result)
            else:
                fused[result.doc_id] = (rrf_score, result)

    ranked = sorted(fused.values(), key=lambda x: x[0], reverse=True)
    return [
        SearchResult(
            doc_id=r.doc_id,
            text=r.text,
            score=fused_score,
            source=r.source,
            metadata={"rrf_contributions": len(result_lists)},
        )
        for fused_score, r in ranked
    ]


# ─── Cross-Encoder Reranker ──────────────────────────────────────────────────


class CrossEncoderReranker:
    """Lightweight cross-encoder reranker using pairwise scoring.

    Uses simple query-document overlap features when no ML model is available.
    Falls back gracefully — designed to work without sentence-transformers.
    """

    def __init__(self, model_name: str = "") -> None:
        self._model_name = model_name
        self._has_ml = False
        if model_name:
            self._try_load_ml(model_name)

    def _try_load_ml(self, model_name: str) -> None:
        """Attempt to load a sentence-transformers cross-encoder model."""
        try:
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(model_name)
            self._has_ml = True
            logger.info("Loaded cross-encoder model: %s", model_name)
        except ImportError:
            logger.debug("sentence-transformers not installed — using heuristic reranker")
        except Exception as exc:
            logger.debug("Failed to load cross-encoder: %s", exc)

    def rerank(
        self,
        query: str,
        candidates: list[SearchResult],
        top_k: int = 10,
    ) -> list[SearchResult]:
        """Rerank candidates using cross-encoder scores.

        When no ML model is available, uses a heuristic overlap + position score.
        """
        if not candidates:
            return []

        if self._has_ml:
            return self._ml_rerank(query, candidates, top_k)
        return self._heuristic_rerank(query, candidates, top_k)

    def _ml_rerank(
        self,
        query: str,
        candidates: list[SearchResult],
        top_k: int,
    ) -> list[SearchResult]:
        """ML-based cross-encoder reranking."""
        pairs = [(query, c.text[:1000]) for c in candidates]
        scores = self._model.predict(pairs)
        for result, score in zip(candidates, scores):
            result.score = float(score)
        reranked = sorted(candidates, key=lambda r: r.score, reverse=True)
        return reranked[:top_k]

    def _heuristic_rerank(
        self,
        query: str,
        candidates: list[SearchResult],
        top_k: int,
    ) -> list[SearchResult]:
        """Heuristic reranker using query-document overlap + source weight."""
        query_terms = set(query.lower().split())
        source_weights = {
            "janus": 1.2,        # Conversation history — highly relevant
            "chronos": 1.1,      # Temporal knowledge
            "hks": 1.0,          # Validated exemplars
            "browseros": 0.9,    # Documentation
            "bm25": 0.8,         # Keyword-only
            "vector": 0.8,       # Vector-only
            "unknown": 0.7,
        }

        for result in candidates:
            doc_terms = set(result.text.lower().split())
            overlap = len(query_terms & doc_terms) / max(1, len(query_terms))
            src_weight = source_weights.get(result.source, 0.7)
            result.score = result.score * 0.5 + overlap * src_weight * 0.5

        reranked = sorted(candidates, key=lambda r: r.score, reverse=True)
        return reranked[:top_k]


# ─── Hybrid RAG Pipeline ─────────────────────────────────────────────────────


class HybridRAGPipeline:
    """Complete Hybrid RAG pipeline: BM25 + Vector + RRF + Reranker.

    Usage:
        pipeline = HybridRAGPipeline()
        pipeline.index_document("doc1", "Some text content", source="janus")
        results = pipeline.search("query text", top_k=5)
    """

    def __init__(
        self,
        bm25_k1: float = 1.5,
        bm25_b: float = 0.75,
        reranker_model: str = "",
    ) -> None:
        self._bm25 = BM25Index(k1=bm25_k1, b=bm25_b)
        self._reranker = CrossEncoderReranker(model_name=reranker_model)
        self._vector_store: list[tuple[str, str, str]] = []  # [(doc_id, text, source)]
        self._has_vector_search = False
        self._try_init_vector()

    def _try_init_vector(self) -> None:
        """Try to initialize vector search via existing HKS infrastructure."""
        try:
            from hlf_mcp.rag.memory import HybridKnowledgeStore
            self._hks = HybridKnowledgeStore()
            self._has_vector_search = True
            logger.info("Hybrid RAG pipeline: vector search enabled via HKS")
        except (ImportError, AttributeError) as exc:
            logger.debug("Vector search disabled: %s", exc)
            self._hks = None  # type: ignore[assignment]

    # ── Indexing ──────────────────────────────────────────────────────────

    def index_document(
        self,
        doc_id: str,
        text: str,
        source: str = "unknown",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Index a document in BM25 and optionally the vector store."""
        self._bm25.index(doc_id, text)
        self._vector_store.append((doc_id, text, source))

    def index_batch(
        self,
        documents: list[tuple[str, str, str]],
    ) -> None:
        """Index multiple (doc_id, text, source) tuples."""
        for doc_id, text, source in documents:
            self.index_document(doc_id, text, source)

    # ── Search ────────────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        top_k: int = 10,
        sources: list[str] | None = None,
        use_reranker: bool = True,
    ) -> HybridSearchResult:
        """Execute hybrid search: BM25 → Vector → RRF → Reranker."""
        t0 = time.perf_counter()

        # 1. BM25 keyword search
        bm25_results = self._bm25.search(query, top_k=top_k * 2)

        # 2. Vector semantic search (via HKS if available)
        vector_results: list[SearchResult] = []
        if self._has_vector_search and self._hks:
            vector_results = self._vector_search(query, top_k=top_k * 2)

        # 3. Reciprocal Rank Fusion
        result_lists: list[list[SearchResult]] = []
        if bm25_results:
            result_lists.append(bm25_results)
        if vector_results:
            result_lists.append(vector_results)
        if not result_lists:
            # Fallback: text overlap scan
            result_lists.append(self._fallback_scan(query, top_k))

        fused = reciprocal_rank_fusion(result_lists)

        # 4. Cross-encoder reranker
        if use_reranker and len(fused) > 1:
            fused = self._reranker.rerank(query, fused, top_k=top_k)

        # 5. Filter by source if requested
        if sources:
            fused = [r for r in fused if r.source in sources]

        # Source breakdown
        breakdown: dict[str, int] = defaultdict(int)
        for r in fused:
            breakdown[r.source] += 1

        elapsed = (time.perf_counter() - t0) * 1000

        return HybridSearchResult(
            results=fused[:top_k],
            query=query,
            fusion_method="rrf",
            reranker_applied=use_reranker and len(fused) > 1,
            elapsed_ms=elapsed,
            source_breakdown=dict(breakdown),
        )

    def _vector_search(self, query: str, top_k: int) -> list[SearchResult]:
        """Vector semantic search via HKS."""
        try:
            if self._hks is None:
                return []
            hks_results = self._hks.hybrid_search(query=query, limit=top_k, include_witness=True)
            search_results: list[SearchResult] = []
            for item in hks_results if isinstance(hks_results, list) else []:
                if isinstance(item, dict):
                    search_results.append(SearchResult(
                        doc_id=item.get("id", ""),
                        text=item.get("text", item.get("content", "")),
                        score=item.get("score", 0.0),
                        source=item.get("source", "hks"),
                    ))
            return search_results
        except Exception as exc:
            logger.debug("Vector search failed: %s", exc)
            return []

    def _fallback_scan(self, query: str, top_k: int) -> list[SearchResult]:
        """Simple text overlap scan when no index is available."""
        query_terms = set(query.lower().split())
        scored: list[tuple[float, SearchResult]] = []
        for doc_id, text, source in self._vector_store:
            doc_terms = set(text.lower().split())
            overlap = len(query_terms & doc_terms) / max(1, len(query_terms))
            if overlap > 0:
                scored.append((overlap, SearchResult(doc_id=doc_id, text=text, score=overlap, source=source)))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [sr for _, sr in scored[:top_k]]

    # ── Management ────────────────────────────────────────────────────────

    @property
    def doc_count(self) -> int:
        return self._bm25.doc_count

    @property
    def has_vector(self) -> bool:
        return self._has_vector_search

    def stats(self) -> dict[str, Any]:
        return {
            "bm25_docs": self._bm25.doc_count,
            "vector_store_docs": len(self._vector_store),
            "vector_search_enabled": self._has_vector_search,
            "reranker_ml_enabled": self._reranker._has_ml,
        }

    def clear(self) -> None:
        """Clear all indices."""
        self._bm25 = BM25Index(k1=self._bm25.k1, b=self._bm25.b)
        self._vector_store.clear()


# ─── Module-level singleton ──────────────────────────────────────────────────

_pipeline: HybridRAGPipeline | None = None


def get_hybrid_rag() -> HybridRAGPipeline:
    """Get or create the singleton Hybrid RAG pipeline."""
    global _pipeline
    if _pipeline is None:
        _pipeline = HybridRAGPipeline()
    return _pipeline


def search_hybrid(
    query: str,
    top_k: int = 10,
    sources: list[str] | None = None,
) -> HybridSearchResult:
    """Convenience function: search the hybrid RAG pipeline."""
    return get_hybrid_rag().search(query, top_k=top_k, sources=sources)
