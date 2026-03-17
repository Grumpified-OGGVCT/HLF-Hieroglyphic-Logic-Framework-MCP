"""
Tests for scripts/fork_compliance_check.py and governance/license_revocation.py

fork_compliance_check.py:
  - Compliant repo passes all hard checks
  - Missing required file triggers a hard failure
  - Missing recommended file is a warning, not a hard failure
  - Low ALIGN rule count is a hard failure
  - Missing capsule tier is a hard failure
  - Missing HIL gate is a warning, not a hard failure
  - JSON output is valid
  - ComplianceReport.to_dict() shape

license_revocation.py:
  - warn() creates a WARNING entry
  - revoke() requires a prior warning
  - revoke() without warning raises EntityNotWarned
  - reinstate() clears revoked status
  - audit() records a routine check
  - verify_chain() passes on unmodified ledger
  - verify_chain() detects tampered trace_id
  - is_revoked() / has_warning() helpers
  - export_list() returns dicts
  - Unknown clause raises ClauseUnknown
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from governance.license_revocation import (
    ClauseUnknown,
    EntityNotWarned,
    EntryType,
    RevocationLedger,
)
from scripts.fork_compliance_check import run_compliance_check

_REPO_ROOT = Path(__file__).resolve().parent.parent

# ─────────────────────────────────────────────────────────────────────────────
# Fork Compliance Check Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestForkComplianceCheck:
    """Runs the compliance checker against the live repo root."""

    @pytest.fixture(autouse=True)
    def repo_root(self) -> Path:
        self.root = _REPO_ROOT
        return self.root

    def test_live_repo_passes_hard_checks(self) -> None:
        report = run_compliance_check(self.root)
        assert report.passed, (
            "Live repo failed hard compliance checks:\n"
            + "\n".join(r.message for r in report.hard_failures)
        )

    def test_live_repo_has_no_required_file_failures(self) -> None:
        report = run_compliance_check(self.root)
        hard_names = {r.name for r in report.hard_failures}
        for name in hard_names:
            assert not name.startswith("required_file:"), (
                f"Required file check failed: {name}"
            )

    def test_report_passed_checks_not_empty(self) -> None:
        report = run_compliance_check(self.root)
        assert len(report.passed_checks) > 0

    def test_to_dict_has_expected_keys(self) -> None:
        report = run_compliance_check(self.root)
        d = report.to_dict()
        assert "fork_path"     in d
        assert "passed"        in d
        assert "hard_failures" in d
        assert "warnings"      in d
        assert "passed_checks" in d
        assert "summary"       in d
        assert "hard_failures" in d["summary"]
        assert "warnings"      in d["summary"]
        assert "passed"        in d["summary"]

    def test_to_dict_is_json_serialisable(self) -> None:
        report = run_compliance_check(self.root)
        raw = json.dumps(report.to_dict())
        assert isinstance(json.loads(raw), dict)

    def test_missing_required_file_produces_hard_failure(self, tmp_path: Path) -> None:
        # Empty directory — all required files missing
        report = run_compliance_check(tmp_path)
        assert not report.passed
        assert len(report.hard_failures) > 0
        names = {r.name for r in report.hard_failures}
        assert any(n.startswith("required_file:") for n in names)

    def test_missing_required_file_includes_remediation(self, tmp_path: Path) -> None:
        report = run_compliance_check(tmp_path)
        for r in report.hard_failures:
            if r.name.startswith("required_file:"):
                assert r.remediation, "Hard failures must include remediation steps"
                break

    def test_missing_recommended_file_is_warning_not_hard(self, tmp_path: Path) -> None:
        # Populate all REQUIRED files so hard checks pass, but omit recommended ones
        required_paths = [
            "HLF_ETHICAL_GOVERNOR.md",
            "governance/align_rules.json",
            "hlf_mcp/hlf/ethics/constitution.py",
            "hlf_mcp/hlf/ethics/governor.py",
            "hlf_mcp/hlf/capsules.py",
        ]
        align_rules = {
            "version": "1.0.0",
            "rules": [
                {"id": f"ALIGN-00{i}", "name": f"rule_{i}", "pattern": f"pattern{i}",
                 "action": "warn", "description": f"Rule {i}"}
                for i in range(1, 6)
            ],
        }
        capsule_text = "hearth\nforge\nsovereign\n"

        for rel in required_paths:
            p = tmp_path / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            if rel == "governance/align_rules.json":
                p.write_text(json.dumps(align_rules))
            elif rel == "hlf_mcp/hlf/capsules.py":
                p.write_text(capsule_text)
            else:
                p.write_text(f"# {rel} placeholder\nTRANSPARENT\nHUMAN-FIRST\nNON-REDUCTIVE\n")

        report = run_compliance_check(tmp_path)
        # Should pass hard checks (no hard_failures)
        assert report.passed, (
            "Expected to pass with required files present; hard_failures="
            + str([r.name for r in report.hard_failures])
        )

    def test_low_align_rules_is_hard_failure(self, tmp_path: Path) -> None:
        align_path = tmp_path / "governance" / "align_rules.json"
        align_path.parent.mkdir(parents=True, exist_ok=True)
        align_path.write_text(json.dumps({"rules": [{"id": "ALIGN-001"}]}))

        report = run_compliance_check(tmp_path)
        names = {r.name for r in report.hard_failures}
        assert "align_rule_count" in names

    def test_sufficient_align_rules_passes(self, tmp_path: Path) -> None:
        align_path = tmp_path / "governance" / "align_rules.json"
        align_path.parent.mkdir(parents=True, exist_ok=True)
        rules = [{"id": f"ALIGN-00{i}"} for i in range(1, 6)]
        align_path.write_text(json.dumps({"rules": rules}))

        from scripts.fork_compliance_check import check_align_rules
        result = check_align_rules(tmp_path)
        assert result.passed

    def test_missing_capsule_tier_is_hard_failure(self, tmp_path: Path) -> None:
        caps_path = tmp_path / "hlf_mcp" / "hlf" / "capsules.py"
        caps_path.parent.mkdir(parents=True, exist_ok=True)
        # Only define two of the three tiers — third tier intentionally absent
        caps_path.write_text("hearth\nforge\n# third tier not defined here\n")

        from scripts.fork_compliance_check import check_capsule_tiers
        result = check_capsule_tiers(tmp_path)
        assert not result.passed
        assert result.level == "hard"
        assert "sovereign" in result.message

    def test_all_capsule_tiers_passes(self, tmp_path: Path) -> None:
        caps_path = tmp_path / "hlf_mcp" / "hlf" / "capsules.py"
        caps_path.parent.mkdir(parents=True, exist_ok=True)
        caps_path.write_text("hearth\nforge\nsovereign\n")

        from scripts.fork_compliance_check import check_capsule_tiers
        result = check_capsule_tiers(tmp_path)
        assert result.passed

    def test_missing_hil_gate_is_warning_not_hard(self, tmp_path: Path) -> None:
        dispatch = tmp_path / "hlf_mcp" / "hlf" / "tool_dispatch.py"
        dispatch.parent.mkdir(parents=True, exist_ok=True)
        dispatch.write_text("# tool dispatch without HIL\ndef dispatch(): pass\n")

        from scripts.fork_compliance_check import check_hil_gate
        result = check_hil_gate(tmp_path)
        assert not result.passed
        assert result.level == "warn"   # warning, not hard block


# ─────────────────────────────────────────────────────────────────────────────
# License Revocation Ledger Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestRevocationLedger:
    def setup_method(self) -> None:
        self.ledger = RevocationLedger()

    # ── warn ─────────────────────────────────────────────────────────────────

    def test_warn_creates_warning_entry(self) -> None:
        entry = self.ledger.warn(
            entity    = "github.com/test-fork",
            clause_id = "HLF-ETHICS-001",
            evidence  = {"removed_file": "HLF_ETHICAL_GOVERNOR.md"},
            operator  = "monitor",
        )
        assert entry.entry_type == EntryType.WARNING
        assert entry.entity    == "github.com/test-fork"
        assert entry.clause_id == "HLF-ETHICS-001"
        assert entry.trace_id
        assert entry.prev_hash

    def test_warn_records_operator(self) -> None:
        entry = self.ledger.warn(
            entity="fork", clause_id="HLF-ETHICS-001", operator="alice"
        )
        assert entry.operator == "alice"

    def test_warn_sets_appealable_true(self) -> None:
        entry = self.ledger.warn(entity="fork", clause_id="HLF-ETHICS-001")
        assert entry.appealable is True

    def test_warn_unknown_clause_raises(self) -> None:
        with pytest.raises(ClauseUnknown):
            self.ledger.warn(entity="fork", clause_id="TOTALLY-UNKNOWN-CLAUSE-XYZ")

    # ── revoke ────────────────────────────────────────────────────────────────

    def test_revoke_requires_prior_warning(self) -> None:
        with pytest.raises(EntityNotWarned):
            self.ledger.revoke(
                entity="fork-never-warned",
                clause_id="HLF-ETHICS-001",
                operator="alice",
            )

    def test_revoke_after_warning_succeeds(self) -> None:
        self.ledger.warn(entity="fork", clause_id="HLF-ETHICS-001", operator="monitor")
        entry = self.ledger.revoke(
            entity="fork", clause_id="HLF-ETHICS-001", operator="alice",
            notes="No response after 14 days."
        )
        assert entry.entry_type == EntryType.REVOCATION
        assert "fork" in entry.description

    def test_revoke_sets_is_revoked(self) -> None:
        self.ledger.warn(entity="fork", clause_id="HLF-ETHICS-001")
        self.ledger.revoke(entity="fork", clause_id="HLF-ETHICS-001", operator="alice")
        assert self.ledger.is_revoked("fork") is True

    def test_not_revoked_before_warning(self) -> None:
        assert self.ledger.is_revoked("unknown-entity") is False

    # ── reinstate ─────────────────────────────────────────────────────────────

    def test_reinstate_clears_revoked_status(self) -> None:
        self.ledger.warn(entity="fork", clause_id="HLF-ETHICS-001")
        self.ledger.revoke(entity="fork", clause_id="HLF-ETHICS-001", operator="alice")
        assert self.ledger.is_revoked("fork") is True

        self.ledger.reinstate(
            entity="fork", operator="alice", notes="Files restored."
        )
        assert self.ledger.is_revoked("fork") is False

    def test_reinstate_creates_reinstate_entry(self) -> None:
        entry = self.ledger.reinstate(entity="fork", operator="alice")
        assert entry.entry_type == EntryType.REINSTATE

    # ── audit ─────────────────────────────────────────────────────────────────

    def test_audit_creates_audit_entry(self) -> None:
        entry = self.ledger.audit(entity="fork", operator="monitor")
        assert entry.entry_type == EntryType.AUDIT
        assert entry.entity == "fork"

    # ── chain verification ────────────────────────────────────────────────────

    def test_verify_chain_passes_on_clean_ledger(self) -> None:
        self.ledger.warn(entity="fork-a", clause_id="HLF-ETHICS-001")
        self.ledger.warn(entity="fork-b", clause_id="HLF-ETHICS-002")
        ok, errors = self.ledger.verify_chain()
        assert ok is True
        assert errors == []

    def test_verify_chain_detects_tampered_trace_id(self) -> None:
        self.ledger.warn(entity="fork-a", clause_id="HLF-ETHICS-001")
        # Tamper with the trace_id
        self.ledger._entries[0].trace_id = "0" * 64
        ok, errors = self.ledger.verify_chain()
        assert ok is False
        assert len(errors) > 0

    def test_verify_chain_detects_tampered_prev_hash(self) -> None:
        self.ledger.warn(entity="fork-a", clause_id="HLF-ETHICS-001")
        self.ledger.warn(entity="fork-b", clause_id="HLF-ETHICS-002")

        self.ledger._entries[1].prev_hash = "f" * 64

        ok, errors = self.ledger.verify_chain()
        assert ok is False
        assert any("prev_hash mismatch" in error for error in errors)

    def test_verify_chain_detects_tampered_evidence_hash(self) -> None:
        self.ledger.warn(
            entity="fork-a",
            clause_id="HLF-ETHICS-001",
            evidence={"removed_file": "HLF_ETHICAL_GOVERNOR.md"},
        )

        self.ledger._entries[0].evidence["removed_file"] = "OTHER.md"

        ok, errors = self.ledger.verify_chain()
        assert ok is False
        assert any("evidence_hash mismatch" in error for error in errors)

    def test_verify_chain_empty_ledger_passes(self) -> None:
        ok, errors = self.ledger.verify_chain()
        assert ok is True
        assert errors == []

    # ── helpers ───────────────────────────────────────────────────────────────

    def test_has_warning_true_after_warn(self) -> None:
        self.ledger.warn(entity="fork", clause_id="HLF-ETHICS-001")
        assert self.ledger.has_warning("fork") is True

    def test_has_warning_false_before_warn(self) -> None:
        assert self.ledger.has_warning("never-warned") is False

    def test_entries_for_filters_by_entity(self) -> None:
        self.ledger.warn(entity="fork-a", clause_id="HLF-ETHICS-001")
        self.ledger.warn(entity="fork-b", clause_id="HLF-ETHICS-001")
        self.ledger.warn(entity="fork-a", clause_id="HLF-ETHICS-002")

        a_entries = self.ledger.entries_for("fork-a")
        assert len(a_entries) == 2
        assert all(e.entity == "fork-a" for e in a_entries)

    def test_all_entries_returns_all(self) -> None:
        self.ledger.warn(entity="fork-a", clause_id="HLF-ETHICS-001")
        self.ledger.warn(entity="fork-b", clause_id="HLF-ETHICS-001")
        assert len(self.ledger.all_entries()) == 2

    # ── export ────────────────────────────────────────────────────────────────

    def test_export_list_returns_dicts(self) -> None:
        self.ledger.warn(entity="fork", clause_id="HLF-ETHICS-001")
        data = self.ledger.export_list()
        assert isinstance(data, list)
        assert len(data) == 1
        assert "entry_id"   in data[0]
        assert "entry_type" in data[0]
        assert "trace_id"   in data[0]

    def test_export_list_is_json_serialisable(self) -> None:
        self.ledger.warn(entity="fork", clause_id="HLF-ETHICS-001")
        raw = json.dumps(self.ledger.export_list())
        assert isinstance(json.loads(raw), list)

    def test_export_jsonl_writes_file(self, tmp_path: Path) -> None:
        self.ledger.warn(entity="fork-a", clause_id="HLF-ETHICS-001")
        out = tmp_path / "ledger.jsonl"
        self.ledger.export_jsonl(out)
        lines = [line for line in out.read_text().splitlines() if line.strip()]
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert parsed["entity"] == "fork-a"

    def test_export_jsonl_multiple_entries(self, tmp_path: Path) -> None:
        for i in range(3):
            self.ledger.audit(entity=f"fork-{i}", operator="monitor")
        out = tmp_path / "ledger.jsonl"
        self.ledger.export_jsonl(out)
        lines = [line for line in out.read_text().splitlines() if line.strip()]
        assert len(lines) == 3
