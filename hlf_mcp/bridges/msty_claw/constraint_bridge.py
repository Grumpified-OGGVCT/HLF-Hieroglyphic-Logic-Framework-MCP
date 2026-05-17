"""
Msty Claw Constraint Enforcer Bridge.

Converts HLF Ж [FORBID] / [ALLOW] / [REQUIRE_APPROVAL] declarations into
a JSON constraint manifest that Msty Claw can check before executing any tool.

HLF constraint format (flat glyph statements):
    Ж [FORBID] tool="shell" pattern="rm -rf"
    Ж [ALLOW]  tool="file_read" path="/workspace/*"
    Ж [REQUIRE_APPROVAL] tool="http_request" host="*" tier="hearth"
"""

from __future__ import annotations

import fnmatch
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# Tier ordering: hearth (lowest) → forge → sovereign (highest)
_TIER_RANK: dict[str, int] = {"hearth": 0, "forge": 1, "sovereign": 2}

# Regex to parse a single key="value" argument from an HLF line.
_ARG_RE = re.compile(r"""(\w+)\s*=\s*"((?:[^"\\]|\\.)*)"(?=\s|$)""")


@dataclass
class ConstraintResult:
    """Result of checking a tool call against constraints."""

    allowed: bool
    blocked_by: Optional[str] = None
    requires_approval: bool = False
    matched_rule: Optional[str] = None
    message: str = ""


class MstyConstraintBridge:
    """Bridge from HLF constraint declarations to Msty Claw runtime gates.

    Parses .hlf files containing Ж [FORBID] / [ALLOW] / [REQUIRE_APPROVAL]
    glyph statements and produces a JSON manifest that Msty Claw can
    consult before executing any tool call.

    Usage::

        bridge = MstyConstraintBridge()
        bridge.load_from_file("constraints.hlf")
        result = bridge.check_tool_call("shell", {"command": "rm -rf /"}, "hearth")
        assert result.allowed is False
    """

    VALID_ACTIONS: tuple[str, ...] = ("FORBID", "ALLOW", "REQUIRE_APPROVAL")
    VALID_TOOLS: tuple[str, ...] = (
        "shell",
        "file_read",
        "file_write",
        "http_request",
        "process_spawn",
        "db_query",
        "db_execute",
    )

    def __init__(self) -> None:
        self._constraints: list[dict[str, Any]] = []
        self._rule_counter: int = 0

    # ── parsing ────────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_args(text: str) -> dict[str, str]:
        """Parse key="value" pairs from an HLF argument string."""
        return {m.group(1): m.group(2) for m in _ARG_RE.finditer(text)}

    @staticmethod
    def _classify_pattern(pattern: str) -> str:
        """Determine if a pattern is 'regex' or 'glob' based on content."""
        regex_indicators = {"^", "$", "(", ")", "|", "[", "]", "\\d", "\\w", ".+", ".*?"}
        # .* alone is ambiguous — treat as glob wildcard
        if pattern in (".*", ".*?"):
            return "glob"
        for indicator in regex_indicators:
            if indicator in pattern:
                return "regex"
        return "glob"

    def load_constraints(self, hlf_source: str) -> list[dict[str, Any]]:
        """Parse HLF constraint source into a list of structured constraint dicts.

        Each constraint dict has keys:
            id, action, tool, pattern/path/host, pattern_type,
            args_pattern, min_tier, message
        """
        constraints: list[dict[str, Any]] = []
        self._rule_counter = 0

        for raw_line in hlf_source.splitlines():
            line = raw_line.strip()
            # Skip non-constraint lines
            if not line or line.startswith("#") or line in ("Ω", "[HLF-v3]"):
                continue
            if not line.startswith("Ж"):
                continue

            # Extract tag (action)
            tag_match = re.match(r"Ж\s*\[([A-Z_]+)\]", line)
            if not tag_match:
                continue
            tag = tag_match.group(1)
            if tag not in self.VALID_ACTIONS:
                continue

            # Parse arguments
            args = self._parse_args(line)
            tool = args.get("tool", "")

            # Determine the match field
            pattern = args.get("pattern", args.get("path", args.get("host", "")))
            pattern_type = self._classify_pattern(pattern)
            args_pattern = args.get("args_pattern", "")
            tier = args.get("tier", "").lower()

            self._rule_counter += 1
            rule_id = f"rule_{self._rule_counter:03d}"

            constraint: dict[str, Any] = {
                "id": rule_id,
                "action": tag,
                "tool": tool,
                "pattern": pattern,
                "pattern_type": pattern_type,
                "args_pattern": args_pattern,
                "min_tier": tier if tier else None,
                "message": self._build_message(tag, tool, pattern, tier),
            }
            # Preserve raw path/host fields if present
            if "path" in args:
                constraint["match_field"] = "path"
                constraint["path"] = args["path"]
            elif "host" in args:
                constraint["match_field"] = "host"
                constraint["host"] = args["host"]
            else:
                constraint["match_field"] = "pattern"

            constraints.append(constraint)

        self._constraints = constraints
        return constraints

    @staticmethod
    def _build_message(action: str, tool: str, pattern: str, tier: str) -> str:
        """Build a human-readable message for a constraint rule."""
        tier_suffix = f" (below tier {tier})" if tier and tier != "sovereign" else ""
        if action == "FORBID":
            return f"Tool '{tool}' matching '{pattern}' is forbidden by HLF constraint{tier_suffix}"
        if action == "ALLOW":
            return f"Tool '{tool}' matching '{pattern}' is explicitly allowed by HLF constraint"
        return f"Tool '{tool}' matching '{pattern}' requires operator approval{tier_suffix}"

    # ── file I/O ───────────────────────────────────────────────────────────────

    def load_from_file(self, path: str | Path) -> list[dict[str, Any]]:
        """Load constraints from a .hlf file on disk."""
        source = Path(path).read_text(encoding="utf-8")
        return self.load_constraints(source)

    def load_defaults(self) -> list[dict[str, Any]]:
        """Load the bundled default constraints."""
        default_path = Path(__file__).parent / "constraints.hlf"
        return self.load_from_file(default_path)

    # ── validation ─────────────────────────────────────────────────────────────

    def validate_constraints(self, constraints: list[dict[str, Any]]) -> tuple[bool, list[str]]:
        """Validate a list of constraints. Returns (is_valid, error_messages)."""
        errors: list[str] = []

        if not constraints:
            errors.append("No constraints provided")
            return False, errors

        for c in constraints:
            rid = c.get("id", "unknown")

            # Action must be valid
            if c.get("action") not in self.VALID_ACTIONS:
                errors.append(f"[{rid}] Invalid action: {c.get('action')}")

            # Tool must be non-empty
            if not c.get("tool", "").strip():
                errors.append(f"[{rid}] Empty tool name")

            # Pattern must be non-empty
            pattern = c.get("pattern", "")
            if not pattern.strip():
                errors.append(f"[{rid}] Empty pattern")

            # Tier must be valid if specified
            tier = c.get("min_tier")
            if tier and tier not in _TIER_RANK:
                errors.append(f"[{rid}] Invalid tier: {tier}")

        return len(errors) == 0, errors

    # ── export ─────────────────────────────────────────────────────────────────

    def export_manifest(self, constraints: list[dict[str, Any]], fmt: str = "json") -> str:
        """Export constraints as a JSON manifest for Msty Claw consumption."""
        manifest = {
            "version": "1.0",
            "source": "HLF_MCP constraint bridge",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "rule_count": len(constraints),
            "rules": constraints,
        }
        return json.dumps(manifest, indent=2)

    # ── runtime checking ───────────────────────────────────────────────────────

    def check_tool_call(
        self,
        tool: str,
        args: dict[str, Any],
        tier: str = "hearth",
    ) -> ConstraintResult:
        """Check if a tool call is permitted under current constraints.

        Args:
            tool: The tool name (e.g. "shell", "file_write", "http_request").
            args: The tool arguments dict (e.g. {"command": "rm -rf /"}).
            tier: The caller's current governance tier (hearth/forge/sovereign).

        Returns:
            ConstraintResult with allowed/blocked_by/requires_approval fields.
        """
        tier = tier.lower() if tier else "hearth"
        caller_rank = _TIER_RANK.get(tier, 0)

        explicit_allow: Optional[dict[str, Any]] = None
        approval_required: bool = False

        # Build a searchable string from args to match patterns against
        args_str = json.dumps(args) if args else ""

        for constraint in self._constraints:
            action = constraint["action"]
            c_tool = constraint["tool"]
            c_tier = constraint.get("min_tier")

            # Tool must match
            if c_tool and c_tool != tool:
                continue

            # Tier check: if constraint has a min_tier, it applies to callers
            # whose rank is <= the constraint's tier rank.
            # e.g., tier="hearth" (rank 0) → applies to hearth
            #       tier="forge"  (rank 1) → applies to hearth, forge
            #       tier="sovereign" (rank 2) → applies to all
            if c_tier:
                c_rank = _TIER_RANK.get(c_tier, 0)
                if caller_rank > c_rank:
                    continue  # caller is above the constraint tier — skip

            # Does the pattern match?
            if not self._match_constraint(constraint, args, args_str):
                continue

            if action == "FORBID":
                return ConstraintResult(
                    allowed=False,
                    blocked_by=constraint["id"],
                    requires_approval=False,
                    matched_rule=constraint["id"],
                    message=constraint.get("message", "Blocked by HLF constraint"),
                )

            if action == "ALLOW":
                explicit_allow = constraint

            if action == "REQUIRE_APPROVAL":
                approval_required = True

        # If we're here, no FORBID matched
        if explicit_allow:
            return ConstraintResult(
                allowed=True,
                requires_approval=approval_required,
                matched_rule=explicit_allow["id"],
                message=explicit_allow.get("message", "Explicitly allowed"),
            )

        # No forbids, no explicit allows → allowed by default
        return ConstraintResult(
            allowed=True,
            requires_approval=approval_required,
            message="No matching constraint — allowed by default",
        )

    def _match_constraint(
        self, constraint: dict[str, Any], args: dict[str, Any], args_str: str
    ) -> bool:
        """Check if a constraint's pattern matches the given tool args."""
        pattern = constraint.get("pattern", "")
        pattern_type = constraint.get("pattern_type", "glob")
        match_field = constraint.get("match_field", "pattern")
        args_pattern = constraint.get("args_pattern", "")

        # Determine the value to match against
        if match_field == "path":
            values = self._extract_path_values(args)
        elif match_field == "host":
            values = self._extract_host_values(args)
        else:
            # For generic pattern: match against all individual arg values
            # plus the full JSON representation
            values = [str(v) for v in args.values()] + [args_str]

        # Try matching any extracted value
        for value in values:
            if pattern_type == "regex":
                if self._regex_match(pattern, value):
                    if self._args_pattern_match(args_pattern, args_str):
                        return True
            else:
                if self._glob_match(pattern, value):
                    if self._args_pattern_match(args_pattern, args_str):
                        return True

        return False

    def _args_pattern_match(self, args_pattern: str, args_str: str) -> bool:
        """Check if args_pattern (if any) also matches. Empty pattern = always pass."""
        if not args_pattern:
            return True
        return self._glob_match(args_pattern, args_str)

    @staticmethod
    def _extract_path_values(args: dict[str, Any]) -> list[str]:
        """Extract path-like values from tool args."""
        values: list[str] = []
        for key in ("path", "file", "target", "source", "dest", "destination"):
            if key in args:
                values.append(str(args[key]))
        if not values:
            values.append(json.dumps(args))
        return values

    @staticmethod
    def _extract_host_values(args: dict[str, Any]) -> list[str]:
        """Extract host/URL-like values from tool args.
        Parses URL strings to also include the hostname component for matching.
        """
        from urllib.parse import urlparse

        values: list[str] = []
        for key in ("url", "host", "endpoint", "base_url", "target"):
            if key in args:
                raw = str(args[key])
                values.append(raw)
                # If it looks like a URL, extract the hostname for host-based matching
                if "://" in raw or raw.startswith("//"):
                    try:
                        parsed = urlparse(raw if "://" in raw else f"https:{raw}")
                        if parsed.hostname:
                            values.append(parsed.hostname)
                    except Exception:
                        pass
        if not values:
            values.append(json.dumps(args))
        return values

    @staticmethod
    def _glob_match(pattern: str, value: str) -> bool:
        """Match using fnmatch (glob). Case-insensitive.
        If pattern contains no wildcard characters, wraps it in *...*
        to perform substring matching. Otherwise uses fnmatch directly.
        """
        lower_pattern = pattern.lower()
        lower_value = value.lower()
        if not any(c in lower_pattern for c in ("*", "?", "[")):
            # No wildcards — do substring match
            return lower_pattern in lower_value
        return fnmatch.fnmatch(lower_value, lower_pattern)

    @staticmethod
    def _regex_match(pattern: str, value: str) -> bool:
        """Match using compiled regex."""
        try:
            return bool(re.search(pattern, value, re.IGNORECASE))
        except re.error:
            return False

    # ── runtime mutation ───────────────────────────────────────────────────────

    def add_constraint(self, constraint: dict[str, Any]) -> str:
        """Add a constraint at runtime, assigning it an ID. Returns the new ID."""
        self._rule_counter += 1
        rid = f"rule_{self._rule_counter:03d}"
        constraint["id"] = rid
        if "message" not in constraint:
            constraint["message"] = self._build_message(
                constraint.get("action", "FORBID"),
                constraint.get("tool", ""),
                constraint.get("pattern", ""),
                constraint.get("min_tier", ""),
            )
        self._constraints.append(constraint)
        return rid

    def remove_constraint(self, pattern_id: str) -> bool:
        """Remove a constraint by ID. Returns True if found and removed."""
        for i, c in enumerate(self._constraints):
            if c.get("id") == pattern_id:
                self._constraints.pop(i)
                return True
        return False

    @property
    def constraint_count(self) -> int:
        """Number of currently loaded constraints."""
        return len(self._constraints)
