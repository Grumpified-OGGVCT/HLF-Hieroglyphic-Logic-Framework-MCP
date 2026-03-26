"""Response validation layer for model substrate completions.

Every model response — Ollama Cloud (primary) and OpenRouter (fallback) —
must pass through validation before being accepted as trustworthy output
for the knowledge substrate.

Validation tiers:
  - structural: response is well-formed, non-empty, model field present
  - model_fidelity: the model that answered matches what was requested
  - completeness: response was not truncated (done_reason != "length")
  - token_sanity: token counts are internally consistent
  - governed: all of the above, plus stricter thresholds for knowledge paths

Design: Ollama is the primary provider and receives the same scrutiny as
OpenRouter. Neither provider's output is trusted without validation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ── types ────────────────────────────────────────────────────────────────────


class ValidationSeverity(Enum):
    """How serious is the validation finding."""

    INFO = "info"  # Worth logging but not blocking
    WARNING = "warning"  # Suspicious, may degrade quality
    REJECT = "reject"  # Response is not trustworthy


@dataclass(slots=True, frozen=True)
class ValidationFinding:
    """A single validation check result."""

    check: str
    severity: ValidationSeverity
    detail: str


@dataclass(slots=True)
class ValidationResult:
    """Aggregate validation result for a response."""

    passed: bool
    findings: list[ValidationFinding] = field(default_factory=list)
    model_requested: str = ""
    model_returned: str = ""
    provider: str = ""

    @property
    def has_warnings(self) -> bool:
        return any(f.severity == ValidationSeverity.WARNING for f in self.findings)

    @property
    def has_rejections(self) -> bool:
        return any(f.severity == ValidationSeverity.REJECT for f in self.findings)

    @property
    def rejection_reasons(self) -> list[str]:
        return [f.detail for f in self.findings if f.severity == ValidationSeverity.REJECT]

    @property
    def warning_reasons(self) -> list[str]:
        return [f.detail for f in self.findings if f.severity == ValidationSeverity.WARNING]


# ── configuration ────────────────────────────────────────────────────────────


@dataclass(slots=True, frozen=True)
class ValidationConfig:
    """Controls how strict validation is.

    Defaults are tuned for governed knowledge paths — maximum scrutiny.
    For non-governed paths, callers can relax thresholds.
    """

    # Structural
    require_non_empty_content: bool = True
    min_content_chars: int = 1

    # Model fidelity
    require_model_match: bool = True
    # Ollama normalizes model names — e.g. "nemotron-3-super" might return
    # "nemotron-3-super:latest". Allow prefix matching by default.
    allow_ollama_tag_suffix: bool = True

    # Completeness
    reject_on_truncation: bool = True  # done_reason == "length"
    warn_on_missing_done: bool = True

    # Token sanity
    require_nonzero_tokens: bool = True
    # Ratio: completion_tokens / prompt_tokens — if absurdly low, model
    # may have refused or produced a trivial response
    min_completion_ratio: float = 0.0  # 0 = disabled
    max_completion_tokens: int = 0  # 0 = no cap

    # OpenRouter-specific
    reject_autorouter_responses: bool = True  # governed default


# ── validators ───────────────────────────────────────────────────────────────


def validate_ollama_response(
    response: dict[str, Any],
    model_requested: str,
    config: ValidationConfig | None = None,
) -> ValidationResult:
    """Validate a raw Ollama Cloud API response dict.

    Ollama returns:
      {
        "model": "nemotron-3-super:latest",
        "message": {"role": "assistant", "content": "..."},
        "done": true,
        "done_reason": "stop",
        "total_duration": ...,
        "prompt_eval_count": 42,
        "eval_count": 128,
        ...
      }
    """
    cfg = config or ValidationConfig()
    findings: list[ValidationFinding] = []

    # ── structural ───────────────────────────────────────────────────────

    message = response.get("message", {})
    content = str(message.get("content", ""))

    if cfg.require_non_empty_content and len(content.strip()) < cfg.min_content_chars:
        findings.append(ValidationFinding(
            check="empty_content",
            severity=ValidationSeverity.REJECT,
            detail=f"Response content is empty or below minimum "
                   f"({len(content.strip())} < {cfg.min_content_chars} chars)",
        ))

    if "message" not in response:
        findings.append(ValidationFinding(
            check="missing_message",
            severity=ValidationSeverity.REJECT,
            detail="Response has no 'message' field",
        ))

    # ── model fidelity ───────────────────────────────────────────────────

    model_returned = str(response.get("model", ""))

    if cfg.require_model_match and model_returned:
        match = _ollama_model_match(model_requested, model_returned, cfg.allow_ollama_tag_suffix)
        if not match:
            findings.append(ValidationFinding(
                check="model_mismatch",
                severity=ValidationSeverity.REJECT,
                detail=f"Model mismatch: requested='{model_requested}', "
                       f"returned='{model_returned}'",
            ))

    if not model_returned:
        findings.append(ValidationFinding(
            check="missing_model",
            severity=ValidationSeverity.WARNING,
            detail="Response has no 'model' field",
        ))

    # ── completeness ─────────────────────────────────────────────────────

    done = response.get("done")
    done_reason = str(response.get("done_reason", ""))

    if done is False:
        findings.append(ValidationFinding(
            check="incomplete_response",
            severity=ValidationSeverity.REJECT,
            detail="Response 'done' is False — stream was not completed",
        ))

    if done is None and cfg.warn_on_missing_done:
        findings.append(ValidationFinding(
            check="missing_done",
            severity=ValidationSeverity.WARNING,
            detail="Response has no 'done' field",
        ))

    if done_reason == "length" and cfg.reject_on_truncation:
        findings.append(ValidationFinding(
            check="truncated",
            severity=ValidationSeverity.REJECT,
            detail="Response was truncated (done_reason='length') — "
                   "context window or max_tokens exceeded",
        ))
    elif done_reason == "length":
        findings.append(ValidationFinding(
            check="truncated",
            severity=ValidationSeverity.WARNING,
            detail="Response was truncated (done_reason='length')",
        ))

    # ── token sanity ─────────────────────────────────────────────────────

    prompt_tokens = int(response.get("prompt_eval_count", 0))
    completion_tokens = int(response.get("eval_count", 0))

    if cfg.require_nonzero_tokens and completion_tokens == 0 and content.strip():
        findings.append(ValidationFinding(
            check="zero_eval_count",
            severity=ValidationSeverity.WARNING,
            detail="eval_count is 0 but content is non-empty — token counting may be broken",
        ))

    if cfg.require_nonzero_tokens and prompt_tokens == 0:
        findings.append(ValidationFinding(
            check="zero_prompt_eval",
            severity=ValidationSeverity.WARNING,
            detail="prompt_eval_count is 0 — prompt may not have been evaluated",
        ))

    if (
        cfg.min_completion_ratio > 0
        and prompt_tokens > 0
        and completion_tokens > 0
        and (completion_tokens / prompt_tokens) < cfg.min_completion_ratio
    ):
        ratio = completion_tokens / prompt_tokens
        findings.append(ValidationFinding(
            check="low_completion_ratio",
            severity=ValidationSeverity.WARNING,
            detail=f"Suspiciously low completion ratio: {ratio:.3f} "
                   f"({completion_tokens}/{prompt_tokens})",
        ))

    if cfg.max_completion_tokens > 0 and completion_tokens > cfg.max_completion_tokens:
        findings.append(ValidationFinding(
            check="excess_tokens",
            severity=ValidationSeverity.WARNING,
            detail=f"Completion tokens ({completion_tokens}) exceed cap ({cfg.max_completion_tokens})",
        ))

    # ── final verdict ────────────────────────────────────────────────────

    has_rejection = any(f.severity == ValidationSeverity.REJECT for f in findings)
    passed = not has_rejection

    result = ValidationResult(
        passed=passed,
        findings=findings,
        model_requested=model_requested,
        model_returned=model_returned,
        provider="ollama_cloud",
    )

    if not passed:
        logger.warning(
            "Ollama response validation FAILED for %s: %s",
            model_requested, result.rejection_reasons,
        )
    elif result.has_warnings:
        logger.info(
            "Ollama response validation PASSED with warnings for %s: %s",
            model_requested, result.warning_reasons,
        )

    return result


def validate_openrouter_response(
    result: Any,
    model_requested: str,
    config: ValidationConfig | None = None,
) -> ValidationResult:
    """Validate an OpenRouter ChatResult object.

    ChatResult has: content, model_used, model_requested, finish_reason,
    prompt_tokens, completion_tokens, total_tokens, etc.
    """
    cfg = config or ValidationConfig()
    findings: list[ValidationFinding] = []

    content = getattr(result, "content", "") or ""
    model_returned = getattr(result, "model_used", "") or ""

    # ── structural ───────────────────────────────────────────────────────

    if cfg.require_non_empty_content and len(content.strip()) < cfg.min_content_chars:
        findings.append(ValidationFinding(
            check="empty_content",
            severity=ValidationSeverity.REJECT,
            detail=f"Response content is empty or below minimum "
                   f"({len(content.strip())} < {cfg.min_content_chars} chars)",
        ))

    # ── model fidelity ───────────────────────────────────────────────────

    if cfg.require_model_match and model_returned and model_requested:
        if model_returned != model_requested:
            # Check if this is an autorouter situation
            if cfg.reject_autorouter_responses and model_requested in (
                "openrouter/auto", "openrouter/free",
            ):
                findings.append(ValidationFinding(
                    check="autorouter_response",
                    severity=ValidationSeverity.REJECT,
                    detail=f"Autorouter used (requested='{model_requested}', "
                           f"routed to='{model_returned}') — not permitted "
                           "on governed paths",
                ))
            else:
                # Non-autorouter mismatch — provider re-routed
                findings.append(ValidationFinding(
                    check="model_mismatch",
                    severity=ValidationSeverity.WARNING,
                    detail=f"Model mismatch: requested='{model_requested}', "
                           f"returned='{model_returned}'",
                ))

    # ── completeness ─────────────────────────────────────────────────────

    finish_reason = getattr(result, "finish_reason", "") or ""

    if finish_reason == "length" and cfg.reject_on_truncation:
        findings.append(ValidationFinding(
            check="truncated",
            severity=ValidationSeverity.REJECT,
            detail="Response was truncated (finish_reason='length')",
        ))
    elif finish_reason == "length":
        findings.append(ValidationFinding(
            check="truncated",
            severity=ValidationSeverity.WARNING,
            detail="Response was truncated (finish_reason='length')",
        ))

    # ── token sanity ─────────────────────────────────────────────────────

    prompt_tokens = getattr(result, "prompt_tokens", 0) or 0
    completion_tokens = getattr(result, "completion_tokens", 0) or 0

    if cfg.require_nonzero_tokens and completion_tokens == 0 and content.strip():
        findings.append(ValidationFinding(
            check="zero_completion_tokens",
            severity=ValidationSeverity.WARNING,
            detail="completion_tokens is 0 but content is non-empty",
        ))

    if (
        cfg.min_completion_ratio > 0
        and prompt_tokens > 0
        and completion_tokens > 0
        and (completion_tokens / prompt_tokens) < cfg.min_completion_ratio
    ):
        ratio = completion_tokens / prompt_tokens
        findings.append(ValidationFinding(
            check="low_completion_ratio",
            severity=ValidationSeverity.WARNING,
            detail=f"Suspiciously low completion ratio: {ratio:.3f}",
        ))

    # ── final verdict ────────────────────────────────────────────────────

    has_rejection = any(f.severity == ValidationSeverity.REJECT for f in findings)
    passed = not has_rejection

    vr = ValidationResult(
        passed=passed,
        findings=findings,
        model_requested=model_requested,
        model_returned=model_returned,
        provider="openrouter",
    )

    if not passed:
        logger.warning(
            "OpenRouter response validation FAILED for %s: %s",
            model_requested, vr.rejection_reasons,
        )
    elif vr.has_warnings:
        logger.info(
            "OpenRouter response validation PASSED with warnings for %s: %s",
            model_requested, vr.warning_reasons,
        )

    return vr


# ── helpers ──────────────────────────────────────────────────────────────────


def _ollama_model_match(
    requested: str,
    returned: str,
    allow_tag_suffix: bool = True,
) -> bool:
    """Check if an Ollama model name matches.

    Ollama normalizes model names by appending `:latest` or other tags.
    Examples:
      requested="nemotron-3-super"  returned="nemotron-3-super:latest"  → match
      requested="cogito-2.1:671b-cloud"  returned="cogito-2.1:671b-cloud"  → match
      requested="qwen3.5:cloud"  returned="qwen3.5:cloud"  → match
      requested="nemotron-3-super"  returned="totally-different"  → no match
    """
    if requested == returned:
        return True

    if allow_tag_suffix:
        # Ollama often appends ":latest" to bare names
        if returned == f"{requested}:latest":
            return True
        # Or requested already has a tag and returned matches the base
        req_base = requested.split(":")[0]
        ret_base = returned.split(":")[0]
        if req_base == ret_base:
            return True

    return False


# ── governed convenience ─────────────────────────────────────────────────────


# Pre-built config for governed knowledge paths — strictest settings
GOVERNED_VALIDATION = ValidationConfig(
    require_non_empty_content=True,
    min_content_chars=1,
    require_model_match=True,
    allow_ollama_tag_suffix=True,
    reject_on_truncation=True,
    warn_on_missing_done=True,
    require_nonzero_tokens=True,
    reject_autorouter_responses=True,
)

# Relaxed config for non-governed general completions
RELAXED_VALIDATION = ValidationConfig(
    require_non_empty_content=True,
    min_content_chars=1,
    require_model_match=False,
    allow_ollama_tag_suffix=True,
    reject_on_truncation=False,
    warn_on_missing_done=False,
    require_nonzero_tokens=False,
    reject_autorouter_responses=False,
)
