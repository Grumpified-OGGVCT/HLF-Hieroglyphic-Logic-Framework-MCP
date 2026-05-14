### ✅ routing

**File:** `routing.hlf` | **Lines:** 7 | **Nodes:** 3 | **Bytecode:** 305B | **Time:** 0.7ms

<details open><summary><b>Surface 1: Glyph Source</b></summary>

```hlf
# HLF v3 — Real-Time Resource Mediation (MoMA Router)
# The router dynamically selects from the tier's model matrix.
[HLF-v3]
⌘ [ROUTE] strategy="auto" tier="$DEPLOYMENT_TIER"
  ∇ [PARAM] temperature=0.0
  Ж [VOTE] confirmation="required"
Ω
```

</details>

<details><summary><b>Surface 2: Formatted Canonical</b></summary>

```hlf
[HLF-v3]
⌘ [ROUTE] strategy="auto" tier="$DEPLOYMENT_TIER"
  ∇ [PARAM] temperature=0.0
  Ж [VOTE] confirmation="required"
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
    }
  ],
  "node_count": 3,
  "human_readable": "HLF v3 program with 3 statement(s)",
  "sha256": "4592aa1f9c471c1815167a437ca69360ce1e55d78b15828a09f909885fc38594",
  "env": {}
}
```

</details>

<details><summary><b>Surface 4: Bytecode (hex)</b></summary>

```
f24f7d5e782fb96db2ddb276bd8337d28f80fe54c6692783e967419167a19e5c484c4200040030000000793578a000000f000000030b000000e28c98205b524f5554455d03040000006175746f0308000000737472617465677903040000006175746f0310000000244445504c4f594d454e545f544945520304000000746965720310000000244445504c4f594d454e545f54494552030b000000e28887205b504152414d5d020000000000000000030b00000074656d70657261747572650200000000000000000309000000d096205b564f54455d03080000007265717569726564030c000000636f6e6669726d6174696f6e03080000007265717569726564010100020200010300010400020500010600510008010800020900010a00010700010c00020d00010e00600b00ff0000
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
  0021  PUSH_CONST         #12  ; 'required'
  0024  STORE              #13  ; 'confirmation'
  0027  PUSH_CONST         #14  ; 'required'
  002A  TAG                #11  ; 'Ж [VOTE]'
  002D  HALT
```

</details>

<details><summary><b>Surface 6: English Translation</b></summary>

> HLF v3 program with 3 statement(s): delegate [ROUTE]: strategy=auto, tier=$DEPLOYMENT_TIER; source [PARAM]: temperature=0.0; enforce [VOTE]: confirmation=required.

</details>

---
