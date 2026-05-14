"""
HLF ↔ LLM Bridge — connects SwarmOrchestrator to actual Ollama models.

Routes HLF prompts through governed routing → Ollama completion,
extracts HLF output, and validates/compiles the result.

Usage:
    bridge = HLFLLMBridge(model="qwen3.5:9b")
    hlf_output = await bridge.send(prompt, role="executor")
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)

# ── result types ─────────────────────────────────────────────────────────────


@dataclass(slots=True)
class LLMCallResult:
    """Result from a governed LLM call for HLF generation."""

    hlf_output: str
    raw_response: str
    model_used: str
    prompt_tokens: int
    completion_tokens: int
    latency_s: float
    compile_success: bool
    compile_error: str = ""
    extracted: bool = False  # whether HLF was extracted from the raw response


# ── bridge ───────────────────────────────────────────────────────────────────


class HLFLLMBridge:
    """Bridge between HLF swarm orchestrator and Ollama LLM backend.

    Sends HLF-structured prompts to Ollama, extracts the HLF portion
    from the response, and validates that it compiles.
    """

    # Models known to produce high-quality HLF output
    # Certification requirements: math-strong, tool-calling, long-horizon
    # Override via HLF_DEFAULT_MODEL / HLF_FALLBACK_MODEL env vars.
    DEFAULT_MODEL = os.environ.get("HLF_DEFAULT_MODEL", "kimi-k2.6:cloud")
    FALLBACK_MODEL = os.environ.get("HLF_FALLBACK_MODEL", "deepseek-v4-pro:cloud")

    def __init__(
        self,
        model: str | None = None,
        ollama_url: str = "http://localhost:11434",
        timeout_s: float = 300.0,
        temperature: float = 0.2,
        num_predict: int = 4096,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self.model = model or self.DEFAULT_MODEL
        self.ollama_url = ollama_url.rstrip("/")
        self.timeout_s = timeout_s
        self.temperature = temperature
        self.num_predict = num_predict
        self._shared_session = session

    # ── public API ────────────────────────────────────────────────────────

    async def send(
        self,
        prompt: str,
        *,
        role: str = "agent",
        system: str = "",
        model: str | None = None,
        session: aiohttp.ClientSession | None = None,
    ) -> LLMCallResult:
        """Send a prompt to Ollama and extract HLF output.

        Parameters
        ----------
        prompt : str
            The full prompt (may contain task description + HLF guidance).
        role : str
            Agent role for logging (planner, executor, verifier, etc.).
        system : str
            Optional system message.
        model : str | None
            Override the default model.

        Returns
        -------
        LLMCallResult
            Structured result with extracted HLF, raw response, and metrics.
        """
        t0 = asyncio.get_event_loop().time()
        selected_model = model or self.model

        # Build the system prompt for HLF-native generation
        full_system = system or self._hlf_system_prompt(role)

        payload = {
            "model": selected_model,
            "prompt": prompt,
            "system": full_system,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.num_predict,
            },
        }

        raw_response = ""
        # Use the per-call session if provided, otherwise the bridge-level shared
        # session, otherwise create a fresh one.
        effective_session = session or self._shared_session
        try:
            async def _do_post(sess: aiohttp.ClientSession) -> str:
                async with sess.post(
                    f"{self.ollama_url}/api/generate",
                    json=payload,
                ) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        raise RuntimeError(
                            f"Ollama API error {resp.status}: {error_text[:200]}"
                        )
                    try:
                        result = await resp.json()
                    except (ValueError, aiohttp.ContentTypeError) as exc:
                        raise RuntimeError(
                            f"Ollama returned non-JSON response: {exc}"
                        ) from exc
                    return result.get("response", "")

            if effective_session is not None:
                raw_response = await _do_post(effective_session)
            else:
                async with aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=self.timeout_s, connect=30)
                ) as fresh_session:
                    raw_response = await _do_post(fresh_session)

        except asyncio.TimeoutError:
            raise RuntimeError(
                f"Ollama call timed out after {self.timeout_s}s for role '{role}'"
            )
        except aiohttp.ClientError as exc:
            raise RuntimeError(f"Ollama connection error: {exc}") from exc

        latency = asyncio.get_event_loop().time() - t0

        # Extract HLF from the response
        hlf_output, extracted = self._extract_hlf(raw_response)

        # Count tokens (character/4 heuristic — common approximation)
        prompt_tokens = max(1, len(prompt) // 4)
        completion_tokens = max(1, len(raw_response) // 4)

        return LLMCallResult(
            hlf_output=hlf_output,
            raw_response=raw_response,
            model_used=selected_model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_s=latency,
            compile_success=False,  # caller must validate
            extracted=extracted,
        )

    async def send_with_fallback(
        self,
        prompt: str,
        *,
        role: str = "agent",
        system: str = "",
    ) -> LLMCallResult:
        """Send with automatic fallback to secondary model on failure."""
        try:
            return await self.send(prompt, role=role, system=system, model=self.model)
        except RuntimeError as exc:
            logger.warning(
                "Primary model '%s' failed for '%s': %s — trying fallback '%s'",
                self.model, role, exc, self.FALLBACK_MODEL,
            )
            try:
                return await self.send(
                    prompt, role=role, system=system, model=self.FALLBACK_MODEL
                )
            except RuntimeError:
                raise  # both failed

    # ── HLF extraction ────────────────────────────────────────────────────

    @staticmethod
    def _extract_hlf(raw: str) -> tuple[str, bool]:
        """Extract HLF source from an LLM response.

        Tries in order:
        1. Code block with [HLF-v3] marker
        2. Code block (any)
        3. Lines starting from [HLF-v3] to Ω (inline HLF)
        4. Full raw text (fallback)

        Returns (hlf_text, was_extracted).
        """
        if not raw:
            return "Ω", False

        # 1. Code block with explicit HLF-v3 header
        pattern_v3 = r"```(?:hlf)?\s*\n\s*(\[HLF-v3\][\s\S]*?)```"
        match = re.search(pattern_v3, raw)
        if match:
            return match.group(1).strip(), True

        # 2. Any code block
        pattern_any = r"```(?:hlf)?\s*\n([\s\S]*?)```"
        match = re.search(pattern_any, raw)
        if match:
            content = match.group(1).strip()
            if content:
                # Normalize: auto-prepend [HLF-v3] if missing
                if not re.match(r"\[HLF-v", content):
                    content = f"[HLF-v3]\n{content}"
                return content, True

        # 3. Inline HLF: find [HLF-v3] ... Ω
        inline = re.search(r"\[HLF-v3\][\s\S]*?Ω", raw)
        if inline:
            return inline.group(0).strip(), True

        # 4. Unrecoverable: no HLF structure detected — return parse-failed marker
        return "[HLF-v3]\n# LLM response contained no recognizable HLF structure\nΩ", False

    # ── system prompts ────────────────────────────────────────────────────

    @staticmethod
    def _hlf_system_prompt(role: str) -> str:
        """Build a system prompt that instructs the LLM to produce valid HLF."""
        return f"""You are an HLF-v3 native agent. You communicate in Hieroglyphic Logic Format.

Respond ONLY with valid HLF-v3 source code wrapped in a code block. Never output explanatory text outside the code block.

HLF-v3 grammar rules:
- Header: [HLF-v3]
- Statements use Unicode glyphs: ⌘ Δ Ж ∇ Σ ⨝ ⌂ ⊎ ⩕
- Tags use [TAG_NAME] syntax (uppercase, underscores allowed): Ж [ASSERT], ⌘ [ROUTE]
- Arguments: key="value" or positional
- Terminator: Ω (must be on its own line)
- Comments: # ...

Example valid HLF:
```hlf
[HLF-v3]
⌘ [GOAL] input="task" output="result"
Δ action="validate input"
Ж [ASSERT] condition="input not empty"
Σ summary="Plan for task execution"
Ω
```

Your role: {role}. Output ONLY the code block with valid HLF-v3."""
