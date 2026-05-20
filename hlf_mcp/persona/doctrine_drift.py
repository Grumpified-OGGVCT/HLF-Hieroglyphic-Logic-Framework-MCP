"""
Doctrine Drift Detection — compares current agent behavior against persona
doctrine, flags deviations, and generates corrective HLF constraints.

Provides:
  - DoctrineDriftDetector: monitors agent behavior for doctrine drift
  - DriftReport: detailed deviation report with severity and corrective actions
  - DriftConstraint: HLF constraint to correct a specific drift

Integration points:
  - hlf_mcp.persona.operator_doctrine: OperatorDoctrine for contract definitions
  - hlf_mcp.persona.gate_integration: PersonaGate for constitutional checks
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# DriftConstraint — a single corrective HLF constraint
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class DriftConstraint:
    """A single HLF constraint to correct a detected doctrine drift.

    Attributes:
        constraint_id: Unique constraint identifier.
        persona: The persona affected.
        drifted_action: The action that drifted from doctrine.
        expected_rule: The doctrine rule that should have applied.
        severity: Drift severity (info / warning / critical).
        hlf_statement: Generated HLF constraint to correct the drift.
        generated_at: Timestamp of generation.
    """

    constraint_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    persona: str = ""
    drifted_action: str = ""
    expected_rule: str = ""
    severity: str = "warning"
    hlf_statement: str = ""
    generated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "constraint_id": self.constraint_id,
            "persona": self.persona,
            "drifted_action": self.drifted_action,
            "expected_rule": self.expected_rule,
            "severity": self.severity,
            "hlf_statement": self.hlf_statement,
            "generated_at": self.generated_at,
        }


# ---------------------------------------------------------------------------
# DriftReport — full drift detection report
# ---------------------------------------------------------------------------


@dataclass
class DriftReport:
    """Detailed report of doctrine drift detection for a persona.

    Attributes:
        report_id: Unique report identifier.
        persona: The persona being analyzed.
        drift_detected: Whether any drift was found.
        total_actions_analyzed: Number of actions evaluated.
        drifted_actions: Actions that deviated from doctrine.
        compliant_actions: Actions that matched doctrine.
        constraints: Generated corrective HLF constraints.
        severity_counts: Counts by severity level.
        analyzed_at: Timestamp of analysis.
    """

    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    persona: str = ""
    drift_detected: bool = False
    total_actions_analyzed: int = 0
    drifted_actions: list[dict[str, Any]] = field(default_factory=list)
    compliant_actions: list[str] = field(default_factory=list)
    constraints: list[DriftConstraint] = field(default_factory=list)
    severity_counts: dict[str, int] = field(default_factory=dict)
    analyzed_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "persona": self.persona,
            "drift_detected": self.drift_detected,
            "total_actions_analyzed": self.total_actions_analyzed,
            "drifted_actions": list(self.drifted_actions),
            "compliant_actions": list(self.compliant_actions),
            "constraints": [c.to_dict() for c in self.constraints],
            "severity_counts": dict(self.severity_counts),
            "analyzed_at": self.analyzed_at,
        }


# ---------------------------------------------------------------------------
# DoctrineDriftDetector — monitors and detects doctrine drift
# ---------------------------------------------------------------------------


class DoctrineDriftDetector:
    """Detects when agent behavior drifts from persona doctrine contracts.

    Compares observed agent actions against the doctrine's permissions,
    obligations, and prohibitions.  Flags actions that violate doctrine
    and generates corrective HLF constraints to realign behavior.

    Usage::

        detector = DoctrineDriftDetector()
        report = detector.analyze_behavior(
            persona="steward",
            observed_actions=["review_tool_contracts", "auto_apply_changes"],
        )
        if report.drift_detected:
            for constraint in report.constraints:
                print(constraint.hlf_statement)
    """

    def __init__(
        self,
        doctrine: Any = None,  # OperatorDoctrine (lazy import)
        drift_threshold: float = 0.1,
        max_history_actions: int = 1000,
    ) -> None:
        self._doctrine = doctrine
        self._drift_threshold = drift_threshold
        self._max_history = max_history_actions
        self._action_history: dict[str, list[dict[str, Any]]] = {}
        self._drift_reports: list[DriftReport] = []
        self._constraint_library: dict[str, DriftConstraint] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_action(
        self,
        persona: str,
        action: str,
        success: bool = True,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Record an observed agent action for later drift analysis.

        Args:
            persona: The persona performing the action.
            action: The action identifier.
            success: Whether the action completed successfully.
            context: Optional context dict.
        """
        p = persona.strip().lower()
        if p not in self._action_history:
            self._action_history[p] = []

        entry = {
            "action": action,
            "success": success,
            "timestamp": time.time(),
            "context": dict(context or {}),
        }
        self._action_history[p].append(entry)

        # Trim history if over max
        if len(self._action_history[p]) > self._max_history:
            self._action_history[p] = self._action_history[p][-self._max_history:]

    def analyze_behavior(
        self,
        persona: str,
        observed_actions: list[str] | None = None,
        context: dict[str, Any] | None = None,
    ) -> DriftReport:
        """Analyze observed behavior for doctrine drift.

        If observed_actions is provided, those actions are analyzed directly.
        Otherwise, the accumulated action history for the persona is used.

        Args:
            persona: The persona to analyze.
            observed_actions: Optional explicit list of actions to check.
            context: Optional context for compliance validation.

        Returns:
            DriftReport with drift detection results and corrective constraints.
        """
        p = persona.strip().lower()
        ctx = context or {}

        # Load doctrine if not provided
        doctrine = self._get_doctrine()
        contract = doctrine.get_contract(p) if doctrine else None

        # Determine actions to analyze
        if observed_actions is not None:
            actions = list(observed_actions)
        else:
            history = self._action_history.get(p, [])
            actions = [entry["action"] for entry in history]

        drifted: list[dict[str, Any]] = []
        compliant: list[str] = []
        constraints: list[DriftConstraint] = []
        severity_counts: dict[str, int] = {"info": 0, "warning": 0, "critical": 0}

        for action in actions:
            if contract is None:
                # No contract — all actions are drift
                drifted.append({
                    "action": action,
                    "reason": "no_doctrine_contract",
                    "severity": "critical",
                })
                severity_counts["critical"] += 1
                constraint = self._generate_constraint(
                    p, action, "unknown_persona", "critical"
                )
                constraints.append(constraint)
                continue

            # Check compliance
            report = doctrine.validate_compliance(p, action, ctx)

            if report.allowed:
                compliant.append(action)
            else:
                severity = self._determine_severity(action, report.matched_rule, contract)
                drifted.append({
                    "action": action,
                    "reason": report.block_reason,
                    "matched_rule": report.matched_rule,
                    "severity": severity,
                })
                severity_counts[severity] += 1

                constraint = self._generate_constraint(
                    p, action, report.matched_rule, severity
                )
                constraints.append(constraint)

        drift_detected = len(drifted) > 0

        report = DriftReport(
            persona=p,
            drift_detected=drift_detected,
            total_actions_analyzed=len(actions),
            drifted_actions=drifted,
            compliant_actions=compliant,
            constraints=constraints,
            severity_counts=severity_counts,
        )
        self._drift_reports.append(report)
        return report

    def analyze_all_personas(self) -> dict[str, DriftReport]:
        """Run drift analysis for all personas with recorded history.

        Returns:
            Dict mapping persona name to DriftReport.
        """
        doctrine = self._get_doctrine()
        results: dict[str, DriftReport] = {}

        personas = set(self._action_history.keys())
        if doctrine is not None:
            personas.update(doctrine.all_personas())

        for persona in sorted(personas):
            results[persona] = self.analyze_behavior(persona)

        return results

    def generate_corrective_hlf(self, report: DriftReport) -> str:
        """Generate a complete HLF source string to correct all drifts in a report.

        Args:
            report: The drift report to generate corrections for.

        Returns:
            HLF source string with corrective constraint blocks.
        """
        if not report.drift_detected or not report.constraints:
            return (
                f"// ── No drift detected for persona '{report.persona}' ──\n"
                f"// All {report.total_actions_analyzed} actions compliant.\n"
            )

        lines: list[str] = [
            f"// ── Drift Correction HLF for persona '{report.persona}' ──",
            f"// Generated: {time.strftime('%Y-%m-%dT%H:%M:%S')}",
            f"// Drifted actions: {len(report.drifted_actions)}",
            f"// Compliant actions: {len(report.compliant_actions)}",
            "",
        ]

        for constraint in report.constraints:
            lines.append(
                f"// Drift: {constraint.drifted_action} "
                f"[{constraint.severity}] → {constraint.expected_rule}"
            )
            lines.append(constraint.hlf_statement)
            lines.append("")

        return "\n".join(lines)

    def get_drift_history(self, persona: str | None = None) -> list[DriftReport]:
        """Get drift reports, optionally filtered by persona.

        Args:
            persona: Optional persona filter.

        Returns:
            List of DriftReports.
        """
        if persona is not None:
            p = persona.strip().lower()
            return [r for r in self._drift_reports if r.persona == p]
        return list(self._drift_reports)

    def get_drift_summary(self) -> dict[str, Any]:
        """Return a summary of all detected drift across personas."""
        if not self._drift_reports:
            return {
                "total_reports": 0,
                "personas_with_drift": [],
                "total_drifted_actions": 0,
                "total_constraints_generated": 0,
                "severity_totals": {},
            }

        personas_with_drift = set()
        total_drifted = 0
        total_constraints = 0
        severity_totals: dict[str, int] = {}

        for report in self._drift_reports:
            if report.drift_detected:
                personas_with_drift.add(report.persona)
            total_drifted += len(report.drifted_actions)
            total_constraints += len(report.constraints)
            for sev, count in report.severity_counts.items():
                severity_totals[sev] = severity_totals.get(sev, 0) + count

        return {
            "total_reports": len(self._drift_reports),
            "personas_with_drift": sorted(personas_with_drift),
            "total_drifted_actions": total_drifted,
            "total_constraints_generated": total_constraints,
            "severity_totals": severity_totals,
        }

    def get_action_history(
        self, persona: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Get recent action history for a persona.

        Args:
            persona: The persona to query.
            limit: Maximum number of entries to return.

        Returns:
            List of action history entries (most recent first).
        """
        p = persona.strip().lower()
        history = self._action_history.get(p, [])
        return list(reversed(history[-limit:]))

    def clear_history(self, persona: str | None = None) -> None:
        """Clear action history, optionally for a specific persona.

        Args:
            persona: Optional persona to clear. If None, clears all.
        """
        if persona is not None:
            self._action_history.pop(persona.strip().lower(), None)
        else:
            self._action_history.clear()

    def clear_reports(self) -> None:
        """Clear all drift reports."""
        self._drift_reports.clear()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _get_doctrine(self) -> Any:
        """Lazy-load the OperatorDoctrine if not provided."""
        if self._doctrine is not None:
            return self._doctrine
        from hlf_mcp.persona.operator_doctrine import build_operator_doctrine

        self._doctrine = build_operator_doctrine()
        return self._doctrine

    def _determine_severity(
        self,
        action: str,
        matched_rule: str,
        contract: Any,  # DoctrineContract
    ) -> str:
        """Determine the severity of a drifted action.

        Critical: explicit prohibition violation
        Warning: no explicit permission, unknown action
        Info: obligation not matched (but not prohibited)
        """
        if "prohibition" in matched_rule:
            return "critical"
        if "no_explicit_permission" in matched_rule:
            return "warning"
        if "unknown_persona" in matched_rule:
            return "critical"
        return "info"

    def _generate_constraint(
        self,
        persona: str,
        action: str,
        matched_rule: str,
        severity: str,
    ) -> DriftConstraint:
        """Generate a corrective HLF constraint for a drifted action."""
        constraint_id = str(uuid.uuid4())

        if "prohibition" in matched_rule:
            rule_name = matched_rule.split(":", 1)[1] if ":" in matched_rule else matched_rule
            hlf_statement = (
                f"@tier(hearth)\n"
                f"@validate(drift_correction=\"{constraint_id}\")\n"
                f"capsule drift_fix_{persona}_{action} {{\n"
                f"  @must_not(\"{action}\")  // Re-affirming prohibition: {rule_name}\n"
                f"  @escalate_to(\"operator\")\n"
                f"}}"
            )
        elif "no_explicit_permission" in matched_rule:
            hlf_statement = (
                f"@tier(hearth)\n"
                f"@validate(drift_correction=\"{constraint_id}\")\n"
                f"capsule drift_fix_{persona}_{action} {{\n"
                f"  @must_not(\"{action}\")  // Blocking unpermitted action for {persona}\n"
                f"  @require_approval(\"operator\")\n"
                f"}}"
            )
        else:
            hlf_statement = (
                f"@tier(hearth)\n"
                f"@validate(drift_correction=\"{constraint_id}\")\n"
                f"capsule drift_fix_{persona}_{action} {{\n"
                f"  @review(\"{action}\")  // Review required for drift correction\n"
                f"  @escalate_to(\"operator\")\n"
                f"}}"
            )

        constraint = DriftConstraint(
            constraint_id=constraint_id,
            persona=persona,
            drifted_action=action,
            expected_rule=matched_rule,
            severity=severity,
            hlf_statement=hlf_statement,
        )
        self._constraint_library[constraint_id] = constraint
        return constraint
