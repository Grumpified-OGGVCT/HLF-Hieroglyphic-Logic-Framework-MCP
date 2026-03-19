from __future__ import annotations

import json
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from hlf_mcp.hlf.bytecode import OPCODES

_PACKAGE_DIR = Path(__file__).resolve().parent
_GOVERNANCE_DIR = _PACKAGE_DIR.parent / "governance"


def _read_governance_file(filename: str) -> str:
    path = _GOVERNANCE_DIR / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    return json.dumps(
        {
            "error": "governance_file_not_found",
            "file": filename,
            "hint": (
                "The governance/ directory is not bundled in wheel installs. "
                "Install from source (`pip install -e .`) or mount the directory "
                "to the container's working directory."
            ),
        },
        indent=2,
    )


def _read_fixture_file(name: str) -> str:
    available = (
        "hello_world, security_audit, delegation, routing, "
        "db_migration, log_analysis, stack_deployment"
    )
    candidates = [
        _PACKAGE_DIR.parent / "fixtures" / f"{name}.hlf",
        _PACKAGE_DIR / "fixtures" / f"{name}.hlf",
    ]
    for path in candidates:
        if path.exists():
            return path.read_text(encoding="utf-8")
    return json.dumps(
        {
            "error": "example_not_found",
            "requested": name,
            "available": available,
            "hint": (
                "The fixtures/ directory is not bundled in wheel installs. "
                "Install from source or copy fixtures/ into the package tree."
            ),
        }
    )


def _render_model_catalog_status(ctx: object | None, *, agent_id: str | None = None) -> str:
    if ctx is None or not hasattr(ctx, "get_model_catalog_status"):
        return json.dumps(
            {
                "status": "error",
                "error": "server_context_unavailable",
                "agent_id": agent_id,
            },
            indent=2,
        )

    status = ctx.get_model_catalog_status(agent_id=agent_id)
    if status is None:
        return json.dumps(
            {
                "status": "not_found",
                "agent_id": agent_id,
            },
            indent=2,
        )
    return json.dumps({"status": "ok", "catalog_status": status}, indent=2)


def _render_align_status(ctx: object | None) -> str:
    if ctx is None or not hasattr(ctx, "align_governor"):
        return json.dumps({"status": "error", "error": "align_governor_unavailable"}, indent=2)
    return json.dumps(
        {"status": "ok", "align_status": ctx.align_governor.status_snapshot()}, indent=2
    )


def _render_formal_verifier_status(ctx: object | None) -> str:
    if ctx is None or not hasattr(ctx, "formal_verifier"):
        return json.dumps({"status": "error", "error": "formal_verifier_unavailable"}, indent=2)
    return json.dumps(
        {"status": "ok", "formal_verifier_status": ctx.formal_verifier.status_snapshot()}, indent=2
    )


def _render_governed_route_status(ctx: object | None, *, agent_id: str | None = None) -> str:
    if ctx is None or not hasattr(ctx, "get_governed_route"):
        return json.dumps(
            {"status": "error", "error": "governed_route_unavailable", "agent_id": agent_id},
            indent=2,
        )
    route_trace = ctx.get_governed_route(agent_id=agent_id)
    if route_trace is None:
        return json.dumps({"status": "not_found", "agent_id": agent_id}, indent=2)
    return json.dumps({"status": "ok", "route_trace": route_trace}, indent=2)


def _render_instinct_status(ctx: object | None, *, mission_id: str | None = None) -> str:
    if ctx is None or not hasattr(ctx, "instinct_mgr"):
        return json.dumps(
            {"status": "error", "error": "instinct_manager_unavailable", "mission_id": mission_id},
            indent=2,
        )
    if mission_id:
        mission = ctx.instinct_mgr.get_mission(mission_id)
        if mission is None:
            return json.dumps({"status": "not_found", "mission_id": mission_id}, indent=2)
        return json.dumps({"status": "ok", "mission": mission}, indent=2)
    return json.dumps({"status": "ok", "missions": ctx.instinct_mgr.list_missions()}, indent=2)


def _render_witness_status(ctx: object | None, *, subject_agent_id: str | None = None) -> str:
    if ctx is None or not hasattr(ctx, "get_witness_status"):
        return json.dumps(
            {
                "status": "error",
                "error": "witness_governance_unavailable",
                "subject_agent_id": subject_agent_id,
            },
            indent=2,
        )
    status = ctx.get_witness_status(subject_agent_id=subject_agent_id)
    if status is None:
        return json.dumps({"status": "not_found", "subject_agent_id": subject_agent_id}, indent=2)
    return json.dumps({"status": "ok", "witness_status": status}, indent=2)


def register_resources(mcp: FastMCP, ctx: object | None = None) -> dict[str, object]:
    @mcp.resource("hlf://status/benchmark_artifacts")
    def get_benchmark_artifacts() -> str:
        """Operator-facing: List all persisted benchmark artifacts."""
        if ctx is None or not hasattr(ctx, "memory_store"):
            return json.dumps({"status": "error", "error": "memory_store_unavailable"}, indent=2)
        memory = ctx.memory_store
        try:
            artifacts = memory.query_facts(entry_kind="benchmark_artifact")
        except Exception:
            artifacts = []
            for fact in memory.all_facts():
                if fact.get("entry_kind") != "benchmark_artifact":
                    continue
                artifacts.append(fact)
        return json.dumps({"status": "ok", "artifacts": artifacts}, indent=2)

    @mcp.resource("hlf://status/active_profiles")
    def get_active_profiles() -> str:
        """Operator-facing: List currently active profiles and their supporting evidence."""
        if ctx is None or not hasattr(ctx, "session_profiles"):
            return json.dumps(
                {"status": "error", "error": "session_profiles_unavailable"}, indent=2
            )
        profiles = ctx.session_profiles
        evidence = {}
        if hasattr(ctx, "session_benchmark_artifacts"):
            evidence = ctx.session_benchmark_artifacts
        return json.dumps(
            {"status": "ok", "active_profiles": profiles, "evidence": evidence}, indent=2
        )

    @mcp.resource("hlf://status/profile_evidence/{profile_name}")
    def get_profile_evidence(profile_name: str) -> str:
        """Operator-facing: List all evidence (artifacts, scores, history) for a given profile."""
        if ctx is None or not hasattr(ctx, "memory_store"):
            return json.dumps({"status": "error", "error": "memory_store_unavailable"}, indent=2)
        memory = ctx.memory_store
        evidence = []
        try:
            evidence = memory.query_facts(entry_kind="benchmark_artifact", profile=profile_name)
        except Exception:
            for fact in memory.all_facts():
                if fact.get("entry_kind") != "benchmark_artifact":
                    continue
                if fact.get("profile") != profile_name:
                    continue
                evidence.append(fact)
        return json.dumps({"status": "ok", "profile": profile_name, "evidence": evidence}, indent=2)

    @mcp.resource("hlf://grammar")
    def get_grammar() -> str:
        """HLF grammar specification (LALR(1) Lark format)."""
        from hlf_mcp.hlf.grammar import HLF_GRAMMAR

        return HLF_GRAMMAR

    @mcp.resource("hlf://opcodes")
    def get_opcodes() -> str:
        """HLF bytecode opcode table (37 opcodes)."""
        return json.dumps(OPCODES, indent=2)

    @mcp.resource("hlf://host_functions")
    def get_host_functions() -> str:
        """Available HLF host function registry (28 functions)."""
        from hlf_mcp.hlf.runtime import HOST_FUNCTIONS

        return json.dumps(HOST_FUNCTIONS, indent=2)

    @mcp.resource("hlf://examples/{name}")
    def get_example(name: str) -> str:
        """Return a named example HLF program."""
        return _read_fixture_file(name)

    @mcp.resource("hlf://governance/host_functions")
    def get_governance_host_functions() -> str:
        """Governance host_functions.json — full host function definitions."""
        return _read_governance_file("host_functions.json")

    @mcp.resource("hlf://governance/bytecode_spec")
    def get_governance_bytecode_spec() -> str:
        """Governance bytecode_spec.yaml — bytecode encoding specification."""
        return _read_governance_file("bytecode_spec.yaml")

    @mcp.resource("hlf://governance/align_rules")
    def get_governance_align_rules() -> str:
        """Governance align_rules.json — alignment and safety rules."""
        return _read_governance_file("align_rules.json")

    @mcp.resource("hlf://governance/tag_i18n")
    def get_governance_tag_i18n() -> str:
        """Multilingual HLF tag registry — 14 canonical tags × 8 languages + ASCII glyph aliases."""
        return _read_governance_file("tag_i18n.yaml")

    @mcp.resource("hlf://stdlib")
    def get_stdlib() -> str:
        """List all available HLF stdlib modules."""
        stdlib_dir = _PACKAGE_DIR / "hlf" / "stdlib"
        if not os.path.isdir(stdlib_dir):
            return json.dumps({"modules": []})
        modules = sorted(
            name[:-3]
            for name in os.listdir(stdlib_dir)
            if name.endswith(".py") and not name.startswith("_")
        )
        return json.dumps({"modules": modules}, indent=2)

    @mcp.resource("hlf://status/model_catalog")
    def get_model_catalog_status_latest() -> str:
        """Latest operator-facing status summary for the synced governed model catalog."""
        return _render_model_catalog_status(ctx)

    @mcp.resource("hlf://status/model_catalog/{agent_id}")
    def get_model_catalog_status_for_agent(agent_id: str) -> str:
        """Operator-facing status summary for a specific agent's synced governed model catalog."""
        return _render_model_catalog_status(ctx, agent_id=agent_id)

    @mcp.resource("hlf://status/align")
    def get_align_status() -> str:
        """Operator-facing ALIGN governor status including normalized action semantics."""
        return _render_align_status(ctx)

    @mcp.resource("hlf://status/formal_verifier")
    def get_formal_verifier_status() -> str:
        """Operator-facing formal verifier status including solver and capability snapshot."""
        return _render_formal_verifier_status(ctx)

    @mcp.resource("hlf://status/governed_route")
    def get_governed_route_status_latest() -> str:
        """Operator-facing latest governed route trace summary."""
        return _render_governed_route_status(ctx)

    @mcp.resource("hlf://status/governed_route/{agent_id}")
    def get_governed_route_status_for_agent(agent_id: str) -> str:
        """Operator-facing governed route trace summary for a specific agent."""
        return _render_governed_route_status(ctx, agent_id=agent_id)

    @mcp.resource("hlf://status/instinct")
    def get_instinct_status() -> str:
        """Operator-facing Instinct lifecycle mission list with current phase and realignment counts."""
        return _render_instinct_status(ctx)

    @mcp.resource("hlf://status/instinct/{mission_id}")
    def get_instinct_status_for_mission(mission_id: str) -> str:
        """Operator-facing Instinct lifecycle status for a specific mission."""
        return _render_instinct_status(ctx, mission_id=mission_id)

    @mcp.resource("hlf://status/witness_governance")
    def get_witness_status_summary() -> str:
        """Operator-facing packaged witness-governance summary across tracked subjects."""
        return _render_witness_status(ctx)

    @mcp.resource("hlf://status/witness_governance/{subject_agent_id}")
    def get_witness_status_for_subject(subject_agent_id: str) -> str:
        """Operator-facing packaged witness-governance status for a specific subject."""
        return _render_witness_status(ctx, subject_agent_id=subject_agent_id)

    return {
        "hlf://grammar": get_grammar,
        "hlf://opcodes": get_opcodes,
        "hlf://host_functions": get_host_functions,
        "hlf://examples/{name}": get_example,
        "hlf://governance/host_functions": get_governance_host_functions,
        "hlf://governance/bytecode_spec": get_governance_bytecode_spec,
        "hlf://governance/align_rules": get_governance_align_rules,
        "hlf://governance/tag_i18n": get_governance_tag_i18n,
        "hlf://stdlib": get_stdlib,
        "hlf://status/model_catalog": get_model_catalog_status_latest,
        "hlf://status/model_catalog/{agent_id}": get_model_catalog_status_for_agent,
        "hlf://status/align": get_align_status,
        "hlf://status/formal_verifier": get_formal_verifier_status,
        "hlf://status/governed_route": get_governed_route_status_latest,
        "hlf://status/governed_route/{agent_id}": get_governed_route_status_for_agent,
        "hlf://status/instinct": get_instinct_status,
        "hlf://status/instinct/{mission_id}": get_instinct_status_for_mission,
        "hlf://status/witness_governance": get_witness_status_summary,
        "hlf://status/witness_governance/{subject_agent_id}": get_witness_status_for_subject,
        "hlf://status/benchmark_artifacts": get_benchmark_artifacts,
        "hlf://status/active_profiles": get_active_profiles,
        "hlf://status/profile_evidence/{profile_name}": get_profile_evidence,
    }
