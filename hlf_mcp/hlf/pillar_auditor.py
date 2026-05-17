"""
HLF Pillar Compliance Auditor — verify inter-agent HLF communication quality.

Checks that agent-to-agent HLF messages contain all required pillars
for valid, verifiable, governable coordination.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from hlf_mcp.hlf.grammar import GLYPHS, TAGS


# ── Pillar Definitions ───────────────────────────────────────────────────────

# Core communication pillars: every inter-agent HLF message MUST have these
CORE_PILLARS = ["INTENT"]

# Verification pillars: messages that carry commitments MUST have one of these
VERIFY_PILLARS = ["ASSERT", "EXPECT", "RESULT"]

# Governance pillars: multi-agent coordination MUST have these
GOVERNANCE_PILLARS = ["VOTE", "CONSTRAINT"]

# Delegation pillars: messages that hand off work MUST have these
DELEGATION_PILLARS = ["DELEGATE", "ROUTE"]

# Complete pillar set for full compliance
ALL_PILLARS = sorted(set(CORE_PILLARS + VERIFY_PILLARS + GOVERNANCE_PILLARS + DELEGATION_PILLARS))

# Glyph roles that SHOULD be represented for a complete message
CORE_GLYPH_ROLES = ["analyze", "enforce", "consensus"]


@dataclass
class PillarAudit:
    """Result of auditing a single HLF message for pillar compliance."""

    source: str
    audit_id: str

    # Presence checks
    has_intent: bool = False
    has_assert: bool = False
    has_expect: bool = False
    has_result: bool = False
    has_vote: bool = False
    has_constraint: bool = False
    has_delegate: bool = False
    has_route: bool = False

    # Coverage
    core_pillars_found: list[str] = field(default_factory=list)
    core_pillars_missing: list[str] = field(default_factory=list)
    verify_pillars_found: list[str] = field(default_factory=list)
    verify_pillars_missing: list[str] = field(default_factory=list)
    governance_pillars_found: list[str] = field(default_factory=list)
    governance_pillars_missing: list[str] = field(default_factory=list)
    delegation_pillars_found: list[str] = field(default_factory=list)
    delegation_pillars_missing: list[str] = field(default_factory=list)

    # Quality
    tags_used: list[str] = field(default_factory=list)
    glyphs_used: list[str] = field(default_factory=list)
    roles_used: list[str] = field(default_factory=list)
    unknown_tags: list[str] = field(default_factory=list)

    # Scores
    core_score: float = 0.0  # INTENT present = 1.0
    verify_score: float = 0.0  # At least one of ASSERT/EXPECT/RESULT
    governance_score: float = 0.0  # VOTE + CONSTRAINT
    delegation_score: float = 0.0  # DELEGATE or ROUTE if needed
    glyph_diversity_score: float = 0.0  # How many distinct glyph roles
    overall_score: float = 0.0

    # Verdict
    compliant: bool = False
    severity: str = "info"  # info | warning | error | critical
    findings: list[str] = field(default_factory=list)


class PillarComplianceAuditor:
    """Audit HLF messages for pillar compliance."""

    def __init__(self) -> None:
        self.tag_names = set(TAGS.keys())
        self.glyph_roles = {g["role"] for g in GLYPHS.values()}

    def audit(self, source: str, audit_id: str = "") -> PillarAudit:
        """Audit an HLF source string for pillar compliance."""
        result = PillarAudit(source=source, audit_id=audit_id or "audit-0")

        # Extract tags and glyphs
        result.tags_used = self._extract_tags(source)
        result.glyphs_used = self._extract_glyphs(source)
        result.roles_used = self._extract_roles(source)
        result.unknown_tags = [t for t in result.tags_used if t not in self.tag_names]

        # Presence checks
        result.has_intent = "INTENT" in result.tags_used
        result.has_assert = "ASSERT" in result.tags_used
        result.has_expect = "EXPECT" in result.tags_used
        result.has_result = "RESULT" in result.tags_used
        result.has_vote = "VOTE" in result.tags_used
        result.has_constraint = "CONSTRAINT" in result.tags_used
        result.has_delegate = "DELEGATE" in result.tags_used
        result.has_route = "ROUTE" in result.tags_used

        # Core pillars
        result.core_pillars_found = [p for p in CORE_PILLARS if p in result.tags_used]
        result.core_pillars_missing = [p for p in CORE_PILLARS if p not in result.tags_used]

        # Verify pillars
        result.verify_pillars_found = [p for p in VERIFY_PILLARS if p in result.tags_used]
        result.verify_pillars_missing = [p for p in VERIFY_PILLARS if p not in result.tags_used]

        # Governance pillars
        result.governance_pillars_found = [p for p in GOVERNANCE_PILLARS if p in result.tags_used]
        result.governance_pillars_missing = [p for p in GOVERNANCE_PILLARS if p not in result.tags_used]

        # Delegation pillars
        result.delegation_pillars_found = [p for p in DELEGATION_PILLARS if p in result.tags_used]
        result.delegation_pillars_missing = [p for p in DELEGATION_PILLARS if p not in result.tags_used]

        # Scores
        result.core_score = len(result.core_pillars_found) / max(len(CORE_PILLARS), 1)
        result.verify_score = 1.0 if result.verify_pillars_found else 0.0
        result.governance_score = len(result.governance_pillars_found) / max(len(GOVERNANCE_PILLARS), 1)
        result.delegation_score = len(result.delegation_pillars_found) / max(len(DELEGATION_PILLARS), 1)
        result.glyph_diversity_score = len(set(result.roles_used)) / max(len(CORE_GLYPH_ROLES), 1)

        # Overall: weighted average
        result.overall_score = (
            result.core_score * 0.30
            + result.verify_score * 0.25
            + result.governance_score * 0.20
            + result.glyph_diversity_score * 0.15
            + (1.0 if not result.unknown_tags else 0.5) * 0.10
        )

        # Findings
        result.findings = self._generate_findings(result)

        # Severity
        if result.core_score < 1.0:
            result.severity = "critical"
        elif result.verify_score < 1.0:
            result.severity = "error"
        elif result.governance_score < 1.0:
            result.severity = "warning"
        elif result.unknown_tags:
            result.severity = "warning"
        else:
            result.severity = "info"

        result.compliant = result.severity in ("info", "warning")
        return result

    def audit_conversation(self, messages: list[dict[str, Any]], conversation_id: str = "") -> list[PillarAudit]:
        """Audit a sequence of HLF messages (e.g., a swarm conversation)."""
        results = []
        for i, msg in enumerate(messages):
            source = msg.get("hlf", msg.get("source", ""))
            audit_id = f"{conversation_id or 'conv'}-msg-{i}"
            results.append(self.audit(source, audit_id))
        return results

    def _extract_tags(self, source: str) -> list[str]:
        """Extract canonical tag names from HLF source."""
        import re
        tags = re.findall(r'\[([A-Z][A-Z_0-9]*)\]', source)
        return sorted(set(tags))

    def _extract_glyphs(self, source: str) -> list[str]:
        """Extract Unicode glyph characters from HLF source."""
        return sorted({c for c in source if c in GLYPHS})

    def _extract_roles(self, source: str) -> list[str]:
        """Extract glyph roles used in HLF source."""
        roles = []
        for glyph_char, info in GLYPHS.items():
            if glyph_char in source:
                roles.append(info["role"])
        return sorted(set(roles))

    def _generate_findings(self, audit: PillarAudit) -> list[str]:
        """Generate human-readable findings."""
        findings = []
        if not audit.has_intent:
            findings.append("CRITICAL: Missing INTENT tag — every HLF message must declare intent")
        if not audit.verify_pillars_found:
            findings.append("ERROR: No verification pillar (ASSERT, EXPECT, or RESULT) — commitments are unverifiable")
        if audit.governance_pillars_missing:
            findings.append(f"WARNING: Missing governance pillars: {audit.governance_pillars_missing}")
        if audit.unknown_tags:
            findings.append(f"WARNING: Unknown tags used: {audit.unknown_tags}")
        if audit.glyph_diversity_score < 1.0:
            missing_roles = [r for r in CORE_GLYPH_ROLES if r not in audit.roles_used]
            findings.append(f"INFO: Missing glyph roles: {missing_roles}")
        if not findings:
            findings.append("INFO: Full pillar compliance — message is well-formed for agent coordination")
        return findings

    @staticmethod
    def summarize_audits(audits: list[PillarAudit]) -> dict[str, Any]:
        """Summarize a list of audits into aggregate metrics."""
        if not audits:
            return {"count": 0, "avg_score": 0.0, "compliance_rate": 0.0}

        scores = [a.overall_score for a in audits]
        compliant_count = sum(1 for a in audits if a.compliant)
        critical_count = sum(1 for a in audits if a.severity == "critical")
        error_count = sum(1 for a in audits if a.severity == "error")

        # Track which pillars are most often missing
        missing_counts: dict[str, int] = {}
        for a in audits:
            for p in a.core_pillars_missing + a.verify_pillars_missing + a.governance_pillars_missing:
                missing_counts[p] = missing_counts.get(p, 0) + 1

        return {
            "count": len(audits),
            "avg_score": round(sum(scores) / len(scores), 3),
            "min_score": round(min(scores), 3),
            "max_score": round(max(scores), 3),
            "compliance_rate": round(compliant_count / len(audits), 3),
            "critical_count": critical_count,
            "error_count": error_count,
            "warning_count": sum(1 for a in audits if a.severity == "warning"),
            "info_count": sum(1 for a in audits if a.severity == "info"),
            "most_missing_pillars": sorted(missing_counts.items(), key=lambda x: -x[1])[:5],
        }
