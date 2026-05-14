### ✅ delegation

**File:** `delegation.hlf` | **Lines:** 8 | **Nodes:** 4 | **Bytecode:** 407B | **Time:** 0.9ms

<details open><summary><b>Surface 1: Glyph Source</b></summary>

```hlf
# HLF v3 — Multi-Agent Task Delegation (Orchestrator Mode)
# The primary agent delegates a long-running summarization task to a Scribe agent.
[HLF-v3]
⌘ [DELEGATE] agent="scribe" goal="fractal_summarize"
  ∇ [SOURCE] /data/raw_logs/matrix_sync_2026.txt
  ⩕ [PRIORITY] level="high"
  Ж [ASSERT] vram_limit="8GB"
Ω
```

</details>

<details><summary><b>Surface 2: Formatted Canonical</b></summary>

```hlf
[HLF-v3]
⌘ [DELEGATE] agent="scribe" goal="fractal_summarize"
  ∇ [SOURCE] /data/raw_logs/matrix_sync_2026.txt
  ⩕ [PRIORITY] level="high"
  Ж [ASSERT] vram_limit="8GB"
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
      "glyph": "\u2318",
      "tag": "DELEGATE",
      "arguments": [
        {
          "kind": "kv_arg",
          "name": "agent",
          "value": {
            "kind": "value",
            "type": "string",
            "value": "scribe"
          }
        },
        {
          "kind": "kv_arg",
          "name": "goal",
          "value": {
            "kind": "value",
            "type": "string",
            "value": "fractal_summarize"
          }
        }
      ],
      "human_readable": "delegate [DELEGATE]: agent=scribe, goal=fractal_summarize"
    },
    {
      "kind": "glyph_stmt",
      "glyph": "\u2207",
      "tag": "SOURCE",
      "arguments": [
        {
          "kind": "pos_arg",
          "value": {
            "kind": "value",
            "type": "path",
            "value": "/data/raw_logs/matrix_sync_2026.txt"
          }
        }
      ],
      "human_readable": "source [SOURCE]: /data/raw_logs/matrix_sync_2026.txt"
    },
    {
      "kind": "glyph_stmt",
      "glyph": "\u2a55",
      "tag": "PRIORITY",
      "arguments": [
        {
          "kind": "kv_arg",
          "name": "level",
          "value": {
            "kind": "value",
            "type": "string",
            "value": "high"
          }
        }
      ],
      "human_readable": "priority [PRIORITY]: level=high"
    },
    {
      "kind": "glyph_stmt",
      "glyph": "\u0416",
      "tag": "ASSERT",
      "arguments": [
        {
          "kind": "kv_arg",
          "name": "vram_limit",
          "value": {
            "kind": "value",
            "type": "string",
            "value": "8GB"
          }
        }
      ],
      "human_readable": "enforce [ASSERT]: vram_limit=8GB"
    }
  ],
  "node_count": 4,
  "human_readable": "HLF v3 program with 4 statement(s)",
  "sha256": "f804541dda66373d049dfd2e6c3531a443343acfec7d445b6f8c7cedd215e732",
  "env": {}
}
```

</details>

<details><summary><b>Surface 4: Bytecode (hex)</b></summary>

```
f461ba03c4b940395bdbb89e8d2542d019ba25d83641213b96dc6f1d4384b350484c4200040036000000ddb7ee29000011000000030e000000e28c98205b44454c45474154455d030600000073637269626503050000006167656e74030600000073637269626503110000006672616374616c5f73756d6d6172697a650304000000676f616c03110000006672616374616c5f73756d6d6172697a65030c000000e28887205b534f555243455d03510000007b276b696e64273a202776616c7565272c202774797065273a202770617468272c202776616c7565273a20272f646174612f7261775f6c6f67732f6d61747269785f73796e635f323032362e747874277d030e000000e2a995205b5052494f524954595d03040000006869676803050000006c6576656c030400000068696768030b000000d096205b4153534552545d0303000000384742030a0000007672616d5f6c696d69740303000000384742010100020200010300010400020500010600510008010800010700010a00020b00010c00600900010e00020f00011000600d00ff0000
```

</details>

<details><summary><b>Surface 5: Assembly</b></summary>

```asm
  0000  PUSH_CONST         #1  ; 'scribe'
  0003  STORE              #2  ; 'agent'
  0006  PUSH_CONST         #3  ; 'scribe'
  0009  PUSH_CONST         #4  ; 'fractal_summarize'
  000C  STORE              #5  ; 'goal'
  000F  PUSH_CONST         #6  ; 'fractal_summarize'
  0012  CALL_HOST          #0 (args=2)  ; '⌘ [DELEGATE]'
  0015  PUSH_CONST         #8  ; "{'kind': 'value', 'type': 'path', 'value': '/data/raw_logs/matrix_sync_2026.txt'}"
  0018  PUSH_CONST         #7  ; '∇ [SOURCE]'
  001B  PUSH_CONST         #10  ; 'high'
  001E  STORE              #11  ; 'level'
  0021  PUSH_CONST         #12  ; 'high'
  0024  TAG                #9  ; '⩕ [PRIORITY]'
  0027  PUSH_CONST         #14  ; '8GB'
  002A  STORE              #15  ; 'vram_limit'
  002D  PUSH_CONST         #16  ; '8GB'
  0030  TAG                #13  ; 'Ж [ASSERT]'
  0033  HALT
```

</details>

<details><summary><b>Surface 6: English Translation</b></summary>

> HLF v3 program with 4 statement(s): delegate [DELEGATE]: agent=scribe, goal=fractal_summarize; source [SOURCE]: /data/raw_logs/matrix_sync_2026.txt; priority [PRIORITY]: level=high; enforce [ASSERT]: vram_limit=8GB.

</details>

---
