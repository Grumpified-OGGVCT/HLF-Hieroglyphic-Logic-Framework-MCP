"""
Architecture Decision Record (ADR) System — SAFE Tier 1.

Lightweight, structured decision logging for the Sovereign OS.
Each ADR captures a design decision with context, consequences,
and traceability. Supports both programmatic and file-based usage.

Architecture:
    ADR → Markdown file in governance/decisions/
    ADRRegistry → manages ADRs, assigns IDs, supports tagging/search

Based on the Michael Nygard ADR format:
https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ─── Status ─────────────────────────────────────────────────────────────────

class ADRStatus(StrEnum):
    """Status of an architecture decision."""

    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    DEPRECATED = "deprecated"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"


# ─── ADR ────────────────────────────────────────────────────────────────────

@dataclass
class ADR:
    """A single Architecture Decision Record.

    Fields:
        id: Unique numeric identifier (auto-assigned).
        title: Short descriptive title.
        status: Current status (proposed → accepted → ...).
        context: Why this decision is needed.
        decision: What was decided.
        consequences: Expected results of this decision.
        tags: Categories (e.g., "security", "performance").
        supersedes: ID of ADR this one replaces.
        superseded_by: ID of ADR that replaces this one.
        date: Creation timestamp.
        author: Who created the ADR.
    """

    id: int = 0
    title: str = ""
    status: ADRStatus = ADRStatus.PROPOSED
    context: str = ""
    decision: str = ""
    consequences: str = ""
    tags: list[str] = field(default_factory=list)
    supersedes: int | None = None
    superseded_by: int | None = None
    date: float = field(default_factory=time.time)
    author: str = ""

    def to_markdown(self) -> str:
        """Render as Nygard-format Markdown."""
        lines = [
            f"# ADR-{self.id:04d}: {self.title}",
            f"",
            f"**Status:** {self.status.value}",
            f"**Date:** {time.strftime('%Y-%m-%d', time.localtime(self.date))}",
        ]

        if self.author:
            lines.append(f"**Author:** {self.author}")
        if self.tags:
            lines.append(f"**Tags:** {', '.join(self.tags)}")
        if self.supersedes is not None:
            lines.append(f"**Supersedes:** ADR-{self.supersedes:04d}")
        if self.superseded_by is not None:
            lines.append(f"**Superseded by:** ADR-{self.superseded_by:04d}")

        lines.extend([
            "",
            "## Context",
            "",
            self.context,
            "",
            "## Decision",
            "",
            self.decision,
            "",
            "## Consequences",
            "",
            self.consequences,
        ])

        return "\n".join(lines) + "\n"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status.value,
            "context": self.context,
            "decision": self.decision,
            "consequences": self.consequences,
            "tags": self.tags,
            "supersedes": self.supersedes,
            "superseded_by": self.superseded_by,
            "date": self.date,
            "author": self.author,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ADR:
        return cls(
            id=data.get("id", 0),
            title=data.get("title", ""),
            status=ADRStatus(data.get("status", "proposed")),
            context=data.get("context", ""),
            decision=data.get("decision", ""),
            consequences=data.get("consequences", ""),
            tags=data.get("tags", []),
            supersedes=data.get("supersedes"),
            superseded_by=data.get("superseded_by"),
            date=data.get("date", 0),
            author=data.get("author", ""),
        )


# ─── Registry ───────────────────────────────────────────────────────────────

class ADRRegistry:
    """Manages Architecture Decision Records.

    Can persist to a JSON index and individual markdown files.

    Args:
        storage_dir: Directory for ADR markdown files.
    """

    def __init__(self, storage_dir: Path | str | None = None) -> None:
        self._adrs: dict[int, ADR] = {}
        self._next_id = 1
        self._storage_dir = Path(storage_dir) if storage_dir else None

    # ── CRUD ────────────────────────────────────────────────────────────

    def create(
        self,
        title: str,
        context: str,
        decision: str,
        consequences: str = "",
        tags: list[str] | None = None,
        author: str = "",
        status: ADRStatus = ADRStatus.PROPOSED,
    ) -> ADR:
        """Create a new ADR.

        Returns:
            The created ADR with auto-assigned ID.
        """
        adr = ADR(
            id=self._next_id,
            title=title,
            context=context,
            decision=decision,
            consequences=consequences,
            tags=tags or [],
            author=author,
            status=status,
        )
        self._adrs[adr.id] = adr
        self._next_id += 1

        if self._storage_dir:
            self._write_adr(adr)

        logger.info("ADR-%04d created: %s", adr.id, adr.title)
        return adr

    def get(self, adr_id: int) -> ADR | None:
        """Get an ADR by ID."""
        return self._adrs.get(adr_id)

    def update_status(self, adr_id: int, status: ADRStatus) -> ADR | None:
        """Update the status of an ADR."""
        adr = self._adrs.get(adr_id)
        if adr:
            adr.status = status
            if self._storage_dir:
                self._write_adr(adr)
        return adr

    def supersede(self, old_id: int, new_adr: ADR) -> tuple[ADR | None, ADR]:
        """Mark an ADR as superseded by a new one.

        Args:
            old_id: ID of the ADR being superseded.
            new_adr: The new ADR (will have supersedes set).

        Returns:
            Tuple of (old_adr, new_adr).
        """
        old = self._adrs.get(old_id)
        if old:
            old.status = ADRStatus.SUPERSEDED
            old.superseded_by = new_adr.id
            new_adr.supersedes = old_id
            if self._storage_dir:
                self._write_adr(old)
                self._write_adr(new_adr)

        return old, new_adr

    # ── Query ───────────────────────────────────────────────────────────

    def list_all(self) -> list[ADR]:
        """List all ADRs, sorted by ID."""
        return sorted(self._adrs.values(), key=lambda a: a.id)

    def by_status(self, status: ADRStatus) -> list[ADR]:
        """Filter ADRs by status."""
        return [a for a in self._adrs.values() if a.status == status]

    def by_tag(self, tag: str) -> list[ADR]:
        """Filter ADRs by tag."""
        return [a for a in self._adrs.values() if tag in a.tags]

    def search(self, query: str) -> list[ADR]:
        """Search ADRs by title and content."""
        q = query.lower()
        return [
            a for a in self._adrs.values()
            if q in a.title.lower()
            or q in a.context.lower()
            or q in a.decision.lower()
        ]

    @property
    def count(self) -> int:
        return len(self._adrs)

    # ── Persistence ─────────────────────────────────────────────────────

    def save_index(self, path: Path | str | None = None) -> str:
        """Save the ADR index as JSON."""
        data = {
            "adrs": [a.to_dict() for a in self.list_all()],
            "next_id": self._next_id,
        }
        content = json.dumps(data, indent=2)

        if path or self._storage_dir:
            target = Path(path) if path else self._storage_dir / "adr_index.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

        return content

    def load_index(self, path: Path | str) -> int:
        """Load ADRs from a JSON index file.

        Returns:
            Number of ADRs loaded.
        """
        p = Path(path)
        if not p.exists():
            return 0

        data = json.loads(p.read_text(encoding="utf-8"))
        for adr_data in data.get("adrs", []):
            adr = ADR.from_dict(adr_data)
            self._adrs[adr.id] = adr

        self._next_id = data.get("next_id", len(self._adrs) + 1)
        return len(self._adrs)

    def _write_adr(self, adr: ADR) -> None:
        """Write a single ADR to a markdown file."""
        if not self._storage_dir:
            return

        self._storage_dir.mkdir(parents=True, exist_ok=True)
        filename = f"ADR-{adr.id:04d}-{_slugify(adr.title)}.md"
        path = self._storage_dir / filename
        path.write_text(adr.to_markdown(), encoding="utf-8")


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _slugify(text: str) -> str:
    """Convert text to a filename-safe slug."""
    import re
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return slug[:60]
