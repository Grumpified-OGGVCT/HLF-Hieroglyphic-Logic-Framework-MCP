### ✅ module_workflow

**File:** `module_workflow.hlf` | **Lines:** 12 | **Nodes:** 8 | **Bytecode:** 773B | **Time:** 1.2ms

<details open><summary><b>Surface 1: Glyph Source</b></summary>

```hlf
# HLF v3 — Module Workflow
# Extracted from Sovereign source and adapted to the packaged v3 surface.
[HLF-v3]
Δ [INTENT] goal="module_workflow"
  ∇ [SOURCE] math
  ∇ [SOURCE] string
  ∇ [SOURCE] io
  ∇ [PARAM] input_text="Hello World"
  Ж [EXPECT] processed_output
  Ж [CONSTRAINT] output_format="json"
  ∇ [RESULT] message="Module workflow completed — processed HELLO WORLD, area=31"
Ω
```

</details>

<details><summary><b>Surface 2: Formatted Canonical</b></summary>

```hlf
[HLF-v3]
Δ [INTENT] goal="module_workflow"
  ∇ [SOURCE] math
  ∇ [SOURCE] string
  ∇ [SOURCE] io
  ∇ [PARAM] input_text="Hello World"
  Ж [EXPECT] processed_output
  Ж [CONSTRAINT] output_format="json"
  ∇ [RESULT] message="Module workflow completed — processed HELLO WORLD, area=31"
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
      "tag": "INTENT",
      "arguments": [
        {
          "kind": "kv_arg",
          "name": "goal",
          "value": {
            "kind": "value",
            "type": "string",
            "value": "module_workflow"
          }
        }
      ],
      "human_readable": "analyze [INTENT]: goal=module_workflow"
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
            "type": "ident",
            "value": "math"
          }
        }
      ],
      "human_readable": "source [SOURCE]: math"
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
            "type": "ident",
            "value": "string"
          }
        }
      ],
      "human_readable": "source [SOURCE]: string"
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
            "type": "ident",
            "value": "io"
          }
        }
      ],
      "human_readable": "source [SOURCE]: io"
    },
    {
      "kind": "glyph_stmt",
      "glyph"
... (truncated) ...
age",
          "value": {
            "kind": "value",
            "type": "string",
            "value": "Module workflow completed \u2014 processed HELLO WORLD, area=31"
          }
        }
      ],
      "human_readable": "source [RESULT]: message=Module workflow completed \u2014 processed HELLO WORLD, area=31"
    }
  ],
  "node_count": 8,
  "human_readable": "HLF v3 program with 8 statement(s)",
  "sha256": "ec64a848e29e83c99e0a8bf71399cde8d2a129dfca38e242f551fdec286163df",
  "env": {}
}
```

</details>

<details><summary><b>Surface 4: Bytecode (hex)</b></summary>

```
c3a945eba2e34c977bf33bdad2840c461c7907208ef673870836cc6f0a8b310d484c420004004b000000823f58d0000018000000030b000000ce94205b494e54454e545d030f0000006d6f64756c655f776f726b666c6f770304000000676f616c030f0000006d6f64756c655f776f726b666c6f77030c000000e28887205b534f555243455d03330000007b276b696e64273a202776616c7565272c202774797065273a20276964656e74272c202776616c7565273a20276d617468277d030c000000e28887205b534f555243455d03350000007b276b696e64273a202776616c7565272c202774797065273a20276964656e74272c202776616c7565273a2027737472696e67277d030c000000e28887205b534f555243455d03310000007b276b696e64273a202776616c7565272c202774797065273a20276964656e74272c202776616c7565273a2027696f277d030b000000e28887205b504152414d5d030b00000048656c6c6f20576f726c64030a000000696e7075745f74657874030b00000048656c6c6f20576f726c64030b000000d096205b4558504543545d033f0000007b276b696e64273a202776616c7565272c202774797065273a20276964656e74272c202776616c7565273a202770726f6365737365645f6f7574707574277d030f000000d096205b434f4e53545241494e545d03040000006a736f6e030d0000006f75747075745f666f726d617403040000006a736f6e030c000000e28887205b524553554c545d033c0000004d6f64756c6520776f726b666c6f7720636f6d706c6574656420e280942070726f6365737365642048454c4c4f20574f524c442c20617265613d333103070000006d657373616765033c0000004d6f64756c6520776f726b666c6f7720636f6d706c6574656420e280942070726f6365737365642048454c4c4f20574f524c442c20617265613d3331010100020200010300510004010500010400010700010600010900010800010b00020c00010d00010a00010f00600e00011100021200011300601000011500021600011700011400ff0000
```

</details>

<details><summary><b>Surface 5: Assembly</b></summary>

```asm
  0000  PUSH_CONST         #1  ; 'module_workflow'
  0003  STORE              #2  ; 'goal'
  0006  PUSH_CONST         #3  ; 'module_workflow'
  0009  CALL_HOST          #0 (args=1)  ; 'Δ [INTENT]'
  000C  PUSH_CONST         #5  ; "{'kind': 'value', 'type': 'ident', 'value': 'math'}"
  000F  PUSH_CONST         #4  ; '∇ [SOURCE]'
  0012  PUSH_CONST         #7  ; "{'kind': 'value', 'type': 'ident', 'value': 'string'}"
  0015  PUSH_CONST         #6  ; '∇ [SOURCE]'
  0018  PUSH_CONST         #9  ; "{'kind': 'value', 'type': 'ident', 'value': 'io'}"
  001B  PUSH_CONST         #8  ; '∇ [SOURCE]'
  001E  PUSH_CONST         #11  ; 'Hello World'
  0021  STORE              #12  ; 'input_text'
  0024  PUSH_CONST         #13  ; 'Hello World'
  0027  PUSH_CONST         #10  ; '∇ [PARAM]'
  002A  PUSH_CONST         #15  ; "{'kind': 'value', 'type': 'ident', 'value': 'processed_output'}"
  002D  TAG                #14  ; 'Ж [EXPECT]'
  0030  PUSH_CONST         #17  ; 'json'
  0033  STORE              #18  ; 'output_format'
  0036  PUSH_CONST         #19  ; 'json'
  0039  TAG                #16  ; 'Ж [CONSTRAINT]'
  003C  PUSH_CONST         #21  ; 'Module workflow completed — processed HELLO WORLD, area=31'
  003F  STORE              #22  ; 'message'
  0042  PUSH_CONST         #23  ; 'Module workflow completed — processed HELLO WORLD, area=31'
  0045  PUSH_CONST         #20  ; '∇ [RESULT]'
  0048  HALT
```

</details>

<details><summary><b>Surface 6: English Translation</b></summary>

> HLF v3 program with 8 statement(s): analyze [INTENT]: goal=module_workflow; source [SOURCE]: math; source [SOURCE]: string; source [SOURCE]: io; source [PARAM]: input_text=Hello World; enforce [EXPECT]: processed_output; enforce [CONSTRAINT]: output_format=json; source [RESULT]: message=Module workflow completed — processed HELLO WORLD, area=31.

</details>

---
