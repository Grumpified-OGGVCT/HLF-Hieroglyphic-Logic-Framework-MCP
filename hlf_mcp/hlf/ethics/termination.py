"""
Placeholder for self-termination / fail-closed protocol.

The real implementation should:
- Decide when execution must halt to prevent harm or policy breach
- Emit auditable reasoning for termination events
- Surface signals to the VM/runtime for graceful shutdown
"""

from __future__ import annotations

from typing import Any


def should_terminate(ast: dict[str, Any] | None, violations: list[str]) -> bool:
    """Stub: return False until termination policy is implemented."""
    return False
