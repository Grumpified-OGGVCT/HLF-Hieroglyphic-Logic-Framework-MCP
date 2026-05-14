"""
Tests for operator-proof surface endpoints (governed, explainable, verifiable).

Covers:
  1. Route evidence summary format — GovernedRouteVerdict + RouteProfile rationales
  2. Verifier result readability — formal verifier findings → plain-English explainer
  3. Provenance trace completeness — memory provenance with hash-chain linkage
  4. Promotion rationale format — HKS promotion-eligible artifacts with justification
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure the hlf_mcp package is importable
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from hlf_mcp.server_resources import (  # noqa: E402
    _explain_verifier_finding,
    _render_memory_provenance_markdown,
    _render_memory_provenance_status,
    _render_promotion_rationale_markdown,
    _render_promotion_rationale_status,
    _render_route_evidence_markdown,
    _render_route_evidence_status,
    _render_verifier_explainer_markdown,
    _render_verifier_explainer_status,
)


# ── Route evidence tests ────────────────────────────────────────────────────


def test_route_evidence_status_no_context():
    """Returns error JSON when ctx is None."""
    result = _render_route_evidence_status(None)
    data = json.loads(result)
    assert data["status"] == "error"
    assert "context_unavailable" in data["error"]


def test_route_evidence_status_not_found():
    """Returns not_found when get_governed_route returns None."""
    ctx = MagicMock()
    ctx.get_governed_route.return_value = None
    result = _render_route_evidence_status(ctx)
    data = json.loads(result)
    assert data["status"] == "not_found"


def test_route_evidence_status_with_trace():
    """Returns structured verdict with fields from route trace."""
    ctx = MagicMock()
    ctx.get_governed_route.return_value = {
        "agent_id": "test-agent",
        "route_decision": {
            "allowed": True,
            "decision": "approved",
            "governance_mode": "trusted",
            "review_required": False,
            "selected_lane": "A",
            "primary_model": "gpt-4o",
            "rationale": ["Model qualified", "Benchmark passed"],
        },
        "operator_summary": "Route approved via tier walk.",
        "escalation_depth": 1,
        "latency_s": 0.45,
    }
    result = _render_route_evidence_status(ctx)
    data = json.loads(result)
    assert data["status"] == "ok"
    assert data["verdict"]["allowed"] is True
    assert data["verdict"]["decision"] == "approved"
    assert data["verdict"]["selected_lane"] == "A"
    assert "Model qualified" in data["verdict"]["rationale"]
    assert data["escalation_depth"] == 1


def test_route_evidence_status_with_agent_id():
    """Passes agent_id through to get_governed_route."""
    ctx = MagicMock()
    ctx.get_governed_route.return_value = {
        "agent_id": "specific-agent",
        "route_decision": {"decision": "approved", "selected_lane": "B"},
    }
    result = _render_route_evidence_status(ctx, agent_id="specific-agent")
    data = json.loads(result)
    ctx.get_governed_route.assert_called_once_with(agent_id="specific-agent")
    assert data["agent_id"] == "specific-agent"


def test_route_evidence_markdown_no_context():
    """Returns error markdown when ctx is None."""
    result = _render_route_evidence_markdown(None)
    assert "context unavailable" in result.lower()


def test_route_evidence_markdown_with_trace():
    """Returns human-readable markdown with decision details."""
    ctx = MagicMock()
    ctx.get_governed_route.return_value = {
        "route_decision": {
            "decision": "approved",
            "selected_lane": "A+",
            "primary_model": "claude-4",
            "governance_mode": "trusted",
            "review_required": False,
            "rationale": ["High confidence benchmark evidence"],
        },
        "operator_summary": "Trusted lane selected.",
    }
    result = _render_route_evidence_markdown(ctx)
    assert "# Route Evidence Report" in result
    assert "`approved`" in result
    assert "`A+`" in result
    assert "`claude-4`" in result
    assert "High confidence benchmark evidence" in result


def test_route_evidence_markdown_advisory_mode():
    """Shows advisory mode warning when applicable."""
    ctx = MagicMock()
    ctx.get_governed_route.return_value = {
        "route_decision": {"decision": "denied", "selected_lane": "advisory"},
        "advisory_mode": True,
        "governance_warning": "Proceeding without governance.",
    }
    result = _render_route_evidence_markdown(ctx)
    assert "Advisory mode" in result
    assert "Proceeding without governance" in result


# ── Verifier explainer tests ────────────────────────────────────────────────


def test_explain_verifier_finding_error():
    """Maps error severity to plain-English."""
    result = _explain_verifier_finding("error", "type_invariant", "Expected int, got str")
    assert "A problem was found" in result
    assert "type safety" in result
    assert "Expected int, got str" in result


def test_explain_verifier_finding_warning():
    """Maps warning severity with category phrase."""
    result = _explain_verifier_finding("warning", "gas_bound", "Gas estimate exceeds budget")
    assert "A caution is raised" in result
    assert "gas budget" in result


def test_explain_verifier_finding_info():
    """Maps info severity generically."""
    result = _explain_verifier_finding("info", "unknown_category", "FYI check")
    assert "Note" in result


def test_verifier_explainer_status_no_context():
    """Returns error when ctx is None."""
    result = _render_verifier_explainer_status(None)
    data = json.loads(result)
    assert data["status"] == "error"


def test_verifier_explainer_status_with_findings():
    """Includes plain-English for each finding."""
    ctx = MagicMock()
    ctx.get_execution_admission.return_value = {
        "verification": {
            "passed": False,
            "findings": [
                {
                    "severity": "error",
                    "category": "type_invariant",
                    "message": "Type mismatch in return",
                    "location": "line 12",
                },
                {
                    "severity": "warning",
                    "category": "gas_bound",
                    "message": "Gas usage near ceiling",
                },
            ],
            "summary": {"errors": 1, "warnings": 1},
        },
    }
    result = _render_verifier_explainer_status(ctx)
    data = json.loads(result)
    assert data["status"] == "ok"
    assert data["passed"] is False
    assert data["total_findings"] == 2
    assert data["error_count"] == 1
    assert data["warning_count"] == 1
    assert len(data["findings"]) == 2
    assert "plain_english" in data["findings"][0]
    assert "Type mismatch" in data["findings"][0]["message"]


def test_verifier_explainer_markdown_with_findings():
    """Produces markdown with icon'd severity sections."""
    ctx = MagicMock()
    ctx.get_execution_admission.return_value = {
        "verification": {
            "passed": False,
            "findings": [
                {"severity": "error", "category": "null_safety", "message": "None not handled"},
                {"severity": "info", "category": "spec_gate", "message": "All gates nominal"},
            ],
        },
    }
    result = _render_verifier_explainer_markdown(ctx)
    assert "# Formal Verifier" in result
    assert "🔴" in result
    assert "ERROR" in result
    assert "null_safety" in result
    assert "None not handled" in result


def test_verifier_explainer_markdown_passed():
    """Shows success when all checks pass."""
    ctx = MagicMock()
    ctx.get_execution_admission.return_value = {
        "verification": {"passed": True, "findings": []},
    }
    result = _render_verifier_explainer_markdown(ctx)
    assert "All checks passed" in result


# ── Promotion rationale tests ───────────────────────────────────────────────


def test_promotion_rationale_status_no_store():
    """Returns error when memory store unavailable."""
    result = _render_promotion_rationale_status(None)
    data = json.loads(result)
    assert data["status"] == "error"


def test_promotion_rationale_status_empty():
    """Returns empty candidates list when no HKS exemplars."""
    ctx = MagicMock()
    ctx.memory_store.query_facts.return_value = []
    result = _render_promotion_rationale_status(ctx)
    data = json.loads(result)
    assert data["status"] == "ok"
    assert data["total"] == 0
    assert data["promotion_candidates"] == []


def test_promotion_rationale_status_with_candidates():
    """Marks confidence >= 0.8 as promotion-eligible."""
    ctx = MagicMock()
    ctx.memory_store.query_facts.return_value = [
        {
            "id": 1,
            "topic": "auth-pattern",
            "domain": "security",
            "confidence": 0.92,
            "provenance": "git:abc123",
            "summary": "Validated auth fix pattern",
            "tests": [{"name": "test_auth"}],
        },
        {
            "id": 2,
            "topic": "wip-pattern",
            "domain": "general",
            "confidence": 0.45,
            "provenance": "git:def456",
        },
    ]
    result = _render_promotion_rationale_status(ctx)
    data = json.loads(result)
    assert data["total"] == 2
    assert data["promotion_candidates"][0]["promotion_eligible"] is True
    assert data["promotion_candidates"][1]["promotion_eligible"] is False


def test_promotion_rationale_markdown():
    """Produces markdown with eligible/not-eligible badges."""
    ctx = MagicMock()
    ctx.memory_store.query_facts.return_value = [
        {
            "topic": "good-exemplar",
            "domain": "backend",
            "confidence": 0.95,
            "provenance": "repo:main",
            "tests": [{"name": "test_x"}],
            "summary": "Proven solution.",
        },
        {
            "topic": "weak-exemplar",
            "domain": "frontend",
            "confidence": 0.55,
            "provenance": "draft",
        },
    ]
    result = _render_promotion_rationale_markdown(ctx)
    assert "# HKS Promotion Rationale" in result
    assert "✅" in result
    assert "❌" in result
    assert "good-exemplar" in result
    assert "weak-exemplar" in result
    assert "0.95" in result
    assert "0.55" in result


# ── Memory provenance tests ─────────────────────────────────────────────────


def test_memory_provenance_status_no_store():
    """Returns error when memory store unavailable."""
    result = _render_memory_provenance_status(None)
    data = json.loads(result)
    assert data["status"] == "error"


def test_memory_provenance_status_with_traces():
    """Returns provenance traces with hash and authority data."""
    ctx = MagicMock()
    ctx.memory_store.query_facts.return_value = [
        {
            "id": 1,
            "sha256": "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            "topic": "routing-decision",
            "provenance": "hlf_governed_complete:session-42",
            "source_authority_label": "canonical",
            "confidence": 0.99,
            "fresh_until": "2027-01-01",
        },
    ]
    result = _render_memory_provenance_status(ctx)
    data = json.loads(result)
    assert data["status"] == "ok"
    assert data["total_traced"] == 1
    assert data["provenance_traces"][0]["topic"] == "routing-decision"
    assert data["provenance_traces"][0]["source_authority_label"] == "canonical"


def test_memory_provenance_markdown():
    """Produces markdown with hash chain details."""
    ctx = MagicMock()
    ctx.memory_store.query_facts.return_value = [
        {
            "sha256": "abc123def456abc123def456abc123def456abc123def456abc123def456abc123",
            "topic": "deployment-pattern",
            "provenance": "HKS capture: workflow-run-99",
            "source_authority_label": "canonical",
            "confidence": 0.88,
            "fresh_until": "never",
        },
    ]
    ctx.memory_store.stats.return_value = {"total_facts": 1}
    result = _render_memory_provenance_markdown(ctx)
    assert "# Memory Provenance" in result
    assert "deployment-pattern" in result
    assert "abc123def456…" in result
    assert "HKS capture" in result
    assert "canonical" in result
    assert "provenance chain" in result.lower()


def test_memory_provenance_markdown_empty():
    """Shows empty message when no provenance facts exist."""
    ctx = MagicMock()
    ctx.memory_store.query_facts.return_value = []
    result = _render_memory_provenance_markdown(ctx)
    assert "No provenance-bearing facts" in result


def test_memory_provenance_markdown_superseded():
    """Shows superseded warning."""
    ctx = MagicMock()
    ctx.memory_store.query_facts.return_value = [
        {
            "sha256": "oldhash123456oldhash123456oldhash123456oldhash123456oldhash123456oldhash123456",
            "topic": "stale-pattern",
            "provenance": "git:old-commit",
            "source_authority_label": "advisory",
            "confidence": 0.7,
            "fresh_until": "2025-01-01",
            "superseded_by": "newhash999",
        },
    ]
    result = _render_memory_provenance_markdown(ctx)
    assert "Superseded" in result
    assert "newhash999" in result
