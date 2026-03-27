"""
HLF v3 LALR(1) Grammar (Lark format).

Hieroglyphic Logic Framework — deterministic orchestration protocol
for zero-trust agent execution with cryptographic governance.

Statement types (21 top-level + block forms):
  Glyph statements  : Δ Ж ⨝ ⌘ ∇ ⩕ ⊎
  Declarations      : SET (immutable), ASSIGN (mutable)
  Control flow      : IF/ELIF/ELSE/ENDIF (flat), IF/ELIF/ELSE blocks
  Loops             : FOR ... IN ... (block)
  Parallel          : PARALLEL block+
  Invocations       : CALL, TOOL, FUNCTION (with block body)
  Capsule           : INTENT name args block
  Import            : IMPORT
  Logging           : LOG / RESULT
  Memory            : MEMORY, RECALL
  Instinct specs    : SPEC_DEFINE, SPEC_GATE, SPEC_UPDATE, SPEC_SEAL

Glyph → semantic mapping:
  Δ  (Delta)   — analyze / primary action
  Ж  (Zhe)     — enforce / constrain / assert
  ⨝  (Join)    — consensus / join / vote
  ⌘  (Command) — command / delegate / route
  ∇  (Nabla)   — source / parameter / data flow
  ⩕  (Bowtie)  — priority / weight / rank
  ⊎  (Union)   — branch / condition / union

Expression types (for block-form control flow):
  Arithmetic : + - * / %
  Comparison : == != < > <= >=
  Logical    : AND OR NOT
  Atoms      : string, int, float, var_ref ($VAR), ident, path
"""

HLF_GRAMMAR = r"""
start: header statement* OMEGA

OMEGA: "Ω"

header: HEADER_PREFIX _hlf_version RBRACKET
HEADER_PREFIX: "[HLF-v"
RBRACKET: "]"
LBRACKET: "["

_hlf_version: INT ("." INT)*

?statement: glyph_stmt
          | assign_stmt
          | set_stmt
          | if_block_stmt
          | for_stmt
          | parallel_stmt
          | func_block_stmt
          | intent_stmt
          | tool_stmt
          | call_stmt
          | return_stmt
          | result_stmt
          | log_stmt
          | import_stmt
          | memory_stmt
          | recall_stmt
          | spec_define_stmt
          | spec_gate_stmt
          | spec_update_stmt
          | spec_seal_stmt

// ── Glyph statement ───────────────────────────────────────────────────────────
glyph_stmt: GLYPH tag? arg_list?

GLYPH: /[ΔЖ⨝⌘∇⩕⊎]/

tag: LBRACKET TAG_NAME RBRACKET
TAG_NAME: /[A-Z][A-Z0-9_]*/

arg_list: argument+

argument: IDENT "=" value -> kv_arg
        | value            -> pos_arg

value: ESCAPED_STRING    -> str_val
     | FLOAT             -> float_val
     | INT               -> int_val
     | VAR_REF           -> var_ref_val
     | PATH              -> path_val
     | IDENT             -> ident_val

// ── Declaration statements ────────────────────────────────────────────────────
// Immutable binding — SET name = value
set_stmt:    KW_SET    IDENT "=" value
// Mutable binding — ASSIGN name = expr  (also bare name = expr via assign_stmt)
assign_stmt: KW_ASSIGN IDENT "=" expr

// ── Block-form control flow ───────────────────────────────────────────────────
// IF expr { ... } (ELIF expr { ... })* (ELSE { ... })?
// Block is optional: flat "IF expr" (no body) is backward-compat shorthand.
if_block_stmt: KW_IF expr block? elif_clause* else_clause?

elif_clause: KW_ELIF expr block
else_clause: KW_ELSE block

// FOR name IN expr { ... }
for_stmt: KW_FOR IDENT KW_IN expr block

// PARALLEL { ... } { ... }+
parallel_stmt: KW_PARALLEL block block+

// ── Function and Intent blocks ────────────────────────────────────────────────
func_block_stmt: KW_FUNCTION IDENT param_list? block

param_list: "(" param_item ("," param_item)* ")"
param_item: IDENT (":" IDENT)?   -> typed_param

// INTENT name args { ... } — capsule-scoped block
intent_stmt: KW_INTENT IDENT arg_list? block

// ── Explicit tool / call ──────────────────────────────────────────────────────
tool_stmt: KW_TOOL   IDENT arg_list?
call_stmt: KW_CALL   IDENT arg_list?

// ── Result / Log / Return ────────────────────────────────────────────────────
result_stmt: KW_RESULT expr (expr)?
return_stmt: KW_RETURN value?
log_stmt:    KW_LOG   value

// ── Import ───────────────────────────────────────────────────────────────────
import_stmt: KW_IMPORT PATH

// ── Memory ───────────────────────────────────────────────────────────────────
memory_stmt: KW_MEMORY LBRACKET IDENT RBRACKET arg_list?
recall_stmt: KW_RECALL LBRACKET IDENT RBRACKET

// ── Instinct Spec Lifecycle ──────────────────────────────────────────────────
spec_define_stmt: KW_SPEC_DEFINE tag? arg_list?
spec_gate_stmt:   KW_SPEC_GATE   tag? arg_list?
spec_update_stmt: KW_SPEC_UPDATE tag? arg_list?
spec_seal_stmt:   KW_SPEC_SEAL   tag? arg_list?

// ── Block ────────────────────────────────────────────────────────────────────
block: LBRACE statement* RBRACE
LBRACE: "{"
RBRACE: "}"

// ── Expression system ────────────────────────────────────────────────────────
// Arithmetic and logical expressions for block-form control flow

?expr: expr_or

expr_or:  expr_and (KW_OR  expr_and)*
expr_and: expr_not (KW_AND expr_not)*

?expr_not: KW_NOT expr_not -> not_expr
         | expr_cmp

expr_cmp: expr_add (CMP expr_add)*

expr_add: expr_mul ((ADDOP | MINUS) expr_mul)*
expr_mul: expr_unary ((MULOP) expr_unary)*

?expr_unary: MINUS expr_primary -> neg_expr
           | expr_primary

?expr_primary: ESCAPED_STRING -> str_val
             | FLOAT          -> float_val
             | INT            -> int_val
             | VAR_REF        -> var_ref_val
             | PATH           -> path_val
             | IDENT          -> ident_val
             | "(" expr ")"   -> paren_expr

ADDOP: "+"
MULOP: "*" | "/" | "%"
MINUS: "-"

// ── Keywords (priority 10 beats IDENT priority 1) ────────────────────────────
KW_ASSIGN.10:      "ASSIGN"
KW_SET.10:         "SET"
KW_IF.10:          "IF"
KW_ELIF.10:        "ELIF"
KW_ELSE.10:        "ELSE"
KW_ENDIF.10:       "ENDIF"
KW_FOR.10:         "FOR"
KW_IN.10:          "IN"
KW_PARALLEL.10:    "PARALLEL"
KW_FUNCTION.10:    "FUNCTION"
KW_INTENT.10:      "INTENT"
KW_TOOL.10:        "TOOL"
KW_CALL.10:        "CALL"
KW_RESULT.10:      "RESULT"
KW_RETURN.10:      "RETURN"
KW_LOG.10:         "LOG"
KW_IMPORT.10:      "IMPORT"
KW_MEMORY.10:      "MEMORY"
KW_RECALL.10:      "RECALL"
KW_SPEC_DEFINE.10: "SPEC_DEFINE"
KW_SPEC_GATE.10:   "SPEC_GATE"
KW_SPEC_UPDATE.10: "SPEC_UPDATE"
KW_SPEC_SEAL.10:   "SPEC_SEAL"
KW_AND.10:         "AND"
KW_OR.10:          "OR"
KW_NOT.10:         "NOT"

// ── Terminals ─────────────────────────────────────────────────────────────────
CMP:     ">=" | "<=" | "!=" | "==" | ">" | "<"
PATH.5:    /\/[^\s"\[\]\{\}\n]+/
FLOAT.3:   /[+-]?[0-9]+\.[0-9]+/
INT.2:     /[+-]?[0-9]+/
VAR_REF.4: /\$[A-Z_][A-Z0-9_]*/
IDENT.1:   /[a-zA-Z_][a-zA-Z0-9_\-.:@]*/

%import common.ESCAPED_STRING
%ignore /[ \t\n\r]+/
%ignore /#[^\n]*/
"""

# Canonical glyph definitions for reference and documentation
GLYPHS = {
    "Δ": {"name": "DELTA", "role": "analyze", "ascii": "ANALYZE", "opcode": 0x51},
    "Ж": {"name": "ZHE", "role": "enforce", "ascii": "ENFORCE", "opcode": 0x60},
    "⨝": {"name": "JOIN", "role": "consensus", "ascii": "JOIN", "opcode": 0x61},
    "⌘": {"name": "COMMAND", "role": "delegate", "ascii": "CMD", "opcode": 0x52},
    "∇": {"name": "NABLA", "role": "source", "ascii": "SOURCE", "opcode": 0x01},
    "⩕": {"name": "BOWTIE", "role": "priority", "ascii": "PRIORITY", "opcode": 0x11},
    "⊎": {"name": "UNION", "role": "branch", "ascii": "BRANCH", "opcode": 0x41},
}

# Canonical tag definitions
TAGS = {
    "INTENT": "Primary intent declaration",
    "CONSTRAINT": "Hard constraint enforcement",
    "ASSERT": "Assertion / precondition check",
    "EXPECT": "Expected output type or value",
    "DELEGATE": "Sub-agent delegation target",
    "ROUTE": "Model routing strategy",
    "SOURCE": "Data source reference",
    "PARAM": "Runtime parameter binding",
    "PRIORITY": "Execution priority level",
    "VOTE": "Consensus vote configuration",
    "RESULT": "Result capture binding",
    "MEMORY": "Memory node reference",
    "RECALL": "Memory retrieval query",
    "GATE": "Spec gate assertion",
    "DEFINE": "Spec definition block",
    "MIGRATION": "Database migration spec",
    "MIGRATION_SPEC": "Database migration specification",
    "ALIGN": "ALIGN Ledger governance rule",
}

# ASCII word-form aliases for Unicode glyphs (Pass 0 substitution, glyph-position only).
# Applied via word-boundary regex BEFORE char-level CONFUSABLES so that string values
# containing these words (e.g. goal="ANALYZE_MODE") are NOT replaced.
ASCII_ALIASES: dict[str, str] = {
    # DELTA Δ — analyze / reason
    "ANALYZE": "Δ",
    "ANALYSE": "Δ",  # British English
    "ANALYSER": "Δ",  # French
    "ANALIZAR": "Δ",  # Spanish
    # ZHE Ж — enforce / constrain
    "ENFORCE": "Ж",
    "CONSTRAIN": "Ж",
    # JOIN ⨝ — consensus / merge
    "JOIN": "⨝",
    "CONSENSUS": "⨝",
    # COMMAND ⌘ — delegate / execute
    "CMD": "⌘",
    "COMMAND": "⌘",
    # NABLA ∇ — source / gradient
    "SOURCE": "∇",
    # BOWTIE ⩕ — priority / weight
    "PRIORITY": "⩕",
    # UNION ⊎ — branch / fork
    "BRANCH": "⊎",
    "UNION": "⊎",
    # OMEGA Ω — end / terminate
    "END": "Ω",
    "OMEGA": "Ω",
}

# Homoglyph confusables map (Pass 0 normalization)
CONFUSABLES: dict[str, str] = {
    # Cyrillic lookalikes (IDN homograph attack vector)
    "а": "a",
    "е": "e",
    "о": "o",
    "р": "p",
    "с": "c",
    "х": "x",
    "у": "y",
    "А": "A",
    "Е": "E",
    "О": "O",
    "Р": "P",
    "С": "C",
    "Х": "X",
    # Greek lookalikes
    "α": "a",
    "ε": "e",
    "ο": "o",
    "ρ": "p",
    "σ": "s",
    # Mathematical operator lookalikes
    "−": "-",
    "×": "*",
    "÷": "/",
    "≠": "!=",
    "≤": "<=",
    "≥": ">=",
}
