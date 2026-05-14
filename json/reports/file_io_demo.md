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
