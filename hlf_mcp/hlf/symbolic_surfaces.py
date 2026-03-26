from __future__ import annotations

import hashlib
from typing import Any

from hlf_mcp.hlf.audit_chain import AuditChain
from hlf_mcp.hlf.compiler import HLFCompiler

RELATION_TAG = "RELATE"
UNICODE_RELATION_GLYPH = "⋈"

_RELATION_FAMILY_LABELS = {
    "time": "temporal",
    "cause": "causal",
    "depends": "dependency",
    "agent": "agent-role",
    "scope": "scope",
}

_AUTHORITY_LABELS = {
    "canonical_source": "canonical-executable",
    "ascii_projection": "plain-text-safe-display",
    "unicode_projection": "display-only",
    "explanation": "trust-surface",
}


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


def _relation_namespace(relation: str) -> str:
    if "." not in relation:
        return "unscoped"
    return relation.split(".", 1)[0]


def _relation_family(relation: str) -> str:
    return _RELATION_FAMILY_LABELS.get(_relation_namespace(relation), "unclassified")


def _canonical_relation_source(edge: dict[str, Any]) -> str:
    return (
        f'{edge["glyph"]} [{edge["tag"]}] relation="{edge["relation"]}" '
        f'from="{edge["from"]}" to="{edge["to"]}"'
    )


def _relation_artifact_id(edge: dict[str, Any]) -> str:
    payload = "|".join(
        [
            str(edge.get("path", [])),
            edge["relation"],
            edge["from"],
            edge["to"],
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _relation_artifact(
    edge: dict[str, Any],
    *,
    ascii_projection: str,
    unicode_projection: str,
    explanation: str,
) -> dict[str, Any]:
    return {
        "artifact_id": edge["artifact_id"],
        "canonical_source": edge["canonical_source"],
        "ascii_projection": ascii_projection,
        "unicode_projection": unicode_projection,
        "explanation": explanation,
        "authority_labels": dict(_AUTHORITY_LABELS),
        "relation_namespace": edge["relation_namespace"],
        "relation_family": edge["relation_family"],
        "relation_assertion": edge["relation_assertion"],
        "endpoints": {"from": edge["from"], "to": edge["to"]},
    }


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
                "relation_namespace": _relation_namespace(relation),
                "relation_family": _relation_family(relation),
                "relation_assertion": "operator-asserted",
                "from": source,
                "to": target,
                "path": list(path),
                "canonical_source": "",
                "artifact_id": "",
                "human_readable": node.get("human_readable", ""),
            }
        )
        edges[-1]["canonical_source"] = _canonical_relation_source(edges[-1])
        edges[-1]["artifact_id"] = _relation_artifact_id(edges[-1])
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
        f"{edge['relation_assertion'].capitalize()} {edge['relation_family']} relation "
        f"{edge['relation']} links {edge['from']} to {edge['to']}."
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
    ascii_projection = project_relation_edges(relation_edges)
    unicode_projection = project_relation_edges(relation_edges, unicode_projection=True)
    explanations = explain_relation_edges(relation_edges)
    relation_artifacts = [
        _relation_artifact(
            edge,
            ascii_projection=ascii_line,
            unicode_projection=unicode_line,
            explanation=explanation,
        )
        for edge, ascii_line, unicode_line, explanation in zip(
            relation_edges,
            ascii_projection,
            unicode_projection,
            explanations,
            strict=False,
        )
    ]
    return {
        "version": compiled.get("version"),
        "ast": ast,
        "relation_edges": relation_edges,
        "ascii_projection": ascii_projection,
        "unicode_projection": unicode_projection,
        "explanations": explanations,
        "relation_artifacts": relation_artifacts,
    }


def audit_symbolic_surface(
    symbolic_surface: dict[str, Any],
    audit_chain: AuditChain,
    *,
    goal_id: str = "",
    agent_role: str = "hlf_symbolic_surface",
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    relation_artifacts = symbolic_surface.get("relation_artifacts", [])
    for edge, relation_artifact in zip(
        symbolic_surface.get("relation_edges", []),
        relation_artifacts,
        strict=False,
    ):
        entry = audit_chain.log(
            "symbolic_relation_edge",
            {
                "artifact_id": edge["artifact_id"],
                "relation": edge["relation"],
                "relation_namespace": edge["relation_namespace"],
                "relation_family": edge["relation_family"],
                "relation_assertion": edge["relation_assertion"],
                "from": edge["from"],
                "to": edge["to"],
                "path": edge.get("path", []),
                "canonical_source": relation_artifact["canonical_source"],
                "ascii_projection": relation_artifact["ascii_projection"],
                "unicode_projection": relation_artifact["unicode_projection"],
                "explanation": relation_artifact["explanation"],
                "authority_labels": relation_artifact["authority_labels"],
            },
            goal_id=goal_id,
            agent_role=agent_role,
        )
        entries.append(entry)
    return entries
