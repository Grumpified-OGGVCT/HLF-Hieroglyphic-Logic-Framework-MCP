"""
AGENTS-KB PRO (ENTERPRISE UPGRADE)
Retrieval Transformation: QueryTransformationEngine

Hardcoded verbatim system prompt + schema (as provided by user).
"""

from __future__ import annotations

import json
import re
from typing import List, Optional

import structlog
from pydantic import BaseModel

from app.services.llm_executor import LLMExecutor

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# VERBATIM SYSTEM PROMPT (user-provided)
# ---------------------------------------------------------------------------
QUERY_TRANSFORMATION_SYSTEM_PROMPT = """You are a Technical Search Optimizer. Users (AI Agents) ask vague questions.
GOAL: Translate the input into precise search keywords.
INPUT: {raw_query}
OUTPUT JSON:
{
  "keywords": ["list", "of", "precise", "technical", "terms"],
  "hypothetical_answer": "A hallucinated technical summary of the likely answer using standard terminology.",
  "decomposed_queries": ["sub_query_1", "sub_query_2"] // or null if simple
}"""


class QueryTransformationResult(BaseModel):
    # Verbatim schema (user-provided)
    keywords: List[str]
    hypothetical_answer: str
    decomposed_queries: Optional[List[str]] = None


class QueryTransformationEngine:
    """
    Produces a retrieval-optimized representation of a raw user query.

    - Calls admin-controlled model chain via LLMExecutor (purpose="retrieval_transform").
    - Returns validated QueryTransformationResult.
    """

    def __init__(self, executor: Optional[LLMExecutor] = None):
        self.executor = executor or LLMExecutor()

    async def close(self) -> None:
        await self.executor.close()

    async def transform(self, raw_query: str) -> QueryTransformationResult:
        system = QUERY_TRANSFORMATION_SYSTEM_PROMPT.format(raw_query=raw_query)

        # Request JSON output explicitly.
        user = "Return ONLY the JSON object matching the schema. No markdown, no explanations."

        result = await self.executor.chat_text(
            purpose="retrieval_transform",
            messages=[{"role": "user", "content": user}],
            system=system,
            temperature=0.0,
            max_tokens=1024,
            json_mode=True,
            think="low",
        )

        text = (result.content or "").strip()
        data = self._parse_json(text)
        return QueryTransformationResult.model_validate(data)

    def build_query_strings(self, transformed: QueryTransformationResult, raw_query: str) -> list[str]:
        """
        Build query strings to feed into retrieval.

        Strategy:
        - Primary: space-joined keywords (precise technical terms)
        - Optional: decomposed sub-queries (if provided)
        - Last: include raw_query as a safety net
        """
        queries: list[str] = []

        kw = " ".join([k.strip() for k in transformed.keywords if k and k.strip()])
        if kw:
            queries.append(kw)

        if transformed.decomposed_queries:
            for q in transformed.decomposed_queries:
                q2 = (q or "").strip()
                if q2:
                    queries.append(q2)

        # Safety fallback to original question
        if raw_query.strip():
            queries.append(raw_query.strip())

        # Deduplicate while preserving order
        seen = set()
        out: list[str] = []
        for q in queries:
            key = q.lower().strip()
            if key and key not in seen:
                seen.add(key)
                out.append(q)
        return out

    def _parse_json(self, text: str) -> dict:
        """
        Parse a JSON object from a model output string.
        """
        # Best case: raw JSON object
        try:
            obj = json.loads(text)
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass

        # Fallback: extract first {...} block
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            raise ValueError("No JSON object found in transformation output")
        try:
            obj = json.loads(m.group(0))
        except Exception as e:
            raise ValueError(f"Failed to parse JSON object: {e}") from e
        if not isinstance(obj, dict):
            raise ValueError("Parsed JSON is not an object")
        return obj


