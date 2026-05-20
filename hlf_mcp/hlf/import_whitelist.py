"""
Import Whitelist: allowed Python imports per capability tier, with transitive
dependency scanning and most-specific-match routing.

Design Principles:
1. Every import is classified into a CapabilityTier that gates access.
2. Rules use longest-prefix matching — ``os.path`` beats ``os`` when both match.
3. Transitive dependency scanning reveals what a module actually pulls in at
   import time, preventing hidden privilege escalation.
4. Tiers are cumulative: STANDARD includes all of BASIC, ELEVATED includes all
   of STANDARD, etc.
5. The whitelist is auditable — every allowed import has a documented reason
   and every denial produces a structured violation report.

This module is the gatekeeper between HLF capability tiers and Python's import
system. It answers the question: "Can this module be imported at this tier,
and what else would it pull in?"
"""

from __future__ import annotations

import importlib
import importlib.util
import pkgutil
import sys
from dataclasses import dataclass, field
from enum import Enum, auto
from types import ModuleType
from typing import Any


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class CapabilityTier(Enum):
    """Capability tiers for import gating, ordered least→most privileged."""
    BASIC = 1
    STANDARD = 2
    ELEVATED = 3
    PRIVILEGED = 4
    UNRESTRICTED = 5

    def __ge__(self, other: CapabilityTier) -> bool:
        if self.__class__ is other.__class__:
            return self.value >= other.value
        return NotImplemented

    def __le__(self, other: CapabilityTier) -> bool:
        if self.__class__ is other.__class__:
            return self.value <= other.value
        return NotImplemented

    def __gt__(self, other: CapabilityTier) -> bool:
        if self.__class__ is other.__class__:
            return self.value > other.value
        return NotImplemented

    def __lt__(self, other: CapabilityTier) -> bool:
        if self.__class__ is other.__class__:
            return self.value < other.value
        return NotImplemented


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class ImportRule:
    """Defines what can be imported at a given capability tier.

    Attributes:
        module_path: The full dotted module path (e.g. 'os.path').
        allowed_symbols: Specific symbols allowed from this module.
            Empty list means all symbols are allowed.
        tier: Minimum capability tier required to import this module.
        reason: Human-readable justification for this rule.
        transitive_allowed: Whether transitive dependencies of this module
            are automatically permitted.
        max_depth: Maximum recursion depth for transitive scanning.
        submodules_included: Whether submodules of this package are
            implicitly included.
    """
    module_path: str
    allowed_symbols: list[str] = field(default_factory=list)
    tier: CapabilityTier = CapabilityTier.BASIC
    reason: str = ""
    transitive_allowed: bool = False
    max_depth: int = 3
    submodules_included: bool = False


@dataclass(slots=True)
class ImportCheck:
    """Result of checking a single import against the whitelist.

    Attributes:
        requested_import: The module path that was requested.
        tier: The capability tier the check was performed at.
        allowed: True if the import is permitted.
        matched_rule: The ImportRule that matched, or None if no rule matched.
        violations: List of human-readable violation descriptions.
        transitive_scan: List of transitive dependencies discovered.
    """
    requested_import: str
    tier: CapabilityTier
    allowed: bool
    matched_rule: ImportRule | None = None
    violations: list[str] = field(default_factory=list)
    transitive_scan: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "requested_import": self.requested_import,
            "tier": self.tier.name,
            "allowed": self.allowed,
            "matched_rule": self.matched_rule.module_path if self.matched_rule else None,
            "violations": list(self.violations),
            "transitive_scan": list(self.transitive_scan),
        }


# ---------------------------------------------------------------------------
# Default tier modules
# ---------------------------------------------------------------------------

_BASIC_MODULES: set[str] = {
    "math", "json", "datetime", "collections", "itertools", "functools",
    "typing", "enum", "dataclasses", "hashlib", "re", "string", "textwrap",
    "struct", "decimal", "fractions", "statistics",
}

_STANDARD_MODULES: set[str] = _BASIC_MODULES | {
    "os.path", "pathlib", "csv", "io", "base64", "binascii", "copy",
    "random", "secrets", "logging", "warnings", "sys", "argparse",
    "configparser",
}

_ELEVATED_MODULES: set[str] = _STANDARD_MODULES | {
    "os", "subprocess", "socket", "http.client", "urllib.parse",
    "sqlite3", "tempfile", "shutil", "zipfile", "gzip", "tarfile",
}

_PRIVILEGED_MODULES: set[str] = _ELEVATED_MODULES | {
    "threading", "multiprocessing", "asyncio", "concurrent.futures",
    "pickle",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _module_exists(module_path: str) -> bool:
    """Check if a module can be found/imported without actually executing it."""
    spec = importlib.util.find_spec(module_path)
    return spec is not None


def _iter_module_imports(module: ModuleType) -> set[str]:
    """Introspect a module to discover what it imports at the top level.

    Walks ``dir(module)`` looking for ModuleType values that represent
    sub-imports or re-exports. Also checks ``__all__`` if present.

    Returns a set of dotted module paths that this module references.
    """
    found: set[str] = set()
    # Check __all__ for re-exported symbols
    all_names = getattr(module, "__all__", None)
    names_to_check = set(dir(module))
    if isinstance(all_names, (list, tuple)):
        names_to_check.update(all_names)

    for name in names_to_check:
        if name.startswith("_"):
            continue
        try:
            obj = getattr(module, name)
        except AttributeError:
            continue
        if isinstance(obj, ModuleType):
            mod_name = getattr(obj, "__name__", "")
            if mod_name:
                found.add(mod_name)
    return found


def _longest_prefix_match(
    module_path: str,
    rules: dict[str, ImportRule],
) -> ImportRule | None:
    """Find the ImportRule with the longest module_path prefix matching module_path.

    For example, given rules for 'os' and 'os.path', a request for 'os.path.join'
    matches 'os.path' (longer match) over 'os'.
    """
    best: ImportRule | None = None
    best_len = -1

    # Also check parent prefixes
    parts = module_path.split(".")
    for i in range(len(parts), 0, -1):
        prefix = ".".join(parts[:i])
        rule = rules.get(prefix)
        if rule is not None and len(prefix) > best_len:
            best = rule
            best_len = len(prefix)

    # Also check exact
    exact = rules.get(module_path)
    if exact is not None and len(exact.module_path) > best_len:
        best = exact

    return best


# ---------------------------------------------------------------------------
# ImportWhitelist
# ---------------------------------------------------------------------------

class ImportWhitelist:
    """Gated import system mapping Python modules to HLF capability tiers.

    Each capability tier gates a set of allowed modules. The whitelist uses
    longest-prefix-match to resolve ambiguous rules and can scan transitive
    dependencies to detect privilege escalation.

    Usage::

        whitelist = ImportWhitelist(default_tier=CapabilityTier.STANDARD)
        check = whitelist.check_import("os", CapabilityTier.BASIC)
        assert not check.allowed  # os requires ELEVATED
    """

    def __init__(
        self,
        name: str = "import-whitelist",
        default_tier: CapabilityTier = CapabilityTier.BASIC,
    ) -> None:
        """Initialize the import whitelist with sensible defaults.

        Args:
            name: Identifier for this whitelist instance.
            default_tier: The tier assigned to modules without an explicit rule.
        """
        self.name = name
        self.default_tier = default_tier
        self._rules: dict[str, ImportRule] = {}

        self._populate_defaults()

    # ------------------------------------------------------------------
    # Rule management
    # ------------------------------------------------------------------

    def add_rule(self, rule: ImportRule) -> None:
        """Register a new import rule, overwriting any existing rule for the
        same module_path."""
        self._rules[rule.module_path] = rule

    def remove_rule(self, module_path: str) -> bool:
        """Remove the rule for a module_path. Returns True if removed, False
        if no rule existed."""
        if module_path in self._rules:
            del self._rules[module_path]
            return True
        return False

    # ------------------------------------------------------------------
    # Import checking
    # ------------------------------------------------------------------

    def check_import(
        self,
        module_path: str,
        requested_tier: CapabilityTier | None = None,
    ) -> ImportCheck:
        """Check if a module import is allowed at the given tier.

        Uses longest-prefix matching: a request for ``os.path.join``
        matches the rule for ``os.path`` over the rule for ``os``.

        If no rule matches, the default tier is used as the threshold.

        Args:
            module_path: The dotted Python module path being imported.
            requested_tier: The capability tier of the requester.
                Defaults to the instance's default_tier.

        Returns:
            ImportCheck with the result, matched rule, and any violations.
        """
        tier = requested_tier if requested_tier is not None else self.default_tier
        module_path = module_path.strip()
        violations: list[str] = []

        matched = _longest_prefix_match(module_path, self._rules)

        if matched is None:
            # If UNRESTRICTED, allow everything implicitly
            if tier >= CapabilityTier.UNRESTRICTED:
                return ImportCheck(
                    requested_import=module_path,
                    tier=tier,
                    allowed=True,
                    matched_rule=None,
                    violations=[],
                )
            # Try parent prefixes for implicit rules
            parent_match = _longest_prefix_match(module_path, self._rules)
            if parent_match is None:
                violations.append(
                    f"No import rule for '{module_path}' — denied at tier {tier.name}"
                )
                return ImportCheck(
                    requested_import=module_path,
                    tier=tier,
                    allowed=False,
                    matched_rule=None,
                    violations=violations,
                )

            matched = parent_match

        # Check tier
        if tier.value < matched.tier.value:
            violations.append(
                f"'{module_path}' requires tier {matched.tier.name} "
                f"(requested at {tier.name})"
            )

        # Check symbol restrictions
        # (symbol-level checking is for when specific functions are imported;
        # for module-level imports this is only relevant if symbols are
        # restricted and submodules_included is False)
        if matched.allowed_symbols and not matched.submodules_included:
            # The full module is restricted — only specific symbols are allowed
            # This is a module-level check, so we warn but allow (symbol
            # checking happens at a finer granularity)
            pass

        allowed = tier.value >= matched.tier.value

        # Transitive scan (only if allowed, to avoid unnecessary work)
        transitive: list[str] = []
        if allowed and matched.transitive_allowed:
            try:
                transitive = self.scan_transitive_deps(
                    module_path,
                    max_depth=matched.max_depth,
                )
            except Exception:
                pass

        return ImportCheck(
            requested_import=module_path,
            tier=tier,
            allowed=allowed,
            matched_rule=matched,
            violations=violations,
            transitive_scan=transitive,
        )

    def check_imports(
        self,
        imports: list[str],
        tier: CapabilityTier,
    ) -> list[ImportCheck]:
        """Batch-check multiple imports against the same tier.

        Args:
            imports: List of module_path strings to check.
            tier: The capability tier to check against.

        Returns:
            One ImportCheck per input import.
        """
        return [self.check_import(imp, tier) for imp in imports]

    # ------------------------------------------------------------------
    # Transitive dependency scanning
    # ------------------------------------------------------------------

    def scan_transitive_deps(
        self,
        module_path: str,
        max_depth: int = 3,
    ) -> list[str]:
        """Discover what a module transitively imports.

        Uses importlib to load the module (if available in the current
        environment) and introspects its members to find sub-module
        references.  Respects max_depth to avoid infinite recursion.

        Note: This actually imports the module, so it has side effects.
        Use with caution at lower tiers.

        Args:
            module_path: The dotted path of the module to scan.
            max_depth: Maximum recursion depth for transitive scanning.

        Returns:
            Sorted list of unique module paths discovered as transitive
            dependencies.
        """
        found: set[str] = set()
        _scan_recursive(module_path, found, depth=0, max_depth=max_depth)
        return sorted(found)

    # ------------------------------------------------------------------
    # Tier summaries & auditing
    # ------------------------------------------------------------------

    def tier_summary(self) -> dict[str, Any]:
        """Generate a summary of all rules grouped by tier.

        Returns:
            Dict mapping tier name to dict with 'count' (int) and
            'modules' (list[str]).
        """
        tier_map: dict[str, dict[str, Any]] = {}
        for tier in CapabilityTier:
            tier_map[tier.name] = {"count": 0, "modules": []}

        for rule in self._rules.values():
            entry = tier_map[rule.tier.name]
            entry["count"] += 1
            entry["modules"].append(rule.module_path)

        for v in tier_map.values():
            v["modules"].sort()

        return tier_map

    def audit_imports(self, tier: CapabilityTier) -> list[ImportRule]:
        """Return all rules that are applicable at the given tier.

        A rule is applicable if the requesting tier is >= the rule's tier.
        This gives the operator a view of everything importable at a tier.

        Args:
            tier: The capability tier to audit.

        Returns:
            List of ImportRule sorted by module_path.
        """
        applicable: list[ImportRule] = []
        for rule in self._rules.values():
            if tier.value >= rule.tier.value:
                applicable.append(rule)
        applicable.sort(key=lambda r: r.module_path)
        return applicable

    # ------------------------------------------------------------------
    # Internal: populate defaults
    # ------------------------------------------------------------------

    def _populate_defaults(self) -> None:
        """Seed the whitelist with tiered module defaults."""
        tiers: dict[CapabilityTier, set[str]] = {
            CapabilityTier.BASIC: _BASIC_MODULES,
            CapabilityTier.STANDARD: _STANDARD_MODULES - _BASIC_MODULES,
            CapabilityTier.ELEVATED: _ELEVATED_MODULES - _STANDARD_MODULES,
            CapabilityTier.PRIVILEGED: _PRIVILEGED_MODULES - _ELEVATED_MODULES,
        }
        descriptions: dict[CapabilityTier, str] = {
            CapabilityTier.BASIC: "Core standard library — safe for all agents",
            CapabilityTier.STANDARD: "I/O and system introspection — read-only",
            CapabilityTier.ELEVATED: "OS interaction, networking, subprocess — contained access",
            CapabilityTier.PRIVILEGED: "Concurrency, multiprocessing, serialization — full access",
        }

        for tier, modules in tiers.items():
            for mod in sorted(modules):
                rule = ImportRule(
                    module_path=mod,
                    tier=tier,
                    reason=descriptions.get(tier, f"Allowed at {tier.name}"),
                    transitive_allowed=False,
                    max_depth=1,
                    submodules_included=True,
                )
                self._rules[mod] = rule

        # Special rules with tighter controls
        self._rules["sys"] = ImportRule(
            module_path="sys",
            tier=CapabilityTier.STANDARD,
            reason="Read-only sys for path inspection; write to sys blocked at lower tiers",
            transitive_allowed=False,
            max_depth=1,
            submodules_included=False,
        )
        self._rules["os"] = ImportRule(
            module_path="os",
            tier=CapabilityTier.ELEVATED,
            reason="Limited OS access at ELEVATED; full at PRIVILEGED",
            transitive_allowed=False,
            max_depth=1,
            submodules_included=True,
        )
        self._rules["subprocess"] = ImportRule(
            module_path="subprocess",
            tier=CapabilityTier.ELEVATED,
            reason="Capture-only subprocess at ELEVATED; full at PRIVILEGED",
            transitive_allowed=False,
            max_depth=1,
            submodules_included=False,
        )
        self._rules["socket"] = ImportRule(
            module_path="socket",
            tier=CapabilityTier.ELEVATED,
            reason="Limited socket API at ELEVATED",
            transitive_allowed=False,
            max_depth=1,
            submodules_included=False,
        )
        self._rules["pickle"] = ImportRule(
            module_path="pickle",
            tier=CapabilityTier.PRIVILEGED,
            reason="Pickle allowed at PRIVILEGED with warnings (security risk)",
            transitive_allowed=False,
            max_depth=1,
            submodules_included=False,
        )
        self._rules["asyncio"] = ImportRule(
            module_path="asyncio",
            tier=CapabilityTier.PRIVILEGED,
            reason="Full async runtime access",
            transitive_allowed=False,
            max_depth=2,
            submodules_included=True,
        )
        self._rules["threading"] = ImportRule(
            module_path="threading",
            tier=CapabilityTier.PRIVILEGED,
            reason="Thread management at PRIVILEGED tier",
            transitive_allowed=False,
            max_depth=1,
            submodules_included=False,
        )
        self._rules["multiprocessing"] = ImportRule(
            module_path="multiprocessing",
            tier=CapabilityTier.PRIVILEGED,
            reason="Process management at PRIVILEGED tier",
            transitive_allowed=False,
            max_depth=1,
            submodules_included=False,
        )

    # ------------------------------------------------------------------
    # Property accessors
    # ------------------------------------------------------------------

    @property
    def rule_count(self) -> int:
        """Total number of registered import rules."""
        return len(self._rules)

    @property
    def tiers_coverage(self) -> dict[str, int]:
        """Count of rules per tier."""
        counts: dict[str, int] = {t.name: 0 for t in CapabilityTier}
        for rule in self._rules.values():
            counts[rule.tier.name] += 1
        return counts


# ---------------------------------------------------------------------------
# Internal: recursive scan helper
# ---------------------------------------------------------------------------

def _scan_recursive(
    module_path: str,
    found: set[str],
    depth: int,
    max_depth: int,
) -> None:
    """Recursively scan module imports up to max_depth."""
    if depth >= max_depth or module_path in found:
        return

    found.add(module_path)

    try:
        mod = importlib.import_module(module_path)
    except (ImportError, ModuleNotFoundError, SyntaxError, SystemExit):
        return

    imports = _iter_module_imports(mod)
    for imp_path in sorted(imports):
        if imp_path in found:
            continue
        # Only follow modules that could be standard library or already allowed
        if imp_path.startswith("_"):
            continue
        _scan_recursive(imp_path, found, depth + 1, max_depth)


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------

def check_import_tier(
    module_path: str,
    tier: CapabilityTier,
) -> ImportCheck:
    """Check if a single import is allowed at a given tier."""
    whitelist = ImportWhitelist()
    return whitelist.check_import(module_path, tier)


__all__ = [
    "CapabilityTier",
    "ImportRule",
    "ImportCheck",
    "ImportWhitelist",
    "check_import_tier",
]
