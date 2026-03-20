from __future__ import annotations

import json
from pathlib import Path

from hlf_mcp.hlf.audit_chain import AuditChain
from hlf_mcp.hlf.symbolic_surfaces import (
    audit_symbolic_surface,
    compile_symbolic_surface,
    project_relation_edges,
)


def _program(body: str) -> str:
    return f"[HLF-v3]\n{body}\nΩ\n"


def test_compile_symbolic_surface_extracts_relation_edge() -> None:
    source = _program('Δ [RELATE] relation="depends.on" from="verify" to="compile"')

    result = compile_symbolic_surface(source)
    edge = result["relation_edges"][0]

    assert result["ast"]["statements"][0]["kind"] == "glyph_stmt"
    assert result["ast"]["statements"][0]["tag"] == "RELATE"
    assert edge["glyph"] == "Δ"
    assert edge["tag"] == "RELATE"
    assert edge["relation"] == "depends.on"
    assert edge["from"] == "verify"
    assert edge["to"] == "compile"
    assert edge["path"] == [0]
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

    assert result["explanations"] == ["Relation edge depends.on links verify to compile."]


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
    assert entries[0]["data"]["relation"] == "depends.on"
    assert entries[0]["data"]["ascii_projection"] == "verify -[depends.on]-> compile"
    assert entries[0]["data"]["unicode_projection"] == "verify ⋈{depends.on} compile"

    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    persisted = json.loads(lines[-1])
    assert persisted["trace_id"]
    assert persisted["data"]["from"] == "verify"
