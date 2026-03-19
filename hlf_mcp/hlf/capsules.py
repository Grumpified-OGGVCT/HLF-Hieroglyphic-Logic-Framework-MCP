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
import hashlib
import uuid
from typing import Any

from hlf_mcp.hlf.memory_node import (
    lookup_pointer_registry_entry,
    parse_pointer_ref,
    verify_pointer_ref,
)

class CapsuleViolation(Exception):
    def __init__(self, message):
        super().__init__(f"Capsule violation: {message}")
        self.violation_type = "capsule"


_TIER_RANK: dict[str, int] = {
    "hearth": 0,
    "forge": 1,
    "sovereign": 2,
}


def normalize_tier(tier: str | None) -> str:
    normalized = str(tier or "hearth").strip().lower()
    return normalized if normalized in _TIER_RANK else "hearth"


def tier_rank(tier: str | None) -> int:
    return _TIER_RANK[normalize_tier(tier)]


def build_capsule_approval_token(
    capsule_id: str,
    base_tier: str,
    requested_tier: str,
    requirements: list[dict[str, Any]],
) -> str:
    serialized_requirements = "|".join(
        sorted(
            f"{item.get('type', '')}:{item.get('scope', '')}:{item.get('value', '')}"
            for item in requirements
        )
    )
    payload = f"{capsule_id}|{normalize_tier(base_tier)}|{normalize_tier(requested_tier)}|{serialized_requirements}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]

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
    base_tier: str = "hearth"
    agent_id: str = "unknown-agent"
    capsule_id: str = dataclasses.field(default_factory=lambda: str(uuid.uuid4()))
    requested_tier: str = "hearth"
    pointer_trust_mode: str = "enforce"
    trusted_pointers: dict[str, dict[str, Any]] = dataclasses.field(default_factory=dict)
    approval_required_tags: set[str] = dataclasses.field(default_factory=set)
    approval_required_tools: set[str] = dataclasses.field(default_factory=set)
    approved_by: str = ""
    approval_token: str = ""
    metadata: dict[str, Any] = dataclasses.field(default_factory=dict)

    def collect_approval_requirements(self, statements: list[dict[str, Any]]) -> list[dict[str, str]]:
        requirements: list[dict[str, str]] = []
        if tier_rank(self.requested_tier) > tier_rank(self.base_tier):
            requirements.append(
                {
                    "type": "tier_escalation",
                    "scope": "capsule",
                    "value": f"{self.base_tier}->{self.requested_tier}",
                }
            )
        for node in statements:
            if not isinstance(node, dict):
                continue
            tag = str(node.get("tag", "") or "")
            if tag and tag in self.approval_required_tags:
                requirements.append({"type": "tag", "scope": "tag", "value": tag})
            kind = node.get("kind", "")
            if kind in ("tool_stmt", "call_stmt"):
                name = str(node.get("name", "") or "")
                if name and name in self.approval_required_tools:
                    requirements.append({"type": "tool", "scope": "tool", "value": name})
            for key in ("body", "statements"):
                sub = node.get(key)
                if isinstance(sub, dict):
                    requirements.extend(self.collect_approval_requirements(sub.get("statements", [])))
                elif isinstance(sub, list):
                    requirements.extend(self.collect_approval_requirements(sub))

        unique: list[dict[str, str]] = []
        seen: set[tuple[str, str, str]] = set()
        for item in requirements:
            key = (item["type"], item["scope"], item["value"])
            if key in seen:
                continue
            seen.add(key)
            unique.append(item)
        return unique

    def _merged_requirements(
        self,
        statements: list[dict[str, Any]],
        extra_requirements: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, str]]:
        requirements = list(self.collect_approval_requirements(statements))
        for item in extra_requirements or []:
            normalized = {
                "type": str(item.get("type", "") or ""),
                "scope": str(item.get("scope", "") or ""),
                "value": str(item.get("value", "") or ""),
            }
            if not normalized["type"] or not normalized["scope"] or not normalized["value"]:
                continue
            if normalized in requirements:
                continue
            requirements.append(normalized)
        return requirements

    def expected_approval_token(
        self,
        statements: list[dict[str, Any]],
        extra_requirements: list[dict[str, Any]] | None = None,
    ) -> str:
        requirements = self._merged_requirements(statements, extra_requirements)
        if not requirements:
            return ""
        return build_capsule_approval_token(
            self.capsule_id,
            self.base_tier,
            self.requested_tier,
            requirements,
        )

    def approval_granted(
        self,
        statements: list[dict[str, Any]],
        extra_requirements: list[dict[str, Any]] | None = None,
    ) -> bool:
        requirements = self._merged_requirements(statements, extra_requirements)
        if not requirements:
            return True
        if not self.approved_by or not self.approval_token:
            return False
        return self.approval_token == self.expected_approval_token(statements, extra_requirements)

    def validate_host_function(self, function_name: str) -> list[str]:
        violations: list[str] = []
        if function_name in self.denied_tools:
            violations.append(f"Denied tool/function: {function_name}")
        if self.allowed_tools and function_name not in self.allowed_tools:
            violations.append(f"Tool/function not in allowed list: {function_name}")
        return violations

    def approval_violations(
        self,
        statements: list[dict[str, Any]],
        extra_requirements: list[dict[str, Any]] | None = None,
    ) -> list[str]:
        requirements = self._merged_requirements(statements, extra_requirements)
        if not requirements:
            return []
        if self.approval_granted(statements, extra_requirements):
            return []
        violations: list[str] = []
        for item in requirements:
            if item["type"] == "tier_escalation":
                violations.append(
                    f"Tier escalation requires higher-order approval: {item['value']}"
                )
            elif item["type"] == "tag":
                violations.append(f"Tag requires higher-order approval: [{item['value']}]")
            elif item["type"] == "tool":
                violations.append(f"Tool/function requires higher-order approval: {item['value']}")
            elif item["type"] == "verification_review":
                violations.append(
                    f"Verifier review requires higher-order approval: {item['value']}"
                )
        return violations

    def _validate_pointer_string(self, value: str) -> list[str]:
        parsed = parse_pointer_ref(value)
        if parsed is None:
            return []
        if self.pointer_trust_mode == "disabled":
            return []
        verification = verify_pointer_ref(
            parsed["pointer"],
            registry_entry=lookup_pointer_registry_entry(parsed["pointer"], self.trusted_pointers),
        )
        if verification["status"] == "ok":
            return []
        if self.pointer_trust_mode == "audit":
            return []
        return [
            f"Untrusted pointer {parsed['pointer']}: {verification.get('reason', verification['status'])}"
        ]

    def _validate_pointer_literals(self, value: Any) -> list[str]:
        violations: list[str] = []
        if isinstance(value, str):
            violations.extend(self._validate_pointer_string(value))
        elif isinstance(value, dict):
            for nested in value.values():
                violations.extend(self._validate_pointer_literals(nested))
        elif isinstance(value, list):
            for nested in value:
                violations.extend(self._validate_pointer_literals(nested))
        return violations

    def validate_ast(
        self,
        statements: list[dict[str, Any]],
        extra_requirements: list[dict[str, Any]] | None = None,
    ) -> list[str]:
        """Pre-flight check. Returns list of violation messages."""
        violations = self.approval_violations(statements, extra_requirements)
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
                violations.extend(self.validate_host_function(name))
            violations.extend(self._validate_pointer_literals(node))
            # Recurse into blocks
            for key in ("body", "statements"):
                sub = node.get(key)
                if isinstance(sub, dict):
                    violations.extend(self.validate_ast(sub.get("statements", []), extra_requirements))
                elif isinstance(sub, list):
                    violations.extend(self.validate_ast(sub, extra_requirements))
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
            "base_tier": self.base_tier,
            "agent_id": self.agent_id,
            "capsule_id": self.capsule_id,
            "requested_tier": self.requested_tier,
            "pointer_trust_mode": self.pointer_trust_mode,
            "trusted_pointer_count": len(self.trusted_pointers),
            "approval_required_tags": sorted(self.approval_required_tags),
            "approval_required_tools": sorted(self.approval_required_tools),
            "approved_by": self.approved_by,
            "approval_granted": bool(self.approved_by and self.approval_token),
            "metadata": dict(self.metadata),
        }


def sovereign_capsule(
    *,
    base_tier: str = "sovereign",
    agent_id: str = "unknown-agent",
    capsule_id: str | None = None,
    requested_tier: str | None = None,
    trusted_pointers: dict[str, dict[str, Any]] | None = None,
    pointer_trust_mode: str = "enforce",
    approval_required_tags: set[str] | None = None,
    approval_required_tools: set[str] | None = None,
    approved_by: str = "",
    approval_token: str = "",
) -> IntentCapsule:
    """Full permissions capsule for sovereign agents."""
    effective_tier = normalize_tier(requested_tier or "sovereign")
    return IntentCapsule(
        allowed_tags=set(), denied_tags=set(),
        allowed_tools=set(), denied_tools=set(),
        max_gas=1000, tier=effective_tier, read_only_vars=set(),
        base_tier=normalize_tier(base_tier),
        agent_id=agent_id,
        capsule_id=capsule_id or str(uuid.uuid4()),
        requested_tier=effective_tier,
        trusted_pointers=dict(trusted_pointers or {}),
        pointer_trust_mode=pointer_trust_mode,
        approval_required_tags=set(approval_required_tags or set()),
        approval_required_tools=set(approval_required_tools or set()),
        approved_by=approved_by,
        approval_token=approval_token,
    )

def forge_capsule(
    *,
    base_tier: str = "forge",
    agent_id: str = "unknown-agent",
    capsule_id: str | None = None,
    requested_tier: str | None = None,
    trusted_pointers: dict[str, dict[str, Any]] | None = None,
    pointer_trust_mode: str = "enforce",
    approval_required_tags: set[str] | None = None,
    approval_required_tools: set[str] | None = None,
    approved_by: str = "",
    approval_token: str = "",
) -> IntentCapsule:
    """Moderate permissions for forge tier agents."""
    effective_tier = normalize_tier(requested_tier or "forge")
    return IntentCapsule(
        allowed_tags={
            "SET", "ASSIGN", "IF", "FOR", "RESULT", "TOOL", "CALL", "MEMORY", "RECALL", "IMPORT", "LOG",
            "INTENT", "CONSTRAINT", "EXPECT", "ASSERT", "PARAM", "ROUTE", "DELEGATE", "VOTE", "PRIORITY", "SOURCE", "ACTION",
        },
        denied_tags={"SPAWN", "SHELL_EXEC"},
        allowed_tools={"READ", "WRITE", "HTTP_GET", "hash_sha256", "log_emit", "memory_store", "memory_recall"},
        denied_tools={"WEB_SEARCH", "spawn_agent", "z3_verify"},
        max_gas=500, tier=effective_tier, read_only_vars={"SYS_INFO"},
        base_tier=normalize_tier(base_tier),
        agent_id=agent_id,
        capsule_id=capsule_id or str(uuid.uuid4()),
        requested_tier=effective_tier,
        trusted_pointers=dict(trusted_pointers or {}),
        pointer_trust_mode=pointer_trust_mode,
        approval_required_tags=set(approval_required_tags or set()),
        approval_required_tools=set(approval_required_tools or set()),
        approved_by=approved_by,
        approval_token=approval_token,
    )

def hearth_capsule(
    *,
    base_tier: str = "hearth",
    agent_id: str = "unknown-agent",
    capsule_id: str | None = None,
    requested_tier: str | None = None,
    trusted_pointers: dict[str, dict[str, Any]] | None = None,
    pointer_trust_mode: str = "enforce",
    approval_required_tags: set[str] | None = None,
    approval_required_tools: set[str] | None = None,
    approved_by: str = "",
    approval_token: str = "",
) -> IntentCapsule:
    """Highly restricted capsule for hearth tier agents."""
    effective_tier = normalize_tier(requested_tier or "hearth")
    return IntentCapsule(
        allowed_tags={"SET", "IF", "RESULT", "LOG", "INTENT", "CONSTRAINT", "ASSERT", "PARAM", "SOURCE"},
        denied_tags={"SPAWN", "SHELL_EXEC", "TOOL", "HOST", "MEMORY", "RECALL"},
        allowed_tools=set(), denied_tools=set(),
        max_gas=100, tier=effective_tier, read_only_vars={"SYS_INFO", "NOW"},
        base_tier=normalize_tier(base_tier),
        agent_id=agent_id,
        capsule_id=capsule_id or str(uuid.uuid4()),
        requested_tier=effective_tier,
        trusted_pointers=dict(trusted_pointers or {}),
        pointer_trust_mode=pointer_trust_mode,
        approval_required_tags=set(approval_required_tags or set()),
        approval_required_tools=set(approval_required_tools or set()),
        approved_by=approved_by,
        approval_token=approval_token,
    )

def capsule_for_tier(
    tier: str,
    *,
    agent_id: str = "unknown-agent",
    capsule_id: str | None = None,
    requested_tier: str | None = None,
    trusted_pointers: dict[str, dict[str, Any]] | None = None,
    pointer_trust_mode: str = "enforce",
    approval_required_tags: set[str] | None = None,
    approval_required_tools: set[str] | None = None,
    approved_by: str = "",
    approval_token: str = "",
) -> IntentCapsule:
    """Get the default capsule for a deployment tier."""
    normalized_tier = normalize_tier(tier)
    normalized_requested_tier = normalize_tier(requested_tier or tier)
    if normalized_requested_tier == "sovereign":
        return sovereign_capsule(
            base_tier=normalized_tier,
            agent_id=agent_id,
            capsule_id=capsule_id,
            requested_tier=normalized_requested_tier,
            trusted_pointers=trusted_pointers,
            pointer_trust_mode=pointer_trust_mode,
            approval_required_tags=approval_required_tags,
            approval_required_tools=approval_required_tools,
            approved_by=approved_by,
            approval_token=approval_token,
        )
    if normalized_requested_tier == "forge":
        return forge_capsule(
            base_tier=normalized_tier,
            agent_id=agent_id,
            capsule_id=capsule_id,
            requested_tier=normalized_requested_tier,
            trusted_pointers=trusted_pointers,
            pointer_trust_mode=pointer_trust_mode,
            approval_required_tags=approval_required_tags,
            approval_required_tools=approval_required_tools,
            approved_by=approved_by,
            approval_token=approval_token,
        )
    return hearth_capsule(
        base_tier=normalized_tier,
        agent_id=agent_id,
        capsule_id=capsule_id,
        requested_tier=normalized_requested_tier,
        trusted_pointers=trusted_pointers,
        pointer_trust_mode=pointer_trust_mode,
        approval_required_tags=approval_required_tags,
        approval_required_tools=approval_required_tools,
        approved_by=approved_by,
        approval_token=approval_token,
    )
