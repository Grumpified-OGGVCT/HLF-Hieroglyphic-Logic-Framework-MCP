from __future__ import annotations

import json


def test_resolve_persona_contract_for_docs_truth_source() -> None:
    from hlf_mcp.persona_contract import resolve_persona_contract

    contract = resolve_persona_contract(
        source="weekly-doc-accuracy",
        review_type="weekly_artifact",
        severity="warning",
        recommended_triage_lane="backlog",
    )

    assert contract["change_class"] == "docs_truth"
    assert contract["lane"] == "bridge-true"
    assert contract["owner_persona"] == "herald"
    assert contract["review_personas"] == ["strategist", "chronicler", "cove"]
    assert contract["required_gates"] == [
        "strategist_review",
        "herald_review",
        "chronicler_review",
        "cove_review",
        "operator_promotion",
    ]
    assert contract["gate_results"]["herald_review"]["owner_persona"] == "herald"
    assert contract["gate_results"]["operator_promotion"]["owner_persona"] == "operator"
    assert contract["escalate_to_persona"] is None
    assert contract["handoff_template_ref"] == "governance/templates/persona_review_handoff.md"


def test_resolve_persona_contract_preserves_valid_existing_gate_results() -> None:
    from hlf_mcp.persona_contract import resolve_persona_contract

    contract = resolve_persona_contract(
        source="weekly-code-quality",
        review_type="weekly_artifact",
        severity="critical",
        recommended_triage_lane="current_batch",
        existing={
            "gate_results": {
                "sentinel_review": {
                    "owner_persona": "sentinel",
                    "status": "blocked",
                    "notes": "Open CodeQL findings remain.",
                }
            }
        },
    )

    assert contract["change_class"] == "security_sensitive"
    assert contract["owner_persona"] == "sentinel"
    assert contract["gate_results"]["sentinel_review"]["status"] == "blocked"
    assert contract["gate_results"]["sentinel_review"]["notes"] == "Open CodeQL findings remain."
    assert contract["escalate_to_persona"] == "operator"


def test_validate_persona_contract_rejects_missing_required_gate() -> None:
    from hlf_mcp.governed_review import default_governed_review, validate_governed_review

    review = default_governed_review(source="weekly-spec-sentinel")
    review["gate_results"].pop("strategist_review")

    errors: list[str] = []
    validate_governed_review(review, errors)

    assert "governed_review_gate_results[strategist_review]_missing" in errors


def test_load_persona_matrix_prefers_runtime_copy_when_present(tmp_path, monkeypatch) -> None:
    from hlf_mcp import persona_contract

    runtime_matrix = tmp_path / "runtime.json"
    runtime_matrix.write_text(
        json.dumps(
            {
                "lane": "runtime-lane",
                "change_classes": {},
                "gate_states": {},
                "personas": {},
            }
        ),
        encoding="utf-8",
    )
    repo_matrix = tmp_path / "repo.json"
    repo_matrix.write_text(
        json.dumps(
            {
                "lane": "repo-lane",
                "change_classes": {},
                "gate_states": {},
                "personas": {},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(persona_contract, "_runtime_matrix_path", lambda: runtime_matrix)
    monkeypatch.setattr(persona_contract, "_repo_matrix_path", lambda: repo_matrix)
    persona_contract.load_persona_matrix.cache_clear()

    try:
        matrix = persona_contract.load_persona_matrix()
    finally:
        persona_contract.load_persona_matrix.cache_clear()

    assert matrix["lane"] == "runtime-lane"
