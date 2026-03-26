"""
Change Detector - Monitors sources for content changes.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import httpx
import structlog

from app.harvester.registry import Source

logger = structlog.get_logger()


@dataclass
class ChangeResult:
    """Result of checking a source for changes."""
    url: str
    domain: str
    changed: bool
    old_hash: Optional[str]
    new_hash: str
    content: Optional[str]  # Only populated if changed
    error: Optional[str] = None


class ChangeDetector:
    """
    Detects changes in documentation sources.
    
    Uses content hashing to determine if a page has been updated.
    Stores hash history in a local JSON file.
    """
    
    def __init__(self, state_path: Path = None):
        self.state_path = state_path or Path(".harvester_state.json")
        self.state: dict = {}
        self._load_state()
    
    def _load_state(self) -> None:
        """Load persisted state."""
        if self.state_path.exists():
            with open(self.state_path) as f:
                self.state = json.load(f)
        else:
            self.state = {"sources": {}, "last_run": None}
    
    def _save_state(self) -> None:
        """Save state to disk."""
        self.state["last_run"] = datetime.utcnow().isoformat()
        with open(self.state_path, "w") as f:
            json.dump(self.state, f, indent=2)
    
    def _compute_hash(self, content: str) -> str:
        """Compute SHA-256 hash of content."""
        return hashlib.sha256(content.encode()).hexdigest()
    
    def _should_check(self, source: Source) -> bool:
        """Determine if source should be checked based on interval."""
        source_key = source.url
        
        if source_key not in self.state["sources"]:
            return True
        
        last_checked_str = self.state["sources"][source_key].get("last_checked")
        if not last_checked_str:
            return True
        
        last_checked = datetime.fromisoformat(last_checked_str)
        now = datetime.utcnow()
        
        intervals = {
            "hourly": timedelta(hours=1),
            "daily": timedelta(days=1),
            "weekly": timedelta(weeks=1),
        }
        
        interval = intervals.get(source.check_interval, timedelta(days=1))
        return now - last_checked >= interval
    
    async def check_source(self, domain: str, source: Source) -> ChangeResult:
        """
        Check a single source for changes.
        
        Returns a ChangeResult indicating whether content changed.
        """
        source_key = source.url
        old_hash = self.state["sources"].get(source_key, {}).get("hash")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(source.url, follow_redirects=True)
                response.raise_for_status()
                content = response.text
        except Exception as e:
            logger.error("fetch_failed", url=source.url, error=str(e))
            return ChangeResult(
                url=source.url,
                domain=domain,
                changed=False,
                old_hash=old_hash,
                new_hash="",
                content=None,
                error=str(e),
            )
        
        new_hash = self._compute_hash(content)
        changed = old_hash != new_hash
        
        # Update state
        self.state["sources"][source_key] = {
            "hash": new_hash,
            "last_checked": datetime.utcnow().isoformat(),
            "domain": domain,
        }
        self._save_state()
        
        logger.info(
            "source_checked",
            url=source.url,
            domain=domain,
            changed=changed,
        )
        
        return ChangeResult(
            url=source.url,
            domain=domain,
            changed=changed,
            old_hash=old_hash,
            new_hash=new_hash,
            content=content if changed else None,
        )
    
    async def check_all(
        self,
        sources: list[tuple[str, Source]],
        force: bool = False,
    ) -> list[ChangeResult]:
        """
        Check all sources for changes.
        
        Args:
            sources: List of (domain, source) tuples
            force: If True, ignore check intervals
        
        Returns:
            List of ChangeResults for sources that were checked
        """
        results = []
        
        for domain, source in sources:
            if not force and not self._should_check(source):
                logger.debug("skipping_source", url=source.url, reason="interval_not_met")
                continue
            
            result = await self.check_source(domain, source)
            results.append(result)
        
        return results
    
    def get_changed_sources(self, results: list[ChangeResult]) -> list[ChangeResult]:
        """Filter results to only those with changes."""
        return [r for r in results if r.changed and not r.error]

