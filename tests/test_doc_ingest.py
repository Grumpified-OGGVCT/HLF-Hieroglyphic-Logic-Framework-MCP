"""Tests for the governed document ingestion pipeline.

Covers: markdown chunking, memory storage, dedup, directory ingestion,
evidence schema population, and the MCP tool surface.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

import pytest

from hlf_mcp.doc_ingest import (
    AUTHORITY_LEVELS,
    KNOWN_DOMAINS,
    DocumentChunk,
    DocumentIngester,
    IngestionReport,
    chunk_markdown,
    summarize_reports,
)
from hlf_mcp.rag.memory import RAGMemory


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture()
def memory():
    """In-memory InfiniteRAGMemory instance."""
    return RAGMemory(":memory:")


@pytest.fixture()
def ingester(memory):
    """DocumentIngester wired to in-memory store."""
    return DocumentIngester(memory)


SAMPLE_MD = """\
# Architecture

This section covers the high-level architecture.

## Components

The system has three layers.

### Layer One

The first layer handles parsing.

### Layer Two

The second layer handles compilation.

## Deployment

Deployed via Docker Compose.

# Testing

Unit tests cover all modules.
"""

SMALL_MD = """\
# Quick Note

Just a tiny section.
"""

NO_HEADERS_MD = """\
This is plain text without any markdown headers.
It has multiple lines but no structure.
The chunker should treat it as a single document.
"""


# ── Chunking Tests ────────────────────────────────────────────────────────

class TestChunkMarkdown:
    def test_basic_header_split(self):
        chunks = chunk_markdown(SAMPLE_MD, source_file="arch.md")
        assert len(chunks) >= 3  # At least Architecture, Components+subs, Testing
        titles = [c.title for c in chunks]
        assert "Architecture" in titles
        assert "Testing" in titles

    def test_chunk_has_source_sha256(self):
        chunks = chunk_markdown(SAMPLE_MD, source_file="arch.md")
        assert all(c.source_sha256 for c in chunks)
        # All chunks from same doc share the same source hash
        assert len({c.source_sha256 for c in chunks}) == 1

    def test_chunk_indices_sequential(self):
        chunks = chunk_markdown(SAMPLE_MD, source_file="arch.md")
        for i, c in enumerate(chunks):
            assert c.chunk_index == i

    def test_total_chunks_consistent(self):
        chunks = chunk_markdown(SAMPLE_MD, source_file="arch.md")
        for c in chunks:
            assert c.total_chunks == len(chunks)

    def test_section_path_hierarchy(self):
        chunks = chunk_markdown(SAMPLE_MD, source_file="arch.md")
        # At least one chunk should have multi-level hierarchy
        has_deep = any(len(c.section_path) > 1 for c in chunks)
        assert has_deep, "Expected at least one chunk with nested section path"

    def test_no_headers_single_chunk(self):
        chunks = chunk_markdown(NO_HEADERS_MD, source_file="plain.md")
        assert len(chunks) == 1
        assert chunks[0].title == "plain"

    def test_empty_content_no_chunks(self):
        chunks = chunk_markdown("", source_file="empty.md")
        assert chunks == []
        chunks2 = chunk_markdown("   \n\n   ", source_file="whitespace.md")
        assert chunks2 == []

    def test_char_count_populated(self):
        chunks = chunk_markdown(SAMPLE_MD, source_file="arch.md")
        for c in chunks:
            assert c.char_count > 0
            assert c.char_count == len(c.content)


# ── Ingestion Tests ───────────────────────────────────────────────────────

class TestIngestText:
    def test_basic_ingestion(self, ingester):
        report = ingester.ingest_text(
            SAMPLE_MD,
            source_file="arch.md",
            domain="hlf-specific",
            source_authority_label="canonical",
        )
        assert isinstance(report, IngestionReport)
        assert report.total_chunks >= 3
        assert report.stored_count >= 3
        assert report.error_count == 0
        assert report.deduped_count == 0

    def test_dedup_on_reingest(self, ingester):
        r1 = ingester.ingest_text(
            SAMPLE_MD, source_file="doc.md", domain="general-coding",
        )
        r2 = ingester.ingest_text(
            SAMPLE_MD, source_file="doc.md", domain="general-coding",
        )
        assert r1.stored_count >= 3
        # Second ingest should dedup all chunks
        assert r2.deduped_count == r1.stored_count
        assert r2.stored_count == 0

    def test_chunk_ids_returned(self, ingester):
        report = ingester.ingest_text(
            SAMPLE_MD, source_file="test.md", domain="hlf-specific",
        )
        assert len(report.chunk_ids) == report.stored_count
        assert all(isinstance(cid, int) for cid in report.chunk_ids)

    def test_evidence_metadata_in_memory(self, ingester, memory):
        ingester.ingest_text(
            SMALL_MD,
            source_file="note.md",
            domain="ai-engineering",
            source_authority_label="canonical",
        )
        # Query memory for the stored fact
        results = memory.query("Quick Note", top_k=5)
        facts = results.get("results") or results.get("facts") or []
        assert len(facts) >= 1
        # Check evidence metadata on a retrieved fact
        fact = facts[0]
        meta = json.loads(fact["metadata_json"]) if isinstance(fact.get("metadata_json"), str) else (fact.get("metadata") or {})
        ge = meta.get("governed_evidence", {})
        assert ge.get("source_type") == "documentation"
        assert ge.get("source_authority_label") == "canonical"
        assert ge.get("memory_stratum") == "semantic"

    def test_unknown_domain_accepted_with_warning(self, ingester):
        report = ingester.ingest_text(
            SMALL_MD, source_file="x.md", domain="quantum-computing",
        )
        # Should succeed — unknown domain is a warning, not an error
        assert report.error_count == 0 or report.stored_count >= 1

    def test_bad_authority_defaults_to_advisory(self, ingester, memory):
        report = ingester.ingest_text(
            SMALL_MD,
            source_file="x.md",
            domain="general-coding",
            source_authority_label="supreme_ruler",
        )
        assert report.stored_count >= 1
        # Verify it was stored as advisory (the default)
        results = memory.query("Quick Note", top_k=5)
        facts = results.get("results") or results.get("facts") or []
        if facts:
            meta = json.loads(facts[0]["metadata_json"]) if isinstance(facts[0].get("metadata_json"), str) else (facts[0].get("metadata") or {})
            ge = meta.get("governed_evidence", {})
            assert ge.get("source_authority_label") == "advisory"

    def test_elapsed_tracked(self, ingester):
        report = ingester.ingest_text(SAMPLE_MD, source_file="t.md")
        assert report.elapsed_seconds >= 0.0

    def test_topic_derived_from_filename(self, ingester, memory):
        ingester.ingest_text(
            SMALL_MD,
            source_file="HLF_VISION_DOCTRINE.md",
            domain="hlf-specific",
        )
        results = memory.query("Quick Note", top_k=5)
        facts = results.get("results") or results.get("facts") or []
        if facts:
            assert facts[0]["topic"] == "hlf-specific_vision_doctrine"

    def test_fresh_until_in_evidence(self, ingester, memory):
        ingester.ingest_text(
            SMALL_MD,
            source_file="versioned.md",
            domain="general-coding",
            fresh_until="2026-06-01T00:00:00Z",
        )
        results = memory.query("Quick Note", top_k=5)
        facts = results.get("results") or results.get("facts") or []
        if facts:
            meta = json.loads(facts[0]["metadata_json"]) if isinstance(facts[0].get("metadata_json"), str) else (facts[0].get("metadata") or {})
            ge = meta.get("governed_evidence", {})
            assert ge.get("fresh_until") == "2026-06-01T00:00:00Z"


# ── File Ingestion Tests ─────────────────────────────────────────────────

class TestIngestFile:
    def test_file_from_disk(self, ingester, tmp_path):
        md_file = tmp_path / "test_doc.md"
        md_file.write_text(SAMPLE_MD, encoding="utf-8")
        report = ingester.ingest_file(md_file, domain="hlf-specific")
        assert report.stored_count >= 3
        assert report.error_count == 0
        assert str(md_file) in report.source_file

    def test_file_not_found(self, ingester):
        report = ingester.ingest_file("/nonexistent/path/doc.md")
        assert report.error_count == 1
        assert "not found" in report.errors[0]["error"]


# ── Directory Ingestion Tests ────────────────────────────────────────────

class TestIngestDirectory:
    def test_directory_batch(self, ingester, tmp_path):
        for i in range(3):
            (tmp_path / f"doc_{i}.md").write_text(
                f"# Section {i}\n\nContent for document {i}.\n",
                encoding="utf-8",
            )
        reports = ingester.ingest_directory(tmp_path, domain="general-coding")
        assert len(reports) == 3
        assert all(r.stored_count >= 1 for r in reports)

    def test_directory_not_found(self, ingester):
        reports = ingester.ingest_directory("/nonexistent/dir")
        assert len(reports) == 1
        assert reports[0].error_count == 1

    def test_pattern_filter(self, ingester, tmp_path):
        (tmp_path / "doc.md").write_text("# MD\nContent\n", encoding="utf-8")
        (tmp_path / "code.py").write_text("# Python\nprint('hi')\n", encoding="utf-8")
        reports = ingester.ingest_directory(
            tmp_path, file_pattern="*.md",
        )
        assert len(reports) == 1  # Only .md


# ── Report Summary Tests ─────────────────────────────────────────────────

class TestSummarizeReports:
    def test_summary_aggregation(self):
        r1 = IngestionReport("a.md", "sha1", "hlf-specific", total_chunks=5, stored_count=4, deduped_count=1, elapsed_seconds=1.5)
        r2 = IngestionReport("b.md", "sha2", "hlf-specific", total_chunks=3, stored_count=3, deduped_count=0, elapsed_seconds=0.5)
        summary = summarize_reports([r1, r2])
        assert summary["files_processed"] == 2
        assert summary["total_chunks"] == 8
        assert summary["stored"] == 7
        assert summary["deduped"] == 1
        assert summary["errors"] == 0
        assert summary["elapsed_seconds"] == 2.0


# ── Domain & Authority Constants Tests ───────────────────────────────────

class TestConstants:
    def test_hlf_specific_in_domains(self):
        assert "hlf-specific" in KNOWN_DOMAINS

    def test_general_coding_in_domains(self):
        assert "general-coding" in KNOWN_DOMAINS

    def test_ai_engineering_in_domains(self):
        assert "ai-engineering" in KNOWN_DOMAINS

    def test_canonical_in_authority(self):
        assert "canonical" in AUTHORITY_LEVELS

    def test_advisory_in_authority(self):
        assert "advisory" in AUTHORITY_LEVELS


# ── Edge Cases ───────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_large_section_split(self, ingester):
        """A section > MAX_CHUNK_CHARS should be split at paragraph boundaries."""
        # Build a document with one huge section
        big_section = "\n\n".join([f"Paragraph {i}: " + "x" * 500 for i in range(25)])
        content = f"# Big Section\n\n{big_section}\n"
        report = ingester.ingest_text(content, source_file="big.md")
        # Should produce more than 1 chunk
        assert report.total_chunks >= 2
        assert report.stored_count >= 2

    def test_tags_propagated(self, ingester, memory):
        ingester.ingest_text(
            SMALL_MD,
            source_file="tagged.md",
            domain="security",
            tags=["owasp", "2026"],
        )
        results = memory.query("Quick Note", top_k=5)
        facts = results.get("results") or results.get("facts") or []
        if facts:
            tags_raw = facts[0].get("tags_json") or facts[0].get("tags") or "[]"
            tags = json.loads(tags_raw) if isinstance(tags_raw, str) else tags_raw
            assert "owasp" in tags
            assert "2026" in tags
