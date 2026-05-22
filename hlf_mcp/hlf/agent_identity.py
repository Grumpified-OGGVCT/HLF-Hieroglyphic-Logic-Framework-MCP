"""Agent identity module using Ed25519 keypairs.

Commit 15 of enterprise hardening gauntlet.
Provides cryptographically verifiable agent identities via Ed25519
signatures.  Complements the Bearer token auth in server_auth.py with
asymmetric key-based agent proof.

Architecture:
    ┌─────────────────────┐
    │   AgentIdentity     │
    │   (keypair holder)  │
    │                     │
    │  - generate()       │
    │  - sign(payload)    │
    │  - verify(proof)    │
    │  - agent_id         │
    └─────────┬───────────┘
              │
    ┌─────────▼───────────┐
    │   AgentProof        │
    │   (serializable)    │
    │                     │
    │  - agent_id         │
    │  - payload          │
    │  - signature_hex    │
    │  - timestamp        │
    │  - token (HMAC)     │
    └─────────────────────┘

Usage:
    # Generate a new identity
    identity = AgentIdentity.generate()

    # Sign a payload
    proof = identity.sign(b"HLF intent payload")

    # Verify from public key
    AgentIdentity.verify(identity.public_key_bytes(), proof)

    # Derive deterministic agent_id
    agent_id = identity.agent_id
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
from dataclasses import dataclass, field
from enum import Enum

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.exceptions import InvalidSignature


# ---------------------------------------------------------------------------
# Core identity types
# ---------------------------------------------------------------------------

class IdentityGenerationError(Exception):
    """Failed to generate or load an agent identity."""


class ProofVerificationError(Exception):
    """Signature verification failed — agent identity is not trusted."""


class AgentTier(Enum):
    """Agent capability tiers (same namespace as MCP tier gating)."""
    HEARTH = "hearth"
    FORGE = "forge"
    SOVEREIGN = "sovereign"


@dataclass(frozen=True)
class AgentProof:
    """A signed attestation from an agent identity.

    This is the serializable unit that flows over HTTP auth
    headers (Bearer token) or is embedded in capsule metadata.
    """
    agent_id: str
    payload: str
    signature_hex: str
    timestamp: int
    token: str  # HMAC(token_key, agent_id + payload + signature)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "payload": self.payload,
            "signature_hex": self.signature_hex,
            "timestamp": self.timestamp,
            "token": self.token,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentProof:
        return cls(
            agent_id=data["agent_id"],
            payload=data["payload"],
            signature_hex=data["signature_hex"],
            timestamp=data["timestamp"],
            token=data["token"],
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_json(cls, json_str: str) -> AgentProof:
        return cls.from_dict(json.loads(json_str))


# ---------------------------------------------------------------------------
# AgentIdentity
# ---------------------------------------------------------------------------

class AgentIdentity:
    """Holder for an Ed25519 keypair representing an agent identity.

    The agent_id is derived deterministically from the public key bytes:
        agent_id = "hlf-ag-" + sha256(pubkey_bytes).hexdigest()[:16]

    This allows any party with the public key to verify that an
    AgentProof was signed by the claimed agent.

    Thread-safe: all methods are pure or use local state only.
    """

    __slots__ = ("_private_key", "_public_key", "_agent_id", "_tier")

    def __init__(
        self,
        private_key: Ed25519PrivateKey,
        public_key: Ed25519PublicKey,
        tier: AgentTier = AgentTier.HEARTH,
    ) -> None:
        self._private_key = private_key
        self._public_key = public_key
        self._agent_id = _derive_agent_id(public_key)
        self._tier = tier

    # -- Factory methods --

    @classmethod
    def generate(cls, tier: AgentTier = AgentTier.HEARTH) -> AgentIdentity:
        """Generate a new Ed25519 keypair for a fresh agent identity."""
        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        return cls(private_key=private_key, public_key=public_key, tier=tier)

    @classmethod
    def from_private_bytes(cls, private_bytes: bytes, tier: AgentTier = AgentTier.HEARTH) -> AgentIdentity:
        """Load identity from raw 32-byte Ed25519 seed."""
        if len(private_bytes) != 32:
            raise IdentityGenerationError(f"Expected 32-byte seed, got {len(private_bytes)}")
        private_key = Ed25519PrivateKey.from_private_bytes(private_bytes)
        public_key = private_key.public_key()
        return cls(private_key=private_key, public_key=public_key, tier=tier)

    @classmethod
    def from_pem(cls, pem_data: bytes, tier: AgentTier = AgentTier.HEARTH) -> AgentIdentity:
        """Load identity from PEM-encoded private key."""
        private_key = Ed25519PrivateKey.from_private_bytes(
            _pem_load_private(pem_data)
        )
        public_key = private_key.public_key()
        return cls(private_key=private_key, public_key=public_key, tier=tier)

    @classmethod
    def from_public_bytes(cls, public_bytes: bytes, tier: AgentTier = AgentTier.HEARTH) -> AgentIdentity:
        """Create a public-only identity (cannot sign, can only verify)."""
        public_key = Ed25519PublicKey.from_public_bytes(public_bytes)
        return cls(private_key=None, public_key=public_key, tier=tier)

    # -- Properties --

    @property
    def agent_id(self) -> str:
        """Deterministic agent ID derived from the public key."""
        return self._agent_id

    @property
    def tier(self) -> AgentTier:
        return self._tier

    @property
    def has_private_key(self) -> bool:
        return self._private_key is not None

    # -- Serialization --

    def private_bytes(self) -> bytes:
        """Export private key as raw 32-byte seed."""
        if self._private_key is None:
            raise IdentityGenerationError("Public-only identity has no private key")
        return self._private_key.private_bytes_raw()

    def public_key_bytes(self) -> bytes:
        """Export public key as raw 32 bytes."""
        return self._public_key.public_bytes_raw()

    def private_pem(self) -> bytes:
        """Export private key as PEM."""
        if self._private_key is None:
            raise IdentityGenerationError("Public-only identity has no private key")
        return _pem_encode_private(self._private_key.private_bytes_raw())

    def public_pem(self) -> bytes:
        """Export public key as PEM."""
        return _pem_encode_public(self._public_key.public_bytes_raw())

    # -- Cryptographic operations --

    def sign(self, payload: bytes) -> AgentProof:
        """Sign a payload with this identity's private key.

        Returns an AgentProof containing the signature, agent_id,
        timestamp, and HMAC token for auth binding.
        """
        if self._private_key is None:
            raise IdentityGenerationError("Cannot sign: public-only identity")

        signature = self._private_key.sign(payload)
        signature_hex = signature.hex()
        timestamp = int(time.time())

        # Token key derived from public key bytes (available in both
        # sign and verify contexts).  Using public bytes avoids the
        # private-seed vs public-key mismatch.
        token_key = hashlib.sha256(
            self._public_key.public_bytes_raw() + b":hlf-token-key:"
        ).digest()
        token = _compute_token(token_key, self._agent_id, payload.hex(), signature_hex, timestamp)

        return AgentProof(
            agent_id=self._agent_id,
            payload=payload.hex(),
            signature_hex=signature_hex,
            timestamp=timestamp,
            token=token,
        )

    def sign_text(self, text: str) -> AgentProof:
        """Convenience: sign a UTF-8 string."""
        return self.sign(text.encode("utf-8"))

    @staticmethod
    def verify(public_key_bytes: bytes, proof: AgentProof, *, max_age: int | None = None) -> bool:
        """Verify an AgentProof against a raw public key.

        Args:
            public_key_bytes: Raw 32-byte Ed25519 public key.
            proof: The AgentProof to verify.
            max_age: If set, reject proofs older than this many seconds.

        Returns:
            True if the signature and HMAC token are valid.

        Raises:
            ProofVerificationError: On any verification failure.
        """
        public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)

        # Check agent_id consistency
        expected_agent_id = _derive_agent_id(public_key)
        if not hmac.compare_digest(proof.agent_id, expected_agent_id):
            raise ProofVerificationError(
                f"Agent ID mismatch: expected {expected_agent_id}, got {proof.agent_id}"
            )

        # Check age
        if max_age is not None:
            age = int(time.time()) - proof.timestamp
            if age > max_age:
                raise ProofVerificationError(f"Proof expired: {age}s old (max {max_age}s)")

        # Verify signature
        try:
            payload_bytes = bytes.fromhex(proof.payload)
            public_key.verify(bytes.fromhex(proof.signature_hex), payload_bytes)
        except (ValueError, InvalidSignature) as exc:
            raise ProofVerificationError(f"Signature verification failed: {exc}") from exc

        # Verify HMAC token (binds signature to this identity)
        token_key = hashlib.sha256(
            public_key_bytes + b":hlf-token-key:"
        ).digest()
        expected_token = _compute_token(
            token_key, proof.agent_id, proof.payload, proof.signature_hex, proof.timestamp
        )
        if not hmac.compare_digest(proof.token, expected_token):
            raise ProofVerificationError("HMAC token verification failed")

        return True

    # -- Comparison --

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, AgentIdentity):
            return NotImplemented
        return self._agent_id == other._agent_id

    def __hash__(self) -> int:
        return hash(self._agent_id)

    def __repr__(self) -> str:
        return f"AgentIdentity(agent_id={self._agent_id!r}, tier={self._tier.value})"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _derive_agent_id(public_key: Ed25519PublicKey) -> str:
    """Derive a deterministic agent ID from a public key."""
    digest = hashlib.sha256(public_key.public_bytes_raw()).hexdigest()[:16]
    return f"hlf-ag-{digest}"


def _compute_token(key: bytes, agent_id: str, payload_hex: str, signature_hex: str, timestamp: int) -> str:
    """Compute HMAC-SHA256 token binding identity to proof."""
    message = f"{agent_id}:{payload_hex}:{signature_hex}:{timestamp}".encode()
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def _pem_encode_private(private_bytes: bytes) -> bytes:
    """Encode raw Ed25519 private bytes as PEM."""
    encoded = _b64_encode(private_bytes)
    return f"-----BEGIN HLF AGENT PRIVATE KEY-----\n{encoded}\n-----END HLF AGENT PRIVATE KEY-----\n".encode()


def _pem_encode_public(public_bytes: bytes) -> bytes:
    """Encode raw Ed25519 public bytes as PEM."""
    encoded = _b64_encode(public_bytes)
    return f"-----BEGIN HLF AGENT PUBLIC KEY-----\n{encoded}\n-----END HLF AGENT PUBLIC KEY-----\n".encode()


def _pem_load_private(pem_data: bytes) -> bytes:
    """Load raw Ed25519 private bytes from PEM."""
    try:
        text = pem_data.decode("utf-8")
    except UnicodeDecodeError:
        raise IdentityGenerationError("PEM data is not valid UTF-8") from None

    if "-----BEGIN HLF AGENT PRIVATE KEY-----" not in text:
        raise IdentityGenerationError("Missing HLF AGENT PRIVATE KEY header in PEM")
    if "-----END HLF AGENT PRIVATE KEY-----" not in text:
        raise IdentityGenerationError("Missing HLF AGENT PRIVATE KEY footer in PEM")

    # Extract base64 body
    lines = text.strip().split("\n")
    body_lines = [
        line.strip()
        for line in lines
        if not line.startswith("-----")
    ]
    body = "".join(body_lines)
    return _b64_decode(body)


def _b64_encode(data: bytes) -> str:
    """Base64 encode without padding (raw format)."""
    import base64
    return base64.b64encode(data).decode("ascii")


def _b64_decode(data: str) -> bytes:
    """Base64 decode (with optional padding)."""
    import base64
    return base64.b64decode(data)


# ---------------------------------------------------------------------------
# Auth integration helpers
# ---------------------------------------------------------------------------

class AgentIdentityAuth:
    """Integration layer between AgentIdentity and server_auth.py.

    Provides functions for validating Bearer tokens that carry
    Ed25519 proofs, and for registering trusted agent public keys.
    """

    def __init__(self, allowed_agents: dict[str, bytes] | None = None) -> None:
        """Initialize with optional pre-registered agents.

        Args:
            allowed_agents: Dict mapping agent_id → public_key_bytes.
                           If None, starts empty (only explicit registration).
        """
        self._allowed_agents: dict[str, bytes] = dict(allowed_agents or {})

    def register_agent(self, agent_id: str, public_key_bytes: bytes) -> None:
        """Register a trusted agent's public key."""
        if len(public_key_bytes) != 32:
            raise IdentityGenerationError(f"Invalid public key length: {len(public_key_bytes)}")
        self._allowed_agents[agent_id] = public_key_bytes

    def unregister_agent(self, agent_id: str) -> None:
        """Remove a trusted agent."""
        self._allowed_agents.pop(agent_id, None)

    def is_registered(self, agent_id: str) -> bool:
        """Check if an agent is registered."""
        return agent_id in self._allowed_agents

    def verify_proof(self, proof: AgentProof, *, max_age: int | None = 300) -> AgentIdentity | None:
        """Verify an AgentProof against registered agents.

        Args:
            proof: The AgentProof to verify.
            max_age: Maximum proof age in seconds (default 5 minutes).

        Returns:
            A public-only AgentIdentity if verified, or None if the
            agent is not registered or verification fails.
        """
        pubkey = self._allowed_agents.get(proof.agent_id)
        if pubkey is None:
            return None

        try:
            AgentIdentity.verify(pubkey, proof, max_age=max_age)
        except ProofVerificationError:
            return None

        return AgentIdentity.from_public_bytes(pubkey)

    def authenticate_token(self, token_header: str, *, max_age: int | None = 300) -> AgentIdentity | None:
        """Authenticate an HTTP Bearer token as an Ed25519 agent proof.

        The token format is:
            Bearer hlf-ed25519:<base64-encoded-proof-json>

        Returns None for non-Ed25519 tokens (they may be static
        Bearer tokens handled by server_auth.py).
        """
        prefix = "Bearer hlf-ed25519:"
        if not token_header.startswith(prefix):
            return None

        try:
            import base64
            proof_json = base64.b64decode(token_header[len(prefix):]).decode("utf-8")
            proof = AgentProof.from_json(proof_json)
        except Exception:
            return None

        return self.verify_proof(proof, max_age=max_age)

    def generate_auth_header(self, identity: AgentIdentity, payload: str = "") -> str:
        """Generate an HTTP Authorization header value from a full identity.

        Args:
            identity: An AgentIdentity with private key.
            payload: Optional payload to bind to this auth attempt
                     (e.g., request path + method).

        Returns:
            An 'Bearer hlf-ed25519:<base64>' header value.
        """
        import base64
        proof = identity.sign_text(payload)
        proof_b64 = base64.b64encode(proof.to_json().encode()).decode("ascii")
        return f"Bearer hlf-ed25519:{proof_b64}"


__all__ = [
    "AgentIdentity",
    "AgentProof",
    "AgentTier",
    "AgentIdentityAuth",
    "IdentityGenerationError",
    "ProofVerificationError",
]
