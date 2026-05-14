### ✅ system_health_check

**File:** `system_health_check.hlf` | **Lines:** 10 | **Nodes:** 6 | **Bytecode:** 670B | **Time:** 1.1ms

<details open><summary><b>Surface 1: Glyph Source</b></summary>

```hlf
# HLF v3 — System Health Check
# Extracted from Sovereign source and adapted to the packaged v3 surface.
[HLF-v3]
Δ analyze /config/settings.json
  Ж [CONSTRAINT] tier="hearth"
  Ж [CONSTRAINT] gas_limit=20
  Ж [EXPECT] config_valid
  ∇ [PARAM] summary="all systems operational"
  ∇ [RESULT] message="System health check passed — all systems operational"
Ω
```

</details>

<details><summary><b>Surface 2: Formatted Canonical</b></summary>

```hlf
[HLF-v3]
Δ analyze /config/settings.json
  Ж [CONSTRAINT] tier="hearth"
  Ж [CONSTRAINT] gas_limit=20
  Ж [EXPECT] config_valid
  ∇ [PARAM] summary="all systems operational"
  ∇ [RESULT] message="System health check passed — all systems operational"
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
            "value": "/config/settings.json"
          }
        }
      ],
      "human_readable": "analyze: analyze, /config/settings.json"
    },
    {
      "kind": "glyph_stmt",
      "glyph": "\u0416",
      "tag": "CONSTRAINT",
      "arguments": [
        {
          "kind": "kv_arg",
          "name": "tier",
          "value": {
            "kind": "value",
            "type": "string",
            "value": "hearth"
          }
        }
      ],
      "human_readable": "enforce [CONSTRAINT]: tier=hearth"
    },
    {
      "kind": "glyph_stmt",
      "glyph": "\u0416",
      "tag": "CONSTRAINT",
      "arguments": [
        {
          "kind": "kv_arg",
          "name": "gas_limit",
          "value": {
            "kind": "value",
            "type": "int",
            "value": 20
          }
        }
      ],
      "human_readable": "enforce [CONSTRAINT]: gas_limit=20"
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
            "value": "config_valid"
          }
        }
      ],
      "human_readable": "enforce [EXPECT]: config_valid"
    },
    {
      "kind": "glyph_stmt",
      "glyph": "\u2207",
      "tag": "PARAM",
      "arguments": [
        {
          "kind": "kv_arg",
          "name": "summary",
          "value": {
            "kind": "value",
            "type": "string",
            "value": "all systems operational"
          }
        }
      ],
      "human_readable": "source [PARAM]: summary=all systems operational"
    },
    {
      "kind": "glyph_stmt",
      "glyph": "\u2207",
      "tag": "RESULT",
      "arguments": [
        {
          "kind": "kv_arg",
          "name": "message",
          "value": {
            "kind": "value",
            "type": "string",
            "value": "System health check passed \u2014 all systems operational"
          }
        }
      ],
      "human_readable": "source [RESULT]: message=System health check passed \u2014 all systems operational"
    }
  ],
  "node_count": 6,
  "human_readable": "HLF v3 program with 6 statement(s)",
  "sha256": "650a423b952141f832c0993123d062faac8cfe2a693b98c43152dca9124ad2ac",
  "env": {}
}
```

</details>

<details><summary><b>Surface 4: Bytecode (hex)</b></summary>

```
b53678ac09042026fb51129ddaf62a16bce73ab536b29fc021826d05f7d15103484c4200040042000000598961d70000150000000302000000ce9403360000007b276b696e64273a202776616c7565272c202774797065273a20276964656e74272c202776616c7565273a2027616e616c797a65277d03430000007b276b696e64273a202776616c7565272c202774797065273a202770617468272c202776616c7565273a20272f636f6e6669672f73657474696e67732e6a736f6e277d030f000000d096205b434f4e53545241494e545d03060000006865617274680304000000746965720306000000686561727468030f000000d096205b434f4e53545241494e545d01140000000000000003090000006761735f6c696d6974011400000000000000030b000000d096205b4558504543545d033b0000007b276b696e64273a202776616c7565272c202774797065273a20276964656e74272c202776616c7565273a2027636f6e6669675f76616c6964277d030b000000e28887205b504152414d5d0317000000616c6c2073797374656d73206f7065726174696f6e616c030700000073756d6d6172790317000000616c6c2073797374656d73206f7065726174696f6e616c030c000000e28887205b524553554c545d033600000053797374656d206865616c746820636865636b2070617373656420e2809420616c6c2073797374656d73206f7065726174696f6e616c03070000006d657373616765033600000053797374656d206865616c746820636865636b2070617373656420e2809420616c6c2073797374656d73206f7065726174696f6e616c010100010200510008010400020500010600600300010800020900010a00600700010c00600b00010e00020f00011000010d00011200021300011400011100ff0000
```

</details>

<details><summary><b>Surface 5: Assembly</b></summary>

```asm
  0000  PUSH_CONST         #1  ; "{'kind': 'value', 'type': 'ident', 'value': 'analyze'}"
  0003  PUSH_CONST         #2  ; "{'kind': 'value', 'type': 'path', 'value': '/config/settings.json'}"
  0006  CALL_HOST          #0 (args=2)  ; 'Δ'
  0009  PUSH_CONST         #4  ; 'hearth'
  000C  STORE              #5  ; 'tier'
  000F  PUSH_CONST         #6  ; 'hearth'
  0012  TAG                #3  ; 'Ж [CONSTRAINT]'
  0015  PUSH_CONST         #8  ; 20
  0018  STORE              #9  ; 'gas_limit'
  001B  PUSH_CONST         #10  ; 20
  001E  TAG                #7  ; 'Ж [CONSTRAINT]'
  0021  PUSH_CONST         #12  ; "{'kind': 'value', 'type': 'ident', 'value': 'config_valid'}"
  0024  TAG                #11  ; 'Ж [EXPECT]'
  0027  PUSH_CONST         #14  ; 'all systems operational'
  002A  STORE              #15  ; 'summary'
  002D  PUSH_CONST         #16  ; 'all systems operational'
  0030  PUSH_CONST         #13  ; '∇ [PARAM]'
  0033  PUSH_CONST         #18  ; 'System health check passed — all systems operational'
  0036  STORE              #19  ; 'message'
  0039  PUSH_CONST         #20  ; 'System health check passed — all systems operational'
  003C  PUSH_CONST         #17  ; '∇ [RESULT]'
  003F  HALT
```

</details>

<details><summary><b>Surface 6: English Translation</b></summary>

> HLF v3 program with 6 statement(s): analyze: analyze, /config/settings.json; enforce [CONSTRAINT]: tier=hearth; enforce [CONSTRAINT]: gas_limit=20; enforce [EXPECT]: config_valid; source [PARAM]: summary=all systems operational; source [RESULT]: message=System health check passed — all systems operational.

</details>

---
