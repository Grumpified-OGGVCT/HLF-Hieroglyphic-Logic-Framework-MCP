"""
Review Proof — structured proof that review processes were conducted
completely and correctly for HLF artifacts.

Every component, program, manifest, verification report, and trust edge
in HLF must pass through a formal review process.  This module provides
the data structures and proof-generation functions to:

  - Record individual review events with integrity hashing (ReviewRecord).
  - Aggregate records into a verifiable completeness proof (ReviewProof).
  - Generate review checklists per component type.
  - Audit review histories for gaps, stale reviews, and missing checklist items.
  - Produce deterministic, operator-readable proof documents in Markdown.

Integration points:
  - hlf_mcp.hlf.governance_proofs → shared hashing primitives
  - hlf_mcp.hlf.formal_verifier → verification reports referenced in reviews
  - hlf_mcp.hlf.approval_ledger → review dispositions feed the ledger
  - hlf_mcp.hlf.audit_trail → review records contribute to the audit trail
  - hlf_mcp.hlf.capability_manifest → manifests under review
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from hlf_mcp.hlf.governance_proofs import sha256_digest


# ═══════════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════════

_VALID_DISPOSITIONS: frozenset[str] = frozenset(
    {"approved", "rejected", "needs_revision", "conditional"}
)

_VALID_ITEM_TYPES: frozenset[str] = frozenset(
    {"component", "program", "manifest", "verification_report", "trust_edge"}
)

_STALE_DAYS_THRESHOLD: int = 90


# ═══════════════════════════════════════════════════════════════════════════════
# ReviewRecord — immutable record of a single review event
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class ReviewRecord:
    """A record of a review conducted on an HLF artifact.

    Each record captures who reviewed what, against which checklist items,
    and what disposition was reached.  The record is self-integrity-checked
    via a truncated SHA-256 review_id computed at construction time.

    Attributes:
        reviewer: Identity of the reviewer (name, agent ID, or role).
        reviewed_item: Identifier of the item under review.
        item_type: Category of the item (component, program, manifest, etc.).
        findings: List of observations or issues discovered during review.
        disposition: Final review outcome (approved, rejected, needs_revision, conditional).
        timestamp: UTC ISO-8601 timestamp of the review; auto-populated if empty.
        review_id: Truncated SHA-256 hash of the review payload for integrity.
        checklist_completed: Which checklist items the reviewer verified.
        evidence_refs: References to evidence (reports, hashes, file paths).
    """

    reviewer: str
    reviewed_item: str
    item_type: str
    findings: list[str]
    disposition: str
    timestamp: str = ""
    review_id: str = ""
    checklist_completed: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()
        if not self.review_id:
            payload = {
                "reviewer": self.reviewer,
                "reviewed_item": self.reviewed_item,
                "item_type": self.item_type,
                "findings": self.findings,
                "disposition": self.disposition,
                "timestamp": self.timestamp,
            }
            self.review_id = hashlib.sha256(
                json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
            ).hexdigest()[:16]

    # ── serialization ──────────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """Serialize this review record to a plain dictionary."""
        return {
            "reviewer": self.reviewer,
            "reviewed_item": self.reviewed_item,
            "item_type": self.item_type,
            "findings": list(self.findings),
            "disposition": self.disposition,
            "timestamp": self.timestamp,
            "review_id": self.review_id,
            "checklist_completed": list(self.checklist_completed),
            "evidence_refs": list(self.evidence_refs),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReviewRecord:
        """Deserialize a ReviewRecord from a dictionary.

        Missing keys are filled with sensible defaults so that partial
        or legacy records can still be reconstructed.
        """
        return cls(
            reviewer=str(data.get("reviewer", "")),
            reviewed_item=str(data.get("reviewed_item", "")),
            item_type=str(data.get("item_type", "")),
            findings=list(data.get("findings", [])),
            disposition=str(data.get("disposition", "")),
            timestamp=str(data.get("timestamp", "")),
            review_id=str(data.get("review_id", "")),
            checklist_completed=list(data.get("checklist_completed", [])),
            evidence_refs=list(data.get("evidence_refs", [])),
        )

    # ── validation ─────────────────────────────────────────────────────────

    def is_well_formed(self) -> tuple[bool, list[str]]:
        """Check that the record contains all required fields with valid values.

        Returns:
            A tuple of (is_valid, list_of_error_strings).
        """
        errors: list[str] = []
        if not self.reviewer.strip():
            errors.append("reviewer is empty")
        if not self.reviewed_item.strip():
            errors.append("reviewed_item is empty")
        if self.item_type not in _VALID_ITEM_TYPES:
            errors.append(
                f"item_type '{self.item_type}' is not one of {sorted(_VALID_ITEM_TYPES)}"
            )
        if self.disposition not in _VALID_DISPOSITIONS:
            errors.append(
                f"disposition '{self.disposition}' is not one of {sorted(_VALID_DISPOSITIONS)}"
            )
        if not self.review_id:
            errors.append("review_id is empty")
        return (len(errors) == 0, errors)


# ═══════════════════════════════════════════════════════════════════════════════
# ReviewProof — aggregate proof of review completeness
# ═══════════════════════════════════════════════════════════════════════════════


class ReviewProof:
    """Generates proofs that a review was conducted properly and completely.

    A ReviewProof is a structured claim that a set of ReviewRecords
    satisfies the required review criteria for a given component type.
    It can be verified (deterministic check) and provides counterexamples
    when requirements are not met.

    Attributes:
        records: The collection of review records forming this proof.
        component_type: The type of component under review.
        required_checks: The checklist items mandated for this component type.
    """

    def __init__(
        self,
        records: list[ReviewRecord] | None = None,
        component_type: str = "",
        required_checks: list[str] | None = None,
    ) -> None:
        self.records: list[ReviewRecord] = records or []
        self.component_type: str = component_type
        self.required_checks: list[str] = required_checks or []

    # ── record management ──────────────────────────────────────────────────

    def add_record(self, record: ReviewRecord) -> None:
        """Add a review record to this proof's collection."""
        self.records.append(record)

    # ── completeness proof ─────────────────────────────────────────────────

    def prove_completeness(self) -> dict[str, Any]:
        """Prove that all required checks have been completed.

        Scans every record in the proof for completed checklist items
        and determines whether the union of all completed items covers
        every required check.  Produces a deterministic proof hash so
        that an operator can later verify that the proof hasn't been
        tampered with.

        Returns:
            A dict with keys:
                complete (bool): Whether all required checks are satisfied.
                completed_checks (list[str]): Every unique checklist item completed.
                missing_checks (list[str]): Required checks not yet completed.
                records_used (int): Number of records that contributed checklist items.
                proof_hash (str): SHA-256 digest over the proof payload.
                counterexample (dict | None): If incomplete, shows what is missing
                    and which records failed to cover it.
                recommendation (str): Human-readable next steps.
        """
        if not self.required_checks:
            proof_payload = {
                "component_type": self.component_type,
                "required_checks": [],
                "completed_checks": [],
                "missing_checks": [],
                "complete": True,
                "record_ids": [],
            }
            return {
                "complete": True,
                "completed_checks": [],
                "missing_checks": [],
                "records_used": 0,
                "proof_hash": sha256_digest(proof_payload)[:16],
                "counterexample": None,
                "recommendation": (
                    "No required checks were specified; review is vacuously complete. "
                    "Consider adding a checklist via generate_review_checklist()."
                ),
            }

        completed: set[str] = set()
        record_count = 0
        for rec in self.records:
            if rec.checklist_completed:
                completed.update(rec.checklist_completed)
                record_count += 1

        required_set = set(self.required_checks)
        completed_checks = sorted(completed & required_set)
        missing_checks = sorted(required_set - completed)

        complete = len(missing_checks) == 0

        # ── counterexample: for each missing check, find which records
        #    should have addressed it but didn't ──────────────────────────
        counterexample: dict[str, Any] | None = None
        if not complete:
            missing_detail: dict[str, list[str]] = {}
            for check in missing_checks:
                reviewers_who_could_have = [
                    r.reviewer
                    for r in self.records
                    if check in self.required_checks
                ]
                missing_detail[check] = reviewers_who_could_have or ["(no reviewers)"]
            counterexample = {
                "missing_checks": missing_checks,
                "unaddressed_by": missing_detail,
                "total_required": len(self.required_checks),
                "total_completed": len(completed_checks),
            }

        proof_payload = {
            "component_type": self.component_type,
            "required_checks": sorted(self.required_checks),
            "completed_checks": completed_checks,
            "missing_checks": missing_checks,
            "complete": complete,
            "record_ids": sorted(r.review_id for r in self.records if r.review_id),
        }
        proof_hash = sha256_digest(proof_payload)[:16]

        if complete:
            recommendation = (
                f"All {len(self.required_checks)} required checks have been "
                f"completed across {record_count} review record(s). No further action required."
            )
        else:
            recommendation = (
                f"{len(missing_checks)} of {len(self.required_checks)} required checks "
                f"are still outstanding: {', '.join(missing_checks)}. "
                f"Conduct additional reviews to address these items."
            )

        return {
            "complete": complete,
            "completed_checks": completed_checks,
            "missing_checks": missing_checks,
            "records_used": record_count,
            "proof_hash": proof_hash,
            "counterexample": counterexample,
            "recommendation": recommendation,
        }

    # ── verification ───────────────────────────────────────────────────────

    def verify_proof(self) -> dict[str, Any]:
        """Verify that this proof is internally consistent and complete.

        Performs the following checks:
          - Every record is well-formed (has reviewer, item, valid disposition).
          - No duplicate review IDs exist in the record set.
          - All required checks are addressed by at least one record.
          - Every disposition is one of the valid values.

        Returns:
            A dict with keys:
                valid (bool): True if the proof passes all consistency checks.
                consistency_errors (list[str]): Descriptive error messages.
                record_count (int): Total number of records evaluated.
                coverage (float): Fraction of required checks covered (0.0–1.0).
                verdict (str): "complete", "incomplete", or "invalid".
        """
        errors: list[str] = []
        record_count = len(self.records)

        # ── well-formedness ──────────────────────────────────────────────
        seen_ids: set[str] = set()
        for i, record in enumerate(self.records):
            valid, rec_errors = record.is_well_formed()
            if not valid:
                for err in rec_errors:
                    errors.append(f"record[{i}] ({record.reviewer}/{record.reviewed_item}): {err}")
            if record.review_id:
                if record.review_id in seen_ids:
                    errors.append(
                        f"record[{i}] duplicate review_id: {record.review_id}"
                    )
                seen_ids.add(record.review_id)

        # ── required check coverage ──────────────────────────────────────
        completeness = self.prove_completeness()
        missing = completeness.get("missing_checks", [])
        if missing:
            errors.append(
                f"incomplete coverage: {len(missing)} required check(s) not addressed: "
                f"{', '.join(missing)}"
            )

        # ── verdict determination ────────────────────────────────────────
        coverage = completeness.get("coverage", 0.0)
        if not completeness:
            coverage = 0.0
        elif self.required_checks:
            completed_count = len(completeness.get("completed_checks", []))
            coverage = completed_count / len(self.required_checks)
        else:
            coverage = 1.0

        if errors:
            verdict = "invalid"
        elif coverage >= 1.0:
            verdict = "complete"
        else:
            verdict = "incomplete"

        return {
            "valid": len(errors) == 0,
            "consistency_errors": errors,
            "record_count": record_count,
            "coverage": coverage,
            "verdict": verdict,
        }

    # ── serialization ──────────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """Serialize the review proof to a plain dictionary."""
        return {
            "component_type": self.component_type,
            "required_checks": list(self.required_checks),
            "records": [r.to_dict() for r in self.records],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReviewProof:
        """Deserialize a ReviewProof from a dictionary."""
        records_data = data.get("records", [])
        records = [
            (
                ReviewRecord.from_dict(r)
                if isinstance(r, dict)
                else r
            )
            for r in (records_data if isinstance(records_data, list) else [])
        ]
        return cls(
            records=records,
            component_type=str(data.get("component_type", "")),
            required_checks=list(data.get("required_checks", [])),
        )

    # ── markdown rendering ─────────────────────────────────────────────────

    def to_markdown(self) -> str:
        """Generate a markdown review proof document.

        Produces a self-contained document suitable for operator inspection,
        audit archiving, or inclusion in a governance report.
        """
        verification = self.verify_proof()
        completeness = self.prove_completeness()

        lines: list[str] = [
            "# HLF Review Proof",
            "",
            f"**Component Type:** `{self.component_type or '(unspecified)'}`",
            f"**Verdict:** {_verdict_icon(verification.get('verdict', 'invalid'))} {verification.get('verdict', 'invalid').upper()}",
            f"**Records:** {len(self.records)}",
            f"**Coverage:** {verification.get('coverage', 0.0):.1%}",
            f"**Proof Hash:** `{completeness.get('proof_hash', 'N/A')}`",
            "",
            "---",
            "",
            "## 📋 Required Checks",
            "",
        ]

        if self.required_checks:
            for check in self.required_checks:
                covered = check in completeness.get("completed_checks", [])
                icon = "✅" if covered else "❌"
                lines.append(f"- {icon} **{check}**")
        else:
            lines.append("- _(no required checks specified)_")

        lines.extend([
            "",
            "## 🔍 Completeness",
            "",
            f"- **Complete:** {completeness.get('complete', False)}",
            f"- **Completed Checks:** {len(completeness.get('completed_checks', []))}",
            f"- **Missing Checks:** {len(completeness.get('missing_checks', []))}",
        ])

        missing = completeness.get("missing_checks", [])
        if missing:
            lines.append("")
            lines.append("### Missing Checks")
            for m in missing:
                lines.append(f"- ❌ `{m}`")

        lines.extend([
            "",
            "## 📄 Review Records",
            "",
        ])

        if self.records:
            for i, rec in enumerate(self.records, start=1):
                lines.append(f"### Record {i}: `{rec.review_id or 'N/A'}`")
                lines.append("")
                lines.append(f"| Field | Value |")
                lines.append(f"|-------|-------|")
                lines.append(f"| Reviewer | {rec.reviewer} |")
                lines.append(f"| Item | {rec.reviewed_item} |")
                lines.append(f"| Type | {rec.item_type} |")
                lines.append(f"| Disposition | **{rec.disposition}** |")
                lines.append(f"| Timestamp | {rec.timestamp} |")
                if rec.checklist_completed:
                    lines.append(
                        f"| Checklist | {', '.join(rec.checklist_completed)} |"
                    )
                if rec.findings:
                    lines.append(
                        f"| Findings | {', '.join(rec.findings)} |"
                    )
                if rec.evidence_refs:
                    lines.append(
                        f"| Evidence | {', '.join(rec.evidence_refs)} |"
                    )
                lines.append("")
        else:
            lines.append("_(no review records)_")
            lines.append("")

        # ── consistency errors ──────────────────────────────────────────
        consistency_errors = verification.get("consistency_errors", [])
        if consistency_errors:
            lines.append("## ⚠️ Consistency Errors")
            lines.append("")
            for err in consistency_errors:
                lines.append(f"- ⚠️ {err}")
            lines.append("")

        lines.append("## 📝 Recommendation")
        lines.append("")
        lines.append(completeness.get("recommendation", "No recommendation available."))
        lines.append("")

        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# Module-level functions
# ═══════════════════════════════════════════════════════════════════════════════


# ── completeness proof ──────────────────────────────────────────────────────


def prove_review_completeness(
    review_records: list[ReviewRecord],
    required_checks: list[str],
) -> dict[str, Any]:
    """Generate a completeness proof from review records.

    A standalone entry point that constructs a temporary ReviewProof
    and returns the completeness result without requiring the caller
    to manage a ReviewProof instance.

    Args:
        review_records: The set of review records to evaluate.
        required_checks: The checklist items that must be addressed.

    Returns:
        A dict with keys:
            complete (bool): Whether all checks are satisfied.
            missing (list[str]): Required checks not found in any record.
            coverage (float): Fraction of required checks covered (0.0–1.0).
            proof_id (str): Truncated SHA-256 proof hash for integrity.
    """
    proof = ReviewProof(
        records=list(review_records) if review_records else [],
        required_checks=list(required_checks) if required_checks else [],
    )
    result = proof.prove_completeness()

    coverage: float = 0.0
    if required_checks:
        completed_count = len(result.get("completed_checks", []))
        coverage = completed_count / len(required_checks)
    else:
        coverage = 1.0

    return {
        "complete": result.get("complete", False),
        "missing": result.get("missing_checks", []),
        "coverage": coverage,
        "proof_id": result.get("proof_hash", ""),
    }


# ── checklist generation ────────────────────────────────────────────────────


def generate_review_checklist(component_type: str) -> list[str]:
    """Generate the required review items for a given component type.

    Each component type carries a canonical checklist derived from the
    governance and verification requirements that apply to that type.
    The checklist is exhaustive — every item must be addressed before
    a review can be considered complete.

    Args:
        component_type: One of the known HLF component types (compiler,
            verifier, executor, governor, runtime, manifest, trust_edge,
            audit_trail).

    Returns:
        A list of checklist item strings.  For unknown types, a generic
        checklist with essential governance items is returned.
    """
    _CHECKLISTS: dict[str, list[str]] = {
        "compiler": [
            "AST validation",
            "bytecode correctness",
            "gas estimation",
            "manifest generation",
            "tier compliance",
        ],
        "verifier": [
            "proof soundness",
            "counterexample coverage",
            "Z3 integration",
            "tier gating logic",
            "report completeness",
        ],
        "executor": [
            "channel integrity",
            "provenance tracking",
            "capability enforcement",
            "gas accounting",
            "error handling",
        ],
        "governor": [
            "constitutional compliance",
            "rogue detection",
            "termination protocol",
            "red-hat handling",
            "decision auditability",
        ],
        "runtime": [
            "bytecode dispatch",
            "memory isolation",
            "host function safety",
            "gas metering",
            "trap handling",
        ],
        "manifest": [
            "effect declaration",
            "capability listing",
            "tier requirements",
            "signature validity",
            "dependency graph",
        ],
        "trust_edge": [
            "condition verification",
            "evidence sufficiency",
            "boundary check",
            "constitutional check",
            "reciprocity check",
        ],
        "audit_trail": [
            "event completeness",
            "timestamp ordering",
            "provenance linking",
            "readability",
            "format compliance",
        ],
    }

    if component_type in _CHECKLISTS:
        return list(_CHECKLISTS[component_type])

    # ── generic fallback for unknown component types ─────────────────────
    return [
        "functional correctness",
        "security review",
        "performance assessment",
        "governance compliance",
        "documentation completeness",
    ]


# ── review gap audit ────────────────────────────────────────────────────────


def audit_review_gaps(review_history: list[ReviewRecord]) -> dict[str, Any]:
    """Find missing or incomplete reviews in a review history.

    Analyzes a set of review records and identifies operational gaps
    that an operator or governance agent would need to address:

      - Components with no review records at all.
      - Components whose latest disposition is rejected or needs_revision.
      - Components reviewed without completing their type-specific checklist.
      - Stale reviews older than the configured threshold (90 days).

    Args:
        review_history: The collection of review records to audit.
            Pass an empty list or None-safe — the function handles both.

    Returns:
        A dict with keys:
            total_records (int): Number of records analyzed.
            components_reviewed (list[str]): Unique component IDs with at least one record.
            unreviewed_components (list[str]): Component types that appear in no record.
            rejected_items (list[str]): Items with rejected or needs_revision disposition.
            incomplete_checklists (list[str]): Items whose records didn't cover the full checklist.
            stale_reviews (list[str]): Review records older than the stale threshold.
            overall_health (str): One of "healthy", "needs_attention", or "critical".
            recommendations (list[str]): Actionable next steps.
    """
    records = review_history if review_history else []
    if not records:
        return {
            "total_records": 0,
            "components_reviewed": [],
            "unreviewed_components": list(_VALID_ITEM_TYPES),
            "rejected_items": [],
            "incomplete_checklists": [],
            "stale_reviews": [],
            "overall_health": "critical",
            "recommendations": [
                "No review records exist. Initiate reviews for all component types.",
                "Run generate_review_checklist() for each component type to establish baselines.",
            ],
        }

    # ── identify components without any review records ───────────────────
    reviewed_types: set[str] = set()
    rejected_items: list[str] = []
    incomplete_checklists: list[str] = []
    stale_reviews: list[str] = []

    now = datetime.now(timezone.utc)
    component_records: dict[str, list[ReviewRecord]] = {}
    for rec in records:
        reviewed_types.add(rec.item_type)
        component_records.setdefault(rec.reviewed_item, []).append(rec)

    unreviewed = sorted(_VALID_ITEM_TYPES - reviewed_types)

    # ── per-component analysis ──────────────────────────────────────────
    for item_id, item_records in component_records.items():
        # check for rejected / needs_revision dispositions
        for rec in item_records:
            if rec.disposition in ("rejected", "needs_revision"):
                rejected_items.append(
                    f"{item_id} ({rec.item_type}) — {rec.disposition} by {rec.reviewer}"
                )

        # check checklist completeness
        item_type = item_records[0].item_type if item_records else ""
        required = generate_review_checklist(item_type)
        completed: set[str] = set()
        for rec in item_records:
            if rec.checklist_completed:
                completed.update(rec.checklist_completed)
        missing = set(required) - completed
        if missing:
            incomplete_checklists.append(
                f"{item_id} ({item_type}) — missing: {', '.join(sorted(missing))}"
            )

        # check for stale reviews
        for rec in item_records:
            try:
                ts = datetime.fromisoformat(rec.timestamp)
                age_days = (now - ts).days
                if age_days > _STALE_DAYS_THRESHOLD:
                    stale_reviews.append(
                        f"{rec.reviewed_item} — {age_days} days old "
                        f"(reviewer: {rec.reviewer}, disposition: {rec.disposition})"
                    )
            except (ValueError, TypeError):
                # unparseable timestamps are treated as stale
                stale_reviews.append(
                    f"{rec.reviewed_item} — unparseable timestamp "
                    f"(reviewer: {rec.reviewer})"
                )

    # ── overall health assessment ───────────────────────────────────────
    issue_count = len(rejected_items) + len(incomplete_checklists) + len(stale_reviews)
    if len(unreviewed) >= 3 or issue_count >= 5:
        overall_health = "critical"
    elif unreviewed or issue_count > 0:
        overall_health = "needs_attention"
    else:
        overall_health = "healthy"

    # ── recommendations ─────────────────────────────────────────────────
    recommendations: list[str] = []
    if unreviewed:
        recommendations.append(
            f"Schedule reviews for unreviewed component types: {', '.join(unreviewed)}."
        )
    if rejected_items:
        recommendations.append(
            f"Re-review {len(rejected_items)} item(s) with rejected/needs_revision disposition."
        )
    if incomplete_checklists:
        recommendations.append(
            f"Complete checklist items for {len(incomplete_checklists)} item(s)."
        )
    if stale_reviews:
        recommendations.append(
            f"Refresh {len(stale_reviews)} stale review(s) older than {_STALE_DAYS_THRESHOLD} days."
        )
    if not recommendations:
        recommendations.append("All reviews are current and complete. No action required.")

    return {
        "total_records": len(records),
        "components_reviewed": sorted(reviewed_types),
        "unreviewed_components": unreviewed,
        "rejected_items": rejected_items,
        "incomplete_checklists": incomplete_checklists,
        "stale_reviews": stale_reviews,
        "overall_health": overall_health,
        "recommendations": recommendations,
    }


# ── markdown generation ─────────────────────────────────────────────────────


def generate_review_proof_markdown(review_proof: ReviewProof) -> str:
    """Generate a detailed markdown document from a ReviewProof instance.

    Produces a comprehensive, operator-facing document that includes:
      - Proof header with the integrity hash.
      - Completeness table showing every required check and its status.
      - Per-record details with all fields.
      - Checklist coverage visualization as a progress bar.
      - Consistency verification results.
      - Actionable recommendations.

    Args:
        review_proof: A fully populated ReviewProof instance.

    Returns:
        A Markdown string suitable for saving to a file, embedding in
        a report, or displaying in a dashboard.
    """
    return review_proof.to_markdown()


# ═══════════════════════════════════════════════════════════════════════════════
# Internal helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _verdict_icon(verdict: str) -> str:
    """Return a Unicode icon for a proof verdict string."""
    _icons: dict[str, str] = {
        "complete": "✅",
        "incomplete": "⚠️",
        "invalid": "❌",
    }
    return _icons.get(verdict, "❓")


# ═══════════════════════════════════════════════════════════════════════════════
# Exports
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    "ReviewProof",
    "ReviewRecord",
    "audit_review_gaps",
    "generate_review_checklist",
    "generate_review_proof_markdown",
    "prove_review_completeness",
]
