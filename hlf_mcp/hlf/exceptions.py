"""HLF tool execution exceptions for MCP isError signaling.

Instead of catching exceptions inside tools and returning
``{"status": "error", ...}`` dicts as normal results, tools raise
typed HLF exceptions.  FastMCP converts unhandled exceptions into
MCP-standard ``isError: true`` ToolExecutionError responses so agents
can reliably distinguish execution failures from legitimate results.
"""

from __future__ import annotations


class HLFToolError(Exception):
    """Base for HLF tool execution errors with structured diagnostics."""

    def __init__(self, message: str, diagnostics: dict | None = None) -> None:
        super().__init__(message)
        self.diagnostics = diagnostics or {}


class HLFCompileError(HLFToolError):
    """Compilation failure with source location."""

    def __init__(self, message: str, line: int = 0, col: int = 0) -> None:
        super().__init__(message, {"line": line, "col": col})


class HLFValidationError(HLFToolError):
    """Input validation failure (missing/invalid arguments)."""


class HLFExecutionError(HLFToolError):
    """Runtime execution failure."""


class HLFGasExceededError(HLFToolError):
    """Gas limit exceeded."""

    def __init__(self, gas_used: int, gas_limit: int) -> None:
        super().__init__(
            f"Gas limit exceeded: used {gas_used}/{gas_limit}",
            {"gas_used": gas_used, "gas_limit": gas_limit},
        )
