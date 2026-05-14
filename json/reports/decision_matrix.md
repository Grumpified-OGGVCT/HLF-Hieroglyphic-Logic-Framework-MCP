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
