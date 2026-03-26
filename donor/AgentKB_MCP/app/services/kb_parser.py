"""
Knowledge Base file parser.

Parses Markdown KB files into structured entries.
"""

import logging
import hashlib
from pathlib import Path
from typing import List, Optional, Dict, Iterator, Tuple
from datetime import datetime

from app.models.kb import KBEntry, KBEntryMetadata, ParsedKBEntry
from app.config import get_settings

logger = logging.getLogger(__name__)


class KBParser:
    """
    Parser for KB Markdown files.
    
    Reads and parses KB files from the configured directories,
    supporting both production and staging files.
    """
    
    # Entry separator in Markdown files
    ENTRY_SEPARATOR = "---"
    
    def __init__(self):
        """Initialize the parser."""
        self.settings = get_settings()
        self._entries_cache: Dict[str, KBEntry] = {}
        self._last_scan: Optional[datetime] = None
    
    @property
    def kb_files_path(self) -> Path:
        """Path to production KB files."""
        return Path(self.settings.kb.kb_files_path)
    
    @property
    def kb_staging_path(self) -> Path:
        """Path to staging KB files."""
        return Path(self.settings.kb.kb_staging_path)
    
    def list_domains(self, include_staging: bool = False) -> List[str]:
        """
        List all domains with KB files.
        
        Args:
            include_staging: Whether to include staging domains
            
        Returns:
            List of domain names
        """
        domains = set()
        
        # Production domains
        if self.kb_files_path.exists():
            for file in self.kb_files_path.glob("*.md"):
                domains.add(file.stem)
        
        # Staging domains
        if include_staging and self.kb_staging_path.exists():
            for file in self.kb_staging_path.glob("*-pending.md"):
                domain = file.stem.replace("-pending", "")
                domains.add(f"{domain} (staging)")
        
        return sorted(domains)
    
    def get_file_path(self, domain: str, staging: bool = False) -> Path:
        """
        Get the file path for a domain.
        
        Args:
            domain: The domain name
            staging: Whether to get staging file
            
        Returns:
            Path to the KB file
        """
        if staging:
            return self.kb_staging_path / f"{domain.lower()}-pending.md"
        return self.kb_files_path / f"{domain.lower()}.md"
    
    def parse_file(self, file_path: Path) -> List[KBEntry]:
        """
        Parse a single KB file into entries.
        
        Args:
            file_path: Path to the Markdown file
            
        Returns:
            List of parsed KBEntry objects
        """
        if not file_path.exists():
            logger.warning(f"KB file not found: {file_path}")
            return []
        
        try:
            content = file_path.read_text(encoding="utf-8")
            return self.parse_content(content)
            
        except Exception as e:
            logger.error(f"Error parsing KB file {file_path}: {e}")
            return []
    
    def parse_content(self, content: str) -> List[KBEntry]:
        """
        Parse KB content into entries.
        
        Splits content on entry separators and parses each entry.
        
        Args:
            content: Raw Markdown content
            
        Returns:
            List of parsed KBEntry objects
        """
        entries = []
        
        # Split on the entry separator
        # Entries are separated by "---" on its own line
        raw_entries = content.split(f"\n{self.ENTRY_SEPARATOR}\n")
        
        for raw_entry in raw_entries:
            raw_entry = raw_entry.strip()
            if not raw_entry:
                continue
            
            # Skip if doesn't look like an entry
            if "### ID:" not in raw_entry:
                continue
            
            try:
                entry = KBEntry.from_markdown(raw_entry)
                
                # Validate required fields
                if entry.id and entry.question and entry.answer:
                    entries.append(entry)
                else:
                    logger.warning(f"Skipping incomplete entry: {entry.id or 'unknown'}")
                    
            except Exception as e:
                logger.warning(f"Error parsing entry: {e}")
                continue
        
        return entries
    
    def parse_domain(self, domain: str, include_staging: bool = False) -> List[KBEntry]:
        """
        Parse all entries for a domain.
        
        Args:
            domain: The domain name
            include_staging: Whether to include staging entries
            
        Returns:
            List of entries for the domain
        """
        entries = []
        
        # Production entries
        prod_path = self.get_file_path(domain, staging=False)
        entries.extend(self.parse_file(prod_path))
        
        # Staging entries
        if include_staging:
            staging_path = self.get_file_path(domain, staging=True)
            staging_entries = self.parse_file(staging_path)
            for entry in staging_entries:
                entry.id = f"{entry.id} (staging)"
            entries.extend(staging_entries)
        
        return entries
    
    def parse_all(self, include_staging: bool = False) -> List[KBEntry]:
        """
        Parse all KB entries from all domains.
        
        Args:
            include_staging: Whether to include staging entries
            
        Returns:
            List of all entries
        """
        entries = []
        
        # Production files
        if self.kb_files_path.exists():
            for file in self.kb_files_path.glob("*.md"):
                entries.extend(self.parse_file(file))
        
        # Staging files
        if include_staging and self.kb_staging_path.exists():
            for file in self.kb_staging_path.glob("*-pending.md"):
                staging_entries = self.parse_file(file)
                for entry in staging_entries:
                    entry.id = f"{entry.id} (staging)"
                entries.extend(staging_entries)
        
        return entries
    
    def get_entry_by_id(self, entry_id: str) -> Optional[KBEntry]:
        """
        Get a specific entry by ID.
        
        Args:
            entry_id: The entry ID
            
        Returns:
            The entry if found, None otherwise
        """
        # Check cache first
        if entry_id in self._entries_cache:
            return self._entries_cache[entry_id]
        
        # Parse domain from ID
        parts = entry_id.split("-")
        if len(parts) < 3:
            return None
        
        domain = parts[0]
        
        # Parse the domain file
        entries = self.parse_domain(domain)
        
        # Update cache and find entry
        for entry in entries:
            self._entries_cache[entry.id] = entry
            if entry.id == entry_id:
                return entry
        
        return None
    
    def get_entry_hash(self, entry_id: str) -> Optional[str]:
        """
        Get SHA256 hash of an entry for lockfile support.
        
        Args:
            entry_id: The entry ID
            
        Returns:
            SHA256 hash string or None if not found
        """
        entry = self.get_entry_by_id(entry_id)
        if entry:
            return entry.sha256
        return None
    
    def iter_entries(
        self,
        domain: Optional[str] = None,
        tier: Optional[str] = None,
        version: Optional[str] = None
    ) -> Iterator[KBEntry]:
        """
        Iterate over entries with optional filtering.
        
        Args:
            domain: Filter by domain
            tier: Filter by tier (GOLD, SILVER, BRONZE)
            version: Filter by version compatibility
            
        Yields:
            Matching KBEntry objects
        """
        if domain:
            entries = self.parse_domain(domain)
        else:
            entries = self.parse_all()
        
        for entry in entries:
            # Apply filters
            if tier and entry.tier.upper() != tier.upper():
                continue
            
            if version:
                metadata = entry.metadata
                if not metadata.is_version_compatible(version):
                    continue
            
            yield entry
    
    def get_stats(self) -> Dict:
        """
        Get statistics about the KB.
        
        Returns:
            Dict with entry counts, domain counts, etc.
        """
        entries = self.parse_all()
        
        by_domain = {}
        by_tier = {"GOLD": 0, "SILVER": 0, "BRONZE": 0}
        total_confidence = 0.0
        
        for entry in entries:
            # Count by domain
            domain = entry.domain.lower()
            by_domain[domain] = by_domain.get(domain, 0) + 1
            
            # Count by tier
            tier = entry.tier.upper()
            if tier in by_tier:
                by_tier[tier] += 1
            
            # Sum confidence
            total_confidence += entry.confidence
        
        total = len(entries)
        
        return {
            "total_entries": total,
            "domains": len(by_domain),
            "entries_by_domain": by_domain,
            "entries_by_tier": by_tier,
            "avg_confidence": total_confidence / total if total > 0 else 0.0
        }
    
    def validate_entry(self, entry: KBEntry) -> Tuple[bool, List[str]]:
        """
        Validate an entry against the canonical template.
        
        Args:
            entry: The entry to validate
            
        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []
        
        # Required fields
        if not entry.id:
            errors.append("Missing ID")
        elif not entry.id.startswith(entry.domain.lower() + "-"):
            errors.append(f"ID should start with domain: {entry.domain.lower()}-")
        
        if not entry.question:
            errors.append("Missing Question")
        elif len(entry.question) < 10:
            errors.append("Question too short (minimum 10 characters)")
        
        if not entry.answer:
            errors.append("Missing Answer")
        elif len(entry.answer) < 50:
            errors.append("Answer too short (minimum 50 characters)")
        
        if not entry.domain:
            errors.append("Missing Domain")
        
        if not entry.software_version:
            errors.append("Missing Software Version")
        
        if not entry.valid_until:
            errors.append("Missing Valid Until")
        
        if entry.confidence < 0 or entry.confidence > 1:
            errors.append("Confidence must be between 0.00 and 1.00")
        
        if entry.tier.upper() not in ["GOLD", "SILVER", "BRONZE"]:
            errors.append("Tier must be GOLD, SILVER, or BRONZE")
        
        if not entry.sources or len(entry.sources) == 0:
            errors.append("Must have at least one source")
        
        if not entry.related_questions or len(entry.related_questions) < 3:
            errors.append("Must have at least 3 related questions")
        
        return len(errors) == 0, errors
    
    def clear_cache(self) -> None:
        """Clear the entries cache."""
        self._entries_cache.clear()
        self._last_scan = None

