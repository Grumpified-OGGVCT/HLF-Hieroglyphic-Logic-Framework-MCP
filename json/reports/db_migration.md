### ✅ db_migration

**File:** `db_migration.hlf` | **Lines:** 11 | **Nodes:** 7 | **Bytecode:** 507B | **Time:** 12.8ms

<details open><summary><b>Surface 1: Glyph Source</b></summary>

```hlf
# HLF v3 — Database Migration
# Execute a production DB migration with schema versioning and verification.
[HLF-v3]
⌘ [DELEGATE] agent="db_agent" goal="migrate"
  ∇ [SOURCE] /data/prod.db
  ∇ [PARAM] schema_version="2.1"
  Ж [ASSERT] table="users"
  Ж [EXPECT] migration_success
SPEC_DEFINE [MIGRATION_SPEC] version="2.1" idempotent=true
SPEC_GATE [MIGRATION_SPEC] rollback_on_fail=true
Ω
```

</details>

<details><summary><b>Surface 2: Formatted Canonical</b></summary>

```hlf
[HLF-v3]
⌘ [DELEGATE] agent="db_agent" goal="migrate"
  ∇ [SOURCE] /data/prod.db
  ∇ [PARAM] schema_version="2.1"
  Ж [ASSERT] table="users"
  Ж [EXPECT] migration_success
SPEC_DEFINE [MIGRATION_SPEC] version="2.1" idempotent=true
SPEC_GATE [MIGRATION_SPEC] rollback_on_fail=true
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
            "value": "db_agent"
          }
        },
        {
          "kind": "kv_arg",
          "name": "goal",
          "value": {
            "kind": "value",
            "type": "string",
            "value": "migrate"
          }
        }
      ],
      "human_readable": "delegate [DELEGATE]: agent=db_agent, goal=migrate"
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
            "value": "/data/prod.db"
          }
        }
      ],
      "human_readable": "source [SOURCE]: /data/prod.db"
    },
    {
      "kind": "glyph_stmt",
      "glyph": "\u2207",
      "tag": "PARAM",
      "arguments": [
        {
          "kind": "kv_arg",
          "name": "schema_version",
          "value": {
            "kind": "value",
            "type": "string",
            "value": "2.1"
          }
        }
      ],
      "human_readable": "source [PARAM]: schema_version=2.1"
    },
    {
      "kind": "glyph_stmt",
      "glyph": "\u0416",
      "tag": "ASSERT",
      "arguments": [
        {

... (truncated) ...
,
      "tag": "MIGRATION_SPEC",
      "arguments": [
        {
          "kind": "kv_arg",
          "name": "rollback_on_fail",
          "value": {
            "kind": "value",
            "type": "ident",
            "value": "true"
          }
        }
      ],
      "human_readable": "spec gate MIGRATION_SPEC"
    }
  ],
  "node_count": 7,
  "human_readable": "HLF v3 program with 7 statement(s)",
  "sha256": "ed2d0c521855acfe829a95e0994c8be7f6e18532ddeaf9f5280ff4dde658e0e8",
  "env": {}
}
```

</details>

<details><summary><b>Surface 4: Bytecode (hex)</b></summary>

```
63292b44033665dfb30b13cb30e2a1de1c277cf5f99754b863aa7b21a2073230484c4200040042000000795bbd79000015000000030e000000e28c98205b44454c45474154455d030800000064625f6167656e7403050000006167656e74030800000064625f6167656e7403070000006d6967726174650304000000676f616c03070000006d696772617465030c000000e28887205b534f555243455d033b0000007b276b696e64273a202776616c7565272c202774797065273a202770617468272c202776616c7565273a20272f646174612f70726f642e6462277d030b000000e28887205b504152414d5d0303000000322e31030e000000736368656d615f76657273696f6e0303000000322e31030b000000d096205b4153534552545d0305000000757365727303050000007461626c6503050000007573657273030b000000d096205b4558504543545d03400000007b276b696e64273a202776616c7565272c202774797065273a20276964656e74272c202776616c7565273a20276d6967726174696f6e5f73756363657373277d030e0000004d4947524154494f4e5f53504543030e0000004d4947524154494f4e5f53504543010100020200010300010400020500010600510008010800010700010a00020b00010c00010900010e00020f00011000600d00011200601100651300661400ff0000
```

</details>

<details><summary><b>Surface 5: Assembly</b></summary>

```asm
  0000  PUSH_CONST         #1  ; 'db_agent'
  0003  STORE              #2  ; 'agent'
  0006  PUSH_CONST         #3  ; 'db_agent'
  0009  PUSH_CONST         #4  ; 'migrate'
  000C  STORE              #5  ; 'goal'
  000F  PUSH_CONST         #6  ; 'migrate'
  0012  CALL_HOST          #0 (args=2)  ; '⌘ [DELEGATE]'
  0015  PUSH_CONST         #8  ; "{'kind': 'value', 'type': 'path', 'value': '/data/prod.db'}"
  0018  PUSH_CONST         #7  ; '∇ [SOURCE]'
  001B  PUSH_CONST         #10  ; '2.1'
  001E  STORE              #11  ; 'schema_version'
  0021  PUSH_CONST         #12  ; '2.1'
  0024  PUSH_CONST         #9  ; '∇ [PARAM]'
  0027  PUSH_CONST         #14  ; 'users'
  002A  STORE              #15  ; 'table'
  002D  PUSH_CONST         #16  ; 'users'
  0030  TAG                #13  ; 'Ж [ASSERT]'
  0033  PUSH_CONST         #18  ; "{'kind': 'value', 'type': 'ident', 'value': 'migration_success'}"
  0036  TAG                #17  ; 'Ж [EXPECT]'
  0039  SPEC_DEFINE        #19  ; 'MIGRATION_SPEC'
  003C  SPEC_GATE          #20  ; 'MIGRATION_SPEC'
  003F  HALT
```

</details>

<details><summary><b>Surface 6: English Translation</b></summary>

> HLF v3 program with 7 statement(s): delegate [DELEGATE]: agent=db_agent, goal=migrate; source [SOURCE]: /data/prod.db; source [PARAM]: schema_version=2.1; enforce [ASSERT]: table=users; enforce [EXPECT]: migration_success; spec define MIGRATION_SPEC; spec gate MIGRATION_SPEC.

</details>

---
