"""Governed document ingestion pipeline for the HKS memory substrate.

This module provides document-to-evidence ingestion: reads source material
(markdown, plain text, code), chunks it into governed sections, and stores
each chunk as evidence in the memory substrate with full provenance.

**Multi-tenant design**: HLF docs are the first tenant, but the architecture
supports ANY knowledge domain (general-coding, ai-engineering, security, etc.).

Entry classification:
    entry_kind  = "evidence"
    strict      = True (enforces provenance gate)
    provenance  = "extraction"
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Domain taxonomy ───────────────────────────────────────────────────────
# First tenant: hlf-specific.  Extensible to any coding/AI domain.
KNOWN_DOMAINS = frozenset({
    "hlf-specific",
    "general-coding",
    "ai-engineering",
    "devops",
    "security",
    "data-engineering",
    "frontend",
    "backend",
    "infrastructure",
})

# ── Source authority levels ───────────────────────────────────────────────
AUTHORITY_LEVELS = frozenset({"canonical", "advisory", "external", "draft"})

# ── Chunk size guardrails ────────────────────────────────────────────────
MIN_CHUNK_CHARS = 20        # below this, merge with previous section
MAX_CHUNK_CHARS = 8_000     # above this, split at paragraph boundaries


@dataclass(slots=True)
class DocumentChunk:
    """One meaningful section extracted from a source document."""

    title: str
    content: str
    section_path: list[str]          # hierarchy: ["Top Header", "Sub Header"]
    source_file: str                 # origin file path or identifier
    source_sha256: str               # SHA-256 of entire source document
    chunk_index: int                 # 0-based position within document
    total_chunks: int                # total chunks from this document
    char_count: int = 0

    def __post_init__(self) -> None:
        self.char_count = len(self.content)


@dataclass(slots=True)
class IngestionReport:
    """Result of a document ingestion run."""

    source_file: str
    source_sha256: str
    domain: str
    total_chunks: int = 0
    stored_count: int = 0
    deduped_count: int = 0
    error_count: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)
    chunk_ids: list[int] = field(default_factory=list)
    elapsed_seconds: float = 0.0


# ── Markdown chunking ────────────────────────────────────────────────────

_HEADER_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


def chunk_markdown(content: str, source_file: str = "") -> list[DocumentChunk]:
    """Split markdown content into sections by headers.

    Strategy:
    - Split on H1-H6 headers
    - Preserve header hierarchy as section_path
    - Merge tiny sections (< MIN_CHUNK_CHARS) with previous
    - Split oversized sections at paragraph boundaries
    """
    source_sha256 = hashlib.sha256(content.encode()).hexdigest()

    # Find all header positions
    headers: list[tuple[int, int, str]] = []  # (position, level, title)
    for m in _HEADER_RE.finditer(content):
        level = len(m.group(1))
        title = m.group(2).strip()
        headers.append((m.start(), level, title))

    if not headers:
        # No headers — treat entire doc as one chunk
        trimmed = content.strip()
        if not trimmed:
            return []
        return [DocumentChunk(
            title=Path(source_file).stem if source_file else "untitled",
            content=trimmed,
            section_path=[Path(source_file).stem if source_file else "untitled"],
            source_file=source_file,
            source_sha256=source_sha256,
            chunk_index=0,
            total_chunks=1,
        )]

    # Extract sections between headers
    raw_sections: list[tuple[list[str], str, str]] = []  # (path, title, body)
    hierarchy: list[str] = []

    for idx, (pos, level, title) in enumerate(headers):
        # Get body between this header and the next
        body_start = content.index("\n", pos) + 1 if "\n" in content[pos:] else pos + len(title) + level + 1
        body_end = headers[idx + 1][0] if idx + 1 < len(headers) else len(content)
        body = content[body_start:body_end].strip()

        # Update hierarchy
        hierarchy = hierarchy[:level - 1]
        while len(hierarchy) < level - 1:
            hierarchy.append("")
        hierarchy.append(title)

        raw_sections.append((list(hierarchy), title, body))

    # Merge tiny sections with previous
    merged: list[tuple[list[str], str, str]] = []
    for path, title, body in raw_sections:
        if merged and len(body) < MIN_CHUNK_CHARS:
            prev_path, prev_title, prev_body = merged[-1]
            merged[-1] = (prev_path, prev_title, prev_body + f"\n\n## {title}\n{body}")
        else:
            merged.append((path, title, body))

    # Split oversized sections
    final_sections: list[tuple[list[str], str, str]] = []
    for path, title, body in merged:
        if len(body) <= MAX_CHUNK_CHARS:
            final_sections.append((path, title, body))
        else:
            sub_chunks = _split_large_text(body, MAX_CHUNK_CHARS)
            for i, sub in enumerate(sub_chunks):
                sub_title = f"{title} (part {i + 1}/{len(sub_chunks)})"
                final_sections.append((path, sub_title, sub))

    # Build DocumentChunk objects
    total = len(final_sections)
    chunks: list[DocumentChunk] = []
    for idx, (path, title, body) in enumerate(final_sections):
        if not body.strip():
            continue
        chunks.append(DocumentChunk(
            title=title,
            content=body,
            section_path=path,
            source_file=source_file,
            source_sha256=source_sha256,
            chunk_index=idx,
            total_chunks=total,
        ))

    return chunks


def _split_large_text(text: str, max_chars: int) -> list[str]:
    """Split text at paragraph boundaries to stay under max_chars."""
    paragraphs = text.split("\n\n")
    result: list[str] = []
    current: list[str] = []
    current_len = 0

    for para in paragraphs:
        if current_len + len(para) + 2 > max_chars and current:
            result.append("\n\n".join(current))
            current = [para]
            current_len = len(para)
        else:
            current.append(para)
            current_len += len(para) + 2

    if current:
        result.append("\n\n".join(current))

    return result if result else [text]


# ── Document ingestion engine ────────────────────────────────────────────

class DocumentIngester:
    """Ingests documents into the HKS memory substrate as governed evidence.

    Usage::

        from hlf_mcp.rag.memory import RAGMemory
        mem = RAGMemory(":memory:")
        ingester = DocumentIngester(mem)

        report = ingester.ingest_file(
            path="docs/HLF_VISION_DOCTRINE.md",
            domain="hlf-specific",
            source_authority_label="canonical",
        )

        # Or batch:
        reports = ingester.ingest_directory(
            dir_path="docs/",
            domain="hlf-specific",
            source_authority_label="canonical",
            file_pattern="*.md",
        )
    """

    def __init__(self, memory: Any) -> None:
        """Initialize with a RAGMemory instance."""
        self._memory = memory

    def ingest_text(
        self,
        content: str,
        *,
        source_file: str = "inline",
        domain: str = "general-coding",
        source_authority_label: str = "advisory",
        topic: str | None = None,
        confidence: float = 0.9,
        tags: list[str] | None = None,
        fresh_until: str | None = None,
    ) -> IngestionReport:
        """Ingest raw text content into the memory substrate.

        Chunks the content, then stores each chunk as governed evidence.
        """
        if domain not in KNOWN_DOMAINS:
            logger.warning("Unknown domain %r — accepting but flagging", domain)
        if source_authority_label not in AUTHORITY_LEVELS:
            logger.warning("Unknown authority %r — defaulting to 'advisory'", source_authority_label)
            source_authority_label = "advisory"

        source_sha256 = hashlib.sha256(content.encode()).hexdigest()
        report = IngestionReport(
            source_file=source_file,
            source_sha256=source_sha256,
            domain=domain,
        )
        t0 = time.monotonic()

        # Chunk the document
        chunks = chunk_markdown(content, source_file=source_file)
        report.total_chunks = len(chunks)

        if not chunks:
            report.elapsed_seconds = time.monotonic() - t0
            return report

        # Determine topic
        effective_topic = topic or _derive_topic(source_file, domain)

        # Store each chunk
        for chunk in chunks:
            try:
                result = self._store_chunk(
                    chunk=chunk,
                    domain=domain,
                    source_authority_label=source_authority_label,
                    topic=effective_topic,
                    confidence=confidence,
                    tags=tags,
                    fresh_until=fresh_until,
                )
                if result.get("stored"):
                    report.stored_count += 1
                    if result.get("id"):
                        report.chunk_ids.append(result["id"])
                elif result.get("duplicate_reason"):
                    report.deduped_count += 1
                else:
                    report.error_count += 1
                    report.errors.append({
                        "chunk_index": chunk.chunk_index,
                        "chunk_title": chunk.title,
                        "error": result.get("error", "unknown"),
                    })
            except Exception as exc:
                report.error_count += 1
                report.errors.append({
                    "chunk_index": chunk.chunk_index,
                    "chunk_title": chunk.title,
                    "error": str(exc),
                })

        report.elapsed_seconds = time.monotonic() - t0
        return report

    def ingest_file(
        self,
        path: str | Path,
        *,
        domain: str = "general-coding",
        source_authority_label: str = "advisory",
        topic: str | None = None,
        confidence: float = 0.9,
        tags: list[str] | None = None,
        fresh_until: str | None = None,
    ) -> IngestionReport:
        """Ingest a single file from disk into the memory substrate."""
        path = Path(path)
        if not path.exists():
            return IngestionReport(
                source_file=str(path),
                source_sha256="",
                domain=domain,
                error_count=1,
                errors=[{"error": f"file not found: {path}"}],
            )

        content = path.read_text(encoding="utf-8", errors="replace")
        return self.ingest_text(
            content,
            source_file=str(path),
            domain=domain,
            source_authority_label=source_authority_label,
            topic=topic,
            confidence=confidence,
            tags=tags,
            fresh_until=fresh_until,
        )

    def ingest_directory(
        self,
        dir_path: str | Path,
        *,
        domain: str = "general-coding",
        source_authority_label: str = "advisory",
        topic: str | None = None,
        confidence: float = 0.9,
        tags: list[str] | None = None,
        fresh_until: str | None = None,
        file_pattern: str = "*.md",
        recursive: bool = True,
    ) -> list[IngestionReport]:
        """Ingest all matching files from a directory.

        Returns one IngestionReport per file processed.
        """
        dir_path = Path(dir_path)
        if not dir_path.is_dir():
            return [IngestionReport(
                source_file=str(dir_path),
                source_sha256="",
                domain=domain,
                error_count=1,
                errors=[{"error": f"directory not found: {dir_path}"}],
            )]

        glob_method = dir_path.rglob if recursive else dir_path.glob
        files = sorted(glob_method(file_pattern))
        reports: list[IngestionReport] = []

        for f in files:
            if not f.is_file():
                continue
            report = self.ingest_file(
                f,
                domain=domain,
                source_authority_label=source_authority_label,
                topic=topic,
                confidence=confidence,
                tags=tags,
                fresh_until=fresh_until,
            )
            reports.append(report)
            logger.info(
                "Ingested %s: %d stored, %d deduped, %d errors",
                f.name, report.stored_count, report.deduped_count, report.error_count,
            )

        return reports

    def _store_chunk(
        self,
        chunk: DocumentChunk,
        domain: str,
        source_authority_label: str,
        topic: str,
        confidence: float,
        tags: list[str] | None,
        fresh_until: str | None,
    ) -> dict[str, Any]:
        """Store a single chunk as governed evidence in memory."""
        # Build section tag hierarchy
        section_tags = [f"section:{s}" for s in chunk.section_path if s]
        chunk_tags = list(tags or []) + section_tags + [
            f"source:{chunk.source_file}",
            f"domain:{domain}",
            f"chunk:{chunk.chunk_index + 1}/{chunk.total_chunks}",
        ]

        # Build governed evidence metadata
        metadata: dict[str, Any] = {
            "governed_evidence": {
                "source_type": "documentation",
                "source_path": chunk.source_file,
                "source_sha256": chunk.source_sha256,
                "source_authority_label": source_authority_label,
                "artifact_form": "canonical_knowledge" if source_authority_label == "canonical" else "reference_material",
                "memory_stratum": "semantic",
                "storage_tier": "warm",
                "section_title": chunk.title,
                "section_path": chunk.section_path,
                "chunk_index": chunk.chunk_index,
                "total_chunks": chunk.total_chunks,
                "char_count": chunk.char_count,
            },
            "source_capture": {
                "extraction_fidelity_score": 1.0,  # exact text extraction
                "structure_fidelity_score": 0.95,   # section boundaries may shift
                "citation_recoverability_score": 1.0,  # source_path + sha256
            },
        }

        if fresh_until:
            metadata["governed_evidence"]["fresh_until"] = fresh_until

        # Prefix chunk content with section title for better retrieval
        enriched_content = f"[{chunk.title}]\n{chunk.content}"

        return self._memory.store(
            content=enriched_content,
            topic=topic,
            confidence=confidence,
            provenance="extraction",
            tags=chunk_tags,
            entry_kind="evidence",
            domain=domain,
            metadata=metadata,
            strict=True,
        )


# ── Helpers ──────────────────────────────────────────────────────────────

def _derive_topic(source_file: str, domain: str) -> str:
    """Derive a topic from the source file name and domain."""
    if not source_file or source_file == "inline":
        return f"{domain}_knowledge"
    stem = Path(source_file).stem.lower()
    # Strip common prefixes
    for prefix in ("hlf_", "hlf-"):
        if stem.startswith(prefix):
            stem = stem[len(prefix):]
    return f"{domain}_{stem}" if stem else f"{domain}_knowledge"


def summarize_reports(reports: list[IngestionReport]) -> dict[str, Any]:
    """Summarize a batch of ingestion reports."""
    total_stored = sum(r.stored_count for r in reports)
    total_deduped = sum(r.deduped_count for r in reports)
    total_errors = sum(r.error_count for r in reports)
    total_chunks = sum(r.total_chunks for r in reports)
    total_elapsed = sum(r.elapsed_seconds for r in reports)
    all_errors = []
    for r in reports:
        for e in r.errors:
            all_errors.append({"file": r.source_file, **e})

    return {
        "files_processed": len(reports),
        "total_chunks": total_chunks,
        "stored": total_stored,
        "deduped": total_deduped,
        "errors": total_errors,
        "error_details": all_errors[:20],  # cap for response size
        "elapsed_seconds": round(total_elapsed, 2),
    }
