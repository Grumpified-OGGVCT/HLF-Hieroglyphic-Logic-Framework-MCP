### ✅ security_audit

**File:** `security_audit.hlf` | **Lines:** 9 | **Nodes:** 4 | **Bytecode:** 418B | **Time:** 1.0ms

<details open><summary><b>Surface 1: Glyph Source</b></summary>

```hlf
# HLF v3 — Security Baseline Audit (Sentinel Mode)
# The agent audits a critical system file while enforcing strict RO constraints.
# All agents must reach strict consensus before proceeding.
[HLF-v3]
Δ analyze /security/seccomp.json
  Ж [CONSTRAINT] mode="ro"
  Ж [EXPECT] vulnerability_shorthand
  ⨝ [VOTE] consensus="strict"
Ω
```

</details>

<details><summary><b>Surface 2: Formatted Canonical</b></summary>

```hlf
[HLF-v3]
Δ analyze /security/seccomp.json
  Ж [CONSTRAINT] mode="ro"
  Ж [EXPECT] vulnerability_shorthand
  ⨝ [VOTE] consensus="strict"
Ω
```

</details>

<details><summary><b>Surface 3: AST (JSON)</b></summary>

```json
{
  "kind": "program",
  "version": "3",
  "statements": [
    {
      "kind": "glyph_stmt",
      "glyph": "\u0394",
      "tag": null,
      "arguments": [
        {
          "kind": "pos_arg",
          "value": {
            "kind": "value",
            "type": "ident",
            "value": "analyze"
          }
        },
        {
          "kind": "pos_arg",
          "value": {
            "kind": "value",
            "type": "path",
            "value": "/security/seccomp.json"
          }
        }
      ],
      "human_readable": "analyze: analyze, /security/seccomp.json"
    },
    {
      "kind": "glyph_stmt",
      "glyph": "\u0416",
      "tag": "CONSTRAINT",
      "arguments": [
        {
          "kind": "kv_arg",
          "name": "mode",
          "value": {
            "kind": "value",
            "type": "string",
            "value": "ro"
          }
        }
      ],
      "human_readable": "enforce [CONSTRAINT]: mode=ro"
    },
    {
      "kind": "glyph_stmt",
      "glyph": "\u0416",
      "tag": "EXPECT",
      "arguments": [
        {
          "kind": "pos_arg",
          "value": {
            "kind": "value",
            "type": "ident",
            "value": "vulnerability_shorthand"
          }
        }
      ],
      "human_readable": "enforce [EXPECT]: vulnerability_shorthand"
    },
    {
      "kind": "glyph_stmt",
      "glyph": "\u2a1d",
      "tag": "VOTE",
      "arguments": [
        {
          "kind": "kv_arg",
          "name": "consensus",
          "value": {
            "kind": "value",
            "type": "string",
            "value": "strict"
          }
        }
      ],
      "human_readable": "consensus [VOTE]: consensus=strict"
    }
  ],
  "node_count": 4,
  "human_readable": "HLF v3 program with 4 statement(s)",
  "sha256": "ea9dc15cb41651675d7f6db32f02440e99be6c0a10fd271a3551c2f60c429bc8",
  "env": {}
}
```

</details>

<details><summary><b>Surface 4: Bytecode (hex)</b></summary>

```
ac6354c17d09c188b5c93067f6f9d32dc3000623dfdd6128a2b639294db90b7e484c420004002a0000009c080a3e00000d0000000302000000ce9403360000007b276b696e64273a202776616c7565272c202774797065273a20276964656e74272c202776616c7565273a2027616e616c797a65277d03440000007b276b696e64273a202776616c7565272c202774797065273a202770617468272c202776616c7565273a20272f73656375726974792f736563636f6d702e6a736f6e277d030f000000d096205b434f4e53545241494e545d0302000000726f03040000006d6f64650302000000726f030b000000d096205b4558504543545d03460000007b276b696e64273a202776616c7565272c202774797065273a20276964656e74272c202776616c7565273a202776756c6e65726162696c6974795f73686f727468616e64277d030a000000e2a89d205b564f54455d03060000007374726963740309000000636f6e73656e7375730306000000737472696374010100010200510008010400020500010600600300010800600700010a00020b00010c00610900ff0000
```

</details>

<details><summary><b>Surface 5: Assembly</b></summary>

```asm
  0000  PUSH_CONST         #1  ; "{'kind': 'value', 'type': 'ident', 'value': 'analyze'}"
  0003  PUSH_CONST         #2  ; "{'kind': 'value', 'type': 'path', 'value': '/security/seccomp.json'}"
  0006  CALL_HOST          #0 (args=2)  ; 'Δ'
  0009  PUSH_CONST         #4  ; 'ro'
  000C  STORE              #5  ; 'mode'
  000F  PUSH_CONST         #6  ; 'ro'
  0012  TAG                #3  ; 'Ж [CONSTRAINT]'
  0015  PUSH_CONST         #8  ; "{'kind': 'value', 'type': 'ident', 'value': 'vulnerability_shorthand'}"
  0018  TAG                #7  ; 'Ж [EXPECT]'
  001B  PUSH_CONST         #10  ; 'strict'
  001E  STORE              #11  ; 'consensus'
  0021  PUSH_CONST         #12  ; 'strict'
  0024  INTENT             #9  ; '⨝ [VOTE]'
  0027  HALT
```

</details>

<details><summary><b>Surface 6: English Translation</b></summary>

> HLF v3 program with 4 statement(s): analyze: analyze, /security/seccomp.json; enforce [CONSTRAINT]: mode=ro; enforce [EXPECT]: vulnerability_shorthand; consensus [VOTE]: consensus=strict.

</details>

---
