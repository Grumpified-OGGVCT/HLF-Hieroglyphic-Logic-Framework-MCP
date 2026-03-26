"""OpenRouter Cloud API client — production-hardened, OpenAI-compatible.

Provides the same resilience primitives as the Ollama client:
  CircuitBreaker, RetryPolicy, ResponseValidator, audit trail

Uses the OpenAI-compatible API surface at https://openrouter.ai/api/v1
with model IDs in "provider/model-name" format.

All API keys are resolved from environment variables via model_config —
never hardcoded or logged.

Usage:
    from hlf_mcp.hlf.openrouter_client import OpenRouterClient
    from hlf_mcp.hlf.model_config import load_model_config, get_api_key

    cfg = load_model_config()
    key = get_api_key(cfg, "openrouter")
    client = OpenRouterClient(api_key=key, config=cfg.providers["openrouter"])
    result = await client.chat_completion(
        model="deepseek/deepseek-r1",
        messages=[{"role": "user", "content": "Hello"}],
    )
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from http import HTTPStatus
from typing import Any, AsyncIterator
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

# We use stdlib urllib for the sync path and try httpx for async;
# fall back to urllib if httpx is unavailable.
try:
    import httpx

    _HAS_HTTPX = True
except ModuleNotFoundError:
    _HAS_HTTPX = False

# ── dataclasses ──────────────────────────────────────────────────────────────


@dataclass(slots=True)
class ChatResult:
    """Result from a chat completion call."""

    content: str
    model_used: str
    model_requested: str
    finish_reason: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_s: float
    streamed: bool
    cost: float | None  # OpenRouter returns cost in usage
    raw: dict[str, Any] = field(default_factory=dict)
    thinking: str = ""  # Reasoning trace if model supports it
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    audit_trail: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class ModelInfo:
    """A model entry from OpenRouter's /models endpoint."""

    id: str
    name: str
    context_length: int
    pricing_prompt: float  # $/token
    pricing_completion: float  # $/token
    top_provider: str
    architecture: str
    is_free: bool
    raw: dict[str, Any] = field(default_factory=dict)
    # Deprecation signal: null/None = active, date string = deprecated/expiring
    expiration_date: str | None = None
    # Permanent identifier — never changes even if display name is updated
    canonical_slug: str = ""
    # Supported API parameters (e.g. "tools", "reasoning", "temperature")
    supported_parameters: list[str] = field(default_factory=list)
    # Input/output modality info from architecture object
    input_modalities: list[str] = field(default_factory=list)
    output_modalities: list[str] = field(default_factory=list)


# ── circuit breaker ──────────────────────────────────────────────────────────


class CircuitBreaker:
    """Per-model circuit breaker.

    CLOSED -> OPEN (after ``threshold`` consecutive failures)
    OPEN -> HALF-OPEN (after ``recovery_s`` seconds — allows one probe)
    HALF-OPEN -> CLOSED (on success) or OPEN (on failure)
    """

    _instances: dict[str, CircuitBreaker] = {}

    def __init__(self, model: str, threshold: int = 4, recovery_s: float = 300.0):
        self._model = model
        self._threshold = threshold
        self._recovery_s = recovery_s
        self._failures = 0
        self._opened_at: float | None = None

    @classmethod
    def get(cls, model: str, threshold: int = 4, recovery_s: float = 300.0) -> CircuitBreaker:
        if model not in cls._instances:
            cls._instances[model] = cls(model, threshold, recovery_s)
        return cls._instances[model]

    @classmethod
    def reset_all(cls) -> None:
        cls._instances.clear()

    @property
    def is_open(self) -> bool:
        if self._opened_at is None:
            return False
        elapsed = time.monotonic() - self._opened_at
        if elapsed >= self._recovery_s:
            logger.info("Circuit %s entering HALF-OPEN after %.0fs", self._model, elapsed)
            self._opened_at = None
            self._failures = self._threshold - 1
            return False
        return True

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self._threshold and self._opened_at is None:
            self._opened_at = time.monotonic()
            logger.warning(
                "Circuit OPENED for %s after %d consecutive failures",
                self._model, self._failures,
            )


# ── retry policy ─────────────────────────────────────────────────────────────

_RETRYABLE_STATUS = frozenset({
    HTTPStatus.TOO_MANY_REQUESTS,
    HTTPStatus.INTERNAL_SERVER_ERROR,
    HTTPStatus.BAD_GATEWAY,
    HTTPStatus.SERVICE_UNAVAILABLE,
    HTTPStatus.GATEWAY_TIMEOUT,
})


def _backoff_delay(attempt: int, base: float = 2.0, cap: float = 90.0) -> float:
    """Decorrelated jitter: sleep = min(cap, base * 2^attempt * random)."""
    import random
    delay = min(cap, base * (2 ** attempt) * random.uniform(0.5, 1.0))
    return delay


# ── client ───────────────────────────────────────────────────────────────────


class OpenRouterClient:
    """Async OpenRouter API client with resilience primitives.

    Parameters
    ----------
    api_key : str | None
        The OpenRouter API key. If None, calls will fail with 401.
    base_url : str
        API base URL (default: https://openrouter.ai/api/v1).
    app_name : str
        Application name for OpenRouter tracking headers.
    app_url : str
        Application URL for OpenRouter tracking headers.
    timeout_s : float
        Total request timeout in seconds.
    max_retries : int
        Maximum retry attempts per request.
    circuit_threshold : int
        Consecutive failures before circuit opens.
    circuit_recovery_s : float
        Seconds before a tripped circuit enters half-open.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://openrouter.ai/api/v1",
        app_name: str = "HLF-MCP",
        app_url: str = "",
        timeout_s: float = 300.0,
        max_retries: int = 3,
        circuit_threshold: int = 4,
        circuit_recovery_s: float = 300.0,
    ):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._app_name = app_name
        self._app_url = app_url
        self._timeout_s = timeout_s
        self._max_retries = max_retries
        self._circuit_threshold = circuit_threshold
        self._circuit_recovery_s = circuit_recovery_s
        self._client: httpx.AsyncClient | None = None

    @classmethod
    def from_provider_config(
        cls,
        provider_config: Any,  # ProviderConfig from model_config
        api_key: str | None = None,
    ) -> OpenRouterClient:
        """Build from a ProviderConfig dataclass."""
        return cls(
            api_key=api_key,
            base_url=provider_config.base_url,
            app_name=provider_config.app_name,
            app_url=provider_config.app_url,
            timeout_s=provider_config.timeout_total_s,
            max_retries=provider_config.max_retries,
            circuit_threshold=provider_config.circuit_breaker_threshold,
            circuit_recovery_s=provider_config.circuit_breaker_recovery_s,
        )

    def _headers(self) -> dict[str, str]:
        h: dict[str, str] = {
            "Content-Type": "application/json",
        }
        if self._api_key:
            h["Authorization"] = f"Bearer {self._api_key}"
        if self._app_name:
            h["X-Title"] = self._app_name
        if self._app_url:
            h["HTTP-Referer"] = self._app_url
        return h

    async def _ensure_client(self) -> httpx.AsyncClient:
        if not _HAS_HTTPX:
            raise RuntimeError(
                "httpx is required for async OpenRouter client. "
                "Install with: pip install httpx"
            )
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout_s),
                headers=self._headers(),
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    # ── core request ─────────────────────────────────────────────────────

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        model: str = "",
    ) -> dict[str, Any]:
        """Make an HTTP request with retry + circuit breaker.

        Returns parsed JSON response body.
        """
        client = await self._ensure_client()
        url = f"{self._base_url}{path}"
        breaker = CircuitBreaker.get(
            model or path,
            threshold=self._circuit_threshold,
            recovery_s=self._circuit_recovery_s,
        )

        last_error: Exception | None = None
        audit: list[dict[str, Any]] = []

        for attempt in range(self._max_retries + 1):
            if breaker.is_open:
                logger.warning("Circuit open for %s — skipping attempt %d", model or path, attempt)
                audit.append({
                    "attempt": attempt,
                    "status": "circuit_open",
                    "model": model,
                })
                break

            t0 = time.monotonic()
            try:
                if method.upper() == "GET":
                    resp = await client.get(url)
                else:
                    resp = await client.post(url, json=json_body)

                elapsed = time.monotonic() - t0
                audit.append({
                    "attempt": attempt,
                    "status_code": resp.status_code,
                    "latency_s": round(elapsed, 3),
                    "model": model,
                })

                if resp.status_code == HTTPStatus.OK:
                    breaker.record_success()
                    data = resp.json()
                    data["_audit_trail"] = audit
                    return data

                if resp.status_code in _RETRYABLE_STATUS:
                    breaker.record_failure()
                    if attempt < self._max_retries:
                        delay = _backoff_delay(attempt)
                        logger.info(
                            "Retryable %d for %s — backing off %.1fs",
                            resp.status_code, model, delay,
                        )
                        await asyncio.sleep(delay)
                        continue

                # Non-retryable error
                breaker.record_failure()
                error_body = resp.text[:500]
                logger.error(
                    "OpenRouter %s %s returned %d: %s",
                    method, path, resp.status_code, error_body,
                )
                raise OpenRouterAPIError(
                    status_code=resp.status_code,
                    message=error_body,
                    model=model,
                    audit_trail=audit,
                )

            except httpx.TimeoutException as exc:
                elapsed = time.monotonic() - t0
                breaker.record_failure()
                last_error = exc
                audit.append({
                    "attempt": attempt,
                    "status": "timeout",
                    "latency_s": round(elapsed, 3),
                    "model": model,
                })
                if attempt < self._max_retries:
                    delay = _backoff_delay(attempt)
                    logger.info("Timeout for %s — backing off %.1fs", model, delay)
                    await asyncio.sleep(delay)
                    continue

            except httpx.ConnectError as exc:
                elapsed = time.monotonic() - t0
                breaker.record_failure()
                last_error = exc
                audit.append({
                    "attempt": attempt,
                    "status": "connect_error",
                    "latency_s": round(elapsed, 3),
                    "model": model,
                })
                if attempt < self._max_retries:
                    delay = _backoff_delay(attempt)
                    await asyncio.sleep(delay)
                    continue

        # All retries exhausted
        raise OpenRouterAPIError(
            status_code=0,
            message=f"All {self._max_retries + 1} attempts failed: {last_error}",
            model=model,
            audit_trail=audit,
        )

    # ── streaming request ────────────────────────────────────────────────

    async def _stream_request(
        self,
        path: str,
        json_body: dict[str, Any],
        model: str = "",
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream SSE chunks from an OpenRouter endpoint.

        Yields parsed JSON objects from each ``data:`` line.
        """
        client = await self._ensure_client()
        url = f"{self._base_url}{path}"
        breaker = CircuitBreaker.get(
            model or path,
            threshold=self._circuit_threshold,
            recovery_s=self._circuit_recovery_s,
        )

        if breaker.is_open:
            raise OpenRouterAPIError(
                status_code=0,
                message=f"Circuit open for {model}",
                model=model,
            )

        try:
            async with client.stream("POST", url, json=json_body) as resp:
                if resp.status_code != HTTPStatus.OK:
                    body = await resp.aread()
                    breaker.record_failure()
                    raise OpenRouterAPIError(
                        status_code=resp.status_code,
                        message=body.decode("utf-8", errors="replace")[:500],
                        model=model,
                    )

                breaker.record_success()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:].strip()
                    if payload == "[DONE]":
                        return
                    try:
                        yield json.loads(payload)
                    except json.JSONDecodeError:
                        logger.warning("Bad SSE chunk: %s", payload[:100])

        except httpx.TimeoutException:
            breaker.record_failure()
            raise OpenRouterAPIError(
                status_code=0,
                message=f"Stream timeout for {model}",
                model=model,
            )

    # ── public API ───────────────────────────────────────────────────────

    async def chat_completion(
        self,
        model: str,
        messages: list[dict[str, Any]],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        stream: bool = False,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        response_format: dict[str, Any] | None = None,
        plugins: list[dict[str, Any]] | None = None,
        route: str | None = None,
        models: list[str] | None = None,
        provider: dict[str, Any] | None = None,
    ) -> ChatResult:
        """Execute a chat completion against OpenRouter.

        Parameters
        ----------
        model : str
            OpenRouter model ID (e.g. "deepseek/deepseek-r1").
        messages : list[dict]
            OpenAI-format message list.
        temperature : float | None
            Sampling temperature.
        max_tokens : int | None
            Maximum completion tokens.
        stream : bool
            Whether to use SSE streaming.
        tools : list | None
            Tool definitions for function calling.
        tool_choice : str | dict | None
            Tool choice strategy.
        response_format : dict | None
            Structured output format (json_object or json_schema).
        plugins : list | None
            OpenRouter plugins (web, file-parser, etc.).
        route : str | None
            "fallback" to enable model routing across ``models`` list.
        models : list[str] | None
            Multiple models for fallback routing.
        provider : dict | None
            Provider routing preferences.
        """
        t0 = time.monotonic()

        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
        }
        if temperature is not None:
            body["temperature"] = temperature
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        if stream:
            body["stream"] = True
        if tools:
            body["tools"] = tools
        if tool_choice is not None:
            body["tool_choice"] = tool_choice
        if response_format:
            body["response_format"] = response_format
        if plugins:
            body["plugins"] = plugins
        if route:
            body["route"] = route
        if models:
            body["models"] = models
        if provider:
            body["provider"] = provider

        if stream:
            return await self._handle_stream(model, body, t0)
        else:
            data = await self._request("POST", "/chat/completions", json_body=body, model=model)
            return self._parse_completion(model, data, t0, streamed=False)

    async def _handle_stream(
        self, model: str, body: dict[str, Any], t0: float
    ) -> ChatResult:
        """Accumulate streaming chunks into a ChatResult."""
        chunks: list[str] = []
        thinking_chunks: list[str] = []
        tool_call_chunks: list[dict[str, Any]] = []
        finish_reason = ""
        raw_model = model
        usage: dict[str, int] = {}

        async for chunk in self._stream_request("/chat/completions", body, model):
            choices = chunk.get("choices", [])
            if not choices:
                # Usage chunk at end of stream
                if "usage" in chunk:
                    usage = chunk["usage"]
                continue

            delta = choices[0].get("delta", {})

            # Content
            if "content" in delta and delta["content"]:
                chunks.append(delta["content"])

            # Reasoning/thinking
            if "reasoning" in delta and delta["reasoning"]:
                thinking_chunks.append(delta["reasoning"])

            # Tool calls
            if "tool_calls" in delta:
                tool_call_chunks.extend(delta["tool_calls"])

            # Finish reason
            fr = choices[0].get("finish_reason")
            if fr:
                finish_reason = fr

            # Model actually used
            if "model" in chunk:
                raw_model = chunk["model"]

        latency = time.monotonic() - t0
        return ChatResult(
            content="".join(chunks),
            model_used=raw_model,
            model_requested=model,
            finish_reason=finish_reason,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            latency_s=round(latency, 3),
            streamed=True,
            cost=None,  # Cost not available in stream
            thinking="".join(thinking_chunks),
            tool_calls=tool_call_chunks,
        )

    def _parse_completion(
        self, model: str, data: dict[str, Any], t0: float, *, streamed: bool
    ) -> ChatResult:
        """Parse a non-streamed chat completion response."""
        latency = time.monotonic() - t0
        audit = data.pop("_audit_trail", [])

        choices = data.get("choices", [])
        message = choices[0].get("message", {}) if choices else {}
        usage = data.get("usage", {})

        # Extract tool calls
        tool_calls = message.get("tool_calls", [])

        # Extract thinking/reasoning
        thinking = ""
        if "reasoning" in message:
            thinking = str(message["reasoning"])

        # OpenRouter can include cost in usage
        cost = None
        if "cost" in usage:
            cost = float(usage["cost"])

        # Response model verification — log if model routed differently
        actual_model = str(data.get("model", model))
        if actual_model != model:
            logger.info(
                "Model mismatch: requested=%s, actual=%s — "
                "response was routed to a different model",
                model, actual_model,
            )

        return ChatResult(
            content=str(message.get("content", "")),
            model_used=actual_model,
            model_requested=model,
            finish_reason=str(choices[0].get("finish_reason", "")) if choices else "",
            prompt_tokens=int(usage.get("prompt_tokens", 0)),
            completion_tokens=int(usage.get("completion_tokens", 0)),
            total_tokens=int(usage.get("total_tokens", 0)),
            latency_s=round(latency, 3),
            streamed=streamed,
            cost=cost,
            raw=data,
            thinking=thinking,
            tool_calls=tool_calls,
            audit_trail=audit,
        )

    # ── model discovery ──────────────────────────────────────────────────

    async def list_models(
        self,
        *,
        include_free: bool = True,
        family_filter: list[str] | None = None,
        max_models: int = 200,
    ) -> list[ModelInfo]:
        """Discover available models from the OpenRouter /models endpoint.

        Parameters
        ----------
        include_free : bool
            Whether to include free-tier models.
        family_filter : list[str] | None
            If provided, only return models whose architecture matches.
        max_models : int
            Maximum number of models to return (0 = unlimited).
        """
        data = await self._request("GET", "/models")
        raw_models = data.get("data", [])

        result: list[ModelInfo] = []
        for m in raw_models:
            pricing = m.get("pricing", {})
            prompt_price = float(pricing.get("prompt", "0") or "0")
            completion_price = float(pricing.get("completion", "0") or "0")
            is_free = prompt_price == 0 and completion_price == 0

            if not include_free and is_free:
                continue

            arch = m.get("architecture", {})
            arch_name = str(arch.get("modality", ""))

            if family_filter and arch_name not in family_filter:
                id_parts = str(m.get("id", "")).split("/")
                provider_name = id_parts[0] if id_parts else ""
                if provider_name not in family_filter:
                    continue

            result.append(ModelInfo(
                id=str(m.get("id", "")),
                name=str(m.get("name", "")),
                context_length=int(m.get("context_length", 0)),
                pricing_prompt=prompt_price,
                pricing_completion=completion_price,
                top_provider=str(m.get("top_provider", {}).get("max_completion_tokens", "")),
                architecture=arch_name,
                is_free=is_free,
                raw=m,
                expiration_date=m.get("expiration_date"),  # None = active
                canonical_slug=str(m.get("canonical_slug", "")),
                supported_parameters=list(m.get("supported_parameters", []) or []),
                input_modalities=list(arch.get("input_modalities", []) or []),
                output_modalities=list(arch.get("output_modalities", []) or []),
            ))

            if max_models and len(result) >= max_models:
                break

        return result

    # ── convenience ──────────────────────────────────────────────────────

    @staticmethod
    def verify_response_model(
        result: ChatResult,
        *,
        strict: bool = False,
    ) -> tuple[bool, str]:
        """Verify that the response model matches the requested model.

        Parameters
        ----------
        result : ChatResult
            The completion result to verify.
        strict : bool
            If True, any mismatch is treated as a failure.
            If False, only auto-router mismatches are flagged.

        Returns
        -------
        tuple[bool, str]
            (is_valid, reason). ``is_valid`` is True if the response is
            acceptable for governed use.
        """
        requested = result.model_requested
        actual = result.model_used

        if actual == requested:
            return True, "exact match"

        # Auto-router always produces mismatches — always flag
        if requested in ("openrouter/auto", "openrouter/free"):
            return False, (
                f"Auto-router response: requested={requested}, "
                f"actual={actual} — reject for governed paths"
            )

        if strict:
            return False, (
                f"Model mismatch (strict): requested={requested}, actual={actual}"
            )

        # Non-strict: log but allow (provider may have routed to equivalent)
        return True, f"model routed: requested={requested}, actual={actual}"

    async def simple_complete(
        self,
        model: str,
        prompt: str,
        *,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> ChatResult:
        """Simple prompt→completion shorthand."""
        messages: list[dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return await self.chat_completion(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )


# ── error class ──────────────────────────────────────────────────────────────


class OpenRouterAPIError(Exception):
    """Raised when an OpenRouter API call fails."""

    def __init__(
        self,
        status_code: int,
        message: str,
        model: str = "",
        audit_trail: list[dict[str, Any]] | None = None,
    ):
        self.status_code = status_code
        self.model = model
        self.audit_trail = audit_trail or []
        super().__init__(f"OpenRouter error {status_code} for {model}: {message}")
