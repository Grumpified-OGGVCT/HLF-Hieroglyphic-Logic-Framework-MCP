"""
Dynamic Model Certification Pipeline
====================================
Discovers Ollama models dynamically, sends standard HLF prompts to each model,
validates compilation output, and produces ranked certification reports.

Usage::

    # Run certification against all discovered models
    python -m hlf_mcp.hlf.model_certification

    # Filter to specific models
    python -m hlf_mcp.hlf.model_certification --models kimi-k2.5:cloud,deepseek-v4-pro:cloud

    # Environment overrides
    HLF_CERTIFY_MODELS=kimi-k2.5:cloud,deepseek-v4-pro:cloud
    HLF_CERTIFY_PROMPT_COUNT=3
"""

from __future__ import annotations

import aiohttp
import argparse
import asyncio
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


# ── Standard certification prompts ──────────────────────────────────────────────
# Each prompt targets a specific HLF-v3 construct.
# Models must respond with valid [HLF-v3] blocks, not English prose.

_STANDARD_PROMPTS: tuple[tuple[str, str], ...] = (
    (
        "SET",
        "Create an HLF program that sets a variable 'threshold' to 80. "
        "Output ONLY a valid [HLF-v3] code block with no explanatory text outside the block.",
    ),
    (
        "IF/THEN",
        "Write HLF that checks if risk is greater than 0, then marks result as elevated. "
        "Output ONLY a valid [HLF-v3] code block with no explanatory text outside the block.",
    ),
    (
        "PARALLEL",
        "Create HLF with two parallel tasks: analyze_data and validate_results. "
        "Output ONLY a valid [HLF-v3] code block with no explanatory text outside the block.",
    ),
    (
        "FUNC/DEFINE",
        "Write an HLF function called calculate_score that takes a value parameter. "
        "Output ONLY a valid [HLF-v3] code block with no explanatory text outside the block.",
    ),
    (
        "CONSTRAINT",
        "Write HLF with a constraint that score must be between 0 and 100. "
        "Output ONLY a valid [HLF-v3] code block with no explanatory text outside the block.",
    ),
    (
        "SPEC_GATE",
        "Write an HLF spec gate called safety_check that requires simulation_only mode. "
        "Output ONLY a valid [HLF-v3] code block with no explanatory text outside the block.",
    ),
)


# ── Result dataclasses ──────────────────────────────────────────────────────────


@dataclass(slots=True)
class ModelCertificationResult:
    """Per-model certification result with aggregated metrics."""

    model_name: str
    prompts_tested: int
    compile_successes: int
    compile_success_rate: float  # 0.0 to 1.0
    avg_latency_s: float
    avg_prompt_tokens: int
    avg_completion_tokens: int
    per_prompt_results: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def is_fluent(self) -> bool:
        """A model is 'fluent' if >= 80% of prompts compile successfully."""
        return self.compile_success_rate >= 0.8

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "prompts_tested": self.prompts_tested,
            "compile_successes": self.compile_successes,
            "compile_success_rate": self.compile_success_rate,
            "avg_latency_s": self.avg_latency_s,
            "avg_prompt_tokens": self.avg_prompt_tokens,
            "avg_completion_tokens": self.avg_completion_tokens,
            "per_prompt_results": self.per_prompt_results,
            "errors": self.errors,
            "is_fluent": self.is_fluent(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ModelCertificationResult:
        return cls(
            model_name=data["model_name"],
            prompts_tested=data["prompts_tested"],
            compile_successes=data["compile_successes"],
            compile_success_rate=data["compile_success_rate"],
            avg_latency_s=data["avg_latency_s"],
            avg_prompt_tokens=data["avg_prompt_tokens"],
            avg_completion_tokens=data["avg_completion_tokens"],
            per_prompt_results=data.get("per_prompt_results", []),
            errors=data.get("errors", []),
        )


@dataclass(slots=True)
class CertificationReport:
    """Aggregate certification report for all tested models."""

    models_tested: int
    total_prompts_per_model: int
    results: list[ModelCertificationResult] = field(default_factory=list)
    rankings: list[dict[str, Any]] = field(default_factory=list)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def fluent_models(self) -> list[str]:
        """Return model names with >= 80% compile success rate."""
        return [r.model_name for r in self.results if r.is_fluent()]

    def best_model(self) -> str:
        """Return name of the top-ranked model, or empty string if none."""
        if not self.rankings:
            return ""
        return str(self.rankings[0].get("model_name", ""))

    def to_dict(self) -> dict[str, Any]:
        return {
            "models_tested": self.models_tested,
            "total_prompts_per_model": self.total_prompts_per_model,
            "results": [r.to_dict() for r in self.results],
            "rankings": self.rankings,
            "timestamp": self.timestamp,
            "fluent_models": self.fluent_models(),
            "best_model": self.best_model(),
        }

    def summary(self) -> str:
        """Human-readable summary of certification results."""
        lines = [
            "=" * 60,
            "HLF MODEL CERTIFICATION REPORT",
            "=" * 60,
            f"Timestamp:           {self.timestamp}",
            f"Models tested:       {self.models_tested}",
            f"Prompts per model:   {self.total_prompts_per_model}",
            "",
            "─" * 60,
            "RANKINGS (by compile success rate)",
            "─" * 60,
        ]
        for i, entry in enumerate(self.rankings, 1):
            lines.append(
                f"  {i:2d}. {entry['model_name']:<30s} "
                f"success={entry['compile_success_rate']:.1%}  "
                f"latency={entry.get('avg_latency_s', 0):.1f}s  "
                f"{'FLUENT' if entry.get('is_fluent') else 'FAIL'}"
            )
        lines.append("")
        fluent = self.fluent_models()
        lines.append(f"Fluent models (>=80%): {', '.join(fluent) if fluent else 'NONE'}")
        if self.rankings:
            lines.append(f"Best model:           {self.best_model()}")
        lines.append("=" * 60)
        return "\n".join(lines)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CertificationReport:
        return cls(
            models_tested=data["models_tested"],
            total_prompts_per_model=data["total_prompts_per_model"],
            results=[ModelCertificationResult.from_dict(r) for r in data.get("results", [])],
            rankings=data.get("rankings", []),
            timestamp=data.get("timestamp", ""),
        )


# ── Model Certification Runner ──────────────────────────────────────────────────


class ModelCertificationRunner:
    """Discovers Ollama models dynamically and runs HLF certification against them.

    Parameters
    ----------
    ollama_url : str
        Base URL for the Ollama API (default: http://localhost:11434).
    timeout : int
        Timeout in seconds for individual model calls.
    """

    def __init__(
        self,
        ollama_url: str = "http://localhost:11434",
        timeout: int = 300,
    ) -> None:
        self.ollama_url = ollama_url.rstrip("/")
        self.timeout = timeout

    # ── Dynamic model discovery ─────────────────────────────────────────────

    async def discover_models(self) -> list[str]:
        """Query the Ollama API for available model names.

        Returns
        -------
        list[str]
            Sorted list of model names discovered from ``/api/tags``.
        """
        return await _discover_ollama_models(self.ollama_url, self.timeout)

    # ── Certification pipeline ──────────────────────────────────────────────

    async def run_certification(
        self,
        models: list[str] | None = None,
        prompt_count: int = 6,
    ) -> CertificationReport:
        """Run full certification against the specified (or all discovered) models.

        Parameters
        ----------
        models : list[str] | None
            Model names to test.  If ``None``, all models discovered from Ollama
            are tested.
        prompt_count : int
            Number of standard prompts to use (1–6).  Defaults to all 6.

        Returns
        -------
        CertificationReport
            Aggregated results, rankings, and summary.
        """
        if models is None:
            models = await self.discover_models()

        if not models:
            logger.warning("No models to certify — returning empty report")
            return CertificationReport(
                models_tested=0,
                total_prompts_per_model=min(prompt_count, len(_STANDARD_PROMPTS)),
            )

        prompt_count = max(1, min(prompt_count, len(_STANDARD_PROMPTS)))
        prompts = _STANDARD_PROMPTS[:prompt_count]

        # Test each model concurrently, sharing one ClientSession for efficiency.
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout, connect=30)
        ) as shared_session:
            tasks = [
                self.certify_model(name, prompts, session=shared_session)
                for name in models
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        certification_results: list[ModelCertificationResult] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error("Model '%s' certification crashed: %s", models[i], result)
                certification_results.append(
                    ModelCertificationResult(
                        model_name=models[i],
                        prompts_tested=len(prompts),
                        compile_successes=0,
                        compile_success_rate=0.0,
                        avg_latency_s=0.0,
                        avg_prompt_tokens=0,
                        avg_completion_tokens=0,
                        errors=[str(result)],
                    )
                )
            else:
                certification_results.append(result)

        # Build rankings sorted by compile_success_rate descending
        rankings = sorted(
            [
                {
                    "model_name": r.model_name,
                    "compile_success_rate": r.compile_success_rate,
                    "avg_latency_s": r.avg_latency_s,
                    "is_fluent": r.is_fluent(),
                    "compile_successes": r.compile_successes,
                    "prompts_tested": r.prompts_tested,
                }
                for r in certification_results
            ],
            key=lambda x: (-x["compile_success_rate"], x["avg_latency_s"]),
        )

        return CertificationReport(
            models_tested=len(models),
            total_prompts_per_model=len(prompts),
            results=certification_results,
            rankings=rankings,
        )

    async def certify_model(
        self,
        model_name: str,
        prompts: tuple[tuple[str, str], ...] | None = None,
        session: aiohttp.ClientSession | None = None,
    ) -> ModelCertificationResult:
        """Test a single model against all standard prompts.

        Parameters
        ----------
        model_name : str
            The Ollama model name to test.
        prompts : tuple of (label, prompt_text), optional
            Prompts to use; defaults to all 6 standard prompts.

        Returns
        -------
        ModelCertificationResult
        """
        if prompts is None:
            prompts = _STANDARD_PROMPTS

        # Lazy import to avoid circular issues and keep heavy deps out of module
        # scope until needed.
        from hlf_mcp.hlf.compiler import HLFCompiler
        from hlf_mcp.hlf.hlf_llm_bridge import HLFLLMBridge

        bridge = HLFLLMBridge(
            model=model_name,
            ollama_url=self.ollama_url,
            timeout_s=self.timeout,
            session=session,
        )
        compiler = HLFCompiler()

        per_prompt_results: list[dict[str, Any]] = []
        errors: list[str] = []
        compile_successes = 0
        total_latency = 0.0
        total_prompt_tokens = 0
        total_completion_tokens = 0

        for label, prompt_text in prompts:
            try:
                call_result = await bridge.send(prompt_text, model=model_name)

                # Compiler validation
                compile_success = False
                compile_error = ""
                if call_result.hlf_output:
                    try:
                        compiler.compile(call_result.hlf_output)
                        compile_success = True
                    except Exception as exc:
                        compile_error = str(exc)

                if compile_success:
                    compile_successes += 1

                total_latency += call_result.latency_s
                total_prompt_tokens += call_result.prompt_tokens
                total_completion_tokens += call_result.completion_tokens

                per_prompt_results.append(
                    {
                        "prompt_label": label,
                        "prompt_text": prompt_text,
                        "hlf_output": call_result.hlf_output[:500],  # truncate
                        "extracted": call_result.extracted,
                        "compile_success": compile_success,
                        "compile_error": compile_error,
                        "latency_s": call_result.latency_s,
                        "prompt_tokens": call_result.prompt_tokens,
                        "completion_tokens": call_result.completion_tokens,
                    }
                )

            except Exception as exc:
                logger.warning(
                    "Model '%s' failed on prompt '%s': %s",
                    model_name, label, exc,
                )
                errors.append(f"[{label}] {exc}")
                per_prompt_results.append(
                    {
                        "prompt_label": label,
                        "prompt_text": prompt_text,
                        "hlf_output": "",
                        "extracted": False,
                        "compile_success": False,
                        "compile_error": str(exc),
                        "latency_s": 0.0,
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                    }
                )

        prompt_count = len(prompts)
        return ModelCertificationResult(
            model_name=model_name,
            prompts_tested=prompt_count,
            compile_successes=compile_successes,
            compile_success_rate=compile_successes / prompt_count if prompt_count > 0 else 0.0,
            avg_latency_s=total_latency / prompt_count if prompt_count > 0 else 0.0,
            avg_prompt_tokens=int(total_prompt_tokens / prompt_count) if prompt_count > 0 else 0,
            avg_completion_tokens=int(total_completion_tokens / prompt_count) if prompt_count > 0 else 0,
            per_prompt_results=per_prompt_results,
            errors=errors,
        )


# ── Dynamic discovery helper ────────────────────────────────────────────────────


async def _discover_ollama_models(
    ollama_url: str,
    timeout: int = 30,
) -> list[str]:
    """Fetch model names from the Ollama ``/api/tags`` endpoint.

    Returns a sorted list of model name strings.
    """
    url = f"{ollama_url}/api/tags"
    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=timeout, connect=15)
        ) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.error(
                        "Ollama /api/tags returned %d: %s",
                        resp.status, text[:300],
                    )
                    return []
                data = await resp.json()
                return sorted(
                    [m["name"] for m in data.get("models", []) if m.get("name")]
                )
    except aiohttp.ClientError as exc:
        logger.error("Failed to connect to Ollama at %s: %s", ollama_url, exc)
        return []
    except asyncio.TimeoutError:
        logger.error("Timeout connecting to Ollama at %s", ollama_url)
        return []


# ── Filter helpers ──────────────────────────────────────────────────────────────


def _resolve_model_list(
    cli_models: str | None,
    env_key: str = "HLF_CERTIFY_MODELS",
) -> list[str] | None:
    """Resolve model filter from CLI arg or env var.

    Returns ``None`` if no filter is set (meaning: use all discovered models).
    Returns a list of model names if a filter is provided.
    """
    raw = cli_models or os.environ.get(env_key, "")
    if not raw.strip():
        return None
    parts = [m.strip() for m in raw.split(",") if m.strip()]
    return parts if parts else None


# ── CLI entry point ─────────────────────────────────────────────────────────────


def _build_argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="HLF Model Certification Runner — test Ollama models for HLF fluency",
    )
    parser.add_argument(
        "--models",
        type=str,
        default=None,
        help="Comma-separated model names to test (default: all discovered)",
    )
    parser.add_argument(
        "--prompt-count",
        type=int,
        default=None,
        help=f"Number of prompts to use (1-{len(_STANDARD_PROMPTS)}), default from env or 6",
    )
    parser.add_argument(
        "--ollama-url",
        type=str,
        default=None,
        help="Ollama base URL (default: http://localhost:11434, env: OLLAMA_HOST)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Timeout in seconds per model LLM call (default: 300)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output report as JSON instead of human-readable summary",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Write report to file instead of stdout",
    )
    return parser


async def _main() -> None:
    parser = _build_argparser()
    args = parser.parse_args()

    # Resolve Ollama URL
    ollama_url = args.ollama_url or os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    if ollama_url and not ollama_url.startswith(("http://", "https://")):
        ollama_url = f"http://{ollama_url}"

    # Resolve prompt count
    prompt_count_env = os.environ.get("HLF_CERTIFY_PROMPT_COUNT", "")
    if args.prompt_count is not None:
        prompt_count = args.prompt_count
    elif prompt_count_env.strip():
        prompt_count = int(prompt_count_env)
    else:
        prompt_count = 6
    prompt_count = max(1, min(prompt_count, len(_STANDARD_PROMPTS)))

    # Resolve model list
    model_list = _resolve_model_list(args.models)

    runner = ModelCertificationRunner(ollama_url=ollama_url, timeout=args.timeout)
    report = await runner.run_certification(models=model_list, prompt_count=prompt_count)

    output = json.dumps(report.to_dict(), indent=2) if args.json_output else report.summary()

    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output)
            print(f"Report written to {args.output}")
        except (OSError, IOError) as exc:
            logger.error("Failed to write report to %s: %s", args.output, exc)
            print(f"Error: Cannot write to {args.output}: {exc}", file=sys.stderr)
            print(output)  # still show report on stdout
    else:
        print(output)


def main() -> None:
    """Synchronous CLI entry point."""
    asyncio.run(_main())


if __name__ == "__main__":
    main()
