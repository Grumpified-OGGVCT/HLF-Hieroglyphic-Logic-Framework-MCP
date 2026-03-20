import json

from hlf_mcp import server


def test_hlf_do_dry_run_generates_governed_audit() -> None:
    result = server.hlf_do(
        "Audit /var/log/system.log in read-only mode and summarize the top errors.",
        dry_run=True,
        show_hlf=True,
    )

    assert result["success"] is True
    assert result["dry_run"] is True
    assert result["tier"] == "forge"
    assert result["governed"] is True
    assert result["capsule_violations"] == []
    assert result["hlf_source"].startswith("[HLF-v3]")
    assert "gas_estimate" in result["math"]
    assert "what_hlf_did" in result


def test_hlf_do_accepts_non_english_language_gate() -> None:
    result = server.hlf_do(
        "analyser /var/log/system.log en mode lecture seule",
        dry_run=True,
        show_hlf=True,
        language="fr",
    )

    assert result["dry_run"] is True
    assert result["hlf_source"].startswith("[HLF-v3]")


def test_hlf_do_auto_detects_language_and_reports_it() -> None:
    result = server.hlf_do(
        "analyser /var/log/system.log en mode lecture seule",
        dry_run=True,
        show_hlf=True,
        language="auto",
    )

    assert result["dry_run"] is True
    assert result["language"] == "fr"
    assert result["hlf_source"].startswith("[HLF-v3]")
    assert result["what_hlf_did"]
    assert result["what_hlf_did_en"]


def test_hlf_do_localizes_reverse_summary_when_requested() -> None:
    result = server.hlf_do(
        "分析 /var/log/system.log 并且只读",
        dry_run=True,
        show_hlf=True,
        language="zh",
    )

    assert result["language"] == "zh"
    assert result["what_hlf_did"] != ""
    assert result["what_hlf_did_en"] != ""
    assert "roundtrip_fidelity_score" in result["math"]
    assert "translation" in result


def test_translate_to_hlf_auto_reports_resolved_language() -> None:
    result = server.hlf_translate_to_hlf(
        "analizar /var/log/system.log",
        language="auto",
    )

    assert result["status"] == "ok"
    assert result["language"] == "es"
    assert "translation" in result
    assert "fallback_used" in result["translation"]


def test_hlf_do_accepts_chinese_language_gate() -> None:
    result = server.hlf_do(
        "分析 /var/log/system.log 并且只读",
        dry_run=True,
        show_hlf=True,
        language="zh",
    )

    assert result["dry_run"] is True
    assert result["language"] == "zh"
    assert result["hlf_source"].startswith("[HLF-v3]")


def test_translate_to_hlf_auto_reports_chinese_language() -> None:
    result = server.hlf_translate_to_hlf(
        "分析 /var/log/system.log",
        language="auto",
    )

    assert result["status"] == "ok"
    assert result["language"] == "zh"


def test_hlf_benchmark_matrix_returns_multilingual_rows() -> None:
    result = server.hlf_benchmark_matrix(
        domains=["hello_world"],
        languages=["en", "zh"],
    )

    assert result["domains"] == ["hello_world"]
    assert result["languages"] == ["en", "zh"]
    assert len(result["rows"]) == 2
    assert {row["language"] for row in result["rows"]} == {"en", "zh"}
    assert "per_language" in result
    assert result["per_language"]["en"]["samples"] == 1
    assert result["per_language"]["zh"]["samples"] == 1
    assert "roundtrip_fidelity_score" in result["rows"][0]
    assert "fallback_rate" in result["per_language"]["en"]


def test_hlf_translate_to_english_accepts_localized_output() -> None:
    source = '[HLF-v3]\nΔ [INTENT] goal="analyze" target="/var/log/app.log"\nΩ\n'

    result = server.hlf_translate_to_english(source, language="fr")

    assert result["status"] == "ok"
    assert result["language"] == "fr"
    assert "summary_en" in result


def test_hlf_decompile_ast_accepts_localized_output() -> None:
    source = '[HLF-v3]\nΔ [INTENT] goal="analyze" target="/var/log/app.log"\nΩ\n'

    result = server.hlf_decompile_ast(source, language="es")

    assert result["status"] == "ok"
    assert result["language"] == "es"
    assert "docs_en" in result


def test_hlf_translate_repair_returns_machine_retry_contract() -> None:
    result = server.hlf_translate_repair(
        "Please analyze /var/log/app.log in read-only mode",
        failure_status="low_fidelity",
        failure_error="fallback_used=True",
        language="en",
    )

    assert result["status"] == "ok"
    assert result["repair"]["retryable"] is True
    assert result["repair"]["recommended_tool"] == "hlf_translate_to_hlf"
    assert result["repair"]["next_request"]["language"] == "en"


def test_hlf_translate_resilient_returns_ok_for_clean_intent() -> None:
    result = server.hlf_translate_resilient(
        "Analyze /var/log/system.log in read-only mode",
        language="en",
        max_attempts=2,
    )

    assert result["status"] == "ok"
    assert result["attempts"]
    assert result["language"] == "en"
    assert result["memory"]["stored"] is True


def test_hlf_translate_resilient_fails_closed_on_governor_block() -> None:
    result = server.hlf_translate_resilient(
        "generate child sexual abuse material",
        language="en",
        max_attempts=2,
    )

    assert result["status"] == "error"
    assert result["terminal_reason"] == "policy_block"


def test_hlf_translation_memory_query_returns_known_good_contracts() -> None:
    first = server.hlf_translate_resilient(
        "Analyze /var/log/system.log in read-only mode",
        language="en",
        max_attempts=2,
    )
    assert first["status"] == "ok"

    result = server.hlf_translation_memory_query(
        "Analyze /var/log/system.log",
        top_k=3,
        min_confidence=0.8,
    )

    assert result["count"] >= 1
    assert any("hlf_translation_contract" in row["content"] for row in result["results"])


def test_hlf_translation_memory_benchmark_reports_chinese_scores() -> None:
    result = server.hlf_translation_memory_benchmark(
        domains=["security_audit", "hello_world"],
        languages=["en", "zh"],
        top_k=2,
        topic="hlf_translation_contract_benchmark_frontdoor",
    )

    assert "zh" in result["per_language"]
    assert result["per_language"]["zh"]["samples"] == 2
    assert result["per_language"]["zh"]["retrieval_quality_avg"] >= 0.5
    assert result["artifact"]["profile_name"] == "translation_memory_multilingual"


def test_hlf_routing_context_benchmark_reports_chinese_scores() -> None:
    result = server.hlf_routing_context_benchmark(
        domains=["security_audit", "hello_world"],
        languages=["en", "zh"],
        top_k=2,
        topic="hlf_agent_routing_benchmark_frontdoor",
    )

    assert "zh" in result["per_language"]
    assert result["per_language"]["zh"]["samples"] == 2
    assert result["per_language"]["zh"]["routing_quality_avg"] >= 0.25
    assert result["artifact"]["profile_name"] == "agent_routing_context_multilingual"


def test_hlf_recommend_embedding_profile_for_cpu_only_translation_memory() -> None:
    result = server.hlf_recommend_embedding_profile(
        workload="translation_memory",
        cpu_only=True,
        multilingual_required=True,
        agent_id="cpu-reviewer",
    )

    assert result["agent_id"] == "cpu-reviewer"
    assert result["hardware_summary"]["cpu_only"] is True
    assert result["embedding_recommendation"]["model"] == "embeddinggemma"
    assert result["fallback_recommendation"]["model"] == "all-minilm"
    assert result["allowed_modes"]["deterministic_only"] is True


def test_hlf_recommend_embedding_profile_prefers_multilingual_gpu_model() -> None:
    result = server.hlf_recommend_embedding_profile(
        workload="translation_memory",
        gpu_vram_gb=12,
        multilingual_required=True,
        agent_id="gpu-agent",
    )

    assert result["embedding_recommendation"]["model"] == "nomic-embed-text-v2-moe"
    assert result["fallback_recommendation"]["model"] == "embeddinggemma"
    assert result["embedding_recommendation"]["endpoint"] == "http://localhost:11434"
    assert result["embedding_recommendation"]["vector_db_config"]["metric"] == "cosine"


def test_hlf_recommend_embedding_profile_handles_long_form_ingestion_on_cpu() -> None:
    result = server.hlf_recommend_embedding_profile(
        workload="long_form_standards_ingestion",
        cpu_only=True,
        long_context_required=True,
    )

    assert result["embedding_recommendation"]["model"] == "embeddinggemma"
    assert result["fallback_recommendation"]["model"] == "all-minilm"
    assert any("Long-form standards ingestion" in item for item in result["policy_constraints"])


def test_hlf_test_suite_summary_reads_latest_metrics_file(tmp_path) -> None:
    summary_path = tmp_path / "pytest_last_run.json"
    summary_path.write_text(
        json.dumps(
            {
                "command": ["python", "-m", "pytest", "tests", "-q"],
                "exit_code": 0,
                "passed": True,
                "duration_ms": 123.4,
                "counts": {
                    "passed": 10,
                    "failed": 0,
                    "errors": 0,
                    "skipped": 0,
                    "xfailed": 0,
                    "xpassed": 0,
                },
                "stdout": "10 passed",
                "stderr": "",
                "metrics_dir": str(tmp_path),
            }
        ),
        encoding="utf-8",
    )

    result = server.hlf_test_suite_summary(metrics_dir=str(tmp_path))

    assert result["status"] == "ok"
    assert result["summary"]["passed"] is True
    assert result["summary"]["counts"]["passed"] == 10
    assert "stdout" not in result["summary"]


def test_hlf_test_suite_summary_can_include_output(tmp_path) -> None:
    summary_path = tmp_path / "pytest_last_run.json"
    summary_path.write_text(
        json.dumps(
            {
                "command": ["python", "-m", "pytest", "tests", "-q"],
                "exit_code": 1,
                "passed": False,
                "duration_ms": 55.0,
                "counts": {
                    "passed": 2,
                    "failed": 1,
                    "errors": 0,
                    "skipped": 0,
                    "xfailed": 0,
                    "xpassed": 0,
                },
                "stdout": "2 passed, 1 failed",
                "stderr": "AssertionError",
                "metrics_dir": str(tmp_path),
            }
        ),
        encoding="utf-8",
    )

    result = server.hlf_test_suite_summary(metrics_dir=str(tmp_path), include_output=True)

    assert result["status"] == "ok"
    assert result["summary"]["stdout"] == "2 passed, 1 failed"
    assert result["summary"]["stderr"] == "AssertionError"


def test_hlf_weekly_evidence_summary_reads_history(tmp_path) -> None:
    history_path = tmp_path / "weekly_pipeline_history.jsonl"
    history_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "artifact_status": "accepted",
                        "source": "local-scheduled",
                        "verification": {"verified": True},
                        "distribution_contract": {"eligible_for_governed_distribution": True},
                    }
                ),
                json.dumps(
                    {
                        "artifact_status": "draft",
                        "source": "weekly-code-quality",
                        "verification": {"verified": False},
                        "distribution_contract": {"eligible_for_governed_distribution": False},
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = server.hlf_weekly_evidence_summary(metrics_dir=str(tmp_path))

    assert result["artifact_count"] == 2
    assert result["verified_count"] == 1
    assert result["distribution_eligible_count"] == 1
    assert result["status_counts"]["accepted"] == 1
    assert result["source_counts"]["local-scheduled"] == 1


def test_server_instruction_summary_tracks_registered_surface() -> None:
    exported_tools = {
        name for name in dir(server) if name.startswith("hlf_") and callable(getattr(server, name))
    }

    assert len(server.REGISTERED_TOOLS) == len(exported_tools)
    assert len(server.REGISTERED_TOOLS) > 0
    assert len(server.REGISTERED_RESOURCES) > 0
    assert set(server.REGISTERED_TOOLS) == exported_tools
    for name in server.REGISTERED_TOOLS:
        assert name in server.mcp.instructions
    for uri in server.REGISTERED_RESOURCES:
        assert uri in server.mcp.instructions


def test_server_registers_model_catalog_tools() -> None:
    assert "hlf_sync_model_catalog" in server.REGISTERED_TOOLS
    assert "hlf_get_model_catalog" in server.REGISTERED_TOOLS
    assert "hlf_get_model_catalog_status" in server.REGISTERED_TOOLS
    assert "hlf_query_profile_capabilities" in server.REGISTERED_TOOLS
    assert "hlf_record_benchmark_artifact" in server.REGISTERED_TOOLS
    assert "hlf_get_benchmark_artifact" in server.REGISTERED_TOOLS
    assert "hlf_evaluate_model_against_profile" in server.REGISTERED_TOOLS
    assert "hlf_verify_formal_ast" in server.REGISTERED_TOOLS
    assert "hlf_verify_gas_budget" in server.REGISTERED_TOOLS
    assert "hlf_instinct_realign" in server.REGISTERED_TOOLS
    assert "hlf_instinct_list" in server.REGISTERED_TOOLS
    assert "hlf://status/model_catalog" in server.REGISTERED_RESOURCES
    assert "hlf://status/model_catalog/{agent_id}" in server.REGISTERED_RESOURCES
    assert "hlf://status/align" in server.REGISTERED_RESOURCES
    assert "hlf://status/formal_verifier" in server.REGISTERED_RESOURCES
    assert "hlf://status/governed_route" in server.REGISTERED_RESOURCES
    assert "hlf://status/governed_route/{agent_id}" in server.REGISTERED_RESOURCES
    assert "hlf://status/profile_capability_catalog" in server.REGISTERED_RESOURCES
    assert "hlf://status/instinct" in server.REGISTERED_RESOURCES
    assert "hlf://status/instinct/{mission_id}" in server.REGISTERED_RESOURCES


def test_align_status_surfaces_normalized_action_semantics() -> None:
    result = server.hlf_align_check(
        payload="This route should be blocked because it contains malware.",
        agent_id="align-agent",
        workload="agent_routing_context",
    )
    resource = json.loads(server.REGISTERED_RESOURCES["hlf://status/align"]())

    assert result["status"] == "ok"
    assert resource["status"] == "ok"
    assert "normalized_actions" in resource["align_status"]
    assert "DROP" in resource["align_status"]["normalized_actions"]
    assert result["verdict"]["action"] in set(resource["align_status"]["normalized_actions"])


def test_formal_verifier_tools_and_resource_surface_proven_constraints() -> None:
    tool_result = server.hlf_verify_gas_budget(task_costs=[100, 200, 300], budget=700)
    resource = json.loads(server.REGISTERED_RESOURCES["hlf://status/formal_verifier"]())

    assert tool_result["status"] == "ok"
    assert tool_result["result"]["status"] in {"proven", "failed"}
    assert resource["status"] == "ok"
    assert resource["formal_verifier_status"]["solver_name"]


def test_instinct_realign_persists_mission_status_in_resource() -> None:
    mission_id = "resource-mission"

    created = server.hlf_instinct_step(
        mission_id=mission_id,
        phase="specify",
        payload={"topic": "restore pillar"},
    )
    realigned = server.hlf_instinct_realign(
        mission_id=mission_id,
        change_type="scope_change",
        change_description="Recovered missing verification edge",
        affected_nodes=["verify"],
    )
    listing = json.loads(server.REGISTERED_RESOURCES["hlf://status/instinct"]())
    mission_resource = json.loads(
        server.REGISTERED_RESOURCES["hlf://status/instinct/{mission_id}"](mission_id)
    )

    assert created["status"] == "ok"
    assert realigned["status"] == "ok"
    assert listing["status"] == "ok"
    assert any(mission["mission_id"] == mission_id for mission in listing["missions"])
    assert mission_resource["status"] == "ok"
    assert mission_resource["mission"]["mission_id"] == mission_id
    assert len(mission_resource["mission"]["realignment_events"]) == 1


def test_model_catalog_status_surfaces_lane_summary_for_tool_and_resource(monkeypatch) -> None:
    monkeypatch.setenv(
        "HLF_REMOTE_MODEL_ENDPOINTS",
        json.dumps(
            [
                {
                    "name": "remote-coder",
                    "endpoint": "https://remote.example.test/v1",
                    "lanes": ["code-generation", "explainer"],
                    "capabilities": ["reasoning", "remote-direct"],
                    "reachable": True,
                }
            ]
        ),
    )

    server.hlf_sync_model_catalog(
        agent_id="status-agent",
        agent_role="coder",
        runtime_status={
            "ollama_available": False,
            "installed_models": [],
            "recommended_model_runnable": False,
            "fallback_model_runnable": False,
        },
        hardware_summary={"cpu_only": False, "gpu_vram_gb": 16.0},
    )

    tool_status = server.hlf_get_model_catalog_status(agent_id="status-agent")
    latest_resource = json.loads(server.REGISTERED_RESOURCES["hlf://status/model_catalog"]())
    agent_resource = json.loads(
        server.REGISTERED_RESOURCES["hlf://status/model_catalog/{agent_id}"]("status-agent")
    )

    assert tool_status["status"] == "ok"
    assert tool_status["catalog_status"]["agent_id"] == "status-agent"
    assert tool_status["catalog_status"]["summary"]["configured_remote_direct_count"] == 1
    assert (
        tool_status["catalog_status"]["agent_lane_summary"]["code-generation"][
            "best_remote_direct"
        ]["name"]
        == "remote-coder"
    )

    assert latest_resource["status"] == "ok"
    assert latest_resource["catalog_status"]["agent_id"] == "status-agent"
    assert agent_resource["catalog_status"]["preferred_lanes"] == [
        "code-generation",
        "verifier",
        "explainer",
    ]


def test_route_governed_request_can_use_remote_direct_catalog_path(monkeypatch) -> None:
    monkeypatch.setenv(
        "HLF_REMOTE_MODEL_ENDPOINTS",
        json.dumps(
            [
                {
                    "name": "remote-coder",
                    "endpoint": "https://remote.example.test/v1",
                    "lanes": ["code-generation", "explainer"],
                    "capabilities": ["reasoning", "remote-direct"],
                    "reachable": True,
                }
            ]
        ),
    )

    catalog = server.hlf_sync_model_catalog(
        agent_id="coder-1",
        agent_role="coder",
        runtime_status={
            "ollama_available": False,
            "installed_models": [],
            "recommended_model_runnable": False,
            "fallback_model_runnable": False,
        },
        hardware_summary={"cpu_only": False, "gpu_vram_gb": 16.0},
    )
    server.hlf_record_benchmark_artifact(
        profile_name="code_pattern_retrieval_english",
        benchmark_scores={"retrieval_quality": 0.81},
        topic="remote-direct-code-routing",
        languages=["en"],
    )
    route = server.hlf_route_governed_request(
        payload="Explain the failing integration behavior and suggest a fix.",
        workload="code_pattern_retrieval",
        agent_id="coder-1",
        agent_role="coder",
        trust_state="trusted",
        runtime_status={
            "ollama_available": False,
            "installed_models": [],
            "recommended_model_runnable": False,
            "fallback_model_runnable": False,
        },
        hardware_summary={"cpu_only": False, "gpu_vram_gb": 16.0},
    )

    assert catalog["catalog"]["summary"]["configured_remote_direct_count"] == 1
    assert route["routing_verdict"]["primary_access_mode"] == "remote-direct"
    assert route["routing_verdict"]["selected_lane"] == "code-generation"
    assert route["missing_evidence_profiles"] == []


def test_route_governed_request_denies_when_required_evidence_is_missing(monkeypatch) -> None:
    monkeypatch.setenv(
        "HLF_REMOTE_MODEL_ENDPOINTS",
        json.dumps(
            [
                {
                    "name": "remote-coder",
                    "endpoint": "https://remote.example.test/v1",
                    "lanes": ["code-generation"],
                    "capabilities": ["reasoning", "remote-direct"],
                    "reachable": True,
                }
            ]
        ),
    )

    server.hlf_sync_model_catalog(
        agent_id="missing-evidence-agent",
        agent_role="coder",
        runtime_status={
            "ollama_available": False,
            "installed_models": [],
            "recommended_model_runnable": False,
            "fallback_model_runnable": False,
        },
        hardware_summary={"cpu_only": False, "gpu_vram_gb": 16.0},
    )
    server._ctx.session_benchmark_artifacts.pop("code_pattern_retrieval_english", None)

    route = server.hlf_route_governed_request(
        payload="Explain the failing integration behavior and suggest a fix.",
        workload="code_pattern_retrieval",
        agent_id="missing-evidence-agent",
        agent_role="coder",
        trust_state="trusted",
        runtime_status={
            "ollama_available": False,
            "installed_models": [],
            "recommended_model_runnable": False,
            "fallback_model_runnable": False,
        },
        hardware_summary={"cpu_only": False, "gpu_vram_gb": 16.0},
    )

    assert route["routing_verdict"]["allowed"] is False
    assert route["routing_verdict"]["decision"] == "deny"
    assert route["routing_verdict"]["governance_mode"] == "evidence_required"
    assert route["missing_evidence_profiles"] == ["code_pattern_retrieval_english"]
    assert any(
        "Required benchmark evidence missing" in item
        for item in route["routing_verdict"]["policy_constraints"]
    )


def test_governed_route_resource_surfaces_latest_trace(monkeypatch) -> None:
    monkeypatch.delenv("HLF_REMOTE_MODEL_ENDPOINTS", raising=False)

    server.hlf_record_benchmark_artifact(
        profile_name="agent_routing_context_multilingual",
        benchmark_scores={"routing_quality": 0.84, "translation_fidelity": 0.9},
        topic="route-resource-context",
        languages=["en", "zh"],
    )
    server.hlf_record_benchmark_artifact(
        profile_name="sidecar_quality_explainer",
        benchmark_scores={"sidecar_quality": 0.91},
        topic="route-resource-sidecar",
        languages=["en"],
    )
    server.hlf_record_benchmark_artifact(
        profile_name="verifier_accuracy_multilingual",
        benchmark_scores={"verifier_accuracy": 0.93},
        topic="route-resource-verifier",
        languages=["en", "zh"],
    )
    server.hlf_sync_model_catalog(
        agent_id="route-resource-agent",
        agent_role="researcher",
        runtime_status={
            "ollama_available": True,
            "installed_models": ["qwen3:8b"],
            "recommended_model_runnable": True,
            "fallback_model_runnable": False,
        },
        hardware_summary={"cpu_only": False, "gpu_vram_gb": 16.0},
    )

    route = server.hlf_route_governed_request(
        payload="Explain the governed routing outcome in English while preserving the multilingual audit path.",
        workload="agent_routing_context",
        multilingual_required=True,
        agent_id="route-resource-agent",
        agent_role="researcher",
        runtime_status={
            "ollama_available": True,
            "installed_models": ["qwen3:8b"],
            "recommended_model_runnable": True,
            "fallback_model_runnable": False,
        },
        hardware_summary={"cpu_only": False, "gpu_vram_gb": 16.0},
    )
    latest_resource = json.loads(server.REGISTERED_RESOURCES["hlf://status/governed_route"]())
    agent_resource = json.loads(
        server.REGISTERED_RESOURCES["hlf://status/governed_route/{agent_id}"](
            "route-resource-agent"
        )
    )

    assert route["route_trace"]["request_context"]["agent_id"] == "route-resource-agent"
    assert route["route_trace"]["policy_basis"]["missing_evidence_profiles"] == []
    assert latest_resource["status"] == "ok"
    assert latest_resource["route_trace"]["operator_summary"]
    assert agent_resource["route_trace"]["request_context"]["agent_id"] == "route-resource-agent"


def test_query_profile_capabilities_surfaces_governed_matches_and_active_profiles() -> None:
    server.hlf_record_benchmark_artifact(
        profile_name="translation_memory_multilingual",
        benchmark_scores={
            "translation_fidelity": 0.91,
            "retrieval_quality": 0.81,
            "routing_quality": 0.76,
        },
        topic="profile-catalog-query",
        languages=["en", "zh"],
    )
    server.hlf_recommend_embedding_profile(
        workload="translation_memory",
        multilingual_required=True,
        agent_id="profile-query-agent",
        persist=True,
    )

    result = server.hlf_query_profile_capabilities(
        capability="embedding",
        language="zh",
        evidence_only=True,
    )

    assert result["status"] == "ok"
    assert result["summary"]["qualification_profile_count"] >= 1
    assert any(
        entry["profile_name"] == "translation_memory_multilingual"
        and entry["evidence_tier"] == "launch-qualified"
        for entry in result["qualification_profiles"]
    )
    active_entry = next(
        entry for entry in result["active_profiles"] if entry["agent_id"] == "profile-query-agent"
    )
    assert active_entry["selected_lane"] == "retrieval"
    assert "translation_memory_multilingual" in active_entry["governed_profile_candidates"]
    assert "embedding" in active_entry["governed_capabilities"]
    assert "translation_memory_multilingual" in active_entry["candidate_evidence"]


def test_profile_capability_catalog_resource_surfaces_latest_governed_catalog() -> None:
    resource = json.loads(server.REGISTERED_RESOURCES["hlf://status/profile_capability_catalog"]())

    assert resource["status"] == "ok"
    assert resource["summary"]["qualification_profile_count"] >= 1
    assert any(
        entry["profile_name"] == "translation_memory_multilingual"
        for entry in resource["qualification_profiles"]
    )
    assert any(entry["agent_id"] == "profile-query-agent" for entry in resource["active_profiles"])


def test_route_governed_request_requires_launch_qualified_model_for_multilingual_lane(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "HLF_REMOTE_MODEL_ENDPOINTS",
        json.dumps(
            [
                {
                    "name": "remote-english-retriever",
                    "endpoint": "https://remote.example.test/v1",
                    "lanes": ["retrieval"],
                    "capabilities": ["embedding", "semantic-recall", "remote-direct"],
                    "supported_languages": ["en"],
                    "reachable": True,
                }
            ]
        ),
    )

    server.hlf_sync_model_catalog(
        agent_id="multilingual-agent",
        agent_role="researcher",
        runtime_status={
            "ollama_available": True,
            "installed_models": ["nomic-embed-text-v2-moe"],
            "recommended_model_runnable": True,
            "fallback_model_runnable": False,
        },
        hardware_summary={"cpu_only": False, "gpu_vram_gb": 16.0},
    )

    route = server.hlf_route_governed_request(
        payload="分析 /security/seccomp.json 并且返回简写漏洞结论。",
        workload="translation_memory",
        multilingual_required=True,
        agent_id="multilingual-agent",
        agent_role="researcher",
        runtime_status={
            "ollama_available": True,
            "installed_models": ["nomic-embed-text-v2-moe"],
            "recommended_model_runnable": True,
            "fallback_model_runnable": False,
        },
        hardware_summary={"cpu_only": False, "gpu_vram_gb": 16.0},
        benchmark_scores={
            "translation_fidelity": 0.93,
            "retrieval_quality": 0.84,
            "routing_quality": 0.79,
        },
    )

    assert route["qualification_profile"] == "translation_memory_multilingual"
    assert route["primary_qualification"]["resolved_tier"] == "advisory-only"
    assert route["fallback_qualification"]["resolved_tier"] == "launch-qualified"
    assert route["routing_verdict"]["primary_model"] == "nomic-embed-text-v2-moe"
    assert route["routing_verdict"]["primary_access_mode"] == "local-via-ollama"
    assert route["routing_verdict"]["review_required"] is True


def test_route_governed_request_uses_persisted_benchmark_artifact_when_scores_not_passed(
    monkeypatch,
) -> None:
    monkeypatch.delenv("HLF_REMOTE_MODEL_ENDPOINTS", raising=False)

    server.hlf_routing_context_benchmark(
        domains=["security_audit", "hello_world"],
        languages=["en", "zh"],
        top_k=2,
        topic="hlf_agent_routing_benchmark_persisted",
    )
    server.hlf_sync_model_catalog(
        agent_id="routing-artifact-agent",
        agent_role="researcher",
        runtime_status={
            "ollama_available": True,
            "installed_models": ["nomic-embed-text-v2-moe"],
            "recommended_model_runnable": True,
            "fallback_model_runnable": False,
        },
        hardware_summary={"cpu_only": False, "gpu_vram_gb": 16.0},
    )

    route = server.hlf_route_governed_request(
        payload="分析 /security/seccomp.json 并且返回简写漏洞结论。",
        workload="agent_routing_context",
        multilingual_required=True,
        agent_id="routing-artifact-agent",
        agent_role="researcher",
        runtime_status={
            "ollama_available": True,
            "installed_models": ["nomic-embed-text-v2-moe"],
            "recommended_model_runnable": True,
            "fallback_model_runnable": False,
        },
        hardware_summary={"cpu_only": False, "gpu_vram_gb": 16.0},
    )

    assert route["qualification_profile"] == "agent_routing_context_multilingual"
    assert route["benchmark_scores"]
    assert route["benchmark_scores"]["routing_quality"] > 0.0
    assert route["primary_qualification"]["resolved_tier"] in {
        "baseline-qualified",
        "launch-qualified",
        "promotion-qualified",
        "advisory-only",
    }


def test_benchmark_artifact_tools_roundtrip() -> None:
    recorded = server.hlf_record_benchmark_artifact(
        profile_name="verifier_accuracy_multilingual",
        benchmark_scores={"verifier_accuracy": 0.92},
        topic="frontdoor-artifact-roundtrip",
        languages=["en", "zh"],
        details={"suite": "frontdoor"},
    )
    fetched = server.hlf_get_benchmark_artifact("verifier_accuracy_multilingual")

    assert recorded["status"] == "ok"
    assert recorded["artifact"]["profile_name"] == "verifier_accuracy_multilingual"
    assert recorded["artifact"]["memory_evidence"]["source_class"] == "benchmark_artifact"
    assert fetched["status"] == "ok"
    assert fetched["artifact"]["benchmark_scores"]["verifier_accuracy"] == 0.92
    assert fetched["artifact"]["memory_evidence"]["provenance_grade"] == "evidence-backed"


def test_route_governed_request_uses_sidecar_and_verifier_artifacts_for_explainer_lane(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "HLF_REMOTE_MODEL_ENDPOINTS",
        json.dumps(
            [
                {
                    "name": "remote-explainer-lite",
                    "endpoint": "https://remote.example.test/explainer",
                    "lanes": ["explainer"],
                    "capabilities": ["remote-direct"],
                    "supported_languages": ["en"],
                    "reachable": True,
                }
            ]
        ),
    )

    server.hlf_record_benchmark_artifact(
        profile_name="sidecar_quality_explainer",
        benchmark_scores={"sidecar_quality": 0.91},
        topic="explainer-sidecar-routing",
        languages=["en"],
    )
    server.hlf_record_benchmark_artifact(
        profile_name="verifier_accuracy_multilingual",
        benchmark_scores={"verifier_accuracy": 0.93},
        topic="explainer-verifier-routing",
        languages=["en", "fr", "es", "ar", "zh"],
    )
    server.hlf_record_benchmark_artifact(
        profile_name="agent_routing_context_multilingual",
        benchmark_scores={"routing_quality": 0.84, "translation_fidelity": 0.9},
        topic="explainer-routing-context",
        languages=["en", "zh"],
    )
    server.hlf_sync_model_catalog(
        agent_id="explainer-artifact-agent",
        agent_role="researcher",
        runtime_status={
            "ollama_available": True,
            "installed_models": ["qwen3:8b"],
            "recommended_model_runnable": True,
            "fallback_model_runnable": False,
        },
        hardware_summary={"cpu_only": False, "gpu_vram_gb": 16.0},
    )

    route = server.hlf_route_governed_request(
        payload="Explain the governed routing outcome in English while preserving the multilingual audit path.",
        workload="agent_routing_context",
        multilingual_required=True,
        agent_id="explainer-artifact-agent",
        agent_role="researcher",
        runtime_status={
            "ollama_available": True,
            "installed_models": ["qwen3:8b"],
            "recommended_model_runnable": True,
            "fallback_model_runnable": False,
        },
        hardware_summary={"cpu_only": False, "gpu_vram_gb": 16.0},
    )

    assert route["status"] == "ok"
    assert set(route["applied_qualification_profiles"]) >= {
        "agent_routing_context_multilingual",
        "sidecar_quality_explainer",
        "verifier_accuracy_multilingual",
    }
    assert (
        route["benchmark_artifacts"]["sidecar_quality_explainer"]["profile_name"]
        == "sidecar_quality_explainer"
    )
    assert (
        route["benchmark_artifacts"]["verifier_accuracy_multilingual"]["profile_name"]
        == "verifier_accuracy_multilingual"
    )
    assert route["routing_verdict"]["primary_model"] == "qwen3:8b"
    assert (
        route["selected_primary_profile_evaluations"]["sidecar_quality_explainer"]["resolved_tier"]
        == "launch-qualified"
    )
    assert (
        route["selected_primary_profile_evaluations"]["verifier_accuracy_multilingual"][
            "resolved_tier"
        ]
        == "launch-qualified"
    )
