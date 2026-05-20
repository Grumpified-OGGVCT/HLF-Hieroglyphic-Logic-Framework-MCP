"""
Persona Composition Proofs — proves that when agent A (persona P1) hands off
to agent B (persona P2), the composed behavior satisfies both doctrines.

Provides:
  - PersonaCompositionProver: verifies handoff composition correctness
  - CompositionProof: proof that a composed handoff is doctrinally sound
  - CompositionConflict: detected conflict between two persona doctrines
  - CompositionConstraint: HLF constraint to resolve a composition conflict

Integration points:
  - hlf_mcp.persona.operator_doctrine: OperatorDoctrine for contract definitions
  - hlf_mcp.persona.gate_integration: PersonaTransitionProof for handoff validation
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# CompositionConflict — detected conflict between doctrines
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class CompositionConflict:
    """A conflict detected when composing two persona doctrines.

    Attributes:
        conflict_id: Unique conflict identifier.
        source_persona: First persona in the composition.
        target_persona: Second persona in the composition.
        conflict_type: Type of conflict (permission_clash / obligation_gap /
            prohibition_overlap / capability_mismatch).
        description: Human-readable conflict description.
        source_rule: The rule from the source persona.
        target_rule: The rule from the target persona.
        severity: Conflict severity (warning / critical).
        resolvable: Whether the conflict can be automatically resolved.
    """

    conflict_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_persona: str = ""
    target_persona: str = ""
    conflict_type: str = "permission_clash"
    description: str = ""
    source_rule: str = ""
    target_rule: str = ""
    severity: str = "warning"
    resolvable: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "conflict_id": self.conflict_id,
            "source_persona": self.source_persona,
            "target_persona": self.target_persona,
            "conflict_type": self.conflict_type,
            "description": self.description,
            "source_rule": self.source_rule,
            "target_rule": self.target_rule,
            "severity": self.severity,
            "resolvable": self.resolvable,
        }


# ---------------------------------------------------------------------------
# CompositionConstraint — HLF constraint for a conflict
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class CompositionConstraint:
    """An HLF constraint to resolve a composition conflict.

    Attributes:
        constraint_id: Unique constraint identifier.
        conflict_ref: Reference to the CompositionConflict.
        hlf_statement: Generated HLF constraint statement.
        applies_to: Which persona the constraint applies to.
        precedence: Priority for resolution ordering.
    """

    constraint_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    conflict_ref: str = ""
    hlf_statement: str = ""
    applies_to: str = ""
    precedence: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "constraint_id": self.constraint_id,
            "conflict_ref": self.conflict_ref,
            "hlf_statement": self.hlf_statement,
            "applies_to": self.applies_to,
            "precedence": self.precedence,
        }


# ---------------------------------------------------------------------------
# CompositionProof — proof that a composed handoff is sound
# ---------------------------------------------------------------------------


@dataclass
class CompositionProof:
    """Proof that a composed persona handoff satisfies both doctrines.

    Attributes:
        proof_id: Unique proof identifier.
        source_persona: Persona handing off.
        target_persona: Target persona receiving.
        valid: Whether the composition is doctrinally sound.
        conflicts: Detected conflicts between the doctrines.
        constraints: Generated HLF constraints to resolve conflicts.
        permission_overlap: Actions permitted by both personas.
        permission_gap: Actions permitted by source but not target.
        obligation_transfer: Obligations that must transfer.
        prohibition_continuity: Prohibitions that must persist across handoff.
        checksum: SHA-256 integrity hash.
        proven_at: Timestamp of proof generation.
    """

    proof_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_persona: str = ""
    target_persona: str = ""
    valid: bool = False
    conflicts: list[CompositionConflict] = field(default_factory=list)
    constraints: list[CompositionConstraint] = field(default_factory=list)
    permission_overlap: list[str] = field(default_factory=list)
    permission_gap: list[str] = field(default_factory=list)
    obligation_transfer: list[dict[str, str]] = field(default_factory=list)
    prohibition_continuity: list[str] = field(default_factory=list)
    checksum: str = ""
    proven_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "proof_id": self.proof_id,
            "source_persona": self.source_persona,
            "target_persona": self.target_persona,
            "valid": self.valid,
            "conflicts": [c.to_dict() for c in self.conflicts],
            "constraints": [c.to_dict() for c in self.constraints],
            "permission_overlap": list(self.permission_overlap),
            "permission_gap": list(self.permission_gap),
            "obligation_transfer": list(self.obligation_transfer),
            "prohibition_continuity": list(self.prohibition_continuity),
            "checksum": self.checksum,
            "proven_at": self.proven_at,
        }


# ---------------------------------------------------------------------------
# PersonaCompositionProver — verifies handoff composition correctness
# ---------------------------------------------------------------------------


class PersonaCompositionProver:
    """Proves that composed persona handoffs satisfy both doctrines.

    When agent A (persona P1) hands off to agent B (persona P2), the
    composed behavior must satisfy both P1's and P2's doctrine contracts.
    This prover detects conflicts (permission clashes, obligation gaps,
    prohibition overlaps) and generates HLF constraints to resolve them.

    Usage::

        prover = PersonaCompositionProver()
        proof = prover.prove_composition("steward", "herald")
        if not proof.valid:
            for conflict in proof.conflicts:
                print(f"Conflict: {conflict.description}")
    """

    def __init__(
        self,
        doctrine: Any = None,  # OperatorDoctrine (lazy import)
        strict_composition: bool = True,
    ) -> None:
        self._doctrine = doctrine
        self._strict = strict_composition
        self._proofs: list[CompositionProof] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def prove_composition(
        self,
        source_persona: str,
        target_persona: str,
    ) -> CompositionProof:
        """Prove that a composed handoff is doctrinally sound.

        Analyzes both persona doctrines for conflicts, gaps, and overlaps.
        Generates constraints to resolve any issues found.

        Args:
            source_persona: The persona handing off.
            target_persona: The persona receiving.

        Returns:
            CompositionProof with validity, conflicts, and constraints.
        """
        src = source_persona.strip().lower()
        tgt = target_persona.strip().lower()

        doctrine = self._get_doctrine()
        src_contract = doctrine.get_contract(src)
        tgt_contract = doctrine.get_contract(tgt)

        if src_contract is None and tgt_contract is None:
            proof = CompositionProof(
                source_persona=src,
                target_persona=tgt,
                valid=False,
                conflicts=[
                    CompositionConflict(
                        source_persona=src,
                        target_persona=tgt,
                        conflict_type="capability_mismatch",
                        description=f"Neither '{src}' nor '{tgt}' have doctrine contracts.",
                        severity="critical",
                        resolvable=False,
                    )
                ],
            )
            self._proofs.append(proof)
            return proof

        if src_contract is None:
            proof = CompositionProof(
                source_persona=src,
                target_persona=tgt,
                valid=False,
                conflicts=[
                    CompositionConflict(
                        source_persona=src,
                        target_persona=tgt,
                        conflict_type="capability_mismatch",
                        description=f"Source persona '{src}' has no doctrine contract.",
                        severity="critical",
                        resolvable=False,
                    )
                ],
            )
            self._proofs.append(proof)
            return proof

        if tgt_contract is None:
            proof = CompositionProof(
                source_persona=src,
                target_persona=tgt,
                valid=False,
                conflicts=[
                    CompositionConflict(
                        source_persona=src,
                        target_persona=tgt,
                        conflict_type="capability_mismatch",
                        description=f"Target persona '{tgt}' has no doctrine contract.",
                        severity="critical",
                        resolvable=False,
                    )
                ],
            )
            self._proofs.append(proof)
            return proof

        conflicts: list[CompositionConflict] = []
        constraints: list[CompositionConstraint] = []

        src_perms = set(src_contract.permissions)
        tgt_perms = set(tgt_contract.permissions)
        src_prohs = set(src_contract.prohibitions)
        tgt_prohs = set(tgt_contract.prohibitions)
        src_obls = set(src_contract.obligations)
        tgt_obls = set(tgt_contract.obligations)

        # ── Permission overlap analysis ──────────────────────────────
        permission_overlap = sorted(src_perms & tgt_perms)
        permission_gap = sorted(src_perms - tgt_perms)

        # Source permissions not in target — potential gap
        for perm in permission_gap:
            if self._strict:
                conflict = CompositionConflict(
                    source_persona=src,
                    target_persona=tgt,
                    conflict_type="permission_clash",
                    description=(
                        f"Permission '{perm}' granted to '{src}' but not to '{tgt}'. "
                        "Handoff may lose this capability."
                    ),
                    source_rule=f"permission:{perm}",
                    target_rule="no_explicit_permission",
                    severity="warning",
                    resolvable=True,
                )
                conflicts.append(conflict)
                constraints.append(
                    self._generate_constraint(conflict, src, tgt)
                )

        # ── Prohibition continuity analysis ──────────────────────────
        # Prohibitions on source must persist on target
        prohibition_continuity = sorted(src_prohs & tgt_prohs)
        prohibition_gap = sorted(src_prohs - tgt_prohs)

        for proh in prohibition_gap:
            conflict = CompositionConflict(
                source_persona=src,
                target_persona=tgt,
                conflict_type="prohibition_overlap",
                description=(
                    f"Prohibition '{proh}' on '{src}' is NOT enforced on '{tgt}'. "
                    "Handoff creates a prohibition gap."
                ),
                source_rule=f"prohibition:{proh}",
                target_rule="no_matching_prohibition",
                severity="critical" if self._strict else "warning",
                resolvable=True,
            )
            conflicts.append(conflict)
            constraints.append(
                self._generate_constraint(conflict, src, tgt)
            )

        # ── Obligation transfer analysis ─────────────────────────────
        obligation_transfer: list[dict[str, str]] = []
        for obl in sorted(src_obls):
            if obl in tgt_obls:
                obligation_transfer.append({
                    "obligation": obl,
                    "transfer": "preserved",
                })
            else:
                obligation_transfer.append({
                    "obligation": obl,
                    "transfer": "gapped",
                })
                conflict = CompositionConflict(
                    source_persona=src,
                    target_persona=tgt,
                    conflict_type="obligation_gap",
                    description=(
                        f"Obligation '{obl}' on '{src}' is not matched on '{tgt}'. "
                        "Handoff may drop required duty."
                    ),
                    source_rule=f"obligation:{obl}",
                    target_rule="no_matching_obligation",
                    severity="warning",
                    resolvable=True,
                )
                conflicts.append(conflict)
                constraints.append(
                    self._generate_constraint(conflict, src, tgt)
                )

        # ── Capability mismatch detection ────────────────────────────
        # If source has capabilities target lacks entirely
        src_all = src_perms | src_obls
        tgt_all = tgt_perms | tgt_obls
        capability_gap = len(src_all - tgt_all)
        if capability_gap > len(src_all) * 0.5:
            conflict = CompositionConflict(
                source_persona=src,
                target_persona=tgt,
                conflict_type="capability_mismatch",
                description=(
                    f"Major capability gap: '{tgt}' covers only "
                    f"{len(tgt_all)}/{len(src_all)} of '{src}' actions."
                ),
                source_rule="capability_set",
                target_rule="capability_set",
                severity="critical",
                resolvable=False,
            )
            conflicts.append(conflict)

        has_critical = any(
            c.severity == "critical" and not c.resolvable for c in conflicts
        )
        valid = not has_critical

        # Compute checksum
        checksum = self._compute_checksum(src, tgt, conflicts, constraints)

        proof = CompositionProof(
            source_persona=src,
            target_persona=tgt,
            valid=valid,
            conflicts=conflicts,
            constraints=constraints,
            permission_overlap=permission_overlap,
            permission_gap=permission_gap,
            obligation_transfer=obligation_transfer,
            prohibition_continuity=prohibition_continuity,
            checksum=checksum,
        )
        self._proofs.append(proof)
        return proof

    def prove_all_compositions(self) -> list[CompositionProof]:
        """Prove composition for all defined handoff pairs.

        Returns:
            List of CompositionProofs, one per handoff pair.
        """
        doctrine = self._get_doctrine()
        proofs: list[CompositionProof] = []

        for src, tgt in doctrine.all_handoff_pairs():
            proof = self.prove_composition(src, tgt)
            proofs.append(proof)

        return proofs

    def generate_resolution_hlf(self, proof: CompositionProof) -> str:
        """Generate HLF source to resolve all conflicts in a composition proof.

        Args:
            proof: The composition proof to generate resolutions for.

        Returns:
            HLF source string with resolution constraint blocks.
        """
        if proof.valid and not proof.constraints:
            return (
                f"// ── Composition {proof.source_persona}→{proof.target_persona} is valid ──\n"
                f"// No conflicts detected.\n"
            )

        lines: list[str] = [
            f"// ── Composition Resolution HLF: {proof.source_persona}→{proof.target_persona} ──",
            f"// Generated: {time.strftime('%Y-%m-%dT%H:%M:%S')}",
            f"// Valid: {proof.valid}",
            f"// Conflicts: {len(proof.conflicts)}",
            f"// Constraints: {len(proof.constraints)}",
            "",
        ]

        for constraint in proof.constraints:
            lines.append(
                f"// Conflict: {constraint.conflict_ref} → {constraint.applies_to}"
            )
            lines.append(constraint.hlf_statement)
            lines.append("")

        return "\n".join(lines)

    def get_proof(self, proof_id: str) -> CompositionProof | None:
        """Retrieve a composition proof by ID."""
        for proof in self._proofs:
            if proof.proof_id == proof_id:
                return proof
        return None

    def get_proofs_for(
        self, source_persona: str, target_persona: str
    ) -> list[CompositionProof]:
        """Get all proofs for a specific handoff pair."""
        src = source_persona.strip().lower()
        tgt = target_persona.strip().lower()
        return [
            p for p in self._proofs
            if p.source_persona == src and p.target_persona == tgt
        ]

    def get_composition_summary(self) -> dict[str, Any]:
        """Return a summary of all composition proofs."""
        if not self._proofs:
            return {
                "total_proofs": 0,
                "valid_count": 0,
                "invalid_count": 0,
                "total_conflicts": 0,
                "pairs_analyzed": [],
            }

        valid = sum(1 for p in self._proofs if p.valid)
        total_conflicts = sum(len(p.conflicts) for p in self._proofs)
        pairs = sorted({
            (p.source_persona, p.target_persona) for p in self._proofs
        })

        return {
            "total_proofs": len(self._proofs),
            "valid_count": valid,
            "invalid_count": len(self._proofs) - valid,
            "total_conflicts": total_conflicts,
            "pairs_analyzed": [f"{s}→{t}" for s, t in pairs],
        }

    def clear_proofs(self) -> None:
        """Clear all composition proofs."""
        self._proofs.clear()

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

    def _generate_constraint(
        self,
        conflict: CompositionConflict,
        source_persona: str,
        target_persona: str,
    ) -> CompositionConstraint:
        """Generate an HLF constraint to resolve a composition conflict."""
        constraint_id = str(uuid.uuid4())

        if conflict.conflict_type == "prohibition_overlap":
            # Extract the prohibition action name
            proh_name = conflict.source_rule.split(":", 1)[1] if ":" in conflict.source_rule else conflict.source_rule
            hlf = (
                f"@tier(hearth)\n"
                f"@validate(composition=\"{constraint_id}\")\n"
                f"capsule compose_prohibition_{source_persona}_to_{target_persona} {{\n"
                f"  @must_not(\"{proh_name}\")  // Carry-forward prohibition to {target_persona}\n"
                f"  @inherit_from(\"{source_persona}\")\n"
                f"  @escalate_to(\"operator\")\n"
                f"}}"
            )
            precedence = 2
        elif conflict.conflict_type == "obligation_gap":
            obl_name = conflict.source_rule.split(":", 1)[1] if ":" in conflict.source_rule else conflict.source_rule
            hlf = (
                f"@tier(hearth)\n"
                f"@validate(composition=\"{constraint_id}\")\n"
                f"capsule compose_obligation_{source_persona}_to_{target_persona} {{\n"
                f"  @must(\"{obl_name}\")  // Transfer obligation to {target_persona}\n"
                f"  @inherit_from(\"{source_persona}\")\n"
                f"  @escalate_to(\"operator\")\n"
                f"}}"
            )
            precedence = 1
        elif conflict.conflict_type == "permission_clash":
            perm_name = conflict.source_rule.split(":", 1)[1] if ":" in conflict.source_rule else conflict.source_rule
            hlf = (
                f"@tier(hearth)\n"
                f"@validate(composition=\"{constraint_id}\")\n"
                f"capsule compose_permission_{source_persona}_to_{target_persona} {{\n"
                f"  @may(\"{perm_name}\")  // Extend permission to {target_persona}\n"
                f"  @require_approval(\"operator\")\n"
                f"  @inherit_from(\"{source_persona}\")\n"
                f"}}"
            )
            precedence = 0
        else:
            hlf = (
                f"@tier(hearth)\n"
                f"@validate(composition=\"{constraint_id}\")\n"
                f"capsule compose_fix_{source_persona}_to_{target_persona} {{\n"
                f"  @review(\"{conflict.conflict_type}\")\n"
                f"  @escalate_to(\"operator\")\n"
                f"}}"
            )
            precedence = 3

        return CompositionConstraint(
            constraint_id=constraint_id,
            conflict_ref=conflict.conflict_id,
            hlf_statement=hlf,
            applies_to=target_persona,
            precedence=precedence,
        )

    @staticmethod
    def _compute_checksum(
        source: str,
        target: str,
        conflicts: list[CompositionConflict],
        constraints: list[CompositionConstraint],
    ) -> str:
        """Compute deterministic checksum for a composition proof."""
        payload = json.dumps(
            {
                "source": source,
                "target": target,
                "conflicts": sorted(
                    [(c.conflict_type, c.description) for c in conflicts]
                ),
                "constraint_count": len(constraints),
            },
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
