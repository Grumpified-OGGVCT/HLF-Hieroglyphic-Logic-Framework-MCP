from __future__ import annotations

from typing import Any

from hlf_mcp.hlf.audit_chain import AuditChain
from hlf_mcp.hlf.compiler import HLFCompiler

RELATION_TAG = "RELATE"
UNICODE_RELATION_GLYPH = "⋈"


def _kv_arguments(node: dict[str, Any]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for argument in node.get("arguments", []):
        if argument.get("kind") != "kv_arg":
            continue
        value = argument.get("value", {})
        values[argument.get("name", "")] = value.get("value")
    return values


def _walk_nodes(node: dict[str, Any], path: tuple[int, ...] = ()):
    statements = node.get("statements", [])
    for index, statement in enumerate(statements):
        if not isinstance(statement, dict):
            continue
        current_path = path + (index,)
        yield statement, current_path
        body = statement.get("body")
        if isinstance(body, dict):
            yield from _walk_nodes(body, current_path)
        for block_index, block in enumerate(statement.get("blocks", [])):
            if isinstance(block, dict):
                yield from _walk_nodes(block, current_path + (block_index,))


def extract_relation_edges(ast: dict[str, Any]) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    for node, path in _walk_nodes(ast):
        if node.get("kind") != "glyph_stmt" or node.get("tag") != RELATION_TAG:
            continue
        arguments = _kv_arguments(node)
        relation = arguments.get("relation")
        source = arguments.get("from")
        target = arguments.get("to")
        if not relation or not source or not target:
            continue
        edges.append(
            {
                "glyph": node.get("glyph"),
                "tag": node.get("tag"),
                "relation": relation,
                "from": source,
                "to": target,
                "path": list(path),
                "human_readable": node.get("human_readable", ""),
            }
        )
    return edges


def project_relation_edges(
    relation_edges: list[dict[str, Any]],
    *,
    unicode_projection: bool = False,
) -> list[str]:
    lines: list[str] = []
    for edge in relation_edges:
        source = edge["from"]
        relation = edge["relation"]
        target = edge["to"]
        if unicode_projection:
            lines.append(f"{source} {UNICODE_RELATION_GLYPH}{{{relation}}} {target}")
        else:
            lines.append(f"{source} -[{relation}]-> {target}")
    return lines


def explain_relation_edges(relation_edges: list[dict[str, Any]]) -> list[str]:
    return [
        f"Relation edge {edge['relation']} links {edge['from']} to {edge['to']}."
        for edge in relation_edges
    ]


def compile_symbolic_surface(
    source: str,
    *,
    compiler: HLFCompiler | None = None,
) -> dict[str, Any]:
    active_compiler = compiler or HLFCompiler()
    compiled = active_compiler.compile(source)
    ast = compiled["ast"]
    relation_edges = extract_relation_edges(ast)
    return {
        "version": compiled.get("version"),
        "ast": ast,
        "relation_edges": relation_edges,
        "ascii_projection": project_relation_edges(relation_edges),
        "unicode_projection": project_relation_edges(relation_edges, unicode_projection=True),
        "explanations": explain_relation_edges(relation_edges),
    }


def audit_symbolic_surface(
    symbolic_surface: dict[str, Any],
    audit_chain: AuditChain,
    *,
    goal_id: str = "",
    agent_role: str = "hlf_symbolic_surface",
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for edge, ascii_projection, unicode_projection in zip(
        symbolic_surface.get("relation_edges", []),
        symbolic_surface.get("ascii_projection", []),
        symbolic_surface.get("unicode_projection", []),
        strict=False,
    ):
        entry = audit_chain.log(
            "symbolic_relation_edge",
            {
                "relation": edge["relation"],
                "from": edge["from"],
                "to": edge["to"],
                "path": edge.get("path", []),
                "ascii_projection": ascii_projection,
                "unicode_projection": unicode_projection,
            },
            goal_id=goal_id,
            agent_role=agent_role,
        )
        entries.append(entry)
    return entries
