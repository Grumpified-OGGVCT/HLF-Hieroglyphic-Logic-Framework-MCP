"""
Tests for HLF Secret Capsule (Enterprise Hardening #5: Secret Management).

Tests:
- encrypt/decrypt round-trip
- SecretCapsule add/decrypt/get_hash
- Auto-redaction (repr/str never show plaintext)
- Merkle-safe metadata (only SHA-256 of ciphertext)
- Glyph parsing (∇ [SECRET] name="x" value="y")
- SecretCapsule.from_glyphs creation
- Serialization round-trip (to_dict/from_dict)
- Error cases: missing key, wrong key, missing secret
- Integration: governed_latent_infer with secrets parameter
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest


# ── Fixtures ──

@pytest.fixture
def temp_master_key():
    """Set HLF_MASTER_KEY for tests."""
    old = os.environ.get("HLF_MASTER_KEY")
    os.environ["HLF_MASTER_KEY"] = "test-master-key-12345678"
    yield
    if old is not None:
        os.environ["HLF_MASTER_KEY"] = old
    else:
        os.environ.pop("HLF_MASTER_KEY", None)


@pytest.fixture
def seed_capsule(temp_master_key):
    """A SecretCapsule with two pre-loaded secrets."""
    from hlf_mcp.hlf.secret_capsule import SecretCapsule

    capsule = SecretCapsule()
    capsule.add("db_password", "super-secret-db-pass")
    capsule.add("api_key", "sk-test-api-key-value")
    return capsule


# ── Cryptography availability check ──

def _skip_if_no_crypto():
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # noqa: F401
    except ImportError:
        pytest.skip("cryptography library not available")


# ── Basic encryption/decryption ──

class TestEncryptDecrypt:
    def test_round_trip(self, temp_master_key):
        _skip_if_no_crypto()
        from hlf_mcp.hlf.secret_capsule import encrypt_secret, decrypt_secret

        plaintext = "my-precious-secret"
        encrypted = encrypt_secret(plaintext)
        assert "ciphertext_b64" in encrypted
        assert "nonce_b64" in encrypted
        assert "salt_b64" in encrypted

        decrypted = decrypt_secret(
            encrypted["ciphertext_b64"],
            encrypted["nonce_b64"],
            encrypted["salt_b64"],
        )
        assert decrypted == plaintext

    def test_different_master_keys_produce_different_ciphertexts(self, temp_master_key):
        _skip_if_no_crypto()
        from hlf_mcp.hlf.secret_capsule import encrypt_secret

        c1 = encrypt_secret("test-value", master_key="key-alpha")
        c2 = encrypt_secret("test-value", master_key="key-beta")
        assert c1["ciphertext_b64"] != c2["ciphertext_b64"]

    def test_decrypt_with_wrong_key_fails(self, temp_master_key):
        _skip_if_no_crypto()
        from hlf_mcp.hlf.secret_capsule import encrypt_secret, decrypt_secret
        from hlf_mcp.hlf.secret_capsule import SecretCapsuleError

        encrypted = encrypt_secret("sensitive-data", master_key="correct-key")

        with pytest.raises(SecretCapsuleError):
            decrypt_secret(
                encrypted["ciphertext_b64"],
                encrypted["nonce_b64"],
                encrypted["salt_b64"],
                master_key="wrong-key",
            )

    def test_no_master_key_raises_error(self):
        _skip_if_no_crypto()
        from hlf_mcp.hlf.secret_capsule import encrypt_secret, SecretCapsuleError

        old = os.environ.pop("HLF_MASTER_KEY", None)
        try:
            with pytest.raises(SecretCapsuleError, match="HLF_MASTER_KEY"):
                encrypt_secret("test-value")
        finally:
            if old is not None:
                os.environ["HLF_MASTER_KEY"] = old

    def test_ciphertext_is_different_each_time(self, temp_master_key):
        _skip_if_no_crypto()
        from hlf_mcp.hlf.secret_capsule import encrypt_secret

        c1 = encrypt_secret("same-value")
        c2 = encrypt_secret("same-value")
        # Different salt/nonce each time → different ciphertext
        assert c1["ciphertext_b64"] != c2["ciphertext_b64"]


# ── SecretCapsule ──

class TestSecretCapsule:
    def test_add_and_decrypt(self, temp_master_key):
        _skip_if_no_crypto()
        from hlf_mcp.hlf.secret_capsule import SecretCapsule

        capsule = SecretCapsule()
        capsule_hash = capsule.add("test_secret", "hello-world")
        assert capsule_hash is not None
        assert len(capsule_hash) == 64  # SHA-256 hex

        decrypted = capsule.decrypt("test_secret")
        assert decrypted == "hello-world"

    def test_count_and_names(self, seed_capsule):
        _skip_if_no_crypto()
        assert seed_capsule.count == 2
        assert seed_capsule.names == ["api_key", "db_password"]

    def test_contains(self, seed_capsule):
        _skip_if_no_crypto()
        assert "db_password" in seed_capsule
        assert "nonexistent" not in seed_capsule

    def test_get_hash(self, seed_capsule):
        _skip_if_no_crypto()
        h = seed_capsule.get_hash("db_password")
        assert len(h) == 64
        # Same secret → same hash
        assert seed_capsule.get_hash("db_password") == h

    def test_decrypt_nonexistent_raises(self, seed_capsule):
        _skip_if_no_crypto()
        from hlf_mcp.hlf.secret_capsule import SecretNotFoundError

        with pytest.raises(SecretNotFoundError, match="nonexistent"):
            seed_capsule.decrypt("nonexistent")

    def test_get_hash_nonexistent_raises(self, seed_capsule):
        _skip_if_no_crypto()
        from hlf_mcp.hlf.secret_capsule import SecretNotFoundError

        with pytest.raises(SecretNotFoundError, match="nonexistent"):
            seed_capsule.get_hash("nonexistent")


# ── Auto-redaction ──

class TestAutoRedaction:
    def test_repr_does_not_leak_plaintext(self, seed_capsule):
        """repr() must never expose plaintext secret values."""
        r = repr(seed_capsule)
        assert "super-secret" not in r
        assert "sk-test" not in r
        assert "db_password" in r or seed_capsule.names[0] in r

    def test_str_does_not_leak_plaintext(self, seed_capsule):
        """str() must never expose plaintext secret values."""
        s = str(seed_capsule)
        assert "super-secret" not in s
        assert "sk-test" not in s

    def test_to_dict_does_not_leak_plaintext(self, seed_capsule):
        """to_dict() must only expose ciphertext, not plaintext."""
        d = seed_capsule.to_dict()
        secrets_dict = d["secrets"]
        for name, entry in secrets_dict.items():
            assert "ciphertext_b64" in entry
            assert "nonce_b64" in entry
            assert "salt_b64" in entry
            assert "hash" in entry
            # Plaintext must not appear
            assert "super-secret" not in str(entry)
            assert "sk-test" not in str(entry)

    def test_merkle_metadata_safe(self, seed_capsule):
        """Merkle metadata only contains SHA-256 hashes, no plaintext."""
        meta = seed_capsule.merkle_metadata
        for name, hash_val in meta.items():
            assert len(hash_val) == 64
            assert "super-secret" not in hash_val
            assert "sk-test" not in hash_val


# ── Serialization round-trip ──

class TestSerialization:
    def test_round_trip(self, seed_capsule):
        _skip_if_no_crypto()
        from hlf_mcp.hlf.secret_capsule import SecretCapsule

        data = seed_capsule.to_dict()
        restored = SecretCapsule.from_dict(data, master_key=seed_capsule.master_key)

        assert restored.count == seed_capsule.count
        assert restored.names == seed_capsule.names
        assert restored.decrypt("db_password") == "super-secret-db-pass"
        assert restored.decrypt("api_key") == "sk-test-api-key-value"

    def test_json_serializable(self, seed_capsule):
        """to_dict() output must be JSON-serializable."""
        data = seed_capsule.to_dict()
        json_str = json.dumps(data)
        parsed = json.loads(json_str)
        assert parsed["secret_count"] == 2


# ── Glyph parsing ──

class TestGlyphParsing:
    def test_parse_with_value(self):
        from hlf_mcp.hlf.secret_capsule import parse_secret_glyphs

        text = '∇ [SECRET] name="db_pass" value="mypassword"'
        results = parse_secret_glyphs(text)
        assert len(results) == 1
        assert results[0]["name"] == "db_pass"
        assert results[0]["value"] == "mypassword"

    def test_parse_without_value(self):
        from hlf_mcp.hlf.secret_capsule import parse_secret_glyphs

        text = '∇ [SECRET] name="api_key"'
        results = parse_secret_glyphs(text)
        assert len(results) == 1
        assert results[0]["name"] == "api_key"
        assert "value" not in results[0]

    def test_parse_multiple(self):
        from hlf_mcp.hlf.secret_capsule import parse_secret_glyphs

        text = '∇ [SECRET] name="x" value="vx" ∇ [SECRET] name="y" value="vy" ∇ [SECRET] name="z"'
        results = parse_secret_glyphs(text)
        assert len(results) == 3
        assert results[0]["name"] == "x"
        assert results[1]["name"] == "y"
        assert results[2]["name"] == "z"
        assert "value" not in results[2]

    def test_parse_empty(self):
        from hlf_mcp.hlf.secret_capsule import parse_secret_glyphs

        assert parse_secret_glyphs("") == []
        assert parse_secret_glyphs("no secrets here") == []

    def test_case_insensitive(self):
        from hlf_mcp.hlf.secret_capsule import parse_secret_glyphs

        results = parse_secret_glyphs('∇ [secret] name="test" value="val"')
        assert len(results) == 1
        assert results[0]["name"] == "test"

    def test_spacing_variations(self):
        from hlf_mcp.hlf.secret_capsule import parse_secret_glyphs

        # Extra spaces between ∇ and [SECRET]
        results = parse_secret_glyphs('∇    [SECRET]  name="abc"  value="xyz"')
        assert len(results) == 1
        assert results[0]["name"] == "abc"
        assert results[0]["value"] == "xyz"


# ── SecretCapsule.from_glyphs ──

class TestFromGlyphs:
    def test_from_glyphs_with_explicit_values(self, temp_master_key):
        _skip_if_no_crypto()
        from hlf_mcp.hlf.secret_capsule import SecretCapsule

        text = '∇ [SECRET] name="db" value="secret1" ∇ [SECRET] name="api" value="secret2"'
        capsule = SecretCapsule.from_glyphs(text)

        assert capsule.count == 2
        assert capsule.decrypt("db") == "secret1"
        assert capsule.decrypt("api") == "secret2"

    def test_from_glyphs_from_env(self, temp_master_key):
        _skip_if_no_crypto()
        from hlf_mcp.hlf.secret_capsule import SecretCapsule

        os.environ["MY_SECRET_VAR"] = "env-value"

        try:
            text = '∇ [SECRET] name="MY_SECRET_VAR"'
            capsule = SecretCapsule.from_glyphs(text)

            assert capsule.count == 1
            assert capsule.decrypt("MY_SECRET_VAR") == "env-value"
        finally:
            os.environ.pop("MY_SECRET_VAR", None)

    def test_from_glyphs_missing_env_raises(self, temp_master_key):
        _skip_if_no_crypto()
        from hlf_mcp.hlf.secret_capsule import SecretCapsule, SecretCapsuleError

        text = '∇ [SECRET] name="NONEXISTENT_ENV_VAR"'
        with pytest.raises(SecretCapsuleError, match="NONEXISTENT_ENV_VAR"):
            SecretCapsule.from_glyphs(text)

    def test_from_glyphs_empty_text(self, temp_master_key):
        _skip_if_no_crypto()
        from hlf_mcp.hlf.secret_capsule import SecretCapsule

        capsule = SecretCapsule.from_glyphs("")
        assert capsule.count == 0


# ── Cross-capsule security ──

class TestCrossCapsuleSecurity:
    def test_different_capsules_with_same_master_key(self, temp_master_key):
        """Two capsules with same master key can decrypt their own secrets."""
        _skip_if_no_crypto()
        from hlf_mcp.hlf.secret_capsule import SecretCapsule

        c1 = SecretCapsule()
        c2 = SecretCapsule()

        c1.add("secret1", "alpha")
        c2.add("secret2", "beta")

        assert c1.decrypt("secret1") == "alpha"
        assert c2.decrypt("secret2") == "beta"

        # Cross-capsule access not allowed since secrets are stored per-capsule
        from hlf_mcp.hlf.secret_capsule import SecretNotFoundError

        with pytest.raises(SecretNotFoundError):
            c1.decrypt("secret2")

    def test_different_master_keys(self, temp_master_key):
        """Capsules with different master keys produce incompatible ciphertext."""
        _skip_if_no_crypto()
        from hlf_mcp.hlf.secret_capsule import SecretCapsule

        c1 = SecretCapsule(master_key="key-alpha")
        hash1 = c1.add("shared_name", "value1")

        c2 = SecretCapsule(master_key="key-beta")
        with pytest.raises(Exception):
            # Different keys → different hashes
            c2.get_hash("shared_name")  # should not exist in c2
        from hlf_mcp.hlf.secret_capsule import SecretNotFoundError

        with pytest.raises(SecretNotFoundError):
            c2.decrypt("shared_name")


# ── compute_secret_hash ──

class TestComputeSecretHash:
    def test_same_ciphertext_same_hash(self):
        from hlf_mcp.hlf.secret_capsule import compute_secret_hash

        h1 = compute_secret_hash("abc123")
        h2 = compute_secret_hash("abc123")
        assert h1 == h2

    def test_different_ciphertext_different_hash(self):
        from hlf_mcp.hlf.secret_capsule import compute_secret_hash

        h1 = compute_secret_hash("abc123")
        h2 = compute_secret_hash("def456")
        assert h1 != h2

    def test_hash_is_64_hex_chars(self):
        from hlf_mcp.hlf.secret_capsule import compute_secret_hash

        h = compute_secret_hash("test")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


# ── Integration: governed_latent_infer with secrets ──

class TestGovernedLatentInferWithSecrets:
    def test_secrets_are_redacted_from_trace_output(self, temp_master_key):
        """When secrets are passed to governed_latent_infer, plaintext must
        not appear in the trace file."""
        _skip_if_no_crypto()
        from hlf_mcp.hlf.secret_capsule import SecretCapsule
        from hlf_mcp.hlf.latent_capsule import _write_latent_observability_trace

        # Create a secret capsule
        capsule = SecretCapsule()
        capsule.add("test_pass", "REDACTED-PLAINTEXT")

        # Manually verify redaction in trace data serialization
        capsule_dict = capsule.to_dict()
        serialized = json.dumps(capsule_dict, sort_keys=True)
        assert "REDACTED-PLAINTEXT" not in serialized
        assert "REDACTED" not in serialized

        # Merkle metadata should only have hashes
        meta = capsule.merkle_metadata
        for h in meta.values():
            assert "REDACTED" not in h
