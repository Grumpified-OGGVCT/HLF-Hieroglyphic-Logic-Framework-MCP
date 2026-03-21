from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from hlf_mcp.hlf.bytecode import OPCODES, HLFBytecode
from hlf_mcp.hlf.compiler import HLFCompiler
from hlf_mcp.server_profiles import (
    build_multimodal_contract_catalog,
    build_profile_capability_catalog,
)

_PACKAGE_DIR = Path(__file__).resolve().parent
_GOVERNANCE_DIR = _PACKAGE_DIR.parent / "governance"
_FIXTURE_DIR_CANDIDATES = [_PACKAGE_DIR.parent / "fixtures", _PACKAGE_DIR / "fixtures"]
_log = logging.getLogger(__name__)


def _normalize_host_functions_payload(raw_text: str) -> dict[str, object]:
    try:
        data = json.loads(raw_text)
    except (json.JSONDecodeError, ValueError) as exc:
        _log.error("Failed to parse governance host_functions.json: %s", exc)
        return {
            "functions": [],
            "status": "error",
            "error": "invalid_governance_json",
        }

    if isinstance(data, dict):
        if "error" in data:
            return {
                "functions": [],
                "status": "error",
                "error": str(data.get("error") or "invalid_governance_payload"),
                "details": data,
            }
        if "functions" in data and isinstance(data["functions"], list):
            return data
        _log.warning(
            "host_functions.json has unexpected top-level dict schema; preserving error state"
        )
        return {
            "functions": [],
            "status": "error",
            "error": "invalid_governance_schema:dict",
            "details": data,
        }

    if isinstance(data, list):
        return {"functions": data}

    _log.warning(
        "host_functions.json has unexpected top-level type %s; preserving error state",
        type(data).__name__,
    )
    return {
        "functions": [],
        "status": "error",
        "error": f"invalid_governance_schema:{type(data).__name__}",
    }


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


def _get_fixture_dir() -> Path | None:
    for path in _FIXTURE_DIR_CANDIDATES:
        if not path.is_dir():
            continue
        try:
            next(path.iterdir(), None)
        except (PermissionError, OSError) as exc:
            _log.warning("Fixtures directory candidate %s is not accessible: %s", path, exc)
            continue
        return path
    return None


def _build_fixture_gallery_report(ctx: object | None) -> dict[str, object]:
    fixture_dir = _get_fixture_dir()
    if fixture_dir is None:
        return {
            "status": "error",
            "error": "fixtures_directory_missing",
            "message": (
                "No fixtures/ directory found. Checked: "
                + ", ".join(str(p) for p in _FIXTURE_DIR_CANDIDATES)
            ),
            "gallery": {
                "surface_type": "generated_report",
                "report_id": "fixture_gallery",
                "grounded_in_packaged_truth": False,
                "fixture_dir": None,
                "summary": {
                    "fixture_count": 0,
                    "compile_ok_count": 0,
                    "compile_failed_count": 0,
                    "bytecode_ok_count": 0,
                    "bytecode_failed_count": 0,
                },
                "entries": [],
            },
        }

    fixtures = sorted(fixture_dir.glob("*.hlf"))
    if not fixtures:
        return {
            "status": "warning",
            "warning": "no_fixtures_found",
            "message": f"No .hlf fixtures found in fixtures directory: {fixture_dir}",
            "gallery": {
                "surface_type": "generated_report",
                "report_id": "fixture_gallery",
                "grounded_in_packaged_truth": False,
                "fixture_dir": str(fixture_dir),
                "summary": {
                    "fixture_count": 0,
                    "compile_ok_count": 0,
                    "compile_failed_count": 0,
                    "bytecode_ok_count": 0,
                    "bytecode_failed_count": 0,
                },
                "entries": [],
            },
        }

    compiler = getattr(ctx, "compiler", None)
    if compiler is None:
        compiler = HLFCompiler()

    bytecoder = getattr(ctx, "bytecoder", None)
    if bytecoder is None:
        bytecoder = HLFBytecode()

    entries: list[dict[str, object]] = []
    compile_ok_count = 0
    bytecode_ok_count = 0

    for path in fixtures:
        source = path.read_text(encoding="utf-8")
        entry: dict[str, object] = {
            "name": path.stem,
            "file": path.name,
            "source_lines": len(source.strip().splitlines()),
            "compile_status": "failed",
            "bytecode_status": "skipped",
            "node_count": 0,
            "gas_estimate": 0,
            "bytecode_size": 0,
            "errors": [],
        }

        try:
            compile_result = compiler.compile(source)
            entry["compile_status"] = "ok"
            entry["node_count"] = compile_result.get("node_count", 0)
            entry["gas_estimate"] = compile_result.get("gas_estimate", 0)
            compile_ok_count += 1
            try:
                bytecode = bytecoder.encode(compile_result["ast"])
                entry["bytecode_status"] = "ok"
                entry["bytecode_size"] = len(bytecode)
                bytecode_ok_count += 1
            except Exception as exc:
                entry["bytecode_status"] = "failed"
                entry["errors"].append(f"Bytecode: {exc}")
        except Exception as exc:
            entry["errors"].append(f"Compile: {exc}")

        entries.append(entry)

    overall_status = "ok"
    if compile_ok_count != len(entries) or bytecode_ok_count != len(entries):
        overall_status = "warning"

    return {
        "status": overall_status,
        "gallery": {
            "surface_type": "generated_report",
            "report_id": "fixture_gallery",
            "grounded_in_packaged_truth": True,
            "taxonomy": {
                "static_docs": [
                    "fixtures/README.md",
                    "docs/HLF_REFERENCE.md",
                    "docs/HLF_GRAMMAR_REFERENCE.md",
                ],
                "generated_reports": ["hlf://reports/fixture_gallery"],
                "mcp_resources": ["hlf://status/fixture_gallery", "hlf://examples/{name}"],
            },
            "source_authority": [
                "hlf_source/scripts/run_hlf_gallery.py",
                "fixtures/README.md",
                "hlf_mcp/server_resources.py",
            ],
            "fixture_dir": str(fixture_dir),
            "summary": {
                "fixture_count": len(entries),
                "compile_ok_count": compile_ok_count,
                "compile_failed_count": len(entries) - compile_ok_count,
                "bytecode_ok_count": bytecode_ok_count,
                "bytecode_failed_count": len(entries) - bytecode_ok_count,
            },
            "entries": entries,
        },
    }


def _render_fixture_gallery_status(ctx: object | None) -> str:
    return json.dumps(_build_fixture_gallery_report(ctx), indent=2)


def _render_fixture_gallery_markdown(ctx: object | None) -> str:
    report = _build_fixture_gallery_report(ctx)
    gallery = report["gallery"]
    summary = gallery["summary"]
    lines = [
        "# HLF Fixture Gallery Report",
        "",
        "Generated from packaged fixtures using the current packaged compiler and bytecode encoder.",
        "",
        f"- Status: {report['status']}",
        f"- Fixture count: {summary['fixture_count']}",
        f"- AST compile OK: {summary['compile_ok_count']}/{summary['fixture_count']}",
        f"- Bytecode compile OK: {summary['bytecode_ok_count']}/{summary['fixture_count']}",
        "- Grounding: packaged fixtures plus packaged compiler and bytecode encoder",
        "",
        "| Fixture | Lines | AST | Bytecode | Nodes | Gas | Bytes |",
        "| --- | ---: | --- | --- | ---: | ---: | ---: |",
    ]

    for entry in gallery["entries"]:
        lines.append(
            "| {name} | {source_lines} | {compile_status} | {bytecode_status} | {node_count} | {gas_estimate} | {bytecode_size} |".format(
                **entry
            )
        )
        errors = entry.get("errors") or []
        if errors:
            lines.append(f"| {entry['name']} errors | - | {'; '.join(errors)} | - | - | - | - |")

    lines.extend(
        [
            "",
            "## Taxonomy",
            "",
            "- Static docs: fixtures/README.md, docs/HLF_REFERENCE.md, docs/HLF_GRAMMAR_REFERENCE.md",
            "- Generated report: hlf://reports/fixture_gallery",
            "- Queryable MCP resources: hlf://status/fixture_gallery, hlf://examples/{name}",
        ]
    )
    return "\n".join(lines) + "\n"


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


def _render_provenance_contract(ctx: object | None) -> str:
    if ctx is None or not hasattr(ctx, "summarize_provenance_contract"):
        return json.dumps(
            {"status": "error", "error": "provenance_contract_unavailable"},
            indent=2,
        )
    return json.dumps(
        {"status": "ok", "provenance_contract": ctx.summarize_provenance_contract()},
        indent=2,
    )


def _render_memory_governance_status(ctx: object | None) -> str:
    if ctx is None or not hasattr(ctx, "summarize_provenance_contract"):
        return json.dumps(
            {"status": "error", "error": "memory_governance_unavailable"},
            indent=2,
        )
    contract = ctx.summarize_provenance_contract()
    recent_interventions: list[dict[str, object]] = []
    if hasattr(ctx, "recent_governance_events"):
        for event in ctx.recent_governance_events(limit=20, kind="memory_governance"):
            details = event.get("details") if isinstance(event.get("details"), dict) else {}
            recent_interventions.append(
                {
                    "kind": event.get("kind"),
                    "action": event.get("action"),
                    "status": event.get("status"),
                    "severity": event.get("severity"),
                    "source": event.get("source"),
                    "subject_id": event.get("subject_id"),
                    "goal_id": event.get("goal_id"),
                    "timestamp": event.get("timestamp"),
                    "event_ref": event.get("event_ref"),
                    "state": details.get("state"),
                    "pointer": details.get("pointer"),
                    "sha256": details.get("sha256"),
                    "reason": details.get("reason"),
                    "operator_summary": details.get("operator_summary"),
                    "operator_identity": {
                        "operator_id": details.get("operator_id") or "",
                        "operator_display_name": details.get("operator_display_name") or "",
                        "operator_channel": details.get("operator_channel") or "",
                    },
                }
            )
    return json.dumps(
        {
            "status": "ok",
            "memory_governance": {
                "summary": contract.get("summary", {}),
                "memory_state_counts": contract.get("memory_state_counts", {}),
                "recent_targets": contract.get("recent_memory_facts", []),
                "recent_interventions": recent_interventions,
                "pointer_chain_summary": contract.get("pointer_chain_summary", {}),
            },
        },
        indent=2,
    )


def _render_dream_cycle_status(ctx: object | None) -> str:
    if ctx is None or not hasattr(ctx, "get_dream_cycle_status"):
        return json.dumps(
            {"status": "error", "error": "dream_cycle_unavailable"},
            indent=2,
        )
    return json.dumps(
        {"status": "ok", "dream_cycle_status": ctx.get_dream_cycle_status()}, indent=2
    )


def _render_dream_findings(
    ctx: object | None,
    *,
    cycle_id: str | None = None,
    topic: str | None = None,
    min_confidence: float = 0.0,
) -> str:
    if ctx is None or not hasattr(ctx, "list_dream_findings"):
        return json.dumps(
            {"status": "error", "error": "dream_findings_unavailable"},
            indent=2,
        )
    payload = ctx.list_dream_findings(
        cycle_id=cycle_id,
        topic=topic,
        min_confidence=min_confidence,
    )
    return json.dumps({"status": "ok", **payload}, indent=2)


def _render_dream_finding(ctx: object | None, *, finding_id: str) -> str:
    if ctx is None or not hasattr(ctx, "get_dream_finding"):
        return json.dumps(
            {"status": "error", "error": "dream_finding_unavailable", "finding_id": finding_id},
            indent=2,
        )
    finding = ctx.get_dream_finding(finding_id)
    if finding is None:
        return json.dumps({"status": "not_found", "finding_id": finding_id}, indent=2)
    return json.dumps({"status": "ok", "finding": finding}, indent=2)


def _render_media_evidence(ctx: object | None, *, media_type: str | None = None) -> str:
    if ctx is None or not hasattr(ctx, "list_media_evidence"):
        return json.dumps({"status": "error", "error": "media_evidence_unavailable"}, indent=2)
    return json.dumps({"status": "ok", **ctx.list_media_evidence(media_type=media_type)}, indent=2)


def _render_media_evidence_detail(ctx: object | None, *, artifact_id: str) -> str:
    if ctx is None or not hasattr(ctx, "get_media_evidence"):
        return json.dumps(
            {"status": "error", "error": "media_evidence_unavailable", "artifact_id": artifact_id},
            indent=2,
        )
    evidence = ctx.get_media_evidence(artifact_id)
    if evidence is None:
        return json.dumps({"status": "not_found", "artifact_id": artifact_id}, indent=2)
    return json.dumps({"status": "ok", "media_evidence": evidence}, indent=2)


def _render_dream_proposals(ctx: object | None, *, lane: str | None = None) -> str:
    if ctx is None or not hasattr(ctx, "list_dream_proposals"):
        return json.dumps({"status": "error", "error": "dream_proposals_unavailable"}, indent=2)
    return json.dumps({"status": "ok", **ctx.list_dream_proposals(lane=lane)}, indent=2)


def _render_dream_proposal(ctx: object | None, *, proposal_id: str) -> str:
    if ctx is None or not hasattr(ctx, "get_dream_proposal"):
        return json.dumps(
            {"status": "error", "error": "dream_proposals_unavailable", "proposal_id": proposal_id},
            indent=2,
        )
    proposal = ctx.get_dream_proposal(proposal_id)
    if proposal is None:
        return json.dumps({"status": "not_found", "proposal_id": proposal_id}, indent=2)
    return json.dumps({"status": "ok", "proposal": proposal}, indent=2)


def render_resource_uri(ctx: object | None, resource_uri: str) -> str:
    """Render a packaged resource URI outside the running MCP server."""
    if resource_uri == "hlf://status/benchmark_artifacts":
        if ctx is None or not hasattr(ctx, "memory_store"):
            return json.dumps({"status": "error", "error": "memory_store_unavailable"}, indent=2)
        memory = ctx.memory_store
        try:
            artifacts = memory.query_facts(entry_kind="benchmark_artifact")
        except Exception:
            artifacts = []
            for fact in memory.all_facts():
                if fact.get("entry_kind") == "benchmark_artifact":
                    artifacts.append(fact)
        return json.dumps({"status": "ok", "artifacts": artifacts}, indent=2)

    if resource_uri == "hlf://status/active_profiles":
        if ctx is None or not hasattr(ctx, "session_profiles"):
            return json.dumps(
                {"status": "error", "error": "session_profiles_unavailable"}, indent=2
            )
        evidence = {}
        if hasattr(ctx, "session_benchmark_artifacts"):
            evidence = ctx.session_benchmark_artifacts
        return json.dumps(
            {"status": "ok", "active_profiles": ctx.session_profiles, "evidence": evidence},
            indent=2,
        )

    if resource_uri == "hlf://status/profile_capability_catalog":
        return json.dumps(build_profile_capability_catalog(ctx), indent=2)

    if resource_uri == "hlf://status/multimodal_contracts":
        return json.dumps(build_multimodal_contract_catalog(ctx), indent=2)

    if resource_uri == "hlf://host_functions":
        if ctx is not None and hasattr(ctx, "host_registry"):
            return json.dumps({"functions": ctx.host_registry.list_all()}, indent=2)
        return json.dumps(
            _normalize_host_functions_payload(_read_governance_file("host_functions.json")),
            indent=2,
        )

    if resource_uri == "hlf://status/model_catalog":
        return _render_model_catalog_status(ctx)

    if resource_uri == "hlf://status/fixture_gallery":
        return _render_fixture_gallery_status(ctx)

    if resource_uri == "hlf://reports/fixture_gallery":
        return _render_fixture_gallery_markdown(ctx)

    if resource_uri.startswith("hlf://status/model_catalog/"):
        return _render_model_catalog_status(
            ctx,
            agent_id=resource_uri.removeprefix("hlf://status/model_catalog/") or None,
        )

    if resource_uri == "hlf://status/align":
        return _render_align_status(ctx)

    if resource_uri == "hlf://status/formal_verifier":
        return _render_formal_verifier_status(ctx)

    if resource_uri == "hlf://status/governed_route":
        return _render_governed_route_status(ctx)

    if resource_uri.startswith("hlf://status/governed_route/"):
        return _render_governed_route_status(
            ctx,
            agent_id=resource_uri.removeprefix("hlf://status/governed_route/") or None,
        )

    if resource_uri == "hlf://status/instinct":
        return _render_instinct_status(ctx)

    if resource_uri.startswith("hlf://status/instinct/"):
        return _render_instinct_status(
            ctx,
            mission_id=resource_uri.removeprefix("hlf://status/instinct/") or None,
        )

    if resource_uri == "hlf://status/witness_governance":
        return _render_witness_status(ctx)

    if resource_uri.startswith("hlf://status/witness_governance/"):
        return _render_witness_status(
            ctx,
            subject_agent_id=resource_uri.removeprefix("hlf://status/witness_governance/") or None,
        )

    if resource_uri == "hlf://status/provenance_contract":
        return _render_provenance_contract(ctx)

    if resource_uri == "hlf://status/memory_governance":
        return _render_memory_governance_status(ctx)

    if resource_uri == "hlf://status/dream-cycle":
        return _render_dream_cycle_status(ctx)

    if resource_uri == "hlf://dream/findings":
        return _render_dream_findings(ctx)

    if resource_uri.startswith("hlf://dream/findings/"):
        return _render_dream_finding(
            ctx,
            finding_id=resource_uri.removeprefix("hlf://dream/findings/") or "",
        )

    if resource_uri == "hlf://media/evidence":
        return _render_media_evidence(ctx)

    if resource_uri.startswith("hlf://media/evidence/"):
        return _render_media_evidence_detail(
            ctx,
            artifact_id=resource_uri.removeprefix("hlf://media/evidence/") or "",
        )

    if resource_uri == "hlf://dream/proposals":
        return _render_dream_proposals(ctx)

    if resource_uri.startswith("hlf://dream/proposals/"):
        return _render_dream_proposal(
            ctx,
            proposal_id=resource_uri.removeprefix("hlf://dream/proposals/") or "",
        )

    return json.dumps(
        {"status": "error", "error": "unsupported_resource_uri", "resource_uri": resource_uri},
        indent=2,
    )


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

    @mcp.resource("hlf://status/profile_capability_catalog")
    def get_profile_capability_catalog() -> str:
        """Operator-facing governed profile catalog across qualification profiles and active session profiles."""
        return json.dumps(build_profile_capability_catalog(ctx), indent=2)

    @mcp.resource("hlf://status/multimodal_contracts")
    def get_multimodal_contracts() -> str:
        """Operator-facing multimodal qualification profiles mapped to current host-function contracts."""
        return json.dumps(build_multimodal_contract_catalog(ctx), indent=2)

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
        """Available HLF host function registry from the packaged governed contract surface."""
        if ctx is not None and hasattr(ctx, "host_registry"):
            normalized: dict[str, object] = {"functions": ctx.host_registry.list_all()}
        else:
            normalized = _normalize_host_functions_payload(
                _read_governance_file("host_functions.json")
            )
        return json.dumps(normalized, indent=2)

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

    @mcp.resource("hlf://status/fixture_gallery")
    def get_fixture_gallery_status() -> str:
        """Operator-facing generated fixture gallery health derived from packaged fixture compilation truth."""
        return _render_fixture_gallery_status(ctx)

    @mcp.resource("hlf://reports/fixture_gallery")
    def get_fixture_gallery_report() -> str:
        """Operator-facing markdown fixture gallery report derived from packaged compile and bytecode checks."""
        return _render_fixture_gallery_markdown(ctx)

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

    @mcp.resource("hlf://status/provenance_contract")
    def get_provenance_contract() -> str:
        """Operator-facing packaged provenance summary across memory, governance, witness, and evidence surfaces."""
        return _render_provenance_contract(ctx)

    @mcp.resource("hlf://status/memory_governance")
    def get_memory_governance_status() -> str:
        """Operator-facing governance targets and governed memory state for revocation or tombstone intervention."""
        return _render_memory_governance_status(ctx)

    @mcp.resource("hlf://status/dream-cycle")
    def get_dream_cycle_status() -> str:
        """Operator-facing bounded dream-cycle status across recent advisory runs."""
        return _render_dream_cycle_status(ctx)

    @mcp.resource("hlf://dream/findings")
    def get_dream_findings() -> str:
        """Operator-facing list of advisory dream findings from bounded dream-cycle runs."""
        return _render_dream_findings(ctx)

    @mcp.resource("hlf://dream/findings/{finding_id}")
    def get_dream_finding(finding_id: str) -> str:
        """Operator-facing detail view for a specific advisory dream finding."""
        return _render_dream_finding(ctx, finding_id=finding_id)

    @mcp.resource("hlf://media/evidence")
    def get_media_evidence() -> str:
        """Operator-facing list of normalized shared media evidence records."""
        return _render_media_evidence(ctx)

    @mcp.resource("hlf://media/evidence/{artifact_id}")
    def get_media_evidence_detail(artifact_id: str) -> str:
        """Operator-facing detail for a specific shared media evidence record."""
        return _render_media_evidence_detail(ctx, artifact_id=artifact_id)

    @mcp.resource("hlf://dream/proposals")
    def get_dream_proposals() -> str:
        """Operator-facing list of advisory dream proposals with explicit citation-chain gates."""
        return _render_dream_proposals(ctx)

    @mcp.resource("hlf://dream/proposals/{proposal_id}")
    def get_dream_proposal(proposal_id: str) -> str:
        """Operator-facing detail view for a specific advisory dream proposal."""
        return _render_dream_proposal(ctx, proposal_id=proposal_id)

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
        "hlf://status/fixture_gallery": get_fixture_gallery_status,
        "hlf://reports/fixture_gallery": get_fixture_gallery_report,
        "hlf://status/model_catalog/{agent_id}": get_model_catalog_status_for_agent,
        "hlf://status/align": get_align_status,
        "hlf://status/formal_verifier": get_formal_verifier_status,
        "hlf://status/governed_route": get_governed_route_status_latest,
        "hlf://status/governed_route/{agent_id}": get_governed_route_status_for_agent,
        "hlf://status/instinct": get_instinct_status,
        "hlf://status/instinct/{mission_id}": get_instinct_status_for_mission,
        "hlf://status/witness_governance": get_witness_status_summary,
        "hlf://status/witness_governance/{subject_agent_id}": get_witness_status_for_subject,
        "hlf://status/provenance_contract": get_provenance_contract,
        "hlf://status/memory_governance": get_memory_governance_status,
        "hlf://status/dream-cycle": get_dream_cycle_status,
        "hlf://dream/findings": get_dream_findings,
        "hlf://dream/findings/{finding_id}": get_dream_finding,
        "hlf://status/benchmark_artifacts": get_benchmark_artifacts,
        "hlf://status/active_profiles": get_active_profiles,
        "hlf://status/profile_evidence/{profile_name}": get_profile_evidence,
        "hlf://status/profile_capability_catalog": get_profile_capability_catalog,
        "hlf://status/multimodal_contracts": get_multimodal_contracts,
        "hlf://media/evidence": get_media_evidence,
        "hlf://media/evidence/{artifact_id}": get_media_evidence_detail,
        "hlf://dream/proposals": get_dream_proposals,
        "hlf://dream/proposals/{proposal_id}": get_dream_proposal,
    }
