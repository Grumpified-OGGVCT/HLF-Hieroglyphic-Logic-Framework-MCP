### ✅ log_analysis

**File:** `log_analysis.hlf` | **Lines:** 10 | **Nodes:** 6 | **Bytecode:** 535B | **Time:** 1.1ms

<details open><summary><b>Surface 1: Glyph Source</b></summary>

```hlf
# HLF v3 — Log Analysis
# Analyze system log with read-only constraint, extract error patterns.
[HLF-v3]
Δ analyze /var/log/system.log
  Ж [CONSTRAINT] mode="ro"
  Ж [EXPECT] error_patterns
  ∇ [PARAM] top_k=10
  ∇ [PARAM] include_timestamps=true
  ⨝ [VOTE] consensus="majority"
Ω
```

</details>

<details><summary><b>Surface 2: Formatted Canonical</b></summary>

```hlf
[HLF-v3]
Δ analyze /var/log/system.log
  Ж [CONSTRAINT] mode="ro"
  Ж [EXPECT] error_patterns
  ∇ [PARAM] top_k=10
  ∇ [PARAM] include_timestamps=true
  ⨝ [VOTE] consensus="majority"
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
            "value": "/var/log/system.log"
          }
        }
      ],
      "human_readable": "analyze: analyze, /var/log/system.log"
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
            "value": "error_patterns"
          }
        }
      ],
      "human_readable": "enforce [EXPECT]: error_patterns"
    },
    {
      "kind": "glyph_stmt",
      "glyph": "\u2207",
      "tag": "PARAM",
      "arguments": [
        {
          "kind": "kv_arg",
          "name": "top_k",
          "value": {
            "kind": "value",
            "type": "int",
            "value": 10
          }
        }
      ],
      "human_readable": "source [PARAM]: top_k=10"
    },
    {
      "kind": "glyph_stmt",
      "glyph": "\u2207",
      "tag": "PARAM",
      "arguments": [
        {
          "kind": "kv_arg",
          "name": "include_timestamps",
          "value": {
            "kind": "value",
            "type": "ident",
            "value": "true"
          }
        }
      ],
      "human_readable": "source [PARAM]: include_timestamps=true"
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
            "value": "majority"
          }
        }
      ],
      "human_readable": "consensus [VOTE]: consensus=majority"
    }
  ],
  "node_count": 6,
  "human_readable": "HLF v3 program with 6 statement(s)",
  "sha256": "2ef9b209727ef9223167a6b713aa7c0d96be4b2565500245a8e73158fff28dba",
  "env": {}
}
```

</details>

<details><summary><b>Surface 4: Bytecode (hex)</b></summary>

```
c756e211f5e8dc46da9e5ec6431a0057b51ab5b19af6f99f402fde948c625bef484c420004004200000039ce95860000150000000302000000ce9403360000007b276b696e64273a202776616c7565272c202774797065273a20276964656e74272c202776616c7565273a2027616e616c797a65277d03410000007b276b696e64273a202776616c7565272c202774797065273a202770617468272c202776616c7565273a20272f7661722f6c6f672f73797374656d2e6c6f67277d030f000000d096205b434f4e53545241494e545d0302000000726f03040000006d6f64650302000000726f030b000000d096205b4558504543545d033d0000007b276b696e64273a202776616c7565272c202774797065273a20276964656e74272c202776616c7565273a20276572726f725f7061747465726e73277d030b000000e28887205b504152414d5d010a000000000000000305000000746f705f6b010a00000000000000030b000000e28887205b504152414d5d0304000000747275650312000000696e636c7564655f74696d657374616d7073030400000074727565030a000000e2a89d205b564f54455d03080000006d616a6f726974790309000000636f6e73656e73757303080000006d616a6f72697479010100010200510008010400020500010600600300010800600700010a00020b00010c00010900010e00020f00011000010d00011200021300011400611100ff0000
```

</details>

<details><summary><b>Surface 5: Assembly</b></summary>

```asm
  0000  PUSH_CONST         #1  ; "{'kind': 'value', 'type': 'ident', 'value': 'analyze'}"
  0003  PUSH_CONST         #2  ; "{'kind': 'value', 'type': 'path', 'value': '/var/log/system.log'}"
  0006  CALL_HOST          #0 (args=2)  ; 'Δ'
  0009  PUSH_CONST         #4  ; 'ro'
  000C  STORE              #5  ; 'mode'
  000F  PUSH_CONST         #6  ; 'ro'
  0012  TAG                #3  ; 'Ж [CONSTRAINT]'
  0015  PUSH_CONST         #8  ; "{'kind': 'value', 'type': 'ident', 'value': 'error_patterns'}"
  0018  TAG                #7  ; 'Ж [EXPECT]'
  001B  PUSH_CONST         #10  ; 10
  001E  STORE              #11  ; 'top_k'
  0021  PUSH_CONST         #12  ; 10
  0024  PUSH_CONST         #9  ; '∇ [PARAM]'
  0027  PUSH_CONST         #14  ; 'true'
  002A  STORE              #15  ; 'include_timestamps'
  002D  PUSH_CONST         #16  ; 'true'
  0030  PUSH_CONST         #13  ; '∇ [PARAM]'
  0033  PUSH_CONST         #18  ; 'majority'
  0036  STORE              #19  ; 'consensus'
  0039  PUSH_CONST         #20  ; 'majority'
  003C  INTENT             #17  ; '⨝ [VOTE]'
  003F  HALT
```

</details>

<details><summary><b>Surface 6: English Translation</b></summary>

> HLF v3 program with 6 statement(s): analyze: analyze, /var/log/system.log; enforce [CONSTRAINT]: mode=ro; enforce [EXPECT]: error_patterns; source [PARAM]: top_k=10; source [PARAM]: include_timestamps=true; consensus [VOTE]: consensus=majority.

</details>

---
