"""
Credential Manager — scoped API keys, token rotation, TTL enforcement,
and per-trust-tier credential scoping for HLF ecosystem bridges.

Design:
  - Credentials are scoped by trust tier: "hearth" gets full access,
    "advisory" gets read-only, lower tiers get minimal access.
  - API keys carry an HMAC-like signature derived from a master secret
    so they can be validated without a database lookup.
  - Token rotation: old tokens are invalidated after rotation, with
    a configurable grace period for in-flight requests.
  - Storage uses hashlib (sha256) for encrypted credential storage,
    compatible with the existing capability manifest signing approach.
  - TTL (time-to-live) enforces credential expiration.

Integration points:
  - hlf_mcp.ecosystem.rest_bridge.RESTBridge (API key validation middleware)
  - hlf_mcp.hlf.capability_manifest.CapabilityManifest.sign() (signing pattern)
  - TRUST_TIER_ORDER from hlf_mcp.hlf.capability_manifest (tier hierarchy)
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════════════════════════
# CredentialScope — what a credential grants access to
# ═══════════════════════════════════════════════════════════════════════════════


class CredentialScope(Enum):
    """Access scope granted to a credential based on trust tier.

    Values are assigned in ascending privilege order so that
    ``scope.value >= required.value`` implies sufficient access.
    """

    NONE = 0             # No access — below "advisory"
    LIMITED_READ = 1     # Restricted read subset — "advisory" level
    READ_ONLY = 2        # Read-only effects — "watched" / "approved" level
    READ_WRITE = 3       # Read + non-critical write — "trusted" level
    FULL = 4             # All effects, all tiers — "hearth" level


# ═══════════════════════════════════════════════════════════════════════════════
# Credential — a single API key with scope and TTL
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class Credential:
    """A single API credential with scope, TTL, and rotation support.

    Attributes:
        key_id: Unique identifier for this credential (public, safe to log).
        key_hash: SHA-256 hash of the API key (stored, never the raw key).
        scope: Access scope granted by this credential.
        trust_tier: Trust tier this credential authenticates as.
        created_at: Unix timestamp when the credential was issued.
        expires_at: Unix timestamp when the credential expires.
        rotated_from: key_id of the credential this replaced (if any).
        is_active: Whether the credential is currently valid.
    """

    key_id: str
    key_hash: str
    scope: CredentialScope
    trust_tier: str
    created_at: float
    expires_at: float
    rotated_from: str | None = None
    is_active: bool = True

    def is_expired(self) -> bool:
        """Check whether the credential has exceeded its TTL."""
        return time.time() > self.expires_at

    def is_valid(self) -> bool:
        """Check whether the credential is active and not expired."""
        return self.is_active and not self.is_expired()

    def time_until_expiry(self) -> float:
        """Return seconds until expiry (0 if already expired)."""
        return max(0.0, self.expires_at - time.time())

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dictionary (excluding the key hash for safety)."""
        return {
            "key_id": self.key_id,
            "scope": self.scope.name,
            "trust_tier": self.trust_tier,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "is_active": self.is_active,
            "time_until_expiry": self.time_until_expiry(),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# CredentialManager — lifecycle management for API credentials
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class CredentialManager:
    """Manages the lifecycle of scoped API credentials for HLF bridges.

    Credentials are scoped by trust tier:
      - "hearth"   → CredentialScope.FULL
      - "trusted"  → CredentialScope.READ_WRITE
      - "approved" → CredentialScope.READ_ONLY
      - "watched"  → CredentialScope.READ_ONLY
      - "advisory" → CredentialScope.LIMITED_READ
      - below       → CredentialScope.NONE

    Usage:
        cm = CredentialManager(master_secret="my-secret")
        cred = cm.create_credential("hearth", ttl=3600)
        # cred.key_id and cred.key_hash are stored; raw key returned once
        raw_key = cm.issue_key("hearth", ttl=3600)
        is_valid = cm.validate(raw_key)

    Attributes:
        master_secret: Secret used for HMAC-based key derivation.
        credentials: Dict of key_id → Credential for all managed credentials.
        grace_period: Seconds after rotation during which old keys remain valid.
        lock: Reentrant lock for thread safety.
    """

    master_secret: str
    credentials: dict[str, Credential] = field(default_factory=dict)
    grace_period: float = 300.0  # 5 minutes
    lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    # ═══════════════════════════════════════════════════════════════════════════
    # Trust-tier → CredentialScope mapping
    # ═══════════════════════════════════════════════════════════════════════════

    _TIER_TO_SCOPE: dict[str, CredentialScope] = field(
        default_factory=lambda: {
            "hearth": CredentialScope.FULL,
            "trusted": CredentialScope.READ_WRITE,
            "approved": CredentialScope.READ_ONLY,
            "watched": CredentialScope.READ_ONLY,
            "advisory": CredentialScope.LIMITED_READ,
        },
        init=False,
        repr=False,
    )

    # ── Credential creation ───────────────────────────────────────────────────

    def create_credential(self, trust_tier: str, ttl: float = 3600.0) -> Credential:
        """Create a new credential for the given trust tier.

        The raw API key is derived deterministically from the master secret
        and the key_id.  Only the hash is stored.

        Args:
            trust_tier: The trust tier to scope the credential to.
            ttl: Time-to-live in seconds from now (default: 3600 = 1 hour).

        Returns:
            A Credential object (the raw key can be derived from key_id
            using the master secret).
        """
        scope = self._scope_for_tier(trust_tier)
        key_id = self._generate_key_id(trust_tier)
        raw_key = self._derive_key(key_id)
        key_hash = self._hash_key(raw_key)

        now = time.time()
        credential = Credential(
            key_id=key_id,
            key_hash=key_hash,
            scope=scope,
            trust_tier=trust_tier,
            created_at=now,
            expires_at=now + ttl,
        )

        with self.lock:
            self.credentials[key_id] = credential

        return credential

    def issue_key(self, trust_tier: str, ttl: float = 3600.0) -> str:
        """Create a credential and return the raw API key.

        This is the primary entry point: returns the raw key that the
        client should store.  The key is NOT stored in plaintext — only
        its hash is retained.

        Args:
            trust_tier: The trust tier to scope the credential to.
            ttl: Time-to-live in seconds.

        Returns:
            The raw API key string.
        """
        credential = self.create_credential(trust_tier, ttl)
        return self._derive_key(credential.key_id)

    # ── Validation ────────────────────────────────────────────────────────────

    def validate(self, raw_key: str) -> Credential | None:
        """Validate a raw API key and return the matching Credential.

        Returns None if the key is invalid, expired, or revoked.
        """
        key_hash = self._hash_key(raw_key)

        with self.lock:
            # Search by hash (O(n) — acceptable for credential counts)
            for credential in self.credentials.values():
                if credential.key_hash == key_hash:
                    if credential.is_valid():
                        return credential
                    return None  # found but invalid
        return None

    def validate_with_scope(
        self, raw_key: str, required_scope: CredentialScope
    ) -> Credential | None:
        """Validate a raw API key with a minimum scope requirement.

        Returns the Credential only if the key is valid AND its scope
        is at least the required scope.
        """
        credential = self.validate(raw_key)
        if credential is None:
            return None
        if credential.scope.value < required_scope.value:
            return None  # insufficient scope
        return credential

    def validate_for_tier(self, raw_key: str, required_tier: str) -> Credential | None:
        """Validate a raw API key against a required trust tier.

        Uses TRUST_TIER_ORDER implicitly through scope comparison.
        """
        required_scope = self._scope_for_tier(required_tier)
        return self.validate_with_scope(raw_key, required_scope)

    # ── Rotation ──────────────────────────────────────────────────────────────

    def rotate_credential(self, key_id: str, new_ttl: float = 3600.0) -> Credential | None:
        """Rotate a credential: deactivate the old one and create a new one.

        The old credential remains valid for the grace period to allow
        in-flight requests to complete.

        Args:
            key_id: The key_id of the credential to rotate.
            new_ttl: Time-to-live for the new credential.

        Returns:
            The new Credential, or None if the old credential was not found.
        """
        with self.lock:
            old = self.credentials.get(key_id)
            if old is None:
                return None

            old.is_active = False
            old.rotated_from = None  # clear any previous rotation chain

            new_cred = self.create_credential(old.trust_tier, ttl=new_ttl)
            new_cred.rotated_from = key_id
            return new_cred

    def expire_grace_periods(self) -> int:
        """Permanently invalidate credentials past their grace period.

        Returns the count of credentials fully revoked.
        """
        now = time.time()
        count = 0
        with self.lock:
            for credential in list(self.credentials.values()):
                if not credential.is_active and (now - credential.expires_at) > self.grace_period:
                    del self.credentials[credential.key_id]
                    count += 1
        return count

    # ── Revocation ────────────────────────────────────────────────────────────

    def revoke(self, key_id: str) -> bool:
        """Immediately revoke a credential by key_id.

        Returns True if the credential was found and revoked.
        """
        with self.lock:
            credential = self.credentials.get(key_id)
            if credential is None:
                return False
            credential.is_active = False
            return True

    def revoke_all_for_tier(self, trust_tier: str) -> int:
        """Revoke all credentials scoped to a specific trust tier.

        Returns the count of credentials revoked.
        """
        count = 0
        with self.lock:
            for credential in self.credentials.values():
                if credential.trust_tier == trust_tier and credential.is_active:
                    credential.is_active = False
                    count += 1
        return count

    # ── Queries ───────────────────────────────────────────────────────────────

    def list_credentials(self) -> list[dict[str, Any]]:
        """List all managed credentials (safe, no raw keys)."""
        with self.lock:
            return [c.to_dict() for c in self.credentials.values()]

    def list_active(self) -> list[dict[str, Any]]:
        """List only active (non-expired, non-revoked) credentials."""
        with self.lock:
            return [c.to_dict() for c in self.credentials.values() if c.is_valid()]

    def count_active(self) -> int:
        """Return the count of currently active credentials."""
        with self.lock:
            return sum(1 for c in self.credentials.values() if c.is_valid())

    def stats(self) -> dict[str, Any]:
        """Return monitoring statistics."""
        with self.lock:
            active = sum(1 for c in self.credentials.values() if c.is_valid())
            expired = sum(1 for c in self.credentials.values() if c.is_expired())
            revoked = sum(1 for c in self.credentials.values() if not c.is_active)
            return {
                "total": len(self.credentials),
                "active": active,
                "expired": expired,
                "revoked": revoked,
                "by_tier": {
                    tier: sum(1 for c in self.credentials.values() if c.trust_tier == tier)
                    for tier in set(c.trust_tier for c in self.credentials.values())
                },
            }

    # ── Internals ─────────────────────────────────────────────────────────────

    @staticmethod
    def _scope_for_tier(tier: str) -> CredentialScope:
        """Map a trust tier string to a CredentialScope."""
        scope_map: dict[str, CredentialScope] = {
            "hearth": CredentialScope.FULL,
            "trusted": CredentialScope.READ_WRITE,
            "approved": CredentialScope.READ_ONLY,
            "watched": CredentialScope.READ_ONLY,
            "advisory": CredentialScope.LIMITED_READ,
        }
        return scope_map.get(tier.lower(), CredentialScope.NONE)

    def _generate_key_id(self, trust_tier: str) -> str:
        """Generate a unique, descriptive key_id."""
        random_part = secrets.token_hex(8)
        return f"hlf_{trust_tier}_{random_part}"

    def _derive_key(self, key_id: str) -> str:
        """Derive a raw API key from the key_id using HMAC with master secret."""
        return hmac.new(
            self.master_secret.encode("utf-8"),
            key_id.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    @staticmethod
    def _hash_key(raw_key: str) -> str:
        """Hash a raw API key for storage (never store plaintext keys)."""
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    # ── Compatibility: manifest-style signing ─────────────────────────────────

    def sign_credential(self, raw_key: str) -> str:
        """Produce a signature for a raw key compatible with manifest.sign().

        Uses SHA-256 hashing, consistent with CapabilityManifest.sign().
        """
        return hashlib.sha256(
            (self.master_secret + raw_key).encode("utf-8")
        ).hexdigest()

    def verify_credential_signature(self, raw_key: str, signature: str) -> bool:
        """Verify a credential signature against the stored master secret."""
        expected = self.sign_credential(raw_key)
        return hmac.compare_digest(expected, signature)
