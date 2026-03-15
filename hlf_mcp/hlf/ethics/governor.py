"""
HLF Ethical Governor — main orchestrator.

Runs the full 4-layer pipeline against a compiled HLF program:

  Layer 0+1: Constitutional + legal constraints  (constitution.py)
  Layer 2:   Self-termination protocol           (termination.py)
  Layer 3:   Red-hat declaration handling        (red_hat.py)
  Layer 4:   Rogue agent detection               (rogue_detection.py)

The governor is invoked from the compiler pipeline (Pass 2.5) and from the
VM runtime before execution.  It is the single authoritative gate between
intent and execution.

Design guarantees:
  • FAILS CLOSED — any unhandled error triggers a safe termination.
  • TRANSPARENT  — all blocks cite the rule and documentation.
  • HUMAN-FIRST  — blocks are narrow; ambiguous cases pass with a warning.
  • NON-REDUCTIVE — no checks are ever silently removed without a code change.

People are the priority.  AI is the tool.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .constitution import evaluate_constitution, violations_to_strings, Violation
from .termination import terminate, should_terminate, TerminationResult, get_audit_log
from .red_hat import declare_research_intent, get_attestations, latest_attestation
from .rogue_detection import detect_rogue_signals, signals_require_termination, RogueSignal


# ── Result types ─────────────────────────────────────────────────────────────

@dataclass
class LayerResult:
    layer: str
    passed: bool
    violations: list[str] = field(default_factory=list)
    signals: list[RogueSignal] = field(default_factory=list)
    termination: TerminationResult | None = None


@dataclass
class GovernorResult:
    passed: bool
    layer_results: list[LayerResult] = field(default_factory=list)
    blocks: list[str] = field(default_factory=list)         # human-readable block reasons
    warnings: list[str] = field(default_factory=list)       # non-fatal advisories
    termination: TerminationResult | None = None
    audit_log: list[dict[str, Any]] = field(default_factory=list)

    def raise_if_blocked(self) -> None:
        """Raise a GovernorError if this result represents a hard block."""
        if not self.passed:
            msg = "HLF Ethical Governor blocked compilation:\n" + "\n".join(self.blocks)
            raise GovernorError(msg, result=self)


class GovernorError(Exception):
    """Raised by GovernorResult.raise_if_blocked() when execution must halt."""
    def __init__(self, message: str, result: GovernorResult | None = None) -> None:
        super().__init__(message)
        self.result = result


# ── Main governor ─────────────────────────────────────────────────────────────

class EthicalGovernor:
    """
    Single-instance ethical governor.

    Usage in compiler::

        governor = EthicalGovernor()
        result = governor.check(ast, env, source=source, tier="hearth")
        result.raise_if_blocked()   # raises GovernorError if hard block

    Or check without raising::

        if not result.passed:
            handle_block(result.blocks)
    """

    def __init__(self, strict: bool = True) -> None:
        """
        Args:
            strict: When True (default) any high-severity rogue signal is a hard
                    block.  When False, rogue signals become warnings (useful for
                    testing / local dev; NOT recommended for production).
        """
        self.strict = strict

    # ── Public entry point ────────────────────────────────────────────────────

    def check(
        self,
        ast: dict[str, Any] | None,
        env: dict[str, Any] | None,
        source: str = "",
        tier: str = "hearth",
        red_hat_metadata: dict[str, Any] | None = None,
    ) -> GovernorResult:
        """
        Run full 4-layer ethics check.

        Args:
            ast:               Compiled AST dict.
            env:               Compiler variable environment.
            source:            Raw HLF source for pattern analysis.
            tier:              Active capsule tier ('hearth' | 'forge' | 'sovereign').
            red_hat_metadata:  Optional security research declaration metadata.
                               If present, Layer 3 processes it before constitutional
                               checks run (declared research is treated as legitimate).

        Returns:
            GovernorResult.  Call .raise_if_blocked() to convert a block into an
            exception suitable for the compiler pipeline.
        """
        layer_results: list[LayerResult] = []
        blocks: list[str] = []
        warnings: list[str] = []
        final_termination: TerminationResult | None = None

        try:
            # ── Layer 3: Red-hat pre-processing ──────────────────────────────
            # Process declarations BEFORE constitutional checks so that a
            # properly declared research context is on record.
            rh_layer = self._run_red_hat(red_hat_metadata)
            layer_results.append(rh_layer)
            if not rh_layer.passed:
                warnings.extend(rh_layer.violations)  # declaration issues = warnings

            # ── Layer 4: Rogue agent detection ────────────────────────────────
            rogue_layer = self._run_rogue_detection(source, ast, tier)
            layer_results.append(rogue_layer)
            if not rogue_layer.passed:
                for sig in rogue_layer.signals:
                    block_msg = (
                        f"[{sig.rule_id}] {sig.signal_id} ({sig.severity}): "
                        f"{sig.description}"
                    )
                    if self.strict:
                        blocks.append(block_msg)
                    else:
                        warnings.append(block_msg)

            # ── Layer 0+1: Constitutional + legal ─────────────────────────────
            const_layer, term_result = self._run_constitutional(ast, env, source, tier)
            layer_results.append(const_layer)
            if not const_layer.passed:
                blocks.extend(const_layer.violations)
                final_termination = term_result

            # ── Layer 2: Self-termination decision ────────────────────────────
            term_layer = LayerResult(layer="termination", passed=True)
            if blocks:
                # Terminate on first hard block
                if final_termination is None:
                    final_termination = terminate(
                        trigger=_first_rule_id(blocks),
                        context={"source_excerpt": source[:200], "tier": tier},
                    )
                term_layer.passed = False
                term_layer.termination = final_termination
            layer_results.append(term_layer)

        except Exception as exc:  # noqa: BLE001
            # Fail closed — any unexpected error terminates
            emergency = terminate(
                "C-5",
                context={"error": str(exc), "source_excerpt": source[:100]},
            )
            return GovernorResult(
                passed=False,
                layer_results=layer_results,
                blocks=[f"Governor internal error (fail-closed): {exc}"],
                termination=emergency,
                audit_log=get_audit_log(),
            )

        passed = len(blocks) == 0
        return GovernorResult(
            passed=passed,
            layer_results=layer_results,
            blocks=blocks,
            warnings=warnings,
            termination=final_termination if not passed else None,
            audit_log=get_audit_log(),
        )

    # ── Layer runners ─────────────────────────────────────────────────────────

    def _run_red_hat(self, metadata: dict[str, Any] | None) -> LayerResult:
        if metadata is None:
            return LayerResult(layer="red_hat", passed=True)
        result = declare_research_intent(metadata)
        if result["valid"]:
            return LayerResult(layer="red_hat", passed=True)
        return LayerResult(
            layer="red_hat",
            passed=False,
            violations=[f"Red-hat declaration incomplete: {result['reason']}"],
        )

    def _run_rogue_detection(
        self,
        source: str,
        ast: dict[str, Any] | None,
        tier: str,
    ) -> LayerResult:
        signals = detect_rogue_signals(source=source, ast=ast, tier=tier)
        if not signals:
            return LayerResult(layer="rogue_detection", passed=True)
        requires_term = signals_require_termination(signals)
        if not requires_term:
            # Only medium/low signals — pass with advisory
            return LayerResult(
                layer="rogue_detection",
                passed=True,
                signals=signals,
                violations=[f"[advisory] {s.signal_id}: {s.description}" for s in signals],
            )
        return LayerResult(
            layer="rogue_detection",
            passed=False,
            signals=signals,
            violations=[f"{s.signal_id}: {s.description}" for s in signals],
        )

    def _run_constitutional(
        self,
        ast: dict[str, Any] | None,
        env: dict[str, Any] | None,
        source: str,
        tier: str,
    ) -> tuple[LayerResult, TerminationResult | None]:
        violations: list[Violation] = evaluate_constitution(
            ast=ast, env=env, source=source, tier=tier
        )
        if not violations:
            return LayerResult(layer="constitutional", passed=True), None

        hard_block = should_terminate(ast, violations)
        violation_strings = violations_to_strings(violations)

        if hard_block:
            # Terminate on first non-appealable violation
            first = next(v for v in violations if not v.appealable)
            term = terminate(
                trigger=first.rule_id or first.article,
                context={"source_excerpt": source[:200], "tier": tier},
            )
            return (
                LayerResult(layer="constitutional", passed=False, violations=violation_strings),
                term,
            )

        # All violations are appealable — soft warnings
        return (
            LayerResult(layer="constitutional", passed=True, violations=violation_strings),
            None,
        )


# ── Module-level singleton for compiler use ──────────────────────────────────

_default_governor = EthicalGovernor(strict=True)


def check(
    ast: dict[str, Any] | None,
    env: dict[str, Any] | None,
    source: str = "",
    tier: str = "hearth",
    red_hat_metadata: dict[str, Any] | None = None,
) -> GovernorResult:
    """Convenience wrapper using the default strict governor."""
    return _default_governor.check(
        ast=ast, env=env, source=source, tier=tier, red_hat_metadata=red_hat_metadata
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _first_rule_id(blocks: list[str]) -> str:
    """Extract the rule ID token from the first block message."""
    import re
    m = re.search(r"\[([A-Z0-9\-]+)\]", blocks[0]) if blocks else None
    return m.group(1) if m else "C-3"
