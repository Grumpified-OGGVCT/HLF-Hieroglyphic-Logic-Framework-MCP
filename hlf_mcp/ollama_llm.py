"""
Synchronous Ollama LLM client for SwarmGlass orchestrator.
Provides chat/generate calls for answer synthesis and semantic filtering.

Usage:
    from hlf_mcp.ollama_llm import ollama_generate, DEFAULT_MODEL, FAST_MODEL

    result = ollama_generate("Summarize this", model=DEFAULT_MODEL)
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import requests

logger = logging.getLogger(__name__)

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
if not OLLAMA_HOST.startswith(("http://", "https://")):
    OLLAMA_HOST = f"http://{OLLAMA_HOST}"

# ── Model selection ───────────────────────────────────────────────────────────

# DEFAULT_MODEL: best balance of quality and speed for narrative synthesis
# gemma4 has issues with narrative prompts; llama3.2 handles prose well
DEFAULT_MODEL = os.environ.get("HLF_NARRATIVE_MODEL", "llama3.2:latest")

# FAST_MODEL: quick lightweight model for filtering / classification
FAST_MODEL = os.environ.get("HLF_FAST_MODEL", "gemma3n:latest")

# FALLBACK_MODEL: if primary model fails
FALLBACK_MODEL = os.environ.get("HLF_NARRATIVE_FALLBACK", "llama3.2:latest")

# ── Public API ────────────────────────────────────────────────────────────────


def ollama_generate(
    prompt: str,
    *,
    model: str = DEFAULT_MODEL,
    system: str = "",
    temperature: float = 0.3,
    max_tokens: int = 1024,
    timeout_s: float = 60.0,
) -> str:
    """Send a prompt to Ollama and return the generated text.

    Synchronous — uses requests (not aiohttp) for simplicity in tool handlers.

    Parameters
    ----------
    prompt : str
        The user prompt.
    model : str
        Model name from ``ollama list``.
    system : str
        Optional system prompt.
    temperature : float
        Sampling temperature (lower = more deterministic).
    max_tokens : int
        Maximum tokens to generate.
    timeout_s : float
        Request timeout.

    Returns
    -------
    str
        Generated text response (empty string on failure).

    Raises
    ------
    RuntimeError
        If Ollama returns an error status.
    """
    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }
    if system:
        payload["system"] = system

    url = f"{OLLAMA_HOST}/api/generate"

    try:
        resp = requests.post(url, json=payload, timeout=timeout_s)
        if resp.status_code != 200:
            error_text = resp.text[:200]
            logger.warning("Ollama API error %d: %s", resp.status_code, error_text)
            return ""
        data = resp.json()
        # Reasoning models (deepseek-v4-pro, etc.) return content in "thinking" instead of "response"
        text = data.get("response", "") or data.get("thinking", "")
        # Attach cost metadata — use a wrapper dict since str is immutable
        cost_info = {
            "model": data.get("model", model),
            "total_duration_ns": data.get("total_duration", 0),
            "prompt_tokens": data.get("prompt_eval_count", 0),
            "eval_tokens": data.get("eval_count", 0),
            "text": str(text),
        }
        # Return as a dict for callers that need cost data
        # Legacy callers expecting a raw string: wrap in a dict but also support str()
        class _CostString(str):
            pass
        result = _CostString(text)
        result._cost_info = cost_info  # type: ignore[attr-defined]
        return result
    except requests.Timeout:
        logger.warning("Ollama call timed out after %.0fs for model %s", timeout_s, model)
        return ""
    except requests.ConnectionError as exc:
        logger.warning("Ollama connection error: %s", exc)
        return ""


def ollama_generate_with_fallback(
    prompt: str,
    *,
    model: str = DEFAULT_MODEL,
    fallback_model: str | None = None,
    system: str = "",
    **kwargs: Any,
) -> str:
    """Generate with automatic fallback to secondary model on failure.

    Parameters
    ----------
    prompt : str
        The user prompt.
    model : str
        Primary model.
    fallback_model : str | None
        Fallback model. Defaults to FALLBACK_MODEL if None.
    system : str
        Optional system prompt.
    **kwargs
        Passed to ollama_generate().

    Returns
    -------
    str
        Generated text (empty string if both models fail).
    """
    fb = fallback_model or FALLBACK_MODEL
    result = ollama_generate(prompt, model=model, system=system, **kwargs)
    if not result and fb != model:
        logger.info("Primary model '%s' failed, trying fallback '%s'", model, fb)
        result = ollama_generate(prompt, model=fb, system=system, **kwargs)
    return result


def filter_recall_results(
    query: str,
    results: list[dict[str, Any]],
    *,
    model: str = FAST_MODEL,
) -> list[dict[str, Any]]:
    """Use LLM to filter recall results for relevance to the query.

    Takes raw semantic-search results and asks the LLM to select only
    those that genuinely answer the user's question, discarding false
    positives from embedding similarity.

    Parameters
    ----------
    query : str
        Original user query.
    results : list[dict]
        Raw results from sg_memory_governed_recall or sg_memory_query.
    model : str
        Model for filtering (uses FAST_MODEL by default).

    Returns
    -------
    list[dict]
        Filtered subset of results that the LLM deemed relevant.
    """
    if not results:
        return results
    if len(results) <= 1:
        return results  # single result, nothing to filter

    # Build a compact prompt for filtering
    items_text = ""
    for i, r in enumerate(results):
        content = str(r.get("content", r))[:200]
        fid = r.get("id", f"item-{i}")
        items_text += f"[{i}] ID={fid} | {content}\n"

    prompt = f"""You are a relevance filter. Given a user query and a list of search results, return ONLY the indices of results that are genuinely relevant to answering the query. Ignore false positives from semantic similarity.

USER QUERY: {query[:300]}

RESULTS:
{items_text}

Return a JSON array of indices (numbers only) that are relevant. Example: [0, 3, 5]
If none are relevant, return [].
ONLY output the JSON array, nothing else."""

    system = "Output ONLY a JSON array of indices. No other text."

    raw = ollama_generate(prompt, model=model, system=system, max_tokens=200, temperature=0.1)

    if not raw:
        return results  # fallback: return all

    # Parse the JSON array
    try:
        # Find the JSON array in the response
        import re
        match = re.search(r"\[[\d,\s]*\]", raw)
        if match:
            indices = json.loads(match.group(0))
            filtered = [results[i] for i in indices if 0 <= i < len(results)]
            if filtered:
                logger.debug("LLM filtered %d→%d results", len(results), len(filtered))
                return filtered
    except (json.JSONDecodeError, ValueError, IndexError) as exc:
        logger.debug("LLM filtering parse error: %s", exc)

    return results  # fallback: return all


def synthesize_narrative_answer(
    intent: str,
    pillar_summaries: dict[str, str],
    *,
    model: str = DEFAULT_MODEL,
) -> str:
    """Generate human-readable narrative prose from structured pillar results.

    Takes the mechanical bullet-point answer and rephrases it as flowing
    natural language that a human can read and forward without editing.

    Parameters
    ----------
    intent : str
        Original user intent.
    pillar_summaries : dict[str, str]
        Dict mapping pillar name → summary line (e.g., {"memory": "Stored fact #65712", ...}).
    model : str
        Model for synthesis (uses DEFAULT_MODEL).

    Returns
    -------
    str
        Flowing narrative prose.
    """
    if not pillar_summaries:
        return ""

    summary_text = "\n".join(f"- {k}: {v}" for k, v in pillar_summaries.items())

    prompt = f"""You are a governance assistant summarizing what just happened. Turn these structured results into one flowing paragraph a busy professional can read and forward. Be concise but conversational. Include the key fact IDs, Merkle root prefix, and status. Never mention tool names.

USER ASKED: {intent[:300]}

WHAT HAPPENED:
{summary_text}

Write one paragraph summarizing the outcome:"""

    system = "Be concise and helpful."

    narrative = ollama_generate(
        prompt,
        model=model,
        system=system,
        max_tokens=300,
        temperature=0.3,
    )

    if not narrative:
        # Fallback: just return the structured summary
        return "\n".join(pillar_summaries.values())

    return narrative.strip()


# ── Model health check ────────────────────────────────────────────────────────


def check_ollama_available(timeout_s: float = 5.0) -> bool:
    """Check if Ollama is reachable."""
    try:
        resp = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=timeout_s)
        return resp.status_code == 200
    except (requests.ConnectionError, requests.Timeout):
        return False
