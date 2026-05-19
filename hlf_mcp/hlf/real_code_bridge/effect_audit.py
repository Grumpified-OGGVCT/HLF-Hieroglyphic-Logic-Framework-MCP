"""
Effect Audit: verify that declared effects match actual side effects.

The audit works by:
1. Compiling HLF source to AST
2. Extracting declared effects via EffectExtractor
3. Executing the HLF program via the VM
4. Comparing declared effects with actual VM side_effects output
5. Reporting any declared-but-not-executed or executed-but-not-declared effects

This proves the effect system is honest: the manifest is not decorative, it
accurately predicts what the program will do.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from hlf_mcp.hlf.bytecode import HLFBytecode
from hlf_mcp.hlf.compiler import HLFCompiler
from hlf_mcp.hlf.effect_extractor import EffectExtractor
from hlf_mcp.hlf.runtime import HLFRuntime
from hlf_mcp.hlf.capability_manifest import CapabilityManifest


@dataclass
class AuditResult:
    """Result of an effect audit."""

    source_label: str
    declared_effects: list[str]
    actual_effects: list[str]
    undeclared_effects: list[str]  # executed but not declared
    unexecuted_effects: list[str]  # declared but not executed
    matched_effects: list[str]
    passed: bool

    @property
    def output(self) -> dict[str, Any]:
        return {
            "source_label": self.source_label,
            "declared_effects": self.declared_effects,
            "actual_effects": self.actual_effects,
            "undeclared_effects": self.undeclared_effects,
            "unexecuted_effects": self.unexecuted_effects,
            "matched_effects": self.matched_effects,
            "passed": self.passed,
        }


class EffectAuditor:
    """Verify declared effects match actual side effects."""

    def __init__(self, compiler: HLFCompiler | None = None) -> None:
        self.compiler = compiler or HLFCompiler()

    def _normalize_declared_effect_name(self, name: str) -> str:
        """Normalize declared effect names to match runtime categories."""
        # Map known mismatches between declared (Extractor) and runtime (VM) naming
        declared_to_runtime = {
            "route_selection": "model_inference",
            "agent_delegation": "agent_delegation",  # already matches
        }
        return declared_to_runtime.get(name, name)

    def _runtime_effect_to_category(self, effect: dict[str, Any]) -> str:
        """Map a VM side_effect entry to a category string."""
        etype = str(effect.get("type", "")).lower()
        ename = str(effect.get("name", "")).lower()

        # Map VM effect types to effect categories
        if etype in ("tool_call", "host_call"):
            return ename
        if etype == "spawn_agent":
            return "agent_delegation"
        if etype == "delegation":
            return "agent_delegation"
        if etype == "network":
            return "network_read"
        if etype == "write_fs":
            return "file_write"
        if etype == "read_fs":
            return "file_read"
        if etype == "memory_write":
            return "memory_write"
        if etype == "memory_read":
            return "memory_read"
        if etype == "model_call":
            return "model_inference"
        if etype == "sensor_read":
            return "sensor_read"
        if etype == "trajectory_plan":
            return "trajectory_plan"
        if etype == "guarded_actuation":
            return "guarded_actuation"
        if etype == "safety_stop":
            return "safety_stop"
        if etype == "memory_context_query":
            return "memory_read"
        return etype

    def audit(self, source: str, label: str = "") -> AuditResult:
        """Audit a single HLF program: compare declared effects with actual side effects."""
        try:
            ast = self.compiler.compile(source)["ast"]
        except Exception as exc:
            return AuditResult(
                source_label=label or "unnamed",
                declared_effects=[],
                actual_effects=[],
                undeclared_effects=[],
                unexecuted_effects=[],
                matched_effects=[],
                passed=False,
            )

        # Extract declared effects
        from hlf_mcp.hlf.capability_manifest import CapabilityManifest
        manifest = EffectExtractor.extract(ast, source)
        declared = _collect_declared_effect_names(manifest)

        # Execute to get actual effects
        bytecode = HLFBytecode().encode(ast)
        runtime = HLFRuntime()
        result = runtime.run(bytecode, gas_limit=500)
        actual_effects = result.get("side_effects", [])

        actual_categories = {self._runtime_effect_to_category(e) for e in actual_effects if e}
        actual_categories.discard("")

        declared_set = {self._normalize_declared_effect_name(d) for d in declared}
        actual_set = actual_categories

        undeclared = sorted(actual_set - declared_set)
        unexecuted = sorted(declared_set - actual_set)
        matched = sorted(actual_set & declared_set)

        return AuditResult(
            source_label=label or "unnamed",
            declared_effects=sorted(declared),
            actual_effects=sorted(actual_categories),
            undeclared_effects=undeclared,
            unexecuted_effects=unexecuted,
            matched_effects=matched,
            passed=len(undeclared) == 0,
        )


def _collect_declared_effect_names(manifest: CapabilityManifest) -> list[str]:
    """Collect effect names from a CapabilityManifest."""
    names: set[str] = set()
    for effect in manifest.effects:
        name = _effect_declaration_name(effect)
        if name:
            names.add(name)
    return list(names)


def _effect_declaration_name(effect: Any) -> str:
    """Extract canonical name from a TypedEffectDeclaration."""
    if hasattr(effect, "effect_class") and effect.effect_class:
        return str(effect.effect_class.name).lower()
    if hasattr(effect, "effect_name") and effect.effect_name:
        return str(effect.effect_name).lower()
    if isinstance(effect, dict):
        return str(effect.get("effect_class", effect.get("name", ""))).lower()
    return ""


def audit_effects(source: str, label: str = "") -> AuditResult:
    """Convenience function for auditing declared vs actual effects."""
    return EffectAuditor().audit(source, label=label)
