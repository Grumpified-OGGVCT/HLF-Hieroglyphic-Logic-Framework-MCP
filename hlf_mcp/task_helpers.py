"""
Task execution helpers for HLF MCP tools.

Provides infrastructure for tools to opt into task-augmented execution
via the MCP Tasks protocol (experimental).  Long-running tools can use
these helpers to return a CreateTaskResult so the client can poll for
completion instead of waiting on a synchronous response.

WARNING: The underlying MCP task APIs are experimental and may change.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from mcp.types import (
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
    TASK_STATUS_WORKING,
    CreateTaskResult,
    Task,
    TaskMetadata,
    TaskStatus,
)

_log = logging.getLogger(__name__)

# ── Task annotation constants ────────────────────────────────────────────────

# Per-spec metadata key for task execution mode on a tool declaration.
# Clients see this in the tool's _meta and may request task-augmented execution.
TASK_META_KEY = "task"
TASK_EXECUTION_MODE_KEY = "execution_mode"

# Execution modes understood by the MCP spec:
MODE_REQUIRED = "required"   # tool MUST be called as a task
MODE_OPTIONAL = "optional"   # tool MAY be called as a task
MODE_FORBIDDEN = "forbidden" # tool MUST NOT be called as a task

# Metadata key for model-immediate-response (per MCP spec).
# Servers MAY include this in CreateTaskResult._meta to provide an immediate
# response string while the task executes in the background.
MODEL_IMMEDIATE_RESPONSE_KEY = "io.modelcontextprotocol/model-immediate-response"


def task_meta(execution_mode: str = MODE_OPTIONAL) -> dict[str, Any]:
    """Return a ``meta`` dict suitable for passing to ``@mcp.tool(meta=...)``.

    Args:
        execution_mode: One of ``"required"``, ``"optional"``, or ``"forbidden"``.
            Defaults to ``"optional"`` — the tool *may* be called as a task.
    """
    if execution_mode not in (MODE_REQUIRED, MODE_OPTIONAL, MODE_FORBIDDEN):
        raise ValueError(
            f"execution_mode must be one of {MODE_REQUIRED!r}, {MODE_OPTIONAL!r}, "
            f"{MODE_FORBIDDEN!r}, got {execution_mode!r}"
        )
    return {TASK_META_KEY: {TASK_EXECUTION_MODE_KEY: execution_mode}}


def create_task_result(
    task_id: str | None = None,
    *,
    status: TaskStatus = TASK_STATUS_WORKING,
    status_message: str | None = None,
    ttl_ms: int | None = None,
    immediate_response: str | None = None,
) -> CreateTaskResult:
    """Build a ``CreateTaskResult`` that the MCP client will poll against.

    This is the return value a tool should produce when it chooses to run
    in the background rather than blocking until completion.

    Args:
        task_id: Unique task identifier.  Defaults to a random UUID4 hex string.
        status: Initial task status (default ``"working"``).
        status_message: Optional human-readable status message.
        ttl_ms: Retention duration in milliseconds from creation.
        immediate_response: If provided, included in ``_meta`` under the
            ``model-immediate-response`` key so clients can show a placeholder
            while the task runs.

    Returns:
        A ``CreateTaskResult`` that the lowlevel MCP server recognises and
        surfaces to the client as a task-augmented response.
    """
    now = datetime.now(timezone.utc)
    task_id = task_id or uuid.uuid4().hex

    task = Task(
        taskId=task_id,
        status=status,
        statusMessage=status_message,
        createdAt=now,
        lastUpdatedAt=now,
        ttl=ttl_ms,
    )

    extra_meta: dict[str, Any] = {}
    if immediate_response:
        extra_meta[MODEL_IMMEDIATE_RESPONSE_KEY] = immediate_response

    return CreateTaskResult(task=task, _meta=extra_meta or None)


# ── Registration helpers ─────────────────────────────────────────────────────

# Set of tool names that have been annotated for task execution.
# Populated by ``register_task_capable_tools``.
TASK_CAPABLE_TOOLS: set[str] = set()


def register_task_capable_tools(tool_names: list[str]) -> None:
    """Record which HLF tools support task-augmented execution.

    This is informational — it doesn't change runtime behaviour but lets
    introspection and documentation discover task-capable tools easily.

    Args:
        tool_names: Iterable of tool function names (e.g. ``["hlf_swarm_run"]``).
    """
    TASK_CAPABLE_TOOLS.update(tool_names)
    _log.debug("Registered %d task-capable tools", len(tool_names))
