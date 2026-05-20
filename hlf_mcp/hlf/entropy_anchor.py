"""Entropy Anchor — cryptographic anchor points with drift detection and re-anchoring.

Provides:
- EntropyAnchor: immutable cryptographic snapshots of knowledge state
- DriftDetector: semantic drift detection beyond bit-level comparison
- DriftSeverity: classification with operator guidance
- Re-anchoring protocol: controlled anchor evolution after legitimate change
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum, auto
from typing import Any

from hlf_mcp.hlf import insaits

# ---------------------------------------------------------------------------
# Constants (preserved from original)
# ---------------------------------------------------------------------------
DEFAULT_THRESHOLD = 0.5
HIGH_RISK_THRESHOLD = 0.65
POLICY_MODES = {"advisory", "enforce", "high_risk_enforce"}

# Drift detection constants
SEMANTIC_DRIFT_WINDOW = 100  # max token-window size for sub-sequence comparison
DRIFT_MIN_CONFIDENCE = 0.3   # minimum confidence to report drift
ANCHOR_STABILITY_WINDOW = 5  # number of stable snapshots before re-anchoring


# ---------------------------------------------------------------------------
# Drift Severity
# ---------------------------------------------------------------------------

class DriftSeverity(Enum):
    """Severity classification for detected drift with operator guidance."""
    NONE = auto()
    COSMETIC = auto()       # formatting, whitespace — no semantic change
    MINOR = auto()          # minor rewording, same intent
    MAJOR = auto()          # significant semantic divergence
    CATASTROPHIC = auto()   # complete semantic break, safety concern

    def guidance(self) -> str:
        """Operator-facing guidance for each severity level."""
        return {
            DriftSeverity.NONE: "No action required — anchors are stable.",
            DriftSeverity.COSMETIC: "Trivial formatting change detected. "
                "Review if automated re-anchoring is acceptable.",
            DriftSeverity.MINOR: "Minor semantic shift detected. "
                "Verify change is intentional before re-anchoring.",
            DriftSeverity.MAJOR: "Significant semantic divergence. "
                "Requires operator review and explicit re-anchoring approval.",
            DriftSeverity.CATASTROPHIC: "CRITICAL: complete semantic break detected. "
                "Halt branch, require multi-operator sign-off before any re-anchoring.",
        }[self]

    def requires_operator(self) -> bool:
        """Whether this severity level mandates operator intervention."""
        return self in (DriftSeverity.MAJOR, DriftSeverity.CATASTROPHIC)

    def auto_reanchor_allowed(self) -> bool:
        """Whether automatic re-anchoring is permitted at this severity."""
        return self in (DriftSeverity.NONE, DriftSeverity.COSMETIC)


# ---------------------------------------------------------------------------
# EntropyAnchor — cryptographic anchor point
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class EntropyAnchor:
    """An immutable cryptographic anchor point in the knowledge chain.

    Anchors capture the complete state of a knowledge node at a point in time,
    providing a verifiable reference for drift detection. Each anchor is
    content-addressed via SHA-256 and links to its predecessor for chain integrity.

    Attributes:
        anchor_id: Unique identifier for this anchor.
        content_hash: SHA-256 hash of the anchored content.
        content_snapshot: The full content at anchor time.
        metadata: Arbitrary metadata captured with the anchor.
        predecessor_hash: Hash of the previous anchor in the chain (None for genesis).
        created_at: Unix timestamp of anchor creation.
        sequence_number: Monotonically increasing sequence number.
        signature: HMAC-like integrity signature over anchor fields.
    """

    anchor_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content_hash: str = ""
    content_snapshot: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    predecessor_hash: str | None = None
    created_at: float = field(default_factory=time.time)
    sequence_number: int = 0
    signature: str = ""

    def __post_init__(self) -> None:
        if not self.content_hash and self.content_snapshot:
            self.content_hash = hashlib.sha256(
                self.content_snapshot.encode("utf-8")
            ).hexdigest()
        if not self.signature:
            self.signature = self._compute_signature()

    def _compute_signature(self) -> str:
        """Compute an integrity signature over anchor fields."""
        payload = json.dumps({
            "anchor_id": self.anchor_id,
            "content_hash": self.content_hash,
            "content_snapshot": self.content_snapshot,
            "predecessor_hash": self.predecessor_hash or "",
            "sequence_number": self.sequence_number,
            "created_at": self.created_at,
        }, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def verify_integrity(self) -> bool:
        """Verify this anchor's signature matches its fields."""
        return self.signature == self._compute_signature()

    def to_dict(self) -> dict[str, Any]:
        return {
            "anchor_id": self.anchor_id,
            "content_hash": self.content_hash,
            "content_snapshot": self.content_snapshot,
            "metadata": self.metadata,
            "predecessor_hash": self.predecessor_hash,
            "created_at": self.created_at,
            "sequence_number": self.sequence_number,
            "signature": self.signature,
        }

    @staticmethod
    def genesis(content: str, metadata: dict[str, Any] | None = None) -> EntropyAnchor:
        """Create the first (genesis) anchor in a chain."""
        return EntropyAnchor(
            content_snapshot=content,
            metadata=metadata or {},
            predecessor_hash=None,
            sequence_number=0,
        )

    def create_successor(self, content: str, metadata: dict[str, Any] | None = None) -> EntropyAnchor:
        """Create the next anchor in the chain, linked to this one."""
        return EntropyAnchor(
            content_snapshot=content,
            metadata=metadata or {},
            predecessor_hash=self.content_hash,
            sequence_number=self.sequence_number + 1,
        )


# ---------------------------------------------------------------------------
# EntropyAnchorResult (preserved from original — public API)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# DriftDetector — semantic drift detection
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class DriftReport:
    """Result of a drift detection run between two content states.

    Attributes:
        drift_detected: Whether any drift was found.
        severity: Classified severity of the drift.
        similarity_score: Overall similarity (0.0 - 1.0).
        structural_similarity: Similarity of structural elements (headings, sections).
        lexical_overlap: Jaccard-like word overlap ratio.
        semantic_divergence: Estimated semantic distance (0.0 = identical, 1.0 = unrelated).
        changed_sections: List of section names that changed.
        guidance: Operator-facing guidance string.
        anchor_id: The anchor this report compares against.
        compared_at: Timestamp of comparison.
    """

    drift_detected: bool
    severity: DriftSeverity
    similarity_score: float
    structural_similarity: float
    lexical_overlap: float
    semantic_divergence: float
    changed_sections: list[str] = field(default_factory=list)
    guidance: str = ""
    anchor_id: str = ""
    compared_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if not self.guidance:
            self.guidance = self.severity.guidance()

    def to_dict(self) -> dict[str, Any]:
        return {
            "drift_detected": self.drift_detected,
            "severity": self.severity.name,
            "similarity_score": self.similarity_score,
            "structural_similarity": self.structural_similarity,
            "lexical_overlap": self.lexical_overlap,
            "semantic_divergence": self.semantic_divergence,
            "changed_sections": self.changed_sections,
            "guidance": self.guidance,
            "anchor_id": self.anchor_id,
            "compared_at": self.compared_at,
        }


class DriftDetector:
    """Detects semantic drift between knowledge states and anchors.

    Goes beyond bit-level comparison by analyzing structural, lexical, and
    semantic dimensions of change. Classifies drift severity and provides
    operator guidance for each detection.
    """

    def __init__(self, similarity_threshold: float = 0.7) -> None:
        """Initialize the drift detector.

        Args:
            similarity_threshold: Overall similarity below which drift is
                considered detected (0.0 - 1.0).
        """
        self._threshold = max(0.0, min(1.0, similarity_threshold))

    def detect(
        self,
        current_content: str,
        anchor: EntropyAnchor,
        current_metadata: dict[str, Any] | None = None,
    ) -> DriftReport:
        """Detect drift between current content and an anchored snapshot.

        Args:
            current_content: The current knowledge content to check.
            anchor: The EntropyAnchor to compare against.
            current_metadata: Optional metadata about the current state.

        Returns:
            DriftReport with full analysis.
        """
        if not anchor.verify_integrity():
            return DriftReport(
                drift_detected=True,
                severity=DriftSeverity.CATASTROPHIC,
                similarity_score=0.0,
                structural_similarity=0.0,
                lexical_overlap=0.0,
                semantic_divergence=1.0,
                changed_sections=[],
                guidance="Anchor integrity check FAILED — anchor may be corrupted.",
                anchor_id=anchor.anchor_id,
            )

        # Compute similarity dimensions
        structural_sim = self._structural_similarity(
            anchor.content_snapshot, current_content
        )
        lexical_overlap = self._lexical_overlap(
            anchor.content_snapshot, current_content
        )
        semantic_div = self._semantic_divergence(
            anchor.content_snapshot, current_content
        )

        # Weighted composite similarity
        similarity = (
            0.25 * structural_sim
            + 0.35 * lexical_overlap
            + 0.40 * (1.0 - semantic_div)
        )
        similarity = round(max(0.0, min(1.0, similarity)), 4)

        drift_detected = similarity < self._threshold
        changed_sections = self._find_changed_sections(
            anchor.content_snapshot, current_content
        )

        severity = self._classify_severity(
            drift_detected=drift_detected,
            structural_sim=structural_sim,
            lexical_overlap=lexical_overlap,
            semantic_div=semantic_div,
            has_changed_sections=len(changed_sections) > 0,
        )

        return DriftReport(
            drift_detected=drift_detected,
            severity=severity,
            similarity_score=similarity,
            structural_similarity=round(structural_sim, 4),
            lexical_overlap=round(lexical_overlap, 4),
            semantic_divergence=round(semantic_div, 4),
            changed_sections=changed_sections,
            anchor_id=anchor.anchor_id,
        )

    def detect_batch(
        self,
        current_content: str,
        anchors: list[EntropyAnchor],
    ) -> list[DriftReport]:
        """Run drift detection against multiple anchors.

        Args:
            current_content: The current knowledge content.
            anchors: List of EntropyAnchors to compare against.

        Returns:
            List of DriftReports, one per anchor.
        """
        return [self.detect(current_content, anchor) for anchor in anchors]

    def severity_summary(self, reports: list[DriftReport]) -> dict[str, Any]:
        """Aggregate severity across multiple drift reports.

        Args:
            reports: List of DriftReports to summarize.

        Returns:
            Dict with severity counts, worst severity, and consensus assessment.
        """
        if not reports:
            return {
                "total": 0,
                "counts": {},
                "worst_severity": DriftSeverity.NONE.name,
                "requires_operator": False,
                "consensus": "No reports to evaluate.",
            }

        counts: dict[str, int] = {}
        worst = DriftSeverity.NONE
        for r in reports:
            counts[r.severity.name] = counts.get(r.severity.name, 0) + 1
            if r.severity.value > worst.value:
                worst = r.severity

        needs_op = any(r.severity.requires_operator() for r in reports)

        if worst == DriftSeverity.NONE:
            consensus = "All anchors stable — no drift across any comparison."
        elif worst == DriftSeverity.COSMETIC:
            consensus = "Minor formatting differences only — safe to proceed."
        elif worst == DriftSeverity.MINOR:
            consensus = "Minor semantic shifts detected — review recommended."
        elif worst == DriftSeverity.MAJOR:
            consensus = "Significant drift detected — operator review REQUIRED."
        else:
            consensus = "CATASTROPHIC drift — halt and escalate immediately."

        return {
            "total": len(reports),
            "counts": counts,
            "worst_severity": worst.name,
            "worst_guidance": worst.guidance(),
            "requires_operator": needs_op,
            "consensus": consensus,
        }

    # ------------------------------------------------------------------
    # Internal analysis methods
    # ------------------------------------------------------------------

    @staticmethod
    def _structural_similarity(original: str, current: str) -> float:
        """Compare structural elements: line count, paragraph count, heading structure."""
        orig_lines = original.strip().splitlines()
        curr_lines = current.strip().splitlines()

        if not orig_lines and not curr_lines:
            return 1.0
        if not orig_lines or not curr_lines:
            return 0.0

        # Line count ratio
        line_ratio = min(len(orig_lines), len(curr_lines)) / max(
            len(orig_lines), len(curr_lines)
        )

        # Heading structure similarity
        orig_headings = [l.strip() for l in orig_lines if l.strip().startswith("#")]
        curr_headings = [l.strip() for l in curr_lines if l.strip().startswith("#")]
        heading_overlap = 1.0  # default: both have same (no) headings
        if orig_headings or curr_headings:
            orig_set = set(orig_headings)
            curr_set = set(curr_headings)
            union = orig_set | curr_set
            heading_overlap = (
                len(orig_set & curr_set) / len(union) if union else 1.0
            )

        return round(0.5 * line_ratio + 0.5 * heading_overlap, 4)

    @staticmethod
    def _lexical_overlap(original: str, current: str) -> float:
        """Compute Jaccard-like word overlap between two texts."""
        def tokenize(text: str) -> set[str]:
            import re
            return set(re.findall(r"[a-z0-9]+", text.lower()))

        orig_tokens = tokenize(original)
        curr_tokens = tokenize(current)

        if not orig_tokens and not curr_tokens:
            return 1.0
        if not orig_tokens or not curr_tokens:
            return 0.0

        intersection = orig_tokens & curr_tokens
        union = orig_tokens | curr_tokens
        return round(len(intersection) / len(union), 4)

    @staticmethod
    def _semantic_divergence(original: str, current: str) -> float:
        """Estimate semantic divergence using n-gram overlap as a proxy.

        Uses character-level n-grams (n=3..5) as a lightweight semantic proxy.
        Returns 0.0 for identical, 1.0 for completely unrelated content.
        """
        def ngrams(text: str, n: int) -> set[str]:
            t = text.lower()
            return {t[i:i + n] for i in range(len(t) - n + 1)}

        if original == current:
            return 0.0
        if not original or not current:
            return 1.0

        scores: list[float] = []
        for n in (3, 4, 5):
            orig_ng = ngrams(original, n)
            curr_ng = ngrams(current, n)
            if not orig_ng or not curr_ng:
                scores.append(1.0)
                continue
            intersection = orig_ng & curr_ng
            union = orig_ng | curr_ng
            scores.append(1.0 - len(intersection) / len(union))

        return round(sum(scores) / len(scores), 4)

    @staticmethod
    def _find_changed_sections(
        original: str, current: str
    ) -> list[str]:
        """Identify which sections (heading-delimited blocks) changed."""
        import re

        def extract_sections(text: str) -> dict[str, str]:
            sections: dict[str, str] = {}
            pattern = re.compile(r"^(#{1,6}\s+.+)$", re.MULTILINE)
            matches = list(pattern.finditer(text))
            for i, m in enumerate(matches):
                start = m.end()
                end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
                sections[m.group(1).strip()] = text[start:end].strip()
            if not matches and text.strip():
                sections["(no heading)"] = text.strip()
            return sections

        orig_sec = extract_sections(original)
        curr_sec = extract_sections(current)

        changed: list[str] = []
        all_headings = set(orig_sec.keys()) | set(curr_sec.keys())
        for heading in sorted(all_headings):
            o = orig_sec.get(heading, "")
            c = curr_sec.get(heading, "")
            if o != c:
                changed.append(heading)

        return changed

    @staticmethod
    def _classify_severity(
        *,
        drift_detected: bool,
        structural_sim: float,
        lexical_overlap: float,
        semantic_div: float,
        has_changed_sections: bool,
    ) -> DriftSeverity:
        """Classify drift severity from dimensional scores."""
        if not drift_detected:
            return DriftSeverity.NONE

        if semantic_div >= 0.8:
            return DriftSeverity.CATASTROPHIC
        if semantic_div >= 0.5:
            return DriftSeverity.MAJOR
        if semantic_div >= 0.2 or lexical_overlap < 0.7:
            return DriftSeverity.MINOR
        if has_changed_sections:
            return DriftSeverity.COSMETIC

        return DriftSeverity.NONE


# ---------------------------------------------------------------------------
# Re-anchoring protocol
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class ReAnchorDecision:
    """Result of evaluating whether to create a new anchor.

    Attributes:
        should_reanchor: Whether a new anchor should be created.
        reason: Human-readable rationale.
        drift_report: The DriftReport that triggered this evaluation.
        approval_required: Whether operator approval is needed.
        auto_approved: Whether re-anchoring can proceed automatically.
        recommended_metadata: Suggested metadata for the new anchor.
    """

    should_reanchor: bool
    reason: str
    drift_report: DriftReport | None = None
    approval_required: bool = False
    auto_approved: bool = False
    recommended_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "should_reanchor": self.should_reanchor,
            "reason": self.reason,
            "approval_required": self.approval_required,
            "auto_approved": self.auto_approved,
            "recommended_metadata": self.recommended_metadata,
            "drift_report": self.drift_report.to_dict() if self.drift_report else None,
        }


class ReAnchoringProtocol:
    """Manages the controlled evolution of entropy anchors.

    Determines when and how to establish new anchors after legitimate
    knowledge evolution, preventing anchor rot while maintaining chain
    integrity.
    """

    def __init__(self) -> None:
        self._anchor_chain: list[EntropyAnchor] = []
        self._stability_counter: dict[str, int] = {}  # content_hash → consecutive stable checks

    def evaluate(
        self,
        current_content: str,
        drift_report: DriftReport,
        force: bool = False,
    ) -> ReAnchorDecision:
        """Evaluate whether to create a new anchor based on drift analysis.

        Args:
            current_content: The current knowledge content.
            drift_report: Drift detection result against the latest anchor.
            force: If True, bypass severity checks and re-anchor.

        Returns:
            ReAnchorDecision with guidance.
        """
        if not drift_report.drift_detected and not force:
            # Track stability
            h = hashlib.sha256(current_content.encode()).hexdigest()
            self._stability_counter[h] = self._stability_counter.get(h, 0) + 1
            return ReAnchorDecision(
                should_reanchor=False,
                reason="No drift detected — anchor remains stable.",
                drift_report=drift_report,
                approval_required=False,
                auto_approved=False,
            )

        severity = drift_report.severity

        if force:
            return ReAnchorDecision(
                should_reanchor=True,
                reason="Forced re-anchoring requested by operator.",
                drift_report=drift_report,
                approval_required=False,
                auto_approved=True,
                recommended_metadata={"force_reanchor": True},
            )

        if severity == DriftSeverity.NONE:
            return ReAnchorDecision(
                should_reanchor=False,
                reason="No semantic change — re-anchoring unnecessary.",
                drift_report=drift_report,
                approval_required=False,
                auto_approved=False,
            )

        if severity == DriftSeverity.COSMETIC:
            return ReAnchorDecision(
                should_reanchor=True,
                reason="Cosmetic change — auto-reanchoring.",
                drift_report=drift_report,
                approval_required=False,
                auto_approved=True,
                recommended_metadata={"reanchor_trigger": "cosmetic_drift"},
            )

        if severity == DriftSeverity.MINOR:
            return ReAnchorDecision(
                should_reanchor=True,
                reason="Minor semantic shift — re-anchoring with advisory note.",
                drift_report=drift_report,
                approval_required=False,
                auto_approved=True,
                recommended_metadata={
                    "reanchor_trigger": "minor_drift",
                    "operator_note": "Review drift report for intentionality.",
                },
            )

        if severity == DriftSeverity.MAJOR:
            return ReAnchorDecision(
                should_reanchor=False,
                reason="Major drift requires operator approval before re-anchoring.",
                drift_report=drift_report,
                approval_required=True,
                auto_approved=False,
                recommended_metadata={"reanchor_trigger": "major_drift"},
            )

        # CATASTROPHIC
        return ReAnchorDecision(
            should_reanchor=False,
            reason="CATASTROPHIC drift — re-anchoring BLOCKED pending multi-operator review.",
            drift_report=drift_report,
            approval_required=True,
            auto_approved=False,
            recommended_metadata={
                "reanchor_trigger": "catastrophic_drift",
                "requires": "multi_operator_signoff",
            },
        )

    def execute_reanchor(
        self,
        current_content: str,
        decision: ReAnchorDecision,
        metadata_override: dict[str, Any] | None = None,
    ) -> EntropyAnchor:
        """Create a new anchor in the chain after approval.

        Args:
            current_content: Content to anchor.
            decision: The ReAnchorDecision authorizing this action.
            metadata_override: Optional metadata to merge/replace.

        Returns:
            The newly created EntropyAnchor.

        Raises:
            ValueError: If re-anchoring is not approved.
        """
        if not decision.should_reanchor:
            raise ValueError(
                f"Cannot re-anchor: {decision.reason}"
            )
        if decision.approval_required and not (
            metadata_override or {}
        ).get("operator_approved"):
            raise ValueError(
                f"Re-anchoring requires operator approval: {decision.reason}"
            )

        metadata = {**decision.recommended_metadata, **(metadata_override or {})}
        metadata["reanchor_timestamp"] = time.time()
        metadata["reanchor_reason"] = decision.reason

        if self._anchor_chain:
            predecessor = self._anchor_chain[-1]
            new_anchor = predecessor.create_successor(current_content, metadata)
        else:
            new_anchor = EntropyAnchor.genesis(current_content, metadata)

        self._anchor_chain.append(new_anchor)
        return new_anchor

    def get_chain(self) -> list[EntropyAnchor]:
        """Return the current anchor chain (defensive copy)."""
        return list(self._anchor_chain)

    def get_latest(self) -> EntropyAnchor | None:
        """Return the most recent anchor, or None if chain is empty."""
        return self._anchor_chain[-1] if self._anchor_chain else None

    def verify_chain_integrity(self) -> dict[str, Any]:
        """Verify the entire anchor chain for integrity.

        Returns:
            Dict with chain validity, broken links, and chain length.
        """
        broken: list[int] = []
        for i, anchor in enumerate(self._anchor_chain):
            if not anchor.verify_integrity():
                broken.append(i)
                continue
            if i > 0 and anchor.predecessor_hash != self._anchor_chain[i - 1].content_hash:
                broken.append(i)

        return {
            "valid": len(broken) == 0,
            "chain_length": len(self._anchor_chain),
            "broken_at_indices": broken,
            "broken_count": len(broken),
        }


# ---------------------------------------------------------------------------
# Original helper functions (preserved for backward compatibility)
# ---------------------------------------------------------------------------

def _resolve_threshold(policy_mode: str, threshold: float | None) -> float:
    if policy_mode not in POLICY_MODES:
        raise ValueError(f"policy_mode must be one of {sorted(POLICY_MODES)}, got {policy_mode!r}")
    effective_threshold = (
        HIGH_RISK_THRESHOLD if policy_mode == "high_risk_enforce" else DEFAULT_THRESHOLD
    )
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
