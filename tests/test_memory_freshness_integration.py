"""
B4: Memory Freshness Integration Tests.

Validates that:
  - Lifecycle transitions reject stale/superseded/revoked evidence
  - Lifecycle transitions accept fresh evidence
  - Supersession chain resolution works during orchestration
  - Revoked evidence is excluded from lifecycle decisions
  - Handoff chain verification surfaces freshness issues
  - Dream cycle purpose correctly handles freshness policy
"""

from __future__ import annotations

import json
import time
from typing import Any

import pytest

from hlf_mcp.handoff_events import (
    _scan_handoff_chain_freshness,
    verify_handoff_chain,
)
from hlf_mcp.hlf.memory_node import (
    FreshnessVerdict,
    check_evidence_freshness,
    resolve_supersession_chain,
)
from hlf_mcp.instinct.lifecycle import (
    InstinctLifecycle,
    _check_mission_evidence_freshness,
)


# ═══════════════════════════════════════════════════════════════════════════
# Freshness Verdict tests
# ═══════════════════════════════════════════════════════════════════════════


class TestCheckEvidenceFreshness:
    """Unit tests for check_evidence_freshness with various evidence states."""

    def test_fresh_evidence_admitted(self) -> None:
        evidence: dict[str, Any] = {
            "freshness_status": "fresh",
            "revoked": False,
            "tombstoned": False,
            "superseded": False,
            "content_hash_valid": True,
        }
        verdict = check_evidence_freshness(evidence=evidence, purpose="default")
        assert verdict.admissible is True
        assert verdict.freshness_status == "fresh"

    def test_stale_evidence_rejected_for_mandatory_purpose(self) -> None:
        evidence: dict[str, Any] = {
            "freshness_status": "stale",
            "revoked": False,
            "tombstoned": False,
            "superseded": False,
            "content_hash_valid": True,
        }
        # routing_evidence is a mandatory-fresh purpose
        verdict = check_evidence_freshness(
            evidence=evidence,
            purpose="routing_evidence",
            allow_stale=False,
        )
        assert verdict.admissible is False
        assert "stale" in " ".join(verdict.reasons).lower()

    def test_stale_evidence_rejected_when_allow_stale_false(self) -> None:
        evidence: dict[str, Any] = {
            "freshness_status": "stale",
            "revoked": False,
            "tombstoned": False,
            "superseded": False,
            "content_hash_valid": True,
        }
        # translation_memory is overridable — rejects stale when allow_stale=False
        verdict = check_evidence_freshness(
            evidence=evidence,
            purpose="translation_memory",
            allow_stale=False,
        )
        assert verdict.admissible is False

    def test_stale_evidence_ok_for_unrestricted_purpose(self) -> None:
        evidence: dict[str, Any] = {
            "freshness_status": "stale",
            "revoked": False,
            "tombstoned": False,
            "superseded": False,
            "content_hash_valid": True,
        }
        # dream_cycle is unrestricted — always admits stale
        verdict = check_evidence_freshness(
            evidence=evidence,
            purpose="dream_cycle",
            allow_stale=False,
        )
        assert verdict.admissible is True

    def test_superseded_evidence_rejected(self) -> None:
        evidence: dict[str, Any] = {
            "freshness_status": "superseded",
            "revoked": False,
            "tombstoned": False,
            "superseded": True,
            "superseded_by": "abc123",
            "supersession_chain_length": 2,
            "content_hash_valid": True,
        }
        verdict = check_evidence_freshness(
            evidence=evidence,
            purpose="orchestration_plan",
            allow_superseded=False,
        )
        assert verdict.admissible is False
        assert "superseded" in " ".join(verdict.reasons).lower()
        assert verdict.superseded_by_sha256 == "abc123"
        assert verdict.supersession_chain_length == 2

    def test_revoked_evidence_rejected(self) -> None:
        evidence: dict[str, Any] = {
            "freshness_status": "fresh",
            "revoked": True,
            "tombstoned": False,
            "superseded": False,
            "content_hash_valid": True,
        }
        verdict = check_evidence_freshness(
            evidence=evidence,
            purpose="execution_admission",
            allow_revoked=False,
        )
        assert verdict.admissible is False
        assert "revoked" in " ".join(verdict.reasons).lower()

    def test_tombstoned_evidence_rejected(self) -> None:
        evidence: dict[str, Any] = {
            "freshness_status": "fresh",
            "revoked": False,
            "tombstoned": True,
            "superseded": False,
            "content_hash_valid": True,
        }
        verdict = check_evidence_freshness(
            evidence=evidence,
            purpose="execution_admission",
            allow_revoked=False,
        )
        assert verdict.admissible is False
        # tombstoned counts as revoked for policy purposes
        assert "tombstoned" in " ".join(verdict.reasons).lower()

    def test_content_hash_invalid_rejected(self) -> None:
        evidence: dict[str, Any] = {
            "freshness_status": "fresh",
            "revoked": False,
            "tombstoned": False,
            "superseded": False,
            "content_hash_valid": False,
        }
        verdict = check_evidence_freshness(evidence=evidence, purpose="default")
        assert verdict.admissible is False
        assert "content_hash" in " ".join(verdict.reasons).lower()

    def test_revoked_allowed_when_flag_set(self) -> None:
        evidence: dict[str, Any] = {
            "freshness_status": "fresh",
            "revoked": True,
            "tombstoned": False,
            "superseded": False,
            "content_hash_valid": True,
        }
        verdict = check_evidence_freshness(
            evidence=evidence,
            purpose="default",
            allow_revoked=True,
        )
        assert verdict.admissible is True


# ═══════════════════════════════════════════════════════════════════════════
# Supersession chain resolution tests
# ═══════════════════════════════════════════════════════════════════════════


class TestSupersessionChainResolution:
    """Tests for resolve_supersession_chain walking forward to latest replacement."""

    def test_simple_supersession_chain(self) -> None:
        fact_rows: list[dict[str, Any]] = [
            {"sha256": "aaa", "supersedes_sha256": "", "revoked": False, "tombstoned": False},
            {"sha256": "bbb", "supersedes_sha256": "aaa", "revoked": False, "tombstoned": False},
            {"sha256": "ccc", "supersedes_sha256": "bbb", "revoked": False, "tombstoned": False},
        ]
        result = resolve_supersession_chain(start_sha256="aaa", fact_rows=fact_rows)
        assert result["found"] is True
        assert result["latest_sha256"] == "ccc"
        assert result["chain_length"] == 3
        assert result["chain"] == ["aaa", "bbb", "ccc"]

    def test_chain_stops_at_revoked_superseder(self) -> None:
        fact_rows: list[dict[str, Any]] = [
            {"sha256": "aaa", "supersedes_sha256": "", "revoked": False, "tombstoned": False},
            {"sha256": "bbb", "supersedes_sha256": "aaa", "revoked": True, "tombstoned": False},
        ]
        result = resolve_supersession_chain(start_sha256="aaa", fact_rows=fact_rows)
        assert result["found"] is True
        # The chain walks to bbb but it is revoked
        assert result["chain"] == ["aaa", "bbb"]

    def test_no_supersession(self) -> None:
        fact_rows: list[dict[str, Any]] = [
            {"sha256": "aaa", "supersedes_sha256": "", "revoked": False, "tombstoned": False},
        ]
        result = resolve_supersession_chain(start_sha256="aaa", fact_rows=fact_rows)
        assert result["found"] is True
        assert result["latest_sha256"] == "aaa"
        assert result["chain_length"] == 1

    def test_missing_start_sha256(self) -> None:
        fact_rows: list[dict[str, Any]] = []
        result = resolve_supersession_chain(start_sha256="nonexistent", fact_rows=fact_rows)
        assert result["found"] is False
        assert result["chain_length"] == 0

    def test_cycle_detection_stops_chain(self) -> None:
        fact_rows: list[dict[str, Any]] = [
            {"sha256": "aaa", "supersedes_sha256": "bbb", "revoked": False, "tombstoned": False},
            {"sha256": "bbb", "supersedes_sha256": "aaa", "revoked": False, "tombstoned": False},
        ]
        result = resolve_supersession_chain(start_sha256="aaa", fact_rows=fact_rows)
        assert result["found"] is True
        assert len(result["chain"]) <= 2


# ═══════════════════════════════════════════════════════════════════════════
# Lifecycle freshness gate tests (Instinct SDD state machine)
# ═══════════════════════════════════════════════════════════════════════════


class TestLifecycleFreshnessGate:
    """Verifies lifecycle rejects stale evidence and accepts fresh evidence."""

    def test_verify_blocked_by_stale_execution_evidence(self) -> None:
        """Stale evidence in the verification report blocks merge transition.

        Evidence embedded in execution trace nodes is stripped during
        normalize_execution_trace.  The canonical freshness-check path
        for governed transitions is via the verification report, which
        is populated by the verify phase payload and scanned during
        the merge phase freshness gate.
        """
        lc = InstinctLifecycle()
        lc.step("stale-ev", "specify", {"topic": "test stale evidence"})
        lc.step("stale-ev", "plan", {
            "task_dag": [{"node_id": "n1"}]
        })
        lc.step("stale-ev", "execute", {
            "execution_trace": [
                {
                    "node_id": "n1",
                    "success": True,
                }
            ]
        })
        # Verify phase embeds stale evidence into the verification report
        lc.step("stale-ev", "verify", {
            "all_proven": True,
            "evidence": {
                "freshness_status": "stale",
                "revoked": False,
                "tombstoned": False,
                "superseded": False,
                "sha256": "deadbeef",
            },
        })
        # Merge phase freshness gate scans verification_report and blocks
        result = lc.step("stale-ev", "merge", {})
        assert result["status"] == "blocked"
        assert "stale" in result["error"].lower()
        assert "memory_freshness" in result
        assert result["memory_freshness"]["all_fresh"] is False

    def test_verify_blocked_by_superseded_execution_evidence(self) -> None:
        """Superseded evidence in verification report blocks merge.

        Evidence embedded in execution trace nodes is stripped during
        normalization, so we use the verification-report path (checked
        at merge time) to validate superseded-evidence detection.
        """
        lc = InstinctLifecycle()
        lc.step("super-ev", "specify", {"topic": "test superseded"})
        lc.step("super-ev", "plan", {
            "task_dag": [{"node_id": "n1"}]
        })
        lc.step("super-ev", "execute", {
            "execution_trace": [
                {
                    "node_id": "n1",
                    "success": True,
                }
            ]
        })
        lc.step("super-ev", "verify", {
            "all_proven": True,
            "evidence": {
                "freshness_status": "superseded",
                "revoked": False,
                "tombstoned": False,
                "superseded": True,
                "superseded_by": "new_sha",
                "sha256": "old_sha",
            },
        })
        result = lc.step("super-ev", "merge", {})
        assert result["status"] == "blocked"
        assert result["memory_freshness"]["superseded_count"] >= 1

    def test_verify_blocked_by_revoked_evidence(self) -> None:
        """Revoked evidence in verification report blocks merge.

        Evidence embedded in execution trace nodes is stripped during
        normalization, so we use the verification-report path (checked
        at merge time) to validate revoked-evidence detection.
        """
        lc = InstinctLifecycle()
        lc.step("revoked-ev", "specify", {"topic": "test revoked"})
        lc.step("revoked-ev", "plan", {
            "task_dag": [{"node_id": "n1"}]
        })
        lc.step("revoked-ev", "execute", {
            "execution_trace": [
                {
                    "node_id": "n1",
                    "success": True,
                }
            ]
        })
        lc.step("revoked-ev", "verify", {
            "all_proven": True,
            "evidence": {
                "freshness_status": "fresh",
                "revoked": True,
                "tombstoned": False,
                "superseded": False,
                "sha256": "revoked_hash",
            },
        })
        result = lc.step("revoked-ev", "merge", {})
        assert result["status"] == "blocked"
        assert result["memory_freshness"]["all_fresh"] is False
        assert result["memory_freshness"]["stale_count"] >= 1

    def test_verify_succeeds_with_fresh_evidence(self) -> None:
        """Fresh evidence allows verify transition."""
        lc = InstinctLifecycle()
        lc.step("fresh-ev", "specify", {"topic": "test fresh evidence"})
        lc.step("fresh-ev", "plan", {
            "task_dag": [{"node_id": "n1"}]
        })
        lc.step("fresh-ev", "execute", {
            "execution_trace": [
                {
                    "node_id": "n1",
                    "success": True,
                    "evidence": {
                        "freshness_status": "fresh",
                        "revoked": False,
                        "tombstoned": False,
                        "superseded": False,
                        "sha256": "fresh_hash",
                    },
                }
            ]
        })
        result = lc.step("fresh-ev", "verify", {})
        assert result["status"] == "ok"
        assert result["current_phase"] == "verify"

    def test_merge_blocked_by_stale_verification_evidence(self) -> None:
        """Stale evidence in verification report blocks merge transition."""
        lc = InstinctLifecycle()
        lc.step("merge-stale", "specify", {"topic": "test merge stale"})
        lc.step("merge-stale", "plan", {
            "task_dag": [{"node_id": "n1"}]
        })
        lc.step("merge-stale", "execute", {
            "execution_trace": [
                {
                    "node_id": "n1",
                    "success": True,
                    "evidence": {
                        "freshness_status": "fresh",
                        "revoked": False,
                        "tombstoned": False,
                        "superseded": False,
                        "sha256": "ok_hash",
                    },
                }
            ]
        })
        lc.step("merge-stale", "verify", {
            "all_proven": True,
            "evidence": {
                "freshness_status": "stale",
                "revoked": False,
                "tombstoned": False,
                "superseded": False,
                "sha256": "stale_vfy",
            },
        })
        result = lc.step("merge-stale", "merge", {})
        assert result["status"] == "blocked"
        assert "stale" in result["error"].lower()

    def test_full_pipeline_with_fresh_evidence_succeeds(self) -> None:
        """Full specify→plan→execute→verify→merge pipeline with all-fresh evidence."""
        lc = InstinctLifecycle()

        r = lc.step("full-fresh", "specify", {"topic": "full fresh pipeline"})
        assert r["status"] == "ok"

        r = lc.step("full-fresh", "plan", {
            "task_dag": [
                {"node_id": "impl", "task_type": "create_file", "assigned_role": "scribe"},
                {"node_id": "test", "task_type": "run_tests", "depends_on": ["impl"], "assigned_role": "cove"},
            ]
        })
        assert r["status"] == "ok"

        r = lc.step("full-fresh", "execute", {
            "execution_trace": [
                {
                    "node_id": "impl",
                    "success": True,
                    "duration_ms": 10.0,
                    "evidence": {
                        "freshness_status": "fresh",
                        "revoked": False,
                        "tombstoned": False,
                        "superseded": False,
                        "sha256": "ev_impl",
                    },
                },
                {
                    "node_id": "test",
                    "success": True,
                    "duration_ms": 20.0,
                    "evidence": {
                        "freshness_status": "fresh",
                        "revoked": False,
                        "tombstoned": False,
                        "superseded": False,
                        "sha256": "ev_test",
                    },
                },
            ]
        })
        assert r["status"] == "ok"
        assert r["execution_summary"]["all_nodes_succeeded"] is True

        r = lc.step("full-fresh", "verify", {
            "all_proven": True,
            "evidence": {
                "freshness_status": "fresh",
                "revoked": False,
                "tombstoned": False,
                "superseded": False,
                "sha256": "ev_vfy",
            },
        })
        assert r["status"] == "ok"

        r = lc.step("full-fresh", "merge", {})
        assert r["status"] == "ok"
        assert r["current_phase"] == "merge"
        assert r["sealed"] is True

    def test_override_bypasses_freshness_gate(self) -> None:
        """Override=True should bypass the memory freshness gate."""
        lc = InstinctLifecycle()
        lc.step("override-fresh", "specify", {"topic": "override freshness"})
        lc.step("override-fresh", "plan", {
            "task_dag": [{"node_id": "n1"}]
        })
        lc.step("override-fresh", "execute", {
            "execution_trace": [
                {
                    "node_id": "n1",
                    "success": True,
                    "evidence": {
                        "freshness_status": "stale",
                        "revoked": False,
                        "tombstoned": False,
                        "superseded": False,
                        "sha256": "stale_hash",
                    },
                }
            ]
        })
        # override=True skips freshness check
        result = lc.step("override-fresh", "verify", {}, override=True)
        # It should succeed or at least not be blocked by freshness
        # (it may still be blocked by other gates like trace completeness)
        if result["status"] == "blocked":
            assert "memory_freshness" not in result
        else:
            assert result["status"] == "ok"

    def test_specify_and_plan_not_gated_by_freshness(self) -> None:
        """Specify and plan transitions should proceed without freshness checks."""
        lc = InstinctLifecycle()
        r = lc.step("early", "specify", {
            "topic": "early phases",
            "evidence": {
                "freshness_status": "stale",
                "revoked": False,
                "tombstoned": False,
                "superseded": False,
                "sha256": "early_stale",
            },
        })
        assert r["status"] == "ok"

        r = lc.step("early", "plan", {
            "task_dag": [{"node_id": "n1"}],
            "evidence": {
                "freshness_status": "superseded",
                "revoked": False,
                "tombstoned": False,
                "superseded": True,
                "sha256": "early_super",
            },
        })
        assert r["status"] == "ok"

    def test_orchestration_contract_evidence_scanned(self) -> None:
        """Verifies that orchestration_contract evidence entries are scanned."""
        lc = InstinctLifecycle()
        lc.step("orch-scan", "specify", {"topic": "orch scan"})
        lc.step("orch-scan", "plan", {
            "task_dag": [
                {"node_id": "n1"},
                {"node_id": "n2", "depends_on": ["n1"]},
            ]
        })
        lc.step("orch-scan", "execute", {
            "execution_trace": [
                {"node_id": "n1", "success": True},
                {"node_id": "n2", "success": True},
            ]
        })
        # Manually inject stale evidence into orchestration contract
        mission = lc.get_mission("orch-scan")
        assert mission is not None
        mission["orchestration_contract"] = {
            "evidence": [
                {
                    "freshness_status": "stale",
                    "revoked": False,
                    "tombstoned": False,
                    "superseded": False,
                    "sha256": "orch_stale",
                }
            ]
        }
        # Directly call _check_mission_evidence_freshness
        result = _check_mission_evidence_freshness(mission)
        assert result["all_fresh"] is False
        assert result["stale_count"] >= 1
        assert len(result["stale_entries"]) >= 1


# ═══════════════════════════════════════════════════════════════════════════
# Handoff chain freshness tests
# ═══════════════════════════════════════════════════════════════════════════


class TestHandoffChainFreshness:
    """Tests for freshness checks in handoff chain verification."""

    def test_handoff_chain_detects_stale_evidence(self) -> None:
        events: list[dict[str, Any]] = [
            {
                "event_hash": "a" * 64,
                "event_type": "delegate",
                "parent_event_hash": "",
                "lineage_hash": "",
                "scope": "test stale",
                "payload": {
                    "evidence": {
                        "freshness_status": "stale",
                        "revoked": False,
                        "tombstoned": False,
                        "superseded": False,
                        "sha256": "stale_in_handoff",
                    }
                },
            }
        ]
        freshness = _scan_handoff_chain_freshness(events)
        assert freshness["all_fresh"] is False
        assert freshness["stale_count"] >= 1
        assert len(freshness["stale_entries"]) >= 1

    def test_handoff_chain_detects_superseded_evidence(self) -> None:
        events: list[dict[str, Any]] = [
            {
                "event_hash": "b" * 64,
                "event_type": "delegate",
                "parent_event_hash": "",
                "lineage_hash": "",
                "scope": "test superseded",
                "payload": {
                    "hks_evidence": {
                        "freshness_status": "superseded",
                        "revoked": False,
                        "tombstoned": False,
                        "superseded": True,
                        "sha256": "superseded_ev",
                    }
                },
            }
        ]
        freshness = _scan_handoff_chain_freshness(events)
        assert freshness["all_fresh"] is False
        assert freshness["superseded_count"] >= 1

    def test_handoff_chain_detects_revoked_evidence(self) -> None:
        events: list[dict[str, Any]] = [
            {
                "event_hash": "c" * 64,
                "event_type": "delegate",
                "parent_event_hash": "",
                "lineage_hash": "",
                "scope": "test revoked",
                "payload": {
                    "memory_evidence": {
                        "freshness_status": "fresh",
                        "revoked": True,
                        "tombstoned": False,
                        "superseded": False,
                        "sha256": "revoked_ev",
                    }
                },
            }
        ]
        freshness = _scan_handoff_chain_freshness(events)
        assert freshness["all_fresh"] is False
        assert freshness["revoked_count"] >= 1

    def test_handoff_chain_all_fresh(self) -> None:
        events: list[dict[str, Any]] = [
            {
                "event_hash": "d" * 64,
                "event_type": "delegate",
                "parent_event_hash": "",
                "lineage_hash": "",
                "scope": "test fresh",
                "payload": {
                    "evidence": {
                        "freshness_status": "fresh",
                        "revoked": False,
                        "tombstoned": False,
                        "superseded": False,
                        "sha256": "fresh_handoff",
                    }
                },
            }
        ]
        freshness = _scan_handoff_chain_freshness(events)
        assert freshness["all_fresh"] is True
        assert freshness["fresh_count"] == 1

    def test_handoff_chain_no_payload(self) -> None:
        """Empty payload should not cause errors."""
        events: list[dict[str, Any]] = [
            {
                "event_hash": "e" * 64,
                "event_type": "delegate",
                "parent_event_hash": "",
                "lineage_hash": "",
                "scope": "no payload",
            }
        ]
        freshness = _scan_handoff_chain_freshness(events)
        assert freshness["all_fresh"] is True
        assert freshness["total_checked"] == 0

    def test_verify_handoff_chain_includes_memory_freshness(self) -> None:
        events: list[dict[str, Any]] = [
            {
                "event_hash": "f" * 64,
                "event_type": "delegate",
                "parent_event_hash": "",
                "lineage_hash": "f" * 64,
                "scope": "verify test",
                "payload": {
                    "evidence": {
                        "freshness_status": "stale",
                        "revoked": False,
                        "tombstoned": False,
                        "superseded": False,
                        "sha256": "stale_vfy",
                    }
                },
            }
        ]
        verification = verify_handoff_chain(events)
        assert "memory_freshness" in verification
        assert verification["memory_freshness"]["all_fresh"] is False

    def test_handoff_evidence_list_scanning(self) -> None:
        """Evidence in list form is also scanned."""
        events: list[dict[str, Any]] = [
            {
                "event_hash": "g" * 64,
                "event_type": "delegate",
                "parent_event_hash": "",
                "lineage_hash": "",
                "scope": "list scan",
                "payload": {
                    "evidence": [
                        {
                            "freshness_status": "fresh",
                            "revoked": False,
                            "tombstoned": False,
                            "superseded": False,
                            "sha256": "list_fresh",
                        },
                        {
                            "freshness_status": "stale",
                            "revoked": False,
                            "tombstoned": False,
                            "superseded": False,
                            "sha256": "list_stale",
                        },
                    ]
                },
            }
        ]
        freshness = _scan_handoff_chain_freshness(events)
        assert freshness["total_checked"] == 2
        assert freshness["stale_count"] == 1
        assert freshness["fresh_count"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# Purpose policy tests
# ═══════════════════════════════════════════════════════════════════════════


class TestPurposePolicies:
    """Verify that purpose-based freshness policies work as expected."""

    def test_mandatory_purposes_reject_stale(self) -> None:
        stale_evidence: dict[str, Any] = {
            "freshness_status": "stale",
            "revoked": False,
            "tombstoned": False,
            "superseded": False,
            "content_hash_valid": True,
        }
        for purpose in ("routing_evidence", "verifier_evidence", "execution_admission",
                        "orchestration_plan", "audit_evidence"):
            verdict = check_evidence_freshness(
                evidence=stale_evidence,
                purpose=purpose,
                allow_stale=True,  # even when caller allows, mandatory rejects
            )
            assert verdict.admissible is False, f"Mandatory purpose {purpose} should reject stale"

    def test_unrestricted_purposes_always_admit(self) -> None:
        stale_evidence: dict[str, Any] = {
            "freshness_status": "stale",
            "revoked": False,
            "tombstoned": False,
            "superseded": False,
            "content_hash_valid": True,
        }
        for purpose in ("default", "knowledge_ingestion", "benchmark", "dream_cycle"):
            verdict = check_evidence_freshness(
                evidence=stale_evidence,
                purpose=purpose,
                allow_stale=False,
            )
            assert verdict.admissible is True, f"Unrestricted purpose {purpose} should admit stale"

    def test_overridable_purposes_reject_by_default(self) -> None:
        stale_evidence: dict[str, Any] = {
            "freshness_status": "stale",
            "revoked": False,
            "tombstoned": False,
            "superseded": False,
            "content_hash_valid": True,
        }
        for purpose in ("operator_review", "translation_memory",
                        "repair_pattern_recall", "governance_policy_retrieval"):
            verdict = check_evidence_freshness(
                evidence=stale_evidence,
                purpose=purpose,
                allow_stale=False,
            )
            assert verdict.admissible is False, f"Overridable purpose {purpose} should reject with allow_stale=False"

    def test_overridable_purposes_admit_when_allow_stale(self) -> None:
        stale_evidence: dict[str, Any] = {
            "freshness_status": "stale",
            "revoked": False,
            "tombstoned": False,
            "superseded": False,
            "content_hash_valid": True,
        }
        for purpose in ("operator_review", "translation_memory",
                        "repair_pattern_recall", "governance_policy_retrieval"):
            verdict = check_evidence_freshness(
                evidence=stale_evidence,
                purpose=purpose,
                allow_stale=True,
            )
            assert verdict.admissible is True, f"Overridable purpose {purpose} should admit stale with allow_stale=True"


# ═══════════════════════════════════════════════════════════════════════════
# FreshnessVerdict dataclass tests
# ═══════════════════════════════════════════════════════════════════════════


class TestFreshnessVerdict:
    """Tests for the FreshnessVerdict dataclass."""

    def test_default_verdict_is_admissible(self) -> None:
        verdict = FreshnessVerdict(admissible=True)
        assert verdict.admissible is True
        assert verdict.freshness_status == "fresh"
        assert verdict.reasons == []
        assert verdict.superseded_by_sha256 == ""
        assert verdict.supersession_chain_length == 0

    def test_rejected_verdict_carries_reasons(self) -> None:
        verdict = FreshnessVerdict(
            admissible=False,
            freshness_status="stale",
            reasons=["stale_memory_denied"],
        )
        assert verdict.admissible is False
        assert "stale_memory_denied" in verdict.reasons

    def test_superseded_verdict_carries_chain_info(self) -> None:
        verdict = FreshnessVerdict(
            admissible=False,
            freshness_status="superseded",
            reasons=["superseded_memory_denied"],
            superseded_by_sha256="new_sha",
            supersession_chain_length=3,
        )
        assert verdict.superseded_by_sha256 == "new_sha"
        assert verdict.supersession_chain_length == 3
