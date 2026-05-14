# HLF NLP Translation Layer — Syntax Reference (Parser Truth)

> **Grounded in `grammar.py` LALR(1) rules + `compiler.py` transformer + `bytecode.py` emitter.**
> This documents what the parser ACTUALLY accepts, not aspirationally.

---

## Program Structure

Every HLF program must have:

```
[HLF-v3]             ← version header (required, first line)
...statements...     ← zero or more statement forms
Ω                    ← OMEGA terminator (required, last token)
```

- `# ...` starts a line comment (ignored)
- Whitespace (spaces, tabs, newlines) separates tokens — no explicit statement separator
- Statements may appear in any order; no statement delimiter token
- Programs are single-file (no `#include`)

**Minimal valid program:**
```hlf
[HLF-v3]
Ω
```

---

## Primitive Value Types

Used everywhere (SET, positional args, glyph arg values):

| Type | Regex / Format | Example |
|---|---|---|
| `ESCAPED_STRING` | Double-quoted only | `"hello world"` |
| `FLOAT` | `[+-]?digits.digits` | `3.14`, `-0.5` |
| `INT` | `[+-]?digits` | `42`, `-1` |
| `VAR_REF` | `$UPPER_SNAKE` | `$DEPLOYMENT_TIER` |
| `PATH` | Starts with `/`, no whitespace/brackets/braces | `/var/log/app.log` |
| `IDENT` | `[a-zA-Z_][a-zA-Z0-9_\-.:@]*` | `status`, `my-var`, `v2.1` |

---

## Expression Types

For block-form control flow (IF condition, FOR iterable, ASSIGN rhs, RESULT args):

| Family | Operators | Associativity |
|---|---|---|
| Logical OR | `OR` | Left |
| Logical AND | `AND` | Left |
| Unary NOT | `NOT` | Prefix |
| Comparison | `==` `!=` `<` `>` `<=` `>=` | Non-associative (flat chain) |
| Arithmetic add | `+` `-` | Left |
| Arithmetic mul | `*` `/` `%` | Left |
| Unary minus | `-` | Prefix |
| Grouping | `( expr )` | — |

Expression primitives: same as value types above (string, int, float, var_ref, path, ident).

---

## Argument Format

Used in: glyph statements, CALL, TOOL, INTENT, MODULE, MEMORY, SPEC_*

```
argument: IDENT "=" value   → keyword argument (kv_arg)
        | value             → positional argument (pos_arg)
```

- Mix positional and keyword args freely
- Order: positional args before keyword args (by convention, not enforced)
- No commas between arguments — whitespace-separated

---

# STATEMENT FORMS

## 1. FUNCTION block

**Syntax:**
```
FUNCTION name(param1, param2:type, ...) {
    ...body statements...
}
```

| Property | Value |
|---|---|
| Form | Block (`{ }`) |
| Parameter list | Parens, comma-separated |
| Parameter types | Optional `:type` suffix (IDENT) |
| Body | Required `{ }` block with zero or more statements |

**AST node:** `func_block_stmt` → `{kind, name, params: [{name, type}], body: {kind: "block", statements: [...]}}`

**Example:**
```hlf
FUNCTION deploy(app_name, tier:forge) {
    Δ [INTENT] goal="deploy" target="$app_name"
    RESULT 0 "deployed to $tier"
}
```

---

## 2. CALL

**Syntax:**
```
CALL name arg1 key2=val2 ...
```

| Property | Value |
|---|---|
| Form | Single-line (no block) |
| Arguments | Optional, whitespace-separated `arg_list` |

**AST node:** `call_stmt` → `{kind, name, arguments: [...]}`

**Example:**
```hlf
CALL deploy "my-app" tier="forge"
```

---

## 3. IF / ELIF / ELSE block

**Syntax:**
```
IF expr {
    ...body...
} ELIF expr {
    ...body...
} ELSE {
    ...body...
}
```

**Flat shorthand (no body):**
```
IF expr
```
This produces an AST node with `body: None` (backward-compat).

| Property | Value |
|---|---|
| Form | Block (`{ }`) for each branch |
| Condition | Full expression (comparison, logical, arithmetic) |
| ELIF | Zero or more, each requires `{ }` body |
| ELSE | Optional single `{ }` body |
| Nesting | Blocks can nest other IF/FOR etc. |

**AST node:** `if_block_stmt` → `{kind, condition, body, elif_clauses: [...], else_clause}`

**Example:**
```hlf
ASSIGN score = 85
ASSIGN threshold = 70
IF score >= threshold {
    Δ [INTENT] goal="deploy"
} ELIF score >= 50 {
    Δ [INTENT] goal="review"
} ELSE {
    Δ [INTENT] goal="abort"
}
```

**Example with logical operators:**
```hlf
IF query_rank >= 12 AND query_rank < 35 {
    Δ [INTENT] goal="qualifies_translation"
}
```

---

## 4. FOR loop

**Syntax:**
```
FOR var_name IN expr {
    ...body...
}
```

| Property | Value |
|---|---|
| Form | Block (`{ }`) |
| Loop variable | IDENT (bare name, no `$`) |
| Iterable | Expression (typically ident or var_ref) |
| Body | Required `{ }` block |

**AST node:** `for_stmt` → `{kind, var, iterable, body}`

**Example:**
```hlf
FOR item IN $ITEMS {
    LOG "processing $item"
}
```

---

## 5. PARALLEL block

**Syntax:**
```
PARALLEL { ... } { ... } ...
```

| Property | Value |
|---|---|
| Form | Block |
| Minimum blocks | 2 (grammar requires `block block+`) |
| Block contents | Each `{ }` contains zero or more statements |

**AST node:** `parallel_stmt` → `{kind, blocks: [...]}`

**Example:**
```hlf
PARALLEL {
    Δ [INTENT] goal="deploy_service_a"
} {
    Δ [INTENT] goal="deploy_service_b"
} {
    Δ [INTENT] goal="deploy_service_c"
}
```

---

## 6. SET (immutable binding)

**Syntax:**
```
SET name = value
```

| Property | Value |
|---|---|
| Form | Single-line |
| RHS | `value` (not expr — no arithmetic/comparison) |
| Mutability | Immutable — cannot reassign in same scope |
| Name | IDENT (bare name) |

**AST node:** `set_stmt` → `{kind, name, value}`

**Example:**
```hlf
SET model_name = "llama3.2"
SET max_retries = 3
SET target_path = "/app"
```

---

## 7. ASSIGN (mutable assignment)

**Syntax:**
```
ASSIGN name = expr
```

| Property | Value |
|---|---|
| Form | Single-line |
| RHS | Full `expr` (arithmetic, logical, comparison allowed) |
| Mutability | Mutable — can reassign |
| Name | IDENT (bare name) |

**AST node:** `assign_stmt` → `{kind, name, expr}`

**Example:**
```hlf
ASSIGN counter = 0
ASSIGN total = hash_gas + merkle_gas + verify_gas
ASSIGN is_ready = score >= threshold AND validated == true
```

---

## 8. LOG

**Syntax:**
```
LOG value
```

| Property | Value |
|---|---|
| Form | Single-line |
| Argument | Single `value` (string, int, var_ref, etc.) |

**AST node:** `log_stmt` → `{kind, value}`

**Example:**
```hlf
LOG "processing started"
LOG $STATUS
LOG 42
```

---

## 9. RETURN

**Syntax:**
```
RETURN value?
```

| Property | Value |
|---|---|
| Form | Single-line |
| Value | Optional `value` (string, int, ident, var_ref) |
| Without value | Bare `RETURN` is valid |

**AST node:** `return_stmt` → `{kind, value}` (value may be None)

**Example:**
```hlf
RETURN "ok"
RETURN 0
RETURN
```

---

## 10. RESULT

**Syntax:**
```
RESULT code_expr message_expr?
```

| Property | Value |
|---|---|
| Form | Single-line |
| First arg | `expr` — result code (typically INT) |
| Second arg | Optional `expr` — message (typically string) |

**AST node:** `result_stmt` → `{kind, code, message}`

**Example:**
```hlf
RESULT 0 "success"
RESULT 1 "deployment failed"
RESULT $EXIT_CODE
```

---

## 11. MEMORY[key] (memory write)

**Syntax:**
```
MEMORY[key] key1=val1 val2 ...
```

| Property | Value |
|---|---|
| Form | Single-line |
| Key | IDENT inside `[ ]` — the memory node name |
| Arguments | Optional `arg_list` (positional and/or keyword) |
| Space around `[key]` | Allowed (whitespace is ignored between tokens) |

**AST node:** `memory_stmt` → `{kind, name, arguments}`

**Example:**
```hlf
MEMORY [agent_state] value="initialized" confidence=0.95
MEMORY [deploy_context] "Deployment v2 started" tier="forge"
MEMORY [task_log] confidence=0.8 "Task completed"
```

---

## 12. RECALL[key] (memory recall)

**Syntax:**
```
RECALL[key]
```

| Property | Value |
|---|---|
| Form | Single-line |
| Key | IDENT inside `[ ]` — the memory node to recall |
| Arguments | NONE — recall takes no arg_list |
| Space around `[key]` | Allowed |

**AST node:** `recall_stmt` → `{kind, name}`

**Example:**
```hlf
RECALL [agent_state]
RECALL [deploy_context]
```

---

## 13–21. Glyph Statements

**Syntax:**
```
GLYPH [TAG] arg1 key2=val2 ...
```

| Property | Value |
|---|---|
| Form | Single-line |
| Glyph | One of: `Δ` `Ж` `⨝` `⌘` `∇` `⩕` `⊎` `⌂` `Σ` |
| Tag | Optional `[TAG_NAME]` where TAG_NAME is `[A-Z][A-Z0-9_]*` |
| Arguments | Optional `arg_list` (positional + keyword) |
| ASCII Alias | Line-start word aliases (e.g., `ANALYZE` → `Δ`) normalized in Pass 0 |

**AST node:** `glyph_stmt` → `{kind, glyph, tag, arguments}`

**Glyph → semantic mapping:**

| Glyph | Role | ASCII Alias | Example Tags |
|---|---|---|---|
| `Δ` | Analyze / primary action | `ANALYZE`, `ANALYSE` | `[INTENT]`, `[ACTION]`, `[THOUGHT]`, `[PLAN]` |
| `Ж` | Enforce / constrain | `ENFORCE`, `CONSTRAIN` | `[CONSTRAINT]`, `[ASSERT]`, `[EXPECT]` |
| `⨝` | Consensus / vote / join | `JOIN`, `CONSENSUS`, `VOTE` | `[VOTE]` |
| `⌘` | Command / delegate / route | `CMD`, `COMMAND` | `[DELEGATE]`, `[ROUTE]`, `[ACTION]` |
| `∇` | Source / data flow | `SOURCE` | `[SOURCE]`, `[PARAM]`, `[RESULT]`, `[OBSERVATION]` |
| `⩕` | Priority / weighting | `PRIORITY` | `[PRIORITY]`, `[PLAN]` |
| `⊎` | Branch / union / condition | `BRANCH`, `UNION` | `[RELATE]`, `[BRANCH]` |
| `⌂` | Memory anchor / provenance | `MEMORY_ANCHOR` | `[MEMORY]`, `[PROVENANCE]` |
| `Σ` | Summary / aggregate | `SUMMARY`, `SUMMARIZE`, `AGGREGATE` | `[RESULT]`, `[SUMMARY]` |

**Example (each glyph):**
```hlf
Δ [INTENT] goal="deploy" target="/app"
Δ analyze /security/seccomp.json
  Ж [CONSTRAINT] mode="ro"
  Ж [EXPECT] vulnerability_shorthand
  Ж [ASSERT] status="ok"
  ⨝ [VOTE] consensus="strict" quorum=5
  ⨝ [VOTE] option="option_a" score=8 verdict="selected"
⌘ [DELEGATE] agent="scribe" goal="summarize"
⌘ [ROUTE] strategy="auto" tier="$DEPLOYMENT_TIER"
∇ [SOURCE] /data/raw_logs/sync.txt
∇ [PARAM] temperature=0.0 replicas=3
∇ [RESULT] message="all systems operational"
⩕ [PRIORITY] level="high"
⊎ [RELATE] condition="threshold_check"
⌂ [MEMORY] key="agent_state"
Σ [SUMMARY] report="audit_complete"
```

---

## 22. INSTINCT Lifecycle (SPEC_DEFINE, SPEC_GATE, SPEC_UPDATE, SPEC_SEAL)

**Syntax:**
```
SPEC_DEFINE [TAG] key1=val1 val2 ...
SPEC_GATE [TAG] key1=val1 ...
SPEC_UPDATE [TAG] key1=val1 ...
SPEC_SEAL [TAG] key1=val1 ...
```

| Property | Value |
|---|---|
| Form | Single-line |
| Tag | Optional `[TAG]` |
| Arguments | Optional `arg_list` |

**AST node:** `spec_define_stmt` / `spec_gate_stmt` / `spec_update_stmt` / `spec_seal_stmt` → `{kind, tag, arguments}`

**Example:**
```hlf
SPEC_DEFINE [MIGRATION_SPEC] version="2.1" idempotent=true
SPEC_GATE [MIGRATION_SPEC] rollback_on_fail=true
SPEC_UPDATE [MIGRATION_SPEC] version="2.2"
SPEC_SEAL [MIGRATION_SPEC]
```

---

## 23. IMPORT

**Syntax:**
```
IMPORT /path/to/module
```

| Property | Value |
|---|---|
| Form | Single-line |
| Argument | `PATH` token (starts with `/`) |

**AST node:** `import_stmt` → `{kind, path}`

**Example:**
```hlf
IMPORT /stdlib/math
IMPORT /stdlib/crypto
IMPORT /stdlib/io
```

**Note:** The parser requires a PATH token (starts with `/`). Stdlib modules like `math`, `crypto`, `string` exist logically but the parse-time syntax requires a path-like form.

---

## 24. TOOL

**Syntax:**
```
TOOL name arg1 key2=val2 ...
```

| Property | Value |
|---|---|
| Form | Single-line |
| Name | IDENT — the tool name |
| Arguments | Optional `arg_list` |

**AST node:** `tool_stmt` → `{kind, name, arguments}`

**Example:**
```hlf
TOOL read_file path="/app/config.json"
TOOL deploy target="production" replicas=3
```

---

## 25. MODULE block

**Syntax:**
```
MODULE name arg1 key2=val2 {
    ...body...
}
```

| Property | Value |
|---|---|
| Form | Block (`{ }`) |
| Arguments | Optional `arg_list` between name and `{` |
| Body | Required `{ }` block |

**AST node:** `module_block_stmt` → `{kind, name, arguments, body}`

**Example:**
```hlf
MODULE deployer tier="forge" {
    FUNCTION deploy(target) {
        Δ [INTENT] goal="deploy" target="$target"
        RESULT 0 "ok"
    }
}
```

---

## 26. INTENT block (capsule)

**Syntax:**
```
INTENT name arg1 key2=val2 {
    ...body...
}
```

| Property | Value |
|---|---|
| Form | Block (`{ }`) |
| Arguments | Optional `arg_list` between name and `{` |
| Body | Required `{ }` block |

**AST node:** `intent_stmt` → `{kind, name, arguments, body}`

**Example:**
```hlf
INTENT deploy_capsule goal="production_deploy" tier="forge" {
    Δ [INTENT] goal="deploy"
    Ж [ASSERT] health_check=true
    RESULT 0 "deployed"
}
```

---

# Constraints & Quirks

## Statement Separation
- No explicit statement separator (no semicolons, no newline requirements)
- Statements are separated by token boundaries — whitespace suffices
- Blocks `{ }` naturally delimit their contents

## Nesting
- Blocks can nest: IF inside FUNCTION inside MODULE, etc.
- `PARALLEL` blocks can contain any statement types including other PARALLEL blocks
- FOR body can contain IF, ASSIGN, CALL, glyph statements, etc.

## Value vs Expression
- **SET** uses `value` (literals, var_refs only — no arithmetic)
- **ASSIGN**, **IF**, **FOR**, **RESULT** use `expr` (full arithmetic/logical/comparison)
- **LOG**, **RETURN**, **MEMORY**, **RECALL**, **TOOL**, **CALL**, glyph args use `value` or `arg_list` (not full expressions)

## TAG Names
- Must match `[A-Z][A-Z0-9_]*` — uppercase, no lowercase, digits allowed after first char
- Common tags: `INTENT`, `CONSTRAINT`, `ASSERT`, `EXPECT`, `VOTE`, `DELEGATE`, `ROUTE`, `SOURCE`, `PARAM`, `RESULT`, `PRIORITY`, `ACTION`, `PLAN`, `MEMORY`, etc.
- Tags are metadata — the parser does not validate tag semantics, only syntax

## String Quoting
- Double quotes only (`"..."`) — single quotes are NOT valid string delimiters
- No escape sequences beyond what Python's `ESCAPED_STRING` supports (standard backslash escapes)

## Variable References
- `$UPPER_SNAKE` format: `$DEPLOYMENT_TIER`, `$ITEMS`, `$EXIT_CODE`
- Expanded via SET environment in Pass 2
- `${VAR}` form also expanded (in string interpolation context)
- Bare variable names in expressions are IDENT tokens (loaded as variable loads)

## PATH Token
- Must start with `/`
- Cannot contain: whitespace, `"`, `[`, `]`, `{`, `}`, newlines
- Examples: `/var/log/app.log`, `/stdlib/math`, `/data/config.json`

## ASCII Aliases (Pass 0)
- Line-start only, word-boundary
- `ANALYZE` → `Δ`, `ENFORCE` → `Ж`, `JOIN` → `⨝`, `CMD`/`COMMAND` → `⌘`
- `SOURCE` → `∇`, `PRIORITY` → `⩕`, `BRANCH`/`UNION` → `⊎`
- `MEMORY_ANCHOR` → `⌂`, `SUMMARY`/`SUMMARIZE`/`AGGREGATE` → `Σ`
- `END`/`OMEGA` → `Ω` (terminator)
- Aliases inside quoted strings are NOT replaced

---

# QUICK REFERENCE — Complete Valid Program

```hlf
[HLF-v3]
# Declarations
SET app_name = "my-service"
ASSIGN gas_total = 2 + 3 + 5

# Glyph statements
Δ [INTENT] goal="deploy" target="/app"
  Ж [CONSTRAINT] mode="ro"
  Ж [ASSERT] health_check=true
  ⨝ [VOTE] consensus="strict"
  ∇ [PARAM] replicas=3
  ∇ [RESULT] message="deployment started"

⌘ [DELEGATE] agent="builder" goal="compile"
⌘ [ROUTE] strategy="auto" tier="$DEPLOYMENT_TIER"
⩕ [PRIORITY] level="high"
⊎ [RELATE] condition="gate_check"
⌂ [MEMORY] key="state_snapshot"
Σ [SUMMARY] report="audit_complete"

# Memory
MEMORY [deploy_context] value="v2.1" confidence=0.95
RECALL [deploy_context]

# Control flow
IF gas_total <= 100 {
    Δ [INTENT] goal="gas_ok"
} ELIF gas_total <= 500 {
    Δ [INTENT] goal="gas_warn"
} ELSE {
    Δ [INTENT] goal="gas_exceeded"
}

FOR item IN $ITEMS {
    LOG "processing $item"
}

PARALLEL {
    CALL deploy "service-a"
} {
    CALL deploy "service-b"
}

# Functions
FUNCTION deploy(name, tier:forge) {
    Δ [INTENT] goal="deploy" target="$name"
    RESULT 0 "deployed to $tier"
}

CALL deploy "my-app" tier="forge"
TOOL health_check target="/app"

# Instinct lifecycle
SPEC_DEFINE [MIGRATION_SPEC] version="2.1" idempotent=true
SPEC_GATE [MIGRATION_SPEC] rollback_on_fail=true
SPEC_UPDATE [MIGRATION_SPEC] version="2.2"
SPEC_SEAL [MIGRATION_SPEC]

# Logging & return
LOG "pipeline complete"
RETURN "ok"
RESULT 0 "all systems operational"

# Imports
IMPORT /stdlib/math
IMPORT /stdlib/crypto

# Capsule
INTENT audit_capsule goal="security_audit" {
    Δ [INTENT] goal="audit"
    Ж [CONSTRAINT] mode="ro"
}

Ω
```
