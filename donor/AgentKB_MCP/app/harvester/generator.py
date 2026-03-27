"""
Entry Generator - Creates KB entries from changed documentation content.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import structlog

from app.config import settings
from app.harvester.detector import ChangeResult

logger = structlog.get_logger()


@dataclass
class GeneratedEntry:
    """A KB entry generated from documentation content."""
    id: str
    question: str
    answer: str
    domain: str
    software_version: str
    valid_until: str
    confidence: float
    tier: str
    sources: list[str]
    related_questions: list[str]
    harvested_from: str  # Source URL
    harvested_at: str  # ISO timestamp


class EntryGenerator:
    """
    Generates KB entries from documentation content.
    
    Uses Gemini to analyze changed content and extract Q&A pairs.
    Writes entries to the staging directory for human review.
    """
    
    ENTRY_TEMPLATE = """### ID: {id}

**Question**: {question}

**Answer**:
{answer}

**Domain**: {domain}

**Software Version**: {version}

**Valid Until**: {valid_until}

**Confidence**: {confidence:.2f}

**Tier**: {tier}

**Sources**:
{sources}

**Related Questions**:
{related}

**Harvested From**: {harvested_from}
**Harvested At**: {harvested_at}

---
"""

    EXTRACTION_PROMPT = """You are analyzing official documentation content to extract discrete, factual Q&A pairs for a developer knowledge base.

<source>
URL: {url}
Domain: {domain}
Content Type: {content_type}

{content}
</source>

<instructions>
1. Identify discrete, atomic facts that developers commonly need to look up
2. For each fact, formulate a clear question and comprehensive answer
3. Focus on: defaults, limits, syntax, configuration options, breaking changes, deprecations
4. Skip: opinions, tutorials, marketing content, examples without explanation
5. Each Q&A should be self-contained (no "as mentioned above")
6. Include version numbers when the content specifies them
</instructions>

<output_format>
Return a JSON array of entries. Each entry must have:
{{
  "question": "The complete question being answered",
  "answer": "The detailed, factual answer with code examples if relevant",
  "version": "The software version this applies to (or 'latest')",
  "confidence": 0.95,  // How confident you are this is factual (0.80-1.00)
  "tier": "GOLD",  // GOLD=directly from docs, SILVER=inferred, BRONZE=uncertain
  "related": ["Related question 1", "Related question 2", "Related question 3"]
}}
</output_format>

Extract up to 10 high-quality Q&A pairs from this content. Return only the JSON array, no other text.
"""
    
    def __init__(self, staging_dir: Path = None):
        self.staging_dir = staging_dir or Path("kb_staging")
        self.staging_dir.mkdir(exist_ok=True)
    
    async def generate_entries(
        self,
        change_result: ChangeResult,
        content_type: str = "documentation",
    ) -> list[GeneratedEntry]:
        """
        Generate KB entries from changed content.
        
        Args:
            change_result: The ChangeResult with new content
            content_type: Type of content (documentation, release_notes, etc.)
        
        Returns:
            List of generated entries
        """
        if not change_result.content:
            return []
        
        # Truncate very long content
        content = change_result.content[:50000]
        
        try:
            import google.generativeai as genai
            
            genai.configure(api_key=settings.google_api_key)
            model = genai.GenerativeModel(
                model_name="gemini-1.5-flash",  # Use fast model for bulk extraction
                generation_config={
                    "temperature": 0.1,
                    "response_mime_type": "application/json",
                },
            )
            
            prompt = self.EXTRACTION_PROMPT.format(
                url=change_result.url,
                domain=change_result.domain,
                content_type=content_type,
                content=content,
            )
            
            response = model.generate_content(prompt)
            
            import json
            entries_data = json.loads(response.text)
            
        except Exception as e:
            logger.error("extraction_failed", error=str(e), url=change_result.url)
            return []
        
        # Convert to GeneratedEntry objects
        entries = []
        timestamp = datetime.utcnow().isoformat()
        
        for i, data in enumerate(entries_data):
            entry_id = self._generate_id(change_result.domain, data["question"], i)
            
            entry = GeneratedEntry(
                id=entry_id,
                question=data["question"],
                answer=data["answer"],
                domain=change_result.domain,
                software_version=data.get("version", "latest"),
                valid_until="latest",
                confidence=data.get("confidence", 0.90),
                tier=data.get("tier", "SILVER"),
                sources=[change_result.url],
                related_questions=data.get("related", []),
                harvested_from=change_result.url,
                harvested_at=timestamp,
            )
            entries.append(entry)
        
        logger.info(
            "entries_generated",
            domain=change_result.domain,
            count=len(entries),
            source=change_result.url,
        )
        
        return entries
    
    def _generate_id(self, domain: str, question: str, index: int) -> str:
        """Generate a unique entry ID."""
        # Extract keywords from question
        words = re.findall(r'\w+', question.lower())
        keywords = [w for w in words if len(w) > 3 and w not in {'what', 'does', 'how', 'when', 'where', 'which', 'that', 'this', 'with'}][:3]
        slug = "-".join(keywords) if keywords else "entry"
        
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M")
        return f"{domain}-{slug}-harvested-{timestamp}-{index:04d}"
    
    def write_to_staging(self, entries: list[GeneratedEntry]) -> Path:
        """
        Write generated entries to staging directory.
        
        Returns path to the staging file.
        """
        if not entries:
            return None
        
        # Group by domain
        by_domain: dict[str, list[GeneratedEntry]] = {}
        for entry in entries:
            if entry.domain not in by_domain:
                by_domain[entry.domain] = []
            by_domain[entry.domain].append(entry)
        
        files_written = []
        
        for domain, domain_entries in by_domain.items():
            timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
            filename = f"{domain}-harvested-{timestamp}.md"
            filepath = self.staging_dir / filename
            
            content = f"# Harvested Entries: {domain}\n\n"
            content += f"Generated at: {datetime.utcnow().isoformat()}\n"
            content += f"Total entries: {len(domain_entries)}\n\n"
            content += "---\n\n"
            
            for entry in domain_entries:
                sources_md = "\n".join(f"- {s}" for s in entry.sources)
                related_md = "\n".join(f"- {r}" for r in entry.related_questions)
                
                content += self.ENTRY_TEMPLATE.format(
                    id=entry.id,
                    question=entry.question,
                    answer=entry.answer,
                    domain=entry.domain,
                    version=entry.software_version,
                    valid_until=entry.valid_until,
                    confidence=entry.confidence,
                    tier=entry.tier,
                    sources=sources_md,
                    related=related_md,
                    harvested_from=entry.harvested_from,
                    harvested_at=entry.harvested_at,
                )
            
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            
            files_written.append(filepath)
            logger.info("staging_file_written", path=str(filepath), entries=len(domain_entries))
        
        return files_written[0] if files_written else None
    
    async def check_duplicates(
        self,
        entries: list[GeneratedEntry],
        existing_entries: list,  # ParsedKBEntry from kb_parser
    ) -> list[GeneratedEntry]:
        """
        Filter out entries that duplicate existing KB content.
        
        Uses simple text matching for now. Could be enhanced with
        semantic similarity using embeddings.
        """
        unique = []
        
        existing_questions = {e.question.lower().strip() for e in existing_entries}
        
        for entry in entries:
            normalized = entry.question.lower().strip()
            
            # Check for exact match
            if normalized in existing_questions:
                logger.debug("duplicate_skipped", question=entry.question[:50])
                continue
            
            # Check for high substring overlap
            is_dup = False
            for existing in existing_questions:
                if len(normalized) > 20 and len(existing) > 20:
                    # Simple overlap check
                    if normalized in existing or existing in normalized:
                        is_dup = True
                        break
            
            if not is_dup:
                unique.append(entry)
        
        logger.info(
            "dedup_complete",
            original=len(entries),
            unique=len(unique),
            duplicates=len(entries) - len(unique),
        )
        
        return unique

