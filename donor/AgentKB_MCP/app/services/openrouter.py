"""
OpenRouter Client - Multi-provider LLM access via OpenRouter.

Provides access to 300+ models with:
- Intelligent routing (price, throughput, latency)
- Automatic fallbacks
- Privacy controls (ZDR, data collection)
- Exact cost tracking
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, AsyncGenerator, Optional

import httpx
import structlog

from app.config import settings

logger = structlog.get_logger()


class RoutingStrategy(Enum):
    """LLM routing strategies."""
    PRICE = "price"           # Cheapest provider
    THROUGHPUT = "throughput" # Fastest tokens/sec
    LATENCY = "latency"       # Lowest time-to-first-token


class DataPolicy(Enum):
    """Data collection policies."""
    ALLOW = "allow"   # Allow providers that may store/train
    DENY = "deny"     # Only use privacy-respecting providers


@dataclass
class ProviderPreferences:
    """OpenRouter provider routing preferences."""
    
    order: Optional[list[str]] = None       # Provider order: ["anthropic", "openai"]
    only: Optional[list[str]] = None        # Restrict to these providers
    ignore: Optional[list[str]] = None      # Skip these providers
    allow_fallbacks: bool = True            # Allow fallback to other providers
    require_parameters: bool = False        # Only use providers supporting all params
    data_collection: DataPolicy = DataPolicy.DENY  # Privacy default
    zdr: bool = False                       # Zero Data Retention
    quantizations: Optional[list[str]] = None  # ["fp8", "fp16"]
    sort: Optional[RoutingStrategy] = None  # Routing strategy
    max_price_prompt: Optional[float] = None    # Max $/M prompt tokens
    max_price_completion: Optional[float] = None  # Max $/M completion tokens
    
    def to_dict(self) -> dict:
        """Convert to OpenRouter provider object."""
        result = {}
        
        if self.order:
            result["order"] = self.order
        if self.only:
            result["only"] = self.only
        if self.ignore:
            result["ignore"] = self.ignore
        if not self.allow_fallbacks:
            result["allow_fallbacks"] = False
        if self.require_parameters:
            result["require_parameters"] = True
        if self.data_collection == DataPolicy.DENY:
            result["data_collection"] = "deny"
        if self.zdr:
            result["zdr"] = True
        if self.quantizations:
            result["quantizations"] = self.quantizations
        if self.sort:
            result["sort"] = self.sort.value
        if self.max_price_prompt or self.max_price_completion:
            result["max_price"] = {}
            if self.max_price_prompt:
                result["max_price"]["prompt"] = self.max_price_prompt
            if self.max_price_completion:
                result["max_price"]["completion"] = self.max_price_completion
        
        return result


@dataclass
class OpenRouterUsage:
    """Token usage from OpenRouter response."""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass
class GenerationStats:
    """Detailed generation statistics from OpenRouter."""
    id: str
    model: str
    provider: str
    native_prompt_tokens: int
    native_completion_tokens: int
    cost: float
    latency_ms: int
    created_at: datetime


@dataclass
class OpenRouterResponse:
    """Response from OpenRouter chat completion."""
    id: str
    model: str
    content: str
    finish_reason: str
    native_finish_reason: Optional[str]
    usage: OpenRouterUsage
    tool_calls: Optional[list[dict]] = None


class OpenRouterClient:
    """
    Client for OpenRouter API.
    
    Features:
    - OpenAI-compatible chat completions
    - Provider routing with preferences
    - Streaming support
    - Tool calling
    - Exact cost tracking via generation stats
    """
    
    BASE_URL = "https://openrouter.ai/api/v1"
    
    # Recommended models for different tasks
    MODELS = {
        "kb_primary": "anthropic/claude-3.5-sonnet",
        "kb_fast": "anthropic/claude-3-haiku",
        "research": "anthropic/claude-3.5-sonnet",
        "research_fast": "meta-llama/llama-3.1-70b-instruct:nitro",
        "research_cheap": "meta-llama/llama-3.1-70b-instruct:floor",
        "embeddings_fallback": "openai/gpt-4o",  # For non-embedding tasks
    }
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        default_model: Optional[str] = None,
        app_name: str = "Verified Developer KB Pro",
        app_url: Optional[str] = None,
    ):
        self.api_key = api_key or settings.openrouter_api_key
        self.default_model = default_model or self.MODELS["kb_primary"]
        self.app_name = app_name
        self.app_url = app_url
        
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.BASE_URL,
                timeout=120.0,
                headers=self._build_headers(),
            )
        return self._client
    
    def _build_headers(self) -> dict[str, str]:
        """Build request headers with auth and attribution."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-Title": self.app_name,
        }
        if self.app_url:
            headers["HTTP-Referer"] = self.app_url
        return headers
    
    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
    
    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        system: Optional[str] = None,
        tools: Optional[list[dict]] = None,
        tool_choice: Optional[str | dict] = None,
        response_format: Optional[dict] = None,
        provider: Optional[ProviderPreferences] = None,
        stop: Optional[list[str]] = None,
    ) -> OpenRouterResponse:
        """
        Send a chat completion request.
        
        Args:
            messages: List of message dicts with role/content
            model: Model ID (e.g., "anthropic/claude-3.5-sonnet")
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate
            system: System prompt (prepended to messages)
            tools: Tool definitions for function calling
            tool_choice: Tool choice strategy
            response_format: {"type": "json_object"} for JSON mode
            provider: Provider routing preferences
            stop: Stop sequences
        
        Returns:
            OpenRouterResponse with content and usage
        """
        client = await self._get_client()
        
        # Build messages with optional system prompt
        final_messages = []
        if system:
            final_messages.append({"role": "system", "content": system})
        final_messages.extend(messages)
        
        # Build request body
        body: dict[str, Any] = {
            "model": model or self.default_model,
            "messages": final_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        
        if tools:
            body["tools"] = tools
        if tool_choice:
            body["tool_choice"] = tool_choice
        if response_format:
            body["response_format"] = response_format
        if stop:
            body["stop"] = stop
        if provider:
            body["provider"] = provider.to_dict()
        
        logger.debug(
            "openrouter_request",
            model=body["model"],
            messages=len(final_messages),
            provider=provider.to_dict() if provider else None,
        )
        
        response = await client.post("/chat/completions", json=body)
        response.raise_for_status()
        
        data = response.json()
        
        choice = data["choices"][0]
        message = choice.get("message", choice.get("delta", {}))
        
        result = OpenRouterResponse(
            id=data["id"],
            model=data["model"],
            content=message.get("content", ""),
            finish_reason=choice.get("finish_reason", "unknown"),
            native_finish_reason=choice.get("native_finish_reason"),
            usage=OpenRouterUsage(
                prompt_tokens=data.get("usage", {}).get("prompt_tokens", 0),
                completion_tokens=data.get("usage", {}).get("completion_tokens", 0),
                total_tokens=data.get("usage", {}).get("total_tokens", 0),
            ),
            tool_calls=message.get("tool_calls"),
        )
        
        logger.info(
            "openrouter_response",
            model=result.model,
            finish_reason=result.finish_reason,
            tokens=result.usage.total_tokens,
        )
        
        return result
    
    async def chat_completion_stream(
        self,
        messages: list[dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        system: Optional[str] = None,
        provider: Optional[ProviderPreferences] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream a chat completion response.
        
        Yields text deltas as they arrive.
        """
        client = await self._get_client()
        
        final_messages = []
        if system:
            final_messages.append({"role": "system", "content": system})
        final_messages.extend(messages)
        
        body = {
            "model": model or self.default_model,
            "messages": final_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        
        if provider:
            body["provider"] = provider.to_dict()
        
        async with client.stream("POST", "/chat/completions", json=body) as response:
            response.raise_for_status()
            
            async for line in response.aiter_lines():
                if not line or line.startswith(":"):
                    continue
                
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    
                    try:
                        data = json.loads(data_str)
                        delta = data["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        continue
    
    async def get_generation_stats(self, generation_id: str) -> GenerationStats:
        """
        Get detailed generation statistics.
        
        This returns the EXACT cost and native token counts,
        as opposed to the normalized counts in the completion response.
        
        Args:
            generation_id: The ID from a chat completion response
        
        Returns:
            GenerationStats with exact cost and native tokens
        """
        client = await self._get_client()
        
        response = await client.get(f"/generation?id={generation_id}")
        response.raise_for_status()
        
        data = response.json()
        
        return GenerationStats(
            id=data["id"],
            model=data.get("model", "unknown"),
            provider=data.get("provider", "unknown"),
            native_prompt_tokens=data.get("native_tokens", {}).get("prompt", 0),
            native_completion_tokens=data.get("native_tokens", {}).get("completion", 0),
            cost=data.get("total_cost", 0.0),
            latency_ms=data.get("latency", 0),
            created_at=datetime.fromisoformat(data.get("created_at", "2024-01-01T00:00:00Z").replace("Z", "+00:00")),
        )
    
    async def list_models(self) -> list[dict]:
        """
        List available models.
        
        Returns list of model info dicts.
        """
        client = await self._get_client()
        
        response = await client.get("/models")
        response.raise_for_status()
        
        data = response.json()
        return data.get("data", [])
    
    # Convenience methods for common use cases
    
    async def kb_query(
        self,
        question: str,
        kb_context: str,
        system_prompt: str,
    ) -> OpenRouterResponse:
        """
        Execute a KB query with privacy-first defaults.
        
        Uses:
        - Claude 3.5 Sonnet for best accuracy
        - Zero data retention
        - No data collection for training
        """
        provider = ProviderPreferences(
            data_collection=DataPolicy.DENY,
            zdr=True,
            sort=RoutingStrategy.LATENCY,  # Fast response for KB
        )
        
        messages = [
            {"role": "user", "content": f"<context>\n{kb_context}\n</context>\n\n{question}"}
        ]
        
        return await self.chat_completion(
            messages=messages,
            model=self.MODELS["kb_primary"],
            system=system_prompt,
            temperature=0.0,
            provider=provider,
        )
    
    async def research_query(
        self,
        question: str,
        research_context: str,
        system_prompt: str,
    ) -> OpenRouterResponse:
        """
        Execute a research query optimized for throughput.
        
        Uses:
        - Throughput-optimized routing
        - Cost caps
        - Privacy protection
        """
        provider = ProviderPreferences(
            data_collection=DataPolicy.DENY,
            sort=RoutingStrategy.THROUGHPUT,
            max_price_prompt=2.0,
            max_price_completion=10.0,
        )
        
        messages = [
            {"role": "user", "content": f"<research_context>\n{research_context}\n</research_context>\n\n{question}"}
        ]
        
        return await self.chat_completion(
            messages=messages,
            model=self.MODELS["research"],
            system=system_prompt,
            temperature=0.1,
            max_tokens=8192,
            provider=provider,
        )
    
    async def cheap_query(
        self,
        prompt: str,
        system: Optional[str] = None,
    ) -> OpenRouterResponse:
        """
        Execute a cheap query for non-critical tasks.
        
        Uses floor pricing (cheapest available).
        """
        provider = ProviderPreferences(
            sort=RoutingStrategy.PRICE,
            data_collection=DataPolicy.DENY,
        )
        
        return await self.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            model=self.MODELS["research_cheap"],
            system=system,
            provider=provider,
        )


# Singleton instance
_openrouter_client: Optional[OpenRouterClient] = None


def get_openrouter_client() -> OpenRouterClient:
    """Get or create the OpenRouter client singleton."""
    global _openrouter_client
    if _openrouter_client is None:
        _openrouter_client = OpenRouterClient()
    return _openrouter_client

