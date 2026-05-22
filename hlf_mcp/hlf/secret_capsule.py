"""
HLF Secret Capsule — AES-256-GCM encrypted secrets with auto-redaction.

Enterprise hardening item #5: Secret Management.

Secrets are declared via the ∇ [SECRET] glyph and never appear in plaintext
in logs, memory dumps, or Merkle-chain metadata. Only the SHA-256 of the
ciphertext is stored in the audit trail.

Usage:
    from hlf_mcp.hlf.secret_capsule import SecretCapsule, encrypt_secret, decrypt_secret

    capsule = SecretCapsule()
    capsule.add("db_password", "super-secret-value")
    capsule.add("api_key", "sk-1234567890")

    # Secrets are encrypted at rest and auto-redacted from __repr__/__str__
    print(capsule)  # SecretCapsule(2 secrets, hash=sha256:abc123...)

    # Decrypt when needed for actual use
    db_pass = capsule.decrypt("db_password")  # "super-secret-value"

    # Glyph parsing
    secrets = SecretCapsule.from_glyphs('∇ [SECRET] name="db_password"')
"""

from __future__ import annotations

import base64
import hashlib
import os
import re
import secrets as _secrets
from dataclasses import dataclass, field
from typing import Any


# ── Cryptography imports with graceful fallback ──
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    _CRYPTO_AVAILABLE = True
except ImportError:
    _CRYPTO_AVAILABLE = False


# ── Constants ──
_SALT_LENGTH = 32          # bytes
_NONCE_LENGTH = 12         # AES-GCM standard nonce
_KEY_LENGTH = 32           # AES-256 key
_PBKDF2_ITERATIONS = 600_000
_MASTER_KEY_ENV = "HLF_MASTER_KEY"


class SecretCapsuleError(Exception):
    """Secret capsule operation failure."""
    pass


class SecretNotFoundError(SecretCapsuleError):
    """Requested secret name not found in capsule."""
    pass


def _derive_key(master_key: str, salt: bytes) -> bytes:
    """Derive an AES-256 key from the master key using PBKDF2."""
    if not _CRYPTO_AVAILABLE:
        raise SecretCapsuleError(
            "cryptography library is required for secret management. "
            "Install with: pip install cryptography"
        )
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=_KEY_LENGTH,
        salt=salt,
        iterations=_PBKDF2_ITERATIONS,
    )
    return kdf.derive(master_key.encode("utf-8"))


def encrypt_secret(plaintext: str, master_key: str | None = None) -> dict[str, Any]:
    """Encrypt a secret value with AES-256-GCM.

    Args:
        plaintext: The secret value to encrypt.
        master_key: Optional master key (defaults to HLF_MASTER_KEY env var).

    Returns:
        dict with keys: ciphertext (base64), nonce (base64), salt (base64).
    """
    if not _CRYPTO_AVAILABLE:
        raise SecretCapsuleError("cryptography library is required for secret management")

    if master_key is None:
        master_key = os.environ.get(_MASTER_KEY_ENV, "")
    if not master_key:
        raise SecretCapsuleError(
            f"HLF_MASTER_KEY environment variable is required for secret encryption"
        )

    salt = _secrets.token_bytes(_SALT_LENGTH)
    nonce = _secrets.token_bytes(_NONCE_LENGTH)
    key = _derive_key(master_key, salt)

    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)

    return {
        "ciphertext_b64": base64.b64encode(ciphertext).decode("ascii"),
        "nonce_b64": base64.b64encode(nonce).decode("ascii"),
        "salt_b64": base64.b64encode(salt).decode("ascii"),
    }


def decrypt_secret(
    ciphertext_b64: str,
    nonce_b64: str,
    salt_b64: str,
    master_key: str | None = None,
) -> str:
    """Decrypt a secret value with AES-256-GCM.

    Args:
        ciphertext_b64: Base64-encoded ciphertext.
        nonce_b64: Base64-encoded nonce.
        salt_b64: Base64-encoded salt.
        master_key: Optional master key (defaults to HLF_MASTER_KEY env var).

    Returns:
        Decrypted plaintext string.
    """
    if not _CRYPTO_AVAILABLE:
        raise SecretCapsuleError("cryptography library is required for secret management")

    if master_key is None:
        master_key = os.environ.get(_MASTER_KEY_ENV, "")
    if not master_key:
        raise SecretCapsuleError(
            f"HLF_MASTER_KEY environment variable is required for secret decryption"
        )

    salt = base64.b64decode(salt_b64)
    nonce = base64.b64decode(nonce_b64)
    ciphertext = base64.b64decode(ciphertext_b64)

    key = _derive_key(master_key, salt)
    aesgcm = AESGCM(key)
    try:
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    except Exception as e:
        raise SecretCapsuleError(
            f"Decryption failed (likely wrong master key or tampered ciphertext): {e}"
        ) from e

    return plaintext.decode("utf-8")


def compute_secret_hash(ciphertext_b64: str) -> str:
    """Compute SHA-256 of ciphertext for Merkle chain storage.

    Only the ciphertext hash is stored in the audit trail — never the plaintext.
    """
    return hashlib.sha256(ciphertext_b64.encode()).hexdigest()


# ── Secret glyph parsing ──
# Grammar: ∇ [SECRET] name="x"  OR  ∇ [SECRET] name="x" value="y"
_SECRET_GLYPH_RE = re.compile(
    r'∇\s*\[SECRET\]\s+name="([^"]+)"(?:\s+value="([^"]*)")?',
    re.IGNORECASE,
)


def parse_secret_glyphs(text: str) -> list[dict[str, str]]:
    """Parse ∇ [SECRET] glyphs from text.

    Each match produces a dict with 'name' and optionally 'value'.
    """
    results: list[dict[str, str]] = []
    for match in _SECRET_GLYPH_RE.finditer(text):
        entry = {"name": match.group(1)}
        value = match.group(2)
        if value is not None:
            entry["value"] = value
        results.append(entry)
    return results


@dataclass
class SecretCapsule:
    """A collection of encrypted secrets with auto-redaction.

    Secrets are encrypted at rest using AES-256-GCM with a key derived from
    HLF_MASTER_KEY. The plaintext is never stored in memory longer than
    necessary, and __repr__/__str__ only show metadata.

    The capsule exposes SHA-256(ciphertext) for Merkle chain storage.
    """

    _secrets: dict[str, dict[str, str]] = field(default_factory=dict)
    master_key: str | None = field(default=None)

    def __post_init__(self):
        if self.master_key is None:
            self.master_key = os.environ.get(_MASTER_KEY_ENV, "")

    def add(self, name: str, value: str) -> str:
        """Add a secret to the capsule. Returns SHA-256 of ciphertext."""
        encrypted = encrypt_secret(value, self.master_key)
        self._secrets[name] = encrypted
        return compute_secret_hash(encrypted["ciphertext_b64"])

    def decrypt(self, name: str) -> str:
        """Decrypt a secret by name."""
        if name not in self._secrets:
            raise SecretNotFoundError(f"Secret '{name}' not found in capsule")
        entry = self._secrets[name]
        return decrypt_secret(
            entry["ciphertext_b64"],
            entry["nonce_b64"],
            entry["salt_b64"],
            self.master_key,
        )

    def get_hash(self, name: str) -> str:
        """Get SHA-256 of ciphertext for a secret (safe for audit trail)."""
        if name not in self._secrets:
            raise SecretNotFoundError(f"Secret '{name}' not found in capsule")
        return compute_secret_hash(self._secrets[name]["ciphertext_b64"])

    @property
    def names(self) -> list[str]:
        return sorted(self._secrets.keys())

    @property
    def count(self) -> int:
        return len(self._secrets)

    @property
    def merkle_metadata(self) -> dict[str, str]:
        """Safe-for-audit metadata: name → SHA-256(ciphertext)."""
        return {name: compute_secret_hash(e["ciphertext_b64"])
                for name, e in self._secrets.items()}

    def __repr__(self) -> str:
        return f"SecretCapsule({self.count} secrets, keys={self.names})"

    def __str__(self) -> str:
        return self.__repr__()

    def __contains__(self, name: str) -> bool:
        return name in self._secrets

    @classmethod
    def from_glyphs(cls, text: str, master_key: str | None = None) -> SecretCapsule:
        """Create a SecretCapsule from ∇ [SECRET] glyphs in text.

        Each ∇ [SECRET] name="x" creates a secret entry. If value="y" is
        present, it uses the explicit value; otherwise the value is read
        from the environment variable matching the name.

        Args:
            text: Text containing ∇ [SECRET] glyphs.
            master_key: Optional master key override.

        Returns:
            SecretCapsule with parsed and encrypted secrets.
        """
        capsule = cls(master_key=master_key)
        entries = parse_secret_glyphs(text)

        for entry in entries:
            name = entry["name"]
            if "value" in entry and entry["value"]:
                value = entry["value"]
            else:
                value = os.environ.get(name, "")
                if not value:
                    raise SecretCapsuleError(
                        f"Secret '{name}' has no explicit value and no matching "
                        f"environment variable"
                    )
            capsule.add(name, value)

        return capsule

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict (ciphertext only, no plaintext)."""
        return {
            "secrets": {
                name: {
                    "ciphertext_b64": entry["ciphertext_b64"],
                    "nonce_b64": entry["nonce_b64"],
                    "salt_b64": entry["salt_b64"],
                    "hash": compute_secret_hash(entry["ciphertext_b64"]),
                }
                for name, entry in self._secrets.items()
            },
            "secret_names": self.names,
            "secret_count": self.count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], master_key: str | None = None) -> SecretCapsule:
        """Restore from serialized dict."""
        capsule = cls(master_key=master_key)
        for name, entry in data.get("secrets", {}).items():
            capsule._secrets[name] = {
                "ciphertext_b64": entry["ciphertext_b64"],
                "nonce_b64": entry["nonce_b64"],
                "salt_b64": entry["salt_b64"],
            }
        return capsule
