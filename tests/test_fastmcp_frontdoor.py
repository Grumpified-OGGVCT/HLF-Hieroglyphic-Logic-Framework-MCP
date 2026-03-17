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
    source = "[HLF-v3]\nΔ [INTENT] goal=\"analyze\" target=\"/var/log/app.log\"\nΩ\n"

    result = server.hlf_translate_to_english(source, language="fr")

    assert result["status"] == "ok"
    assert result["language"] == "fr"
    assert "summary_en" in result


def test_hlf_decompile_ast_accepts_localized_output() -> None:
    source = "[HLF-v3]\nΔ [INTENT] goal=\"analyze\" target=\"/var/log/app.log\"\nΩ\n"

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