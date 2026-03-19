from __future__ import annotations

from pathlib import Path

import pytest

from hlf_mcp.hlf.tool_dispatch import ToolDispatchError, ToolLifecycleState, ToolRegistry


def test_register_creates_pending_hitl_tool_with_approval_token() -> None:
    registry = ToolRegistry()
    registry.register("demo.tool", {"gas_cost": 3})

    entry = registry._registry["demo.tool"]
    assert entry["status"] == ToolLifecycleState.PENDING
    assert entry["step_id"] == 1
    assert entry["approval_token"]


def test_approval_requires_matching_token() -> None:
    registry = ToolRegistry()
    registry.register("demo.tool", {})

    with pytest.raises(ToolDispatchError, match="token mismatch"):
        registry.approve_forged_tool("demo.tool", approval_token="wrong-token")


def test_dispatch_requires_activation_then_returns_simulated_result() -> None:
    registry = ToolRegistry()
    registry.register("demo.tool", {"gas_cost": 5})

    with pytest.raises(ToolDispatchError, match="not active"):
        registry.dispatch("demo.tool", {"message": "hi"})

    token = registry._registry["demo.tool"]["approval_token"]
    assert (
        registry.approve_forged_tool("demo.tool", operator="tester", approval_token=token) is True
    )

    result = registry.dispatch("demo.tool", {"message": "hi"})

    assert result.success is True
    assert result.result["status"] == "simulated"
    assert result.gas_used == 5
    assert registry._approval_log[-1]["operator"] == "tester"


def test_dynamic_dispatch_loads_entrypoint_from_install_path(tmp_path: Path) -> None:
    tool_dir = tmp_path / "demo_tool"
    tool_dir.mkdir()
    (tool_dir / "main.py").write_text(
        "def run(message: str) -> dict[str, str]:\n    return {'echo': message}\n",
        encoding="utf-8",
    )

    registry = ToolRegistry()
    registry.register(
        "dynamic.echo",
        {
            "install_path": str(tool_dir),
            "entrypoint": "main.py",
            "entrypoint_func": "run",
            "gas_cost": 7,
        },
    )
    token = registry._registry["dynamic.echo"]["approval_token"]
    registry.approve_forged_tool("dynamic.echo", approval_token=token)

    result = registry.dispatch("dynamic.echo", {"message": "hello"})

    assert result.success is True
    assert result.result == {"echo": "hello"}
    assert result.gas_used == 7
    assert result.duration_ms >= 0


def test_list_tools_omits_install_path_from_public_view(tmp_path: Path) -> None:
    registry = ToolRegistry()
    registry.register("demo.tool", {"install_path": str(tmp_path), "gas_cost": 2})

    tools = registry.list_tools()

    assert tools[0]["name"] == "demo.tool"
    assert "install_path" not in tools[0]
