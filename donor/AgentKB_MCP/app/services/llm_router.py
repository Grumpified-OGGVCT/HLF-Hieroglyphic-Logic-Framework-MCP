"""
LLM Router - Intelligent routing between LLM providers.

Supports multiple strategies:
- PRIMARY_ONLY: Use Gemini exclusively
- FALLBACK: Try Gemini, fall back to OpenRouter on failure
- OPENROUTER_ONLY: Use OpenRouter exclusively
- COST_OPTIMIZED: Route based on estimated cost
- THROUGHPUT: Route to fastest provider
- PRIVACY_FIRST: Use only ZDR endpoints
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

import structlog

from app.config import settings
from app.services.openrouter import (
    DataPolicy,
    OpenRouterClient,
    OpenRouterResponse,
    ProviderPreferences,
    RoutingStrategy,
    get_openrouter_client,
)

logger = structlog.get_logger()


class LLMRoutingStrategy(Enum):
    """Routing strategy for LLM requests."""
    PRIMARY_ONLY = "primary_only"        # Gemini only
    FALLBACK = "fallback"                # Gemini → OpenRouter
    OPENROUTER_ONLY = "openrouter_only"  # OpenRouter only
    COST_OPTIMIZED = "cost_optimized"    # Cheapest option
    THROUGHPUT = "throughput"            # Fastest option
    PRIVACY_FIRST = "privacy_first"      # ZDR endpoints only


@dataclass
class LLMResponse:
    """Unified response from any LLM provider."""
    content: str
    provider: str                    # "gemini" or "openrouter"
    model: str
    finish_reason: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_estimate: Optional[float] = None  # Estimated cost in USD
    generation_id: Optional[str] = None    # For exact cost lookup


class LLMRouter:
    """
    Routes LLM requests to the optimal provider.
    
    Supports Gemini (primary) and OpenRouter (300+ models).
    """
    
    def __init__(
        self,
        strategy: LLMRoutingStrategy = LLMRoutingStrategy.FALLBACK,
        openrouter_client: Optional[OpenRouterClient] = None,
    ):
        self.strategy = strategy
        self._openrouter = openrouter_client
        self._gemini_available = bool(settings.google_api_key)
        self._openrouter_available = bool(settings.openrouter_api_key)
    
    @property
    def openrouter(self) -> OpenRouterClient:
        """Get OpenRouter client (lazy init)."""
        if self._openrouter is None:
            self._openrouter = get_openrouter_client()
        return self._openrouter
    
    async def _call_gemini(
        self,
        messages: list[dict[str, str]],
        system: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Call Gemini API."""
        import google.generativeai as genai
        
        genai.configure(api_key=settings.google_api_key)
        
        # Build prompt
        full_prompt = ""
        if system:
            full_prompt = f"<system>\n{system}\n</system>\n\n"
        
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            if role == "user":
                full_prompt += f"User: {content}\n\n"
            elif role == "assistant":
                full_prompt += f"Assistant: {content}\n\n"
        
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config={
                "temperature": temperature,
                "max_output_tokens": max_tokens,
            },
        )
        
        response = model.generate_content(full_prompt)
        
        # Estimate tokens (rough)
        prompt_tokens = len(full_prompt) // 4
        completion_tokens = len(response.text) // 4
        
        return LLMResponse(
            content=response.text,
            provider="gemini",
            model="gemini-1.5-flash",
            finish_reason="stop",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            cost_estimate=self._estimate_gemini_cost(prompt_tokens, completion_tokens),
        )
    
    async def _call_openrouter(
        self,
        messages: list[dict[str, str]],
        system: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        model: Optional[str] = None,
        provider_prefs: Optional[ProviderPreferences] = None,
    ) -> LLMResponse:
        """Call OpenRouter API."""
        response = await self.openrouter.chat_completion(
            messages=messages,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
            model=model,
            provider=provider_prefs,
        )
        
        return LLMResponse(
            content=response.content,
            provider="openrouter",
            model=response.model,
            finish_reason=response.finish_reason,
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            total_tokens=response.usage.total_tokens,
            generation_id=response.id,
            cost_estimate=self._estimate_openrouter_cost(
                response.model,
                response.usage.prompt_tokens,
                response.usage.completion_tokens,
            ),
        )
    
    def _estimate_gemini_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Estimate Gemini cost in USD."""
        # Gemini 1.5 Flash pricing (as of late 2024)
        prompt_cost = (prompt_tokens / 1_000_000) * 0.075
        completion_cost = (completion_tokens / 1_000_000) * 0.30
        return prompt_cost + completion_cost
    
    def _estimate_openrouter_cost(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> float:
        """Estimate OpenRouter cost in USD."""
        # Approximate pricing (varies by model)
        pricing = {
            "anthropic/claude-3.5-sonnet": (3.0, 15.0),
            "anthropic/claude-3-haiku": (0.25, 1.25),
            "openai/gpt-4o": (2.50, 10.0),
            "meta-llama/llama-3.1-70b-instruct": (0.52, 0.75),
        }
        
        # Default pricing for unknown models
        prompt_rate, completion_rate = pricing.get(
            model.replace(":nitro", "").replace(":floor", ""),
            (1.0, 3.0)
        )
        
        prompt_cost = (prompt_tokens / 1_000_000) * prompt_rate
        completion_cost = (completion_tokens / 1_000_000) * completion_rate
        return prompt_cost + completion_cost
    
    async def route(
        self,
        messages: list[dict[str, str]],
        system: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        task_type: str = "kb_query",  # kb_query, research, cheap
    ) -> LLMResponse:
        """
        Route a request to the optimal provider based on strategy.
        
        Args:
            messages: Chat messages
            system: System prompt
            temperature: Sampling temperature
            max_tokens: Max tokens to generate
            task_type: Type of task (affects model selection)
        
        Returns:
            LLMResponse from the selected provider
        """
        logger.info(
            "llm_route",
            strategy=self.strategy.value,
            task_type=task_type,
            gemini_available=self._gemini_available,
            openrouter_available=self._openrouter_available,
        )
        
        # Determine routing based on strategy
        if self.strategy == LLMRoutingStrategy.PRIMARY_ONLY:
            return await self._route_primary_only(messages, system, temperature, max_tokens)
        
        elif self.strategy == LLMRoutingStrategy.FALLBACK:
            return await self._route_with_fallback(messages, system, temperature, max_tokens)
        
        elif self.strategy == LLMRoutingStrategy.OPENROUTER_ONLY:
            return await self._route_openrouter_only(messages, system, temperature, max_tokens, task_type)
        
        elif self.strategy == LLMRoutingStrategy.COST_OPTIMIZED:
            return await self._route_cost_optimized(messages, system, temperature, max_tokens)
        
        elif self.strategy == LLMRoutingStrategy.THROUGHPUT:
            return await self._route_throughput(messages, system, temperature, max_tokens)
        
        elif self.strategy == LLMRoutingStrategy.PRIVACY_FIRST:
            return await self._route_privacy_first(messages, system, temperature, max_tokens)
        
        else:
            raise ValueError(f"Unknown strategy: {self.strategy}")
    
    async def _route_primary_only(
        self,
        messages: list[dict[str, str]],
        system: Optional[str],
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        """Use Gemini only, fail if unavailable."""
        if not self._gemini_available:
            raise RuntimeError("Gemini API key not configured")
        
        return await self._call_gemini(messages, system, temperature, max_tokens)
    
    async def _route_with_fallback(
        self,
        messages: list[dict[str, str]],
        system: Optional[str],
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        """Try Gemini first, fall back to OpenRouter on failure."""
        if self._gemini_available:
            try:
                return await self._call_gemini(messages, system, temperature, max_tokens)
            except Exception as e:
                logger.warning("gemini_failed", error=str(e))
                if not self._openrouter_available:
                    raise
        
        if not self._openrouter_available:
            raise RuntimeError("No LLM providers configured")
        
        # Fall back to OpenRouter
        provider = ProviderPreferences(
            data_collection=DataPolicy.DENY,
            sort=RoutingStrategy.LATENCY,
        )
        
        return await self._call_openrouter(
            messages, system, temperature, max_tokens,
            provider_prefs=provider,
        )
    
    async def _route_openrouter_only(
        self,
        messages: list[dict[str, str]],
        system: Optional[str],
        temperature: float,
        max_tokens: int,
        task_type: str,
    ) -> LLMResponse:
        """Use OpenRouter only."""
        if not self._openrouter_available:
            raise RuntimeError("OpenRouter API key not configured")
        
        # Select model based on task
        model_map = {
            "kb_query": OpenRouterClient.MODELS["kb_primary"],
            "research": OpenRouterClient.MODELS["research"],
            "cheap": OpenRouterClient.MODELS["research_cheap"],
        }
        model = model_map.get(task_type, OpenRouterClient.MODELS["kb_primary"])
        
        provider = ProviderPreferences(
            data_collection=DataPolicy.DENY,
        )
        
        return await self._call_openrouter(
            messages, system, temperature, max_tokens,
            model=model,
            provider_prefs=provider,
        )
    
    async def _route_cost_optimized(
        self,
        messages: list[dict[str, str]],
        system: Optional[str],
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        """Route to cheapest option."""
        # Gemini Flash is typically cheaper for most workloads
        if self._gemini_available:
            try:
                return await self._call_gemini(messages, system, temperature, max_tokens)
            except Exception as e:
                logger.warning("gemini_failed", error=str(e))
        
        if not self._openrouter_available:
            raise RuntimeError("No LLM providers configured")
        
        # Use floor pricing on OpenRouter
        provider = ProviderPreferences(
            sort=RoutingStrategy.PRICE,
            data_collection=DataPolicy.DENY,
        )
        
        return await self._call_openrouter(
            messages, system, temperature, max_tokens,
            model=OpenRouterClient.MODELS["research_cheap"],
            provider_prefs=provider,
        )
    
    async def _route_throughput(
        self,
        messages: list[dict[str, str]],
        system: Optional[str],
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        """Route to fastest option."""
        if not self._openrouter_available:
            # Fall back to Gemini
            if not self._gemini_available:
                raise RuntimeError("No LLM providers configured")
            return await self._call_gemini(messages, system, temperature, max_tokens)
        
        # Use throughput-optimized routing on OpenRouter
        provider = ProviderPreferences(
            sort=RoutingStrategy.THROUGHPUT,
            data_collection=DataPolicy.DENY,
        )
        
        return await self._call_openrouter(
            messages, system, temperature, max_tokens,
            model=OpenRouterClient.MODELS["research_fast"],
            provider_prefs=provider,
        )
    
    async def _route_privacy_first(
        self,
        messages: list[dict[str, str]],
        system: Optional[str],
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        """Route to ZDR endpoints only."""
        if not self._openrouter_available:
            raise RuntimeError("OpenRouter required for ZDR enforcement")
        
        provider = ProviderPreferences(
            zdr=True,
            data_collection=DataPolicy.DENY,
            only=["anthropic"],  # Anthropic has strong privacy guarantees
        )
        
        return await self._call_openrouter(
            messages, system, temperature, max_tokens,
            provider_prefs=provider,
        )


# Factory function
def create_router(
    strategy: Optional[str] = None,
) -> LLMRouter:
    """
    Create an LLM router with the specified strategy.
    
    Args:
        strategy: Routing strategy name (from config or explicit)
    
    Returns:
        Configured LLMRouter instance
    """
    strategy_str = strategy or getattr(settings, "llm_routing_strategy", "fallback")
    
    try:
        routing_strategy = LLMRoutingStrategy(strategy_str)
    except ValueError:
        logger.warning(f"Unknown strategy '{strategy_str}', using fallback")
        routing_strategy = LLMRoutingStrategy.FALLBACK
    
    return LLMRouter(strategy=routing_strategy)

