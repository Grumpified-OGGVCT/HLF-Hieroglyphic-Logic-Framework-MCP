### ✅ stack_deployment

**File:** `stack_deployment.hlf` | **Lines:** 9 | **Nodes:** 5 | **Bytecode:** 427B | **Time:** 0.9ms

<details open><summary><b>Surface 1: Glyph Source</b></summary>

```hlf
# HLF v3 — Stack Deployment
# Deploy application stack with MoMA routing and HITL confirmation.
[HLF-v3]
⌘ [ROUTE] strategy="auto" tier="$DEPLOYMENT_TIER"
  ∇ [PARAM] temperature=0.0
  ∇ [PARAM] replicas=3
  Ж [VOTE] confirmation="required"
  Ж [ASSERT] health_check=true
Ω
```

</details>

<details><summary><b>Surface 2: Formatted Canonical</b></summary>

```hlf
[HLF-v3]
⌘ [ROUTE] strategy="auto" tier="$DEPLOYMENT_TIER"
  ∇ [PARAM] temperature=0.0
  ∇ [PARAM] replicas=3
  Ж [VOTE] confirmation="required"
  Ж [ASSERT] health_check=true
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
      "tag": "ROUTE",
      "arguments": [
        {
          "kind": "kv_arg",
          "name": "strategy",
          "value": {
            "kind": "value",
            "type": "string",
            "value": "auto"
          }
        },
        {
          "kind": "kv_arg",
          "name": "tier",
          "value": {
            "kind": "value",
            "type": "string",
            "value": "$DEPLOYMENT_TIER"
          }
        }
      ],
      "human_readable": "delegate [ROUTE]: strategy=auto, tier=$DEPLOYMENT_TIER"
    },
    {
      "kind": "glyph_stmt",
      "glyph": "\u2207",
      "tag": "PARAM",
      "arguments": [
        {
          "kind": "kv_arg",
          "name": "temperature",
          "value": {
            "kind": "value",
            "type": "float",
            "value": 0.0
          }
        }
      ],
      "human_readable": "source [PARAM]: temperature=0.0"
    },
    {
      "kind": "glyph_stmt",
      "glyph": "\u2207",
      "tag": "PARAM",
      "arguments": [
        {
          "kind": "kv_arg",
          "name": "replicas",
          "value": {
            "kind": "value",
            "type": "int",
            "value": 3
          }
        }
      ],
      "human_readable": "source [PARAM]: replicas=3"
    },
    {
      "kind": "glyph_stmt",
      "glyph": "\u0416",
      "tag": "VOTE",
      "arguments": [
        {
          "kind": "kv_arg",
          "name": "confirmation",
          "value": {
            "kind": "value",
            "type": "string",
            "value": "required"
          }
        }
      ],
      "human_readable": "enforce [VOTE]: confirmation=required"
    },
    {
      "kind": "glyph_stmt",
      "glyph": "\u0416",
      "tag": "ASSERT",
      "arguments": [
        {
          "kind": "kv_arg",
          "name": "health_check",
          "value": {
            "kind": "value",
            "type": "ident",
            "value": "true"
          }
        }
      ],
      "human_readable": "enforce [ASSERT]: health_check=true"
    }
  ],
  "node_count": 5,
  "human_readable": "HLF v3 program with 5 statement(s)",
  "sha256": "4ae8b8eafd3c323e52e1136049a68910d56e19e8687749ab9006c48863e1a420",
  "env": {}
}
```

</details>

<details><summary><b>Surface 4: Bytecode (hex)</b></summary>

```
092609e49dd93ec85274290e7103eb41c288fc351fd13b9b633022526786b581484c4200040048000000b1968be9000017000000030b000000e28c98205b524f5554455d03040000006175746f0308000000737472617465677903040000006175746f0310000000244445504c4f594d454e545f544945520304000000746965720310000000244445504c4f594d454e545f54494552030b000000e28887205b504152414d5d020000000000000000030b00000074656d7065726174757265020000000000000000030b000000e28887205b504152414d5d01030000000000000003080000007265706c696361730103000000000000000309000000d096205b564f54455d03080000007265717569726564030c000000636f6e6669726d6174696f6e03080000007265717569726564030b000000d096205b4153534552545d030400000074727565030c0000006865616c74685f636865636b030400000074727565010100020200010300010400020500010600510008010800020900010a00010700010c00020d00010e00010b00011000021100011200600f00011400021500011600601300ff0000
```

</details>

<details><summary><b>Surface 5: Assembly</b></summary>

```asm
  0000  PUSH_CONST         #1  ; 'auto'
  0003  STORE              #2  ; 'strategy'
  0006  PUSH_CONST         #3  ; 'auto'
  0009  PUSH_CONST         #4  ; '$DEPLOYMENT_TIER'
  000C  STORE              #5  ; 'tier'
  000F  PUSH_CONST         #6  ; '$DEPLOYMENT_TIER'
  0012  CALL_HOST          #0 (args=2)  ; '⌘ [ROUTE]'
  0015  PUSH_CONST         #8  ; 0.0
  0018  STORE              #9  ; 'temperature'
  001B  PUSH_CONST         #10  ; 0.0
  001E  PUSH_CONST         #7  ; '∇ [PARAM]'
  0021  PUSH_CONST         #12  ; 3
  0024  STORE              #13  ; 'replicas'
  0027  PUSH_CONST         #14  ; 3
  002A  PUSH_CONST         #11  ; '∇ [PARAM]'
  002D  PUSH_CONST         #16  ; 'required'
  0030  STORE              #17  ; 'confirmation'
  0033  PUSH_CONST         #18  ; 'required'
  0036  TAG                #15  ; 'Ж [VOTE]'
  0039  PUSH_CONST         #20  ; 'true'
  003C  STORE              #21  ; 'health_check'
  003F  PUSH_CONST         #22  ; 'true'
  0042  TAG                #19  ; 'Ж [ASSERT]'
  0045  HALT
```

</details>

<details><summary><b>Surface 6: English Translation</b></summary>

> HLF v3 program with 5 statement(s): delegate [ROUTE]: strategy=auto, tier=$DEPLOYMENT_TIER; source [PARAM]: temperature=0.0; source [PARAM]: replicas=3; enforce [VOTE]: confirmation=required; enforce [ASSERT]: health_check=true.

</details>

---
