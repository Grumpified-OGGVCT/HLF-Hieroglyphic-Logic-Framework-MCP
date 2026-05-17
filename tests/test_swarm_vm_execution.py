"""End-to-end test: swarm.hlf → compile → bytecode → VM → live agent spawn.

Demonstrates parsing, compilation, execution, spawning, and result collection.
Uses the asyncio backend so no Ollama or subprocess isolation is required.
"""

from __future__ import annotations

import pytest

from hlf_mcp.hlf.bytecode import HLFBytecode
from hlf_mcp.hlf.compiler import HLFCompiler
from hlf_mcp.hlf.runtime import HLFRuntime


SWARM_SOURCE = """\
# HLF v3 — Swarm VM Execution Test Fixture
[HLF-v3]
CALL spawn_agent "alpha" "planner" "plan architecture"
CALL spawn_agent "beta" "executor" "execute build"
CALL spawn_agent "gamma" "verifier" "verify output"
CALL wait_all_agents 60
Ω
"""


class TestSwarmVMExecution:
    def test_swarm_compiles_without_errors(self, monkeypatch) -> None:
        monkeypatch.setenv("HLF_STRICT", "0")
        compiler = HLFCompiler()
        result = compiler.compile(SWARM_SOURCE)
        assert result["errors"] == []
        ast = result["ast"]
        assert ast["kind"] == "program"
        stmts = ast["statements"]
        kinds = [s["kind"] for s in stmts]
        assert kinds.count("call_stmt") == 4  # 3 spawn + 1 wait

    def test_swarm_bytecode_encodes(self, monkeypatch) -> None:
        monkeypatch.setenv("HLF_STRICT", "0")
        compiler = HLFCompiler()
        ast = compiler.compile(SWARM_SOURCE)["ast"]
        bytecode = HLFBytecode().encode(ast)
        assert isinstance(bytecode, bytes)
        assert len(bytecode) > 0

    def test_swarm_executes_and_spawns_agents(self, monkeypatch) -> None:
        monkeypatch.setenv("HLF_STRICT", "0")
        compiler = HLFCompiler()
        ast = compiler.compile(SWARM_SOURCE)["ast"]
        bytecode = HLFBytecode().encode(ast)
        runtime = HLFRuntime()
        vm_result = runtime.run(
            bytecode,
            gas_limit=500,
            variables={"_spawner_backend": "asyncio", "_tier": "operators"},
        )
        assert vm_result["status"] == "ok", f"VM error: {vm_result.get('error')}"
        side_effects = vm_result.get("side_effects", [])
        # The spawn_agent handler emits a detailed effect with agent_id;
        # the generic effects recorder also emits a summary with fn/args.
        # We want the detailed ones for counting actual spawns.
        spawn_effects = [e for e in side_effects if e.get("type") == "spawn_agent" and "agent_id" in e]
        assert len(spawn_effects) == 3
        agent_ids = {e["agent_id"] for e in spawn_effects}
        assert agent_ids == {"alpha", "beta", "gamma"}

    def test_swarm_wait_all_returns_results(self, monkeypatch) -> None:
        monkeypatch.setenv("HLF_STRICT", "0")
        compiler = HLFCompiler()
        ast = compiler.compile(SWARM_SOURCE)["ast"]
        bytecode = HLFBytecode().encode(ast)
        runtime = HLFRuntime()
        vm_result = runtime.run(
            bytecode,
            gas_limit=500,
            variables={"_spawner_backend": "asyncio", "_tier": "operators"},
        )
        assert vm_result["status"] == "ok"
        top = vm_result["result"]
        # wait_all_agents returns a dict of agent_id -> result
        assert isinstance(top, dict)
        assert "alpha" in top
        assert "beta" in top
        assert "gamma" in top
        for agent_id in ("alpha", "beta", "gamma"):
            res = top[agent_id]
            assert res["status"] == "complete"
            assert f"asyncio agent {agent_id} done" in res["stdout"]
