"""
Placeholder for constitutional constraints.

Downstream agent: implement immutable guardrails for HLF programs, enforcing
hard-law constraints without adopting surveillance or paternalistic blocking.
Wire evaluation entrypoints back into the compiler pipeline where noted.
"""

from __future__ import annotations

from typing import Any


def evaluate_constitution(ast: dict[str, Any] | None, env: dict[str, Any] | None) -> list[str]:
    """
    Return a list of violations once constitutional checks are implemented.

    This is a stub so integration points compile cleanly; replace with real
    logic during ethics module bring-up.
    """
    return []
