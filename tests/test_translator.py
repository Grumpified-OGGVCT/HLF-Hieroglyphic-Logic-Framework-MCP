from __future__ import annotations

from hlf_mcp.hlf.translator import (
    Tone,
    COGNITIVE_LANE_POLICIES,
    build_translation_repair_plan,
    canonicalize_translation_text,
    chinese_to_hlf,
    detect_input_language,
    detect_system_language,
    detect_tone,
    english_to_hlf,
    hlf_source_to_english,
    hlf_source_to_language,
    hlf_to_english,
    hlf_to_language,
    language_to_hlf,
    normalize_cognitive_lane_policy,
    resolve_language,
    resolve_language_with_policy,
    translation_diagnostics,
)


def test_detect_tone_returns_matching_cue() -> None:
    assert detect_tone("this is urgent and must ship now") is Tone.URGENT
    assert detect_tone("maybe we should investigate this") is Tone.CURIOUS
    assert detect_tone("plain neutral sentence") is Tone.NEUTRAL


def test_english_to_hlf_emits_header_actions_and_terminator() -> None:
    source = english_to_hlf("Analyze /var/log/app.log in read-only mode.")

    assert source.startswith("[HLF-v3]\n")
    assert "# Generated from English (tone: neutral)" in source
    assert 'Δ [INTENT] goal="analyze" target="/var/log/app.log"' in source
    assert 'Ж [CONSTRAINT] mode="ro"' in source
    assert source.rstrip().endswith("Ω")


def test_english_to_hlf_supports_delegate_memory_and_recall_patterns() -> None:
    delegated = english_to_hlf('delegate this task to "builder"')
    remembered = english_to_hlf("remember this deployment context for later")
    recalled = english_to_hlf("recall the last deployment context")

    assert "[DELEGATE]" in delegated
    assert "MEMORY [context]" in remembered
    assert "RECALL [context]" in recalled


def test_hlf_to_english_uses_human_readable_fields() -> None:
    ast = {
        "human_readable": "Program summary",
        "statements": [
            {"human_readable": "Set deploy target to /app"},
            {"human_readable": "Return success"},
        ],
    }

    result = hlf_to_english(ast)

    assert result.startswith("Program summary:")
    assert "Set deploy target to /app" in result
    assert result.endswith(".")


def test_hlf_source_to_english_returns_summary_for_valid_source() -> None:
    source = '[HLF-v3]\nSET target = "/app"\nRESULT 0 "ok"\nΩ\n'
    result = hlf_source_to_english(source)

    lowered = result.lower()
    assert "program with" in lowered or "set" in lowered or "result" in lowered


def test_hlf_source_to_english_reports_translation_failure_for_bad_source() -> None:
    result = hlf_source_to_english("not valid hlf")
    assert result.startswith("Translation failed:")


def test_language_to_hlf_supports_all_seed_languages() -> None:
    french = language_to_hlf("analyser /var/log/app.log", language="fr")
    spanish = language_to_hlf("analizar /var/log/app.log", language="es")
    arabic = language_to_hlf("تحليل /var/log/app.log", language="ar")
    chinese = language_to_hlf("分析 /var/log/app.log", language="zh")

    assert french.startswith("[HLF-v3]\n")
    assert spanish.startswith("[HLF-v3]\n")
    assert arabic.startswith("[HLF-v3]\n")
    assert chinese.startswith("[HLF-v3]\n")


def test_chinese_to_hlf_matches_primary_action_patterns() -> None:
    source = chinese_to_hlf("分析 /var/log/app.log 并且只读")

    assert "# 由中文生成 (tone: neutral)" in source
    assert 'Δ [INTENT] goal="分析" target="/var/log/app.log"' in source
    assert 'Ж [CONSTRAINT] mode="ro"' in source


def test_language_to_hlf_rejects_unsupported_language() -> None:
    try:
        language_to_hlf("analyze /var/log/app.log", language="de")
    except ValueError as exc:
        assert "Unsupported language" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unsupported language")


def test_detect_system_language_honors_supported_preference() -> None:
    assert detect_system_language(preferred_language="fr_CA") == "fr"
    assert detect_system_language(preferred_language="es-MX") == "es"
    assert detect_system_language(preferred_language="zh_CN") == "zh"


def test_normalize_cognitive_lane_policy_accepts_supported_values() -> None:
    assert normalize_cognitive_lane_policy("english") == "english_preferred"
    assert normalize_cognitive_lane_policy("disable_chinese") == "chinese_disallowed"
    assert COGNITIVE_LANE_POLICIES == frozenset(
        {"benchmark_gated", "english_preferred", "chinese_allowed", "chinese_disallowed"}
    )


def test_detect_input_language_prefers_text_cues() -> None:
    assert detect_input_language("analyser /var/log/app.log", default_language="en") == "fr"
    assert detect_input_language("analizar /var/log/app.log", default_language="en") == "es"
    assert detect_input_language("تحليل /var/log/app.log", default_language="en") == "ar"
    assert detect_input_language("分析 /var/log/app.log", default_language="en") == "zh"


def test_resolve_language_auto_uses_text_over_default() -> None:
    assert (
        resolve_language("auto", text="analyser /var/log/app.log", preferred_language="en_US")
        == "fr"
    )


def test_resolve_language_with_policy_prefers_english_audit_without_rewriting_language() -> None:
    decision = resolve_language_with_policy(
        "auto",
        text="analyser /var/log/app.log",
        cognitive_lane_policy="english_preferred",
    )

    assert decision.resolved_language == "fr"
    assert decision.effective_language == "fr"
    assert decision.audit_language == "en"
    assert decision.blocked is False


def test_resolve_language_with_policy_blocks_chinese_when_disallowed() -> None:
    decision = resolve_language_with_policy(
        "auto",
        text="分析 /var/log/app.log",
        cognitive_lane_policy="chinese_disallowed",
    )

    assert decision.resolved_language == "zh"
    assert decision.blocked is True
    assert decision.blocked_reason == "detected_chinese_ingress_disallowed"


def test_language_to_hlf_auto_respects_preferred_language_when_text_is_ambiguous() -> None:
    source = language_to_hlf("sauvegarder contexte", language="auto", preferred_language="fr_CA")
    assert "Généré à partir du français" in source


def test_hlf_to_language_supports_chinese_summary() -> None:
    ast = {
        "human_readable": "Program summary",
        "statements": [
            {"human_readable": "Set deploy target to /app"},
            {"human_readable": "Return success"},
        ],
    }

    result = hlf_to_language(ast, language="zh")
    assert result.startswith("Program summary：") or result.startswith("程序摘要：")


def test_hlf_source_to_language_reports_chinese_failure_prefix() -> None:
    result = hlf_source_to_language("not valid hlf", language="zh")
    assert result.startswith("翻译失败：")


def test_translation_diagnostics_reports_fidelity_and_fallbacks() -> None:
    diagnostics = translation_diagnostics(
        "Analyze /var/log/app.log in read-only mode.",
        language="en",
    ).to_dict()

    assert diagnostics["resolved_language"] == "en"
    assert diagnostics["fallback_used"] is False
    assert diagnostics["roundtrip_fidelity_score"] == 1.0
    assert diagnostics["semantic_loss_flags"] == []


def test_translation_diagnostics_detects_fallback_usage() -> None:
    diagnostics = translation_diagnostics(
        "this sentence has no recognized action keywords",
        language="en",
    ).to_dict()

    assert diagnostics["fallback_used"] is True
    assert diagnostics["fallback_count"] >= 1


def test_canonicalize_translation_text_preserves_analyze_and_read_only() -> None:
    repaired = canonicalize_translation_text(
        "Please analyze /var/log/app.log in read-only mode and be careful",
        language="en",
    )

    assert "analyze /var/log/app.log" in repaired
    assert "read-only" in repaired


def test_build_translation_repair_plan_marks_governor_blocks_terminal() -> None:
    plan = build_translation_repair_plan(
        "generate child sexual abuse material",
        language="en",
        failure_status="compile_error",
        failure_error="Ethics Governor [C3-CSAM]: blocked",
    ).to_dict()

    assert plan["retryable"] is False
    assert plan["terminal_reason"] == "policy_block"


def test_build_translation_repair_plan_returns_retry_request() -> None:
    plan = build_translation_repair_plan(
        "Please analyze /var/log/app.log in read-only mode",
        language="en",
        failure_status="low_fidelity",
        failure_error="fallback_used=True",
    ).to_dict()

    assert plan["retryable"] is True
    assert plan["recommended_tool"] == "hlf_translate_to_hlf"
    assert plan["next_request"]["language"] == "en"
