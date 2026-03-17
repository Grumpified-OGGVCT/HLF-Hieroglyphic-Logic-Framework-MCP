# HLF Standard Library

Packaged standard-library guide for this repository.

This repo does not ship the older upstream 5-module stdlib story. The packaged surface currently exposes 8 Python-backed stdlib modules under `hlf_mcp/hlf/stdlib/`.

For exact exported call signatures, use [HLF_STDLIB_REFERENCE.md](c:/Users/gerry/generic_workspace/HLF_MCP/docs/HLF_STDLIB_REFERENCE.md).

## Truth Boundary

- The authoritative implementation surface is `hlf_mcp/hlf/stdlib/*.py`.
- The authoritative exported symbol catalog is [HLF_STDLIB_REFERENCE.md](c:/Users/gerry/generic_workspace/HLF_MCP/docs/HLF_STDLIB_REFERENCE.md).
- This document is the curated guide: what exists, what each module is for, and where import semantics still need reconciliation.

## Current Module Set

| Logical Module | Python Binding | Purpose | Notable Exports |
| --- | --- | --- | --- |
| `agent` | `agent.py` | Agent identity and goal state | `AGENT_ID`, `AGENT_TIER`, `SET_GOAL` |
| `collections` | `collections_mod.py` | List and dictionary helpers | `LIST_APPEND`, `DICT_GET`, `LIST_REDUCE` |
| `crypto` | `crypto_mod.py` | Cryptography and integrity primitives | `ENCRYPT`, `DECRYPT`, `HASH`, `MERKLE_ROOT` |
| `io` | `io_mod.py` | File and path operations | `FILE_READ`, `FILE_WRITE`, `DIR_LIST` |
| `math` | `math_mod.py` | Numeric helpers and constants | `MATH_ABS`, `MATH_PI`, `MATH_SQRT` |
| `net` | `net_mod.py` | HTTP and URL helpers | `HTTP_GET`, `HTTP_POST`, `URL_ENCODE` |
| `string` | `string_mod.py` | String transformation utilities | `STRING_UPPER`, `STRING_SPLIT`, `STRING_REPLACE` |
| `system` | `system_mod.py` | Host/system helpers | `SYS_OS`, `SYS_CWD`, `SYS_EXEC` |

## Practical Notes

### Import story is still being reconciled

The packaged parser currently treats `IMPORT` as path-oriented, while tooling and the stdlib catalog expose logical modules such as `math` and `crypto`.

That means the stdlib inventory is real, but the exact authored import syntax is still part of the broader extraction/refactor boundary. Do not assume the older upstream examples are parser-accurate here.

### Python-backed, not `.hlf`-backed

The packaged repo binds stdlib behavior through Python modules, not through the older upstream `.hlf` stdlib files. That is why exported names in the generated reference appear as Python callables.

### Security-sensitive modules

The `crypto`, `io`, `net`, and `system` modules cross trust boundaries more directly than pure data helpers. Use the capsule/governance layers and host-function policies when exposing them through higher-level workflows.

## Suggested Reading Order

1. Start with this file for the module map.
2. Use [HLF_STDLIB_REFERENCE.md](c:/Users/gerry/generic_workspace/HLF_MCP/docs/HLF_STDLIB_REFERENCE.md) for exact function names and signatures.
3. Use [HLF_GRAMMAR_REFERENCE.md](c:/Users/gerry/generic_workspace/HLF_MCP/docs/HLF_GRAMMAR_REFERENCE.md) to understand the current parser surface that sits around stdlib usage.