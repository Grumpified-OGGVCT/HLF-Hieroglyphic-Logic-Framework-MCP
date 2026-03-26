"""
Embedding service for semantic operations.

Provides embeddings for questions to enable semantic deduplication
and similarity search.
"""

import logging
from typing import List, Optional
import hashlib

from app.config import get_settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Service for generating text embeddings.
    
    Uses Google's embedding model for semantic operations.
    Falls back to simple hashing if API unavailable.
    """
    
    def __init__(self):
        """Initialize the embedding service."""
        self.settings = get_settings()
        self._client = None
        self._initialized = False
        self._dimension = 768  # Default for Gemini embeddings
    
    async def initialize(self) -> None:
        """Initialize the Gemini client."""
        try:
            import google.generativeai as genai
            
            api_key = self.settings.google.api_key.get_secret_value()
            if not api_key:
                logger.warning("No Google API key configured, embeddings will be unavailable")
                return
            
            genai.configure(api_key=api_key)
            self._client = genai
            self._initialized = True
            logger.info("Embedding service initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize embedding service: {e}")
    
    @property
    def is_available(self) -> bool:
        """Check if embedding service is available."""
        return self._initialized and self._client is not None
    
    @property
    def dimension(self) -> int:
        """Get embedding dimension."""
        return self._dimension
    
    async def embed(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding for a single text.
        
        Args:
            text: The text to embed
            
        Returns:
            List of floats representing the embedding, or None if unavailable
        """
        if not self.is_available:
            logger.debug("Embedding service not available, returning None")
            return None
        
        try:
            result = self._client.embed_content(
                model=self.settings.google.embedding_model,
                content=text,
                task_type="retrieval_document"
            )
            
            embedding = result['embedding']
            self._dimension = len(embedding)
            
            return embedding
            
        except Exception as e:
            logger.error(f"Embedding failed: {e}")
            return None
    
    async def embed_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embeddings (may contain None for failed items)
        """
        if not self.is_available:
            return [None] * len(texts)
        
        try:
            # Gemini supports batch embedding
            result = self._client.embed_content(
                model=self.settings.google.embedding_model,
                content=texts,
                task_type="retrieval_document"
            )
            
            embeddings = result['embedding']
            if embeddings and len(embeddings) > 0:
                self._dimension = len(embeddings[0])
            
            return embeddings
            
        except Exception as e:
            logger.error(f"Batch embedding failed: {e}")
            # Fall back to individual embedding
            return [await self.embed(t) for t in texts]
    
    async def embed_query(self, query: str) -> Optional[List[float]]:
        """
        Generate embedding for a search query.
        
        Uses slightly different task type optimized for queries.
        
        Args:
            query: The search query
            
        Returns:
            Query embedding
        """
        if not self.is_available:
            return None
        
        try:
            result = self._client.embed_content(
                model=self.settings.google.embedding_model,
                content=query,
                task_type="retrieval_query"
            )
            
            return result['embedding']
            
        except Exception as e:
            logger.error(f"Query embedding failed: {e}")
            return None
    
    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Calculate cosine similarity between two vectors.
        
        Args:
            vec1: First vector
            vec2: Second vector
            
        Returns:
            Cosine similarity (-1 to 1)
        """
        import math
        
        if len(vec1) != len(vec2):
            raise ValueError("Vectors must have same dimension")
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    def fallback_hash_embedding(self, text: str, dimension: int = 768) -> List[float]:
        """
        Generate a deterministic pseudo-embedding using hashing.
        
        This is a fallback for when the API is unavailable.
        It won't provide semantic similarity but allows dedup
        of exact matches.
        
        Args:
            text: Text to hash
            dimension: Output dimension
            
        Returns:
            Pseudo-embedding as list of floats
        """
        # Use multiple hash functions to generate enough values
        import struct
        
        embedding = []
        for i in range(dimension):
            # Create unique hash for each dimension
            hash_input = f"{text}_{i}".encode()
            hash_bytes = hashlib.sha256(hash_input).digest()
            # Convert first 4 bytes to float in range [-1, 1]
            value = struct.unpack('f', hash_bytes[:4])[0]
            # Normalize to [-1, 1] range
            normalized = (value % 2.0) - 1.0
            embedding.append(normalized)
        
        # Normalize the vector
        import math
        norm = math.sqrt(sum(x * x for x in embedding))
        if norm > 0:
            embedding = [x / norm for x in embedding]
        
        return embedding

