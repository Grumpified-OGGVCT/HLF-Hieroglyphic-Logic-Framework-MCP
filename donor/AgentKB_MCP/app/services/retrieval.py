"""
Intelligent retrieval pipeline.

Implements the full retrieval flow with caching, normalization,
fallback chain, and confidence decay.
"""

import re
import logging
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from pybreaker import CircuitBreaker, CircuitBreakerError

from app.config import get_settings
from app.services.cache import CacheService
from app.services.kb_parser import KBParser
from app.services.embedding import EmbeddingService
from app.models.kb import ParsedKBEntry, KBEntry
from app.services.retrieval_transformation import QueryTransformationEngine

logger = logging.getLogger(__name__)


class IntelligentRetriever:
    """
    Intelligent retrieval pipeline.
    
    Implements:
    - Query normalization (abbreviation expansion)
    - Cache-first architecture
    - Google File Search primary retrieval
    - Fallback chain (local vector DB, file grep)
    - Confidence decay based on entry age
    - Stack pack filtering
    """
    
    # Abbreviation mappings for query normalization
    ABBREVIATIONS = {
        "k8s": "kubernetes",
        "postgres": "postgresql",
        "psql": "postgresql",
        "js": "javascript",
        "ts": "typescript",
        "py": "python",
        "tf": "tensorflow",
        "sklearn": "scikit-learn",
        "ml": "machine learning",
        "dl": "deep learning",
        "api": "application programming interface",
        "db": "database",
        "sql": "structured query language",
        "nosql": "non-relational database",
        "aws": "amazon web services",
        "gcp": "google cloud platform",
        "ecs": "elastic container service",
        "eks": "elastic kubernetes service",
        "rds": "relational database service",
        "s3": "simple storage service",
        "ec2": "elastic compute cloud",
        "ci": "continuous integration",
        "cd": "continuous deployment",
    }
    
    def __init__(
        self,
        cache_service: Optional[CacheService] = None,
        kb_parser: Optional[KBParser] = None,
        embedding_service: Optional[EmbeddingService] = None
    ):
        """
        Initialize the retriever.
        
        Args:
            cache_service: Optional cache service (creates one if not provided)
            kb_parser: Optional KB parser (creates one if not provided)
            embedding_service: Optional embedding service
        """
        self.settings = get_settings()
        self.cache = cache_service or CacheService()
        self.kb_parser = kb_parser or KBParser()
        self.embedding_service = embedding_service or EmbeddingService()
        self._query_transformer = QueryTransformationEngine()
        
        # Initialize circuit breaker for Google services
        self._google_breaker = CircuitBreaker(
            fail_max=self.settings.circuit_breaker.fail_max,
            reset_timeout=self.settings.circuit_breaker.reset_timeout
        )
        
        # File Search client (initialized lazily)
        self._file_search_client = None
    
    async def initialize(self) -> None:
        """Initialize external services."""
        await self.cache.connect()
        await self.embedding_service.initialize()
        # File search will be initialized on first use
    
    async def close(self) -> None:
        """Close connections."""
        await self.cache.close()
        await self._query_transformer.close()
    
    def _normalize_question(self, question: str) -> str:
        """
        Normalize question by expanding abbreviations.
        
        Args:
            question: The raw question
            
        Returns:
            Normalized question with abbreviations expanded
        """
        normalized = question.lower().strip()
        
        for abbr, full in self.ABBREVIATIONS.items():
            # Use word boundaries to avoid partial replacements
            pattern = r'\b' + re.escape(abbr) + r'\b'
            normalized = re.sub(pattern, full, normalized, flags=re.IGNORECASE)
        
        return normalized
    
    def _apply_confidence_decay(
        self,
        entries: List[ParsedKBEntry],
        current_time: Optional[datetime] = None
    ) -> List[ParsedKBEntry]:
        """
        Apply confidence decay based on entry age.
        
        Args:
            entries: List of parsed entries
            current_time: Current time for calculation (defaults to now)
            
        Returns:
            Entries with adjusted confidence scores
        """
        if current_time is None:
            current_time = datetime.utcnow()
        
        decay_rate = self.settings.kb.confidence_decay_rate
        
        for entry in entries:
            if entry.entry.created_at:
                # Calculate months since creation
                delta = current_time - entry.entry.created_at
                months_old = delta.days / 30.0
                
                # Apply decay: adjusted = base * (decay_rate ^ months)
                decay_factor = decay_rate ** months_old
                entry.adjusted_confidence = entry.entry.confidence * decay_factor
            else:
                # No creation date, assume recent (no decay)
                entry.adjusted_confidence = entry.entry.confidence
        
        return entries
    
    def _filter_by_version(
        self,
        entries: List[ParsedKBEntry],
        software_version: Optional[str]
    ) -> List[ParsedKBEntry]:
        """
        Filter entries by version compatibility.
        
        Args:
            entries: List of parsed entries
            software_version: Target version (None means latest)
            
        Returns:
            Filtered entries
        """
        filtered = []
        
        for entry in entries:
            metadata = entry.entry.metadata
            if metadata.is_version_compatible(software_version):
                filtered.append(entry)
        
        return filtered
    
    def _filter_by_stack_pack(
        self,
        entries: List[ParsedKBEntry],
        stack_pack: Optional[str]
    ) -> List[ParsedKBEntry]:
        """
        Filter entries by stack pack membership.
        
        Args:
            entries: List of parsed entries
            stack_pack: Stack pack ID
            
        Returns:
            Filtered entries
        """
        if not stack_pack:
            return entries
        
        # Load stack pack manifest
        import json
        from pathlib import Path
        
        pack_path = Path(self.settings.kb.stack_packs_path) / f"{stack_pack}.json"
        
        if not pack_path.exists():
            logger.warning(f"Stack pack not found: {stack_pack}")
            return entries
        
        try:
            with open(pack_path) as f:
                manifest = json.load(f)
            
            entry_ids = set(manifest.get("entry_ids", []))
            
            if not entry_ids:
                return entries
            
            return [e for e in entries if e.entry.id in entry_ids]
            
        except Exception as e:
            logger.error(f"Error loading stack pack: {e}")
            return entries
    
    async def _primary_retrieval(
        self,
        query: str,
        domain: Optional[str],
        top_k: int = 10
    ) -> List[ParsedKBEntry]:
        """
        Primary retrieval using Google File Search.
        
        Args:
            query: Normalized query
            domain: Optional domain filter
            top_k: Number of results to retrieve
            
        Returns:
            List of parsed entries from retrieval
        """
        try:
            # Use circuit breaker
            with self._google_breaker:
                # TODO: Implement actual Google File Search integration
                # For now, fall back to local retrieval
                logger.info("Google File Search not yet integrated, using local fallback")
                return await self._fallback_local_retrieval(query, domain, top_k)
                
        except CircuitBreakerError:
            logger.warning("Circuit breaker open for Google services")
            return await self._fallback_local_retrieval(query, domain, top_k)
    
    async def _fallback_local_retrieval(
        self,
        query: str,
        domain: Optional[str],
        top_k: int = 10
    ) -> List[ParsedKBEntry]:
        """
        Fallback retrieval using local KB files.
        
        Args:
            query: Normalized query
            domain: Optional domain filter
            top_k: Number of results to retrieve
            
        Returns:
            List of parsed entries
        """
        # Get all entries (filtered by domain if specified)
        if domain:
            entries = self.kb_parser.parse_domain(domain)
        else:
            entries = self.kb_parser.parse_all()
        
        if not entries:
            return []
        
        # Calculate similarity scores
        query_embedding = await self.embedding_service.embed_query(query)
        
        scored_entries: List[Tuple[KBEntry, float]] = []
        
        for entry in entries:
            if query_embedding:
                # Get entry embedding
                entry_embedding = await self.embedding_service.embed(
                    f"{entry.question} {entry.answer[:500]}"
                )
                
                if entry_embedding:
                    similarity = self.embedding_service.cosine_similarity(
                        query_embedding, entry_embedding
                    )
                    scored_entries.append((entry, similarity))
                else:
                    # Fall back to keyword matching
                    similarity = self._keyword_similarity(query, entry)
                    scored_entries.append((entry, similarity))
            else:
                # No embeddings available, use keyword matching
                similarity = self._keyword_similarity(query, entry)
                scored_entries.append((entry, similarity))
        
        # Sort by similarity and take top_k
        scored_entries.sort(key=lambda x: x[1], reverse=True)
        top_entries = scored_entries[:top_k]
        
        # Convert to ParsedKBEntry
        results = []
        for entry, similarity in top_entries:
            parsed = ParsedKBEntry(
                entry=entry,
                similarity=similarity,
                adjusted_confidence=entry.confidence
            )
            results.append(parsed)
        
        return results
    
    def _keyword_similarity(self, query: str, entry: KBEntry) -> float:
        """
        Simple keyword-based similarity.
        
        Args:
            query: The search query
            entry: The KB entry
            
        Returns:
            Similarity score between 0 and 1
        """
        query_words = set(query.lower().split())
        entry_text = f"{entry.question} {entry.answer}".lower()
        entry_words = set(entry_text.split())
        
        if not query_words:
            return 0.0
        
        # Jaccard-like similarity
        intersection = query_words & entry_words
        union = query_words | entry_words
        
        if not union:
            return 0.0
        
        return len(intersection) / len(query_words)
    
    async def _fallback_grep_retrieval(
        self,
        query: str,
        domain: Optional[str]
    ) -> List[ParsedKBEntry]:
        """
        Last-resort fallback using file grep.
        
        Args:
            query: The search query
            domain: Optional domain filter
            
        Returns:
            List of matching entries
        """
        from pathlib import Path
        
        results = []
        kb_path = Path(self.settings.kb.kb_files_path)
        
        if not kb_path.exists():
            return []
        
        # Determine files to search
        if domain:
            files = [kb_path / f"{domain.lower()}.md"]
        else:
            files = list(kb_path.glob("*.md"))
        
        # Search terms from query
        search_terms = query.lower().split()
        
        for file in files:
            if not file.exists():
                continue
            
            try:
                content = file.read_text(encoding="utf-8")
                
                # Parse entries from file
                entries = self.kb_parser.parse_content(content)
                
                for entry in entries:
                    # Check if any search term appears in entry
                    entry_text = f"{entry.question} {entry.answer}".lower()
                    
                    matches = sum(1 for term in search_terms if term in entry_text)
                    
                    if matches > 0:
                        similarity = matches / len(search_terms)
                        results.append(ParsedKBEntry(
                            entry=entry,
                            similarity=similarity,
                            adjusted_confidence=entry.confidence * 0.8  # Penalty for grep
                        ))
                        
            except Exception as e:
                logger.warning(f"Error searching file {file}: {e}")
        
        # Sort by similarity
        results.sort(key=lambda x: x.similarity, reverse=True)
        
        return results[:10]
    
    async def retrieve(
        self,
        question: str,
        domain: Optional[str] = None,
        software_version: Optional[str] = None,
        stack_pack: Optional[str] = None,
        top_k: int = 10
    ) -> Tuple[List[ParsedKBEntry], bool]:
        """
        Main retrieval method.
        
        Implements the full retrieval flow:
        1. Check cache
        2. Normalize question
        3. Apply filters
        4. Try primary retrieval (with fallback chain)
        5. Apply confidence decay
        6. Cache results
        
        Args:
            question: The question to search for
            domain: Optional domain filter
            software_version: Optional version filter
            stack_pack: Optional stack pack filter
            top_k: Number of results to retrieve
            
        Returns:
            Tuple of (list of entries, cache_hit flag)
        """
        # 1. Check cache first
        cached = await self.cache.get(question, domain, software_version, stack_pack)
        if cached:
            # Deserialize cached entries
            entries = []
            for item in cached.get("entries", []):
                try:
                    entry = KBEntry(**item["entry"])
                    parsed = ParsedKBEntry(
                        entry=entry,
                        similarity=item.get("similarity", 1.0),
                        adjusted_confidence=item.get("adjusted_confidence", entry.confidence)
                    )
                    entries.append(parsed)
                except Exception as e:
                    logger.warning(f"Error deserializing cached entry: {e}")
            
            if entries:
                return entries, True
        
        # 2. Retrieval Transformation (replaces abbreviation-only normalization)
        # If transformation fails, fall back to the legacy normalization behavior.
        try:
            transformed = await self._query_transformer.transform(question)
            candidate_queries = self._query_transformer.build_query_strings(transformed, question)
        except Exception as e:
            logger.warning(f"Query transformation failed: {e}, falling back to legacy normalization")
            candidate_queries = [self._normalize_question(question)]

        # 3. Try primary retrieval with fallback chain (supports decomposed queries)
        entries_by_id: Dict[str, ParsedKBEntry] = {}
        for q in candidate_queries:
            try:
                found = await self._primary_retrieval(q, domain, top_k)
            except Exception as e:
                logger.warning(f"Primary retrieval failed: {e}, trying local fallback")
                found = await self._fallback_local_retrieval(q, domain, top_k)

            for pe in found:
                existing = entries_by_id.get(pe.entry.id)
                if existing is None:
                    entries_by_id[pe.entry.id] = pe
                else:
                    # Keep the best similarity signal across query variants.
                    if pe.similarity > existing.similarity:
                        existing.similarity = pe.similarity
                    # Keep the highest base adjusted confidence prior to decay.
                    if pe.adjusted_confidence > existing.adjusted_confidence:
                        existing.adjusted_confidence = pe.adjusted_confidence

        entries = list(entries_by_id.values())
        
        if not entries:
            # Last resort: grep (try candidate queries in order)
            for q in candidate_queries:
                entries = await self._fallback_grep_retrieval(q, domain)
                if entries:
                    break
        
        # 4. Apply version filtering
        entries = self._filter_by_version(entries, software_version)
        
        # 5. Apply stack pack filtering
        entries = self._filter_by_stack_pack(entries, stack_pack)
        
        # 6. Apply confidence decay
        entries = self._apply_confidence_decay(entries)
        
        # 7. Sort by adjusted confidence
        entries.sort(key=lambda x: x.adjusted_confidence, reverse=True)
        
        # 8. Cache results
        if entries:
            cache_data = {
                "entries": [
                    {
                        "entry": e.entry.model_dump(),
                        "similarity": e.similarity,
                        "adjusted_confidence": e.adjusted_confidence
                    }
                    for e in entries
                ],
                "domain": domain,
                "software_version": software_version,
                "stack_pack": stack_pack
            }
            
            is_hit = entries[0].adjusted_confidence >= self.settings.kb.confidence_threshold
            await self.cache.set(
                question, cache_data, domain, software_version, stack_pack, is_hit
            )
        
        return entries, False
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check retrieval service health.
        
        Returns:
            Health status dict
        """
        cache_health = await self.cache.health_check()
        
        # Check KB files
        from pathlib import Path
        kb_path = Path(self.settings.kb.kb_files_path)
        kb_exists = kb_path.exists()
        
        # Check circuit breaker
        breaker_state = "closed"  # Healthy
        if self._google_breaker.current_state == "open":
            breaker_state = "open"
        elif self._google_breaker.current_state == "half-open":
            breaker_state = "half-open"
        
        return {
            "cache": cache_health,
            "kb_files": "available" if kb_exists else "missing",
            "circuit_breaker": breaker_state,
            "embeddings": "available" if self.embedding_service.is_available else "unavailable"
        }

