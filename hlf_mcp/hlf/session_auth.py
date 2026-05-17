"""
HLF VM Session Authentication — lightweight signed-session tokens.

Provides create / validate / delegate / revoke operations for VM sessions
using HMAC-SHA256 (no full JWT/JOSE dependency).

A session token is:
    base64url(header).base64url(payload).base64url(signature)

where header = {"alg": "HS256", "typ": "HLF-Session-v1"}
      payload = {"sid": <ulid>, "ptier": ..., "ctier": ..., "eff": [...],
                "iat": <unix>, "exp": <unix>, "pid": <sid|null>, "jti": <ulid>}
      signature = HMAC-SHA256(key, b64header + "." + b64payload)

Usage
-----
    from hlf_mcp.hlf.session_auth import create_session, validate_session

    token = create_session(tier="sovereign", effects=["*"], expiry_seconds=3600)
    auth = validate_session(token)
    if auth.valid:
        print(auth.session_id, auth.delegated_effects)
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any


# ── In-memory revocation set ──────────────────────────────────────────
_REVOKED_SESSIONS: set[str] = set()
_revoke_lock = threading.Lock()


# ── Secret loading ──────────────────────────────────────────────────────
def _get_secret() -> bytes:
    """Load the HMAC signing secret from environment."""
    raw = os.environ.get("HLF_SESSION_SECRET", "")
    if not raw:
        # Dev fallback — deterministic but NOT for production
        return b"hlf-dev-fallback-secret-do-not-use-in-prod"
    return raw.encode("utf-8")


def _b64url_encode(data: bytes) -> str:
    """URL-safe base64 without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    """URL-safe base64 decode, tolerant of missing padding."""
    pad = 4 - len(data) % 4
    if pad != 4:
        data += "=" * pad
    return base64.urlsafe_b64decode(data.encode("ascii"))


def _now() -> int:
    return int(time.time())


def _make_ulid() -> str:
    """Generate a ULID-like identifier using time + randomness."""
    # Fallback when python-ulid is not installed
    try:
        import ulid  # type: ignore[import-untyped]
        return str(ulid.new())
    except Exception:
        # 48-bit timestamp ms + 80-bit randomness, base32 encoded
        ts = int(time.time() * 1000)
        rnd = os.urandom(10)
        combined = ts.to_bytes(6, "big") + rnd
        return base64.b32encode(combined).decode("ascii").rstrip("=").lower()


# ── Data model ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SessionAuth:
    """Result of validating a session token."""

    valid: bool
    session_id: str = ""
    parent_session_id: str | None = None
    parent_tier: str = "hearth"
    delegated_tier: str = "hearth"
    delegated_effects: list[str] = field(default_factory=list)
    issued_at: int = 0
    expires_at: int = 0
    jti: str = ""
    reason: str = ""


# ── Core functions ────────────────────────────────────────────────────

def create_session(
    tier: str,
    effects: list[str],
    expiry_seconds: int = 3600,
    parent_session_id: str | None = None,
    parent_tier: str | None = None,
) -> str:
    """
    Create a new signed session token.

    Parameters
    ----------
    tier:       The tier this session is authorized for (hearth / forge / sovereign).
    effects:    List of permitted side-effects (e.g. ["write_fs", "network"]).
                Use ["*"] for wildcard (all effects).
    expiry_seconds: Token lifetime in seconds.
    parent_session_id: If delegating, the parent session ID; otherwise None.
    parent_tier: The tier of the parent session (defaults to ``tier`` if not provided).

    Returns
    -------
    A signed base64url token string.
    """
    now = _now()
    sid = _make_ulid()
    jti = _make_ulid()
    _parent_tier = parent_tier if parent_tier is not None else tier

    header = {"alg": "HS256", "typ": "HLF-Session-v1"}
    payload = {
        "sid": sid,
        "ptier": _parent_tier,
        "ctier": tier,
        "eff": list(effects),
        "iat": now,
        "exp": now + expiry_seconds,
        "pid": parent_session_id,
        "jti": jti,
    }

    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}"

    sig = hmac.new(_get_secret(), signing_input.encode("utf-8"), hashlib.sha256).digest()
    sig_b64 = _b64url_encode(sig)

    return f"{signing_input}.{sig_b64}"


def validate_session(token: str) -> SessionAuth:
    """
    Validate a session token.

    Returns a SessionAuth dataclass.  If ``valid`` is False, ``reason``
    explains why.
    """
    parts = token.split(".")
    if len(parts) != 3:
        return SessionAuth(valid=False, reason="malformed token: expected 3 parts")

    header_b64, payload_b64, sig_b64 = parts

    # 1. Verify signature
    signing_input = f"{header_b64}.{payload_b64}"
    expected_sig = hmac.new(
        _get_secret(), signing_input.encode("utf-8"), hashlib.sha256
    ).digest()
    try:
        actual_sig = _b64url_decode(sig_b64)
    except Exception:
        return SessionAuth(valid=False, reason="invalid base64 in signature")

    if not hmac.compare_digest(expected_sig, actual_sig):
        return SessionAuth(valid=False, reason="signature mismatch")

    # 2. Decode payload
    try:
        payload_bytes = _b64url_decode(payload_b64)
        payload: dict[str, Any] = json.loads(payload_bytes.decode("utf-8"))
    except Exception as exc:
        return SessionAuth(valid=False, reason=f"payload decode error: {exc}")

    # 3. Check revocation
    sid = str(payload.get("sid", ""))
    with _revoke_lock:
        if sid in _REVOKED_SESSIONS:
            return SessionAuth(valid=False, reason="session revoked")

    # 4. Check expiry
    now = _now()
    exp = int(payload.get("exp", 0))
    if now >= exp:
        return SessionAuth(valid=False, reason="token expired")

    return SessionAuth(
        valid=True,
        session_id=sid,
        parent_session_id=payload.get("pid"),
        parent_tier=str(payload.get("ptier", "hearth")),
        delegated_tier=str(payload.get("ctier", "hearth")),
        delegated_effects=list(payload.get("eff", [])),
        issued_at=int(payload.get("iat", 0)),
        expires_at=exp,
        jti=str(payload.get("jti", "")),
    )


def delegate_session(
    parent_token: str,
    child_tier: str,
    child_effects: list[str],
    expiry_seconds: int = 3600,
) -> str:
    """
    Create a child session token derived from a parent token.

    Enforcement rules
    -----------------
    * ``child_tier`` must be <= parent tier (hearth < forge < sovereign).
    * ``child_effects`` must be a subset of the parent's delegated effects
      (or parent has wildcard ``["*"]``).
    """
    parent = validate_session(parent_token)
    if not parent.valid:
        raise PermissionError(f"Cannot delegate from invalid parent: {parent.reason}")

    # Tier escalation guard
    _TIER_ORDER = {"hearth": 0, "forge": 1, "sovereign": 2}
    if _TIER_ORDER.get(child_tier, 0) > _TIER_ORDER.get(parent.delegated_tier, 0):
        raise PermissionError(
            f"Child tier '{child_tier}' exceeds parent tier '{parent.delegated_tier}'"
        )

    # Effect subset guard
    parent_effects = set(parent.delegated_effects)
    child_effects_set = set(child_effects)
    if "*" not in parent_effects and not child_effects_set.issubset(parent_effects):
        raise PermissionError(
            f"Child effects {child_effects_set - parent_effects} exceed parent delegation"
        )

    return create_session(
        tier=child_tier,
        effects=list(child_effects),
        expiry_seconds=expiry_seconds,
        parent_session_id=parent.session_id,
        parent_tier=parent.delegated_tier,
    )


def revoke_session(session_id: str) -> bool:
    """
    Revoke a session by ID.

    Returns True if the session was newly revoked, False if already revoked.
    """
    with _revoke_lock:
        if session_id in _REVOKED_SESSIONS:
            return False
        _REVOKED_SESSIONS.add(session_id)
        return True


def is_revoked(session_id: str) -> bool:
    """Check whether a session ID has been revoked."""
    with _revoke_lock:
        return session_id in _REVOKED_SESSIONS


def clear_revocations() -> None:
    """Clear the revocation set.  Useful in tests."""
    with _revoke_lock:
        _REVOKED_SESSIONS.clear()
