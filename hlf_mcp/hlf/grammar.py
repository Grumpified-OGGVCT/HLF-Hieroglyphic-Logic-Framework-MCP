"""
HLF v3 LALR(1) Grammar (Lark format).

Hieroglyphic Logic Framework — deterministic orchestration protocol
for zero-trust agent execution with cryptographic governance.

Statement types (21 top-level + block forms):
  Glyph statements  : Δ Ж ⨝ ⌘ ∇ ⩕ ⊎ ⌂ Σ
  Declarations      : SET (immutable), ASSIGN (mutable)
  Control flow      : IF/ELIF/ELSE/ENDIF (flat), IF/ELIF/ELSE blocks
  Loops             : FOR ... IN ... (block)
  Parallel          : PARALLEL block+
  Invocations       : CALL, TOOL, MODULE/FUNCTION (with block body)
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
  ⌂  (House)   — memory anchor / recall provenance
  Σ  (Sigma)   — summary / aggregate / capsule surface

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

statement: glyph_stmt
         | assign_stmt
         | set_stmt
         | if_block_stmt
         | for_stmt
         | parallel_stmt
         | module_block_stmt
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
         | pipe_stmt
         | template_stmt

         // ── RFC 9005: Glyph-based statements (additive — keyword forms co-exist) ──
         | glyph_assign_stmt
         | struct_stmt
         | sync_stmt
         | cond_stmt

// ── Glyph statement ───────────────────────────────────────────────────────────
glyph_stmt: GLYPH tag? arg_list? validate_annot?

GLYPH: /[ΔЖ⨝⌘∇⩕⌂Σ]/

// ── Pipe operator (statement chaining) ────────────────────────────────────────
PIPE: "→"
pipe_stmt: glyph_stmt (PIPE statement)+
         | tool_stmt (PIPE statement)+
         | call_stmt (PIPE statement)+

// ── RFC 9005: Glyph-based assignment (←) ──────────────────────────────────────
glyph_assign_stmt: IDENT type_ann? ASSIGN_GLYPH assign_rhs epistemic?
assign_rhs: expr | call_stmt | tool_stmt

// ── RFC 9005: Type annotations (:: TYPE_SYM | param_type_sym | refine_type) ──
type_ann: TYPE_ANN (TYPE_SYM | param_type_sym | refine_type)

// ── RFC 9005: Epistemic confidence modifier (_{ρ:val}) ────────────────────────
EPISTEMIC_START.10: "_{"
CONFIDENCE_NUM.5: /[0-9]+(\.[0-9]+)?/
epistemic: EPISTEMIC_START "ρ" ":" CONFIDENCE_NUM "}"

// ── RFC 9007: Struct definitions (≡) ──────────────────────────────────────────
struct_stmt: IDENT STRUCT_GLYPH LBRACE struct_field ("," struct_field)* RBRACE epistemic?
struct_field: STRUCT_FIELD_IDENT ":" TYPE_SYM
STRUCT_FIELD_IDENT.5: /[a-zA-Z_][a-zA-Z0-9_\-@]*/

// ── RFC 9005: Sync barrier (⋈) ────────────────────────────────────────────────
sync_stmt: SYNC_GLYPH LBRACKET IDENT ("," IDENT)* RBRACKET PIPE statement epistemic?

// ── RFC 9005: Conditional logic (⊎ ⇒ ⇌) ──────────────────────────────────────
cond_stmt: COND_GLYPH cond_expr THEN_GLYPH statement (ELSE_GLYPH statement)? epistemic?
cond_expr: expr

tag: LBRACKET TAG_NAME RBRACKET
TAG_NAME: /[A-Z][A-Z0-9_]*/

arg_list: argument+

argument: IDENT "=" value -> kv_arg
         | REF IDENT       -> ref_arg
         | value            -> pos_arg

value: ESCAPED_STRING    -> str_val
     | FLOAT             -> float_val
     | INT               -> int_val
     | VAR_REF           -> var_ref_val
     | PATH              -> path_val
     | IDENT             -> ident_val

// ── @validate inline annotation ───────────────────────────────────────────────
KW_VALIDATE: /@validate/
validate_annot: KW_VALIDATE "(" validate_arg ("," validate_arg)* ")"
validate_arg: IDENT "=" value -> kv_arg

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

// ── Module, Function, and Intent blocks ───────────────────────────────────────
module_block_stmt: KW_MODULE IDENT arg_list? block
func_block_stmt: KW_FUNCTION IDENT param_list? block

param_list: "(" param_item ("," param_item)* ")"
param_item: PARAM_IDENT (":" PARAM_IDENT)?   -> typed_param

// INTENT name args { ... } — capsule-scoped block
intent_stmt: KW_INTENT IDENT arg_list? block

// ── Explicit tool / call ──────────────────────────────────────────────────────
tool_stmt: KW_TOOL   IDENT arg_list? validate_annot?
call_stmt: KW_CALL   IDENT arg_list? validate_annot?

// ── Result / Log / Return ────────────────────────────────────────────────────
result_stmt: KW_RESULT expr (expr)?
return_stmt: KW_RETURN value?
log_stmt:    KW_LOG   value

// ── Import ───────────────────────────────────────────────────────────────────
import_stmt: KW_IMPORT PATH

// ── Memory ───────────────────────────────────────────────────────────────────
memory_stmt: KW_MEMORY LBRACKET IDENT RBRACKET arg_list?
recall_stmt: KW_RECALL LBRACKET IDENT RBRACKET

// ── Template (reusable pattern blocks) ───────────────────────────────────────
template_stmt: KW_TEMPLATE IDENT block

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

expr_or:  expr_and ((KW_OR | OR_GLYPH) expr_and)*
expr_and: expr_not ((KW_AND | AND_GLYPH) expr_not)*

?expr_not: KW_NOT expr_not -> not_expr
         | NEG_GLYPH expr_primary -> not_expr
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
KW_MODULE.10:      "MODULE"
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
KW_TEMPLATE.10:    "TEMPLATE"

// ── Terminals ─────────────────────────────────────────────────────────────────
CMP:     ">=" | "<=" | "!=" | "==" | ">" | "<"

// ── RFC 9005/9007: Unicode operator glyphs ────────────────────────────────────
ASSIGN_GLYPH.10: "←"
STRUCT_GLYPH.10: "≡"
SYNC_GLYPH.10:   "⋈"
COND_GLYPH.10:   "⊎"
THEN_GLYPH.10:   "⇒"
ELSE_GLYPH.10:   "⇌"
NEG_GLYPH.10:    "¬"
AND_GLYPH.10:    "∩"
OR_GLYPH.10:     "∪"
TYPE_ANN.10:     "::"
REF.10:          "&"
TYPE_SYM.10:     "ℕ" | "ℤ" | "ℝ" | "ℚ" | "𝕊" | "𝔹" | "𝕁" | "𝔸"

// ── Parametric types: List⟨T⟩, Set⟨T⟩, Map⟨K,V⟩ ─────────────────────────────
CHEVRON_OPEN.10:  "⟨"
CHEVRON_CLOSE.10: "⟩"
param_type_sym.10: TYPE_SYM CHEVRON_OPEN TYPE_SYM ("," TYPE_SYM)* CHEVRON_CLOSE

// ── Refinement types: {var: ℕ | var > 0} ────────────────────────────────────
refine_type.10: LBRACE PARAM_IDENT ":" TYPE_SYM "|" expr RBRACE

PATH.5:    /\/[^\s"\[\]\{\}\n]+/
FLOAT.3:   /[+-]?[0-9]+\.[0-9]+/
INT.2:     /[+-]?[0-9]+/
VAR_REF.4: /\$[A-Z_][A-Z0-9_]*/
PARAM_IDENT.2: /[a-zA-Z_][a-zA-Z0-9_\-.@]*/
IDENT.1:   /[a-zA-Z_][a-zA-Z0-9_\-.:@]*/

%import common.ESCAPED_STRING
%ignore /[ \t\n\r]+/
%ignore /#[^\n]*/
"""

# Canonical glyph definitions for reference and documentation.
# `syntax=statement` glyphs compile today through the generic glyph statement
# production. `syntax=terminator` is required program structure, not a statement.
GLYPHS = {
    "Ω": {
        "name": "OMEGA",
        "role": "terminate",
        "ascii": "OMEGA",
        "opcode": None,
        "syntax": "terminator",
    },
    "Δ": {"name": "DELTA", "role": "analyze", "ascii": "ANALYZE", "opcode": 0x51, "syntax": "statement"},
    "Ж": {"name": "ZHE", "role": "enforce", "ascii": "ENFORCE", "opcode": 0x60, "syntax": "statement"},
    "⨝": {"name": "JOIN", "role": "consensus", "ascii": "JOIN", "opcode": 0x61, "syntax": "statement"},
    "⌘": {"name": "COMMAND", "role": "delegate", "ascii": "CMD", "opcode": 0x52, "syntax": "statement"},
    "∇": {"name": "NABLA", "role": "source", "ascii": "SOURCE", "opcode": 0x01, "syntax": "statement"},
    "⩕": {"name": "BOWTIE", "role": "priority", "ascii": "PRIORITY", "opcode": 0x11, "syntax": "statement"},
    "⊎": {"name": "UNION", "role": "branch", "ascii": "BRANCH", "opcode": 0x41, "syntax": "statement"},
    "⌂": {
        "name": "HOUSE",
        "role": "memory_anchor",
        "ascii": "MEMORY_ANCHOR",
        "opcode": None,
        "syntax": "statement",
    },
    "Σ": {
        "name": "SIGMA",
        "role": "summarize",
        "ascii": "SUMMARY",
        "opcode": None,
        "syntax": "statement",
    },
    # ── RFC 9005/9007: Operator glyphs (inline, not standalone statements) ──
    "←": {
        "name": "LEFT_ARROW",
        "role": "assign",
        "ascii": "<-",
        "opcode": None,
        "syntax": "operator",
    },
    "≡": {
        "name": "IDENTICAL_TO",
        "role": "struct_def",
        "ascii": "struct",
        "opcode": None,
        "syntax": "operator",
    },
    "⋈": {
        "name": "BOWTIE_JOIN",
        "role": "sync_barrier",
        "ascii": "SYNC",
        "opcode": 0x62,
        "syntax": "statement",
    },
    "⇒": {
        "name": "RIGHT_DOUBLE_ARROW",
        "role": "then",
        "ascii": "=>",
        "opcode": None,
        "syntax": "operator",
    },
    "⇌": {
        "name": "RIGHT_LEFT_HARPOON",
        "role": "else",
        "ascii": "else",
        "opcode": None,
        "syntax": "operator",
    },
    "¬": {
        "name": "NOT_SIGN",
        "role": "negate",
        "ascii": "NOT",
        "opcode": None,
        "syntax": "operator",
    },
    "∩": {
        "name": "INTERSECTION",
        "role": "and",
        "ascii": "AND",
        "opcode": None,
        "syntax": "operator",
    },
    "∪": {
        "name": "UNION_MATH",
        "role": "or",
        "ascii": "OR",
        "opcode": None,
        "syntax": "operator",
    },
    "::": {
        "name": "DOUBLE_COLON",
        "role": "type_annotate",
        "ascii": "::",
        "opcode": None,
        "syntax": "operator",
    },
    "&": {
        "name": "AMPERSAND",
        "role": "reference",
        "ascii": "&",
        "opcode": None,
        "syntax": "operator",
    },
}

STATEMENT_GLYPHS = {
    glyph: metadata for glyph, metadata in GLYPHS.items() if metadata.get("syntax") == "statement"
}

# Canonical tag definitions
TAGS = {
    "INTENT": "Primary intent declaration",
    "CAPSULE": "Capsule boundary / scoped intent surface",
    "THOUGHT": "Pure reasoning note",
    "OBSERVATION": "Pure observed data note",
    "PLAN": "Plan or ordered step surface",
    "CONSTRAINT": "Hard constraint enforcement",
    "ASSERT": "Assertion / precondition check",
    "EXPECT": "Expected output type or value",
    "ACTION": "Executable action request",
    "DELEGATE": "Sub-agent delegation target",
    "ROUTE": "Model routing strategy",
    "SOURCE": "Data source reference",
    "PARAM": "Runtime parameter binding",
    "PRIORITY": "Execution priority level",
    "VOTE": "Consensus vote configuration",
    "RESULT": "Result capture binding",
    "SET": "Immutable binding metadata",
    "MODULE": "Module declaration metadata",
    "IMPORT": "Module import metadata",
    "FUNCTION": "Function declaration metadata",
    "CODE": "Code surface metadata",
    "DATA": "Data payload metadata",
    "MEMORY": "Memory node reference",
    "RECALL": "Memory retrieval query",
    "PROVENANCE": "Evidence provenance metadata",
    "GOVERNANCE": "Governance or policy metadata",
    "RELATE": "Explicit symbolic relation edge",
    "GATE": "Spec gate assertion",
    "DEFINE": "Spec definition block",
    "CALL": "Function or tool call metadata",
    "WHILE": "Loop metadata retained for tooling",
    "TRY": "Error-handling try metadata retained for tooling",
    "CATCH": "Error-handler metadata retained for tooling",
    "RETURN": "Return payload metadata",
    "MIGRATION": "Database migration spec",
    "MIGRATION_SPEC": "Database migration specification",
    "ALIGN": "ALIGN Ledger governance rule",
    "SPEC": "Instinct specification metadata",
    "SPEC_DEFINE": "Instinct specification definition metadata",
    "SPEC_GATE": "Instinct specification gate metadata",
    "SPEC_UPDATE": "Instinct specification update metadata",
    "SPEC_SEAL": "Instinct specification seal metadata",
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
    "VOTE": "⨝",
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
    # HOUSE ⌂ — memory anchor
    "MEMORY_ANCHOR": "⌂",
    # SIGMA Σ — aggregate / summarize
    "SUMMARY": "Σ",
    "SUMMARIZE": "Σ",
    "AGGREGATE": "Σ",
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
