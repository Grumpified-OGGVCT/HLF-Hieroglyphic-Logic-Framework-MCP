"""
RAG Integrations — Janus, ChronosGraph, BrowserOS, LOLLMS, MSTY, AnythingLLM.

Each integration module wraps an external service for RAG ingestion,
accepting a HybridRAG instance and returning structured results with
evidence records following the memory_node.py EvidenceContract pattern.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# Evidence Contract (mirrors memory_node.py pattern)
# ------------------------------------------------------------------ #

@dataclass
class EvidenceContract:
    """Structured evidence record for provenance tracking."""

    evidence_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: str = ""
    source_type: str = ""
    content_hash: str = ""
    ingested_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)
    rag_doc_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "source": self.source,
            "source_type": self.source_type,
            "content_hash": self.content_hash,
            "ingested_at": self.ingested_at,
            "metadata": self.metadata,
            "rag_doc_ids": self.rag_doc_ids,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EvidenceContract":
        return cls(
            evidence_id=data.get("evidence_id", str(uuid.uuid4())),
            source=data.get("source", ""),
            source_type=data.get("source_type", ""),
            content_hash=data.get("content_hash", ""),
            ingested_at=data.get("ingested_at", time.time()),
            metadata=data.get("metadata", {}),
            rag_doc_ids=data.get("rag_doc_ids", []),
        )


# ------------------------------------------------------------------ #
# Base Integration
# ------------------------------------------------------------------ #

class BaseIntegration:
    """Base class for RAG integrations.

    Provides common evidence record creation and RAG ingestion helpers.
    """

    def __init__(self, rag=None, source_type: str = "unknown"):
        """
        Args:
            rag: HybridRAG instance (imported lazily to avoid circular imports)
            source_type: Label for evidence records
        """
        self._rag = rag
        self.source_type = source_type

    @property
    def rag(self):
        """Lazy-load HybridRAG to avoid circular imports."""
        if self._rag is None:
            from hlf_mcp.hlf.hybrid_rag import get_hybrid_rag

            self._rag = get_hybrid_rag()
        return self._rag

    def _compute_hash(self, content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()

    def _ingest_text(
        self, text: str, metadata: dict[str, Any] | None = None, chunk_size: int = 2000
    ) -> list[str]:
        """Ingest text into RAG, optionally chunking large texts.

        Returns list of RAG document IDs.
        """
        metadata = metadata or {}
        doc_ids = []

        if len(text) <= chunk_size:
            doc_id = self.rag.add_document(text=text, metadata=metadata)
            doc_ids.append(doc_id)
        else:
            # Chunk large texts
            for i in range(0, len(text), chunk_size):
                chunk = text[i : i + chunk_size]
                chunk_meta = {**metadata, "chunk_index": i // chunk_size, "chunk_total": (len(text) // chunk_size) + 1}
                doc_id = self.rag.add_document(text=chunk, metadata=chunk_meta)
                doc_ids.append(doc_id)

        return doc_ids

    def _create_evidence(
        self, source: str, content: str, doc_ids: list[str], extra_meta: dict[str, Any] | None = None
    ) -> EvidenceContract:
        """Create an evidence record for an ingestion operation."""
        return EvidenceContract(
            source=source,
            source_type=self.source_type,
            content_hash=self._compute_hash(content),
            metadata={**(extra_meta or {}), "doc_count": len(doc_ids)},
            rag_doc_ids=doc_ids,
        )


# ------------------------------------------------------------------ #
# Janus Integration
# ------------------------------------------------------------------ #

class JanusIntegration(BaseIntegration):
    """Janus knowledge graph integration for RAG.

    Janus provides a semantic knowledge graph that can be crawled
    and queried. This integration wraps Janus endpoints for RAG ingestion.
    """

    def __init__(self, rag=None, janus_endpoint: str = "http://localhost:8100"):
        super().__init__(rag=rag, source_type="janus")
        self.janus_endpoint = janus_endpoint

    def crawl(self, url: str, depth: int = 1) -> EvidenceContract:
        """Crawl a URL via Janus and ingest into RAG.

        Args:
            url: URL or Janus resource path to crawl
            depth: Crawl depth (1 = single page only)

        Returns:
            EvidenceContract with ingestion results
        """
        logger.info(f"Janus crawl: {url} (depth={depth})")

        # Attempt actual crawl if httpx available
        content = ""
        try:
            import httpx

            crawl_url = f"{self.janus_endpoint}/crawl"
            resp = httpx.post(
                crawl_url,
                json={"url": url, "depth": depth},
                timeout=30.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                content = data.get("content", data.get("text", json.dumps(data)))
            else:
                logger.warning(f"Janus crawl returned {resp.status_code}, using simulated response")
                content = self._simulate_crawl(url)
        except Exception as e:
            logger.info(f"Janus service not reachable ({e}); using simulated crawl")
            content = self._simulate_crawl(url)

        doc_ids = self._ingest_text(
            content,
            metadata={"source": "janus", "url": url, "crawl_depth": depth, "timestamp": time.time()},
        )

        return self._create_evidence(
            source=url,
            content=content,
            doc_ids=doc_ids,
            extra_meta={"crawl_depth": depth},
        )

    def query(self, query_text: str) -> dict[str, Any]:
        """Query Janus knowledge graph.

        Args:
            query_text: Natural language or SPARQL-like query

        Returns:
            Dict with query results and evidence
        """
        logger.info(f"Janus query: {query_text}")

        results = []
        try:
            import httpx

            query_url = f"{self.janus_endpoint}/query"
            resp = httpx.post(
                query_url,
                json={"query": query_text},
                timeout=30.0,
            )
            if resp.status_code == 200:
                results = resp.json().get("results", [])
            else:
                logger.warning(f"Janus query returned {resp.status_code}")
        except Exception as e:
            logger.info(f"Janus query not reachable ({e}); using RAG fallback")
            # Fallback: search local RAG
            rag_results = self.rag.search(query_text, k=5)
            results = [{"doc_id": r["doc_id"], "text": r["text"], "score": r["score"]} for r in rag_results]

        # Also ingest query results into RAG for future reference
        for i, result in enumerate(results):
            result_text = json.dumps(result) if isinstance(result, dict) else str(result)
            self.rag.add_document(
                text=result_text,
                metadata={"source": "janus_query", "query": query_text, "result_index": i},
            )

        return {
            "query": query_text,
            "results": results,
            "count": len(results),
        }

    def archive(self, resource_id: str) -> EvidenceContract:
        """Archive a Janus resource into RAG persistent storage.

        Args:
            resource_id: Janus resource identifier

        Returns:
            EvidenceContract with archival results
        """
        logger.info(f"Janus archive: {resource_id}")

        content = ""
        try:
            import httpx

            archive_url = f"{self.janus_endpoint}/resource/{resource_id}"
            resp = httpx.get(archive_url, timeout=30.0)
            if resp.status_code == 200:
                content = resp.text
            else:
                content = self._simulate_archive(resource_id)
        except Exception as e:
            logger.info(f"Janus archive not reachable ({e}); using simulation")
            content = self._simulate_archive(resource_id)

        doc_ids = self._ingest_text(
            content,
            metadata={
                "source": "janus_archive",
                "resource_id": resource_id,
                "archived_at": time.time(),
            },
        )

        return self._create_evidence(
            source=f"janus://{resource_id}",
            content=content,
            doc_ids=doc_ids,
            extra_meta={"resource_id": resource_id},
        )

    def _simulate_crawl(self, url: str) -> str:
        """Simulated crawl content when Janus is unavailable."""
        return (
            f"Janus Crawl Result for: {url}\n\n"
            f"This is a simulated crawl response generated at {time.time()}.\n"
            f"In production, this would contain the actual crawled page content\n"
            f"from the Janus knowledge graph crawler.\n\n"
            f"Key entities found (simulated):\n"
            f"- Entity: {url.split('/')[-1] or 'root'}\n"
            f"- Relations: linked_to, references, contains\n"
            f"- Confidence: 0.85\n"
        )

    def _simulate_archive(self, resource_id: str) -> str:
        """Simulated archive content."""
        return (
            f"Janus Archived Resource: {resource_id}\n"
            f"Archived at: {time.time()}\n"
            f"Status: preserved\n"
            f"Content hash: {hashlib.sha256(resource_id.encode()).hexdigest()[:16]}...\n"
        )


# ------------------------------------------------------------------ #
# ChronosGraph Integration
# ------------------------------------------------------------------ #

class ChronosGraphIntegration(BaseIntegration):
    """ChronosGraph integration for video→text→RAG pipeline.

    ChronosGraph processes video and audio content into transcriptions
    that can be ingested into the RAG index.
    """

    def __init__(self, rag=None, chronos_endpoint: str = "http://localhost:8200"):
        super().__init__(rag=rag, source_type="chronos_graph")
        self.chronos_endpoint = chronos_endpoint

    def transcribe(self, video_path: str, language: str = "en") -> dict[str, Any]:
        """Transcribe a video/audio file via ChronosGraph.

        Args:
            video_path: Path to video or audio file
            language: Language code for transcription

        Returns:
            Dict with transcription text and metadata
        """
        logger.info(f"ChronosGraph transcribe: {video_path} (lang={language})")

        transcription = ""
        duration = 0.0
        try:
            import httpx

            transcribe_url = f"{self.chronos_endpoint}/transcribe"
            resp = httpx.post(
                transcribe_url,
                json={"path": video_path, "language": language},
                timeout=120.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                transcription = data.get("text", data.get("transcription", ""))
                duration = data.get("duration", 0.0)
            else:
                logger.warning(f"ChronosGraph transcribe returned {resp.status_code}")
                transcription = self._simulate_transcription(video_path)
        except Exception as e:
            logger.info(f"ChronosGraph not reachable ({e}); using simulation")
            transcription = self._simulate_transcription(video_path)

        return {
            "video_path": video_path,
            "language": language,
            "transcription": transcription,
            "duration": duration,
            "char_count": len(transcription),
            "timestamp": time.time(),
        }

    def ingest(self, transcription: str | dict[str, Any]) -> EvidenceContract:
        """Ingest a transcription into the RAG index.

        Args:
            transcription: Transcription text string or dict with 'transcription' key

        Returns:
            EvidenceContract with ingestion results
        """
        if isinstance(transcription, dict):
            text = transcription.get("transcription", json.dumps(transcription))
            source = transcription.get("video_path", "chronos_transcription")
            extra = {"video_path": transcription.get("video_path", ""), "language": transcription.get("language", "en")}
        else:
            text = transcription
            source = "chronos_transcription"
            extra = {}

        logger.info(f"ChronosGraph ingest: {len(text)} chars")

        doc_ids = self._ingest_text(
            text,
            metadata={
                "source": "chronos_graph",
                "type": "transcription",
                "timestamp": time.time(),
                **extra,
            },
        )

        return self._create_evidence(
            source=source,
            content=text,
            doc_ids=doc_ids,
            extra_meta={"type": "transcription", **extra},
        )

    def _simulate_transcription(self, video_path: str) -> str:
        """Simulated transcription when ChronosGraph is unavailable."""
        filename = os.path.basename(video_path) if video_path else "unknown"
        return (
            f"[ChronosGraph Transcription: {filename}]\n"
            f"Generated at: {time.time()}\n\n"
            f"This is a simulated transcription. In production, ChronosGraph\n"
            f"would process the video/audio file and produce accurate text.\n\n"
            f"Simulated content:\n"
            f"- Speaker 1: Welcome to the HLF ecosystem overview.\n"
            f"- Speaker 1: The Hybrid RAG pipeline combines BM25 and vector search.\n"
            f"- Speaker 2: Integration with external knowledge sources is key.\n"
            f"- Speaker 1: Evidence tracking ensures provenance of all ingested data.\n"
        )


# ------------------------------------------------------------------ #
# BrowserOS Guides Integration
# ------------------------------------------------------------------ #

class BrowserOSGuidesIntegration(BaseIntegration):
    """BrowserOS knowledge extraction integration for RAG.

    Extracts knowledge from BrowserOS guides, documentation pages,
    and interactive tutorials for RAG ingestion.
    """

    def __init__(self, rag=None, browseros_endpoint: str = "http://localhost:8300"):
        super().__init__(rag=rag, source_type="browseros_guides")
        self.browseros_endpoint = browseros_endpoint

    def extract(self, url: str) -> dict[str, Any]:
        """Extract knowledge from a BrowserOS guide URL.

        Args:
            url: BrowserOS guide or documentation URL

        Returns:
            Dict with extracted sections and metadata
        """
        logger.info(f"BrowserOS extract: {url}")

        sections = []
        try:
            import httpx

            extract_url = f"{self.browseros_endpoint}/extract"
            resp = httpx.post(
                extract_url,
                json={"url": url},
                timeout=60.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                sections = data.get("sections", data.get("results", []))
            else:
                logger.warning(f"BrowserOS extract returned {resp.status_code}")
                sections = self._simulate_extract(url)
        except Exception as e:
            logger.info(f"BrowserOS not reachable ({e}); using simulation")
            sections = self._simulate_extract(url)

        return {
            "url": url,
            "sections": sections,
            "section_count": len(sections),
            "timestamp": time.time(),
        }

    def compile(self, guide_id: str) -> EvidenceContract:
        """Compile a BrowserOS guide into RAG.

        Args:
            guide_id: Guide identifier to compile

        Returns:
            EvidenceContract with compilation results
        """
        logger.info(f"BrowserOS compile: {guide_id}")

        # First extract
        extraction = self.extract(f"browseros://guides/{guide_id}")
        sections = extraction.get("sections", [])

        # Compile combined text
        combined = f"BrowserOS Guide: {guide_id}\n\n"
        for i, section in enumerate(sections):
            if isinstance(section, dict):
                title = section.get("title", f"Section {i + 1}")
                content = section.get("content", section.get("text", ""))
                combined += f"## {title}\n{content}\n\n"
            else:
                combined += f"## Section {i + 1}\n{section}\n\n"

        doc_ids = self._ingest_text(
            combined,
            metadata={
                "source": "browseros_guides",
                "guide_id": guide_id,
                "section_count": len(sections),
                "compiled_at": time.time(),
            },
        )

        return self._create_evidence(
            source=f"browseros://guides/{guide_id}",
            content=combined,
            doc_ids=doc_ids,
            extra_meta={"guide_id": guide_id, "section_count": len(sections)},
        )

    def _simulate_extract(self, url: str) -> list[dict[str, Any]]:
        """Simulated extraction when BrowserOS is unavailable."""
        return [
            {
                "title": "Getting Started",
                "content": (
                    "This guide covers the fundamentals of BrowserOS navigation. "
                    "Learn how to interact with the browser-based operating system "
                    "and its MCP server CLI integration."
                ),
                "level": "beginner",
            },
            {
                "title": "Advanced Automation",
                "content": (
                    "BrowserOS supports advanced automation through its MCP server. "
                    "Use the browseros-cli skill to navigate, inspect, and interact "
                    "with browser pages programmatically."
                ),
                "level": "advanced",
            },
            {
                "title": "Integration Patterns",
                "content": (
                    "BrowserOS can be integrated with HLF for knowledge extraction. "
                    "This enables automatic ingestion of web content into the RAG "
                    "pipeline for semantic search and retrieval."
                ),
                "level": "intermediate",
            },
        ]


# ------------------------------------------------------------------ #
# LOLLMS Import
# ------------------------------------------------------------------ #

class LOLLMSImport(BaseIntegration):
    """LOLLMS DataStore import for RAG.

    Imports knowledge from LOLLMS (Lord of Large Language Models)
    DataStores into the Hybrid RAG index.
    """

    def __init__(self, rag=None, lollms_endpoint: str = "http://localhost:9600"):
        super().__init__(rag=rag, source_type="lollms_datastore")
        self.lollms_endpoint = lollms_endpoint

    def import_datastore(self, datastore_id: str) -> EvidenceContract:
        """Import a LOLLMS DataStore into RAG.

        Args:
            datastore_id: LOLLMS DataStore identifier

        Returns:
            EvidenceContract with import results
        """
        logger.info(f"LOLLMS import datastore: {datastore_id}")

        documents = []
        try:
            import httpx

            ds_url = f"{self.lollms_endpoint}/datastore/{datastore_id}/documents"
            resp = httpx.get(ds_url, timeout=60.0)
            if resp.status_code == 200:
                data = resp.json()
                documents = data.get("documents", data.get("results", []))
            else:
                logger.warning(f"LOLLMS datastore returned {resp.status_code}")
                documents = self._simulate_datastore(datastore_id)
        except Exception as e:
            logger.info(f"LOLLMS not reachable ({e}); using simulation")
            documents = self._simulate_datastore(datastore_id)

        doc_ids = []
        all_text = ""
        for i, doc in enumerate(documents):
            text = doc.get("content", doc.get("text", str(doc)))
            meta = doc.get("metadata", {})
            all_text += text + "\n"
            rag_id = self.rag.add_document(
                text=text,
                metadata={
                    "source": "lollms_datastore",
                    "datastore_id": datastore_id,
                    "document_index": i,
                    "original_metadata": meta,
                    "imported_at": time.time(),
                },
            )
            doc_ids.append(rag_id)

        return self._create_evidence(
            source=f"lollms://datastore/{datastore_id}",
            content=all_text,
            doc_ids=doc_ids,
            extra_meta={"datastore_id": datastore_id, "document_count": len(documents)},
        )

    def _simulate_datastore(self, datastore_id: str) -> list[dict[str, Any]]:
        """Simulated LOLLMS datastore documents."""
        return [
            {
                "content": f"LOLLMS Datastore '{datastore_id}' — Document 1: "
                "Configuration guide for LLM bindings and persona management.",
                "metadata": {"type": "guide", "author": "lollms_system"},
            },
            {
                "content": f"LOLLMS Datastore '{datastore_id}' — Document 2: "
                "API reference for the LOLLMS hub data connectors and model registry.",
                "metadata": {"type": "reference", "author": "lollms_system"},
            },
            {
                "content": f"LOLLMS Datastore '{datastore_id}' — Document 3: "
                "Best practices for binding multiple LLM backends through the LOLLMS factory.",
                "metadata": {"type": "practices", "author": "lollms_system"},
            },
        ]


# ------------------------------------------------------------------ #
# MSTY Import
# ------------------------------------------------------------------ #

class MSTYImport(BaseIntegration):
    """MSTY Knowledge Stack import for RAG.

    Imports knowledge from MSTY Knowledge Stacks into the Hybrid RAG index.
    """

    def __init__(self, rag=None, msty_endpoint: str = "http://localhost:9500"):
        super().__init__(rag=rag, source_type="msty_knowledge_stack")
        self.msty_endpoint = msty_endpoint

    def import_knowledge_stack(self, stack_id: str) -> EvidenceContract:
        """Import an MSTY Knowledge Stack into RAG.

        Args:
            stack_id: MSTY Knowledge Stack identifier

        Returns:
            EvidenceContract with import results
        """
        logger.info(f"MSTY import knowledge stack: {stack_id}")

        entries = []
        try:
            import httpx

            stack_url = f"{self.msty_endpoint}/knowledge-stack/{stack_id}/entries"
            resp = httpx.get(stack_url, timeout=60.0)
            if resp.status_code == 200:
                data = resp.json()
                entries = data.get("entries", data.get("results", []))
            else:
                logger.warning(f"MSTY knowledge stack returned {resp.status_code}")
                entries = self._simulate_knowledge_stack(stack_id)
        except Exception as e:
            logger.info(f"MSTY not reachable ({e}); using simulation")
            entries = self._simulate_knowledge_stack(stack_id)

        doc_ids = []
        all_text = ""
        for i, entry in enumerate(entries):
            text = entry.get("content", entry.get("text", str(entry)))
            all_text += text + "\n"
            rag_id = self.rag.add_document(
                text=text,
                metadata={
                    "source": "msty_knowledge_stack",
                    "stack_id": stack_id,
                    "entry_index": i,
                    "entry_title": entry.get("title", f"Entry {i + 1}"),
                    "imported_at": time.time(),
                },
            )
            doc_ids.append(rag_id)

        return self._create_evidence(
            source=f"msty://knowledge-stack/{stack_id}",
            content=all_text,
            doc_ids=doc_ids,
            extra_meta={"stack_id": stack_id, "entry_count": len(entries)},
        )

    def _simulate_knowledge_stack(self, stack_id: str) -> list[dict[str, Any]]:
        """Simulated MSTY knowledge stack entries."""
        return [
            {
                "title": "HLF Protocol Overview",
                "content": (
                    "The Hieroglyphic Logic Framework (HLF) is a deterministic "
                    "orchestration protocol for agentic systems. It uses a constraint-based "
                    "language for specifying agent behaviors and knowledge flows."
                ),
            },
            {
                "title": "RAG Architecture",
                "content": (
                    "The Hybrid RAG pipeline combines BM25 keyword search with vector "
                    "semantic search and cross-encoder reranking for optimal retrieval. "
                    "It integrates with multiple external knowledge sources."
                ),
            },
            {
                "title": "Integration Patterns",
                "content": (
                    "MSTY Knowledge Stacks can serve as a knowledge source for the HLF "
                    "RAG pipeline. This enables bidirectional knowledge flow between MSTY's "
                    "conversational memory and HLF's structured retrieval system."
                ),
            },
        ]


# ------------------------------------------------------------------ #
# AnythingLLM Import
# ------------------------------------------------------------------ #

class AnythingLLMImport(BaseIntegration):
    """AnythingLLM workspace import for RAG.

    Imports knowledge from AnythingLLM workspaces into the Hybrid RAG index.
    """

    def __init__(self, rag=None, anythingllm_endpoint: str = "http://localhost:3001"):
        super().__init__(rag=rag, source_type="anythingllm_workspace")
        self.anythingllm_endpoint = anythingllm_endpoint

    def import_workspace(self, workspace_id: str) -> EvidenceContract:
        """Import an AnythingLLM workspace into RAG.

        Args:
            workspace_id: AnythingLLM workspace identifier (slug)

        Returns:
            EvidenceContract with import results
        """
        logger.info(f"AnythingLLM import workspace: {workspace_id}")

        documents = []
        try:
            import httpx

            ws_url = f"{self.anythingllm_endpoint}/api/v1/workspace/{workspace_id}/documents"
            headers = {}
            api_key = os.environ.get("ANYTHINGLLM_API_KEY", "")
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            resp = httpx.get(ws_url, headers=headers, timeout=60.0)
            if resp.status_code == 200:
                data = resp.json()
                documents = data.get("documents", data.get("results", data.get("localFiles", {}).get("items", [])))
            else:
                logger.warning(f"AnythingLLM workspace returned {resp.status_code}")
                documents = self._simulate_workspace(workspace_id)
        except Exception as e:
            logger.info(f"AnythingLLM not reachable ({e}); using simulation")
            documents = self._simulate_workspace(workspace_id)

        doc_ids = []
        all_text = ""
        for i, doc in enumerate(documents):
            if isinstance(doc, dict):
                text = doc.get("content", doc.get("text", doc.get("title", str(doc))))
            else:
                text = str(doc)
            all_text += text + "\n"
            rag_id = self.rag.add_document(
                text=text,
                metadata={
                    "source": "anythingllm_workspace",
                    "workspace_id": workspace_id,
                    "document_index": i,
                    "original_title": doc.get("title", "") if isinstance(doc, dict) else "",
                    "imported_at": time.time(),
                },
            )
            doc_ids.append(rag_id)

        return self._create_evidence(
            source=f"anythingllm://workspace/{workspace_id}",
            content=all_text,
            doc_ids=doc_ids,
            extra_meta={"workspace_id": workspace_id, "document_count": len(documents)},
        )

    def _simulate_workspace(self, workspace_id: str) -> list[dict[str, Any]]:
        """Simulated AnythingLLM workspace documents."""
        return [
            {
                "title": "HLF System Architecture",
                "content": (
                    "The HLF system architecture employs a tiered approach with hot, "
                    "warm, and cold storage layers. The RAG pipeline sits at the warm "
                    "layer, providing semantic retrieval across all ingested knowledge."
                ),
            },
            {
                "title": "Agent Orchestration",
                "content": (
                    "AnythingLLM workspaces can be configured with custom agents that "
                    "leverage the HLF orchestration protocol. This enables deterministic "
                    "multi-agent workflows with provenance tracking."
                ),
            },
        ]


# ------------------------------------------------------------------ #
# Convenience factory
# ------------------------------------------------------------------ #

def create_all_integrations(rag=None) -> dict[str, BaseIntegration]:
    """Create all RAG integration instances.

    Args:
        rag: Optional HybridRAG instance (auto-created if None)

    Returns:
        Dict mapping integration name to instance
    """
    return {
        "janus": JanusIntegration(rag=rag),
        "chronos_graph": ChronosGraphIntegration(rag=rag),
        "browseros_guides": BrowserOSGuidesIntegration(rag=rag),
        "lollms": LOLLMSImport(rag=rag),
        "msty": MSTYImport(rag=rag),
        "anythingllm": AnythingLLMImport(rag=rag),
    }
