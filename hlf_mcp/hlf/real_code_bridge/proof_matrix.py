"""
Unified Proof Matrix: aggregate all 3 proof types (equivalence, effect audit,
bytecode roundtrip) into a single aggregated report per fixture.

Provides:
  - ProofMatrixEntry: dataclass holding all 3 proof results for one fixture
  - ProofMatrix: orchestrator that runs all proofs on a set of fixtures
  - FixtureCatalog: discovers .hlf files and extracts metadata / Python expressions
  - ProofMatrixReport: generates markdown / JSON / compact reports
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field, asdict
from typing import Any

from hlf_mcp.hlf.real_code_bridge.equivalence import (
    EquivalenceProver,
    EquivalenceResult,
)
from hlf_mcp.hlf.real_code_bridge.effect_audit import (
    EffectAuditor,
    AuditResult,
)
from hlf_mcp.hlf.real_code_bridge.bytecode_roundtrip import (
    BytecodeRoundtripper,
    RoundtripResult,
)


# ──────────────────────────────────────────────────────────────────────────────
# ProofMatrixEntry
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class ProofMatrixEntry:
    """Aggregated proof results for a single HLF fixture."""

    fixture_id: str
    fixture_path: str
    label: str
    hlf_source: str
    python_code: str = ""

    equivalence_result: EquivalenceResult | None = None
    audit_result: AuditResult | None = None
    roundtrip_result: RoundtripResult | None = None

    error: str = ""

    @property
    def proof_count(self) -> int:
        """Number of proof types that were actually run (non-None results)."""
        count = 0
        if self.equivalence_result is not None:
            count += 1
        if self.audit_result is not None:
            count += 1
        if self.roundtrip_result is not None:
            count += 1
        return count

    @property
    def failed_proofs(self) -> list[str]:
        """Names of proof types that failed (or None if not run)."""
        failed: list[str] = []
        if self.equivalence_result is not None and not self.equivalence_result.passed:
            failed.append("equivalence")
        if self.audit_result is not None and not self.audit_result.passed:
            failed.append("effect_audit")
        if self.roundtrip_result is not None and not self.roundtrip_result.passed:
            failed.append("bytecode_roundtrip")
        return failed

    @property
    def overall_passed(self) -> bool:
        """True only if all non-None results passed. False if any failed or no proofs run."""
        if self.proof_count == 0:
            return False
        results: list[Any] = [
            self.equivalence_result,
            self.audit_result,
            self.roundtrip_result,
        ]
        for r in results:
            if r is not None and not r.passed:
                return False
        return True


# ──────────────────────────────────────────────────────────────────────────────
# FixtureCatalog
# ──────────────────────────────────────────────────────────────────────────────

class FixtureCatalog:
    """Discover HLF fixtures and extract metadata / associated Python expressions."""

    # Patterns for finding Python expressions in HLF comments
    _PYTHON_MARKERS = [
        "PYTHON:",
        "python:",
        "PYTHON_EXPR:",
        "python_expr:",
        "PYTHON_EXPRESSION:",
        "python_expression:",
    ]

    @staticmethod
    def discover_fixtures(directory: str) -> list[dict[str, Any]]:
        """Scan a directory for .hlf files and return metadata for each.

        Returns a list of dicts with keys: fixture_id, path, label, hlf_source, python_code.
        """
        entries: list[dict[str, Any]] = []
        if not os.path.isdir(directory):
            return entries

        for fname in sorted(os.listdir(directory)):
            if not fname.endswith(".hlf"):
                continue
            full_path = os.path.join(directory, fname)
            fixture_id = os.path.splitext(fname)[0]
            try:
                with open(full_path, "r", encoding="utf-8") as fh:
                    hlf_source = fh.read()
            except (OSError, UnicodeDecodeError):
                continue

            # Extract a label from the first comment line or filename
            label = FixtureCatalog._extract_label(hlf_source, fixture_id)

            # Try to find an associated Python expression
            python_code = FixtureCatalog._extract_python_expression(hlf_source)

            entries.append({
                "fixture_id": fixture_id,
                "path": full_path,
                "label": label,
                "hlf_source": hlf_source,
                "python_code": python_code or "",
            })

        return entries

    @staticmethod
    def get_python_expression(fixture_path: str) -> str | None:
        """Read a fixture file and extract any embedded Python expression.

        Also checks for a companion .py file with the same base name.
        """
        if not os.path.isfile(fixture_path):
            return None

        # Read the .hlf file
        try:
            with open(fixture_path, "r", encoding="utf-8") as fh:
                source = fh.read()
        except (OSError, UnicodeDecodeError):
            return None

        # Check for embedded Python expression in the .hlf file
        expr = FixtureCatalog._extract_python_expression(source)
        if expr:
            return expr

        # Check for a companion .py file
        dirname = os.path.dirname(fixture_path)
        base = os.path.splitext(os.path.basename(fixture_path))[0]
        companion_py = os.path.join(dirname, f"{base}.py")
        if os.path.isfile(companion_py):
            try:
                with open(companion_py, "r", encoding="utf-8") as fh:
                    return fh.read().strip()
            except (OSError, UnicodeDecodeError):
                pass

        return None

    @staticmethod
    def catalog_to_matrix_input(
        catalog_entries: list[dict[str, Any]],
    ) -> list[tuple[str, str, str, str]]:
        """Convert catalog entries to (fixture_path, label, hlf_source, python_code) tuples."""
        result: list[tuple[str, str, str, str]] = []
        for entry in catalog_entries:
            result.append((
                entry.get("path", ""),
                entry.get("label", ""),
                entry.get("hlf_source", ""),
                entry.get("python_code", ""),
            ))
        return result

    # ── internal helpers ────────────────────────────────────────────────────

    @staticmethod
    def _extract_label(source: str, fallback: str) -> str:
        """Extract a human-readable label from the first comment line."""
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                # Remove leading '#' and any leading/trailing whitespace
                label = stripped.lstrip("#").strip()
                if label:
                    return label
        return fallback

    @staticmethod
    def _extract_python_expression(source: str) -> str | None:
        """Extract a Python expression from a specially-marked comment."""
        for line in source.splitlines():
            stripped = line.strip()
            if not (stripped.startswith("#") or stripped.startswith("//") or stripped.startswith("--")):
                continue
            # Remove comment prefix
            content = stripped.lstrip("#/ -")
            content = content.strip()
            for marker in FixtureCatalog._PYTHON_MARKERS:
                if content.startswith(marker):
                    expr = content[len(marker):].strip()
                    if expr:
                        return expr
        return None


# ──────────────────────────────────────────────────────────────────────────────
# ProofMatrix
# ──────────────────────────────────────────────────────────────────────────────

class ProofMatrix:
    """Orchestrator that runs all 3 proof types on HLF fixtures and aggregates results."""

    def __init__(
        self,
        equivalence_prover: EquivalenceProver | None = None,
        effect_auditor: EffectAuditor | None = None,
        bytecode_roundtripper: BytecodeRoundtripper | None = None,
    ) -> None:
        self._equivalence = equivalence_prover or EquivalenceProver()
        self._auditor = effect_auditor or EffectAuditor()
        self._roundtripper = bytecode_roundtripper or BytecodeRoundtripper()
        self._entries: list[ProofMatrixEntry] = []

    @property
    def entries(self) -> list[ProofMatrixEntry]:
        """The list of ProofMatrixEntry objects after building the matrix."""
        return list(self._entries)

    def build_entry(
        self,
        fixture_path: str,
        label: str,
        hlf_source: str,
        python_code: str = "",
    ) -> ProofMatrixEntry:
        """Run all 3 proofs on a single fixture and return a ProofMatrixEntry.

        If python_code is empty, the equivalence proof is skipped (set to None).
        If any proof raises an exception, it is captured and the result is set to None.
        """
        fixture_id = os.path.splitext(os.path.basename(fixture_path))[0]

        entry = ProofMatrixEntry(
            fixture_id=fixture_id,
            fixture_path=fixture_path,
            label=label or fixture_id,
            hlf_source=hlf_source,
            python_code=python_code,
        )

        # ── Equivalence proof ──────────────────────────────────────────────
        if python_code:
            try:
                entry.equivalence_result = self._equivalence.prove_equivalence(
                    hlf_source, python_code, label=label or fixture_id
                )
            except Exception as exc:
                entry.equivalence_result = EquivalenceResult(
                    source_label=label or fixture_id,
                    hlf_source=hlf_source,
                    python_code=python_code,
                    hlf_result=None,
                    python_result=None,
                    gas_used=0,
                    passed=False,
                    error=f"Proof matrix error: {exc}",
                )
        else:
            entry.equivalence_result = None

        # ── Effect audit ──────────────────────────────────────────────────
        try:
            entry.audit_result = self._auditor.audit(hlf_source, label=label or fixture_id)
        except Exception as exc:
            entry.audit_result = AuditResult(
                source_label=label or fixture_id,
                declared_effects=[],
                actual_effects=[],
                undeclared_effects=[],
                unexecuted_effects=[],
                matched_effects=[],
                passed=False,
            )
            if not entry.error:
                entry.error = f"Audit error: {exc}"

        # ── Bytecode roundtrip proof ──────────────────────────────────────
        try:
            entry.roundtrip_result = self._roundtripper.prove_roundtrip(
                hlf_source, label=label or fixture_id
            )
        except Exception as exc:
            entry.roundtrip_result = RoundtripResult(
                source_label=label or fixture_id,
                original_sha256="",
                roundtrip_sha256="",
                instruction_count=0,
                constant_count=0,
                original_size=0,
                roundtrip_size=0,
            )
            if not entry.error:
                entry.error = f"Roundtrip error: {exc}"

        return entry

    def build_matrix(self, fixture_dir: str) -> list[ProofMatrixEntry]:
        """Scan a directory for .hlf files and run all 3 proofs on each.

        Returns the list of ProofMatrixEntry objects, also stored in self.entries.
        """
        catalog = FixtureCatalog()
        discovered = catalog.discover_fixtures(fixture_dir)
        entries: list[ProofMatrixEntry] = []

        for item in discovered:
            entry = self.build_entry(
                fixture_path=item["path"],
                label=item["label"],
                hlf_source=item["hlf_source"],
                python_code=item.get("python_code", ""),
            )
            entries.append(entry)

        self._entries = entries
        return entries

    def from_fixture_catalog(self, catalog: FixtureCatalog) -> list[ProofMatrixEntry]:
        """Build the proof matrix from a FixtureCatalog's discovered entries."""
        discovered = catalog.discover_fixtures(".")  # catalog has its own directory context
        # Re-discover using the catalog's directory
        entries: list[ProofMatrixEntry] = []
        for item in discovered:
            entry = self.build_entry(
                fixture_path=item["path"],
                label=item["label"],
                hlf_source=item["hlf_source"],
                python_code=item.get("python_code", ""),
            )
            entries.append(entry)
        self._entries = entries
        return entries

    def summary_stats(self) -> dict[str, Any]:
        """Compute aggregate statistics across all entries.

        Returns a dict with keys:
          total_entries, fully_passing, partially_passing, fully_failing,
          per_proof_type_breakdown, failure_rate, total_proofs_run,
          total_equivalence_run, total_equivalence_passed,
          total_audit_run, total_audit_passed,
          total_roundtrip_run, total_roundtrip_passed,
        """
        entries = self._entries
        total = len(entries)

        fully_passing = 0
        partially_passing = 0
        fully_failing = 0

        eq_run = 0
        eq_passed = 0
        au_run = 0
        au_passed = 0
        rt_run = 0
        rt_passed = 0

        for e in entries:
            results = [e.equivalence_result, e.audit_result, e.roundtrip_result]
            passed_count = sum(1 for r in results if r is not None and r.passed)
            non_none = sum(1 for r in results if r is not None)

            if non_none == 0:
                fully_failing += 1
            elif passed_count == non_none:
                fully_passing += 1
            elif passed_count == 0:
                fully_failing += 1
            else:
                partially_passing += 1

            # Per-proof-type breakdown
            if e.equivalence_result is not None:
                eq_run += 1
                if e.equivalence_result.passed:
                    eq_passed += 1
            if e.audit_result is not None:
                au_run += 1
                if e.audit_result.passed:
                    au_passed += 1
            if e.roundtrip_result is not None:
                rt_run += 1
                if e.roundtrip_result.passed:
                    rt_passed += 1

        # "Fully failing" means at least one proof was run and all failed, OR no proofs run
        # Recalculate: if an entry has at least one non-None result:
        fully_failing_recalc = 0
        for e in entries:
            results = [e.equivalence_result, e.audit_result, e.roundtrip_result]
            non_none = sum(1 for r in results if r is not None)
            if non_none == 0:
                fully_failing_recalc += 1
            else:
                passed_count = sum(1 for r in results if r is not None and r.passed)
                if passed_count == non_none:
                    pass  # already counted as fully_passing
                elif passed_count == 0:
                    fully_failing_recalc += 1
                # else partially_passing

        # Re-run the classification more carefully
        fully_passing = 0
        partially_passing = 0
        fully_failing = 0
        for e in entries:
            results = [e.equivalence_result, e.audit_result, e.roundtrip_result]
            non_none = sum(1 for r in results if r is not None)
            if non_none == 0:
                fully_failing += 1
            else:
                passed_count = sum(1 for r in results if r is not None and r.passed)
                if passed_count == non_none:
                    fully_passing += 1
                elif passed_count == 0:
                    fully_failing += 1
                else:
                    partially_passing += 1

        total_proofs_run = eq_run + au_run + rt_run
        total_proofs_passed = eq_passed + au_passed + rt_passed

        return {
            "total_entries": total,
            "fully_passing": fully_passing,
            "partially_passing": partially_passing,
            "fully_failing": fully_failing,
            "per_proof_type_breakdown": {
                "equivalence": {"run": eq_run, "passed": eq_passed},
                "effect_audit": {"run": au_run, "passed": au_passed},
                "bytecode_roundtrip": {"run": rt_run, "passed": rt_passed},
            },
            "failure_rate": (
                round((total_proofs_run - total_proofs_passed) / total_proofs_run * 100, 1)
                if total_proofs_run > 0
                else 100.0
            ),
            "total_proofs_run": total_proofs_run,
            "total_proofs_passed": total_proofs_passed,
            "total_equivalence_run": eq_run,
            "total_equivalence_passed": eq_passed,
            "total_audit_run": au_run,
            "total_audit_passed": au_passed,
            "total_roundtrip_run": rt_run,
            "total_roundtrip_passed": rt_passed,
        }

    def to_csv(self, entries: list[ProofMatrixEntry] | None = None) -> str:
        """Generate CSV representation of the proof matrix.

        Columns: fixture_id, label, equivalence_passed, audit_passed,
        roundtrip_passed, overall_passed, errors
        """
        target = entries if entries is not None else self._entries
        lines = ["fixture_id,label,equivalence_passed,audit_passed,roundtrip_passed,overall_passed,errors"]
        for e in target:
            eq_passed = _bool_to_csv(e.equivalence_result.passed if e.equivalence_result else None)
            au_passed = _bool_to_csv(e.audit_result.passed if e.audit_result else None)
            rt_passed = _bool_to_csv(e.roundtrip_result.passed if e.roundtrip_result else None)
            overall = str(e.overall_passed).lower()

            # Collect error strings
            error_parts: list[str] = []
            if e.error:
                error_parts.append(e.error)
            if e.equivalence_result and e.equivalence_result.error:
                error_parts.append(f"eq: {e.equivalence_result.error}")
            errors = "; ".join(error_parts).replace('"', '""')
            if errors:
                errors = f'"{errors}"'

            line = (
                f"{e.fixture_id},{e.label},{eq_passed},{au_passed},{rt_passed},{overall},{errors}"
            )
            lines.append(line)
        return "\n".join(lines) + "\n"

    def to_markdown_table(self, entries: list[ProofMatrixEntry] | None = None) -> str:
        """Generate a markdown table representation of the proof matrix."""
        target = entries if entries is not None else self._entries
        header = "| Fixture | Label | Equivalence | Effect Audit | Bytecode Roundtrip | Overall |"
        sep = "|---------|-------|-------------|--------------|-------------------|---------|"
        rows = [header, sep]
        for e in target:
            eq = _result_icon(e.equivalence_result)
            au = _result_icon(e.audit_result)
            rt = _result_icon(e.roundtrip_result)
            overall = "✅" if e.overall_passed else "❌"

            rows.append(
                f"| `{e.fixture_id}` | {e.label} | {eq} | {au} | {rt} | {overall} |"
            )
        return "\n".join(rows) + "\n"

    def to_json(self, entries: list[ProofMatrixEntry] | None = None) -> str:
        """Generate a JSON array representation of the proof matrix."""
        target = entries if entries is not None else self._entries
        output: list[dict[str, Any]] = []
        for e in target:
            item: dict[str, Any] = {
                "fixture_id": e.fixture_id,
                "fixture_path": e.fixture_path,
                "label": e.label,
                "hlf_source": e.hlf_source,
                "python_code": e.python_code,
                "overall_passed": e.overall_passed,
                "failed_proofs": e.failed_proofs,
                "proof_count": e.proof_count,
                "error": e.error,
            }
            if e.equivalence_result:
                item["equivalence"] = e.equivalence_result.output
            else:
                item["equivalence"] = None
            if e.audit_result:
                item["effect_audit"] = e.audit_result.output
            else:
                item["effect_audit"] = None
            if e.roundtrip_result:
                item["bytecode_roundtrip"] = {
                    "source_label": e.roundtrip_result.source_label,
                    "original_sha256": e.roundtrip_result.original_sha256,
                    "roundtrip_sha256": e.roundtrip_result.roundtrip_sha256,
                    "instruction_count": e.roundtrip_result.instruction_count,
                    "constant_count": e.roundtrip_result.constant_count,
                    "original_size": e.roundtrip_result.original_size,
                    "roundtrip_size": e.roundtrip_result.roundtrip_size,
                    "passed": e.roundtrip_result.passed,
                }
            else:
                item["bytecode_roundtrip"] = None
            output.append(item)
        return json.dumps(output, indent=2, default=str)


# ──────────────────────────────────────────────────────────────────────────────
# ProofMatrixReport
# ──────────────────────────────────────────────────────────────────────────────

class ProofMatrixReport:
    """Generate formatted reports from the proof matrix."""

    def __init__(self, matrix: ProofMatrix | None = None) -> None:
        self._matrix = matrix or ProofMatrix()

    @property
    def matrix(self) -> ProofMatrix:
        return self._matrix

    def generate(self, directory: str) -> str:
        """Generate a full markdown report: header + summary stats + per-fixture table.

        Reads the fixture directory, builds the matrix, and returns markdown.
        """
        self._matrix.build_matrix(directory)
        stats = self._matrix.summary_stats()
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())

        lines: list[str] = []
        lines.append(f"# HLF Proof Matrix Report")
        lines.append(f"")
        lines.append(f"**Generated:** {timestamp}")
        lines.append(f"**Fixture directory:** `{directory}`")
        lines.append(f"")
        lines.append(f"## Summary Statistics")
        lines.append(f"")
        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|-------|")
        lines.append(f"| Total fixtures | {stats['total_entries']} |")
        lines.append(f"| Fully passing (all proofs) | {stats['fully_passing']} |")
        lines.append(f"| Partially passing | {stats['partially_passing']} |")
        lines.append(f"| Fully failing | {stats['fully_failing']} |")
        lines.append(f"| Total proofs run | {stats['total_proofs_run']} |")
        lines.append(f"| Total proofs passed | {stats['total_proofs_passed']} |")
        lines.append(f"| Failure rate | {stats['failure_rate']}% |")
        lines.append(f"")

        breakdown = stats["per_proof_type_breakdown"]
        lines.append(f"### Per-Proof-Type Breakdown")
        lines.append(f"")
        lines.append(f"| Proof Type | Run | Passed | Pass Rate |")
        lines.append(f"|------------|-----|--------|-----------|")
        for proof_type, counts in breakdown.items():
            run = counts["run"]
            passed = counts["passed"]
            rate = f"{round(passed / run * 100, 1)}%" if run > 0 else "N/A"
            label = proof_type.replace("_", " ").title()
            lines.append(f"| {label} | {run} | {passed} | {rate} |")
        lines.append(f"")

        lines.append(f"## Per-Fixture Results")
        lines.append(f"")
        lines.append(self._matrix.to_markdown_table())
        return "\n".join(lines)

    def generate_json(self, directory: str) -> str:
        """Generate a full JSON report."""
        self._matrix.build_matrix(directory)
        stats = self._matrix.summary_stats()
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        report: dict[str, Any] = {
            "report_type": "proof_matrix",
            "generated": timestamp,
            "fixture_directory": directory,
            "summary": stats,
            "entries": json.loads(self._matrix.to_json()),
        }
        return json.dumps(report, indent=2, default=str)

    def generate_compact(self, directory: str) -> str:
        """Generate a one-line-per-fixture compact summary.

        Format: fixture_id | E:PASS/FAIL/- | A:PASS/FAIL/- | R:PASS/FAIL/- | OVERALL
        """
        self._matrix.build_matrix(directory)
        lines: list[str] = []
        lines.append(f"# Compact Proof Matrix — {directory}")
        lines.append(f"# Format: fixture_id | E(quivalence) | A(udit) | R(oundtrip) | OVERALL")
        lines.append("")

        for e in self._matrix.entries:
            eq = _compact_icon(e.equivalence_result)
            au = _compact_icon(e.audit_result)
            rt = _compact_icon(e.roundtrip_result)
            overall = "PASS" if e.overall_passed else "FAIL"
            lines.append(f"{e.fixture_id:30s} | E:{eq:4s} | A:{au:4s} | R:{rt:4s} | {overall}")

        return "\n".join(lines) + "\n"


# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────────────

def _bool_to_csv(value: bool | None) -> str:
    """Convert a boolean/None to a CSV-safe string."""
    if value is None:
        return "N/A"
    return str(value).lower()


def _result_icon(result: Any) -> str:
    """Return a markdown icon for a proof result."""
    if result is None:
        return "—"
    return "✅" if result.passed else "❌"


def _compact_icon(result: Any) -> str:
    """Return a compact PASS/FAIL/- indicator."""
    if result is None:
        return "-"
    return "PASS" if result.passed else "FAIL"
