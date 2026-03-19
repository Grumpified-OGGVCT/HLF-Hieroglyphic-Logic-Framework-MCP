from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import uuid
from typing import Any, Literal

import httpx
from mcp.server.fastmcp import FastMCP

from hlf_mcp.hlf.governed_routing import build_governed_route
from hlf_mcp.hlf.model_catalog import (
    build_lane_trace_context,
    evaluate_model_against_profile,
    evaluate_model_requirement_tiers,
    evaluate_model_requirements,
    load_model_qualification_profiles,
    sync_model_catalog,
)
from hlf_mcp.hlf.routing_trace import (
    RouteDecisionRecord,
    RouteTraceRecord,
    build_operator_route_summary,
)
from hlf_mcp.server_context import ServerContext

Workload = Literal[
    "translation_memory",
    "repair_pattern_recall",
    "governance_policy_retrieval",
    "code_pattern_retrieval",
    "agent_routing_context",
    "long_form_standards_ingestion",
]

_ROUTE_READY_TIERS = {"launch-qualified", "promotion-qualified"}
_QUALIFICATION_PROFILES = dict(load_model_qualification_profiles().get("profiles") or {})


def _qualification_profile_for(workload: Workload, multilingual_required: bool) -> str | None:
    if workload == "translation_memory" and multilingual_required:
        return "translation_memory_multilingual"
    if workload == "agent_routing_context" and multilingual_required:
        return "agent_routing_context_multilingual"
    return None


def _route_profile_candidates(
    workload: Workload, selected_lane: str, multilingual_required: bool
) -> list[str]:
    profiles: list[str] = []
    # Map lane families to qualification profiles
    lane_profile_map = {
        "retrieval": [],
        "explainer": ["sidecar_quality_explainer"],
        "code-generation": ["code_pattern_retrieval_english"],
        "verifier": ["verifier_accuracy_multilingual"],
        "standards-ingestion": [],
        "multimodal": [],
    }
    # Add multilingual variants if required
    if multilingual_required:
        if "verifier_accuracy_multilingual" not in lane_profile_map["explainer"]:
            lane_profile_map["explainer"].append("verifier_accuracy_multilingual")

    # Always include the primary profile for the workload if defined
    primary_profile = _qualification_profile_for(workload, multilingual_required)
    if primary_profile:
        profiles.append(primary_profile)

    # Add profiles based on the selected lane
    if selected_lane in lane_profile_map:
        profiles.extend(lane_profile_map[selected_lane])

    # Remove duplicates while preserving order
    ordered: list[str] = []
    for profile_name in profiles:
        if profile_name not in ordered:
            ordered.append(profile_name)
    return ordered


def _profile_metric_names(profile_name: str) -> set[str]:
    profile = _QUALIFICATION_PROFILES.get(profile_name)
    if not isinstance(profile, dict):
        return set()
    tiers = profile.get("tiers") or {}
    metric_names: set[str] = set()
    for definition in tiers.values():
        if isinstance(definition, dict):
            metric_names.update(str(metric_name) for metric_name in definition)
    return metric_names


def _collect_route_profile_artifacts(
    ctx: ServerContext,
    *,
    profile_names: list[str],
    benchmark_scores: dict[str, float] | None,
) -> tuple[
    list[str], dict[str, dict[str, Any] | None], dict[str, dict[str, float]], dict[str, float]
]:
    explicit_scores = {
        str(metric): float(score) for metric, score in (benchmark_scores or {}).items()
    }
    active_profiles: list[str] = []
    artifacts: dict[str, dict[str, Any] | None] = {}
    per_profile_scores: dict[str, dict[str, float]] = {}
    merged_scores: dict[str, float] = {}

    for profile_name in profile_names:
        artifact = ctx.get_benchmark_artifact(profile_name=profile_name)
        persisted_scores = {
            str(metric): float(score)
            for metric, score in ((artifact or {}).get("benchmark_scores") or {}).items()
        }
        relevant_explicit_scores = {
            metric: score
            for metric, score in explicit_scores.items()
            if metric in _profile_metric_names(profile_name)
        }
        combined_scores = {**persisted_scores, **relevant_explicit_scores}
        if not combined_scores:
            continue
        active_profiles.append(profile_name)
        artifacts[profile_name] = artifact
        per_profile_scores[profile_name] = combined_scores
        merged_scores.update(combined_scores)

    return active_profiles, artifacts, per_profile_scores, merged_scores


def _profile_set_ready(profile_evaluations: dict[str, dict[str, Any]]) -> bool:
    return bool(profile_evaluations) and all(
        evaluation.get("resolved_tier") in _ROUTE_READY_TIERS
        for evaluation in profile_evaluations.values()
    )


def _route_selection_profiles(
    *,
    active_profiles: list[str],
    qualification_profile: str | None,
    selected_lane: str,
) -> list[str]:
    if selected_lane != "retrieval" and qualification_profile:
        filtered = [
            profile_name
            for profile_name in active_profiles
            if profile_name != qualification_profile
        ]
        if filtered:
            return filtered
    return list(active_profiles)


def _parse_vram_gb(raw: str | None) -> float | None:
    if raw is None:
        return None
    normalized = raw.strip().lower().replace("gib", "gb")
    if not normalized:
        return None
    if normalized.endswith("gb"):
        normalized = normalized[:-2].strip()
    try:
        return float(normalized)
    except ValueError:
        return None


def _batch_size_for(model: str, cpu_only: bool) -> int:
    if cpu_only:
        if model == "all-minilm":
            return 8
        if model == "embeddinggemma":
            return 4
        return 2
    return {
        "embeddinggemma": 256,
        "nomic-embed-text-v2-moe": 64,
        "bge-m3": 128,
        "mxbai-embed-large": 128,
        "all-minilm": 64,
        "granite-embedding:30m": 64,
        "qwen3-embedding:4b": 32,
    }.get(model, 32)


def _vector_db_config_for(model: str) -> dict[str, Any]:
    configs = {
        "embeddinggemma": {
            "dimension": 768,
            "metric": "cosine",
            "recommended_index": "flat_or_small_hnsw",
            "qdrant": {"hnsw_m": 16, "ef_construct": 200},
        },
        "nomic-embed-text-v2-moe": {
            "dimension": 768,
            "metric": "cosine",
            "recommended_index": "hnsw",
            "qdrant": {"hnsw_m": 24, "ef_construct": 300},
        },
        "bge-m3": {
            "dimension": 1024,
            "metric": "cosine",
            "recommended_index": "hnsw",
            "qdrant": {"hnsw_m": 24, "ef_construct": 300},
        },
        "mxbai-embed-large": {
            "dimension": 1024,
            "metric": "cosine",
            "recommended_index": "hnsw",
            "qdrant": {"hnsw_m": 32, "ef_construct": 400},
        },
        "all-minilm": {
            "dimension": 384,
            "metric": "cosine",
            "recommended_index": "flat",
            "qdrant": {"hnsw_m": 8, "ef_construct": 64},
        },
        "granite-embedding:30m": {
            "dimension": 384,
            "metric": "cosine",
            "recommended_index": "flat",
            "qdrant": {"hnsw_m": 8, "ef_construct": 64},
        },
        "qwen3-embedding:4b": {
            "dimension": 2048,
            "metric": "cosine",
            "recommended_index": "hnsw_or_diskann",
            "qdrant": {"hnsw_m": 32, "ef_construct": 400},
        },
    }
    return configs.get(model, {"metric": "cosine"})


def _normalize_ollama_endpoint(raw_host: str | None) -> str:
    endpoint = raw_host or os.environ.get("OLLAMA_HOST") or "http://localhost:11434"
    if not endpoint.startswith("http://") and not endpoint.startswith("https://"):
        endpoint = f"http://{endpoint}"
    endpoint = endpoint.replace("http://0.0.0.0", "http://localhost")
    endpoint = endpoint.replace("https://0.0.0.0", "https://localhost")
    endpoint = endpoint.replace("http://[::]", "http://localhost")
    endpoint = endpoint.replace("https://[::]", "https://localhost")
    return endpoint


def _load_remote_direct_entries() -> tuple[list[dict[str, Any]], str | None]:
    raw_value = os.environ.get("HLF_REMOTE_MODEL_ENDPOINTS", "").strip()
    if not raw_value:
        return [], None
    try:
        payload = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        return [], f"Invalid HLF_REMOTE_MODEL_ENDPOINTS JSON: {exc}"

    if isinstance(payload, dict):
        payload = payload.get("entries", [])
    if not isinstance(payload, list):
        return (
            [],
            "HLF_REMOTE_MODEL_ENDPOINTS must be a JSON list or an object with an 'entries' list.",
        )

    normalized: list[dict[str, Any]] = []
    for index, entry in enumerate(payload):
        if not isinstance(entry, dict):
            return [], f"HLF_REMOTE_MODEL_ENDPOINTS entry {index} must be an object."
        endpoint = str(entry.get("endpoint", "")).strip()
        if not endpoint:
            return [], f"HLF_REMOTE_MODEL_ENDPOINTS entry {index} is missing an endpoint."
        normalized.append(
            {
                "name": str(entry.get("name") or f"remote-direct-{index + 1}"),
                "family": str(entry.get("family") or "remote-direct"),
                "endpoint": endpoint,
                "lanes": [str(lane) for lane in entry.get("lanes", ["explainer"])],
                "capabilities": [
                    str(capability) for capability in entry.get("capabilities", ["remote-direct"])
                ],
                "reachable": bool(entry.get("reachable", True)),
                "known_but_impractical": bool(entry.get("known_but_impractical", False)),
                "privacy_preserving": bool(entry.get("privacy_preserving", False)),
                "min_vram_gb": float(entry.get("min_vram_gb") or 0.0),
                "rationale": [
                    str(reason)
                    for reason in entry.get(
                        "rationale",
                        [
                            "Remote direct operator endpoint configured through HLF_REMOTE_MODEL_ENDPOINTS."
                        ],
                    )
                ],
            }
        )
    return normalized, None


def _workload_to_catalog_lane(workload: Workload) -> str:
    lane_map: dict[Workload, str] = {
        "translation_memory": "retrieval",
        "repair_pattern_recall": "retrieval",
        "governance_policy_retrieval": "retrieval",
        "code_pattern_retrieval": "code-generation",
        "agent_routing_context": "explainer",
        "long_form_standards_ingestion": "standards-ingestion",
    }
    return lane_map[workload]


def _catalog_candidate_to_route(
    candidate: dict[str, Any] | None, fallback: dict[str, Any]
) -> dict[str, Any]:
    if not candidate:
        return dict(fallback)
    return {
        "model": candidate.get("name", fallback.get("model", "")),
        "endpoint": candidate.get("endpoint", fallback.get("endpoint", "")),
        "access_mode": candidate.get("access_mode", ""),
        "family": candidate.get("family", ""),
        "lanes": list(candidate.get("lanes", [])),
        "capabilities": list(candidate.get("capabilities", [])),
        "rationale": list(candidate.get("rationale", [])),
    }


def _probe_local_hardware() -> dict[str, Any]:
    cpu_count = os.cpu_count() or 1
    gpu_devices: list[dict[str, Any]] = []
    if shutil.which("nvidia-smi"):
        try:
            completed = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=name,memory.total",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=2,
            )
            for line in completed.stdout.splitlines():
                if not line.strip():
                    continue
                parts = [part.strip() for part in line.split(",", 1)]
                if len(parts) != 2:
                    continue
                name, total_mb = parts
                try:
                    total_gb = round(float(total_mb) / 1024, 2)
                except ValueError:
                    continue
                gpu_devices.append({"name": name, "memory_gb": total_gb})
        except Exception:
            gpu_devices = []

    max_vram = max((device["memory_gb"] for device in gpu_devices), default=None)
    return {
        "cpu_only": len(gpu_devices) == 0,
        "cpu_count": cpu_count,
        "gpu_count": len(gpu_devices),
        "gpu_devices": gpu_devices,
        "gpu_vram_gb": max_vram,
        "platform": platform.system(),
        "platform_release": platform.release(),
        "probe_sources": ["nvidia-smi"] if gpu_devices else [],
    }


def _check_ollama_runtime(
    endpoint: str, recommended_model: str, fallback_model: str
) -> dict[str, Any]:
    tags_url = endpoint.rstrip("/") + "/api/tags"
    try:
        response = httpx.get(tags_url, timeout=1.5)
        response.raise_for_status()
        payload = response.json()
        models = payload.get("models", []) if isinstance(payload, dict) else []
        installed_names = [
            str(model.get("name", "")) for model in models if isinstance(model, dict)
        ]
        installed_set = set(installed_names)
        return {
            "ollama_available": True,
            "ollama_endpoint": endpoint,
            "installed_models": installed_names,
            "recommended_model_runnable": recommended_model in installed_set,
            "fallback_model_runnable": fallback_model in installed_set,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ollama_available": False,
            "ollama_endpoint": endpoint,
            "installed_models": [],
            "recommended_model_runnable": False,
            "fallback_model_runnable": False,
            "error": str(exc),
        }


def _recommend_model(
    *,
    workload: Workload,
    gpu_vram_gb: float | None,
    cpu_only: bool,
    multilingual_required: bool,
    long_context_required: bool,
    latency_priority: str,
) -> tuple[str, str, list[str]]:
    reasons: list[str] = []

    if cpu_only:
        if workload == "long_form_standards_ingestion":
            reasons.append(
                "CPU-only mode is not a strong first target for long-form standards ingestion."
            )
            return "embeddinggemma", "all-minilm", reasons
        if workload == "agent_routing_context":
            reasons.append("Routing context should stay lightweight on CPU-only systems.")
            return "embeddinggemma", "all-minilm", reasons
        if workload == "translation_memory" and multilingual_required:
            reasons.append(
                "CPU-only mode prefers the most practical quality/size balance over heavier multilingual models."
            )
            return "embeddinggemma", "all-minilm", reasons
        reasons.append("CPU-only mode prioritizes portability and low operational cost.")
        return "embeddinggemma", "all-minilm", reasons

    vram = gpu_vram_gb or 0.0

    if workload == "translation_memory":
        if multilingual_required and vram >= 10:
            reasons.append(
                "Translation memory benefits from stronger multilingual semantic recall."
            )
            return "nomic-embed-text-v2-moe", "embeddinggemma", reasons
        reasons.append(
            "Translation memory can start with a lighter model if multilingual pressure is modest."
        )
        return "embeddinggemma", "all-minilm", reasons

    if workload == "repair_pattern_recall":
        reasons.append("Repair recall favors short, fast local lookups over heavy context windows.")
        return "embeddinggemma", "bge-m3" if vram >= 10 else "all-minilm", reasons

    if workload == "governance_policy_retrieval":
        reasons.append(
            "Governance retrieval remains deterministic-first; semantic retrieval is advisory only."
        )
        return "embeddinggemma", "all-minilm" if vram < 4 else "bge-m3", reasons

    if workload == "code_pattern_retrieval":
        if vram >= 10 and (long_context_required or latency_priority == "quality"):
            reasons.append(
                "Code and doc retrieval benefit from a longer-context embedding model when hardware allows."
            )
            return "bge-m3", "mxbai-embed-large", reasons
        reasons.append(
            "Shorter-context English-heavy code retrieval can start with a lighter, faster model."
        )
        return "mxbai-embed-large" if vram >= 4 else "embeddinggemma", "embeddinggemma", reasons

    if workload == "agent_routing_context":
        if multilingual_required and vram >= 10:
            reasons.append(
                "Multilingual routing context can justify a stronger multilingual embedding model."
            )
            return "nomic-embed-text-v2-moe", "embeddinggemma", reasons
        reasons.append("Routing context should remain cheap, fast, and optional.")
        return "embeddinggemma", "all-minilm", reasons

    if workload == "long_form_standards_ingestion":
        if long_context_required and vram >= 12:
            reasons.append(
                "Long-form standards ingestion benefits from larger context capacity when hardware can support it."
            )
            return "bge-m3", "qwen3-embedding:4b", reasons
        reasons.append(
            "Standards ingestion should start with disciplined chunking before heavier model adoption."
        )
        return "bge-m3" if vram >= 10 else "embeddinggemma", "embeddinggemma", reasons

    reasons.append("Defaulting to a conservative local embedding profile.")
    return "embeddinggemma", "all-minilm", reasons


def register_profile_tools(mcp: FastMCP, ctx: ServerContext) -> dict[str, Any]:
    @mcp.tool()
    def hlf_probe_local_hardware() -> dict[str, Any]:
        """Probe local hardware capabilities relevant to embedding profile negotiation."""
        return _probe_local_hardware()

    @mcp.tool()
    def hlf_recommend_embedding_profile(
        workload: Workload = "translation_memory",
        gpu_vram_gb: float | None = None,
        cpu_only: bool = False,
        multilingual_required: bool = False,
        long_context_required: bool = False,
        latency_priority: str = "balanced",
        ollama_host: str | None = None,
        agent_id: str = "unknown-agent",
        persist: bool = True,
    ) -> dict[str, Any]:
        """Negotiate a hardware-aware local embedding profile for an HLF agent or operator."""
        hardware_probe = _probe_local_hardware()
        detected_vram = gpu_vram_gb
        detected_from = "request"
        if detected_vram is None:
            if hardware_probe.get("gpu_vram_gb") is not None:
                detected_vram = float(hardware_probe["gpu_vram_gb"])
                detected_from = "hardware_probe"
            else:
                detected_vram = _parse_vram_gb(os.environ.get("HLF_VRAM"))
                detected_from = "environment" if detected_vram is not None else "unknown"

        effective_cpu_only = cpu_only or bool(
            hardware_probe.get("cpu_only", False) and detected_vram in {None, 0.0}
        )

        normalized_latency = latency_priority.lower().strip()
        if normalized_latency not in {"speed", "balanced", "quality"}:
            normalized_latency = "balanced"

        recommended_model, fallback_model, reasons = _recommend_model(
            workload=workload,
            gpu_vram_gb=detected_vram,
            cpu_only=effective_cpu_only,
            multilingual_required=multilingual_required,
            long_context_required=long_context_required,
            latency_priority=normalized_latency,
        )

        constraints = [
            "Canonical governance retrieval remains deterministic-first.",
            "Memory-backed recommendations are advisory unless policy says otherwise.",
            "Fail open if local embedding retrieval is unavailable.",
            "Apply governed PII handling before persistent memory writes.",
        ]
        if effective_cpu_only:
            constraints.append(
                "CPU-only mode should avoid latency-sensitive routing loops and large long-form ingestion as first deployments."
            )
        if workload == "long_form_standards_ingestion":
            constraints.append(
                "Long-form standards ingestion still requires chunking, provenance, and freshness policy beyond model selection."
            )

        endpoint = _normalize_ollama_endpoint(ollama_host)
        runtime_status = _check_ollama_runtime(endpoint, recommended_model, fallback_model)

        recommendation = {
            "profile_id": str(uuid.uuid4()),
            "agent_id": agent_id,
            "hardware_summary": {
                "cpu_only": effective_cpu_only,
                "gpu_vram_gb": detected_vram,
                "gpu_vram_source": detected_from,
                "platform": platform.system(),
                "platform_release": platform.release(),
                "cpu_count": hardware_probe.get("cpu_count"),
                "gpu_count": hardware_probe.get("gpu_count"),
                "gpu_devices": hardware_probe.get("gpu_devices", []),
            },
            "workload_profile": {
                "workload": workload,
                "multilingual_required": multilingual_required,
                "long_context_required": long_context_required,
                "latency_priority": normalized_latency,
            },
            "embedding_recommendation": {
                "model": recommended_model,
                "batch_size": _batch_size_for(recommended_model, effective_cpu_only),
                "transport": "local_ollama_embed_api",
                "endpoint": endpoint,
                "vector_db_config": _vector_db_config_for(recommended_model),
            },
            "fallback_recommendation": {
                "model": fallback_model,
                "batch_size": _batch_size_for(fallback_model, effective_cpu_only),
                "vector_db_config": _vector_db_config_for(fallback_model),
            },
            "allowed_modes": {
                "deterministic_only": True,
                "advisory_memory_context": True,
                "default_enable_memory_context": workload
                in {"translation_memory", "repair_pattern_recall"},
            },
            "policy_constraints": constraints,
            "runtime_status": runtime_status,
            "reasons": reasons,
            "confidence": "medium",
        }
        if persist:
            recommendation = ctx.persist_embedding_profile(recommendation)
        return recommendation

    @mcp.tool()
    def hlf_sync_model_catalog(
        agent_id: str = "unknown-agent",
        agent_role: str = "generalist",
        ollama_host: str | None = None,
        runtime_status: dict[str, Any] | None = None,
        hardware_summary: dict[str, Any] | None = None,
        persist: bool = True,
    ) -> dict[str, Any]:
        """Sync a governed model catalog for an agent, including explicit remote-direct endpoints from HLF_REMOTE_MODEL_ENDPOINTS."""
        profile = ctx.get_embedding_profile(agent_id=agent_id)
        endpoint = _normalize_ollama_endpoint(
            ollama_host or (profile or {}).get("embedding_recommendation", {}).get("endpoint")
        )
        effective_hardware = dict(
            hardware_summary or (profile or {}).get("hardware_summary") or _probe_local_hardware()
        )

        effective_runtime = dict(runtime_status or (profile or {}).get("runtime_status") or {})
        if not effective_runtime:
            reference_model = (
                (profile or {}).get("embedding_recommendation", {}).get("model", "embeddinggemma")
            )
            fallback_model = (
                (profile or {}).get("fallback_recommendation", {}).get("model", "all-minilm")
            )
            effective_runtime = _check_ollama_runtime(
                endpoint, str(reference_model), str(fallback_model)
            )

        remote_direct_entries, env_error = _load_remote_direct_entries()
        catalog = sync_model_catalog(
            ollama_endpoint=endpoint,
            runtime_status=effective_runtime,
            hardware_summary=effective_hardware,
            agent_id=agent_id,
            agent_role=agent_role,
            remote_direct_entries=remote_direct_entries,
        )
        if env_error:
            catalog["remote_direct_env_error"] = env_error
        catalog["remote_direct_entries"] = remote_direct_entries
        catalog["remote_direct_env_var_present"] = bool(
            os.environ.get("HLF_REMOTE_MODEL_ENDPOINTS", "").strip()
        )
        if persist:
            catalog = ctx.persist_model_catalog(catalog)
        return {"status": "ok", "catalog": catalog}

    @mcp.tool()
    def hlf_align_check(
        payload: str,
        agent_id: str = "unknown-agent",
        workload: Workload = "agent_routing_context",
    ) -> dict[str, Any]:
        """Run the packaged deterministic ALIGN gate against a routing or execution payload."""
        verdict = ctx.align_governor.evaluate(payload)
        governance_event = ctx.emit_governance_event(
            kind="align_verdict",
            source="server_profiles.hlf_align_check",
            action="align_check",
            status="blocked" if verdict.status == "blocked" else verdict.status,
            severity="critical"
            if verdict.status == "blocked"
            else "warning"
            if verdict.status == "warning"
            else "info",
            subject_id=verdict.subject_hash,
            goal_id=agent_id,
            details={
                "agent_id": agent_id,
                "workload": workload,
                "loaded_rule_count": verdict.loaded_rule_count,
                "decisive_rule_id": verdict.decisive_rule_id,
                "decisive_rule_name": verdict.decisive_rule_name,
                "action": verdict.action,
                "matches": verdict.to_dict()["matches"],
            },
            agent_role="align_governor",
            anomaly_score=1.0
            if verdict.status == "blocked"
            else 0.5
            if verdict.status == "warning"
            else 0.0,
        )
        return {
            "status": "ok",
            "agent_id": agent_id,
            "workload": workload,
            "verdict": verdict.to_dict(),
            "governance_event": governance_event,
        }

    @mcp.tool()
    def hlf_route_governed_request(
        payload: str,
        workload: Workload = "agent_routing_context",
        gpu_vram_gb: float | None = None,
        cpu_only: bool = False,
        multilingual_required: bool = False,
        long_context_required: bool = False,
        latency_priority: str = "balanced",
        ollama_host: str | None = None,
        trust_state: str = "trusted",
        agent_id: str = "unknown-agent",
        agent_role: str = "generalist",
        runtime_status: dict[str, Any] | None = None,
        hardware_summary: dict[str, Any] | None = None,
        benchmark_scores: dict[str, float] | None = None,
        persist: bool = True,
    ) -> dict[str, Any]:
        """Produce a packaged governed-routing verdict by combining ALIGN, hardware, runtime, and policy posture."""
        align_result = hlf_align_check(payload=payload, agent_id=agent_id, workload=workload)
        align_verdict = align_result["verdict"]

        profile = hlf_recommend_embedding_profile(
            workload=workload,
            gpu_vram_gb=gpu_vram_gb,
            cpu_only=cpu_only,
            multilingual_required=multilingual_required,
            long_context_required=long_context_required,
            latency_priority=latency_priority,
            ollama_host=ollama_host,
            agent_id=agent_id,
            persist=persist,
        )

        catalog_result = hlf_sync_model_catalog(
            agent_id=agent_id,
            agent_role=agent_role,
            ollama_host=ollama_host,
            runtime_status=runtime_status,
            hardware_summary=hardware_summary,
            persist=persist,
        )
        catalog = catalog_result["catalog"]
        selected_lane = _workload_to_catalog_lane(workload)
        lane_summary = dict(catalog.get("lane_recommendations", {}).get(selected_lane) or {})
        routing_primary = _catalog_candidate_to_route(
            lane_summary.get("preferred"),
            profile.get("embedding_recommendation", {}),
        )
        routing_fallback = _catalog_candidate_to_route(
            lane_summary.get("best_local")
            or lane_summary.get("best_remote_direct")
            or lane_summary.get("fallback"),
            profile.get("fallback_recommendation", {}),
        )

        route_profile_candidates = _route_profile_candidates(
            workload, selected_lane, multilingual_required
        )
        (
            active_profiles,
            benchmark_artifacts,
            profile_benchmark_scores,
            effective_benchmark_scores,
        ) = _collect_route_profile_artifacts(
            ctx,
            profile_names=route_profile_candidates,
            benchmark_scores=benchmark_scores,
        )
        required_evidence_profiles = [
            profile_name for profile_name in route_profile_candidates if profile_name
        ]
        missing_evidence_profiles = [
            profile_name
            for profile_name in required_evidence_profiles
            if profile_name not in active_profiles
        ]

        qualification_profile = _qualification_profile_for(workload, multilingual_required)
        selection_profiles = _route_selection_profiles(
            active_profiles=active_profiles,
            qualification_profile=qualification_profile,
            selected_lane=selected_lane,
        )
        fallback_entry = (
            lane_summary.get("best_local")
            or lane_summary.get("best_remote_direct")
            or lane_summary.get("fallback")
        )
        primary_qualification = None
        fallback_qualification = None
        primary_profile_evaluations: dict[str, dict[str, Any]] = {}
        fallback_profile_evaluations: dict[str, dict[str, Any]] = {}
        if lane_summary.get("preferred"):
            for profile_name in active_profiles:
                primary_profile_evaluations[profile_name] = evaluate_model_against_profile(
                    lane_summary["preferred"],
                    profile_name=profile_name,
                    benchmark_scores=profile_benchmark_scores.get(profile_name),
                    require_reachable=True,
                )
        if fallback_entry:
            for profile_name in active_profiles:
                fallback_profile_evaluations[profile_name] = evaluate_model_against_profile(
                    fallback_entry,
                    profile_name=profile_name,
                    benchmark_scores=profile_benchmark_scores.get(profile_name),
                    require_reachable=True,
                )

        primary_qualification = (
            primary_profile_evaluations.get(qualification_profile)
            if qualification_profile
            else None
        )
        fallback_qualification = (
            fallback_profile_evaluations.get(qualification_profile)
            if qualification_profile
            else None
        )

        selection_primary_evaluations = {
            profile_name: primary_profile_evaluations[profile_name]
            for profile_name in selection_profiles
            if profile_name in primary_profile_evaluations
        }
        selection_fallback_evaluations = {
            profile_name: fallback_profile_evaluations[profile_name]
            for profile_name in selection_profiles
            if profile_name in fallback_profile_evaluations
        }
        selected_primary_profile_evaluations = dict(primary_profile_evaluations)
        selected_primary_qualification = primary_qualification

        if selection_profiles and not _profile_set_ready(selection_primary_evaluations):
            if fallback_entry and _profile_set_ready(selection_fallback_evaluations):
                routing_primary = _catalog_candidate_to_route(
                    fallback_entry, profile.get("embedding_recommendation", {})
                )
                lane_summary = dict(lane_summary)
                lane_summary["preferred"] = fallback_entry
                selected_primary_profile_evaluations = dict(fallback_profile_evaluations)
                selected_primary_qualification = fallback_qualification

        route_verdict = build_governed_route(
            workload=workload,
            align_status=str(align_verdict.get("status", "ok")),
            trust_state=trust_state,
            hardware_summary=catalog.get("hardware_summary", profile.get("hardware_summary", {})),
            runtime_status=catalog.get("runtime_status", profile.get("runtime_status", {})),
            embedding_recommendation=routing_primary,
            fallback_recommendation=routing_fallback,
            selected_lane=selected_lane,
            lane_candidate_summary=lane_summary,
        )
        if active_profiles:
            for profile_name in active_profiles:
                evaluation = primary_profile_evaluations.get(profile_name)
                if evaluation is None:
                    continue
                route_verdict.rationale.append(
                    f"Qualification profile '{profile_name}' resolved the preferred candidate at tier {evaluation.get('resolved_tier', 'advisory-only')}."
                )
            if not _profile_set_ready(primary_profile_evaluations):
                route_verdict.review_required = True
                route_verdict.governance_mode = "qualification_constrained"
                route_verdict.rationale.append(
                    "Preferred candidate did not clear the evidence-backed qualification set for this governed lane, so preferred selection was constrained."
                )
                for profile_name in active_profiles:
                    fallback_evaluation = fallback_profile_evaluations.get(profile_name)
                    if fallback_evaluation:
                        route_verdict.rationale.append(
                            f"Fallback candidate under '{profile_name}' resolved at tier {fallback_evaluation.get('resolved_tier', 'advisory-only')}."
                        )
                route_verdict.primary_model = str(
                    routing_primary.get("model", route_verdict.primary_model)
                )
                route_verdict.primary_access_mode = str(
                    routing_primary.get("access_mode", route_verdict.primary_access_mode)
                )
        policy_basis_present = bool(
            align_result.get("governance_event", {}).get("event_ref")
        ) and bool(align_verdict.get("status"))
        if missing_evidence_profiles or not policy_basis_present:
            route_verdict.allowed = False
            route_verdict.decision = "deny"
            route_verdict.governance_mode = "evidence_required"
            route_verdict.review_required = True
            if missing_evidence_profiles:
                route_verdict.rationale.append(
                    "Routing was denied because required benchmark evidence is missing for one or more governed profiles."
                )
                route_verdict.policy_constraints.append(
                    f"Required benchmark evidence missing for profiles: {', '.join(missing_evidence_profiles)}."
                )
            if not policy_basis_present:
                route_verdict.rationale.append(
                    "Routing was denied because the policy basis could not be fully materialized from ALIGN status and governance event context."
                )
                route_verdict.policy_constraints.append(
                    "A governed route requires both ALIGN status and a persisted governance event reference."
                )
        governance_event = ctx.emit_governance_event(
            kind="routing_decision",
            source="server_profiles.hlf_route_governed_request",
            action="route_governed_request",
            status="blocked"
            if not route_verdict.allowed
            else "warning"
            if route_verdict.review_required
            else "ok",
            severity="critical"
            if not route_verdict.allowed
            else "warning"
            if route_verdict.review_required
            else "info",
            subject_id=agent_id,
            goal_id=str(profile.get("profile_id", "")),
            details={
                "workload": workload,
                "trust_state": trust_state,
                "decision": route_verdict.decision,
                "governance_mode": route_verdict.governance_mode,
                "review_required": route_verdict.review_required,
                "selected_lane": route_verdict.selected_lane,
                "primary_model": route_verdict.primary_model,
                "primary_access_mode": route_verdict.primary_access_mode,
                "fallback_model": route_verdict.fallback_model,
                "fallback_access_mode": route_verdict.fallback_access_mode,
                "qualification_profile": qualification_profile,
                "applied_qualification_profiles": active_profiles,
                "preferred_model_tier": (primary_qualification or {}).get("resolved_tier"),
                "benchmark_scores": effective_benchmark_scores,
                "align_status": align_verdict.get("status"),
                "align_rule_id": align_verdict.get("decisive_rule_id"),
            },
            agent_role="governed_router",
            anomaly_score=1.0
            if not route_verdict.allowed
            else 0.5
            if route_verdict.review_required
            else 0.0,
            related_refs=[align_result["governance_event"]["event_ref"]],
        )
        route_trace = RouteTraceRecord(
            request_context={
                "agent_id": agent_id,
                "agent_role": agent_role,
                "workload": workload,
                "trust_state": trust_state,
            },
            route_decision=RouteDecisionRecord(
                decision=route_verdict.decision,
                governance_mode=route_verdict.governance_mode,
                review_required=route_verdict.review_required,
                selected_lane=route_verdict.selected_lane,
                primary_model=route_verdict.primary_model,
                fallback_model=route_verdict.fallback_model,
                primary_access_mode=route_verdict.primary_access_mode,
                fallback_access_mode=route_verdict.fallback_access_mode,
                qualification_profile=qualification_profile,
                applied_qualification_profiles=list(active_profiles),
                preferred_model_tier=(selected_primary_qualification or {}).get("resolved_tier"),
                benchmark_scores=dict(effective_benchmark_scores),
                align_status=str(align_verdict.get("status"))
                if align_verdict.get("status") is not None
                else None,
                align_rule_id=align_verdict.get("decisive_rule_id"),
            ),
            selection_profiles=list(selection_profiles),
            profile_evaluations=dict(selected_primary_profile_evaluations),
            benchmark_evidence=dict(benchmark_artifacts),
            policy_basis={
                "align_status": align_verdict.get("status"),
                "align_rule_id": align_verdict.get("decisive_rule_id"),
                "governance_event_ref": governance_event.get("event_ref"),
                "policy_constraints": list(route_verdict.policy_constraints),
                "policy_basis_present": policy_basis_present,
                "required_evidence_profiles": list(required_evidence_profiles),
                "missing_evidence_profiles": list(missing_evidence_profiles),
            },
            fallback_chain=[
                {
                    "model": routing_fallback.get("model", ""),
                    "access_mode": routing_fallback.get("access_mode", ""),
                    "qualification": fallback_qualification,
                }
            ]
            if routing_fallback.get("model")
            else [],
            lane_candidate_summary=build_lane_trace_context(catalog, selected_lane),
        )
        route_trace.operator_summary = build_operator_route_summary(route_trace)
        persisted_route_trace = ctx.persist_governed_route(route_trace.to_dict())
        return {
            "status": "ok",
            "agent_id": agent_id,
            "workload": workload,
            "align_verdict": align_verdict,
            "align_governance_event": align_result["governance_event"],
            "profile": profile,
            "model_catalog": catalog,
            "routing_verdict": route_verdict.to_dict(),
            "qualification_profile": qualification_profile,
            "applied_qualification_profiles": active_profiles,
            "benchmark_scores": effective_benchmark_scores,
            "benchmark_artifacts": benchmark_artifacts,
            "required_evidence_profiles": required_evidence_profiles,
            "missing_evidence_profiles": missing_evidence_profiles,
            "primary_qualification": primary_qualification,
            "fallback_qualification": fallback_qualification,
            "selected_primary_qualification": selected_primary_qualification,
            "primary_profile_evaluations": primary_profile_evaluations,
            "fallback_profile_evaluations": fallback_profile_evaluations,
            "selected_primary_profile_evaluations": selected_primary_profile_evaluations,
            "route_trace": persisted_route_trace,
            "governance_event": governance_event,
        }

    @mcp.tool()
    def hlf_get_embedding_profile(
        agent_id: str | None = None,
        profile_id: str | None = None,
    ) -> dict[str, Any]:
        """Retrieve a previously negotiated embedding profile from session context."""
        profile = ctx.get_embedding_profile(agent_id=agent_id, profile_id=profile_id)
        if profile is None:
            return {"status": "not_found", "agent_id": agent_id, "profile_id": profile_id}
        return {"status": "ok", "profile": profile}

    @mcp.tool()
    def hlf_get_model_catalog(agent_id: str | None = None) -> dict[str, Any]:
        """Retrieve the last synced governed model catalog for an agent."""
        catalog = ctx.get_model_catalog(agent_id=agent_id)
        if catalog is None:
            return {"status": "not_found", "agent_id": agent_id}
        return {"status": "ok", "catalog": catalog}

    @mcp.tool()
    def hlf_get_model_catalog_status(agent_id: str | None = None) -> dict[str, Any]:
        """Return the latest operator-facing lane summary for the synced governed model catalog."""
        status = ctx.get_model_catalog_status(agent_id=agent_id)
        if status is None:
            return {"status": "not_found", "agent_id": agent_id}
        return {"status": "ok", "catalog_status": status}

    @mcp.tool()
    def hlf_record_benchmark_artifact(
        profile_name: str,
        benchmark_scores: dict[str, float],
        artifact_id: str | None = None,
        topic: str = "manual_governed_benchmark",
        domains: list[str] | None = None,
        languages: list[str] | None = None,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Persist a governed benchmark artifact so routing and qualification can consume recorded evidence."""
        normalized_scores = {
            str(metric): float(score) for metric, score in benchmark_scores.items()
        }
        normalized_artifact_id = (
            artifact_id or f"benchmark:{profile_name}:{topic}:{uuid.uuid4().hex[:12]}"
        )
        artifact = {
            "artifact_id": normalized_artifact_id,
            "profile_name": profile_name,
            "benchmark_scores": normalized_scores,
            "topic": topic,
            "domains": list(domains or []),
            "languages": list(languages or []),
            "details": dict(details or {}),
        }
        persisted = ctx.persist_benchmark_artifact(artifact)
        return {"status": "ok", "artifact": persisted}

    @mcp.tool()
    def hlf_get_benchmark_artifact(profile_name: str | None = None) -> dict[str, Any]:
        """Retrieve the latest persisted governed benchmark artifact by profile."""
        artifact = ctx.get_benchmark_artifact(profile_name=profile_name)
        if artifact is None:
            return {"status": "not_found", "profile_name": profile_name}
        return {"status": "ok", "artifact": artifact}

    @mcp.tool()
    def hlf_evaluate_model_against_profile(
        model_name: str,
        profile_name: str,
        agent_id: str | None = None,
        benchmark_scores: dict[str, float] | None = None,
        require_reachable: bool = True,
    ) -> dict[str, Any]:
        """Evaluate a synced model against a governed qualification profile, using persisted benchmark evidence when available."""
        catalog = ctx.get_model_catalog(agent_id=agent_id)
        if catalog is None:
            return {"status": "not_found", "agent_id": agent_id, "model_name": model_name}

        selected_entry = None
        for entry in catalog.get("entries", []):
            if str(entry.get("name")) == model_name:
                selected_entry = entry
                break
        if selected_entry is None:
            return {
                "status": "not_found",
                "agent_id": agent_id,
                "model_name": model_name,
                "available_models": [
                    str(entry.get("name", "")) for entry in catalog.get("entries", [])
                ],
            }

        artifact = ctx.get_benchmark_artifact(profile_name=profile_name)
        effective_scores = {
            str(metric): float(score)
            for metric, score in ((artifact or {}).get("benchmark_scores") or {}).items()
        }
        if benchmark_scores:
            effective_scores.update(
                {str(metric): float(score) for metric, score in benchmark_scores.items()}
            )

        evaluation = evaluate_model_against_profile(
            selected_entry,
            profile_name=profile_name,
            benchmark_scores=effective_scores,
            require_reachable=require_reachable,
        )
        return {
            "status": "ok",
            "agent_id": agent_id,
            "artifact": artifact,
            "evaluation": evaluation,
        }

    @mcp.tool()
    def hlf_evaluate_model_requirements(
        model_name: str,
        agent_id: str | None = None,
        required_lanes: list[str] | None = None,
        required_capabilities: list[str] | None = None,
        required_languages: list[str] | None = None,
        minimum_benchmark_scores: dict[str, float] | None = None,
        benchmark_scores: dict[str, float] | None = None,
        require_reachable: bool = True,
    ) -> dict[str, Any]:
        """Evaluate whether a synced model satisfies minimum lane, language, and benchmark requirements."""
        catalog = ctx.get_model_catalog(agent_id=agent_id)
        if catalog is None:
            return {"status": "not_found", "agent_id": agent_id, "model_name": model_name}

        selected_entry = None
        for entry in catalog.get("entries", []):
            if str(entry.get("name")) == model_name:
                selected_entry = entry
                break
        if selected_entry is None:
            return {
                "status": "not_found",
                "agent_id": agent_id,
                "model_name": model_name,
                "available_models": [
                    str(entry.get("name", "")) for entry in catalog.get("entries", [])
                ],
            }

        evaluation = evaluate_model_requirements(
            selected_entry,
            required_lanes=required_lanes or [],
            required_capabilities=required_capabilities or [],
            required_languages=required_languages or [],
            minimum_benchmark_scores=minimum_benchmark_scores,
            benchmark_scores=benchmark_scores,
            require_reachable=require_reachable,
        )
        return {"status": "ok", "agent_id": agent_id, "evaluation": evaluation}

    @mcp.tool()
    def hlf_evaluate_model_requirement_tiers(
        model_name: str,
        agent_id: str | None = None,
        required_lanes: list[str] | None = None,
        required_capabilities: list[str] | None = None,
        required_languages: list[str] | None = None,
        baseline_benchmark_scores: dict[str, float] | None = None,
        launch_benchmark_scores: dict[str, float] | None = None,
        promotion_benchmark_scores: dict[str, float] | None = None,
        benchmark_scores: dict[str, float] | None = None,
        require_reachable: bool = True,
    ) -> dict[str, Any]:
        """Evaluate a synced model against advisory, baseline, launch, and promotion qualification tiers."""
        catalog = ctx.get_model_catalog(agent_id=agent_id)
        if catalog is None:
            return {"status": "not_found", "agent_id": agent_id, "model_name": model_name}

        selected_entry = None
        for entry in catalog.get("entries", []):
            if str(entry.get("name")) == model_name:
                selected_entry = entry
                break
        if selected_entry is None:
            return {
                "status": "not_found",
                "agent_id": agent_id,
                "model_name": model_name,
                "available_models": [
                    str(entry.get("name", "")) for entry in catalog.get("entries", [])
                ],
            }

        evaluation = evaluate_model_requirement_tiers(
            selected_entry,
            required_lanes=required_lanes or [],
            required_capabilities=required_capabilities or [],
            required_languages=required_languages or [],
            baseline_benchmark_scores=baseline_benchmark_scores,
            launch_benchmark_scores=launch_benchmark_scores,
            promotion_benchmark_scores=promotion_benchmark_scores,
            benchmark_scores=benchmark_scores,
            require_reachable=require_reachable,
        )
        return {"status": "ok", "agent_id": agent_id, "evaluation": evaluation}

    return {
        "hlf_probe_local_hardware": hlf_probe_local_hardware,
        "hlf_recommend_embedding_profile": hlf_recommend_embedding_profile,
        "hlf_sync_model_catalog": hlf_sync_model_catalog,
        "hlf_align_check": hlf_align_check,
        "hlf_route_governed_request": hlf_route_governed_request,
        "hlf_get_embedding_profile": hlf_get_embedding_profile,
        "hlf_get_model_catalog": hlf_get_model_catalog,
        "hlf_get_model_catalog_status": hlf_get_model_catalog_status,
        "hlf_record_benchmark_artifact": hlf_record_benchmark_artifact,
        "hlf_get_benchmark_artifact": hlf_get_benchmark_artifact,
        "hlf_evaluate_model_against_profile": hlf_evaluate_model_against_profile,
        "hlf_evaluate_model_requirements": hlf_evaluate_model_requirements,
        "hlf_evaluate_model_requirement_tiers": hlf_evaluate_model_requirement_tiers,
    }
