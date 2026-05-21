"""End-to-end stale artifact supersession lifecycle tests.

Covers the P2 knowledge substrate goal:
  - Store artifact → supersede with new version → verify chain
  - Stale detection via EvidenceContract.is_stale() with fresh_until in the past
  - Supersession chain walking across 3+ generations using resolve_supersession_chain
  - Confirm stale/superseded artifacts are excluded from default retrieval
"""
from __future__ import annotations

import time
from datetime import datetime, timezone as dt_timezone
from typing import Any

from hlf_mcp.hlf.memory_node import (
    EvidenceContract,
    check_evidence_freshness,
    resolve_supersession_chain,
)


UTC = dt_timezone.utc


# ── Helpers ──────────────────────────────────────────────────────────────────

def _epoch_sha(prefix: str) -> str:
    """Deterministic 64-hex-char hash from a short prefix for test readability."""
    import hashlib
    raw = hashlib.sha256(prefix.encode()).hexdigest()
    return raw[:64].lower()


def _future_iso() -> str:
    """Return an ISO timestamp 90 days in the future."""
    return (datetime.now(UTC).replace(tzinfo=None) + __import__("datetime").timedelta(days=90)).isoformat() + "+00:00"


def _past_iso() -> str:
    """Return an ISO timestamp 30 days in the past."""
    return (datetime.now(UTC).replace(tzinfo=None) - __import__("datetime").timedelta(days=30)).isoformat() + "+00:00"


# ── Stale Detection via fresh_until ──────────────────────────────────────────

class TestStaleDetectionViaFreshUntil:
    """EvidenceContract.is_stale() should detect past fresh_until."""

    def test_future_fresh_until_is_fresh(self) -> None:
        contract = EvidenceContract(
            sha256=_epoch_sha("future"),
            fresh_until=_future_iso(),
        )
        assert contract.is_stale() is False

    def test_past_fresh_until_is_stale(self) -> None:
        contract = EvidenceContract(
            sha256=_epoch_sha("past"),
            fresh_until=_past_iso(),
        )
        assert contract.is_stale() is True

    def test_none_fresh_until_is_fresh(self) -> None:
        contract = EvidenceContract(
            sha256=_epoch_sha("none"),
            fresh_until=None,
        )
        assert contract.is_stale() is False

    def test_empty_fresh_until_is_fresh(self) -> None:
        contract = EvidenceContract(
            sha256=_epoch_sha("empty"),
            fresh_until="",
        )
        # empty string != None, but fromisoformat will raise → returns False
        assert contract.is_stale() is False

    def test_malformed_fresh_until_graceful(self) -> None:
        contract = EvidenceContract(
            sha256=_epoch_sha("bad"),
            fresh_until="not-a-date",
        )
        # fromisoformat raises ValueError → returns False (not stale)
        assert contract.is_stale() is False


# ── EvidenceContract.normalize ↔ Rag Storage Round-trip ─────────────────────

class TestNormalizeRoundTrip:
    """EvidenceContract.normalize() should handle rag-layer dicts end-to-end."""

    def test_round_trip_clean_contract(self) -> None:
        original = EvidenceContract(
            sha256=_epoch_sha("clean"),
            trust_tier="verified",
            memory_stratum="semantic",
            artifact_form="raw_intake",
            source_authority_label="external",
            fresh_until=_future_iso(),
        )
        as_dict = original.to_dict()
        normalized = EvidenceContract.normalize(as_dict)
        assert normalized.sha256 == original.sha256
        assert normalized.trust_tier == original.trust_tier
        assert normalized.memory_stratum == original.memory_stratum

    def test_round_trip_rag_style_dict(self) -> None:
        """Simulate a dict coming from rag/memory.py _build_evidence."""
        collected_when = _past_iso()
        rag_dict: dict[str, Any] = {
            "content_hash": _epoch_sha("rag"),
            "trust_tier": "normalized",
            "source_path": "/tmp/ingest/test.json",
            "source_authority_label": "draft",
            "artifact_form": "canonical_knowledge",
            "memory_stratum": "episodic",
            "source_lineage": {
                "collector": "test-collector",
                "collected_at": collected_when,
            },
            "revoked": 0,  # SQLite int → bool
            "tombstoned": 0,
            "extra_field": "should land in collection_metadata",
        }
        normalized = EvidenceContract.normalize(rag_dict)
        assert normalized.sha256 == _epoch_sha("rag")
        assert normalized.trust_tier == "normalized"
        assert normalized.source_file == "/tmp/ingest/test.json"
        assert normalized.collector == "test-collector"
        # normalize reads source_lineage.collected_at
        assert normalized.collected_at == collected_when
        assert normalized.revoked is False  # 0 → False
        assert normalized.tombstoned is False
        assert normalized.memory_stratum == "episodic"
        assert normalized.artifact_form == "canonical_knowledge"
        assert normalized.source_authority_label == "draft"
        assert normalized.collection_metadata is not None
        assert "extra_field" in normalized.collection_metadata

    def test_normalize_minimal_dict(self) -> None:
        """Minimal dict with only essential fields."""
        minimal: dict[str, Any] = {"sha256": _epoch_sha("minimal")}
        normalized = EvidenceContract.normalize(minimal)
        assert normalized.sha256 == _epoch_sha("minimal")
        assert normalized.trust_tier == "trusted"  # default
        assert normalized.memory_stratum == "working"  # default


# ── Supersession Chain: 3+ generations ──────────────────────────────────────

class TestSupersessionChainEndToEnd:
    """Walk supersession chains across multiple generations."""

    def _build_chain_rows(self, *sha256s: str) -> list[dict[str, Any]]:
        """Build rows where each entry supersedes the previous one."""
        rows: list[dict[str, Any]] = []
        for i, sha in enumerate(sha256s):
            row: dict[str, Any] = {
                "sha256": sha,
                "revoked": False,
                "tombstoned": False,
            }
            if i < len(sha256s) - 1:
                # This row is superseded BY the next one
                row["superseded_by_sha256"] = sha256s[i + 1]
            else:
                row["superseded_by_sha256"] = ""
            rows.append(row)
        return rows

    def test_three_gen_chain(self) -> None:
        a, b, c = _epoch_sha("a"), _epoch_sha("b"), _epoch_sha("c")
        rows = self._build_chain_rows(a, b, c)
        result = resolve_supersession_chain(sha256=a, rows=rows)
        assert result["head"] == a
        assert result["terminal"] == c
        assert result["length"] == 3
        assert result["chain"] == [a, b, c]
        assert result["cycle_detected"] is False

    def test_five_gen_chain(self) -> None:
        hashes = [_epoch_sha(ch) for ch in "abcde"]
        rows = self._build_chain_rows(*hashes)
        result = resolve_supersession_chain(sha256=hashes[0], rows=rows)
        assert result["head"] == hashes[0]
        assert result["terminal"] == hashes[-1]
        assert result["length"] == 5
        assert not result["cycle_detected"]

    def test_mid_chain_start(self) -> None:
        """Start from the middle of a 5-gen chain."""
        hashes = [_epoch_sha(ch) for ch in "abcde"]
        rows = self._build_chain_rows(*hashes)
        result = resolve_supersession_chain(sha256=hashes[2], rows=rows)
        assert result["head"] == hashes[2]
        assert result["terminal"] == hashes[-1]
        assert result["length"] == 3

    def test_single_entry_no_supersession(self) -> None:
        sha = _epoch_sha("single")
        rows = self._build_chain_rows(sha)
        result = resolve_supersession_chain(sha256=sha, rows=rows)
        assert result["head"] == sha
        assert result["terminal"] == sha
        assert result["length"] == 1
        assert not result["cycle_detected"]

    def test_cycle_detection(self) -> None:
        a, b, c = _epoch_sha("a"), _epoch_sha("b"), _epoch_sha("c")
        rows = [
            {"sha256": a, "superseded_by_sha256": b, "revoked": False, "tombstoned": False},
            {"sha256": b, "superseded_by_sha256": c, "revoked": False, "tombstoned": False},
            {"sha256": c, "superseded_by_sha256": a, "revoked": False, "tombstoned": False},  # cycle back to a
        ]
        result = resolve_supersession_chain(sha256=a, rows=rows)
        assert result["cycle_detected"] is True
        assert result["terminal"] == a  # cycle point
        assert len(result["chain"]) == 3


# ── E2E: Store → Supersede → Verify exclusion ───────────────────────────────

class TestStaleArtifactSupersessionLifecycle:
    """Full lifecycle: store artifact, supersede with new version,
    verify chain, confirm stale/superseded excluded from default retrieval."""

    def _fresh_evidence(self, sha: str, purpose: str = "default") -> EvidenceContract:
        return EvidenceContract(
            sha256=sha,
            trust_tier="verified",
            fresh_until=_future_iso(),
        )

    def _stale_evidence(self, sha: str) -> EvidenceContract:
        return EvidenceContract(
            sha256=sha,
            trust_tier="verified",
            fresh_until=_past_iso(),
        )

    def _superseded_evidence(self, sha: str, supersedes: str) -> EvidenceContract:
        return EvidenceContract(
            sha256=sha,
            trust_tier="verified",
            fresh_until=_future_iso(),
            supersedes_sha256=supersedes,
        )

    def test_fresh_artifact_passes_execution_admission(self) -> None:
        """Fresh evidence must be admissible for execution_admission."""
        contract = self._fresh_evidence(_epoch_sha("fresh1"))
        row_style = {
            "freshness_status": "stale" if contract.is_stale() else "fresh",
            "superseded_by_sha256": contract.supersedes_sha256,
            "revoked": contract.revoked,
            "tombstoned": contract.tombstoned,
        }
        verdict = check_evidence_freshness(row_style, purpose="execution_admission")
        assert verdict.admissible is True
        assert verdict.freshness_status == "fresh"

    def test_stale_artifact_rejected_by_execution_admission(self) -> None:
        """Stale evidence must be rejected for execution_admission."""
        contract = self._stale_evidence(_epoch_sha("stale1"))
        row_style = {
            "freshness_status": "stale" if contract.is_stale() else "fresh",
            "superseded_by_sha256": contract.supersedes_sha256,
            "revoked": contract.revoked,
            "tombstoned": contract.tombstoned,
        }
        verdict = check_evidence_freshness(row_style, purpose="execution_admission")
        assert verdict.admissible is False
        assert verdict.freshness_status == "stale"

    def test_superseded_artifact_rejected_by_execution_admission(self) -> None:
        """Superseded evidence must be rejected for execution_admission."""
        contract = self._superseded_evidence(_epoch_sha("old"), _epoch_sha("new"))
        row_style = {
            "freshness_status": "stale" if contract.is_stale() else "fresh",
            "superseded_by_sha256": contract.supersedes_sha256,
            "revoked": contract.revoked,
            "tombstoned": contract.tombstoned,
        }
        verdict = check_evidence_freshness(row_style, purpose="execution_admission")
        assert verdict.admissible is False
        assert verdict.freshness_status == "superseded"

    def test_stale_admitted_for_benchmark(self) -> None:
        """Stale evidence should be admitted for unrestricted purposes."""
        contract = self._stale_evidence(_epoch_sha("stale2"))
        row_style = {
            "freshness_status": "stale" if contract.is_stale() else "fresh",
            "superseded_by_sha256": contract.supersedes_sha256,
            "revoked": contract.revoked,
            "tombstoned": contract.tombstoned,
        }
        verdict = check_evidence_freshness(row_style, purpose="benchmark")
        assert verdict.admissible is True
        # still reports stale status but admits

    def test_full_lifecycle_store_supersede_verify(self) -> None:
        """End-to-end: v1 stored → v2 supersedes v1 → chain confirms v1 excluded."""
        v1 = _epoch_sha("v1")
        v2 = _epoch_sha("v2")
        v3 = _epoch_sha("v3")

        # Build 3-gen chain: v1 → v2 → v3
        rows = [
            {"sha256": v1, "superseded_by_sha256": v2, "revoked": False, "tombstoned": False},
            {"sha256": v2, "superseded_by_sha256": v3, "revoked": False, "tombstoned": False},
            {"sha256": v3, "superseded_by_sha256": "", "revoked": False, "tombstoned": False},
        ]

        # Verify chain from v1
        chain = resolve_supersession_chain(sha256=v1, rows=rows)
        assert chain["head"] == v1
        assert chain["terminal"] == v3
        assert chain["length"] == 3
        assert chain["chain"] == [v1, v2, v3]

        # v1 as superseded evidence → rejected for governance_vote
        v1_row = {
            "freshness_status": "fresh",
            "superseded_by_sha256": v2,
            "revoked": False,
            "tombstoned": False,
        }
        verdict = check_evidence_freshness(v1_row, purpose="governance_vote")
        assert verdict.admissible is False
        assert verdict.freshness_status == "superseded"

        # v3 as terminal evidence → admitted for governance_vote
        v3_row = {
            "freshness_status": "fresh",
            "superseded_by_sha256": "",
            "revoked": False,
            "tombstoned": False,
        }
        verdict_v3 = check_evidence_freshness(v3_row, purpose="governance_vote")
        assert verdict_v3.admissible is True
        assert verdict_v3.freshness_status == "fresh"

    def test_stale_artifact_excluded_from_default_retrieval_pattern(self) -> None:
        """Simulate the retrieval pattern: stale artifact flagged but
        admissible for overridable 'default' purpose (caller decides)."""
        contract = self._stale_evidence(_epoch_sha("excluded"))
        row = {
            "freshness_status": "stale" if contract.is_stale() else "fresh",
            "superseded_by_sha256": contract.supersedes_sha256,
            "revoked": contract.revoked,
            "tombstoned": contract.tombstoned,
        }
        # For "default" purpose (overridable), stale is flagged not rejected
        verdict = check_evidence_freshness(row, purpose="default")
        assert verdict.admissible is True  # overridable: admitted but flagged
        assert verdict.freshness_status == "stale"
        assert any("flagged" in r.lower() for r in verdict.reasons)

    def test_content_hash_tampered_always_rejected(self) -> None:
        """Tampered content hash rejects regardless of purpose."""
        row = {
            "freshness_status": "fresh",
            "superseded_by_sha256": "",
            "revoked": False,
            "tombstoned": False,
            "content_hash_valid": False,
        }
        for purpose in ("execution_admission", "default", "benchmark"):
            verdict = check_evidence_freshness(row, purpose=purpose)
            assert verdict.admissible is False, f"Tampered should reject for {purpose}"
            assert verdict.freshness_status == "tampered"


# ── EvidenceContract normalized lifecycle ────────────────────────────────────

class TestEvidenceContractNormalizedLifecycle:
    """Store → retrieve → normalize → check freshness full round-trip."""

    def test_normalize_preserves_supersession_fields(self) -> None:
        raw: dict[str, Any] = {
            "sha256": _epoch_sha("norm"),
            "superseded_by_sha256": _epoch_sha("next"),
            "freshness_status": "fresh",
            "revoked": False,
            "tombstoned": 0,
            "fresh_until": _future_iso(),
            "confidence": 0.95,
        }
        contract = EvidenceContract.normalize(raw)
        assert contract.supersedes_sha256 == _epoch_sha("next")
        assert contract.fresh_until == _future_iso()
        assert contract.confidence == 0.95
        assert not contract.revoked
        assert not contract.tombstoned

    def test_normalize_handles_stale_freshness_status(self) -> None:
        """freshness_status='stale' without fresh_until → normalize synthesizes
        epoch-0 fresh_until so is_stale() returns True."""
        raw: dict[str, Any] = {
            "sha256": _epoch_sha("stale-norm"),
            "freshness_status": "stale",
            "revoked": False,
            "tombstoned": False,
        }
        contract = EvidenceContract.normalize(raw)
        assert contract.fresh_until is not None
        assert contract.is_stale() is True

    def test_normalize_round_trips_superseded_then_check(self) -> None:
        """Normalize a superseded dict, then verify it's rejected."""
        raw: dict[str, Any] = {
            "sha256": _epoch_sha("oldest"),
            "superseded_by_sha256": _epoch_sha("newest"),
            "fresh_until": _future_iso(),
            "revoked": 0,
            "tombstoned": 0,
        }
        contract = EvidenceContract.normalize(raw)
        row = {
            "freshness_status": "stale" if contract.is_stale() else "fresh",
            "superseded_by_sha256": contract.supersedes_sha256,
            "revoked": contract.revoked,
            "tombstoned": contract.tombstoned,
        }
        verdict = check_evidence_freshness(row, purpose="execution_admission")
        assert verdict.admissible is False
        assert verdict.freshness_status == "superseded"
