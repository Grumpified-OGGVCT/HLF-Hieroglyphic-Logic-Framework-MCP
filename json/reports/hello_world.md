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
