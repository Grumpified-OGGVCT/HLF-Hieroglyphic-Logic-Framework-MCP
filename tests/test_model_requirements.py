from __future__ import annotations

from hlf_mcp import server
from hlf_mcp.hlf.model_catalog import evaluate_model_against_profile, evaluate_model_requirement_tiers, evaluate_model_requirements, sync_model_catalog


def _catalog_entries() -> dict[str, dict]:
    catalog = sync_model_catalog(
        ollama_endpoint="http://localhost:11434",
        runtime_status={
            "ollama_available": True,
            "installed_models": ["nomic-embed-text-v2-moe", "embeddinggemma", "qwen3:8b"],
        },
        hardware_summary={"cpu_only": False, "gpu_vram_gb": 16.0},
        agent_id="bench-agent",
        agent_role="researcher",
    )
    return {entry["name"]: entry for entry in catalog["entries"]}


def test_model_requirements_accept_multilingual_model_with_required_scores() -> None:
    entry = _catalog_entries()["nomic-embed-text-v2-moe"]

    result = evaluate_model_requirements(
        entry,
        required_lanes=["retrieval"],
        required_capabilities=["embedding"],
        required_languages=["en", "zh"],
        minimum_benchmark_scores={"translation_fidelity": 0.9, "routing_quality": 0.8},
        benchmark_scores={"translation_fidelity": 0.95, "routing_quality": 0.84},
    )

    assert result["qualified"] is True
    assert result["missing_languages"] == []
    assert result["failed_benchmarks"] == []


def test_model_requirements_reject_model_missing_language_and_benchmark_threshold() -> None:
    entry = _catalog_entries()["embeddinggemma"]

    result = evaluate_model_requirements(
        entry,
        required_lanes=["retrieval"],
        required_capabilities=["embedding"],
        required_languages=["en", "zh"],
        minimum_benchmark_scores={"translation_fidelity": 0.9},
        benchmark_scores={"translation_fidelity": 0.72},
    )

    assert result["qualified"] is False
    assert result["missing_languages"] == ["zh"]
    assert result["failed_benchmarks"] == [
        {
            "benchmark": "translation_fidelity",
            "required_minimum": 0.9,
            "actual_score": 0.72,
        }
    ]


def test_model_requirement_tiers_distinguish_baseline_launch_and_promotion() -> None:
    entry = _catalog_entries()["nomic-embed-text-v2-moe"]

    result = evaluate_model_requirement_tiers(
        entry,
        required_lanes=["retrieval"],
        required_capabilities=["embedding", "semantic-recall"],
        required_languages=["en", "zh"],
        baseline_benchmark_scores={"translation_fidelity": 0.85},
        launch_benchmark_scores={"translation_fidelity": 0.9, "routing_quality": 0.8},
        promotion_benchmark_scores={"translation_fidelity": 0.97, "routing_quality": 0.9},
        benchmark_scores={"translation_fidelity": 0.94, "routing_quality": 0.82},
    )

    assert result["resolved_tier"] == "launch-qualified"
    assert result["tiers"]["baseline-qualified"]["qualified"] is True
    assert result["tiers"]["launch-qualified"]["qualified"] is True
    assert result["tiers"]["promotion-qualified"]["qualified"] is False


def test_model_profile_evaluation_uses_governed_translation_memory_profile() -> None:
    entry = _catalog_entries()["nomic-embed-text-v2-moe"]

    result = evaluate_model_against_profile(
        entry,
        profile_name="translation_memory_multilingual",
        benchmark_scores={
            "translation_fidelity": 0.93,
            "retrieval_quality": 0.82,
            "routing_quality": 0.78,
        },
    )

    assert result["profile_name"] == "translation_memory_multilingual"
    assert result["resolved_tier"] == "launch-qualified"


def test_model_profile_evaluation_supports_sidecar_quality_profile() -> None:
    entry = _catalog_entries()["qwen3:8b"]

    result = evaluate_model_against_profile(
        entry,
        profile_name="sidecar_quality_explainer",
        benchmark_scores={"sidecar_quality": 0.91},
    )

    assert result["resolved_tier"] == "launch-qualified"


def test_profile_tool_uses_persisted_benchmark_artifact_when_scores_are_omitted(monkeypatch) -> None:
    monkeypatch.delenv("HLF_REMOTE_MODEL_ENDPOINTS", raising=False)

    server.hlf_record_benchmark_artifact(
        profile_name="sidecar_quality_explainer",
        benchmark_scores={"sidecar_quality": 0.91},
        topic="persisted_profile_eval",
        details={"source": "test"},
    )
    server.hlf_sync_model_catalog(
        agent_id="profile-artifact-agent",
        agent_role="researcher",
        runtime_status={
            "ollama_available": True,
            "installed_models": ["qwen3:8b"],
            "recommended_model_runnable": True,
            "fallback_model_runnable": False,
        },
        hardware_summary={"cpu_only": False, "gpu_vram_gb": 16.0},
    )

    result = server.hlf_evaluate_model_against_profile(
        model_name="qwen3:8b",
        profile_name="sidecar_quality_explainer",
        agent_id="profile-artifact-agent",
    )

    assert result["status"] == "ok"
    assert result["artifact"]["profile_name"] == "sidecar_quality_explainer"
    assert result["evaluation"]["resolved_tier"] == "launch-qualified"
