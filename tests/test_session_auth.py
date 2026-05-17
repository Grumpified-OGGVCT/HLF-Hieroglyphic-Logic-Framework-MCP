"""
Test plan for HLF VM session delegation authentication.

These are structured stubs documenting the required test cases.
Full implementations should be added as the session_auth module matures.

Run with:  pytest tests/test_session_auth.py -v
"""

from __future__ import annotations

import time

import pytest

from hlf_mcp.hlf.session_auth import (
    clear_revocations,
    create_session,
    delegate_session,
    is_revoked,
    revoke_session,
    validate_session,
)


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clean_revocations():
    """Ensure revocation set is empty before each test."""
    clear_revocations()


# ── Test 1: Valid session token allows authorized effects ──────────────


def test_valid_token_allows_authorized_effects():
    """
    A token created with effects ["write_fs", "read_fs"] should validate
    successfully and report those exact effects.
    """
    token = create_session(
        tier="forge",
        effects=["write_fs", "read_fs"],
        expiry_seconds=3600,
    )
    auth = validate_session(token)

    assert auth.valid is True
    assert auth.delegated_tier == "forge"
    assert "write_fs" in auth.delegated_effects
    assert "read_fs" in auth.delegated_effects
    assert auth.reason == ""
    # Session ID and JTI should be non-empty strings
    assert auth.session_id
    assert auth.jti


# ── Test 2: Expired token is rejected ─────────────────────────────────


def test_expired_token_is_rejected():
    """
    A token with expiry_seconds=0 should be immediately invalid.
    """
    token = create_session(
        tier="hearth",
        effects=["memory_store"],
        expiry_seconds=0,
    )
    # Small sleep to guarantee we are past the expiry boundary
    time.sleep(0.1)
    auth = validate_session(token)

    assert auth.valid is False
    assert "expired" in auth.reason.lower()


# ── Test 3: Revoked session is rejected ───────────────────────────────


def test_revoked_session_is_rejected():
    """
    After revoking a session ID, validate_session() must return invalid
    even if the token is otherwise well-formed and unexpired.
    """
    token = create_session(
        tier="sovereign",
        effects=["*"],
        expiry_seconds=3600,
    )
    # First validation succeeds
    auth1 = validate_session(token)
    assert auth1.valid is True

    # Revoke the session
    revoke_session(auth1.session_id)

    # Second validation fails
    auth2 = validate_session(token)
    assert auth2.valid is False
    assert "revoked" in auth2.reason.lower()
    assert is_revoked(auth1.session_id) is True


# ── Test 4: Child session inherits parent tier ─────────────────────────


def test_child_session_inherits_parent_tier():
    """
    A child token delegated from a 'forge' parent should report
    parent_tier='forge' and its own delegated_tier as specified.
    """
    parent_token = create_session(
        tier="forge",
        effects=["write_fs", "read_fs", "network"],
        expiry_seconds=3600,
    )
    child_token = delegate_session(
        parent_token=parent_token,
        child_tier="hearth",
        child_effects=["write_fs"],
    )
    child_auth = validate_session(child_token)

    assert child_auth.valid is True
    assert child_auth.parent_tier == "forge"
    assert child_auth.delegated_tier == "hearth"
    assert child_auth.parent_session_id == validate_session(parent_token).session_id


# ── Test 5: Child session cannot escalate beyond delegated effects ────


def test_child_cannot_escalate_effects():
    """
    Attempting to delegate effects not present in the parent token must
    raise PermissionError.
    """
    parent_token = create_session(
        tier="forge",
        effects=["write_fs", "read_fs"],  # NO network
        expiry_seconds=3600,
    )
    with pytest.raises(PermissionError) as exc_info:
        delegate_session(
            parent_token=parent_token,
            child_tier="hearth",
            child_effects=["write_fs", "network"],  # network not allowed
        )
    assert "network" in str(exc_info.value)


def test_child_cannot_escalate_tier():
    """
    Attempting to delegate a tier higher than the parent tier must
    raise PermissionError.
    """
    parent_token = create_session(
        tier="hearth",
        effects=["*"],
        expiry_seconds=3600,
    )
    with pytest.raises(PermissionError) as exc_info:
        delegate_session(
            parent_token=parent_token,
            child_tier="sovereign",  # cannot escalate from hearth
            child_effects=["write_fs"],
        )
    assert "sovereign" in str(exc_info.value)


# ── Test 6: Wildcard parent allows any child effects ──────────────────


def test_wildcard_parent_allows_any_child_effects():
    """
    A parent token with effects=["*"] should permit delegation of any
    child effect subset without raising PermissionError.
    """
    parent_token = create_session(
        tier="sovereign",
        effects=["*"],
        expiry_seconds=3600,
    )
    child_token = delegate_session(
        parent_token=parent_token,
        child_tier="forge",
        child_effects=["crypto", "network", "spawn_agent", "write_fs"],
    )
    child_auth = validate_session(child_token)
    assert child_auth.valid is True
    assert set(child_auth.delegated_effects) == {"crypto", "network", "spawn_agent", "write_fs"}


# ── Test 7: Malformed token is rejected ───────────────────────────────


def test_malformed_token_rejected():
    """
    Strings that do not match the header.payload.signature format must
    be rejected with a clear reason.
    """
    auth = validate_session("not-a-token")
    assert auth.valid is False
    assert "malformed" in auth.reason.lower()


# ── Test 8: Tampered payload is rejected ─────────────────────────────


def test_tampered_payload_rejected():
    """
    Modifying the payload segment of a token must cause signature
    verification to fail.
    """
    token = create_session(
        tier="hearth",
        effects=["read_fs"],
        expiry_seconds=3600,
    )
    parts = token.split(".")
    # Corrupt the payload (base64url tamper)
    parts[1] = parts[1][:-4] + "XXXX"
    tampered = ".".join(parts)

    auth = validate_session(tampered)
    assert auth.valid is False
    assert "signature" in auth.reason.lower()


# ── Test 9: Revocation idempotency ────────────────────────────────────


def test_revoke_idempotent():
    """
    revoke_session() should return False when the session is already
    revoked, and True on the first call.
    """
    token = create_session(tier="hearth", effects=[], expiry_seconds=3600)
    sid = validate_session(token).session_id
    assert revoke_session(sid) is True
    assert revoke_session(sid) is False


# ── Test 10: clear_revocations resets state ───────────────────────────


def test_clear_revocations():
    """
    After clear_revocations(), a previously-revoked token should validate
    again (assuming it has not expired).
    """
    token = create_session(tier="hearth", effects=[], expiry_seconds=3600)
    sid = validate_session(token).session_id
    revoke_session(sid)
    assert validate_session(token).valid is False

    clear_revocations()
    assert validate_session(token).valid is True
