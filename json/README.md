# HLF Program Gallery

> **12/12** fixtures pass the full 5-surface round-trip.
> **12/12** compile to AST successfully.

Each fixture is shown through all 5 canonical surfaces:
1. **Glyph source** — the native HLF program
2. **Formatted source** — canonical whitespace/ordering
3. **AST** — JSON parse tree
4. **Bytecode** — hex-encoded .hlb binary
5. **Assembly** — human-readable disassembly
6. **English** — natural-language translation

## Gallery Index

| Fixture | Lines | Nodes | Bytecode | Status | Time |
| --- | ---: | ---: | ---: | --- | ---: |
| [db_migration](#db-migration) | 11 | 7 | 507B | ✅ full_ok | 12.8ms |
| [decision_matrix](#decision-matrix) | 14 | 10 | 1040B | ✅ full_ok | 1.9ms |
| [delegation](#delegation) | 8 | 4 | 407B | ✅ full_ok | 0.9ms |
| [file_io_demo](#file-io-demo) | 10 | 6 | 709B | ✅ full_ok | 1.2ms |
| [hello_world](#hello-world) | 7 | 3 | 254B | ✅ full_ok | 0.7ms |
| [log_analysis](#log-analysis) | 10 | 6 | 535B | ✅ full_ok | 1.1ms |
| [math_expressions](#math-expressions) | 112 | 44 | 3132B | ✅ full_ok | 12.2ms |
| [module_workflow](#module-workflow) | 12 | 8 | 773B | ✅ full_ok | 1.2ms |
| [routing](#routing) | 7 | 3 | 305B | ✅ full_ok | 0.7ms |
| [security_audit](#security-audit) | 9 | 4 | 418B | ✅ full_ok | 1.0ms |
| [stack_deployment](#stack-deployment) | 9 | 5 | 427B | ✅ full_ok | 0.9ms |
| [system_health_check](#system-health-check) | 10 | 6 | 670B | ✅ full_ok | 1.1ms |

## Benchmark Compression by Domain

Verified benchmark suite (hlf_benchmark_suite) reports **48.6% average compression** across 6 domains:

| Domain | Fixture | Compression |
| --- | --- | ---: |
| General Coding / Baseline | `hello_world.hlf` | 52.3% |
| Security | `security_audit.hlf` | 48.1% |
| AI Engineering / Delegation | `delegation.hlf` | 46.7% |
| Data Engineering | `db_migration.hlf` | 49.2% |
| DevOps / Observability | `log_analysis.hlf` | 45.8% |
| Infrastructure / Deployment | `stack_deployment.hlf` | 49.8% |

> Compression = (1 - HLF_tokens / NLP_tokens) × 100. Higher is better.
> Measured with tiktoken cl100k_base tokenizer.

## Detailed 5-Surface Round-Trips

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

### ✅ decision_matrix

**File:** `decision_matrix.hlf` | **Lines:** 14 | **Nodes:** 10 | **Bytecode:** 1040B | **Time:** 1.9ms

<details open><summary><b>Surface 1: Glyph Source</b></summary>

```hlf
# HLF v3 — Decision Matrix
# Extracted from Sovereign source and adapted to the packaged v3 surface.
[HLF-v3]
Δ [INTENT] goal="decision_matrix"
  ∇ [PARAM] criteria_count=5
  ∇ [PARAM] threshold=7
  Ж [CONSTRAINT] min_voters=3
  Ж [CONSTRAINT] consensus_pct=66
  ⨝ [VOTE] option="option_a" score=8 verdict="selected"
  ⨝ [VOTE] option="option_b" score=6 verdict="deferred"
  ⨝ [VOTE] option="option_c" score=5 verdict="rejected"
  Ж [ASSERT] winning_option="option_a"
  ∇ [RESULT] message="Decision: option_a (score=8, threshold=7)"
Ω
```

</details>

<details><summary><b>Surface 2: Formatted Canonical</b></summary>

```hlf
[HLF-v3]
Δ [INTENT] goal="decision_matrix"
  ∇ [PARAM] criteria_count=5
  ∇ [PARAM] threshold=7
  Ж [CONSTRAINT] min_voters=3
  Ж [CONSTRAINT] consensus_pct=66
  ⨝ [VOTE] option="option_a" score=8 verdict="selected"
  ⨝ [VOTE] option="option_b" score=6 verdict="deferred"
  ⨝ [VOTE] option="option_c" score=5 verdict="rejected"
  Ж [ASSERT] winning_option="option_a"
  ∇ [RESULT] message="Decision: option_a (score=8, threshold=7)"
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
            "value": "decision_matrix"
          }
        }
      ],
      "human_readable": "analyze [INTENT]: goal=decision_matrix"
    },
    {
      "kind": "glyph_stmt",
      "glyph": "\u2207",
      "tag": "PARAM",
      "arguments": [
        {
          "kind": "kv_arg",
          "name": "criteria_count",
          "value": {
            "kind": "value",
            "type": "int",
            "value": 5
          }
        }
      ],
      "human_readable": "source [PARAM]: criteria_count=5"
    },
    {
      "kind": "glyph_stmt",
      "glyph": "\u2207",
      "tag": "PARAM",
      "arguments": [
        {
          "kind": "kv_arg",
          "name": "threshold",
          "value": {
            "kind": "value",
            "type": "int",
            "value": 7
          }
        }
      ],
      "human_readable": "source [PARAM]: threshold=7"
    },
    {
      "kind": "glyph_stmt",
      "glyph": "\u0416",
      "tag": "CONSTRAINT",
      "arguments": [
        {
          "kind": "kv_arg",
          "name": "min_voters",
          "value": {
            "kind": "value",
            "type": "int",
            "value": 3
          }
        }
      ],
      "h
... (truncated) ...
 "kind": "kv_arg",
          "name": "message",
          "value": {
            "kind": "value",
            "type": "string",
            "value": "Decision: option_a (score=8, threshold=7)"
          }
        }
      ],
      "human_readable": "source [RESULT]: message=Decision: option_a (score=8, threshold=7)"
    }
  ],
  "node_count": 10,
  "human_readable": "HLF v3 program with 10 statement(s)",
  "sha256": "6833e7e5b7d9496d67fcb8b6c15f35822f7ffcf1cba36656c82b3113b5cb6565",
  "env": {}
}
```

</details>

<details><summary><b>Surface 4: Bytecode (hex)</b></summary>

```
21c7e48cb08e7dfb47cf68d8b0586e90fc1fd7b4cb21e0aac351bcb8a820a9e5484c42000400b10000007896350b00003a000000030b000000ce94205b494e54454e545d030f0000006465636973696f6e5f6d61747269780304000000676f616c030f0000006465636973696f6e5f6d6174726978030b000000e28887205b504152414d5d010500000000000000030e00000063726974657269615f636f756e74010500000000000000030b000000e28887205b504152414d5d01070000000000000003090000007468726573686f6c64010700000000000000030f000000d096205b434f4e53545241494e545d010300000000000000030a0000006d696e5f766f74657273010300000000000000030f000000d096205b434f4e53545241494e545d014200000000000000030d000000636f6e73656e7375735f706374014200000000000000030a000000e2a89d205b564f54455d03080000006f7074696f6e5f6103060000006f7074696f6e03080000006f7074696f6e5f61010800000000000000030500000073636f7265010800000000000000030800000073656c6563746564030700000076657264696374030800000073656c6563746564030a000000e2a89d205b564f54455d03080000006f7074696f6e5f6203060000006f7074696f6e03080000006f7074696f6e5f62010600000000000000030500000073636f72650106000000000000000308000000646566657272656403070000007665726469637403080000006465666572726564030a000000e2a89d205b564f54455d03080000006f7074696f6e5f6303060000006f7074696f6e03080000006f7074696f6e5f63010500000000000000030500000073636f7265010500000000000000030800000072656a6563746564030700000076657264696374030800000072656a6563746564030b000000d096205b4153534552545d03080000006f7074696f6e5f61030e00000077696e6e696e675f6f7074696f6e03080000006f7074696f6e5f61030c000000e28887205b524553554c545d03290000004465636973696f6e3a206f7074696f6e5f61202873636f72653d382c207468726573686f6c643d372903070000006d65737361676503290000004465636973696f6e3a206f7074696f6e5f61202873636f72653d382c207468726573686f6c643d3729010100020200010300510004010500020600010700010400010900020a00010b00010800010d00020e00010f00600c00011100021200011300601000011500021600011700011800021900011a00011b00021c00011d00611400011f00022000012100012200022300012400012500022600012700611e00012900022a00012b00012c00022d00012e00012f00023000013100612800013300023400013500603200013700023800013900013600ff0000
```

</details>

<details><summary><b>Surface 5: Assembly</b></summary>

```asm
  0000  PUSH_CONST         #1  ; 'decision_matrix'
  0003  STORE              #2  ; 'goal'
  0006  PUSH_CONST         #3  ; 'decision_matrix'
  0009  CALL_HOST          #0 (args=1)  ; 'Δ [INTENT]'
  000C  PUSH_CONST         #5  ; 5
  000F  STORE              #6  ; 'criteria_count'
  0012  PUSH_CONST         #7  ; 5
  0015  PUSH_CONST         #4  ; '∇ [PARAM]'
  0018  PUSH_CONST         #9  ; 7
  001B  STORE              #10  ; 'threshold'
  001E  PUSH_CONST         #11  ; 7
  0021  PUSH_CONST         #8  ; '∇ [PARAM]'
  0024  PUSH_CONST         #13  ; 3
  0027  STORE              #14  ; 'min_voters'
  002A  PUSH_CONST         #15  ; 3
  002D  TAG                #12  ; 'Ж [CONSTRAINT]'
  0030  PUSH_CONST         #17  ; 66
  0033  STORE              #18  ; 'consensus_pct'
  0036  PUSH_CONST         #19  ; 66
  0039  TAG                #16  ; 'Ж [CONSTRAINT]'
  003C  PUSH_CONST         #21  ; 'option_a'
  003F  STORE              #22  ; 'option'
  0042  PUSH_CONST         #23  ; 'option_a'
  0045  PUSH_CONST         #24  ; 8
  0048  STORE              #25  ; 'score'
  004B  PUSH_CONST         #26  ; 8
  004E  PUSH_CONST         #27  ; 'selected'
  0051  STORE              #28  ; 'verdict'
  0054  PUSH_CONST         #29  ; 'selected'
  0057  INTENT             #20  ; '⨝ [VOTE]'
  005A  PUSH_CONST         #31  ; 'option_b'
  005D  STORE              #32  ; 'option'
  0060  PUSH_CONST         #33  ; 'option_b'
  0063  PUSH_CONST         #34  ; 6
  0066  STORE              #35  ; 'score'
  0069  PUSH_CONST         #36  ; 6
  006C  PUSH_CONST         #37  ; 'deferred'
  006F  STORE              #38  ; 'verdict'
  0072  PUSH_CONST         #39  ; 'deferred'
  0075  INTENT             #30  ; '⨝ [VOTE]'
  0078  PUSH_CONST         #41  ; 'option_c'
  007B  STORE              #42  ; 'option'
  007E  PUSH_CONST         #43  ; 'option_c'
  0081  PUSH_CONST         #44  ; 5
  0084  STORE              #45  ; 'score'
  0087  PUSH_CONST         #46  ; 5
  008A  PUSH_CONST         #47  ; 'rejected'
  008D  STORE              #48  ; 'verdict'
  0090  PUSH_CONST         #49  ; 'rejected'
  0093  INTENT             #40  ; '⨝ [VOTE]'
  0096  PUSH_CONST         #51  ; 'option_a'
  0099  STORE              #52  ; 'winning_option'
  009C  PUSH_CONST         #53  ; 'option_a'
  009F  TAG                #50  ; 'Ж [ASSERT]'
  00A2  PUSH_CONST         #55  ; 'Decision: option_a (score=8, threshold=7)'
  00A5  STORE              #56  ; 'message'
  00A8  PUSH_CONST         #57  ; 'Decision: option_a (score=8, threshold=7)'
  00AB  PUSH_CONST         #54  ; '∇ [RESULT]'
  00AE  HALT
```

</details>

<details><summary><b>Surface 6: English Translation</b></summary>

> HLF v3 program with 10 statement(s): analyze [INTENT]: goal=decision_matrix; source [PARAM]: criteria_count=5; source [PARAM]: threshold=7; enforce [CONSTRAINT]: min_voters=3; enforce [CONSTRAINT]: consensus_pct=66; consensus [VOTE]: option=option_a, score=8, verdict=selected; consensus [VOTE]: option=option_b, score=6, verdict=deferred; consensus [VOTE]: option=option_c, score=5, verdict=rejected; enforce [ASSERT]: winning_option=option_a; source [RESULT]: message=Decision: option_a (score=8, threshold=7).

</details>

---

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

### ✅ file_io_demo

**File:** `file_io_demo.hlf` | **Lines:** 10 | **Nodes:** 6 | **Bytecode:** 709B | **Time:** 1.2ms

<details open><summary><b>Surface 1: Glyph Source</b></summary>

```hlf
# HLF v3 — File I/O Demo
# Extracted from Sovereign source and adapted to the packaged v3 surface.
[HLF-v3]
⌘ [ACTION] verb="write_file" target="test_output.txt"
  ∇ [PARAM] content="Hello from HLF runtime!"
  Ж [EXPECT] write_complete
⌘ [ACTION] verb="read_file" target="test_output.txt"
  Ж [EXPECT] round_trip_verified
  ∇ [RESULT] message="File I/O demo completed successfully"
Ω
```

</details>

<details><summary><b>Surface 2: Formatted Canonical</b></summary>

```hlf
[HLF-v3]
⌘ [ACTION] verb="write_file" target="test_output.txt"
  ∇ [PARAM] content="Hello from HLF runtime!"
  Ж [EXPECT] write_complete
⌘ [ACTION] verb="read_file" target="test_output.txt"
  Ж [EXPECT] round_trip_verified
  ∇ [RESULT] message="File I/O demo completed successfully"
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
      "tag": "ACTION",
      "arguments": [
        {
          "kind": "kv_arg",
          "name": "verb",
          "value": {
            "kind": "value",
            "type": "string",
            "value": "write_file"
          }
        },
        {
          "kind": "kv_arg",
          "name": "target",
          "value": {
            "kind": "value",
            "type": "string",
            "value": "test_output.txt"
          }
        }
      ],
      "human_readable": "delegate [ACTION]: verb=write_file, target=test_output.txt"
    },
    {
      "kind": "glyph_stmt",
      "glyph": "\u2207",
      "tag": "PARAM",
      "arguments": [
        {
          "kind": "kv_arg",
          "name": "content",
          "value": {
            "kind": "value",
            "type": "string",
            "value": "Hello from HLF runtime!"
          }
        }
      ],
      "human_readable": "source [PARAM]: content=Hello from HLF runtime!"
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
            "value": "write_complete"
          }
        }
      ],
      "human_readable": "enforce [EXPECT]: write_complete"
    },
    {
      "kind": "glyph_stmt",
      "glyph": "\u2318",
      
... (truncated) ...
 {
          "kind": "kv_arg",
          "name": "message",
          "value": {
            "kind": "value",
            "type": "string",
            "value": "File I/O demo completed successfully"
          }
        }
      ],
      "human_readable": "source [RESULT]: message=File I/O demo completed successfully"
    }
  ],
  "node_count": 6,
  "human_readable": "HLF v3 program with 6 statement(s)",
  "sha256": "b98f5d1f3f4ba86ed574d3191171c5f937adb08bb0ebedcaac3d40fd7cd68724",
  "env": {}
}
```

</details>

<details><summary><b>Surface 4: Bytecode (hex)</b></summary>

```
b7146990331b9b399be728b65678368a9b2e8932344e5ba394c973b046e162bc484c4200040051000000c276733200001a000000030c000000e28c98205b414354494f4e5d030a00000077726974655f66696c65030400000076657262030a00000077726974655f66696c65030f000000746573745f6f75747075742e7478740306000000746172676574030f000000746573745f6f75747075742e747874030b000000e28887205b504152414d5d031700000048656c6c6f2066726f6d20484c462072756e74696d65210307000000636f6e74656e74031700000048656c6c6f2066726f6d20484c462072756e74696d6521030b000000d096205b4558504543545d033d0000007b276b696e64273a202776616c7565272c202774797065273a20276964656e74272c202776616c7565273a202777726974655f636f6d706c657465277d030c000000e28c98205b414354494f4e5d0309000000726561645f66696c650304000000766572620309000000726561645f66696c65030f000000746573745f6f75747075742e7478740306000000746172676574030f000000746573745f6f75747075742e747874030b000000d096205b4558504543545d03420000007b276b696e64273a202776616c7565272c202774797065273a20276964656e74272c202776616c7565273a2027726f756e645f747269705f7665726966696564277d030c000000e28887205b524553554c545d032400000046696c6520492f4f2064656d6f20636f6d706c65746564207375636365737366756c6c7903070000006d657373616765032400000046696c6520492f4f2064656d6f20636f6d706c65746564207375636365737366756c6c79010100020200010300010400020500010600510008010800020900010a00010700010c00600b00010e00020f00011000011100021200011300510d08011500601400011700021800011900011600ff0000
```

</details>

<details><summary><b>Surface 5: Assembly</b></summary>

```asm
  0000  PUSH_CONST         #1  ; 'write_file'
  0003  STORE              #2  ; 'verb'
  0006  PUSH_CONST         #3  ; 'write_file'
  0009  PUSH_CONST         #4  ; 'test_output.txt'
  000C  STORE              #5  ; 'target'
  000F  PUSH_CONST         #6  ; 'test_output.txt'
  0012  CALL_HOST          #0 (args=2)  ; '⌘ [ACTION]'
  0015  PUSH_CONST         #8  ; 'Hello from HLF runtime!'
  0018  STORE              #9  ; 'content'
  001B  PUSH_CONST         #10  ; 'Hello from HLF runtime!'
  001E  PUSH_CONST         #7  ; '∇ [PARAM]'
  0021  PUSH_CONST         #12  ; "{'kind': 'value', 'type': 'ident', 'value': 'write_complete'}"
  0024  TAG                #11  ; 'Ж [EXPECT]'
  0027  PUSH_CONST         #14  ; 'read_file'
  002A  STORE              #15  ; 'verb'
  002D  PUSH_CONST         #16  ; 'read_file'
  0030  PUSH_CONST         #17  ; 'test_output.txt'
  0033  STORE              #18  ; 'target'
  0036  PUSH_CONST         #19  ; 'test_output.txt'
  0039  CALL_HOST          #13 (args=2)  ; '⌘ [ACTION]'
  003C  PUSH_CONST         #21  ; "{'kind': 'value', 'type': 'ident', 'value': 'round_trip_verified'}"
  003F  TAG                #20  ; 'Ж [EXPECT]'
  0042  PUSH_CONST         #23  ; 'File I/O demo completed successfully'
  0045  STORE              #24  ; 'message'
  0048  PUSH_CONST         #25  ; 'File I/O demo completed successfully'
  004B  PUSH_CONST         #22  ; '∇ [RESULT]'
  004E  HALT
```

</details>

<details><summary><b>Surface 6: English Translation</b></summary>

> HLF v3 program with 6 statement(s): delegate [ACTION]: verb=write_file, target=test_output.txt; source [PARAM]: content=Hello from HLF runtime!; enforce [EXPECT]: write_complete; delegate [ACTION]: verb=read_file, target=test_output.txt; enforce [EXPECT]: round_trip_verified; source [RESULT]: message=File I/O demo completed successfully.

</details>

---

### ✅ hello_world

**File:** `hello_world.hlf` | **Lines:** 7 | **Nodes:** 3 | **Bytecode:** 254B | **Time:** 0.7ms

<details open><summary><b>Surface 1: Glyph Source</b></summary>

```hlf
# HLF v3 — Hello World
# Minimal conformance test: header, one primary intent, assertion, result, terminator.
[HLF-v3]
Δ [INTENT] goal="hello_world"
  Ж [ASSERT] status="ok"
  ∇ [RESULT] message="Hello, World!"
Ω
```

</details>

<details><summary><b>Surface 2: Formatted Canonical</b></summary>

```hlf
[HLF-v3]
Δ [INTENT] goal="hello_world"
  Ж [ASSERT] status="ok"
  ∇ [RESULT] message="Hello, World!"
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
            "value": "hello_world"
          }
        }
      ],
      "human_readable": "analyze [INTENT]: goal=hello_world"
    },
    {
      "kind": "glyph_stmt",
      "glyph": "\u0416",
      "tag": "ASSERT",
      "arguments": [
        {
          "kind": "kv_arg",
          "name": "status",
          "value": {
            "kind": "value",
            "type": "string",
            "value": "ok"
          }
        }
      ],
      "human_readable": "enforce [ASSERT]: status=ok"
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
            "value": "Hello, World!"
          }
        }
      ],
      "human_readable": "source [RESULT]: message=Hello, World!"
    }
  ],
  "node_count": 3,
  "human_readable": "HLF v3 program with 3 statement(s)",
  "sha256": "9c90c09f7e3d0d1b65abbd012250be569f9e4718b15551efa8f905fa942be844",
  "env": {}
}
```

</details>

<details><summary><b>Surface 4: Bytecode (hex)</b></summary>

```
14bc5934a6622e94474b3e95bf49250c9cee7089ba522aa722dd92d32bb9de4b484c42000400270000006ad86c3000000c000000030b000000ce94205b494e54454e545d030b00000068656c6c6f5f776f726c640304000000676f616c030b00000068656c6c6f5f776f726c64030b000000d096205b4153534552545d03020000006f6b030600000073746174757303020000006f6b030c000000e28887205b524553554c545d030d00000048656c6c6f2c20576f726c642103070000006d657373616765030d00000048656c6c6f2c20576f726c6421010100020200010300510004010500020600010700600400010900020a00010b00010800ff0000
```

</details>

<details><summary><b>Surface 5: Assembly</b></summary>

```asm
  0000  PUSH_CONST         #1  ; 'hello_world'
  0003  STORE              #2  ; 'goal'
  0006  PUSH_CONST         #3  ; 'hello_world'
  0009  CALL_HOST          #0 (args=1)  ; 'Δ [INTENT]'
  000C  PUSH_CONST         #5  ; 'ok'
  000F  STORE              #6  ; 'status'
  0012  PUSH_CONST         #7  ; 'ok'
  0015  TAG                #4  ; 'Ж [ASSERT]'
  0018  PUSH_CONST         #9  ; 'Hello, World!'
  001B  STORE              #10  ; 'message'
  001E  PUSH_CONST         #11  ; 'Hello, World!'
  0021  PUSH_CONST         #8  ; '∇ [RESULT]'
  0024  HALT
```

</details>

<details><summary><b>Surface 6: English Translation</b></summary>

> HLF v3 program with 3 statement(s): analyze [INTENT]: goal=hello_world; enforce [ASSERT]: status=ok; source [RESULT]: message=Hello, World!.

</details>

---

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

### ✅ math_expressions

**File:** `math_expressions.hlf` | **Lines:** 112 | **Nodes:** 44 | **Bytecode:** 3132B | **Time:** 12.2ms

<details open><summary><b>Surface 1: Glyph Source</b></summary>

```hlf
# HLF v3 — Governing Algorithm Fixture
# Exercises the specific formulas and algorithms that HLF uses internally:
#   Gas budget verification, salience scoring, compression ratio,
#   similarity thresholds, entropy drift policy, Merkle chain linkage.
# Each ASSIGN and IF maps to a real HLF governing computation.
[HLF-v3]

# ── Gas Budget Verification ──────────────────────────────────────────────────
# Real formula: total_gas = sum(op_gas) per statement, checked against tier max.
# Capsule tier budgets: hearth=100, forge=500, sovereign=1000.
# Host function gas: hash_sha256=2, merkle_chain=3, cosine_similarity=2,
#   formal_verify=10, memory_store=5, memory_recall=5, summarize=8, embed_text=5.
ASSIGN hash_gas = 2
ASSIGN merkle_gas = 3
ASSIGN similarity_gas = 2
ASSIGN verify_gas = 10
ASSIGN audit_pipeline_gas = hash_gas + merkle_gas + similarity_gas + verify_gas
ASSIGN hearth_max = 100
ASSIGN forge_max = 500
IF audit_pipeline_gas <= hearth_max {
  Δ [INTENT] goal="gas_budget_hearth_ok"
}
IF audit_pipeline_gas <= forge_max {
  Δ [INTENT] goal="gas_budget_forge_ok"
}

# ── Salience Scoring ─────────────────────────────────────────────────────────
# Real formula from rag/memory.py _compute_salience_score():
#   score = confidence*0.25 + groundedness*0.25 + citation_coverage*0.2
#         + freshness*0.15 + provenance*0.15 + semantic_bonus + promotion_bonus
# Archive threshold: score < 0.45 → eligible for long-term archival.
ASSIGN confidence = 8
ASSIGN groundedness = 9
ASSIGN citation_coverage = 7
ASSIGN freshness = 10
ASSIGN provenance = 10
ASSIGN weighted_score = confidence * 25 + groundedness * 25 + citation_coverage * 20 + freshness * 15 + provenance * 15
ASSIGN archive_threshold = 450
IF weighted_score >= archive_threshold {
  Δ [INTENT] goal="salience_above_archive_threshold"
}

# ── Token Compression Ratio ──────────────────────────────────────────────────
# Real formula from hlf/benchmark.py:
#   compression_pct = hlf_tokens * 100 / nlp_tokens
# HLF claims 12-30% compression over equivalent NLP (tiktoken cl100k_base).
ASSIGN hlf_tokens = 42
ASSIGN nlp_tokens = 58
ASSIGN compression_pct = hlf_tokens * 100 / nlp_tokens
ASSIGN target_ceiling = 88
IF compression_pct <= target_ceiling {
  Δ [INTENT] goal="compression_ratio_within_target"
}

# ── Similarity Gate Thresholds ───────────────────────────────────────────────
# Real thresholds:
#   Dedup gate:    cosine > 0.98 → block duplicate storage
#   Entropy anchor: cosine >= 0.95 → no drift
#   InsAIts round-trip: cosine >= 0.95 → semantic fidelity preserved
# Scaled to integer percentages for expression system.
ASSIGN similarity_score = 96
ASSIGN dedup_threshold = 98
ASSIGN drift_threshold = 95
IF similarity_score >= drift_threshold {
  Δ [INTENT] goal="entropy_anchor_no_drift"
}
IF similarity_score < dedup_threshold {
  Δ [INTENT] goal="dedup_gate_allows_storage"
}

# ── Entropy Drift Policy ─────────────────────────────────────────────────────
# Real policy from hlf/entropy_anchor.py:
#   default_threshold = 50 (0.5 scaled)
#   high_risk_threshold = 65 (0.65 scaled)
#   drift_detected = similarity < threshold → escalate
ASSIGN observed_similarity = 48
ASSIGN default_threshold = 50
ASSIGN high_risk_threshold = 65
IF observed_similarity < default_threshold {
  Δ [INTENT] goal="drift_detected_escalate"
}
IF observed_similarity < high_risk_threshold {
  Δ [INTENT] goal="drift_high_risk_halt_branch"
}

# ── Governance Retrieval Thresholds ──────────────────────────────────────────
# Real thresholds from rag/memory.py retrieval purpose policies:
#   translation_memory: min_rank_score = 12 (0.12 scaled to 100)
#   routing_evidence:   min_rank_score = 35 (0.35 scaled)
#   verifier_evidence:  min_rank_score = 30 (0.30 scaled)
ASSIGN query_rank = 28
ASSIGN translation_min = 12
ASSIGN routing_min = 35
ASSIGN verifier_min = 30
IF query_rank >= translation_min AND query_rank < routing_min {
  Δ [INTENT] goal="qualifies_translation_not_routing"
}

# ── Capsule Gas Boundary Check ───────────────────────────────────────────────
# Validates that a proposed operation chain fits within the capsule tier.
# memory_store=5, memory_recall=5, embed_text=5, cosine_similarity=2 = 17 total
ASSIGN mem_store = 5
ASSIGN mem_recall = 5
ASSIGN embed = 5
ASSIGN cosine = 2
ASSIGN rag_pipeline_gas = mem_store + mem_recall + embed + cosine
IF rag_pipeline_gas <= hearth_max {
  Δ [INTENT] goal="rag_pipeline_fits_hearth"
}

∇ [RESULT] message="governing_algorithms_validated"
Ω
```

</details>

<details><summary><b>Surface 2: Formatted Canonical</b></summary>

```hlf
[HLF-v3]
ASSIGN hash_gas = 2
ASSIGN merkle_gas = 3
ASSIGN similarity_gas = 2
ASSIGN verify_gas = 10
ASSIGN audit_pipeline_gas = hash_gas + merkle_gas + similarity_gas + verify_gas
ASSIGN hearth_max = 100
ASSIGN forge_max = 500
IF audit_pipeline_gas <= hearth_max {
Δ [INTENT] goal="gas_budget_hearth_ok"
}
IF audit_pipeline_gas <= forge_max {
Δ [INTENT] goal="gas_budget_forge_ok"
}
ASSIGN confidence = 8
ASSIGN groundedness = 9
ASSIGN citation_coverage = 7
ASSIGN freshness = 10
ASSIGN provenance = 10
ASSIGN weighted_score = confidence * 25 + groundedness * 25 + citation_coverage * 20 + freshness * 15 + provenance * 15
ASSIGN archive_threshold = 450
IF weighted_score >= archive_threshold {
Δ [INTENT] goal="salience_above_archive_threshold"
}
ASSIGN hlf_tokens = 42
ASSIGN nlp_tokens = 58
ASSIGN compression_pct = hlf_tokens * 100 / nlp_tokens
ASSIGN target_ceiling = 88
IF compression_pct <= target_ceiling {
Δ [INTENT] goal="compression_ratio_within_target"
}
ASSIGN similarity_score = 96
ASSIGN dedup_threshold = 98
ASSIGN drift_threshold = 95
IF similarity_score >= drift_threshold {
Δ [INTENT] goal="entropy_anchor_no_drift"
}
IF similarity_score < dedup_threshold {
Δ [INTENT] goal="dedup_gate_allows_storage"
}
ASSIGN observed_similarity = 48
ASSIGN default_threshold = 50
ASSIGN high_risk_threshold = 65
IF observed_similarity < default_threshold {
Δ [INTENT] goal="drift_detected_escalate"
}
IF observed_similarity < high_risk_threshold {
Δ [INTENT] goal="drift_high_risk_halt_branch"
}
ASSIGN query_rank = 28
ASSIGN translation_min = 12
ASSIGN routing_min = 35
ASSIGN verifier_min = 30
IF query_rank >= translation_min AND query_rank < routing_min {
Δ [INTENT] goal="qualifies_translation_not_routing"
}
ASSIGN mem_store = 5
ASSIGN mem_recall = 5
ASSIGN embed = 5
ASSIGN cosine = 2
ASSIGN rag_pipeline_gas = mem_store + mem_recall + embed + cosine
IF rag_pipeline_gas <= hearth_max {
Δ [INTENT] goal="rag_pipeline_fits_hearth"
}
  ∇ [RESULT] message="governing_algorithms_validated"
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
      "kind": "assign_stmt",
      "name": "hash_gas",
      "expr": {
        "kind": "value",
        "type": "int",
        "value": 2
      },
      "human_readable": "assign (mutable) hash_gas = 2"
    },
    {
      "kind": "assign_stmt",
      "name": "merkle_gas",
      "expr": {
        "kind": "value",
        "type": "int",
        "value": 3
      },
      "human_readable": "assign (mutable) merkle_gas = 3"
    },
    {
      "kind": "assign_stmt",
      "name": "similarity_gas",
      "expr": {
        "kind": "value",
        "type": "int",
        "value": 2
      },
      "human_readable": "assign (mutable) similarity_gas = 2"
    },
    {
      "kind": "assign_stmt",
      "name": "verify_gas",
      "expr": {
        "kind": "value",
        "type": "int",
        "value": 10
      },
      "human_readable": "assign (mutable) verify_gas = 10"
    },
    {
      "kind": "assign_stmt",
      "name": "audit_pipeline_gas",
      "expr": {
        "kind": "binop",
        "op": "+",
        "left": {
          "kind": "binop",
          "op": "+",
          "left": {
            "kind": "binop",
            "op": "+",
            "left": {
              "kind": "value",
              "type": "ident",
              "value": "hash_gas"
            },
            "right": {
              "kind": "value",
              "type": "ident",
              "value": "merkle_gas"
            }
          },
     
... (truncated) ...
 [
        {
          "kind": "kv_arg",
          "name": "message",
          "value": {
            "kind": "value",
            "type": "string",
            "value": "governing_algorithms_validated"
          }
        }
      ],
      "human_readable": "source [RESULT]: message=governing_algorithms_validated"
    }
  ],
  "node_count": 44,
  "human_readable": "HLF v3 program with 44 statement(s)",
  "sha256": "a02da4282df62087f505d0087e1f24d8cefd9db9d889b41a2c38fb765caa97fe",
  "env": {}
}
```

</details>

<details><summary><b>Surface 4: Bytecode (hex)</b></summary>

```
9020aa0b2c17da320c2375ac8e05bcadab8c5be4afe47bd8917bd84e922003d3484c42000400370200008da906df0000950000000102000000000000000308000000686173685f676173010300000000000000030a0000006d65726b6c655f676173010200000000000000030e00000073696d696c61726974795f676173010a00000000000000030a0000007665726966795f6761730308000000686173685f676173030a0000006d65726b6c655f676173030e00000073696d696c61726974795f676173030a0000007665726966795f676173031200000061756469745f706970656c696e655f676173016400000000000000030a0000006865617274685f6d617801f4010000000000000309000000666f7267655f6d6178031200000061756469745f706970656c696e655f676173030a0000006865617274685f6d6178030b000000ce94205b494e54454e545d03140000006761735f6275646765745f6865617274685f6f6b0304000000676f616c03140000006761735f6275646765745f6865617274685f6f6b031200000061756469745f706970656c696e655f6761730309000000666f7267655f6d6178030b000000ce94205b494e54454e545d03130000006761735f6275646765745f666f7267655f6f6b0304000000676f616c03130000006761735f6275646765745f666f7267655f6f6b010800000000000000030a000000636f6e666964656e6365010900000000000000030c00000067726f756e6465646e65737301070000000000000003110000006369746174696f6e5f636f766572616765010a00000000000000030900000066726573686e657373010a00000000000000030a00000070726f76656e616e6365030a000000636f6e666964656e6365011900000000000000030c00000067726f756e6465646e65737301190000000000000003110000006369746174696f6e5f636f766572616765011400000000000000030900000066726573686e657373010f00000000000000030a00000070726f76656e616e6365010f00000000000000030e00000077656967687465645f73636f726501c2010000000000000311000000617263686976655f7468726573686f6c64030e00000077656967687465645f73636f72650311000000617263686976655f7468726573686f6c64030b000000ce94205b494e54454e545d032000000073616c69656e63655f61626f76655f617263686976655f7468726573686f6c640304000000676f616c032000000073616c69656e63655f61626f76655f617263686976655f7468726573686f6c64012a00000000000000030a000000686c665f746f6b656e73013a00000000000000030a0000006e6c705f746f6b656e73030a000000686c665f746f6b656e73016400000000000000030a0000006e6c705f746f6b656e73030f000000636f6d7072657373696f6e5f706374015800000000000000030e0000007461726765745f6365696c696e67030f000000636f6d7072657373696f6e5f706374030e0000007461726765745f6365696c696e67030b000000ce94205b494e54454e545d031f000000636f6d7072657373696f6e5f726174696f5f77697468696e5f7461726765740304000000676f616c031f000000636f6d7072657373696f6e5f726174696f5f77697468696e5f746172676574016000000000000000031000000073696d696c61726974795f73636f7265016200000000000000030f00000064656475705f7468726573686f6c64015f00000000000000030f00000064726966745f7468726573686f6c64031000000073696d696c61726974795f73636f7265030f00000064726966745f7468726573686f6c64030b000000ce94205b494e54454e545d0317000000656e74726f70795f616e63686f725f6e6f5f64726966740304000000676f616c0317000000656e74726f70795f616e63686f725f6e6f5f6472696674031000000073696d696c61726974795f73636f7265030f00000064656475705f7468726573686f6c64030b000000ce94205b494e54454e545d031900000064656475705f676174655f616c6c6f77735f73746f726167650304000000676f616c031900000064656475705f676174655f616c6c6f77735f73746f7261676501300000000000000003130000006f627365727665645f73696d696c6172697479013200000000000000031100000064656661756c745f7468726573686f6c640141000000000000000313000000686967685f7269736b5f7468726573686f6c6403130000006f627365727665645f73696d696c6172697479031100000064656661756c745f7468726573686f6c64030b000000ce94205b494e54454e545d031700000064726966745f64657465637465645f657363616c6174650304000000676f616c031700000064726966745f64657465637465645f657363616c61746503130000006f627365727665645f73696d696c61726974790313000000686967685f7269736b5f7468726573686f6c64030b000000ce94205b494e54454e545d031b00000064726966745f686967685f7269736b5f68616c745f6272616e63680304000000676f616c031b00000064726966745f686967685f7269736b5f68616c745f6272616e6368011c00000000000000030a00000071756572795f72616e6b010c00000000000000030f0000007472616e736c6174696f6e5f6d696e012300000000000000030b000000726f7574696e675f6d696e011e00000000000000030c00000076657269666965725f6d696e030a00000071756572795f72616e6b030f0000007472616e736c6174696f6e5f6d696e030a00000071756572795f72616e6b030b000000726f7574696e675f6d696e030b000000ce94205b494e54454e545d03210000007175616c69666965735f7472616e736c6174696f6e5f6e6f745f726f7574696e670304000000676f616c03210000007175616c69666965735f7472616e736c6174696f6e5f6e6f745f726f7574696e6701050000000000000003090000006d656d5f73746f7265010500000000000000030a0000006d656d5f726563616c6c0105000000000000000305000000656d6265640102000000000000000306000000636f73696e6503090000006d656d5f73746f7265030a0000006d656d5f726563616c6c0305000000656d6265640306000000636f73696e6503100000007261675f706970656c696e655f67617303100000007261675f706970656c696e655f676173030a0000006865617274685f6d6178030b000000ce94205b494e54454e545d03180000007261675f706970656c696e655f666974735f6865617274680304000000676f616c03180000007261675f706970656c696e655f666974735f686561727468030c000000e28887205b524553554c545d031e000000676f7665726e696e675f616c676f726974686d735f76616c69646174656403070000006d657373616765031e000000676f7665726e696e675f616c676f726974686d735f76616c696461746564010000020100010200020300010400020500010600020700030800030900100000030a00100000030b00100000020c00010d00020e00010f00021000031100031200230000415400011400021500011600511304031700031800230000416c00011a00021b00011c00511904011d00021e00011f00022000012100022200012300022400012500022600032700012800120000032900012a00120000100000032b00012c00120000100000032d00012e00120000100000032f0001300012000010000002310001320002330003340003350025000041e400013700023800013900513604013a00023b00013c00023d00033e00013f00120000034000130000024100014200024300034400034500230000412001014700024800014900514604014a00024b00014c00024d00014e00024f00035000035100250000414a01015300025400015500515204035600035700220000416201015900025a00015b00515804015c00025d00015e00025f00016000026100036200036300220000418c0101650002660001670051640403680003690022000041a401016b00026c00016d00516a04016e00026f0001700002710001720002730001740002750003760003770025000003780003790022000030000041e001017b00027c00017d00517a04017e00027f00018000028100018200028300018400028500038600038700100000038800100000038900100000028a00038b00038c00230000412802018e00028f00019000518d04019200029300019400019100ff0000
```

</details>

<details><summary><b>Surface 5: Assembly</b></summary>

```asm
  0000  PUSH_CONST         #0  ; 2
  0003  STORE              #1  ; 'hash_gas'
  0006  PUSH_CONST         #2  ; 3
  0009  STORE              #3  ; 'merkle_gas'
  000C  PUSH_CONST         #4  ; 2
  000F  STORE              #5  ; 'similarity_gas'
  0012  PUSH_CONST         #6  ; 10
  0015  STORE              #7  ; 'verify_gas'
  0018  LOAD               #8  ; 'hash_gas'
  001B  LOAD               #9  ; 'merkle_gas'
  001E  ADD
  0021  LOAD               #10  ; 'similarity_gas'
  0024  ADD
  0027  LOAD               #11  ; 'verify_gas'
  002A  ADD
  002D  STORE              #12  ; 'audit_pipeline_gas'
  0030  PUSH_CONST         #13  ; 100
  0033  STORE              #14  ; 'hearth_max'
  0036  PUSH_CONST         #15  ; 500
  0039  STORE              #16  ; 'forge_max'
  003C  LOAD               #17  ; 'audit_pipeline_gas'
  003F  LOAD               #18  ; 'hearth_max'
  0042  CMP_LE
  0045  JZ                 #84  ; 'goal'
  0048  PUSH_CONST         #20  ; 'gas_budget_hearth_ok'
  004B  STORE              #21  ; 'goal'
  004E  PUSH_CONST         #22  ; 'gas_budget_hearth_ok'
  0051  CALL_HOST          #19 (args=1)  ; 'Δ [INTENT]'
  0054  LOAD               #23  ; 'audit_pipeline_gas'
  0057  LOAD               #24  ; 'forge_max'
  005A  CMP_LE
  005D  JZ                 #108  ; 'goal'
  0060  PUSH_CONST         #26  ; 'gas_budget_forge_ok'
  0063  STORE              #27  ; 'goal'
  0066  PUSH_CONST         #28  ; 'gas_budget_forge_ok'
  0069  CALL_HOST          #25 (args=1)  ; 'Δ [INTENT]'
  006C  PUSH_CONST         #29  ; 8
  006F  STORE              #30  ; 'confidence'
  0072  PUSH_CONST         #31  ; 9
  0075  STORE              #32  ; 'groundedness'
  0078  PUSH_CONST         #33  ; 7
  007B  STORE              #34  ; 'citation_coverage'
  007E  PUSH_CONST         #35  ; 10
  0081  STORE              #36  ; 'freshness'
  0084  PUSH_CONST         #37  ; 10
  0087  STORE              #38  ; 'provenance'
  008A  LOAD               #39  ; 'confidence'
  008D  PUSH_CONST         #40  ; 25
  0090  MUL
  0093  LOAD               #41  ; 'groundedness'
  0096  PUSH_CONST         #42  ; 25
  0099  MUL
  009C  ADD
  009F  LOAD               #43  ; 'citation_coverage'
  00A2  PUSH_CONST         #44  ; 20
  00A5  MUL
  00A8  ADD
  00AB  LOAD               #45  ; 'freshness'
  00AE  PUSH_CONST         #46  ; 15
  00B1  MUL
  00B4  ADD
  00B7  LOAD               #47  ; 'provenance'
  00BA  PUSH_CONST         #48  ; 15
  00BD  MUL
  00C0  ADD
  00C3  STORE              #49  ; 'weighted_score'
  00C6  PUSH_CONST         #50  ; 450
  00C9  STORE              #51  ; 'archive_threshold'
  00CC  LOAD               #52  ; 'weighted_score'
  00CF  LOAD               #53  ; 'archive_threshold'
  00D2  CMP_GE
  00D5  JZ                 #228  ; None
  00D8  PUSH_CONST         #55  ; 'salience_above_archive_threshold'
  00DB  STORE              #56  ; 'goal'
  00DE  PUSH_CONST         #57  ; 'salience_above_archive_threshold'
  00E1  CALL_HOST          #54 (args=1)  ; 'Δ [INTENT]'
  00E4  PUSH_CONST         #58  ; 42
  00E7  STORE              #59  ; 'hlf_tokens'
  00EA  PUSH_CONST         #60  ; 58
  00ED  STORE              #61  ; 'nlp_tokens'
  00F0  LOAD               #62  ; 'hlf_tokens'
  00F3  PUSH_CONST         #63  ; 100
  00F6  MUL
  00F9  LOAD               #64  ; 'nlp_tokens'
  00FC  DIV
  00FF  STORE              #65  ; 'compression_pct'
  0102  PUSH_CONST         #66  ; 88
  0105  STORE              #67  ; 'target_ceiling'
  0108  LOAD               #68  ; 'compression_pct'
  010B  LOAD               #69  ; 'target_ceiling'
  010E  CMP_LE
  0111  JZ                 #288  ; None
  0114  PUSH_CONST         #71  ; 'compression_ratio_within_target'
  0117  STORE              #72  ; 'goal'
  011A  PUSH_CONST         #73  ; 'compression_ratio_within_target'
  011D  CALL_HOST          #70 (args=1)  ; 'Δ [INTENT]'
  0120  PUSH_CONST         #74  ; 96
  0123  STORE              #75  ; 'similarity_score'
  0126  PUSH_CONST         #76  ; 98
  0129  STORE              #77  ; 'dedup_threshold'
  012C  PUSH_CONST         #78  ; 95
  012F  STORE              #79  ; 'drift_threshold'
  0132  LOAD               #80  ; 'similarity_score'
  0135  LOAD               #81  ; 'drift_threshold'
  0138  CMP_GE
  013B  JZ                 #330  ; None
  013E  PUSH_CONST         #83  ; 'entropy_anchor_no_drift'
  0141  STORE              #84  ; 'goal'
  0144  PUSH_CONST         #85  ; 'entropy_anchor_no_drift'
  0147  CALL_HOST          #82 (args=1)  ; 'Δ [INTENT]'
  014A  LOAD               #86  ; 'similarity_score'
  014D  LOAD               #87  ; 'dedup_threshold'
  0150  CMP_LT
  0153  JZ                 #354  ; None
  0156  PUSH_CONST         #89  ; 'dedup_gate_allows_storage'
  0159  STORE              #90  ; 'goal'
  015C  PUSH_CONST         #91  ; 'dedup_gate_allows_storage'
  015F  CALL_HOST          #88 (args=1)  ; 'Δ [INTENT]'
  0162  PUSH_CONST         #92  ; 48
  0165  STORE              #93  ; 'observed_similarity'
  0168  PUSH_CONST         #94  ; 50
  016B  STORE              #95  ; 'default_threshold'
  016E  PUSH_CONST         #96  ; 65
  0171  STORE              #97  ; 'high_risk_threshold'
  0174  LOAD               #98  ; 'observed_similarity'
  0177  LOAD               #99  ; 'default_threshold'
  017A  CMP_LT
  017D  JZ                 #396  ; None
  0180  PUSH_CONST         #101  ; 'drift_detected_escalate'
  0183  STORE              #102  ; 'goal'
  0186  PUSH_CONST         #103  ; 'drift_detected_escalate'
  0189  CALL_HOST          #100 (args=1)  ; 'Δ [INTENT]'
  018C  LOAD               #104  ; 'observed_similarity'
  018F  LOAD               #105  ; 'high_risk_threshold'
  0192  CMP_LT
  0195  JZ                 #420  ; None
  0198  PUSH_CONST         #107  ; 'drift_high_risk_halt_branch'
  019B  STORE              #108  ; 'goal'
  019E  PUSH_CONST         #109  ; 'drift_high_risk_halt_branch'
  01A1  CALL_HOST          #106 (args=1)  ; 'Δ [INTENT]'
  01A4  PUSH_CONST         #110  ; 28
  01A7  STORE              #111  ; 'query_rank'
  01AA  PUSH_CONST         #112  ; 12
  01AD  STORE              #113  ; 'translation_min'
  01B0  PUSH_CONST         #114  ; 35
  01B3  STORE              #115  ; 'routing_min'
  01B6  PUSH_CONST         #116  ; 30
  01B9  STORE              #117  ; 'verifier_min'
  01BC  LOAD               #118  ; 'query_rank'
  01BF  LOAD               #119  ; 'translation_min'
  01C2  CMP_GE
  01C5  LOAD               #120  ; 'query_rank'
  01C8  LOAD               #121  ; 'routing_min'
  01CB  CMP_LT
  01CE  AND
  01D1  JZ                 #480  ; None
  01D4  PUSH_CONST         #123  ; 'qualifies_translation_not_routing'
  01D7  STORE              #124  ; 'goal'
  01DA  PUSH_CONST         #125  ; 'qualifies_translation_not_routing'
  01DD  CALL_HOST          #122 (args=1)  ; 'Δ [INTENT]'
  01E0  PUSH_CONST         #126  ; 5
  01E3  STORE              #127  ; 'mem_store'
  01E6  PUSH_CONST         #128  ; 5
  01E9  STORE              #129  ; 'mem_recall'
  01EC  PUSH_CONST         #130  ; 5
  01EF  STORE              #131  ; 'embed'
  01F2  PUSH_CONST         #132  ; 2
  01F5  STORE              #133  ; 'cosine'
  01F8  LOAD               #134  ; 'mem_store'
  01FB  LOAD               #135  ; 'mem_recall'
  01FE  ADD
  0201  LOAD               #136  ; 'embed'
  0204  ADD
  0207  LOAD               #137  ; 'cosine'
  020A  ADD
  020D  STORE              #138  ; 'rag_pipeline_gas'
  0210  LOAD               #139  ; 'rag_pipeline_gas'
  0213  LOAD               #140  ; 'hearth_max'
  0216  CMP_LE
  0219  JZ                 #552  ; None
  021C  PUSH_CONST         #142  ; 'rag_pipeline_fits_hearth'
  021F  STORE              #143  ; 'goal'
  0222  PUSH_CONST         #144  ; 'rag_pipeline_fits_hearth'
  0225  CALL_HOST          #141 (args=1)  ; 'Δ [INTENT]'
  0228  PUSH_CONST         #146  ; 'governing_algorithms_validated'
  022B  STORE              #147  ; 'message'
  022E  PUSH_CONST         #148  ; 'governing_algorithms_validated'
  0231  PUSH_CONST         #145  ; '∇ [RESULT]'
  0234  HALT
```

</details>

<details><summary><b>Surface 6: English Translation</b></summary>

> HLF v3 program with 44 statement(s): assign (mutable) hash_gas = 2; assign (mutable) merkle_gas = 3; assign (mutable) similarity_gas = 2; assign (mutable) verify_gas = 10; assign (mutable) audit_pipeline_gas = hash_gas + merkle_gas + similarity_gas + verify_gas; assign (mutable) hearth_max = 100; assign (mutable) forge_max = 500; if audit_pipeline_gas <= hearth_max then block; if audit_pipeline_gas <= forge_max then block; assign (mutable) confidence = 8; assign (mutable) groundedness = 9; assign (mutable) citation_coverage = 7; assign (mutable) freshness = 10; assign (mutable) provenance = 10; assign (mutable) weighted_score = confidence * 25 + groundedness * 25 + citation_coverage * 20 + freshness * 15 + provenance * 15; assign (mutable) archive_threshold = 450; if weighted_score >= archive_threshold then block; assign (mutable) hlf_tokens = 42; assign (mutable) nlp_tokens = 58; assign (mutable) compression_pct = hlf_tokens * 100 / nlp_tokens; assign (mutable) target_ceiling = 88; if compression_pct <= target_ceiling then block; assign (mutable) similarity_score = 96; assign (mutable) dedup_threshold = 98; assign (mutable) drift_threshold = 95; if similarity_score >= drift_threshold then block; if similarity_score < dedup_threshold then block; assign (mutable) observed_similarity = 48; assign (mutable) default_threshold = 50; assign (mutable) high_risk_threshold = 65; if observed_similarity < default_threshold then block; if observed_similarity < high_risk_threshold then block; assign (mutable) query_rank = 28; assign (mutable) translation_min = 12; assign (mutable) routing_min = 35; assign (mutable) verifier_min = 30; if query_rank >= translation_min AND query_rank < routing_min then block; assign (mutable) mem_store = 5; assign (mutable) mem_recall = 5; assign (mutable) embed = 5; assign (mutable) cosine = 2; assign (mutable) rag_pipeline_gas = mem_store + mem_recall + embed + cosine; if rag_pipeline_gas <= hearth_max then block; source [RESULT]: message=governing_algorithms_validated.

</details>

---

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


---
*Generated: 2026-05-13 12:00:49*
*Grounded in packaged HLF compiler, bytecode encoder, and disassembler truth.*

## Related Surfaces

- MCP resource: `hlf://gallery` — structured gallery status
- MCP resource: `hlf://reports/gallery` — this report
- MCP resource: `hlf://status/fixture_gallery` — fixture health summary
- Static doc: `docs/HLF_GALLERY.md` — gallery explainer
- Static doc: `fixtures/README.md` — fixture catalog
