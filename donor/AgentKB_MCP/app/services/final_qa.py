"""
Final QA pass (secondary critique + improvement).

Per user requirement: apply a final pass to each non-cached response looking for:
- inaccuracies
- inconsistencies
- missed opportunities

The output must remain human-readable (junior developer friendly) and must not
contain "agent speak" meta commentary.
"""

from __future__ import annotations

from typing import Optional

import structlog

from app.config import get_settings
from app.services.llm_executor import LLMExecutor

logger = structlog.get_logger()


QA_SYSTEM_PROMPT = """You are a strict QA reviewer for a developer knowledge base answer.

Goal:
- Improve the answer for correctness and completeness without adding unverifiable facts.

Rules:
- Do NOT add new claims that are not supported by the provided sources list.
- If the answer cites URLs, preserve them exactly.
- Remove inconsistencies, fix mistakes, and tighten the explanation.
- Write for a junior developer (clear, direct, minimal jargon).
- Output ONLY the final answer text. No headings like "QA", no commentary.

If the provided answer is already correct and complete, output it unchanged verbatim.
"""


class FinalQAPassService:
    def __init__(self, executor: Optional[LLMExecutor] = None):
        self.settings = get_settings()
        self.executor = executor or LLMExecutor()

    async def close(self) -> None:
        await self.executor.close()

    async def maybe_apply(
        self,
        *,
        question: str,
        answer: str,
        sources: Optional[list[str]] = None,
        enabled: Optional[bool] = None,
    ) -> str:
        if enabled is None:
            enabled = self.settings.model_policy.qa_enabled
        if not enabled:
            return answer

        if not answer or answer.strip() == "":
            return answer

        sources_block = ""
        if sources:
            sources_block = "\n\nSOURCES (must not invent beyond these):\n" + "\n".join(f"- {s}" for s in sources)

        user_prompt = f"""QUESTION:
{question}

DRAFT ANSWER:
{answer}
{sources_block}

Return the improved FINAL ANSWER only:"""

        # Use strong reasoning for QA pass.
        result = await self.executor.chat_text(
            purpose="qa",
            messages=[{"role": "user", "content": user_prompt}],
            system=QA_SYSTEM_PROMPT,
            temperature=0.0,
            max_tokens=4096,
            json_mode=False,
            think="high",
        )

        improved = (result.content or "").strip()
        if not improved:
            return answer
        return improved


