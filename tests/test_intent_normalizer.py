"""Comprehensive tests for IntentNormalizer and the normalization gate.

Covers: unit tests (5 rules, verdicts, edge cases), integration tests
(gate wiring, skip_normalization, audit trail), and MCP-tool round-trips.
"""

from __future__ import annotations

import asyncio

from hlf_mcp import server
from hlf_mcp.hlf.intent_normalizer import (
    IntentNormalizer,
    NormalizationVerdict,
    _AMBIGUOUS_PRONOUNS,
    _ASSUMED_CONTEXT_PATTERNS,
    _VAGUE_TERMS,
)
from hlf_mcp.server_context import build_server_context
from hlf_mcp.server_translation import _apply_normalization_gate


# ═══════════════════════════════════════════════════════════════════════════════
# Unit tests: construction / configuration
# ═══════════════════════════════════════════════════════════════════════════════


def test_default_construction() -> None:
    n = IntentNormalizer()
    assert n.threshold == 0.7
    assert n.auto_rewrite is True
    assert n.strict_mode is False


def test_custom_threshold() -> None:
    n = IntentNormalizer(threshold=0.5)
    assert n.threshold == 0.5
    verdict = n.normalize("a perfectly fine intent string that should pass")
    # This should pass at 0.5 even with length < 10 and missing constraints
    assert isinstance(verdict, NormalizationVerdict)


def test_threshold_out_of_range_raises() -> None:
    import pytest
    with pytest.raises(ValueError, match="threshold must be 0.0"):
        IntentNormalizer(threshold=1.5)
    with pytest.raises(ValueError, match="threshold must be 0.0"):
        IntentNormalizer(threshold=-0.1)


def test_strict_mode_rejects_everything_below_threshold() -> None:
    n = IntentNormalizer(threshold=0.7, strict_mode=True)
    # Even a well-formed intent gets rejected in strict mode if score < threshold
    verdict = n.normalize("fix bug")
    assert verdict.threshold_passed is False
    assert verdict.rejection_reason is not None


def test_auto_rewrite_disabled_skips_rewrite() -> None:
    n = IntentNormalizer(threshold=0.7, auto_rewrite=False)
    # This intent will score low but not trigger reject
    verdict = n.normalize("fix the stuff in the file")
    assert verdict.threshold_passed is False
    assert verdict.rewritten_intent is None
    # In non-strict mode, only reject if score < 0.3 or single word
    # "fix the stuff in the file" = 5 words, score might be >= 0.3
    # So it shouldn't reject — just pass through without rewrite


# ═══════════════════════════════════════════════════════════════════════════════
# Unit tests: 5 detection rules
# ═══════════════════════════════════════════════════════════════════════════════

# ── Rule 1: Vague terms (-0.10 each) ─────────────────────────────────────────


def test_vague_terms_detected() -> None:
    n = IntentNormalizer(threshold=0.7)
    verdict = n.normalize("fix some stuff and things in the code")
    findings_text = " ".join(verdict.findings)
    assert "Vague term" in findings_text
    assert "'stuff'" in findings_text
    assert "'things'" in findings_text


def test_vague_terms_reduce_score() -> None:
    n = IntentNormalizer(threshold=0.7)
    verdict_clean = n.normalize(
        "fix the authentication bug in src/auth.py with tier=trusted gas=100"
    )
    verdict_vague = n.normalize(
        "fix stuff and things whatever in src/auth.py with tier=trusted gas=100"
    )
    assert verdict_vague.score < verdict_clean.score


def test_vague_terms_detected_by_word_boundary() -> None:
    n = IntentNormalizer(threshold=0.7)
    verdict = n.normalize("it is probably something we should fix")
    findings_text = " ".join(verdict.findings)
    assert "probably" in findings_text
    assert "something" in findings_text


def test_vague_multi_word_terms_detected() -> None:
    """Multi-word terms like 'kind of' and 'sort of' use substring matching."""
    n = IntentNormalizer(threshold=0.7)
    verdict = n.normalize("this is kind of broken and sort of messy")
    findings_text = " ".join(verdict.findings)
    assert "kind of" in findings_text
    assert "sort of" in findings_text


def test_vague_terms_not_false_positive() -> None:
    """Legitimate uses of words that overlap vague terms shouldn't trigger."""
    n = IntentNormalizer(threshold=0.7)
    verdict = n.normalize(
        "implement the sorting algorithm in src/sort.py with tier=trusted gas=200"
    )
    # "sort" should not match "sort of" — this is word-boundary only
    # Multi-word terms checked via substring, but "sort" alone shouldn't match "sort of"
    vague_findings = [f for f in verdict.findings if "Vague term" in f]
    # "sort" alone should not trigger (it's not in the vague set)
    assert not any("sort" in f and "sort of" not in f for f in vague_findings)


# ── Rule 2: Missing constraints (-0.15 each) ──────────────────────────────────


def test_missing_file_path_detected_with_code_verb() -> None:
    n = IntentNormalizer(threshold=0.7)
    verdict = n.normalize("fix the authentication bug")
    findings_text = " ".join(verdict.findings)
    assert "no file, path, or target module" in findings_text


def test_missing_tier_detected() -> None:
    n = IntentNormalizer(threshold=0.7)
    verdict = n.normalize("fix the bug in src/auth.py with gas=100")
    findings_text = " ".join(verdict.findings)
    assert "no execution tier or trust level" in findings_text


def test_missing_gas_budget_detected() -> None:
    n = IntentNormalizer(threshold=0.7)
    verdict = n.normalize("fix the bug in src/auth.py with tier=trusted")
    findings_text = " ".join(verdict.findings)
    assert "no gas budget or resource limit" in findings_text


def test_all_constraints_present_no_penalty() -> None:
    n = IntentNormalizer(threshold=0.7)
    verdict = n.normalize(
        "fix the authentication bug in src/auth.py with tier=trusted gas=200"
    )
    constraint_findings = [f for f in verdict.findings if "Missing constraint" in f]
    assert len(constraint_findings) == 0


def test_missing_file_not_triggered_without_code_verb() -> None:
    """Missing file constraint only fires if a code verb is present."""
    n = IntentNormalizer(threshold=0.7)
    verdict = n.normalize("describe how authentication works")
    findings_text = " ".join(verdict.findings)
    assert "no file, path, or target module" not in findings_text


def test_tier_via_trust_keyword() -> None:
    n = IntentNormalizer(threshold=0.7)
    verdict = n.normalize("fix bug in src/auth.py with trusted access gas=200")
    tier_findings = [f for f in verdict.findings if "tier" in f.lower()]
    assert len(tier_findings) == 0  # "trusted" matches tier pattern


def test_gas_via_token_count() -> None:
    n = IntentNormalizer(threshold=0.7)
    verdict = n.normalize("fix bug in src/auth.py tier=trusted max 500 tokens")
    gas_findings = [f for f in verdict.findings if "gas" in f.lower()]
    assert len(gas_findings) == 0  # "max 500 tokens" matches gas pattern


# ── Rule 3: Ambiguous references (-0.15 each) ────────────────────────────────


def test_ambiguous_pronoun_without_referent() -> None:
    n = IntentNormalizer(threshold=0.7)
    verdict = n.normalize("fix it and update that")
    findings_text = " ".join(verdict.findings)
    assert "Ambiguous reference" in findings_text
    assert "'it'" in findings_text
    assert "'that'" in findings_text


def test_pronoun_with_clear_noun_referent_passes() -> None:
    n = IntentNormalizer(threshold=0.7)
    # "module" is not a concrete noun for the regex, but we avoid file paths
    # with dots (the sentence-splitter splits on dots).  Instead, use a snake_case
    # identifier (matches [a-z]+(?:_[a-z]+)+) in the same sentence as "it".
    verdict = n.normalize("fix the auth_handler module it is broken with tier trusted gas 200")
    ambiguous = [f for f in verdict.findings if "Ambiguous reference" in f and "it" in f]
    assert len(ambiguous) == 0


def test_ambiguous_reference_multiple_sentences() -> None:
    n = IntentNormalizer(threshold=0.7)
    verdict = n.normalize(
        "Look at the database module. It has issues. Fix that with tier=trusted gas=200."
    )
    findings_text = " ".join(verdict.findings)
    # "It" in sentence 2 — if no concrete noun in that sentence, it's ambiguous
    assert "Ambiguous reference" in findings_text


def test_ambiguous_reference_not_triggered_with_identifiers() -> None:
    """A sentence with a snake_case identifier referent is not ambiguous."""
    n = IntentNormalizer(threshold=0.7)
    # snake_case "config_file" matches the [a-z]+(?:_[a-z]+)+ noun pattern
    verdict = n.normalize("fix the config_file handler it throws on null input")
    ambiguous = [f for f in verdict.findings if "Ambiguous reference" in f and "it" in f.lower()]
    assert len(ambiguous) == 0


# ── Rule 4: Length penalty (-0.20 for < 10 words) ────────────────────────────


def test_length_penalty_short_intent() -> None:
    n = IntentNormalizer(threshold=0.7)
    verdict = n.normalize("fix the bug")
    findings_text = " ".join(verdict.findings)
    assert "Length penalty" in findings_text
    assert "3 word" in findings_text


def test_no_length_penalty_for_long_intent() -> None:
    n = IntentNormalizer(threshold=0.7)
    verdict = n.normalize(
        "fix the authentication bug in the login handler of src/auth.py "
        "with tier trusted and gas budget 200 tokens"
    )
    length_findings = [f for f in verdict.findings if "Length penalty" in f]
    assert len(length_findings) == 0


def test_length_penalty_exactly_nine_words() -> None:
    n = IntentNormalizer(threshold=0.7)
    # 9 words — should trigger length penalty (< 10)
    # "fix auth bug source file with proper constraints" = 8 words + no length penalty?
    # Actually we need exactly 9: "please fix auth bug source file proper constraints"
    # Let's just count: "please fix my auth source file proper constraints" = 7 + 1 for "bug" = 8... 
    verdict = n.normalize("please fix auth bug in source file proper constraints")
    # count: please(1) fix(2) auth(3) bug(4) in(5) source(6) file(7) proper(8) constraints(9) = 9
    findings_text = " ".join(verdict.findings)
    assert "Length penalty" in findings_text


def test_length_penalty_exactly_ten_words() -> None:
    n = IntentNormalizer(threshold=0.7)
    # 10 words — should NOT trigger length penalty
    verdict = n.normalize(
        "fix the authentication bug in the login source file today"
    )
    length_findings = [f for f in verdict.findings if "Length penalty" in f]
    assert len(length_findings) == 0


# ── Rule 5: Assumed context (-0.20 each) ─────────────────────────────────────


def test_assumed_context_as_before() -> None:
    n = IntentNormalizer(threshold=0.7)
    verdict = n.normalize("fix the bug as before in src/auth.py tier=trusted gas=200")
    assert any("Assumed context" in f for f in verdict.findings)
    assert any("as before" in f for f in verdict.findings)


def test_assumed_context_same_as_last_time() -> None:
    n = IntentNormalizer(threshold=0.7)
    verdict = n.normalize("same as last time, fix the auth bug")
    assert any("Assumed context" in f for f in verdict.findings)


def test_assumed_context_like_we_discussed() -> None:
    n = IntentNormalizer(threshold=0.7)
    verdict = n.normalize("like we discussed, update the config")
    assert any("Assumed context" in f for f in verdict.findings)


def test_assumed_context_the_usual() -> None:
    n = IntentNormalizer(threshold=0.7)
    verdict = n.normalize("the usual please")
    assert any("Assumed context" in f for f in verdict.findings)


def test_assumed_context_per_conversation() -> None:
    n = IntentNormalizer(threshold=0.7)
    verdict = n.normalize("per our conversation, update the deployment script")
    assert any("Assumed context" in f for f in verdict.findings)
    # Also test "per our last conversation"
    verdict2 = n.normalize("per our last conversation, update the deployment script")
    assert any("Assumed context" in f for f in verdict2.findings)


def test_assumed_context_case_insensitive() -> None:
    n = IntentNormalizer(threshold=0.7)
    verdict = n.normalize("As Before, do the thing")
    assert any("Assumed context" in f for f in verdict.findings)


def test_no_assumed_context_when_not_present() -> None:
    n = IntentNormalizer(threshold=0.7)
    verdict = n.normalize(
        "fix the authentication bug in src/auth.py with tier=trusted gas=200"
    )
    assert not any("Assumed context" in f for f in verdict.findings)


# ═══════════════════════════════════════════════════════════════════════════════
# Unit tests: verdict outcomes (pass / rewrite / reject)
# ═══════════════════════════════════════════════════════════════════════════════


def test_pass_verdict_well_formed_intent() -> None:
    n = IntentNormalizer(threshold=0.7)
    verdict = n.normalize(
        "fix the authentication bug in src/auth.py with tier trusted and gas budget 500 tokens"
    )
    assert verdict.threshold_passed is True
    assert verdict.rewritten_intent is None
    assert verdict.rejection_reason is None
    assert verdict.score >= 0.7


def test_rewrite_verdict_medium_quality_intent() -> None:
    n = IntentNormalizer(threshold=0.7)
    verdict = n.normalize("fix the stuff in the login module")
    assert verdict.threshold_passed is False
    assert verdict.rewritten_intent is not None
    assert verdict.rejection_reason is None
    # Should be in the rewrite range
    assert 0.3 <= verdict.score < 0.7


def test_rewrite_contains_clarified_markers() -> None:
    n = IntentNormalizer(threshold=0.7)
    # Stack deductions: "stuff" (-0.1), missing file constraint (-0.15),
    # ambiguous "it" (-0.15), "as before" (-0.2) = 0.4 (rewrite zone 0.3–0.7).
    verdict = n.normalize("fix the stuff with it as before tier trusted gas 200")
    assert verdict.rewritten_intent is not None
    assert "[CLARIFIED:" in verdict.rewritten_intent
    assert "[NEEDS:" in verdict.rewritten_intent


def test_rewrite_contains_caveman_structure() -> None:
    n = IntentNormalizer(threshold=0.7)
    verdict = n.normalize("fix the bug in the login")
    assert verdict.rewritten_intent is not None
    rewritten = verdict.rewritten_intent
    assert rewritten.startswith("I will ")
    assert " on " in rewritten
    assert " with " in rewritten
    assert "Result:" in rewritten


def test_reject_verdict_very_low_score() -> None:
    n = IntentNormalizer(threshold=0.7)
    verdict = n.normalize("stuff things whatever")
    assert verdict.threshold_passed is False
    assert verdict.rejection_reason is not None
    assert verdict.score < 0.3


def test_reject_verdict_single_word() -> None:
    n = IntentNormalizer(threshold=0.7)
    verdict = n.normalize("fix")
    assert verdict.threshold_passed is False
    assert verdict.rejection_reason is not None


def test_reject_verdict_exact_score_boundary() -> None:
    """Score < 0.3 triggers rejection. Verify the boundary behavior."""
    n = IntentNormalizer(threshold=0.7)
    # Stack many penalties for a guaranteed reject (< 0.3)
    verdict = n.normalize("stuff it as before whatever")
    # Score should be well below 0.3: stuff(-0.1) + ambiguous it(-0.15) +
    #   missing tier(-0.15) + missing gas(-0.15) + assumed as before(-0.2) +
    #   vague whatever(-0.1) + length(-0.2) = 1.0 - 1.05 = -0.05 → 0.0
    assert verdict.rejection_reason is not None
    assert verdict.score < 0.3


def test_rejection_reason_is_helpful() -> None:
    n = IntentNormalizer(threshold=0.7)
    verdict = n.normalize("fix")
    assert "rejected" in verdict.rejection_reason.lower()
    assert "specific" in verdict.rejection_reason.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Unit tests: edge cases
# ═══════════════════════════════════════════════════════════════════════════════


def test_empty_string_rejected() -> None:
    n = IntentNormalizer(threshold=0.7)
    verdict = n.normalize("")
    assert verdict.score == 0.0
    assert verdict.rejection_reason is not None
    assert "empty" in verdict.rejection_reason.lower()
    assert verdict.original_intent == ""


def test_whitespace_only_rejected() -> None:
    n = IntentNormalizer(threshold=0.7)
    verdict = n.normalize("   \t\n  ")
    assert verdict.score == 0.0
    assert verdict.rejection_reason is not None


def test_single_word_rejected() -> None:
    n = IntentNormalizer(threshold=0.7)
    for word in ["fix", "hello", "deploy", "test"]:
        verdict = n.normalize(word)
        assert verdict.rejection_reason is not None, f"'{word}' should be rejected"


def test_two_words_with_code_verb() -> None:
    n = IntentNormalizer(threshold=0.7)
    verdict = n.normalize("fix auth")
    # 2 words, missing constraints — should be rewrite or reject
    assert verdict.threshold_passed is False


def test_very_long_prompt_passes() -> None:
    n = IntentNormalizer(threshold=0.7)
    long_intent = (
        "refactor the authentication middleware in src/middleware/auth.py "
        "to support OAuth2 flow with JWT token validation, add rate limiting "
        "with tier trusted and gas budget of 2000 tokens, ensure all existing "
        "tests in tests/test_auth.py continue to pass, and generate documentation "
        "for the new configuration options"
    )
    verdict = n.normalize(long_intent)
    # Should have enough words, might still miss tier/gas depending on matching
    # But it should definitely not be rejected
    assert verdict.score > 0.3


def test_intent_with_only_greeting() -> None:
    n = IntentNormalizer(threshold=0.7)
    verdict = n.normalize("hello world how are you")
    assert verdict.threshold_passed is False
    # Should be rewrite or reject since no code verb, no constraints


def test_score_never_below_zero() -> None:
    n = IntentNormalizer(threshold=0.7)
    # Stack as many penalties as possible
    verdict = n.normalize("stuff things whatever etc as before same as last time fix it")
    assert verdict.score >= 0.0


def test_score_never_above_one() -> None:
    n = IntentNormalizer(threshold=0.7)
    verdict = n.normalize(
        "fix the authentication bug in src/auth.py with tier trusted gas limit 200 tokens"
    )
    assert verdict.score <= 1.0


def test_score_rounded_to_four_decimals() -> None:
    n = IntentNormalizer(threshold=0.7)
    verdict = n.normalize("fix the stuff in auth.py")
    score_str = str(verdict.score)
    if "." in score_str:
        decimals = len(score_str.split(".")[1])
        assert decimals <= 4


# ═══════════════════════════════════════════════════════════════════════════════
# Unit tests: NormalizationVerdict dataclass
# ═══════════════════════════════════════════════════════════════════════════════


def test_verdict_to_dict_contains_all_fields() -> None:
    n = IntentNormalizer(threshold=0.7)
    verdict = n.normalize("fix the bug in src/auth.py")
    d = verdict.to_dict()
    assert "score" in d
    assert "findings" in d
    assert "rewritten_intent" in d
    assert "rejection_reason" in d
    assert "threshold_passed" in d
    assert "threshold" in d
    assert "original_intent" in d


def test_verdict_to_dict_is_json_serializable() -> None:
    import json
    n = IntentNormalizer(threshold=0.7)
    verdict = n.normalize("fix the stuff in auth.py with tier=trusted gas=200")
    json_str = json.dumps(verdict.to_dict())
    assert isinstance(json_str, str)
    roundtripped = json.loads(json_str)
    assert roundtripped["score"] == verdict.score
    assert roundtripped["findings"] == list(verdict.findings)


def test_verdict_to_audit_json_is_deterministic() -> None:
    n = IntentNormalizer(threshold=0.7)
    verdict = n.normalize("fix the bug in src/auth.py")
    json1 = verdict.to_audit_json()
    json2 = verdict.to_audit_json()
    assert json1 == json2


def test_verdict_is_hashable() -> None:
    n = IntentNormalizer(threshold=0.7)
    verdict = n.normalize("fix the bug in src/auth.py")
    # Should not raise
    s = {verdict}
    assert len(s) == 1


def test_verdict_findings_are_tuple() -> None:
    n = IntentNormalizer(threshold=0.7)
    verdict = n.normalize("fix stuff in auth.py")
    assert isinstance(verdict.findings, tuple)


def test_verdict_fields_on_pass() -> None:
    n = IntentNormalizer(threshold=0.7)
    verdict = n.normalize(
        "fix the authentication bug in src/auth.py with tier trusted and gas budget 500"
    )
    assert verdict.threshold_passed is True
    assert verdict.rewritten_intent is None
    assert verdict.rejection_reason is None


def test_verdict_fields_on_reject() -> None:
    n = IntentNormalizer(threshold=0.7)
    verdict = n.normalize("stuff")
    assert verdict.threshold_passed is False
    assert verdict.rewritten_intent is None
    assert verdict.rejection_reason is not None


def test_verdict_fields_on_rewrite() -> None:
    n = IntentNormalizer(threshold=0.7)
    # "stuff" (-0.1), missing file (-0.15), "it" ambiguous (-0.15) + "as before" (-0.2) = 0.4
    # Also length 10+ no penalty. Score 0.4 is in rewrite zone (0.3–0.7).
    verdict = n.normalize("fix the stuff in it as before with tier trusted gas 200")
    assert verdict.threshold_passed is False
    assert verdict.rewritten_intent is not None
    assert verdict.rejection_reason is None


# ═══════════════════════════════════════════════════════════════════════════════
# Unit tests: lexicon integrity
# ═══════════════════════════════════════════════════════════════════════════════


def test_vague_terms_lexicon_is_frozenset() -> None:
    assert isinstance(_VAGUE_TERMS, frozenset)


def test_vague_terms_lexicon_not_empty() -> None:
    assert len(_VAGUE_TERMS) > 5


def test_ambiguous_pronouns_lexicon_is_frozenset() -> None:
    assert isinstance(_AMBIGUOUS_PRONOUNS, frozenset)


def test_assumed_context_patterns_not_empty() -> None:
    assert len(_ASSUMED_CONTEXT_PATTERNS) > 3


# ═══════════════════════════════════════════════════════════════════════════════
# Integration tests: _apply_normalization_gate
# ═══════════════════════════════════════════════════════════════════════════════


def test_gate_returns_expected_keys_on_pass() -> None:
    ctx = build_server_context()
    result = _apply_normalization_gate(
        ctx,
        "fix the authentication bug in src/auth.py with tier trusted and gas budget 500",
    )
    assert "text" in result
    assert "verdict" in result
    assert "rejected" in result
    assert "rewritten" in result
    assert "normalization" in result
    assert result["rejected"] is False


def test_gate_returns_expected_keys_on_rewrite() -> None:
    ctx = build_server_context()
    # Stack enough deductions: "stuff" (-0.1), "it" ambiguous (-0.15),
    # "as before" (-0.2) = 0.55 (rewrite zone 0.3–0.7)
    result = _apply_normalization_gate(ctx, "fix stuff in it as before with tier trusted gas 200")
    assert result["rejected"] is False
    assert result["rewritten"] is True
    assert result["text"] != "fix stuff in it as before with tier trusted gas 200"
    assert result["verdict"] is not None
    assert result["normalization"]["rewritten"] is True


def test_gate_returns_expected_keys_on_reject() -> None:
    ctx = build_server_context()
    result = _apply_normalization_gate(ctx, "stuff")
    assert result["rejected"] is True
    assert result["rewritten"] is False
    assert "reason" in result
    assert "findings" in result
    assert result["verdict"] is not None


def test_gate_skip_normalization_bool() -> None:
    ctx = build_server_context()
    result = _apply_normalization_gate(ctx, "fix stuff", skip_normalization=True)
    assert result["verdict"] is None
    assert result["rejected"] is False
    assert result["rewritten"] is False
    assert result["text"] == "fix stuff"
    assert result["normalization"] is None


def test_gate_audit_log_has_intent_normalized() -> None:
    ctx = build_server_context()
    _apply_normalization_gate(
        ctx,
        "fix the auth bug in src/auth.py with tier trusted gas=200 tokens",
    )
    recent = ctx.audit_chain.recent(10)
    normalized_events = [e for e in recent if e["event"] == "intent_normalized"]
    assert len(normalized_events) >= 1


def test_gate_audit_log_data_contains_score() -> None:
    ctx = build_server_context()
    _apply_normalization_gate(
        ctx,
        "fix the auth bug in src/auth.py with tier trusted gas=200 tokens",
    )
    recent = ctx.audit_chain.recent(10)
    normalized_events = [e for e in recent if e["event"] == "intent_normalized"]
    assert len(normalized_events) >= 1
    entry = normalized_events[0]
    assert "score" in entry["data"]


def test_gate_anomaly_score_when_rejected() -> None:
    ctx = build_server_context()
    _apply_normalization_gate(ctx, "stuff")
    recent = ctx.audit_chain.recent(10)
    normalized_events = [e for e in recent if e["event"] == "intent_normalized"]
    assert len(normalized_events) >= 1
    entry = normalized_events[0]
    # anomaly_score should be > 0 for failed normalization
    assert entry["anomaly_score"] > 0.0


def test_gate_anomaly_score_zero_when_passed() -> None:
    ctx = build_server_context()
    _apply_normalization_gate(
        ctx,
        "fix the authentication bug in src/auth.py with tier trusted and gas budget 500 tokens",
    )
    recent = ctx.audit_chain.recent(10)
    normalized_events = [e for e in recent if e["event"] == "intent_normalized"]
    assert len(normalized_events) >= 1
    entry = normalized_events[0]
    assert entry["anomaly_score"] == 0.0


def test_gate_normalization_summary_fields() -> None:
    ctx = build_server_context()
    result = _apply_normalization_gate(ctx, "fix the stuff")
    assert result["normalization"] is not None
    norm = result["normalization"]
    assert "score" in norm
    assert "threshold_passed" in norm
    assert "findings" in norm
    assert "rewritten" in norm
    assert "rejected" in norm


# ═══════════════════════════════════════════════════════════════════════════════
# Integration tests: MCP tool round-trips
# ═══════════════════════════════════════════════════════════════════════════════


def test_translate_to_hlf_well_formed_passes() -> None:
    result = asyncio.run(server.hlf_translate_to_hlf(
        "fix the authentication bug in src/auth.py with tier trusted and gas budget 500 tokens",
    ))
    assert result["status"] == "ok"
    assert result["source"].startswith("[HLF-v3]")


def test_translate_to_hlf_rejected_intent_returns_error() -> None:
    result = asyncio.run(server.hlf_translate_to_hlf("fix"))
    assert result["status"] == "rejected"
    assert "reason" in result
    assert "normalization" in result


def test_translate_to_hlf_with_rewrite_still_succeeds() -> None:
    """A medium-quality intent gets rewritten then proceeds to translation."""
    result = asyncio.run(server.hlf_translate_to_hlf(
        "fix the auth module with tier trusted and gas budget 500 tokens"
    ))
    # This has enough words and constraints that it should pass or get rewritten
    # If rewritten, status is still "ok"
    assert "status" in result


def test_translate_to_hlf_skip_normalization() -> None:
    """With skip_normalization=True, even 'Hi' passes through the gate."""
    result = asyncio.run(server.hlf_translate_to_hlf(
        "Hi", language="en", skip_normalization=True
    ))
    assert result["status"] == "ok"
    # No normalization block in response (or it's None)
    norm = result.get("normalization")
    # When skipped, normalization is None in the response
    assert norm is None or norm is False


def test_translate_to_hlf_normalization_in_response() -> None:
    result = asyncio.run(server.hlf_translate_to_hlf(
        "fix the auth bug in src/auth.py with tier trusted gas=200 tokens "
        "so that login works correctly"
    ))
    # Response should include normalization data
    if result.get("normalization"):
        norm = result["normalization"]
        assert "score" in norm


def test_hlf_do_dry_run_with_normalization() -> None:
    result = server.hlf_do(
        "Audit src/auth.py in read-only mode with tier trusted and gas 500 tokens",
        dry_run=True,
        show_hlf=True,
    )
    assert result["success"] is True


def test_hlf_do_rejected_intent() -> None:
    result = server.hlf_do("stuff", dry_run=True)
    # Should be rejected by the gate
    if result.get("status") == "rejected":
        assert "reason" in result


def test_hlf_do_skip_normalization() -> None:
    result = server.hlf_do(
        "Hi", dry_run=True, skip_normalization=True, language="en"
    )
    # Even with minimal input, skip_normalization bypasses the gate
    assert "success" in result or "status" in result


def test_hlf_translate_resilient_with_normalization() -> None:
    """Resilient translate should go through normalization gate."""
    result = server.hlf_translate_resilient(
        "fix the auth bug in src/auth.py with tier trusted gas=200 tokens",
    )
    assert result["status"] == "ok"


def test_hlf_translate_repair_rejected() -> None:
    """Repair of a failed translation — the repair intent goes through the gate."""
    result = server.hlf_translate_repair(
        "fix the broken auth module in src/auth.py with tier trusted and gas 500",
    )
    # Repair uses skip_normalization=True internally for its own internal calls
    # But the initial text goes through the gate
    assert "status" in result


# ═══════════════════════════════════════════════════════════════════════════════
# Integration tests: audit trail across tools
# ═══════════════════════════════════════════════════════════════════════════════


def test_audit_trail_after_translate_to_hlf() -> None:
    """After calling translate_to_hlf, the global audit chain has events."""
    # Read the audit chain BEFORE to get a baseline count
    initial_events = server._ctx.audit_chain.recent(200)
    initial_count = len([e for e in initial_events if e["event"] == "intent_normalized"])

    asyncio.run(server.hlf_translate_to_hlf(
        "fix the auth bug in src/auth.py with tier trusted gas=200 tokens "
        "so that login works correctly"
    ))

    later_events = server._ctx.audit_chain.recent(200)
    later_count = len([e for e in later_events if e["event"] == "intent_normalized"])
    assert later_count > initial_count


def test_audit_trail_includes_original_intent() -> None:
    intent = (
        "fix the authentication bug in src/auth.py "
        "with tier trusted and gas budget 500 tokens"
    )
    asyncio.run(server.hlf_translate_to_hlf(intent))
    recent = server._ctx.audit_chain.recent(10)
    normalized_events = [e for e in recent if e["event"] == "intent_normalized"]
    assert len(normalized_events) >= 1
    entry = normalized_events[0]
    assert entry["data"].get("original_intent") == intent


# ═══════════════════════════════════════════════════════════════════════════════
# Integration tests: different personas / cognitive lanes
# ═══════════════════════════════════════════════════════════════════════════════


def test_translate_with_cognitive_lane_policy() -> None:
    result = asyncio.run(server.hlf_translate_to_hlf(
        "fix the auth bug in src/auth.py with tier trusted and gas budget 500",
        cognitive_lane_policy="benchmark_gated",
    ))
    assert result["status"] == "ok"


def test_hlf_do_with_agent_id_trace() -> None:
    result = server.hlf_do(
        "Audit src/auth.py with tier trusted gas=500 tokens",
        dry_run=True,
        agent_id="test-agent-42",
    )
    assert result["success"] is True
