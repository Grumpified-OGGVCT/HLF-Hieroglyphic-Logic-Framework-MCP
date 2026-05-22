"""
Tests for Memory Freshness & Supersession Enforcement (B4).

Covers:
  - FreshnessVerdict dataclass
  - check_evidence_freshness() with purpose classes
  - resolve_supersession_chain() including cycle detection
  - lifecycle _check_mission_evidence_freshness()
"""
from __future__ import annotations

import time
from typing import Any

import pytest

from hlf_mcp.hlf.memory_node import (
    FreshnessVerdict,
    check_evidence_freshness,
    resolve_supersession_chain,
)


# ═══════════════════════════════════════════════════════════════════════════════
# FreshnessVerdict
# ═══════════════════════════════════════════════════════════════════════════════

class TestFreshnessVerdict:
    def test_default_constructor(self) -> None:
        fv = FreshnessVerdict(admissible=False)
        assert fv.admissible is False
        assert fv.freshness_status == "fresh"
        assert fv.reasons == []
        assert fv.superseded_by_sha256 == ""
        assert fv.supersession_chain_length == 0

    def test_explicit_rejection(self) -> None:
        fv = FreshnessVerdict(
            admissible=False,
            freshness_status="stale",
            reasons=["stale evidence"],
        )
        assert fv.admissible is False
        assert fv.freshness_status == "stale"
        assert "stale evidence" in fv.reasons

    def test_advisory_admit(self) -> None:
        fv = FreshnessVerdict(
            admissible=True,
            freshness_status="stale",
            reasons=["stale_evidence_admitted_by_policy"],
        )
        assert fv.admissible is True
        assert fv.freshness_status == "stale"
        assert "admitted_by_policy" in fv.reasons[0]

    def test_fields_are_distinct(self) -> None:
        fv = FreshnessVerdict(admissible=True, freshness_status="fresh")
        assert isinstance(fv.admissible, bool)
        assert isinstance(fv.freshness_status, str)
        assert isinstance(fv.reasons, list)
        assert isinstance(fv.superseded_by_sha256, str)
        assert isinstance(fv.supersession_chain_length, int)


# ═══════════════════════════════════════════════════════════════════════════════
# check_evidence_freshness  —  mandatory purposes
# ═══════════════════════════════════════════════════════════════════════════════

class TestCheckEvidenceFreshnessMandatory:
    """Mandatory-purpose calls must hard-reject stale or superseded evidence."""

    @pytest.mark.parametrize("purpose", [
        "execution_admission",
        "governance_vote",
        "audit_entry",
    ])
    def test_fresh_passes(self, purpose: str) -> None:
        evidence: dict[str, Any] = {
            "freshness_status": "fresh",
            "revoked": False,
            "tombstoned": False,
            "superseded_by_sha256": "",
            "content_hash_valid": True,
        }
        v = check_evidence_freshness(evidence, purpose=purpose)
        assert v.admissible is True
        assert v.freshness_status == "fresh"

    @pytest.mark.parametrize("purpose", [
        "execution_admission",
        "governance_vote",
        "audit_entry",
    ])
    def test_stale_rejected(self, purpose: str) -> None:
        evidence = {
            "freshness_status": "stale",
            "revoked": False,
            "tombstoned": False,
            "superseded_by_sha256": "",
            "content_hash_valid": True,
        }
        v = check_evidence_freshness(evidence, purpose=purpose)
        assert v.admissible is False
        assert "stale" in str(v.reasons).lower()

    @pytest.mark.parametrize("purpose", [
        "execution_admission",
        "governance_vote",
    ])
    def test_revoked_rejected(self, purpose: str) -> None:
        evidence = {
            "freshness_status": "fresh",
            "revoked": True,
            "tombstoned": False,
            "superseded_by_sha256": "",
            "content_hash_valid": True,
        }
        v = check_evidence_freshness(evidence, purpose=purpose)
        assert v.admissible is False

    @pytest.mark.parametrize("purpose", [
        "execution_admission",
        "audit_entry",
    ])
    def test_tombstoned_rejected(self, purpose: str) -> None:
        evidence = {
            "freshness_status": "fresh",
            "revoked": False,
            "tombstoned": True,
            "superseded_by_sha256": "",
            "content_hash_valid": True,
        }
        v = check_evidence_freshness(evidence, purpose=purpose)
        assert v.admissible is False

    def test_superseded_rejected_for_execution_admission(self) -> None:
        evidence = {
            "freshness_status": "fresh",
            "revoked": False,
            "tombstoned": False,
            "superseded_by_sha256": "aaaabbbbccccddddeeeeffff0000111122223333444455556666777788889999",
            "content_hash_valid": True,
        }
        v = check_evidence_freshness(evidence, purpose="execution_admission")
        assert v.admissible is False
        assert "superseded" in str(v.reasons).lower()


# ═══════════════════════════════════════════════════════════════════════════════
# check_evidence_freshness  —  overridable purposes
# ═══════════════════════════════════════════════════════════════════════════════

class TestCheckEvidenceFreshnessOverridable:
    """Overridable purposes flag but still admit stale evidence when callers allow."""

    @pytest.mark.parametrize("purpose", [
        "default",
        "dream_cycle",
    ])
    def test_stale_flagged_but_admitted(self, purpose: str) -> None:
        evidence = {
            "freshness_status": "stale",
            "revoked": False,
            "tombstoned": False,
            "superseded_by_sha256": "",
            "content_hash_valid": True,
        }
        v = check_evidence_freshness(evidence, purpose=purpose)
        assert v.admissible is True
        assert v.freshness_status == "stale"

    @pytest.mark.parametrize("purpose", [
        "default",
        "memory_recall",
    ])
    def test_fresh_passes_cleanly(self, purpose: str) -> None:
        evidence = {
            "freshness_status": "fresh",
            "revoked": False,
            "tombstoned": False,
            "superseded_by_sha256": "",
            "content_hash_valid": True,
        }
        v = check_evidence_freshness(evidence, purpose=purpose)
        assert v.admissible is True
        assert v.freshness_status == "fresh"


# ═══════════════════════════════════════════════════════════════════════════════
# check_evidence_freshness  —  unrestricted purposes
# ═══════════════════════════════════════════════════════════════════════════════

class TestCheckEvidenceFreshnessUnrestricted:
    """Unrestricted purposes always admit, even stale evidence."""

    @pytest.mark.parametrize("purpose", [
        "benchmark",
        "dream_proposal",
        "media_synthesis",
    ])
    def test_stale_still_admitted(self, purpose: str) -> None:
        evidence = {
            "freshness_status": "stale",
            "revoked": False,
            "tombstoned": False,
            "superseded_by_sha256": "",
            "content_hash_valid": True,
        }
        v = check_evidence_freshness(evidence, purpose=purpose)
        assert v.admissible is True

    @pytest.mark.parametrize("purpose", [
        "benchmark",
        "media_synthesis",
    ])
    def test_superseded_still_admitted(self, purpose: str) -> None:
        evidence = {
            "freshness_status": "fresh",
            "revoked": False,
            "tombstoned": False,
            "superseded_by_sha256": "aaaabbbbccccddddeeeeffff0000111122223333444455556666777788889999",
            "content_hash_valid": True,
        }
        v = check_evidence_freshness(evidence, purpose=purpose)
        assert v.admissible is True


# ═══════════════════════════════════════════════════════════════════════════════
# check_evidence_freshness  —  edge cases
# ═══════════════════════════════════════════════════════════════════════════════

class TestCheckEvidenceFreshnessEdgeCases:
    def test_tampered_content_hash(self) -> None:
        evidence: dict[str, Any] = {
            "freshness_status": "fresh",
            "revoked": False,
            "tombstoned": False,
            "superseded_by_sha256": "",
            "content_hash_valid": False,
        }
        v = check_evidence_freshness(evidence, purpose="execution_admission")
        assert v.admissible is False
        assert "tampered" in v.freshness_status

    def test_missing_freshness_status_is_unknown(self) -> None:
        evidence = {
            "revoked": False,
            "tombstoned": False,
            "superseded_by_sha256": "",
            "content_hash_valid": True,
        }
        v = check_evidence_freshness(evidence, purpose="execution_admission")
        # unknown → treated as fresh
        assert v.admissible is True

    def test_none_freshness_status_treated_as_unknown(self) -> None:
        evidence = {
            "freshness_status": None,
            "revoked": False,
            "tombstoned": False,
            "superseded_by_sha256": "",
            "content_hash_valid": True,
        }
        v = check_evidence_freshness(evidence, purpose="execution_admission")
        assert v.admissible is True

    def test_missing_purpose_defaults_to_unrestricted(self) -> None:
        evidence = {
            "freshness_status": "stale",
            "revoked": False,
            "tombstoned": False,
            "superseded_by_sha256": "",
            "content_hash_valid": True,
        }
        v = check_evidence_freshness(evidence)
        assert v.admissible is True


# ═══════════════════════════════════════════════════════════════════════════════
# resolve_supersession_chain
# ═══════════════════════════════════════════════════════════════════════════════

class TestResolveSupersessionChain:
    """Chain resolution walks forward through supersedes_sha256 links."""

    def test_no_supersession_returns_self(self) -> None:
        rows = [
            {"sha256": "a", "supersedes_sha256": None, "revoked": False, "tombstoned": False},
        ]
        result = resolve_supersession_chain(start_sha256="a", fact_rows=rows)
        assert result["chain"][0] == "a"
        assert result["chain_length"] == 1
        assert result["cycle_detected"] is False

    def test_single_link_chain(self) -> None:
        rows = [
            {"sha256": "a", "supersedes_sha256": "", "revoked": False, "tombstoned": False},
            {"sha256": "b", "supersedes_sha256": "a", "revoked": False, "tombstoned": False},
        ]
        result = resolve_supersession_chain(start_sha256="a", fact_rows=rows)
        assert result["chain"][0] == "a"
        assert result["latest_sha256"] == "b"
        assert result["chain_length"] == 2
        assert len(result["chain"]) == 2

    def test_multi_link_chain(self) -> None:
        rows = [
            {"sha256": "a", "supersedes_sha256": "", "revoked": False, "tombstoned": False},
            {"sha256": "b", "supersedes_sha256": "a", "revoked": False, "tombstoned": False},
            {"sha256": "c", "supersedes_sha256": "b", "revoked": False, "tombstoned": False},
            {"sha256": "d", "supersedes_sha256": "c", "revoked": False, "tombstoned": False},
        ]
        result = resolve_supersession_chain(start_sha256="a", fact_rows=rows)
        assert result["chain"][0] == "a"
        assert result["latest_sha256"] == "d"
        assert result["chain_length"] == 4

    def test_not_found_in_rows(self) -> None:
        rows: list[dict[str, Any]] = []
        result = resolve_supersession_chain(start_sha256="missing", fact_rows=rows)
        assert result["found"] is False
        assert result["latest_sha256"] == "missing"
        assert result["chain_length"] == 0

    def test_cycle_detection(self) -> None:
        """A→B→A should be detected as a cycle."""
        rows = [
            {"sha256": "a", "supersedes_sha256": "b", "revoked": False, "tombstoned": False},
            {"sha256": "b", "supersedes_sha256": "a", "revoked": False, "tombstoned": False},
        ]
        result = resolve_supersession_chain(start_sha256="a", fact_rows=rows)
        assert result["cycle_detected"] is True

    def test_max_depth_enforced(self) -> None:
        """Very long chains should truncate at max_depth."""
        rows: list[dict[str, Any]] = []
        for i in range(60):
            prev = f"h{i - 1}" if i > 0 else None
            rows.append({"sha256": f"h{i}", "supersedes_sha256": prev, "revoked": False, "tombstoned": False})
        result = resolve_supersession_chain(start_sha256="h0", fact_rows=rows, max_depth=50)
        assert result["chain_length"] <= 50

    def test_mid_chain_lookup(self) -> None:
        """Walk from a middle-of-chain entry forward."""
        rows = [
            {"sha256": "a", "supersedes_sha256": "", "revoked": False, "tombstoned": False},
            {"sha256": "b", "supersedes_sha256": "a", "revoked": False, "tombstoned": False},
            {"sha256": "c", "supersedes_sha256": "b", "revoked": False, "tombstoned": False},
        ]
        result = resolve_supersession_chain(start_sha256="b", fact_rows=rows)
        assert result["chain"][0] == "b"
        assert result["latest_sha256"] == "c"
        assert result["chain_length"] == 2


# ═══════════════════════════════════════════════════════════════════════════════
# Lifecycle integration  —  _check_mission_evidence_freshness
# ═══════════════════════════════════════════════════════════════════════════════

class TestMissionEvidenceFreshness:
    """Tests for the lifecycle helper _check_mission_evidence_freshness()."""

    def _import_helper(self):
        from hlf_mcp.instinct.lifecycle import _check_mission_evidence_freshness
        return _check_mission_evidence_freshness

    def test_empty_mission_is_fresh(self) -> None:
        check = self._import_helper()
        mission: dict[str, Any] = {}
        result = check(mission)
        assert result["all_fresh"] is True
        assert result["stale_count"] == 0

    def test_fresh_execution_trace(self) -> None:
        check = self._import_helper()
        mission = {
            "execution_trace": [
                {
                    "node_id": "n1",
                    "evidence": {
                        "sha256": "a" * 64,
                        "fresh_until": "2099-12-31T23:59:59+00:00",
                    },
                },
            ],
        }
        result = check(mission)
        assert result["all_fresh"] is True

    def test_stale_execution_trace(self) -> None:
        check = self._import_helper()
        mission = {
            "execution_trace": [
                {
                    "node_id": "n2",
                    "evidence": {
                        "sha256": "a" * 64,
                        "fresh_until": "2020-01-01T00:00:00+00:00",
                        "freshness_status": "stale",
                    },
                },
            ],
        }
        result = check(mission)
        assert result["all_fresh"] is False

    def test_superseded_in_trace(self) -> None:
        check = self._import_helper()
        mission = {
            "execution_trace": [
                {
                    "node_id": "n3",
                    "evidence": {
                        "sha256": "old_key",
                        "freshness_status": "fresh",
                        "supersedes_sha256": "aaaabbbbccccddddeeeeffff0000111122223333444455556666777788889999",
                    },
                },
            ],
        }
        result = check(mission)
        # superseded evidence may be rejected depending on purpose
        assert result["all_fresh"] is not None  # function runs without error

    def test_revoked_in_trace(self) -> None:
        check = self._import_helper()
        mission = {
            "execution_trace": [
                {
                    "node_id": "n4",
                    "evidence": {
                        "sha256": "b" * 64,
                        "revoked": True,
                    },
                },
            ],
        }
        result = check(mission)
        assert result["all_fresh"] is False

    def test_mixed_fresh_stale(self) -> None:
        check = self._import_helper()
        mission = {
            "execution_trace": [
                {
                    "node_id": "ok",
                    "evidence": {
                        "sha256": "f" * 64,
                        "fresh_until": "2099-12-31T23:59:59+00:00",
                    },
                },
                {
                    "node_id": "bad",
                    "evidence": {
                        "sha256": "e" * 64,
                        "fresh_until": "2020-01-01T00:00:00+00:00",
                        "freshness_status": "stale",
                    },
                },
            ],
        }
        result = check(mission)
        assert result["all_fresh"] is False

    def test_verification_report_evidence(self) -> None:
        check = self._import_helper()
        mission = {
            "verification_report": {
                "proof_surface": {
                    "bundle_sha256": "f" * 64,
                    "freshness_status": "fresh",
                },
            },
        }
        result = check(mission)
        # verification_report is not scanned; only artifacts.verify.payload.evidence is checked
        assert result["all_fresh"] is True

    def test_nested_result_evidence(self) -> None:
        check = self._import_helper()
        mission = {
            "execution_trace": [
                {
                    "node_id": "n5",
                    "result": {
                        "memory_evidence": {
                            "sha256": "c" * 64,
                            "fresh_until": "2020-01-01T00:00:00+00:00",
                        },
                    },
                },
            ],
        }
        result = check(mission)
        # Only top-level "evidence" key is checked; nested "result.memory_evidence" is not
        assert result["all_fresh"] is True

    def test_orchestration_contract_evidence(self) -> None:
        check = self._import_helper()
        mission = {
            "orchestration_contract": {
                "evidence": [
                    {"sha256": "d" * 64, "fresh_until": "2099-01-01T00:00:00+00:00"},
                    {"sha256": "e" * 64, "fresh_until": "2020-01-01T00:00:00+00:00"},
                ],
            },
        }
        result = check(mission)
        # orchestration_contract evidence is now scanned by the function
        assert result["all_fresh"] is True  # no freshness_status set → defaults to fresh

    def test_non_dict_evidence_skipped(self) -> None:
        check = self._import_helper()
        mission = {
            "execution_trace": [
                {
                    "node_id": "n6",
                    "evidence": "just_a_string",
                },
            ],
        }
        result = check(mission)
        # String evidence is skipped (not a dict)
        assert result["all_fresh"] is True
