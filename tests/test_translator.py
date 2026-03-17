from __future__ import annotations

from hlf_mcp.hlf.translator import Tone, detect_tone, english_to_hlf, hlf_source_to_english, hlf_to_english


def test_detect_tone_returns_matching_cue() -> None:
    assert detect_tone("this is urgent and must ship now") is Tone.URGENT
    assert detect_tone("maybe we should investigate this") is Tone.CURIOUS
    assert detect_tone("plain neutral sentence") is Tone.NEUTRAL


def test_english_to_hlf_emits_header_actions_and_terminator() -> None:
    source = english_to_hlf("Analyze /var/log/app.log in read-only mode.")

    assert source.startswith("[HLF-v3]\n")
    assert '# Generated from English (tone: neutral)' in source
    assert 'Δ [INTENT] goal="analyze" target="/var/log/app.log"' in source
    assert 'Ж [CONSTRAINT] mode="ro"' in source
    assert source.rstrip().endswith("Ω")


def test_english_to_hlf_supports_delegate_memory_and_recall_patterns() -> None:
    delegated = english_to_hlf('delegate this task to "builder"')
    remembered = english_to_hlf("remember this deployment context for later")
    recalled = english_to_hlf("recall the last deployment context")

    assert '[DELEGATE]' in delegated
    assert 'MEMORY [context]' in remembered
    assert 'RECALL [context]' in recalled


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
    source = "[HLF-v3]\nSET target = \"/app\"\nRESULT 0 \"ok\"\nΩ\n"
    result = hlf_source_to_english(source)

    lowered = result.lower()
    assert "program with" in lowered or "set" in lowered or "result" in lowered


def test_hlf_source_to_english_reports_translation_failure_for_bad_source() -> None:
    result = hlf_source_to_english("not valid hlf")
    assert result.startswith("Translation failed:")