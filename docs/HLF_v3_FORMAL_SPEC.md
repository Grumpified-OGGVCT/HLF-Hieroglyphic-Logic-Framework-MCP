# HLF v3 Formal Specification

**Version:** 3.0.0
**Status:** Authoritative
**Last Updated:** 2026-05-18
**Scope:** Grammar, type system, gas algebra, bytecode semantics, provenance schema, Merkle chain format, effect algebra, capsule governance

---

## Table of Contents

1. [Grammar](#1-grammar)
   - 1.1 [Program Structure](#11-program-structure)
   - 1.2 [Glyph Statements](#12-glyph-statements)
   - 1.3 [Keyword Statements](#13-keyword-statements)
   - 1.4 [Expression System](#14-expression-system)
   - 1.5 [Type Annotations](#15-type-annotations)
   - 1.6 [Tags](#16-tags)
   - 1.7 [RFC 9005/9007 Extensions](#17-rfc-90059007-extensions)
   - 1.8 [AST Node Reference](#18-ast-node-reference)
2. [Type System](#2-type-system)
   - 2.1 [Primitive Types](#21-primitive-types)
   - 2.2 [Parametric Types](#22-parametric-types)
   - 2.3 [Refinement Types](#23-refinement-types)
   - 2.4 [Type Compatibility](#24-type-compatibility)
   - 2.5 [Python Coercion](#25-python-coercion)
3. [Gas Cost Algebra](#3-gas-cost-algebra)
   - 3.1 [Opcode Costs](#31-opcode-costs)
   - 3.2 [Host Function Costs](#32-host-function-costs)
   - 3.3 [Capsule Budgets](#33-capsule-budgets)
   - 3.4 [Metering Semantics](#34-metering-semantics)
4. [Bytecode Semantics](#4-bytecode-semantics)
   - 4.1 [Binary Format](#41-binary-format)
   - 4.2 [Opcode Reference](#42-opcode-reference)
   - 4.3 [Execution Model](#43-execution-model)
   - 4.4 [Glyph-to-Opcode Mapping](#44-glyph-to-opcode-mapping)
5. [Provenance Schema](#5-provenance-schema)
   - 5.1 [EvidenceRecord](#51-evidencerecord)
   - 5.2 [ProvenanceNode](#52-provenancenode)
   - 5.3 [ProvenanceChain](#53-provenancechain)
   - 5.4 [TrustRoot](#54-trustroot)
   - 5.5 [AuditChain](#55-auditchain)
   - 5.6 [JSON-LD Context](#56-json-ld-context)
6. [Merkle Chain Format](#6-merkle-chain-format)
   - 6.1 [Chain Entry](#61-chain-entry)
   - 6.2 [Merkle DR Backup](#62-merkle-dr-backup)
   - 6.3 [Hash Computation](#63-hash-computation)
   - 6.4 [Signing](#64-signing)
7. [Effect Algebra](#7-effect-algebra)
   - 7.1 [Effect Classes](#71-effect-classes)
   - 7.2 [Failure Modes](#72-failure-modes)
   - 7.3 [Proof Requirements](#73-proof-requirements)
   - 7.4 [Effect Combinators](#74-effect-combinators)
   - 7.5 [TypedEffectDeclaration](#75-typedeffectdeclaration)
8. [Operator Semantics](#8-operator-semantics)
   - 8.1 [Operator Taxonomy](#81-operator-taxonomy)
   - 8.2 [Type × Operator Coverage Matrix](#82-type--operator-coverage-matrix)
9. [Capsule Governance](#9-capsule-governance)
   - 9.1 [IntentCapsule](#91-intentcapsule)
   - 9.2 [Tier Model](#92-tier-model)
   - 9.3 [HITL Gate Protocol](#93-hitl-gate-protocol)
   - 9.4 [Secret Management](#94-secret-management)
   - 9.5 [Model Version Pinning](#95-model-version-pinning)
10. [MCP Tool Interface](#10-mcp-tool-interface)
    - 10.1 [Core Tools](#101-core-tools)
    - 10.2 [Enterprise Tools](#102-enterprise-tools)
    - 10.3 [Tier-Gated Visibility](#103-tier-gated-visibility)
11. [Appendix: Opcode Quick Reference](#11-appendix-opcode-quick-reference)

---

## 1. Grammar

### 1.1 Program Structure

HLF source is parsed by a **LALR(1) grammar** using the Lark parser. Every valid program conforms to:

```ebnf
program        ::= header? statement* "Ω"
header         ::= "[HLF-v" VERSION "]"
VERSION        ::= "3"   (* current version *)
statement      ::= glyph_stmt
                 | keyword_stmt
                 | rfc_extension_stmt
```

The `Ω` (OMEGA) glyph is the mandatory program terminator.

**Source files:**
- `hlf_mcp/hlf/grammar.py` — LALR(1) grammar rules (lines 38–605)
- `hlf_mcp/hlf/compiler.py` — AST transformer (lines 1–1400+)

### 1.2 Glyph Statements

Glyph statements are the core HLF surface syntax. Each glyph maps to a semantic role and a bytecode opcode.

```ebnf
glyph_stmt     ::= GLYPH tag? arg_list? validate_annot?
GLYPH          ::= "Δ" | "Ж" | "⨝" | "⌘" | "∇" | "⩕" | "⊎" | "⌂" | "Σ"
tag            ::= "[" TAG_NAME "]"   (* see §1.6 *)
arg_list       ::= IDENT "=" value ("," IDENT "=" value)*
validate_annot ::= "@" IDENT ("," IDENT)*
```

#### Glyph Reference

| Glyph | Name | Opcode | ASCII Alias | Semantic Role |
|-------|------|--------|-------------|---------------|
| `Δ` | DELTA | `0x51` | ANALYZE | Analyze / primary action |
| `Ж` | ZHE | `0x60` | ENFORCE, CONSTRAIN | Enforce / constrain / assert |
| `⨝` | JOIN | `0x61` | JOIN, CONSENSUS, VOTE | Consensus / vote |
| `⌘` | COMMAND | `0x52` | CMD, COMMAND | Delegate / route |
| `∇` | NABLA | `0x01` | SOURCE | Source / data parameter |
| `⩕` | BOWTIE | `0x11` | PRIORITY | Priority / weight / rank |
| `⊎` | UNION | `0x41` | BRANCH, UNION | Branch / condition |
| `⌂` | HOUSE | — | MEMORY_ANCHOR | Memory anchor / recall |
| `Σ` | SIGMA | — | SUMMARY, AGGREGATE | Summarize / aggregate |

### 1.3 Keyword Statements

```ebnf
keyword_stmt   ::= set_stmt | assign_stmt | if_block_stmt | for_stmt
                 | parallel_stmt | module_block_stmt | func_block_stmt
                 | intent_stmt | tool_stmt | call_stmt | return_stmt
                 | result_stmt | log_stmt | import_stmt | memory_stmt
                 | recall_stmt | spec_define_stmt | spec_gate_stmt
                 | spec_update_stmt | spec_seal_stmt | pipe_stmt
                 | template_stmt

set_stmt       ::= "SET" IDENT "=" expr
assign_stmt    ::= "ASSIGN" IDENT "=" expr
if_block_stmt  ::= "IF" expr "{" statement* "}"
                   ("ELIF" expr "{" statement* "}")*
                   ("ELSE" "{" statement* "}")?
for_stmt       ::= "FOR" IDENT "IN" expr "{" statement* "}"
parallel_stmt  ::= "PARALLEL" ("{" statement* "}")+
module_block_stmt ::= "MODULE" IDENT ("(" param ("," param)* ")")? "{" statement* "}"
func_block_stmt   ::= "FUNCTION" IDENT "(" (IDENT ":" type_annot ("," IDENT ":" type_annot)*)? ")" "{" statement* "}"
intent_stmt    ::= "INTENT" IDENT arg_list? "{" statement* "}"
tool_stmt      ::= "TOOL" IDENT arg_list?
call_stmt      ::= "CALL" IDENT arg_list?
return_stmt    ::= "RETURN" expr?
result_stmt    ::= "RESULT" INT (STRING)?
log_stmt       ::= "LOG" expr
import_stmt    ::= "IMPORT" PATH
memory_stmt    ::= "MEMORY" "[" IDENT "]" arg_list?
recall_stmt    ::= "RECALL" "[" IDENT "]"
spec_define_stmt ::= "SPEC_DEFINE" tag? arg_list?
spec_gate_stmt   ::= "SPEC_GATE" tag? arg_list?
spec_update_stmt ::= "SPEC_UPDATE" tag? arg_list?
spec_seal_stmt   ::= "SPEC_SEAL" tag? arg_list?
pipe_stmt      ::= statement ("→" statement)+
template_stmt  ::= "TEMPLATE" IDENT "{" statement* "}"
```

### 1.4 Expression System

Expressions follow standard precedence with right-associative exponentiation.

```ebnf
(* Precedence: lowest → highest *)
expr           ::= expr_or
expr_or        ::= expr_and (("OR" | "∪") expr_and)*
expr_and       ::= expr_bitwise (("AND" | "∩") expr_bitwise)*
expr_bitwise   ::= expr_not (("&" | "|" | "⊕") expr_not)*
expr_not       ::= ("NOT" | "¬") expr_not | expr_cmp
expr_cmp       ::= expr_add (CMP_OP expr_add)*
CMP_OP         ::= ">=" | "<=" | "!=" | "==" | ">" | "<"
expr_add       ::= expr_mul (("+" | "-") expr_mul)*
expr_mul       ::= expr_exp (("*" | "/" | "%") expr_exp)*
expr_exp       ::= expr_unary ("^" expr_exp)?   (* right-associative *)
expr_unary     ::= "-" expr_primary | expr_primary
expr_primary   ::= STRING | FLOAT | INT | BOOL
                 | "$" IDENT          (* variable reference *)
                 | PATH               (* file path: /prefix *)
                 | IDENT ("(" args? ")")?  (* identifier or function call *)
                 | "(" expr ")"
                 | list_literal
                 | match_expr
                 | struct_expr

list_literal   ::= "[" expr ("," expr)* "]"
match_expr     ::= "MATCH" expr "{" (pattern "=>" expr ",")* "}"
struct_expr    ::= "{" (IDENT ":" expr ("," IDENT ":" expr)*)? "}"
```

#### Literal Values

```ebnf
STRING         ::= '"' ('\\"' | ~'"')* '"'
FLOAT          ::= DIGIT+ "." DIGIT+
INT            ::= DIGIT+
BOOL           ::= "true" | "false"
PATH           ::= "/" PATH_SEGMENT ("/" PATH_SEGMENT)*
```

### 1.5 Type Annotations

```ebnf
type_annot     ::= type_glyph | parametric_type | refinement_type

type_glyph     ::= "ℕ"     (* NUMBER — any numeric *)
                 | "ℤ"     (* INTEGER *)
                 | "ℝ"     (* REAL *)
                 | "ℚ"     (* RATIONAL *)
                 | "𝕊"     (* STRING *)
                 | "𝔹"     (* BOOLEAN *)
                 | "𝕁"     (* JSON *)
                 | "𝔸"     (* ANY — top type *)

parametric_type ::= "List⟨" type_annot "⟩"
                  | "Set⟨" type_annot "⟩"
                  | "Map⟨" type_annot "," type_annot "⟩"

refinement_type ::= "{" IDENT ":" type_annot "|" expr "}"
epistemic_conf  ::= "_{ρ:" FLOAT "}"   (* epistemic confidence modifier *)
```

### 1.6 Tags

Tags are uppercase identifiers enclosed in brackets. They serve as structured metadata annotations on glyph and keyword statements.

```ebnf
tag            ::= "[" TAG_NAME "]"
TAG_NAME       ::= /[A-Z][A-Z0-9_]*/
```

**Defined tags (35):**
`INTENT`, `CAPSULE`, `THOUGHT`, `OBSERVATION`, `PLAN`, `CONSTRAINT`, `ASSERT`, `EXPECT`,
`ACTION`, `DELEGATE`, `ROUTE`, `SOURCE`, `PARAM`, `PRIORITY`, `VOTE`, `RESULT`, `SET`,
`MODULE`, `IMPORT`, `FUNCTION`, `CODE`, `DATA`, `MEMORY`, `RECALL`, `PROVENANCE`,
`GOVERNANCE`, `RELATE`, `GATE`, `DEFINE`, `CALL`, `WHILE`, `TRY`, `CATCH`, `RETURN`,
`MIGRATION`, `MIGRATION_SPEC`, `ALIGN`, `SPEC`, `SPEC_DEFINE`, `SPEC_GATE`,
`SPEC_UPDATE`, `SPEC_SEAL`

### 1.7 RFC 9005/9007 Extensions

Extensions to the base grammar supporting epistemic confidence and structured types:

```ebnf
glyph_assign_stmt ::= IDENT "::" type_annot "←" expr epistemic_conf?
struct_stmt       ::= IDENT "≡" "{" field_def ("," field_def)* "}" epistemic_conf?
field_def         ::= IDENT ":" type_annot
sync_stmt         ::= "⋈" "[" IDENT ("," IDENT)* "]" "→" statement epistemic_conf?
cond_stmt         ::= "⊎" expr "⇒" statement ("⇌" statement)? epistemic_conf?
prose_stmt        ::= expr "§" STRING
aesthetic_stmt    ::= expr "~" IDENT
negate_stmt       ::= "⊖" statement
```

### 1.8 AST Node Reference

The compiler transforms parsed Lark trees into a normalized AST using dict-based nodes. Every node has a `kind` field.

**Node kinds (32):**
`program`, `glyph_stmt`, `set_stmt`, `assign_stmt`, `if_block_stmt`, `elif_clause`, `else_clause`,
`for_stmt`, `parallel_stmt`, `module_block_stmt`, `func_block_stmt`, `intent_stmt`,
`tool_stmt`, `call_stmt`, `return_stmt`, `result_stmt`, `log_stmt`, `import_stmt`,
`memory_stmt`, `recall_stmt`, `spec_define_stmt`, `spec_gate_stmt`, `spec_update_stmt`,
`spec_seal_stmt`, `pipe_stmt`, `template_stmt`, `struct_stmt`, `sync_stmt`, `cond_stmt`,
`prose_stmt`, `aesthetic_stmt`, `negate_stmt`, `block`, `match_expr`, `list_literal`,
`binop`, `unop`, `paren_expr`, `value`

---

## 2. Type System

### 2.1 Primitive Types

| Glyph | HlfType | Description |
|-------|---------|-------------|
| `ℕ` | `NUMBER` | Any numeric value (superset of ℤ, ℝ, ℚ) |
| `ℤ` | `INTEGER` | Arbitrary-precision integer |
| `ℝ` | `REAL` | Floating-point (IEEE 754 double) |
| `ℚ` | `RATIONAL` | Exact rational (numerator/denominator) |
| `𝕊` | `STRING` | Unicode string (soft cap: 10 MB) |
| `𝔹` | `BOOLEAN` | `true` or `false` |
| `𝕁` | `JSON` | JSON-compatible structure |
| `𝔸` | `ANY` | Top type — accepts all values |

### 2.2 Parametric Types

| Syntax | Type | Description |
|--------|------|-------------|
| `List⟨T⟩` | `LIST[T]` | Homogeneous list, elements of type T |
| `Set⟨T⟩` | `SET[T]` | Homogeneous set, elements of type T |
| `Map⟨K,V⟩` | `MAP[K,V]` | Dictionary with keys of type K, values of type V |

### 2.3 Refinement Types

```ebnf
refinement_type ::= "{" IDENT ":" type_annot "|" predicate_expr "}"
```

Example: `{x: ℤ | x > 0}` defines the positive integers.

Refinement types delegate operator semantics to their base type. Validation checks the predicate at runtime.

### 2.4 Type Compatibility

Type compatibility governs which types can flow into which operators and effect contracts.

```
Rule 1: 𝔸 (ANY) accepts all types.              (top type)
Rule 2: Same types are always compatible.
Rule 3: ℕ, ℤ, ℝ, ℚ are mutually compatible.     (numeric lattice)
Rule 4: 𝕁 accepts 𝕊, ℕ, ℤ, ℝ, ℚ, 𝔹, 𝕁.         (JSON compatibility)
Rule 5: LIST, 𝕊, 𝔹, 𝕁 are compatible with 𝕁.
Rule 6: SET is compatible with LIST.
```

**Source file:** `hlf_mcp/hlf/typed_effect_algebra.py` (lines 579–600)

### 2.5 Python Coercion

When HLF values cross the Python boundary, `TypeCoercionContract` enforces:

| HLF Type | Python Type | Safety | Constraint |
|----------|-------------|--------|------------|
| `ℤ` | `int` | SAFE | 64-bit overflow check |
| `ℝ` | `float` | WARNING | 15-digit precision cap |
| `𝕊` | `str` | SAFE | 10 MB soft cap |
| `𝔹` | `bool` | SAFE | — |
| `List⟨T⟩` | `list` | SAFE | Recursive element coercion |
| `Map⟨K,V⟩` | `dict` | SAFE | Recursive value coercion |
| `BYTES` | `bytes` | SAFE | 100 MB cap |
| `𝔸` | `object` | WARNING | Unchecked |
| `Optional[T]` | `T \| None` | depends | Strict mode rejects None for non-optional |

**Source file:** `hlf_mcp/hlf/python_type_coercion.py`

---

## 3. Gas Cost Algebra

### 3.1 Opcode Costs

Gas is a monotonically increasing counter that bounds execution. Each opcode has a fixed cost.

| Opcode | Cost | Opcode | Cost | Opcode | Cost |
|--------|------|--------|------|--------|------|
| `NOP` (`0x00`) | 0 | `ADD` (`0x10`) | 2 | `CALL_BUILTIN` (`0x50`) | 5 |
| `PUSH_CONST` (`0x01`) | 1 | `SUB` (`0x11`) | 2 | `CALL_HOST` (`0x51`) | 10 |
| `STORE` (`0x02`) | 2 | `MUL` (`0x12`) | 3 | `CALL_TOOL` (`0x52`) | 15 |
| `LOAD` (`0x03`) | 1 | `DIV` (`0x13`) | 5 | `OPENCLAW_TOOL` (`0x53`) | 20 |
| `STORE_IMMUT` (`0x04`) | 3 | `MOD` (`0x14`) | 3 | `TAG` (`0x60`) | 1 |
| `CMP_EQ` (`0x20`) | 1 | `NEG` (`0x15`) | 1 | `INTENT` (`0x61`) | 2 |
| `CMP_NE` (`0x21`) | 1 | `JMP` (`0x40`) | 1 | `RESULT` (`0x62`) | 1 |
| `CMP_LT` (`0x22`) | 1 | `JZ` (`0x41`) | 2 | `MEMORY_STORE` (`0x63`) | 3 |
| `CMP_LE` (`0x23`) | 1 | `JNZ` (`0x42`) | 2 | `MEMORY_RECALL` (`0x64`) | 2 |
| `CMP_GT` (`0x24`) | 1 | `AND` (`0x30`) | 1 | `SPEC_DEFINE` (`0x65`) | 4 |
| `CMP_GE` (`0x25`) | 1 | `OR` (`0x31`) | 1 | `SPEC_GATE` (`0x66`) | 4 |
| — | — | `NOT` (`0x32`) | 1 | `SPEC_UPDATE` (`0x67`) | 4 |
| — | — | `POP` (`0x33`) | 0 | `SPEC_SEAL` (`0x68`) | 4 |
| — | — | `HALT` (`0xFF`) | 0 | — | — |

**Source file:** `hlf_mcp/hlf/bytecode.py` (lines 66–104)

### 3.2 Host Function Costs

Host functions are environment-level operations with costs reflecting their external impact.

| Function | Gas | Function | Gas |
|----------|-----|----------|-----|
| `analyze` | 2 | `sensor_read` | 4 |
| `vote` | 1 | `trajectory_propose` | 6 |
| `delegate` | 3 | `guarded_actuate` | 8 |
| `route` | 2 | `emergency_stop` | 3 |
| `memory_store` | 5 | `spawn_agent` | 10 |
| `memory_recall` | 5 | `http_get` | 4 |
| `hash_sha256` | 2 | `file_read` | 2 |
| `merkle_chain` | 3 | `file_write` | 5 |
| `align_verify` | 4 | `math/string/stdlib` | 1–2 |
| `summarize` | 8 | `embed_text` | 5 |
| `cove_validate` | 6 | `z3_verify` | 10 |

**Source file:** `hlf_mcp/hlf/runtime.py` (lines 68–285)

### 3.3 Capsule Budgets

| Tier | Gas Budget |
|------|-----------|
| `hearth` | 100 |
| `forge` | 500 |
| `sovereign` | 1000 |

**Source file:** `hlf_mcp/hlf/capsules.py`

### 3.4 Metering Semantics

Gas is checked **before each instruction executes**. The invariant is:

```
∀ instruction i:
    cost_i = GAS_COSTS[opcode_i]  (default: 1 if undefined)
    assert gas_used + cost_i ≤ max_gas
    gas_used := gas_used + cost_i
```

If the assertion fails, `HlfVMGasExhausted` is raised. Execution terminates immediately.

**Source file:** `hlf_mcp/hlf/runtime.py` (lines 639–644)

---

## 4. Bytecode Semantics

### 4.1 Binary Format

The `.hlb` binary format is a fixed-structure container:

```
┌────────────────────────────────────┐
│ SHA-256 (32 bytes)                 │  ← hash of entire payload following
├────────────────────────────────────┤
│ Header (16 bytes, little-endian):  │
│   magic[4]:  0x48 0x4C 0x42 0x00  │  "HLB\0"
│   version[2]: 0x0004               │  v0.4
│   code_len[4]: uint32              │  byte length of code section
│   crc32[4]:   uint32               │  CRC-32 of code section
│   flags[2]:   uint16               │  reserved
├────────────────────────────────────┤
│ Constant Pool:                     │
│   count: uint32 LE                 │
│   per entry:                       │
│     type_byte: uint8               │  (see type table below)
│     data: variable-length           │  type-dependent payload
├────────────────────────────────────┤
│ Code Section:                      │
│   fixed 3-byte instructions:       │
│     opcode: uint8                  │
│     operand: uint16 LE             │  (pool index or jump target)
└────────────────────────────────────┘
```

#### Constant Pool Types

| Type Byte | Type | Payload |
|-----------|------|---------|
| `0x01` | INT | varint-encoded signed integer |
| `0x02` | FLOAT | 8 bytes (IEEE 754 double) |
| `0x03` | STRING | length-prefixed UTF-8 |
| `0x04` | BOOL | 1 byte (0x00 or 0x01) |
| `0x05` | NULL | 0 bytes |
| `0x06` | RATIONAL | two varint-encoded integers (num, denom) |
| `0x07` | INTEGER (ℤ) | varint-encoded signed integer |
| `0x08` | REAL (ℝ) | 8 bytes (IEEE 754 double) |
| `0x09` | LIST | count + recursive entries |
| `0x0A` | SET | count + recursive entries |
| `0x0B` | MAP | count + recursive key-value pairs |
| `0x0C` | REFINEMENT | base type byte + predicate string |

**Source file:** `hlf_mcp/hlf/bytecode.py` (lines 1–9, 109–121, 225–400)

### 4.2 Opcode Reference

All opcodes are defined in `Op(IntEnum)`. Each instruction occupies exactly 3 bytes: `[opcode: 1 byte][operand: 2 bytes LE]`.

| Code | Mnemonic | Operand | Stack Effect | Description |
|------|----------|---------|--------------|-------------|
| `0x00` | NOP | — | `∅ → ∅` | No operation |
| `0x01` | PUSH_CONST | pool index | `∅ → value` | Push constant from pool onto stack |
| `0x02` | STORE | pool index (name) | `value → ∅` | Pop TOS, store to variable |
| `0x03` | LOAD | pool index (name) | `∅ → value` | Push variable value onto stack |
| `0x04` | STORE_IMMUT | pool index (name) | `value → ∅` | Pop TOS, store immutable variable |
| `0x10` | ADD | — | `b, a → a+b` | Arithmetic addition |
| `0x11` | SUB | — | `b, a → a-b` | Arithmetic subtraction |
| `0x12` | MUL | — | `b, a → a*b` | Arithmetic multiplication |
| `0x13` | DIV | — | `b, a → a/b` | Arithmetic division |
| `0x14` | MOD | — | `b, a → a%b` | Modulus |
| `0x15` | NEG | — | `a → -a` | Negation |
| `0x20` | CMP_EQ | — | `b, a → a==b` | Equal comparison |
| `0x21` | CMP_NE | — | `b, a → a!=b` | Not-equal comparison |
| `0x22` | CMP_LT | — | `b, a → a<b` | Less-than comparison |
| `0x23` | CMP_LE | — | `b, a → a<=b` | Less-or-equal comparison |
| `0x24` | CMP_GT | — | `b, a → a>b` | Greater-than comparison |
| `0x25` | CMP_GE | — | `b, a → a>=b` | Greater-or-equal comparison |
| `0x30` | AND | — | `b, a → a&&b` | Logical AND |
| `0x31` | OR | — | `b, a → a\|\|b` | Logical OR |
| `0x32` | NOT | — | `a → !a` | Logical NOT |
| `0x33` | POP | — | `a → ∅` | Pop and discard TOS |
| `0x40` | JMP | target PC | `∅ → ∅` | Unconditional jump |
| `0x41` | JZ | target PC | `a → ∅` | Jump if zero/false |
| `0x42` | JNZ | target PC | `a → ∅` | Jump if nonzero/true |
| `0x50` | CALL_BUILTIN | pool index (name) | `args... → result` | Call built-in function |
| `0x51` | CALL_HOST | pool index (name) | `args... → result` | Call host function |
| `0x52` | CALL_TOOL | pool index (name) | `args... → result` | Call registered tool |
| `0x53` | OPENCLAW_TOOL | pool index (name) | `args... → result` | Call OpenClaw sandboxed tool |
| `0x60` | TAG | pool index (name) | `∅ → ∅` | Tag/label annotation |
| `0x61` | INTENT | pool index (name) | `∅ → ∅` | Declare intent |
| `0x62` | RESULT | — | `∅ → result` | Push result value |
| `0x63` | MEMORY_STORE | — | `value → ∅` | Store TOS to RAG memory |
| `0x64` | MEMORY_RECALL | — | `∅ → value` | Recall from RAG memory |
| `0x65` | SPEC_DEFINE | pool index (name) | `∅ → ∅` | Define instinct spec |
| `0x66` | SPEC_GATE | pool index (name) | `∅ → ∅` | Gate instinct spec |
| `0x67` | SPEC_UPDATE | pool index (name) | `∅ → ∅` | Update instinct spec |
| `0x68` | SPEC_SEAL | pool index (name) | `∅ → ∅` | Seal instinct spec |
| `0xFF` | HALT | — | `∅ → ∅` | Halt execution |

**Source file:** `hlf_mcp/hlf/bytecode.py` (lines 23–61)

### 4.3 Execution Model

HLF uses a **stack-based virtual machine** (`HlfVM`) with the following state:

```
State = ⟨stack, scope, immutables, pc, gas_used, max_gas, trace, side_effects⟩

stack       : list[Any]       — operand stack
scope       : dict[str, Any]  — variable bindings (mutable)
immutables  : set[str]        — variables set via STORE_IMMUT (write-protected)
pc          : int             — program counter (byte offset into code)
gas_used    : int             — cumulative gas consumed
max_gas     : int             — gas budget (from capsule)
trace       : list[dict]      — execution trace: {pc, op, gas, stack_depth}
side_effects: list[dict]      — side effect log: {type, ...}
```

**Execution loop:**

```
while pc < len(code):
    opcode, operand = decode_instruction(code, pc)
    if gas_used + GAS_COSTS[opcode] > max_gas:
        raise HlfVMGasExhausted
    gas_used += GAS_COSTS[opcode]
    dispatch(opcode, operand)
    pc += 3  (unless opcode is JMP/JZ/JNZ which set pc directly)
```

**Result type:** `VMResult(code, message, gas_used, stack, scope, trace, side_effects, error)`

**Source file:** `hlf_mcp/hlf/runtime.py` (lines 349–867)

### 4.4 Glyph-to-Opcode Mapping

```python
_GLYPH_OP = {
    "Δ": Op.CALL_HOST,    # analyze → host function call
    "Ж": Op.TAG,           # enforce → tag annotation
    "⨝": Op.INTENT,        # consensus → intent declaration
    "⌘": Op.CALL_HOST,     # command → host function call
    "∇": Op.PUSH_CONST,    # source → push constant
    "⩕": Op.TAG,           # priority → tag annotation
    "⊎": Op.JZ,            # branch → conditional jump
}
```

**Source file:** `hlf_mcp/hlf/bytecode.py` (lines 249–257)

---

## 5. Provenance Schema

### 5.1 EvidenceRecord

The canonical record of an evidence artifact in the knowledge substrate.

```python
@dataclass(slots=True)
class EvidenceRecord:
    evidence_id: str              # UUID v5 (deterministic from seed)
    source: str                   # "server_memory" | "rag" | "hybrid_rag" | "hks"
    artifact_type: str            # "benchmark" | "exemplar" | "route_trace" | "proof" | "memory_node"
    content_hash: str             # SHA-256 hex digest
    created_at: str               # ISO-8601
    expires_at: str | None        # None = no expiry
    superseded_by: str | None     # evidence_id of replacement
    provenance_chain: list[str]   # ordered evidence_ids forming the chain
    confidence: float             # 0.0–1.0
    metadata: dict[str, Any]      # source-specific enrichment
    is_stale: bool                # True if past expiry
    is_superseded: bool           # True if superseded_by is set
```

**Artifact type mapping:**

| Source Prefix | artifact_type |
|---------------|---------------|
| `benchmark_artifact` | `benchmark` |
| `hks_exemplar` | `exemplar` |
| `governed_route` | `route_trace` |
| `governance_proof` | `proof` |
| `memory_node:fact` | `memory_node` |
| `memory_node:evidence` | `memory_node` |
| `memory_node:dream_finding` | `memory_node` |
| `memory_node:governed_recall` | `memory_node` |
| `memory_node:internal_workflow` | `memory_node` |
| `memory_node:execution_admission` | `memory_node` |
| `memory_node:witness_observation` | `memory_node` |
| `memory_node:media_evidence` | `memory_node` |
| `memory_node:translation_contract` | `memory_node` |
| `memory_node:symbolic_surface` | `memory_node` |

**Source file:** `hlf_mcp/hlf/evidence_schema.py` (lines 27–63, 127–149)

### 5.2 ProvenanceNode

A single node in a knowledge provenance DAG with Merkle-hash integrity.

```python
@dataclass(slots=True)
class ProvenanceNode:
    node_id: str                  # UUID
    claim_hash: str               # SHA-256 of claim_content
    claim_content: str            # The knowledge claim
    derivation_kind: DerivationKind  # see §5.2.1
    predecessor_hashes: list[str] # ordered dependency hashes
    merkle_hash: str              # SHA-256 of canonical payload
    created_at: float             # Unix timestamp
    creator_id: str               # Agent or operator identifier
    evidence: dict[str, Any]      # Supporting evidence
    metadata: dict[str, Any]      # Additional metadata
```

#### DerivationKind Enum

| Value | Description |
|-------|-------------|
| `DIRECT_OBSERVATION` | First-hand measurement or sensor reading |
| `INFERENCE` | Derived from other claims via reasoning |
| `AGGREGATION` | Combined from multiple source claims |
| `TRANSFORMATION` | Computed from source claims via transformation |
| `EXTERNAL_IMPORT` | Imported from external system |
| `OPERATOR_ATTESTED` | Asserted by human operator |
| `CONSTITUTIONAL` | Root trust axiom (not derived) |
| `BENCHMARK_VERIFIED` | Validated against benchmark ground truth |

#### Merkle Hash Computation

```python
merkle_hash = SHA-256(json.dumps({
    "claim_hash": claim_hash,
    "claim_content": claim_content,
    "predecessors": sorted(predecessor_hashes),
    "derivation_kind": derivation_kind.name,
    "creator_id": creator_id,
    "created_at": created_at,
}, sort_keys=True, default=str))
```

**Source file:** `hlf_mcp/hlf/knowledge_provenance.py` (lines 37–109)

### 5.3 ProvenanceChain

```python
@dataclass(slots=True)
class ProvenanceChain:
    chain_id: str                 # Unique chain identifier
    nodes: list[ProvenanceNode]   # Ordered list of provenance nodes
    root_hashes: set[str]         # Trust root hashes for verification
    created_at: float             # Unix timestamp
```

Chain integrity verification walks each node, checking:
1. Merkle hash consistency (recompute and compare)
2. Predecessor resolution (all predecessor_hashes exist in chain or trust roots)
3. No cycles in the predecessor DAG

**Source file:** `hlf_mcp/hlf/knowledge_provenance.py` (lines 345–497)

### 5.4 TrustRoot

```python
@dataclass(slots=True)
class TrustRoot:
    root_id: str                  # Unique root identifier
    claim_hash: str               # SHA-256 of the root claim
    root_type: str                # "constitutional" | "benchmark" | "operator_attested"
    description: str              # Human-readable description
    attested_by: str              # Identity of attesting party
    attested_at: float            # Unix timestamp of attestation
    expires_at: float | None      # Expiry timestamp (None = permanent)
    signature: str                # SHA-256 of canonical payload
```

**Source file:** `hlf_mcp/hlf/knowledge_provenance.py` (lines 116–179)

### 5.5 AuditChain

A JSONL-based append-only hash chain. Each line is a self-describing JSON object.

```json
{
  "trace_id": "<SHA-256 hex>",
  "parent_trace_hash": "<SHA-256 hex of previous entry>",
  "timestamp": "YYYY-MM-DDTHH:MM:SS",
  "goal_id": "",
  "agent_role": "hlf_mcp",
  "event": "event_name",
  "data": {},
  "confidence_score": 1.0,
  "anomaly_score": 0.0,
  "token_cost": 0
}
```

**Chain hash:** `SHA-256(prev_hash + json.dumps({"event": event, "data": data}, sort_keys=True))`

**File:** `hlf_mcp.audit.jsonl`

**Source file:** `hlf_mcp/hlf/audit_chain.py` (lines 32–191)

### 5.6 JSON-LD Context

All provenance artifacts are serializable to JSON-LD with the following context:

```json
{
  "@context": {
    "hlf": "https://hlf.spec/v3#",
    "evidence_id": "hlf:evidenceId",
    "artifact_type": "hlf:artifactType",
    "content_hash": "hlf:contentHash",
    "provenance_chain": "hlf:provenanceChain",
    "confidence": "hlf:confidence",
    "derivation_kind": "hlf:derivationKind",
    "merkle_hash": "hlf:merkleHash",
    "trust_root": "hlf:trustRoot",
    "attested_by": "hlf:attestedBy"
  }
}
```

---

## 6. Merkle Chain Format

### 6.1 Chain Entry

Each chain entry in a JSONL file has the structure defined in §5.5. The chain is verified by iterating entries in order:

```
prev_hash = "0" * 64  (genesis)
for entry in file:
    payload = json.dumps({"event": entry.event, "data": entry.data}, sort_keys=True)
    computed = SHA-256(prev_hash + payload)
    assert computed == entry.trace_id
    prev_hash = computed
```

### 6.2 Merkle DR Backup

Disaster recovery backups use the following directory structure:

```
<backup_dir>/
├── manifest.json              # Signed chain metadata
├── chains/
│   ├── latent_traces.jsonl    # Latent execution traces
│   └── hlf_mcp.audit.jsonl   # Audit chain entries
└── signatures/
    ├── latent_traces.jsonl.sig   # HMAC-SHA256 per file
    ├── hlf_mcp.audit.jsonl.sig
    └── manifest.json.sig
```

#### Manifest Structure

```json
{
  "version": 1,
  "backup_type": "hlf-merkle-dr",
  "timestamp_utc": "2026-05-18T04:15:00Z",
  "combined_merkle_root": "<SHA-256 hex>",
  "chain_count": 2,
  "chains": {
    "latent_traces": {
      "file": "latent_traces.jsonl",
      "merkle_root": "<SHA-256 hex>",
      "entry_count": 42,
      "size_bytes": 12345,
      "signature": "<HMAC-SHA256 hex>"
    },
    "hlf_mcp.audit": {
      "file": "hlf_mcp.audit.jsonl",
      "merkle_root": "<SHA-256 hex>",
      "entry_count": 128,
      "size_bytes": 45678,
      "signature": "<HMAC-SHA256 hex>"
    }
  }
}
```

**Source file:** `hlf_mcp/hlf/merkle_dr.py` (lines 8–19, 176–183)

### 6.3 Hash Computation

#### Per-Chain Root

For each JSONL chain file, the Merkle root is the final `trace_id` after processing all entries:

```
root = reduce(lambda h, e: SHA-256(h + canonical_payload(e)), entries, "0"*64)
```

#### Combined Root

Chains are sorted alphabetically by name:

```
parts = sorted([f"{name}:{root}" for name, root in chain_roots.items()])
combined_root = SHA-256("|".join(parts))
```

**Critical ordering invariant:** `combined_root_hashes.sort()` must be called before hashing. `json.dumps(sort_keys=True)` is insufficient because it reorders nested dict keys but does not guarantee consistent top-level ordering when keys vary across executions.

**Source file:** `hlf_mcp/hlf/merkle_dr.py` (lines 54–86, 168–174)

### 6.4 Signing

- **Algorithm:** HMAC-SHA256
- **Key derivation:** `SHA-256("hlf-merkle-dr-v1:" + HLF_MASTER_KEY)`
- **Verification:** Constant-time comparison via `hmac.compare_digest()`

Each file signature covers the entire file content. Manifest signature covers the manifest JSON (excluding the signature field itself).

**Source file:** `hlf_mcp/hlf/merkle_dr.py` (lines 89–99)

---

## 7. Effect Algebra

### 7.1 Effect Classes

Every operation in HLF is categorized into one of 33 effect classes:

| Effect Class | System Boundary | Mutating? |
|-------------|-----------------|-----------|
| `AGENT_DELEGATION` | internal | yes |
| `ASSERTION` | internal | no |
| `AUDIT_LOG` | internal | yes |
| `CRYPTOGRAPHIC_HASH` | internal | no |
| `EMBEDDING_GENERATION` | model | no |
| `ENVIRONMENT_READ` | external | no |
| `FILE_READ` | external | no |
| `FILE_WRITE` | external | yes |
| `FORMAL_VERIFICATION` | model | no |
| `GUARDED_ACTUATION` | external | yes |
| `GOVERNANCE_VOTE` | internal | yes |
| `LATENT_COMMUNICATION` | model | no |
| `LOCAL_ANALYSIS` | internal | no |
| `MEMORY_READ` | internal | no |
| `MEMORY_WRITE` | internal | yes |
| `MERKLE_APPEND` | internal | yes |
| `MODEL_INFERENCE` | model | no |
| `MULTIMODAL_AUDIO` | model | no |
| `MULTIMODAL_OCR` | model | no |
| `MULTIMODAL_VIDEO` | model | no |
| `MULTIMODAL_VISION` | model | no |
| `NETWORK_READ` | external | no |
| `NETWORK_WRITE` | external | yes |
| `PROCESS_SPAWN` | external | yes |
| `ROUTE_SELECTION` | internal | no |
| `SAFETY_STOP` | external | yes |
| `SENSOR_READ` | external | no |
| `SIMILARITY_MATH` | internal | no |
| `TIMING` | internal | no |
| `TOKEN_TRANSFORM` | internal | no |
| `TRAJECTORY_PLAN` | internal | no |
| `VERIFICATION` | internal | no |
| `WEB_SEARCH` | external | no |
| `WORLD_STATE_READ` | external | no |

**Source file:** `hlf_mcp/hlf/typed_contracts.py` (lines 202–241)

### 7.2 Failure Modes

| Failure Mode | Recoverable? | Security Sensitive? | Severity |
|-------------|--------------|---------------------|----------|
| `EXECUTION_ERROR` | no | no | error |
| `GOVERNANCE_ERROR` | no | yes | critical |
| `INFERENCE_ERROR` | sometimes | no | error |
| `IO_ERROR` | yes | no | error |
| `MEMORY_ERROR` | no | no | critical |
| `NETWORK_ERROR` | yes | no | error |
| `POLICY_DENIED` | no | yes | warning |
| `TIMEOUT_ERROR` | yes | no | error |
| `VALIDATION_ERROR` | no | no | error |
| `VERIFICATION_ERROR` | no | yes | critical |

**Source file:** `hlf_mcp/hlf/typed_contracts.py` (lines 324–367)

### 7.3 Proof Requirements

| Level | Description |
|-------|-------------|
| `NONE` | No proof required — best-effort execution |
| `RUNTIME_CHECKED` | Assertions checked at runtime |
| `VERIFICATION_ADMITTED` | Z3 solver proof admitted into evidence |
| `OPERATOR_REVIEW_OR_VERIFIED_ADMISSION` | Human review OR formal verification required |

**Source file:** `hlf_mcp/hlf/typed_contracts.py` (lines 374–388)

### 7.4 Effect Combinators

Effects compose via five combinators forming the `TypedEffect` sum type:

```python
TypedEffect = Union[
    TypedEffectDeclaration,  # atomic effect leaf
    NoEffect,                # identity element: ∅
    EffectChain,             # sequential: first >> second
    EffectParallel,          # parallel: left || right
    EffectConditional,       # branch: if condition ? then : else
    EffectIterate,           # bounded loop: body until condition (max N iterations)
]
```

#### Algebraic Laws

| Law | Expression | Property |
|-----|-----------|----------|
| Associativity | `(a >> b) >> c ≡ a >> (b >> c)` | Chain composition is associative |
| Left Identity | `NoEffect() >> a ≡ a` | NoEffect is left identity |
| Right Identity | `a >> NoEffect() ≡ a` | NoEffect is right identity |
| Idempotence | `a \|\| a ≡ a` (for pure effects) | Parallel of identical pure effects = single effect |

**Source file:** `hlf_mcp/hlf/typed_effect_algebra.py` (lines 44–185, 579–600)

### 7.5 TypedEffectDeclaration

The fully specified contract for a single effect:

```python
@dataclass(slots=True)
class TypedEffectDeclaration:
    function_name: str                           # Unique function identifier
    input_contract: InputContract                # Validated input schema
    output_contract: OutputContract              # Validated output schema
    effect_class: EffectClass                    # One of 33 effect classes
    failure_modes: list[FailureMode]             # Possible failure modes
    proof_requirement: ProofRequirement          # Required proof level
    safety_class: str                            # "none" | "bounded" | "high" | "critical"
    review_posture: str                          # "none" | "operator_review" | "post_action_review"
    execution_mode: str                          # "direct" | "simulation_only" | "simulation_preferred" | "replay_only"
    side_effects: list[str]                      # Named side effects produced
    required_evidence: list[str]                 # Evidence artifacts that must be produced
    egress_validation: dict[str, Any]            # Egress validation rules
    supervisory_only: bool                       # If True, only sovereign tier may invoke
```

**Source file:** `hlf_mcp/hlf/typed_contracts.py` (lines 697–825)

---

## 8. Operator Semantics

### 8.1 Operator Taxonomy

46 canonical operators across 10 families:

| Family | Operators |
|--------|-----------|
| **ARITHMETIC** | `add`, `sub`, `mul`, `div`, `mod`, `neg`, `pow` |
| **COMPARISON** | `eq`, `neq`, `lt`, `gt`, `leq`, `geq` |
| **LOGICAL** | `and_op`, `or_op`, `not_op` |
| **CONTAINER** | `len`, `get`, `set`, `contains`, `append`, `remove`, `keys`, `values` |
| **SET_THEORY** | `union`, `intersection`, `difference`, `subset` |
| **STRING_OPS** | `concat`, `slice`, `format`, `upper`, `lower`, `split` |
| **JSON_OPS** | `merge`, `project`, `flatten` |
| **MAP_OPS** | `lookup`, `insert`, `delete` |
| **RATIONAL_OPS** | `numer`, `denom`, `simplify` |
| **TYPE_OPS** | `cast`, `is_instance` |

**Source file:** `hlf_mcp/hlf/operand_coverage.py` (lines 42–157)

### 8.2 Type × Operator Coverage Matrix

Every `(HlfType, operator)` pair is classified as:

- **covered** — semantically meaningful AND defined
- **gap** — semantically meaningful but NOT yet defined
- **excluded** — semantically meaningless for this type

#### Primitive Types

| Type | Arithmetic | Comparison | Logical | Container | Set | String | JSON | Map | Rational | Type |
|------|-----------|------------|---------|-----------|-----|--------|------|-----|----------|------|
| ℕ | covered | covered | not_op | len | — | — | — | — | — | covered |
| ℤ | covered | covered | not_op | len | — | — | — | — | — | covered |
| ℝ | covered | covered | not_op | len | — | — | — | — | — | covered |
| ℚ | add/sub/mul/div/neg | covered | — | — | — | — | — | — | covered | covered |
| 𝕊 | — | covered | not_op | len/get/contains | — | covered | — | — | — | covered |
| 𝔹 | — | eq/neq | covered | — | — | — | — | — | — | covered |
| 𝕁 | — | eq/neq | — | len/get/set/contains/keys/values | — | slice | covered | — | — | covered |
| 𝔸 | — | eq/neq | not_op | — | — | — | — | — | — | covered |

#### Parametric Types

| Type | Comparison | Container | Set | String | Map | Type |
|------|-----------|-----------|-----|--------|-----|------|
| List⟨T⟩ | covered | covered | covered | concat/slice | — | covered |
| Set⟨T⟩ | covered | len/contains/append/remove/keys/values | covered | — | — | covered |
| Map⟨K,V⟩ | covered | len/contains/keys/values/get/set | — | — | covered | covered |

#### Refinement Types

| Type | Comparison | Logical | Type |
|------|-----------|---------|------|
| {var:T\|pred} | eq/neq | not_op | covered (delegates to T) |

**Source file:** `hlf_mcp/hlf/operand_coverage.py` (lines 172–272)

---

## 9. Capsule Governance

### 9.1 IntentCapsule

The `IntentCapsule` is the fundamental unit of governed execution. Every MCP invocation runs inside a capsule.

```python
@dataclass
class IntentCapsule:
    # Capability bounds
    allowed_tags: set[str]              # Empty = all allowed
    denied_tags: set[str]               # Explicitly denied tags
    allowed_tools: set[str]             # Empty = all allowed (if no deny)
    denied_tools: set[str]              # Explicitly denied tool/function names
    max_gas: int                        # Gas budget cap
    tier: str                           # Effective tier (hearth|forge|sovereign)
    read_only_vars: set[str]            # Variables that cannot be mutated

    # Identity
    base_tier: str = "hearth"           # Original deployment tier
    agent_id: str = "unknown-agent"     # Owning agent identifier
    capsule_id: str = uuid4()           # Unique capsule ID (auto-generated)
    requested_tier: str = "hearth"      # Tier requested (may exceed base_tier)

    # Trust
    pointer_trust_mode: str = "enforce" # "enforce" | "audit" | "disabled"
    trusted_pointers: dict = {}         # Registry of trusted pointer refs

    # Approval
    approval_required_tags: set[str] = set()
    approval_required_tools: set[str] = set()
    approved_by: str = ""               # Who approved (empty = unapproved)
    approval_token: str = ""            # SHA-256[:24] proving approval

    # Metadata
    metadata: dict[str, Any] = {}       # Arbitrary metadata
```

**Source file:** `hlf_mcp/hlf/capsules.py` (lines 67–88)

### 9.2 Tier Model

```python
_TIER_RANK = {"hearth": 0, "forge": 1, "sovereign": 2}
```

| Tier | Gas | Typical Agent | Restrictions |
|------|-----|---------------|--------------|
| `hearth` | 100 | Simple agents, read-only queries | No SPAWN, SHELL_EXEC, WEB_SEARCH |
| `forge` | 500 | Code agents, builders | No SPAWN, SHELL_EXEC, WEB_SEARCH, spawn_agent, z3_verify |
| `sovereign` | 1000 | Orchestrators, HITL operators | No restrictions |

Factory functions produce pre-configured capsules:
- `hearth_capsule()` — gas=100, restricted tags, `read_only_vars={"SYS_INFO", "NOW"}`
- `forge_capsule()` — gas=500, broad whitelist, denied: SPAWN, SHELL_EXEC, WEB_SEARCH, spawn_agent, z3_verify
- `sovereign_capsule()` — gas=1000, no restrictions
- `capsule_for_tier(tier)` — dispatcher

**Source file:** `hlf_mcp/hlf/capsules.py` (lines 35–38, 307–456)

### 9.3 HITL Gate Protocol

Human-In-The-Loop approval uses a file-based pending queue with strict timeout semantics.

#### ApprovalRequest

```python
@dataclass
class ApprovalRequest:
    capsule_id: str                    # Capsule requiring approval
    agent_id: str                      # Requesting agent
    tier: str                          # Agent tier at request time
    intent_summary: str                # Truncated to 200 chars
    output_preview: str                # First 200 chars of output
    manifest_hash: str                 # SHA-256 of manifest
    output_hash: str                   # SHA-256 of output
    gas_consumed: int                  # Gas used
    gas_limit: int                     # Gas budget
    provenance_hashes: list[str] = []  # Linked provenance
    created_at: str = now_iso()        # ISO 8601 timestamp
    status: str = "AWAITING_HUMAN_APPROVAL"
    approved_by: str = ""
    approved_at: str = ""
    rejection_reason: str = ""
    timeout_seconds: int = 600         # 10 minutes
```

#### State Machine

```
                    ┌──────────────────────────┐
                    │ AWAITING_HUMAN_APPROVAL  │
                    └──────┬───────┬───────┬───┘
                           │       │       │
                    approve()  reject()  timeout (600s)
                           │       │       │
                           ▼       ▼       ▼
                      COMPLETED  REJECTED_HUMAN  REJECTED_TIMEOUT
```

#### Approval Token

```python
payload = f"{capsule_id}|{base_tier}|{requested_tier}|{sorted_requirements}"
approval_token = SHA-256(payload)[:24]  # first 24 hex chars
```

Where `requirements` are sorted serializations of `{type, scope, value}` triples from approval_required_tags and approval_required_tools.

#### Operator CLI

```bash
hlf-operator approve --capsule-id <id> [--reason "..."]
hlf-operator reject --capsule-id <id> --reason "..."
hlf-operator list [--status pending|completed|rejected]
```

**Source file:** `hlf_mcp/hlf/hitl_gate.py` (lines 40–270)

### 9.4 Secret Management

#### Encryption Scheme

| Parameter | Value |
|-----------|-------|
| Algorithm | AES-256-GCM |
| Key derivation | PBKDF2-HMAC-SHA256 |
| Iterations | 600,000 |
| Salt length | 32 bytes |
| Nonce length | 12 bytes |
| Key length | 32 bytes |
| Master key source | `HLF_MASTER_KEY` environment variable |

#### Format

```python
{
    "ciphertext_b64": base64(AES-GCM(ciphertext + auth_tag)),
    "nonce_b64": base64(12_byte_random_nonce),
    "salt_b64": base64(32_byte_random_salt),
}
```

#### Security Properties

- Plaintext never stored in memory after encryption
- `__repr__()` / `__str__()` redact all secret values
- `merkle_metadata` returns only `SHA-256(ciphertext)` — suitable for public audit chains
- `to_dict()` serializes ciphertext only (no plaintext)
- Glyph syntax: `∇ [SECRET] name="x" value="y"` or `∇ [SECRET] name="x"` (reads from env var `x`)

**Source file:** `hlf_mcp/hlf/secret_capsule.py` (lines 48–315)

### 9.5 Model Version Pinning

The `CapabilityManifest` carries a `model_versions` field:

```python
model_versions: dict[str, str] = {}  # model_name → expected_sha256
```

Before inference, the model orchestrator:
1. Computes SHA-256 of the loaded model weights
2. Compares against `model_versions[name]`
3. If mismatch: raises `CapsuleViolation` — execution is blocked
4. If match: proceeds with inference

This prevents silent model swaps (e.g., Ollama pull updating a tag).

**Source file:** `hlf_mcp/hlf/model_version.py`

---

## 10. MCP Tool Interface

### 10.1 Core Tools

Registered in `hlf_mcp/server_core.py` via `register_core_tools()`. These are always visible regardless of tier.

| Tool | Signature | Auth Required |
|------|-----------|---------------|
| `hlf_compile` | `(source: str) → dict` | stdio: no, HTTP: token |
| `hlf_format` | `(source: str) → dict` | stdio: no, HTTP: token |
| `hlf_lint` | `(source: str, gas_limit: int = 1000, token_limit: int = 30) → dict` | stdio: no, HTTP: token |
| `hlf_run` | `(source: str, gas_limit: int = 1000, variables: dict = None, agent_id: str = "", ingress_nonce: str = "") → dict` | stdio: no, HTTP: token |
| `hlf_code_execute` | `(source: str, entrypoint: str = "", gas_limit: int = 500, tier: str = "hearth", dry_run: bool = False, variables: dict = None) → dict` | stdio: no, HTTP: token |
| `hlf_validate` | `(source: str) → dict` | stdio: no, HTTP: token |
| `hlf_swarm_mechanics` | `(source: str = "", handoff: dict = None, votes: list = None, dissent: list = None, progress_events: list = None, quorum: str = "strict", persist: bool = True) → dict` | stdio: no, HTTP: token |
| `hlf_benchmark` | `(source: str, compare_text: str = None, domain: str = None) → dict` | stdio: no, HTTP: token |
| `hlf_benchmark_suite` | `() → dict` | stdio: no, HTTP: token |
| `hlf_real_workflow_benchmark` | `(workflow_ids: list = None, mode: str = "patch-plan", persist: bool = True) → dict` | stdio: no, HTTP: token |
| `hlf_disassemble` | `(bytecode_hex: str) → dict` | stdio: no, HTTP: token |
| `hlf_submit_ast` | `(ast_json: str) → dict` | stdio: no, HTTP: token |
| `hlf_test_suite_summary` | `(metrics_dir: str = None, include_output: bool = False) → dict` | stdio: no, HTTP: token |
| `hlf_capture_symbolic_surface` | `(source: str, surface_id: str = "", goal_id: str = "") → dict` | stdio: no, HTTP: token |
| `hlf_governance_proof_verify` | `(proof: dict, include_report: bool = False) → dict` | stdio: no, HTTP: token |
| `hlf_weekly_evidence_summary` | `(metrics_dir: str = None) → dict` | stdio: no, HTTP: token |
| `hlf_compile_wasm` | `(source: str, module_name: str = "hlf_module") → dict` | stdio: no, HTTP: token |
| `janus_crawl` | `(url: str, depth: int = 1, endpoint: str = "http://localhost:8100") → dict` | stdio: no, HTTP: token |
| `janus_query` | `(query_text: str, endpoint: str = "http://localhost:8100") → dict` | stdio: no, HTTP: token |
| `janus_archive` | `(resource_id: str, endpoint: str = "http://localhost:8100") → dict` | stdio: no, HTTP: token |
| `hlf_latent_recursive_infer` | `(prompt: str, recursion_rounds: int = 2, agent_models_json: str = "{}") → dict` | stdio: no, HTTP: token |
| `hlf_entropy_anchor` | `(source: str, expected_intent: str = "", threshold: float = 0.5, policy_mode: str = "advisory", subject_agent_id: str = "") → dict` | stdio: no, HTTP: token |

### 10.2 Enterprise Tools

Registered in `hlf_mcp/server_enterprise.py` via `register_enterprise_tools()`. Visibility is tier-gated.

#### Hearth Tier (read-only audit + status)

| Tool | Description |
|------|-------------|
| `hlf_evidence_show` | Show evidence for a capsule (with optional latent trace rendering) |
| `hlf_evidence_list` | List recent evidence records |
| `hlf_evidence_verify` | Verify Merkle chain integrity for a capsule |
| `hlf_merkle_chain_status` | Show Merkle chain health summary |
| `hlf_ab_test_show` | Show A/B test results |
| `hlf_ab_test_list` | List all A/B tests |
| `hlf_ab_test_run` | Run a previously defined A/B test |
| `hlf_model_version_check` | Check model version against manifest |
| `hlf_chaos_status` | Show chaos engineering test status |
| `hlf_hitl_list` | List HITL approval requests |

#### Forge Tier (hearth + operational tools)

| Tool | Description |
|------|-------------|
| `hlf_load_test_run` | Execute load test with config |
| `hlf_load_test_status` | Show load test status |
| `hlf_merkle_verify` | Verify Merkle DR backup integrity |
| `hlf_merkle_export` | Export Merkle chains to backup |
| `hlf_secret_retrieve` | Retrieve decrypted secret value |
| `hlf_ab_test_define` | Define a new A/B test |

#### Sovereign Tier (hearth + forge + privileged tools)

| Tool | Description |
|------|-------------|
| `hlf_secret_store` | Store encrypted secret |
| `hlf_secret_rotate` | Rotate secret value |
| `hlf_hitl_approve` | Approve HITL request |
| `hlf_hitl_reject` | Reject HITL request |

### 10.3 Tier-Gated Visibility

Tier gating is enforced at MCP tool registration time. The `ENTERPRISE_TOOL_TIERS` dict maps each enterprise tool to its minimum required tier:

```python
ENTERPRISE_TOOL_TIERS = {
    # hearth (visible to all)
    "hlf_evidence_show": "hearth",
    "hlf_evidence_list": "hearth",
    # ... (10 hearth tools)
    # forge (visible to forge + sovereign)
    "hlf_load_test_run": "forge",
    # ... (6 forge tools)
    # sovereign (visible to sovereign only)
    "hlf_secret_store": "sovereign",
    # ... (4 sovereign tools)
}
```

Tier is resolved from:
1. `HLF_AGENT_TIER` environment variable (HTTP transport)
2. Defaults to `"sovereign"` (stdio transport — local trust)

A tool is visible to `listTools` if and only if:
```
TIER_RANK[agent_tier] >= TIER_RANK[ENTERPRISE_TOOL_TIERS[tool_name]]
```

**Source file:** `hlf_mcp/hlf/server_enterprise.py` (lines ~30, ~1040)

---

## 11. Appendix: Opcode Quick Reference

```
Hex  Mnemonic        Gas  Stack Effect        Description
───  ──────────────  ───  ─────────────────   ──────────────────────────────
00   NOP             0    ∅ → ∅               No operation
01   PUSH_CONST      1    ∅ → value           Push constant from pool
02   STORE           2    value → ∅           Pop TOS, store to variable
03   LOAD            1    ∅ → value           Push variable onto stack
04   STORE_IMMUT     3    value → ∅           Store immutable variable
10   ADD             2    b,a → a+b           Addition
11   SUB             2    b,a → a-b           Subtraction
12   MUL             3    b,a → a*b           Multiplication
13   DIV             5    b,a → a/b           Division
14   MOD             3    b,a → a%b           Modulus
15   NEG             1    a → -a              Negation
20   CMP_EQ          1    b,a → a==b          Equal
21   CMP_NE          1    b,a → a!=b          Not equal
22   CMP_LT          1    b,a → a<b           Less than
23   CMP_LE          1    b,a → a<=b          Less or equal
24   CMP_GT          1    b,a → a>b           Greater than
25   CMP_GE          1    b,a → a>=b          Greater or equal
30   AND             1    b,a → a&&b          Logical AND
31   OR              1    b,a → a||b          Logical OR
32   NOT             1    a → !a              Logical NOT
33   POP             0    a → ∅               Pop and discard
40   JMP             1    ∅ → ∅               Unconditional jump
41   JZ              2    a → ∅               Jump if zero/false
42   JNZ             2    a → ∅               Jump if nonzero/true
50   CALL_BUILTIN    5    args... → result    Call built-in function
51   CALL_HOST       10   args... → result    Call host function
52   CALL_TOOL       15   args... → result    Call registered tool
53   OPENCLAW_TOOL   20   args... → result    Call OpenClaw sandboxed tool
60   TAG             1    ∅ → ∅               Tag annotation
61   INTENT          2    ∅ → ∅               Intent declaration
62   RESULT          1    ∅ → result          Push result value
63   MEMORY_STORE    3    value → ∅           Store to RAG memory
64   MEMORY_RECALL   2    ∅ → value           Recall from RAG memory
65   SPEC_DEFINE     4    ∅ → ∅               Define instinct spec
66   SPEC_GATE       4    ∅ → ∅               Gate instinct spec
67   SPEC_UPDATE     4    ∅ → ∅               Update instinct spec
68   SPEC_SEAL       4    ∅ → ∅               Seal instinct spec
FF   HALT            0    ∅ → ∅               Halt execution
```

---

*End of HLF v3 Formal Specification.*
