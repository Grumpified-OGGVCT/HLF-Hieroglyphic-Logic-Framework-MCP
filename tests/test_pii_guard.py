"""
Tests for hlf_mcp.hlf.pii_guard — Runtime PII Guard module.

Covers:
- PIIGuard.scan() detects and does not detect various PII categories
- PIIGuard._apply_redactions() redacts text correctly
- PIIGuard.scan_and_block() returns safe/unsafe flags
- Convenience functions scan_for_pii() / redact_pii()
- PIIScanResult.to_dict() serialisation
- PII guard integration in runtime _dispatch_host memory_store
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hlf_mcp.hlf.pii_guard import (
    PIICategory,
    PIIDetection,
    PIIGuard,
    PIIScanResult,
    load_pii_policy,
    redact_pii,
    scan_for_pii,
)


# ── PIIDetection ──────────────────────────────────────────────────────────────

class TestPIIDetection:
    def test_redaction_short_value(self):
        d = PIIDetection(PIICategory.EMAIL, "ab", 0, 2, 0.9)
        assert d.redacted_value == "**"

    def test_redaction_longer_value(self):
        d = PIIDetection(PIICategory.EMAIL, "hello@world.com", 0, 15, 0.9)
        # first 2 + stars + last 2
        assert d.redacted_value.startswith("he")
        assert d.redacted_value.endswith("om")
        assert "*" in d.redacted_value

    def test_explicit_redacted_value_preserved(self):
        d = PIIDetection(PIICategory.SSN, "123-45-6789", 0, 11, 0.95, "[REDACTED]")
        assert d.redacted_value == "[REDACTED]"


# ── PIIScanResult ─────────────────────────────────────────────────────────────

class TestPIIScanResult:
    def test_to_dict_no_pii(self):
        result = PIIScanResult(has_pii=False, redacted_text="safe text")
        d = result.to_dict()
        assert d["has_pii"] is False
        assert d["safe_to_store"] is True
        assert d["detection_count"] == 0

    def test_to_dict_with_pii(self):
        det = PIIDetection(PIICategory.EMAIL, "x@y.com", 0, 7, 0.9)
        result = PIIScanResult(
            has_pii=True,
            detections=[det],
            redacted_text="x*****m",
            categories_found={PIICategory.EMAIL},
        )
        d = result.to_dict()
        assert d["has_pii"] is True
        assert d["safe_to_store"] is False
        assert d["detection_count"] == 1
        assert "EMAIL" in d["categories"]


# ── PIIGuard.scan() ───────────────────────────────────────────────────────────

class TestPIIGuardScan:
    def setup_method(self):
        self.guard = PIIGuard()

    # --- Email ---
    def test_detects_email(self):
        result = self.guard.scan("Contact me at alice@example.com for details.")
        assert result.has_pii
        assert PIICategory.EMAIL in result.categories_found

    def test_no_false_positive_for_plain_text(self):
        result = self.guard.scan("The quick brown fox jumps over the lazy dog.")
        # Should not flag email/ssn/credit-card
        assert PIICategory.EMAIL not in result.categories_found
        assert PIICategory.SSN not in result.categories_found
        assert PIICategory.CREDIT_CARD not in result.categories_found

    # --- Phone ---
    def test_detects_us_phone(self):
        result = self.guard.scan("Call us at 555-867-5309.")
        assert PIICategory.PHONE in result.categories_found

    # --- SSN ---
    def test_detects_ssn(self):
        result = self.guard.scan("SSN: 123-45-6789")
        assert PIICategory.SSN in result.categories_found

    # --- Credit card ---
    def test_detects_visa_card(self):
        result = self.guard.scan("Card: 4111111111111111")
        assert PIICategory.CREDIT_CARD in result.categories_found

    # --- IP address ---
    def test_detects_ip_address(self):
        result = self.guard.scan("Server IP is 192.168.1.100")
        assert PIICategory.IP_ADDRESS in result.categories_found

    # --- Date of birth ---
    def test_detects_dob(self):
        result = self.guard.scan("DOB: 01/15/1990")
        assert PIICategory.DATE_OF_BIRTH in result.categories_found

    # --- URL ---
    def test_detects_url(self):
        result = self.guard.scan("Visit https://example.com/path?q=1 for info.")
        assert PIICategory.URL in result.categories_found

    # --- Address ---
    def test_detects_street_address(self):
        result = self.guard.scan("I live at 123 Main Street, Springfield.")
        assert PIICategory.ADDRESS in result.categories_found

    # --- Name ---
    def test_detects_person_name_with_title(self):
        result = self.guard.scan("Please speak with Dr. John Smith about your case.")
        assert PIICategory.NAME in result.categories_found

    # --- Redaction correctness ---
    def test_redacted_text_differs_from_original(self):
        text = "Email alice@example.com now."
        result = self.guard.scan(text)
        assert result.redacted_text != text
        assert "alice@example.com" not in result.redacted_text

    def test_empty_string_no_pii(self):
        result = self.guard.scan("")
        assert not result.has_pii
        assert result.redacted_text == ""

    def test_multiple_pii_in_one_string(self):
        text = "Bob Smith's email is bob@test.org and phone 555-123-4567."
        result = self.guard.scan(text)
        assert result.has_pii
        assert len(result.detections) >= 2

    # --- strict_mode ---
    def test_strict_mode_lowers_threshold(self):
        guard_strict = PIIGuard(strict_mode=True, min_confidence=0.9)
        guard_normal = PIIGuard(strict_mode=False, min_confidence=0.9)
        text = "John Doe lives nearby."
        # In strict mode, everything that matches is flagged regardless of confidence
        result_strict = guard_strict.scan(text)
        result_normal = guard_normal.scan(text)
        # Strict should flag at least as many (potentially more) detections
        assert len(result_strict.detections) >= len(result_normal.detections)


# ── PIIGuard.scan_and_block() ─────────────────────────────────────────────────

class TestScanAndBlock:
    def setup_method(self):
        self.guard = PIIGuard()

    def test_safe_text_returns_true_and_original(self):
        text = "This is completely safe."
        is_safe, content = self.guard.scan_and_block(text)
        assert is_safe is True
        assert content == text

    def test_pii_text_returns_false_and_redacted(self):
        text = "My email is danger@example.com"
        is_safe, content = self.guard.scan_and_block(text)
        assert is_safe is False
        assert "danger@example.com" not in content


# ── Convenience functions ─────────────────────────────────────────────────────

class TestConvenienceFunctions:
    def test_scan_for_pii_returns_result_object(self):
        result = scan_for_pii("Call 555-867-5309 now.")
        assert isinstance(result, PIIScanResult)
        assert result.has_pii

    def test_redact_pii_removes_email(self):
        redacted = redact_pii("Send to user@domain.com please.")
        assert "user@domain.com" not in redacted

    def test_redact_pii_safe_text_unchanged(self):
        text = "Nothing to see here."
        assert redact_pii(text) == text

    def test_get_statistics(self):
        guard = PIIGuard()
        stats = guard.get_statistics()
        assert "pattern_count" in stats
        assert stats["pattern_count"] >= 7
        assert "EMAIL" in stats["categories"]
        assert stats["policy_source"].endswith("governance\\pii_policy.json") or stats["policy_source"].endswith("governance/pii_policy.json")


class TestGovernedPIIPolicy:
    def test_default_policy_loads_from_governance(self):
        policy = load_pii_policy()
        assert policy["strict_mode"] is False
        assert policy["min_confidence"] == 0.7
        assert "EMAIL" in policy["enabled_categories"]

    def test_custom_policy_can_disable_category(self, tmp_path: Path):
        policy_path = tmp_path / "pii_policy.json"
        policy_path.write_text(
            '{"enabled_categories": ["EMAIL"], "strict_mode": false, "min_confidence": 0.7}',
            encoding="utf-8",
        )

        guard = PIIGuard(policy_path=policy_path)
        result = guard.scan("Call us at 555-867-5309 or email alice@example.com")

        assert PIICategory.EMAIL in result.categories_found
        assert PIICategory.PHONE not in result.categories_found


# ── Runtime integration: memory_store PII guard ───────────────────────────────

class TestRuntimeMemoryStorePIIGuard:
    """Verify that _dispatch_host('memory_store', ...) redacts PII values."""

    def _call_memory_store(self, value: str) -> tuple[dict, list]:
        from hlf_mcp.hlf.runtime import _dispatch_host
        scope: dict = {}
        side_effects: list = []
        _dispatch_host("memory_store", ["test_key", value], scope, side_effects)
        return scope, side_effects

    def test_clean_value_stored_as_is(self):
        scope, effects = self._call_memory_store("hello world")
        stored = scope.get("_mem_test_key", [])
        assert stored == ["hello world"]
        pii_events = [e for e in effects if e.get("type") == "pii_redacted"]
        assert len(pii_events) == 0

    def test_email_in_value_is_redacted(self):
        scope, effects = self._call_memory_store("Contact alice@secret.org for info")
        stored = scope.get("_mem_test_key", [])
        assert stored, "value should have been stored"
        stored_val = stored[0]
        assert "alice@secret.org" not in str(stored_val)

        pii_events = [e for e in effects if e.get("type") == "pii_redacted"]
        assert len(pii_events) == 1
        assert "EMAIL" in pii_events[0]["categories"]

    def test_ssn_in_value_is_redacted(self):
        scope, effects = self._call_memory_store("SSN 123-45-6789")
        stored_val = scope.get("_mem_test_key", [])[0]
        assert "123-45-6789" not in str(stored_val)

    def test_memory_write_side_effect_recorded(self):
        _, effects = self._call_memory_store("hello")
        write_events = [e for e in effects if e.get("type") == "memory_write"]
        # The registry effects loop + the explicit branch each append a memory_write entry
        assert len(write_events) >= 1
        # The branch-level entry has 'count' and 'key'
        branch_events = [e for e in write_events if "count" in e]
        assert branch_events, "Expected at least one branch-level memory_write side-effect"
        assert branch_events[0]["key"] == "test_key"

    def test_none_value_handled_gracefully(self):
        from hlf_mcp.hlf.runtime import _dispatch_host
        scope: dict = {}
        side_effects: list = []
        # Two args: key + None as value
        result = _dispatch_host("memory_store", ["k", None], scope, side_effects)
        assert result is True
