import json
from pathlib import Path

from hlf_mcp import server, server_resources


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
    assert "hlf_dream_cycle_run" in server.REGISTERED_TOOLS
    assert "hlf_dream_findings_list" in server.REGISTERED_TOOLS
    assert "hlf_dream_findings_get" in server.REGISTERED_TOOLS
    assert "hlf_media_evidence_list" in server.REGISTERED_TOOLS
    assert "hlf_media_evidence_get" in server.REGISTERED_TOOLS
    assert "hlf_dream_proposal_create" in server.REGISTERED_TOOLS
    assert "hlf_dream_proposals_list" in server.REGISTERED_TOOLS
    assert "hlf_dream_proposals_get" in server.REGISTERED_TOOLS
    assert "hlf_memory_govern" in server.REGISTERED_TOOLS
    assert "hlf://status/model_catalog" in server.REGISTERED_RESOURCES
    assert "hlf://status/model_catalog/{agent_id}" in server.REGISTERED_RESOURCES
    assert "hlf://status/align" in server.REGISTERED_RESOURCES
    assert "hlf://status/formal_verifier" in server.REGISTERED_RESOURCES
    assert "hlf://status/governed_route" in server.REGISTERED_RESOURCES
    assert "hlf://status/governed_route/{agent_id}" in server.REGISTERED_RESOURCES
    assert "hlf://status/profile_capability_catalog" in server.REGISTERED_RESOURCES
    assert "hlf://status/instinct" in server.REGISTERED_RESOURCES
    assert "hlf://status/instinct/{mission_id}" in server.REGISTERED_RESOURCES
    assert "hlf://status/provenance_contract" in server.REGISTERED_RESOURCES
    assert "hlf://status/memory_governance" in server.REGISTERED_RESOURCES
    assert "hlf://status/dream-cycle" in server.REGISTERED_RESOURCES
    assert "hlf://dream/findings" in server.REGISTERED_RESOURCES
    assert "hlf://dream/findings/{finding_id}" in server.REGISTERED_RESOURCES
    assert "hlf://media/evidence" in server.REGISTERED_RESOURCES
    assert "hlf://media/evidence/{artifact_id}" in server.REGISTERED_RESOURCES
    assert "hlf://dream/proposals" in server.REGISTERED_RESOURCES
    assert "hlf://dream/proposals/{proposal_id}" in server.REGISTERED_RESOURCES
    assert "hlf://status/multimodal_contracts" in server.REGISTERED_RESOURCES
    assert "hlf://status/fixture_gallery" in server.REGISTERED_RESOURCES
    assert "hlf://reports/fixture_gallery" in server.REGISTERED_RESOURCES


def test_fixture_gallery_status_resource_reports_packaged_fixture_health() -> None:
    resource = json.loads(server.REGISTERED_RESOURCES["hlf://status/fixture_gallery"]())

    assert resource["status"] == "ok"
    assert resource["gallery"]["surface_type"] == "generated_report"
    assert resource["gallery"]["grounded_in_packaged_truth"] is True
    assert resource["gallery"]["summary"]["fixture_count"] >= 11
    assert resource["gallery"]["summary"]["compile_failed_count"] == 0
    assert resource["gallery"]["summary"]["bytecode_failed_count"] == 0
    assert "hlf://reports/fixture_gallery" in resource["gallery"]["taxonomy"]["generated_reports"]
    assert any(entry["name"] == "hello_world" for entry in resource["gallery"]["entries"])


def test_fixture_gallery_markdown_report_matches_structured_status_surface() -> None:
    resource = json.loads(server.REGISTERED_RESOURCES["hlf://status/fixture_gallery"]())
    report = server.REGISTERED_RESOURCES["hlf://reports/fixture_gallery"]()

    assert report.startswith("# HLF Fixture Gallery Report\n")
    assert (
        "Generated from packaged fixtures using the current packaged compiler and bytecode encoder."
        in report
    )
    assert f"- Fixture count: {resource['gallery']['summary']['fixture_count']}" in report
    assert "| hello_world |" in report
    assert "- Generated report: hlf://reports/fixture_gallery" in report


def test_fixture_gallery_status_reports_missing_directory_when_candidates_are_invalid(
    monkeypatch, tmp_path: Path
) -> None:
    invalid_fixture_file = tmp_path / "fixtures"
    invalid_fixture_file.write_text("not a directory", encoding="utf-8")
    monkeypatch.setattr(server_resources, "_FIXTURE_DIR_CANDIDATES", [invalid_fixture_file])

    resource = json.loads(
        server_resources.render_resource_uri(None, "hlf://status/fixture_gallery")
    )

    assert resource["status"] == "error"
    assert resource["error"] == "fixtures_directory_missing"
    assert resource["gallery"]["fixture_dir"] is None


def test_host_functions_resource_preserves_missing_governance_error_signal(monkeypatch) -> None:
    monkeypatch.setattr(
        server_resources,
        "_read_governance_file",
        lambda filename: json.dumps(
            {
                "error": "governance_file_not_found",
                "file": filename,
                "hint": "install from source",
            }
        ),
    )

    resource = json.loads(server_resources.render_resource_uri(None, "hlf://host_functions"))

    assert resource["functions"] == []
    assert resource["status"] == "error"
    assert resource["error"] == "governance_file_not_found"
    assert resource["details"]["file"] == "host_functions.json"


def test_memory_governance_tool_returns_structured_error_for_missing_identifier() -> None:
    result = server.hlf_memory_govern(action="revoke")

    assert result["status"] == "error"
    assert result["error"] == "Either fact_id or sha256 must be provided."
    assert result["action"] == "revoke"


def test_memory_governance_tool_returns_structured_error_for_invalid_action() -> None:
    stored = server.hlf_memory_store(
        content="Invalid memory-govern action regression",
        topic="memory-governance-invalid-action",
        provenance="test_frontdoor",
        confidence=0.87,
    )

    result = server.hlf_memory_govern(action="invalid", fact_id=stored["id"])

    assert result["status"] == "error"
    assert "unsupported governance action" in result["error"].lower()
    assert result["fact_id"] == stored["id"]


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


def test_provenance_contract_resource_surfaces_memory_and_governance_summary() -> None:
    stored = server.hlf_memory_store(
        content="HLF provenance contract regression fact",
        topic="provenance-contract-resource",
        provenance="test_frontdoor",
        confidence=0.93,
        tags=["provenance-contract", "operator-regression"],
    )
    superseded = server._ctx.memory_store.store(
        "Superseded provenance contract fact",
        topic="provenance-contract-resource",
        provenance="test_frontdoor",
        metadata={"governed_evidence": {"operator_summary": "Superseded fact"}},
    )
    server._ctx.memory_store.store(
        "Superseding provenance contract fact",
        topic="provenance-contract-resource",
        provenance="test_frontdoor",
        supersedes_sha256=superseded["sha256"],
        metadata={"governed_evidence": {"operator_summary": "Superseding fact"}},
    )
    server._ctx.memory_store.store(
        "Revoked provenance contract fact",
        topic="provenance-contract-resource",
        provenance="test_frontdoor",
        metadata={"governed_evidence": {"revoked": True, "operator_summary": "Revoked fact"}},
    )
    server._ctx.memory_store.store(
        "Tombstoned provenance contract fact",
        topic="provenance-contract-resource",
        provenance="test_frontdoor",
        metadata={"governed_evidence": {"tombstoned": True, "operator_summary": "Tombstoned fact"}},
    )

    resource = json.loads(server.REGISTERED_RESOURCES["hlf://status/provenance_contract"]())

    assert stored["stored"] is True
    assert resource["status"] == "ok"
    assert resource["provenance_contract"]["contract_version"] == "1.0"
    assert resource["provenance_contract"]["summary"]["memory_fact_count"] >= 1
    assert resource["provenance_contract"]["summary"]["governance_event_count"] >= 1
    assert "fact" in resource["provenance_contract"]["memory_entry_kind_counts"]
    assert resource["provenance_contract"]["memory_state_counts"]["revoked"] >= 1
    assert resource["provenance_contract"]["memory_state_counts"]["tombstoned"] >= 1
    assert resource["provenance_contract"]["memory_state_counts"]["superseded"] >= 1
    assert (
        resource["provenance_contract"]["pointer_chain_summary"]["superseding_pointer_count"] >= 1
    )
    assert any(
        pointer["pointer"].startswith("&")
        for pointer in resource["provenance_contract"]["pointer_chain_summary"]["recent_pointers"]
    )
    assert any(
        fact["topic"] == "provenance-contract-resource"
        for fact in resource["provenance_contract"]["recent_memory_facts"]
    )


def test_memory_governance_tool_and_resource_surface_governed_intervention() -> None:
    stored = server.hlf_memory_store(
        content="Govern this memory fact",
        topic="memory-governance-resource",
        provenance="test_frontdoor",
        confidence=0.88,
    )

    governed = server.hlf_memory_govern(
        action="revoke",
        fact_id=stored["id"],
        operator_summary="Revoked during regression test",
        reason="governance test",
        operator_id="alice",
        operator_display_name="Alice Example",
        operator_channel="pytest.fastmcp_frontdoor",
    )
    resource = json.loads(server.REGISTERED_RESOURCES["hlf://status/memory_governance"]())

    assert governed["status"] == "ok"
    assert governed["fact"]["evidence"]["revoked"] is True
    assert governed["fact"]["governance_status"] == "revoked"
    assert resource["status"] == "ok"
    assert resource["memory_governance"]["memory_state_counts"]["revoked"] >= 1
    assert any(
        target["topic"] == "memory-governance-resource"
        for target in resource["memory_governance"]["recent_targets"]
    )
    assert any(
        target["operator_identity"]["operator_id"] == "alice"
        for target in resource["memory_governance"]["recent_targets"]
        if target["topic"] == "memory-governance-resource"
    )
    assert any(
        event["kind"] == "memory_governance"
        for event in resource["memory_governance"]["recent_interventions"]
    )
    assert any(
        event["operator_identity"]["operator_id"] == "alice"
        for event in resource["memory_governance"]["recent_interventions"]
    )


def test_memory_governance_resource_orders_multiple_interventions_for_same_fact() -> None:
    stored = server.hlf_memory_store(
        content="Govern this sequence fact",
        topic="memory-governance-sequence",
        provenance="test_frontdoor",
        confidence=0.9,
    )

    server.hlf_memory_govern(
        action="revoke",
        fact_id=stored["id"],
        operator_summary="First revoke",
        reason="sequence_revoke",
        operator_id="alice",
        operator_display_name="Alice Example",
        operator_channel="pytest.fastmcp_frontdoor",
    )
    server.hlf_memory_govern(
        action="tombstone",
        fact_id=stored["id"],
        operator_summary="Second tombstone",
        reason="sequence_tombstone",
        operator_id="alice",
        operator_display_name="Alice Example",
        operator_channel="pytest.fastmcp_frontdoor",
    )
    server.hlf_memory_govern(
        action="reinstate",
        fact_id=stored["id"],
        operator_summary="Third reinstate",
        reason="sequence_reinstate",
        operator_id="alice",
        operator_display_name="Alice Example",
        operator_channel="pytest.fastmcp_frontdoor",
    )

    resource = json.loads(server.REGISTERED_RESOURCES["hlf://status/memory_governance"]())
    events = [
        event
        for event in resource["memory_governance"]["recent_interventions"]
        if event["subject_id"] == str(stored["id"])
    ]

    assert [event["action"] for event in events[:3]] == [
        "memory_reinstate",
        "memory_tombstone",
        "memory_revoke",
    ]
    assert events[0]["operator_identity"] == {
        "operator_id": "alice",
        "operator_display_name": "Alice Example",
        "operator_channel": "pytest.fastmcp_frontdoor",
    }
    assert events[0]["pointer"].startswith("&memory-governance-sequence-")
    assert events[0]["reason"] == "sequence_reinstate"


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


def test_profile_capability_catalog_includes_multimodal_host_function_requirements() -> None:
    result = server.hlf_query_profile_capabilities(lane="multimodal")

    assert result["status"] == "ok"
    multimodal_entry = next(
        entry
        for entry in result["qualification_profiles"]
        if entry["profile_name"] == "multimodal_vision_ocr_governed"
    )
    assert "OCR_EXTRACT" in multimodal_entry["required_host_functions"]
    assert "IMAGE_SUMMARIZE" in multimodal_entry["required_host_functions"]


def test_multimodal_contract_resource_surfaces_host_function_bindings() -> None:
    resource = json.loads(server.REGISTERED_RESOURCES["hlf://status/multimodal_contracts"]())

    assert resource["status"] == "ok"
    assert resource["profile_count"] >= 3
    vision_entry = next(
        entry
        for entry in resource["multimodal_profiles"]
        if entry["profile_name"] == "multimodal_vision_ocr_governed"
    )
    assert vision_entry["contract_ready"] is True
    assert any(
        contract["name"] == "OCR_EXTRACT" for contract in vision_entry["host_function_contracts"]
    )


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
