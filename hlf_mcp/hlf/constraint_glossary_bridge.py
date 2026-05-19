"""
Constraint Glossary Bridge — maps the frozen A+ CONSTRAINT_GLOSSARY.md
into the HLF Ж-glyph constraint system for runtime enforcement.

The CONSTRAINT_GLOSSARY.md defines what agents must PRODUCE (output quality).
The constraints.hlf defines what agents may DO (tool safety).
These are complementary domains. This bridge unifies them.

Usage:
    bridge = ConstraintGlossaryBridge.from_markdown("docs/CONSTRAINT_GLOSSARY.md")
    violations = bridge.check_output(agent_id="CartService", files={"services/cartService.js": content})
    for v in violations:
        print(f"{v.constraint}: {v.message}")
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class GlossaryConstraint:
    """A single constraint from the frozen glossary."""
    tag: str
    category: str  # cross-cutting | ownership | naming | agent-specific | architecture
    definition: str
    applies_to: list[str] = field(default_factory=list)  # agent IDs or "*" for all


@dataclass
class ConstraintViolation:
    """A detected violation of a glossary constraint."""
    constraint: str
    category: str
    agent_id: str
    file_path: str
    message: str
    severity: str = "error"  # error | warning | info


class ConstraintGlossaryBridge:
    """Bridge from frozen constraint glossary to runtime enforcement.

    Parses CONSTRAINT_GLOSSARY.md into structured constraint rules,
    then checks agent output files against those rules.
    """

    def __init__(self) -> None:
        self._constraints: list[GlossaryConstraint] = []
        self._by_tag: dict[str, GlossaryConstraint] = {}
        self._version: str = "1.0"

    @classmethod
    def from_markdown(cls, path: str | Path) -> "ConstraintGlossaryBridge":
        """Parse CONSTRAINT_GLOSSARY.md into a bridge instance."""
        bridge = cls()
        bridge._parse_markdown(Path(path))
        return bridge

    @classmethod
    def from_embedded(cls) -> "ConstraintGlossaryBridge":
        """Load from the packaged glossary in the HLF_MCP docs directory."""
        import os
        possible_paths = [
            Path(os.path.dirname(__file__)).parent.parent / "docs" / "CONSTRAINT_GLOSSARY.md",
            Path("docs") / "CONSTRAINT_GLOSSARY.md",
        ]
        for p in possible_paths:
            if p.exists():
                return cls.from_markdown(p)
        return cls()  # empty, no constraints loaded

    # ── Parsing ────────────────────────────────────────────────────────────

    def _parse_markdown(self, path: Path) -> None:
        """Parse the glossary markdown into structured constraints.

        Handles two table formats found in the glossary:
        1. | Tag | Description |  (architecture table)
        2. | Tag | v1.0 Definition |  (all other tables)
        """
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()

        current_category = "unknown"
        in_table = False
        table_header_seen = False

        for line in lines:
            stripped = line.strip()

            # Detect category headings: ## Cross-Cutting Constraints, ## SchemaDesigner Constraints, etc.
            if stripped.startswith("## "):
                current_category = stripped[3:].lower().replace(" ", "_").replace("-", "_")
                in_table = False
                table_header_seen = False
                continue

            # Detect table start — any row starting with | Tag or | **Tag
            if re.match(r'^\|\s*(?:\*\*)?Tag(?:\*\*)?\s*\|', stripped):
                in_table = True
                table_header_seen = True
                continue

            # Table separator row: |--- or |----- or |:---|
            if in_table and re.match(r'^\|[\s\-:]+(\|[\s\-:]+)*\|?\s*$', stripped):
                continue

            # Table data row
            if in_table and table_header_seen and stripped.startswith("|"):
                parts = [p.strip() for p in stripped.split("|")]
                # Remove leading/trailing empty parts from split
                parts = [p for p in parts if p]
                if len(parts) < 2:
                    continue

                tag = parts[0].strip("*").strip("`").strip()
                definition = parts[1].strip()

                # Skip header rows, empty rows, and cross-reference-only entries
                if not tag or tag.lower() in ("tag", "description", "v1.0 definition"):
                    continue
                if definition.lower().startswith("see cross-cutting above"):
                    continue  # This is an index entry, not a real definition

                constraint = GlossaryConstraint(
                    tag=tag,
                    category=current_category,
                    definition=definition,
                )
                self._constraints.append(constraint)
                self._by_tag[tag] = constraint

            # Exit table on blank line (but not on lines with content)
            if in_table and not stripped:
                in_table = False
                table_header_seen = False

    @property
    def all_tags(self) -> list[str]:
        return [c.tag for c in self._constraints]

    @property
    def all_constraints(self) -> list[GlossaryConstraint]:
        return list(self._constraints)

    @property
    def version(self) -> str:
        return self._version

    def get(self, tag: str) -> GlossaryConstraint | None:
        return self._by_tag.get(tag)

    def by_category(self, category: str) -> list[GlossaryConstraint]:
        cat = category.lower()
        return [c for c in self._constraints if c.category == cat]

    # ── Output Checking ────────────────────────────────────────────────────

    def check_file(self, agent_id: str, filepath: str, content: str,
                   agent_constraints: list[str] | None = None) -> list[ConstraintViolation]:
        """Check a single file against applicable glossary constraints.

        Args:
            agent_id: The agent that produced this file (e.g. "CartService")
            filepath: Relative path within the output (e.g. "services/cartService.js")
            content: The file content as a string
            agent_constraints: The constraint tags that apply to this agent

        Returns:
            List of ConstraintViolation objects (empty if all pass)
        """
        violations: list[ConstraintViolation] = []

        # Determine applicable constraints
        applicable = agent_constraints or []
        for tag in applicable:
            constraint = self._by_tag.get(tag)
            if constraint is None:
                continue

            # Check specific constraint rules
            checker = getattr(self, f"_check_{tag.lower().replace('-', '_')}", None)
            if checker:
                result = checker(agent_id, filepath, content)
                if result:
                    violations.append(ConstraintViolation(
                        constraint=tag,
                        category=constraint.category,
                        agent_id=agent_id,
                        file_path=filepath,
                        message=result,
                    ))

        return violations

    def check_batch(self, agent_id: str, files: dict[str, str],
                    constraints: list[str] | None = None) -> list[ConstraintViolation]:
        """Check all files produced by an agent against its constraints."""
        all_violations: list[ConstraintViolation] = []
        for filepath, content in files.items():
            all_violations.extend(
                self.check_file(agent_id, filepath, content, constraints)
            )
        return all_violations

    # ── Built-in Constraint Checkers ───────────────────────────────────────

    def _check_commonjs(self, agent_id: str, filepath: str, content: str) -> str | None:
        """Check that file uses CommonJS (require/module.exports), not ES modules."""
        if not filepath.endswith(".js"):
            return None
        # Check for ES module import (only flags if it's the dominant pattern)
        es_imports = len(re.findall(r'\bimport\s+\{', content))
        es_exports = len(re.findall(r'\bexport\s+(default|const|function|class)', content))
        cjs_requires = len(re.findall(r'\brequire\s*\(', content))
        cjs_exports = len(re.findall(r'\bmodule\.exports', content))

        if es_imports > cjs_requires and es_imports > 0:
            return f"Uses ES module imports ({es_imports}) instead of require()"
        if es_exports > 0 and cjs_exports == 0 and es_exports >= 2:
            return f"Uses ES module exports ({es_exports}) instead of module.exports"
        return None

    def _check_null_on_missing(self, agent_id: str, filepath: str, content: str) -> str | None:
        """Check that findById returns null on missing, doesn't throw."""
        if "findById" not in content:
            return None
        # Flag patterns that throw instead of returning null
        throwing_patterns = [
            r'throw\s+new\s+Error.*[Nn]ot\s+[Ff]ound',
            r'throw\s+new\s+Error.*does\s+not\s+exist',
        ]
        has_null_return = bool(re.search(r'return\s+null', content))
        has_throw = any(re.search(p, content) for p in throwing_patterns)

        if has_throw and not has_null_return:
            return "findById appears to throw on missing records instead of returning null"
        return None

    def _check_no_install(self, agent_id: str, filepath: str, content: str) -> str | None:
        """Flag any npm install commands in agent output."""
        if re.search(r'npm\s+(install|i)\b', content):
            return "Contains 'npm install' — agents must not run side effects"
        return None

    def _check_ownership(self, agent_id: str, filepath: str, content: str,
                         owned_dir: str) -> str | None:
        """Check that agent doesn't write to another agent's owned directory."""
        norm_path = filepath.replace("\\", "/")
        norm_owned = owned_dir.replace("\\", "/")

        if not norm_path.startswith(norm_owned):
            return None  # Not in the owned directory, skip

        return None  # In owned directory — allowed

    def check_ownership_violations(self, agent_id: str, files: dict[str, str],
                                   owned_dirs: list[str] | None = None,
                                   forbidden_dirs: list[str] | None = None) -> list[ConstraintViolation]:
        """Check ownership constraints: agents must not write to other agents' directories."""
        violations: list[ConstraintViolation] = []

        forbidden = forbidden_dirs or []
        owned = owned_dirs or []

        for filepath in files:
            norm = filepath.replace("\\", "/")
            # Check forbidden directories
            for fdir in forbidden:
                if norm.startswith(fdir.replace("\\", "/")):
                    violations.append(ConstraintViolation(
                        constraint="OWNERSHIP",
                        category="ownership",
                        agent_id=agent_id,
                        file_path=filepath,
                        message=f"Agent {agent_id} wrote to {filepath} in forbidden directory {fdir}",
                        severity="error",
                    ))

        return violations

    # ── Ж-Glyph Manifest Generation ─────────────────────────────────────────

    def to_glyph_manifest(self) -> list[dict[str, Any]]:
        """Convert glossary constraints into Ж-glyph constraint manifest entries.

        These complement the existing constraints.hlf entries by adding
        output-quality checks to the tool-safety checks.
        """
        manifest: list[dict[str, Any]] = []

        # Map each glossary constraint to a Ж-glyph action
        for c in self._constraints:
            entry = {
                "source": "constraint_glossary_v1",
                "tag": c.tag,
                "category": c.category,
                "definition": c.definition,
                "glyph_action": self._map_to_glyph_action(c),
                "enforcement": "advisory" if c.category in ("architecture",) else "required",
            }
            manifest.append(entry)

        return manifest

    def _map_to_glyph_action(self, constraint: GlossaryConstraint) -> str:
        """Map a glossary constraint to its Ж-glyph action."""
        category_map = {
            "cross_cutting_constraints": "REQUIRE",
            "ownership_constraints": "FORBID",
            "naming_constraints": "REQUIRE",
            "schemadesigner_constraints": "REQUIRE",
            "configengineer_constraints": "REQUIRE",
            "middlewareengineer_constraints": "REQUIRE",
            "authservice_constraints": "REQUIRE",
            "test_agent_constraints": "REQUIRE",
        }
        return category_map.get(constraint.category, "REQUIRE")

    def to_json_manifest(self) -> str:
        """Export the full glossary as a JSON constraint manifest."""
        import json
        return json.dumps({
            "version": self._version,
            "source": "CONSTRAINT_GLOSSARY.md",
            "total_constraints": len(self._constraints),
            "constraints": [
                {
                    "tag": c.tag,
                    "category": c.category,
                    "definition": c.definition,
                }
                for c in self._constraints
            ],
            "glyph_manifest": self.to_glyph_manifest(),
        }, indent=2)

    # ── Summary ────────────────────────────────────────────────────────────

    @property
    def summary(self) -> dict[str, int]:
        """Count constraints by category."""
        counts: dict[str, int] = {}
        for c in self._constraints:
            counts[c.category] = counts.get(c.category, 0) + 1
        return counts

    def __repr__(self) -> str:
        return (f"ConstraintGlossaryBridge(v{self._version}, "
                f"{len(self._constraints)} constraints, "
                f"{len(self.summary)} categories)")
