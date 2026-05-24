"""
tests/test_env_migration.py — verify env var migration helpers for SwarmGlass.

Covers:
  - Old HLF_* names still work (deprecation)
  - New SWARMGLASS_* names work cleanly
  - New name takes precedence when both are set
  - DeprecationWarning emitted when old name used
  - Default values work correctly
  - HLF_EXP alias for HLF_EXPERIMENTAL_MODE
"""

from __future__ import annotations

import warnings

import pytest

from hlf_mcp.env_migration import ENV_VAR_MIGRATIONS, get_env


# ── Unit tests for get_env ──────────────────────────────────────────────────


def test_new_name_works(monkeypatch: pytest.MonkeyPatch) -> None:
    """New SWARMGLASS_* name returns its value cleanly."""
    monkeypatch.setenv("SWARMGLASS_EXPERIMENTAL", "1")
    monkeypatch.delenv("HLF_EXPERIMENTAL_MODE", raising=False)
    monkeypatch.delenv("HLF_EXP", raising=False)

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = get_env("SWARMGLASS_EXPERIMENTAL", "0")

    assert result == "1"
    assert len(w) == 0, f"Expected no warnings, got {[str(x.message) for x in w]}"


def test_old_name_still_works(monkeypatch: pytest.MonkeyPatch) -> None:
    """Old HLF_EXPERIMENTAL_MODE still resolves and emits DeprecationWarning."""
    monkeypatch.delenv("SWARMGLASS_EXPERIMENTAL", raising=False)
    monkeypatch.setenv("HLF_EXPERIMENTAL_MODE", "1")

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = get_env("SWARMGLASS_EXPERIMENTAL", "0")

    assert result == "1"
    assert len(w) == 1
    assert issubclass(w[0].category, DeprecationWarning)
    assert "HLF_EXPERIMENTAL_MODE" in str(w[0].message)
    assert "SWARMGLASS_EXPERIMENTAL" in str(w[0].message)


def test_hlf_exp_alias_works(monkeypatch: pytest.MonkeyPatch) -> None:
    """HLF_EXP shorthand alias also resolves to SWARMGLASS_EXPERIMENTAL."""
    monkeypatch.delenv("SWARMGLASS_EXPERIMENTAL", raising=False)
    monkeypatch.setenv("HLF_EXP", "1")

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = get_env("SWARMGLASS_EXPERIMENTAL", "0")

    assert result == "1"
    assert len(w) == 1
    assert issubclass(w[0].category, DeprecationWarning)
    assert "HLF_EXP" in str(w[0].message)


def test_new_takes_precedence_over_old(monkeypatch: pytest.MonkeyPatch) -> None:
    """When both old and new are set, new name wins."""
    monkeypatch.setenv("SWARMGLASS_EXPERIMENTAL", "new-value")
    monkeypatch.setenv("HLF_EXPERIMENTAL_MODE", "old-value")

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = get_env("SWARMGLASS_EXPERIMENTAL", "0")

    assert result == "new-value"
    assert len(w) == 1
    assert issubclass(w[0].category, DeprecationWarning)
    assert "ignoring" in str(w[0].message).lower()


def test_default_value_when_nothing_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """When neither old nor new is set, default is returned."""
    monkeypatch.delenv("SWARMGLASS_EXPERIMENTAL", raising=False)
    monkeypatch.delenv("HLF_EXPERIMENTAL_MODE", raising=False)
    monkeypatch.delenv("HLF_EXP", raising=False)

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = get_env("SWARMGLASS_EXPERIMENTAL", "0")

    assert result == "0"
    assert len(w) == 0


def test_default_string_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default parameter respects the passed value (empty string)."""
    monkeypatch.delenv("SWARMGLASS_EXPERIMENTAL", raising=False)
    monkeypatch.delenv("HLF_EXPERIMENTAL_MODE", raising=False)

    result = get_env("SWARMGLASS_EXPERIMENTAL", "")
    assert result == ""


def test_custom_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """A custom default is returned when nothing is set."""
    monkeypatch.delenv("SWARMGLASS_TRANSPORT", raising=False)
    monkeypatch.delenv("HLF_TRANSPORT", raising=False)

    result = get_env("SWARMGLASS_TRANSPORT", "stdio")
    assert result == "stdio"


def test_new_name_silent_when_only_new_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """No warning when only the new name is set (clean migration path)."""
    monkeypatch.setenv("SWARMGLASS_TRANSPORT", "sse")
    monkeypatch.delenv("HLF_TRANSPORT", raising=False)

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = get_env("SWARMGLASS_TRANSPORT", "stdio")

    assert result == "sse"
    assert len(w) == 0


def test_old_name_warns_for_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    """Old HLF_TRANSPORT emits DeprecationWarning."""
    monkeypatch.delenv("SWARMGLASS_TRANSPORT", raising=False)
    monkeypatch.setenv("HLF_TRANSPORT", "sse")

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = get_env("SWARMGLASS_TRANSPORT", "stdio")

    assert result == "sse"
    assert len(w) == 1
    assert issubclass(w[0].category, DeprecationWarning)
    assert "HLF_TRANSPORT" in str(w[0].message)
    assert "SWARMGLASS_TRANSPORT" in str(w[0].message)


def test_both_old_aliases_conflict_with_new(monkeypatch: pytest.MonkeyPatch) -> None:
    """When both HLF_EXP and HLF_EXPERIMENTAL_MODE are set alongside the new name,
    new wins and both old values are reported as ignored."""
    monkeypatch.setenv("SWARMGLASS_EXPERIMENTAL", "canonical")
    monkeypatch.setenv("HLF_EXPERIMENTAL_MODE", "mode-val")
    monkeypatch.setenv("HLF_EXP", "exp-val")

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = get_env("SWARMGLASS_EXPERIMENTAL", "0")

    assert result == "canonical"
    # One warning per conflicting old var
    assert len(w) == 2
    messages = " ".join(str(x.message) for x in w)
    assert "HLF_EXPERIMENTAL_MODE" in messages
    assert "HLF_EXP" in messages


# ── Mapping integrity ──────────────────────────────────────────────────────


def test_all_mapped_new_names_are_valid() -> None:
    """Every mapped new var name follows the SWARMGLASS_* convention."""
    for old_name, new_name in ENV_VAR_MIGRATIONS.items():
        assert new_name.startswith("SWARMGLASS_"), (
            f"New name {new_name!r} for old {old_name!r} "
            f"does not start with SWARMGLASS_"
        )


def test_experimental_mappings_share_target() -> None:
    """HLF_EXPERIMENTAL_MODE and HLF_EXP both map to the same target."""
    assert ENV_VAR_MIGRATIONS["HLF_EXPERIMENTAL_MODE"] == "SWARMGLASS_EXPERIMENTAL"
    assert ENV_VAR_MIGRATIONS["HLF_EXP"] == "SWARMGLASS_EXPERIMENTAL"


def test_no_duplicate_old_names() -> None:
    """No old name appears more than once in the mapping."""
    assert len(ENV_VAR_MIGRATIONS) == len(set(ENV_VAR_MIGRATIONS.keys()))
