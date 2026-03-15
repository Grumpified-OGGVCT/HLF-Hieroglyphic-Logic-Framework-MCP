"""
HLF Compiler — multi-pass LALR(1) parser + AST transformer.

Compilation pipeline:
  Pass 0: Unicode NFKC normalization + homoglyph/confusable substitution
  Pass 1: LALR(1) Lark parse → raw parse tree → JSON AST
  Pass 2: Collect immutable SET bindings into variable environment
  Pass 3: Expand ${VAR} / $VAR references
  Pass 4: ALIGN Ledger validation (pattern-based governance rules)
  Pass 5: Dictionary arity/type constraint validation
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import sys
import unicodedata
from typing import Any

from lark import Lark, Token, Transformer, UnexpectedInput, v_args
from lark.exceptions import UnexpectedCharacters, UnexpectedToken

from hlf_mcp.hlf.grammar import ASCII_ALIASES, CONFUSABLES, GLYPHS, HLF_GRAMMAR

_log = logging.getLogger(__name__)

# Module-level SHA-256 → result cache.  Bounded to 256 entries (LRU-like eviction).
_AST_CACHE: dict[str, dict] = {}
_AST_CACHE_MAX = 256

# Build a compiled regex for ASCII glyph aliases once at import time.
# Pattern matches any ASCII alias at the start of a logical line (after optional
# whitespace), so aliases inside quoted string values are NOT replaced.
_ALIAS_PATTERN = re.compile(
    r"(?m)^([ \t]*)" + "(" + "|".join(re.escape(k) for k in sorted(ASCII_ALIASES, key=len, reverse=True)) + r")\b"
)


class CompileError(Exception):
    """Raised when HLF source cannot be compiled."""

    def __init__(self, message: str, line: int = 0, col: int = 0):
        super().__init__(message)
        self.line = line
        self.col = col


# ── AST node helpers ──────────────────────────────────────────────────────────


def _node(kind: str, **kwargs: Any) -> dict[str, Any]:
    return {"kind": kind, **kwargs}


def _human(node: dict[str, Any]) -> str:
    """InsAIts: generate human-readable description for an AST node."""
    kind = node.get("kind", "")
    if kind == "program":
        stmts = node.get("statements", [])
        return f"HLF v{node.get('version', '?')} program with {len(stmts)} statement(s)"
    if kind == "glyph_stmt":
        glyph = node.get("glyph", "?")
        glyph_info = GLYPHS.get(glyph, {})
        role = glyph_info.get("role", "action")
        tag = node.get("tag")
        args = node.get("arguments", [])
        tag_str = f" [{tag}]" if tag else ""
        arg_str = ", ".join(_arg_human(a) for a in args)
        return f"{role}{tag_str}: {arg_str}" if arg_str else f"{role}{tag_str}"
    if kind == "set_stmt":
        return f"set (immutable) {node.get('name')} = {_val_str(node.get('value'))}"
    if kind == "assign_stmt":
        return f"assign (mutable) {node.get('name')} = {_expr_str(node.get('expr'))}"
    if kind == "if_block_stmt":
        return f"if {_expr_str(node.get('condition'))} then block"
    if kind == "if_flat_stmt":
        return f"if {node.get('name')} {node.get('cmp')} {_val_str(node.get('value'))}"
    if kind == "for_stmt":
        return f"for {node.get('var')} in {_expr_str(node.get('iterable'))}"
    if kind == "parallel_stmt":
        n = len(node.get("blocks", []))
        return f"parallel execution of {n} blocks"
    if kind in ("else_stmt", "endif_stmt"):
        return kind.replace("_stmt", "")
    if kind == "import_stmt":
        return f"import {node.get('path')}"
    if kind == "log_stmt":
        return f"log {_val_str(node.get('value'))}"
    if kind == "result_stmt":
        return f"result code={_expr_str(node.get('code'))} message={_expr_str(node.get('message'))}"
    if kind == "memory_stmt":
        return f"memory store [{node.get('name')}]"
    if kind == "recall_stmt":
        return f"memory recall [{node.get('name')}]"
    if kind == "spec_define_stmt":
        return f"spec define {node.get('tag', '')}"
    if kind == "spec_gate_stmt":
        return f"spec gate {node.get('tag', '')}"
    if kind == "spec_seal_stmt":
        return f"spec seal {node.get('tag', '')}"
    if kind == "func_block_stmt":
        params = [p.get("name", "") for p in node.get("params", [])]
        return f"function {node.get('name')}({', '.join(params)})"
    if kind == "intent_stmt":
        return f"intent capsule {node.get('name')}"
    if kind == "tool_stmt":
        return f"tool call {node.get('name')}"
    if kind == "call_stmt":
        return f"call {node.get('name')}"
    if kind == "return_stmt":
        v = node.get("value")
        return f"return {_val_str(v)}" if v else "return"
    return kind


def _val_str(v: Any) -> str:
    if isinstance(v, dict):
        return str(v.get("value", v))
    return str(v) if v is not None else ""


def _expr_str(e: Any) -> str:
    if e is None:
        return ""
    if isinstance(e, dict):
        kind = e.get("kind", "")
        if kind == "value":
            return str(e.get("value", ""))
        if kind == "binop":
            return f"{_expr_str(e.get('left'))} {e.get('op')} {_expr_str(e.get('right'))}"
        if kind == "unop":
            return f"{e.get('op')} {_expr_str(e.get('operand'))}"
        if kind == "paren_expr":
            return f"({_expr_str(e.get('expr'))})"
    return str(e)


def _arg_human(arg: dict[str, Any]) -> str:
    kind = arg.get("kind", "")
    if kind == "kv_arg":
        return f"{arg['name']}={_val_str(arg['value'])}"
    return _val_str(arg.get("value", arg.get("path", "")))


# ── Lark Transformer ──────────────────────────────────────────────────────────


@v_args(inline=True)
class HLFTransformer(Transformer):
    """Transform Lark parse tree → HLF AST dicts."""

    # ── Top level ────────────────────────────────────────────────────────────

    def start(self, header, *statements):
        stmts = [s for s in statements if s is not None]
        n = _node(
            "program",
            version=header["version"],
            statements=stmts,
            node_count=len(stmts),
        )
        n["human_readable"] = _human(n)
        n["sha256"] = hashlib.sha256(str(stmts).encode()).hexdigest()
        return n

    def header(self, *tokens):
        ints = [str(t) for t in tokens if isinstance(t, Token) and t.type == "INT"]
        return {"version": ".".join(ints) if ints else "3"}

    # ── Glyph statement ──────────────────────────────────────────────────────

    def glyph_stmt(self, glyph, *rest):
        tag = None
        args = []
        for item in rest:
            if isinstance(item, dict) and item.get("kind") == "_tag":
                tag = item["name"]
            elif isinstance(item, list):
                args.extend(item)
            elif isinstance(item, dict):
                args.append(item)
        n = _node("glyph_stmt", glyph=str(glyph), tag=tag, arguments=args)
        n["human_readable"] = _human(n)
        return n

    def tag(self, _lb, tag_name, _rb):
        return {"kind": "_tag", "name": str(tag_name)}

    def arg_list(self, *args):
        return list(args)

    # ── Declaration ──────────────────────────────────────────────────────────

    def set_stmt(self, _kw, name, value):
        n = _node("set_stmt", name=str(name), value=value)
        n["human_readable"] = _human(n)
        return n

    def assign_stmt(self, _kw, name, expr):
        n = _node("assign_stmt", name=str(name), expr=expr)
        n["human_readable"] = _human(n)
        return n

    # ── Block-form control flow ──────────────────────────────────────────────

    def if_block_stmt(self, _kw, condition, body, *rest):
        elif_clauses = [r for r in rest if isinstance(r, dict) and r.get("kind") == "elif_clause"]
        else_clause = next((r for r in rest if isinstance(r, dict) and r.get("kind") == "else_clause"), None)
        n = _node(
            "if_block_stmt",
            condition=condition,
            body=body,
            elif_clauses=elif_clauses,
            else_clause=else_clause,
        )
        n["human_readable"] = _human(n)
        return n

    def elif_clause(self, _kw, condition, body):
        return _node("elif_clause", condition=condition, body=body)

    def else_clause(self, _kw, body):
        return _node("else_clause", body=body)

    def for_stmt(self, _kw, var, _in, iterable, body):
        n = _node("for_stmt", var=str(var), iterable=iterable, body=body)
        n["human_readable"] = _human(n)
        return n

    def parallel_stmt(self, _kw, *blocks):
        n = _node("parallel_stmt", blocks=list(blocks))
        n["human_readable"] = _human(n)
        return n

    # ── Flat single-line IF (backward compat) ────────────────────────────────

    def if_flat_stmt(self, _kw, name, cmp, value):
        n = _node("if_flat_stmt", name=str(name), cmp=str(cmp), value=value)
        n["human_readable"] = _human(n)
        return n

    # ── Function & Intent blocks ─────────────────────────────────────────────

    def func_block_stmt(self, _kw, name, *rest):
        params = []
        body = None
        for item in rest:
            if isinstance(item, list):  # param_list returns list
                params = item
            elif isinstance(item, dict) and item.get("kind") == "block":
                body = item
        n = _node("func_block_stmt", name=str(name), params=params, body=body)
        n["human_readable"] = _human(n)
        return n

    def param_list(self, *params):
        return list(params)

    def typed_param(self, name, *rest):
        typ = str(rest[0]) if rest else "any"
        return _node("param", name=str(name), type=typ)

    def intent_stmt(self, _kw, name, *rest):
        args = []
        body = None
        for item in rest:
            if isinstance(item, list):
                args.extend(item)
            elif isinstance(item, dict) and item.get("kind") == "block":
                body = item
        n = _node("intent_stmt", name=str(name), arguments=args, body=body)
        n["human_readable"] = _human(n)
        return n

    # ── Block ────────────────────────────────────────────────────────────────

    def block(self, _lb, *stmts, **kwargs):
        # Last token is RBRACE
        stmts_list = [s for s in stmts if isinstance(s, dict) and s is not None]
        return _node("block", statements=stmts_list)

    # ── Tool / Call ──────────────────────────────────────────────────────────

    def tool_stmt(self, _kw, name, *rest):
        args = []
        for item in rest:
            if isinstance(item, list):
                args.extend(item)
        n = _node("tool_stmt", name=str(name), arguments=args)
        n["human_readable"] = _human(n)
        return n

    def call_stmt(self, _kw, name, *rest):
        args = []
        for item in rest:
            if isinstance(item, list):
                args.extend(item)
        n = _node("call_stmt", name=str(name), arguments=args)
        n["human_readable"] = _human(n)
        return n

    # ── Statements ───────────────────────────────────────────────────────────

    def result_stmt(self, _kw, code, *rest):
        message = rest[0] if rest else None
        n = _node("result_stmt", code=code, message=message)
        n["human_readable"] = _human(n)
        return n

    def return_stmt(self, _kw, *rest):
        value = rest[0] if rest else None
        n = _node("return_stmt", value=value)
        n["human_readable"] = _human(n)
        return n

    def log_stmt(self, _kw, value):
        n = _node("log_stmt", value=value)
        n["human_readable"] = _human(n)
        return n

    def import_stmt(self, _kw, path):
        n = _node("import_stmt", path=str(path))
        n["human_readable"] = _human(n)
        return n

    def memory_stmt(self, _kw, _lb, name, _rb, *rest):
        args = []
        for item in rest:
            if isinstance(item, list):
                args.extend(item)
        n = _node("memory_stmt", name=str(name), arguments=args)
        n["human_readable"] = _human(n)
        return n

    def recall_stmt(self, _kw, _lb, name, _rb):
        n = _node("recall_stmt", name=str(name))
        n["human_readable"] = _human(n)
        return n

    def spec_define_stmt(self, _kw, *rest):
        tag, args = _extract_tag_args(rest)
        n = _node("spec_define_stmt", tag=tag, arguments=args)
        n["human_readable"] = _human(n)
        return n

    def spec_gate_stmt(self, _kw, *rest):
        tag, args = _extract_tag_args(rest)
        n = _node("spec_gate_stmt", tag=tag, arguments=args)
        n["human_readable"] = _human(n)
        return n

    def spec_update_stmt(self, _kw, *rest):
        tag, args = _extract_tag_args(rest)
        n = _node("spec_update_stmt", tag=tag, arguments=args)
        n["human_readable"] = _human(n)
        return n

    def spec_seal_stmt(self, _kw, *rest):
        tag, args = _extract_tag_args(rest)
        n = _node("spec_seal_stmt", tag=tag, arguments=args)
        n["human_readable"] = _human(n)
        return n

    # ── Arguments ────────────────────────────────────────────────────────────

    def kv_arg(self, name, value):
        return _node("kv_arg", name=str(name), value=value)

    def pos_arg(self, value):
        return _node("pos_arg", value=value)

    # ── Values ───────────────────────────────────────────────────────────────

    def str_val(self, s):
        raw = str(s)
        return _node("value", type="string", value=raw[1:-1])

    def float_val(self, f):
        return _node("value", type="float", value=float(f))

    def int_val(self, i):
        return _node("value", type="int", value=int(i))

    def ident_val(self, name):
        return _node("value", type="ident", value=str(name))

    def var_ref_val(self, var):
        return _node("value", type="var_ref", value=str(var))

    def path_val(self, path):
        return _node("value", type="path", value=str(path))

    # ── Expression system ────────────────────────────────────────────────────

    def expr_or(self, *operands):
        return _fold_binop(operands, "OR")

    def expr_and(self, *operands):
        return _fold_binop(operands, "AND")

    def not_expr(self, _kw, operand):
        return _node("unop", op="NOT", operand=operand)

    def expr_cmp(self, *operands):
        return _fold_binop_with_ops(operands)

    def expr_add(self, *operands):
        return _fold_binop_with_ops(operands)

    def expr_mul(self, *operands):
        return _fold_binop_with_ops(operands)

    def neg_expr(self, _minus, operand):
        return _node("unop", op="NEG", operand=operand)

    def paren_expr(self, inner):
        return _node("paren_expr", expr=inner)

    # ── Terminals ────────────────────────────────────────────────────────────

    def OMEGA(self, _):
        return None


def _fold_binop(operands: tuple, op_name: str) -> Any:
    items = [o for o in operands if not isinstance(o, Token)]
    if len(items) == 1:
        return items[0]
    result = items[0]
    for item in items[1:]:
        result = _node("binop", op=op_name, left=result, right=item)
    return result


def _fold_binop_with_ops(operands: tuple) -> Any:
    """Fold alternating (expr, op, expr, op, expr) into left-associative binops."""
    items = list(operands)
    if len(items) == 1:
        return items[0]
    result = items[0]
    i = 1
    while i < len(items):
        op = str(items[i])
        right = items[i + 1]
        result = _node("binop", op=op, left=result, right=right)
        i += 2
    return result


def _extract_tag_args(rest: tuple) -> tuple[str | None, list]:
    tag = None
    args = []
    for item in rest:
        if isinstance(item, dict) and item.get("kind") == "_tag":
            tag = item["name"]
        elif isinstance(item, list):
            args.extend(item)
        elif isinstance(item, dict):
            args.append(item)
    return tag, args


# ── Pass 0: Unicode normalisation + homoglyph substitution ───────────────────


_VAR_RE = re.compile(r"\$\{(\w+)\}")  # ${VAR} expansion


def _pass0_normalize(source: str) -> tuple[str, list[tuple[int, str, str]]]:
    """NFKC normalization + ASCII glyph alias substitution + confusable chars.

    Order:
      0a. NFKC canonical decomposition
      0b. ASCII glyph aliases (word-boundary, line-start only)
      0c. Char-level homoglyph CONFUSABLES substitution

    Returns (normalized_source, replacements_list)
    """
    normalized = unicodedata.normalize("NFKC", source)
    replacements: list[tuple[int, str, str]] = []

    # Step 0b: collapse ASCII glyph aliases at line-start positions only.
    def _sub_alias(m: re.Match) -> str:
        glyph = ASCII_ALIASES[m.group(2)]
        replacements.append((m.start(2), m.group(2), glyph))
        return m.group(1) + glyph

    normalized = _ALIAS_PATTERN.sub(_sub_alias, normalized)

    # Step 0c: char-level homoglyph substitution.
    result = []
    for i, char in enumerate(normalized):
        if char in CONFUSABLES:
            repl = CONFUSABLES[char]
            replacements.append((i, char, repl))
            result.append(repl)
        else:
            result.append(char)

    return "".join(result), replacements


# ── Pass 1: Collect immutable SET bindings ────────────────────────────────────


def _pass1_collect_env(statements: list[dict]) -> dict[str, Any]:
    """Collect all SET (immutable) bindings into a variable environment."""
    env: dict[str, Any] = {}
    for node in statements:
        if not node:
            continue
        if node.get("kind") == "set_stmt":
            name = node["name"]
            if name in env:
                raise CompileError(f"Immutable variable '{name}' cannot be reassigned")
            val = node.get("value", {})
            env[name] = val.get("value") if isinstance(val, dict) else val
    return env


# ── Pass 2: Expand $VAR / ${VAR} references ───────────────────────────────────


def _pass2_expand_vars(value: Any, env: dict[str, Any]) -> Any:
    """Recursively expand $VAR and ${VAR} references in string values."""
    if isinstance(value, str):
        def _replace(m: re.Match) -> str:
            return str(env.get(m.group(1), m.group(0)))
        # Handle ${VAR}
        expanded = _VAR_RE.sub(_replace, value)
        # Handle $VAR (bare, uppercase only — to match HLF convention)
        def _replace_bare(m: re.Match) -> str:
            key = m.group(1)
            return str(env.get(key, m.group(0)))
        return re.sub(r"\$([A-Z_][A-Z0-9_]*)", _replace_bare, expanded)
    if isinstance(value, list):
        return [_pass2_expand_vars(v, env) for v in value]
    if isinstance(value, dict):
        return {k: _pass2_expand_vars(v, env) for k, v in value.items()}
    return value


# ── Pass 3: ALIGN Ledger validation ───────────────────────────────────────────

# Default ALIGN rules — can be extended by loading governance/align_rules.json
_DEFAULT_ALIGN_RULES = [
    {
        "id": "ALIGN-001",
        "name": "no_credential_exposure",
        "pattern": r"(?i)(password|secret|api[-_]?key|bearer|token)\s*=\s*['\"]?\w",
        "action": "block",
        "description": "Blocks credential exposure in HLF source",
    },
    {
        "id": "ALIGN-002",
        "name": "no_localhost_exfil",
        "pattern": r"https?://127\.0\.0\.1|https?://localhost",
        "action": "warn",
        "description": "Warns on localhost URL references",
    },
]


def _compile_align_rules(rules: list[dict]) -> list[tuple[str, str, re.Pattern, str]]:
    return [
        (r["id"], r["name"], re.compile(r["pattern"]), r["action"])
        for r in rules
    ]


_ALIGN_COMPILED = _compile_align_rules(_DEFAULT_ALIGN_RULES)


def _pass3_align_validate(statements: list[dict], strict: bool = True) -> list[str]:
    """Validate AST against ALIGN Ledger rules. Returns list of violations."""
    violations = []
    for node in statements:
        strings = _extract_strings_from_node(node)
        for text in strings:
            for rule_id, rule_name, pattern, action in _ALIGN_COMPILED:
                m = pattern.search(text)
                if m:
                    msg = f"{rule_id} ({rule_name}): matched '{m.group(0)}'"
                    if action == "block":
                        if strict:
                            raise CompileError(f"ALIGN Ledger violation — {msg}")
                        violations.append(msg)
                    else:
                        violations.append(f"ALIGN warn — {msg}")
    return violations


def _extract_strings_from_node(node: Any) -> list[str]:
    """Recursively extract all string values from an AST node."""
    if isinstance(node, str):
        return [node]
    if isinstance(node, dict):
        result = []
        for v in node.values():
            result.extend(_extract_strings_from_node(v))
        return result
    if isinstance(node, list):
        result = []
        for item in node:
            result.extend(_extract_strings_from_node(item))
        return result
    return []


# ── Compiler ──────────────────────────────────────────────────────────────────


class HLFCompiler:
    """Compile HLF source to JSON AST via multi-pass pipeline."""

    def __init__(self, strict_align: bool = True) -> None:
        self._parser = Lark(
            HLF_GRAMMAR,
            parser="lalr",
            lexer="contextual",
            propagate_positions=True,
        )
        self._transformer = HLFTransformer()
        self.strict_align = strict_align

    def compile(self, source: str) -> dict[str, Any]:
        """Full multi-pass compilation.

        Returns:
            dict with keys: ast, version, node_count, gas_estimate, errors,
                            normalization_changes, align_violations
        """
        if not source or not source.strip():
            raise CompileError("Empty source")

        # Cache check: skip all passes for identical source.
        _src_key = hashlib.sha256(source.strip().encode()).hexdigest()
        if _src_key in _AST_CACHE:
            return _AST_CACHE[_src_key]

        # Pass 0: Normalize
        normalized, norm_changes = _pass0_normalize(source.strip())
        if not normalized.endswith("\n"):
            normalized += "\n"

        # Pass 1: Parse
        try:
            tree = self._parser.parse(normalized)
            ast = self._transformer.transform(tree)
        except (UnexpectedCharacters, UnexpectedToken) as exc:
            line = getattr(exc, "line", 0)
            col = getattr(exc, "column", 0)
            raise CompileError(str(exc), line=line, col=col) from exc
        except UnexpectedInput as exc:
            raise CompileError(str(exc)) from exc

        stmts = ast.get("statements", [])

        # Pass 2: Collect env
        env = _pass1_collect_env(stmts)

        # Pass 2.5: Ethics Governor — hard-law enforcement before any expansion.
        # Runs constitutional, rogue-detection, and self-termination layers.
        # When HLF_STRICT=0, violations are logged as warnings instead of raising.
        _strict = os.environ.get("HLF_STRICT", "1") != "0"
        try:
            from hlf_mcp.hlf.ethics.governor import GovernorError, check as _ethics_check
            _gov_result = _ethics_check(ast=ast, env=env, source=normalized, tier="hearth")
            if not _gov_result.passed:
                term = _gov_result.termination
                if term is not None:
                    _msg = (
                        f"Ethics Governor [{term.trigger}]: {term.message}\n"
                        f"Documentation: {term.documentation}\n"
                        f"Audit ID: {term.audit_id}"
                    )
                    if _strict:
                        raise CompileError(_msg)
                    _log.warning("[HLF_STRICT=0] Governor termination suppressed: %s", _msg)
                elif _strict:
                    raise CompileError(
                        "Ethics Governor blocked compilation: "
                        + "; ".join(_gov_result.blocks)
                    )
                else:
                    _log.warning(
                        "[HLF_STRICT=0] Governor blocks suppressed: %s",
                        "; ".join(_gov_result.blocks),
                    )
        except CompileError:
            raise
        except GovernorError as _ge:
            raise CompileError(str(_ge)) from _ge
        except Exception as _e:  # pragma: no cover — fail closed
            raise CompileError(f"Ethics Governor internal error (fail-closed): {_e}") from _e

        # Pass 3: Expand vars
        expanded_stmts = [_pass2_expand_vars(s, env) for s in stmts]
        ast["statements"] = expanded_stmts
        ast["env"] = env

        # Pass 4: ALIGN Ledger
        align_violations = _pass3_align_validate(expanded_stmts, strict=self.strict_align)

        gas = _estimate_gas(expanded_stmts)
        result = {
            "ast": ast,
            "version": ast.get("version", "3"),
            "node_count": len(expanded_stmts),
            "gas_estimate": gas,
            "errors": [],
            "normalization_changes": norm_changes,
            "align_violations": align_violations,
        }

        # Store in cache (evict oldest entry if over limit).
        if len(_AST_CACHE) >= _AST_CACHE_MAX:
            _AST_CACHE.pop(next(iter(_AST_CACHE)))
        _AST_CACHE[_src_key] = result
        return result

    def validate(self, source: str) -> dict[str, Any]:
        """Quick syntax validation without full pipeline."""
        if not source or not source.strip():
            return {"valid": False, "version": None, "statement_count": 0,
                    "has_terminator": False, "error": "Empty source"}
        normalized, _ = _pass0_normalize(source.strip())
        if not normalized.endswith("\n"):
            normalized += "\n"
        try:
            tree = self._parser.parse(normalized)
            stmt_count = sum(
                1 for _ in tree.iter_subtrees()
                if hasattr(_, "data") and _.data.endswith("_stmt")
            )
            return {
                "valid": True,
                "version": _extract_version(tree),
                "statement_count": stmt_count,
                "has_terminator": True,
                "error": None,
            }
        except Exception as exc:
            return {
                "valid": False,
                "version": None,
                "statement_count": 0,
                "has_terminator": False,
                "error": str(exc),
            }


def _extract_version(tree) -> str:
    try:
        header = next(tree.find_data("header"))
        # Use isinstance(v, Token) to avoid calling .isdigit() on Tree nodes.
        ints = [
            str(v)
            for v in header.scan_values(
                lambda v: isinstance(v, Token) and str(v).isdigit()
            )
        ]
        return ".".join(ints) if ints else "3"
    except StopIteration:
        return "3"


def _estimate_gas(statements: list[dict]) -> int:
    """Estimate gas usage from AST statements."""
    GAS_TABLE: dict[str, int] = {
        "glyph_stmt":        2,
        "memory_stmt":       5,
        "recall_stmt":       5,
        "call_stmt":         3,
        "tool_stmt":         4,
        "spec_define_stmt":  4,
        "spec_gate_stmt":    4,
        "spec_update_stmt":  3,
        "spec_seal_stmt":    4,
        "set_stmt":          1,
        "assign_stmt":       2,
        "if_block_stmt":     2,
        "if_flat_stmt":      1,
        "for_stmt":          3,
        "parallel_stmt":     5,
        "func_block_stmt":   2,
        "intent_stmt":       3,
        "import_stmt":       2,
        "log_stmt":          1,
        "result_stmt":       1,
        "return_stmt":       1,
    }
    total = 0
    for stmt in statements:
        if not isinstance(stmt, dict):
            continue
        kind = stmt.get("kind", "")
        total += GAS_TABLE.get(kind, 1)
        args = stmt.get("arguments", [])
        total += len(args)
        # Recurse into blocks
        for key in ("body", "block"):
            sub = stmt.get(key)
            if isinstance(sub, dict) and "statements" in sub:
                total += _estimate_gas(sub["statements"])
        for clause in stmt.get("elif_clauses", []):
            if isinstance(clause, dict):
                sub = clause.get("body", {})
                if isinstance(sub, dict):
                    total += _estimate_gas(sub.get("statements", []))
    return total


# ── CLI entry point ───────────────────────────────────────────────────────────


def main() -> None:
    """CLI: hlfc <file.hlf>"""
    import json

    if len(sys.argv) < 2:
        print("Usage: hlfc <file.hlf>", file=sys.stderr)
        sys.exit(1)

    with open(sys.argv[1]) as f:
        source = f.read()

    compiler = HLFCompiler()
    try:
        result = compiler.compile(source)
        print(json.dumps(result["ast"], indent=2, ensure_ascii=False))
    except CompileError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
