"""
KB Model service.

Integrates with Gemini for KB queries using the sacrosanct prompt.
"""

import logging
import json
import re
from typing import Optional, List, Dict, Any
from pathlib import Path
from dataclasses import dataclass

from app.config import get_settings
from app.models.kb import ParsedKBEntry
from app.models.responses import AnswerResponse, MissResponse

logger = logging.getLogger(__name__)


@dataclass
class KBModelResponse:
    """Structured response from KB model."""
    
    question: str
    answer: str
    confidence: float
    tier: Optional[str] = None
    sources: List[str] = None
    related_questions: List[str] = None
    reasoning_summary: Optional[str] = None
    entry_ids: List[str] = None
    
    def __post_init__(self):
        if self.sources is None:
            self.sources = []
        if self.related_questions is None:
            self.related_questions = []
        if self.entry_ids is None:
            self.entry_ids = []
    
    @property
    def is_hit(self) -> bool:
        """Check if this is a hit (confidence >= threshold)."""
        settings = get_settings()
        return self.confidence >= settings.kb.confidence_threshold
    
    @property
    def is_miss(self) -> bool:
        """Check if this is a miss."""
        return not self.is_hit


class KBModelService:
    """
    Service for KB model queries.
    
    Uses Gemini with the sacrosanct system prompt defined in
    prompts/kb_model.xml to generate grounded responses.
    """
    
    # The exact miss phrase from the prompt
    MISS_PHRASE = "No verified high-confidence answer found in the knowledge base."
    
    def __init__(self):
        """Initialize the KB model service."""
        self.settings = get_settings()
        self._client = None
        self._system_prompt = None
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize the Gemini client and load system prompt."""
        try:
            import google.generativeai as genai
            
            api_key = self.settings.google.api_key.get_secret_value()
            if not api_key:
                logger.warning("No Google API key configured")
                return
            
            genai.configure(api_key=api_key)
            
            # Create model with generation config
            self._client = genai.GenerativeModel(
                model_name=self.settings.google.model_name,
                generation_config={
                    "temperature": 0.0,  # Strict grounding
                    "top_p": 1.0,
                    "top_k": 1,
                    "max_output_tokens": 4096,
                }
            )
            
            # Load system prompt
            self._system_prompt = self._load_system_prompt()
            
            self._initialized = True
            logger.info("KB model service initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize KB model service: {e}")
    
    def _load_system_prompt(self) -> str:
        """Load the sacrosanct system prompt from file."""
        prompt_path = Path("prompts/kb_model.xml")
        
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        
        # Fallback to inline prompt if file not found
        logger.warning("kb_model.xml not found, using inline fallback")
        return self._get_fallback_prompt()
    
    def _get_fallback_prompt(self) -> str:
        """Fallback system prompt if file not available."""
        return """You are an ultra-precise, grounded knowledge base specialized in developer technologies.

CRITICAL RULES:
1. NEVER hallucinate, speculate, or invent details
2. Only use information from the provided context chunks
3. If confidence < 0.80, output: "No verified high-confidence answer found in the knowledge base."
4. Always include source URLs from the chunks
5. Provide confidence score between 0.00 and 1.00

OUTPUT FORMAT (JSON):
{
    "question": "restate the original question",
    "answer": "the grounded answer from chunks",
    "confidence": 0.95,
    "tier": "GOLD",
    "sources": ["url1", "url2"],
    "related_questions": ["q1", "q2", "q3"],
    "reasoning_summary": "only if synthesis was required"
}
"""
    
    @property
    def is_available(self) -> bool:
        """Check if the service is available."""
        return self._initialized and self._client is not None
    
    def _format_context(self, chunks: List[ParsedKBEntry]) -> str:
        """
        Format retrieved chunks for the model context.
        
        Args:
            chunks: List of parsed KB entries
            
        Returns:
            Formatted context string
        """
        context_parts = []
        
        for i, chunk in enumerate(chunks, 1):
            entry = chunk.entry
            context_parts.append(f"""
--- Chunk {i} ---
ID: {entry.id}
Question: {entry.question}
Answer: {entry.answer}
Domain: {entry.domain}
Software Version: {entry.software_version}
Valid Until: {entry.valid_until}
Confidence: {entry.confidence}
Tier: {entry.tier}
Sources: {', '.join(entry.sources)}
Related Questions: {', '.join(entry.related_questions)}
Similarity Score: {chunk.similarity:.2f}
Adjusted Confidence: {chunk.adjusted_confidence:.2f}
---
""")
        
        return "\n".join(context_parts)
    
    def _parse_response(self, response_text: str, original_question: str) -> KBModelResponse:
        """
        Parse the model response into structured format.
        
        Args:
            response_text: Raw response from model
            original_question: The original question asked
            
        Returns:
            Parsed KBModelResponse
        """
        # Try to extract JSON from response
        try:
            # Find JSON block in response
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                data = json.loads(json_match.group())
                
                return KBModelResponse(
                    question=data.get("question", original_question),
                    answer=data.get("answer", ""),
                    confidence=float(data.get("confidence", 0.0)),
                    tier=data.get("tier"),
                    sources=data.get("sources", []),
                    related_questions=data.get("related_questions", []),
                    reasoning_summary=data.get("reasoning_summary"),
                    entry_ids=data.get("entry_ids", [])
                )
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse JSON response: {e}")
        
        # Check for miss phrase
        if self.MISS_PHRASE in response_text:
            return KBModelResponse(
                question=original_question,
                answer=self.MISS_PHRASE,
                confidence=0.0,
                sources=[],
                related_questions=[]
            )
        
        # Fallback: treat entire response as answer with low confidence
        return KBModelResponse(
            question=original_question,
            answer=response_text[:2000],  # Truncate if too long
            confidence=0.5,  # Low confidence for unparsed responses
            sources=[],
            related_questions=[]
        )
    
    async def query(
        self,
        question: str,
        chunks: List[ParsedKBEntry],
        software_version: Optional[str] = None
    ) -> KBModelResponse:
        """
        Query the KB model with retrieved chunks.
        
        Args:
            question: The user's question
            chunks: Retrieved KB entry chunks
            software_version: Optional version context
            
        Returns:
            Structured response from the model
        """
        if not self.is_available:
            logger.warning("KB model not available, returning miss")
            return KBModelResponse(
                question=question,
                answer=self.MISS_PHRASE,
                confidence=0.0,
                sources=[],
                related_questions=[]
            )
        
        # Check for empty chunks
        if not chunks:
            return KBModelResponse(
                question=question,
                answer=self.MISS_PHRASE,
                confidence=0.0,
                sources=[],
                related_questions=[]
            )
        
        # Check for high-confidence exact match (fast path)
        if len(chunks) == 1:
            top_chunk = chunks[0]
            if (top_chunk.adjusted_confidence >= 0.95 and 
                top_chunk.entry.tier == "GOLD" and
                top_chunk.similarity >= 0.9):
                # Fast path: return directly from chunk
                return KBModelResponse(
                    question=question,
                    answer=top_chunk.entry.answer,
                    confidence=top_chunk.adjusted_confidence,
                    tier=top_chunk.entry.tier,
                    sources=top_chunk.entry.sources,
                    related_questions=top_chunk.entry.related_questions,
                    entry_ids=[top_chunk.entry.id]
                )
        
        # Build the full prompt
        context = self._format_context(chunks)
        
        version_context = ""
        if software_version:
            version_context = f"\nUser is asking about version: {software_version}"
        
        full_prompt = f"""{self._system_prompt}

<retrieved_chunks>
{context}
</retrieved_chunks>
{version_context}

User Question: {question}

Provide your response in the specified JSON format:"""

        try:
            # Call the model
            response = self._client.generate_content(full_prompt)
            
            if response.text:
                return self._parse_response(response.text, question)
            else:
                logger.warning("Empty response from model")
                return KBModelResponse(
                    question=question,
                    answer=self.MISS_PHRASE,
                    confidence=0.0,
                    sources=[],
                    related_questions=[]
                )
                
        except Exception as e:
            logger.error(f"KB model query failed: {e}")
            return KBModelResponse(
                question=question,
                answer=self.MISS_PHRASE,
                confidence=0.0,
                sources=[],
                related_questions=[]
            )
    
    def to_answer_response(
        self,
        model_response: KBModelResponse,
        cache_hit: bool = False,
        entry_hashes: Optional[Dict[str, str]] = None
    ) -> AnswerResponse:
        """
        Convert model response to API AnswerResponse.
        
        Args:
            model_response: The KB model response
            cache_hit: Whether this was a cache hit
            entry_hashes: Optional entry SHA256 hashes for lockfiles
            
        Returns:
            AnswerResponse for API
        """
        return AnswerResponse(
            question=model_response.question,
            answer=model_response.answer,
            confidence=model_response.confidence,
            tier=model_response.tier,
            sources=model_response.sources,
            related_questions=model_response.related_questions,
            reasoning_summary=model_response.reasoning_summary,
            cache_hit=cache_hit,
            entry_id=model_response.entry_ids[0] if model_response.entry_ids else None,
            entry_ids=model_response.entry_ids if model_response.entry_ids else None,
            entry_hashes_sha256=entry_hashes
        )
    
    def to_miss_response(
        self,
        model_response: KBModelResponse,
        queue_id: Optional[str] = None
    ) -> MissResponse:
        """
        Convert model response to API MissResponse.
        
        Args:
            model_response: The KB model response
            queue_id: Queue item ID if queued
            
        Returns:
            MissResponse for API
        """
        return MissResponse(
            question=model_response.question,
            answer=self.MISS_PHRASE,
            confidence=model_response.confidence,
            queued=queue_id is not None,
            queue_id=queue_id,
            related_questions=model_response.related_questions
        )

