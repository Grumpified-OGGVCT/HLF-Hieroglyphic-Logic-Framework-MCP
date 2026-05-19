"""
HLF Constitutional Check — program-structure governance rules.

Unlike the ethics governor (constitution.py) which validates content against
ethical rules (C-1 through C-5), the constitutional check validates PROGRAM
STRUCTURE against four fundamental safety rules:

  R-1  No unbounded recursion without explicit termination proof
  R-2  No unrestricted network effects without capability declaration
  R-3  No data exfiltration paths (output contracts must be declared)
  R-4  Agent identity must be verifiable (no anonymous execution at hearth tier)

These rules are about WHAT THE PROGRAM IS, not WHAT IT DOES.
They run BEFORE the ethics governor in the compilation pipeline because
constitution is about what's fundamentally disallowed; ethics is about
what's conditionally allowed.

People are the priority.  AI is the tool.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ── Network-effect host functions (mirrors runtime HOST_FUNCTIONS effects) ────
# These are the functions whose invocation constitutes a network effect.

_NETWORK_EFFECT_FUNCTIONS: set[str] = {
    "http_get",
    "http_post",
    "http_put",
    "http_delete",
    "url_encode",
    "url_decode",
}

# ── Write-effect host functions (potential exfiltration paths) ─────────────────

_WRITE_EFFECT_FUNCTIONS: set[str] = {
    "http_post",
    "http_put",
    "http_delete",
    "file_write",
}

# ── Capability-required functions (need explicit declaration) ──────────────────

_CAPABILITY_REQUIRED: dict[str, str] = {
    "http_get": "network",
    "http_post": "network",
    "http_put": "network",
    "http_delete": "network",
    "url_encode": "network",
    "url_decode": "network",
    "file_write": "filesystem_write",
    "spawn_agent": "agent_spawn",
    "sys_exec": "process_exec",
    "sys_setenv": "write_env",
}


# ── Exception ─────────────────────────────────────────────────────────────────


class ConstitutionalViolationError(Exception):
    """Raised when a program violates constitutional rules."""

    def __init__(self, rule: str, location: str, detail: str):
        self.rule = rule
        self.location = location
        self.detail = detail
        super().__init__(
            f"Constitutional violation at {location}: {rule} — {detail}"
        )


# ── Rule definitions ──────────────────────────────────────────────────────────


@dataclass
class ConstitutionalRule:
    """A single constitutional rule with its check implementation."""

    rule_id: str
    description: str
    severity: str = "hard_block"  # hard_block | warning


# The four constitutional rules
RULES: dict[str, ConstitutionalRule] = {
    "R-1": ConstitutionalRule(
        rule_id="R-1",
        description="No unbounded recursion without explicit termination proof",
    ),
    "R-2": ConstitutionalRule(
        rule_id="R-2",
        description="No unrestricted network effects without capability declaration",
    ),
    "R-3": ConstitutionalRule(
        rule_id="R-3",
        description="No data exfiltration paths (output contracts must be declared)",
    ),
    "R-4": ConstitutionalRule(
        rule_id="R-4",
        description="Agent identity must be verifiable (no anonymous execution at hearth tier)",
    ),
}


# ── Check implementations ─────────────────────────────────────────────────────


def _check_unbounded_recursion(
    statements: list[dict[str, Any]], source: str = ""
) -> list[tuple[str, str, str]]:
    """R-1: Detect self-recursive function calls without termination proof.

    Walks func_block_stmt nodes and checks whether the function body contains
    a call_stmt referencing the same function name (direct self-recursion).
    """
    violations: list[tuple[str, str, str]] = []

    def _collect_call_names(
        stmts: list[dict[str, Any]], collected: set[str]
    ) -> None:
        """Recursively collect all call_stmt/tool_stmt names from a statement list."""
        for stmt in stmts:
            if not isinstance(stmt, dict):
                continue
            kind = stmt.get("kind", "")
            if kind in ("call_stmt", "tool_stmt"):
                name = stmt.get("name", "")
                if isinstance(name, str) and name:
                    collected.add(name)
            # Recurse into bodies
            _collect_call_names(stmt.get("body", {}).get("statements", []), collected)
            _collect_call_names(stmt.get("blocks", []), collected)
            # Recurse into pipe stages
            for stage in stmt.get("stages", []):
                if isinstance(stage, dict):
                    _collect_call_names([stage], collected)

    for stmt in statements:
        if not isinstance(stmt, dict):
            continue
        if stmt.get("kind") == "func_block_stmt":
            func_name = stmt.get("name", "")
            if not isinstance(func_name, str) or not func_name:
                continue
            body = stmt.get("body", {})
            body_stmts = body.get("statements", []) if isinstance(body, dict) else []
            called_names: set[str] = set()
            _collect_call_names(body_stmts, called_names)
            if func_name in called_names:
                violations.append(
                    (
                        "R-1",
                        f"function '{func_name}'",
                        "Self-recursive function call detected without explicit termination proof. "
                        "Add a termination condition or @validate(termination_proof=...) annotation.",
                    )
                )

    return violations


def _check_network_effects(
    statements: list[dict[str, Any]], tier: str = "hearth", source: str = ""
) -> list[tuple[str, str, str]]:
    """R-2: Detect network-effect calls without capability declaration.

    A capability declaration can be:
    - A @validate(capability="network") annotation on the tool/call statement
    - Tier >= forge (network is implicitly allowed at forge/sovereign)
    """
    violations: list[tuple[str, str, str]] = []

    # At forge and sovereign tiers, network is implicitly allowed
    if tier in ("forge", "sovereign"):
        return violations

    def _check_stmt(stmt: dict[str, Any], path: str = "") -> None:
        if not isinstance(stmt, dict):
            return
        kind = stmt.get("kind", "")
        if kind in ("tool_stmt", "call_stmt"):
            name = stmt.get("name", "")
            if isinstance(name, str) and name.lower() in _NETWORK_EFFECT_FUNCTIONS:
                # Check for capability declaration via @validate annotation
                validations = stmt.get("validations", [])
                has_capability = _has_capability_declaration(validations, "network")
                if not has_capability:
                    loc = path or f"statement '{name}'"
                    violations.append(
                        (
                            "R-2",
                            loc,
                            f"Network effect '{name}' used without capability declaration. "
                            "Add @validate(capability=\"network\") or elevate to forge tier.",
                        )
                    )
        # Recurse
        for child_key in ("body", "blocks", "stages"):
            child = stmt.get(child_key)
            if isinstance(child, list):
                for i, c in enumerate(child):
                    _check_stmt(c, f"{path}/{child_key}[{i}]" if path else f"{child_key}[{i}]")
            elif isinstance(child, dict):
                _check_stmt(child, f"{path}/{child_key}" if path else child_key)
        body = stmt.get("body")
        if isinstance(body, dict):
            for i, s in enumerate(body.get("statements", [])):
                _check_stmt(s, f"{path}/body[{i}]" if path else f"body[{i}]")

    for i, stmt in enumerate(statements):
        _check_stmt(stmt, f"statement[{i}]")

    return violations


def _check_data_exfiltration(
    statements: list[dict[str, Any]], tier: str = "hearth", source: str = ""
) -> list[tuple[str, str, str]]:
    """R-3: Detect data output paths without declared output contracts.

    Output contracts are declared via:
    - @validate(output_contract="...") annotation
    - Output-related glyph statements (Δ with result expectations)
    """
    violations: list[tuple[str, str, str]] = []

    def _check_stmt(stmt: dict[str, Any], path: str = "") -> None:
        if not isinstance(stmt, dict):
            return
        kind = stmt.get("kind", "")
        if kind in ("tool_stmt", "call_stmt"):
            name = stmt.get("name", "")
            if isinstance(name, str) and name.lower() in _WRITE_EFFECT_FUNCTIONS:
                validations = stmt.get("validations", [])
                has_output_contract = _has_output_contract_declaration(validations)
                if not has_output_contract:
                    loc = path or f"statement '{name}'"
                    violations.append(
                        (
                            "R-3",
                            loc,
                            f"Write effect '{name}' used without declared output contract. "
                            "Add @validate(output_contract=\"...\") to declare expected output shape.",
                        )
                    )
        # Recurse
        for child_key in ("body", "blocks", "stages"):
            child = stmt.get(child_key)
            if isinstance(child, list):
                for i, c in enumerate(child):
                    _check_stmt(c, f"{path}/{child_key}[{i}]" if path else f"{child_key}[{i}]")
            elif isinstance(child, dict):
                _check_stmt(child, f"{path}/{child_key}" if path else child_key)
        body = stmt.get("body")
        if isinstance(body, dict):
            for i, s in enumerate(body.get("statements", [])):
                _check_stmt(s, f"{path}/body[{i}]" if path else f"body[{i}]")

    for i, stmt in enumerate(statements):
        _check_stmt(stmt, f"statement[{i}]")

    return violations


def _check_agent_identity(
    statements: list[dict[str, Any]], tier: str = "hearth", source: str = ""
) -> list[tuple[str, str, str]]:
    """R-4: At hearth tier, agent identity must be verifiable.

    Identity can be declared via:
    - intent_stmt (INTENT capsule with agent identity)
    - glyph_stmt with identity-related tag (IDENTITY, AGENT)
    - set_stmt with agent_id or identity variable

    The check only triggers when the program performs sensitive operations
    (network effects, file writes, agent spawns, process execution).  Pure
    analysis/computation programs without side effects are exempt — the
    identity requirement escalates with capability use.
    """
    violations: list[tuple[str, str, str]] = []

    # Only enforced at hearth tier
    if tier != "hearth":
        return violations

    # ── First, check if the program performs sensitive operations ─────────
    _SENSITIVE_FUNCTIONS: set[str] = {
        "http_get",
        "http_post",
        "http_put",
        "http_delete",
        "file_write",
        "spawn_agent",
        "sys_exec",
        "sys_setenv",
    }

    def _has_sensitive_ops(stmts: list[dict[str, Any]]) -> bool:
        """Check if any statement invokes a sensitive function."""
        for stmt in stmts:
            if not isinstance(stmt, dict):
                continue
            kind = stmt.get("kind", "")
            if kind in ("tool_stmt", "call_stmt"):
                name = stmt.get("name", "")
                if isinstance(name, str) and name.lower() in _SENSITIVE_FUNCTIONS:
                    return True
            # Recurse
            for child_key in ("body", "blocks", "stages"):
                child = stmt.get(child_key)
                if isinstance(child, list):
                    if _has_sensitive_ops([c for c in child if isinstance(c, dict)]):
                        return True
                elif isinstance(child, dict):
                    if _has_sensitive_ops([child]):
                        return True
            body = stmt.get("body")
            if isinstance(body, dict):
                if _has_sensitive_ops(body.get("statements", [])):
                    return True
        return False

    if not _has_sensitive_ops(statements):
        return violations  # No sensitive ops → identity check skipped

    # ── Now check for identity declaration ────────────────────────────────
    has_identity = False
    identity_location = ""

    _IDENTITY_TAGS = {"IDENTITY", "INTENT", "AGENT"}
    _IDENTITY_VARS = {"agent_id", "agent_identity", "identity"}

    def _check_identity(stmt: dict[str, Any], path: str = "") -> None:
        nonlocal has_identity, identity_location
        if not isinstance(stmt, dict):
            return
        kind = stmt.get("kind", "")

        # intent_stmt always declares identity
        if kind == "intent_stmt":
            has_identity = True
            identity_location = path or f"intent '{stmt.get('name', '?')}'"
            return

        # glyph_stmt with identity tag
        if kind == "glyph_stmt":
            tag = stmt.get("tag", "")
            if isinstance(tag, str) and tag.upper() in _IDENTITY_TAGS:
                has_identity = True
                identity_location = path or f"glyph [{tag}]"
                return

        # set_stmt with identity variable name
        if kind == "set_stmt":
            name = stmt.get("name", "")
            if isinstance(name, str) and name.lower() in _IDENTITY_VARS:
                has_identity = True
                identity_location = path or f"set '{name}'"
                return

        # Recurse
        for child_key in ("body", "blocks", "stages"):
            child = stmt.get(child_key)
            if isinstance(child, list):
                for i, c in enumerate(child):
                    _check_identity(
                        c, f"{path}/{child_key}[{i}]" if path else f"{child_key}[{i}]"
                    )
            elif isinstance(child, dict):
                _check_identity(
                    child, f"{path}/{child_key}" if path else child_key
                )
        body = stmt.get("body")
        if isinstance(body, dict):
            for i, s in enumerate(body.get("statements", [])):
                _check_identity(
                    s, f"{path}/body[{i}]" if path else f"body[{i}]"
                )

    for i, stmt in enumerate(statements):
        _check_identity(stmt, f"statement[{i}]")

    if not has_identity:
        violations.append(
            (
                "R-4",
                "program root",
                "No agent identity declared. At hearth tier, programs performing "
                "sensitive operations (network, file writes, agent spawns) must "
                "declare a verifiable agent identity via INTENT capsule, IDENTITY "
                "glyph, or agent_id variable. Anonymous execution is not permitted.",
            )
        )

    return violations


# ── Public API ────────────────────────────────────────────────────────────────


def check_constitution(
    ast: dict[str, Any] | None,
    source: str = "",
    tier: str = "hearth",
) -> list[tuple[str, str, str]]:
    """Run all constitutional structural checks.

    Args:
        ast:    Compiled AST dict (may be None for source-only checks).
        source: Raw HLF source text.
        tier:   Active capsule tier ('hearth' | 'forge' | 'sovereign').

    Returns:
        List of (rule_id, location, detail) tuples.  Empty list = all passed.

    Raises:
        ConstitutionalViolationError: On the first hard-block violation.
    """
    statements: list[dict[str, Any]] = []
    if ast:
        statements = ast.get("statements", [])

    all_violations: list[tuple[str, str, str]] = []

    # R-1: Unbounded recursion
    all_violations.extend(_check_unbounded_recursion(statements, source))

    # R-2: Network effects
    all_violations.extend(_check_network_effects(statements, tier, source))

    # R-3: Data exfiltration
    all_violations.extend(_check_data_exfiltration(statements, tier, source))

    # R-4: Agent identity
    all_violations.extend(_check_agent_identity(statements, tier, source))

    # Raise on first violation for clear error reporting
    if all_violations:
        rule_id, location, detail = all_violations[0]
        raise ConstitutionalViolationError(
            rule=rule_id,
            location=location,
            detail=detail,
        )

    return all_violations  # empty list = all passed


def check_constitution_collect(
    ast: dict[str, Any] | None,
    source: str = "",
    tier: str = "hearth",
) -> list[tuple[str, str, str]]:
    """Run all constitutional structural checks without raising.

    Returns all violations instead of raising on the first one.
    Useful for testing and for the ethics governor to collect all issues.
    """
    statements: list[dict[str, Any]] = []
    if ast:
        statements = ast.get("statements", [])

    all_violations: list[tuple[str, str, str]] = []

    all_violations.extend(_check_unbounded_recursion(statements, source))
    all_violations.extend(_check_network_effects(statements, tier, source))
    all_violations.extend(_check_data_exfiltration(statements, tier, source))
    all_violations.extend(_check_agent_identity(statements, tier, source))

    return all_violations


# ── Helpers ───────────────────────────────────────────────────────────────────


def _has_capability_declaration(
    validations: list[dict[str, Any]], capability: str
) -> bool:
    """Check if @validate annotations include a capability declaration."""
    for v in validations:
        if not isinstance(v, dict):
            continue
        # Check key-value pairs in validation
        for key in v:
            if key == "capability" or key == "cap":
                val = v[key]
                if isinstance(val, dict):
                    val = val.get("value", "")
                if str(val).lower() == capability.lower():
                    return True
    return False


def _has_output_contract_declaration(
    validations: list[dict[str, Any]],
) -> bool:
    """Check if @validate annotations include an output contract declaration."""
    for v in validations:
        if not isinstance(v, dict):
            continue
        for key in v:
            if key in ("output_contract", "output", "returns", "ensures"):
                return True
    return False
