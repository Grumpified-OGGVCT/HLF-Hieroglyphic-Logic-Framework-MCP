"""
Knowledge Base entry models.

Models for parsing and representing KB entries from Markdown files.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
import hashlib
import re


class KBEntryMetadata(BaseModel):
    """
    Metadata extracted from a KB entry.
    
    Used for retrieval filtering and provenance tracking.
    """
    
    id: str = Field(
        ...,
        description="Unique entry ID (e.g., 'postgresql-max-connections-0001')"
    )
    domain: str = Field(
        ...,
        description="Domain/technology area"
    )
    software_version: str = Field(
        ...,
        description="Software version the entry applies to"
    )
    valid_until: str = Field(
        default="latest",
        description="Last version this entry is valid for, or 'latest'"
    )
    tier: str = Field(
        default="GOLD",
        description="Quality tier: GOLD, SILVER, or BRONZE"
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Base confidence score"
    )
    created_at: Optional[datetime] = Field(
        default=None,
        description="When the entry was created"
    )

    @property
    def sha256(self) -> str:
        """Generate SHA256 hash for lockfile support."""
        content = f"{self.id}|{self.domain}|{self.software_version}|{self.valid_until}"
        return hashlib.sha256(content.encode()).hexdigest()

    def is_version_compatible(self, query_version: Optional[str]) -> bool:
        """
        Check if this entry is compatible with the queried version.
        
        Args:
            query_version: The version specified in the query (None means latest)
            
        Returns:
            True if compatible, False otherwise
        """
        if query_version is None:
            # No version specified, only match "latest" entries
            return self.valid_until.lower() == "latest"
        
        # If query specifies a version, check if it's within range
        # For now, simple string matching or prefix matching
        if self.valid_until.lower() == "latest":
            return True
        
        # Compare major versions
        try:
            query_major = query_version.split(".")[0]
            entry_major = self.software_version.split(".")[0]
            valid_until_major = self.valid_until.split(".")[0]
            
            return int(query_major) >= int(entry_major) and int(query_major) <= int(valid_until_major)
        except (ValueError, IndexError):
            # Fall back to string comparison
            return query_version.startswith(self.software_version.split(".")[0])


class KBEntry(BaseModel):
    """
    Full KB entry model matching the canonical Markdown template.
    """
    
    id: str = Field(
        ...,
        description="Unique entry ID"
    )
    question: str = Field(
        ...,
        description="Complete exact text of the question"
    )
    answer: str = Field(
        ...,
        description="Full technical answer"
    )
    domain: str = Field(
        ...,
        description="Domain name matching the filename"
    )
    software_version: str = Field(
        ...,
        description="Exact version used to verify the answer"
    )
    valid_until: str = Field(
        default="latest",
        description="Last version this entry is valid for"
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence score"
    )
    tier: str = Field(
        default="GOLD",
        description="Quality tier"
    )
    sources: List[str] = Field(
        default_factory=list,
        description="List of source URLs"
    )
    related_questions: List[str] = Field(
        default_factory=list,
        description="Related questions"
    )
    dependencies: Optional[List[str]] = Field(
        default=None,
        description="Entry IDs this entry depends on"
    )
    created_at: Optional[datetime] = Field(
        default=None,
        description="Creation timestamp"
    )
    raw_content: Optional[str] = Field(
        default=None,
        description="Original Markdown content"
    )

    @property
    def sha256(self) -> str:
        """Generate SHA256 hash of the full entry content."""
        content = self.raw_content or self.to_markdown()
        return hashlib.sha256(content.encode()).hexdigest()

    @property
    def metadata(self) -> KBEntryMetadata:
        """Extract metadata for retrieval filtering."""
        return KBEntryMetadata(
            id=self.id,
            domain=self.domain,
            software_version=self.software_version,
            valid_until=self.valid_until,
            tier=self.tier,
            confidence=self.confidence,
            created_at=self.created_at
        )

    def to_markdown(self) -> str:
        """
        Serialize the entry to the canonical Markdown format.
        """
        sources_str = "\n".join(f"- {s}" for s in self.sources)
        related_str = "\n".join(f"- {q}" for q in self.related_questions)
        
        deps_section = ""
        if self.dependencies:
            deps_str = "\n".join(f"- {d}" for d in self.dependencies)
            deps_section = f"\n**Dependencies**:\n{deps_str}\n"
        
        return f"""### ID: {self.id}

**Question**: {self.question}

**Answer**:
{self.answer}

**Domain**: {self.domain}

**Software Version**: {self.software_version}

**Valid Until**: {self.valid_until}

**Confidence**: {self.confidence:.2f}

**Tier**: {self.tier}

**Sources**:
{sources_str}

**Related Questions**:
{related_str}
{deps_section}
---
"""

    @classmethod
    def from_markdown(cls, content: str) -> "KBEntry":
        """
        Parse a KB entry from Markdown content.
        
        Args:
            content: The Markdown content of a single entry
            
        Returns:
            Parsed KBEntry instance
        """
        # Extract ID
        id_match = re.search(r"###\s*ID:\s*(.+?)(?:\n|$)", content)
        entry_id = id_match.group(1).strip() if id_match else ""
        
        # Extract Question
        question_match = re.search(r"\*\*Question\*\*:\s*(.+?)(?=\n\*\*|\n\n\*\*|$)", content, re.DOTALL)
        question = question_match.group(1).strip() if question_match else ""
        
        # Extract Answer
        answer_match = re.search(r"\*\*Answer\*\*:\s*\n(.*?)(?=\n\*\*Domain\*\*)", content, re.DOTALL)
        answer = answer_match.group(1).strip() if answer_match else ""
        
        # Extract Domain
        domain_match = re.search(r"\*\*Domain\*\*:\s*(.+?)(?:\n|$)", content)
        domain = domain_match.group(1).strip() if domain_match else ""
        
        # Extract Software Version
        version_match = re.search(r"\*\*Software Version\*\*:\s*(.+?)(?:\n|$)", content)
        software_version = version_match.group(1).strip() if version_match else ""
        
        # Extract Valid Until
        valid_match = re.search(r"\*\*Valid Until\*\*:\s*(.+?)(?:\n|$)", content)
        valid_until = valid_match.group(1).strip() if valid_match else "latest"
        
        # Extract Confidence
        conf_match = re.search(r"\*\*Confidence\*\*:\s*([\d.]+)", content)
        confidence = float(conf_match.group(1)) if conf_match else 1.0
        
        # Extract Tier
        tier_match = re.search(r"\*\*Tier\*\*:\s*(\w+)", content)
        tier = tier_match.group(1).strip().upper() if tier_match else "GOLD"
        
        # Extract Sources
        sources_match = re.search(r"\*\*Sources\*\*:\s*\n((?:-\s*.+\n?)+)", content)
        sources = []
        if sources_match:
            sources = [
                s.strip().lstrip("- ").strip() 
                for s in sources_match.group(1).strip().split("\n")
                if s.strip()
            ]
        
        # Extract Related Questions
        related_match = re.search(r"\*\*Related Questions\*\*:\s*\n((?:-\s*.+\n?)+)", content)
        related_questions = []
        if related_match:
            related_questions = [
                q.strip().lstrip("- ").strip() 
                for q in related_match.group(1).strip().split("\n")
                if q.strip()
            ]
        
        # Extract Dependencies (optional)
        deps_match = re.search(r"\*\*Dependencies\*\*:\s*\n((?:-\s*.+\n?)+)", content)
        dependencies = None
        if deps_match:
            dependencies = [
                d.strip().lstrip("- ").strip() 
                for d in deps_match.group(1).strip().split("\n")
                if d.strip()
            ]
        
        return cls(
            id=entry_id,
            question=question,
            answer=answer,
            domain=domain,
            software_version=software_version,
            valid_until=valid_until,
            confidence=confidence,
            tier=tier,
            sources=sources,
            related_questions=related_questions,
            dependencies=dependencies,
            raw_content=content
        )


class ParsedKBEntry(BaseModel):
    """
    Parsed KB entry with additional retrieval metadata.
    
    Used for retrieval results that include similarity scores
    and adjusted confidence.
    """
    
    entry: KBEntry
    similarity: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Semantic similarity score from retrieval"
    )
    adjusted_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confidence after decay adjustment"
    )
    chunk_content: Optional[str] = Field(
        default=None,
        description="The specific chunk retrieved"
    )

    @classmethod
    def from_entry(
        cls, 
        entry: KBEntry, 
        similarity: float = 1.0,
        decay_factor: float = 1.0
    ) -> "ParsedKBEntry":
        """Create from a KBEntry with calculated scores."""
        adjusted = entry.confidence * decay_factor
        return cls(
            entry=entry,
            similarity=similarity,
            adjusted_confidence=adjusted
        )

