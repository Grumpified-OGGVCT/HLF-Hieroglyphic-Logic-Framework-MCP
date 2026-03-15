"""HLF stdlib: crypto module."""
import hashlib, hmac, secrets

def HASH(data: str, algo: str = "sha256") -> str:
    h = hashlib.new(algo)
    h.update(data.encode())
    return h.hexdigest()

def HASH_VERIFY(data: str, expected_hash: str, algo: str = "sha256") -> bool:
    return hmac.compare_digest(HASH(data, algo), expected_hash)

def ENCRYPT(data: str, key: str) -> str:
    """XOR-based obfuscation only — NOT secure encryption. Do not use for sensitive data."""
    import base64
    key_bytes = key.encode()
    data_bytes = data.encode()
    xored = bytes(d ^ key_bytes[i % len(key_bytes)] for i, d in enumerate(data_bytes))
    return base64.b64encode(xored).decode()

def DECRYPT(data: str, key: str) -> str:
    import base64
    key_bytes = key.encode()
    data_bytes = base64.b64decode(data)
    xored = bytes(d ^ key_bytes[i % len(key_bytes)] for i, d in enumerate(data_bytes))
    return xored.decode()

def SIGN(data: str, private_key: str) -> str:
    return hmac.new(private_key.encode(), data.encode(), hashlib.sha256).hexdigest()

def SIGN_VERIFY(data: str, signature: str, public_key: str) -> bool:
    expected = SIGN(data, public_key)
    return hmac.compare_digest(expected, signature)
