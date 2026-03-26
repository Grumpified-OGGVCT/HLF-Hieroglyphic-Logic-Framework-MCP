"""
Research Agent service.

Performs research using official sources to expand the KB.
"""

import logging
import json
import re
from typing import Optional, Dict, Any
from pathlib import Path
from datetime import datetime

from app.config import get_settings
from app.models.kb import KBEntry
from app.services.sanitizer import PIISanitizer
from app.agents.researcher import ResearchAgent, ModelRef

logger = logging.getLogger(__name__)


class ResearchAgentService:
    """
    Research Agent for KB expansion.
    
    Uses Gemini with the research prompt to perform targeted research
    from official sources only.
    """
    
    # Discard phrase from the prompt
    DISCARD_PHRASE = "Insufficient official information – discard this queue entry"
    
    # Official source domains (from prompt)
    OFFICIAL_DOMAINS = [
        "postgresql.org",
        "nextjs.org",
        "typescriptlang.org",
        "fastapi.tiangolo.com",
        "docs.docker.com",
        "kubernetes.io",
        "docs.aws.amazon.com",
        "python.org",
        "rust-lang.org",
        "golang.org",
        "reactjs.org",
        "vuejs.org",
        "angular.io",
        "nodejs.org",
        "redis.io",
        "mongodb.com/docs",
        "developer.mozilla.org",
    ]
    
    def __init__(self):
        """Initialize the research agent service."""
        self.settings = get_settings()
        self._client = None
        self._system_prompt = None
        self._initialized = False
        self.sanitizer = PIISanitizer()
        self.last_qa_audit_message: Optional[str] = None
    
    async def initialize(self) -> None:
        """Initialize the Gemini client and load system prompt."""
        try:
            import google.generativeai as genai
            
            api_key = self.settings.google.api_key.get_secret_value()
            if not api_key:
                logger.warning("No Google API key configured for research")
                return
            
            genai.configure(api_key=api_key)
            
            # Create model with appropriate config for research
            self._client = genai.GenerativeModel(
                model_name=self.settings.google.research_model_name,
                generation_config={
                    "temperature": 0.1,  # Low but not zero for research
                    "top_p": 0.95,
                    "max_output_tokens": 8192,  # Longer for research output
                }
            )
            
            # Load system prompt
            self._system_prompt = self._load_system_prompt()
            
            self._initialized = True
            logger.info("Research agent service initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize research agent: {e}")
    
    def _load_system_prompt(self) -> str:
        """Load the sacrosanct research prompt from file."""
        prompt_path = Path("prompts/research_model.xml")
        
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        
        logger.warning("research_model.xml not found, using inline fallback")
        return self._get_fallback_prompt()
    
    def _get_fallback_prompt(self) -> str:
        """Fallback research prompt if file not available."""
        return """You are the Research Agent for a developer knowledge base.

CRITICAL RULES:
1. Research ONLY from official documentation:
   - postgresql.org, nextjs.org, typescriptlang.org, etc.
2. NEVER use forums, blogs, StackOverflow, Reddit, Medium
3. If no authoritative source found, output:
   "Insufficient official information – discard this queue entry"
4. Generate exactly ONE new KB entry if successful

OUTPUT FORMAT (Markdown):
### ID: {domain}-{descriptive-id}-{number}

**Question**: The question being answered

**Answer**:
Full technical answer with code examples...

**Domain**: domain-name

**Software Version**: X.Y.Z

**Valid Until**: latest

**Confidence**: 0.95

**Tier**: GOLD

**Sources**:
- https://official-url-1
- https://official-url-2

**Related Questions**:
- Related question 1
- Related question 2
- Related question 3

---
"""
    
    @property
    def is_available(self) -> bool:
        """Check if the service is available."""
        return self._initialized and self._client is not None
    
    def _extract_domain_from_question(self, question: str) -> str:
        """
        Extract the likely domain from a question.
        
        Args:
            question: The question text
            
        Returns:
            Best guess domain
        """
        question_lower = question.lower()
        
        # Domain keywords
        domain_keywords = {
            "postgresql": ["postgresql", "postgres", "psql", "pg_"],
            "nextjs": ["next.js", "nextjs", "next js", "getserversideprops"],
            "typescript": ["typescript", "ts", ".ts file", "type annotation"],
            "fastapi": ["fastapi", "fast api", "starlette"],
            "docker": ["docker", "dockerfile", "container", "docker-compose"],
            "kubernetes": ["kubernetes", "k8s", "kubectl", "pod", "deployment"],
            "aws": ["aws", "amazon", "ec2", "s3", "lambda", "dynamodb"],
            "python": ["python", "pip", "venv", ".py"],
            "rust": ["rust", "cargo", "rustc", ".rs"],
            "go": ["golang", "go ", " go", "goroutine"],
            "react": ["react", "jsx", "usestate", "useeffect"],
            "nodejs": ["node.js", "nodejs", "npm", "express"],
            "redis": ["redis", "redis-cli"],
            "mongodb": ["mongodb", "mongo", "mongoose"],
        }
        
        for domain, keywords in domain_keywords.items():
            for keyword in keywords:
                if keyword in question_lower:
                    return domain
        
        return "general"
    
    def _generate_entry_id(self, domain: str, question: str) -> str:
        """
        Generate a unique entry ID.
        
        Args:
            domain: The domain
            question: The question text
            
        Returns:
            Entry ID in format domain-descriptive-0001
        """
        # Create descriptive slug from question
        words = re.sub(r'[^\w\s]', '', question.lower()).split()[:5]
        slug = "-".join(words)
        
        # Add timestamp for uniqueness
        timestamp = datetime.utcnow().strftime("%H%M%S")
        
        return f"{domain}-{slug}-{timestamp}"
    
    async def research(
        self,
        question: str,
        domain: Optional[str] = None,
        software_version: Optional[str] = None
    ) -> Optional[KBEntry]:
        """
        Perform research for a question.
        
        Args:
            question: The question to research
            domain: Optional domain hint
            software_version: Optional version context
            
        Returns:
            New KBEntry if successful, None if discarded
        """
        if not self.is_available:
            logger.warning("Research agent not available")
            return None
        
        # Sanitization check
        if self.sanitizer.contains_sensitive(question):
            logger.warning(f"Question contains sensitive content, skipping research")
            return None
        
        # Determine domain
        if not domain:
            domain = self._extract_domain_from_question(question)
        
        # Build research prompt
        version_context = ""
        if software_version:
            version_context = f"\nSpecific version context: {software_version}"
        
        research_prompt = f"""{self._system_prompt}

Research the following question using ONLY official documentation.
If you cannot find authoritative information, output the discard phrase.

Question: {question}
Domain: {domain}
{version_context}

Generate a complete KB entry or the discard phrase:"""

        try:
            response = self._client.generate_content(research_prompt)
            
            if not response.text:
                logger.warning("Empty response from research agent")
                return None
            
            response_text = response.text.strip()
            
            # Check for discard phrase
            if self.DISCARD_PHRASE in response_text:
                logger.info(f"Research discarded for question: {question[:50]}...")
                return None
            
            # Parse the response into a KB entry
            return self._parse_entry(response_text, domain, question)
            
        except Exception as e:
            logger.error(f"Research failed: {e}")
            return None
    
    def _parse_entry(
        self,
        response_text: str,
        domain: str,
        original_question: str
    ) -> Optional[KBEntry]:
        """
        Parse research response into a KB entry.
        
        Args:
            response_text: The raw response text
            domain: The domain
            original_question: The original question
            
        Returns:
            Parsed KBEntry or None if parsing fails
        """
        try:
            # Try to parse as Markdown entry
            entry = KBEntry.from_markdown(response_text)
            
            # Validate and fix missing fields
            if not entry.id:
                entry.id = self._generate_entry_id(domain, original_question)
            
            if not entry.domain:
                entry.domain = domain
            
            if not entry.question:
                entry.question = original_question
            
            if not entry.software_version:
                entry.software_version = "latest"
            
            if not entry.valid_until:
                entry.valid_until = "latest"
            
            if entry.confidence == 0:
                entry.confidence = 0.95
            
            if not entry.tier:
                entry.tier = "GOLD"
            
            # Set creation time
            entry.created_at = datetime.utcnow()
            
            # Store raw content
            entry.raw_content = response_text
            
            # Validate sources are from official domains
            valid_sources = []
            for source in entry.sources:
                if any(official in source.lower() for official in self.OFFICIAL_DOMAINS):
                    valid_sources.append(source)
            entry.sources = valid_sources
            
            # Must have at least one valid source
            if not entry.sources:
                logger.warning("No valid official sources found in research output")
                return None
            
            return entry
            
        except Exception as e:
            logger.error(f"Failed to parse research entry: {e}")
            return None
    
    async def write_to_staging(
        self,
        entry: KBEntry,
        staging_path: Optional[Path] = None
    ) -> bool:
        """
        Write a research entry to the staging area.
        
        Args:
            entry: The KB entry to write
            staging_path: Optional custom staging path
            
        Returns:
            True if written successfully
        """
        # Save interception (Task 6): QA audit before staging write
        agent = ResearchAgent(
            staging_root=staging_path or Path(self.settings.kb.kb_staging_path),
            primary_research_model=ModelRef(provider="gemini", model=self.settings.google.research_model_name),
        )
        try:
            ok, msg = await agent.write_to_staging(entry, staging_path=staging_path)
            self.last_qa_audit_message = msg
            return ok
        finally:
            await agent.close()
    
    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Estimate the cost of a research operation.
        
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            
        Returns:
            Estimated cost in USD
        """
        # Gemini Pro pricing (approximate)
        # Input: $0.00025 per 1K tokens
        # Output: $0.0005 per 1K tokens
        input_cost = (input_tokens / 1000) * 0.00025
        output_cost = (output_tokens / 1000) * 0.0005
        
        return input_cost + output_cost

