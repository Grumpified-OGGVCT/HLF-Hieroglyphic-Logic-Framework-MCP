"""
Tests for .github/scripts/ — spec_drift_check, ethics_compliance_check,
codebase_snapshot, and the production-hardened ollama_client with
circuit breaker, tiered chains, streaming buffer, retry policy,
response validator, connection monitor, and fallback orchestrator.
"""

from __future__ import annotations

import http.client
import io
import json
import sys
import time
from pathlib import Path
from textwrap import dedent
from unittest.mock import MagicMock, patch

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent / ".github" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


# ============================================================
# spec_drift_check
# ============================================================


class TestSpecDriftCheck:
    def test_load_yaml_opcodes_parses_pairs(self, tmp_path):
        from spec_drift_check import _load_yaml_opcodes

        p = tmp_path / "spec.yaml"
        p.write_text("  - name: NOP   code: 0x00\n  - name: HALT  code: 0xFF\n")
        assert _load_yaml_opcodes(p) == {"NOP": 0x00, "HALT": 0xFF}

    def test_load_py_opcodes_parses_enum(self, tmp_path):
        from spec_drift_check import _load_py_opcodes

        p = tmp_path / "bytecode.py"
        p.write_text("class Op:\n    NOP  = 0x00\n    HALT = 0xFF\n")
        assert _load_py_opcodes(p) == {"NOP": 0x00, "HALT": 0xFF}

    def test_no_drift_when_matching(self, tmp_path):
        from spec_drift_check import _load_py_opcodes, _load_yaml_opcodes

        yaml = tmp_path / "spec.yaml"
        yaml.write_text("  - name: NOP  code: 0x00\n")
        py = tmp_path / "bytecode.py"
        py.write_text("class Op:\n    NOP = 0x00\n")
        assert _load_yaml_opcodes(yaml) == _load_py_opcodes(py)

    def test_detects_missing_opcode_in_py(self, tmp_path):
        from spec_drift_check import _load_py_opcodes, _load_yaml_opcodes

        yaml = tmp_path / "spec.yaml"
        yaml.write_text("  - name: NOP  code: 0x00\n  - name: NEW_OP  code: 0x99\n")
        py = tmp_path / "bytecode.py"
        py.write_text("class Op:\n    NOP = 0x00\n")
        only_yaml = set(_load_yaml_opcodes(yaml)) - set(_load_py_opcodes(py))
        assert "NEW_OP" in only_yaml

    def test_detects_code_mismatch(self, tmp_path):
        from spec_drift_check import _load_py_opcodes, _load_yaml_opcodes

        yaml = tmp_path / "spec.yaml"
        yaml.write_text("  - name: NOP  code: 0x00\n")
        py = tmp_path / "bytecode.py"
        py.write_text("class Op:\n    NOP = 0x01\n")
        assert _load_yaml_opcodes(yaml)["NOP"] != _load_py_opcodes(py)["NOP"]

    def test_count_mcp_tools(self, tmp_path):
        from spec_drift_check import _count_mcp_tools

        from hlf_mcp import server as packaged_server

        p = tmp_path / "server.py"
        p.write_text("@mcp.tool()\ndef a(): pass\n@mcp.tool()\ndef b(): pass\n")
        assert _count_mcp_tools(p) == len(packaged_server.REGISTERED_TOOLS)

    def test_readme_claimed_counts(self, tmp_path):
        from spec_drift_check import _readme_claimed_counts

        p = tmp_path / "README.md"
        p.write_text("22 MCP tools\n37 opcodes\n8 stdlib modules\n")
        counts = _readme_claimed_counts(p)
        assert counts.get("tools") == 22
        assert counts.get("opcodes") == 37
        assert counts.get("stdlib_modules") == 8

    def test_run_checks_returns_structure(self):
        from spec_drift_check import run_checks

        findings, has_drift = run_checks()
        assert isinstance(findings, list) and isinstance(has_drift, bool)
        for f in findings:
            assert "check" in f and "drift" in f

    def test_real_repo_no_opcode_drift(self):
        """Integration: real repo bytecode_spec.yaml must match bytecode.py Op enum."""
        from spec_drift_check import run_checks

        findings, _ = run_checks()
        check = next((f for f in findings if f["check"] == "bytecode_spec_vs_op_enum"), None)
        if check:
            assert check["only_in_yaml"] == [], f"Only in yaml: {check['only_in_yaml']}"
            assert check["only_in_py"] == [], f"Only in py: {check['only_in_py']}"


class TestReadinessRefreshCheck:
    def test_refresh_required_when_truth_input_changes_without_readiness_outputs(self, tmp_path):
        from readiness_refresh_check import build_refresh_report

        changed = ["SSOT_HLF_MCP.md"]
        report = build_refresh_report(changed)

        assert report["refresh_required"] is True
        assert report["satisfied"] is False
        assert "SSOT_HLF_MCP.md" in report["changed_inputs"]

    def test_refresh_satisfied_when_input_and_readiness_output_change_together(self):
        from readiness_refresh_check import build_refresh_report

        changed = [
            "docs/HLF_MISSING_PILLARS.md",
            "docs/HLF_PILLAR_READINESS_SCORECARD_2026-03-20.md",
        ]
        report = build_refresh_report(changed)

        assert report["refresh_required"] is True
        assert report["satisfied"] is True
        assert "docs/HLF_PILLAR_READINESS_SCORECARD_2026-03-20.md" in report["changed_outputs"]

    def test_refresh_required_when_weekly_artifact_changes_without_generated_outputs(self):
        from readiness_refresh_check import build_refresh_report

        changed = ["observability/local_validation/2026-03-20/test-health-final/weekly-test-health-artifact.json"]
        report = build_refresh_report(changed)

        assert report["refresh_required"] is True
        assert report["satisfied"] is False
        assert changed[0] in report["changed_inputs"]

    def test_refresh_satisfied_when_weekly_artifact_and_status_outputs_change_together(self):
        from readiness_refresh_check import build_refresh_report

        changed = [
            "observability/local_validation/2026-03-20/test-health-final/weekly-test-health-artifact.json",
            "docs/HLF_STATUS_OVERVIEW.md",
            "docs/index.html",
        ]
        report = build_refresh_report(changed)

        assert report["refresh_required"] is True
        assert report["satisfied"] is True
        assert "docs/index.html" in report["changed_outputs"]


class TestGenerateStatusOverview:
    def test_docs_blob_href_uses_relative_links_locally_and_github_env_in_ci(
        self, monkeypatch
    ):
        from generate_status_overview import _docs_blob_href

        monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
        monkeypatch.delenv("GITHUB_HEAD_REF", raising=False)
        monkeypatch.delenv("GITHUB_REF_NAME", raising=False)
        assert _docs_blob_href("HLF_STATUS_OVERVIEW.md") == "HLF_STATUS_OVERVIEW.md"

        monkeypatch.setenv("GITHUB_REPOSITORY", "example-org/example-repo")
        monkeypatch.setenv("GITHUB_HEAD_REF", "feature/readiness")
        assert (
            _docs_blob_href("HLF_STATUS_OVERVIEW.md")
            == "https://github.com/example-org/example-repo/blob/feature/readiness/docs/HLF_STATUS_OVERVIEW.md"
        )

    def test_collect_status_data_and_render_surfaces(self, tmp_path):
        from generate_status_overview import (
            collect_status_data,
            render_claims_ledger_html,
            render_merge_readiness_html,
            render_status_index_html,
            render_status_overview_markdown,
            write_status_surfaces,
        )

        docs_dir = tmp_path / "docs"
        docs_dir.mkdir(parents=True)
        (tmp_path / "observability" / "local_validation" / "2026-03-20" / "test-health-final").mkdir(parents=True)
        (tmp_path / "observability" / "local_validation" / "2026-03-20" / "doc-accuracy").mkdir(parents=True)

        (docs_dir / "HLF_INTERNAL_READINESS_DASHBOARD_2026-03-20.md").write_text(
            "\n".join(
                [
                    "## Top-Level Indices",
                    "",
                    "| Index | Score | Reading |",
                    "| --- | ---: | --- |",
                    "| Overall repo readiness | 58.9% | bridge-active |",
                    "",
                    "## Cluster View",
                    "",
                    "| Cluster | Included pillars | Score | Reading |",
                    "| --- | --- | ---: | --- |",
                    "| Semantic core | deterministic language core | 70.8% | strongest current cluster |",
                    "| Governance and trust | governance-native execution | 59.8% | real substance |",
                    "| Coordination and operator systems | routing | 41.3% | main drag on total readiness |",
                    "",
                    "### Per-Pillar Readiness",
                    "",
                    "| Pillar | Score |",
                    "| --- | ---: |",
                    "| Deterministic language core | 87.5% |",
                    "| Runtime and capsule-bounded execution | 82.5% |",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        (docs_dir / "HLF_PILLAR_READINESS_SCORECARD_2026-03-20.md").write_text(
            "\n".join(
                [
                    "## Weighted Result",
                    "",
                    "- `58.9%`",
                    "",
                    "## Strongest Pillars",
                    "",
                    "| Pillar | Score | Why it leads |",
                    "| --- | ---: | --- |",
                    "| Deterministic language core | 87.5% | strongest combination of implementation and proof |",
                    "",
                    "## Weakest Pillars",
                    "",
                    "| Pillar | Score | Why it lags |",
                    "| --- | ---: | --- |",
                    "| Ecosystem integration surface | 22.5% | packaged proof remains mostly absent |",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        (docs_dir / "HLF_MERGE_READINESS_SUMMARY_2026-03-20.md").write_text(
            "\n".join(
                [
                    "# HLF Merge Readiness Summary",
                    "",
                    "Status: branch-aware merge/readiness summary for 2026-03-20.",
                    "",
                    "## Purpose",
                    "",
                    "- summarize what this branch can honestly claim now",
                    "- separate current packaged truth from bridge-qualified branch work",
                    "",
                    "## Verified branch facts",
                    "",
                    "- branch: `integrate/vscode-operator-governed-review`",
                    "- repo-wide regression snapshot on 2026-03-20: `758 passed`",
                    "",
                    "## Current-True In This Checkout",
                    "",
                    "These are implemented and verified enough to claim in present tense for this local branch.",
                    "",
                    "- packaged FastMCP front door with `69` tools and `31` resources",
                    "",
                    "## Bridge-True But Real In This Branch",
                    "",
                    "These surfaces are real in the checkout, but should remain explicitly qualified.",
                    "",
                    "- bounded dream-cycle, media-evidence normalization, and citation-chain proposal surfaces",
                    "",
                    "## Still-Open Architectural Gaps",
                    "",
                    "- full upstream routing fabric restoration",
                    "",
                    "## Near-Term Merge Risks",
                    "",
                    "- public-facing docs can still lag branch reality if the new ledger and summary are not linked and kept current",
                    "",
                    "## Merge Reading",
                    "",
                    "- materially ahead of `main`",
                    "",
                    "## Recommended Merge Framing",
                    "",
                    "1. `current-true`: packaged surfaces now real in this checkout",
                    "2. `bridge-true`: meaningful branch slices now landed but not yet full target-state completion",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        (docs_dir / "HLF_BRANCH_AWARE_CLAIMS_LEDGER_2026-03-20.md").write_text(
            "\n".join(
                [
                    "# HLF Branch-Aware Claims Ledger",
                    "",
                    "Status: public-facing branch-aware review aid for 2026-03-20.",
                    "",
                    "Purpose:",
                    "",
                    "- give reviewers a compact way to distinguish public-main perception from current branch reality",
                    "- keep branch improvements visible without promoting bridge work into false completion",
                    "",
                    "Reading rule:",
                    "",
                    "- use `docs/HLF_CLAIM_LANES.md` when reusing or promoting any statement from this file",
                    "- this ledger is branch-aware, not `main`-only",
                    "",
                    "Verified branch facts used here:",
                    "",
                    "- active branch: `integrate/vscode-operator-governed-review`",
                    "- packaged surface count in this checkout: `69` tools, `31` resources",
                    "",
                    "## 1. Overstated Public Gaps",
                    "",
                    "| Public gap claim | Branch-aware reality | True remaining gap after both are considered |",
                    "| --- | --- | --- |",
                    "| Formal verification is only a placeholder | Packaged verifier behavior exists | Deeper verifier semantics remain open |",
                    "",
                    "## 2. Valid Public Gaps",
                    "",
                    "| Public gap claim | Branch-aware reality | True remaining gap after both are considered |",
                    "| --- | --- | --- |",
                    "| Memory governance is still incomplete | Correct | Stronger freshness and revocation closure remain open |",
                    "",
                    "## 3. Branch-Resolved Gaps",
                    "",
                    "| Gap previously inferred from public-facing materials | What now exists in this checkout | Lane-qualified reading |",
                    "| --- | --- | --- |",
                    "| Formal verifier only exposes a status stub | Tools and reports now exist | `current-true` for the packaged slice |",
                    "",
                    "## 4. Still-Open Architectural Gaps",
                    "",
                    "| Gap | Why it is still open |",
                    "| --- | --- |",
                    "| Full routing fabric restoration | The broader gateway coordination layer is not yet restored |",
                    "",
                    "## Bottom Line",
                    "",
                    "The public repo can still make the branch look thinner than it is.",
                    "",
                    "- some public gaps are stale or overstated for this checkout",
                    "- some remain real architectural gaps even after the branch work is counted",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        test_health_artifact = {
            "source": "weekly-test-health",
            "generated_at": "2026-03-20T20:41:45+00:00",
            "artifact_status": "advisory",
            "governed_review": {
                "summary": "Test health reports partial coverage at 74.8%.",
                "recommended_triage_lane": "backlog",
                "owner_persona": "steward",
                "review_metadata": {"percent_covered": 74.8383122882661},
            },
        }
        prior_test_health_artifact = {
            "source": "weekly-test-health",
            "generated_at": "2026-03-20T20:10:00+00:00",
            "artifact_status": "advisory",
            "governed_review": {
                "summary": "Test health run completed without usable coverage totals.",
                "recommended_triage_lane": "backlog",
                "owner_persona": "steward",
                "review_metadata": {"percent_covered": None},
            },
        }
        doc_accuracy_artifact = {
            "source": "weekly-doc-accuracy",
            "generated_at": "2026-03-20T20:29:01+00:00",
            "artifact_status": "advisory",
            "governed_review": {
                "summary": "Documentation accuracy review found no measured drift.",
                "recommended_triage_lane": "ignore",
                "owner_persona": "herald",
                "review_metadata": {"drift_detected": False},
            },
            "workflow_payload": {"doc_drift": {"drift_detected": False}},
        }

        (tmp_path / "observability" / "local_validation" / "2026-03-20" / "test-health-final" / "weekly-test-health-artifact.json").write_text(
            json.dumps(test_health_artifact),
            encoding="utf-8",
        )
        (tmp_path / "observability" / "local_validation" / "2026-03-20" / "test-health-final" / "weekly-test-health-prior-artifact.json").write_text(
            json.dumps(prior_test_health_artifact),
            encoding="utf-8",
        )
        (tmp_path / "observability" / "local_validation" / "2026-03-20" / "doc-accuracy" / "weekly-doc-accuracy-artifact.json").write_text(
            json.dumps(doc_accuracy_artifact),
            encoding="utf-8",
        )

        data = collect_status_data(tmp_path)
        markdown = render_status_overview_markdown(data)
        html = render_status_index_html(data)
        merge_html = render_merge_readiness_html(
            data,
            {
                "path": "docs/HLF_MERGE_READINESS_SUMMARY_2026-03-20.md",
                "status": "branch-aware merge/readiness summary for 2026-03-20.",
                "purpose": [
                    "summarize what this branch can honestly claim now",
                    "separate current packaged truth from bridge-qualified branch work",
                ],
                "verified": [
                    "branch: `integrate/vscode-operator-governed-review`",
                    "repo-wide regression snapshot on 2026-03-20: `758 passed`",
                ],
                "sections": [
                    {
                        "title": "Current-True In This Checkout",
                        "paragraphs": [
                            "These are implemented and verified enough to claim in present tense for this local branch.",
                        ],
                        "bullets": ["packaged FastMCP front door with `69` tools and `31` resources"],
                    }
                ],
            },
        )
        claims_html = render_claims_ledger_html(
            data,
            {
                "path": "docs/HLF_BRANCH_AWARE_CLAIMS_LEDGER_2026-03-20.md",
                "status": "public-facing branch-aware review aid for 2026-03-20.",
                "purpose": [
                    "give reviewers a compact way to distinguish public-main perception from current branch reality",
                ],
                "reading_rule": [
                    "use `docs/HLF_CLAIM_LANES.md` when reusing or promoting any statement from this file",
                ],
                "verified": [
                    "active branch: `integrate/vscode-operator-governed-review`",
                ],
                "sections": [
                    {
                        "title": "Overstated Public Gaps",
                        "rows": [
                            {
                                "Public gap claim": "Formal verification is only a placeholder",
                                "Branch-aware reality": "Packaged verifier behavior exists",
                                "True remaining gap after both are considered": "Deeper verifier semantics remain open",
                            }
                        ],
                    }
                ],
                "bottom_line": {
                    "paragraphs": ["The public repo can still make the branch look thinner than it is."],
                    "bullets": ["some public gaps are stale or overstated for this checkout"],
                },
            },
        )
        write_result = write_status_surfaces(tmp_path)

        assert data["dashboard"]["overall_readiness"] == 58.9
        assert "Test health reports partial coverage at 74.8%." in markdown
        assert "latest replay restored a comparable coverage signal" in markdown
        assert "Artifact paths under `observability/local_validation/...` are example/local-only" in markdown
        assert "HLF Status Surface" in html
        assert "Documentation accuracy review found no measured drift." in html
        assert "example/local-only governed-run locations" in html
        assert "Lane Reading Bands" in html
        assert "Trend Micrographics" in html
        assert "Governance Trust Path" in html
        assert "Source Provenance" in html
        assert "HLF Merge Readiness" in merge_html
        assert "branch-aware merge/readiness summary for 2026-03-20." in merge_html
        assert "Reviewer Decision Panel" in merge_html
        assert "HLF Claims Ledger" in claims_html
        assert "Verdict System" in claims_html
        assert "HLF_BRANCH_AWARE_CLAIMS_LEDGER_2026-03-20.md" in claims_html
        assert write_result["merge_html_changed"] is True
        assert write_result["claims_html_changed"] is True
        assert (docs_dir / "merge-readiness.html").exists()
        assert (docs_dir / "claims-ledger.html").exists()


# ============================================================
# ethics_compliance_check
# ============================================================


class TestEthicsComplianceCheck:
    def test_missing_module_is_stub(self, tmp_path, monkeypatch):
        import ethics_compliance_check as ecc

        monkeypatch.setattr(ecc, "ETHICS_DIR", tmp_path)
        result = ecc._check_ethics_stubs()
        assert all(v["is_stub"] for v in result.values())

    def test_implemented_module_detected(self, tmp_path, monkeypatch):
        import ethics_compliance_check as ecc

        monkeypatch.setattr(ecc, "ETHICS_DIR", tmp_path)
        (tmp_path / "constitution.py").write_text(
            "\n".join(f"def rule_{i}(x): return x > 0" for i in range(20))
        )
        result = ecc._check_ethics_stubs()
        assert result["constitution.py"]["status"] == "IMPLEMENTED"
        assert result["termination.py"]["status"] == "MISSING"

    def test_compiler_hook_comment_only(self, tmp_path, monkeypatch):
        import ethics_compliance_check as ecc

        p = tmp_path / "compiler.py"
        p.write_text("# TODO: ethics governor hook\n")
        monkeypatch.setattr(ecc, "COMPILER_PY", p)
        r = ecc._check_compiler_ethics_hook()
        assert r["wired"] is False and r["status"] == "COMMENT_ONLY"

    def test_compiler_hook_wired(self, tmp_path, monkeypatch):
        import ethics_compliance_check as ecc

        p = tmp_path / "compiler.py"
        p.write_text("from hlf_mcp.hlf.ethics import constitution\nconstitution.check(tree)\n")
        monkeypatch.setattr(ecc, "COMPILER_PY", p)
        r = ecc._check_compiler_ethics_hook()
        assert r["wired"] is True and r["status"] == "WIRED"

    def test_align_rules_adequate(self, tmp_path, monkeypatch):
        import ethics_compliance_check as ecc

        p = tmp_path / "align_rules.json"
        p.write_text(json.dumps([{"id": f"R{i}"} for i in range(5)]))
        monkeypatch.setattr(ecc, "ALIGN_JSON", p)
        r = ecc._check_align_rules()
        assert r["adequate"] is True and r["rule_count"] == 5

    def test_align_rules_inadequate(self, tmp_path, monkeypatch):
        import ethics_compliance_check as ecc

        p = tmp_path / "align_rules.json"
        p.write_text(json.dumps([{"id": "R1"}]))
        monkeypatch.setattr(ecc, "ALIGN_JSON", p)
        r = ecc._check_align_rules()
        assert r["adequate"] is False and r["status"] == "NEEDS_MORE_RULES"


# ============================================================
# codebase_snapshot
# ============================================================


class TestCodebaseSnapshot:
    def test_snapshot_non_empty(self):
        from codebase_snapshot import build_snapshot

        result = build_snapshot(char_budget=50_000)
        assert len(result) > 100 and "FILE TREE" in result

    def test_snapshot_respects_budget(self):
        from codebase_snapshot import build_snapshot

        result = build_snapshot(char_budget=5_000)
        assert len(result) <= 6_000

    def test_snapshot_writes_file(self, tmp_path):
        from codebase_snapshot import build_snapshot

        out = str(tmp_path / "snap.txt")
        build_snapshot(output_file=out, char_budget=10_000)
        assert Path(out).exists() and Path(out).stat().st_size > 0


# ============================================================
# governed_review_contract
# ============================================================


class TestGovernedReviewContract:
    def test_render_evolution_issue_accepts_dict_content(self):
        from governed_review_contract import _render_evolution_issue

        plan_payload = {
            "content": {
                "summary": "Structured plan summary",
                "top_priority_index": 0,
                "pillar_assessments": [
                    {
                        "pillar": "governance",
                        "status": "strong",
                        "rationale": "Deterministic review contract preserved.",
                    }
                ],
                "evolution_items": [
                    {
                        "title": "Promote governed bridge hardening",
                        "why": "Close the structured output gap.",
                        "impact": "Higher reliability",
                        "impact_metric": "fewer runtime failures",
                        "effort": "low",
                        "priority": "high",
                        "lane": "bridge",
                        "phase": "current",
                        "pillar": "governance",
                        "first_step_file": ".github/scripts/governed_review_contract.py",
                        "first_step_function": "_coerce_plan_content",
                    }
                ],
            },
            "model": "planner-model",
        }
        code_starter_payload = {"content": "starter code", "model": "coder-model"}

        rendered = _render_evolution_issue(
            plan_payload,
            code_starter_payload,
            "https://example.test/run/123",
        )

        assert "HLF Weekly Evolution Plan" in rendered
        assert "Structured plan summary" in rendered
        assert "Promote governed bridge hardening" in rendered
        assert "planner-model" in rendered
        assert "## Persona Handoff" in rendered
        assert "- Change class: planning_only" in rendered
        assert "- Owner persona: strategist" in rendered
        assert "- Handoff template: `governance/templates/persona_review_handoff.md`" in rendered

    def test_render_evolution_issue_preserves_persona_handoff_block_wording(self):
        from governed_review_contract import _render_evolution_issue

        plan_payload = {
            "content": {
                "summary": "Structured plan summary",
                "top_priority_index": 0,
                "pillar_assessments": [],
                "evolution_items": [],
            },
            "model": "planner-model",
        }
        code_starter_payload = {"content": "starter code", "model": "coder-model"}

        rendered = _render_evolution_issue(
            plan_payload,
            code_starter_payload,
            "https://example.test/run/123",
        )

        expected_block = dedent(
            """
            ## Persona Handoff

            - Change class: planning_only
            - Lane: bridge-true
            - Owner persona: strategist
            - Review personas: chronicler, cove
            - Required gates: strategist_review, chronicler_review, cove_review, operator_promotion
            - Escalate to: none
            - Operator summary: Owner persona strategist; review personas chronicler, cove; required gates strategist_review, chronicler_review, cove_review, operator_promotion.
            - Handoff template: `governance/templates/persona_review_handoff.md`
            """
        ).strip()

        assert expected_block in rendered


# ============================================================
# ollama_client — model registry & chains
# ============================================================


class TestModelRegistry:
    def test_all_chains_have_at_least_two_models(self):
        from ollama_client import CHAIN_MAP

        for name, chain in CHAIN_MAP.items():
            assert len(chain) >= 2, f"Chain {name!r} too short"

    def test_all_chain_models_in_registry(self):
        from ollama_client import CHAIN_MAP, MODEL_REGISTRY

        for name, chain in CHAIN_MAP.items():
            for model in chain:
                assert model in MODEL_REGISTRY, f"{model!r} not in registry (chain {name!r})"

    def test_reasoning_chain_primary_is_nemotron(self):
        from ollama_client import REASONING_CHAIN

        assert REASONING_CHAIN[0] == "glm-5:cloud"

    def test_planning_chain_primary_is_cogito(self):
        from ollama_client import PLANNING_CHAIN

        assert PLANNING_CHAIN[0] == "cogito-2.1:671b-cloud"

    def test_doer_chain_primary_is_minimax(self):
        from ollama_client import DOER_CHAIN

        assert DOER_CHAIN[0] == "minimax-m2.7:cloud"

    def test_coding_chain_primary_is_devstral(self):
        from ollama_client import CODING_CHAIN

        assert CODING_CHAIN[0] == "devstral-2:123b-cloud"

    def test_ethics_chain_primary_is_deepseek(self):
        from ollama_client import ETHICS_CHAIN

        assert ETHICS_CHAIN[0] == "deepseek-v3.2:cloud"

    def test_all_chains_contain_qwen_fallback(self):
        from ollama_client import CHAIN_MAP

        for name, chain in CHAIN_MAP.items():
            assert "qwen3.5:cloud" in chain, f"qwen3.5:cloud missing from {name!r} chain"

    def test_all_chains_contain_nemotron(self):
        from ollama_client import CHAIN_MAP

        for name, chain in CHAIN_MAP.items():
            assert "nemotron-3-super" in chain, f"nemotron-3-super missing from {name!r} chain"

    def test_planning_and_doer_models_are_in_registry(self):
        from ollama_client import MODEL_REGISTRY

        assert "cogito-2.1:671b-cloud" in MODEL_REGISTRY
        assert "minimax-m2.7:cloud" in MODEL_REGISTRY
        assert "glm-5:cloud" in MODEL_REGISTRY
        assert "kimi-k2.5:cloud" in MODEL_REGISTRY
        assert "devstral-2:123b-cloud" in MODEL_REGISTRY


# ============================================================
# CircuitBreaker
# ============================================================


class TestCircuitBreaker:
    def setup_method(self):
        from ollama_client import CircuitBreaker

        CircuitBreaker._instances.clear()

    def test_initially_closed(self):
        from ollama_client import CircuitBreaker

        assert not CircuitBreaker("model-a").is_open

    def test_opens_after_threshold(self):
        from ollama_client import CIRCUIT_FAIL_THRESHOLD, CircuitBreaker

        cb = CircuitBreaker("model-b")
        for _ in range(CIRCUIT_FAIL_THRESHOLD):
            cb.record_failure()
        assert cb.is_open

    def test_success_resets_counter(self):
        from ollama_client import CircuitBreaker

        cb = CircuitBreaker("model-c")
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert not cb.is_open

    def test_reset_closes_circuit(self):
        from ollama_client import CIRCUIT_FAIL_THRESHOLD, CircuitBreaker

        cb = CircuitBreaker("model-d")
        for _ in range(CIRCUIT_FAIL_THRESHOLD):
            cb.record_failure()
        assert cb.is_open
        cb.reset()
        assert not cb.is_open

    def test_singleton_same_model(self):
        from ollama_client import CircuitBreaker

        assert CircuitBreaker("same-model") is CircuitBreaker("same-model")

    def test_different_models_independent(self):
        from ollama_client import CIRCUIT_FAIL_THRESHOLD, CircuitBreaker

        cb1 = CircuitBreaker("independent-1")
        cb2 = CircuitBreaker("independent-2")
        for _ in range(CIRCUIT_FAIL_THRESHOLD):
            cb1.record_failure()
        assert cb1.is_open
        assert not cb2.is_open


# ============================================================
# RetryPolicy
# ============================================================


class TestRetryPolicy:
    def test_no_wait_on_first_attempt(self):
        from ollama_client import RetryPolicy

        rp = RetryPolicy()
        t = time.monotonic()
        rp.wait(1)
        assert time.monotonic() - t < 0.05

    def test_wait_occurs_on_retry(self):
        from ollama_client import RetryPolicy

        rp = RetryPolicy(base=0.01, cap=0.05)
        t = time.monotonic()
        rp.wait(2)
        assert time.monotonic() - t >= 0.005

    def test_cap_enforced(self):
        from ollama_client import RetryPolicy

        rp = RetryPolicy(base=1.0, cap=2.0)
        rp._prev = 100.0
        with patch("random.uniform", return_value=200.0):
            sleep = min(rp._cap, 200.0)
        assert sleep == 2.0

    def test_reset_restores_base(self):
        from ollama_client import RetryPolicy

        rp = RetryPolicy(base=1.0, cap=10.0)
        rp._prev = 9.0
        rp.reset()
        assert rp._prev == 1.0


# ============================================================
# ConnectionMonitor
# ============================================================


class TestConnectionMonitor:
    def setup_method(self):
        from ollama_client import ConnectionMonitor

        ConnectionMonitor._instances.clear()

    def test_initial_success_rate_is_one(self):
        from ollama_client import ConnectionMonitor

        assert ConnectionMonitor("probe-a").success_rate == 1.0

    def test_records_success_and_failure(self):
        from ollama_client import ConnectionMonitor

        mon = ConnectionMonitor("probe-b")
        mon.record(1.0, True)
        mon.record(2.0, False)
        assert 0.4 < mon.success_rate < 0.6

    def test_p50_latency_correct(self):
        from ollama_client import ConnectionMonitor

        mon = ConnectionMonitor("probe-c")
        for t in [1.0, 2.0, 3.0, 4.0, 5.0]:
            mon.record(t, True)
        assert 2.5 < mon.p50_latency < 3.5

    def test_summary_contains_model_name(self):
        from ollama_client import ConnectionMonitor

        mon = ConnectionMonitor("my-special-model")
        assert "my-special-model" in mon.summary()


# ============================================================
# ResponseValidator
# ============================================================


class TestResponseValidator:
    def test_valid_response(self):
        from ollama_client import ResponseValidator

        ok, reason = ResponseValidator.validate("This is a perfectly valid HLF analysis.", "m")
        assert ok is True and reason == ""

    def test_too_short_invalid(self):
        from ollama_client import ResponseValidator

        ok, _ = ResponseValidator.validate("Hi", "m")
        assert ok is False

    def test_empty_invalid(self):
        from ollama_client import ResponseValidator

        ok, _ = ResponseValidator.validate("", "m")
        assert ok is False

    def test_rate_limit_detected(self):
        from ollama_client import ResponseValidator

        ok, reason = ResponseValidator.validate("rate limit exceeded for your account today", "m")
        assert ok is False and "Error body" in reason

    def test_unauthorized_detected(self):
        from ollama_client import ResponseValidator

        ok, _ = ResponseValidator.validate("unauthorized — check your API credentials", "m")
        assert ok is False

    def test_long_valid_response(self):
        from ollama_client import ResponseValidator

        ok, _ = ResponseValidator.validate("x" * 1000, "m")
        assert ok is True


# ============================================================
# StreamingBuffer
# ============================================================


class TestStreamingBuffer:
    def _make_resp(self, ndjson_lines: list[str]) -> MagicMock:
        data = "\n".join(ndjson_lines).encode() + b"\n"
        chunks = [data[i : i + 64] for i in range(0, len(data), 64)] + [b""]
        resp = MagicMock(spec=http.client.HTTPResponse)
        resp.read.side_effect = chunks
        return resp

    def test_reads_complete_stream(self):
        from ollama_client import StreamingBuffer

        lines = [
            json.dumps({"message": {"content": "Hello "}, "done": False}),
            json.dumps({"message": {"content": "world!"}, "done": False}),
            json.dumps({"message": {"content": ""}, "done": True}),
        ]
        content, complete = StreamingBuffer(self._make_resp(lines), "m").read_all()
        assert content == "Hello world!" and complete is True

    def test_missing_done_sentinel(self):
        from ollama_client import StreamingBuffer

        lines = [json.dumps({"message": {"content": "partial"}, "done": False})]
        content, complete = StreamingBuffer(self._make_resp(lines), "m").read_all()
        assert content == "partial" and complete is False

    def test_openai_compat_delta_chunks(self):
        from ollama_client import StreamingBuffer

        lines = [
            json.dumps({"choices": [{"delta": {"content": "compat "}}], "done": False}),
            json.dumps({"choices": [{"delta": {"content": "stream"}}], "done": True}),
        ]
        content, complete = StreamingBuffer(self._make_resp(lines), "m").read_all()
        assert "compat" in content and complete is True

    def test_network_reset_preserves_partial(self):
        from ollama_client import StreamingBuffer

        resp = MagicMock(spec=http.client.HTTPResponse)
        resp.read.side_effect = [
            json.dumps({"message": {"content": "before "}, "done": False}).encode() + b"\n",
            ConnectionResetError("connection reset"),
        ]
        content, complete = StreamingBuffer(resp, "m").read_all()
        assert "before" in content and complete is False

    def test_bad_json_chunk_skipped(self):
        from ollama_client import StreamingBuffer

        good = json.dumps({"message": {"content": "ok"}, "done": True})
        data = b"not-json\n" + good.encode() + b"\n" + b""
        chunks = [data, b""]
        resp = MagicMock(spec=http.client.HTTPResponse)
        resp.read.side_effect = chunks
        content, complete = StreamingBuffer(resp, "m").read_all()
        assert "ok" in content and complete is True


# ============================================================
# FallbackOrchestrator
# ============================================================


class TestFallbackOrchestrator:
    def setup_method(self):
        from ollama_client import CircuitBreaker, ConnectionMonitor

        CircuitBreaker._instances.clear()
        ConnectionMonitor._instances.clear()

    def _streaming_ctx(self, content: str):
        """Build a mock context manager wrapping a streaming HTTP response."""
        data = (
            json.dumps({"message": {"content": content}, "done": False})
            + "\n"
            + json.dumps({"message": {"content": ""}, "done": True})
            + "\n"
        ).encode()
        chunks = [data[i : i + 64] for i in range(0, len(data), 64)] + [b""]
        resp = MagicMock(spec=http.client.HTTPResponse)
        resp.status = 200
        resp.reason = "OK"
        resp.headers = {}
        resp.read.side_effect = chunks
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=resp)
        ctx.__exit__ = MagicMock(return_value=False)
        return ctx

    def test_primary_tier_used_on_success(self):
        from ollama_client import CODING_CHAIN, FallbackOrchestrator

        # Use side_effect lambda so each urlopen call gets a FRESH mock response
        # (return_value reuses the same mock whose read.side_effect gets exhausted)
        with patch(
            "urllib.request.urlopen",
            side_effect=lambda req, timeout=None: self._streaming_ctx("primary tier succeeded OK"),
        ):
            result = FallbackOrchestrator(chain=CODING_CHAIN, api_key="k").complete("sys", "p")
        assert result.tier_index == 0
        assert result.model_used == CODING_CHAIN[0]

    def test_falls_back_on_open_circuit(self):
        from ollama_client import CIRCUIT_FAIL_THRESHOLD, CircuitBreaker, FallbackOrchestrator

        cb = CircuitBreaker("devstral-2:123b-cloud")
        for _ in range(CIRCUIT_FAIL_THRESHOLD):
            cb.record_failure()
        with patch("urllib.request.urlopen", return_value=self._streaming_ctx("fallback ok")):
            result = FallbackOrchestrator(
                chain=["devstral-2:123b-cloud", "nemotron-3-super"],
                api_key="k",
            ).complete("sys", "p")
        assert result.tier_index >= 1
        assert result.model_used != "devstral-2:123b-cloud"

    def test_all_tiers_exhausted_raises(self):
        import urllib.error

        from ollama_client import FallbackOrchestrator

        def fail(req, timeout=None):
            raise urllib.error.HTTPError("", 503, "down", {}, io.BytesIO(b"down"))

        with patch("urllib.request.urlopen", fail):
            with pytest.raises(RuntimeError, match="tiers exhausted"):
                FallbackOrchestrator(
                    chain=["devstral-2:123b-cloud", "qwen3.5:cloud"],
                    api_key="k",
                    max_retries_per_tier=1,
                ).complete("sys", "p")

    def test_audit_trail_has_error_and_success(self):
        import urllib.error

        from ollama_client import FallbackOrchestrator

        calls = [0]

        def mixed(req, timeout=None):
            calls[0] += 1
            if calls[0] == 1:
                raise urllib.error.HTTPError("", 503, "down", {}, io.BytesIO(b"down"))
            return self._streaming_ctx("ok from tier 2")

        with patch("urllib.request.urlopen", mixed):
            result = FallbackOrchestrator(
                chain=["devstral-2:123b-cloud", "nemotron-3-super"],
                api_key="k",
                max_retries_per_tier=1,
            ).complete("sys", "p")
        outcomes = [e["outcome"] for e in result.audit_trail]
        assert "error" in outcomes and "success" in outcomes

    def test_tier_index_correct_after_n_fallbacks(self):
        import urllib.error

        from ollama_client import FallbackOrchestrator

        calls = [0]

        def fail_two_then_succeed(req, timeout=None):
            calls[0] += 1
            if calls[0] <= 2:
                raise urllib.error.HTTPError("", 503, "down", {}, io.BytesIO(b"down"))
            return self._streaming_ctx("third tier wins")

        with patch("urllib.request.urlopen", fail_two_then_succeed):
            result = FallbackOrchestrator(
                chain=["devstral-2:123b-cloud", "nemotron-3-super", "qwen3.5:cloud"],
                api_key="k",
                max_retries_per_tier=1,
            ).complete("sys", "p")
        assert result.tier_index == 2

    def test_health_report_lists_all_models(self):
        from ollama_client import UNIVERSAL_CHAIN, FallbackOrchestrator

        report = FallbackOrchestrator(chain=UNIVERSAL_CHAIN).health_report()
        for model in UNIVERSAL_CHAIN:
            assert model in report

    def test_attempts_count_accumulated_across_tiers(self):
        import urllib.error

        from ollama_client import FallbackOrchestrator

        calls = [0]

        def fail_then_ok(req, timeout=None):
            calls[0] += 1
            if calls[0] < 3:
                raise urllib.error.HTTPError("", 503, "down", {}, io.BytesIO(b"down"))
            # Content must exceed MIN_RESPONSE_CHARS (10) to be considered valid
            return self._streaming_ctx("third tier succeeded successfully")

        with patch("urllib.request.urlopen", fail_then_ok):
            result = FallbackOrchestrator(
                chain=["devstral-2:123b-cloud", "nemotron-3-super", "qwen3.5:cloud"],
                api_key="k",
                max_retries_per_tier=1,
            ).complete("sys", "p")
        assert result.attempts >= 3

    def test_result_includes_latency(self):
        from ollama_client import FallbackOrchestrator

        with patch(
            "urllib.request.urlopen",
            side_effect=lambda req, timeout=None: self._streaming_ctx("x" * 50),
        ):
            result = FallbackOrchestrator(
                chain=["nemotron-3-super"],
                api_key="k",
            ).complete("sys", "p")
        assert result.latency_s >= 0.0


# ============================================================
# Backward-compat shims
# ============================================================


class TestBackwardCompatShims:
    def setup_method(self):
        from ollama_client import CircuitBreaker, ConnectionMonitor

        CircuitBreaker._instances.clear()
        ConnectionMonitor._instances.clear()

    def test_extract_content_native(self):
        from ollama_client import extract_content

        assert extract_content({"message": {"content": "HLF!"}}) == "HLF!"

    def test_extract_content_openai_compat(self):
        from ollama_client import extract_content

        assert extract_content({"choices": [{"message": {"content": "compat"}}]}) == "compat"

    def test_extract_content_compat_key(self):
        from ollama_client import extract_content

        assert extract_content({"_content": "via shim"}) == "via shim"

    def test_call_ollama_auth_raises_runtime_error(self):
        import urllib.error

        from ollama_client import call_ollama

        def fake_401(req, timeout=None):
            raise urllib.error.HTTPError("", 401, "Unauthorized", {}, io.BytesIO(b"Unauthorized"))

        with patch("urllib.request.urlopen", fake_401):
            with pytest.raises(RuntimeError, match="Auth failure"):
                call_ollama("devstral-2:123b-cloud", "sys", "prompt", api_key="bad")

    def test_call_with_fallback_uses_fallback_on_primary_fail(self):
        from ollama_client import CIRCUIT_FAIL_THRESHOLD, CircuitBreaker, call_with_fallback

        cb = CircuitBreaker("devstral-2:123b-cloud")
        for _ in range(CIRCUIT_FAIL_THRESHOLD):
            cb.record_failure()

        data = (
            json.dumps({"message": {"content": "fallback ok"}, "done": False})
            + "\n"
            + json.dumps({"message": {"content": ""}, "done": True})
            + "\n"
        ).encode()
        chunks = [data[i : i + 64] for i in range(0, len(data), 64)] + [b""]
        resp = MagicMock(spec=http.client.HTTPResponse)
        resp.status = 200
        resp.reason = "OK"
        resp.headers = {}
        resp.read.side_effect = chunks
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=resp)
        ctx.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=ctx):
            _, model_used = call_with_fallback(
                "devstral-2:123b-cloud", "nemotron-3-super", "sys", "prompt", api_key="k"
            )
        assert model_used == "nemotron-3-super"
