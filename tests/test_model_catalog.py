from __future__ import annotations

from hlf_mcp.hlf.model_catalog import build_named_model_chain, build_named_model_chains, sync_model_catalog


def test_sync_model_catalog_marks_pullable_and_impractical_models() -> None:
    result = sync_model_catalog(
        ollama_endpoint="http://localhost:11434",
        runtime_status={
            "ollama_available": True,
            "installed_models": ["embeddinggemma", "qwen3:8b"],
        },
        hardware_summary={"cpu_only": True, "gpu_vram_gb": 0.0},
        agent_id="retriever-1",
        agent_role="retriever",
    )

    entries = {entry["name"]: entry for entry in result["entries"]}

    assert result["ollama_access_mode"] == "local-via-ollama"
    assert entries["embeddinggemma"]["installed"] is True
    assert entries["nomic-embed-text-v2-moe"]["pullable"] is True
    assert entries["qwen3-embedding:4b"]["known_but_impractical"] is True
    assert result["agent_lane_summary"]["retrieval"]["preferred"]["name"] == "embeddinggemma"


def test_sync_model_catalog_surfaces_cloud_via_ollama_recommendations() -> None:
    result = sync_model_catalog(
        ollama_endpoint="https://cloud.ollama.example.com",
        runtime_status={
            "ollama_available": True,
            "installed_models": ["embeddinggemma", "qwen3:8b", "devstral:24b"],
        },
        hardware_summary={"cpu_only": False, "gpu_vram_gb": 24.0},
        agent_id="verifier-1",
        agent_role="verifier",
    )

    verifier_lane = result["agent_lane_summary"]["verifier"]

    assert result["ollama_access_mode"] == "cloud-via-ollama"
    assert verifier_lane["best_cloud_via_ollama"]["access_mode"] == "cloud-via-ollama"
    assert verifier_lane["preferred"]["name"] in {"qwen3:8b", "devstral:24b"}


def test_build_named_model_chain_uses_packaged_policy() -> None:
    chain = build_named_model_chain(
        "coding",
        available_models={
            "devstral-2:123b-cloud",
            "minimax-m2.7:cloud",
            "qwen3-coder-next:cloud",
            "glm-5:cloud",
            "qwen3.5:cloud",
        },
    )

    assert len(chain) >= 2
    assert chain[0] in {
        "devstral-2:123b-cloud",
        "minimax-m2.7:cloud",
        "qwen3-coder-next:cloud",
    }
    assert "qwen3.5:cloud" in chain


def test_build_named_model_chains_returns_all_workflow_names() -> None:
    chains = build_named_model_chains(
        available_models={
            "glm-5:cloud",
            "nemotron-3-super",
            "cogito-2.1:671b-cloud",
            "kimi-k2-thinking:cloud",
            "kimi-k2.5:cloud",
            "minimax-m2.7:cloud",
            "devstral-2:123b-cloud",
            "qwen3-coder-next:cloud",
            "qwen3.5:cloud",
            "deepseek-v3.2:cloud",
        }
    )

    assert set(chains) == {
        "reasoning",
        "planning",
        "doer",
        "coding",
        "analysis",
        "ethics",
        "universal",
    }
