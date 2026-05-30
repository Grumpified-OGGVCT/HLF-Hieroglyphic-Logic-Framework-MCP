#!/usr/bin/env python3
"""
Cloud Dispatch — stdlib-only module for calling OpenAI-compatible cloud models.

Purpose: Provide a zero-dependency cloud model invocation layer that the
governed_pipeline can use for hybrid dispatch (local MicroSquad + cloud verification).

Constraints:
  - NO hlf_mcp imports (stdlib only)
  - NO torch imports
  - NO requests library (urllib only)
  - Graceful fallback on all errors (never raises)
"""

from __future__ import annotations

import json
import os
import ssl
import time
import hashlib
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

# ── Model Pricing (USD per 1M tokens) ────────────────────────────────────────

MODEL_PRICING: dict[str, dict[str, float]] = {
    "gpt-4o":              {"input": 2.50,  "output": 10.00},
    "gpt-4o-mini":         {"input": 0.15,  "output": 0.60},
    "gpt-4-turbo":         {"input": 10.00, "output": 30.00},
    "claude-3.5-sonnet":   {"input": 3.00,  "output": 15.00},
    "deepseek-chat":       {"input": 0.27,  "output": 1.10},
}

# Fallback pricing for unknown models (uses gpt-4o-mini rates as conservative default)
_DEFAULT_PRICING = {"input": 0.15, "output": 0.60}

# ── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class CloudUsage:
    """Single cloud API call usage record."""
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float
    duration_s: float
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    compressed_query: str = ""  # The distilled query sent (not full context)
    error: str = ""             # Non-empty if the call failed


@dataclass
class UsageTracker:
    """Tracks cumulative cloud usage across calls."""
    calls: list = field(default_factory=list)

    def record(self, usage: CloudUsage) -> None:
        """Record a cloud API call usage."""
        self.calls.append(usage)

    def total_cost(self) -> float:
        """Total cost in USD across all calls."""
        return sum(c.cost_usd for c in self.calls)

    def total_tokens(self) -> dict[str, int]:
        """Cumulative token counts: {prompt, completion, total}."""
        return {
            "prompt": sum(c.prompt_tokens for c in self.calls),
            "completion": sum(c.completion_tokens for c in self.calls),
            "total": sum(c.total_tokens for c in self.calls),
        }

    def summary(self) -> str:
        """Human-readable summary like '4 calls, $0.023, 8,452 tokens'."""
        n = len(self.calls)
        cost = self.total_cost()
        tokens = self.total_tokens()["total"]
        return f"{n} call{'s' if n != 1 else ''}, ${cost:.4f}, {tokens:,} tokens"

    def to_dict(self) -> dict:
        """Full serializable summary."""
        tokens = self.total_tokens()
        return {
            "calls": len(self.calls),
            "total_cost_usd": round(self.total_cost(), 6),
            "total_tokens": tokens,
            "models_used": list(set(c.model for c in self.calls)),
            "call_details": [
                {
                    "model": c.model,
                    "prompt_tokens": c.prompt_tokens,
                    "completion_tokens": c.completion_tokens,
                    "total_tokens": c.total_tokens,
                    "cost_usd": c.cost_usd,
                    "duration_s": c.duration_s,
                    "timestamp": c.timestamp,
                    "error": c.error,
                }
                for c in self.calls
            ],
        }


# ── Helper ───────────────────────────────────────────────────────────────────

def _get_pricing(model: str) -> dict[str, float]:
    """Get pricing dict for a model, falling back to default if unknown."""
    # Try exact match first
    if model in MODEL_PRICING:
        return MODEL_PRICING[model]
    # Try prefix match (e.g., "gpt-4o-2024-08-06" → "gpt-4o")
    for known in MODEL_PRICING:
        if model.startswith(known):
            return MODEL_PRICING[known]
    return _DEFAULT_PRICING


def _calculate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Calculate USD cost from token counts and model pricing."""
    pricing = _get_pricing(model)
    input_cost = (prompt_tokens / 1_000_000) * pricing["input"]
    output_cost = (completion_tokens / 1_000_000) * pricing["output"]
    return round(input_cost + output_cost, 8)


# ── Main API ─────────────────────────────────────────────────────────────────

def call_cloud_model(
    prompt: str,
    model: str = "gpt-4o-mini",
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    max_tokens: int = 1000,
    temperature: float = 0.6,
    tracker: Optional[UsageTracker] = None,
    system_prompt: str = "You are a precise reasoning oracle. Answer concisely and accurately.",
    timeout: int = 30,
) -> tuple[str, CloudUsage]:
    """Call a cloud model via an OpenAI-compatible API.

    Args:
        prompt: The user prompt to send.
        model: Model name (default: gpt-4o-mini).
        api_key: API key. Falls back to OPENAI_API_KEY env var.
        api_base: API base URL. Falls back to OPENAI_API_BASE env var or
                  https://api.openai.com/v1.
        max_tokens: Max completion tokens.
        temperature: Sampling temperature.
        tracker: Optional UsageTracker to record the call.
        system_prompt: System message to prepend.
        timeout: HTTP request timeout in seconds.

    Returns:
        Tuple of (response_text, CloudUsage).
        On any error, response_text is "" and CloudUsage.error is set.
        This function never raises.
    """
    t0 = time.time()

    # Resolve API key
    resolved_key = api_key or os.environ.get("OPENAI_API_KEY", "")
    if not resolved_key:
        usage = CloudUsage(
            model=model,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            cost_usd=0.0,
            duration_s=0.0,
            compressed_query=prompt[:200],
            error="No API key: set OPENAI_API_KEY env var or pass api_key",
        )
        if tracker:
            tracker.record(usage)
        return "", usage

    # Resolve API base
    resolved_base = (api_base or os.environ.get("OPENAI_API_BASE", "")).rstrip("/")
    if not resolved_base:
        resolved_base = "https://api.openai.com/v1"

    url = f"{resolved_base}/chat/completions"

    # Build request body
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    body_bytes = json.dumps(body).encode("utf-8")

    # Build request
    req = urllib.request.Request(
        url,
        data=body_bytes,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {resolved_key}",
        },
        method="POST",
    )

    # Perform request with timeout
    try:
        # Create SSL context that doesn't fail on some corporate proxies
        ctx = ssl.create_default_context()
        response = urllib.request.urlopen(req, timeout=timeout, context=ctx)
        response_bytes = response.read()
        response_text = response_bytes.decode("utf-8")
        data = json.loads(response_text)
    except urllib.error.HTTPError as e:
        duration = time.time() - t0
        error_body = ""
        try:
            error_body = e.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            error_body = str(e)
        # Try to parse error JSON
        error_msg = f"HTTP {e.code}"
        try:
            err_data = json.loads(error_body)
            if "error" in err_data:
                error_msg = err_data["error"].get("message", error_msg)
        except Exception:
            error_msg = f"HTTP {e.code}: {error_body[:200]}"
        usage = CloudUsage(
            model=model,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            cost_usd=0.0,
            duration_s=duration,
            compressed_query=prompt[:200],
            error=error_msg,
        )
        if tracker:
            tracker.record(usage)
        return "", usage
    except urllib.error.URLError as e:
        duration = time.time() - t0
        usage = CloudUsage(
            model=model,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            cost_usd=0.0,
            duration_s=duration,
            compressed_query=prompt[:200],
            error=f"Connection error: {e.reason}",
        )
        if tracker:
            tracker.record(usage)
        return "", usage
    except Exception as e:
        duration = time.time() - t0
        usage = CloudUsage(
            model=model,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            cost_usd=0.0,
            duration_s=duration,
            compressed_query=prompt[:200],
            error=f"Unexpected error: {type(e).__name__}: {e}",
        )
        if tracker:
            tracker.record(usage)
        return "", usage

    duration = time.time() - t0

    # Parse response
    try:
        content = data["choices"][0]["message"]["content"]
        usage_data = data.get("usage", {})
        prompt_tokens = usage_data.get("prompt_tokens", 0)
        completion_tokens = usage_data.get("completion_tokens", 0)
        total_tokens = usage_data.get("total_tokens", prompt_tokens + completion_tokens)
    except (KeyError, IndexError, TypeError) as e:
        usage = CloudUsage(
            model=model,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            cost_usd=0.0,
            duration_s=duration,
            compressed_query=prompt[:200],
            error=f"Bad response format: {e}",
        )
        if tracker:
            tracker.record(usage)
        return "", usage

    cost = _calculate_cost(model, prompt_tokens, completion_tokens)

    usage = CloudUsage(
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        cost_usd=cost,
        duration_s=duration,
        compressed_query=prompt[:200],
    )

    if tracker:
        tracker.record(usage)

    return content, usage


# ── Quick test ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Cloud Dispatch module loaded successfully.")
    print(f"  Known models: {list(MODEL_PRICING.keys())}")
    tracker = UsageTracker()
    print(f"  Tracker: {tracker.summary()}")
    print("  (SKIPPING live API test — run governed_pipeline.py to exercise)")
