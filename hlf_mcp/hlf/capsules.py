"""
HLF Intent Capsules — sandboxed execution with tier-based capability restrictions.

Tiers:
  hearth    — minimal permissions, no tools/host calls, gas=100
  forge     — moderate permissions, read/write/http allowed, gas=500
  sovereign — full permissions, all tools, gas=1000

Usage:
  capsule = hearth_capsule()
  violations = capsule.validate_ast(program_statements)
  # Run with CapsuleInterpreter to enforce at runtime
"""

from __future__ import annotations
import dataclasses
from typing import Any

class CapsuleViolation(Exception):
    def __init__(self, message):
        super().__init__(f"Capsule violation: {message}")
        self.violation_type = "capsule"

@dataclasses.dataclass
class IntentCapsule:
    """Sandboxed execution capsule with capability restrictions."""
    allowed_tags: set[str]       # empty = all allowed
    denied_tags: set[str]
    allowed_tools: set[str]      # empty = all allowed (if no deny)
    denied_tools: set[str]
    max_gas: int
    tier: str
    read_only_vars: set[str]

    def validate_ast(self, statements: list[dict[str, Any]]) -> list[str]:
        """Pre-flight check. Returns list of violation messages."""
        violations = []
        for node in statements:
            if not isinstance(node, dict):
                continue
            kind = node.get("kind", "")
            tag = node.get("tag", "")
            # Check denied tags
            if tag and tag in self.denied_tags:
                violations.append(f"Denied tag: [{tag}]")
            # Check whitelist
            if self.allowed_tags and tag and tag not in self.allowed_tags:
                violations.append(f"Tag not in allowed list: [{tag}]")
            # Check tool/host calls
            if kind in ("tool_stmt", "call_stmt"):
                name = node.get("name", "")
                if name in self.denied_tools:
                    violations.append(f"Denied tool/function: {name}")
                if self.allowed_tools and name not in self.allowed_tools:
                    violations.append(f"Tool/function not in allowed list: {name}")
            # Recurse into blocks
            for key in ("body", "statements"):
                sub = node.get(key)
                if isinstance(sub, dict):
                    violations.extend(self.validate_ast(sub.get("statements", [])))
                elif isinstance(sub, list):
                    violations.extend(self.validate_ast(sub))
        return violations

    def check_var_write(self, name: str) -> None:
        if name in self.read_only_vars:
            raise CapsuleViolation(f"Cannot assign to read-only variable: {name}")

    def check_gas(self, gas_used: int) -> None:
        if gas_used > self.max_gas:
            raise CapsuleViolation(f"Gas limit exceeded: {gas_used}/{self.max_gas}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "tier": self.tier,
            "max_gas": self.max_gas,
            "allowed_tags": sorted(self.allowed_tags),
            "denied_tags": sorted(self.denied_tags),
            "allowed_tools": sorted(self.allowed_tools),
            "denied_tools": sorted(self.denied_tools),
            "read_only_vars": sorted(self.read_only_vars),
        }


def sovereign_capsule() -> IntentCapsule:
    """Full permissions capsule for sovereign agents."""
    return IntentCapsule(
        allowed_tags=set(), denied_tags=set(),
        allowed_tools=set(), denied_tools=set(),
        max_gas=1000, tier="sovereign", read_only_vars=set(),
    )

def forge_capsule() -> IntentCapsule:
    """Moderate permissions for forge tier agents."""
    return IntentCapsule(
        allowed_tags={"SET", "ASSIGN", "IF", "FOR", "RESULT", "TOOL", "CALL", "MEMORY", "RECALL", "IMPORT", "LOG"},
        denied_tags={"SPAWN", "SHELL_EXEC"},
        allowed_tools={"READ", "WRITE", "HTTP_GET", "hash_sha256", "log_emit", "memory_store", "memory_recall"},
        denied_tools={"WEB_SEARCH", "spawn_agent", "z3_verify"},
        max_gas=500, tier="forge", read_only_vars={"SYS_INFO"},
    )

def hearth_capsule() -> IntentCapsule:
    """Highly restricted capsule for hearth tier agents."""
    return IntentCapsule(
        allowed_tags={"SET", "IF", "RESULT", "LOG"},
        denied_tags={"SPAWN", "SHELL_EXEC", "TOOL", "HOST", "MEMORY", "RECALL"},
        allowed_tools=set(), denied_tools=set(),
        max_gas=100, tier="hearth", read_only_vars={"SYS_INFO", "NOW"},
    )

def capsule_for_tier(tier: str) -> IntentCapsule:
    """Get the default capsule for a deployment tier."""
    if tier == "sovereign":
        return sovereign_capsule()
    if tier == "forge":
        return forge_capsule()
    return hearth_capsule()
