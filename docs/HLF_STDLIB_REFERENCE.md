# HLF Stdlib Reference

Generated from the packaged Python stdlib bindings in `hlf_mcp/hlf/stdlib/`.

## agent

HLF stdlib: agent module — agent identity and goal management.

| Function | Signature |
| --- | --- |
| `AGENT_CAPABILITIES` | `() -> 'list[str]'` |
| `AGENT_ID` | `() -> 'str'` |
| `AGENT_TIER` | `() -> 'str'` |
| `COMPLETE_GOAL` | `(goal_id: 'str') -> 'bool'` |
| `GET_GOALS` | `() -> 'list[str]'` |
| `SET_GOAL` | `(goal: 'str') -> 'bool'` |

## collections

HLF stdlib: collections module.

| Function | Signature |
| --- | --- |
| `DICT_GET` | `(d, key)` |
| `DICT_KEYS` | `(d)` |
| `DICT_SET` | `(d, key, value)` |
| `DICT_VALUES` | `(d)` |
| `LIST_APPEND` | `(lst, item)` |
| `LIST_CONCAT` | `(lst1, lst2)` |
| `LIST_FILTER` | `(lst, pred)` |
| `LIST_LENGTH` | `(lst)` |
| `LIST_MAP` | `(lst, fn)` |
| `LIST_REDUCE` | `(lst, fn, initial)` |

## crypto

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

| Function | Signature |
| --- | --- |
| `DECRYPT` | `(data: 'str', key: 'str') -> 'str'` |
| `ENCRYPT` | `(data: 'str', key: 'str') -> 'str'` |
| `HASH` | `(data: 'str', algo: 'str' = 'sha256') -> 'str'` |
| `HASH_VERIFY` | `(data: 'str', expected_hash: 'str', algo: 'str' = 'sha256') -> 'bool'` |
| `HMAC_SHA256` | `(key: 'str', data: 'str') -> 'str'` |
| `KEY_DERIVE` | `(password: 'str', salt_hex: 'str' = '', iterations: 'int' = 600000) -> 'dict[str, str]'` |
| `KEY_GENERATE` | `() -> 'str'` |
| `MERKLE_CHAIN_APPEND` | `(prev_hash: 'str', entry: 'str') -> 'str'` |
| `MERKLE_ROOT` | `(items: 'list[str]') -> 'str'` |
| `SIGN` | `(data: 'str', private_key: 'str') -> 'str'` |
| `SIGN_VERIFY` | `(data: 'str', signature: 'str', public_key: 'str') -> 'bool'` |

## io

HLF stdlib: io module — file I/O with ACFS path validation.

| Function | Signature |
| --- | --- |
| `DIR_CREATE` | `(path: str) -> bool` |
| `DIR_LIST` | `(path: str) -> list[str]` |
| `FILE_DELETE` | `(path: str) -> bool` |
| `FILE_EXISTS` | `(path: str) -> bool` |
| `FILE_READ` | `(path: str) -> str` |
| `FILE_WRITE` | `(path: str, data: str) -> bool` |
| `PATH_BASENAME` | `(path: str) -> str` |
| `PATH_DIRNAME` | `(path: str) -> str` |
| `PATH_JOIN` | `(*parts: str) -> str` |

## math

HLF stdlib: math module.

| Function | Signature |
| --- | --- |
| `MATH_ABS` | `(x)` |
| `MATH_CEIL` | `(x)` |
| `MATH_COS` | `(x)` |
| `MATH_E` | `()` |
| `MATH_FLOOR` | `(x)` |
| `MATH_LOG` | `(x)` |
| `MATH_MAX` | `(a, b)` |
| `MATH_MIN` | `(a, b)` |
| `MATH_PI` | `()` |
| `MATH_POW` | `(base, exp)` |
| `MATH_ROUND` | `(x)` |
| `MATH_SIN` | `(x)` |
| `MATH_SQRT` | `(x)` |
| `MATH_TAN` | `(x)` |

## net

HLF stdlib: net module — HTTP helpers.

| Function | Signature |
| --- | --- |
| `HTTP_DELETE` | `(url: str) -> str` |
| `HTTP_GET` | `(url: str) -> str` |
| `HTTP_POST` | `(url: str, body: str) -> str` |
| `HTTP_PUT` | `(url: str, body: str) -> str` |
| `URL_DECODE` | `(query: str) -> dict` |
| `URL_ENCODE` | `(params: dict) -> str` |

## string

HLF stdlib: string module.

| Function | Signature |
| --- | --- |
| `STRING_CONCAT` | `(s1, s2)` |
| `STRING_CONTAINS` | `(s, sub)` |
| `STRING_ENDS_WITH` | `(s, suffix)` |
| `STRING_JOIN` | `(parts, sep)` |
| `STRING_LENGTH` | `(s)` |
| `STRING_LOWER` | `(s)` |
| `STRING_REPLACE` | `(s, old, new)` |
| `STRING_SPLIT` | `(s, sep)` |
| `STRING_STARTS_WITH` | `(s, prefix)` |
| `STRING_SUBSTRING` | `(s, start, end)` |
| `STRING_TRIM` | `(s)` |
| `STRING_UPPER` | `(s)` |

## system

HLF stdlib: system module.

| Function | Signature |
| --- | --- |
| `SYS_ARCH` | `() -> str` |
| `SYS_CWD` | `() -> str` |
| `SYS_ENV` | `(var: str) -> str` |
| `SYS_EXEC` | `(cmd: str, args: list[str] | None = None) -> str` |
| `SYS_EXIT` | `(code: int) -> None` |
| `SYS_OS` | `() -> str` |
| `SYS_SETENV` | `(var: str, value: str) -> bool` |
| `SYS_SLEEP` | `(ms: int) -> bool` |
| `SYS_TIME` | `() -> int` |

