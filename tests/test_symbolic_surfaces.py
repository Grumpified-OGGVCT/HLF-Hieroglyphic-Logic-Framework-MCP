from __future__ import annotations

import json
from pathlib import Path

import pytest

from hlf_mcp.hlf.audit_chain import AuditChain
from hlf_mcp.hlf.compiler import CompileError, HLFCompiler
from hlf_mcp.hlf.symbolic_surfaces import (
    audit_symbolic_surface,
    compile_symbolic_surface,
    project_relation_edges,
)


def _program(body: str) -> str:
    return f"[HLF-v3]\n{body}\nΩ\n"


@pytest.mark.parametrize(
    ("relation", "source_node", "target_node", "expected_namespace", "expected_family"),
    [
        ("time.before", "collect", "verify", "time", "temporal"),
        ("time.after", "deploy", "verify", "time", "temporal"),
        ("cause.enables", "verify", "deploy", "cause", "causal"),
        ("cause.blocks", "policy_gate", "deploy", "cause", "causal"),
        ("agent.owns", "operator", "release_plan", "agent", "agent-role"),
        ("agent.delegates", "scribe", "verify", "agent", "agent-role"),
        ("scope.within", "release_plan", "program", "scope", "scope"),
    ],
)
def test_compile_symbolic_surface_covers_canonical_relation_families(
    relation: str,
    source_node: str,
    target_node: str,
    expected_namespace: str,
    expected_family: str,
) -> None:
    source = _program(
        f'Δ [RELATE] relation="{relation}" from="{source_node}" to="{target_node}"'
    )

    result = compile_symbolic_surface(source)
    edge = result["relation_edges"][0]
    artifact = result["relation_artifacts"][0]

    assert edge["relation"] == relation
    assert edge["relation_namespace"] == expected_namespace
    assert edge["relation_family"] == expected_family
    assert edge["from"] == source_node
    assert edge["to"] == target_node
    assert artifact["relation_namespace"] == expected_namespace
    assert artifact["relation_family"] == expected_family
    assert artifact["canonical_source"] == (
        f'Δ [RELATE] relation="{relation}" from="{source_node}" to="{target_node}"'
    )
    assert artifact["ascii_projection"] == f"{source_node} -[{relation}]-> {target_node}"
    assert artifact["unicode_projection"] == f"{source_node} ⋈{{{relation}}} {target_node}"
    assert artifact["explanation"] == (
        f"Operator-asserted {expected_family} relation {relation} links {source_node} to {target_node}."
    )


def test_compile_symbolic_surface_preserves_multiple_relation_edges_in_order() -> None:
    source = _program(
        "\n".join(
            [
                'Δ [RELATE] relation="time.before" from="collect" to="verify"',
                'Δ [RELATE] relation="time.after" from="deploy" to="verify"',
                'Δ [RELATE] relation="cause.enables" from="verify" to="deploy"',
                'Δ [RELATE] relation="cause.blocks" from="policy_gate" to="deploy"',
                'Δ [RELATE] relation="depends.on" from="verify" to="compile"',
                'Δ [RELATE] relation="agent.owns" from="operator" to="release_plan"',
                'Δ [RELATE] relation="agent.delegates" from="scribe" to="verify"',
                'Δ [RELATE] relation="scope.within" from="release_plan" to="program"',
            ]
        )
    )

    result = compile_symbolic_surface(source)

    assert [edge["relation"] for edge in result["relation_edges"]] == [
        "time.before",
        "time.after",
        "cause.enables",
        "cause.blocks",
        "depends.on",
        "agent.owns",
        "agent.delegates",
        "scope.within",
    ]
    assert [artifact["relation_family"] for artifact in result["relation_artifacts"]] == [
        "temporal",
        "temporal",
        "causal",
        "causal",
        "dependency",
        "agent-role",
        "agent-role",
        "scope",
    ]
    assert [artifact["endpoints"] for artifact in result["relation_artifacts"]] == [
        {"from": "collect", "to": "verify"},
        {"from": "deploy", "to": "verify"},
        {"from": "verify", "to": "deploy"},
        {"from": "policy_gate", "to": "deploy"},
        {"from": "verify", "to": "compile"},
        {"from": "operator", "to": "release_plan"},
        {"from": "scribe", "to": "verify"},
        {"from": "release_plan", "to": "program"},
    ]


def test_compile_symbolic_surface_extracts_relation_edge() -> None:
    source = _program('Δ [RELATE] relation="depends.on" from="verify" to="compile"')

    result = compile_symbolic_surface(source)
    edge = result["relation_edges"][0]

    assert result["ast"]["statements"][0]["kind"] == "glyph_stmt"
    assert result["ast"]["statements"][0]["tag"] == "RELATE"
    assert edge["glyph"] == "Δ"
    assert edge["tag"] == "RELATE"
    assert edge["relation"] == "depends.on"
    assert edge["relation_namespace"] == "depends"
    assert edge["relation_family"] == "dependency"
    assert edge["relation_assertion"] == "operator-asserted"
    assert edge["from"] == "verify"
    assert edge["to"] == "compile"
    assert edge["path"] == [0]
    assert edge["artifact_id"]
    assert edge["canonical_source"] == 'Δ [RELATE] relation="depends.on" from="verify" to="compile"'
    assert "[RELATE]" in edge["human_readable"]
    assert "depends.on" in edge["human_readable"]


def test_project_relation_edges_emits_ascii_and_unicode_forms() -> None:
    relation_edges = [
        {
            "relation": "depends.on",
            "from": "verify",
            "to": "compile",
        }
    ]

    ascii_projection = project_relation_edges(relation_edges)
    unicode_projection = project_relation_edges(relation_edges, unicode_projection=True)

    assert ascii_projection == ["verify -[depends.on]-> compile"]
    assert unicode_projection == ["verify ⋈{depends.on} compile"]


def test_compile_symbolic_surface_provides_relation_explanations() -> None:
    source = _program('Δ [RELATE] relation="depends.on" from="verify" to="compile"')

    result = compile_symbolic_surface(source)

    assert result["explanations"] == [
        "Operator-asserted dependency relation depends.on links verify to compile."
    ]


def test_compile_symbolic_surface_builds_side_by_side_relation_artifact() -> None:
    source = _program('Δ [RELATE] relation="depends.on" from="verify" to="compile"')

    result = compile_symbolic_surface(source)
    artifact = result["relation_artifacts"][0]

    assert artifact["canonical_source"] == 'Δ [RELATE] relation="depends.on" from="verify" to="compile"'
    assert artifact["ascii_projection"] == "verify -[depends.on]-> compile"
    assert artifact["unicode_projection"] == "verify ⋈{depends.on} compile"
    assert artifact["explanation"] == "Operator-asserted dependency relation depends.on links verify to compile."
    assert artifact["authority_labels"] == {
        "canonical_source": "canonical-executable",
        "ascii_projection": "plain-text-safe-display",
        "unicode_projection": "display-only",
        "explanation": "trust-surface",
    }
    assert artifact["relation_namespace"] == "depends"
    assert artifact["relation_family"] == "dependency"
    assert artifact["relation_assertion"] == "operator-asserted"
    assert artifact["endpoints"] == {"from": "verify", "to": "compile"}


def test_unicode_projection_remains_display_only_source() -> None:
    compiler = HLFCompiler()

    with pytest.raises(CompileError):
        compiler.compile(_program("verify ⋈{depends.on} compile"))


def test_audit_symbolic_surface_logs_relation_edge(tmp_path: Path) -> None:
    source = _program('Δ [RELATE] relation="depends.on" from="verify" to="compile"')
    symbolic_surface = compile_symbolic_surface(source)
    log_path = tmp_path / "symbolic.audit.jsonl"
    last_hash_path = tmp_path / "symbolic.last_hash.txt"
    audit_log = AuditChain(
        log_path=str(log_path),
        last_hash_path=str(last_hash_path),
    )

    entries = audit_symbolic_surface(symbolic_surface, audit_log, goal_id="symbolic-proof")

    assert len(entries) == 1
    assert entries[0]["event"] == "symbolic_relation_edge"
    assert entries[0]["goal_id"] == "symbolic-proof"
    assert entries[0]["data"]["artifact_id"]
    assert entries[0]["data"]["relation"] == "depends.on"
    assert entries[0]["data"]["relation_namespace"] == "depends"
    assert entries[0]["data"]["relation_family"] == "dependency"
    assert entries[0]["data"]["relation_assertion"] == "operator-asserted"
    assert (
        entries[0]["data"]["canonical_source"]
        == 'Δ [RELATE] relation="depends.on" from="verify" to="compile"'
    )
    assert entries[0]["data"]["ascii_projection"] == "verify -[depends.on]-> compile"
    assert entries[0]["data"]["unicode_projection"] == "verify ⋈{depends.on} compile"
    assert (
        entries[0]["data"]["explanation"]
        == "Operator-asserted dependency relation depends.on links verify to compile."
    )
    assert entries[0]["data"]["authority_labels"]["unicode_projection"] == "display-only"

    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    persisted = json.loads(lines[-1])
    assert persisted["trace_id"]
    assert persisted["data"]["from"] == "verify"
    assert persisted["data"]["authority_labels"]["canonical_source"] == "canonical-executable"
