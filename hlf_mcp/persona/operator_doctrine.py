"""
Operator Doctrine Contracts — per-persona obligation, permission, and prohibition
contracts for the 4-persona governance pipeline.

Four personas in the operator doctrine pipeline:
  Steward  — workflow integrity reviewer (workflow_contract owner)
  Herald   — documentation truth reviewer (docs_truth owner)
  Builder  — planning authority / strategist (planning_only owner)
  Sentinel — security boundary reviewer (security_sensitive owner)

Each persona carries a DoctrineContract defining:
  - Obligations: what the persona MUST do
  - Permissions: what the persona MAY do
  - Prohibitions: what the persona MUST NOT do

These contracts are sourced from `docs/HLF_PERSONA_OWNERSHIP_MATRIX.json` and
converted to HLF constraint statements for constitutional enforcement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ── Cross-persona handoff pairs ───────────────────────────────────────────────

_HANDOFF_PAIRS: list[tuple[str, str]] = [
    ("steward", "herald"),
    ("herald", "builder"),
    ("builder", "sentinel"),
    ("sentinel", "steward"),
]


# ── Doctrine Contract ─────────────────────────────────────────────────────────


@dataclass
class DoctrineContract:
    """A single persona's operator doctrine contract.

    Attributes:
        persona:       Normalised persona name (steward, herald, builder, sentinel).
        obligations:   Actions the persona MUST perform.
        permissions:   Actions the persona MAY perform.
        prohibitions:  Actions the persona MUST NOT perform.
        tier:          Tier classification (hearth / sovereign / field).
        source_ref:    Reference to the upstream authority document.
    """

    persona: str
    obligations: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
    prohibitions: list[str] = field(default_factory=list)
    tier: str = "hearth"
    source_ref: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "persona": self.persona,
            "obligations": list(self.obligations),
            "permissions": list(self.permissions),
            "prohibitions": list(self.prohibitions),
            "tier": self.tier,
            "source_ref": self.source_ref,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DoctrineContract:
        return cls(
            persona=str(data.get("persona", "")),
            obligations=[str(o) for o in data.get("obligations", []) or []],
            permissions=[str(p) for p in data.get("permissions", []) or []],
            prohibitions=[str(p) for p in data.get("prohibitions", []) or []],
            tier=str(data.get("tier", "hearth")),
            source_ref=str(data.get("source_ref", "")),
        )


# ── Compliance Report ─────────────────────────────────────────────────────────


@dataclass
class DoctrineComplianceReport:
    """Result of validating an action against a persona's doctrine contract.

    Attributes:
        persona:         Persona being checked.
        action:          The action being validated.
        allowed:         Whether the action is permitted.
        block_reason:    If not allowed, why.
        matched_rule:    Which doctrine rule matched (obligation/permission/prohibition).
        tier:            The persona's tier at time of check.
        context:         Additional context from validation.
    """

    persona: str
    action: str
    allowed: bool
    block_reason: str = ""
    matched_rule: str = ""
    tier: str = "hearth"
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "persona": self.persona,
            "action": self.action,
            "allowed": self.allowed,
            "block_reason": self.block_reason,
            "matched_rule": self.matched_rule,
            "tier": self.tier,
            "context": dict(self.context),
        }


# ── Handoff Contract ──────────────────────────────────────────────────────────


@dataclass
class HandoffContract:
    """A contract governing a cross-persona handoff transition.

    Attributes:
        source_persona:  Persona handing off.
        target_persona:  Persona receiving the handoff.
        required_gates:  Gates that must pass before handoff.
        evidence_required: Evidence that must be presented for the handoff.
        escalation_persona: Persona to escalate to if handoff is blocked.
    """

    source_persona: str
    target_persona: str
    required_gates: list[str] = field(default_factory=list)
    evidence_required: list[str] = field(default_factory=list)
    escalation_persona: str = "operator"

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_persona": self.source_persona,
            "target_persona": self.target_persona,
            "required_gates": list(self.required_gates),
            "evidence_required": list(self.evidence_required),
            "escalation_persona": self.escalation_persona,
        }


# ── Operator Doctrine (aggregate) ─────────────────────────────────────────────


@dataclass
class OperatorDoctrine:
    """Aggregate operator doctrine holding contracts for all 4 personas.

    Sourced from the HLF persona ownership matrix.  Provides:
      - Per-persona contract lookup
      - Compliance validation
      - HLF constraint generation
      - Cross-persona handoff contract generation
    """

    contracts: dict[str, DoctrineContract] = field(default_factory=dict)
    handoff_contracts: dict[tuple[str, str], HandoffContract] = field(default_factory=dict)
    tier_map: dict[str, str] = field(default_factory=dict)

    def get_contract(self, persona: str) -> DoctrineContract | None:
        """Return the doctrine contract for a given persona."""
        return self.contracts.get(persona.lower().strip())

    def validate_compliance(
        self,
        persona: str,
        action: str,
        context: dict[str, Any] | None = None,
    ) -> DoctrineComplianceReport:
        """Validate whether an action is compliant with a persona's doctrine.

        Args:
            persona:  The persona attempting the action.
            action:   The action identifier (must match matrix allowed_actions/forbidden_actions).
            context:  Optional context dict (tier, lane, etc.).

        Returns:
            DoctrineComplianceReport with allowed/blocked decision.
        """
        ctx = context or {}
        contract = self.get_contract(persona)
        if contract is None:
            return DoctrineComplianceReport(
                persona=persona,
                action=action,
                allowed=False,
                block_reason=f"Unknown persona '{persona}'. No doctrine contract found.",
                matched_rule="unknown_persona",
                tier=ctx.get("tier", "hearth"),
                context=ctx,
            )

        tier = ctx.get("tier", contract.tier)

        # ── First check: explicit prohibitions ────────────────────────────
        for prohibition in contract.prohibitions:
            if _action_matches(action, prohibition):
                return DoctrineComplianceReport(
                    persona=persona,
                    action=action,
                    allowed=False,
                    block_reason=(
                        f"Action '{action}' is prohibited for persona '{persona}'. "
                        f"Rule: {prohibition}"
                    ),
                    matched_rule=f"prohibition:{prohibition}",
                    tier=tier,
                    context=ctx,
                )

        # ── Second check: explicit permissions ───────────────────────────
        for permission in contract.permissions:
            if _action_matches(action, permission):
                return DoctrineComplianceReport(
                    persona=persona,
                    action=action,
                    allowed=True,
                    matched_rule=f"permission:{permission}",
                    tier=tier,
                    context=ctx,
                )

        # ── Third check: obligations are always allowed ──────────────────
        for obligation in contract.obligations:
            if _action_matches(action, obligation):
                return DoctrineComplianceReport(
                    persona=persona,
                    action=action,
                    allowed=True,
                    matched_rule=f"obligation:{obligation}",
                    tier=tier,
                    context=ctx,
                )

        # ── Fallthrough: not explicitly permitted ───────────────────────
        return DoctrineComplianceReport(
            persona=persona,
            action=action,
            allowed=False,
            block_reason=(
                f"Action '{action}' is not explicitly permitted for persona '{persona}'. "
                "Doctrine requires explicit permission or obligation."
            ),
            matched_rule="no_explicit_permission",
            tier=tier,
            context=ctx,
        )

    def doctrine_to_hlf(self) -> str:
        """Convert all doctrine contracts to HLF constraint statements.

        Returns an HLF source string encoding the full operator doctrine
        as constitutional constraint blocks that can be fed to the compiler.
        """
        lines: list[str] = [
            "// ── Operator Doctrine HLF Constraints ──",
            "// Auto-generated from OperatorDoctrine contracts.",
            "// Sourced from docs/HLF_PERSONA_OWNERSHIP_MATRIX.json",
            "",
        ]
        for persona_name, contract in sorted(self.contracts.items()):
            lines.append(f"// ── {persona_name} doctrine ──")
            lines.append(f"@tier({contract.tier})")
            lines.append(f"@validate(doctrine_contract=\"{persona_name}\")")
            lines.append(f"capsule {persona_name}_doctrine {{")
            lines.append(f"  // Obligations ({len(contract.obligations)})")
            for obl in contract.obligations:
                lines.append(f"  @must(\"{obl}\")")
            lines.append(f"  // Permissions ({len(contract.permissions)})")
            for perm in contract.permissions:
                lines.append(f"  @may(\"{perm}\")")
            lines.append(f"  // Prohibitions ({len(contract.prohibitions)})")
            for proh in contract.prohibitions:
                lines.append(f"  @must_not(\"{proh}\")")
            lines.append("}")
            lines.append("")

        # Cross-persona handoff constraints
        lines.append("// ── Cross-persona handoff constraints ──")
        for (src, tgt), hc in sorted(self.handoff_contracts.items()):
            lines.append(f"@validate(handoff_contract=\"{src}->{tgt}\")")
            lines.append(f"capsule handoff_{src}_to_{tgt} {{")
            for gate in hc.required_gates:
                lines.append(f"  @require_gate(\"{gate}\")")
            for ev in hc.evidence_required:
                lines.append(f"  @require_evidence(\"{ev}\")")
            lines.append(f"  @escalate_to(\"{hc.escalation_persona}\")")
            lines.append("}")
            lines.append("")

        return "\n".join(lines)

    def get_handoff_contract(
        self, source_persona: str, target_persona: str
    ) -> HandoffContract | None:
        """Return the handoff contract for a source→target persona transition."""
        key = (source_persona.lower().strip(), target_persona.lower().strip())
        return self.handoff_contracts.get(key)

    def all_personas(self) -> list[str]:
        """Return sorted list of all persona names in this doctrine."""
        return sorted(self.contracts.keys())

    def all_handoff_pairs(self) -> list[tuple[str, str]]:
        """Return all defined handoff pairs."""
        return sorted(self.handoff_contracts.keys())


# ── Tier-differentiated permission lookup ─────────────────────────────────────


_TIER_PERMISSION_MULTIPLIERS: dict[str, dict[str, bool]] = {
    "hearth": {
        "auto_apply_changes": False,
        "modify_protected_branch_policy": False,
        "grant_runtime_authority": False,
        "merge_changes": False,
        "publish_artifacts": False,
    },
    "sovereign": {
        "auto_apply_changes": True,
        "modify_protected_branch_policy": True,
        "grant_runtime_authority": False,  # operator-only
        "merge_changes": True,
        "publish_artifacts": True,
    },
    "field": {
        "auto_apply_changes": True,
        "modify_protected_branch_policy": False,
        "grant_runtime_authority": False,
        "merge_changes": False,
        "publish_artifacts": True,
    },
}


def tier_allows(tier: str, action: str) -> bool:
    """Check whether a tier permits a given action.

    Tier-differentiated permissions supplement persona-specific doctrine —
    even if a persona's contract allows an action, the active tier may deny it.
    """
    tier_rules = _TIER_PERMISSION_MULTIPLIERS.get(tier.lower(), {})
    return tier_rules.get(action, False)


# ── Factory: build doctrine from persona matrix ──────────────────────────────


def build_operator_doctrine() -> OperatorDoctrine:
    """Build the OperatorDoctrine from the HLF persona ownership matrix.

    Reads the persona matrix via persona_contract.load_persona_matrix() and
    constructs per-persona DoctrineContracts with obligations, permissions,
    and prohibitions extracted from the matrix definition, plus cross-persona
    handoff contracts for the 4-persona governance pipeline.
    """
    from hlf_mcp.persona_contract import load_persona_matrix

    matrix = load_persona_matrix()
    personas = matrix.get("personas") if isinstance(matrix.get("personas"), dict) else {}
    lane = str(matrix.get("lane") or "bridge-true")

    # ── Map persona names to our 4-pipeline names ─────────────────────
    _PIPELINE_ALIASES: dict[str, str] = {
        "strategist": "builder",
        "planner": "builder",
    }

    contracts: dict[str, DoctrineContract] = {}
    tier_map: dict[str, str] = {}

    for raw_name, details in personas.items():
        if not isinstance(details, dict):
            continue
        name = raw_name.strip().lower()
        pipeline_name = _PIPELINE_ALIASES.get(name, name)

        # Only include the 4 pipeline personas
        if pipeline_name not in ("steward", "herald", "builder", "sentinel"):
            continue

        allowed = [
            str(a)
            for a in details.get("allowed_actions", []) or []
            if isinstance(a, str) and a
        ]
        forbidden = [
            str(f)
            for f in details.get("forbidden_actions", []) or []
            if isinstance(f, str) and f
        ]
        tier = str(details.get("tier", "tier_1")).replace("tier_", "")

        contracts[pipeline_name] = DoctrineContract(
            persona=pipeline_name,
            obligations=[],  # Obligations derived from internal_role + maintainer_mode
            permissions=allowed,
            prohibitions=forbidden,
            tier=_tier_label(tier),
            source_ref=str(details.get("upstream_source", "")),
        )
        tier_map[pipeline_name] = _tier_label(tier)

    # ── Augment with obligations (derived from internal role) ──────────
    _obligations_from_role: dict[str, list[str]] = {
        "steward": [
            "review_tool_contracts",
            "review_transport_or_workflow_changes",
            "validate_workflow_integrity",
            "report_contract_risk",
        ],
        "herald": [
            "classify_claim_lanes",
            "sync_docs_and_handoffs",
            "validate_documentation_truth",
            "flag_overstatement",
        ],
        "builder": [
            "classify_lane",
            "set_change_class",
            "sequence_work",
            "approve_or_defer_plan",
        ],
        "sentinel": [
            "review_security_posture",
            "review_fail_closed_behavior",
            "validate_boundary_integrity",
            "report_boundary_risk",
        ],
    }

    for pname, obl_list in _obligations_from_role.items():
        if pname in contracts:
            contracts[pname].obligations = list(obl_list)

    # ── Build cross-persona handoff contracts ──────────────────────────
    handoff_contracts: dict[tuple[str, str], HandoffContract] = {}
    for src, tgt in _HANDOFF_PAIRS:
        handoff_contracts[(src, tgt)] = HandoffContract(
            source_persona=src,
            target_persona=tgt,
            required_gates=[f"{src}_review", f"{tgt}_review", "cove_review"],
            evidence_required=[
                f"{src}_handoff_evidence",
                f"{tgt}_acceptance_evidence",
            ],
            escalation_persona="operator",
        )

    return OperatorDoctrine(
        contracts=contracts,
        handoff_contracts=handoff_contracts,
        tier_map=tier_map,
    )


# ── Module-level convenience functions ────────────────────────────────────────


def validate_doctrine_compliance(
    persona: str,
    action: str,
    context: dict[str, Any] | None = None,
) -> DoctrineComplianceReport:
    """Validate an action against a persona's doctrine contract.

    Convenience wrapper that builds the doctrine, then validates.
    """
    doctrine = build_operator_doctrine()
    return doctrine.validate_compliance(persona, action, context)


def doctrine_to_hlf() -> str:
    """Convert the full operator doctrine to HLF constraint statements.

    Convenience wrapper.
    """
    doctrine = build_operator_doctrine()
    return doctrine.doctrine_to_hlf()


def get_handoff_contract(
    source_persona: str, target_persona: str
) -> HandoffContract | None:
    """Get the handoff contract for a source→target persona transition."""
    doctrine = build_operator_doctrine()
    return doctrine.get_handoff_contract(source_persona, target_persona)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _action_matches(action: str, rule: str) -> bool:
    """Check if an action matches a doctrine rule.

    Supports exact match and substring match for compound patterns.
    """
    a = action.strip().lower()
    r = rule.strip().lower()
    if a == r:
        return True
    # Allow substring matching so 'block_on_contract_risk' matches 'block_on_*'
    if r in a or a in r:
        return True
    return False


def _tier_label(tier_value: str) -> str:
    """Normalise a tier string to hearth / sovereign / field."""
    t = tier_value.strip().lower()
    if t in ("tier_0", "0", "sovereign"):
        return "sovereign"
    if t in ("tier_1", "1", "hearth"):
        return "hearth"
    if t in ("tier_2", "2", "field"):
        return "field"
    return "hearth"
