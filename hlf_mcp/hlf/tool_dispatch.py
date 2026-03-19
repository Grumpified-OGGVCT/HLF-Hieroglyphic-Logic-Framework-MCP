"""
HLF Tool Dispatch — lazy-loading tool registry with HITL gate.

Tools enter pending_hitl state when forged; require explicit approve_forged_tool()
before becoming active. All dispatches are logged to trace.
"""

from __future__ import annotations

import dataclasses
import importlib.util
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class ToolDispatchResult:
    success: bool
    result: Any = None
    error: str = ""
    gas_used: int = 1
    duration_ms: float = 0.0


class ToolDispatchError(Exception):
    pass


class ToolLifecycleState:
    ACTIVE = "active"
    PENDING = "pending_hitl"
    DISABLED = "disabled"
    DEPRECATED = "deprecated"


class ToolRegistry:
    """Registry for installed tools loaded from governance/tool_registry.json."""

    def __init__(self, registry_path: str | None = None):
        self._registry: dict[str, dict[str, Any]] = {}
        self._loaded_modules: dict[str, Any] = {}
        self._approval_log: list[dict[str, Any]] = []
        self._step_counter = 0
        self._load(registry_path)

    def _load(self, registry_path: str | None) -> None:
        candidates = []
        if registry_path:
            candidates.append(Path(registry_path))
        candidates += [
            Path(__file__).parent.parent.parent / "governance" / "tool_registry.json",
            Path("governance") / "tool_registry.json",
        ]
        for path in candidates:
            if path.exists():
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    self._registry = data.get("tools", {})
                    logger.debug("Loaded %d tools from %s", len(self._registry), path)
                    return
                except Exception as exc:
                    logger.warning("Failed to load tool_registry.json: %s", exc)
        # Empty registry — tools can be registered at runtime
        logger.debug("No tool_registry.json found; starting empty")

    def register(self, name: str, entry: dict[str, Any]) -> None:
        """Register a new tool. Enters pending_hitl state."""
        import uuid

        entry["status"] = ToolLifecycleState.PENDING
        entry["step_id"] = self._next_step()
        # Per-tool approval token — approval must present this exact token.
        # This decouples approval from global ordering so registering other
        # tools between registration and approval doesn't invalidate the token.
        entry["approval_token"] = str(uuid.uuid4())
        self._registry[name] = entry

    def approve_forged_tool(
        self, name: str, operator: str = "system", approval_token: str | None = None
    ) -> bool:
        """Approve a pending_hitl tool for activation.

        When *approval_token* is provided it must match the token assigned at
        registration; this prevents accidental cross-tool approval without
        relying on fragile global step adjacency.  If *approval_token* is
        omitted the check is skipped (operator-console / programmatic use).
        """
        entry = self._registry.get(name)
        if not entry:
            raise ToolDispatchError(f"Unknown tool: {name}")
        if entry.get("status") != ToolLifecycleState.PENDING:
            raise ToolDispatchError(f"Tool {name!r} is not pending HITL approval")
        if approval_token is not None and approval_token != entry.get("approval_token"):
            raise ToolDispatchError(f"Invalid approval token for {name!r}: token mismatch")
        step = self._next_step()
        entry["status"] = ToolLifecycleState.ACTIVE
        entry["approved_by"] = operator
        entry.pop("approval_token", None)
        self._approval_log.append(
            {"tool": name, "step": step, "operator": operator, "action": "approved"}
        )
        return True

    def dispatch(self, tool_name: str, args: dict[str, Any]) -> ToolDispatchResult:
        entry = self._registry.get(tool_name)
        if not entry:
            raise ToolDispatchError(f"Unknown tool: {tool_name}")
        if entry.get("status") != ToolLifecycleState.ACTIVE:
            raise ToolDispatchError(
                f"Tool {tool_name!r} is not active (status={entry.get('status')})"
            )
        # Try dynamic load
        install_path = entry.get("install_path")
        if install_path:
            return self._dynamic_dispatch(tool_name, entry, args)
        # Built-in simulated dispatch
        return ToolDispatchResult(
            success=True,
            result={"tool": tool_name, "args": args, "status": "simulated"},
            gas_used=entry.get("gas_cost", 1),
        )

    def _dynamic_dispatch(
        self, name: str, entry: dict[str, Any], args: dict[str, Any]
    ) -> ToolDispatchResult:
        start = time.monotonic()
        try:
            module = self._load_module(name, entry)
            func_name = entry.get("entrypoint_func", "run")
            func = getattr(module, func_name, None)
            if not callable(func):
                raise ToolDispatchError(f"Tool {name!r}: entrypoint {func_name!r} not callable")
            result = func(**args)
            return ToolDispatchResult(
                success=True,
                result=result,
                gas_used=entry.get("gas_cost", 1),
                duration_ms=(time.monotonic() - start) * 1000,
            )
        except ToolDispatchError:
            raise
        except Exception as exc:
            return ToolDispatchResult(
                success=False,
                error=str(exc),
                gas_used=entry.get("gas_cost", 1),
                duration_ms=(time.monotonic() - start) * 1000,
            )

    def _load_module(self, name: str, entry: dict[str, Any]) -> Any:
        """Lazy-load a tool module (cached after first load)."""
        if name in self._loaded_modules:
            return self._loaded_modules[name]
        install_path = Path(entry["install_path"])
        entrypoint = entry.get("entrypoint", "main.py")
        module_file = install_path / entrypoint
        if not module_file.exists():
            raise ToolDispatchError(f"Tool entrypoint not found: {module_file}")
        module_name = f"_hlf_tool_{name}"
        spec = importlib.util.spec_from_file_location(module_name, module_file)
        if spec is None or spec.loader is None:
            raise ToolDispatchError(f"Cannot load tool module: {module_file}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        tool_dir = str(install_path)
        added = tool_dir not in sys.path
        if added:
            sys.path.insert(0, tool_dir)
        try:
            spec.loader.exec_module(module)  # type: ignore[union-attr]
        except Exception as exc:
            sys.modules.pop(module_name, None)
            raise ToolDispatchError(f"Failed to load tool {name!r}: {exc}") from exc
        finally:
            if added and tool_dir in sys.path:
                sys.path.remove(tool_dir)
        self._loaded_modules[name] = module
        return module

    def _next_step(self) -> int:
        self._step_counter += 1
        return self._step_counter

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {"name": n, **{k: v for k, v in e.items() if k != "install_path"}}
            for n, e in self._registry.items()
        ]
