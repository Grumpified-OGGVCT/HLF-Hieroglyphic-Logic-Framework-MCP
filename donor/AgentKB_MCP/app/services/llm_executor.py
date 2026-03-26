"""
Admin-controlled LLM execution (provider + model policy).

This module exists to ensure *end users* never choose models directly; only the
system administrator config controls provider/model selection.

Provider contracts referenced:
- Ollama API: https://docs.ollama.com/api/introduction
- Ollama cloud base URL: https://ollama.com/api (described in docs) https://docs.ollama.com/api/introduction
- Ollama auth: https://docs.ollama.com/api/authentication
- OpenRouter API: https://openrouter.ai/api/v1 (existing client in app/services/openrouter.py)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import structlog

from app.config import get_settings
from app.services.ollama_client import OllamaClient
from app.schemas.ollama import OllamaChatRequest, OllamaMessage
from app.services.openrouter import (
    DataPolicy,
    OpenRouterClient,
    ProviderPreferences,
)

logger = structlog.get_logger()


@dataclass(frozen=True)
class LLMTextResult:
    provider: str
    model: str
    content: str
    finish_reason: str = "stop"
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    meta: Optional[dict[str, Any]] = None


class LLMExecutor:
    """
    Executes LLM calls using admin-configured provider/model selection.

    Purposes are internal-only and determine which model chain to use:
    - rtd: real-time data / grounded general
    - reasoner: strong reasoning (non-RTD)
    - qa: final QA pass
    - retrieval_transform: query rewrite/transformation
    - research: research agent core LLM call
    """

    def __init__(
        self,
        ollama: Optional[OllamaClient] = None,
        openrouter: Optional[OpenRouterClient] = None,
    ):
        self.settings = get_settings()
        self.ollama = ollama or OllamaClient()
        self.openrouter = openrouter or OpenRouterClient()

    async def close(self) -> None:
        await self.ollama.close()
        await self.openrouter.close()

    async def chat_text(
        self,
        *,
        purpose: str,
        messages: list[dict[str, str]],
        system: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        json_mode: bool = False,
        think: Optional[bool | str] = None,
    ) -> LLMTextResult:
        chain = self._provider_chain_for_purpose(purpose)
        last_error: Optional[Exception] = None

        for provider, model in chain:
            if not model:
                continue

            if self.settings.model_policy.disallow_premium_models and model in set(
                self.settings.model_policy.premium_models_list
            ):
                continue

            try:
                if provider == "ollama":
                    resolved_model = await self._resolve_ollama_model(model, purpose=purpose)
                    if not resolved_model:
                        continue
                    return await self._chat_ollama(
                        model=resolved_model,
                        messages=messages,
                        system=system,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        json_mode=json_mode,
                        think=think,
                    )

                if provider == "openrouter":
                    return await self._chat_openrouter(
                        model=model,
                        messages=messages,
                        system=system,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        json_mode=json_mode,
                    )

                if provider == "gemini":
                    return await self._chat_gemini(
                        model=model,
                        messages=messages,
                        system=system,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )

            except Exception as e:
                last_error = e
                logger.warning(
                    "llm_provider_failed",
                    purpose=purpose,
                    provider=provider,
                    model=model,
                    error=str(e),
                )
                continue

        raise RuntimeError(f"No LLM providers succeeded for purpose={purpose}") from last_error

    def _provider_chain_for_purpose(self, purpose: str) -> list[tuple[str, str]]:
        mp = self.settings.model_policy
        google = self.settings.google

        if purpose in {"rtd", "retrieval_transform", "research"}:
            gemini_model = mp.rtd_fallback_gemini_model or google.research_model_name or google.model_name
            return [
                ("ollama", mp.rtd_primary_model),
                ("openrouter", mp.rtd_fallback_openrouter_model),
                ("gemini", gemini_model),
            ]

        if purpose == "reasoner":
            return [
                ("ollama", mp.reasoner_primary_model),
                ("openrouter", mp.reasoner_fallback_openrouter_model),
            ]

        if purpose == "qa":
            chain: list[tuple[str, str]] = [(mp.qa_provider, mp.qa_model)]
            # If QA is ollama-based, allow configured OpenRouter reasoner fallback (often GLM).
            if mp.qa_provider == "ollama" and mp.reasoner_fallback_openrouter_model:
                chain.append(("openrouter", mp.reasoner_fallback_openrouter_model))
            # Last-resort fallback to Gemini if configured.
            gemini_model = mp.rtd_fallback_gemini_model or google.model_name
            if gemini_model:
                chain.append(("gemini", gemini_model))
            return chain

        # Default: behave like RTD chain (safe)
        gemini_model = mp.rtd_fallback_gemini_model or google.model_name
        return [
            ("ollama", mp.rtd_primary_model),
            ("openrouter", mp.rtd_fallback_openrouter_model),
            ("gemini", gemini_model),
        ]

    async def _resolve_ollama_model(self, requested: str, *, purpose: str) -> Optional[str]:
        """
        Resolve model slug changes (e.g. preview → non-preview) by checking /api/tags.
        """
        # For RTD, try configured aliases in order.
        candidates = [requested]
        if purpose in {"rtd", "retrieval_transform", "research"}:
            for m in self.settings.model_policy.rtd_primary_model_aliases_list:
                if m and m not in candidates:
                    candidates.append(m)

        try:
            tags = await self.ollama.list_models()
            available = {m.name for m in tags.models}
        except Exception:
            # If tags fails (e.g., network), attempt requested model as-is.
            return requested

        for cand in candidates:
            if cand in available:
                return cand
        return None

    async def _chat_ollama(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        system: Optional[str],
        temperature: float,
        max_tokens: int,
        json_mode: bool,
        think: Optional[bool | str],
    ) -> LLMTextResult:
        # Ollama expects "messages" array, system prompt is a message with role=system.
        ollama_messages: list[OllamaMessage] = []
        if system:
            ollama_messages.append(OllamaMessage(role="system", content=system))
        for msg in messages:
            ollama_messages.append(OllamaMessage(role=msg["role"], content=msg["content"]))

        req = OllamaChatRequest(
            model=model,
            messages=ollama_messages,
            stream=False,  # structured outputs easier in non-streaming mode
            format="json" if json_mode else None,
            options={
                # Ollama options are model-dependent; keep minimal and safe.
                "temperature": temperature,
                "num_predict": max_tokens,
            },
            think=think,
        )

        resp = await self.ollama.chat(req)
        content = (resp.message.content or "").strip() if isinstance(resp.message.content, str) else str(resp.message.content)
        # Token counts are provided as eval counts; approximate for unified fields.
        prompt_tokens = resp.prompt_eval_count or 0
        completion_tokens = resp.eval_count or 0
        return LLMTextResult(
            provider="ollama",
            model=model,
            content=content,
            finish_reason=resp.done_reason or "stop",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            meta={"created_at": resp.created_at},
        )

    async def _chat_openrouter(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        system: Optional[str],
        temperature: float,
        max_tokens: int,
        json_mode: bool,
    ) -> LLMTextResult:
        provider = ProviderPreferences(data_collection=DataPolicy.DENY)
        response_format = {"type": "json_object"} if json_mode else None
        resp = await self.openrouter.chat_completion(
            messages=messages,
            model=model,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
            provider=provider,
        )
        return LLMTextResult(
            provider="openrouter",
            model=resp.model,
            content=(resp.content or "").strip(),
            finish_reason=resp.finish_reason,
            prompt_tokens=resp.usage.prompt_tokens,
            completion_tokens=resp.usage.completion_tokens,
            total_tokens=resp.usage.total_tokens,
            meta={"generation_id": resp.id},
        )

    async def _chat_gemini(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        system: Optional[str],
        temperature: float,
        max_tokens: int,
    ) -> LLMTextResult:
        """
        Minimal Gemini call (text-only) using google.generativeai.

        Note: Gemini model naming is admin-configured; keep it as-is.
        """
        import google.generativeai as genai

        api_key = self.settings.google.api_key.get_secret_value()
        if not api_key:
            raise RuntimeError("Gemini API key not configured")

        genai.configure(api_key=api_key)

        prompt = ""
        if system:
            prompt += f"<system>\n{system}\n</system>\n\n"

        for m in messages:
            role = m.get("role")
            content = m.get("content", "")
            if role == "user":
                prompt += f"User: {content}\n\n"
            elif role == "assistant":
                prompt += f"Assistant: {content}\n\n"
            else:
                prompt += f"{role}: {content}\n\n"

        gmodel = genai.GenerativeModel(
            model_name=model,
            generation_config={
                "temperature": temperature,
                "max_output_tokens": max_tokens,
            },
        )
        resp = gmodel.generate_content(prompt)
        text = (resp.text or "").strip() if hasattr(resp, "text") else ""
        # Rough token estimate; Gemini token usage is not exposed in this client consistently.
        prompt_tokens = len(prompt) // 4
        completion_tokens = len(text) // 4
        return LLMTextResult(
            provider="gemini",
            model=model,
            content=text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )


