"""
Ollama Cloud API client — shared helper for all HLF GitHub Actions.

Ollama Cloud API reference:
  Base URL: https://ollama.com/api
  Auth:     Authorization: Bearer <OLLAMA_API_KEY>
  Endpoint: POST /api/chat  (native) or POST /v1/chat/completions (OpenAI compat)

Cloud model registry (exact Ollama names, sourced from ollama.com/library pages):

  PRIMARY — multi-agent reasoning & long-horizon planning:
  nemotron-3-super      — NVIDIA, 120B MoE (12B active), Hybrid Mamba+Transformer,
                          256K ctx (up to 1M), LatentMoE architecture, best-in-class
                          for agentic reasoning, long-horizon planning, tool use.
                          https://ollama.com/library/nemotron-3-super

  FALLBACK — universal, multimodal, cloud-optimized:
  qwen3.5:cloud         — Alibaba, 397B cloud tier, Text+Image, 256K ctx, broad
                          utility, strong structured output.
                          https://ollama.com/library/qwen3.5

  CODING AGENT — multi-file codebase, SWE-Bench optimized:
  devstral:24b          — Mistral×AllHands, 24B, 128K ctx, SWE-Bench 46.8%,
                          Apache 2.0, coding agent.
                          https://ollama.com/library/devstral

  REASONING / CHAIN-OF-THOUGHT — ethics, security adversarial:
  deepseek-r1:14b       — DeepSeek, 14B, 128K ctx, chain-of-thought with thinking
                          traces, best for ethics/adversarial reasoning tasks.

  LARGE CONTEXT — full codebase comprehension:
  kimi-k2:1t-cloud      — Moonshot AI, 1T-param MoE, 32B active, 256K ctx,
                          agentic coding, kept as long-context backup.

Model fallback chain (automatic):
  nemotron-3-super → qwen3.5:cloud

Usage:
    python .github/scripts/ollama_client.py \\
        --model nemotron-3-super \\
        --system "You are an HLF code reviewer." \\
        --prompt "Review this code: ..." \\
        --output result.json

    # With automatic fallback to qwen3.5:cloud on failure:
    python .github/scripts/ollama_client.py \\
        --model nemotron-3-super \\
        --fallback-model qwen3.5:cloud \\
        --system "..." --prompt "..."
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error
from typing import Any


OLLAMA_CLOUD_BASE = "https://ollama.com/api"
DEFAULT_TIMEOUT = 300  # seconds — cloud models may be slow for large prompts
MAX_RETRIES = 3
RETRY_DELAY = 10  # seconds between retries


def call_ollama(
    model: str,
    system: str,
    prompt: str,
    temperature: float = 0.2,
    timeout: int = DEFAULT_TIMEOUT,
    api_key: str | None = None,
    think: bool = False,
) -> dict[str, Any]:
    """
    Call the Ollama Cloud /api/chat endpoint.

    Args:
        model:       Exact Ollama model tag, e.g. ``kimi-k2:1t-cloud``
        system:      System prompt — sets the role/task context
        prompt:      The user message / task prompt
        temperature: Sampling temperature (0.0 = deterministic, 1.0 = creative)
        timeout:     HTTP timeout in seconds
        api_key:     Ollama API key; falls back to OLLAMA_API_KEY env var
        think:       Enable extended thinking mode for reasoning models (deepseek-r1)

    Returns:
        Parsed JSON response dict from the API
    """
    key = api_key or os.environ.get("OLLAMA_API_KEY", "")
    if not key:
        print("[ollama_client] WARNING: No OLLAMA_API_KEY found; request may fail.", file=sys.stderr)

    messages: list[dict[str, str]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": 4096,
        },
    }
    if think:
        payload["think"] = True

    body = json.dumps(payload).encode("utf-8")
    url = f"{OLLAMA_CLOUD_BASE}/chat"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw)
        except urllib.error.HTTPError as exc:
            body_text = exc.read().decode("utf-8", errors="replace")
            print(
                f"[ollama_client] HTTP {exc.code} on attempt {attempt}/{MAX_RETRIES}: {body_text[:500]}",
                file=sys.stderr,
            )
            if exc.code in (400, 401, 403, 404):
                # Non-retriable errors
                raise
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY * attempt)
        except (urllib.error.URLError, TimeoutError) as exc:
            print(
                f"[ollama_client] Network error on attempt {attempt}/{MAX_RETRIES}: {exc}",
                file=sys.stderr,
            )
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY * attempt)

    raise RuntimeError(f"All {MAX_RETRIES} attempts to Ollama Cloud API failed for model {model!r}")


def call_with_fallback(
    model: str,
    fallback_model: str,
    system: str,
    prompt: str,
    temperature: float = 0.2,
    timeout: int = DEFAULT_TIMEOUT,
    api_key: str | None = None,
    think: bool = False,
) -> tuple[dict[str, Any], str]:
    """
    Call Ollama Cloud with automatic fallback.

    Tries *model* first; on any failure falls back to *fallback_model*.
    Returns ``(response_dict, model_actually_used)``.

    Default fallback chain: nemotron-3-super → qwen3.5:cloud
    """
    try:
        result = call_ollama(model, system, prompt, temperature, timeout, api_key, think)
        return result, model
    except Exception as primary_exc:
        print(
            f"[ollama_client] Primary model {model!r} failed: {primary_exc}. "
            f"Falling back to {fallback_model!r}.",
            file=sys.stderr,
        )
        try:
            result = call_ollama(fallback_model, system, prompt, temperature, timeout, api_key, think)
            return result, fallback_model
        except Exception as fallback_exc:
            raise RuntimeError(
                f"Both primary ({model!r}) and fallback ({fallback_model!r}) failed.\n"
                f"Primary: {primary_exc}\nFallback: {fallback_exc}"
            ) from fallback_exc


def extract_content(response: dict[str, Any]) -> str:
    """Extract the assistant message content from an Ollama /api/chat response."""
    # Native Ollama format: response.message.content
    msg = response.get("message", {})
    if isinstance(msg, dict):
        content = msg.get("content", "")
        if content:
            return content
    # OpenAI compat fallback: response.choices[0].message.content
    choices = response.get("choices", [])
    if choices:
        return choices[0].get("message", {}).get("content", "")
    return str(response)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ollama Cloud API client")
    parser.add_argument("--model", required=True, help="Ollama model tag, e.g. nemotron-3-super")
    parser.add_argument(
        "--fallback-model", default="qwen3.5:cloud",
        help="Fallback model if primary fails (default: qwen3.5:cloud)",
    )
    parser.add_argument("--system", required=True, help="System prompt")
    parser.add_argument("--prompt", required=True, help="User prompt (or @file.txt to read from file)")
    parser.add_argument("--output", default="-", help="Output file path (- = stdout)")
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--think", action="store_true", help="Enable thinking mode (deepseek-r1 etc.)")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--no-fallback", action="store_true", help="Disable automatic fallback")
    args = parser.parse_args()

    prompt = args.prompt
    if prompt.startswith("@"):
        with open(prompt[1:], encoding="utf-8") as f:
            prompt = f.read()

    if args.no_fallback:
        response = call_ollama(
            model=args.model,
            system=args.system,
            prompt=prompt,
            temperature=args.temperature,
            think=args.think,
            timeout=args.timeout,
        )
        model_used = args.model
    else:
        response, model_used = call_with_fallback(
            model=args.model,
            fallback_model=args.fallback_model,
            system=args.system,
            prompt=prompt,
            temperature=args.temperature,
            think=args.think,
            timeout=args.timeout,
        )

    content = extract_content(response)

    if model_used != args.model:
        print(
            f"[ollama_client] ⚠ Used fallback model {model_used!r} (primary {args.model!r} failed)",
            file=sys.stderr,
        )

    result = {
        "model": model_used,
        "model_requested": args.model,
        "content": content,
        "raw": response,
    }

    if args.output == "-":
        print(content)
    else:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"[ollama_client] Output written to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
