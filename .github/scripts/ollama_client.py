"""
Ollama Cloud API client — production-hardened, zero-compromise resilience.

Architecture:
  ModelChain          — tiered fallback sequences per task type
  CircuitBreaker      — per-model failure tracking; opens circuit after threshold
  StreamingBuffer     — chunk-by-chunk streaming with reassembly + partial-JSON guard
  RetryPolicy         — exponential backoff with full jitter (decorrelated AWS-style)
  ConnectionMonitor   — rolling latency + success-rate ledger per model
  ResponseValidator   — completeness, truncation, error-body detection
  FallbackOrchestrator— drives the full chain with complete audit trail

Model registry (exact Ollama names from ollama.com/library, March 2025):

  nemotron-3-super    NVIDIA | 120B total params, ~12B active per forward pass
                      (LatentMoE sparse activation — Mamba+Transformer hybrid)
                      Best: agentic reasoning, long-horizon planning, tool use
                      https://ollama.com/library/nemotron-3-super

  kimi-k2:1t-cloud    Moonshot AI | 1T MoE (32B active), 256K ctx
                      Best: large-context codebase, autonomous agents
                      https://ollama.com/library/kimi-k2

  qwen3.5:cloud       Alibaba | 397B cloud, Text+Image, 256K ctx
                      Best: structured output, multimodal, universal fallback
                      https://ollama.com/library/qwen3.5

  devstral:24b        Mistral x AllHands | 24B, 128K ctx, SWE-Bench 46.8%
                      Best: multi-file coding, SWE tasks, code review
                      https://ollama.com/library/devstral

  deepseek-r1:14b     DeepSeek | 14B, 128K ctx, chain-of-thought + thinking traces
                      Best: ethical reasoning, adversarial analysis, logic chains

Pre-defined tiered chains — each tier is independently capable:

  REASONING_CHAIN   nemotron-3-super -> kimi-k2:1t-cloud -> qwen3.5:cloud -> deepseek-r1:14b
  CODING_CHAIN      devstral:24b     -> nemotron-3-super  -> qwen3.5:cloud -> deepseek-r1:14b
  ANALYSIS_CHAIN    qwen3.5:cloud    -> nemotron-3-super  -> devstral:24b  -> deepseek-r1:14b
  ETHICS_CHAIN      deepseek-r1:14b  -> nemotron-3-super  -> qwen3.5:cloud -> devstral:24b
  UNIVERSAL_CHAIN   nemotron-3-super -> qwen3.5:cloud     -> devstral:24b  -> deepseek-r1:14b

Usage:
    from ollama_client import FallbackOrchestrator, REASONING_CHAIN
    orch = FallbackOrchestrator(chain=REASONING_CHAIN)
    result = orch.complete(system="...", prompt="...")
    print(result.content)

    # CLI with named chain:
    python .github/scripts/ollama_client.py --chain reasoning \
        --system "You are HLF spec sentinel." --prompt "..." --output out.json

    # CLI with explicit model + fallback:
    python .github/scripts/ollama_client.py \
        --model nemotron-3-super --fallback-model qwen3.5:cloud \
        --system "..." --prompt "..."
"""

from __future__ import annotations

import argparse
import dataclasses
import http.client
import io
import json
import logging
import os
import random
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import deque
from typing import Any

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] ollama — %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stderr,
)
log = logging.getLogger("ollama_client")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
OLLAMA_CLOUD_BASE      = "https://ollama.com/api"
CONNECT_TIMEOUT        = 20      # seconds to establish TCP
CHUNK_IDLE_TIMEOUT     = 60      # seconds between stream chunks before abort
TOTAL_CALL_TIMEOUT     = 600     # hard ceiling per individual model call
MAX_RETRIES_PER_MODEL  = 3       # attempts before advancing to next tier
BASE_BACKOFF_SEC       = 2.0
MAX_BACKOFF_SEC        = 90.0
CIRCUIT_OPEN_SECONDS   = 300     # how long tripped circuit stays open
CIRCUIT_FAIL_THRESHOLD = 4       # consecutive failures to trip circuit
MIN_RESPONSE_CHARS     = 10
STREAM_CHUNK_SIZE      = 4096    # bytes per streaming read
ROLLING_WINDOW         = 20      # calls in ConnectionMonitor rolling window

# ---------------------------------------------------------------------------
# Model registry
# ---------------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class ModelSpec:
    name: str
    context_k: int
    description: str
    supports_think: bool = False
    is_cloud: bool = True


MODEL_REGISTRY: dict[str, ModelSpec] = {
    "nemotron-3-super": ModelSpec(
        name="nemotron-3-super", context_k=256,
        description=(
            "NVIDIA 120B LatentMoE+Mamba — ~12B active params per forward pass "
            "(MoE sparse activation), optimised for agentic reasoning and long-horizon planning"
        ),
    ),
    "kimi-k2:1t-cloud": ModelSpec(
        name="kimi-k2:1t-cloud", context_k=256,
        description="Moonshot 1T MoE (32B active), autonomous coding agents, 256K ctx",
    ),
    "qwen3.5:cloud": ModelSpec(
        name="qwen3.5:cloud", context_k=256,
        description="Alibaba 397B cloud, Text+Image multimodal, universal fallback",
    ),
    "devstral:24b": ModelSpec(
        name="devstral:24b", context_k=128,
        description="Mistral x AllHands 24B, SWE-Bench 46.8%, coding agent, Apache 2.0",
    ),
    "deepseek-r1:14b": ModelSpec(
        name="deepseek-r1:14b", context_k=128,
        description="DeepSeek 14B, chain-of-thought with thinking traces",
        supports_think=True, is_cloud=False,
    ),
}

# Tiered chains — ordered strongest -> final safety net
REASONING_CHAIN: list[str] = ["nemotron-3-super", "kimi-k2:1t-cloud", "qwen3.5:cloud", "deepseek-r1:14b"]
CODING_CHAIN:    list[str] = ["devstral:24b",     "nemotron-3-super",  "qwen3.5:cloud", "deepseek-r1:14b"]
ANALYSIS_CHAIN:  list[str] = ["qwen3.5:cloud",    "nemotron-3-super",  "devstral:24b",  "deepseek-r1:14b"]
ETHICS_CHAIN:    list[str] = ["deepseek-r1:14b",  "nemotron-3-super",  "qwen3.5:cloud", "devstral:24b"]
UNIVERSAL_CHAIN: list[str] = ["nemotron-3-super",  "qwen3.5:cloud",    "devstral:24b",  "deepseek-r1:14b"]

CHAIN_MAP: dict[str, list[str]] = {
    "reasoning": REASONING_CHAIN,
    "coding":    CODING_CHAIN,
    "analysis":  ANALYSIS_CHAIN,
    "ethics":    ETHICS_CHAIN,
    "universal": UNIVERSAL_CHAIN,
}

# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class CompletionResult:
    content: str
    model_used: str
    model_requested: str
    chain_used: list[str]
    tier_index: int           # 0 = primary; 1+ = fell back N times
    attempts: int             # total API calls across all tiers
    latency_s: float
    streamed: bool
    truncated: bool           # True if stream ended without done sentinel
    raw: dict[str, Any]
    audit_trail: list[dict[str, Any]]
    thinking: str = ""                   # Chain-of-thought trace (deepseek-r1 etc.)
    tool_calls: list[dict[str, Any]] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class WebSearchResult:
    """Result from Ollama Cloud /api/web_search endpoint."""
    query: str
    results: list[dict[str, Any]]    # [{title, url, content}, ...]
    raw: dict[str, Any]


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------

class CircuitBreaker:
    """
    Per-model circuit breaker (singleton per model name).
    States: CLOSED (normal) -> OPEN (fast-fail) -> HALF-OPEN (one probe).
    """
    _instances: dict[str, "CircuitBreaker"] = {}
    _class_lock = threading.Lock()

    def __new__(cls, model: str) -> "CircuitBreaker":
        with cls._class_lock:
            if model not in cls._instances:
                inst = super().__new__(cls)
                inst._model = model
                inst._failures = 0
                inst._opened_at: float | None = None
                inst._lock = threading.Lock()
                cls._instances[model] = inst
            return cls._instances[model]

    @property
    def is_open(self) -> bool:
        with self._lock:
            if self._opened_at is None:
                return False
            age = time.monotonic() - self._opened_at
            if age >= CIRCUIT_OPEN_SECONDS:
                log.info("Circuit %s entering HALF-OPEN after %.0fs", self._model, age)
                self._opened_at = None
                # Allow one probe; one more failure reopens
                self._failures = CIRCUIT_FAIL_THRESHOLD - 1
                return False
            return True

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            self._opened_at = None

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._failures >= CIRCUIT_FAIL_THRESHOLD and self._opened_at is None:
                self._opened_at = time.monotonic()
                log.warning(
                    "Circuit OPENED for %s after %d consecutive failures",
                    self._model, self._failures,
                )

    def reset(self) -> None:
        with self._lock:
            self._failures = 0
            self._opened_at = None


# ---------------------------------------------------------------------------
# Connection Monitor
# ---------------------------------------------------------------------------

class ConnectionMonitor:
    """Rolling success-rate and latency tracker (singleton per model)."""
    _instances: dict[str, "ConnectionMonitor"] = {}
    _class_lock = threading.Lock()

    def __new__(cls, model: str) -> "ConnectionMonitor":
        with cls._class_lock:
            if model not in cls._instances:
                inst = super().__new__(cls)
                inst._model = model
                inst._latencies: deque[float] = deque(maxlen=ROLLING_WINDOW)
                inst._outcomes: deque[bool]   = deque(maxlen=ROLLING_WINDOW)
                inst._lock = threading.Lock()
                cls._instances[model] = inst
            return cls._instances[model]

    def record(self, latency_s: float, success: bool) -> None:
        with self._lock:
            self._latencies.append(latency_s)
            self._outcomes.append(success)

    @property
    def success_rate(self) -> float:
        with self._lock:
            if not self._outcomes:
                return 1.0
            return sum(self._outcomes) / len(self._outcomes)

    @property
    def p50_latency(self) -> float:
        with self._lock:
            if not self._latencies:
                return 0.0
            s = sorted(self._latencies)
            return s[len(s) // 2]

    def summary(self) -> str:
        return (
            f"{self._model:<28} ok={self.success_rate:.0%} "
            f"p50={self.p50_latency:.1f}s n={len(self._outcomes)}"
        )


# ---------------------------------------------------------------------------
# Retry Policy  (decorrelated exponential jitter — AWS recommended)
# ---------------------------------------------------------------------------

class RetryPolicy:
    """
    sleep = min(MAX_CAP, random.uniform(BASE, prev_sleep * 3))
    This avoids thundering-herd better than pure exponential + fixed jitter.
    """
    def __init__(
        self,
        max_retries: int = MAX_RETRIES_PER_MODEL,
        base: float = BASE_BACKOFF_SEC,
        cap: float = MAX_BACKOFF_SEC,
    ) -> None:
        self.max_retries = max_retries
        self._base = base
        self._cap = cap
        self._prev = base

    def wait(self, attempt: int) -> None:
        if attempt <= 1:
            return
        sleep = min(self._cap, random.uniform(self._base, self._prev * 3))
        self._prev = sleep
        log.info("  backoff %.1fs before attempt %d/%d", sleep, attempt, self.max_retries)
        time.sleep(sleep)

    def reset(self) -> None:
        self._prev = self._base


# ---------------------------------------------------------------------------
# Streaming Buffer
# ---------------------------------------------------------------------------

class StreamingBuffer:
    """
    Reads Ollama NDJSON streaming response with full protection:
      - Partial-JSON chunk reassembly (chunk boundaries mid-JSON)
      - Per-chunk idle timeout (CHUNK_IDLE_TIMEOUT)
      - Network reset mid-stream (preserves partial content)
      - Soft cap on response size (warns, does not truncate)
      - Missing "done" sentinel detection
      - Thinking trace capture (deepseek-r1, qwen3 thinking mode)
      - Tool-call accumulation from streaming chunks
    read_all()      → (content, is_complete)
    read_all_full() → (content, is_complete, thinking, tool_calls)
    """
    MAX_RESPONSE_CHARS = 400_000

    def __init__(self, response: http.client.HTTPResponse, model: str) -> None:
        self._resp = response
        self._model = model
        self._thinking_buf: list[str] = []
        self._tool_calls_buf: list[Any] = []

    def _read_all_full(self) -> tuple[str, bool, str, list[Any]]:
        parts: list[str] = []
        remainder = b""
        done_seen = False
        total_chars = 0
        last_chunk_at = time.monotonic()

        while True:
            if time.monotonic() - last_chunk_at > CHUNK_IDLE_TIMEOUT:
                log.warning(
                    "[%s] Streaming idle %.0fs — aborting, keeping partial",
                    self._model, CHUNK_IDLE_TIMEOUT,
                )
                break

            try:
                chunk = self._resp.read(STREAM_CHUNK_SIZE)
            except (ConnectionResetError, http.client.IncompleteRead, OSError) as exc:
                log.warning("[%s] Network error mid-stream: %s — keeping partial", self._model, exc)
                break

            if not chunk:
                break

            last_chunk_at = time.monotonic()
            remainder += chunk
            lines = remainder.split(b"\n")
            remainder = lines[-1]  # potentially partial line

            for raw_line in lines[:-1]:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    obj = json.loads(raw_line)
                except json.JSONDecodeError as e:
                    log.debug("[%s] Bad JSON chunk %r: %s", self._model, raw_line[:60], e)
                    continue

                fragment = ""
                thinking_fragment = ""
                msg = obj.get("message", {})
                if isinstance(msg, dict):
                    fragment = msg.get("content", "")
                    # Capture thinking traces (deepseek-r1, qwen3 thinking mode)
                    thinking_fragment = msg.get("thinking", "")
                    # Accumulate tool_calls emitted mid-stream
                    if msg.get("tool_calls"):
                        self._tool_calls_buf = getattr(self, "_tool_calls_buf", [])
                        self._tool_calls_buf.extend(msg["tool_calls"])
                if not fragment:
                    choices = obj.get("choices", [])
                    if choices:
                        delta = choices[0].get("delta", {})
                        fragment = delta.get("content", "")
                        if not thinking_fragment:
                            thinking_fragment = delta.get("thinking", "")

                if thinking_fragment:
                    self._thinking_buf = getattr(self, "_thinking_buf", [])
                    self._thinking_buf.append(thinking_fragment)

                if fragment:
                    parts.append(fragment)
                    total_chars += len(fragment)
                    if total_chars > self.MAX_RESPONSE_CHARS:
                        log.warning(
                            "[%s] Response >%d chars — soft cap reached",
                            self._model, self.MAX_RESPONSE_CHARS,
                        )

                if obj.get("done") is True:
                    done_seen = True

            if done_seen:
                break

        # Flush any remaining buffered bytes
        if remainder.strip():
            try:
                obj = json.loads(remainder.strip())
                msg = obj.get("message", {})
                if isinstance(msg, dict):
                    parts.append(msg.get("content", ""))
                if obj.get("done") is True:
                    done_seen = True
            except json.JSONDecodeError:
                pass

        content = "".join(parts)
        if not done_seen:
            log.warning(
                "[%s] Stream ended without done:true — response may be truncated (%d chars)",
                self._model, len(content),
            )
        thinking = "".join(getattr(self, "_thinking_buf", []))
        tool_calls = getattr(self, "_tool_calls_buf", [])
        return content, done_seen, thinking, tool_calls


    def read_all(self) -> tuple[str, bool]:
        """Simple 2-return-value API for callers that don't need thinking/tool_calls."""
        content, done, _thinking, _tools = self._read_all_full()
        return content, done


# ---------------------------------------------------------------------------
# Response Validator
# ---------------------------------------------------------------------------

class ResponseValidator:
    _ERROR_INDICATORS = (
        "rate limit exceeded", "model not found", "unauthorized",
        "quota exceeded", "service unavailable", "internal server error",
        "context length exceeded", "model is not available",
    )

    @classmethod
    def validate(cls, content: str, model: str) -> tuple[bool, str]:
        if not content or len(content.strip()) < MIN_RESPONSE_CHARS:
            return False, f"Response too short ({len(content)} chars)"
        lower = content.lower().strip()
        for indicator in cls._ERROR_INDICATORS:
            if lower.startswith(indicator) or (len(lower) < 250 and indicator in lower):
                return False, f"Error body detected: {content[:120]!r}"
        return True, ""


# ---------------------------------------------------------------------------
# Low-level single call
# ---------------------------------------------------------------------------

def _call_single(
    model: str,
    system: str,
    prompt: str,
    temperature: float = 0.2,
    think: bool = False,
    api_key: str = "",
    use_streaming: bool = True,
    tools: list[dict[str, Any]] | None = None,
    format_schema: dict[str, Any] | None = None,
    web_search: bool = False,
) -> tuple[str, bool, dict[str, Any]]:
    """
    One attempt against one model.
    Returns (content, is_complete, raw_meta).
    Raises on hard/non-retriable failures.

    Parameters:
        tools         — OpenAI-style tool definitions array for tool calling.
        format_schema — JSON schema dict for structured output enforcement.
        web_search    — If True, inject a web_search tool automatically so
                        the model can fetch live search results during inference.
    """
    cb  = CircuitBreaker(model)
    mon = ConnectionMonitor(model)

    if cb.is_open:
        raise RuntimeError(f"Circuit OPEN for {model!r}")

    spec = MODEL_REGISTRY.get(model)
    messages = [
        {"role": "system", "content": system},
        {"role": "user",   "content": prompt},
    ]
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": use_streaming,
        "options": {"temperature": temperature, "num_predict": 4096},
    }
    # Thinking mode — deepseek-r1, qwen3 etc.
    if think and spec and spec.supports_think:
        payload["think"] = True

    # Structured outputs — pass JSON schema in format field
    if format_schema:
        payload["format"] = format_schema

    # Tool calling — define callable functions for the model to invoke
    resolved_tools = list(tools) if tools else []
    if web_search:
        # Inject the built-in Ollama web_search tool definition
        resolved_tools.append({
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "Search the web for current information to answer the user's query accurately.",
                "parameters": {
                    "type": "object",
                    "required": ["query"],
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query to look up",
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum results to return (1-10, default 5)",
                        },
                    },
                },
            },
        })
    if resolved_tools:
        payload["tools"] = resolved_tools

    body    = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    url     = f"{OLLAMA_CLOUD_BASE}/chat"
    headers = {
        "Content-Type":  "application/json; charset=utf-8",
        "Authorization": f"Bearer {api_key}",
        "Accept":        "application/x-ndjson, application/json",
        "User-Agent":    "hlf-mcp-agent/1.0",
    }
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")

    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=TOTAL_CALL_TIMEOUT) as resp:
            if resp.status != 200:
                raise urllib.error.HTTPError(
                    url=req.full_url, code=resp.status,
                    msg=resp.reason, hdrs=resp.headers,
                    fp=io.BytesIO(resp.read()),
                )
            if use_streaming:
                buf = StreamingBuffer(resp, model)
                content, is_complete, thinking, tool_calls = buf._read_all_full()
                raw_meta = {
                    "model": model, "streamed": True,
                    "thinking": thinking, "tool_calls": tool_calls,
                }
            else:
                raw_bytes = resp.read()
                raw_meta  = json.loads(raw_bytes.decode("utf-8"))
                msg = raw_meta.get("message", {})
                content = msg.get("content", "") if isinstance(msg, dict) else ""
                if not content:
                    choices = raw_meta.get("choices", [])
                    if choices:
                        content = choices[0].get("message", {}).get("content", "")
                is_complete = True
                # Capture thinking and tool_calls from batch response
                if isinstance(msg, dict):
                    raw_meta["thinking"]   = msg.get("thinking", "")
                    raw_meta["tool_calls"] = msg.get("tool_calls", [])

        latency = time.monotonic() - t0
        mon.record(latency, True)
        cb.record_success()
        log.info("[%s] OK %.1fs %d chars complete=%s", model, latency, len(content), is_complete)
        return content, is_complete, raw_meta

    except urllib.error.HTTPError as exc:
        latency = time.monotonic() - t0
        mon.record(latency, False)
        body_snippet = ""
        try:
            body_snippet = (exc.fp.read(400).decode("utf-8", errors="replace") if exc.fp else "")
        except Exception:
            pass
        log.warning("[%s] HTTP %d %.1fs: %s", model, exc.code, latency, body_snippet[:180])
        if exc.code in (401, 403):
            raise RuntimeError(
                f"Auth failure {model!r} HTTP {exc.code} — verify OLLAMA_API_KEY"
            ) from exc
        if exc.code == 404:
            raise RuntimeError(f"Model {model!r} not found (HTTP 404)") from exc
        cb.record_failure()
        raise

    except (urllib.error.URLError, TimeoutError, ConnectionResetError, OSError) as exc:
        latency = time.monotonic() - t0
        mon.record(latency, False)
        cb.record_failure()
        log.warning("[%s] Network error %.1fs: %s", model, latency, exc)
        raise


# ---------------------------------------------------------------------------
# Fallback Orchestrator
# ---------------------------------------------------------------------------

class FallbackOrchestrator:
    """
    Drives a full tiered model chain with every Ollama Cloud API capability:
      - Per-tier circuit-breaker awareness
      - Per-tier retries with decorrelated jitter backoff
      - Streaming buffer protection (chunk reassembly, idle timeout, network reset)
      - Thinking trace capture (deepseek-r1, qwen3 thinking mode)
      - Tool calling (pass tools array; model can invoke functions)
      - Structured outputs (format_schema enforces JSON schema on response)
      - Web search (inject web_search tool so model can retrieve live results)
      - Response validation (content length, error body detection)
      - Complete audit trail on every call
      - Connection health report across the chain

    Ollama API capabilities reference:
      Streaming:          https://docs.ollama.com/capabilities/streaming
      Thinking:           https://docs.ollama.com/capabilities/thinking
      Structured Outputs: https://docs.ollama.com/capabilities/structured-outputs
      Tool Calling:       https://docs.ollama.com/capabilities/tool-calling
      Web Search:         https://docs.ollama.com/capabilities/web-search
    """

    def __init__(
        self,
        chain: list[str] = UNIVERSAL_CHAIN,
        temperature: float = 0.2,
        think: bool = False,
        use_streaming: bool = True,
        max_retries_per_tier: int = MAX_RETRIES_PER_MODEL,
        api_key: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        format_schema: dict[str, Any] | None = None,
        web_search: bool = False,
    ) -> None:
        self.chain = list(chain)
        self.temperature = temperature
        self.think = think
        self.use_streaming = use_streaming
        self.max_retries_per_tier = max_retries_per_tier
        self._api_key = api_key or os.environ.get("OLLAMA_API_KEY", "")
        self.tools = tools or []
        self.format_schema = format_schema
        self.web_search = web_search

    def complete(self, system: str, prompt: str) -> CompletionResult:
        """
        Try every tier until one succeeds and passes validation.
        Returns CompletionResult with full audit trail.
        Raises RuntimeError only after ALL tiers exhausted.
        """
        if not self._api_key:
            log.warning("OLLAMA_API_KEY not set — API calls will likely fail (HTTP 401)")

        audit: list[dict[str, Any]] = []
        total_attempts = 0
        t_start = time.monotonic()

        for tier_idx, model in enumerate(self.chain):
            log.info("── Tier %d/%d: %s ──", tier_idx + 1, len(self.chain), model)
            cb = CircuitBreaker(model)
            if cb.is_open:
                log.warning("[%s] Circuit OPEN — skipping tier %d", model, tier_idx + 1)
                audit.append({"tier": tier_idx, "model": model, "outcome": "circuit_open", "attempts": 0})
                continue

            retry = RetryPolicy(max_retries=self.max_retries_per_tier)

            for attempt in range(1, self.max_retries_per_tier + 1):
                total_attempts += 1
                retry.wait(attempt)
                rec: dict[str, Any] = {"tier": tier_idx, "model": model, "attempt": attempt}
                t_att = time.monotonic()

                try:
                    content, is_complete, raw = _call_single(
                        model=model, system=system, prompt=prompt,
                        temperature=self.temperature, think=self.think,
                        api_key=self._api_key, use_streaming=self.use_streaming,
                        tools=self.tools, format_schema=self.format_schema,
                        web_search=self.web_search,
                    )
                    latency = time.monotonic() - t_att
                    valid, reason = ResponseValidator.validate(content, model)

                    if not valid:
                        log.warning("[%s] attempt %d invalid: %s", model, attempt, reason)
                        rec.update({"outcome": "invalid", "reason": reason, "latency_s": latency})
                        audit.append(rec)
                        continue  # retry

                    rec.update({
                        "outcome": "success", "latency_s": round(latency, 2),
                        "chars": len(content), "complete": is_complete,
                        "thinking_chars": len(raw.get("thinking", "")),
                        "tool_calls_count": len(raw.get("tool_calls", [])),
                    })
                    audit.append(rec)

                    return CompletionResult(
                        content=content, model_used=model,
                        model_requested=self.chain[0], chain_used=self.chain,
                        tier_index=tier_idx, attempts=total_attempts,
                        latency_s=round(time.monotonic() - t_start, 2),
                        streamed=self.use_streaming, truncated=not is_complete,
                        raw=raw, audit_trail=audit,
                        thinking=raw.get("thinking", ""),
                        tool_calls=raw.get("tool_calls", []),
                    )

                except RuntimeError as exc:
                    latency = time.monotonic() - t_att
                    msg = str(exc)
                    non_retriable = any(k in msg for k in ("Auth failure", "not found", "Circuit OPEN"))
                    rec.update({"outcome": "error", "error": msg[:300], "latency_s": round(latency, 2), "non_retriable": non_retriable})
                    audit.append(rec)
                    log.warning("[%s] attempt %d error: %s", model, attempt, msg[:160])
                    if non_retriable:
                        break

                except Exception as exc:
                    latency = time.monotonic() - t_att
                    rec.update({"outcome": "error", "error": str(exc)[:300], "latency_s": round(latency, 2)})
                    audit.append(rec)
                    log.warning("[%s] attempt %d unexpected: %s", model, attempt, exc)

            log.warning("Tier %d (%s) exhausted — trying next tier", tier_idx + 1, model)

        summary = json.dumps([{"m": e["model"], "o": e.get("outcome")} for e in audit])
        raise RuntimeError(
            f"All {len(self.chain)} tiers exhausted after {total_attempts} attempts. "
            f"Chain: {' -> '.join(self.chain)}. Trail: {summary}"
        )

    def health_report(self) -> str:
        lines = [f"Chain health ({' -> '.join(self.chain)}):"]
        for model in self.chain:
            cb  = CircuitBreaker(model)
            mon = ConnectionMonitor(model)
            state = "OPEN " if cb.is_open else "CLOSED"
            lines.append(f"  [{state}] {mon.summary()}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Standalone Web Search  (POST /api/web_search)
# Ref: https://docs.ollama.com/capabilities/web-search
# ---------------------------------------------------------------------------

def web_search(
    query: str,
    max_results: int = 5,
    api_key: str | None = None,
    timeout: int = 30,
) -> WebSearchResult:
    """
    Call Ollama Cloud /api/web_search to retrieve live web results.

    POST https://ollama.com/api/web_search
    Body: {"query": "...", "max_results": N}
    Auth: Authorization: Bearer <OLLAMA_API_KEY>

    Returns WebSearchResult with .results list of {title, url, content} dicts.
    """
    resolved_key = api_key or os.environ.get("OLLAMA_API_KEY", "")
    if not resolved_key:
        log.warning("web_search: OLLAMA_API_KEY not set — request will fail")

    payload = json.dumps({"query": query, "max_results": max_results}, ensure_ascii=False).encode()
    url = f"{OLLAMA_CLOUD_BASE}/web_search"
    req = urllib.request.Request(
        url, data=payload,
        headers={
            "Content-Type":  "application/json; charset=utf-8",
            "Authorization": f"Bearer {resolved_key}",
            "User-Agent":    "hlf-mcp-agent/1.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.fp.read(400).decode("utf-8", errors="replace") if exc.fp else ""
        raise RuntimeError(f"web_search HTTP {exc.code}: {body[:200]}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"web_search network error: {exc}") from exc

    results = raw.get("results", [])
    log.info("web_search %r -> %d results", query, len(results))
    return WebSearchResult(query=query, results=results, raw=raw)


# ---------------------------------------------------------------------------
# Backward-compat shims (keep all existing tests green)
# ---------------------------------------------------------------------------

def call_ollama(
    model: str, system: str, prompt: str,
    temperature: float = 0.2, timeout: int = TOTAL_CALL_TIMEOUT,
    api_key: str | None = None, think: bool = False,
) -> dict[str, Any]:
    """Single-model call — backward compat. Prefer FallbackOrchestrator."""
    content, is_complete, raw = _call_single(
        model=model, system=system, prompt=prompt,
        temperature=temperature, think=think,
        api_key=api_key or os.environ.get("OLLAMA_API_KEY", ""),
        use_streaming=True,
    )
    raw["_content"] = content
    raw["_complete"] = is_complete
    raw.setdefault("message", {})["content"] = content
    return raw


def call_with_fallback(
    model: str, fallback_model: str, system: str, prompt: str,
    temperature: float = 0.2, timeout: int = TOTAL_CALL_TIMEOUT,
    api_key: str | None = None, think: bool = False,
) -> tuple[dict[str, Any], str]:
    """2-tier compat shim. Prefer FallbackOrchestrator."""
    orch = FallbackOrchestrator(
        chain=[model, fallback_model], temperature=temperature,
        think=think, api_key=api_key,
    )
    result = orch.complete(system=system, prompt=prompt)
    raw = result.raw
    raw["_content"] = result.content
    raw.setdefault("message", {})["content"] = result.content
    return raw, result.model_used


def extract_content(response: dict[str, Any]) -> str:
    """Extract content from raw response dict — backward compat."""
    if "_content" in response:
        return response["_content"]
    msg = response.get("message", {})
    if isinstance(msg, dict):
        c = msg.get("content", "")
        if c:
            return c
    choices = response.get("choices", [])
    if choices:
        return choices[0].get("message", {}).get("content", "")
    return str(response)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ollama Cloud — tiered fallback client",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Chains:\n"
            "  reasoning   nemotron-3-super -> kimi-k2:1t-cloud -> qwen3.5:cloud -> deepseek-r1:14b\n"
            "  coding      devstral:24b     -> nemotron-3-super  -> qwen3.5:cloud -> deepseek-r1:14b\n"
            "  analysis    qwen3.5:cloud    -> nemotron-3-super  -> devstral:24b  -> deepseek-r1:14b\n"
            "  ethics      deepseek-r1:14b  -> nemotron-3-super  -> qwen3.5:cloud -> devstral:24b\n"
            "  universal   nemotron-3-super -> qwen3.5:cloud     -> devstral:24b  -> deepseek-r1:14b"
        ),
    )
    grp = parser.add_mutually_exclusive_group(required=True)
    grp.add_argument("--chain",  choices=list(CHAIN_MAP), help="Named tiered chain")
    grp.add_argument("--model",  help="Primary model (requires --fallback-model)")
    parser.add_argument("--fallback-model", default="qwen3.5:cloud")
    parser.add_argument("--system",      required=True)
    parser.add_argument("--prompt",      required=True, help="Prompt text or @file.txt")
    parser.add_argument("--output",      default="-")
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--think",       action="store_true")
    parser.add_argument("--no-stream",   action="store_true")
    parser.add_argument("--retries",     type=int, default=MAX_RETRIES_PER_MODEL)
    parser.add_argument("--health",      action="store_true", help="Print chain health and exit")
    args = parser.parse_args()

    chain = CHAIN_MAP[args.chain] if args.chain else [args.model, args.fallback_model]

    if args.health:
        print(FallbackOrchestrator(chain=chain).health_report())
        return

    prompt = args.prompt
    if prompt.startswith("@"):
        with open(prompt[1:], encoding="utf-8") as f:
            prompt = f.read()
        log.info("Prompt loaded from file (%d chars)", len(prompt))

    orch = FallbackOrchestrator(
        chain=chain, temperature=args.temperature, think=args.think,
        use_streaming=not args.no_stream, max_retries_per_tier=args.retries,
    )

    try:
        result = orch.complete(system=args.system, prompt=prompt)
    except RuntimeError as exc:
        log.error("All tiers exhausted: %s", exc)
        payload = {"error": str(exc), "chain": chain}
        _write_output(args.output, json.dumps(payload, indent=2))
        sys.exit(1)

    if result.tier_index > 0:
        log.warning("Used tier %d (%s) — primary %s was unavailable",
                    result.tier_index + 1, result.model_used, result.model_requested)
    if result.truncated:
        log.warning("Response may be truncated (stream ended without done sentinel)")

    output_data = {
        "model":           result.model_used,
        "model_requested": result.model_requested,
        "tier_index":      result.tier_index,
        "attempts":        result.attempts,
        "latency_s":       result.latency_s,
        "streamed":        result.streamed,
        "truncated":       result.truncated,
        "content":         result.content,
        "audit_trail":     result.audit_trail,
    }

    if args.output == "-":
        print(result.content)
    else:
        _write_output(args.output, json.dumps(output_data, indent=2, ensure_ascii=False))
        log.info(
            "Written to %s (model=%s tier=%d/%d attempts=%d %.1fs %s)",
            args.output, result.model_used, result.tier_index + 1,
            len(chain), result.attempts, result.latency_s,
            "TRUNCATED" if result.truncated else "complete",
        )

    log.info("\n%s", orch.health_report())


def _write_output(path: str, text: str) -> None:
    if path == "-":
        print(text)
    else:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)


if __name__ == "__main__":
    main()
