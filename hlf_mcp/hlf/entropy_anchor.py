from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from typing import Any

from hlf_mcp.hlf import insaits


DEFAULT_THRESHOLD = 0.5
HIGH_RISK_THRESHOLD = 0.65
POLICY_MODES = {"advisory", "enforce", "high_risk_enforce"}


@dataclass(slots=True)
class EntropyAnchorResult:
    status: str
    source_hash: str
    baseline_source: str
    baseline_text: str
    compiled_program_summary: str
    translation_summary: str
    similarity_score: float
    threshold: float
    drift_detected: bool
    policy_mode: str
    policy_action: str
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def audit_payload(self) -> dict[str, Any]:
        return {
            "source_hash": self.source_hash,
            "baseline_source": self.baseline_source,
            "similarity_score": self.similarity_score,
            "threshold": self.threshold,
            "drift_detected": self.drift_detected,
            "policy_mode": self.policy_mode,
            "policy_action": self.policy_action,
        }


def _resolve_threshold(policy_mode: str, threshold: float | None) -> float:
    if policy_mode not in POLICY_MODES:
        raise ValueError(
            f"policy_mode must be one of {sorted(POLICY_MODES)}, got {policy_mode!r}"
        )
    effective_threshold = HIGH_RISK_THRESHOLD if policy_mode == "high_risk_enforce" else DEFAULT_THRESHOLD
    if threshold is not None:
        effective_threshold = threshold
    if not 0.0 <= effective_threshold <= 1.0:
        raise ValueError("threshold must be between 0.0 and 1.0")
    return round(effective_threshold, 4)


def _resolve_baseline_text(
    *,
    source: str,
    ast: dict[str, Any],
    expected_intent: str,
) -> tuple[str, str]:
    cleaned_expected_intent = expected_intent.strip()
    if cleaned_expected_intent:
        return "expected_intent", cleaned_expected_intent

    compiled_summary = str(ast.get("human_readable") or "").strip()
    if compiled_summary:
        return "compiler_human_readable", compiled_summary

    return "source_fallback", source.strip()


def _policy_action(*, drift_detected: bool, policy_mode: str) -> str:
    if not drift_detected:
        return "allow"
    if policy_mode == "advisory":
        return "warn"
    if policy_mode == "high_risk_enforce":
        return "halt_branch"
    return "escalate_hitl"


def evaluate_entropy_anchor(
    *,
    source: str,
    ast: dict[str, Any],
    expected_intent: str = "",
    threshold: float | None = None,
    policy_mode: str = "advisory",
) -> EntropyAnchorResult:
    effective_threshold = _resolve_threshold(policy_mode, threshold)
    baseline_source, baseline_text = _resolve_baseline_text(
        source=source,
        ast=ast,
        expected_intent=expected_intent,
    )
    translation_summary = insaits.decompile(ast)
    similarity = insaits.similarity_gate(
        baseline_text,
        translation_summary,
        threshold=effective_threshold,
    )
    drift_detected = not bool(similarity["passed"])
    return EntropyAnchorResult(
        status="ok",
        source_hash=hashlib.sha256(source.encode("utf-8")).hexdigest(),
        baseline_source=baseline_source,
        baseline_text=baseline_text,
        compiled_program_summary=str(ast.get("human_readable") or ""),
        translation_summary=translation_summary,
        similarity_score=float(similarity["similarity"]),
        threshold=float(similarity["threshold"]),
        drift_detected=drift_detected,
        policy_mode=policy_mode,
        policy_action=_policy_action(drift_detected=drift_detected, policy_mode=policy_mode),
        details=similarity,
    )