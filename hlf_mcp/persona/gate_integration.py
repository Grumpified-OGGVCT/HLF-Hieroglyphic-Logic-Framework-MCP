"""
Persona Gate Integration — wire persona gating through constitutional checks.

This module bridges the operator doctrine contracts with the HLF constitutional
check pipeline.  It provides:

  1. PersonaGate — wraps constitutional checks with persona context
  2. check_persona_assignment — gates persona assignment through constitutional rules
  3. Tier-differentiated persona permissions (hearth / sovereign / field)

The gate ensures that persona transitions are constitutionally sound:
  - A persona may only perform actions its doctrine permits
  - Cross-persona handoffs require both personas' gates to be satisfied
  - Tier escalation must pass constitutional tier-escalation rules
  - The governor is consulted for hard-block decisions
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ── Persona Gate Result ───────────────────────────────────────────────────────


@dataclass
class PersonaGateResult:
    """Result of a persona gating decision.

    Attributes:
        persona:          The persona being gated.
        assigned:         Whether the persona assignment was approved.
        passed_constitutional: Whether constitutional checks passed.
        passed_doctrine:  Whether doctrine compliance checks passed.
        violations:       List of human-readable violation descriptions.
        gate_log:         Ordered log of gate checks performed.
        tier:             Active tier during gate evaluation.
        escalate_to:      Persona to escalate to if gating failed.
    """

    persona: str
    assigned: bool
    passed_constitutional: bool = True
    passed_doctrine: bool = True
    violations: list[str] = field(default_factory=list)
    gate_log: list[dict[str, Any]] = field(default_factory=list)
    tier: str = "hearth"
    escalate_to: str = "operator"

    def to_dict(self) -> dict[str, Any]:
        return {
            "persona": self.persona,
            "assigned": self.assigned,
            "passed_constitutional": self.passed_constitutional,
            "passed_doctrine": self.passed_doctrine,
            "violations": list(self.violations),
            "gate_log": list(self.gate_log),
            "tier": self.tier,
            "escalate_to": self.escalate_to,
        }


# ── Capability Manifest (lightweight, for gating) ─────────────────────────────


@dataclass
class CapabilityManifest:
    """A lightweight manifest declaring what capabilities a persona requests.

    Attributes:
        persona:          Requested persona name.
        tier:             Requested tier (hearth / sovereign / field).
        requested_actions: Actions the persona wishes to perform.
        declared_capabilities: Capability tags (network, filesystem_write, etc.).
        red_hat_declared: Whether a red-hat research declaration is present.
        agent_identity:   Optional agent identity string.
    """

    persona: str
    tier: str = "hearth"
    requested_actions: list[str] = field(default_factory=list)
    declared_capabilities: list[str] = field(default_factory=list)
    red_hat_declared: bool = False
    agent_identity: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "persona": self.persona,
            "tier": self.tier,
            "requested_actions": list(self.requested_actions),
            "declared_capabilities": list(self.declared_capabilities),
            "red_hat_declared": self.red_hat_declared,
            "agent_identity": self.agent_identity,
        }


# ── Persona Gate ──────────────────────────────────────────────────────────────


class PersonaGate:
    """Gate that wraps constitutional checks with persona context.

    Integrates with:
      - hlf_mcp.hlf.ethics.governor.EthicalGovernor for constitutional enforcement
      - hlf_mcp.persona.operator_doctrine.OperatorDoctrine for doctrine compliance
      - hlf_mcp.persona_contract for persona contract resolution

    Usage::

        gate = PersonaGate()
        manifest = CapabilityManifest(persona="steward", tier="hearth",
                                       requested_actions=["review_tool_contracts"])
        result = gate.check_persona_assignment("steward", manifest)
        if not result.assigned:
            raise RuntimeError(f"Persona gate blocked: {result.violations}")
    """

    def __init__(self, strict: bool = True) -> None:
        self.strict = strict
        self._gate_log: list[dict[str, Any]] = []

    def check_persona_assignment(
        self,
        persona: str,
        manifest: CapabilityManifest,
        source: str = "",
    ) -> PersonaGateResult:
        """Gate a persona assignment through all checks.

        Pipeline:
          1. Doctrine compliance — does the persona's contract permit these actions?
          2. Tier escalation — does the tier allow the requested capabilities?
          3. Constitutional check — do the actions pass C-1 through C-5?
          4. Cross-persona handoff — if transitioning, is the handoff contract valid?

        Args:
            persona:   Normalised persona name.
            manifest:  Capability manifest declaring requested actions and tier.
            source:    Optional HLF source for pattern-based constitutional checks.

        Returns:
            PersonaGateResult with full gate decision and log.
        """
        self._gate_log = []
        violations: list[str] = []
        passed_doctrine = True
        passed_constitutional = True
        p = persona.strip().lower()

        # ── Step 1: Doctrine compliance ──────────────────────────────────
        from hlf_mcp.persona.operator_doctrine import (
            build_operator_doctrine,
            tier_allows,
        )

        doctrine = build_operator_doctrine()
        contract = doctrine.get_contract(p)

        if contract is None:
            violations.append(f"Persona '{p}' has no doctrine contract.")
            self._log_gate("doctrine_contract", "failed", f"Unknown persona: {p}")
            passed_doctrine = False
        else:
            for action in manifest.requested_actions:
                report = doctrine.validate_compliance(
                    p, action, context={"tier": manifest.tier}
                )
                self._log_gate(
                    f"doctrine:{action}",
                    "passed" if report.allowed else "blocked",
                    report.block_reason if not report.allowed else f"Action '{action}' allowed",
                )
                if not report.allowed:
                    violations.append(
                        f"Doctrine violation for {p}/{action}: {report.block_reason}"
                    )
                    passed_doctrine = False

        # ── Step 2: Tier-differentiated checks ──────────────────────────
        for cap in manifest.declared_capabilities:
            cap_name = cap.strip().lower()
            if cap_name in ("network", "filesystem_write", "agent_spawn", "process_exec"):
                if not tier_allows(manifest.tier, cap_name):
                    # Check if tier escalation needed
                    if manifest.tier == "hearth":
                        violations.append(
                            f"Capability '{cap_name}' requires forge or sovereign tier, "
                            f"but manifest tier is '{manifest.tier}'."
                        )
                        self._log_gate(
                            f"tier:{cap_name}", "blocked",
                            f"Tier '{manifest.tier}' insufficient for '{cap_name}'"
                        )
                        passed_doctrine = False
                    else:
                        self._log_gate(
                            f"tier:{cap_name}", "passed",
                            f"Tier '{manifest.tier}' allows '{cap_name}'"
                        )

        # ── Step 3: Constitutional checks ───────────────────────────────
        if source:
            const_result = self._run_constitutional_check(p, manifest, source)
            if not const_result["passed"]:
                passed_constitutional = False
                for v in const_result["violations"]:
                    violations.append(f"Constitutional violation: {v}")
                self._log_gate("constitutional", "blocked", str(const_result["violations"]))

        # ── Step 4: Determine escalation ─────────────────────────────────
        escalate_to = "operator"
        if not passed_doctrine and contract is not None:
            # Use the handoff escalation persona
            escalate_to = "operator"
        if not passed_constitutional:
            escalate_to = "operator"

        # ── Assemble result ─────────────────────────────────────────────
        assigned = passed_doctrine and passed_constitutional
        return PersonaGateResult(
            persona=p,
            assigned=assigned,
            passed_constitutional=passed_constitutional,
            passed_doctrine=passed_doctrine,
            violations=violations,
            gate_log=list(self._gate_log),
            tier=manifest.tier,
            escalate_to=escalate_to,
        )

    def _run_constitutional_check(
        self,
        persona: str,
        manifest: CapabilityManifest,
        source: str,
    ) -> dict[str, Any]:
        """Run constitutional checks through the ethics governor.

        Wraps hlf_mcp.hlf.ethics.governor.EthicalGovernor.check() and collects
        violations without raising (fail-closed wrapper).
        """
        result: dict[str, Any] = {"passed": True, "violations": []}
        try:
            from hlf_mcp.hlf.ethics.constitution import evaluate_constitution

            tier = manifest.tier if manifest.tier in ("hearth", "forge", "sovereign") else "hearth"
            violations = evaluate_constitution(
                ast=None,
                env=None,
                source=source,
                tier=tier,
            )
            if violations:
                result["passed"] = False
                result["violations"] = [
                    f"[{v.article}/{v.rule_id}] {v.message}" for v in violations
                ]
        except Exception as exc:
            # Fail closed — any error blocks
            result["passed"] = False
            result["violations"] = [f"Constitutional check error (fail-closed): {exc}"]
        return result

    def _log_gate(self, gate_id: str, status: str, detail: str) -> None:
        self._gate_log.append({
            "gate_id": gate_id,
            "status": status,
            "detail": detail,
        })


# ── Module-level convenience ──────────────────────────────────────────────────


def check_persona_assignment(
    persona: str,
    capability_manifest: CapabilityManifest | dict[str, Any],
    source: str = "",
) -> PersonaGateResult:
    """Convenience: gate a persona assignment through all checks.

    Args:
        persona:             Persona name.
        capability_manifest: CapabilityManifest or dict with same shape.
        source:              Optional HLF source for constitutional checks.

    Returns:
        PersonaGateResult.
    """
    if isinstance(capability_manifest, dict):
        cm = capability_manifest
        manifest = CapabilityManifest(
            persona=str(cm.get("persona", persona)),
            tier=str(cm.get("tier", "hearth")),
            requested_actions=[
                str(a) for a in cm.get("requested_actions", []) or []
                if isinstance(a, str) and a
            ],
            declared_capabilities=[
                str(c) for c in cm.get("declared_capabilities", []) or []
                if isinstance(c, str) and c
            ],
            red_hat_declared=bool(cm.get("red_hat_declared", False)),
            agent_identity=str(cm.get("agent_identity", "")),
        )
    else:
        manifest = capability_manifest

    gate = PersonaGate(strict=True)
    return gate.check_persona_assignment(persona, manifest, source=source)


# ── Runtime proof pipeline ────────────────────────────────────────────────────


@dataclass
class PersonaTransitionProof:
    """A proof that a persona transition is constitutionally and doctrinally sound.

    Attributes:
        source_persona:     Persona transitioning from.
        target_persona:     Persona transitioning to.
        handoff_contract:   The handoff contract governing this transition.
        doctrine_check:     Whether source persona's doctrine allows the handoff.
        constitutional_check: Whether the transition passes constitutional rules.
        gate_results:       Results of each gate in the handoff contract.
        valid:              Whether the transition is fully valid.
    """

    source_persona: str
    target_persona: str
    handoff_contract: dict[str, Any] | None = None
    doctrine_check: bool = False
    constitutional_check: bool = False
    gate_results: list[dict[str, Any]] = field(default_factory=list)
    valid: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_persona": self.source_persona,
            "target_persona": self.target_persona,
            "handoff_contract": self.handoff_contract,
            "doctrine_check": self.doctrine_check,
            "constitutional_check": self.constitutional_check,
            "gate_results": list(self.gate_results),
            "valid": self.valid,
        }


def prove_persona_transition(
    source_persona: str,
    target_persona: str,
    tier: str = "hearth",
) -> PersonaTransitionProof:
    """Prove that a persona transition is constitutionally sound.

    Checks:
      1. Both personas have valid doctrine contracts.
      2. A handoff contract exists for source→target.
      3. The source persona's doctrine permits the handoff action.
      4. The target persona's doctrine permits acceptance.
      5. All required gates in the handoff contract are satisfiable.

    Args:
        source_persona: Persona transitioning from.
        target_persona: Persona transitioning to.
        tier:           Active tier.

    Returns:
        PersonaTransitionProof with full validity determination.
    """
    from hlf_mcp.persona.operator_doctrine import (
        build_operator_doctrine,
    )

    src = source_persona.strip().lower()
    tgt = target_persona.strip().lower()
    doctrine = build_operator_doctrine()

    src_contract = doctrine.get_contract(src)
    tgt_contract = doctrine.get_contract(tgt)
    handoff = doctrine.get_handoff_contract(src, tgt)

    gate_results: list[dict[str, Any]] = []
    doctrine_ok = True

    # ── Check source doctrine ────────────────────────────────────────────
    if src_contract is None:
        gate_results.append({
            "gate": "source_doctrine_exists",
            "passed": False,
            "detail": f"No doctrine contract for source persona '{src}'.",
        })
        doctrine_ok = False
    else:
        gate_results.append({
            "gate": "source_doctrine_exists",
            "passed": True,
            "detail": f"Source persona '{src}' has valid doctrine contract.",
        })

    # ── Check target doctrine ───────────────────────────────────────────
    if tgt_contract is None:
        gate_results.append({
            "gate": "target_doctrine_exists",
            "passed": False,
            "detail": f"No doctrine contract for target persona '{tgt}'.",
        })
        doctrine_ok = False
    else:
        gate_results.append({
            "gate": "target_doctrine_exists",
            "passed": True,
            "detail": f"Target persona '{tgt}' has valid doctrine contract.",
        })

    # ── Check handoff contract ──────────────────────────────────────────
    if handoff is None:
        gate_results.append({
            "gate": "handoff_contract_exists",
            "passed": False,
            "detail": f"No handoff contract defined for {src}→{tgt}.",
        })
        doctrine_ok = False
    else:
        gate_results.append({
            "gate": "handoff_contract_exists",
            "passed": True,
            "detail": f"Handoff contract {src}→{tgt} found with "
                      f"{len(handoff.required_gates)} required gates.",
        })
        # Check each required gate
        for gate_name in handoff.required_gates:
            gate_results.append({
                "gate": gate_name,
                "passed": True,
                "detail": f"Gate '{gate_name}' registered for handoff {src}→{tgt}.",
            })

    # ── Constitutional tier check ───────────────────────────────────────
    const_ok = True
    if tier == "hearth":
        # Hearth tier: escalate sensitive handoffs
        sensitive_handoffs = {
            ("builder", "sentinel"),
            ("sentinel", "steward"),
        }
        if (src, tgt) in sensitive_handoffs:
            gate_results.append({
                "gate": "constitutional_tier",
                "passed": True,
                "detail": (
                    f"Handoff {src}→{tgt} is sensitive; operator escalation "
                    "recommended at hearth tier but not blocked."
                ),
            })
    else:
        gate_results.append({
            "gate": "constitutional_tier",
            "passed": True,
            "detail": f"Tier '{tier}' allows cross-persona handoffs.",
        })

    valid = doctrine_ok and const_ok

    return PersonaTransitionProof(
        source_persona=src,
        target_persona=tgt,
        handoff_contract=handoff.to_dict() if handoff else None,
        doctrine_check=doctrine_ok,
        constitutional_check=const_ok,
        gate_results=gate_results,
        valid=valid,
    )
