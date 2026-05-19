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
from hlf_mcp.hlf.capability_manifest import CapabilityManifest
from hlf_mcp.hlf.effect_extractor import EffectExtractor

_log = logging.getLogger(__name__)

# Module-level SHA-256 → result cache.  Bounded to 256 entries (LRU-like eviction).
_AST_CACHE: dict[str, dict] = {}
_AST_CACHE_MAX = 256

# Build a compiled regex for ASCII glyph aliases once at import time.
# Pattern matches any ASCII alias at the start of a logical line (after optional
# whitespace), so aliases inside quoted string values are NOT replaced.
_ALIAS_PATTERN = re.compile(
    r"(?m)^([ \t]*)"
    + "("
    + "|".join(re.escape(k) for k in sorted(ASCII_ALIASES, key=len, reverse=True))
    + r")\b"
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
        suffix = "then block" if node.get("body") else "(flat)"
        return f"if {_expr_str(node.get('condition'))} {suffix}"
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
    if kind == "module_block_stmt":
        return f"module {node.get('name')}"
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
    if kind == "pipe_stmt":
        stages = len(node.get("stages", []))
        return f"pipe chain of {stages} stage(s)"
    if kind == "template_stmt":
        body_count = len(node.get("body", {}).get("statements", []))
        return f"template {node.get('name')} with {body_count} stmt(s)"
    if kind == "struct_stmt":
        field_count = len(node.get("fields", []))
        return f"struct {node.get('name')} with {field_count} field(s)"
    if kind == "sync_stmt":
        ids = node.get("wait_for", [])
        return f"sync barrier on [{', '.join(ids)}]"
    if kind == "cond_stmt":
        cond = _expr_str(node.get("condition"))
        return f"glyph conditional: {cond}"
    if kind == "prose_stmt":
        return f"prose bridge: {_expr_str(node.get('expr'))} § {node.get('prose', '')[:40]}…"
    if kind == "aesthetic_stmt":
        mod = node.get("modifier", {})
        return f"aesthetic modulation: {_expr_str(node.get('expr'))} ~ {mod.get('value', '?')}"
    if kind == "negate_stmt":
        body_kind = node.get("body", {}).get("kind", "?")
        return f"negative constraint on {body_kind}"
    if kind == "list_literal":
        n = len(node.get("elements", []))
        return f"list literal with {n} element(s)"
    if kind == "match_expr":
        n = len(node.get("arms", []))
        return f"pattern match on {_expr_str(node.get('subject'))} with {n} arm(s)"
    if kind == "prose_expr":
        return f"{_expr_str(node.get('expr'))} § \"{node.get('prose', '')[:30]}…\""
    if kind == "aesthetic_expr":
        mod = node.get("modifier", {})
        return f"{_expr_str(node.get('expr'))} ~ {mod.get('value', '?')}"
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
        if kind == "prose_expr":
            return f"{_expr_str(e.get('expr'))} § \"{e.get('prose', '')[:20]}…\""
        if kind == "aesthetic_expr":
            mod = e.get("modifier", {})
            return f"{_expr_str(e.get('expr'))} ~ {mod.get('value', '?')}"
        if kind == "list_literal":
            elems = [_expr_str(el) for el in e.get("elements", [])]
            return f"[{', '.join(elems)}]"
        if kind == "match_expr":
            return f"match {_expr_str(e.get('subject'))} {{…}}"
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

    def statement(self, stmt):
        """Pass-through for non-inline statement rule."""
        return stmt

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
        validates = []
        for item in rest:
            if isinstance(item, dict) and item.get("kind") == "_tag":
                tag = item["name"]
            elif isinstance(item, dict) and item.get("kind") == "validate_annot":
                validates = item["validations"]
            elif isinstance(item, list):
                args.extend(item)
            elif isinstance(item, dict):
                args.append(item)
        n = _node("glyph_stmt", glyph=str(glyph), tag=tag, arguments=args)
        if validates:
            n["validations"] = validates
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
    # With block? the grammar produces:
    #   flat IF  → children = [KW_IF, expr]
    #   block IF → children = [KW_IF, expr, block, elif_clause*, else_clause?]

    def if_block_stmt(self, _kw, condition, *rest):
        body = None
        remaining = list(rest)
        # First optional child after condition: the block (if present)
        if remaining and isinstance(remaining[0], dict) and remaining[0].get("kind") == "block":
            body = remaining.pop(0)
        elif_clauses = [r for r in remaining if isinstance(r, dict) and r.get("kind") == "elif_clause"]
        else_clause = next(
            (r for r in remaining if isinstance(r, dict) and r.get("kind") == "else_clause"), None
        )
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

    # ── Function & Intent blocks ─────────────────────────────────────────────

    def module_block_stmt(self, _kw, name, *rest):
        args = []
        body = None
        for item in rest:
            if isinstance(item, list):
                args.extend(item)
            elif isinstance(item, dict) and item.get("kind") == "block":
                body = item
        n = _node("module_block_stmt", name=str(name), arguments=args, body=body)
        n["human_readable"] = _human(n)
        return n

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
        validates = []
        for item in rest:
            if isinstance(item, dict) and item.get("kind") == "validate_annot":
                validates = item["validations"]
            elif isinstance(item, list):
                args.extend(item)
        n = _node("tool_stmt", name=str(name), arguments=args)
        if validates:
            n["validations"] = validates
        n["human_readable"] = _human(n)
        return n

    def call_stmt(self, _kw, name, *rest):
        args = []
        validates = []
        for item in rest:
            if isinstance(item, dict) and item.get("kind") == "validate_annot":
                validates = item["validations"]
            elif isinstance(item, list):
                args.extend(item)
        n = _node("call_stmt", name=str(name), arguments=args)
        if validates:
            n["validations"] = validates
        n["human_readable"] = _human(n)
        return n

    # ── Pipe (statement chaining) ──────────────────────────────────────────

    def pipe_stmt(self, first, *rest):
        """Flatten pipe chain into sequential stages with implicit data passing."""
        stages = [first]
        for item in rest:
            if not isinstance(item, Token):
                stages.append(item)
        n = _node("pipe_stmt", stages=stages)
        n["human_readable"] = _human(n)
        return n

    # ── @validate inline annotation ────────────────────────────────────────

    def validate_annot(self, _at_val, *args):
        """Collect @validate(k=v, ...) args as validation list."""
        # args includes the kv_arg dicts (unnamed terminals filtered)
        validations = [a for a in args if isinstance(a, dict)]
        return _node("validate_annot", validations=validations)

    # ── Template ───────────────────────────────────────────────────────────

    def template_stmt(self, _kw, name, body):
        n = _node("template_stmt", name=str(name), body=body)
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

    def ref_arg(self, _ref, name):
        """Pass-by-reference argument: &IDENT."""
        return _node("ref_arg", name=str(name))

    # ── RFC 9005: Glyph-based assignment (←) ────────────────────────────────

    def glyph_assign_stmt(self, name, *rest):
        """Glyph-based assignment: IDENT type_ann? ← assign_rhs epistemic?"""
        typ = None
        rhs = None
        conf = None
        for item in rest:
            if isinstance(item, dict):
                kind = item.get("kind", "")
                if kind == "type_ann":
                    typ = item["type"]
                elif kind == "epistemic":
                    conf = item["confidence"]
                elif item.get("kind") not in ("_tag", "validate_annot"):
                    rhs = item
        n = _node("assign_stmt", name=str(name), expr=rhs)
        if typ:
            n["type"] = typ
        if conf is not None:
            n["confidence"] = conf
        n["human_readable"] = _human(n)
        return n

    def assign_rhs(self, value):
        """Right-hand side of glyph assignment: expr | call_stmt | tool_stmt."""
        return value

    def type_ann(self, _ann, type_sym):
        """Type annotation: :: TYPE_SYM | param_type_sym | refine_type."""
        # type_sym can be a Token (TYPE_SYM), or a dict from param_type_sym/refine_type
        if isinstance(type_sym, dict):
            return _node("type_ann", type=type_sym)
        return _node("type_ann", type=str(type_sym))

    # ── Parametric types: List⟨T⟩, Set⟨T⟩, Map⟨K,V⟩ ────────────────────────────

    def param_type_sym(self, base, _open, *rest):
        """Parametric type: TYPE_SYM ⟨ TYPE_SYM (, TYPE_SYM)* ⟩.
        
        Args are: [base_token, CHEVRON_OPEN, ...type_params..., CHEVRON_CLOSE]
        The closing chevron is the last Token in rest.
        """
        # Filter out Token objects (chevrons) and keep type params
        params = []
        for item in rest:
            if isinstance(item, Token):
                continue  # skip CHEVRON_CLOSE and commas
            params.append(str(item))
        return _node("param_type", base=str(base), params=params)

    # ── Refinement types: {var: TYPE_SYM | pred} ──────────────────────────────

    def refine_type(self, _lbrace, var, _colon, base_type, _pipe, predicate, _rbrace):
        """Refinement type: { var : TYPE_SYM | expr }."""
        return _node(
            "refine_type",
            variable=str(var),
            base_type=str(base_type),
            predicate=predicate,
        )

    # ── RFC 9005: Epistemic confidence modifier ───────────────────────────────

    def epistemic(self, *_args):
        """Epistemic modifier: _{ρ:NUMBER}. Returns confidence float."""
        # _args: [EPISTEMIC_START, RHO, COLON, CONFIDENCE_NUM, RBRACE]
        for a in _args:
            if isinstance(a, Token) and a.type in ("CONFIDENCE_NUM", "INT", "FLOAT"):
                return _node("epistemic", confidence=float(str(a)))
        return _node("epistemic", confidence=1.0)

    # ── RFC 9007: Struct definitions ─────────────────────────────────────────

    def struct_stmt(self, name, _eq, _lbrace, *rest):
        """Struct definition: NAME ≡ { field: TYPE, ... } epistemic?"""
        fields = []
        conf = None
        for item in rest:
            if isinstance(item, dict) and item.get("kind") == "struct_field":
                fields.append(item)
            elif isinstance(item, dict) and item.get("kind") == "epistemic":
                conf = item["confidence"]
        n = _node("struct_stmt", name=str(name), fields=fields)
        if conf is not None:
            n["confidence"] = conf
        n["human_readable"] = _human(n)
        return n

    def struct_field(self, name, *_args):
        """Struct field: IDENT : TYPE_SYM."""
        # _args: [COLON, TYPE_SYM]
        field_type = str(_args[-1]) if _args else "any"
        return _node("struct_field", name=str(name), type=field_type)

    # ── RFC 9005: Sync barrier ───────────────────────────────────────────────

    def sync_stmt(self, _glyph, _lb, *rest):
        """Sync barrier: ⋈ [ID, ...] → statement epistemic?"""
        ids = []
        body = None
        conf = None
        for item in rest:
            if isinstance(item, Token) and item.type == "IDENT":
                ids.append(str(item))
            elif isinstance(item, Token) and item.type == "PIPE":
                continue
            elif isinstance(item, dict):
                if item.get("kind") == "epistemic":
                    conf = item["confidence"]
                elif body is None:
                    body = item
        n = _node("sync_stmt", wait_for=ids, body=body)
        if conf is not None:
            n["confidence"] = conf
        n["human_readable"] = _human(n)
        return n

    # ── RFC 9005: Conditional logic (⊎ ⇒ ⇌) ─────────────────────────────────

    def cond_stmt(self, _glyph, *rest):
        """Conditional: ⊎ condition ⇒ statement (⇌ statement)? epistemic?
                      | ⊎ tag arg_list? epistemic?"""
        if not rest:
            return _node("cond_stmt", condition=None, then_body=None, else_body=None)
        first = rest[0]
        if isinstance(first, dict) and first.get("kind") == "_tag":
            # Glyph-stmt-compatible form: ⊎ [TAG] arg_list? epistemic?
            tag = first["name"]
            args = []
            conf = None
            for item in rest[1:]:
                if isinstance(item, dict) and item.get("kind") == "epistemic":
                    conf = item["confidence"]
                elif isinstance(item, list):
                    args.extend(item)
                elif isinstance(item, dict):
                    args.append(item)
            n = _node("glyph_stmt", glyph="⊎", tag=tag, arguments=args)
            if conf is not None:
                n["confidence"] = conf
            n["human_readable"] = _human(n)
            return n
        # Standard conditional form: ⊎ condition ⇒ statement (⇌ statement)? epistemic?
        condition = first
        then_body = None
        else_body = None
        conf = None
        remaining = list(rest[1:])
        for i, item in enumerate(remaining):
            if isinstance(item, Token) and item.type == "THEN_GLYPH":
                continue
            elif isinstance(item, Token) and item.type == "ELSE_GLYPH":
                continue
            elif isinstance(item, dict):
                if item.get("kind") == "epistemic":
                    conf = item["confidence"]
                elif then_body is None:
                    then_body = item
                elif else_body is None:
                    else_body = item
        n = _node("cond_stmt", condition=condition, then_body=then_body, else_body=else_body)
        if conf is not None:
            n["confidence"] = conf
        n["human_readable"] = _human(n)
        return n

    def cond_expr(self, expr):
        """Conditional expression (proxy to expr)."""
        return expr

    # ── RFC 9005 §12.2: Prose bridge (§) ──────────────────────────────────────

    def prose_stmt(self, expr, _section, prose):
        """Prose bridge: expr § ESCAPED_STRING."""
        conf = None
        n = _node("prose_stmt", expr=expr, prose=str(prose)[1:-1])
        n["human_readable"] = _human(n)
        return n

    def prose_body(self, s):
        """Prose body (escaped string)."""
        return str(s)

    # ── RFC 9005 §12.3: Aesthetic modulation (~) ───────────────────────────────

    def aesthetic_stmt(self, expr, _tilde, modifier):
        """Aesthetic modulation: expr ~ qualifier."""
        n = _node("aesthetic_stmt", expr=expr, modifier=modifier)
        n["human_readable"] = _human(n)
        return n

    def aesthetic_modifier(self, value):
        """Pass-through for aesthetic modifier."""
        return value

    def str_qualifier(self, s):
        """String qualifier for aesthetic modulation."""
        return _node("qualifier", type="string", value=str(s)[1:-1])

    def ident_qualifier(self, name):
        """Identifier qualifier for aesthetic modulation."""
        return _node("qualifier", type="ident", value=str(name))

    # ── RFC 9005 §12.4: Negative constraint (⊖) ────────────────────────────────

    def negate_stmt(self, _negate, stmt):
        """Negative constraint: ⊖ statement."""
        n = _node("negate_stmt", body=stmt)
        n["human_readable"] = _human(n)
        return n

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

    # ── Expression: Bitwise ──────────────────────────────────────────────────

    def expr_bitwise(self, *operands):
        return _fold_binop_with_ops(operands)

    # ── Expression: Prose bridge (§) ─────────────────────────────────────────

    def expr_prose(self, *operands):
        """Expression-level prose bridge: expr § prose_body (repeated)."""
        items = [o for o in operands if not isinstance(o, Token)]
        if len(items) == 1:
            return items[0]
        expr = items[0]
        for prose_tok in items[1:]:
            prose_val = str(prose_tok)[1:-1] if isinstance(prose_tok, Token) else prose_tok
            expr = _node("prose_expr", expr=expr, prose=prose_val)
        return expr

    # ── Expression: Aesthetic modulation (~) ─────────────────────────────────

    def expr_aesthetic(self, *operands):
        """Expression-level aesthetic modulation: expr ~ qualifier (repeated)."""
        items = [o for o in operands if not isinstance(o, Token)]
        if len(items) == 1:
            return items[0]
        expr = items[0]
        for modifier in items[1:]:
            expr = _node("aesthetic_expr", expr=expr, modifier=modifier)
        return expr

    # ── Expression: Exponentiation (^ right-assoc) ───────────────────────────

    def expr_unary(self, child):
        """Pass-through for expr_unary → expr_primary or neg_expr."""
        return child

    def expr_exp(self, *operands):
        """Exponentiation: expr_unary (^ expr_exp)?  Right-associative."""
        items = [o for o in operands if not isinstance(o, Token)]
        if len(items) == 1:
            return items[0]
        # items = [base, exponent] — right-associative
        base, exponent = items
        return _node("binop", op="^", left=base, right=exponent)

    # ── List literal ─────────────────────────────────────────────────────────

    def list_literal(self, _open, *args):
        """List literal: ⟨ expr (, expr)* ⟩."""
        items = [a for a in args if not isinstance(a, Token)]
        return _node("list_literal", elements=items)

    # ── Pattern match ────────────────────────────────────────────────────────

    def match_expr(self, _kw, subject, _lbrace, *arms_and_close):
        """Pattern match: MATCH expr { arm (, arm)* }."""
        arms = [a for a in arms_and_close if isinstance(a, dict) and a.get("kind") == "match_arm"]
        return _node("match_expr", subject=subject, arms=arms)

    def match_arm(self, pattern, _arrow, body):
        """Match arm: pattern => expr."""
        return _node("match_arm", pattern=pattern, body=body)

    def str_pattern(self, s):
        """String literal pattern."""
        return _node("pattern", type="string", value=str(s)[1:-1])

    def int_pattern(self, i):
        """Integer literal pattern."""
        return _node("pattern", type="int", value=int(i))

    def ident_pattern(self, name):
        """Identifier pattern (variable binding)."""
        return _node("pattern", type="ident", value=str(name))

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

    HLF-protected characters (type symbols, operators, glyphs) are saved before
    NFKC normalization and restored afterward, preventing destruction of
    mathematical Unicode symbols used as HLF language tokens.

    Order:
      0a. ASCII glyph aliases (word-boundary, line-start only) — pre-NFKC
      0b. HLF-protected char save → NFKC normalize → restore
      0c. Char-level homoglyph CONFUSABLES substitution

    Returns (normalized_source, replacements_list)
    """
    replacements: list[tuple[int, str, str]] = []

    # Step 0a: collapse ASCII glyph aliases at line-start positions only.
    def _sub_alias(m: re.Match) -> str:
        glyph = ASCII_ALIASES[m.group(2)]
        replacements.append((m.start(2), m.group(2), glyph))
        return m.group(1) + glyph

    source = _ALIAS_PATTERN.sub(_sub_alias, source)

    # Step 0a2: ASCII pipe alias |> → →
    _pipe_found = source.count("|>")
    if _pipe_found:
        source = source.replace("|>", "→")
        replacements.append((0, "|>", "→ (pipe operator)"))

    # Step 0b: Save HLF-protected characters, NFKC-normalize, then restore.
    # Without this, NFKC destroys mathematical symbols: ℕ→N, 𝕊→S, etc.
    _HLF_PROTECTED: frozenset[str] = frozenset({
        # Type symbols
        "\u2115",      # ℕ — Number type
        "\u2124",      # ℤ — Integer type
        "\u211D",      # ℝ — Real type
        "\u211A",      # ℚ — Rational type
        "\U0001D54A",  # 𝕊 — String type
        "\U0001D539",  # 𝔹 — Boolean type
        "\U0001D541",  # 𝕁 — JSON type
        "\U0001D538",  # 𝔸 — Any type
        # Chevrons for parametric types
        "\u27E8",      # ⟨ — Left chevron
        "\u27E9",      # ⟩ — Right chevron
        # Operators
        "\u21A6",  # ↦ — Tool execution
        "\u03C4",  # τ — Tool marker
        "\u228E",  # ⊎ — Conditional
        "\u21D2",  # ⇒ — Then
        "\u21CC",  # ⇌ — Else
        "\u00AC",  # ¬ — Negation
        "\u2229",  # ∩ — Intersection
        "\u222A",  # ∪ — Union
        "\u2190",  # ← — Assignment
        "\u2225",  # ∥ — Parallel
        "\u22C8",  # ⋈ — Sync barrier
        "\u2261",  # ≡ — Struct definition
        "\u2318",  # ⌘ — Command glyph
        "\u0416",  # Ж — Constraint glyph
        "\u2207",  # ∇ — Parameter glyph
        "\u2A55",  # ⩕ — Priority glyph
        "\u2A1D",  # ⨝ — Join glyph
        "\u0394",  # Δ — Delta glyph
        "\u03A9",  # Ω — Terminator
        "\u03A3",  # Σ — Define macro
        "\u2302",  # ⌂ — Memory operator
        "\u03C1",  # ρ — Epistemic modifier
        # Phase 2 operators
        "\u00A7",  # § — Prose bridge
        "\u2296",  # ⊖ — Negative constraint
        "\u2295",  # ⊕ — Bitwise XOR
    })

    chars = list(source)
    protected_positions: dict[int, str] = {}
    for i, ch in enumerate(chars):
        if ch in _HLF_PROTECTED:
            protected_positions[i] = ch
            chars[i] = "\x00"  # placeholder

    intermediate = "".join(chars)
    normalized = unicodedata.normalize("NFKC", intermediate)

    chars = list(normalized)
    for pos, original in protected_positions.items():
        if pos < len(chars):
            chars[pos] = original

    # Step 0c: char-level homoglyph substitution (skip protected chars).
    result = []
    for i, char in enumerate(chars):
        if char in _HLF_PROTECTED:
            result.append(char)
        elif char in CONFUSABLES:
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
    return [(r["id"], r["name"], re.compile(r["pattern"]), r["action"]) for r in rules]


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
        self._template_registry: dict[str, dict] = {}

    def compile(self, source: str) -> dict[str, Any]:
        """Full multi-pass compilation.

        Returns:
            dict with keys: ast, version, node_count, gas_estimate, errors,
                            normalization_changes, align_violations
        """
        if not source or not source.strip():
            raise CompileError("Empty source")

        # Reset per-compile state
        self._template_registry.clear()

        # Cache check: skip all passes for identical source.
        _src_key = hashlib.sha256(source.strip().encode()).hexdigest()
        if _src_key in _AST_CACHE:
            return _AST_CACHE[_src_key]

        # Reset per-compile state
        self._template_registry.clear()

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

        # ── Post-parse expansions ──────────────────────────────────────────
        # 1. Extract template definitions into registry
        stmts = self._extract_templates(stmts)

        # 2. Expand pipe chains into flat sequential statements
        stmts = self._expand_pipes(stmts)

        # 3. Expand @validate annotations into ENFORCE check statements
        stmts = self._expand_validates(stmts)

        # 4. Expand template references (ref="name") by inlining template bodies
        stmts = self._expand_template_refs(stmts)
        ast["statements"] = stmts

        # Pass 2: Collect env
        env = _pass1_collect_env(stmts)

        # ── Constitutional Check Hook ────────────────────────────────────────
        # Runs BEFORE the ethics governor.  Constitution is about what's
        # fundamentally disallowed (program structure); ethics is about
        # what's conditionally allowed (content/rules).
        _strict = os.environ.get("HLF_STRICT", "1") != "0"
        try:
            from hlf_mcp.hlf.ethics.constitutional_check import (
                ConstitutionalViolationError,
                check_constitution,
            )
            check_constitution(ast=ast, source=normalized, tier="hearth")
        except ConstitutionalViolationError as _cve:
            _msg = (
                f"Constitutional violation [{_cve.rule}] at {_cve.location}: "
                f"{_cve.detail}"
            )
            if _strict:
                raise CompileError(_msg) from _cve
            _log.warning("[HLF_STRICT=0] Constitutional violation suppressed: %s", _msg)
        except Exception as _e:  # pragma: no cover — fail closed
            raise CompileError(
                f"Constitutional check internal error (fail-closed): {_e}"
            ) from _e

        # Pass 2.5: Ethics Governor — hard-law enforcement before any expansion.
        # Runs constitutional, rogue-detection, and self-termination layers.
        # When HLF_STRICT=0, violations are logged as warnings instead of raising.
        try:
            from hlf_mcp.hlf.ethics.governor import GovernorError
            from hlf_mcp.hlf.ethics.governor import check as _ethics_check

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
                        "Ethics Governor blocked compilation: " + "; ".join(_gov_result.blocks)
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

    def extract_manifest(self, source: str | None = None) -> CapabilityManifest:
        """Extract a CapabilityManifest from the most recently compiled AST.

        This runs AFTER compilation succeeds but BEFORE the program is handed
        to the executor.  The manifest becomes part of the compiled output —
        it is NOT optional.

        Args:
            source: Optional source text for computing program_id.
                    If omitted, the source key from the most recent compilation
                    is used.

        Returns:
            A fully populated CapabilityManifest.

        Raises:
            CompileError: If no AST is available (compile() must be called first).
        """
        # Use cached AST from most recent compilation
        if not source:
            # Try to use the most recently cached source key
            pass

        # We need the most recent AST — find it from the cache
        ast = None
        effective_source = source or ""
        if _src_key := getattr(self, '_last_src_key', None):
            cached = _AST_CACHE.get(_src_key)
            if cached:
                ast = cached.get("ast")

        if ast is None:
            raise CompileError(
                "extract_manifest() requires a successful compile() call first. "
                "No compiled AST available."
            )

        return EffectExtractor.extract(ast, effective_source)

    def compile_and_manifest(self, source: str) -> tuple[dict[str, Any], CapabilityManifest]:
        """Compile source AND extract the capability manifest in one call.

        This is the recommended API for the full compilation pipeline.
        Returns (compile_result, manifest).
        """
        result = self.compile(source)
        # Store source key for extract_manifest
        self._last_src_key = hashlib.sha256(source.strip().encode()).hexdigest()
        manifest = EffectExtractor.extract(result["ast"], source)
        return result, manifest

    # ── Post-parse expansion passes ──────────────────────────────────────────

    def _extract_templates(self, stmts: list[dict]) -> list[dict]:
        """Extract template_stmt nodes into registry, return remaining statements."""
        remaining = []
        for stmt in stmts:
            if stmt.get("kind") == "template_stmt":
                name = stmt["name"]
                if name in self._template_registry:
                    raise CompileError(f"Duplicate template definition: '{name}'")
                self._template_registry[name] = stmt["body"]
            else:
                remaining.append(stmt)
        return remaining

    def _expand_pipes(self, stmts: list[dict]) -> list[dict]:
        """Flatten pipe_stmt nodes into sequential statements (recursively)."""
        result = []
        for stmt in stmts:
            if stmt.get("kind") == "pipe_stmt":
                stages = stmt.get("stages", [])
                for i, stage in enumerate(stages):
                    if stage.get("kind") == "pipe_stmt":
                        # Recursively expand nested pipe chains
                        result.extend(self._expand_pipes([stage]))
                    else:
                        stage = dict(stage)  # shallow copy
                        if i > 0:
                            stage.setdefault("_pipe_context", {"from_stage": i - 1})
                        result.append(stage)
            else:
                result.append(stmt)
        return result

    def _expand_validates(self, stmts: list[dict]) -> list[dict]:
        """Expand @validate annotations into trailing ENFORCE check statements."""
        result = []
        for stmt in stmts:
            result.append(stmt)
            validations = stmt.get("validations", [])
            if validations:
                # Remove validations from the original stmt (they've been consumed)
                stmt.pop("validations", None)
                for v in validations:
                    name = v.get("name", "check")
                    val = v.get("value", {})
                    val_str = val.get("value", "") if isinstance(val, dict) else str(val)
                    enforce = _node(
                        "glyph_stmt",
                        glyph="Ж",
                        tag="ENFORCE",
                        arguments=[
                            _node("kv_arg", name="check", value=_node("value", type="string", value=str(name))),
                            _node("kv_arg", name="value", value=_node("value", type="string", value=str(val_str))),
                        ],
                    )
                    enforce["human_readable"] = _human(enforce)
                    result.append(enforce)
        return result

    def _expand_template_refs(self, stmts: list[dict]) -> list[dict]:
        """Expand ref='template_name' glyph_stmt args by inlining template body."""
        result = []
        for stmt in stmts:
            if stmt.get("kind") == "glyph_stmt":
                args = stmt.get("arguments", [])
                ref_arg = next(
                    (a for a in args if a.get("kind") == "kv_arg" and a.get("name") == "ref"),
                    None,
                )
                if ref_arg:
                    template_name = ref_arg["value"].get("value", "")
                    if template_name not in self._template_registry:
                        raise CompileError(f"Undefined template reference: '{template_name}'")
                    # Remove ref arg from statement
                    stmt["arguments"] = [a for a in args if a is not ref_arg]
                    # Emit the referencing statement first, then inline the template body
                    result.append(stmt)
                    body = self._template_registry[template_name]
                    for body_stmt in body.get("statements", []):
                        result.append(dict(body_stmt))  # shallow copy
                    continue
            result.append(stmt)
        return result

    def validate(self, source: str) -> dict[str, Any]:
        """Quick syntax validation without full pipeline."""
        if not source or not source.strip():
            return {
                "valid": False,
                "version": None,
                "statement_count": 0,
                "has_terminator": False,
                "error": "Empty source",
            }
        normalized, _ = _pass0_normalize(source.strip())
        if not normalized.endswith("\n"):
            normalized += "\n"
        try:
            tree = self._parser.parse(normalized)
            stmt_count = sum(
                1 for _ in tree.iter_subtrees() if hasattr(_, "data") and _.data.endswith("_stmt")
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
            str(v) for v in header.scan_values(lambda v: isinstance(v, Token) and str(v).isdigit())
        ]
        return ".".join(ints) if ints else "3"
    except StopIteration:
        return "3"


def _estimate_gas(statements: list[dict]) -> int:
    """Estimate gas usage from AST statements."""
    GAS_TABLE: dict[str, int] = {
        "glyph_stmt": 2,
        "memory_stmt": 5,
        "recall_stmt": 5,
        "call_stmt": 3,
        "tool_stmt": 4,
        "spec_define_stmt": 4,
        "spec_gate_stmt": 4,
        "spec_update_stmt": 3,
        "spec_seal_stmt": 4,
        "set_stmt": 1,
        "assign_stmt": 2,
        "if_block_stmt": 2,
        "for_stmt": 3,
        "parallel_stmt": 5,
        "func_block_stmt": 2,
        "intent_stmt": 3,
        "import_stmt": 2,
        "log_stmt": 1,
        "result_stmt": 1,
        "return_stmt": 1,
        "prose_stmt": 2,
        "aesthetic_stmt": 2,
        "negate_stmt": 2,
        "cond_stmt": 3,
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

    with open(sys.argv[1], encoding="utf-8") as f:
        source = f.read()

    compiler = HLFCompiler()
    try:
        result = compiler.compile(source)
        print(json.dumps(result["ast"], indent=2, ensure_ascii=False))
    except CompileError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
