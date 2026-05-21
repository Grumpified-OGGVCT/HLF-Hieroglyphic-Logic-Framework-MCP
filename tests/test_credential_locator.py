"""Tests for Credential Locator — metadata registry for credential lifecycle management."""

from __future__ import annotations

import time

from hlf_mcp.hlf.credential_locator import CredentialLocator, CredentialRef


# ── Helpers ────────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _future_iso(days: int) -> str:
    t = time.time() + (days * 86400)
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


def _past_iso(days: int) -> str:
    t = time.time() - (days * 86400)
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


def _ref(**overrides: object) -> CredentialRef:
    defaults: dict[str, object] = {
        "ref_id": "cred-1",
        "name": "openai-api-key",
        "credential_type": "api_key",
        "location": "env",
        "location_detail": "OPENAI_API_KEY",
        "scope": "global",
        "rotation_days": 0,
        "last_rotated": None,
        "expires_at": None,
        "is_valid": True,
        "sensitivity": "high",
    }
    defaults.update(overrides)
    return CredentialRef(**defaults)  # type: ignore[arg-type]


# ── Tests ──────────────────────────────────────────────────────────────────────


class TestRegisterAndLocate:
    def test_register_and_locate_finds_credential(self) -> None:
        locator = CredentialLocator()
        locator.register(_ref(ref_id="k1", name="openai-key"))
        found = locator.locate("k1")
        assert found is not None
        assert found.name == "openai-key"
        assert found.credential_type == "api_key"

    def test_locate_by_name_field(self) -> None:
        locator = CredentialLocator()
        locator.register(_ref(ref_id="k2", name="gh-token"))
        found = locator.locate("gh-token")
        assert found is not None
        assert found.ref_id == "k2"

    def test_locate_returns_none_for_missing(self) -> None:
        locator = CredentialLocator()
        assert locator.locate("nonexistent") is None

    def test_register_overwrites_existing(self) -> None:
        locator = CredentialLocator()
        locator.register(_ref(ref_id="k1", name="first"))
        locator.register(_ref(ref_id="k1", name="second"))
        assert locator.locate("k1").name == "second"


class TestListExpiring:
    def test_list_expiring_returns_expiring_creds(self) -> None:
        locator = CredentialLocator()
        locator.register(_ref(ref_id="e1", expires_at=_future_iso(10)))  # expiring soon
        locator.register(_ref(ref_id="e2", expires_at=_future_iso(60)))  # not soon
        locator.register(_ref(ref_id="e3"))  # no expiry
        expiring = locator.list_expiring(within_days=30)
        ids = [r.ref_id for r in expiring]
        assert "e1" in ids
        assert "e2" not in ids
        assert "e3" not in ids

    def test_list_expiring_excludes_invalid(self) -> None:
        locator = CredentialLocator()
        locator.register(_ref(ref_id="e1", expires_at=_future_iso(5), is_valid=False))
        expiring = locator.list_expiring(within_days=30)
        assert len(expiring) == 0

    def test_list_expiring_already_expired(self) -> None:
        locator = CredentialLocator()
        locator.register(_ref(ref_id="e1", expires_at=_past_iso(10)))
        expiring = locator.list_expiring(within_days=30)
        assert len(expiring) == 1  # past expiry is still "expiring within 30 days"


class TestListDueRotation:
    def test_list_due_rotation_returns_overdue(self) -> None:
        locator = CredentialLocator()
        locator.register(_ref(ref_id="r1", rotation_days=30, last_rotated=_past_iso(40)))
        due = locator.list_due_rotation()
        assert len(due) == 1
        assert due[0].ref_id == "r1"

    def test_list_due_rotation_excludes_recently_rotated(self) -> None:
        locator = CredentialLocator()
        locator.register(_ref(ref_id="r2", rotation_days=30, last_rotated=_past_iso(5)))
        due = locator.list_due_rotation()
        ids = [r.ref_id for r in due]
        assert "r2" not in ids

    def test_list_due_rotation_never_rotated_included(self) -> None:
        locator = CredentialLocator()
        locator.register(_ref(ref_id="r3", rotation_days=30, last_rotated=None))
        due = locator.list_due_rotation()
        assert len(due) == 1
        assert due[0].ref_id == "r3"

    def test_list_due_rotation_no_rotation_policy(self) -> None:
        locator = CredentialLocator()
        locator.register(_ref(ref_id="r4", rotation_days=0))  # no rotation
        due = locator.list_due_rotation()
        assert len(due) == 0


class TestMarkRotated:
    def test_mark_rotated_updates_timestamp(self) -> None:
        locator = CredentialLocator()
        locator.register(_ref(ref_id="mk1"))
        old_rotated = locator.credentials["mk1"].last_rotated
        assert old_rotated is None

        locator.mark_rotated("mk1")
        new_rotated = locator.credentials["mk1"].last_rotated
        assert new_rotated is not None
        assert new_rotated != old_rotated

    def test_mark_rotated_unknown_no_error(self) -> None:
        locator = CredentialLocator()
        # Should not raise
        locator.mark_rotated("ghost")


class TestAuditReport:
    def test_audit_report_generates_markdown(self) -> None:
        locator = CredentialLocator()
        locator.register(_ref(ref_id="a1"))
        locator.register(_ref(ref_id="a2", expires_at=_future_iso(10)))
        locator.register(_ref(ref_id="a3", is_valid=False))
        report = locator.audit_report()
        assert "# Credential Locator Audit Report" in report
        assert "a1" in report
        assert "a2" in report
        assert "a3" in report
        assert "Expiring" in report
        assert "Invalid" in report

    def test_audit_report_includes_invalid_credentials(self) -> None:
        locator = CredentialLocator()
        locator.register(_ref(ref_id="bad", is_valid=False, sensitivity="critical"))
        report = locator.audit_report()
        assert "bad" in report
        assert "CRITICAL" in report.upper() or "critical" in report.lower()


class TestLifecycleChain:
    def test_lifecycle_chain_shows_full_chain(self) -> None:
        locator = CredentialLocator()
        locator.register(_ref(ref_id="lc-active"))
        locator.register(_ref(ref_id="lc-expiring", expires_at=_future_iso(5)))
        locator.register(_ref(ref_id="lc-retired", is_valid=False))
        chain = locator.lifecycle_chain()
        assert len(chain) == 3
        stages = {c["ref_id"]: c["stage"] for c in chain}
        assert stages["lc-active"] == "active"
        assert stages["lc-expiring"] == "expiring"
        assert stages["lc-retired"] == "retired"

    def test_lifecycle_chain_includes_all_fields(self) -> None:
        locator = CredentialLocator()
        locator.register(_ref(ref_id="lc1"))
        chain = locator.lifecycle_chain()
        entry = chain[0]
        for key in ("ref_id", "name", "stage", "is_valid", "sensitivity", "expires_at", "last_rotated"):
            assert key in entry, f"Missing key: {key}"


class TestSensitivitySorting:
    def test_sensitivity_levels_stored_correctly(self) -> None:
        locator = CredentialLocator()
        levels = ["low", "medium", "high", "critical"]
        for i, level in enumerate(levels):
            locator.register(_ref(ref_id=f"s{i}", sensitivity=level))
        for i, level in enumerate(levels):
            assert locator.credentials[f"s{i}"].sensitivity == level

    def test_audit_report_includes_sensitivity_labels(self) -> None:
        locator = CredentialLocator()
        locator.register(_ref(ref_id="s1", sensitivity="critical"))
        report = locator.audit_report()
        # The report should mention the sensitivity
        assert "CRITICAL" in report.upper()
