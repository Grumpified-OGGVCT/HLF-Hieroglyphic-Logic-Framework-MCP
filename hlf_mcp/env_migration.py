"""
Environment variable migration helpers for the SwarmGlass transition.

Provides backward-compatible env var resolution: old HLF_* names still work
but emit DeprecationWarning, steering users toward new SWARMGLASS_* names.
Mappings are derived from SHIM_DESIGN.md section 5.2.

On import, automatically loads .env from the project root and sets both
SWARMGLASS_* and HLF_* equivalents so all internal code (which reads HLF_*)
and external config (.env uses SWARMGLASS_*) work seamlessly.

Usage:
    from hlf_mcp.env_migration import get_env

    experimental = get_env("SWARMGLASS_HLF_ENABLED", "0")
    transport    = get_env("SWARMGLASS_TRANSPORT", "stdio")
"""

from __future__ import annotations

import logging
import os
import warnings
from pathlib import Path

_log = logging.getLogger(__name__)

# ── Mapping: old HLF_* name → new SWARMGLASS_* name ────────────────────────
# Derived from SHIM_DESIGN.md §5.2 (SG_* → SWARMGLASS_* for consistency).
ENV_VAR_MIGRATIONS: dict[str, str] = {
    # Core transport
    "HLF_TRANSPORT":                            "SWARMGLASS_TRANSPORT",
    "HLF_HOST":                                 "SWARMGLASS_HOST",
    "HLF_PORT":                                 "SWARMGLASS_PORT",
    # Secrets / crypto
    "HLF_MASTER_KEY":                           "SWARMGLASS_MASTER_KEY",
    # State & storage
    "HLF_STATE_DIR":                            "SWARMGLASS_STATE_DIR",
    "HLF_MEMORY_DB":                            "SWARMGLASS_MEMORY_DB",
    "HLF_MEMORY_DB_PATH":                       "SWARMGLASS_MEMORY_DB_PATH",
    "HLF_AUDIT_DB":                             "SWARMGLASS_AUDIT_DB",
    "HLF_AUDIT_CHAIN_LOG":                      "SWARMGLASS_AUDIT_CHAIN_LOG",
    "HLF_AUDIT_CHAIN_LAST_HASH":                "SWARMGLASS_AUDIT_CHAIN_LAST_HASH",
    "LAST_HASH":                                "SWARMGLASS_LAST_HASH",
    # Agent configuration
    "HLF_AGENT_TIER":                           "SWARMGLASS_AGENT_TIER",
    "HLF_STRICT":                               "SWARMGLASS_STRICT",
    "HLF_APPROVAL_LEDGER_DB":                   "SWARMGLASS_APPROVAL_LEDGER_DB",
    # Auth
    "HLF_API_TOKEN":                            "SWARMGLASS_API_TOKEN",
    # External comparator
    "HLF_HKS_EXTERNAL_COMPARATOR_SCRIPT":       "SWARMGLASS_HKS_EXTERNAL_COMPARATOR_SCRIPT",
    "HLF_HKS_EXTERNAL_COMPARATOR_TIMEOUT":      "SWARMGLASS_HKS_EXTERNAL_COMPARATOR_TIMEOUT",
    # Experimental mode (with HLF_EXP shorthand)
    "HLF_EXPERIMENTAL_MODE":                    "SWARMGLASS_HLF_ENABLED",
    "HLF_EXP":                                  "SWARMGLASS_HLF_ENABLED",
}

# ── Reverse mapping: NEW → OLD (for auto-populating HLF_* from SWARMGLASS_*) ─
_NEW_TO_OLD: dict[str, list[str]] = {}
for _old, _new in ENV_VAR_MIGRATIONS.items():
    _NEW_TO_OLD.setdefault(_new, []).append(_old)


def _find_project_root() -> Path | None:
    """Walk up from this file looking for a .env or setup_wizard.py."""
    candidate = Path(__file__).resolve().parent.parent
    for _ in range(6):
        if (candidate / ".env").is_file() or (candidate / "setup_wizard.py").is_file():
            return candidate
        parent = candidate.parent
        if parent == candidate:
            break
        candidate = parent
    return None


def _parse_dotenv(path: Path) -> dict[str, str]:
    """Parse a .env file (simple KEY=VALUE parser, handles quotes and comments)."""
    result: dict[str, str] = {}
    if not path.is_file():
        return result
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        # Strip surrounding quotes
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        if key and value:
            result[key] = value
    return result


def _load_env_file() -> None:
    """Load .env into os.environ, setting both SWARMGLASS_* and HLF_* equivalents.

    Called automatically at module import time. Safe to call multiple times —
    only sets vars that aren't already in the environment (env vars take priority
    over .env, per 12-factor convention).
    """
    root = _find_project_root()
    if root is None:
        return
    env_path = root / ".env"
    if not env_path.is_file():
        return

    dotenv_vars = _parse_dotenv(env_path)
    if not dotenv_vars:
        return

    for key, value in dotenv_vars.items():
        # Only set if not already in the real environment
        if key not in os.environ:
            os.environ[key] = value

        # Auto-populate HLF_* equivalents for SWARMGLASS_* vars
        if key.startswith("SWARMGLASS_"):
            old_names = _NEW_TO_OLD.get(key, [])
            for old_name in old_names:
                if old_name not in os.environ:
                    os.environ[old_name] = value


# ── Auto-load .env at import time ───────────────────────────────────────────
_load_env_file()


def get_env(var_name: str, default: str = "") -> str:
    """Resolve an environment variable with automatic HLF_* backwards compatibility.

    Priority:
        1. New ``SWARMGLASS_*`` name (canonical, no warning)
        2. Old ``HLF_*`` name (works but emits ``DeprecationWarning``)
        3. ``default`` value

    When **both** old and new are set the new name wins and a warning is
    emitted about the conflicting old value being ignored.

    Args:
        var_name: The canonical ``SWARMGLASS_*`` env var name.
        default:  Value returned when neither old nor new name is set.

    Returns:
        The resolved string value.
    """
    # 1. Canonical (new) name
    new_value = os.environ.get(var_name)

    # 2. Find any old→new mappings that target this var_name
    old_names = [old for old, new in ENV_VAR_MIGRATIONS.items() if new == var_name]

    # 3. Check old names
    old_values: dict[str, str] = {}
    for old_name in old_names:
        val = os.environ.get(old_name)
        if val is not None:
            old_values[old_name] = val

    # 4. Resolve
    if new_value is not None:
        if old_values:
            # Both new and old set -- new wins, warn about ignored old values
            # EXCEPT when they're identical (auto-populated from .env loading)
            for old_name, old_val in old_values.items():
                if old_val == new_value:
                    continue  # identical values — silent, .env auto-population
                warnings.warn(
                    f"Both {var_name} and {old_name} are set. "
                    f"Using {var_name}={new_value!r} "
                    f"(ignoring {old_name}={old_val!r}). "
                    f"Remove {old_name} to suppress this warning.",
                    DeprecationWarning,
                    stacklevel=2,
                )
            return new_value
        return new_value

    if old_values:
        # Only old name(s) set -- use it with deprecation warning
        for old_name, old_val in old_values.items():
            warnings.warn(
                f"Environment variable '{old_name}' is deprecated. "
                f"Use '{var_name}' instead. "
                f"Resolved {old_name}={old_val!r}.",
                DeprecationWarning,
                stacklevel=2,
            )
            _log.debug("Resolved %s from deprecated %s", var_name, old_name)
            return old_val

    return default
