"""Tests for HLF → Msty Claw provenance memory bridge."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import pytest

from hlf_mcp.bridges.msty_claw.memory_bridge import (
    DECAY_RULES,
    SOURCE_CONFIDENCE,
    Contradiction,
    MstyMemoryBridge,
    ProvenancedEntry,
    _compute_hash,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def bridge() -> MstyMemoryBridge:
    return MstyMemoryBridge()


@pytest.fixture
def sample_entries(bridge: MstyMemoryBridge) -> list[ProvenancedEntry]:
    return [
        bridge.tag_entry("The API server runs on port 8080", "user_stated"),
        bridge.tag_entry("The API server runs on port 9090", "web_search"),
        bridge.tag_entry("Python 3.12 is the minimum version", "tool_output"),
    ]


# ── Tagging ───────────────────────────────────────────────────────────────────


class TestTagging:
    def test_user_stated_confidence(self, bridge: MstyMemoryBridge) -> None:
        entry = bridge.tag_entry("Deploy to production at 22:00 UTC", "user_stated")
        assert entry.confidence == 0.95
        assert entry.source == "user_stated"
        assert entry.decay_rule == "slow"
        assert entry.validation_status == "unvalidated"
        assert entry.tagged_at  # ISO 8601 timestamp present
        assert entry.entry_hash  # SHA256 present

    def test_web_search_confidence(self, bridge: MstyMemoryBridge) -> None:
        entry = bridge.tag_entry("Latest Python version is 3.13", "web_search")
        assert entry.confidence == 0.50
        assert entry.source == "web_search"
        assert entry.decay_rule == "fast"

    def test_tool_output_confidence(self, bridge: MstyMemoryBridge) -> None:
        entry = bridge.tag_entry("All 247 tests passed", "tool_output")
        assert entry.confidence == 0.90
        assert entry.decay_rule == "slow"

    def test_shell_output_confidence(self, bridge: MstyMemoryBridge) -> None:
        entry = bridge.tag_entry("Disk usage: 45%", "shell_output")
        assert entry.confidence == 0.85

    def test_hlf_symbolic_proof_confidence(self, bridge: MstyMemoryBridge) -> None:
        entry = bridge.tag_entry("Ж [ASSERT] status=ok", "hlf_symbolic_proof")
        assert entry.confidence == 0.95

    def test_model_inference_confidence(self, bridge: MstyMemoryBridge) -> None:
        entry = bridge.tag_entry("This code probably has a race condition", "model_inference")
        assert entry.confidence == 0.30
        assert entry.decay_rule == "medium"

    def test_conversation_context_confidence(self, bridge: MstyMemoryBridge) -> None:
        entry = bridge.tag_entry("User mentioned they prefer PostgreSQL", "conversation_context")
        assert entry.confidence == 0.40

    def test_unknown_source_fallback(self, bridge: MstyMemoryBridge) -> None:
        entry = bridge.tag_entry("Some random fact", "nonexistent_source")
        assert entry.confidence == 0.10
        assert entry.decay_rule == "fast"

    def test_case_insensitive_source(self, bridge: MstyMemoryBridge) -> None:
        entry = bridge.tag_entry("Test", "USER_STATED")
        assert entry.confidence == 0.95

    def test_whitespace_insensitive_source(self, bridge: MstyMemoryBridge) -> None:
        entry = bridge.tag_entry("Test", "  web_search  ")
        assert entry.confidence == 0.50

    def test_empty_content_raises(self, bridge: MstyMemoryBridge) -> None:
        with pytest.raises(ValueError, match="empty"):
            bridge.tag_entry("", "user_stated")

    def test_whitespace_only_content_raises(self, bridge: MstyMemoryBridge) -> None:
        with pytest.raises(ValueError, match="empty"):
            bridge.tag_entry("   \n  \t  ", "user_stated")

    def test_metadata_preserved(self, bridge: MstyMemoryBridge) -> None:
        meta = {"topic": "deployment", "priority": "high"}
        entry = bridge.tag_entry("Deploy at midnight", "user_stated", metadata=meta)
        assert entry.metadata == meta

    def test_entry_hash_consistency(self) -> None:
        """Same content → same hash."""
        h1 = _compute_hash("hello world")
        h2 = _compute_hash("hello world")
        assert h1 == h2
        assert len(h1) == 64  # SHA256 hex

    def test_entry_hash_different_content(self) -> None:
        h1 = _compute_hash("hello world")
        h2 = _compute_hash("hello world!")
        assert h1 != h2


# ── Validation ────────────────────────────────────────────────────────────────


class TestValidation:
    def test_no_validator_passes(self, bridge: MstyMemoryBridge) -> None:
        entry = bridge.tag_entry("Any content", "user_stated")
        result = bridge.validate_entry(entry)
        assert result.validated is True
        assert result.validator == "none"

    def test_tag_and_validate(self, bridge: MstyMemoryBridge) -> None:
        entry, result = bridge.tag_and_validate("Verified fact", "tool_output")
        assert result.validated is True
        # With no validator injected, entry stays unvalidated
        assert entry.validation_status == "validated"

    def test_callable_validator_pass(self) -> None:
        b = MstyMemoryBridge(hlf_validator=lambda content: True)
        entry = b.tag_entry("test", "user_stated")
        result = b.validate_entry(entry)
        assert result.validated is True
        assert result.validator == "hlf_symbolic_surface"

    def test_callable_validator_fail(self) -> None:
        b = MstyMemoryBridge(hlf_validator=lambda content: False)
        entry = b.tag_entry("test", "user_stated")
        result = b.validate_entry(entry)
        assert result.validated is False
        assert "rejected" in result.issues[0]

    def test_set_validator(self, bridge: MstyMemoryBridge) -> None:
        bridge.set_validator(lambda c: True)
        entry = bridge.tag_entry("test", "user_stated")
        result = bridge.validate_entry(entry)
        assert result.validated is True

    def test_validator_exception(self) -> None:
        def raise_err(_: str) -> bool:
            raise RuntimeError("Boom")

        b = MstyMemoryBridge(hlf_validator=raise_err)
        entry = b.tag_entry("test", "user_stated")
        result = b.validate_entry(entry)
        assert result.validated is False
        assert "Boom" in result.issues[0]


# ── Confidence decay ──────────────────────────────────────────────────────────


class TestConfidenceDecay:
    def test_no_decay_immediate(self, bridge: MstyMemoryBridge) -> None:
        entry = bridge.tag_entry("Fresh entry", "user_stated")
        decayed = bridge.check_confidence_decay(entry)
        assert decayed == pytest.approx(0.95)

    def test_slow_decay_one_week(self, bridge: MstyMemoryBridge) -> None:
        entry = bridge.tag_entry("One week old", "user_stated")
        tagged = datetime.fromisoformat(entry.tagged_at)
        now = tagged + timedelta(weeks=1)
        decayed = bridge.check_confidence_decay(entry, now=now)
        # 0.95 * (1 - 0.05 * 1) = 0.9025
        assert decayed == pytest.approx(0.9025)

    def test_fast_decay_one_week(self, bridge: MstyMemoryBridge) -> None:
        entry = bridge.tag_entry("Web fact", "web_search")
        tagged = datetime.fromisoformat(entry.tagged_at)
        now = tagged + timedelta(weeks=1)
        decayed = bridge.check_confidence_decay(entry, now=now)
        # 0.50 * (1 - 0.30 * 1) = 0.35
        assert decayed == pytest.approx(0.35)

    def test_medium_decay_one_week(self, bridge: MstyMemoryBridge) -> None:
        entry = bridge.tag_entry("Inferred thing", "model_inference")
        tagged = datetime.fromisoformat(entry.tagged_at)
        now = tagged + timedelta(weeks=1)
        decayed = bridge.check_confidence_decay(entry, now=now)
        # 0.30 * (1 - 0.15 * 1) = 0.255
        assert decayed == pytest.approx(0.255)

    def test_fast_decay_seven_days(self, bridge: MstyMemoryBridge) -> None:
        """After 7 days, fast decay: 0.50 * (1 - 0.30 * 1) = 0.35."""
        entry = bridge.tag_entry("Old web search", "web_search")
        tagged = datetime.fromisoformat(entry.tagged_at)
        now = tagged + timedelta(days=7)
        decayed = bridge.check_confidence_decay(entry, now=now)
        assert decayed == pytest.approx(0.35)

    def test_decay_clamped_to_zero(self, bridge: MstyMemoryBridge) -> None:
        entry = bridge.tag_entry("Very old", "web_search")
        tagged = datetime.fromisoformat(entry.tagged_at)
        now = tagged + timedelta(weeks=20)
        decayed = bridge.check_confidence_decay(entry, now=now)
        assert decayed == 0.0

    def test_future_date_no_decay(self, bridge: MstyMemoryBridge) -> None:
        entry = bridge.tag_entry("From future", "user_stated")
        tagged = datetime.fromisoformat(entry.tagged_at)
        now = tagged - timedelta(weeks=1)
        decayed = bridge.check_confidence_decay(entry, now=now)
        assert decayed == pytest.approx(0.95)

    def test_no_timestamp_fallback(self, bridge: MstyMemoryBridge) -> None:
        """Entry with no parsable timestamp returns original confidence."""
        entry = bridge.tag_entry("Broken time", "user_stated")
        entry.tagged_at = "not-a-timestamp"
        decayed = bridge.check_confidence_decay(entry)
        assert decayed == 0.95


# ── Contradiction detection ───────────────────────────────────────────────────


class TestContradictionDetection:
    def test_no_contradictions_identical(self, bridge: MstyMemoryBridge) -> None:
        entries = [
            bridge.tag_entry("Python 3.12 required", "tool_output"),
            bridge.tag_entry("Python 3.12 required", "tool_output"),
        ]
        contradictions = bridge.detect_contradictions(entries)
        assert contradictions == []

    def test_no_contradictions_different_topics(self, bridge: MstyMemoryBridge) -> None:
        entries = [
            bridge.tag_entry("Python 3.12 required", "tool_output"),
            bridge.tag_entry("PostgreSQL 16 is the database", "tool_output"),
        ]
        contradictions = bridge.detect_contradictions(entries)
        assert contradictions == []

    def test_contradiction_detected_different_values(self, bridge: MstyMemoryBridge) -> None:
        entries = [
            bridge.tag_entry("The API runs on port 8080", "tool_output"),
            bridge.tag_entry("The API runs on port 9090", "web_search"),
        ]
        contradictions = bridge.detect_contradictions(entries)
        assert len(contradictions) == 1
        c = contradictions[0]
        assert c.conflict_field == "content"
        assert c.confidence_a == 0.90  # tool_output > web_search
        assert c.confidence_b == 0.50
        assert c.resolution == "keep_higher_confidence"

    def test_contradiction_equal_confidence(self, bridge: MstyMemoryBridge) -> None:
        entries = [
            bridge.tag_entry("The API runs on port 8080", "tool_output"),
            bridge.tag_entry("The API runs on port 9090", "tool_output"),
        ]
        contradictions = bridge.detect_contradictions(entries)
        assert len(contradictions) == 1
        # equal confidence → flag_for_review (can't pick a "higher" when tied)
        assert contradictions[0].resolution == "flag_for_review"

    def test_contradiction_higher_b(self, bridge: MstyMemoryBridge) -> None:
        entries = [
            bridge.tag_entry("The API runs on port 9090", "web_search"),
            bridge.tag_entry("The API runs on port 8080", "user_stated"),
        ]
        contradictions = bridge.detect_contradictions(entries)
        assert len(contradictions) == 1
        # user_stated (0.95) > web_search (0.50), entry_b has higher
        assert contradictions[0].resolution == "keep_higher_confidence"

    def test_bulk_contradiction_check_marks_entries(self, bridge: MstyMemoryBridge) -> None:
        entries = [
            bridge.tag_entry("Port is 8080", "tool_output"),
            bridge.tag_entry("Port is 9090", "web_search"),
            bridge.tag_entry("Unrelated fact about weather", "user_stated"),
        ]
        contradictions = bridge.bulk_contradiction_check(entries, mark_contradicted=True)
        assert len(contradictions) == 1
        assert entries[0].validation_status == "contradicted"
        assert entries[1].validation_status == "contradicted"
        assert entries[2].validation_status == "unvalidated"

    def test_multi_entry_contradictions(self, bridge: MstyMemoryBridge) -> None:
        entries = [
            bridge.tag_entry("Service uses Redis for caching", "tool_output"),
            bridge.tag_entry("Service uses Memcached for caching", "web_search"),
            bridge.tag_entry("Service uses Redis for caching", "model_inference"),
        ]
        contradictions = bridge.detect_contradictions(entries)
        # Tool output vs web search on same topic → contradiction
        # Model inference agrees with tool output → no contradiction
        # But model inference vs web search → contradiction
        assert len(contradictions) == 2


# ── Durable promotion ─────────────────────────────────────────────────────────


class TestDurablePromotion:
    def test_promote_high_confidence_validated(self, bridge: MstyMemoryBridge) -> None:
        entry = bridge.tag_entry("Verified fact", "user_stated")
        entry.validation_status = "validated"
        assert bridge.promote_to_durable(entry) is True

    def test_promote_high_confidence_unvalidated(self, bridge: MstyMemoryBridge) -> None:
        entry = bridge.tag_entry("High confidence unvalidated", "user_stated")
        # unvalidated but confidence 0.95 ≥ 0.90 → promoted
        assert bridge.promote_to_durable(entry) is True

    def test_promote_low_confidence_rejected(self, bridge: MstyMemoryBridge) -> None:
        entry = bridge.tag_entry("Unverified web fact", "web_search")
        entry.validation_status = "validated"
        # Confidence 0.50 < 0.70 → rejected
        assert bridge.promote_to_durable(entry) is False

    def test_promote_contradicted_rejected(self, bridge: MstyMemoryBridge) -> None:
        entry = bridge.tag_entry("High confidence but contradicted", "user_stated")
        entry.validation_status = "contradicted"
        assert bridge.promote_to_durable(entry) is False

    def test_promote_borderline_confidence(self, bridge: MstyMemoryBridge) -> None:
        entry = bridge.tag_entry("Tool output", "tool_output")
        entry.validation_status = "validated"
        # 0.90 ≥ 0.70 → promoted
        assert bridge.promote_to_durable(entry) is True

    def test_promote_medium_confidence_unvalidated(self, bridge: MstyMemoryBridge) -> None:
        entry = bridge.tag_entry("Conversation context", "conversation_context")
        # confidence 0.40, unvalidated → rejected on confidence alone
        assert bridge.promote_to_durable(entry) is False

    def test_promote_model_inference(self, bridge: MstyMemoryBridge) -> None:
        entry = bridge.tag_entry("LLM inference", "model_inference")
        entry.validation_status = "validated"
        # confidence 0.30 < 0.70 → rejected
        assert bridge.promote_to_durable(entry) is False


# ── Re-verification checks ────────────────────────────────────────────────────


class TestReverification:
    def test_old_web_search_needs_reverify(self, bridge: MstyMemoryBridge) -> None:
        entry = bridge.tag_entry("Old web fact", "web_search")
        tagged = datetime.fromisoformat(entry.tagged_at)
        tagged_old = tagged - timedelta(days=8)
        entry.tagged_at = tagged_old.isoformat()
        assert bridge.should_reverify(entry) is True

    def test_recent_user_stated_no_reverify(self, bridge: MstyMemoryBridge) -> None:
        entry = bridge.tag_entry("Recent user direction", "user_stated")
        assert bridge.should_reverify(entry) is False

    def test_old_model_inference_needs_reverify(self, bridge: MstyMemoryBridge) -> None:
        entry = bridge.tag_entry("Old inference", "model_inference")
        tagged = datetime.fromisoformat(entry.tagged_at)
        tagged_old = tagged - timedelta(days=10)
        entry.tagged_at = tagged_old.isoformat()
        assert bridge.should_reverify(entry) is True

    def test_old_tool_output_no_reverify_if_not_decayed(self, bridge: MstyMemoryBridge) -> None:
        """tool_output is slow decay (5%/week). 3 weeks → 0.90 * 0.85 = 0.765, still > 0.50."""
        entry = bridge.tag_entry("Old tool output", "tool_output")
        tagged = datetime.fromisoformat(entry.tagged_at)
        tagged_old = tagged - timedelta(weeks=3)
        entry.tagged_at = tagged_old.isoformat()
        # Confidence: 0.90 * (1 - 0.05*3) = 0.765 > 0.50
        # Also tool_output is not one of (web_search, model_inference, unknown)
        assert bridge.should_reverify(entry) is False

    def test_heavily_decayed_user_stated_needs_reverify(self, bridge: MstyMemoryBridge) -> None:
        """user_stated with 5%/week. After 200 weeks → 0.95 * (1 - 0.05*200) ≈ -8.55 → clamped 0.0."""
        entry = bridge.tag_entry("Ancient user fact", "user_stated")
        tagged = datetime.fromisoformat(entry.tagged_at)
        tagged_old = tagged - timedelta(weeks=200)
        entry.tagged_at = tagged_old.isoformat()
        assert bridge.should_reverify(entry) is True

    def test_recent_web_search_no_reverify(self, bridge: MstyMemoryBridge) -> None:
        entry = bridge.tag_entry("Fresh web fact", "web_search")
        assert bridge.should_reverify(entry) is False

    def test_exactly_seven_days_web_search_reverify(self, bridge: MstyMemoryBridge) -> None:
        entry = bridge.tag_entry("7 day web fact", "web_search")
        tagged = datetime.fromisoformat(entry.tagged_at)
        tagged_7 = tagged - timedelta(days=7)
        entry.tagged_at = tagged_7.isoformat()
        # At 7 days (1 week), fast decay: 0.50 * 0.70 = 0.35 < 0.50 → needs reverify
        assert bridge.should_reverify(entry) is True

    def test_unknown_source_old_needs_reverify(self, bridge: MstyMemoryBridge) -> None:
        entry = bridge.tag_entry("Mystery fact", "unknown")
        tagged = datetime.fromisoformat(entry.tagged_at)
        tagged_old = tagged - timedelta(days=8)
        entry.tagged_at = tagged_old.isoformat()
        assert bridge.should_reverify(entry) is True

    def test_decay_below_threshold_needs_reverify(self, bridge: MstyMemoryBridge) -> None:
        """slow decay after many weeks drops below 0.50."""
        entry = bridge.tag_entry("Very old tool output", "tool_output")
        tagged = datetime.fromisoformat(entry.tagged_at)
        tagged_old = tagged - timedelta(weeks=100)
        entry.tagged_at = tagged_old.isoformat()
        # confidence → 0.0, definitely below 0.50
        assert bridge.should_reverify(entry) is True


# ── Entry serialization ───────────────────────────────────────────────────────


class TestSerialization:
    def test_to_dict_from_dict_roundtrip(self, bridge: MstyMemoryBridge) -> None:
        entry = bridge.tag_entry("Roundtrip test", "user_stated", metadata={"key": "value"})
        d = entry.to_dict()
        restored = ProvenancedEntry.from_dict(d)
        assert restored.content == entry.content
        assert restored.source == entry.source
        assert restored.confidence == entry.confidence
        assert restored.validation_status == entry.validation_status
        assert restored.tagged_at == entry.tagged_at
        assert restored.entry_hash == entry.entry_hash
        assert restored.metadata == entry.metadata
        assert restored.decay_rule == entry.decay_rule

    def test_from_dict_defaults(self) -> None:
        d = {
            "content": "test",
            "source": "unknown",
            "confidence": 0.10,
            "validation_status": "unvalidated",
            "tagged_at": "2025-01-01T00:00:00+00:00",
            "entry_hash": "abc123",
        }
        entry = ProvenancedEntry.from_dict(d)
        assert entry.metadata == {}
        assert entry.decay_rule == "medium"


# ── DECAY_RULES constants ─────────────────────────────────────────────────────


class TestDecayRules:
    def test_all_sources_have_decay_rules(self) -> None:
        for source in SOURCE_CONFIDENCE:
            assert source in ("user_stated", "tool_output", "shell_output",
                              "hlf_symbolic_proof", "web_search", "model_inference",
                              "conversation_context", "unknown")

    def test_decay_rate_bounds(self) -> None:
        for rule, rate in DECAY_RULES.items():
            assert 0.0 < rate < 1.0
