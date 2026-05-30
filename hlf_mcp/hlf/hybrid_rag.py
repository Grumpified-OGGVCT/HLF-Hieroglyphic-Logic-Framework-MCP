"""
Hybrid RAG Pipeline — BM25 + Vector + Cross-Encoder Reranker.

Canonical implementation (794 lines) used by RAGService.

Provides:
- BM25 index: TF-IDF BM25 keyword search via rank_bm25 (or internal fallback)
- Vector store: ChromaDB semantic search (or in-memory fallback)
- Cross-encoder reranker: lightweight cross-encoder for result fusion
- Hybrid search: merged, deduplicated, and reranked results
- Index management: add, remove, clear with thread safety

Thread-safe with RWLock.

Note: A smaller parallel implementation (487 lines) exists at
hlf_mcp/rag/hybrid_rag.py, preserved for potential future use in the rag/
subpackage. That file is not currently imported by any production code.
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
import threading
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, ClassVar

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Try optional dependencies — graceful fallbacks
# ------------------------------------------------------------------ #

try:
    from rank_bm25 import BM25Okapi as _ExternalBM25

    _BM25_AVAILABLE = True
except ImportError:
    _BM25_AVAILABLE = False
    logger.info("rank_bm25 not available; using internal TF-IDF BM25")

try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings

    _CHROMA_AVAILABLE = True
except ImportError:
    _CHROMA_AVAILABLE = False
    logger.info("chromadb not available; using in-memory vector store")


# ------------------------------------------------------------------ #
# Internal BM25 implementation (fallback when rank_bm25 missing)
# ------------------------------------------------------------------ #

def _tokenize(text: str) -> list[str]:
    """Simple whitespace + lowercase tokenizer."""
    return re.findall(r"[a-z0-9]{2,}", text.lower())


class _SimpleBM25:
    """Pure-Python BM25 implementation.

    Implements Okapi BM25 scoring without external dependencies.
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self._docs: list[list[str]] = []
        self._doc_ids: list[str] = []
        self._dl: list[int] = []  # document lengths
        self._df: dict[str, int] = {}  # document frequency
        self._avgdl: float = 0.0
        self._n: int = 0
        self._idf_cache: dict[str, float] = {}

    def _compute_idf(self, term: str) -> float:
        if term in self._idf_cache:
            return self._idf_cache[term]
        df = self._df.get(term, 0)
        idf = math.log((self._n - df + 0.5) / (df + 0.5) + 1.0)
        self._idf_cache[term] = idf
        return idf

    def index(self, doc_id: str, text: str) -> None:
        tokens = _tokenize(text)
        self._docs.append(tokens)
        self._doc_ids.append(doc_id)
        self._dl.append(len(tokens))
        self._n += 1

        for token in set(tokens):
            self._df[token] = self._df.get(token, 0) + 1

        self._avgdl = sum(self._dl) / max(1, self._n)
        self._idf_cache = {}

    def remove(self, doc_id: str) -> bool:
        for i, did in enumerate(self._doc_ids):
            if did == doc_id:
                tokens = self._docs[i]
                for token in set(tokens):
                    self._df[token] = max(0, self._df.get(token, 0) - 1)
                del self._docs[i]
                del self._doc_ids[i]
                del self._dl[i]
                self._n -= 1
                self._avgdl = sum(self._dl) / max(1, self._n)
                self._idf_cache = {}
                return True
        return False

    def get_scores(self, query: str) -> list[tuple[str, float]]:
        query_tokens = _tokenize(query)
        if not self._docs or not query_tokens:
            return []

        scores: list[tuple[str, float]] = []
        for i, doc in enumerate(self._docs):
            score = 0.0
            doc_len = self._dl[i]
            for token in query_tokens:
                if token not in self._df:
                    continue
                idf = self._compute_idf(token)
                tf = doc.count(token)
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / max(1, self._avgdl))
                score += idf * numerator / denominator
            scores.append((self._doc_ids[i], score))
        return scores

    def search(self, query: str, k: int = 10) -> list[tuple[str, float]]:
        scored = self.get_scores(query)
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:k]

    def clear(self) -> None:
        self._docs.clear()
        self._doc_ids.clear()
        self._dl.clear()
        self._df.clear()
        self._idf_cache.clear()
        self._n = 0
        self._avgdl = 0.0


# ------------------------------------------------------------------ #
# In-memory vector store (fallback when chromadb missing)
# ------------------------------------------------------------------ #

class _InMemoryVectorStore:
    """Cosine-similarity vector store backed by a Python dict."""

    def __init__(self):
        self._vectors: dict[str, list[float]] = {}
        self._metadata: dict[str, dict[str, Any]] = {}

    def add(self, doc_id: str, text: str, embedding: list[float], metadata: dict[str, Any] | None = None) -> None:
        self._vectors[doc_id] = embedding
        self._metadata[doc_id] = {
            "text": text,
            "metadata": metadata or {},
        }

    def remove(self, doc_id: str) -> bool:
        existed = doc_id in self._vectors
        self._vectors.pop(doc_id, None)
        self._metadata.pop(doc_id, None)
        return existed

    def search(self, query_embedding: list[float], k: int = 10) -> list[tuple[str, float, str, dict]]:
        results = []
        for doc_id, emb in self._vectors.items():
            sim = _cosine_sim(query_embedding, emb)
            if sim > 0:
                meta = self._metadata.get(doc_id, {})
                results.append((doc_id, sim, meta.get("text", ""), meta.get("metadata", {})))
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:k]

    def clear(self) -> None:
        self._vectors.clear()
        self._metadata.clear()

    def count(self) -> int:
        return len(self._vectors)


# ------------------------------------------------------------------ #
# ChromaDB-backed vector store
# ------------------------------------------------------------------ #

class _ChromaVectorStore:
    """ChromaDB-backed vector store.

    Connects to chromadb server at CHROMA_HOST:CHROMA_PORT
    (defaults to localhost:8000 for docker container memory-chromadb).
    Falls back to in-memory chromadb if server unavailable.
    """

    def __init__(self, collection_name: str = "hlf_hybrid_rag"):
        self._collection_name = collection_name
        self._client = None
        self._collection = None
        self._fallback = _InMemoryVectorStore()
        self._using_fallback = False
        self._init_chroma()

    def _init_chroma(self) -> None:
        try:
            import os

            host = os.environ.get("CHROMA_HOST", "localhost")
            port = os.environ.get("CHROMA_PORT", "8000")

            self._client = chromadb.HttpClient(
                host=host,
                port=int(port),
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            # Test connection
            self._client.heartbeat()
            self._collection = self._client.get_or_create_collection(
                name=self._collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info(f"Connected to ChromaDB at {host}:{port}")
        except Exception as e:
            logger.warning(f"ChromaDB server unavailable ({e}); using in-memory fallback")
            self._using_fallback = True
            try:
                self._client = chromadb.Client(
                    ChromaSettings(anonymized_telemetry=False, is_persistent=False)
                )
                self._collection = self._client.get_or_create_collection(
                    name=self._collection_name,
                    metadata={"hnsw:space": "cosine"},
                )
                logger.info("Using in-memory ChromaDB")
            except Exception as e2:
                logger.warning(f"In-memory ChromaDB also failed ({e2}); using dict fallback")
                self._using_fallback = True

    def add(self, doc_id: str, text: str, embedding: list[float], metadata: dict[str, Any] | None = None) -> None:
        if self._using_fallback or self._collection is None:
            self._fallback.add(doc_id, text, embedding, metadata)
            return
        try:
            self._collection.upsert(
                ids=[doc_id],
                embeddings=[embedding],
                documents=[text],
                metadatas=[metadata or {}],
            )
        except Exception as e:
            logger.warning(f"ChromaDB add failed ({e}); using fallback")
            self._fallback.add(doc_id, text, embedding, metadata)

    def remove(self, doc_id: str) -> bool:
        self._fallback.remove(doc_id)
        if not self._using_fallback and self._collection is not None:
            try:
                self._collection.delete(ids=[doc_id])
            except Exception:
                pass
        return True

    def search(self, query_embedding: list[float], k: int = 10) -> list[tuple[str, float, str, dict]]:
        if self._using_fallback or self._collection is None:
            return self._fallback.search(query_embedding, k)
        try:
            results = self._collection.query(query_embeddings=[query_embedding], n_results=k)
            ids = results.get("ids", [[]])[0]
            distances = results.get("distances", [[]])[0]
            documents = results.get("documents", [[]])[0]
            metadatas = results.get("metadatas", [[]])[0]

            out = []
            for i, doc_id in enumerate(ids):
                # Convert distance to similarity (cosine distance → similarity)
                dist = distances[i] if i < len(distances) else 0.0
                sim = 1.0 - dist if isinstance(dist, (int, float)) else 0.5
                doc_text = documents[i] if i < len(documents) else ""
                meta = metadatas[i] if i < len(metadatas) else {}
                out.append((doc_id, sim, doc_text or "", meta or {}))
            return out
        except Exception as e:
            logger.warning(f"ChromaDB search failed ({e}); using fallback")
            return self._fallback.search(query_embedding, k)

    def clear(self) -> None:
        self._fallback.clear()
        if not self._using_fallback and self._collection is not None:
            try:
                self._collection.delete(where={})
            except Exception:
                pass

    def count(self) -> int:
        if not self._using_fallback and self._collection is not None:
            try:
                return self._collection.count()
            except Exception:
                pass
        return self._fallback.count()


# ------------------------------------------------------------------ #
# Lightweight Cross-Encoder Reranker
# ------------------------------------------------------------------ #

class _CrossEncoderReranker:
    """Lightweight cross-encoder for reranking search results.

    Uses TF-IDF overlap + keyword density scoring as a proxy for
    cross-encoding. In production, this could be replaced with a
    sentence-transformers CrossEncoder model.
    """

    def __init__(self):
        self._doc_idf: dict[str, dict[str, float]] = {}

    def _token_tfidf(self, text: str) -> dict[str, float]:
        tokens = _tokenize(text)
        if not tokens:
            return {}
        tf: dict[str, int] = {}
        for t in tokens:
            tf[t] = tf.get(t, 0) + 1
        total = len(tokens)
        return {t: c / total for t, c in tf.items()}

    def score(self, query: str, document: str) -> float:
        """Score a document against a query (0..1)."""
        if not query or not document:
            return 0.0

        query_tfidf = self._token_tfidf(query)
        doc_tfidf = self._token_tfidf(document)

        # Intersection-based scoring + exact phrase overlap bonus
        all_terms = set(query_tfidf) | set(doc_tfidf)
        if not all_terms:
            return 0.0

        dot = sum(query_tfidf.get(t, 0) * doc_tfidf.get(t, 0) for t in all_terms)
        q_norm = math.sqrt(sum(v * v for v in query_tfidf.values()))
        d_norm = math.sqrt(sum(v * v for v in doc_tfidf.values()))

        cosine = dot / max(1e-9, q_norm * d_norm)

        # Phrase overlap bonus
        query_lower = query.lower()
        doc_lower = document.lower()
        phrase_bonus = 0.0
        if query_lower in doc_lower:
            phrase_bonus = 0.3
        elif any(word in doc_lower for word in query_lower.split()):
            phrase_bonus = 0.15

        return min(1.0, cosine + phrase_bonus)

    def rerank(self, query: str, candidates: list[tuple[str, float, str, dict]]) -> list[tuple[str, float, str, dict]]:
        """Rerank candidates using cross-encoder scores."""
        if not candidates:
            return []

        scored = []
        for doc_id, prev_score, text, meta in candidates:
            ce_score = self.score(query, text or "")
            # Blend: 60% cross-encoder, 40% previous score
            blended = 0.6 * ce_score + 0.4 * min(1.0, prev_score)
            scored.append((doc_id, blended, text, meta))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored


# ------------------------------------------------------------------ #
# Embedding helpers
# ------------------------------------------------------------------ #

def _cosine_sim(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two equal-length vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    return dot / (mag_a * mag_b) if mag_a and mag_b else 0.0


def _bag_of_words_embedding(text: str, dim: int = 128) -> list[float]:
    """Generate a deterministic bag-of-tokens embedding vector.

    Uses a deterministic hashing approach to produce fixed-dimension
    vectors suitable for semantic comparison without an ML model.
    """
    tokens = _tokenize(text)
    if not tokens:
        return [0.0] * dim

    vec = [0.0] * dim
    for i, token in enumerate(tokens):
        h = hashlib.sha256(token.encode()).digest()
        for j in range(0, len(h), 4):
            idx = int.from_bytes(h[j : j + 4], "big") % dim
            vec[idx] += 1.0 / (i + 1)  # Position-weighted

    # L2 normalize
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]

    return vec


# ------------------------------------------------------------------ #
# Document store
# ------------------------------------------------------------------ #

@dataclass
class RAGDocument:
    """Document stored in the Hybrid RAG index."""

    doc_id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    embedding: list[float] | None = None
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "text": self.text,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }


# ------------------------------------------------------------------ #
# HybridRAG
# ------------------------------------------------------------------ #

class HybridRAG:
    """Hybrid Retrieval-Augmented Generation pipeline.

    Combines BM25 keyword search, vector/semantic search, and
    cross-encoder reranking for high-quality retrieval.

    Thread-safe via re-entrant lock.
    """

    _instance: ClassVar[HybridRAG | None] = None
    _instance_lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(
        self,
        chroma_host: str | None = None,
        chroma_port: int | None = None,
        embedding_dim: int = 128,
        use_chroma: bool = True,
    ):
        """Initialize HybridRAG.

        Args:
            chroma_host: ChromaDB host (defaults to CHROMA_HOST env or localhost)
            chroma_port: ChromaDB port (defaults to CHROMA_PORT env or 8000)
            embedding_dim: Dimension for bag-of-words embeddings
            use_chroma: Whether to attempt ChromaDB connection
        """
        self._lock = threading.RLock()
        self._embedding_dim = embedding_dim
        self._documents: OrderedDict[str, RAGDocument] = OrderedDict()

        # BM25 index
        if _BM25_AVAILABLE:
            self._bm25: Any = None  # rank_bm25 instance, initialised lazily
            self._bm25_docs: list[list[str]] = []
            self._bm25_ids: list[str] = []
        else:
            self._bm25 = _SimpleBM25()

        # Vector store
        self._use_chroma = use_chroma
        if use_chroma and _CHROMA_AVAILABLE:
            # Override env if explicitly provided
            if chroma_host is not None:
                import os

                os.environ["CHROMA_HOST"] = chroma_host
            if chroma_port is not None:
                import os

                os.environ["CHROMA_PORT"] = str(chroma_port)
            self._vector_store: _ChromaVectorStore | _InMemoryVectorStore = _ChromaVectorStore()
        else:
            self._vector_store = _InMemoryVectorStore()

        # Cross-encoder reranker
        self._reranker = _CrossEncoderReranker()

        # Rebuild tracking
        self._bm25_dirty = False

    # -- Singleton -------------------------------------------------------

    @classmethod
    def get_instance(cls, **kwargs) -> "HybridRAG":
        """Get or create singleton HybridRAG instance."""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls(**kwargs)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton (primarily for testing)."""
        with cls._instance_lock:
            cls._instance = None

    # -- BM25 helpers ----------------------------------------------------

    def _ensure_bm25(self) -> None:
        """Rebuild BM25 index if dirty."""
        if _BM25_AVAILABLE:
            if self._bm25_dirty or self._bm25 is None:
                tokenized = []
                ids_list = []
                for doc_id, doc in self._documents.items():
                    tokenized.append(_tokenize(doc.text))
                    ids_list.append(doc_id)
                if tokenized:
                    self._bm25 = _ExternalBM25(tokenized)
                else:
                    self._bm25 = None
                self._bm25_docs = tokenized
                self._bm25_ids = ids_list
                self._bm25_dirty = False

    def _bm25_search(self, query: str, k: int) -> list[tuple[str, float]]:
        """Run BM25 keyword search."""
        if _BM25_AVAILABLE:
            self._ensure_bm25()
            if self._bm25 is None or not self._bm25_docs:
                return []
            query_tokens = _tokenize(query)
            if not query_tokens:
                return []
            scores = self._bm25.get_scores(query_tokens)
            ranked = sorted(
                zip(self._bm25_ids, scores), key=lambda x: x[1], reverse=True
            )
            # Normalize scores to [0, 1]
            max_score = ranked[0][1] if ranked else 1.0
            if max_score > 0:
                return [(doc_id, min(1.0, s / max_score)) for doc_id, s in ranked[:k]]
            return [(doc_id, 0.0) for doc_id, _ in ranked[:k]]
        else:
            return self._bm25.search(query, k)

    # -- Index management ------------------------------------------------

    def add_document(
        self,
        doc_id: str | None = None,
        text: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Add a document to all indexes.

        Args:
            doc_id: Unique document ID (auto-generated if None)
            text: Document text content
            metadata: Optional metadata dict

        Returns:
            The document ID
        """
        if doc_id is None:
            doc_id = str(uuid.uuid4())

        metadata = metadata or {}

        # Generate embedding
        embedding = _bag_of_words_embedding(text, self._embedding_dim)

        with self._lock:
            doc = RAGDocument(
                doc_id=doc_id,
                text=text,
                metadata=metadata,
                embedding=embedding,
            )

            # Store document
            self._documents[doc_id] = doc

            # Add to BM25
            if _BM25_AVAILABLE:
                self._bm25_dirty = True
            else:
                self._bm25.index(doc_id, text)

            # Add to vector store
            self._vector_store.add(doc_id, text, embedding, metadata)

        return doc_id

    def remove_document(self, doc_id: str) -> bool:
        """Remove a document from all indexes.

        Args:
            doc_id: Document ID to remove

        Returns:
            True if document existed and was removed
        """
        with self._lock:
            existed = doc_id in self._documents
            if existed:
                del self._documents[doc_id]

                # Remove from BM25
                if _BM25_AVAILABLE:
                    self._bm25_dirty = True
                else:
                    self._bm25.remove(doc_id)

                # Remove from vector store
                self._vector_store.remove(doc_id)

            return existed

    def clear_index(self) -> None:
        """Remove all documents from the index."""
        with self._lock:
            self._documents.clear()
            if _BM25_AVAILABLE:
                self._bm25 = None
                self._bm25_docs.clear()
                self._bm25_ids.clear()
                self._bm25_dirty = False
            else:
                self._bm25.clear()
            self._vector_store.clear()

    # -- Search ----------------------------------------------------------

    def search(
        self,
        query: str,
        k: int = 10,
        *,
        bm25_weight: float = 0.4,
        vector_weight: float = 0.6,
        rerank: bool = True,
    ) -> list[dict[str, Any]]:
        """Hybrid search combining BM25 and vector results.

        Args:
            query: Search query string
            k: Number of results to return
            bm25_weight: Weight for BM25 scores in fusion (0-1)
            vector_weight: Weight for vector scores in fusion (0-1)
            rerank: Whether to apply cross-encoder reranking

        Returns:
            List of result dicts with keys:
              doc_id, text, score, metadata, bm25_score, vector_score
        """
        with self._lock:
            # Generate query embedding
            query_embedding = _bag_of_words_embedding(query, self._embedding_dim)

            # BM25 search
            bm25_results = self._bm25_search(query, k * 2)
            bm25_scores: dict[str, float] = {doc_id: s for doc_id, s in bm25_results}

            # Vector search
            vector_results = self._vector_store.search(query_embedding, k * 2)
            vector_scores: dict[str, float] = {
                doc_id: s for doc_id, s, _, _ in vector_results
            }

            # Merge and fuse scores
            all_ids = set(bm25_scores) | set(vector_scores)
            fused: list[tuple[str, float, str, dict]] = []
            for doc_id in all_ids:
                doc = self._documents.get(doc_id)
                if doc is None:
                    continue
                bm25_s = bm25_scores.get(doc_id, 0.0)
                vec_s = vector_scores.get(doc_id, 0.0)
                fused_score = bm25_weight * bm25_s + vector_weight * vec_s
                fused.append((doc_id, fused_score, doc.text, doc.metadata))

            # Sort by fused score
            fused.sort(key=lambda x: x[1], reverse=True)

            # Rerank with cross-encoder
            if rerank and fused:
                fused = self._reranker.rerank(query, fused)

            # Trim to k
            fused = fused[:k]

            # Build results
            results = []
            for doc_id, score, text, meta in fused:
                results.append(
                    {
                        "doc_id": doc_id,
                        "text": text,
                        "score": round(score, 4),
                        "bm25_score": round(bm25_scores.get(doc_id, 0.0), 4),
                        "vector_score": round(vector_scores.get(doc_id, 0.0), 4),
                        "metadata": meta,
                    }
                )

            return results

    def bm25_search(self, query: str, k: int = 10) -> list[dict[str, Any]]:
        """BM25-only search."""
        with self._lock:
            results = self._bm25_search(query, k)
            return [
                {
                    "doc_id": doc_id,
                    "text": self._documents.get(doc_id, RAGDocument(doc_id, "")).text,
                    "score": round(score, 4),
                    "metadata": self._documents.get(
                        doc_id, RAGDocument(doc_id, "")
                    ).metadata,
                }
                for doc_id, score in results
                if doc_id in self._documents
            ]

    def vector_search(self, query: str, k: int = 10) -> list[dict[str, Any]]:
        """Vector-only search."""
        with self._lock:
            query_embedding = _bag_of_words_embedding(query, self._embedding_dim)
            results = self._vector_store.search(query_embedding, k)
            return [
                {
                    "doc_id": doc_id,
                    "text": text,
                    "score": round(score, 4),
                    "metadata": meta,
                }
                for doc_id, score, text, meta in results
            ]

    # -- Stats -----------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """Get index statistics."""
        with self._lock:
            doc_count = len(self._documents)
            total_chars = sum(len(d.text) for d in self._documents.values())
            return {
                "document_count": doc_count,
                "total_characters": total_chars,
                "bm25_available": _BM25_AVAILABLE or True,  # internal fallback always available
                "chroma_available": _CHROMA_AVAILABLE,
                "using_chroma_vector_store": isinstance(
                    self._vector_store, _ChromaVectorStore
                )
                and not self._vector_store._using_fallback,
                "embedding_dim": self._embedding_dim,
            }

    def count(self) -> int:
        """Number of indexed documents."""
        with self._lock:
            return len(self._documents)


# ------------------------------------------------------------------ #
# Convenience
# ------------------------------------------------------------------ #

def create_hybrid_rag(**kwargs) -> HybridRAG:
    """Create a new HybridRAG instance."""
    return HybridRAG(**kwargs)


def get_hybrid_rag(**kwargs) -> HybridRAG:
    """Get the singleton HybridRAG instance."""
    return HybridRAG.get_instance(**kwargs)
