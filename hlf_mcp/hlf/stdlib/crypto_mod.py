"""
HLF stdlib: crypto module — production-grade cryptography.

ENCRYPT/DECRYPT     : AES-256-GCM authenticated encryption (NIST SP 800-38D)
                      Key: 32 raw bytes or a 32-byte hex/base64 string.
                      Output format: base64(nonce[12] || ciphertext || tag[16])
                      The GCM tag is authenticated on decrypt; tampering raises ValueError.

SIGN/SIGN_VERIFY    : HMAC-SHA256 message authentication code (RFC 2104).
                      Keys are treated as raw byte material after UTF-8 encoding.
                      Comparison uses hmac.compare_digest for constant-time safety.

HASH/HASH_VERIFY    : Standard hashlib digest supporting sha256, sha512, sha3_256,
                      sha3_512, blake2b, blake2s.

KEY_DERIVE          : PBKDF2-HMAC-SHA256 key derivation (NIST SP 800-132).
                      Returns 32-byte key as hex. Salt is hex-encoded for portability.

KEY_GENERATE        : Generate a cryptographically random 32-byte AES key (hex).

MERKLE_ROOT         : Compute the Merkle root of a list of string values using SHA-256
                      pairwise hashing (same algorithm used by the ALIGN Ledger).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets

# ── AES-256-GCM ───────────────────────────────────────────────────────────────
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _coerce_key(key: str | bytes) -> bytes:
    """
    Accept a 32-byte raw key, a 64-char hex key, or a base64 key.
    All are normalised to exactly 32 raw bytes for AES-256.
    Raises ValueError if the key cannot be normalised.
    """
    if isinstance(key, bytes):
        raw = key
    else:
        k = key.strip()
        # Try hex
        if len(k) == 64 and all(c in "0123456789abcdefABCDEF" for c in k):
            raw = bytes.fromhex(k)
        else:
            # Try base64
            try:
                raw = base64.b64decode(k)
            except Exception:
                raw = k.encode("utf-8")
    if len(raw) == 32:
        return raw
    # Derive exactly 32 bytes via SHA-256 so any passphrase works
    return hashlib.sha256(raw).digest()


def ENCRYPT(data: str, key: str) -> str:
    """
    Encrypt *data* using AES-256-GCM.

    A fresh 96-bit (12-byte) nonce is generated per call via os.urandom.
    Output is Base64-encoded: nonce[12] || ciphertext || GCM-tag[16].

    :param data: Plaintext string (UTF-8 encoded before encryption).
    :param key:  32-byte raw key, 64-char hex key, base64 key, or passphrase
                 (passphrases are hashed with SHA-256 to derive a 32-byte key).
    :returns:    Base64-encoded authenticated ciphertext.
    """
    raw_key = _coerce_key(key)
    nonce = os.urandom(12)  # 96-bit nonce — NIST SP 800-38D §8.2.1
    aesgcm = AESGCM(raw_key)
    ciphertext = aesgcm.encrypt(nonce, data.encode("utf-8"), None)  # no AAD
    return base64.b64encode(nonce + ciphertext).decode("ascii")


def DECRYPT(data: str, key: str) -> str:
    """
    Decrypt AES-256-GCM ciphertext produced by ENCRYPT.

    Raises:
        ValueError  — ciphertext is too short (< 28 bytes after base64 decode).
        cryptography.exceptions.InvalidTag — authentication tag mismatch (tampered data).
    """
    raw_key = _coerce_key(key)
    raw = base64.b64decode(data)
    if len(raw) < 28:  # 12 nonce + 0 plaintext + 16 tag minimum
        raise ValueError(f"Ciphertext too short: {len(raw)} bytes (minimum 28)")
    nonce = raw[:12]
    ciphertext = raw[12:]
    aesgcm = AESGCM(raw_key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)  # raises InvalidTag on tamper
    return plaintext.decode("utf-8")


# ── HMAC-SHA256 signing ────────────────────────────────────────────────────────


def SIGN(data: str, private_key: str) -> str:
    """
    Produce an HMAC-SHA256 message authentication code.

    :param data:        Message string to authenticate.
    :param private_key: Shared secret key (UTF-8 encoded).
    :returns:           64-char lowercase hex MAC.
    """
    mac = hmac.new(
        private_key.encode("utf-8"),
        data.encode("utf-8"),
        hashlib.sha256,
    )
    return mac.hexdigest()


def SIGN_VERIFY(data: str, signature: str, public_key: str) -> bool:
    """
    Constant-time verification of an HMAC-SHA256 signature.

    :param data:       Original message string.
    :param signature:  Hex MAC string to verify against.
    :param public_key: Shared secret key used when signing.
    :returns:          True if the signature is valid; False otherwise.
    """
    expected = SIGN(data, public_key)
    return hmac.compare_digest(expected, signature.lower())


# ── Hashing ────────────────────────────────────────────────────────────────────


_SUPPORTED_ALGOS = frozenset({"sha256", "sha512", "sha3_256", "sha3_512", "blake2b", "blake2s"})


def HASH(data: str, algo: str = "sha256") -> str:
    """
    Compute a hex digest of *data*.

    :param algo: One of sha256, sha512, sha3_256, sha3_512, blake2b, blake2s.
    :raises ValueError: If the algorithm name is not supported.
    """
    algo = algo.lower().replace("-", "_")
    if algo not in _SUPPORTED_ALGOS:
        raise ValueError(
            f"Unsupported hash algorithm: {algo!r}. Supported: {sorted(_SUPPORTED_ALGOS)}"
        )
    if algo == "blake2b":
        h = hashlib.blake2b(data.encode("utf-8"))
    elif algo == "blake2s":
        h = hashlib.blake2s(data.encode("utf-8"))
    else:
        h = hashlib.new(algo, data.encode("utf-8"))
    return h.hexdigest()


def HASH_VERIFY(data: str, expected_hash: str, algo: str = "sha256") -> bool:
    """
    Constant-time hash comparison.

    :returns: True if HASH(data, algo) == expected_hash (case-insensitive hex).
    """
    return hmac.compare_digest(HASH(data, algo), expected_hash.lower())


# ── Key derivation ─────────────────────────────────────────────────────────────


def KEY_DERIVE(
    password: str,
    salt_hex: str = "",
    iterations: int = 600_000,
) -> dict[str, str]:
    """
    Derive a 32-byte AES key from a password using PBKDF2-HMAC-SHA256.

    NIST SP 800-132 compliant. Default iteration count follows OWASP 2024 guidance.

    :param password:   Passphrase string (UTF-8).
    :param salt_hex:   16-byte salt as 32-char hex. If empty, a random salt is generated.
    :param iterations: PBKDF2 iteration count (default 600,000 per OWASP 2024).
    :returns:          Dict with keys 'key_hex', 'salt_hex', 'iterations'.
    """
    if salt_hex:
        salt = bytes.fromhex(salt_hex)
    else:
        salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
        dklen=32,
    )
    return {
        "key_hex": dk.hex(),
        "salt_hex": salt.hex(),
        "iterations": iterations,
    }


def KEY_GENERATE() -> str:
    """
    Generate a cryptographically random 256-bit AES key.

    :returns: 64-char lowercase hex string (32 raw bytes).
    """
    return secrets.token_hex(32)


# ── Merkle root ────────────────────────────────────────────────────────────────


def MERKLE_ROOT(items: list[str]) -> str:
    """
    Compute the Merkle root of a list of strings using SHA-256 pairwise hashing.

    This is the same algorithm used by the ALIGN Ledger chain.
    An empty list returns the SHA-256 of the empty string.
    An odd number of items duplicates the last leaf (standard Bitcoin/HLF convention).

    :param items: List of string values to hash.
    :returns:     64-char hex SHA-256 Merkle root.
    """
    if not items:
        return hashlib.sha256(b"").hexdigest()

    layer = [hashlib.sha256(item.encode("utf-8")).digest() for item in items]

    while len(layer) > 1:
        if len(layer) % 2 == 1:
            layer.append(layer[-1])  # duplicate last leaf
        next_layer = []
        for i in range(0, len(layer), 2):
            combined = layer[i] + layer[i + 1]
            next_layer.append(hashlib.sha256(combined).digest())
        layer = next_layer

    return layer[0].hex()


# ── Merkle chain append (ALIGN Ledger) ────────────────────────────────────────


def MERKLE_CHAIN_APPEND(prev_hash: str, entry: str) -> str:
    """
    Append an entry to a Merkle chain (ALIGN Ledger pattern).

    Each entry is chained as: SHA-256(prev_hash_hex + SHA-256(entry_bytes).hex())
    The first entry in a new chain should use prev_hash = "0" * 64.

    :returns: 64-char hex hash of the new chain head.
    """
    entry_hash = hashlib.sha256(entry.encode("utf-8")).hexdigest()
    chain_input = (prev_hash + entry_hash).encode("utf-8")
    return hashlib.sha256(chain_input).hexdigest()


# ── HMAC-SHA256 MAC (lower-level, for internal use) ───────────────────────────


def HMAC_SHA256(key: str, data: str) -> str:
    """Compute HMAC-SHA256 of data with key. Returns hex digest."""
    return hmac.new(key.encode("utf-8"), data.encode("utf-8"), hashlib.sha256).hexdigest()
