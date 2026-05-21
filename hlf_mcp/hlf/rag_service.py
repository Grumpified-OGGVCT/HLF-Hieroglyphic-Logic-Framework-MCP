"""
RAG Service — Singleton service for Hybrid RAG + Integrations.

Provides:
- Lazy initialization of HybridRAG (in-memory, falls back gracefully)
- External knowledge import (LOLLMS, MSTY, AnythingLLM)
- Primary search interface
- Health checks with index statistics
- Integration management (Janus, ChronosGraph, BrowserOS)
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)


class RAGService:
    """Singleton RAG service managing HybridRAG and all integrations.

    Usage:
        svc = RAGService.get_instance()
        results = svc.search("what is HLF?")
        svc.import_lollms_datastore("my-datastore")
    """

    _instance: RAGService | None = None
    _instance_lock: threading.Lock = threading.Lock()

    def __init__(self):
        """Initialize RAG service (use get_instance() instead)."""
        self._initialized = False
        self._init_lock = threading.Lock()

        # Lazily loaded
        self._rag = None
        self._integrations: dict[str, Any] = {}
        self._start_time = time.time()

    # -- Singleton -------------------------------------------------------

    @classmethod
    def get_instance(cls) -> "RAGService":
        """Get or create the singleton RAGService."""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    instance = cls()
                    instance._ensure_initialized()
                    cls._instance = instance
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton (primarily for testing)."""
        with cls._instance_lock:
            if cls._instance is not None:
                try:
                    cls._instance._rag.clear_index()
                except Exception:
                    pass
            cls._instance = None

    def _ensure_initialized(self) -> None:
        """Lazy initialization of RAG and integrations."""
        if self._initialized:
            return
        with self._init_lock:
            if self._initialized:
                return
            self._init_rag()
            self._init_integrations()
            self._initialized = True
            logger.info("RAGService initialized")

    def _init_rag(self) -> None:
        """Initialize HybridRAG with graceful fallback chain."""
        from hlf_mcp.hlf.hybrid_rag import HybridRAG

        self._rag = HybridRAG(
            use_chroma=True,  # Try ChromaDB, fall back gracefully
            embedding_dim=128,
        )
        logger.info("HybridRAG initialized (in-memory)")

    def _init_integrations(self) -> None:
        """Initialize all integration modules."""
        from hlf_mcp.hlf.rag_integrations import create_all_integrations

        self._integrations = create_all_integrations(rag=self._rag)
        logger.info(f"Initialized {len(self._integrations)} RAG integrations")

    # -- Properties ------------------------------------------------------

    @property
    def rag(self):
        """Access the HybridRAG instance (lazy init)."""
        self._ensure_initialized()
        return self._rag

    @property
    def integrations(self) -> dict[str, Any]:
        """Access integration instances (lazy init)."""
        self._ensure_initialized()
        return self._integrations

    # -- Search Interface ------------------------------------------------

    def search(self, query: str, k: int = 10, **kwargs) -> list[dict[str, Any]]:
        """Primary search interface — hybrid BM25 + vector + rerank.

        Args:
            query: Search query
            k: Number of results
            **kwargs: Passed to HybridRAG.search()

        Returns:
            List of result dicts
        """
        self._ensure_initialized()
        return self._rag.search(query, k=k, **kwargs)

    def bm25_search(self, query: str, k: int = 10) -> list[dict[str, Any]]:
        """BM25-only keyword search."""
        self._ensure_initialized()
        return self._rag.bm25_search(query, k=k)

    def vector_search(self, query: str, k: int = 10) -> list[dict[str, Any]]:
        """Vector-only semantic search."""
        self._ensure_initialized()
        return self._rag.vector_search(query, k=k)

    # -- Index Management ------------------------------------------------

    def add_document(self, text: str, metadata: dict[str, Any] | None = None, doc_id: str | None = None) -> str:
        """Add a document to the RAG index.

        Args:
            text: Document text
            metadata: Optional metadata
            doc_id: Optional document ID (auto-generated if None)

        Returns:
            Document ID
        """
        self._ensure_initialized()
        return self._rag.add_document(doc_id=doc_id, text=text, metadata=metadata)

    def remove_document(self, doc_id: str) -> bool:
        """Remove a document from the RAG index."""
        self._ensure_initialized()
        return self._rag.remove_document(doc_id)

    def clear_index(self) -> None:
        """Clear all documents from the RAG index."""
        self._ensure_initialized()
        self._rag.clear_index()

    # -- External Imports ------------------------------------------------

    def import_lollms_datastore(self, datastore_id: str) -> dict[str, Any]:
        """Import a LOLLMS DataStore into RAG."""
        self._ensure_initialized()
        integration = self._integrations.get("lollms")
        if integration is None:
            return {"status": "error", "message": "LOLLMS integration not available"}
        evidence = integration.import_datastore(datastore_id)
        return {"status": "ok", "evidence": evidence.to_dict()}

    def import_msty_knowledge_stack(self, stack_id: str) -> dict[str, Any]:
        """Import an MSTY Knowledge Stack into RAG."""
        self._ensure_initialized()
        integration = self._integrations.get("msty")
        if integration is None:
            return {"status": "error", "message": "MSTY integration not available"}
        evidence = integration.import_knowledge_stack(stack_id)
        return {"status": "ok", "evidence": evidence.to_dict()}

    def import_anythingllm_workspace(self, workspace_id: str) -> dict[str, Any]:
        """Import an AnythingLLM workspace into RAG."""
        self._ensure_initialized()
        integration = self._integrations.get("anythingllm")
        if integration is None:
            return {"status": "error", "message": "AnythingLLM integration not available"}
        evidence = integration.import_workspace(workspace_id)
        return {"status": "ok", "evidence": evidence.to_dict()}

    # -- Janus Operations ------------------------------------------------

    def janus_crawl(self, url: str, depth: int = 1) -> dict[str, Any]:
        """Crawl a URL via Janus integration."""
        self._ensure_initialized()
        integration = self._integrations.get("janus")
        if integration is None:
            return {"status": "error", "message": "Janus integration not available"}
        evidence = integration.crawl(url, depth=depth)
        return {"status": "ok", "evidence": evidence.to_dict()}

    def janus_query(self, query_text: str) -> dict[str, Any]:
        """Query Janus knowledge graph."""
        self._ensure_initialized()
        integration = self._integrations.get("janus")
        if integration is None:
            return {"status": "error", "message": "Janus integration not available"}
        return integration.query(query_text)

    def janus_archive(self, resource_id: str) -> dict[str, Any]:
        """Archive a Janus resource."""
        self._ensure_initialized()
        integration = self._integrations.get("janus")
        if integration is None:
            return {"status": "error", "message": "Janus integration not available"}
        evidence = integration.archive(resource_id)
        return {"status": "ok", "evidence": evidence.to_dict()}

    # -- ChronosGraph Operations -----------------------------------------

    def chronos_transcribe(self, video_path: str, language: str = "en") -> dict[str, Any]:
        """Transcribe a video via ChronosGraph."""
        self._ensure_initialized()
        integration = self._integrations.get("chronos_graph")
        if integration is None:
            return {"status": "error", "message": "ChronosGraph integration not available"}
        result = integration.transcribe(video_path, language=language)
        return {"status": "ok", **result}

    def chronos_ingest(self, transcription: str | dict[str, Any]) -> dict[str, Any]:
        """Ingest a transcription into RAG."""
        self._ensure_initialized()
        integration = self._integrations.get("chronos_graph")
        if integration is None:
            return {"status": "error", "message": "ChronosGraph integration not available"}
        evidence = integration.ingest(transcription)
        return {"status": "ok", "evidence": evidence.to_dict()}

    # -- BrowserOS Operations --------------------------------------------

    def browseros_extract(self, url: str) -> dict[str, Any]:
        """Extract knowledge from a BrowserOS guide."""
        self._ensure_initialized()
        integration = self._integrations.get("browseros_guides")
        if integration is None:
            return {"status": "error", "message": "BrowserOS Guides integration not available"}
        result = integration.extract(url)
        return {"status": "ok", **result}

    def browseros_compile(self, guide_id: str) -> dict[str, Any]:
        """Compile a BrowserOS guide into RAG."""
        self._ensure_initialized()
        integration = self._integrations.get("browseros_guides")
        if integration is None:
            return {"status": "error", "message": "BrowserOS Guides integration not available"}
        evidence = integration.compile(guide_id)
        return {"status": "ok", "evidence": evidence.to_dict()}

    # -- Health Check ----------------------------------------------------

    def health_check(self) -> dict[str, Any]:
        """Health check returning index statistics and service status.

        Returns:
            Dict with status, uptime, index stats, and integration statuses
        """
        self._ensure_initialized()

        uptime = time.time() - self._start_time
        stats = self._rag.get_stats()

        integration_status = {}
        for name, integration in self._integrations.items():
            integration_status[name] = {
                "available": True,
                "source_type": integration.source_type,
            }

        return {
            "status": "healthy",
            "uptime_seconds": round(uptime, 1),
            "index_stats": stats,
            "integration_count": len(self._integrations),
            "integrations": integration_status,
            "timestamp": time.time(),
        }

    def get_stats(self) -> dict[str, Any]:
        """Get RAG index statistics (convenience wrapper)."""
        return self.health_check()


# ------------------------------------------------------------------ #
# Convenience
# ------------------------------------------------------------------ #

def get_rag_service() -> RAGService:
    """Get the singleton RAGService instance."""
    return RAGService.get_instance()
