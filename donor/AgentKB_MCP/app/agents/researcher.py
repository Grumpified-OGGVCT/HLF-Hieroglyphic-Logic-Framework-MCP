"""
AGENTS-KB PRO (ENTERPRISE UPGRADE)
ResearchAgent with Save interception + QA critique loop.

Task 6 requirement:
- Hardcode the verbatim QA Audit System Prompt into _critique_draft.
- Ensure critique uses a different model family than the primary researcher if configured/available.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import structlog

from app.config import get_settings
from app.models.kb import KBEntry
from app.schemas.ollama import OllamaChatRequest, OllamaMessage
from app.services.ollama_client import OllamaClient
from app.services.openrouter import DataPolicy, OpenRouterClient, ProviderPreferences

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# VERBATIM QA AUDIT PROMPT (user-provided) — DO NOT MODIFY
# ---------------------------------------------------------------------------
QA_AUDIT_SYSTEM_PROMPT = """Role: Principal Engineer (QA).
Task: Rigorous Technical Audit of a Developer Knowledge Base Entry.

Review the following draft for technical validity. You are the last line of defense against "Happy Path" bias and version hallucinations.

CRITERIA:
1. **Version Integrity**: Does the code match the stated software version? (e.g., Next.js 13 vs 14 syntax).
2. **Failure Modes**: Does the answer omit critical error handling? Does it assume everything works perfectly?
3. **Operational Validity**: Is this theoretically correct but practically impossible in a production environment?

DRAFT CONTENT:
{draft_content}

OUTPUT:
If the draft is solid, output exactly: "LGTM"
If the draft fails any criteria, output a concise, technical explanation of the failure (no fluff)."""


@dataclass(frozen=True)
class ModelRef:
    provider: str  # "ollama" | "openrouter" | "gemini"
    model: str


class ResearchAgent:
    """
    ResearchAgent "Save" interceptor.

    This class owns the staging write step. Before persisting, it runs a QA audit.
    """

    def __init__(
        self,
        staging_root: Optional[Path] = None,
        primary_research_model: Optional[ModelRef] = None,
        ollama: Optional[OllamaClient] = None,
        openrouter: Optional[OpenRouterClient] = None,
    ):
        self.settings = get_settings()
        self.staging_root = staging_root or Path(self.settings.kb.kb_staging_path)
        self.primary_research_model = primary_research_model or ModelRef(
            provider="gemini",
            model=self.settings.google.research_model_name,
        )
        self.ollama = ollama or OllamaClient()
        self.openrouter = openrouter or OpenRouterClient()

    async def close(self) -> None:
        await self.ollama.close()
        await self.openrouter.close()

    async def write_to_staging(self, entry: KBEntry, staging_path: Optional[Path] = None) -> Tuple[bool, Optional[str]]:
        """
        Intercept Save:
        - run _critique_draft(entry markdown)
        - only write if LGTM

        Returns: (success, qa_message)
        """
        draft = entry.to_markdown()
        qa_message = await self._critique_draft(draft_content=draft)
        if (qa_message or "").strip() != "LGTM":
            logger.warning(
                "research_entry_qa_failed",
                entry_id=entry.id,
                domain=entry.domain,
                qa_message=qa_message,
            )
            return False, qa_message

        target_root = staging_path or self.staging_root
        target_root.mkdir(parents=True, exist_ok=True)
        file_path = target_root / f"{entry.domain.lower()}-pending.md"

        try:
            existing = ""
            if file_path.exists():
                existing = file_path.read_text(encoding="utf-8")
                if not existing.endswith("\n\n"):
                    existing += "\n\n"

            file_path.write_text(existing + draft, encoding="utf-8")
            logger.info("research_entry_saved_to_staging", entry_id=entry.id, path=str(file_path))
            return True, "LGTM"
        except Exception as e:
            logger.error("research_entry_save_failed", entry_id=entry.id, error=str(e))
            return False, f"Save failed: {e}"

    async def _critique_draft(self, *, draft_content: str) -> str:
        """
        Run QA audit against the draft content.

        Requirement:
        - Uses QA_AUDIT_SYSTEM_PROMPT verbatim.
        - Selects a different model family than the primary researcher if configured/available.
        """
        prompt = QA_AUDIT_SYSTEM_PROMPT.format(draft_content=draft_content)

        qa_model = self._select_qa_model(primary=self.primary_research_model)

        if qa_model.provider == "ollama":
            return await self._critique_with_ollama(model=qa_model.model, prompt=prompt)
        if qa_model.provider == "openrouter":
            return await self._critique_with_openrouter(model=qa_model.model, prompt=prompt)
        if qa_model.provider == "gemini":
            return await self._critique_with_gemini(model=qa_model.model, prompt=prompt)

        # Should never happen
        return "QA model selection failed"

    # ---------------------------------------------------------------------
    # Model selection (bias prevention)
    # ---------------------------------------------------------------------
    def _select_qa_model(self, *, primary: ModelRef) -> ModelRef:
        """
        Choose QA model ensuring a different family than the primary researcher when possible.
        """
        mp = self.settings.model_policy

        # Candidate list (first is configured QA, then strong reasoner options)
        candidates: list[ModelRef] = []

        if mp.qa_provider and mp.qa_model:
            candidates.append(ModelRef(provider=mp.qa_provider, model=mp.qa_model))

        # Prefer strong reasoner (often GLM) as alternate
        if mp.reasoner_primary_provider and mp.reasoner_primary_model:
            candidates.append(ModelRef(provider=mp.reasoner_primary_provider, model=mp.reasoner_primary_model))

        if mp.reasoner_fallback_openrouter_model:
            candidates.append(ModelRef(provider="openrouter", model=mp.reasoner_fallback_openrouter_model))

        if mp.rtd_fallback_openrouter_model:
            candidates.append(ModelRef(provider="openrouter", model=mp.rtd_fallback_openrouter_model))

        # Last resort: Gemini (may match family, but included for availability)
        gemini_model = mp.rtd_fallback_gemini_model or self.settings.google.model_name
        if gemini_model:
            candidates.append(ModelRef(provider="gemini", model=gemini_model))

        primary_family = self._infer_family(primary.provider, primary.model)

        for cand in candidates:
            if not self._is_available(cand):
                continue
            cand_family = self._infer_family(cand.provider, cand.model)
            if cand_family and primary_family and cand_family != primary_family:
                return cand

        # If none differ, use first available candidate
        for cand in candidates:
            if self._is_available(cand):
                return cand

        # Ultimate fallback: configured QA even if unavailable (will fail loudly upstream)
        return candidates[0] if candidates else ModelRef(provider="gemini", model=self.settings.google.model_name)

    def _infer_family(self, provider: str, model: str) -> str:
        p = (provider or "").lower()
        m = (model or "").lower().strip()

        if p == "openrouter":
            # "google/gemini-..." -> "google"
            return m.split("/", 1)[0] if "/" in m else m

        if p == "ollama":
            # heuristic: gemini-* -> gemini ; glm-* -> glm ; otherwise first token
            for prefix in ("gemini", "glm", "qwen", "gpt", "mistral", "deepseek", "llama", "nemotron", "ministral"):
                if m.startswith(prefix):
                    return prefix
            return m.split("-", 1)[0] if "-" in m else m

        if p == "gemini":
            return "gemini"

        return p or "unknown"

    def _is_available(self, mr: ModelRef) -> bool:
        if mr.provider == "openrouter":
            return bool(self.settings.openrouter.api_key.get_secret_value())

        if mr.provider == "gemini":
            return bool(self.settings.google.api_key.get_secret_value())

        if mr.provider == "ollama":
            base = (self.settings.ollama.base_url or "").strip().lower()
            key = self.settings.ollama.api_key.get_secret_value()
            # Cloud needs key; local does not.
            if base.startswith("https://ollama.com"):
                return bool(key)
            return bool(base)

        return False

    # ---------------------------------------------------------------------
    # Provider calls
    # ---------------------------------------------------------------------
    async def _critique_with_ollama(self, *, model: str, prompt: str) -> str:
        req = OllamaChatRequest(
            model=model,
            messages=[
                OllamaMessage(role="system", content=prompt),
                OllamaMessage(role="user", content="Audit the draft and respond with LGTM or the failure reason."),
            ],
            stream=False,
            think="high",
        )
        resp = await self.ollama.chat(req)
        content = resp.message.content if isinstance(resp.message.content, str) else str(resp.message.content)
        return (content or "").strip()

    async def _critique_with_openrouter(self, *, model: str, prompt: str) -> str:
        provider = ProviderPreferences(data_collection=DataPolicy.DENY)
        resp = await self.openrouter.chat_completion(
            messages=[{"role": "user", "content": "Audit the draft and respond with LGTM or the failure reason."}],
            model=model,
            system=prompt,
            temperature=0.0,
            max_tokens=512,
            provider=provider,
        )
        return (resp.content or "").strip()

    async def _critique_with_gemini(self, *, model: str, prompt: str) -> str:
        import google.generativeai as genai

        api_key = self.settings.google.api_key.get_secret_value()
        if not api_key:
            return "QA Gemini key not configured"
        genai.configure(api_key=api_key)
        gmodel = genai.GenerativeModel(
            model_name=model,
            generation_config={"temperature": 0.0, "max_output_tokens": 512},
        )
        resp = gmodel.generate_content(prompt)
        return (getattr(resp, "text", "") or "").strip()


